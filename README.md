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
