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

# --- NSE DATA LAYER SETTINGS ---
NSE_SYMBOLS = ["RELIANCE", "HDFCBANK", "TCS", "INFY", "ICICIBANK",
               "KOTAKBANK", "HINDUNILVR", "AXISBANK", "SBIN", 
               "BAJFINANCE", "TATASTEEL", "JSWSTEEL", "ONGC"]

NSE_INDICES = ["^NSEI", "^NSEBANK"]  # Yahoo Finance format

MARKET_OPEN  = "09:15"
MARKET_CLOSE = "15:30"
SQUAREOFF_TIME = "15:15"

LOT_SIZES = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
}
