"""
Data-loading and computation helpers shared across all pages.
"""

import os
import pandas as pd

from utils.config import STOCK_SPLITS, EMERGING_DATA_ROOT, _data

# ── Coverage thresholds ───────────────────────────────────────────────────────
# ETF must span this range to appear in main dashboards (filters newly-listed ones)
MIN_DATA_START = pd.Timestamp('2025-01-10')
MIN_DATA_END   = pd.Timestamp('2025-12-20')


def load_csv_data(filepath, etf_code=None):
    """Load a single CSV and return a DatetimeIndex DataFrame with split adjustments."""
    if not os.path.exists(filepath):
        return None
    df = pd.read_csv(filepath)
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)

    if etf_code and etf_code in STOCK_SPLITS:
        for split_date_str, split_ratio in STOCK_SPLITS[etf_code]:
            split_date = pd.to_datetime(split_date_str)
            before_split = df.index < split_date
            for col in ['Open', 'High', 'Low', 'Close']:
                if col in df.columns:
                    df.loc[before_split, col] *= split_ratio
    return df


def has_sufficient_data(df):
    """Return True if df covers at least 2025-01-01 → 2025-12-31 (with ±2-week tolerance)."""
    if df is None or df.empty:
        return False
    return df.index.min() <= MIN_DATA_START and df.index.max() >= MIN_DATA_END


# ── Industry page ─────────────────────────────────────────────────────────────

def get_data_for_industry(industry_key, config, selected_currencies, start_date, end_date):
    """
    Load benchmark + ETFs for one industry, filtered by currency and date range.
    Returns (price_df, volume_df, stats).
    """
    root_dir   = _data(config['settings']['data_root_dir'])
    bench_code = config['benchmark']['code']
    bench_path = os.path.join(root_dir, "benchmark", f"{bench_code}.csv")
    bench_df   = load_csv_data(bench_path, etf_code=bench_code)

    if bench_df is None or bench_df.empty:
        return None, None, []

    bench_df = bench_df[
        (bench_df.index >= pd.Timestamp(start_date)) &
        (bench_df.index <= pd.Timestamp(end_date))
    ]
    if bench_df.empty:
        return None, None, []

    start_price = bench_df['Close'].iloc[0]
    combined_df = pd.DataFrame({
        config['benchmark']['name']: (bench_df['Close'] / start_price) - 1
    })
    volume_df = pd.DataFrame(index=bench_df.index)

    bench_total_ret = combined_df[config['benchmark']['name']].iloc[-1]
    stats = [{
        "Code":       bench_code,
        "Name":       config['benchmark']['name'],
        "Currency":   "CNY" if config['benchmark'].get('market') == "cn_index" else "HKD",
        "Return":     bench_total_ret,
        "Beat Market": "-",
    }]

    industry_path = os.path.join(root_dir, industry_key)
    for etf in config['industries'][industry_key]:
        code         = etf['code']
        etf_currency = etf.get('currency') or (
            "CNY" if code.startswith(('5','1','3','0')) and len(code) == 6 else "HKD"
        )
        if etf_currency not in selected_currencies:
            continue

        name     = etf['name']
        filepath = os.path.join(industry_path, f"{code}.csv")
        df       = load_csv_data(filepath, etf_code=code)
        if df is None or df.empty or not has_sufficient_data(df):
            continue

        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if df.empty:
            continue

        start_p  = df['Close'].iloc[0]
        current_p = df['Close'].iloc[-1]
        cum_ret   = (df['Close'] / start_p) - 1
        col_name  = f"{code} - {name} [{etf_currency}]"

        combined_df[col_name] = cum_ret.reindex(bench_df.index, method='ffill')
        if 'Volume' in df.columns:
            volume_df[col_name] = df['Volume'].reindex(bench_df.index, fill_value=0)

        total_ret = (current_p / start_p) - 1
        stats.append({
            "Code":        code,
            "Name":        name,
            "Currency":    etf_currency,
            "Return":      total_ret,
            "Beat Market": "✅" if total_ret > bench_total_ret else "❌",
        })

    return combined_df, volume_df, stats


# ── Summary page ──────────────────────────────────────────────────────────────


def get_all_etf_returns(config, start_date, end_date):
    """Return (list_of_etf_dicts, bench_return) across all industries."""
    root_dir   = _data(config['settings']['data_root_dir'])
    bench_code = config['benchmark']['code']
    bench_df   = load_csv_data(
        os.path.join(root_dir, "benchmark", f"{bench_code}.csv"), etf_code=bench_code
    )
    if bench_df is None or bench_df.empty:
        return None, None

    bench_df = bench_df[
        (bench_df.index >= pd.Timestamp(start_date)) &
        (bench_df.index <= pd.Timestamp(end_date))
    ]
    if bench_df.empty:
        return None, None

    bench_return = (bench_df['Close'].iloc[-1] / bench_df['Close'].iloc[0]) - 1
    all_etfs = []

    for industry_key, etf_list in config['industries'].items():
        industry_path = os.path.join(root_dir, industry_key)
        for etf in etf_list:
            code     = etf['code']
            currency = etf.get('currency') or (
                "CNY" if code.startswith(('5','1','3','0')) and len(code) == 6 else "HKD"
            )
            df = load_csv_data(os.path.join(industry_path, f"{code}.csv"), etf_code=code)
            if df is None or df.empty or not has_sufficient_data(df):
                continue
            df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
            if df.empty:
                continue
            ret = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1
            all_etfs.append({
                'Code':           code,
                'Name':           etf['name'],
                'Industry':       industry_key.replace('_', ' ').title(),
                'Currency':       currency,
                'Return':         ret,
                'Outperformance': ret - bench_return,
            })

    return all_etfs, bench_return


def get_industry_avg_returns(config, start_date, end_date):
    """Return (list_of_industry_dicts, bench_return)."""
    root_dir   = _data(config['settings']['data_root_dir'])
    bench_code = config['benchmark']['code']
    bench_df   = load_csv_data(
        os.path.join(root_dir, "benchmark", f"{bench_code}.csv"), etf_code=bench_code
    )
    if bench_df is None or bench_df.empty:
        return None, None

    bench_df = bench_df[
        (bench_df.index >= pd.Timestamp(start_date)) &
        (bench_df.index <= pd.Timestamp(end_date))
    ]
    if bench_df.empty:
        return None, None

    bench_return = (bench_df['Close'].iloc[-1] / bench_df['Close'].iloc[0]) - 1
    industry_returns = []

    for industry_key, etf_list in config['industries'].items():
        industry_path = os.path.join(root_dir, industry_key)
        etf = etf_list[0] if etf_list else None
        if etf is None:
            continue
        code = etf['code']
        df   = load_csv_data(os.path.join(industry_path, f"{code}.csv"), etf_code=code)
        if df is None or df.empty or not has_sufficient_data(df):
            continue
        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if df.empty:
            continue
        ret = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1
        industry_returns.append({
            'Industry':       industry_key.replace('_', ' ').title(),
            'ETF':            f"{code} - {etf['name']}",
            'Average Return': ret,
            'Outperformance': ret - bench_return,
            'ETF Count':      1,
        })

    return industry_returns, bench_return


def get_industry_momentum(config, end_date, windows=(5, 21, 63)):
    """
    Compute industry average return and benchmark return for multiple trailing windows.

    Returns:
        industry_df  — pd.DataFrame, rows=industries, cols=window labels, values=avg return
        bench_df     — pd.Series, index=window labels, values=bench return
        rel_df       — pd.DataFrame, same shape as industry_df but values = industry - bench (relative)
    """
    root_dir   = _data(config['settings']['data_root_dir'])
    bench_code = config['benchmark']['code']
    bench_path = os.path.join(root_dir, "benchmark", f"{bench_code}.csv")
    bench_full = load_csv_data(bench_path, etf_code=bench_code)

    end_ts = pd.Timestamp(end_date)
    col_labels = [f"{w}d" for w in windows] + ['YTD']

    # No benchmark data at all — return all-NaN result gracefully
    if bench_full is None or bench_full.empty:
        bench_series = pd.Series({c: float('nan') for c in col_labels})
        empty = pd.DataFrame(float('nan'), index=[], columns=col_labels)
        return empty, bench_series, empty

    # Compute benchmark returns for each window
    bench_rets = {}
    for w in windows:
        win_start = end_ts - pd.tseries.offsets.BDay(w)
        b = bench_full[(bench_full.index >= win_start) & (bench_full.index <= end_ts)]
        if len(b) >= 2:
            bench_rets[f"{w}d"] = (b['Close'].iloc[-1] / b['Close'].iloc[0]) - 1
        else:
            bench_rets[f"{w}d"] = float('nan')

    # YTD window
    ytd_start = pd.Timestamp(f"{end_ts.year}-01-01")
    b_ytd = bench_full[(bench_full.index >= ytd_start) & (bench_full.index <= end_ts)]
    bench_rets['YTD'] = (b_ytd['Close'].iloc[-1] / b_ytd['Close'].iloc[0]) - 1 if len(b_ytd) >= 2 else float('nan')

    bench_series = pd.Series(bench_rets, index=col_labels)

    industry_rows = {}
    for industry_key, etf_list in config['industries'].items():
        industry_path = os.path.join(root_dir, industry_key)
        label = industry_key.replace('_', ' ').title()
        etf = etf_list[0] if etf_list else None
        if etf is None:
            continue
        code = etf['code']
        full_df = load_csv_data(os.path.join(industry_path, f"{code}.csv"), etf_code=code)
        if full_df is None or full_df.empty or not has_sufficient_data(full_df):
            continue
        row = {}
        for col in col_labels:
            win_start = ytd_start if col == 'YTD' else end_ts - pd.tseries.offsets.BDay(int(col[:-1]))
            df = full_df[(full_df.index >= win_start) & (full_df.index <= end_ts)]
            row[col] = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1 if len(df) >= 2 else float('nan')
        industry_rows[label] = row

    industry_df = pd.DataFrame(industry_rows).T  # rows=industries, cols=windows
    industry_df = industry_df[col_labels]         # ensure column order

    rel_df = industry_df.subtract(bench_series)
    return industry_df, bench_series, rel_df


def get_industry_volume_series(config, start_date, end_date):
    """Return {industry_label: pd.Series(daily turnover = volume × close)}."""
    root_dir = _data(config['settings']['data_root_dir'])
    result   = {}
    for industry_key, etf_list in config['industries'].items():
        industry_path = os.path.join(root_dir, industry_key)
        etf = etf_list[0] if etf_list else None
        if etf is None:
            continue
        code = etf['code']
        df   = load_csv_data(os.path.join(industry_path, f"{code}.csv"), etf_code=code)
        if df is None or df.empty or not has_sufficient_data(df):
            continue
        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if not df.empty and 'Volume' in df.columns and 'Close' in df.columns:
            result[industry_key.replace('_', ' ').title()] = df['Volume'] * df['Close']
    return result


def get_industry_turnover_comparison(config, end_date):
    """
    Return {industry_label: {'1M': total_turnover_1m, '3M': monthly_avg_turnover_3m}}
    for a trailing 1-month and 3-month window ending at end_date.
    3M value is normalised to a monthly average so it's comparable to the 1M figure.
    """
    root_dir = _data(config['settings']['data_root_dir'])
    end_ts   = pd.Timestamp(end_date)
    start_1m = end_ts - pd.tseries.offsets.BDay(21)
    start_3m = end_ts - pd.tseries.offsets.BDay(63)

    result = {}
    for industry_key, etf_list in config['industries'].items():
        industry_path = os.path.join(root_dir, industry_key)
        etf = etf_list[0] if etf_list else None
        if etf is None:
            continue
        code = etf['code']
        df   = load_csv_data(os.path.join(industry_path, f"{code}.csv"), etf_code=code)
        if df is None or df.empty or not has_sufficient_data(df):
            continue
        df = df[(df.index >= start_3m) & (df.index <= end_ts)]
        if df.empty or 'Volume' not in df.columns or 'Close' not in df.columns:
            continue

        daily = df['Volume'] * df['Close']
        t1m = daily[daily.index >= start_1m].sum()
        t3m_monthly_avg = daily.sum() / 3.0

        result[industry_key.replace('_', ' ').title()] = {'1M': t1m, '3M': t3m_monthly_avg}

    return result


# ── Comparison page ───────────────────────────────────────────────────────────

def get_comparison_data(configs, selected_etfs, start_date, end_date):
    """
    Load cumulative return + volume for an arbitrary list of selected assets.
    Returns (price_df, volume_df, stats).
    """
    combined_df = pd.DataFrame()
    volume_df   = pd.DataFrame()
    stats       = []

    for item in selected_etfs:
        market   = item['market']
        code     = item['code']
        name     = item['name']
        config   = configs[market]
        root_dir = _data(config['settings']['data_root_dir'])

        if code == config['benchmark']['code']:
            filepath = os.path.join(root_dir, "benchmark", f"{code}.csv")
        else:
            filepath = os.path.join(root_dir, item['industry'], f"{code}.csv")

        df = load_csv_data(filepath, etf_code=code)
        if df is None or df.empty:
            continue

        df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
        if df.empty:
            continue

        start_p   = df['Close'].iloc[0]
        current_p = df['Close'].iloc[-1]
        cum_ret   = (df['Close'] / start_p) - 1
        col_name  = f"{name} ({code}) [{market}]"

        combined_df = (
            pd.DataFrame({col_name: cum_ret}) if combined_df.empty
            else combined_df.join(cum_ret.rename(col_name), how='outer')
        )
        if 'Volume' in df.columns:
            volume_df = (
                pd.DataFrame({col_name: df['Volume']}) if volume_df.empty
                else volume_df.join(df['Volume'].rename(col_name), how='outer')
            )

        stats.append({
            "Market":       market,
            "Code":         code,
            "Name":         name,
            "Total Return": (current_p / start_p) - 1,
        })

    combined_df = combined_df.ffill().bfill()
    volume_df   = volume_df.ffill().fillna(0)
    return combined_df, volume_df, stats


# ── Pair analysis page ────────────────────────────────────────────────────────

def get_pair_data(configs, asset_a, asset_b, start_date, end_date):
    """
    Load Close + Volume for two assets.
    Returns (df_close, df_volume, df_log_returns).
    """
    import numpy as np

    result = {}
    for asset in (asset_a, asset_b):
        market = asset['market']
        code   = asset['code']
        config = configs[market]
        root   = _data(config['settings']['data_root_dir'])
        fp     = (
            os.path.join(root, "benchmark", f"{code}.csv")
            if code == config['benchmark']['code']
            else os.path.join(root, asset['industry'], f"{code}.csv")
        )
        df = load_csv_data(fp, etf_code=code)
        if df is not None and not df.empty:
            df = df[
                (df.index >= pd.Timestamp(start_date)) &
                (df.index <= pd.Timestamp(end_date))
            ]
        result[asset['label']] = df

    labels = list(result.keys())
    dfs    = list(result.values())

    if any(d is None or d.empty for d in dfs):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df_close  = pd.concat([dfs[0]['Close'].rename(labels[0]),
                            dfs[1]['Close'].rename(labels[1])], axis=1).dropna()

    vol_cols = [dfs[i]['Volume'].rename(labels[i])
                for i in range(2) if 'Volume' in dfs[i].columns]
    df_volume = pd.concat(vol_cols, axis=1).dropna() if len(vol_cols) == 2 else pd.DataFrame()

    df_returns = np.log(df_close / df_close.shift(1)).dropna()
    return df_close, df_volume, df_returns


# ── Emerging ETF page ─────────────────────────────────────────────────────────

INDUSTRY_DISPLAY = {
    "bonds_fixed_income":          "Bonds / Fixed Income",
    "semiconductor":               "Semiconductor",
    "technology_innovations":      "Technology Innovations",
    "cloud_computing_robotics_ai": "Cloud / Robotics / AI",
    "real_estate":                 "Real Estate / REIT",
    "satellite_space":             "Satellite & Space",
    "biotech_healthcare":          "Biotech & Healthcare",
    "broad_market":                "Broad Market",
    "esg_clean_energy":            "ESG / Clean Energy",
    "transportation":              "Transportation",
    "internet_communications":     "Internet & Communications",
}


def get_emerging_etf_data(emerging_config, selected_industries, start_date, end_date):
    """
    Load price data for emerging ETFs filtered by industry and date range.
    Returns (records, price_df).
    """
    records      = []
    price_series = {}

    for industry_key, etf_list in emerging_config['industries'].items():
        if industry_key not in selected_industries:
            continue
        industry_dir = os.path.join(EMERGING_DATA_ROOT, industry_key)

        for etf in etf_list:
            code         = etf['code']
            name         = etf['name']
            listing_date = etf.get('listing_date', '')
            scale        = etf.get('scale_billion_cny', 0)
            index_name   = etf.get('index', '')
            currency     = etf.get('currency', 'CNY')

            df = load_csv_data(os.path.join(industry_dir, f"{code}.csv"), etf_code=code)
            if df is None or df.empty:
                continue

            df = df[(df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))]
            if df.empty or len(df) < 2:
                continue

            start_p   = df['Close'].iloc[0]
            end_p     = df['Close'].iloc[-1]
            total_ret = (end_p / start_p) - 1
            days_listed = (df.index[-1] - df.index[0]).days
            weeks       = days_listed / 7
            weekly_growth = (1 + total_ret) ** (1 / max(weeks, 1)) - 1 if days_listed > 0 else 0.0

            col_label = f"{code} {name}"
            price_series[col_label] = (df['Close'] / start_p) - 1

            records.append({
                "Code":          code,
                "Name":          name,
                "Industry":      INDUSTRY_DISPLAY.get(industry_key, industry_key.replace('_', ' ').title()),
                "Industry Key":  industry_key,
                "Listing Date":  listing_date,
                "Scale (B CNY)": round(scale, 2),
                "Index":         index_name,
                "Currency":      currency,
                "Total Return":  total_ret,
                "Weekly Growth": weekly_growth,
                "Days Listed":   days_listed,
                "Label":         col_label,
            })

    price_df = pd.DataFrame(price_series) if price_series else pd.DataFrame()
    return records, price_df
