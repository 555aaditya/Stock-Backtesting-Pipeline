import sqlite3
import os
from typing import List, Dict

# Import the DB_PATH from our config
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database."""
    # Ensure directory exists before connecting
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # We use PARSE_DECLTYPES so we could potentially parse dates,
    # but sticking to TEXT is safer per project requirements.
    # Return dictionary-like rows for easy manipulation
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Creates the necessary tables if they don't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS prices (
        ticker TEXT,
        date   TEXT,
        open   REAL,
        high   REAL,
        low    REAL,
        close  REAL,
        volume INTEGER,
        PRIMARY KEY (ticker, date)
    )
    """
    query_runs = """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT,
        strategy TEXT,
        ticker TEXT,
        metrics TEXT
    )
    """
    query_trades = """
    CREATE TABLE IF NOT EXISTS trade_logs (
        run_id TEXT,
        date TEXT,
        type TEXT,
        qty REAL,
        price REAL,
        costs REAL,
        pnl REAL,
        reason TEXT
    )
    """
    with get_connection() as conn:
        conn.execute(query)
        conn.execute(query_runs)
        conn.execute(query_trades)

def save_prices(ticker: str, rows: List[Dict]) -> None:
    """
    Saves a list of OHLCV dictionaries into the database.
    Uses INSERT OR REPLACE to handle duplicates if run multiple times.
    """
    if not rows:
        return
        
    query = """
    INSERT OR REPLACE INTO prices 
    (ticker, date, open, high, low, close, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    # Extract tuples for executemany
    data = [
        (
            ticker,
            row["date"],
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"]
        ) for row in rows
    ]
    
    with get_connection() as conn:
        conn.executemany(query, data)

def load_prices(ticker: str, start_date: str, end_date: str) -> List[Dict]:
    """
    Loads price data for a ticker between two dates.
    Dates should be inclusive.
    """
    query = """
    SELECT date, open, high, low, close, volume 
    FROM prices
    WHERE ticker = ? AND date >= ? AND date <= ?
    ORDER BY date ASC
    """
    
    with get_connection() as conn:
        cursor = conn.execute(query, (ticker, start_date, end_date))
        # sqlite3.Row makes this easy to convert directly to a dict
        results = [dict(row) for row in cursor.fetchall()]
        
    return results

def create_ohlcv_table(interval: str) -> None:
    """Creates a specific table for an interval (e.g. ohlcv_1m, ohlcv_5m, ohlcv_eod)."""
    table_name = f"ohlcv_{interval}"
    query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        ticker TEXT,
        date   TEXT,
        open   REAL,
        high   REAL,
        low    REAL,
        close  REAL,
        volume INTEGER,
        PRIMARY KEY (ticker, date)
    )
    """
    with get_connection() as conn:
        conn.execute(query)

def store_ohlcv(symbol: str, interval: str, data: List[Dict]) -> None:
    """Saves OHLCV data into interval-specific tables."""
    if not data:
        return
    
    table_name = f"ohlcv_{interval}"
    query = f"""
    INSERT OR REPLACE INTO {table_name} 
    (ticker, date, open, high, low, close, volume)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    
    records = [
        (
            symbol,
            row.get("date") or row.get("timestamp"),
            row["open"],
            row["high"],
            row["low"],
            row["close"],
            row["volume"]
        ) for row in data
    ]
    
    with get_connection() as conn:
        conn.executemany(query, records)

def fetch_ohlcv(symbol: str, interval: str, from_date: str, to_date: str) -> List[Dict]:
    """Loads price data from an interval-specific table."""
    table_name = f"ohlcv_{interval}"
    query = f"""
    SELECT date, open, high, low, close, volume 
    FROM {table_name}
    WHERE ticker = ? AND date >= ? AND date <= ?
    ORDER BY date ASC
    """
    
    try:
        with get_connection() as conn:
            cursor = conn.execute(query, (symbol, from_date, to_date))
            results = [dict(row) for row in cursor.fetchall()]
            
        return results
    except sqlite3.OperationalError:
        return []

def create_fo_ban_table() -> None:
    """Creates table for FnO Ban List."""
    query = """
    CREATE TABLE IF NOT EXISTS fo_ban (
        date   TEXT,
        symbol TEXT,
        PRIMARY KEY (date, symbol)
    )
    """
    with get_connection() as conn:
        conn.execute(query)

def store_fo_ban_list(date: str, symbols: List[str]) -> None:
    """Stores list of symbols in FnO ban for a specific date."""
    if not symbols:
        return
    query = """
    INSERT OR REPLACE INTO fo_ban (date, symbol)
    VALUES (?, ?)
    """
    records = [(date, symbol) for symbol in symbols]
    with get_connection() as conn:
        conn.executemany(query, records)

def is_in_fo_ban(symbol: str, date: str) -> bool:
    """Checks if a symbol was in FnO ban on a specific date."""
    query = """
    SELECT 1 FROM fo_ban
    WHERE symbol = ? AND date = ?
    """
    with get_connection() as conn:
        cursor = conn.execute(query, (symbol, date))
        return cursor.fetchone() is not None

def save_run_metrics(run_id: str, timestamp: str, strategy: str, ticker: str, metrics_json: str) -> None:
    query = """
    INSERT INTO backtest_runs (run_id, timestamp, strategy, ticker, metrics)
    VALUES (?, ?, ?, ?, ?)
    """
    with get_connection() as conn:
        conn.execute(query, (run_id, timestamp, strategy, ticker, metrics_json))

def save_trade_logs(run_id: str, logs: List[Dict]) -> None:
    if not logs:
        return
    query = """
    INSERT INTO trade_logs (run_id, date, type, qty, price, costs, pnl, reason)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    records = [
        (
            run_id, 
            lg.get("date", lg.get("time")), 
            lg.get("type"), 
            lg.get("qty", 1), 
            lg.get("price", 0), 
            lg.get("costs", 0), 
            lg.get("pnl", 0), 
            lg.get("reason", "")
        ) for lg in logs
    ]
    with get_connection() as conn:
        conn.executemany(query, records)

if __name__ == "__main__":
    from src.fetcher import fetch_ohlcv
    
    # Manual test
    print("Testing init_db()...")
    init_db()
    
    print("Fetching AAPL data for db test...")
    rows = fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31")
    
    print(f"Saving {len(rows)} rows to the DB...")
    save_prices("AAPL", rows)
    
    print("Loading prices from DB...")
    loaded = load_prices("AAPL", "2023-01-01", "2023-12-31")
    
    if loaded and len(loaded) == len(rows):
        print(f"✓ Success! DB returned {len(loaded)} rows.")
        print(f"First loaded row: {loaded[0]}")
    else:
        print(f"✗ Failed! Expected {len(rows)} but got {len(loaded)}")
