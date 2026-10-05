"""
Shared constants and config-loading helpers.
All other modules import from here instead of re-defining paths.
"""

import json
import os
import streamlit as st

# ── Data root ─────────────────────────────────────────────────────────────────
# On Render, set DATA_ROOT=/data (persistent disk mount point).
# Locally defaults to the project directory.
DATA_ROOT = os.getenv("DATA_ROOT", ".")

def _data(path: str) -> str:
    """Resolve a data-relative path under DATA_ROOT."""
    return os.path.join(DATA_ROOT, path)

# ── File paths ────────────────────────────────────────────────────────────────
CONFIG_FILES = {
    "Hong Kong":   "etf_config.json",
    "A-Share":     "a_share_etf_config.json",
    "Taiwan":      "tw_etf_config.json",
    "South Korea": "sk_etf_config.json",
    "US":          "us_etf_config.json",
}
EMERGING_CONFIG_FILE = "a_share_etf_emerging.json"
EMERGING_DATA_ROOT   = _data("data_ashare")

# Stock split adjustments: {ETF_CODE: [(split_date, ratio)]}
# NOTE: Data from akshare is already split-adjusted (qfq), so we don't need to adjust it
STOCK_SPLITS: dict = {
    # "03139": [("2025-12-16", 8)]
}

# ── Config loaders ────────────────────────────────────────────────────────────
# Cached per file version (mtime): the collector can rewrite a list (e.g. the
# monthly emerging-ETF refresh) and the page picks it up without a restart.
def _mtime(path: str):
    try:
        stat = os.stat(path)
        return (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return (os.path.abspath(path), None, None)


def load_emerging_config():
    return _load_emerging_config(_mtime(EMERGING_CONFIG_FILE))


@st.cache_data(max_entries=32)
def _load_emerging_config(version):
    if os.path.exists(EMERGING_CONFIG_FILE):
        with open(EMERGING_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None


def load_all_configs():
    return _load_all_configs(tuple(_mtime(f) for f in CONFIG_FILES.values()))


@st.cache_data(max_entries=32)
def _load_all_configs(versions):
    configs = {}
    for market, file in CONFIG_FILES.items():
        if os.path.exists(file):
            with open(file, 'r') as f:
                configs[market] = json.load(f)
    return configs


# ── Latest date actually in the data ──────────────────────────────────────────
def latest_data_date(data_root_dir: str):
    """Newest date across a market's CSVs (its latest completed session as
    collected), or None if there is no data yet."""
    root = _data(data_root_dir)
    files = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs if f.endswith(".csv")]
    if not files:
        return None
    return _latest_data_date(tuple(sorted(files)), tuple(_mtime(f) for f in sorted(files)))


@st.cache_data(max_entries=32)
def _latest_data_date(files, version):
    from datetime import date
    latest = None
    for path in files:
        try:
            with open(path, "rb") as fh:
                fh.seek(0, os.SEEK_END)
                fh.seek(max(fh.tell() - 512, 0))
                last = fh.read().decode("utf-8", "ignore").strip().splitlines()[-1]
            d = date.fromisoformat(last.split(",")[0][:10])
        except (OSError, ValueError, IndexError):
            continue
        latest = d if latest is None or d > latest else latest
    return latest


def load_emerging_refresh_status():
    path = _data("emerging_refresh_status.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}
