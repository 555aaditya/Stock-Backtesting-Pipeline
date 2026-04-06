import os

# --- PATHS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "stocks.db")

# --- BACKTESTING DEFAULTS ---
INITIAL_CAPITAL = 100000.0  # INR
RISK_FREE_RATE = 0.07  # ~7% annual for Indian markets (based on 10Y G-Sec)

# --- PORTFOLIO SETTINGS ---
DEFAULT_START_DATE = "2020-01-01"
DEFAULT_END_DATE = "2024-01-01"

# --- NSE MARKET TIMINGS ---
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
SQUAREOFF_TIME = "15:15"

# --- MCX MARKET TIMINGS ---
MCX_OPEN = "09:00"
MCX_CLOSE_NORMAL = "23:30"   # Non-agri commodities (Nov-Mar: 23:30, Apr-Oct: 23:55)
MCX_CLOSE_DST = "23:55"      # During US daylight saving
MCX_AGRI_CLOSE = "17:00"     # Agricultural commodities

# --- NSE CDS (Currency Derivatives) TIMINGS ---
CDS_OPEN = "09:00"
CDS_CLOSE = "17:00"

# --- NSE F&O LOT SIZES (updated periodically by NSE) ---
LOT_SIZES = {
    # Index derivatives
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 40,
    "MIDCPNIFTY": 50,
    # Stock futures (representative — actual lot sizes vary per stock)
    "RELIANCE": 250,
    "TCS": 150,
    "HDFCBANK": 550,
    "ICICIBANK": 700,
    "INFY": 300,
    "SBIN": 750,
    "BAJFINANCE": 125,
    "AXISBANK": 600,
    "TATAMOTORS": 575,
    "TATASTEEL": 1500,
    "MARUTI": 100,
    "BHARTIARTL": 475,
    "ITC": 1600,
    "HINDUNILVR": 300,
    "KOTAKBANK": 400,
    "LT": 225,
    "M&M": 350,
    "SUNPHARMA": 350,
    "DRREDDY": 125,
    "WIPRO": 1500,
    "ADANIENT": 250,
    "HCLTECH": 350,
    "TITAN": 175,
    "DLF": 1650,
    "INDIGO": 300,
    "NTPC": 2250,
    "POWERGRID": 2700,
    "COALINDIA": 1200,
    "ONGC": 1925,
    "BPCL": 1800,
    "CIPLA": 325,
    "ULTRACEMCO": 50,
    "DIVISLAB": 75,
    "ASIANPAINT": 200,
    "NESTLEIND": 25,
    "EICHERMOT": 175,
    "HEROMOTOCO": 150,
    "GRASIM": 275,
    "HINDALCO": 1075,
    "INDUSINDBK": 450,
    "BRITANNIA": 100,
    "APOLLOHOSP": 125,
    "TATACONSUM": 450,
    "BAJAJ-AUTO": 125,
    "LTIM": 150,
    "TECHM": 400,
    "JSWSTEEL": 675,
    "BAJAJFINSV": 375,
    "HDFCLIFE": 850,
    "SBILIFE": 500,
    "VEDL": 1550,
    "ZOMATO": 3750,
    "PNB": 6000,
    "BANKBARODA": 2925,
    "TATAPOWER": 2700,
    "YESBANK": 10000,
    "IDFCFIRSTB": 7500,
    "HAL": 150,
    "BEL": 3300,
    "IRFC": 5000,
}

# --- MCX LOT SIZES ---
MCX_LOT_SIZES = {
    "GOLD": 100,          # grams
    "GOLDM": 10,          # grams
    "GOLDGUINEA": 8,      # grams
    "GOLDPETAL": 1,       # gram
    "SILVER": 30,         # kg
    "SILVERM": 5,         # kg
    "SILVERMIC": 1,       # kg
    "CRUDEOIL": 100,      # barrels
    "CRUDEOILM": 10,      # barrels
    "NATURALGAS": 1250,   # mmBtu
    "COPPER": 2500,       # kg
    "ZINC": 5000,         # kg
    "LEAD": 5000,         # kg
    "NICKEL": 1500,       # kg
    "ALUMINIUM": 5000,    # kg
    "COTTON": 25,         # bales
    "MENTHAOIL": 360,     # kg
    "CPO": 10,            # MT (metric tonnes)
}

# --- MCX TICK SIZES (INR per unit) ---
MCX_TICK_SIZES = {
    "GOLD": 1.0,          # Rs 1 per gram
    "GOLDM": 1.0,
    "GOLDGUINEA": 1.0,
    "GOLDPETAL": 1.0,
    "SILVER": 1.0,        # Rs 1 per kg
    "SILVERM": 1.0,
    "SILVERMIC": 1.0,
    "CRUDEOIL": 1.0,      # Rs 1 per barrel
    "CRUDEOILM": 1.0,
    "NATURALGAS": 0.10,   # Rs 0.10 per mmBtu
    "COPPER": 0.05,       # Rs 0.05 per kg
    "ZINC": 0.05,
    "LEAD": 0.05,
    "NICKEL": 0.10,
    "ALUMINIUM": 0.05,
    "COTTON": 10.0,       # Rs 10 per bale
}

# --- NSE CDS (Currency Derivatives) LOT SIZES ---
CDS_LOT_SIZES = {
    "USDINR": 1000,   # USD 1000
    "EURINR": 1000,   # EUR 1000
    "GBPINR": 1000,   # GBP 1000
    "JPYINR": 100000, # JPY 100,000
}

# --- NCDEX LOT SIZES (metric tonnes unless noted) ---
NCDEX_LOT_SIZES = {
    "SOYBEAN": 100,       # quintals
    "SOYMEAL": 50,        # MT
    "SOYOIL": 10,         # MT
    "CASTORSEED": 10,     # MT
    "GUARSEED": 10,       # MT
    "GUARRGUM": 5,        # MT
    "JEERA": 3,           # MT
    "TURMERIC": 5,        # MT
    "CORIANDER": 10,      # MT
    "DHANIYA": 10,        # MT
    "CHANA": 10,          # MT
    "MUSTARD": 10,        # MT
    "BARLEY": 10,         # MT
    "WHEAT": 10,          # MT
    "MAIZE": 10,          # MT
    "COTTONSEED": 10,     # MT
}

# --- MARGIN REQUIREMENTS (approximate SPAN margins as % of contract value) ---
MARGIN_RATES = {
    # NSE Index F&O
    "NIFTY": 0.12,        # ~12%
    "BANKNIFTY": 0.14,    # ~14%
    "FINNIFTY": 0.13,
    "MIDCPNIFTY": 0.18,
    # MCX
    "GOLD": 0.05,         # ~5%
    "SILVER": 0.06,
    "CRUDEOIL": 0.08,
    "NATURALGAS": 0.12,
    "COPPER": 0.06,
    "ZINC": 0.07,
    "LEAD": 0.07,
    "NICKEL": 0.10,
    "ALUMINIUM": 0.06,
    # CDS
    "USDINR": 0.03,       # ~3%
    "EURINR": 0.04,
    "GBPINR": 0.04,
    "JPYINR": 0.04,
}

# --- EXCHANGE HOLIDAYS 2024 ---
NSE_HOLIDAYS_2024 = [
    "2024-01-26",  # Republic Day
    "2024-03-08",  # Maha Shivaratri
    "2024-03-25",  # Holi
    "2024-03-29",  # Good Friday
    "2024-04-11",  # Idul Fitr (Eid)
    "2024-04-14",  # Dr. Ambedkar Jayanti
    "2024-04-17",  # Ram Navami
    "2024-04-21",  # Mahavir Jayanti
    "2024-05-01",  # Maharashtra Day
    "2024-05-23",  # Buddha Purnima
    "2024-06-17",  # Bakri Eid
    "2024-07-17",  # Muharram
    "2024-08-15",  # Independence Day
    "2024-09-16",  # Milad-un-Nabi
    "2024-10-02",  # Mahatma Gandhi Jayanti
    "2024-11-01",  # Diwali (Laxmi Puja)
    "2024-11-15",  # Gurunanak Jayanti
    "2024-12-25",  # Christmas
]

MCX_HOLIDAYS_2024 = NSE_HOLIDAYS_2024  # MCX follows same holidays as NSE

# --- NSE WATCHLIST (default tickers) ---
WATCHLIST = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
]

# --- NSE INDICES (Yahoo Finance format) ---
NSE_INDICES = [
    "^NSEI",       # NIFTY 50
    "^NSEBANK",    # NIFTY Bank
    "^CNXIT",      # NIFTY IT
    "^CNXAUTO",    # NIFTY Auto
    "^CNXFMCG",    # NIFTY FMCG
    "^CNXMETAL",   # NIFTY Metal
    "^CNXPHARMA",  # NIFTY Pharma
    "^CNXREALTY",  # NIFTY Realty
    "^CNXENERGY",  # NIFTY Energy
    "^CNXINFRA",   # NIFTY Infrastructure
    "^INDIAVIX",   # India VIX
]

# --- API KEYS (set via environment variables) ---
# ALPHA_VANTAGE_API_KEY - for fallback equity data
# FRED_API_KEY - not used for India-only mode
# TWELVE_DATA_API_KEY - optional fallback
