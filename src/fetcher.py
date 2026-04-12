import os
import time
import requests
import zipfile
import io
import csv
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class YahooFinanceFetcher:
    """
    Fetches OHLCV data from Yahoo Finance API v8.
    
    The API returns deeply nested JSON. This class handles:
    - Date conversion (string → timestamp)
    - HTTP requests with User-Agent header
    - JSON parsing from the nested structure
    - None values for missing prices (holidays)
    - Error handling for network and API issues
    """
    
    # Default API endpoint. Override with MARKET_DATA_BASE_URL for OAuth-backed providers.
    BASE_URL = os.getenv(
        "MARKET_DATA_BASE_URL",
        "https://query1.finance.yahoo.com/v8/finance/chart"
    )

    # Optional OAuth 2.0 client credentials configuration.
    TOKEN_URL = os.getenv("OAUTH_TOKEN_URL")
    CLIENT_ID = os.getenv("OAUTH_CLIENT_ID")
    CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET")
    SCOPE = os.getenv("OAUTH_SCOPE")
    
    # Some tickers need a User-Agent to work
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    def __init__(self, timeout: int = 10):
        """
        Initialize the fetcher.
        
        Args:
            timeout (int): HTTP request timeout in seconds. Default 10.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0
    
    # =========================================================================
    # PUBLIC INTERFACE
    # =========================================================================
    
    def fetch(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        interval: str = "1d"
    ) -> List[Dict]:
        """
        Fetch OHLCV data for a ticker between two dates.
        
        Args:
            ticker (str): Stock symbol, e.g. "AAPL"
            start_date (str): Start date as "YYYY-MM-DD", e.g. "2023-01-01"
            end_date (str): End date as "YYYY-MM-DD", e.g. "2023-12-31"
            interval (str): Data interval. "1d" for daily (only option for this project)
        
        Returns:
            List[Dict]: List of OHLCV dicts, one per trading day:
                [
                    {
                        "date": "2023-01-03",
                        "open": 130.28,
                        "high": 130.90,
                        "low": 124.17,
                        "close": 125.07,
                        "volume": 112117500
                    },
                    ...
                ]
            
            Notes:
            - Excludes weekends and holidays (trading days only)
            - Dates are strings in YYYY-MM-DD format
            - Prices are floats, volume is int
            - None values already removed (no missing data)
        
        Raises:
            ValueError: If date format is invalid or ticker not found
            requests.RequestException: If network request fails
        """
        
        # Convert date strings to Unix timestamps
        period1, period2 = self._parse_dates(start_date, end_date)
        
        # Fetch raw JSON from API
        raw_data = self._fetch_raw(ticker, period1, period2, interval)
        
        # Parse nested JSON structure
        prices = self._parse_prices(raw_data, ticker)
        
        return prices
    
    # =========================================================================
    # HELPER METHODS: DATE CONVERSION
    # =========================================================================
    
    def _parse_dates(self, start_date: str, end_date: str) -> Tuple[int, int]:
        """
        Convert date strings to Unix timestamps (seconds since epoch).
        
        Args:
            start_date (str): "YYYY-MM-DD" format
            end_date (str): "YYYY-MM-DD" format
        
        Returns:
            Tuple[int, int]: (period1, period2) Unix timestamps
        
        Raises:
            ValueError: If date format is invalid or start > end
        
        Example:
            >>> fetcher._parse_dates("2023-01-01", "2023-12-31")
            (1672531200, 1704067200)
        """
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"Invalid date format. Use YYYY-MM-DD. Got: {start_date}, {end_date}"
            ) from e

        # Validate: start should be before end
        if start_dt >= end_dt:
            raise ValueError(
                f"start_date must be before end_date. Got start={start_date}, end={end_date}"
            )

        # Clamp end_date to now (Yahoo rejects future dates)
        now = datetime.now()
        if end_dt > now:
            end_dt = now

        # Convert to Unix timestamps (seconds since epoch)
        period1 = int(start_dt.timestamp())
        period2 = int(end_dt.timestamp())

        return period1, period2
    
    # =========================================================================
    # HELPER METHODS: HTTP REQUESTS
    # =========================================================================
    
    def _fetch_raw(
        self,
        ticker: str,
        period1: int,
        period2: int,
        interval: str
    ) -> Dict:
        """
        Make HTTP request to Yahoo Finance API.
        
        Args:
            ticker (str): Stock symbol
            period1 (int): Start timestamp
            period2 (int): End timestamp
            interval (str): "1d" for daily
        
        Returns:
            Dict: Raw JSON response (still nested)
        
        Raises:
            requests.RequestException: If network fails or API returns error
            ValueError: If API response is malformed
        
        Example:
            >>> raw = fetcher._fetch_raw("AAPL", 1672531200, 1704067200, "1d")
            >>> "chart" in raw
            True
        """
        
        # Build the URL
        url = f"{self.BASE_URL}/{ticker}"
        
        # Build query parameters
        params = {
            "period1": period1,
            "period2": period2,
            "interval": interval,
            "includePrePost": "false",  # No pre-market/after-hours
            "events": "div%7Csplit%7Cearn"  # Include dividends, splits, earnings
        }
        
        # Make the HTTP request
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self._build_headers(),
                timeout=self.timeout
            )
            
            # Raise an exception for 4xx/5xx status codes
            response.raise_for_status()
            
        except requests.exceptions.Timeout:
            raise requests.RequestException(
                f"Request timed out after {self.timeout} seconds for {ticker}"
            )
        except requests.exceptions.ConnectionError:
            raise requests.RequestException(
                f"Connection failed for {ticker}. Check internet connection."
            )
        except requests.exceptions.HTTPError as e:
            # Handle 404 (not found), 403 (forbidden), 500 (server error), etc.
            if response.status_code == 404:
                raise ValueError(f"Ticker not found: {ticker}")
            elif response.status_code == 403:
                raise requests.RequestException(
                    f"Access forbidden for {ticker}. Rate limited?"
                )
            else:
                raise requests.RequestException(
                    f"HTTP {response.status_code} for {ticker}: {e}"
                )
        
        # Parse JSON
        try:
            data = response.json()
        except ValueError as e:
            raise ValueError(
                f"Invalid JSON response from Yahoo Finance for {ticker}"
            ) from e
        
        # Check for API-level errors
        if not data or "chart" not in data:
            raise ValueError(f"Malformed response for {ticker}: missing 'chart' key")
        
        if data["chart"].get("error"):
            error_msg = data["chart"]["error"].get("description", "Unknown error")
            raise ValueError(f"Yahoo Finance API error for {ticker}: {error_msg}")
        
        return data

    def _build_headers(self) -> Dict[str, str]:
        """
        Build request headers, attaching an OAuth bearer token when configured.
        """
        headers = dict(self.HEADERS)

        if self._oauth_configured():
            headers["Authorization"] = f"Bearer {self._get_access_token()}"

        return headers

    def _oauth_configured(self) -> bool:
        """
        OAuth is enabled only when the token endpoint and client credentials exist.
        """
        return bool(self.TOKEN_URL and self.CLIENT_ID and self.CLIENT_SECRET)

    def _get_access_token(self) -> str:
        """
        Fetch and cache an OAuth access token using the client credentials flow.
        """
        # Refresh slightly early to avoid edge-of-expiry failures.
        if self._access_token and time.time() < (self._token_expires_at - 30):
            return self._access_token

        token = self._request_access_token()
        self._access_token = token["access_token"]
        expires_in = int(token.get("expires_in", 3600))
        self._token_expires_at = time.time() + expires_in
        return self._access_token

    def _request_access_token(self) -> Dict:
        """
        Request a new access token from the OAuth provider.
        """
        data = {"grant_type": "client_credentials"}
        if self.SCOPE:
            data["scope"] = self.SCOPE

        try:
            response = self.session.post(
                self.TOKEN_URL,
                data=data,
                auth=(self.CLIENT_ID, self.CLIENT_SECRET),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    **self.HEADERS,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as e:
            raise requests.RequestException(
                f"OAuth token request timed out after {self.timeout} seconds"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise requests.RequestException(
                "OAuth token request failed. Check internet connection."
            ) from e
        except requests.exceptions.HTTPError as e:
            raise requests.RequestException(
                f"OAuth token request failed with HTTP {response.status_code}: {response.text}"
            ) from e

        try:
            token = response.json()
        except ValueError as e:
            raise ValueError("OAuth token endpoint returned invalid JSON") from e

        if "access_token" not in token:
            raise ValueError("OAuth token response missing 'access_token'")

        return token
    
    # =========================================================================
    # HELPER METHODS: JSON PARSING
    # =========================================================================
    
    def _parse_prices(self, data: Dict, ticker: str) -> List[Dict]:
        """
        Extract OHLCV from deeply nested Yahoo Finance JSON structure.
        
        The API response is deeply nested like:
        ```
        data["chart"]["result"][0]["timestamp"] = [1672531200, 1672617600, ...]
        data["chart"]["result"][0]["indicators"]["quote"][0]["open"] = [130.28, 131.0, ...]
        data["chart"]["result"][0]["indicators"]["quote"][0]["high"] = [130.90, 131.5, ...]
        ...
        ```
        
        This method flattens this into:
        ```
        [
            {"date": "2023-01-01", "open": 130.28, "high": 130.90, ...},
            {"date": "2023-01-02", "open": 131.0, "high": 131.5, ...},
            ...
        ]
        ```
        
        Args:
            data (Dict): Raw JSON response from API
            ticker (str): Stock symbol (for error messages)
        
        Returns:
            List[Dict]: Clean list of OHLCV dicts
        
        Raises:
            ValueError: If JSON structure is unexpected
        
        Example:
            >>> prices = fetcher._parse_prices(raw_data, "AAPL")
            >>> prices[0]["date"]
            "2023-01-03"
            >>> prices[0]["close"]
            125.07
        """
        
        try:
            # Navigate through the nested structure
            result = data["chart"]["result"][0]
            timestamps = result.get("timestamp", [])
            indicators = result.get("indicators", {})
            quotes = indicators.get("quote", [{}])[0]
            
            # Extract individual price arrays
            opens = quotes.get("open", [])
            highs = quotes.get("high", [])
            lows = quotes.get("low", [])
            closes = quotes.get("close", [])
            volumes = quotes.get("volume", [])
            
        except (KeyError, IndexError, TypeError) as e:
            raise ValueError(
                f"Cannot parse nested JSON for {ticker}. Response structure unexpected."
            ) from e
        
        # Validate: all arrays should have the same length
        lengths = [len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes)]
        if len(set(lengths)) > 1:
            raise ValueError(
                f"Mismatched array lengths for {ticker}: "
                f"timestamps={len(timestamps)}, opens={len(opens)}, "
                f"closes={len(closes)}, volumes={len(volumes)}"
            )
        
        # Zip everything together, converting timestamps to dates
        prices = []
        for i in range(len(timestamps)):
            timestamp = timestamps[i]
            
            # Skip if any price data is None (shouldn't happen, but be safe)
            if closes[i] is None:
                continue
            
            # Convert Unix timestamp to YYYY-MM-DD date string
            date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            
            # Build the row (skip if volume is None but prices are valid)
            row = {
                "date": date_str,
                "open": opens[i],
                "high": highs[i],
                "low": lows[i],
                "close": closes[i],
                "volume": volumes[i] if volumes[i] is not None else 0,
            }
            
            prices.append(row)
        
        return prices


# ============================================================================
# SIMPLE INTERFACE (if you prefer function-based API)
# ============================================================================

def fetch_ohlcv(
    ticker: str,
    start_date: str,
    end_date: str
) -> List[Dict]:
    """
    Convenience function: fetch OHLCV data.
    
    Args:
        ticker (str): Stock symbol, e.g. "AAPL"
        start_date (str): Start date as "YYYY-MM-DD"
        end_date (str): End date as "YYYY-MM-DD"
    
    Returns:
        List[Dict]: OHLCV data, one dict per trading day
    
    Example:
        >>> rows = fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31")
        >>> len(rows)
        252
        >>> rows[0]
        {'date': '2023-01-03', 'open': 130.28, 'high': 130.9, 'low': 124.17, 'close': 125.07, 'volume': 112117500}
    """
    fetcher = YahooFinanceFetcher()
    return fetcher.fetch(ticker, start_date, end_date)

# ============================================================================
# NSE & YFINANCE HELPERS
# ============================================================================

def fetch_nse_eod(symbol: str, from_date: str, to_date: str) -> List[Dict]:
    """
    Source: NSE India bhavcopy CSV files
    URL pattern: https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date}bhav.csv.zip
    Parse zip -> extract CSV -> return list of OHLCV dicts
    """
    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
    to_dt = datetime.strptime(to_date, "%Y-%m-%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    results = []
    
    current_dt = from_dt
    while current_dt <= to_dt:
        if current_dt.weekday() < 5:  # Monday to Friday
            year = current_dt.strftime("%Y")
            month = current_dt.strftime("%b").upper()
            date_str = current_dt.strftime("%d%b%Y").upper()
            
            url = f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip"
            try:
                response = session.get(url, timeout=10)
                if response.status_code == 200:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                        filename = z.namelist()[0]
                        with z.open(filename) as f:
                            csv_data = f.read().decode('utf-8')
                            reader = csv.DictReader(io.StringIO(csv_data))
                            for row in reader:
                                if row.get("SYMBOL") == symbol and row.get("SERIES") == "EQ":
                                    ohlcv = {
                                        "date": current_dt.strftime("%Y-%m-%d"),
                                        "open": float(row.get("OPEN", 0.0)),
                                        "high": float(row.get("HIGH", 0.0)),
                                        "low": float(row.get("LOW", 0.0)),
                                        "close": float(row.get("CLOSE", 0.0)),
                                        "volume": int(row.get("TOTTRDQTY", 0))
                                    }
                                    results.append(ohlcv)
                                    break
            except Exception:
                # Silently skip days on failure (holidays, network issues, 404s)
                pass
            time.sleep(0.5)  # respectful delay
        current_dt += timedelta(days=1)
        
    return results

def fetch_yfinance_nse(symbol: str, from_date: str, to_date: str) -> List[Dict]:
    """
    Use Yahoo Finance with ".NS" suffix for NSE stocks
    Example: "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS"
    Fallback when NSE direct fails
    """
    y_symbol = f"{symbol}.NS"
    fetcher = YahooFinanceFetcher()
    return fetcher.fetch(y_symbol, from_date, to_date)

def fetch_intraday_nse(symbol: str, interval: str) -> List[Dict]:
    """
    intervals: "1m", "5m", "15m", "30m", "60m"
    Source: Yahoo Finance intraday (yfinance library)
    Returns list of {timestamp, open, high, low, close, volume}
    """
    import yfinance as yf
    
    y_symbol = f"{symbol}.NS"
    # yfinance max periods for intraday data
    period = "7d" if interval == "1m" else "60d"
    
    ticker = yf.Ticker(y_symbol)
    df = ticker.history(period=period, interval=interval)
    
    results = []
    for index, row in df.iterrows():
        results.append({
            "timestamp": index.strftime("%Y-%m-%d %H:%M:%S"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"])
        })
    return results


# ============================================================================
# MAIN: Test the fetcher
# ============================================================================

if __name__ == "__main__":
    # Quick test
    print("Fetching AAPL data...")
    
    try:
        rows = fetch_ohlcv("AAPL", "2023-01-01", "2023-12-31")
        
        print(f"✓ Success! Got {len(rows)} trading days")
        print(f"\nFirst row:")
        print(f"  {rows[0]}")
        print(f"\nLast row:")
        print(f"  {rows[-1]}")
        print(f"\nPrice range:")
        closes = [r["close"] for r in rows]
        print(f"  Min: ${min(closes):.2f}")
        print(f"  Max: ${max(closes):.2f}")
        print(f"  Mean: ${sum(closes) / len(closes):.2f}")
        
    except ValueError as e:
        print(f"✗ ValueError: {e}")
    except requests.RequestException as e:
        print(f"✗ Network error: {e}")
