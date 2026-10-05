"""
Cache-aware wrappers around the Summary-page data functions.

The Summary page imports these instead of utils.data directly. On a cache hit
(default date range, precomputed by build_cache.py) they return instantly; on a
miss they fall through to the live computation in utils.data.
"""
from utils import cache, data
from utils.config import _data, _mtime
import hashlib
import json
import os


def _mk(config) -> str:
    """Per-market cache id (the data dir is unique per market)."""
    root = os.path.abspath(_data(config["settings"]["data_root_dir"]))
    versions = sorted(_mtime(os.path.join(d, f)) for d, _, files in os.walk(root)
                      for f in files if f.endswith(".csv"))
    fingerprint = hashlib.sha256(json.dumps([config, versions], sort_keys=True).encode()).hexdigest()
    return ("v2", root, fingerprint)


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
