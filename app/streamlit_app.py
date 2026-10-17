"""Interactive companion to the article.

    streamlit run app/streamlit_app.py

Same numbers and the same charts as site/index.html (both come from
solar_analytics.story and solar_analytics.figures), plus controls for the
assumptions a reader is most likely to want to change.
"""

from __future__ import annotations

import calendar
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solar_analytics import figures as F  # noqa: E402
from solar_analytics.config import Tariff  # noqa: E402
from solar_analytics.story import compute  # noqa: E402

st.set_page_config(page_title="Rooftop solar · Satya Vihar", page_icon="☀️", layout="wide")


@st.cache_resource(show_spinner="Running the weather model over ten years of data…")
def bundle() -> dict:
    return compute()


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=key)
    st.caption(F.FIGURES[key][1] if key in F.FIGURES else "")


B = bundle()
facts = B["facts"]
tariff = Tariff()

# ------------------------------------------------------------------ sidebar: assumptions
with st.sidebar:
    st.header("Assumptions you can change")
    gain = st.slider("Rear-side gain from a white roof, %", 0, 25, 12,
                     help="Modelled from the module datasheet (15–30% depending on the ground). "
                          "Not yet measured on this roof.") / 100
    paint_cost = st.slider("Cost of paint and labour, ₹", 4000, 20000, (8000, 12000), step=500)
    rate = st.number_input("Value of one avoided unit, ₹", 3.0, 8.0, round(tariff.marginal_rate, 2), 0.05,
                           help="₹6.34 is the top slab (6.10) plus 4% duty. Winter units are often worth less.")
    may = next(m for m in B["monthly"] if m["month"] == "May")
    away = st.slider("Days the house stood empty in May", 0.0, 12.0, float(may["days"] - may["occ_days"]), 0.5,
                     help="Affects demand only. The family recalls about a week away and ~200 fewer units imported; "
                          "7.5 days reproduces that.")
    st.divider()
    st.caption(f"Data: TPCODL bills {facts['first']} – {facts['last']}; NASA POWER weather. "
               "Panels fixed at 12° facing south.")
    st.caption("[Article](https://piyushdash94.github.io/rooftop-solar-analytics/) · "
               "[Code and data](https://github.com/piyushdash94/rooftop-solar-analytics)")

st.title("Reading a rooftop against the sky")
st.write("A 3 kWp bifacial array in Satya Vihar, Bhubaneswar: eight months of bills joined to satellite weather. "
         "Use the tabs to explore; the sidebar changes the assumptions behind the what-ifs.")

c = st.columns(5)
c[0].metric("Generated", f"{facts['gen_total']} kWh", help=f"{facts['n_days']} days")
c[1].metric("Explained by sunlight", f"{facts['fit_r2_pct']}%")
c[2].metric("Typical-year forecast", f"{facts['fc_total']} kWh", help=f"range {facts['yr_min']}–{facts['yr_max']}")
c[3].metric("Saved on bills", f"₹{facts['saved_total']}")
c[4].metric("September forecast miss", f"{facts['sep_err']}%")

tabs = st.tabs(["Weather and output", "Choosing the model", "Panel health", "Forecast",
                "Household and money", "What if", "The long record", "Data"])

# ------------------------------------------------------------------ weather and output
with tabs[0]:
    show(F.fig_daily(B), "daily")
    show(F.fig_calendar(B), "calendar")
    a, b = st.columns(2)
    with a:
        show(F.fig_gen(B), "gen")
    with b:
        show(F.fig_scatter(B), "scatter")
    st.code(f"generation per day = {facts['fit_a']} × sunlight + {facts['fit_c']}   (R² = {facts['fit_r2']})")

# ------------------------------------------------------------------ choosing the model
with tabs[1]:
    st.write("Each model is fitted on seven months and asked to predict the eighth, for every month in turn. "
             "Lower is better. With eight points, extra variables mostly add ways to fit noise.")
    show(F.fig_models(B), "models")
    st.dataframe(pd.DataFrame(B["models"])[["name", "form", "params", "mae", "worst"]].rename(columns={
        "name": "Model", "form": "Form", "params": "Fitted parameters", "mae": "Mean miss, %",
        "worst": "Worst miss, %"}), hide_index=True, width="stretch")
    show(F.fig_loo(B), "loo")
    show(F.fig_chain(B), "chain")

# ------------------------------------------------------------------ panel health
with tabs[2]:
    st.write("Expected energy = sunlight on the panels × heat derate × 3 kWp × η. "
             f"η = {facts['eta']} is the median across the eight months, so this compares months with each other.")
    show(F.fig_resid(B), "resid")
    show(F.fig_normal(B), "normal")

# ------------------------------------------------------------------ forecast
with tabs[3]:
    show(F.fig_forecast(B), "forecast")
    years = ["Typical (2016–2025 average)"] + [str(y) for y in sorted(B["weather_years"])]
    pick = st.selectbox("Run the next twelve months with the weather of", years)
    order = [f["month"] for f in B["forecast"]]
    labels = [f["label"] for f in B["forecast"]]
    typical = [f["mean"] for f in B["forecast"]]
    if pick.startswith("Typical"):
        chosen = typical
    else:
        wy = B["weather_years"][int(pick)]
        chosen = [wy[m - 1] for m in order]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=chosen, name=pick, marker_color=F.col("pv", .7)))
    fig.add_trace(go.Scatter(x=labels, y=typical, name="Typical", mode="lines+markers",
                             line=dict(color=F.col("ink"), width=1.6, dash="dot")))
    F._base(fig, 300)
    fig.update_yaxes(title_text="kWh per month")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="year_pick")
    st.metric(f"Twelve-month total with {pick} weather", f"{sum(chosen):,.0f} kWh",
              delta=f"{sum(chosen) - sum(typical):+,.0f} kWh vs typical")
    show(F.fig_backtest(B), "backtest")

# ------------------------------------------------------------------ household and money
with tabs[4]:
    Bm = copy.deepcopy(B)
    for m in Bm["monthly"]:
        if m["month"] == "May":
            od = m["days"] - away
            m["occ_days"] = od
            m["dem_occ"] = m["demand"] / od
            gd = m["gen"] / m["days"]
            m["scr_occ"] = min(m["self"] / (gd * od), 1) * 100
    show(F.fig_balance(B), "balance")
    show(F.fig_money(B), "money")
    show(F.fig_demand(Bm), "demand")
    cdd = [m["cdd"] for m in Bm["monthly"]]
    r_occ = np.corrcoef(cdd, [m["dem_occ"] for m in Bm["monthly"]])[0, 1]
    st.metric("Demand ↔ cooling-degree-days correlation", f"{r_occ:+.2f}")
    show(F.fig_pies(B), "pies")

# ------------------------------------------------------------------ what if
with tabs[5]:
    show(F.fig_heat(B), "heat")
    show(F.fig_paint(B, gain), "paint")
    base = sum(f["mean"] for f in B["forecast"])
    net_at_12 = sum(p["white"] for p in B["paint"]) - base      # modelled at 12%, net of extra heat
    extra = net_at_12 * gain / 0.12
    worth = extra * rate
    k = st.columns(3)
    k[0].metric("Extra generation", f"{extra:,.0f} kWh/yr")
    k[1].metric("Worth (ceiling)", f"₹{worth:,.0f}/yr")
    k[2].metric("Payback", "—" if worth <= 0 else f"{paint_cost[0] / worth:.1f}–{paint_cost[1] / worth:.1f} yr")
    st.caption("Net of the extra heat from light absorbed on the back of the panels (modelled at 12% and scaled "
               "linearly for other gains). The gain is applied evenly to every month; in reality it is larger in "
               "clear months and smaller under cloud.")

# ------------------------------------------------------------------ long record
with tabs[6]:
    show(F.fig_dimming(B), "dimming")
    a, b = st.columns(2)
    with a:
        show(F.fig_kt(B), "kt")
    with b:
        show(F.fig_seasons(B), "seasons")
    show(F.fig_life(B), "life")

# ------------------------------------------------------------------ data
with tabs[7]:
    df = pd.DataFrame(B["monthly"])[["month", "start", "end", "days", "gen", "imp", "exp", "demand", "ghi", "rain",
                                    "tmean", "expected", "resid", "billed", "saved"]]
    df.columns = ["Month", "From", "To", "Days", "Generated kWh", "Imported kWh", "Exported kWh", "Demand kWh",
                  "Sunlight kWh/m²/day", "Rain mm", "Mean temp °C", "Expected kWh", "Residual %", "Billed ₹",
                  "Saved ₹"]
    st.dataframe(df, hide_index=True, width="stretch")
    st.download_button("Download this table as CSV", df.to_csv(index=False), "rooftop_solar_monthly.csv", "text/csv")
    nm = pd.DataFrame(B["weather_years"], index=[calendar.month_abbr[i] for i in range(1, 13)]).round(0)
    st.write("Modelled generation by month for each weather-year, kWh")
    st.dataframe(nm, width="stretch")
