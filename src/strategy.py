from typing import List, Dict
from src.indicators import sma, rsi

def sma_crossover_strategy(rows: List[Dict], short_window: int = 20, long_window: int = 50) -> List[Dict]:
    """
    SMA Crossover strategy.
    signal = 1 if SMA(short) > SMA(long)
    signal = 0 if SMA(short) < SMA(long)
    Holds previous signal on equality or when SMAs aren't available yet.
    """
    prices = [row["close"] for row in rows]
    short_sma = sma(prices, short_window)
    long_sma = sma(prices, long_window)
    
    signals = []
    current_signal = 0
    
    for i in range(len(rows)):
        s_val = short_sma[i]
        l_val = long_sma[i]
        
        if s_val is not None and l_val is not None:
            if s_val > l_val:
                current_signal = 1
            elif s_val < l_val:
                current_signal = 0
                
        signals.append({
            "date": rows[i]["date"],
            "signal": current_signal
        })
        
    return signals


def rsi_mean_reversion_strategy(rows: List[Dict], rsi_period: int = 14, overbought: float = 70.0, oversold: float = 30.0) -> List[Dict]:
    """
    RSI Mean Reversion.
    Buy (1) when RSI drops below oversold threshold.
    Sell (0) when RSI rises above overbought threshold.
    Otherwise hold the current position.
    """
    prices = [row["close"] for row in rows]
    rsi_vals = rsi(prices, rsi_period)
    
    signals = []
    current_position = 0  # Start flat
    
    for i in range(len(rows)):
        r_val = rsi_vals[i]
        
        if r_val is not None:
            if r_val < oversold:
                current_position = 1
            elif r_val > overbought:
                current_position = 0
                
        signals.append({
            "date": rows[i]["date"],
            "signal": current_position
        })
        
    return signals
