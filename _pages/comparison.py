"""
Comparison page — multi-asset cumulative return + volume.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.data import get_comparison_data
from utils.charts import build_volume_chart


def _build_asset_list(configs):
    all_assets = []
    for market, config in configs.items():
        b = config['benchmark']
        all_assets.append({
            "label":    f"[{market}] Benchmark: {b['name']} ({b['code']})",
            "code":     b['code'],
            "name":     b['name'],
            "market":   market,
            "industry": "benchmark",
        })
        for ind, etfs in config['industries'].items():
            for etf in etfs:
                all_assets.append({
                    "label":    f"[{market}] {etf['name']} ({etf['code']})",
                    "code":     etf['code'],
                    "name":     etf['name'],
                    "market":   market,
                    "industry": ind,
                })
    return all_assets


def render_comparison_page(configs, start_date, end_date):
    st.header("⚖️ Market & ETF Comparison")
    st.subheader("Select Assets to Compare")

    all_assets = _build_asset_list(configs)
    bench_labels = [a['label'] for a in all_assets if a['industry'] == 'benchmark']

    selected_labels = st.multiselect(
        "Search and Select Assets",
        options=[a['label'] for a in all_assets],
        default=bench_labels,
    )

    if not selected_labels:
        st.info("Please select assets to compare.")
        return

    selected_assets = [a for a in all_assets if a['label'] in selected_labels]
    chart_mode      = st.radio("Chart View", ["Price", "Volume", "Both"], horizontal=True)

    combined_df, volume_df, stats = get_comparison_data(
        configs, selected_assets, start_date, end_date
    )

    if combined_df.empty:
        st.warning("No data available for the selected assets in this date range.")
        return

    # ── Price chart ───────────────────────────────────────────────────────────
    if chart_mode in ("Price", "Both"):
        if chart_mode == "Both":
            st.markdown("**Cumulative Return**")
        fig = go.Figure()
        for col in combined_df.columns:
            fig.add_trace(go.Scatter(
                x=combined_df.index, y=combined_df[col], mode='lines', name=col,
            ))
        fig.update_layout(
            yaxis_tickformat='.2%', hovermode="x unified",
            height=500, margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        st.plotly_chart(fig, width='stretch')

    # ── Volume chart ──────────────────────────────────────────────────────────
    if chart_mode in ("Volume", "Both"):
        if chart_mode == "Both":
            st.markdown("**Trading Volume**")
        if not volume_df.empty:
            st.plotly_chart(build_volume_chart(volume_df), width='stretch')
        else:
            st.info("No volume data available for selected assets.")

    # ── Stats table ───────────────────────────────────────────────────────────
    st.subheader("Comparison Stats")
    st.dataframe(
        pd.DataFrame(stats).style.format({"Total Return": "{:.2%}"}),
        hide_index=True, width='stretch',
    )
