from pathlib import Path
import json
import os
import yfinance as yf
import pandas as pd
import time
import akshare as ak
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo
import logging

# ── Paths ─────────────────────────────────────────────────────────────────────
# DATA_ROOT: where CSV data directories live.
# On Render, set DATA_ROOT=/data (persistent disk). Locally defaults to ".".
DATA_ROOT = os.getenv("DATA_ROOT", ".")

# APP_ROOT: directory containing config JSON files (same as this script).
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

def _data(path: str) -> str:
    """Resolve a path under DATA_ROOT."""
    return os.path.join(DATA_ROOT, path)

def _app(path: str) -> str:
    """Resolve a path under APP_ROOT (config files, etc.)."""
    return os.path.join(APP_ROOT, path)

CONFIG_FILES = [
    "etf_config.json",
    "a_share_etf_config.json",
    "tw_etf_config.json",
    "sk_etf_config.json",
    "us_etf_config.json",
]
EMERGING_CONFIG_FILE = "a_share_etf_emerging.json"
EMERGING_DATA_ROOT = _data("data_ashare")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(_data('data_collection.log')),
        logging.StreamHandler()
    ]
)
# yfinance logs its own ERROR for every empty download ("possibly delisted; no
# price data found") — on market holidays that's every symbol. fetch_ticker
# decides what's a real failure and logs that itself.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

# Each market's timezone and regular close; a day counts as complete 30 min after it.
MARKET_SESSIONS = {
    'hk':    ("Asia/Hong_Kong",   dtime(16, 10)),
    'cn':    ("Asia/Shanghai",    dtime(15, 0)),
    'tw':    ("Asia/Taipei",      dtime(13, 30)),
    'sk':    ("Asia/Seoul",       dtime(15, 30)),
    'us':    ("America/New_York", dtime(16, 0)),
    'other': ("Asia/Hong_Kong",   dtime(16, 10)),
}
CLOSE_BUFFER = timedelta(minutes=30)
# An empty download within this many days of the last stored bar is a holiday,
# not a failure.
HOLIDAY_TOLERANCE_DAYS = 10


def last_completed_session(market, now=None):
    """Most recent weekday whose session in `market` has finished (local time).
    Holidays aren't known here: an empty download is handled in fetch_ticker."""
    tz, close = MARKET_SESSIONS.get(market, MARKET_SESSIONS['other'])
    local = (now or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(tz))
    day = local.date()
    if local.weekday() >= 5 or local < datetime.combine(day, close, local.tzinfo) + CLOSE_BUFFER:
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day

def get_existing_data_range(filepath):
    """
    Checks existing CSV file and returns the date range of existing data.
    Returns (min_date, max_date) or (None, None) if file doesn't exist.
    """
    if not os.path.exists(filepath):
        return None, None

    try:
        df = pd.read_csv(filepath, parse_dates=['Date'])
        if df.empty or 'Date' not in df.columns:
            return None, None

        min_date = df['Date'].min()
        max_date = df['Date'].max()
        return min_date, max_date
    except Exception as e:
        logging.warning(f"Error reading existing file {filepath}: {e}")
        return None, None

def merge_and_save_data(filepath, new_df):
    """
    Merges new data with existing CSV, removes duplicates, and saves.
    """
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_csv(filepath, parse_dates=['Date'])
            existing_df.set_index('Date', inplace=True)

            # Combine and remove duplicates (keep the latest data)
            combined_df = pd.concat([existing_df, new_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df.sort_index(inplace=True)

            combined_df.to_csv(filepath)
            logging.info(f"Merged and saved updated data to {filepath}")
        except Exception as e:
            logging.error(f"Error merging data for {filepath}: {e}")
            # Fallback: just save new data
            new_df.to_csv(filepath)
    else:
        new_df.to_csv(filepath)
        logging.info(f"Saved new data to {filepath}")

def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def clean_yfinance_dataframe(df):
    """Cleans multi-index headers from yfinance."""
    if df.empty: return df
    
    # Flatten MultiIndex if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Reset index to access Date
    df = df.reset_index()
    
    # Standardize names
    if 'Adj Close' in df.columns:
        df = df.rename(columns={'Adj Close': 'Close'})
    
    # Keep only essential columns
    target_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = df[[c for c in target_cols if c in df.columns]]
    
    # Set Date index
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
    
    return df

def get_yfinance_symbol(code):
    """Determines the correct yfinance symbol based on the code format."""
    code_str = str(code)

    # Already has exchange suffix (TW, SK configs store full symbol e.g. '0050.TW')
    if '.' in code_str:
        return code_str

    if code_str == "HSI":     return "^HSI"
    if code_str == "000300":  return "000300.SS"  # CSI 300

    # US: purely alphabetic tickers (SPY, XLK, XLF, etc.)
    if code_str.isalpha():
        return code_str

    # A-Share: 6-digit codes
    if len(code_str) == 6:
        if code_str.startswith(('5', '6')):
            return f"{code_str}.SS"   # Shanghai
        elif code_str.startswith(('0', '1', '3')):
            return f"{code_str}.SZ"   # Shenzhen

    # HK: numeric codes without suffix
    try:
        return f"{int(code_str)}.HK"
    except ValueError:
        return f"{code_str}.HK"


def _market_of(code_str, yf_symbol):
    """Return 'hk', 'cn', 'tw', 'sk', 'us', or 'other' for a given symbol."""
    if yf_symbol.endswith('.TW'):  return 'tw'
    if yf_symbol.endswith('.KS'):  return 'sk'
    if yf_symbol.endswith('.SS') or yf_symbol.endswith('.SZ'): return 'cn'
    if yf_symbol.endswith('.HK') or yf_symbol == '^HSI':       return 'hk'
    if yf_symbol.isalpha():                                     return 'us'
    return 'other'

def fetch_with_akshare_hk(symbol):
    """Fetches HK stock data using AkShare."""
    try:
        # AkShare expects '02820' format for HK
        # Ensure it's 5 digits with leading zero if needed, though most are passed as 5 digits string
        formatted_symbol = str(symbol).zfill(5)
        print(f"      (AkShare) Fetching HK: {formatted_symbol}...")
        
        # stock_hk_daily returns: date, open, high, low, close, volume, etc.
        df = ak.stock_hk_daily(symbol=formatted_symbol, adjust="qfq") # Forward adjusted
        
        if df is None or df.empty:
            return None
            
        # Rename columns to standard format
        # AkShare columns: 'date', 'open', 'high', 'low', 'close', 'volume', ...
        df = df.rename(columns={
            'date': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        
        # Keep only essential columns
        target_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df = df[[c for c in target_cols if c in df.columns]]
        
        return df
    except Exception as e:
        print(f"      (AkShare) Error: {e}")
        return None

def fetch_with_akshare_sina(symbol, start, end):
    """
    Fetches A-Share ETF data via AkShare fund_etf_hist_sina (Sina Finance source).
    Shanghai codes get 'sh' prefix; everything else gets 'sz'.
    Returns a filtered DataFrame or None on any failure — never blocks.
    """
    try:
        code_str = str(symbol)
        # Shanghai: starts with 5 or 6; everything else is Shenzhen
        prefix = 'sh' if code_str.startswith(('5', '6')) else 'sz'
        df = ak.fund_etf_hist_sina(symbol=f"{prefix}{code_str}")
        if df is None or df.empty:
            return None
        df = df.rename(columns={
            'date': 'Date', 'open': 'Open', 'high': 'High',
            'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        })
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        target_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df = df[[c for c in target_cols if c in df.columns]]
        # Slice to requested date range
        df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))]
        return df if not df.empty else None
    except Exception as e:
        logging.warning(f"      (AkShare Sina) Error for {symbol}: {e}")
        return None


def fetch_ticker(symbol, name, folder, start, end=None, currency=None):
    """Bring `folder/symbol.csv` up to the market's latest completed session.

    `end` (optional) caps the range further, e.g. a config end_date. Yahoo's
    `end` is exclusive, so the request runs to the day after; anything after
    the latest completed session (a session still trading) is dropped.
    """
    filepath = os.path.join(folder, f"{symbol}.csv")
    curr_str = f" [{currency}]" if currency else ""
    yf_symbol = get_yfinance_symbol(symbol)
    market = _market_of(str(symbol), yf_symbol)

    last_done = pd.Timestamp(last_completed_session(market))
    if end is not None:
        last_done = min(last_done, pd.Timestamp(end))

    existing_min, existing_max = get_existing_data_range(filepath)
    if existing_max is not None:
        if existing_max >= last_done:
            logging.info(f"   {name} ({symbol}){curr_str} - Up to date (through {existing_max.date()})")
            return
        start = (existing_max + timedelta(days=1)).strftime('%Y-%m-%d')
        logging.info(f"   {name} ({symbol}){curr_str} - Updating {start} → {last_done.date()}")
    else:
        logging.info(f"   Fetching {name} ({symbol}){curr_str} - Full range {start} → {last_done.date()}")

    def _in_range(df):
        return df[(df.index >= pd.Timestamp(start)) & (df.index <= last_done)] if df is not None else None

    # 1. Try yfinance first
    df_clean = None
    # Known split-adjusted tickers that yfinance handles poorly. (03033 was here
    # too, but Yahoo's 3033.HK matches our history exactly — and with the AkShare
    # fallback broken it stopped updating after 2026-09-10.)
    problematic_tickers = ['03139', '03032']
    try:
        if symbol not in problematic_tickers:
            df = yf.download(yf_symbol, start=start,
                             end=(last_done + timedelta(days=1)).strftime('%Y-%m-%d'), progress=False)
            df_clean = _in_range(clean_yfinance_dataframe(df))
    except Exception as e:
        logging.warning(f"      -> yfinance error for {symbol}: {e}")

    # 2. Fallback to AkShare (HK and CN only — TW/SK have no AkShare support)
    if df_clean is None or df_clean.empty:
        if market == 'hk':
            df_clean = _in_range(fetch_with_akshare_hk(symbol))
        elif market == 'cn':
            df_clean = _in_range(fetch_with_akshare_sina(symbol, start, last_done.strftime('%Y-%m-%d')))

    # 3. Save, or decide whether "nothing new" is a holiday or a real failure
    if df_clean is not None and not df_clean.empty:
        merge_and_save_data(filepath, df_clean)
        logging.info(f"      -> +{len(df_clean)} rows (through {df_clean.index.max().date()})")
    elif existing_max is not None and (last_done - existing_max).days <= HOLIDAY_TOLERANCE_DAYS:
        logging.info(f"      -> no new sessions since {existing_max.date()} (market holiday?)")
    else:
        since = existing_max.date() if existing_max is not None else "never"
        logging.error(f"      -> FAILED {name} ({symbol}): no data from any source; last stored bar: {since}")

def run_collection(use_dynamic_dates=True):
    """
    Main collection function.

    Args:
        use_dynamic_dates: If True, automatically calculates end_date as last trading day.
                          If False, uses end_date from config file.
    """
    from refresh_emerging import refresh
    # Refresh failures preserve the previous roster and do not stop price collection.
    refresh(Path(_app(EMERGING_CONFIG_FILE)), Path(_data("emerging_refresh_status.json")))

    for config_file in CONFIG_FILES:
        logging.info(f"\n=== Processing Config: {config_file} ===")
        config_path = _app(config_file)
        if not os.path.exists(config_path):
            logging.warning(f"Config file {config_path} not found. Skipping.")
            continue

        config = load_config(config_path)
        root_dir = _data(config['settings']['data_root_dir'])
        start_date = config['settings']['start_date']

        # Dynamic: each symbol runs to its market's latest completed session
        if use_dynamic_dates:
            end_date = None
            logging.info("Using each market's latest completed session as end date")
        else:
            end_date = config['settings']['end_date']
            logging.info(f"Using config end date: {end_date}")

        ensure_dir(root_dir)

        # 1. Fetch Benchmark
        logging.info("--- Fetching Benchmark ---")
        bench_dir = os.path.join(root_dir, "benchmark")
        ensure_dir(bench_dir)
        bench_market = config['benchmark'].get('market', '')
        bench_currency = {
            'cn_index': 'CNY',
            'tw_index': 'TWD',
            'sk_index': 'KRW',
            'us_index': 'USD',
        }.get(bench_market, 'HKD')
        fetch_ticker(
            config['benchmark']['code'],
            config['benchmark']['name'],
            bench_dir,
            start_date,
            end_date,
            currency=bench_currency,
        )

        # 2. Fetch Industries
        logging.info("\n--- Fetching Industries ---")
        for industry_key, etf_list in config['industries'].items():
            logging.info(f"Processing Industry: {industry_key}")
            industry_dir = os.path.join(root_dir, industry_key)
            ensure_dir(industry_dir)

            for etf in etf_list:
                etf_currency = etf.get('currency')
                fetch_ticker(etf['code'], etf['name'], industry_dir, start_date, end_date, currency=etf_currency)
                time.sleep(1)

    # 3. Fetch Emerging A-Share ETFs
    emerging_config_path = _app(EMERGING_CONFIG_FILE)
    if os.path.exists(emerging_config_path):
        logging.info(f"\n=== Processing Emerging Config: {EMERGING_CONFIG_FILE} ===")
        emerging_config = load_config(emerging_config_path)
        for industry_key, etf_list in emerging_config['industries'].items():
            logging.info(f"Processing Emerging Industry: {industry_key}")
            industry_dir = os.path.join(EMERGING_DATA_ROOT, industry_key)
            ensure_dir(industry_dir)
            for etf in etf_list:
                fetch_ticker(etf['code'], etf['name'], industry_dir,
                             etf.get('listing_date', '2025-01-01'),
                             None if use_dynamic_dates else datetime.now().strftime('%Y-%m-%d'))
                time.sleep(1)
    else:
        logging.warning(f"{EMERGING_CONFIG_FILE} not found — skipping emerging ETF collection.")

    logging.info("\nDone! All collections completed.")

if __name__ == "__main__":
    run_collection()