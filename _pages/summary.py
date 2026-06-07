"""
Summary Dashboard page.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.charts import build_volume_chart
from utils.data import (
    get_all_etf_returns,
    get_industry_avg_returns,
    get_industry_momentum,
    get_industry_volume_series,
    get_industry_turnover_comparison,
)


def render_summary_page(config, start_date, end_date, market_name):
    st.header(f"📊 {market_name} Summary Dashboard")
    st.markdown(f"**Period:** {start_date} to {end_date}")

    # ── Section 0: Industry Average Performance ──────────────────────────────
    st.subheader("🏭 Industry Average Performance")
    industry_data, _ = get_industry_avg_returns(config, start_date, end_date)

    if industry_data:
        industry_df = pd.DataFrame(industry_data).sort_values('Average Return', ascending=False)
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("**Industry Comparison Table**")
            vmin = industry_df['Average Return'].min()
            vmax = industry_df['Average Return'].max()

            def _color_return(val):
                if vmax == vmin:
                    t = 0.5
                else:
                    t = (val - vmin) / (vmax - vmin)
                if t < 0.5:
                    r, g = 255, int(255 * t * 2)
                else:
                    r, g = int(255 * (1 - t) * 2), 255
                return f'background-color: rgba({r},{g},0,0.3)'

            st.dataframe(
                industry_df[['Industry', 'ETF', 'Average Return']].style.format({
                    'Average Return': '{:.2%}',
                }).map(_color_return, subset=['Average Return']),
                hide_index=True, width='stretch',
            )
        with col2:
            st.markdown("**Industry Returns**")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=industry_df['Average Return'], y=industry_df['Industry'],
                orientation='h',
                marker=dict(color=industry_df['Average Return'],
                            colorscale='RdYlGn', showscale=False),
                text=industry_df['Average Return'].apply(lambda x: f'{x:.2%}'),
                textposition='auto',
            ))
            fig.update_layout(
                xaxis_title="Average Return", xaxis_tickformat='.1%',
                height=400, margin=dict(l=200, r=20, t=20, b=40),
                showlegend=False, yaxis={'categoryorder': 'total ascending'},
            )
            st.plotly_chart(fig, width='stretch')
    else:
        st.info("No industry data available.")

    st.markdown("---")

    # ── Section 1: Momentum Heatmap ───────────────────────────────────────────
    st.subheader("🔥 Industry Momentum Heatmap")
    st.caption(
        "Rolling returns computed from the selected end date backwards. "
        "Toggle between absolute return and return relative to benchmark."
    )

    momentum_mode = st.radio(
        "Display mode",
        ["Absolute Return", "Relative to Benchmark"],
        horizontal=True,
        key="momentum_mode",
    )

    industry_df, bench_series, rel_df = get_industry_momentum(config, end_date)

    if industry_df.empty:
        st.info("No data available for this market yet. Run the data collector to populate it.")
    else:
        display_df = rel_df if momentum_mode == "Relative to Benchmark" else industry_df

        # Sort rows by 21d column (best recent momentum at top)
        sort_col = "21d" if "21d" in display_df.columns else display_df.columns[0]
        display_df = display_df.sort_values(sort_col, ascending=False)

        # Symmetric color scale centred at 0 for relative; 0-anchored for absolute
        zmax = float(display_df.abs().max().max())
        zmin = -zmax if momentum_mode == "Relative to Benchmark" else float(display_df.min().min())

        # Build annotation text
        text_vals = display_df.map(
            lambda v: f"{v:+.1%}" if not np.isnan(v) else "N/A"
        ).values.tolist()

        fig_heat = go.Figure(go.Heatmap(
            z=display_df.values.tolist(),
            x=list(display_df.columns),
            y=list(display_df.index),
            colorscale="RdYlGn",
            zmin=zmin,
            zmax=zmax,
            text=text_vals,
            texttemplate="%{text}",
            textfont={"size": 12},
            hovertemplate="Industry: %{y}<br>Window: %{x}<br>Return: %{text}<extra></extra>",
            showscale=True,
            colorbar=dict(
                tickformat=".0%",
                len=1,
                yanchor="top",
                y=1.0,
                thickness=15,
            ),
        ))

        # Benchmark row as annotations below the heatmap (not a second trace)
        bench_label = f"── {config['benchmark']['name']} (Benchmark) ──"
        cols = list(display_df.columns)
        for col in cols:
            v = bench_series[col]
            fig_heat.add_annotation(
                x=col, y=bench_label,
                text=f"{v:+.1%}" if not np.isnan(v) else "N/A",
                showarrow=False,
                font=dict(size=11, color="#444"),
                xref="x", yref="y",
            )

        n_rows = len(display_df)
        row_h  = max(36, min(56, 560 // n_rows))
        fig_h  = n_rows * row_h + 60   # +60 for benchmark annotation row + margins

        fig_heat.update_layout(
            height=fig_h,
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis=dict(
                autorange="reversed",
                # extend range to show benchmark label below last row
                range=[-0.5, n_rows + 0.5],
            ),
        )
        st.plotly_chart(fig_heat, width='stretch')

    st.markdown("---")

    all_etfs, bench_return = get_all_etf_returns(config, start_date, end_date)

    if all_etfs is None:
        st.warning("No data found. Please run 'data_collection.py' to fetch missing data.")
        return
    if not all_etfs:
        st.warning("No ETF data available for the selected date range.")
        return

    # ── Section 2: Top 10 / Bottom 10 ────────────────────────────────────────
    sorted_etfs = sorted(all_etfs, key=lambda x: x['Return'], reverse=True)

    def _render_etf_block(etfs, title, color_scale):
        st.subheader(title)
        df = pd.DataFrame(etfs)
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("**Performance Table**")
            st.dataframe(
                df[['Code', 'Name', 'Industry', 'Return']].style.format({
                    'Return': '{:.2%}',
                }),
                hide_index=True, width='stretch',
            )
        with col2:
            st.markdown("**Absolute Return**")
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df['Return'],
                y=[f"{row['Code']}<br>{row['Industry']}" for _, row in df.iterrows()],
                orientation='h',
                marker=dict(color=df['Return'], colorscale=color_scale, showscale=False),
                text=df['Return'].apply(lambda x: f'{x:.2%}'),
                textposition='auto',
            ))
            fig.update_layout(
                xaxis_title="Return", xaxis_tickformat='.1%',
                height=400, margin=dict(l=150, r=20, t=20, b=40),
                yaxis={'categoryorder': 'total ascending'},
            )
            st.plotly_chart(fig, width='stretch')

    _render_etf_block(sorted_etfs[:10],  "🏆 Top 10 Performing ETFs",    'RdYlGn')
    st.markdown("---")
    _render_etf_block(sorted_etfs[-10:], "📉 Bottom 10 Performing ETFs", 'RdYlGn_r')
    st.markdown("---")

    # ── Section 3: Turnover by Industry ──────────────────────────────────────
    st.subheader("📊 Turnover by Industry")
    vol_series = get_industry_volume_series(config, start_date, end_date)

    if vol_series:
        vol_df = pd.DataFrame({label: series for label, series in sorted(vol_series.items())})
        st.plotly_chart(build_volume_chart(vol_df), width='stretch')

        st.markdown("**1-Month vs 3-Month Avg Turnover Ratio by Industry**")
        turnover_cmp = get_industry_turnover_comparison(config, end_date)
        if turnover_cmp:
            industries = list(turnover_cmp.keys())
            t1m = [turnover_cmp[ind]['1M'] for ind in industries]
            t3m = [turnover_cmp[ind]['3M'] for ind in industries]
            # ratio: 1M relative to 3M avg-per-month; 1.0 = same as 3M avg
            ratios = [
                (v1 / v3 if v3 else float('nan'))
                for v1, v3 in zip(t1m, t3m)
            ]
            colors = ['steelblue' if r >= 1 else 'lightcoral' for r in ratios]
            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(
                x=industries,
                y=ratios,
                marker_color=colors,
                text=[f"{r:.2f}x" if not (r != r) else 'N/A' for r in ratios],
                textposition='outside',
            ))
            fig_cmp.add_hline(
                y=1.0,
                line_dash='dash',
                line_color='gray',
                annotation_text='3M avg baseline',
                annotation_position='top right',
            )
            fig_cmp.update_layout(
                height=max(350, len(industries) * 25),
                margin=dict(l=0, r=0, t=20, b=80),
                yaxis_title="1M / 3M Avg Ratio",
                yaxis=dict(tickformat='.2f'),
                xaxis_tickangle=-30,
                showlegend=False,
            )
            st.plotly_chart(fig_cmp, width='stretch')
    else:
        st.info("No turnover data available.")
