"""
ETF Tracker — main entrypoint.

Structure
---------
utils/config.py      — constants, config loaders
utils/data.py        — all data-fetching / computation helpers
utils/charts.py      — reusable Plotly chart builders
pages/summary.py     — Summary Dashboard
pages/industry.py    — Industry Analysis
pages/comparison.py  — Comparison
pages/pair_analysis.py — Pair Analysis
pages/emerging.py    — Emerging ETFs
sentiment_analysis/  — Google Trends sentiment module
"""

import streamlit as st
from datetime import datetime, timedelta, date as _date

from utils.config import load_all_configs

from _pages.summary      import render_summary_page
from _pages.industry     import render_industry_page
from _pages.comparison   import render_comparison_page
from _pages.pair_analysis import render_pair_analysis_page
from _pages.emerging     import render_emerging_page

# Optional sentiment module
try:
    from sentiment_analysis.app_sentiment import render_sentiment_page
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="ETF Tracker", layout="wide")


def _last_trading_day(today: _date) -> _date:
    """Return the most recent completed trading day (Mon–Fri) before or on today."""
    if today.weekday() == 0:    # Monday → last Friday
        return today - timedelta(days=3)
    elif today.weekday() == 6:  # Sunday → last Friday
        return today - timedelta(days=2)
    elif today.weekday() == 5:  # Saturday → last Friday
        return today - timedelta(days=1)
    else:                       # Tue–Fri → yesterday
        return today - timedelta(days=1)


def main():
    st.title("📈 Thematic ETF Tracker")

    configs = load_all_configs()
    if not configs:
        st.error("No configuration files found. Please ensure JSON files are present.")
        return

    # ── Sidebar: Navigation ───────────────────────────────────────────────────
    st.sidebar.header("Navigation")

    selected_market = st.sidebar.selectbox("Select Market", list(configs.keys()))
    active_config   = configs[selected_market]

    page_options = ["Summary Dashboard", "Industry Analysis", "Comparison",
                    "Pair Analysis", "Emerging ETFs"]
    if SENTIMENT_AVAILABLE:
        page_options.append("Sentiment Analysis")
    page = st.sidebar.radio("Select Page", page_options)

    st.sidebar.markdown("---")

    # ── Sidebar: Industry Analysis controls (shown only on that page) ─────────
    selected_industry   = None
    selected_currencies = []
    chart_mode          = "Price"

    if page == "Industry Analysis":
        st.sidebar.header("Configuration")

        industry_options  = list(active_config['industries'].keys())
        format_func       = lambda x: x.replace('_', ' ').title()
        selected_industry = st.sidebar.selectbox(
            "Select Theme/Industry", industry_options, format_func=format_func
        )

        if selected_industry:
            available_currencies = set()
            for etf in active_config['industries'][selected_industry]:
                curr     = etf.get('currency')
                code_str = str(etf['code'])
                if not curr:
                    curr = "CNY" if code_str.startswith(('5','1','3','0')) and len(code_str) == 6 else "HKD"
                available_currencies.add(curr)

            selected_currencies = st.sidebar.multiselect(
                "Filter by Currency",
                options=sorted(available_currencies),
                default=sorted(available_currencies),
            )

        chart_mode = st.sidebar.selectbox("Chart View", ["Price", "Volume", "Both"])
        st.sidebar.markdown("---")

    # ── Sidebar: Date Range ───────────────────────────────────────────────────
    st.sidebar.subheader("📅 Date Range")

    config_start   = datetime.strptime(active_config['settings']['start_date'], '%Y-%m-%d').date()
    config_end_raw = datetime.strptime(active_config['settings']['end_date'],   '%Y-%m-%d').date()
    config_end     = min(config_end_raw, _last_trading_day(_date.today()))

    def clamp_date(d, lo, hi):
        return max(lo, min(d, hi))

    # Quick-select buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("1M", width='stretch'):
            st.session_state['start_date'] = clamp_date(config_end - timedelta(days=30),  config_start, config_end)
            st.session_state['end_date']   = config_end
        if st.button("3M", width='stretch'):
            st.session_state['start_date'] = clamp_date(config_end - timedelta(days=90),  config_start, config_end)
            st.session_state['end_date']   = config_end
    with col2:
        if st.button("6M", width='stretch'):
            st.session_state['start_date'] = clamp_date(config_end - timedelta(days=180), config_start, config_end)
            st.session_state['end_date']   = config_end
        if st.button("All", width='stretch'):
            st.session_state['start_date'] = config_start
            st.session_state['end_date']   = config_end

    if 'start_date' not in st.session_state:
        st.session_state['start_date'] = config_start
    if 'end_date' not in st.session_state:
        st.session_state['end_date'] = config_end

    start_date = st.sidebar.date_input(
        "Start Date",
        value=clamp_date(st.session_state['start_date'], config_start, config_end),
        min_value=config_start, max_value=config_end,
    )
    end_date = st.sidebar.date_input(
        "End Date",
        value=clamp_date(st.session_state['end_date'], config_start, config_end),
        min_value=config_start, max_value=config_end,
    )

    if start_date > end_date:
        st.sidebar.error("Start date must be before end date!")
        start_date, end_date = end_date, start_date

    st.sidebar.caption(f"Data available: {config_start} to {config_end}")

    # ── Route to page ─────────────────────────────────────────────────────────
    if page == "Summary Dashboard":
        render_summary_page(active_config, start_date, end_date, selected_market)

    elif page == "Industry Analysis":
        render_industry_page(
            active_config, selected_industry, selected_currencies,
            start_date, end_date, lambda x: x.replace('_', ' ').title(), chart_mode,
        )

    elif page == "Comparison":
        render_comparison_page(configs, start_date, end_date)

    elif page == "Pair Analysis":
        render_pair_analysis_page(configs, start_date, end_date)

    elif page == "Emerging ETFs":
        render_emerging_page(start_date, end_date)

    elif page == "Sentiment Analysis" and SENTIMENT_AVAILABLE:
        render_sentiment_page()


if __name__ == "__main__":
    main()
