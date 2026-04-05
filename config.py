import os

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "stocks.db")

# --- BACKTESTING DEFAULTS ---
INITIAL_CAPITAL = 10000.0
RISK_FREE_RATE = 0.07  # ~7% annual for Indian markets

# --- PORTFOLIO SETTINGS ---
# Default list of tickers to watch and backtest
WATCHLIST = [
    "AAPL",
    "MSFT",
    "GOOG",
    "SPY",
]

# Analysis boundaries
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = "2024-01-01"
