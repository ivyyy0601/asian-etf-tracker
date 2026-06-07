# Thematic ETF Tracker

A Streamlit dashboard tracking thematic ETFs across 5 markets — Hong Kong, A-Share,
Taiwan, South Korea, and US — with automatic daily data updates.

This is the slim, deploy-focused build: core app + data collection + Hetzner
automation. (Cloud-vendor configs, config-building scripts, and the optional
sentiment module from the original repo are intentionally left out.)

## What's here

```
app.py                  # Streamlit entrypoint — sidebar + page routing
data_collection.py      # Fetches OHLCV (yfinance → AkShare fallback), incremental
run_daily_update.py     # Thin manual wrapper around data_collection
utils/                  # config.py (paths/loaders), data.py (calculations), charts.py
_pages/                 # summary, industry, comparison, pair_analysis, emerging
*.json                  # 6 configs: one per market + emerging A-Share list
deploy/                 # systemd units + setup.sh for Hetzner
DEPLOY_HETZNER.md       # step-by-step server deployment
```

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python data_collection.py      # first run: 20–40 min; incremental after
streamlit run app.py           # http://localhost:8501
```

Data lands in `data/`, `data_ashare/`, `data_tw/`, `data_sk/`, `data_us/`
(all gitignored — you must collect locally before the dashboard shows anything).

## Deploy with auto daily updates

See **[DEPLOY_HETZNER.md](DEPLOY_HETZNER.md)**. Short version: spin up an Ubuntu VPS,
`sudo bash deploy/setup.sh`, open port 8501. A systemd timer refreshes the data
Tue–Sat automatically.

## Pages

| Page | What it shows |
|------|---------------|
| Summary | Industry performance, momentum heatmap, top/bottom ETFs, turnover trends |
| Industry | One industry's price/volume vs benchmark |
| Comparison | Cumulative-return overlay of any assets across markets |
| Pair Analysis | Two-asset stats: correlation, OLS β/α, cointegration + Z-score, rolling beta/vol, lead-lag |
| Emerging ETFs | Post-2025 A-Share listings — growth, AUM vs return |
