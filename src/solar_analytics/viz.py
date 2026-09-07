"""Plotly figures.

Palette: green = solar, amber = caution, red = grid, blue = export.
Any figure using GHI-based PR must carry the tilt caveat in its subtitle --
`_with_caveat` enforces that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .metrics import PR_TILT_CAVEAT

GREEN, AMBER, RED, BLUE, GREY = "#6ee7a0", "#e8c97a", "#e89a7a", "#7ab5e8", "#7d968a"

LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0f0c",
    plot_bgcolor="#111a15",
    font=dict(family="ui-sans-serif, -apple-system, Segoe UI, Roboto", size=12, color="#dfe8e2"),
    margin=dict(l=60, r=30, t=70, b=60),
    legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0),
)


def _with_caveat(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=dict(
            text=f"{title}<br><sub style='color:{GREY}'>⚠ {PR_TILT_CAVEAT[:110]}…</sub>",
            font=dict(size=16),
        ),
        **LAYOUT,
    )
    return fig


def yield_vs_ghi(summary: pd.DataFrame) -> go.Figure:
    """The single most informative plot: slope of the fit IS the performance ratio."""
    x, y = summary["ghi"], summary["specific_yield"]
    slope = float(np.polyfit(x, y, 1)[0])
    xs = np.linspace(x.min() * 0.95, x.max() * 1.05, 50)

    fig = go.Figure()
    fig.add_scatter(
        x=xs, y=slope * xs, mode="lines", name=f"fit (slope ≈ PR = {slope:.2f})",
        line=dict(color=GREY, dash="dash", width=1.5),
    )
    fig.add_scatter(
        x=x, y=y, mode="markers+text", text=summary["month"], textposition="top center",
        name="billing period", marker=dict(size=14, color=GREEN,
                                           line=dict(color="#0a0f0c", width=2)),
    )
    fig.update_layout(
        xaxis_title="GHI (kWh/m²/day)", yaxis_title="Specific yield (kWh/kWp/day)",
    )
    return _with_caveat(fig, f"Yield vs Irradiance · n={len(summary)}")


def pr_and_kt(summary: pd.DataFrame) -> go.Figure:
    """Separates system health (PR) from weather (Kt)."""
    fig = go.Figure()
    fig.add_bar(x=summary["month"], y=summary["pr_ghi"], name="PR (GHI-based) %",
                marker_color=GREEN, opacity=0.85)
    fig.add_scatter(x=summary["month"], y=summary["kt"] * 100, name="Clearness index Kt ×100",
                    mode="lines+markers", line=dict(color=AMBER, width=2.5),
                    marker=dict(size=9), yaxis="y2")
    fig.update_layout(
        yaxis=dict(title="Performance Ratio (%)", range=[0, 110]),
        yaxis2=dict(title="Kt ×100", overlaying="y", side="right", range=[0, 110],
                    showgrid=False),
    )
    return _with_caveat(fig, "System Health vs Weather")


def energy_balance(summary: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_bar(x=summary["month"], y=summary["self_used_kwh"], name="Met by solar",
                marker_color=GREEN)
    fig.add_bar(x=summary["month"], y=summary["import_kwh"], name="Bought from grid",
                marker_color=RED)
    fig.add_scatter(x=summary["month"], y=summary["export_kwh"], name="Exported",
                    mode="lines+markers", line=dict(color=BLUE, width=2.5, dash="dot"))
    fig.update_layout(barmode="stack", yaxis_title="kWh", title="Energy Balance", **LAYOUT)
    return fig


def scenario_comparison(scenarios: list) -> go.Figure:
    names = [s.name for s in scenarios]
    kwh = [s.annual_kwh for s in scenarios]
    colors = [GREY] + [GREEN] * (len(scenarios) - 1)
    fig = go.Figure(go.Bar(x=kwh, y=names, orientation="h", marker_color=colors,
                           text=[f"{k:,.0f} kWh" for k in kwh], textposition="auto"))
    fig.update_layout(xaxis_title="Projected annual generation (kWh)",
                      title="Scenarios (all modelled estimates)", **LAYOUT)
    return fig


def soiling_probe(summary: pd.DataFrame) -> go.Figure:
    """Rain vs PR. UNDERPOWERED at n=6 -- shown as a hypothesis, not a result."""
    fig = go.Figure(go.Scatter(
        x=summary["rain_days"], y=summary["pr_ghi_tcorr"], mode="markers+text",
        text=summary["month"], textposition="top center",
        marker=dict(size=14, color=AMBER, line=dict(color="#0a0f0c", width=2)),
    ))
    fig.update_layout(
        xaxis_title="Rain days in period", yaxis_title="Temp-corrected PR (%)",
        title=dict(text="Soiling probe<br><sub style='color:#e89a7a'>"
                        f"n={len(summary)} — underpowered. Hypothesis only, not a result."
                        "</sub>"),
        **LAYOUT,
    )
    return fig
