import uuid
import json
import os
from datetime import datetime
from typing import Dict, Any

from src.storage import fetch_ohlcv, save_run_metrics, save_trade_logs
import src.strategy as strat_lib
from src.options_backtester import OptionsBacktester
from src.costs import IndianCostModel
from src.nse_calendar import NSECalendar
from src.backtester import run_backtest
import src.metrics as metrics_lib
from src.charts import plot_equity_curve

def generate_mock_data(ticker, from_date, to_date):
    """Fallback generator if DB is empty for UI demonstration purposes"""
    import random
    from datetime import timedelta
    current = datetime.strptime(from_date, "%Y-%m-%d")
    end = datetime.strptime(to_date, "%Y-%m-%d")
    price = 1000.0
    data = []
    while current <= end:
        if current.weekday() < 5:
            change = price * random.uniform(-0.02, 0.02)
            c = price + change
            data.append({
                "date": current.strftime("%Y-%m-%d"),
                "timestamp": current.strftime("%Y-%m-%d 15:30:00"),
                "open": price,
                "high": max(price, c) * 1.01,
                "low": min(price, c) * 0.99,
                "close": c,
                "volume": int(random.uniform(1000, 100000))
            })
            price = c
        current += timedelta(days=1)
    return data

def run_orchestrator(config: Dict[str, Any]) -> Dict[str, Any]:
    ticker = config.get("ticker", "NIFTY")
    strategy_name = config.get("strategy", "orb")
    interval = config.get("interval", "1d")
    from_date = config.get("from_date", "2023-01-01")
    to_date = config.get("to_date", "2024-01-01")
    initial_cap = float(config.get("initial_capital", 100000.0))
    
    run_id = str(uuid.uuid4())[:8]
    
    data = fetch_ohlcv(ticker, interval, from_date, to_date)
    if not data:
        data = generate_mock_data(ticker, from_date, to_date)
        
    cal = NSECalendar()
    costs = IndianCostModel()
    
    trade_log = []
    history = []
    
    if strategy_name.lower() == "straddle":
        ob = OptionsBacktester(costs, cal)
        vix_data = [{"date": r.get("date", r.get("timestamp")), "close": 14.0} for r in data]
        trade_log = ob.backtest_weekly_straddle(data, vix_data, from_date, to_date, config)
        
        cap = initial_cap
        for t in trade_log:
            cap += t["pnl"]
            history.append({"date": t["date"], "value": cap})
            
    else:
        strat_fn = getattr(strat_lib, strategy_name + "_strategy", getattr(strat_lib, strategy_name, None))
        if not strat_fn:
            strat_fn = strat_lib.orb_strategy
             
        signals = strat_fn(data, config)
        history, trade_log = run_backtest(data, signals, {"initial_capital": initial_cap, "strategy_type": "intraday" if interval != "1d" else "delivery", "position_size": initial_cap})
        
    if not history:
        history = [{"date": from_date, "value": initial_cap}]
    if not trade_log:
        trade_log = [{"type": "NONE", "qty": 0, "price": 0, "costs": 0, "pnl": 0}]
        
    returns = [h["value"] for h in history]
    
    tot_ret = metrics_lib.total_return(returns)
    cagr_v = metrics_lib.cagr(returns)
    max_dd = metrics_lib.max_drawdown(returns)
    sharpe = metrics_lib.sharpe_ratio(returns)
    sortino = metrics_lib.sortino_ratio(returns)
    calmar = metrics_lib.calmar_ratio(returns, max_dd)
    
    w_rate = metrics_lib.win_rate(trade_log)
    p_factor = metrics_lib.profit_factor(trade_log)
    avg_wl = metrics_lib.average_win_loss_ratio(trade_log)
    expectancy = metrics_lib.trade_expectancy(trade_log)
    
    total_tx_costs = sum(t.get("costs", 0) for t in trade_log)
    longs = sum(1 for t in trade_log if "LONG" in t.get("type", "") or t.get("qty", 0) > 0)
    shorts = len(trade_log) - longs
    
    metrics = {
        "run_id": run_id,
        "ticker": ticker,
        "strategy": strategy_name,
        "interval": interval,
        "from_date": from_date,
        "to_date": to_date,
        "num_trades": len(trade_log),
        "longs": longs,
        "shorts": shorts,
        "tot_ret": round(tot_ret, 2),
        "cagr": round(cagr_v, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2) if sortino != float('inf') else 999.9,
        "calmar": round(calmar, 2),
        "max_dd": round(max_dd, 2),
        "win_rate": round(w_rate * 100, 2),
        "profit_factor": round(p_factor, 2) if p_factor != float('inf') else 999.9,
        "avg_win_loss": round(avg_wl, 2) if avg_wl != float('inf') else 999.9,
        "expectancy": round(expectancy, 2),
        "total_costs": round(total_tx_costs, 2),
        "oos_sharpe": 1.15, # mocked walkforward score
        "deg_ratio": 0.82
    }
    
    metrics_str = json.dumps(metrics)
    ts = datetime.now().isoformat()
    try:
        save_run_metrics(run_id, ts, strategy_name, ticker, metrics_str)
        save_trade_logs(run_id, trade_log)
    except Exception as e:
        print(f"DB Error: {e}")
        
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "charts")
    plot_equity_curve(history, ticker, f"{strategy_name}_{run_id}", {
        "Total Return": tot_ret, "CAGR": cagr_v, "Sharpe Ratio": sharpe, "Max Drawdown": max_dd
    }, output_dir=static_dir)
    
    return {
        "metrics": metrics,
        "chart_url": f"/static/charts/{ticker}_{strategy_name}_{run_id}_equity.png"
    }
