"""
Reusable Plotly chart builders shared across pages.
"""

import plotly.graph_objects as go


def build_volume_chart(vol_df, height=400):
    """
    Render a volume DataFrame as a 7-day rolling-average normalised line chart.
    Each series is normalised to its own mean = 1 so that assets with very
    different absolute volumes are all visible on the same axis.
    """
    fig     = go.Figure()
    smoothed = vol_df.rolling(7, min_periods=1).mean()
    normed   = smoothed.div(smoothed.mean().replace(0, 1))

    for col in normed.columns:
        fig.add_trace(go.Scatter(
            x=normed.index, y=normed[col],
            mode='lines', name=col,
            line=dict(width=2),
            hovertemplate="%{fullData.name}<br>Relative Vol: %{y:.2f}x<extra></extra>",
        ))

    fig.add_hline(
        y=1, line_dash="dot", line_color="grey", line_width=1,
        annotation_text="avg=1", annotation_position="right",
    )
    fig.update_layout(
        hovermode="x unified",
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        yaxis_title="Relative Volume (7d avg, mean=1×)",
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
    )
    return fig
