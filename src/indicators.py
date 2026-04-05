from typing import List, Optional, Tuple

def sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Simple Moving Average.
    Average of the last `period` prices.
    Returns None for the first `period - 1` indexes.
    """
    result = []
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        else:
            window = prices[i - period + 1 : i + 1]
            result.append(sum(window) / period)
    return result

def ema(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Exponential Moving Average.
    k = 2 / (period + 1)
    Seeds the first valid EMA with the SMA of the first `period` prices.
    """
    result = []
    k = 2.0 / (period + 1)
    
    for i in range(len(prices)):
        if i < period - 1:
            result.append(None)
        elif i == period - 1:
            window = prices[0 : period]
            result.append(sum(window) / period)
        else:
            prev_ema = result[-1]
            current_ema = (prices[i] * k) + (prev_ema * (1 - k))
            result.append(current_ema)
    return result

def rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Relative Strength Index.
    Calculates the RSI based on a rolling mean of gains and losses.
    Returns None for the first `period` values.
    """
    result = []
    gains = []
    losses = []
    
    for i in range(len(prices)):
        if i == 0:
            result.append(None)
            continue
            
        change = prices[i] - prices[i - 1]
        gains.append(change if change > 0 else 0.0)
        losses.append(abs(change) if change < 0 else 0.0)
        
        # We need `period` full days of changes
        if i < period:
            result.append(None)
        else:
            # Getting the last `period` items from the gains/losses arrays
            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period
            
            if avg_loss == 0:
                result.append(100.0)
            else:
                rs = avg_gain / avg_loss
                result.append(100.0 - (100.0 / (1.0 + rs)))
                
    return result

def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """
    Moving Average Convergence Divergence.
    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line, signal)
    Histogram = MACD Line - Signal Line
    """
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    
    macd_line = []
    for i in range(len(prices)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(ema_fast[i] - ema_slow[i])
            
    # Calculate Signal Line
    # We strip the leading Nones from the MACD line to feed it safely into the EMA
    valid_macd = [x for x in macd_line if x is not None]
    
    if not valid_macd:
        return (
            [None] * len(prices),
            [None] * len(prices),
            [None] * len(prices),
        )
        
    signal_valid = ema(valid_macd, signal)
    
    # Pad the Nones back in
    num_nones = len(prices) - len(valid_macd)
    signal_line = ([None] * num_nones) + signal_valid
    
    # Histogram
    histogram = []
    for i in range(len(prices)):
        if macd_line[i] is None or signal_line[i] is None:
            histogram.append(None)
        else:
            histogram.append(macd_line[i] - signal_line[i])
            
    return macd_line, signal_line, histogram
