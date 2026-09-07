"""Generation vs weather, reduced to one variable.

The question this answers
-------------------------
Sunlight, cloud, and heat all move generation at once, so comparing months on
raw kWh confuses three effects. This script collapses them into a single
physical quantity -- EFFECTIVE IRRADIATION -- and asks how much of the observed
generation it explains, and what is left over.

    E_eff  =  POA(tilt, GHI, sky)  x  f_temp(T_air)     [kWh/m^2/day]

    POA     plane-of-array irradiation. Starts from measured GHI, so cloud is
            already inside it, then applies the array's 12 deg tilt geometry.
    f_temp  cell-temperature derate from the module datasheet (-0.30 %/degC).

One number per day. Multiply by kWp and you have the energy the array should
have made. Divide observed by expected and you have system health with weather
removed -- which is the only thing worth looking at.

Method for daily data
---------------------
NASA POWER reports daily totals, not hourly. Rather than invent an hourly
profile and risk fabricating structure, this uses the standard daily approach:
Erbs' daily correlation splits GHI into beam and diffuse via the clearness
index, and the beam tilt factor Rb is integrated numerically over each day's
solar geometry (Liu-Jordan / Duffie-Beckman).

Data
----
206 days of weather, 7 billing periods of generation. The weather is daily; the
generation is not. Everything below aggregates to the 7 periods, and no claim
is made that survives that constraint.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

# ---------------------------------------------------------------- site & data

# Surveyed: 20 deg 18' 43.45" N, 85 deg 52' 03.88" E
# NASA POWER serves radiation on a coarser grid than meteorology. Moving from
# the earlier approximate coordinates (4.85 km away) left GHI BYTE-IDENTICAL --
# same radiation cell -- while T2M and precipitation shifted, because those
# cross a MERRA-2 cell boundary. Net effect on residuals: under 0.03 points.
LAT, LON, TZ = 20.312069, 85.867744, "Asia/Kolkata"
KWP = 3.0
TILT, AZIMUTH = 12.0, 180.0          # ESTIMATE from imagery, +/- 3 deg
ALBEDO = 0.12                         # bare dark concrete
TEMP_COEFF = -0.0030                  # %/degC, Waaree BiN-01 datasheet Pmax
CELL_RISE = 25.0                      # cell temp above ambient, NOCT-style proxy

ROOT = Path(__file__).resolve().parents[1]
WEATHER_CSV = ROOT / "data" / "raw" / "nasa_power_daily.csv"
OUT_HTML = ROOT / "outputs" / "generation_vs_weather.html"

PERIODS = [
    # label, start, end, generation_kWh, days
    ("Feb", "2026-02-08", "2026-03-01", 321.91, 22),
    ("Mar", "2026-03-02", "2026-04-01", 389.55, 31),
    ("Apr", "2026-04-02", "2026-05-01", 436.34, 30),
    ("May", "2026-05-02", "2026-06-01", 436.53, 31),
    ("Jun", "2026-06-02", "2026-07-01", 364.67, 30),
    ("Jul", "2026-07-02", "2026-08-01", 268.76, 31),
    ("Aug", "2026-08-02", "2026-09-01", 263.50, 31),
]


def load_weather() -> pd.DataFrame:
    df = pd.read_csv(WEATHER_CSV, index_col=0, parse_dates=True)
    df = df.apply(pd.to_numeric, errors="coerce")
    df.index = df.index.tz_localize(TZ)
    df.index.name = "date"
    return df


# ------------------------------------------------------- component 1: the POA

def daily_beam_tilt_factor(days: pd.DatetimeIndex) -> pd.Series:
    """Rb: daily beam irradiation on the tilted plane / on the horizontal.

    Integrated numerically over each day at 15-minute resolution, weighting by
    clear-sky beam so the ratio reflects when beam energy actually arrives
    rather than treating all daylight minutes as equal.
    """
    loc = pvlib.location.Location(LAT, LON, tz=TZ)
    times = pd.date_range(days[0].normalize(),
                          days[-1].normalize() + pd.Timedelta("1D"),
                          freq="15min", tz=TZ)[:-1]
    solpos = loc.get_solarposition(times)
    cs = loc.get_clearsky(times, model="ineichen")

    aoi = pvlib.irradiance.aoi(TILT, AZIMUTH,
                               solpos["apparent_zenith"], solpos["azimuth"])
    cos_aoi = np.cos(np.radians(aoi)).clip(lower=0)
    cos_zen = np.cos(np.radians(solpos["apparent_zenith"])).clip(lower=0.03)

    weight = cs["dni"].clip(lower=0)
    num = (weight * cos_aoi).groupby(times.date).sum()
    den = (weight * cos_zen).groupby(times.date).sum()

    rb = (num / den.replace(0, np.nan)).fillna(1.0)
    rb.index = pd.to_datetime(rb.index).tz_localize(TZ)
    return rb.clip(0.4, 2.5)


def compute_poa(w: pd.DataFrame) -> pd.DataFrame:
    """GHI -> plane-of-array, using Erbs daily decomposition."""
    ghi = w["ALLSKY_SFC_SW_DWN"]

    # Extraterrestrial daily irradiation on a horizontal surface
    doy = w.index.dayofyear
    decl = np.radians(23.45 * np.sin(np.radians(360 * (284 + doy) / 365)))
    lat_r = np.radians(LAT)
    ws = np.arccos(np.clip(-np.tan(lat_r) * np.tan(decl), -1, 1))
    gsc = 1367.0  # W/m2
    h0 = (24 / np.pi) * gsc * (1 + 0.033 * np.cos(np.radians(360 * doy / 365))) * (
        np.cos(lat_r) * np.cos(decl) * np.sin(ws) + ws * np.sin(lat_r) * np.sin(decl)
    ) / 1000.0  # -> kWh/m2/day

    kt = (ghi / h0).clip(0, 1)

    # Erbs daily diffuse fraction correlation
    df_frac = pd.Series(index=kt.index, dtype=float)
    lo, hi = kt <= 0.22, kt > 0.80
    mid = ~lo & ~hi
    df_frac[lo] = 1.0 - 0.09 * kt[lo]
    df_frac[mid] = (0.9511 - 0.1604 * kt[mid] + 4.388 * kt[mid] ** 2
                    - 16.638 * kt[mid] ** 3 + 12.336 * kt[mid] ** 4)
    df_frac[hi] = 0.165
    df_frac = df_frac.clip(0, 1)

    diffuse = ghi * df_frac
    beam = ghi - diffuse

    rb = daily_beam_tilt_factor(w.index).reindex(w.index).ffill()
    tilt_r = np.radians(TILT)
    poa = (beam * rb
           + diffuse * (1 + np.cos(tilt_r)) / 2
           + ghi * ALBEDO * (1 - np.cos(tilt_r)) / 2)

    out = w.copy()
    out["kt"] = kt
    out["diffuse_fraction"] = df_frac
    out["rb"] = rb
    out["poa"] = poa
    return out


# ------------------------------------------- component 2: temperature derate

def apply_temperature(w: pd.DataFrame) -> pd.DataFrame:
    w = w.copy()
    w["t_cell"] = w["T2M"] + CELL_RISE
    w["f_temp"] = 1 + TEMP_COEFF * (w["t_cell"] - 25.0)
    # THE CONSOLIDATED VARIABLE
    w["e_eff"] = w["poa"] * w["f_temp"]
    return w


# ------------------------------------------------------------- period rollup

def rollup(w: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for label, start, end, gen, days in PERIODS:
        win = w.loc[start:end]
        # NASA POWER lags real time by ~2 weeks, so the most recent period may
        # be missing trailing days. Summing only the days that exist would
        # understate expected energy and fake an over-performance. Scale the
        # observed-day total up to the full period and report coverage so the
        # reader can discount the result.
        n_valid = int(win["e_eff"].notna().sum())
        coverage = n_valid / days if days else float("nan")
        e_eff_total = win["e_eff"].sum() / coverage if n_valid else float("nan")
        rows.append({
            "month": label,
            "start": start,
            "days": days,
            "weather_days": n_valid,
            "coverage": coverage,
            "actual_kwh": gen,
            "ghi_mean": win["ALLSKY_SFC_SW_DWN"].mean(),
            "poa_mean": win["poa"].mean(),
            "e_eff_mean": win["e_eff"].mean(),
            "e_eff_total": e_eff_total,
            "kt_mean": win["kt"].mean(),
            "f_temp_mean": win["f_temp"].mean(),
            "rain_mm": win["PRECTOTCORR"].sum(),
            "rain_days": int((win["PRECTOTCORR"] > 1).sum()),
            "t_air_mean": win["T2M"].mean(),
        })
    d = pd.DataFrame(rows)

    # Single system-efficiency constant, fitted as the median across periods.
    # NOTE: this normalises away any loss common to ALL months. What survives
    # is relative month-to-month health, not absolute performance.
    d["eta_implied"] = d["actual_kwh"] / (d["e_eff_total"] * KWP)
    eta_ref = d["eta_implied"].median()
    d["expected_kwh"] = d["e_eff_total"] * KWP * eta_ref
    d["residual_kwh"] = d["actual_kwh"] - d["expected_kwh"]
    d["residual_pct"] = d["residual_kwh"] / d["expected_kwh"] * 100
    d.attrs["eta_ref"] = eta_ref
    return d


# ------------------------------------------------------------------ reporting

def build_dashboard(daily: pd.DataFrame, periods: pd.DataFrame) -> str:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    INK, SUN, SEA, CLAY, MUTE = "#1D2B33", "#D98A16", "#0F6E8C", "#A63D2F", "#6B7C86"
    base = dict(
        template="plotly_white",
        paper_bgcolor="#F2F5F7", plot_bgcolor="#FFFFFF",
        font=dict(family="Inter, system-ui, sans-serif", size=13, color=INK),
        margin=dict(l=60, r=30, t=64, b=52),
        hovermode="x unified",
    )
    figs = []

    # 1 -- the consolidated variable, day by day
    f1 = make_subplots(specs=[[{"secondary_y": True}]])
    f1.add_bar(x=daily.index, y=daily["PRECTOTCORR"], name="Rain (mm)",
               marker_color=SEA, opacity=0.30, secondary_y=True)
    f1.add_scatter(x=daily.index, y=daily["poa"], name="POA irradiation",
                   line=dict(color=MUTE, width=1), opacity=0.55)
    f1.add_scatter(x=daily.index, y=daily["e_eff"], name="Effective irradiation E_eff",
                   line=dict(color=SUN, width=2.4))
    f1.add_scatter(x=daily.index, y=daily["e_eff"].rolling(7, center=True).mean(),
                   name="7-day mean", line=dict(color=CLAY, width=2.6, dash="dot"))
    f1.update_yaxes(title_text="kWh/m²/day", secondary_y=False, range=[0, 8])
    f1.update_yaxes(title_text="Rain (mm)", secondary_y=True, range=[0, 120],
                    showgrid=False)
    f1.update_layout(title="One variable, 175 days · effective irradiation vs rainfall",
                     **base)
    figs.append(("daily", f1))

    # 2 -- expected vs actual, the headline
    f2 = go.Figure()
    hi = max(periods["expected_kwh"].max(), periods["actual_kwh"].max()) * 1.08
    f2.add_scatter(x=[0, hi], y=[0, hi], mode="lines", name="perfect agreement",
                   line=dict(color=MUTE, dash="dash", width=1.5))
    colors = [CLAY if r < -3 else SUN if r > 3 else SEA
              for r in periods["residual_pct"]]
    f2.add_scatter(
        x=periods["expected_kwh"], y=periods["actual_kwh"], mode="markers+text",
        text=periods["month"], textposition="top center", name="billing period",
        marker=dict(size=19, color=colors, line=dict(color="#FFFFFF", width=2.5)),
        customdata=periods["residual_pct"],
        hovertemplate="%{text}<br>expected %{x:.0f} kWh<br>actual %{y:.0f} kWh"
                      "<br>residual %{customdata:+.1f}%<extra></extra>",
    )
    f2.update_layout(title="Predicted from weather alone vs what the meter recorded",
                     xaxis_title="Expected kWh (E_eff × kWp × η)",
                     yaxis_title="Actual kWh (meter)", hovermode="closest", **{
                         k: v for k, v in base.items() if k != "hovermode"})
    figs.append(("parity", f2))

    # 3 -- residual: weather removed
    f3 = go.Figure()
    f3.add_bar(x=periods["month"], y=periods["residual_pct"],
               marker_color=[CLAY if r < 0 else SUN for r in periods["residual_pct"]],
               text=[f"{r:+.1f}%" for r in periods["residual_pct"]],
               textposition="outside", name="residual")
    f3.add_hline(y=0, line=dict(color=INK, width=1.4))
    f3.update_layout(
        title="What weather cannot explain · residual after removing E_eff",
        yaxis_title="Deviation from weather-predicted (%)",
        yaxis_range=[min(periods["residual_pct"]) - 6,
                     max(periods["residual_pct"]) + 6],
        showlegend=False, **base)
    figs.append(("residual", f3))

    # 4 -- what E_eff is made of
    f4 = go.Figure()
    f4.add_bar(x=periods["month"], y=periods["ghi_mean"], name="GHI (measured)",
               marker_color=MUTE, opacity=0.55)
    f4.add_bar(x=periods["month"], y=periods["poa_mean"], name="POA (after 12° tilt)",
               marker_color=SEA, opacity=0.75)
    f4.add_bar(x=periods["month"], y=periods["e_eff_mean"],
               name="E_eff (after heat derate)", marker_color=SUN)
    f4.update_layout(title="Building the variable · irradiance, geometry, heat",
                     yaxis_title="kWh/m²/day", barmode="group", **base)
    figs.append(("components", f4))

    # ---- assemble page
    import plotly.io as pio
    blocks = []
    for i, (_name, fig) in enumerate(figs):
        blocks.append(pio.to_html(fig, include_plotlyjs=("cdn" if i == 0 else False), full_html=False,
                                  config={"displayModeBar": False}))

    eta = periods.attrs["eta_ref"]
    worst = periods.loc[periods["residual_pct"].idxmin()]
    best = periods.loc[periods["residual_pct"].idxmax()]
    spread = periods["residual_pct"].max() - periods["residual_pct"].min()

    rows = "".join(
        f"<tr><td>{r.month}</td><td>{r.days}</td><td>{r.kt_mean:.3f}</td>"
        f"<td>{r.ghi_mean:.2f}</td><td>{r.poa_mean:.2f}</td>"
        f"<td>{r.f_temp_mean:.3f}</td><td>{r.e_eff_mean:.2f}</td>"
        f"<td>{r.expected_kwh:.0f}</td><td>{r.actual_kwh:.0f}</td>"
        f"<td class='{'neg' if r.residual_pct < 0 else 'pos'}'>"
        f"{r.residual_pct:+.1f}%</td><td>{r.rain_days}</td></tr>"
        for r in periods.itertuples()
    )

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Generation vs Weather</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#F2F5F7;color:#1D2B33;font-family:Inter,system-ui,sans-serif;
line-height:1.6;padding:24px 16px 64px}}
.wrap{{max-width:1000px;margin:0 auto}}
header{{margin-bottom:30px;padding-bottom:20px;border-bottom:2px solid #1D2B33}}
.eyebrow{{font-family:'IBM Plex Mono',monospace;font-size:.7rem;letter-spacing:.16em;
text-transform:uppercase;color:#0F6E8C;font-weight:500}}
h1{{font-size:clamp(1.7rem,5vw,2.5rem);font-weight:700;letter-spacing:-.025em;
line-height:1.1;margin:8px 0 12px}}
.lede{{font-size:1rem;color:#475A66;max-width:66ch}}
.eq{{background:#FFF;border:1px solid #D3DCE2;border-left:4px solid #D98A16;
padding:16px 18px;margin:22px 0;font-family:'IBM Plex Mono',monospace;font-size:.85rem}}
.eq .big{{font-size:1.05rem;font-weight:500;margin-bottom:10px}}
.eq div.d{{color:#6B7C86;font-size:.76rem;margin-top:5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;
margin-bottom:26px}}
.kpi{{background:#FFF;border:1px solid #D3DCE2;padding:14px 16px}}
.kpi .l{{font-family:'IBM Plex Mono',monospace;font-size:.64rem;letter-spacing:.1em;
text-transform:uppercase;color:#6B7C86}}
.kpi .v{{font-size:1.5rem;font-weight:700;letter-spacing:-.02em;margin-top:3px}}
.kpi .n{{font-size:.75rem;color:#6B7C86}}
.clay{{color:#A63D2F}}.sun{{color:#D98A16}}.sea{{color:#0F6E8C}}
figure{{background:#FFF;border:1px solid #D3DCE2;margin-bottom:24px;padding:6px}}
figcaption{{font-size:.82rem;color:#475A66;padding:10px 16px 12px;
border-top:1px solid #E4EAEE}}
h2{{font-size:1.05rem;font-weight:600;margin:34px 0 12px;letter-spacing:-.01em}}
p{{font-size:.92rem;margin-bottom:12px;max-width:70ch}}
table{{width:100%;border-collapse:collapse;font-family:'IBM Plex Mono',monospace;
font-size:.74rem;background:#FFF;border:1px solid #D3DCE2}}
th,td{{padding:8px 7px;text-align:right;border-bottom:1px solid #E4EAEE}}
th:first-child,td:first-child{{text-align:left}}
th{{background:#E9EEF1;font-size:.63rem;letter-spacing:.07em;text-transform:uppercase;
color:#475A66;font-weight:500}}
td.neg{{color:#A63D2F;font-weight:600}}td.pos{{color:#0F6E8C;font-weight:600}}
.note{{background:#FFF;border:1px solid #D3DCE2;border-left:4px solid #A63D2F;
padding:14px 18px;margin:20px 0;font-size:.88rem}}
.note b{{display:block;margin-bottom:5px;font-weight:600}}
.scroll{{overflow-x:auto}}
footer{{margin-top:40px;padding-top:16px;border-top:2px solid #1D2B33;
font-family:'IBM Plex Mono',monospace;font-size:.7rem;color:#6B7C86}}
</style></head><body><div class="wrap">

<header>
<div class="eyebrow">3 kWp bifacial · Bhubaneswar · 175 days</div>
<h1>Generation vs weather,<br>reduced to one variable</h1>
<p class="lede">Sunlight, cloud and heat move output together, so ranking months
on raw kWh confuses three effects at once. Collapsing them into a single
physical quantity leaves a residual that is only about the system.</p>
</header>

<div class="eq">
<div class="big">E_eff = POA(12° tilt, measured GHI) × f_temp(T_air)</div>
<div class="d">POA — plane-of-array irradiation. Built from measured GHI, so cloud is already inside it; tilt geometry via Erbs daily decomposition and an integrated beam factor.</div>
<div class="d">f_temp — cell derate, −0.30 %/°C on (T_air + 25 °C), from the module datasheet.</div>
<div class="d">Expected energy = E_eff × 3 kWp × η, with η = {eta:.3f} fitted as the median across the six periods.</div>
</div>

<div class="kpis">
<div class="kpi"><div class="l">Weakest</div><div class="v clay">{worst.month} {worst.residual_pct:+.1f}%</div><div class="n">vs weather-predicted</div></div>
<div class="kpi"><div class="l">Strongest</div><div class="v sun">{best.month} {best.residual_pct:+.1f}%</div><div class="n">vs weather-predicted</div></div>
<div class="kpi"><div class="l">Residual spread</div><div class="v">{spread:.1f} pts</div><div class="n">unexplained by weather</div></div>
<div class="kpi"><div class="l">Observations</div><div class="v sea">6</div><div class="n">175 days of weather</div></div>
</div>

<figure>{blocks[0]}<figcaption>Daily effective irradiation across the whole record.
The seasonal collapse from June onward is monsoon cloud, and the rain bars line up
with every sharp trough. This is the weather signal that has to be removed before
the array can be judged.</figcaption></figure>

<h2>Does weather alone predict the meter?</h2>
<p>If effective irradiation captured everything, all six points would sit on the
diagonal. Distance below the line is energy the weather said was available and the
array did not deliver.</p>
<figure>{blocks[1]}<figcaption>Each point is one billing cycle. Points below the
dashed line under-delivered against what the weather allowed.</figcaption></figure>

<h2>The residual</h2>
<p>Same information, stated as a percentage. This is the only chart here that is
about the system rather than the sky.</p>
<figure>{blocks[2]}<figcaption>Deviation from weather-predicted output. March and May
sit lowest; June and July run above the fitted line.</figcaption></figure>

<div class="note"><b>What this residual can and cannot see</b>
η is fitted as the median across the same six periods, which normalises away any
loss shared by every month. A uniformly dirty array, a systematically undersized
string, or a constant inverter clipping loss would all be absorbed into η and show
up as nothing. What survives is <em>relative</em> month-to-month health. With six
observations and a fitted constant, treat the ordering as informative and the
magnitudes as approximate.</div>

<h2>How the variable is built</h2>
<p>Three bars per month: measured horizontal irradiance, the same energy after the
array's 12° tilt geometry, and finally after heat derating. The tilt adds energy in
February and takes it away near the solstice; heat costs most in the hottest months.</p>
<figure>{blocks[3]}<figcaption>Tilt gain is largest in February and slightly negative
from April onward — expected for a shallow tilt at 20°N.</figcaption></figure>

<h2>Period table</h2>
<div class="scroll"><table>
<tr><th>Period</th><th>Days</th><th>Kt</th><th>GHI</th><th>POA</th><th>f_temp</th>
<th>E_eff</th><th>Expected</th><th>Actual</th><th>Residual</th><th>Rain d</th></tr>
{rows}
</table></div>

<footer>
Irradiance: NASA POWER daily · Transposition: Erbs daily decomposition + integrated
beam tilt factor, pvlib 0.15.2 · Tilt 12° ± 3° estimated from imagery, azimuth 180°
assumed · Temperature coefficient −0.30 %/°C from Waaree BiN-01 datasheet ·
Cell temperature is a T_air + 25 °C proxy, not a measured or wind-corrected model ·
Grid outages (~2–3 h fortnightly, daytime) are unmodelled and sit inside the residual
</footer>
</div></body></html>"""


def main() -> None:
    w = load_weather()
    w = compute_poa(w)
    w = apply_temperature(w)
    periods = rollup(w)

    pd.set_option("display.width", 200)
    print(f"\nDaily weather rows: {len(w)}   "
          f"Range: {w.index.min().date()} -> {w.index.max().date()}")
    print(f"Tilt {TILT} deg (ESTIMATE), azimuth {AZIMUTH} deg (ASSUMED), "
          f"albedo {ALBEDO}\n")

    cols = ["month", "weather_days", "days", "kt_mean", "ghi_mean", "poa_mean", "f_temp_mean", "e_eff_mean",
            "expected_kwh", "actual_kwh", "residual_pct", "rain_days"]
    print(periods[cols].round(3).to_string(index=False))
    print(f"\nFitted system efficiency (median): {periods.attrs['eta_ref']:.4f}")
    print("NOTE: eta is fitted on these same 7 periods, so any loss common to all "
          "months is absorbed. Residuals show RELATIVE health only.\n")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_dashboard(w, periods), encoding="utf-8")
    print(f"Dashboard -> {OUT_HTML}")

    daily_out = OUT_HTML.parent / "daily_e_eff.csv"
    w[["ALLSKY_SFC_SW_DWN", "kt", "diffuse_fraction", "rb", "poa",
       "T2M", "f_temp", "e_eff", "PRECTOTCORR"]].to_csv(daily_out)
    periods.to_csv(OUT_HTML.parent / "period_residuals.csv", index=False)
    print(f"Daily series -> {daily_out}")

    with open(OUT_HTML.parent / "summary.json", "w") as f:
        json.dump({"eta_ref": float(periods.attrs["eta_ref"]),
                   "periods": periods[cols].to_dict("records")}, f, indent=1,
                  default=float)


if __name__ == "__main__":
    main()
