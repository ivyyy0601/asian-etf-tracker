"""
Pair Analysis page — deep statistical comparison of exactly two assets.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy import stats as scipy_stats
from statsmodels.tsa.stattools import adfuller, coint, acf
from statsmodels.regression.linear_model import OLS
from statsmodels.tools import add_constant

from utils.data import get_pair_data
from utils.charts import build_volume_chart


def _build_asset_list(configs):
    all_assets = []
    for market, config in configs.items():
        b = config['benchmark']
        all_assets.append({
            "label":    f"[{market}] {b['name']} ({b['code']})",
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


def render_pair_analysis_page(configs, start_date, end_date):
    st.header("🔬 Pair Analysis")
    st.caption("Two-asset deep-dive: price & volume overlay, single-asset statistics, and cross-asset statistical tests.")

    all_assets   = _build_asset_list(configs)
    all_labels   = [a['label'] for a in all_assets]
    bench_labels = [a['label'] for a in all_assets if a['industry'] == 'benchmark']
    default_a    = bench_labels[0] if bench_labels else all_labels[0]
    default_b    = bench_labels[1] if len(bench_labels) > 1 else all_labels[1]

    col1, col2 = st.columns(2)
    with col1:
        sel_a = st.selectbox("Asset A", all_labels, index=all_labels.index(default_a))
    with col2:
        sel_b = st.selectbox("Asset B", all_labels, index=all_labels.index(default_b))

    if sel_a == sel_b:
        st.warning("Please select two different assets.")
        return

    asset_a = next(a for a in all_assets if a['label'] == sel_a)
    asset_b = next(a for a in all_assets if a['label'] == sel_b)
    name_a  = f"{asset_a['name']} ({asset_a['code']})"
    name_b  = f"{asset_b['name']} ({asset_b['code']})"

    df_close, df_volume, df_returns = get_pair_data(
        configs, asset_a, asset_b, start_date, end_date
    )

    if df_close.empty:
        st.warning("Could not load data for one or both assets in this date range.")
        return

    col_a, col_b = df_close.columns[0], df_close.columns[1]
    ret_a, ret_b = df_returns[col_a], df_returns[col_b]
    n = len(df_returns)

    tab_price, tab_single, tab_pair = st.tabs([
        "📈 Price & Volume",
        "📊 Single-Asset Stats",
        "🔗 Pair Statistics",
    ])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1 — Price & Volume
    # ════════════════════════════════════════════════════════════════════════
    with tab_price:
        cum_a  = (df_close[col_a] / df_close[col_a].iloc[0]) - 1
        cum_b  = (df_close[col_b] / df_close[col_b].iloc[0]) - 1
        spread = cum_a - cum_b

        fig_p = go.Figure()
        fig_p.add_trace(go.Scatter(x=cum_a.index, y=cum_a, name=name_a,
                                    mode='lines', line=dict(width=2)))
        fig_p.add_trace(go.Scatter(x=cum_b.index, y=cum_b, name=name_b,
                                    mode='lines', line=dict(width=2, dash='dash')))
        fig_p.update_layout(
            title="Cumulative Return", yaxis_tickformat='.1%',
            hovermode="x unified", height=380,
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        st.plotly_chart(fig_p, width='stretch')

        fig_sp = go.Figure()
        fig_sp.add_trace(go.Scatter(x=spread.index, y=spread, mode='lines',
                                     fill='tozeroy', line=dict(color='#AB63FA', width=1.5)))
        fig_sp.add_hline(y=0, line_dash="dot", line_color="grey")
        fig_sp.update_layout(
            title=f"Return Spread (A − B): {name_a} minus {name_b}",
            yaxis_tickformat='.1%', hovermode="x unified",
            height=250, margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_sp, width='stretch')

        if not df_volume.empty:
            st.plotly_chart(build_volume_chart(df_volume, height=280), width='stretch')

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2 — Single-asset statistics
    # ════════════════════════════════════════════════════════════════════════
    with tab_single:

        def _single_stats(price_series, ret_series, label):
            total_ret    = (price_series.iloc[-1] / price_series.iloc[0]) - 1
            trading_days = len(ret_series)
            ann_ret      = (1 + total_ret) ** (252 / trading_days) - 1 if trading_days > 0 else np.nan
            ann_vol      = ret_series.std() * np.sqrt(252)
            sharpe       = ann_ret / ann_vol if ann_vol > 0 else np.nan
            drawdown     = (price_series - price_series.cummax()) / price_series.cummax()
            max_dd       = drawdown.min()
            skew         = float(scipy_stats.skew(ret_series.dropna()))
            kurt         = float(scipy_stats.kurtosis(ret_series.dropna()))
            adf_res      = adfuller(np.log(price_series.dropna()), autolag='AIC')
            adf_stat, adf_p = adf_res[0], adf_res[1]
            return {
                "Metric": [
                    "Total Return", "Ann. Return", "Ann. Volatility",
                    "Sharpe Ratio", "Max Drawdown",
                    "Skewness", "Excess Kurtosis",
                    "ADF Statistic", "ADF p-value", "Price Stationary?",
                ],
                label: [
                    f"{total_ret:.2%}", f"{ann_ret:.2%}", f"{ann_vol:.2%}",
                    f"{sharpe:.2f}",    f"{max_dd:.2%}",
                    f"{skew:.3f}",      f"{kurt:.3f}",
                    f"{adf_stat:.3f}",  f"{adf_p:.4f}",
                    "Yes ✅" if adf_p < 0.05 else "No ❌",
                ],
            }

        sa = _single_stats(df_close[col_a], ret_a, name_a)
        sb = _single_stats(df_close[col_b], ret_b, name_b)
        st.subheader("Descriptive & Risk Statistics")
        st.dataframe(
            pd.DataFrame({"Metric": sa["Metric"], name_a: sa[name_a], name_b: sb[name_b]}),
            hide_index=True, width='stretch',
        )

        st.markdown("---")

        st.subheader("Daily Return Distribution")
        c1, c2 = st.columns(2)
        for col_n, ret_s, nm in [(c1, ret_a, name_a), (c2, ret_b, name_b)]:
            with col_n:
                mu, sigma   = ret_s.mean(), ret_s.std()
                x_range     = np.linspace(ret_s.min(), ret_s.max(), 200)
                y_norm      = scipy_stats.norm.pdf(x_range, mu, sigma) * len(ret_s) * (ret_s.max() - ret_s.min()) / 60
                fig_h = go.Figure()
                fig_h.add_trace(go.Histogram(x=ret_s, nbinsx=60,
                                              marker_color='#636EFA', opacity=0.75))
                fig_h.add_trace(go.Scatter(x=x_range, y=y_norm, mode='lines',
                                            line=dict(color='red', width=2), name='Normal fit'))
                fig_h.update_layout(title=nm, height=300, xaxis_tickformat='.1%',
                                     margin=dict(l=0, r=0, t=40, b=0), showlegend=False)
                st.plotly_chart(fig_h, width='stretch')

        st.markdown("---")

        st.subheader("Autocorrelation of Daily Returns (ACF)")
        st.caption("Bars beyond the dashed band suggest serial correlation / momentum or mean-reversion.")
        max_lags = min(40, n // 3)
        ci       = 1.96 / np.sqrt(n)
        c1, c2   = st.columns(2)
        for col_n, ret_s, nm in [(c1, ret_a, name_a), (c2, ret_b, name_b)]:
            with col_n:
                acf_vals, confint = acf(ret_s, nlags=max_lags, alpha=0.05)
                lags   = list(range(len(acf_vals)))
                colors = ['#EF553B' if abs(v) > abs(confint[i][1] - v) else '#636EFA'
                          for i, v in enumerate(acf_vals)]
                fig_acf = go.Figure()
                fig_acf.add_trace(go.Bar(x=lags[1:], y=acf_vals[1:],
                                          marker_color=colors[1:], name='ACF'))
                fig_acf.add_hline(y= ci, line_dash='dash', line_color='grey', line_width=1)
                fig_acf.add_hline(y=-ci, line_dash='dash', line_color='grey', line_width=1)
                fig_acf.update_layout(title=nm, height=280,
                                       margin=dict(l=0, r=0, t=40, b=0))
                st.plotly_chart(fig_acf, width='stretch')

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3 — Pair statistics
    # ════════════════════════════════════════════════════════════════════════
    with tab_pair:

        # ── Rolling correlation ───────────────────────────────────────────────
        st.subheader("Rolling Correlation")
        fig_rc = go.Figure()
        for w, dash in zip([21, 63], ['solid', 'dash']):
            roll_corr = ret_a.rolling(w).corr(ret_b)
            fig_rc.add_trace(go.Scatter(x=roll_corr.index, y=roll_corr,
                                         mode='lines', name=f'{w}-day',
                                         line=dict(width=2, dash=dash)))
        fig_rc.add_hline(y=0, line_dash='dot', line_color='grey')
        fig_rc.update_layout(
            yaxis=dict(title="Pearson r", range=[-1, 1]),
            hovermode="x unified", height=320,
            margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_rc, width='stretch')

        pearson_r,  pearson_p  = scipy_stats.pearsonr(ret_a, ret_b)
        spearman_r, spearman_p = scipy_stats.spearmanr(ret_a, ret_b)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Pearson r",   f"{pearson_r:.3f}")
        c2.metric("Pearson p",   f"{pearson_p:.4f}")
        c3.metric("Spearman ρ",  f"{spearman_r:.3f}")
        c4.metric("Spearman p",  f"{spearman_p:.4f}")

        st.markdown("---")

        # ── OLS scatter ───────────────────────────────────────────────────────
        st.subheader("Return Scatter & OLS Regression")
        slope, intercept, r_val, p_val, _ = scipy_stats.linregress(ret_b, ret_a)
        x_line = np.linspace(ret_b.min(), ret_b.max(), 200)
        fig_sc = go.Figure()
        fig_sc.add_trace(go.Scatter(x=ret_b, y=ret_a, mode='markers',
                                     marker=dict(size=4, opacity=0.5, color='#636EFA'),
                                     hovertemplate=f"{name_b}: %{{x:.3%}}<br>{name_a}: %{{y:.3%}}<extra></extra>"))
        fig_sc.add_trace(go.Scatter(x=x_line, y=slope * x_line + intercept,
                                     mode='lines', name=f'β={slope:.3f}',
                                     line=dict(color='red', width=2)))
        fig_sc.update_layout(
            xaxis=dict(title=f"{name_b} return", tickformat='.1%'),
            yaxis=dict(title=f"{name_a} return", tickformat='.1%'),
            height=380, margin=dict(l=0, r=0, t=30, b=0),
        )
        st.plotly_chart(fig_sc, width='stretch')

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Beta (β)",    f"{slope:.3f}",     help="Sensitivity of A to B movements")
        c2.metric("Alpha (α)",   f"{intercept:.4%}", help="Excess return of A unexplained by B")
        c3.metric("R²",          f"{r_val**2:.3f}",  help="Fraction of A's variance explained by B")
        c4.metric("OLS p-value", f"{p_val:.4f}",     help="H₀: β = 0")

        st.markdown("---")

        # ── Cointegration ─────────────────────────────────────────────────────
        st.subheader("Cointegration Test (Engle-Granger)")
        st.caption("If cointegrated, the two price series share a long-run equilibrium — useful for pairs trading.")
        coint_t, coint_p, _ = coint(df_close[col_a], df_close[col_b])
        cointegrated = coint_p < 0.05
        c1, c2, c3 = st.columns(3)
        c1.metric("Test Statistic", f"{coint_t:.3f}")
        c2.metric("p-value",        f"{coint_p:.4f}")
        c3.metric("Cointegrated?",  "Yes ✅" if cointegrated else "No ❌")

        if cointegrated:
            st.markdown("**Long-run spread (cointegration residual)**")
            ols     = OLS(df_close[col_a], add_constant(df_close[col_b])).fit()
            resid   = pd.Series(ols.resid, index=df_close.index)
            z_score = (resid - resid.mean()) / resid.std()
            fig_z   = go.Figure()
            fig_z.add_trace(go.Scatter(x=z_score.index, y=z_score, mode='lines',
                                        name='Z-score', line=dict(width=1.5, color='#00CC96')))
            for lvl, clr in [(2, 'red'), (-2, 'red'), (1, 'orange'), (-1, 'orange')]:
                fig_z.add_hline(y=lvl, line_dash='dash', line_color=clr,
                                annotation_text=f'{lvl:+d}σ', annotation_position='right',
                                line_width=1)
            fig_z.update_layout(height=280, margin=dict(l=0, r=0, t=20, b=0),
                                  yaxis_title="Z-score")
            st.plotly_chart(fig_z, width='stretch')

        st.markdown("---")

        # ── Rolling Beta ──────────────────────────────────────────────────────
        st.subheader("Rolling Beta (A vs B, 63-day window)")
        st.caption("How much A moves per 1% move in B, over time.")
        roll_beta = ret_a.rolling(63).cov(ret_b) / ret_b.rolling(63).var()
        fig_rb = go.Figure()
        fig_rb.add_trace(go.Scatter(x=roll_beta.index, y=roll_beta, mode='lines',
                                     name='Beta', line=dict(width=2, color='#FFA15A')))
        fig_rb.add_hline(y=1, line_dash='dot', line_color='grey', line_width=1,
                          annotation_text='β=1', annotation_position='right')
        fig_rb.add_hline(y=0, line_dash='dot', line_color='grey', line_width=1)
        fig_rb.update_layout(height=280, hovermode="x unified",
                               margin=dict(l=0, r=0, t=20, b=0), yaxis_title="Beta")
        st.plotly_chart(fig_rb, width='stretch')

        st.markdown("---")

        # ── Rolling Volatility ────────────────────────────────────────────────
        st.subheader("Rolling 21-day Annualised Volatility")
        vol_a_roll = ret_a.rolling(21).std() * np.sqrt(252)
        vol_b_roll = ret_b.rolling(21).std() * np.sqrt(252)
        fig_vol = go.Figure()
        fig_vol.add_trace(go.Scatter(x=vol_a_roll.index, y=vol_a_roll,
                                      name=name_a, mode='lines', line=dict(width=2)))
        fig_vol.add_trace(go.Scatter(x=vol_b_roll.index, y=vol_b_roll,
                                      name=name_b, mode='lines', line=dict(width=2, dash='dash')))
        fig_vol.update_layout(yaxis_tickformat='.1%', hovermode="x unified",
                               height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_vol, width='stretch')

        st.markdown("---")

        # ── Lead-Lag cross-correlation ────────────────────────────────────────
        st.subheader("Lead-Lag Cross-Correlation")
        st.caption("Does one asset's return today predict the other's tomorrow? Positive lag = A leads B.")
        max_lag   = min(10, n // 10)
        lags      = list(range(-max_lag, max_lag + 1))
        cc        = [ret_a.corr(ret_b.shift(-lag)) for lag in lags]
        sig_band  = 1.96 / np.sqrt(n)
        colors_cc = ['#EF553B' if abs(v) > sig_band else '#636EFA' for v in cc]
        fig_cc = go.Figure()
        fig_cc.add_trace(go.Bar(x=lags, y=cc, marker_color=colors_cc, name='Cross-corr'))
        fig_cc.add_hline(y= sig_band, line_dash='dash', line_color='grey', line_width=1)
        fig_cc.add_hline(y=-sig_band, line_dash='dash', line_color='grey', line_width=1)
        fig_cc.update_layout(
            xaxis_title="Lag (days) — negative = B leads A",
            yaxis_title="Correlation",
            height=300, margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_cc, width='stretch')
