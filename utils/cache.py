"""
File-backed cache for precomputed dashboard views (rays-dashboard style).

`build_cache.py` runs daily (cron), computes the Summary-page views ONCE and
writes them here. The dashboard reads them instantly instead of recomputing on
every page load. A cache miss (e.g. a custom date range) falls back to live
computation, so behaviour is never worse than before.
"""
from __future__ import annotations

import os
import pickle
import tempfile

from utils.config import _data

CACHE_FILE = _data("dashboard_cache.pkl")

# build_cache.py sets ETF_CACHE_BUILD=1 so wrapped calls compute + record instead
# of reading the (stale) cache.
BUILD_MODE = os.getenv("ETF_CACHE_BUILD") == "1"

_loaded: dict = {"mtime": None, "data": None}
_building: dict = {}


def _read() -> dict:
    if not os.path.exists(CACHE_FILE):
        return {}
    stat = os.stat(CACHE_FILE)
    mtime = (stat.st_mtime_ns, stat.st_size)
    if _loaded["mtime"] != mtime:
        try:
            with open(CACHE_FILE, "rb") as f:
                _loaded["data"] = pickle.load(f)
        except Exception:
            _loaded["data"] = {}
        _loaded["mtime"] = mtime
    return _loaded["data"] or {}


def get(key):
    """Return a cached value for key, or None on miss."""
    return _read().get(key)


def meta() -> dict:
    """Cache metadata (computed_at etc.), for a freshness caption in the UI."""
    return _read().get("__meta__", {})


def record(key, value):
    """Accumulate a computed value during a build (not written until flush)."""
    _building[key] = value


def flush(extra_meta: dict | None = None) -> int:
    """Write all recorded values to the cache file. Returns number of entries."""
    payload = dict(_building)
    payload["__meta__"] = extra_meta or {}
    fd, temp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(CACHE_FILE)), prefix=".dashboard-cache-")
    try:
        with os.fdopen(fd, "wb") as f:
            pickle.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, CACHE_FILE)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return len(_building)
