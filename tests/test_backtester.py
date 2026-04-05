from src.backtester import run_backtest

def test_backtester_all_flat():
    rows = [
        {"date": "Day1", "close": 100},
        {"date": "Day2", "close": 110},
        {"date": "Day3", "close": 120},
    ]
    signals = [
        {"date": "Day1", "signal": 0},
        {"date": "Day2", "signal": 0},
        {"date": "Day3", "signal": 0},
    ]
    
    result = run_backtest(rows, signals, initial_capital=1000)
    
    assert len(result) == 3
    # Value should stay at exactly 1000
    for r in result:
        assert r["value"] == 1000

def test_backtester_all_buy():
    rows = [
        {"date": "Day1", "close": 100},
        {"date": "Day2", "close": 110},
        {"date": "Day3", "close": 120},
    ]
    signals = [
        {"date": "Day1", "signal": 1},
        {"date": "Day2", "signal": 1},
        {"date": "Day3", "signal": 1},
    ]
    
    result = run_backtest(rows, signals, initial_capital=1000)
    
    assert len(result) == 3
    
    # Day 1: buy at 100. 1000 / 100 = 10 shares. 
    # Value = 0 cash + 10 * 100 = 1000
    assert result[0]["value"] == 1000
    
    # Day 2: hold 10 shares at 110
    # Value = 10 * 110 = 1100
    assert result[1]["value"] == 1100
    
    # Day 3: hold 10 shares at 120
    # Value = 10 * 120 = 1200
    assert result[2]["value"] == 1200

def test_backtester_buy_sell():
    rows = [
        {"date": "Day1", "close": 100},
        {"date": "Day2", "close": 110},
        {"date": "Day3", "close": 120},
    ]
    signals = [
        {"date": "Day1", "signal": 1}, # Buy
        {"date": "Day2", "signal": 0}, # Sell
        {"date": "Day3", "signal": 0}, # Hold Cash
    ]
    
    result = run_backtest(rows, signals, initial_capital=1000)
    
    assert len(result) == 3
    
    # Day 1: buy at 100 -> 10 shares. Value = 1000
    assert result[0]["value"] == 1000
    
    # Day 2: sell at 110. Cash = 10 * 110 = 1100. Value = 1100
    assert result[1]["value"] == 1100
    
    # Day 3: in cash. Value = 1100
    assert result[2]["value"] == 1100
