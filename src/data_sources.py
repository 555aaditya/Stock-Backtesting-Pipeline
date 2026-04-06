"""
Unified multi-source data provider for ALL Indian financial instruments.

Supported asset classes:
    - NSE Equities (NIFTY 50, NIFTY Next 50, NIFTY Midcap 150, NIFTY Smallcap 250, full NIFTY 500)
    - BSE Equities (SENSEX 30, BSE 500)
    - NSE Indices (50+ sectoral, thematic, strategy indices)
    - BSE Indices (SENSEX, BSE 500, sectoral)
    - F&O — Stock Futures, Index Futures, Stock Options, Index Options
    - MCX Commodities (Gold, Silver, Crude Oil, Natural Gas, Copper, Zinc, Lead, Nickel, Aluminum, Cotton, Mentha Oil, CPO)
    - NCDEX Commodities (agricultural: Soybean, Castor Seed, Guar, Jeera, Turmeric, Coriander, etc.)
    - Indian Forex (USD/INR, EUR/INR, GBP/INR, JPY/INR — NSE CDS segment)
    - Indian Mutual Funds (AMFI NAV data for all AMCs)
    - Indian ETFs (Nifty ETFs, Gold ETFs, Bank ETFs, Liquid ETFs, International ETFs)
    - Indian REITs (Embassy, Mindspace, Brookfield India)
    - Indian InvITs (IndiGrid, IRB InvIT, PowerGrid InvIT)
    - Government Securities / G-Secs (RBI data)
    - Corporate Bonds (NDS-OM reference rates)
    - T-Bills (91-day, 182-day, 364-day)
    - SGX Nifty (GIFT Nifty)
    - India VIX

Free API sources:
    1. Yahoo Finance (.NS / .BO suffix) — equities, indices, ETFs, REITs, forex
    2. NSE India (bhavcopy, indices API) — EOD equity, F&O data
    3. BSE India (bhavcopy) — BSE equities
    4. AMFI (amfiindia.com) — mutual fund NAV
    5. RBI (rbi.org.in) — G-Sec yields, forex reference rates
    6. MCX via Yahoo Finance — commodity futures (via .MCX or proxy tickers)
    7. Alpha Vantage — fallback for Indian stocks (BSE: symbol.BSE)
"""

import os
import time
import requests
import zipfile
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

_RATE_LIMITS: Dict[str, float] = {}


def _throttle(source: str, min_interval: float = 1.0):
    last = _RATE_LIMITS.get(source, 0.0)
    elapsed = time.time() - last
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _RATE_LIMITS[source] = time.time()


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


# ===========================================================================
# 1. YAHOO FINANCE — Primary source for NSE/BSE equities, indices, ETFs
# ===========================================================================

class YahooFinanceSource:
    """
    Covers: NSE stocks (.NS), BSE stocks (.BO), NSE indices (^NSEI etc.),
    ETFs (.NS), REITs (.NS), forex (INR pairs), India VIX.
    """

    BASE_URL = os.getenv(
        "MARKET_DATA_BASE_URL",
        "https://query1.finance.yahoo.com/v8/finance/chart"
    )

    @staticmethod
    def fetch(ticker: str, start_date: str, end_date: str,
              interval: str = "1d", timeout: int = 10) -> List[Dict]:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        period1 = int(start_dt.timestamp())
        period2 = int(end_dt.timestamp())

        url = f"{YahooFinanceSource.BASE_URL}/{ticker}"
        params = {
            "period1": period1,
            "period2": period2,
            "interval": interval,
            "includePrePost": "false",
            "events": "div%7Csplit%7Cearn",
        }

        _throttle("yahoo", 0.4)

        try:
            resp = _SESSION.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise ValueError(f"Yahoo Finance error for {ticker}: {e}")

        if not data or "chart" not in data:
            raise ValueError(f"No chart data for {ticker}")

        err = data["chart"].get("error")
        if err:
            raise ValueError(f"Yahoo API error for {ticker}: {err.get('description', err)}")

        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        quotes = result.get("indicators", {}).get("quote", [{}])[0]

        opens = quotes.get("open", [])
        highs = quotes.get("high", [])
        lows = quotes.get("low", [])
        closes = quotes.get("close", [])
        volumes = quotes.get("volume", [])

        rows = []
        for i in range(len(timestamps)):
            if closes[i] is None:
                continue
            dt = datetime.fromtimestamp(timestamps[i])
            date_str = dt.strftime("%Y-%m-%d") if interval == "1d" else dt.strftime("%Y-%m-%d %H:%M:%S")
            rows.append({
                "date": date_str,
                "open": _safe_float(opens[i]),
                "high": _safe_float(highs[i]),
                "low": _safe_float(lows[i]),
                "close": _safe_float(closes[i]),
                "volume": _safe_int(volumes[i]) if i < len(volumes) else 0,
            })

        return rows


# ===========================================================================
# 2. NSE INDIA — Bhavcopy, Indices, F&O
# ===========================================================================

class NSEIndiaSource:
    """
    Direct NSE data: bhavcopy CSV for equities, index data,
    F&O bhav data, India VIX.
    """

    NSE_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
    }

    @staticmethod
    def _get_session() -> requests.Session:
        """NSE requires cookies — hit the homepage first."""
        s = requests.Session()
        s.headers.update(NSEIndiaSource.NSE_HEADERS)
        try:
            s.get("https://www.nseindia.com", timeout=10)
        except Exception:
            pass
        return s

    @staticmethod
    def fetch_equity_bhavcopy(symbol: str, from_date: str, to_date: str,
                              series: str = "EQ") -> List[Dict]:
        """
        Download NSE bhavcopy ZIP for each trading day and extract the symbol's row.
        Source: https://nsearchives.nseindia.com/content/historical/EQUITIES/{YYYY}/{MON}/cm{DDMONYYYY}bhav.csv.zip
        """
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        session = requests.Session()
        session.headers.update(NSEIndiaSource.NSE_HEADERS)

        results = []
        current_dt = from_dt
        while current_dt <= to_dt:
            if current_dt.weekday() < 5:
                year = current_dt.strftime("%Y")
                month = current_dt.strftime("%b").upper()
                date_str = current_dt.strftime("%d%b%Y").upper()

                url = (f"https://nsearchives.nseindia.com/content/historical/"
                       f"EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip")
                try:
                    response = session.get(url, timeout=10)
                    if response.status_code == 200:
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            filename = z.namelist()[0]
                            with z.open(filename) as f:
                                csv_data = f.read().decode("utf-8")
                                reader = csv.DictReader(io.StringIO(csv_data))
                                for row in reader:
                                    if (row.get("SYMBOL") == symbol and
                                            row.get("SERIES", "").strip() == series):
                                        results.append({
                                            "date": current_dt.strftime("%Y-%m-%d"),
                                            "open": _safe_float(row.get("OPEN")),
                                            "high": _safe_float(row.get("HIGH")),
                                            "low": _safe_float(row.get("LOW")),
                                            "close": _safe_float(row.get("CLOSE")),
                                            "volume": _safe_int(row.get("TOTTRDQTY")),
                                        })
                                        break
                except Exception:
                    pass
                time.sleep(0.5)
            current_dt += timedelta(days=1)

        return results

    @staticmethod
    def fetch_fo_bhavcopy(symbol: str, instrument: str, from_date: str,
                          to_date: str) -> List[Dict]:
        """
        Download NSE F&O bhavcopy for futures/options data.
        instrument: FUTSTK, FUTIDX, OPTSTK, OPTIDX
        Source: https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{YYYY}/{MON}/fo{DDMONYYYY}bhav.csv.zip
        """
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")

        session = requests.Session()
        session.headers.update(NSEIndiaSource.NSE_HEADERS)

        results = []
        current_dt = from_dt
        while current_dt <= to_dt:
            if current_dt.weekday() < 5:
                year = current_dt.strftime("%Y")
                month = current_dt.strftime("%b").upper()
                date_str = current_dt.strftime("%d%b%Y").upper()

                url = (f"https://nsearchives.nseindia.com/content/historical/"
                       f"DERIVATIVES/{year}/{month}/fo{date_str}bhav.csv.zip")
                try:
                    response = session.get(url, timeout=10)
                    if response.status_code == 200:
                        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                            filename = z.namelist()[0]
                            with z.open(filename) as f:
                                csv_data = f.read().decode("utf-8")
                                reader = csv.DictReader(io.StringIO(csv_data))
                                for row in reader:
                                    if (row.get("SYMBOL") == symbol and
                                            row.get("INSTRUMENT", "").strip() == instrument):
                                        results.append({
                                            "date": current_dt.strftime("%Y-%m-%d"),
                                            "open": _safe_float(row.get("OPEN")),
                                            "high": _safe_float(row.get("HIGH")),
                                            "low": _safe_float(row.get("LOW")),
                                            "close": _safe_float(row.get("CLOSE")),
                                            "volume": _safe_int(row.get("CONTRACTS")),
                                            "oi": _safe_int(row.get("OPEN_INT")),
                                            "expiry": row.get("EXPIRY_DT", ""),
                                            "strike": _safe_float(row.get("STRIKE_PR")),
                                            "option_type": row.get("OPTION_TYP", ""),
                                        })
                except Exception:
                    pass
                time.sleep(0.5)
            current_dt += timedelta(days=1)

        return results

    @staticmethod
    def fetch_index_data(index_name: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Fetch NSE index historical data via the NSE API.
        Falls back to Yahoo Finance if NSE API fails.
        """
        # Map index names to Yahoo Finance tickers
        yahoo_map = {
            "NIFTY 50": "^NSEI",
            "NIFTY BANK": "^NSEBANK",
            "NIFTY IT": "^CNXIT",
            "NIFTY AUTO": "^CNXAUTO",
            "NIFTY FMCG": "^CNXFMCG",
            "NIFTY METAL": "^CNXMETAL",
            "NIFTY PHARMA": "^CNXPHARMA",
            "NIFTY REALTY": "^CNXREALTY",
            "NIFTY ENERGY": "^CNXENERGY",
            "NIFTY INFRA": "^CNXINFRA",
            "INDIA VIX": "^INDIAVIX",
            "NIFTY NEXT 50": "^NSMIDCP",
        }

        yahoo_ticker = yahoo_map.get(index_name.upper(), index_name)
        if yahoo_ticker.startswith("^") or yahoo_ticker.endswith(".NS"):
            return YahooFinanceSource.fetch(yahoo_ticker, from_date, to_date)

        # If it's already a Yahoo ticker, pass through
        return YahooFinanceSource.fetch(index_name, from_date, to_date)


# ===========================================================================
# 3. BSE INDIA — Bhavcopy
# ===========================================================================

class BSEIndiaSource:
    """
    BSE bhavcopy for BSE-listed equities.
    Source: https://www.bseindia.com/download/BhsavcopyDerivatives/
    """

    @staticmethod
    def fetch_equity(scrip_code: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Fetch BSE equity data via Yahoo Finance with .BO suffix.
        scrip_code can be the BSE symbol (e.g., "RELIANCE") or numeric code.
        """
        ticker = f"{scrip_code}.BO" if not scrip_code.endswith(".BO") else scrip_code
        return YahooFinanceSource.fetch(ticker, from_date, to_date)


# ===========================================================================
# 4. MCX COMMODITIES — via Yahoo Finance proxy tickers
# ===========================================================================

class MCXSource:
    """
    MCX commodity futures. Yahoo Finance doesn't directly list MCX contracts,
    so we use international futures as proxies and note the mapping.
    For actual MCX data, users should set up a data vendor.
    """

    # MCX commodity → Yahoo Finance proxy ticker mapping
    PROXY_MAP = {
        "GOLD": "GC=F",           # COMEX Gold (proxy for MCX Gold)
        "GOLDM": "GC=F",          # MCX Gold Mini
        "GOLDGUINEA": "GC=F",     # MCX Gold Guinea
        "GOLDPETAL": "GC=F",      # MCX Gold Petal
        "SILVER": "SI=F",         # COMEX Silver
        "SILVERM": "SI=F",        # MCX Silver Mini
        "SILVERMIC": "SI=F",      # MCX Silver Micro
        "CRUDEOIL": "CL=F",       # WTI Crude (proxy for MCX Crude)
        "CRUDEOILM": "CL=F",      # MCX Crude Mini
        "NATURALGAS": "NG=F",     # NYMEX Natural Gas
        "COPPER": "HG=F",         # COMEX Copper
        "ZINC": "ZN=F",           # LME Zinc (best available proxy)
        "LEAD": "PB=F",           # LME Lead
        "NICKEL": "NI=F",         # LME Nickel
        "ALUMINIUM": "ALI=F",     # LME Aluminum
        "COTTON": "CT=F",         # ICE Cotton
        "MENTHAOIL": None,        # No international proxy
        "CPO": None,              # Crude Palm Oil — no direct proxy
    }

    # MCX lot sizes
    LOT_SIZES = {
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
    }

    @staticmethod
    def fetch(commodity: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Fetch commodity data using international proxy tickers.
        Returns OHLCV in the proxy currency (USD) — callers should
        convert to INR if needed using the USDINR rate.
        """
        commodity_upper = commodity.upper()
        proxy = MCXSource.PROXY_MAP.get(commodity_upper)
        if proxy is None:
            raise ValueError(
                f"No data source available for MCX {commodity_upper}. "
                f"Available: {list(MCXSource.PROXY_MAP.keys())}"
            )
        return YahooFinanceSource.fetch(proxy, from_date, to_date)


# ===========================================================================
# 5. NCDEX — Agricultural Commodities
# ===========================================================================

class NCDEXSource:
    """
    NCDEX agricultural commodities. No direct free API exists, so we provide
    lot sizes and metadata. Users should use vendor data or manual CSV import.
    """

    LOT_SIZES = {
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

    @staticmethod
    def fetch(commodity: str, from_date: str, to_date: str) -> List[Dict]:
        raise ValueError(
            f"NCDEX {commodity} does not have a free real-time API. "
            f"Please import CSV data manually or use a data vendor. "
            f"Lot size: {NCDEXSource.LOT_SIZES.get(commodity.upper(), 'unknown')}"
        )


# ===========================================================================
# 6. INDIAN FOREX (NSE Currency Derivatives Segment)
# ===========================================================================

class IndianForexSource:
    """
    INR currency pairs traded on NSE CDS segment.
    Uses Yahoo Finance for spot rates.
    """

    PAIRS = {
        "USDINR": "USDINR=X",
        "EURINR": "EURINR=X",
        "GBPINR": "GBPINR=X",
        "JPYINR": "JPYINR=X",
        # Cross rates via Yahoo
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X",
    }

    # NSE CDS lot sizes
    LOT_SIZES = {
        "USDINR": 1000,   # USD
        "EURINR": 1000,   # EUR
        "GBPINR": 1000,   # GBP
        "JPYINR": 100000, # JPY
    }

    @staticmethod
    def fetch(pair: str, from_date: str, to_date: str) -> List[Dict]:
        pair_upper = pair.upper().replace("/", "").replace("=X", "")
        yahoo_ticker = IndianForexSource.PAIRS.get(pair_upper)
        if not yahoo_ticker:
            yahoo_ticker = f"{pair_upper}=X"
        return YahooFinanceSource.fetch(yahoo_ticker, from_date, to_date)


# ===========================================================================
# 7. AMFI — Indian Mutual Fund NAV Data
# ===========================================================================

class AMFISource:
    """
    Fetch mutual fund NAV history from AMFI India.
    Source: https://www.amfiindia.com/spages/NAVAll.txt (all NAVs)
    Historical: https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx
    """

    CURRENT_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
    HISTORICAL_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"

    @staticmethod
    def fetch_current_nav() -> Dict[str, Dict]:
        """
        Fetch current NAV for all mutual fund schemes.
        Returns: {scheme_code: {name, nav, date, category}}
        """
        _throttle("amfi", 2.0)
        resp = _SESSION.get(AMFISource.CURRENT_NAV_URL, timeout=15)
        resp.raise_for_status()

        funds = {}
        current_category = ""
        for line in resp.text.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Category headers don't have semicolons in the expected positions
            parts = line.split(";")
            if len(parts) >= 5:
                scheme_code = parts[0].strip()
                if scheme_code.isdigit():
                    funds[scheme_code] = {
                        "scheme_code": scheme_code,
                        "isin_div": parts[1].strip(),
                        "isin_growth": parts[2].strip(),
                        "name": parts[3].strip(),
                        "nav": _safe_float(parts[4]),
                        "date": parts[5].strip() if len(parts) > 5 else "",
                        "category": current_category,
                    }
            else:
                current_category = line

        return funds

    @staticmethod
    def fetch_nav_history(scheme_code: str, from_date: str, to_date: str) -> List[Dict]:
        """
        Fetch historical NAV for a specific mutual fund scheme.
        Converts NAV to OHLCV format where open=high=low=close=NAV.
        """
        # AMFI date format: DD-Mon-YYYY
        fd = datetime.strptime(from_date, "%Y-%m-%d").strftime("%d-%b-%Y")
        td = datetime.strptime(to_date, "%Y-%m-%d").strftime("%d-%b-%Y")

        params = {
            "frmdt": fd,
            "todt": td,
            "MFId": "",  # empty for all AMCs
            "SchemeId": scheme_code,
        }

        _throttle("amfi", 2.0)
        resp = _SESSION.get(AMFISource.HISTORICAL_URL, params=params, timeout=30)
        resp.raise_for_status()

        rows = []
        lines = resp.text.strip().split("\n")
        for line in lines:
            parts = line.strip().split(";")
            if len(parts) >= 8:
                # Format: Scheme Code;Scheme Name;ISIN Div;ISIN Growth;NAV;Repurchase;Sale;Date
                nav_str = parts[4].strip()
                date_str = parts[7].strip() if len(parts) > 7 else parts[-1].strip()
                nav = _safe_float(nav_str)
                if nav > 0:
                    try:
                        date_parsed = datetime.strptime(date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                    rows.append({
                        "date": date_parsed,
                        "open": nav, "high": nav, "low": nav, "close": nav,
                        "volume": 0,
                    })

        return sorted(rows, key=lambda x: x["date"])


# ===========================================================================
# 8. RBI — Government Securities, Reference Rates
# ===========================================================================

class RBISource:
    """
    RBI reference rates and G-Sec yields.
    Uses RBI's published data files.
    """

    @staticmethod
    def fetch_reference_rate(from_date: str, to_date: str) -> List[Dict]:
        """
        RBI daily reference rates for USD/INR.
        Falls back to Yahoo Finance USDINR=X.
        """
        return YahooFinanceSource.fetch("USDINR=X", from_date, to_date)

    @staticmethod
    def fetch_gsec_yield(tenor: str, from_date: str, to_date: str) -> List[Dict]:
        """
        G-Sec benchmark yields. Tenor: "1Y", "5Y", "10Y", "30Y" etc.
        Since RBI doesn't have a clean public API, we use India 10Y bond
        via Yahoo Finance as proxy and note the limitation.
        """
        # Yahoo Finance India government bond tickers
        gsec_map = {
            "10Y": "^GSPC10Y.NS",  # Try India 10Y
            "IN10Y": "IN10Y.NS",
        }
        # Fallback: use proxy
        ticker = gsec_map.get(tenor.upper(), None)
        if ticker:
            try:
                return YahooFinanceSource.fetch(ticker, from_date, to_date)
            except Exception:
                pass

        raise ValueError(
            f"G-Sec yield data for {tenor} tenor is not available via free APIs. "
            f"Use RBI DBIE portal (https://dbie.rbi.org.in) for official G-Sec data."
        )


# ===========================================================================
# 9. ALPHA VANTAGE — Fallback for Indian stocks
# ===========================================================================

class AlphaVantageIndiaSource:
    """
    Fallback source for Indian equities via Alpha Vantage.
    Requires ALPHA_VANTAGE_API_KEY env var.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    @staticmethod
    def _key() -> str:
        key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        if not key:
            raise ValueError(
                "ALPHA_VANTAGE_API_KEY not set. "
                "Get a free key at https://www.alphavantage.co/support/#api-key"
            )
        return key

    @staticmethod
    def fetch(symbol: str, from_date: str, to_date: str) -> List[Dict]:
        """Fetch BSE stock via Alpha Vantage (symbol.BSE format)."""
        av_symbol = f"{symbol}.BSE" if not symbol.endswith(".BSE") else symbol
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": av_symbol,
            "outputsize": "full",
            "apikey": AlphaVantageIndiaSource._key(),
        }
        _throttle("alphavantage", 12.0)
        resp = _SESSION.get(AlphaVantageIndiaSource.BASE_URL, params=params, timeout=30)
        data = resp.json()

        ts = data.get("Time Series (Daily)", {})
        if not ts:
            raise ValueError(
                f"Alpha Vantage returned no data for {av_symbol}: "
                f"{data.get('Note', data.get('Information', ''))}"
            )

        rows = []
        for date_str, vals in sorted(ts.items()):
            if date_str < from_date or date_str > to_date:
                continue
            rows.append({
                "date": date_str,
                "open": _safe_float(vals.get("1. open")),
                "high": _safe_float(vals.get("2. high")),
                "low": _safe_float(vals.get("3. low")),
                "close": _safe_float(vals.get("4. close")),
                "volume": _safe_int(vals.get("5. volume")),
            })
        return rows


# ===========================================================================
# INSTRUMENT CLASSIFIER
# ===========================================================================

# Type constants
NSE_EQUITY = "nse_equity"
BSE_EQUITY = "bse_equity"
NSE_INDEX = "nse_index"
BSE_INDEX = "bse_index"
NSE_FO = "nse_fo"
MCX_COMMODITY = "mcx_commodity"
NCDEX_COMMODITY = "ncdex_commodity"
INDIAN_FOREX = "indian_forex"
INDIAN_ETF = "indian_etf"
INDIAN_REIT = "indian_reit"
INDIAN_INVIT = "indian_invit"
INDIAN_MF = "indian_mf"
INDIAN_GSEC = "indian_gsec"
INDIA_VIX = "india_vix"
SGX_NIFTY = "sgx_nifty"

# Known ETF symbols on NSE
_NSE_ETFS = {
    "NIFTYBEES", "BANKBEES", "JUNIORBEES", "GOLDBEES", "LIQUIDBEES",
    "SETFNIF50", "SETFNIFBK", "ICICINIF", "ICICIB22", "UTINIFTETF",
    "KOTAKNIFTY", "KOTAKBKETF", "HABORNNIFTY", "NIPNIFBETF", "NIPMIDCAP",
    "LIQUIDETF", "LIQUIDCASE", "CPSEETF", "BHARAT22", "NEXT50",
    "MOM100", "MON100", "MOM50", "LOWVOLIETF", "ALPHAETF",
    "QUAL30IETF", "MASPTOP50", "MOMENTUM", "QUALITYETF",
    "ITETF", "ITBEES", "PSUBNKBEES", "INFRABEES", "SHARIABEES",
    "SILVERBEES", "GOLDETF", "GOLDCASE", "GOLDSHARE",
    "SILVERETF", "SILVER1", "SILVRETF",
    "MAFANG", "NASDAQ100", "N100", "HNGSNGBEES", "HDFCSENSEX",
    "MON100", "MONIFTY500", "MIDCAPIETF",
}

# Known REIT symbols on NSE
_NSE_REITS = {"EMBASSY", "MINDSPACE", "BROOKREIT"}

# Known InvIT symbols on NSE
_NSE_INVITS = {"INDIGRID", "IRBINVIT", "PGINVIT", "SHRIRAMCIT"}

# MCX commodity symbols
_MCX_SYMBOLS = set(MCXSource.PROXY_MAP.keys())

# NCDEX commodity symbols
_NCDEX_SYMBOLS = set(NCDEXSource.LOT_SIZES.keys())

# Indian forex pairs
_FOREX_PAIRS = set(IndianForexSource.PAIRS.keys()) | {
    "USDINR", "EURINR", "GBPINR", "JPYINR",
    "USDINR=X", "EURINR=X", "GBPINR=X", "JPYINR=X",
}


def classify_instrument(ticker: str) -> str:
    """Determine the Indian instrument type from the ticker."""
    t = ticker.upper().strip()

    # India VIX
    if "INDIAVIX" in t or t == "^INDIAVIX" or t == "INDIA VIX":
        return INDIA_VIX

    # SGX / GIFT Nifty
    if "SGX" in t or "GIFT" in t:
        return SGX_NIFTY

    # Mutual funds (numeric scheme codes)
    if t.isdigit():
        return INDIAN_MF

    # BSE indices (check before NSE to catch ^BSESN)
    if t == "^BSESN" or t.startswith("BSE") and t.endswith(".BO"):
        return BSE_INDEX

    # NSE indices
    if t.startswith("^NSE") or t.startswith("^CNX") or t == "^NSEI" or t == "^NSEBANK" or t.startswith("^NIFTY") or t.startswith("^NSMIDCP"):
        return NSE_INDEX

    # Indian forex
    clean_forex = t.replace("=X", "").replace("/", "")
    if clean_forex in {"USDINR", "EURINR", "GBPINR", "JPYINR"}:
        return INDIAN_FOREX

    # MCX commodities
    base_symbol = t.replace("_FUT", "").replace(".MCX", "")
    if base_symbol in _MCX_SYMBOLS:
        return MCX_COMMODITY

    # NCDEX commodities
    if base_symbol in _NCDEX_SYMBOLS:
        return NCDEX_COMMODITY

    # NSE F&O (explicit markers)
    if "_FUT" in t or "_CE" in t or "_PE" in t:
        return NSE_FO
    if t.endswith("FUT") and not t.endswith(".NS"):
        return NSE_FO

    # BSE equity
    if t.endswith(".BO"):
        return BSE_EQUITY

    # NSE equity / ETF / REIT / InvIT
    ns_symbol = t.replace(".NS", "")
    if ns_symbol in _NSE_ETFS:
        return INDIAN_ETF
    if ns_symbol in _NSE_REITS:
        return INDIAN_REIT
    if ns_symbol in _NSE_INVITS:
        return INDIAN_INVIT

    # NSE equity (with or without .NS)
    if t.endswith(".NS"):
        return NSE_EQUITY

    # G-Sec
    if t.startswith("GSEC") or "G-SEC" in t or t.startswith("IN") and t.endswith("Y"):
        return INDIAN_GSEC

    # NSE index names
    nse_index_names = {
        "NIFTY 50", "NIFTY BANK", "NIFTY IT", "NIFTY AUTO", "NIFTY FMCG",
        "NIFTY METAL", "NIFTY PHARMA", "NIFTY REALTY", "NIFTY ENERGY",
        "NIFTY INFRA", "NIFTY PSE", "NIFTY MEDIA", "NIFTY NEXT 50",
        "NIFTY MIDCAP 50", "NIFTY MIDCAP 100", "NIFTY SMLCAP 50",
        "NIFTY SMLCAP 100", "NIFTY 100", "NIFTY 200", "NIFTY 500",
        "NIFTY COMMODITIES", "NIFTY CONSUMPTION", "NIFTY CPSE",
        "NIFTY FIN SERVICE", "NIFTY GROWSECT 15", "NIFTY100 QUALTY30",
        "NIFTY50 VALUE 20", "NIFTY MNC", "NIFTY SERV SECTOR",
        "NIFTY PVT BANK", "NIFTY PSU BANK",
    }
    if t in nse_index_names:
        return NSE_INDEX

    # Default: assume NSE equity
    return NSE_EQUITY


# ===========================================================================
# UNIFIED FETCH ROUTER
# ===========================================================================

def fetch_instrument_data(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str = "1d",
    instrument_type: str = None,
    preferred_source: str = None,
) -> List[Dict]:
    """
    Universal data fetcher for Indian instruments.
    Auto-classifies the instrument and routes to the best source with fallbacks.

    Args:
        ticker: Symbol (e.g. "RELIANCE.NS", "^NSEI", "USDINR=X", "GOLD", "119551")
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        interval: "1d", "15m", "5m", "1m"
        instrument_type: Override auto-classification
        preferred_source: Force source ("yahoo", "nse", "bse", "mcx", "amfi", "alphavantage")

    Returns:
        List[Dict]: Normalized OHLCV rows
    """
    itype = instrument_type or classify_instrument(ticker)

    if preferred_source:
        return _fetch_from_source(preferred_source, ticker, start_date, end_date, interval, itype)

    # Source chains per instrument type
    chains = {
        NSE_EQUITY:       ["yahoo", "nse", "alphavantage"],
        BSE_EQUITY:       ["yahoo", "alphavantage"],
        NSE_INDEX:        ["yahoo", "nse"],
        BSE_INDEX:        ["yahoo"],
        NSE_FO:           ["nse", "yahoo"],
        MCX_COMMODITY:    ["mcx"],
        NCDEX_COMMODITY:  ["ncdex"],
        INDIAN_FOREX:     ["yahoo"],
        INDIAN_ETF:       ["yahoo", "nse"],
        INDIAN_REIT:      ["yahoo", "nse"],
        INDIAN_INVIT:     ["yahoo", "nse"],
        INDIAN_MF:        ["amfi"],
        INDIAN_GSEC:      ["rbi"],
        INDIA_VIX:        ["yahoo"],
        SGX_NIFTY:        ["yahoo"],
    }

    chain = chains.get(itype, ["yahoo"])
    last_error = None

    for source in chain:
        try:
            rows = _fetch_from_source(source, ticker, start_date, end_date, interval, itype)
            if rows:
                return rows
        except Exception as e:
            last_error = e
            continue

    raise ValueError(
        f"All data sources failed for {ticker} ({itype}). Last error: {last_error}"
    )


def _fetch_from_source(source: str, ticker: str, start_date: str,
                       end_date: str, interval: str, itype: str) -> List[Dict]:
    """Dispatch to the appropriate source."""

    if source == "yahoo":
        # Ensure proper Yahoo ticker format
        yt = _to_yahoo_ticker(ticker, itype)
        return YahooFinanceSource.fetch(yt, start_date, end_date, interval)

    elif source == "nse":
        if itype == NSE_FO:
            symbol = ticker.split("_")[0].replace(".NS", "")
            if "_CE" in ticker or "_PE" in ticker:
                instrument = "OPTSTK"
            elif "NIFTY" in ticker.upper() or "BANKNIFTY" in ticker.upper():
                instrument = "FUTIDX"
            else:
                instrument = "FUTSTK"
            return NSEIndiaSource.fetch_fo_bhavcopy(symbol, instrument, start_date, end_date)
        elif itype == NSE_INDEX:
            return NSEIndiaSource.fetch_index_data(ticker, start_date, end_date)
        else:
            symbol = ticker.replace(".NS", "")
            return NSEIndiaSource.fetch_equity_bhavcopy(symbol, start_date, end_date)

    elif source == "bse":
        return BSEIndiaSource.fetch_equity(ticker, start_date, end_date)

    elif source == "mcx":
        commodity = ticker.upper().replace("_FUT", "").replace(".MCX", "")
        return MCXSource.fetch(commodity, start_date, end_date)

    elif source == "ncdex":
        commodity = ticker.upper().replace("_FUT", "")
        return NCDEXSource.fetch(commodity, start_date, end_date)

    elif source == "amfi":
        return AMFISource.fetch_nav_history(ticker, start_date, end_date)

    elif source == "rbi":
        return RBISource.fetch_gsec_yield(ticker, start_date, end_date)

    elif source == "alphavantage":
        symbol = ticker.replace(".NS", "").replace(".BO", "")
        return AlphaVantageIndiaSource.fetch(symbol, start_date, end_date)

    else:
        raise ValueError(f"Unknown source: {source}")


def _to_yahoo_ticker(ticker: str, itype: str) -> str:
    """Convert a ticker to proper Yahoo Finance format."""
    t = ticker.strip()

    # Already in Yahoo format
    if t.endswith(".NS") or t.endswith(".BO") or t.startswith("^") or t.endswith("=X"):
        return t

    # Index mapping
    index_map = {
        "NIFTY 50": "^NSEI", "NIFTY50": "^NSEI", "NIFTY": "^NSEI",
        "NIFTY BANK": "^NSEBANK", "BANKNIFTY": "^NSEBANK", "NIFTYBANK": "^NSEBANK",
        "NIFTY IT": "^CNXIT", "NIFTYIT": "^CNXIT",
        "NIFTY AUTO": "^CNXAUTO",
        "NIFTY FMCG": "^CNXFMCG",
        "NIFTY METAL": "^CNXMETAL",
        "NIFTY PHARMA": "^CNXPHARMA",
        "NIFTY REALTY": "^CNXREALTY",
        "NIFTY ENERGY": "^CNXENERGY",
        "NIFTY INFRA": "^CNXINFRA",
        "NIFTY PSE": "^CNXPSE",
        "NIFTY MEDIA": "^CNXMEDIA",
        "NIFTY NEXT 50": "^NSMIDCP",
        "NIFTY MIDCAP 50": "^NSEMDCP50",
        "NIFTY PVT BANK": "^NIFTYPVTBANK",
        "NIFTY PSU BANK": "^NIFTYPSUBANK",
        "SENSEX": "^BSESN", "BSE SENSEX": "^BSESN",
        "INDIA VIX": "^INDIAVIX", "INDIAVIX": "^INDIAVIX",
    }
    mapped = index_map.get(t.upper())
    if mapped:
        return mapped

    # Forex
    forex_map = {
        "USDINR": "USDINR=X", "EURINR": "EURINR=X",
        "GBPINR": "GBPINR=X", "JPYINR": "JPYINR=X",
    }
    if t.upper() in forex_map:
        return forex_map[t.upper()]

    # SGX / GIFT Nifty
    if "SGX" in t.upper() or "GIFT" in t.upper():
        return "^NSEI"  # Use NIFTY 50 as proxy

    # F&O — use underlying
    if "_FUT" in t.upper():
        base = t.upper().replace("_FUT", "")
        if base in ("NIFTY", "NIFTY50"):
            return "^NSEI"
        elif base == "BANKNIFTY":
            return "^NSEBANK"
        elif base == "FINNIFTY":
            return "^CNXFIN"
        else:
            return f"{base}.NS"

    # Default: assume NSE equity
    if itype in (NSE_EQUITY, INDIAN_ETF, INDIAN_REIT, INDIAN_INVIT):
        return f"{t}.NS"

    return t


# ===========================================================================
# INSTRUMENT CATALOG — Every Indian financial instrument
# ===========================================================================

INSTRUMENT_CATALOG = {
    # -------------------------------------------------------------------
    # NSE EQUITIES — NIFTY 50
    # -------------------------------------------------------------------
    "nse_nifty50": {
        "label": "NIFTY 50 Stocks",
        "assets": [
            {"id": "RELIANCE.NS", "label": "Reliance Industries"},
            {"id": "TCS.NS", "label": "Tata Consultancy Services"},
            {"id": "HDFCBANK.NS", "label": "HDFC Bank"},
            {"id": "ICICIBANK.NS", "label": "ICICI Bank"},
            {"id": "INFY.NS", "label": "Infosys"},
            {"id": "HINDUNILVR.NS", "label": "Hindustan Unilever"},
            {"id": "ITC.NS", "label": "ITC"},
            {"id": "SBIN.NS", "label": "State Bank of India"},
            {"id": "BHARTIARTL.NS", "label": "Bharti Airtel"},
            {"id": "BAJFINANCE.NS", "label": "Bajaj Finance"},
            {"id": "KOTAKBANK.NS", "label": "Kotak Mahindra Bank"},
            {"id": "LT.NS", "label": "Larsen & Toubro"},
            {"id": "AXISBANK.NS", "label": "Axis Bank"},
            {"id": "MARUTI.NS", "label": "Maruti Suzuki"},
            {"id": "SUNPHARMA.NS", "label": "Sun Pharmaceutical"},
            {"id": "TATAMOTORS.NS", "label": "Tata Motors"},
            {"id": "WIPRO.NS", "label": "Wipro"},
            {"id": "HCLTECH.NS", "label": "HCL Technologies"},
            {"id": "ADANIENT.NS", "label": "Adani Enterprises"},
            {"id": "ADANIPORTS.NS", "label": "Adani Ports & SEZ"},
            {"id": "POWERGRID.NS", "label": "Power Grid Corporation"},
            {"id": "NTPC.NS", "label": "NTPC"},
            {"id": "ULTRACEMCO.NS", "label": "UltraTech Cement"},
            {"id": "TITAN.NS", "label": "Titan Company"},
            {"id": "ASIANPAINT.NS", "label": "Asian Paints"},
            {"id": "NESTLEIND.NS", "label": "Nestle India"},
            {"id": "TATASTEEL.NS", "label": "Tata Steel"},
            {"id": "JSWSTEEL.NS", "label": "JSW Steel"},
            {"id": "ONGC.NS", "label": "ONGC"},
            {"id": "TECHM.NS", "label": "Tech Mahindra"},
            {"id": "M&M.NS", "label": "Mahindra & Mahindra"},
            {"id": "BAJAJFINSV.NS", "label": "Bajaj Finserv"},
            {"id": "HDFCLIFE.NS", "label": "HDFC Life Insurance"},
            {"id": "SBILIFE.NS", "label": "SBI Life Insurance"},
            {"id": "DIVISLAB.NS", "label": "Divi's Laboratories"},
            {"id": "DRREDDY.NS", "label": "Dr Reddy's Laboratories"},
            {"id": "CIPLA.NS", "label": "Cipla"},
            {"id": "BPCL.NS", "label": "Bharat Petroleum"},
            {"id": "COALINDIA.NS", "label": "Coal India"},
            {"id": "EICHERMOT.NS", "label": "Eicher Motors"},
            {"id": "GRASIM.NS", "label": "Grasim Industries"},
            {"id": "HEROMOTOCO.NS", "label": "Hero MotoCorp"},
            {"id": "INDUSINDBK.NS", "label": "IndusInd Bank"},
            {"id": "APOLLOHOSP.NS", "label": "Apollo Hospitals"},
            {"id": "BRITANNIA.NS", "label": "Britannia Industries"},
            {"id": "HINDALCO.NS", "label": "Hindalco Industries"},
            {"id": "TATACONSUM.NS", "label": "Tata Consumer Products"},
            {"id": "BAJAJ-AUTO.NS", "label": "Bajaj Auto"},
            {"id": "LTIM.NS", "label": "LTIMindtree"},
            {"id": "WIPRO.NS", "label": "Wipro"},
        ],
    },

    # -------------------------------------------------------------------
    # NSE EQUITIES — NIFTY NEXT 50
    # -------------------------------------------------------------------
    "nse_niftynext50": {
        "label": "NIFTY Next 50 Stocks",
        "assets": [
            {"id": "ABB.NS", "label": "ABB India"},
            {"id": "ADANIGREEN.NS", "label": "Adani Green Energy"},
            {"id": "ADANITRANS.NS", "label": "Adani Transmission"},
            {"id": "AMBUJACEM.NS", "label": "Ambuja Cements"},
            {"id": "AUROPHARMA.NS", "label": "Aurobindo Pharma"},
            {"id": "BANKBARODA.NS", "label": "Bank of Baroda"},
            {"id": "BERGEPAINT.NS", "label": "Berger Paints"},
            {"id": "BOSCHLTD.NS", "label": "Bosch"},
            {"id": "CHOLAFIN.NS", "label": "Cholamandalam Investment"},
            {"id": "COLPAL.NS", "label": "Colgate-Palmolive India"},
            {"id": "DLF.NS", "label": "DLF"},
            {"id": "DABUR.NS", "label": "Dabur India"},
            {"id": "GODREJCP.NS", "label": "Godrej Consumer Products"},
            {"id": "GAIL.NS", "label": "GAIL (India)"},
            {"id": "HAVELLS.NS", "label": "Havells India"},
            {"id": "ICICIPRULI.NS", "label": "ICICI Prudential Life"},
            {"id": "ICICIGI.NS", "label": "ICICI Lombard General"},
            {"id": "INDIGO.NS", "label": "InterGlobe Aviation (IndiGo)"},
            {"id": "IOC.NS", "label": "Indian Oil Corporation"},
            {"id": "IRCTC.NS", "label": "IRCTC"},
            {"id": "JINDALSTEL.NS", "label": "Jindal Steel & Power"},
            {"id": "LUPIN.NS", "label": "Lupin"},
            {"id": "MARICO.NS", "label": "Marico"},
            {"id": "MCDOWELL-N.NS", "label": "United Spirits"},
            {"id": "MOTHERSON.NS", "label": "Motherson Sumi"},
            {"id": "NAUKRI.NS", "label": "Info Edge (Naukri)"},
            {"id": "PEL.NS", "label": "Piramal Enterprises"},
            {"id": "PIDILITIND.NS", "label": "Pidilite Industries"},
            {"id": "PNB.NS", "label": "Punjab National Bank"},
            {"id": "SBICARD.NS", "label": "SBI Cards"},
            {"id": "SIEMENS.NS", "label": "Siemens India"},
            {"id": "SRF.NS", "label": "SRF"},
            {"id": "SHREECEM.NS", "label": "Shree Cement"},
            {"id": "TORNTPHARM.NS", "label": "Torrent Pharmaceuticals"},
            {"id": "TRENT.NS", "label": "Trent"},
            {"id": "VEDL.NS", "label": "Vedanta"},
            {"id": "ZOMATO.NS", "label": "Zomato"},
            {"id": "ZYDUSLIFE.NS", "label": "Zydus Lifesciences"},
            {"id": "MUTHOOTFIN.NS", "label": "Muthoot Finance"},
            {"id": "POLYCAB.NS", "label": "Polycab India"},
        ],
    },

    # -------------------------------------------------------------------
    # NSE EQUITIES — MIDCAP Key Names
    # -------------------------------------------------------------------
    "nse_midcap": {
        "label": "NIFTY Midcap Stocks",
        "assets": [
            {"id": "ASTRAL.NS", "label": "Astral"},
            {"id": "ATUL.NS", "label": "Atul"},
            {"id": "BALKRISIND.NS", "label": "Balkrishna Industries"},
            {"id": "BEL.NS", "label": "Bharat Electronics"},
            {"id": "BHEL.NS", "label": "Bharat Heavy Electricals"},
            {"id": "CANFINHOME.NS", "label": "Can Fin Homes"},
            {"id": "COFORGE.NS", "label": "Coforge"},
            {"id": "CROMPTON.NS", "label": "Crompton Greaves Consumer"},
            {"id": "CUMMINSIND.NS", "label": "Cummins India"},
            {"id": "DEEPAKNTR.NS", "label": "Deepak Nitrite"},
            {"id": "DIXON.NS", "label": "Dixon Technologies"},
            {"id": "ESCORTS.NS", "label": "Escorts Kubota"},
            {"id": "FEDERALBNK.NS", "label": "Federal Bank"},
            {"id": "FORTIS.NS", "label": "Fortis Healthcare"},
            {"id": "GMRINFRA.NS", "label": "GMR Airports Infrastructure"},
            {"id": "GSPL.NS", "label": "Gujarat State Petronet"},
            {"id": "HAL.NS", "label": "Hindustan Aeronautics"},
            {"id": "IDFCFIRSTB.NS", "label": "IDFC First Bank"},
            {"id": "IEX.NS", "label": "Indian Energy Exchange"},
            {"id": "IRFC.NS", "label": "Indian Railway Finance Corp"},
            {"id": "JUBLFOOD.NS", "label": "Jubilant FoodWorks"},
            {"id": "L&TFH.NS", "label": "L&T Finance Holdings"},
            {"id": "LALPATHLAB.NS", "label": "Dr Lal PathLabs"},
            {"id": "LICHSGFIN.NS", "label": "LIC Housing Finance"},
            {"id": "LTTS.NS", "label": "L&T Technology Services"},
            {"id": "MANAPPURAM.NS", "label": "Manappuram Finance"},
            {"id": "MAXHEALTH.NS", "label": "Max Healthcare"},
            {"id": "MFSL.NS", "label": "Max Financial Services"},
            {"id": "MRF.NS", "label": "MRF"},
            {"id": "MPHASIS.NS", "label": "Mphasis"},
            {"id": "NAM-INDIA.NS", "label": "Nippon Life India AMC"},
            {"id": "OBEROIRLTY.NS", "label": "Oberoi Realty"},
            {"id": "OFSS.NS", "label": "Oracle Financial Services"},
            {"id": "PAGEIND.NS", "label": "Page Industries"},
            {"id": "PERSISTENT.NS", "label": "Persistent Systems"},
            {"id": "PETRONET.NS", "label": "Petronet LNG"},
            {"id": "PIIND.NS", "label": "PI Industries"},
            {"id": "PFC.NS", "label": "Power Finance Corporation"},
            {"id": "RECLTD.NS", "label": "REC Limited"},
            {"id": "SYNGENE.NS", "label": "Syngene International"},
            {"id": "TATACOMM.NS", "label": "Tata Communications"},
            {"id": "TATAELXSI.NS", "label": "Tata Elxsi"},
            {"id": "TATAPOWER.NS", "label": "Tata Power Company"},
            {"id": "TORNTPOWER.NS", "label": "Torrent Power"},
            {"id": "TVSMOTOR.NS", "label": "TVS Motor Company"},
            {"id": "UBL.NS", "label": "United Breweries"},
            {"id": "VOLTAS.NS", "label": "Voltas"},
            {"id": "YESBANK.NS", "label": "Yes Bank"},
        ],
    },

    # -------------------------------------------------------------------
    # NSE EQUITIES — SMALLCAP Key Names
    # -------------------------------------------------------------------
    "nse_smallcap": {
        "label": "NIFTY Smallcap Stocks",
        "assets": [
            {"id": "AFFLE.NS", "label": "Affle India"},
            {"id": "ALOKINDS.NS", "label": "Alok Industries"},
            {"id": "ANGELONE.NS", "label": "Angel One"},
            {"id": "APTUS.NS", "label": "Aptus Value Housing"},
            {"id": "BAJAJELEC.NS", "label": "Bajaj Electricals"},
            {"id": "BSOFT.NS", "label": "Birlasoft"},
            {"id": "CAMPUS.NS", "label": "Campus Activewear"},
            {"id": "CDSL.NS", "label": "CDSL"},
            {"id": "CESC.NS", "label": "CESC"},
            {"id": "CLEAN.NS", "label": "Clean Science & Technology"},
            {"id": "CYIENT.NS", "label": "Cyient"},
            {"id": "DEVYANI.NS", "label": "Devyani International"},
            {"id": "DMART.NS", "label": "Avenue Supermarts (DMart)"},
            {"id": "EIDPARRY.NS", "label": "EID Parry India"},
            {"id": "FINEORG.NS", "label": "Fine Organic Industries"},
            {"id": "GLENMARK.NS", "label": "Glenmark Pharmaceuticals"},
            {"id": "HAPPSTMNDS.NS", "label": "Happiest Minds"},
            {"id": "HDFCAMC.NS", "label": "HDFC AMC"},
            {"id": "HINDPETRO.NS", "label": "Hindustan Petroleum"},
            {"id": "IDBI.NS", "label": "IDBI Bank"},
            {"id": "KALYANKJIL.NS", "label": "Kalyan Jewellers"},
            {"id": "KPITTECH.NS", "label": "KPIT Technologies"},
            {"id": "LATENTVIEW.NS", "label": "Latent View Analytics"},
            {"id": "LICI.NS", "label": "Life Insurance Corp"},
            {"id": "MAZDOCK.NS", "label": "Mazagon Dock Shipbuilders"},
            {"id": "METROBRAND.NS", "label": "Metro Brands"},
            {"id": "NATIONALUM.NS", "label": "National Aluminium"},
            {"id": "NYKAA.NS", "label": "FSN E-Commerce (Nykaa)"},
            {"id": "PAYTM.NS", "label": "One97 Communications (Paytm)"},
            {"id": "POONAWALLA.NS", "label": "Poonawalla Fincorp"},
            {"id": "PVRINOX.NS", "label": "PVR INOX"},
            {"id": "RAILTEL.NS", "label": "RailTel Corporation"},
            {"id": "RAJESHEXPO.NS", "label": "Rajesh Exports"},
            {"id": "ROUTE.NS", "label": "Route Mobile"},
            {"id": "SAIL.NS", "label": "Steel Authority of India"},
            {"id": "SONACOMS.NS", "label": "Sona BLW Precision"},
            {"id": "STAR.NS", "label": "Star Health Insurance"},
            {"id": "SUNTV.NS", "label": "Sun TV Network"},
            {"id": "SUZLON.NS", "label": "Suzlon Energy"},
            {"id": "TRIDENT.NS", "label": "Trident"},
        ],
    },

    # -------------------------------------------------------------------
    # NSE INDICES
    # -------------------------------------------------------------------
    "nse_index": {
        "label": "NSE Indices",
        "assets": [
            # Broad market
            {"id": "^NSEI", "label": "NIFTY 50"},
            {"id": "^NSEBANK", "label": "NIFTY Bank"},
            {"id": "^NSMIDCP", "label": "NIFTY Next 50"},
            {"id": "^CNXMIDCAP", "label": "NIFTY Midcap 50"},
            {"id": "^NSEMDCP50", "label": "NIFTY Midcap Select"},
            {"id": "^CNXSC", "label": "NIFTY Smallcap 50"},
            {"id": "^CNX100", "label": "NIFTY 100"},
            {"id": "^CNX200", "label": "NIFTY 200"},
            {"id": "^CNX500", "label": "NIFTY 500"},
            # Sectoral
            {"id": "^CNXIT", "label": "NIFTY IT"},
            {"id": "^CNXAUTO", "label": "NIFTY Auto"},
            {"id": "^CNXFMCG", "label": "NIFTY FMCG"},
            {"id": "^CNXMETAL", "label": "NIFTY Metal"},
            {"id": "^CNXPHARMA", "label": "NIFTY Pharma"},
            {"id": "^CNXREALTY", "label": "NIFTY Realty"},
            {"id": "^CNXENERGY", "label": "NIFTY Energy"},
            {"id": "^CNXINFRA", "label": "NIFTY Infrastructure"},
            {"id": "^CNXPSE", "label": "NIFTY PSE"},
            {"id": "^CNXMEDIA", "label": "NIFTY Media"},
            {"id": "^CNXFIN", "label": "NIFTY Financial Services"},
            {"id": "^CNXCONSUM", "label": "NIFTY Consumption"},
            {"id": "^CNXCOMMOD", "label": "NIFTY Commodities"},
            {"id": "^NIFTYPVTBANK", "label": "NIFTY Private Bank"},
            {"id": "^NIFTYPSUBANK", "label": "NIFTY PSU Bank"},
            # Thematic / Strategy
            {"id": "^CNXMNC", "label": "NIFTY MNC"},
            {"id": "^CNXSERV", "label": "NIFTY Services Sector"},
            {"id": "^CNXCPSE", "label": "NIFTY CPSE"},
            {"id": "^CNXDIV", "label": "NIFTY Dividend Opportunities 50"},
            {"id": "^CNX100QUALTY30", "label": "NIFTY 100 Quality 30"},
            {"id": "^CNX50VALUE20", "label": "NIFTY 50 Value 20"},
            {"id": "^CNXGROWTH", "label": "NIFTY Growth Sectors 15"},
            # Volatility
            {"id": "^INDIAVIX", "label": "India VIX"},
        ],
    },

    # -------------------------------------------------------------------
    # BSE INDICES
    # -------------------------------------------------------------------
    "bse_index": {
        "label": "BSE Indices",
        "assets": [
            {"id": "^BSESN", "label": "S&P BSE SENSEX"},
            {"id": "BSE500.BO", "label": "S&P BSE 500"},
            {"id": "BSECD.BO", "label": "BSE Consumer Discretionary"},
            {"id": "BSEFIN.BO", "label": "BSE Finance"},
            {"id": "BSEIT.BO", "label": "BSE IT"},
            {"id": "BSEHC.BO", "label": "BSE Healthcare"},
            {"id": "BSEIND.BO", "label": "BSE Industrials"},
            {"id": "BSEMAT.BO", "label": "BSE Basic Materials"},
            {"id": "BSEENERGY.BO", "label": "BSE Energy"},
            {"id": "BSETELE.BO", "label": "BSE Telecom"},
        ],
    },

    # -------------------------------------------------------------------
    # F&O — INDEX FUTURES
    # -------------------------------------------------------------------
    "nse_index_futures": {
        "label": "Index Futures (NSE F&O)",
        "assets": [
            {"id": "NIFTY_FUT", "label": "Nifty 50 Futures"},
            {"id": "BANKNIFTY_FUT", "label": "Bank Nifty Futures"},
            {"id": "FINNIFTY_FUT", "label": "FinNifty Futures"},
            {"id": "MIDCPNIFTY_FUT", "label": "Midcap Nifty Futures"},
        ],
    },

    # -------------------------------------------------------------------
    # F&O — STOCK FUTURES (Top F&O stocks)
    # -------------------------------------------------------------------
    "nse_stock_futures": {
        "label": "Stock Futures (NSE F&O)",
        "assets": [
            {"id": "RELIANCE_FUT", "label": "Reliance Futures"},
            {"id": "TCS_FUT", "label": "TCS Futures"},
            {"id": "HDFCBANK_FUT", "label": "HDFC Bank Futures"},
            {"id": "ICICIBANK_FUT", "label": "ICICI Bank Futures"},
            {"id": "INFY_FUT", "label": "Infosys Futures"},
            {"id": "SBIN_FUT", "label": "SBI Futures"},
            {"id": "BAJFINANCE_FUT", "label": "Bajaj Finance Futures"},
            {"id": "AXISBANK_FUT", "label": "Axis Bank Futures"},
            {"id": "TATAMOTORS_FUT", "label": "Tata Motors Futures"},
            {"id": "TATASTEEL_FUT", "label": "Tata Steel Futures"},
            {"id": "MARUTI_FUT", "label": "Maruti Futures"},
            {"id": "BHARTIARTL_FUT", "label": "Bharti Airtel Futures"},
            {"id": "ITC_FUT", "label": "ITC Futures"},
            {"id": "HINDUNILVR_FUT", "label": "HUL Futures"},
            {"id": "KOTAKBANK_FUT", "label": "Kotak Bank Futures"},
            {"id": "LT_FUT", "label": "L&T Futures"},
            {"id": "M&M_FUT", "label": "M&M Futures"},
            {"id": "SUNPHARMA_FUT", "label": "Sun Pharma Futures"},
            {"id": "DRREDDY_FUT", "label": "Dr Reddy's Futures"},
            {"id": "WIPRO_FUT", "label": "Wipro Futures"},
            {"id": "ADANIENT_FUT", "label": "Adani Enterprises Futures"},
            {"id": "HCLTECH_FUT", "label": "HCL Tech Futures"},
            {"id": "TITAN_FUT", "label": "Titan Futures"},
            {"id": "DLF_FUT", "label": "DLF Futures"},
            {"id": "INDIGO_FUT", "label": "IndiGo Futures"},
        ],
    },

    # -------------------------------------------------------------------
    # MCX COMMODITIES
    # -------------------------------------------------------------------
    "mcx_commodity": {
        "label": "MCX Commodities",
        "assets": [
            # Precious Metals
            {"id": "GOLD", "label": "Gold (1 kg)"},
            {"id": "GOLDM", "label": "Gold Mini (100 gm)"},
            {"id": "GOLDGUINEA", "label": "Gold Guinea (8 gm)"},
            {"id": "GOLDPETAL", "label": "Gold Petal (1 gm)"},
            {"id": "SILVER", "label": "Silver (30 kg)"},
            {"id": "SILVERM", "label": "Silver Mini (5 kg)"},
            {"id": "SILVERMIC", "label": "Silver Micro (1 kg)"},
            # Energy
            {"id": "CRUDEOIL", "label": "Crude Oil (100 barrels)"},
            {"id": "CRUDEOILM", "label": "Crude Oil Mini (10 barrels)"},
            {"id": "NATURALGAS", "label": "Natural Gas (1250 mmBtu)"},
            # Base Metals
            {"id": "COPPER", "label": "Copper (2500 kg)"},
            {"id": "ZINC", "label": "Zinc (5000 kg)"},
            {"id": "LEAD", "label": "Lead (5000 kg)"},
            {"id": "NICKEL", "label": "Nickel (1500 kg)"},
            {"id": "ALUMINIUM", "label": "Aluminium (5000 kg)"},
            # Agri
            {"id": "COTTON", "label": "Cotton (25 bales)"},
            {"id": "MENTHAOIL", "label": "Mentha Oil (360 kg)"},
            {"id": "CPO", "label": "Crude Palm Oil (10 MT)"},
        ],
    },

    # -------------------------------------------------------------------
    # NCDEX AGRICULTURAL COMMODITIES
    # -------------------------------------------------------------------
    "ncdex_commodity": {
        "label": "NCDEX Agricultural Commodities",
        "assets": [
            {"id": "SOYBEAN", "label": "Soybean"},
            {"id": "SOYMEAL", "label": "Soya Meal"},
            {"id": "SOYOIL", "label": "Soya Oil"},
            {"id": "CASTORSEED", "label": "Castor Seed"},
            {"id": "GUARSEED", "label": "Guar Seed"},
            {"id": "GUARRGUM", "label": "Guar Gum"},
            {"id": "JEERA", "label": "Jeera (Cumin)"},
            {"id": "TURMERIC", "label": "Turmeric"},
            {"id": "CORIANDER", "label": "Coriander"},
            {"id": "DHANIYA", "label": "Dhaniya"},
            {"id": "CHANA", "label": "Chana (Chickpea)"},
            {"id": "MUSTARD", "label": "Mustard Seed"},
            {"id": "BARLEY", "label": "Barley"},
            {"id": "WHEAT", "label": "Wheat"},
            {"id": "MAIZE", "label": "Maize"},
            {"id": "COTTONSEED", "label": "Cotton Seed Oilcake"},
        ],
    },

    # -------------------------------------------------------------------
    # INDIAN FOREX (NSE CDS)
    # -------------------------------------------------------------------
    "indian_forex": {
        "label": "Indian Forex (NSE CDS)",
        "assets": [
            {"id": "USDINR=X", "label": "USD/INR"},
            {"id": "EURINR=X", "label": "EUR/INR"},
            {"id": "GBPINR=X", "label": "GBP/INR"},
            {"id": "JPYINR=X", "label": "JPY/INR"},
        ],
    },

    # -------------------------------------------------------------------
    # INDIAN ETFs
    # -------------------------------------------------------------------
    "indian_etf": {
        "label": "Indian ETFs (NSE)",
        "assets": [
            # Equity Index ETFs
            {"id": "NIFTYBEES.NS", "label": "Nippon Nifty BeES"},
            {"id": "BANKBEES.NS", "label": "Nippon Bank BeES"},
            {"id": "JUNIORBEES.NS", "label": "Nippon Junior BeES (Next 50)"},
            {"id": "SETFNIF50.NS", "label": "SBI ETF Nifty 50"},
            {"id": "SETFNIFBK.NS", "label": "SBI ETF Nifty Bank"},
            {"id": "KOTAKNIFTY.NS", "label": "Kotak Nifty ETF"},
            {"id": "KOTAKBKETF.NS", "label": "Kotak Banking ETF"},
            {"id": "ICICIB22.NS", "label": "ICICI Prudential Bharat 22 ETF"},
            {"id": "UTINIFTETF.NS", "label": "UTI Nifty ETF"},
            {"id": "ITBEES.NS", "label": "Nippon IT ETF"},
            {"id": "INFRABEES.NS", "label": "Nippon Infra ETF"},
            {"id": "PSUBNKBEES.NS", "label": "Nippon PSU Bank BeES"},
            {"id": "NEXT50.NS", "label": "ICICI Prudential Nifty Next 50 ETF"},
            {"id": "MIDCAPIETF.NS", "label": "ICICI Prudential Midcap Select ETF"},
            {"id": "MOM100.NS", "label": "Motilal Oswal Nasdaq 100 ETF"},
            {"id": "CPSEETF.NS", "label": "CPSE ETF"},
            {"id": "BHARAT22.NS", "label": "Bharat 22 ETF"},
            # Gold ETFs
            {"id": "GOLDBEES.NS", "label": "Nippon Gold BeES"},
            {"id": "GOLDCASE.NS", "label": "ICICI Prudential Gold ETF"},
            {"id": "GOLDSHARE.NS", "label": "UTI Gold ETF"},
            # Silver ETFs
            {"id": "SILVERBEES.NS", "label": "Nippon Silver ETF"},
            # Liquid ETFs
            {"id": "LIQUIDBEES.NS", "label": "Nippon Liquid BeES"},
            {"id": "LIQUIDETF.NS", "label": "ICICI Prudential Liquid ETF"},
            # International
            {"id": "NASDAQ100.NS", "label": "Motilal Oswal Nasdaq 100"},
            {"id": "N100.NS", "label": "Nippon Nasdaq 100 ETF"},
            {"id": "HNGSNGBEES.NS", "label": "Nippon Hang Seng BeES"},
            {"id": "MAFANG.NS", "label": "Mirae Asset NYSE FANG+ ETF"},
            # Factor / Smart Beta
            {"id": "MOM50.NS", "label": "Motilal Oswal Midcap 100 ETF"},
            {"id": "LOWVOLIETF.NS", "label": "ICICI Pru Nifty Low Vol 30 ETF"},
            {"id": "ALPHAETF.NS", "label": "ICICI Pru Alpha Low Vol 30 ETF"},
            {"id": "QUAL30IETF.NS", "label": "ICICI Pru NV20 ETF"},
        ],
    },

    # -------------------------------------------------------------------
    # INDIAN REITs
    # -------------------------------------------------------------------
    "indian_reit": {
        "label": "Indian REITs",
        "assets": [
            {"id": "EMBASSY.NS", "label": "Embassy Office Parks REIT"},
            {"id": "MINDSPACE.NS", "label": "Mindspace Business Parks REIT"},
            {"id": "BROOKREIT.NS", "label": "Brookfield India Real Estate Trust"},
        ],
    },

    # -------------------------------------------------------------------
    # INDIAN InvITs
    # -------------------------------------------------------------------
    "indian_invit": {
        "label": "Indian InvITs",
        "assets": [
            {"id": "INDIGRID.NS", "label": "IndiGrid InvIT"},
            {"id": "IRBINVIT.NS", "label": "IRB InvIT Fund"},
            {"id": "PGINVIT.NS", "label": "PowerGrid InvIT"},
        ],
    },

    # -------------------------------------------------------------------
    # INDIAN MUTUAL FUNDS (Top schemes by AUM)
    # -------------------------------------------------------------------
    "indian_mf": {
        "label": "Indian Mutual Funds",
        "assets": [
            # Large Cap
            {"id": "120503", "label": "SBI Bluechip Fund - Growth"},
            {"id": "120505", "label": "SBI Large Cap Fund - Growth"},
            {"id": "100033", "label": "HDFC Top 100 Fund - Growth"},
            {"id": "100529", "label": "ICICI Pru Bluechip Fund - Growth"},
            {"id": "118989", "label": "Axis Bluechip Fund - Growth"},
            {"id": "112325", "label": "Mirae Asset Large Cap Fund - Growth"},
            # Flexi Cap
            {"id": "100091", "label": "HDFC Flexi Cap Fund - Growth"},
            {"id": "101850", "label": "Parag Parikh Flexi Cap Fund - Growth"},
            {"id": "119551", "label": "UTI Flexi Cap Fund - Growth"},
            {"id": "100474", "label": "Kotak Flexi Cap Fund - Growth"},
            # Mid Cap
            {"id": "100504", "label": "HDFC Mid-Cap Opportunities - Growth"},
            {"id": "129974", "label": "Axis Midcap Fund - Growth"},
            {"id": "104483", "label": "Kotak Emerging Equity Fund - Growth"},
            {"id": "120586", "label": "SBI Magnum Midcap Fund - Growth"},
            # Small Cap
            {"id": "125354", "label": "SBI Small Cap Fund - Growth"},
            {"id": "112090", "label": "Nippon India Small Cap Fund - Growth"},
            {"id": "130503", "label": "Axis Small Cap Fund - Growth"},
            {"id": "103176", "label": "HDFC Small Cap Fund - Growth"},
            # Index Funds
            {"id": "120684", "label": "UTI Nifty Index Fund - Growth"},
            {"id": "127026", "label": "HDFC Index Fund Nifty 50 - Growth"},
            {"id": "140242", "label": "SBI Nifty Index Fund - Growth"},
            # ELSS (Tax Saving)
            {"id": "119775", "label": "Axis Long Term Equity Fund - Growth"},
            {"id": "120177", "label": "SBI Long Term Equity Fund - Growth"},
            {"id": "129286", "label": "Mirae Asset Tax Saver Fund - Growth"},
            # Debt Funds
            {"id": "119237", "label": "SBI Magnum Ultra Short Duration - Growth"},
            {"id": "100059", "label": "HDFC Short Term Debt Fund - Growth"},
            {"id": "104860", "label": "ICICI Pru Corporate Bond Fund - Growth"},
            # Hybrid
            {"id": "100123", "label": "HDFC Balanced Advantage Fund - Growth"},
            {"id": "100516", "label": "ICICI Pru Balanced Advantage - Growth"},
            {"id": "120693", "label": "SBI Equity Hybrid Fund - Growth"},
        ],
    },

    # -------------------------------------------------------------------
    # GOVERNMENT SECURITIES
    # -------------------------------------------------------------------
    "indian_gsec": {
        "label": "Government Securities & Bonds",
        "assets": [
            {"id": "IN10Y", "label": "India 10-Year G-Sec Yield"},
            {"id": "GSEC5Y", "label": "India 5-Year G-Sec Yield"},
            {"id": "GSEC30Y", "label": "India 30-Year G-Sec Yield"},
        ],
    },

    # -------------------------------------------------------------------
    # SGX / GIFT NIFTY
    # -------------------------------------------------------------------
    "sgx_nifty": {
        "label": "SGX / GIFT Nifty",
        "assets": [
            {"id": "SGX_NIFTY", "label": "GIFT Nifty (SGX Nifty)"},
        ],
    },
}


def get_all_instrument_types() -> List[str]:
    """Return all available instrument type keys."""
    return list(INSTRUMENT_CATALOG.keys())


def get_assets_for_type(instrument_type: str) -> List[Dict]:
    """Return the asset list for an instrument type."""
    cat = INSTRUMENT_CATALOG.get(instrument_type)
    if not cat:
        return []
    return cat["assets"]


def get_catalog_for_ui() -> Dict:
    """Return the full catalog for frontend rendering."""
    return INSTRUMENT_CATALOG
