from typing import List, Dict

def run_backtest(rows: List[Dict], signals: List[Dict], initial_capital: float = 10000.0) -> List[Dict]:
    """
    Simulates a portfolio moving in and out of the market based on daily signals.
    
    Assumptions:
    - No transaction costs (slippage/commissions).
    - Trades are executed at the day's close price.
    - Fractional shares are allowed (buying implies spending all available cash).
    - Position is binary: either 100% in the market or 100% in cash.
    """
    
    if len(rows) != len(signals):
        raise ValueError("Mismatch between length of data rows and signals.")
        
    cash = initial_capital
    shares = 0.0
    portfolio_history = []
    
    for i in range(len(rows)):
        current_price = rows[i]["close"]
        current_date = rows[i]["date"]
        signal = signals[i]["signal"]
        
        # Check if we should buy (signal == 1 and we have cash)
        # Note: If cash > 0, we assume we are not fully invested. 
        # (Though with fractional shares, cash drops to 0 after buying)
        # To avoid precision errors, we compare cash to a small threshold e.g. 0.01
        
        if signal == 1 and cash > 0.01:
            # Buy: spend all cash
            shares = cash / current_price
            cash = 0.0
            
        elif signal == 0 and shares > 0.0:
            # Sell: liquidate all shares
            cash = shares * current_price
            shares = 0.0
            
        # Calculate daily portfolio value
        portfolio_value = cash + (shares * current_price)
        
        portfolio_history.append({
            "date": current_date,
            "value": portfolio_value,
            "signal": signal,
            "price": current_price
        })
        
    return portfolio_history
