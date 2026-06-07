"""
Industry Analysis page.
"""

import plotly.graph_objects as go
import pandas as pd
import streamlit as st

from utils.data import get_data_for_industry
from utils.charts import build_volume_chart


def render_industry_page(config, selected_industry, selected_currencies,
                         start_date, end_date, format_func, chart_mode="Price"):
    if not selected_industry:
        return

    st.subheader(f"Performance: {format_func(selected_industry)} vs Market")

    if not selected_currencies:
        st.warning("Please select at least one currency.")
        return

    price_data, volume_data, stats_data = get_data_for_industry(
        selected_industry, config, selected_currencies, start_date, end_date
    )

    if price_data is None or price_data.empty:
        st.warning("No data found. Please run 'data_collection.py' to fetch data.")
        return

    bench_name = config['benchmark']['name']

    # ── Price chart ───────────────────────────────────────────────────────────
    if chart_mode in ("Price", "Both"):
        if chart_mode == "Both":
            st.markdown("**Cumulative Return**")
        fig = go.Figure()
        if bench_name in price_data.columns:
            fig.add_trace(go.Scatter(
                x=price_data.index, y=price_data[bench_name],
                mode='lines', name=bench_name,
                line=dict(color='black', width=3, dash='dash'),
            ))
        for col in price_data.columns:
            if col != bench_name:
                fig.add_trace(go.Scatter(
                    x=price_data.index, y=price_data[col],
                    mode='lines', name=col,
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
        if volume_data is not None and not volume_data.empty:
            st.plotly_chart(build_volume_chart(volume_data), width='stretch')
        else:
            st.info("No volume data available for this industry.")

    # ── Performance summary table ─────────────────────────────────────────────
    st.subheader("📊 Performance Summary")
    if stats_data:
        def _color_beat(val):
            return f'color: {"green" if val == "✅" else "red" if val == "❌" else "black"}'

        st.dataframe(
            pd.DataFrame(stats_data)
              .style.format({"Return": "{:.2%}"})
              .map(_color_beat, subset=['Beat Market']),
            width='stretch', hide_index=True,
        )
    else:
        st.info("No ETFs found for the selected currency.")
