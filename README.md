# Thematic ETF Tracker

A Streamlit dashboard tracking thematic ETFs across 5 markets — Hong Kong, A-Share,
Taiwan, South Korea, and US — with automatic daily data updates.

**Live:** http://91.98.37.33/etf/

This is the slim, deploy-focused build: core app + data collection + Hetzner
automation. (Cloud-vendor configs, config-building scripts, and the optional
sentiment module from the original repo are intentionally left out.)

## What's here

```
app.py                  # Streamlit entrypoint — sidebar + page routing
data_collection.py      # Fetches OHLCV (yfinance → AkShare fallback), incremental
build_cache.py          # Precomputes Summary-page views → dashboard_cache.pkl
run_daily_update.py     # Thin manual wrapper around data_collection
utils/
  config.py             #   paths (DATA_ROOT) + config loaders
  data.py               #   calculations
  charts.py             #   Plotly chart builders
  cache.py              #   read/write dashboard_cache.pkl
  cache_builder.py      #   what build_cache.py precomputes
  data_cached.py        #   cache-first wrappers used by the Summary page
_pages/                 # summary, industry, comparison, pair_analysis, emerging
*.json                  # 6 configs: one per market + emerging A-Share list
deploy/                 # systemd units, setup.sh, DEPLOY.md
```

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python data_collection.py      # first run: 20–40 min; incremental after
python build_cache.py          # optional: precompute Summary views (faster load)
streamlit run app.py           # http://localhost:8501
```

Data lands in `data/` (Hong Kong), `data_ashare/`, `data_tw/`, `data_sk/`, `data_us/`
(all gitignored — you must collect locally before the dashboard shows anything).

## Deployment

Runs on a Hetzner VPS at `/opt/etf-tracker`:

- **`etf-dashboard`** (systemd) — Streamlit on `127.0.0.1:8502` with `--server.baseUrlPath=etf`, behind nginx at `/etf/`
- **`etf-collector.timer`** — Mon–Fri 07:00 Hong Kong time: `data_collection.py`, then `build_cache.py`

Full deployment and operations guide (Chinese): **[deploy/DEPLOY.md](deploy/DEPLOY.md)**.

## Pages

| Page | What it shows |
|------|---------------|
| Summary | Industry performance, momentum heatmap, top/bottom ETFs, turnover trends |
| Industry | One industry's price/volume vs benchmark |
| Comparison | Cumulative-return overlay of any assets across markets |
| Pair Analysis | Two-asset stats: correlation, OLS β/α, cointegration + Z-score, rolling beta/vol, lead-lag |
| Emerging ETFs | Post-2025 A-Share listings — growth, AUM vs return |

## Emerging ETF roster and dates

The Emerging ETFs page covers **Shanghai-listed ETFs** listed since 2025-01-01
with the SSE's latest published scale of at least CNY 1 billion (10 亿元).
Shenzhen listings are not covered. The source is https://etf.sse.com.cn/fundlist/.
SSE `SCALE` is in 100 million CNY; the stored `scale_billion_cny` divides it by 10.
The source does not supply a scale valuation date, so retrieval time is labelled
separately from each ETF's actual price observation dates.

`data_collection.py` checks the roster before daily price collection and refreshes
it once per UTC calendar month. Failed requests, incomplete lists, invalid values,
and a drop below half the previous roster preserve the previous JSON and record
a failure in `emerging_refresh_status.json`; the next daily run retries. A successful
refresh atomically replaces the roster and saves the previous version in
`roster_backups/`. Never delete these snapshots as part of deployment.

Existing industry classifications are retained by code. New codes go into
`unclassified` until reviewed, and price collection includes them automatically.
ETFs falling below the size threshold leave the current roster; their historical
CSV files and previous snapshots remain intact. Manual refresh:
`python refresh_emerging.py --force`.

The sidebar shows the newest observed CSV date across the selected market, not a
guarantee of complete coverage. Emerging ETF details show each ETF's observed
start/end dates and coverage count. Cache keys include file path, nanosecond mtime
and size; changing an older file also invalidates the latest-date cache.

Regression checks: `python -m unittest discover -s tests -v`.
