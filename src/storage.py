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
    with get_connection() as conn:
        conn.execute(query)

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
