"""
Rebuild the dashboard cache. Shared by build_cache.py (CLI / cron) and the
in-app "Refresh" button, so both recompute the exact same views.

Recomputes the Summary-page views from the current CSVs and writes the cache,
stamping computed_at. (Does NOT re-fetch prices — that's data_collection.py's
job; this just recomputes the analytics layer.)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from utils import cache
from utils import data_cached as dc
from utils.config import load_all_configs


def last_trading_day(today: date) -> date:
    """Most recent completed trading day (matches app.py)."""
    wd = today.weekday()
    if wd == 0:   return today - timedelta(days=3)   # Mon → Fri
    if wd == 6:   return today - timedelta(days=2)    # Sun → Fri
    if wd == 5:   return today - timedelta(days=1)    # Sat → Fri
    return today - timedelta(days=1)                  # Tue–Fri → yesterday


def default_range(cfg) -> tuple[date, date]:
    """The date range the dashboard uses on first load (must match app.py)."""
    cfg_start = datetime.strptime(cfg["settings"]["start_date"], "%Y-%m-%d").date()
    cfg_end_raw = datetime.strptime(cfg["settings"]["end_date"], "%Y-%m-%d").date()
    return cfg_start, min(cfg_end_raw, last_trading_day(date.today()))


def rebuild_all() -> dict:
    """Recompute every Summary view for every market and write the cache.

    Returns the metadata dict (incl. computed_at). Safe to call from the running
    Streamlit app (the Refresh button) or from the CLI/cron.
    """
    cache._building.clear()
    prev_mode = cache.BUILD_MODE
    cache.BUILD_MODE = True  # data_cached now computes + records instead of reading
    try:
        configs = load_all_configs()
        for cfg in configs.values():
            start, end = default_range(cfg)
            dc.get_industry_avg_returns(cfg, start, end)
            dc.get_all_etf_returns(cfg, start, end)
            dc.get_industry_momentum(cfg, end)
            dc.get_industry_volume_series(cfg, start, end)
            dc.get_industry_turnover_comparison(cfg, end)
        meta = {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "markets": list(configs.keys()),
        }
        cache.flush(meta)
        return meta
    finally:
        cache.BUILD_MODE = prev_mode
        cache._loaded["mtime"] = None  # force reload on next read
