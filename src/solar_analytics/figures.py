"""The article's charts, defined once in Plotly.

The same figure objects are rendered three ways:
  * interactive, in site/index.html (colours swapped for theme tokens at runtime)
  * interactive, in the Streamlit app
  * static PNG, for the PDF and the blog post (via kaleido)

Colours come from PALETTE. Every colour string is produced by `col()`, so the
HTML renderer can map each one back to a theme token by exact string match.
"""

from __future__ import annotations

import calendar

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

PALETTE = {
    "ink": "#1E252A", "mut": "#6B767D", "grid": "#E4E0D6", "card": "#FFFFFF",
    "sun": "#C2851E", "rain": "#3C6A89", "pv": "#2B6350", "dim": "#9A5B3D", "hi": "#7C4E08",
    "ramp0": "#F1ECDD", "ramp1": "#E3C06C",
}
FONT = '"Source Sans 3", "Source Sans Pro", system-ui, -apple-system, "Segoe UI", "DejaVu Sans", sans-serif'


def col(name: str, alpha: float = 1.0) -> str:
    h = PALETTE[name].lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return PALETTE[name] if alpha >= 1 else f"rgba({r},{g},{b},{alpha:g})"


def _base(fig: go.Figure, height: int = 340, legend: bool = True, **kw) -> go.Figure:
    fig.update_layout(
        template="none", height=height, margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=13, color=col("mut")),
        hoverlabel=dict(font=dict(family=FONT, size=12)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0,
                    font=dict(size=12, color=col("ink")), bgcolor="rgba(0,0,0,0)"),
        bargap=0.25, **kw)
    fig.update_xaxes(showgrid=False, linecolor=col("grid"), ticks="", automargin=True,
                     tickfont=dict(color=col("mut")), title_font=dict(size=12, color=col("mut")))
    fig.update_yaxes(gridcolor=col("grid"), zeroline=False, linecolor=col("grid"), automargin=True,
                     tickfont=dict(color=col("mut")), title_font=dict(size=12, color=col("mut")))
    return fig


def _labels(B):
    return [m["month"] for m in B["monthly"]]


# --------------------------------------------------------------------------- figures

def fig_daily(B):
    d = B["daily"]
    x = [r["d"] for r in d]
    g = np.array([np.nan if r["g"] is None else r["g"] for r in d], float)
    roll = [None if np.isnan(v) else round(float(v), 2)
            for v in __import__("pandas").Series(g).rolling(7, center=True, min_periods=4).mean()]
    rain = [r["r"] for r in d]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=x, y=rain, name="Rain, mm", marker_color=col("rain", .75),
                         hovertemplate="%{x|%d %b}: %{y:.1f} mm<extra></extra>"), secondary_y=True)
    fig.add_trace(go.Scatter(x=x, y=g, name="Sunlight", mode="lines", line=dict(color=col("sun", .55), width=1),
                             fill="tozeroy", fillcolor=col("sun", .14),
                             hovertemplate="%{x|%d %b}: %{y:.2f} kWh/m²<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=roll, name="7-day mean", mode="lines", line=dict(color=col("sun"), width=2.4),
                             hoverinfo="skip"), secondary_y=False)
    _base(fig, 330)
    fig.update_yaxes(title_text="sunlight, kWh/m²/day", range=[0, 14], tickvals=[0, 2, 4, 6, 8], secondary_y=False)
    fig.update_yaxes(title_text="rain, mm/day", range=[150, 0], tickvals=[0, 20, 40, 60], tickmode="array", showgrid=False,
                     secondary_y=True)
    fig.update_xaxes(tickformat="%b", dtick="M1")
    return fig


def fig_calendar(B):
    import pandas as pd
    d = pd.DataFrame(B["daily"])
    d["d"] = pd.to_datetime(d["d"])
    months = sorted({(t.year, t.month) for t, g in zip(d["d"], d["g"], strict=True) if g == g and g is not None})
    z, hover, rx, ry, rs, rt = [], [], [], [], [], []
    for (yr, mo) in months:
        row, hrow = [], []
        nd = calendar.monthrange(yr, mo)[1]
        for day in range(1, 32):
            hit = d[(d.d.dt.year == yr) & (d.d.dt.month == mo) & (d.d.dt.day == day)]
            if day > nd or hit.empty or pd.isna(hit.g.iloc[0]):
                row.append(None)
                hrow.append("")
                continue
            gv, rv = float(hit.g.iloc[0]), hit.r.iloc[0]
            row.append(gv)
            hrow.append(f"{day} {calendar.month_abbr[mo]}: sun {gv:.1f} kWh/m², rain {0 if pd.isna(rv) else rv:.1f} mm")
            if rv and not pd.isna(rv) and rv >= 1:
                rx.append(day)
                ry.append(calendar.month_abbr[mo])
                rs.append(float(min(4 + rv / 3.5, 22)))
                rt.append(hrow[-1])
        z.append(row)
        hover.append(hrow)
    ylab = [calendar.month_abbr[m] for _, m in months]
    fig = go.Figure(go.Heatmap(
        z=z, x=list(range(1, 32)), y=ylab, text=hover, hovertemplate="%{text}<extra></extra>",
        colorscale=[[0, col("ramp0")], [.35, col("ramp1")], [.7, col("sun")], [1, col("hi")]],
        zmin=0.5, zmax=7.4, xgap=2, ygap=2,
        colorbar=dict(title=dict(text="kWh/m²", side="right", font=dict(size=11)), thickness=10, len=.9,
                      outlinewidth=0, tickfont=dict(size=11))))
    fig.add_trace(go.Scatter(x=rx, y=ry, mode="markers", name="Rain (size = mm)", text=rt,
                             hovertemplate="%{text}<extra></extra>",
                             marker=dict(size=rs, color=col("rain", .55), line=dict(width=0))))
    _base(fig, 330)
    fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
    fig.update_xaxes(dtick=5, range=[0.5, 31.5], title_text="day of month")
    return fig


def fig_gen(B):
    M = B["monthly"]
    L = _labels(B)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=L, y=[m["gen_day"] for m in M], name="Generation, kWh/day", marker_color=col("pv"),
                         hovertemplate="%{x}: %{y:.1f} kWh/day<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=L, y=[m["ghi"] for m in M], name="Sunlight, kWh/m²/day", mode="lines+markers",
                             line=dict(color=col("sun"), width=2.4), marker=dict(size=8),
                             hovertemplate="%{x}: %{y:.2f} kWh/m²/day<extra></extra>"), secondary_y=True)
    _base(fig, 300)
    fig.update_yaxes(title_text="kWh/day", range=[0, 17], secondary_y=False)
    fig.update_yaxes(title_text="kWh/m²/day", range=[0, 7], dtick=1, tickmode="linear", showgrid=False, secondary_y=True)
    return fig


def fig_scatter(B):
    M = B["monthly"]
    f = B["fit"]
    xs = [m["ghi"] for m in M]
    ys = [m["gen_day"] for m in M]
    lo, hi = 2.8, 6.4
    pos = {"Feb": "top left", "Mar": "bottom right", "Apr": "bottom right", "May": "top left",
           "Jun": "top left", "Jul": "top left", "Aug": "bottom right", "Sep": "top left"}
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[lo, hi], y=[f["a"] * lo + f["c"], f["a"] * hi + f["c"]], mode="lines",
                             name="Fitted line", line=dict(color=col("sun"), width=2, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers+text", name="Billing month", text=_labels(B),
                             textposition=[pos.get(m, "top right") for m in _labels(B)],
                             textfont=dict(size=12, color=col("mut")),
                             marker=dict(size=11, color=col("pv"), line=dict(width=1.5, color=col("card"))),
                             hovertemplate="%{text}: sun %{x:.2f}, generation %{y:.1f} kWh/day<extra></extra>"))
    _base(fig, 300, legend=False)
    fig.update_xaxes(title_text="sunlight, kWh/m²/day", range=[lo, hi])
    fig.update_yaxes(title_text="generation, kWh/day", range=[6, 16.5])
    return fig


def fig_models(B):
    ms = sorted(B["models"], key=lambda m: -m["mae"])
    chosen = {"Sunlight only", "Physics: panel-plane sun × heat"}
    fig = go.Figure(go.Bar(
        y=[m["name"] for m in ms], x=[m["mae"] for m in ms], orientation="h",
        marker_color=[col("pv") if m["name"] in chosen else col("mut", .35) for m in ms],
        text=[f"{m['mae']:.1f}%" for m in ms], textposition="outside", cliponaxis=False,
        customdata=[[m["form"], m["params"], m["worst"]] for m in ms],
        hovertemplate="%{y}<br>%{customdata[0]}<br>%{customdata[1]} fitted parameter(s)"
                      "<br>mean miss %{x:.1f}%, worst %{customdata[2]:.0f}%<extra></extra>"))
    _base(fig, 300, legend=False)
    fig.update_xaxes(title_text="mean miss on the held-out month, %", range=[0, 30], showgrid=True,
                     gridcolor=col("grid"))
    fig.update_yaxes(showgrid=False)
    return fig


def fig_loo(B):
    L = _labels(B)
    errs = B["fit"]["loo"]
    fig = go.Figure(go.Bar(x=L, y=errs, marker_color=[col("dim") if abs(e) > 8 else col("pv", .6) for e in errs],
                           text=[f"{e:+.0f}%" for e in errs], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}: predicted %{y:+.1f}% vs metered<extra></extra>"))
    _base(fig, 280, legend=False)
    fig.update_yaxes(title_text="prediction error, %", range=[-17, 17], zeroline=True,
                     zerolinecolor=col("ink"), zerolinewidth=1)
    return fig


def fig_normal(B):
    N = B["normal"]
    L = [n["month"] for n in N]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=L, y=[n["ghi_normal"] for n in N], name="2016–2025 average (bar: range)",
                         marker_color=col("mut", .25),
                         error_y=dict(type="data", symmetric=False, color=col("mut"), thickness=1.2, width=6,
                                      array=[n["ghi_max"] - n["ghi_normal"] for n in N],
                                      arrayminus=[n["ghi_normal"] - n["ghi_min"] for n in N]),
                         hovertemplate="%{x} normal: %{y:.2f} kWh/m²/day<extra></extra>"))
    fig.add_trace(go.Scatter(x=L, y=[n["ghi_2026"] for n in N], name="2026", mode="markers+text",
                             marker=dict(size=12, color=col("sun"), symbol="diamond"),
                             text=[f"{n['pct']:+.0f}%" for n in N], textposition="middle right",
                             textfont=dict(size=11, color=col("ink")),
                             hovertemplate="%{x} 2026: %{y:.2f} kWh/m²/day (%{text} vs normal)<extra></extra>"))
    _base(fig, 300)
    fig.update_yaxes(title_text="sunlight, kWh/m²/day", range=[0, 7])
    return fig


def fig_resid(B):
    M = B["monthly"]
    L = _labels(B)
    r = [m["resid"] for m in M]
    fig = go.Figure(go.Bar(
        x=L, y=r, marker_color=[col("dim") if v < -5 else col("dim", .35) if v < 0 else col("pv", .55) for v in r],
        text=[f"{v:+.1f}%" for v in r], textposition="outside", cliponaxis=False,
        customdata=[[m["expected"], m["gen"]] for m in M],
        hovertemplate="%{x}: expected %{customdata[0]:.0f} kWh, metered %{customdata[1]:.0f} kWh"
                      "<br>residual %{y:+.1f}%<extra></extra>"))
    _base(fig, 300, legend=False)
    fig.update_yaxes(title_text="metered vs weather-expected, %", range=[-13, 11], zeroline=True,
                     zerolinecolor=col("ink"), zerolinewidth=1)
    return fig


def fig_forecast(B):
    F = B["forecast"]
    x = [f["label"] for f in F]
    act = {m["month"]: m["gen_day"] for m in B["monthly"]}
    seen = [act.get(calendar.month_abbr[f["month"]]) for f in F]
    seen_kwh = [None if s is None else round(s * f["days"], 1) for s, f in zip(seen, F, strict=True)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[f["p90"] for f in F], mode="lines", line=dict(width=0), hoverinfo="skip",
                             showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=[f["p10"] for f in F], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor=col("pv", .16), name="Range across 2016–2025 weather (10th–90th pct)",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=[f["mean"] for f in F], mode="lines+markers", name="Typical year (physics model)",
                             line=dict(color=col("pv"), width=2.6), marker=dict(size=7),
                             customdata=[[f["p10"], f["p90"]] for f in F],
                             hovertemplate="%{x}: %{y:.0f} kWh (range %{customdata[0]:.0f}–%{customdata[1]:.0f})<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=[f["regression"] for f in F], mode="lines", name="Simple sunlight line (cross-check)",
                             line=dict(color=col("sun"), width=1.8, dash="dash"),
                             hovertemplate="%{x}: %{y:.0f} kWh by the simple line<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=seen_kwh, mode="markers", name="Same month in 2026, as metered",
                             marker=dict(size=10, symbol="circle-open", color=col("ink"), line=dict(width=2)),
                             hovertemplate="%{x}: 2026 ran at %{y:.0f} kWh for this month<extra></extra>"))
    _base(fig, 340)
    fig.update_yaxes(title_text="kWh per month", range=[200, 520])
    return fig


def fig_backtest(B):
    bt = B["backtest"]
    mean = np.mean([b["kwh"] for b in bt])
    fig = go.Figure(go.Bar(x=[str(b["year"]) for b in bt], y=[b["kwh"] for b in bt], marker_color=col("pv", .7),
                           text=[f"{b['kwh']:,.0f}" for b in bt], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x} weather: %{y:,.0f} kWh<extra></extra>"))
    fig.add_hline(y=mean, line=dict(color=col("ink"), width=1, dash="dot"))
    _base(fig, 280, legend=False)
    fig.update_yaxes(title_text="kWh per year", range=[3800, 4950])
    return fig


def fig_balance(B):
    M = B["monthly"]
    L = _labels(B)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=L, y=[m["self"] for m in M], name="Solar used at home", marker_color=col("pv"),
                         offsetgroup="d", hovertemplate="%{x}: %{y:.0f} kWh of solar used directly<extra></extra>"))
    fig.add_trace(go.Bar(x=L, y=[m["imp"] for m in M], name="Bought from the grid", marker_color=col("rain", .35),
                         marker_line=dict(color=col("rain"), width=1), offsetgroup="d", base=[m["self"] for m in M],
                         hovertemplate="%{x}: %{y:.0f} kWh imported<extra></extra>"))
    fig.add_trace(go.Bar(x=L, y=[m["exp"] for m in M], name="Sent to the grid", marker_color=col("sun", .35),
                         marker_line=dict(color=col("sun"), width=1), offsetgroup="e",
                         hovertemplate="%{x}: %{y:.0f} kWh exported<extra></extra>"))
    _base(fig, 320)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="kWh per billing month")
    return fig


def fig_money(B):
    M = B["monthly"]
    L = _labels(B)
    cum = np.cumsum([m["saved"] for m in M]).tolist()
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=L, y=[m["billed"] for m in M], name="Paid", marker_color=col("rain", .35),
                         marker_line=dict(color=col("rain"), width=1),
                         hovertemplate="%{x}: paid ₹%{y:,.0f}<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Bar(x=L, y=[m["saved"] for m in M], name="Saved by solar", marker_color=col("pv"),
                         hovertemplate="%{x}: saved ₹%{y:,.0f}<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=L, y=cum, name="Saved so far", mode="lines+markers",
                             line=dict(color=col("sun"), width=2.4), marker=dict(size=7),
                             hovertemplate="%{x}: ₹%{y:,.0f} saved to date<extra></extra>"), secondary_y=True)
    _base(fig, 320)
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="₹ per bill", tickformat=",", secondary_y=False)
    fig.update_yaxes(title_text="₹ saved to date", tickformat=",", showgrid=False, range=[0, 20000], dtick=5000, tickmode="linear", secondary_y=True)
    return fig


def fig_demand(B):
    M = B["monthly"]
    L = _labels(B)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=L, y=[m["dem_occ"] for m in M], name="Household demand per occupied day",
                         marker_color=col("ink", .3),
                         hovertemplate="%{x}: %{y:.1f} kWh per occupied day<extra></extra>"), secondary_y=False)
    fig.add_trace(go.Scatter(x=L, y=[m["cdd"] for m in M], name="Cooling-degree-days", mode="lines+markers",
                             line=dict(color=col("dim"), width=2.4), marker=dict(size=8),
                             hovertemplate="%{x}: %{y:.1f} °C above 25 °C, daily mean<extra></extra>"), secondary_y=True)
    _base(fig, 300)
    fig.update_yaxes(title_text="kWh per day", range=[0, 40], secondary_y=False)
    fig.update_yaxes(title_text="°C above 25 °C, daily mean", range=[0, 10], dtick=2, tickmode="linear",
                     showgrid=False, secondary_y=True)
    return fig


def fig_pies(B):
    M = B["monthly"]
    gen = sum(m["gen"] for m in M)
    exp = sum(m["exp"] for m in M)
    imp = sum(m["imp"] for m in M)
    used = gen - exp
    net = imp - exp
    fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"}, {"type": "domain"}]],
                        subplot_titles=("Where the household's electricity came from", "Where the solar went"))
    fig.add_trace(go.Pie(
        labels=["Solar, used as it was made", "Grid, cancelled by export credits", "Grid, paid for"],
        values=[round(used, 1), round(exp, 1), round(net, 1)], hole=.55, sort=False, direction="clockwise",
        marker=dict(colors=[col("pv"), col("sun", .75), col("rain", .45)], line=dict(color=col("card"), width=2)),
        textinfo="percent", textfont=dict(size=13), hovertemplate="%{label}: %{value:,.0f} kWh (%{percent})<extra></extra>",
        name="demand"), 1, 1)
    fig.add_trace(go.Pie(
        labels=["Used at home", "Sent to the grid"], values=[round(used, 1), round(exp, 1)], hole=.55, sort=False,
        direction="clockwise", marker=dict(colors=[col("pv"), col("sun", .75)], line=dict(color=col("card"), width=2)),
        textinfo="percent", textfont=dict(size=13), hovertemplate="%{label}: %{value:,.0f} kWh (%{percent})<extra></extra>",
        name="solar", showlegend=False), 1, 2)
    _base(fig, 330)
    fig.update_layout(legend=dict(orientation="h", y=-0.08, yanchor="top", x=0.5, xanchor="center"),
                      margin=dict(l=8, r=8, t=36, b=8))
    for a in fig.layout.annotations:
        a.font = dict(size=13, color=col("ink"))
        a.y = 1.06
    return fig


def fig_chain(B):
    M = B["monthly"]
    L = _labels(B)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=L, y=[m["ghi"] for m in M], name="1. Sunlight on the ground (NASA)",
                         marker_color=col("sun", .35), hovertemplate="%{x}: %{y:.2f} kWh/m² per day on the ground<extra></extra>"))
    fig.add_trace(go.Bar(x=L, y=[m["poa"] for m in M], name="2. Sunlight on the 12° panels",
                         marker_color=col("sun", .75), customdata=[(m["geo"] - 1) * 100 for m in M],
                         hovertemplate="%{x}: %{y:.2f} kWh/m² per day on the panels (%{customdata:+.1f}% vs ground)<extra></extra>"))
    fig.add_trace(go.Bar(x=L, y=[m["exp_yield"] for m in M], name="3. After heat loss and system efficiency η",
                         marker_color=col("pv", .55), customdata=[(1 - m["heat"]) * 100 for m in M],
                         hovertemplate="%{x}: expected %{y:.2f} kWh per kWp per day (heat loss %{customdata:.1f}%)<extra></extra>"))
    fig.add_trace(go.Scatter(x=L, y=[m["act_yield"] for m in M], name="Metered", mode="markers",
                             marker=dict(size=11, symbol="diamond", color=col("ink")),
                             hovertemplate="%{x}: metered %{y:.2f} kWh per kWp per day<extra></extra>"))
    _base(fig, 330)
    fig.update_layout(barmode="group", bargap=.22, bargroupgap=.05)
    fig.update_yaxes(title_text="kWh/m² per day  ≈  kWh per kWp per day", range=[0, 7])
    return fig


def fig_heat(B):
    H = B["heat"]
    x = [h["month"] for h in H]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=x, y=[h["loss_now"] for h in H], name="Heat loss today", marker_color=col("dim", .7),
                         customdata=[h["rise_now"] for h in H],
                         hovertemplate="%{x}: %{y:.1f}% lost to heat; cells %{customdata:.0f} °C above air<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=x, y=[h["loss_white"] for h in H], name="With a white roof (more light on the back)",
                         marker_color=col("dim", .3), marker_line=dict(color=col("dim"), width=1),
                         customdata=[h["rise_white"] for h in H],
                         hovertemplate="%{x}: %{y:.1f}% lost to heat; cells %{customdata:.0f} °C above air<extra></extra>"),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=x, y=[h["cdd"] for h in H], name="Cooling-degree-days", mode="lines+markers",
                             line=dict(color=col("ink"), width=1.6, dash="dot"), marker=dict(size=6),
                             hovertemplate="%{x}: %{y:.1f} °C above 25 °C, daily mean<extra></extra>"), secondary_y=True)
    _base(fig, 300)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="share of output lost to heat, %", range=[0, 10], secondary_y=False)
    fig.update_yaxes(title_text="°C above 25 °C", range=[0, 10], dtick=2, tickmode="linear", showgrid=False,
                     secondary_y=True)
    return fig


def fig_paint(B, gain: float = 0.12):
    P = B["paint"]
    x = [p["label"] for p in P]
    scale = gain / 0.12 if gain else 0
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[p["base"] for p in P], name="Today's dark concrete", marker_color=col("pv", .6),
                         hovertemplate="%{x}: %{y:.0f} kWh<extra></extra>"))
    fig.add_trace(go.Bar(x=x, y=[p["base"] + (p["white"] - p["base"]) * scale for p in P],
                         name="White surface (net of the extra heat, modelled)",
                         marker_color=col("sun", .55), marker_line=dict(color=col("sun"), width=1),
                         hovertemplate="%{x}: %{y:.0f} kWh<extra></extra>"))
    _base(fig, 300)
    fig.update_layout(barmode="group", bargap=.3, bargroupgap=.06)
    fig.update_yaxes(title_text="kWh per month (typical year)")
    return fig


def fig_dimming(B):
    A = B["annual"]
    yrs = [a["year"] for a in A]
    t = B["trends"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yrs, y=[a["clr"] for a in A], name="Clear-sky sunlight", mode="lines",
                             line=dict(color=col("sun"), width=1.6),
                             hovertemplate="%{x}: clear-sky %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=yrs, y=t["clr"]["fit"], showlegend=False, mode="lines",
                             line=dict(color=col("sun"), width=2.4, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=yrs, y=[a["ghi"] for a in A], name="Measured sunlight", mode="lines",
                             line=dict(color=col("dim"), width=1.6),
                             hovertemplate="%{x}: measured %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=yrs, y=t["ghi"]["fit"], showlegend=False, mode="lines",
                             line=dict(color=col("dim"), width=2.4, dash="dash"), hoverinfo="skip"))
    _base(fig, 320)
    fig.update_yaxes(title_text="kWh/m²/day, annual mean", range=[4, 7])
    return fig


def fig_kt(B):
    A = B["annual"]
    yrs = [a["year"] for a in A]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yrs, y=[a["kt"] for a in A], mode="lines", line=dict(color=col("rain"), width=1.6),
                             hovertemplate="%{x}: %{y:.3f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=yrs, y=B["trends"]["kt"]["fit"], mode="lines",
                             line=dict(color=col("rain"), width=2.4, dash="dash"), hoverinfo="skip"))
    _base(fig, 260, legend=False)
    fig.update_yaxes(title_text="measured ÷ clear-sky", range=[0.7, 0.9])
    return fig


def fig_seasons(B):
    S = B["seasons"]
    x = [s["season"] for s in S]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[s["early"] for s in S], name="1984–93", marker_color=col("sun", .5),
                         hovertemplate="%{x}, 1984–93: %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Bar(x=x, y=[s["late"] for s in S], name="2016–25", marker_color=col("dim"),
                         text=[f"{s['pct']:+.0f}%" for s in S], textposition="outside", cliponaxis=False,
                         hovertemplate="%{x}, 2016–25: %{y:.2f}<extra></extra>"))
    _base(fig, 260)
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="kWh/m²/day", range=[3, 7.3])
    return fig


def fig_life(B):
    L = B["life"]
    x = [r["year"] for r in L]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r["flat"] for r in L], name="No losses", mode="lines",
                             line=dict(color=col("mut"), width=1.4, dash="dot"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=[r["age"] for r in L], name="Panel ageing only", mode="lines",
                             line=dict(color=col("pv"), width=2.4), fill="tonexty", fillcolor=col("pv", .1),
                             hovertemplate="%{x}: %{y:,.0f} kWh<extra></extra>"))
    fig.add_trace(go.Scatter(x=x, y=[r["both"] for r in L], name="Ageing + dimming continues", mode="lines",
                             line=dict(color=col("dim"), width=2.6), fill="tonexty", fillcolor=col("dim", .14),
                             hovertemplate="%{x}: %{y:,.0f} kWh<extra></extra>"))
    _base(fig, 300)
    fig.update_yaxes(title_text="kWh per year", range=[3300, 4800], tickformat=",")
    return fig


def fig_experiment(B):
    X = B["experiment"]
    rows = X["rows"][:9]
    spec = [("dust", "dry spell, sunlight-weighted days", "Dust", col("dim")),
            ("tcell", "cell temperature, °C", "Heat", col("sun")),
            ("kt", "clearness index (sky)", "Sky", col("rain"))]
    fig = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.05,
                        subplot_titles=[f"{t}: ρ = {X['tests'][k]['rho']:+.2f}, p = {X['tests'][k]['p']:.3f}".replace("-", "−")
                                        for k, _, t, _ in spec])
    y = [r["resid"] for r in rows]
    for i, (k, xt, _t, c) in enumerate(spec, start=1):
        x = [r[k] for r in rows]
        tt = X["tests"][k]
        lo, hi = min(x), max(x)
        fig.add_trace(go.Scatter(x=[lo, hi], y=[tt["icpt"] + tt["slope"] * lo, tt["icpt"] + tt["slope"] * hi],
                                 mode="lines", line=dict(color=c, width=1.6, dash="dash"), hoverinfo="skip",
                                 showlegend=False), row=1, col=i)
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers+text", text=[r["month"] for r in rows],
                                 textposition="top center", textfont=dict(size=10, color=col("mut")),
                                 marker=dict(size=9, color=c, line=dict(width=1, color=col("card"))),
                                 showlegend=False, hovertemplate="%{text}: %{x:.2f}, residual %{y:+.1f}%<extra></extra>"),
                      row=1, col=i)
        fig.update_xaxes(title_text=xt, row=1, col=i)
    _base(fig, 330, legend=False)
    fig.update_layout(margin=dict(l=8, r=8, t=34, b=8))
    fig.update_xaxes(zeroline=False)
    fig.update_yaxes(title_text="residual, %", row=1, col=1)
    fig.update_annotations(font=dict(size=12, color=col("ink")))
    return fig


def fig_prereg(B):
    X = B["experiment"]
    P = X["pred"]
    L = [p["label"] for p in P]
    fig = go.Figure()
    for k, name, c, dash in (("dust", "If dust", col("dim"), "solid"), ("kt", "If sky", col("rain"), "solid"),
                             ("tcell", "If heat", col("sun"), "solid")):
        fig.add_trace(go.Scatter(x=L, y=[p[k] for p in P], name=name, mode="lines+markers",
                                 line=dict(color=c, width=2, dash=dash),
                                 marker=dict(size=[7 if not p[k + "_extrap"] else 9 for p in P],
                                             symbol=["circle" if not p[k + "_extrap"] else "circle-open" for p in P]),
                                 hovertemplate=name + ", %{x}: %{y:+.1f}%<extra></extra>"))
    r = X["rule"]
    fig.add_hrect(y0=r["dust_below"], y1=r["heat_above"], fillcolor=col("rain", .07), line_width=0)
    if X["outcome"]:
        fig.add_trace(go.Scatter(x=[o["month"] for o in X["outcome"]],
                                 y=[o["frozen"] for o in X["outcome"]], name="Metered", mode="markers",
                                 marker=dict(size=13, symbol="diamond", color=col("ink"))))
    _base(fig, 300)
    fig.update_yaxes(title_text="residual vs frozen model, %", zeroline=True, zerolinecolor=col("ink"),
                     zerolinewidth=1)
    return fig


FIGURES = {
    "daily": (fig_daily, "Daily sunlight (left axis, with its 7-day mean) and rainfall (right axis, hanging from the top) for every billed day. NASA POWER, at the roof's coordinates."),
    "calendar": (fig_calendar, "Each cell is one day: deeper colour means more sunlight; blue dots mark rain, sized by millimetres. The monsoon arrives as a run of pale cells from mid-June."),
    "gen": (fig_gen, "Bars: each billing month's generation ÷ its number of days. Line: NASA's daily sunlight averaged over the same days."),
    "scatter": (fig_scatter, "Each dot is one billing month. The dashed line is the least-squares fit: generation per day = a × sunlight + b."),
    "models": (fig_models, "How far each candidate model missed the one month it was not allowed to see, averaged over all nine months. Green: the two models kept."),
    "loo": (fig_loo, "Fit on all months but one, predict the one left out, repeat for every month. September and October were also genuine out-of-sample tests."),
    "chain": (fig_chain, "From sunlight to kilowatt-hours, month by month. Because 1 kWh/m² on the panels gives about 1 kWh per kWp at test conditions, all bars share one scale. Hover for the geometry gain and heat loss."),
    "normal": (fig_normal, "Sunlight in each 2026 billing month (diamonds) against the same calendar dates in 2016–2025 (bars, with the full range)."),
    "resid": (fig_resid, "Metered generation against what the physics model expected from the weather. Hover for the kWh."),
    "forecast": (fig_forecast, "Expected generation for the next twelve months: the physics model run on each of the last ten years of weather. Open circles show what the same calendar month produced in 2026."),
    "backtest": (fig_backtest, "The same array, run through each of the last ten years of weather. Dotted line: the ten-year average."),
    "balance": (fig_balance, "Each month's household demand (stacked: solar used at home plus electricity bought) beside what was sent back to the grid."),
    "pies": (fig_pies, "All nine bills together. Left: bill offset is the green and gold slices together; self-sufficiency is the green slice alone. Right: the same solar, split by where it went."),
    "money": (fig_money, "What each bill cost and what solar saved, slab by slab under net metering, with the running total."),
    "demand": (fig_demand, "Household demand per occupied day (bars) and cooling-degree-days (line). May's days are counted net of the week the house stood empty."),
    "heat": (fig_heat, "Share of output lost to panel heat in a typical year, today and with a white roof below, against cooling-degree-days. Hover for how far the cells run above the air."),
    "paint": (fig_paint, "Typical-year generation with today's dark concrete and with a white surface beneath the panels, after subtracting the extra heat. Modelled from the module datasheet, not measured on this roof."),
    "dimming": (fig_dimming, "Annual mean sunlight at these coordinates, 1984–2025: what reached the ground (measured) and what would on a cloudless day (clear-sky). Dashed: trends."),
    "kt": (fig_kt, "Clearness index, measured ÷ clear-sky. Flat means cloud cover has not changed."),
    "seasons": (fig_seasons, "Seasonal sunlight in the first and the latest decade of the record."),
    "experiment": (fig_experiment, "Each dot is one of the nine discovery months: its residual against a dust proxy (days since rain, weighted by sunlight), cell temperature, and sky clearness. ρ is the rank correlation; p is an exact one-sided permutation test."),
    "prereg": (fig_prereg, "What each explanation predicts for the winter bills, written down on 8 November 2026. Open circles fall outside the range the fit was made on. Shaded: the band where the verdict is 'sky'. Metered diamonds appear as bills arrive."),
    "life": (fig_life, "Annual output over the panels' 30-year power warranty. Ageing follows the datasheet warranty line; dimming extrapolates the 42-year trend, a downside case rather than a forecast."),
}


def build_all(B) -> dict[str, go.Figure]:
    return {k: fn(B) for k, (fn, _) in FIGURES.items()}


# --------------------------------------------------------------------------- twelve cities (research/cities.md)

def _city_col(c):
    return col("pv") if c == "Bhubaneswar" else col("pv", .35)


def fig_c_rank(R):
    D = sorted(R["cities"], key=lambda d: d["kwh"])
    fig = go.Figure(go.Scatter(
        y=[d["city"] for d in D], x=[d["kwh"] for d in D], mode="markers",
        marker=dict(size=[13 if d["city"] == "Bhubaneswar" else 10 for d in D],
                    color=[col("pv") if d["city"] == "Bhubaneswar" else col("ink", .7) for d in D]),
        error_x=dict(type="data", symmetric=False, array=[d["best"] - d["kwh"] for d in D],
                     arrayminus=[d["kwh"] - d["worst"] for d in D], color=col("mut", .6), thickness=1.4, width=0),
        customdata=[[d["yield"], d["worst"], d["best"]] for d in D],
        hovertemplate="%{y}: %{x:,.0f} kWh a year (%{customdata[0]:,.0f} kWh/kWp)"
                      "<br>worst year %{customdata[1]:,.0f}, best %{customdata[2]:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[d["best"] + 18 for d in D], y=[d["city"] for d in D], mode="text",
                             text=[f"{d['kwh']:,.0f}" for d in D], textposition="middle right",
                             textfont=dict(size=11, color=col("mut")), hoverinfo="skip"))
    _base(fig, 420, legend=False)
    fig.update_xaxes(title_text="kWh a year from the same 3 kWp array (dot: ten-year average; line: worst to best year)",
                     range=[4000, 5600], showgrid=True, gridcolor=col("grid"))
    return fig


def fig_c_seasons(R):
    D = sorted(R["cities"], key=lambda d: -d["kwh"])
    names = {"winter": ("Winter (Dec–Feb)", col("rain", .35)), "pre": ("Pre-monsoon (Mar–May)", col("sun")),
             "monsoon": ("Monsoon (Jun–Sep)", col("rain")), "post": ("Post-monsoon (Oct–Nov)", col("sun", .45))}
    fig = go.Figure()
    for k, (n, c) in names.items():
        fig.add_trace(go.Bar(x=[d["city"] for d in D], y=[d[f"poa_{k}"] for d in D], name=n, marker_color=c,
                             hovertemplate="%{x}, " + n + ": %{y:.0f} kWh/m²<extra></extra>"))
    _base(fig, 340, barmode="stack")
    fig.update_layout(legend=dict(traceorder="normal"))
    fig.update_yaxes(title_text="sunlight on the panels, kWh/m² a year")
    fig.update_xaxes(tickangle=-35)
    return fig


def fig_c_shares(R):
    S, Dc, Dd = R["season_share"], R["decomp"], R["decomp_dry"]
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12,
                        subplot_titles=["Which season separates the cities", "Why: latitude, haze or cloud"])
    sl = [("Winter", S["winter"], col("rain", .45)), ("Pre-monsoon", S["pre"], col("sun")),
          ("Monsoon", S["monsoon"], col("rain")), ("Post-monsoon", S["post"], col("sun", .5))]
    fig.add_trace(go.Bar(x=[s[0] for s in sl], y=[s[1] * 100 for s in sl], marker_color=[s[2] for s in sl],
                         text=[f"{s[1] * 100:.0f}%" for s in sl], textposition="outside", cliponaxis=False,
                         showlegend=False, hovertemplate="%{x}: %{y:.0f}% of the between-city spread<extra></extra>"),
                  row=1, col=1)
    for name, d, c in (("Whole year", Dc, col("ink", .75)), ("Dry months (Oct–May)", Dd, col("sun"))):
        ks = ["latitude", "haze", "cloud"]
        fig.add_trace(go.Bar(x=["Latitude", "Haze", "Cloud"], y=[d[k] * 100 for k in ks], name=name, marker_color=c,
                             text=[f"{d[k] * 100:.0f}%" for k in ks], textposition="outside", cliponaxis=False,
                             hovertemplate=name + ", %{x}: %{y:.0f}%<extra></extra>"), row=1, col=2)
    _base(fig, 330)
    fig.update_layout(margin=dict(l=8, r=8, t=34, b=8), barmode="group",
                      legend=dict(orientation="h", y=-0.18, x=0.56))
    fig.update_yaxes(title_text="share of the gap between cities, %", range=[0, 52], row=1, col=1)
    fig.update_yaxes(range=[0, 52], row=1, col=2)
    fig.update_annotations(font=dict(size=12, color=col("ink")))
    return fig


def fig_c_heat(R):
    D = R["cities"]
    pos = {"Bengaluru": "bottom center", "Jaipur": "top left", "Thiruvananthapuram": "top left",
           "Mumbai": "bottom right", "Hyderabad": "bottom right", "Chennai": "top center", "Lucknow": "bottom right",
           "Delhi": "top left", "Bhubaneswar": "bottom left", "Kolkata": "top right"}
    fig = go.Figure(go.Scatter(
        x=[d["heat_loss"] * 100 for d in D], y=[d["kwh"] for d in D], mode="markers+text",
        text=[d["city"] for d in D], textposition=[pos.get(d["city"], "top center") for d in D],
        textfont=dict(size=11, color=col("mut")),
        marker=dict(size=11, color=[_city_col(d["city"]) for d in D], line=dict(width=1, color=col("card"))),
        customdata=[[d["t_cell_peak"]] for d in D],
        hovertemplate="%{text}: heat costs %{x:.1f}%, output %{y:,.0f} kWh"
                      "<br>hottest month's cells %{customdata[0]:.0f} °C<extra></extra>"))
    _base(fig, 320, legend=False)
    fig.update_xaxes(title_text="share of output lost to panel heat, %", range=[3.4, 6.5])
    fig.update_yaxes(title_text="kWh a year")
    return fig


def fig_c_haze(R):
    D = R["cities"]
    pos = {"Kolkata": "bottom center", "Lucknow": "top center", "Bhubaneswar": "bottom right",
           "Guwahati": "bottom center", "Delhi": "top right", "Chennai": "top left",
           "Hyderabad": "top left", "Mumbai": "top center", "Thiruvananthapuram": "bottom right",
           "Bengaluru": "bottom center", "Jaipur": "bottom left", "Ahmedabad": "top left"}
    fig = go.Figure(go.Scatter(
        x=[d["haze_dry"] for d in D], y=[d["cloud_dry"] for d in D], mode="markers+text",
        text=[d["city"] for d in D], textposition=[pos.get(d["city"], "top center") for d in D],
        textfont=dict(size=11, color=col("mut")),
        marker=dict(size=[(d["kwh"] - 3900) / 45 for d in D], color=[_city_col(d["city"]) for d in D],
                    line=dict(width=1, color=col("card"))),
        customdata=[[d["kwh"]] for d in D],
        hovertemplate="%{text}: cloud-free sky passes %{x:.2f}, clouds pass %{y:.2f}"
                      "<br>%{customdata[0]:,.0f} kWh a year<extra></extra>"))
    _base(fig, 340, legend=False)
    fig.update_xaxes(title_text="haze: cloud-free sky ÷ top of atmosphere (dry months)", range=[0.575, 0.695])
    fig.update_yaxes(title_text="cloud: actual ÷ cloud-free sky (dry months)", range=[0.8, 0.98])
    return fig


CITY_FIGURES = {
    "c_rank": (fig_c_rank, "The same array, 12° south, dark concrete roof, run through 2016–2025 NASA weather in each city. Dot: ten-year average. Line: worst to best year. Green: Bhubaneswar."),
    "c_heat": (fig_c_heat, "Each dot is a city. Hotter cities lose more to heat, yet they produce more: the sunshine that heats the panels outweighs what the heat takes away."),
    "c_seasons": (fig_c_seasons, "Sunlight landing on the panels each season, cities in order of annual output. The monsoon slices are similar; winter and pre-monsoon slices are not."),
    "c_shares": (fig_c_shares, "Left: each season's share of the between-city spread in annual panel sunlight. Right: the spread in ground sunlight split into latitude, haze (what a cloud-free sky absorbs and scatters) and cloud."),
    "c_haze": (fig_c_haze, "Dry-season sky in each city. Further right: clearer cloud-free air. Higher: fewer clouds. Bubble size: annual output."),
}


def build_cities(R) -> dict[str, go.Figure]:
    return {k: fn(R) for k, (fn, _) in CITY_FIGURES.items()}
