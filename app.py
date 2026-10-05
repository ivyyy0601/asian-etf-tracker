"""
ETF Tracker — main entrypoint.

Structure
---------
utils/config.py      — constants, config loaders
utils/data.py        — all data-fetching / computation helpers
utils/charts.py      — reusable Plotly chart builders
utils/data_cached.py — reads precomputed views from dashboard_cache.pkl
_pages/summary.py    — Summary Dashboard
_pages/industry.py   — Industry Analysis
_pages/comparison.py — Comparison
_pages/pair_analysis.py — Pair Analysis
_pages/emerging.py   — Emerging ETFs
sentiment_analysis/  — optional Google Trends module (not included in this build)
"""

import streamlit as st
from datetime import datetime, timedelta, date as _date

from utils.config import latest_data_date, load_all_configs

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


# ---- Top navigation shared by the three dashboards on this server ----
_SITES = [("Stock Sentiment", "/dashboard/"), ("Market Sentiment", "/sentiment/"),
          ("ETF Tracker", "/etf/")]


def _site_nav(current: str):
    """A row of links to the three dashboards; `current` is highlighted."""
    links = "".join(
        f'<a href="{url}" target="_self" class="site-nav-btn{" current" if url == current else ""}">{label}</a>'
        for label, url in _SITES
    )
    st.markdown(
        "<style>"
        ".site-nav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 12px}"
        ".site-nav-btn{padding:6px 14px;border:1px solid #d0d4dc;border-radius:8px;"
        "text-decoration:none!important;color:#31333f!important;font-size:0.9rem}"
        ".site-nav-btn:hover{border-color:#ff4b4b;color:#ff4b4b!important}"
        ".site-nav-btn.current{background:#31333f;border-color:#31333f;color:#fff!important}"
        "</style>"
        f'<div class="site-nav">{links}</div>',
        unsafe_allow_html=True,
    )


def main():
    _site_nav("/etf/")
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
    # End = the latest date actually collected for this market (its latest
    # completed trading day), not a guess from the day of the week.
    data_end       = latest_data_date(active_config['settings']['data_root_dir'])
    config_end     = min(config_end_raw, data_end) if data_end else config_end_raw

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
