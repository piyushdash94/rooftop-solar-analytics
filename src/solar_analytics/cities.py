"""The same rooftop array, run through ten years of weather in twelve Indian cities.

Research question: what decides how much a rooftop array makes in India, monsoon cloud or summer
heat? The array, its 12° south-facing mount, its dark concrete roof and its system efficiency are
held fixed at the Bhubaneswar values, so the only thing that changes between cities is the weather.

Hypothesis and test criteria were written down before the model was run (see HYPOTHESIS).
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import stats

from .config import DATA_DIR, RAW_DIR, SITE
from .physics import effective_irradiation, load_daily

ETA = 0.9132  # system efficiency fitted on the Bhubaneswar bills (story.ETA_FROZEN)
KWP = SITE.kwp
MONSOON = [6, 7, 8, 9]  # June to September, the southwest monsoon
SEASONS = {"winter": [12, 1, 2], "pre": [3, 4, 5], "monsoon": [6, 7, 8, 9], "post": [10, 11]}
SEASON_NAMES = {
    "winter": "Winter (Dec–Feb)",
    "pre": "Pre-monsoon (Mar–May)",
    "monsoon": "Monsoon (Jun–Sep)",
    "post": "Post-monsoon (Oct–Nov)",
}
HYPOTHESIS = {
    "statement": (
        "Across Indian cities, monsoon cloud decides rooftop yield far more than summer heat."
    ),
    "a": "Spread across cities in panel sunlight is at least twice the spread in the heat factor.",
    "b": (
        "June-September explains more than half of the between-city variance in annual "
        "panel sunlight."
    ),
    "c": "Yield ranks more closely with monsoon panel sunlight than with heat loss.",
}


def _city_year_table(city: str, lat: float, lon: float, tilt: float | None = None) -> pd.DataFrame:
    w = effective_irradiation(
        load_daily(RAW_DIR / "cities" / f"{city.lower()}.csv"), tilt=tilt, lat=lat, lon=lon
    )
    w["mon"] = w.index.month.isin(MONSOON)
    g = w.groupby(w.index.year)
    out = pd.DataFrame(
        {
            "ghi": g.ALLSKY_SFC_SW_DWN.sum(),
            "poa": g.poa.sum(),
            "poa_mon": w[w.mon].groupby(w[w.mon].index.year).poa.sum(),
            "e_eff": g.e_eff.sum(),
            "t_cell_max_month": w.groupby([w.index.year, w.index.month])
            .t_cell.mean()
            .groupby(level=0)
            .max(),
            "t_air": g.T2M.mean(),
            "rain": g.PRECTOTCORR.sum(),
        }
    )
    out["poa_rest"] = out.poa - out.poa_mon
    for k, ms in SEASONS.items():
        sel = w[w.index.month.isin(ms)]
        out[f"poa_{k}"] = sel.groupby(sel.index.year).poa.sum()
    # Sunlight at the top of the atmosphere, under a cloud-free sky, and what actually arrived.
    w["h0"] = w.ALLSKY_SFC_SW_DWN / w.kt.replace(0, np.nan)
    dry = w[~w.mon]
    for tag, d in (("", w), ("_dry", dry)):
        gg = d.groupby(d.index.year)
        out[f"h0{tag}"] = gg.h0.sum()
        out[f"clr{tag}"] = gg.CLRSKY_SFC_SW_DWN.sum()
        out[f"ghi{tag}_sum"] = gg.ALLSKY_SFC_SW_DWN.sum()
    out["kwh"] = out.e_eff * KWP * ETA
    out["heat_loss"] = 1 - out.e_eff / out.poa
    return out


def _spearman(x, y) -> float:
    return float(stats.spearmanr(x, y)[0])


@lru_cache(maxsize=1)
def compute_cities() -> dict:
    C = pd.read_csv(DATA_DIR / "cities.csv")
    rows, years = [], {}
    for r in C.itertuples():
        t = _city_year_table(r.city, r.lat, r.lon)
        tl = _city_year_table(r.city, r.lat, r.lon, tilt=r.lat)  # robustness: tilt = latitude
        years[r.city] = [round(float(v)) for v in t.kwh]
        m = t.mean()
        rows.append(
            {
                "city": r.city,
                "state": r.state,
                "lat": r.lat,
                "lon": r.lon,
                "kwh": float(m.kwh),
                "yield": float(m.kwh / KWP),
                "ghi": float(m.ghi),
                "poa": float(m.poa),
                "poa_mon": float(m.poa_mon),
                "poa_rest": float(m.poa_rest),
                "mon_share": float(m.poa_mon / m.poa),
                "geom": float(m.poa / m.ghi),
                "heat_loss": float(1 - t.e_eff.sum() / t.poa.sum()),
                "t_cell_peak": float(m.t_cell_max_month),
                "t_air": float(m.t_air),
                "rain": float(m.rain),
                "cv": float(t.kwh.std(ddof=1) / t.kwh.mean()),
                "worst": float(t.kwh.min()),
                "best": float(t.kwh.max()),
                "kwh_lat_tilt": float(tl.kwh.mean()),
                # what the city would make with no heat loss, and with a dry-season sky all year
                "heat_kwh": float((t.poa - t.e_eff).mean() * KWP * ETA),
                **{f"poa_{k}": float(m[f"poa_{k}"]) for k in SEASONS},
                "h0": float(m.h0),
                "clr": float(m.clr),
                "h0_dry": float(m.h0_dry),
                "clr_dry": float(m.clr_dry),
                "ghi_dry": float(m.ghi_dry_sum),
                "haze_dry": float(m.clr_dry / m.h0_dry),
                "cloud_dry": float(m.ghi_dry_sum / m.clr_dry),
                "haze": float(m.clr / m.h0),
                "cloud": float(m.ghi / m.clr),
            }
        )
    D = pd.DataFrame(rows).sort_values("kwh", ascending=False).reset_index(drop=True)

    # (a) spread of the two multiplicative terms: yield ∝ poa × (1 - heat_loss)
    ln_poa, ln_heat = np.log(D.poa), np.log(1 - D.heat_loss)
    spread_sun, spread_heat = float(ln_poa.std(ddof=1)), float(ln_heat.std(ddof=1))
    var_ln_kwh = float(np.log(D.kwh).var(ddof=1))
    share_sun = float(np.cov(ln_poa, np.log(D.kwh))[0, 1] / var_ln_kwh)
    share_heat = float(np.cov(ln_heat, np.log(D.kwh))[0, 1] / var_ln_kwh)
    # (b) how much of the between-city variance in annual panel sunlight comes from Jun-Sep
    var_poa = float(D.poa.var(ddof=1))
    mon_var_share = float(np.cov(D.poa_mon, D.poa)[0, 1] / var_poa)
    # (c) rank correlations
    rho_mon = _spearman(D.kwh, D.poa_mon)
    rho_heat = _spearman(D.kwh, D.heat_loss)
    rho_rest = _spearman(D.kwh, D.poa_rest)
    # year-to-year: do monsoon-dependent cities swing more?
    rho_cv_mon = _spearman(D.cv, D.mon_share)
    rho_cv_rain = _spearman(D.cv, D.rain)
    # robustness: does the ranking survive tilting each array to its own latitude?
    rho_tilt = _spearman(D.kwh, D.kwh_lat_tilt)

    # Which season separates the cities? Covariance share of each season in annual panel sunlight.
    season_share = {k: float(np.cov(D[f"poa_{k}"], D.poa)[0, 1] / var_poa) for k in SEASONS}

    # ln GHI = ln(top of atmosphere) + ln(cloud-free sky / top) + ln(actual / cloud-free):
    # latitude, haze (aerosol and water vapour), cloud. Share of between-city variance for each.
    def decompose(h0, clr, ghi):
        y = np.log(ghi)
        parts = {"latitude": np.log(h0), "haze": np.log(clr / h0), "cloud": np.log(ghi / clr)}
        return {k: float(np.cov(v, y)[0, 1] / y.var(ddof=1)) for k, v in parts.items()}

    decomp = decompose(D.h0, D.clr, D.ghi)
    decomp_dry = decompose(D.h0_dry, D.clr_dry, D.ghi_dry)

    verdict = {
        "a": spread_sun >= 2 * spread_heat,
        "b": mon_var_share > 0.5,
        "c": abs(rho_mon) > abs(rho_heat),
    }
    return {
        "hypothesis": HYPOTHESIS,
        "cities": D.to_dict("records"),
        "years": years,
        "tests": {
            "spread_sun": spread_sun,
            "spread_heat": spread_heat,
            "ratio": spread_sun / spread_heat,
            "share_sun": share_sun,
            "share_heat": share_heat,
            "mon_var_share": mon_var_share,
            "rho_mon": rho_mon,
            "rho_heat": rho_heat,
            "rho_rest": rho_rest,
            "rho_cv_mon": rho_cv_mon,
            "rho_cv_rain": rho_cv_rain,
            "rho_tilt": rho_tilt,
        },
        "verdict": verdict,
        "season_share": season_share,
        "decomp": decomp,
        "decomp_dry": decomp_dry,
        "facts": _facts(
            D,
            verdict,
            spread_sun,
            spread_heat,
            mon_var_share,
            rho_mon,
            rho_heat,
            rho_rest,
            rho_cv_mon,
            rho_tilt,
            season_share,
            decomp,
            decomp_dry,
        ),
    }


def _facts(
    D,
    verdict,
    spread_sun,
    spread_heat,
    mon_var_share,
    rho_mon,
    rho_heat,
    rho_rest,
    rho_cv_mon,
    rho_tilt,
    season_share,
    decomp,
    decomp_dry,
) -> dict:
    def f0(x):
        return f"{x:,.0f}"

    def pct(x):
        return f"{x * 100:.0f}"

    def sg(x):
        return f"{x:+.2f}".replace("-", "−")

    top, bot = D.iloc[0], D.iloc[-1]
    b = D[D.city == "Bhubaneswar"].iloc[0]
    rank_b = int(D.index[D.city == "Bhubaneswar"][0]) + 1
    beng = D[D.city == "Bengaluru"].iloc[0]
    hot = D.sort_values("t_cell_peak", ascending=False).iloc[0]
    cool = D.sort_values("t_cell_peak").iloc[0]
    hazy = D.sort_values("haze_dry").iloc[:5].city.tolist()
    from .story import compute

    art = compute()["facts"]["fc_total"]
    art_kwh = float(art.replace(",", ""))
    return {
        "art_kwh": art,
        "art_diff": f"{abs(b.kwh / art_kwh - 1) * 100:.1f}",
        "n_cities": str(len(D)),
        "kwp": f"{KWP:g}",
        "eta": f"{ETA:.3f}",
        "top_city": top.city,
        "top_kwh": f0(top.kwh),
        "top_yield": f0(top["yield"]),
        "bot_city": bot.city,
        "bot_kwh": f0(bot.kwh),
        "bot_yield": f0(bot["yield"]),
        "spread_pct": pct(top.kwh / bot.kwh - 1),
        "bbsr_kwh": f0(b.kwh),
        "bbsr_rank": str(rank_b),
        "bbsr_yield": f0(b["yield"]),
        "bbsr_vs_top": pct(top.kwh / b.kwh - 1),
        "mean_daily_yield": f"{D['yield'].mean() / 365:.1f}",
        "yield_lo_day": f"{D['yield'].min() / 365:.1f}",
        "yield_hi_day": f"{D['yield'].max() / 365:.1f}",
        "heat_lo": f"{D.heat_loss.min() * 100:.1f}",
        "heat_hi": f"{D.heat_loss.max() * 100:.1f}",
        "heat_lo_city": D.loc[D.heat_loss.idxmin(), "city"],
        "heat_hi_city": D.loc[D.heat_loss.idxmax(), "city"],
        "hot_city": hot.city,
        "hot_tcell": f"{hot.t_cell_peak:.0f}",
        "cool_city": cool.city,
        "cool_tcell": f"{cool.t_cell_peak:.0f}",
        "spread_sun": f"{spread_sun * 100:.1f}",
        "spread_heat": f"{spread_heat * 100:.1f}",
        "spread_ratio": f"{spread_sun / spread_heat:.0f}",
        "rho_heat": sg(rho_heat),
        "rho_mon": sg(rho_mon),
        "rho_rest": sg(rho_rest),
        "mon_share": pct(mon_var_share),
        **{f"ss_{k}": pct(v) for k, v in season_share.items()},
        **{f"dc_{k}": pct(v) for k, v in decomp.items()},
        **{f"dd_{k}": pct(v) for k, v in decomp_dry.items()},
        "va": "supported" if verdict["a"] else "rejected",
        "vb": "supported" if verdict["b"] else "rejected",
        "vc": "supported" if verdict["c"] else "rejected",
        "n_supported": str(sum(verdict.values())),
        "rho_tilt": f"{rho_tilt:.2f}",
        "rho_cv_mon": sg(rho_cv_mon),
        "cv_lo": f"{D.cv.min() * 100:.1f}",
        "cv_hi": f"{D.cv.max() * 100:.1f}",
        "hazy_list": ", ".join(hazy[:-1]) + " and " + hazy[-1],
        "haze_lo": f"{D.haze_dry.min():.2f}",
        "haze_hi": f"{D.haze_dry.max():.2f}",
        "bbsr_haze": f"{b.haze_dry:.2f}",
        "bbsr_cloud": f"{b.cloud_dry:.2f}",
        "bbsr_winter": f0(b.poa_winter),
        "beng_winter": f0(beng.poa_winter),
        "winter_gap": pct(beng.poa_winter / b.poa_winter - 1),
        "bbsr_mon": f0(b.poa_monsoon),
        "beng_mon": f0(beng.poa_monsoon),
        "delhi_mon_rank": str(
            int(
                D.sort_values("poa_mon", ascending=False)
                .reset_index()
                .index[D.sort_values("poa_mon", ascending=False).reset_index().city == "Delhi"][0]
            )
            + 1
        ),
        "delhi_rank": str(int(D.index[D.city == "Delhi"][0]) + 1),
        "lat_lo": f"{D.lat.min():.1f}",
        "lat_hi": f"{D.lat.max():.1f}",
    }
