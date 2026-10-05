"""
Precompute the Summary-page views into a file cache (rays-dashboard style).

Run daily via cron, AFTER data_collection.py has refreshed the CSVs:
    DATA_ROOT=/opt/etf-tracker python build_cache.py

The dashboard (via utils/data_cached.py) then reads these precomputed results
on page load instead of recomputing — fast, and unchanged until the next run.
A custom date range the user picks isn't cached, so it falls back to live compute.

Runs headless: stubs out streamlit so it works without the UI installed.
"""
import os
import sys
import types

# Compute + record (don't read the old cache) for every wrapped call.
os.environ["ETF_CACHE_BUILD"] = "1"

# ── Stub streamlit so importing config/data works without the UI (rays trick) ──
_fake_st = types.ModuleType("streamlit")
def _cache_data(*a, **k):
    if a and callable(a[0]):
        return a[0]
    def deco(f):
        return f
    return deco
_cache_data.clear = lambda: None
_fake_st.cache_data = _cache_data
sys.modules["streamlit"] = _fake_st

from utils import cache, cache_builder              # noqa: E402


def main():
    meta = cache_builder.rebuild_all()
    print(f"✓ cached views for {len(meta['markets'])} markets → {cache.CACHE_FILE}")
    print(f"✓ computed_at {meta['computed_at']}")


if __name__ == "__main__":
    main()
