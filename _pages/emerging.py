"""
Emerging ETFs page — A-Share post-2025 listings.
"""

import plotly.graph_objects as go
import streamlit as st

from utils.config import load_emerging_config
from utils.data import get_emerging_etf_data, INDUSTRY_DISPLAY


def render_emerging_page(start_date, end_date):
    st.header("🌱 Emerging ETFs — A-Share (Post-2025 Listings)")

    emerging_config = load_emerging_config()
    if emerging_config is None:
        st.error("Emerging config file not found.")
        return

    all_industries  = list(emerging_config['industries'].keys())
    industry_labels = {k: INDUSTRY_DISPLAY.get(k, k.replace('_', ' ').title())
                       for k in all_industries}

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.header("Emerging ETF Filters")
    selected_industry_keys = st.sidebar.multiselect(
        "Filter by Industry",
        options=all_industries,
        default=all_industries,
        format_func=lambda k: industry_labels[k],
    )

    if not selected_industry_keys:
        st.info("Select at least one industry in the sidebar.")
        return

    records, price_df = get_emerging_etf_data(
        emerging_config, selected_industry_keys, start_date, end_date
    )

    if not records:
        st.warning(
            "No data found for the selected industries. "
            "Run `data_collection.py` to fetch emerging ETF data first."
        )
        return

    import pandas as pd
    records_df = pd.DataFrame(records)

    # Colour palette mapped to industries
    unique_industries = list({r["Industry Key"] for r in records})
    _palette = [
        "#636EFA","#EF553B","#00CC96","#AB63FA","#FFA15A",
        "#19D3F3","#FF6692","#B6E880","#FF97FF","#FECB52","#72B7B2",
    ]
    ind_color = {ind: _palette[i % len(_palette)] for i, ind in enumerate(unique_industries)}

    # ── 1. Price Trend ────────────────────────────────────────────────────────
    st.subheader("📈 Price Trend (Normalised from First Available Day)")

    if not price_df.empty:
        industry_keys_for_labels = {r["Label"]: r["Industry Key"] for r in records}
        fig_trend = go.Figure()
        fig_trend.add_hline(y=0, line_dash="dot", line_color="grey", line_width=1)
        for col in price_df.columns:
            ind_key = industry_keys_for_labels.get(col, "")
            fig_trend.add_trace(go.Scatter(
                x=price_df.index, y=price_df[col], mode='lines', name=col,
                line=dict(color=ind_color.get(ind_key, "#888"), width=1.8),
                hovertemplate="%{fullData.name}<br>Return: %{y:.2%}<extra></extra>",
            ))
        fig_trend.update_layout(
            yaxis_tickformat='.0%', hovermode="x unified", height=480,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, font=dict(size=11)),
        )
        st.plotly_chart(fig_trend, width='stretch')
    else:
        st.info("No price data available for trend chart.")

    st.markdown("---")

    # ── 2. Total Return bar chart (top 5 + expander) ──────────────────────────
    st.subheader("📊 Total Return by ETF")
    all_sorted = records_df.sort_values("Total Return", ascending=False)

    def _make_bar_chart(df):
        df_asc  = df.sort_values("Total Return", ascending=True)
        colors  = ["#EF553B" if v < 0 else "#00CC96" for v in df_asc["Total Return"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_asc["Total Return"],
            y=df_asc["Code"] + " " + df_asc["Name"],
            orientation='h', marker_color=colors,
            text=[f"{v:.1%}" for v in df_asc["Total Return"]],
            textposition='outside',
            hovertemplate="%{y}<br>Return: %{x:.2%}<extra></extra>",
        ))
        fig.add_vline(x=0, line_color="black", line_width=1)
        fig.update_layout(
            xaxis_tickformat='.0%',
            height=max(280, len(df_asc) * 32),
            margin=dict(l=0, r=70, t=20, b=0),
            showlegend=False,
        )
        return fig

    st.plotly_chart(_make_bar_chart(all_sorted.head(5)), width='stretch')
    with st.expander(f"Show all {len(all_sorted)} ETFs"):
        st.plotly_chart(_make_bar_chart(all_sorted), width='stretch')

    st.markdown("---")

    # ── 3. Bubble chart: Scale vs Return ─────────────────────────────────────
    st.subheader("🏭 Industry Breakdown — Fund Scale vs Return")

    fig_bubble = go.Figure()
    for ind_key in unique_industries:
        ind_records = [r for r in records if r["Industry Key"] == ind_key]
        if not ind_records:
            continue
        best_code = max(ind_records, key=lambda r: r["Total Return"])["Code"]
        labels    = [r["Code"] if r["Code"] == best_code else "" for r in ind_records]
        fig_bubble.add_trace(go.Scatter(
            x=[r["Total Return"]  for r in ind_records],
            y=[r["Scale (B CNY)"] for r in ind_records],
            mode='markers+text',
            name=INDUSTRY_DISPLAY.get(ind_key, ind_key),
            marker=dict(
                size=[max(10, min(r["Scale (B CNY)"] * 0.5, 55)) for r in ind_records],
                color=ind_color.get(ind_key, "#888"),
                opacity=0.7,
                line=dict(width=1.5, color='white'),
            ),
            text=labels,
            textposition="top center",
            textfont=dict(size=11, color="#333"),
            customdata=[[r["Code"], r["Name"], r["Scale (B CNY)"]] for r in ind_records],
            hovertemplate=(
                "<b>%{customdata[0]} %{customdata[1]}</b><br>"
                "Return: %{x:.2%}<br>"
                "Scale: %{customdata[2]:.1f}B CNY"
                "<extra>%{fullData.name}</extra>"
            ),
        ))

    fig_bubble.add_vline(x=0, line_dash="dot", line_color="grey", line_width=1)
    fig_bubble.update_layout(
        xaxis=dict(title="Total Return", tickformat='.0%'),
        yaxis=dict(title="Fund Scale (B CNY)"),
        height=520, margin=dict(l=0, r=20, t=30, b=0),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=1.01, font=dict(size=11)),
    )
    st.plotly_chart(fig_bubble, width='stretch')

    st.markdown("---")

    # ── 4. Details table ──────────────────────────────────────────────────────
    st.subheader("📋 Emerging ETF Details")

    def _color_return(val):
        color = "green" if val > 0 else ("red" if val < 0 else "black")
        return f"color: {color}"

    display_df = records_df[[
        "Code", "Name", "Industry", "Listing Date", "Scale (B CNY)",
        "Index", "Currency", "Total Return", "Weekly Growth", "Days Listed",
    ]].sort_values("Total Return", ascending=False).reset_index(drop=True)

    st.dataframe(
        display_df.style
            .format({"Total Return": "{:.2%}", "Weekly Growth": "{:.2%}"})
            .map(_color_return, subset=["Total Return", "Weekly Growth"]),
        width='stretch', hide_index=True,
    )
