import math
from typing import List

def total_return(values: List[float]) -> float:
    """Calculates total percentage return."""
    if not values or values[0] == 0:
        return 0.0
    start = values[0]
    end = values[-1]
    return ((end - start) / start) * 100.0

def cagr(values: List[float], trading_days: int = 252) -> float:
    """Calculates Compound Annual Growth Rate as a percentage."""
    if not values or values[0] == 0:
        return 0.0
    start = values[0]
    end = values[-1]
    years = len(values) / trading_days
    
    if years <= 0:
        return 0.0
        
    return (math.pow(end / start, 1 / years) - 1.0) * 100.0

def max_drawdown(values: List[float]) -> float:
    """Calculates maximum peak-to-trough drop (as a positive percentage)."""
    if not values:
        return 0.0
        
    peak = values[0]
    max_dd = 0.0
    
    for val in values:
        if val > peak:
            peak = val
        drawdown = (peak - val) / peak
        if drawdown > max_dd:
            max_dd = drawdown
            
    return max_dd * 100.0

def sharpe_ratio(values: List[float], annual_risk_free_rate: float = 0.04) -> float:
    """Calculates the annualized Sharpe Ratio of the portfolio relative returns."""
    if len(values) < 2:
        return 0.0
        
    daily_returns = []
    for i in range(1, len(values)):
        prev = values[i - 1]
        curr = values[i]
        ret = (curr - prev) / prev if prev != 0 else 0
        daily_returns.append(ret)
        
    daily_rf = annual_risk_free_rate / 252.0
    
    # Mean of returns
    mean_return = sum(daily_returns) / len(daily_returns)
    
    # Standard deviation of returns (population variance)
    variance_sum = sum((r - mean_return) ** 2 for r in daily_returns)
    variance = variance_sum / len(daily_returns)
    std_dev = math.sqrt(variance)
    
    if std_dev == 0:
        return 0.0
        
    daily_sharpe = (mean_return - daily_rf) / std_dev
    return daily_sharpe * math.sqrt(252)
