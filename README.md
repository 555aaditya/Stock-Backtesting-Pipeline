# Stock Backtesting Pipeline

A from-scratch, purely Python stock trading algorithmic backtesting system built strictly with standard built-in libraries (with the exception of `requests` and `matplotlib` for charts). We specifically avoid shortcuts like `pandas`, `numpy`, `yfinance`, and `Backtrader` to build our own custom event-driven vector math models.

## Features

- **Data Engineering Layer**: Built-in HTTP REST API connector parsing deeply nested JSON payloads from Yahoo Finance API directly into a local optimized SQLite DB.
- **Indicators Engine**: In-house mathematical logic for `SMA`, `EMA`, `RSI`, and `MACD` using rolling window slices and functional arrays.
- **Backtesting Simulation**: Simulates exact entries, exits, portfolio capital changes tracking fractional shares at closing price logic.
- **Metrics Math**: Financial ratios calculated from scratch (CAGR, Max Drawdown, Sharpe Ratio, Total Returns).
- **Visualization**: Modularly generated equity plot lines and interactive price charts overlapping indicator trigger signals.

## Project Structure

```text
stock-backtest/
├── data/                   # SQLite database and Matplotlib PNG charts
├── src/
│   ├── fetcher.py          # API request handler and JSON parser
│   ├── storage.py          # SQLite persistence and querying
│   ├── indicators.py       # Math logic for technical indicators
│   ├── strategy.py         # Strategy algorithms evaluating indicators into buy/sell signals
│   ├── backtester.py       # Portfolio simulation iterating on historical signals
│   ├── metrics.py          # Performance mathematical evaluator
│   └── charts.py           # Matplotlib automated rendering functions
├── tests/                  # Pytest modular environment
├── config.py               # Constants, logic configs, constraints
├── run.py                  # CLI Executable Pipeline
├── requirements.txt
└── README.md
```

## How to Setup and Run

### 1. Installation
Ensure Python 3.9+ is installed, then build the virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the full pipeline
Automatically fetch the AAPL stock history, compute the indicators, run two concurrent strategies (`sma_crossover`, `rsi_mean_reversion`), calculate metrics and drop all generated visualization graphs in `/data/`:
```bash
python run.py --ticker AAPL
```

### Example Terminal Output
```
INFO: --- Processing AAPL ---
INFO: Fetching data for AAPL from API (2020-01-01 to 2024-01-01)...
INFO: Running strategy: sma_crossover

[AAPL | sma_crossover] Performance:
  Total Return: 66.77%
  CAGR: 13.67%
  Max Drawdown: 29.00%
  Sharpe Ratio: 0.52
----------------------------------------
INFO: Running strategy: rsi_mean_reversion

[AAPL | rsi_mean_reversion] Performance:
  Total Return: 4.68%
  CAGR: 1.15%
  Max Drawdown: 29.90%
  Sharpe Ratio: 0.02
----------------------------------------
```

### 3. Run Pipeline Diagnostics / Unit Tests
All math algorithms (from `cagr` metrics to the calculation of `EMA` multiplier functions mapping) are isolated and confirmed against absolute constants.
```bash
python -m pytest tests/ -v
```

## Strategies Included

- **SMA Crossover**: When a short-term Moving Average (e.g. 20-day) crosses over a long-term Moving Average (e.g. 50-day), it signals a buy since the current trend is faster than the macro trend. We sell when it drops below.
- **RSI Mean-Reversion**: Uses a strict oversell signal (RSI < 30) to execute an instant 100% long entry positioning, seeking a rebound bounce. Exits cleanly once overbought (RSI > 70).

## Known Limitations
- Does not inject algorithmic slippage or specific retail transaction fees (simplification).
- Backtester operates off End of Day (EOD) Close prices, restricting day-trading models.
- Does not prevent look-ahead bias from macro splits/dividends not adequately adjusted within historical closing prices (relying entirely on Yahoo's adjusted data structures natively).

## Next Steps / Future Expansions
- Multi-asset correlation portfolio optimization.
- Add Short Selling models (Signal == -1).
- Expand metrics logic to support rolling Alpha/Beta analysis.
