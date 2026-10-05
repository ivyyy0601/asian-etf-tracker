"""
Cache-aware wrappers around the Summary-page data functions.

The Summary page imports these instead of utils.data directly. On a cache hit
(default date range, precomputed by build_cache.py) they return instantly; on a
miss they fall through to the live computation in utils.data.
"""
from utils import cache, data


def _mk(config) -> str:
    """Per-market cache id (the data dir is unique per market)."""
    return config["settings"]["data_root_dir"]


def _wrap(key, fn, *args):
    if not cache.BUILD_MODE:
        hit = cache.get(key)
        if hit is not None:
            return hit
    val = fn(*args)
    if cache.BUILD_MODE:
        cache.record(key, val)
    return val


def get_industry_avg_returns(config, start, end):
    return _wrap(("avg_returns", _mk(config), str(start), str(end)),
                 data.get_industry_avg_returns, config, start, end)


def get_all_etf_returns(config, start, end):
    return _wrap(("all_etf_returns", _mk(config), str(start), str(end)),
                 data.get_all_etf_returns, config, start, end)


def get_industry_momentum(config, end_date):
    return _wrap(("momentum", _mk(config), str(end_date)),
                 data.get_industry_momentum, config, end_date)


def get_industry_volume_series(config, start, end):
    return _wrap(("volume_series", _mk(config), str(start), str(end)),
                 data.get_industry_volume_series, config, start, end)


def get_industry_turnover_comparison(config, end_date):
    return _wrap(("turnover_cmp", _mk(config), str(end_date)),
                 data.get_industry_turnover_comparison, config, end_date)
