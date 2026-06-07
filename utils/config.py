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
@st.cache_data
def load_emerging_config():
    if os.path.exists(EMERGING_CONFIG_FILE):
        with open(EMERGING_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None


@st.cache_data
def load_all_configs():
    configs = {}
    for market, file in CONFIG_FILES.items():
        if os.path.exists(file):
            with open(file, 'r') as f:
                configs[market] = json.load(f)
    return configs
