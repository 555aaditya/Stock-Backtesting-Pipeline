from typing import List, Dict, Tuple
import copy
from config import MARKET_OPEN, MARKET_CLOSE, SQUAREOFF_TIME
from src.costs import IndianCostModel

def size_fixed_percent(capital: float, risk_percent: float = 0.01) -> float:
    """Risk 1% of capital per trade"""
    return capital * risk_percent

def size_kelly(capital: float, win_rate: float, avg_win: float, avg_loss: float, fraction: float = 0.25) -> float:
    """Quarter Kelly Criterion"""
    if avg_loss == 0.0:
        return 0.0
    b = avg_win / avg_loss
    if b == 0:
        return 0.0
    f = (b * win_rate - (1.0 - win_rate)) / b
    return capital * max(0.0, f * fraction)

def size_volatility_adjusted(capital: float, current_vol: float, target_vol: float = 0.15) -> float:
    """Scale inversely to volatility"""
    if current_vol == 0.0:
        return 0.0
    return capital * (target_vol / current_vol)

def run_backtest(rows: List[Dict], signals: List[Dict], config: Dict = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Simulates portfolio with long/short support, stop loss, and intraday constraint.
    """
    if config is None:
        config = {}
        
    initial_capital = config.get("initial_capital", 10000.0)
    strategy_type = config.get("strategy_type", "delivery")
    hard_stop_pct = config.get("stop_pct", None)
    take_profit_pct = config.get("take_profit_pct", None)
    trailing_stop_pct = config.get("trailing_stop_pct", None)
    
    cash = initial_capital
    position = 0.0 # positive for long shares, negative for short shares
    entry_price = 0.0
    highest_price = 0.0
    lowest_price = 0.0
    
    portfolio_history = []
    trade_log = []
    
    cost_model = IndianCostModel()

    for i in range(len(rows)):
        current_price = rows[i]["close"]
        current_date_time = rows[i].get("timestamp") or rows[i].get("date")
        
        signal_data = signals[i]
        # In strategy.py returns list of dicts, we extract "signal"
        signal_val = signal_data.get("signal", 0)
        
        force_exit = False
        exit_reason = ""
        
        # Check intraday square-off
        if strategy_type == "intraday":
            if " " in current_date_time:
                time_part = current_date_time.split(" ")[1][:5]
                if time_part >= SQUAREOFF_TIME:
                    force_exit = True
                    exit_reason = "SQUAREOFF"
                    
        # Check Stop Loss / Take profit
        if position != 0 and not force_exit:
            if position > 0:
                highest_price = max(highest_price, current_price)
                if hard_stop_pct and current_price <= entry_price * (1 - hard_stop_pct):
                    force_exit = True
                    exit_reason = "HARD_STOP"
                elif trailing_stop_pct and current_price <= highest_price * (1 - trailing_stop_pct):
                    force_exit = True
                    exit_reason = "TRAILING_STOP"
                elif take_profit_pct and current_price >= entry_price * (1 + take_profit_pct):
                    force_exit = True
                    exit_reason = "TAKE_PROFIT"
            elif position < 0:
                lowest_price = min(lowest_price, current_price)
                if hard_stop_pct and current_price >= entry_price * (1 + hard_stop_pct):
                    force_exit = True
                    exit_reason = "HARD_STOP"
                elif trailing_stop_pct and current_price >= lowest_price * (1 + trailing_stop_pct):
                    force_exit = True
                    exit_reason = "TRAILING_STOP"
                elif take_profit_pct and current_price <= entry_price * (1 - take_profit_pct):
                    force_exit = True
                    exit_reason = "TAKE_PROFIT"

        if force_exit:
            signal_val = 0 # Force a signal 0 to exit
        
        # Execute orders
        if position > 0 and signal_val <= 0:
            # Sell long position
            qty = position
            if strategy_type == "intraday":
                costs = cost_model.calculate_equity_intraday(entry_price, current_price, qty)
            else:
                costs = cost_model.calculate_equity_delivery(entry_price, current_price, qty)
            
            cash += (qty * current_price) - costs["total_costs"]
            trade_log.append({
                "type": "EXIT_LONG", "price": current_price, "qty": qty, 
                "time": current_date_time, "reason": exit_reason or "SIGNAL", 
                "costs": costs["total_costs"]
            })
            position = 0.0
            
        elif position < 0 and signal_val >= 0:
            # Buy to cover short position
            qty = abs(position)
            if strategy_type == "intraday":
                costs = cost_model.calculate_equity_intraday(current_price, entry_price, qty)
            else:
                costs = cost_model.calculate_equity_delivery(current_price, entry_price, qty)
                
            cash -= (qty * current_price) + costs["total_costs"]
            trade_log.append({
                "type": "EXIT_SHORT", "price": current_price, "qty": qty, 
                "time": current_date_time, "reason": exit_reason or "SIGNAL", 
                "costs": costs["total_costs"]
            })
            position = 0.0
            
        # Enter new positions
        if position == 0 and signal_val != 0 and not force_exit:
            invest_amount = config.get("position_size", cash)
            invest_amount = min(invest_amount, cash)
            
            qty = invest_amount / current_price
            
            if signal_val == 1:
                cash -= invest_amount
                position = qty
                entry_price = current_price
                highest_price = current_price
                trade_log.append({
                    "type": "ENTER_LONG", "price": current_price, "qty": qty, 
                    "time": current_date_time, "reason": "SIGNAL"
                })
            elif signal_val == -1:
                # Simulated Short Sale Collateral (add cash equivalent to sale, then track PnL)
                cash += invest_amount
                position = -qty
                entry_price = current_price
                lowest_price = current_price
                trade_log.append({
                    "type": "ENTER_SHORT", "price": current_price, "qty": qty, 
                    "time": current_date_time, "reason": "SIGNAL"
                })
                
        # Calculate daily portfolio value
        portfolio_value = cash
        if position > 0:
            portfolio_value += position * current_price
        elif position < 0:
            portfolio_value -= abs(position) * current_price 
            
        portfolio_history.append({
            "date": current_date_time,
            "value": portfolio_value,
            "signal": signal_val,
            "price": current_price
        })
        
    return portfolio_history, trade_log
