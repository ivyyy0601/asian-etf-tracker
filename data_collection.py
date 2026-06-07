import json
import os
import yfinance as yf
import pandas as pd
import time
import akshare as ak
from datetime import datetime, timedelta
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

def get_last_trading_day():
    """
    Returns the most recent trading day (yesterday or last Friday if weekend).
    """
    today = datetime.now()

    # If today is Saturday (5), go back 1 day to Friday
    # If today is Sunday (6), go back 2 days to Friday
    # If today is Monday (0), go back 3 days to Friday
    # Otherwise, go back 1 day to yesterday

    if today.weekday() == 5:  # Saturday
        last_trading_day = today - timedelta(days=1)
    elif today.weekday() == 6:  # Sunday
        last_trading_day = today - timedelta(days=2)
    elif today.weekday() == 0:  # Monday
        last_trading_day = today - timedelta(days=3)
    else:  # Tuesday to Friday
        last_trading_day = today - timedelta(days=1)

    return last_trading_day.strftime('%Y-%m-%d')

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


def fetch_ticker(symbol, name, folder, start, end, currency=None):
    filepath = os.path.join(folder, f"{symbol}.csv")
    curr_str = f" [{currency}]" if currency else ""

    # Check existing data range
    existing_min, existing_max = get_existing_data_range(filepath)

    if existing_min and existing_max:
        # Data already exists, check if we need to update
        start_date = pd.Timestamp(start)
        end_date = pd.Timestamp(end)

        # If existing data already covers the requested range, skip
        if existing_min <= start_date and existing_max >= end_date:
            logging.info(f"   {name} ({symbol}){curr_str} - Data already up-to-date (covers {start} to {end})")
            return

        # Update the fetch range to only get missing data
        if existing_max < end_date:
            # Fetch from day after last existing date to end_date
            start = (existing_max + timedelta(days=1)).strftime('%Y-%m-%d')
            logging.info(f"   {name} ({symbol}){curr_str} - Updating from {start} to {end}")
        else:
            logging.info(f"   {name} ({symbol}){curr_str} - Data already up-to-date")
            return
    else:
        logging.info(f"   Fetching {name} ({symbol}){curr_str} - Full range {start} to {end}")

    # 1. Try yfinance first
    yf_symbol = get_yfinance_symbol(symbol)
    market    = _market_of(str(symbol), yf_symbol)

    success  = False
    df_clean = None

    # Known split-adjusted tickers that yfinance handles poorly
    problematic_tickers = ['03139', '03033', '03032']

    try:
        df = yf.download(yf_symbol, start=start, end=end, progress=False)
        df_clean = clean_yfinance_dataframe(df)

        if symbol in problematic_tickers or df_clean.empty:
            logging.warning(f"      -> yfinance empty/problematic for {symbol}. Trying fallback...")
            success = False
        else:
            success = True

    except Exception as e:
        logging.error(f"      -> yfinance error for {symbol}: {e}")
        success = False

    # 2. Fallback to AkShare (HK and CN only — TW/SK have no AkShare support)
    if not success:
        if market == 'hk':
            df_ak = fetch_with_akshare_hk(symbol)
            if df_ak is not None and not df_ak.empty:
                df_ak = df_ak[(df_ak.index >= pd.Timestamp(start)) & (df_ak.index <= pd.Timestamp(end))]
                if not df_ak.empty:
                    df_clean = df_ak
                    success = True
                else:
                    logging.warning(f"      -> AkShare HK data empty after date filter for {symbol}")
            else:
                logging.warning(f"      -> AkShare HK returned no data for {symbol}")

        elif market == 'cn':
            df_sina = fetch_with_akshare_sina(symbol, start, end)
            if df_sina is not None and not df_sina.empty:
                df_clean = df_sina
                success = True
            else:
                logging.warning(f"      -> AkShare CN returned no data for {symbol}")

        else:
            # TW / SK — no AkShare fallback available, skip gracefully
            logging.warning(f"      -> yfinance failed for {symbol} ({market.upper()}), no fallback available — skipping")

    # 3. Save or merge data
    if success and df_clean is not None and not df_clean.empty:
        merge_and_save_data(filepath, df_clean)
    else:
        logging.error(f"      -> Failed to fetch data for {symbol}")

def run_collection(use_dynamic_dates=True):
    """
    Main collection function.

    Args:
        use_dynamic_dates: If True, automatically calculates end_date as last trading day.
                          If False, uses end_date from config file.
    """
    for config_file in CONFIG_FILES:
        logging.info(f"\n=== Processing Config: {config_file} ===")
        config_path = _app(config_file)
        if not os.path.exists(config_path):
            logging.warning(f"Config file {config_path} not found. Skipping.")
            continue

        config = load_config(config_path)
        root_dir = _data(config['settings']['data_root_dir'])
        start_date = config['settings']['start_date']

        # Use dynamic end date (yesterday/last Friday) or config end_date
        if use_dynamic_dates:
            end_date = get_last_trading_day()
            logging.info(f"Using dynamic end date: {end_date}")
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
        end_date = get_last_trading_day() if use_dynamic_dates else datetime.now().strftime('%Y-%m-%d')

        for industry_key, etf_list in emerging_config['industries'].items():
            logging.info(f"Processing Emerging Industry: {industry_key}")
            industry_dir = os.path.join(EMERGING_DATA_ROOT, industry_key)
            ensure_dir(industry_dir)

            for etf in etf_list:
                code = etf['code']
                name_etf = etf['name']
                etf_start = etf.get('listing_date', '2025-01-01')
                filepath = os.path.join(industry_dir, f"{code}.csv")

                # Check if update needed
                existing_min, existing_max = get_existing_data_range(filepath)
                fetch_start = etf_start
                if existing_min and existing_max:
                    end_ts = pd.Timestamp(end_date)
                    if existing_max >= end_ts:
                        logging.info(f"   {name_etf} ({code}) - Already up-to-date")
                        continue
                    fetch_start = (existing_max + timedelta(days=1)).strftime('%Y-%m-%d')
                    logging.info(f"   {name_etf} ({code}) - Updating from {fetch_start} to {end_date}")
                else:
                    logging.info(f"   {name_etf} ({code}) - Full fetch from {fetch_start} to {end_date}")

                df = None

                # 1. Try yfinance first
                yf_symbol = get_yfinance_symbol(code)
                try:
                    raw = yf.download(yf_symbol, start=fetch_start, end=end_date, progress=False)
                    df_yf = clean_yfinance_dataframe(raw)
                    if not df_yf.empty:
                        df = df_yf
                        logging.info(f"      -> yfinance OK ({len(df)} rows)")
                except Exception as e:
                    logging.warning(f"      -> yfinance error for {code}: {e}")

                # 2. Fallback: AkShare Sina Finance (skip silently on failure)
                if df is None or df.empty:
                    logging.info(f"      -> trying AkShare Sina for {code}...")
                    df_sina = fetch_with_akshare_sina(code, fetch_start, end_date)
                    if df_sina is not None and not df_sina.empty:
                        df = df_sina
                        logging.info(f"      -> AkShare Sina OK ({len(df)} rows)")
                    else:
                        logging.warning(f"   {name_etf} ({code}) - Both sources failed, skipping")

                if df is not None and not df.empty:
                    merge_and_save_data(filepath, df)
                time.sleep(1)
    else:
        logging.warning(f"{EMERGING_CONFIG_FILE} not found — skipping emerging ETF collection.")

    logging.info("\nDone! All collections completed.")

if __name__ == "__main__":
    run_collection()