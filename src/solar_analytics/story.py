"""Every number the article uses, computed in one place.

`compute()` returns a plain dict (JSON-serialisable) that the figures, the
article renderer and the Streamlit app all read. Nothing in the article is
typed by hand: prose placeholders such as {sep_pred} are filled from
`bundle["facts"]`.

Inputs (all in data/):
    bills.csv, meter_readings.csv, occupancy.csv          the household
    raw/nasa_power_daily.csv                              weather for the billed days (2026)
    raw/nasa_power_daily_2016_2025.csv                    ten recent weather-years
    raw/nasa_power_monthly_1984_2025.csv                  the long record, monthly
    bbsr_annual_climate_1984_2025.csv                     the long record, annual
"""

from __future__ import annotations

import calendar
from functools import lru_cache

import numpy as np
import pandas as pd

from .config import DATA_DIR, RAW_DIR, SITE, Tariff
from .loaders import load_bills, load_occupancy, occupied_days
from .physics import effective_irradiation, load_daily, period_rollup

KWP = SITE.kwp
CDD_BASE = 25.0                 # degC, cooling-degree-day base on daily mean air temperature
WHITE_GAIN = 0.12               # modelled bifacial rear gain from a white roof (datasheet-based)
# Pre-registered experiment (published 2026-11-08, before the winter bills): dust, heat or sky?
PREREG_DATE = "2026-11-08"
ETA_FROZEN = 0.9132              # η at registration; winter residuals are scored against this, not a refit
EXP_N = 9                        # the discovery set: Feb-Oct 2026. Hypothesis tests never use later months.
DUST_RAIN_MM = 5.0               # a day with this much rain resets the dust clock (primary choice)
WINTER = [11, 12, 1, 2]          # the test season
GUEST_MONTH = "Oct"             # owner: guests stayed about a week in October (demand only)
PUBLISHED_OCT_FORECAST = 388.8  # kWh, typical-October forecast published 2026-10-06, before the bill
SURROUND_COOL = 1.3             # degC, module cooling over a cool-roof coating, measured on monofacial panels
                                # (Mahmood et al. 2023); used only as the other bound of the white-roof heat effect
PAINT_COST = (8000, 12000)      # INR, paint and labour
AGEING_PER_YEAR = 0.004         # datasheet warranty: 99% after year 1, 87.4% after year 30
LIFE_YEARS = 30                 # datasheet power-output warranty
HIST_YEARS = (2016, 2025)


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def _loo(X: np.ndarray, y: np.ndarray, days: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """Leave-one-out % error of a linear model y ~ X (per-day units)."""
    out = []
    for i in range(len(y)):
        k = np.arange(len(y)) != i
        A = np.c_[np.ones(k.sum()), X[k]]
        beta = np.linalg.lstsq(A, y[k], rcond=None)[0]
        pred = float(np.r_[1, X[i]] @ beta) * days[i]
        out.append((pred / actual[i] - 1) * 100)
    return np.array(out)


def _loo_physics(e_total: np.ndarray, actual: np.ndarray) -> np.ndarray:
    eta = actual / (e_total * KWP)
    return np.array([(e_total[i] * KWP * np.median(np.delete(eta, i)) / actual[i] - 1) * 100
                     for i in range(len(eta))])


def _trend(x, y):
    from scipy import stats
    r = stats.linregress(x, y)
    return {"slope_decade": r.slope * 10, "p": r.pvalue, "r2": r.rvalue ** 2,
            "fit": (r.intercept + r.slope * np.asarray(x)).tolist()}


def _perm_spearman(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Spearman rho and exact one-sided permutation p (H1: rho < 0)."""
    from itertools import permutations
    rx = pd.Series(x).rank().to_numpy() - (len(x) + 1) / 2
    ry = pd.Series(y).rank().to_numpy() - (len(y) + 1) / 2
    den = np.sqrt((rx ** 2).sum() * (ry ** 2).sum())
    obs = float((rx * ry).sum() / den)
    perms = np.array(list(permutations(range(len(y)))))
    null = (rx[None, :] * ry[perms]).sum(1) / den
    return obs, float((null <= obs + 1e-12).mean())


def _partial_rank(x, y, z) -> float:
    """Rank correlation of x and y after removing a linear effect of z from both."""
    rx, ry, rz = (pd.Series(v).rank().to_numpy() for v in (x, y, z))
    ex = rx - np.polyval(np.polyfit(rz, rx, 1), rz)
    ey = ry - np.polyval(np.polyfit(rz, ry, 1), rz)
    return float(np.corrcoef(ex, ey)[0, 1])


def _dust_clock(rain: pd.Series, start_clean: bool) -> pd.Series:
    """Days since the last day with >= DUST_RAIN_MM of rain (0 on the first day if the panels start clean)."""
    out, c = [], 0
    for i, v in enumerate(rain.fillna(0).to_numpy()):
        c = 0 if v >= DUST_RAIN_MM or (start_clean and i == 0) else c + 1
        out.append(c)
    return pd.Series(out, rain.index)


def _experiment(w26: pd.DataFrame, hist: pd.DataFrame, monthly: list[dict], roll: pd.DataFrame) -> dict:
    """Dust, heat or sky: three explanations for the residual pattern, tested on the nine discovery
    months and turned into a written-down forecast for the winter bills."""
    w = w26.copy()
    w["dust"] = _dust_clock(w["PRECTOTCORR"], start_clean=True)       # new panels on 8 February
    h = hist.copy()
    h["dust"] = _dust_clock(h["PRECTOTCORR"], start_clean=False)

    def wmean(df, col):      # sunlight-weighted: a dusty or hot day matters more when it is bright
        d = df.dropna(subset=["poa"])
        return float((d[col] * d.poa).sum() / d.poa.sum())

    rows = []
    for i, m in enumerate(monthly):
        d = w.loc[m["start"]:m["end"]]
        r = roll.iloc[i]
        frozen = r.actual_kwh / (r.e_eff_total * KWP * ETA_FROZEN) - 1
        rows.append({"month": m["month"], "start": m["start"], "resid": m["resid"],
                     "frozen": _r(frozen * 100, 1),
                     "dust": _r(wmean(d, "dust"), 1), "tcell": _r(wmean(d, "t_cell"), 1),
                     "kt": _r(wmean(d, "kt"), 3)})
    disc = pd.DataFrame(rows[:EXP_N])
    y = disc.resid.to_numpy(float)
    names = {"dust": "Dust", "tcell": "Heat", "kt": "Sky"}
    tests = {}
    for k in names:
        x = disc[k].to_numpy(float)
        rho, p = _perm_spearman(x, y)
        slope, icpt = np.polyfit(x, y, 1)
        tests[k] = {"rho": rho, "p": p, "slope": float(slope), "icpt": float(icpt),
                    "lo": float(x.min()), "hi": float(x.max())}
    order = sorted(tests, key=lambda k: tests[k]["p"])          # Holm, three one-sided tests
    adj, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, tests[k]["p"] * (len(order) - i)))
        adj[k] = run
    for k in tests:
        tests[k]["p_holm"] = adj[k]
    part = {"dust_given_sky": _partial_rank(disc.dust, y, disc.kt),
            "sky_given_dust": _partial_rank(disc.kt, y, disc.dust),
            "heat_given_sky": _partial_rank(disc.tcell, y, disc.kt)}
    collin = disc[["dust", "tcell", "kt"]].corr(method="spearman")

    g = h.groupby(h.index.month)
    typ = {mo: {k: wmean(g.get_group(mo), k) for k in ("dust", "t_cell", "kt")} for mo in WINTER}
    pred = []
    for mo in WINTER:
        t = typ[mo]
        row = {"label": calendar.month_abbr[mo]}
        for k, v in (("dust", t["dust"]), ("tcell", t["t_cell"]), ("kt", t["kt"])):
            row[k] = _r(tests[k]["icpt"] + tests[k]["slope"] * v, 1)
            row[k + "_x"] = _r(v, 2)
            row[k + "_extrap"] = bool(v > tests[k]["hi"] * 1.05 or v < tests[k]["lo"] * 0.95)
        pred.append(row)
    outcome = [r for r in rows[EXP_N:] if pd.Timestamp(r["start"]).month in WINTER]
    return {"rows": rows, "tests": tests, "partial": part,
            "collin": {"dust_kt": float(collin.loc["dust", "kt"]),
                       "dust_tcell": float(collin.loc["dust", "tcell"]),
                       "tcell_kt": float(collin.loc["tcell", "kt"])},
            "pred": pred, "outcome": outcome, "sd": float(np.std(y, ddof=1))}


@lru_cache(maxsize=1)
def compute() -> dict:
    tariff = Tariff()
    bills = load_bills()
    occ = occupied_days(bills, load_occupancy())

    # ---------------------------------------------------------------- the billed months
    w26 = effective_irradiation(load_daily())
    roll = period_rollup(w26, bills)
    eta = roll.attrs["eta_ref"]
    raw = load_daily()

    monthly, ghi_raw = [], []
    for i, b in bills.iterrows():
        s = raw.loc[str(b.period_start.date()):str(b.period_end.date())]
        d, od = int(b.days), float(occ.iloc[i])
        gen, imp, exp = float(b.generation_kwh), float(b.import_kwh), float(b.export_kwh)
        self_used = gen - exp
        demand = imp + self_used
        scr_occ = min(self_used / (gen / d * od), 1.0)
        dem_cf = demand / od * d
        self_cf = scr_occ * gen
        imp_cf, exp_cf = dem_cf - self_cf, gen - self_cf
        ghi_raw.append(float(s.ALLSKY_SFC_SW_DWN.mean()))
        r = roll.iloc[i]
        ww = w26.loc[str(b.period_start.date()):str(b.period_end.date())].dropna(subset=["poa"])
        poa_day = float(ww.poa.mean())
        heat = float(ww.e_eff.sum() / ww.poa.sum())
        monthly.append({
            "month": b.period_start.strftime("%b"), "start": str(b.period_start.date()),
            "end": str(b.period_end.date()), "days": d, "occ_days": od,
            "gen": gen, "imp": imp, "exp": exp, "self": _r(self_used, 2), "demand": _r(demand, 2),
            "gen_day": _r(gen / d, 2), "dem_day": _r(demand / d, 2), "imp_day": _r(imp / d, 2),
            "dem_occ": _r(demand / od, 2), "imp_occ": _r(imp / od, 2),
            "ghi": _r(ghi_raw[-1], 3), "rain": _r(s.PRECTOTCORR.sum(), 1),
            "tmean": _r(s.T2M.mean(), 1), "tmax": _r(s.T2M_MAX.mean(), 1),
            "cdd": _r((s.T2M - CDD_BASE).clip(lower=0).mean(), 2),
            "yield_": _r(gen / KWP / d, 2), "scr": _r(self_used / gen * 100, 1),
            "scr_occ": _r(scr_occ * 100, 1), "offset": _r(gen / demand * 100, 1),
            "offset_norm": _r(gen / dem_cf * 100, 1), "selfsuff": _r(self_used / demand * 100, 1),
            "expected": _r(r.expected_kwh, 1), "resid": _r(r.residual_pct, 1), "eta": _r(r.eta_implied, 3),
            "poa": _r(poa_day, 3), "f_temp": _r(r.f_temp_mean, 3), "heat": _r(heat, 4),
            "geo": _r(poa_day / float(ww.ALLSKY_SFC_SW_DWN.mean()), 4),
            "exp_yield": _r(poa_day * heat * eta, 3), "act_yield": _r(gen / KWP / d, 3),
            "t_rise": _r(float(((ww.t_cell - ww.T2M) * ww.poa).sum() / ww.poa.sum()), 1),
            "billed": float(b.billed_amount_inr),
            "saved": _r(tariff.cost(demand) - tariff.cost(imp - exp), 0),
            "cf_imp": _r(imp_cf, 1), "cf_exp": _r(exp_cf, 1), "cf_net": _r(imp_cf - exp_cf, 1),
            "cf_charge": _r(tariff.cost(imp_cf - exp_cf) - tariff.cost(imp - exp), 0),
            "net": _r(imp - exp, 1), "charge": _r(tariff.cost(imp - exp), 0),
        })
    M = pd.DataFrame(monthly)
    x = np.array(ghi_raw)
    y = M.gen_day.to_numpy(float)
    days = M.days.to_numpy(float)
    actual = M.gen.to_numpy(float)

    # ---------------------------------------------------------------- the simple line
    a, c = np.polyfit(x, y, 1)
    r2 = float(np.corrcoef(x, y)[0, 1] ** 2)
    sd = float(np.std(y - (a * x + c), ddof=2))
    a7, c7 = np.polyfit(x[:-1], y[:-1], 1)
    sep_pred = float((a7 * x[-1] + c7) * days[-1])
    loo_sun = _loo(x[:, None], y, days, actual)

    # ---------------------------------------------------------------- which features earn a place
    T = M.tmean.to_numpy(float)
    rain_day = (M.rain / M.days).to_numpy(float)
    e_tot = roll.e_eff_total.to_numpy(float)
    poa_only = []
    for b in bills.itertuples():
        win = w26.loc[str(b.period_start.date()):str(b.period_end.date())]
        poa_only.append(win["poa"].sum() / (win["poa"].notna().sum() / b.days))
    candidates = [
        ("Sunlight only", "gen/day = a·sun + b", 2, _loo(x[:, None], y, days, actual)),
        ("Sunlight + temperature", "gen/day = a·sun + b·T + c", 3, _loo(np.c_[x, T], y, days, actual)),
        ("Sunlight + rain", "gen/day = a·sun + b·rain + c", 3, _loo(np.c_[x, rain_day], y, days, actual)),
        ("Rain only", "gen/day = a·rain + b", 2, _loo(rain_day[:, None], y, days, actual)),
        ("Temperature only", "gen/day = a·T + b", 2, _loo(T[:, None], y, days, actual)),
        ("Physics: panel-plane sun", "E = POA·kWp·η", 1, _loo_physics(np.array(poa_only), actual)),
        ("Physics: panel-plane sun × heat", "E = POA·f(T)·kWp·η", 1, _loo_physics(e_tot, actual)),
    ]
    models = [{"name": n, "form": f, "params": p, "mae": _r(np.abs(e).mean(), 2),
               "worst": _r(np.abs(e).max(), 1), "errs": [_r(v, 1) for v in e]} for n, f, p, e in candidates]

    # ---------------------------------------------------------------- ten weather-years through the same model
    hist = effective_irradiation(load_daily(RAW_DIR / "nasa_power_daily_2016_2025.csv"))
    hist["gen"] = hist["e_eff"] * KWP * eta
    yr_mo = hist.groupby([hist.index.year, hist.index.month])["gen"].mean().unstack()   # kWh/day
    annual = hist.groupby(hist.index.year)["gen"].sum()
    ghi_mo = hist.groupby([hist.index.year, hist.index.month])["ALLSKY_SFC_SW_DWN"].mean().unstack()

    last = pd.Timestamp(bills.period_end.iloc[-1])
    start = (last + pd.offsets.MonthBegin(0)) if last.day != 1 else last
    start = pd.Timestamp(start.year, start.month, 1)
    window = pd.date_range(start, periods=12, freq="MS")
    fc = []
    for mstart in window:
        mo, nd = mstart.month, calendar.monthrange(mstart.year, mstart.month)[1]
        col = yr_mo[mo]
        reg = (a * ghi_mo[mo].mean() + c) * nd
        fc.append({"label": mstart.strftime("%b %y"), "month": mo, "days": nd,
                   "mean": _r(col.mean() * nd, 1), "p10": _r(col.quantile(.1) * nd, 1),
                   "p90": _r(col.quantile(.9) * nd, 1), "min": _r(col.min() * nd, 1),
                   "max": _r(col.max() * nd, 1), "regression": _r(reg, 1),
                   "ghi_normal": _r(ghi_mo[mo].mean(), 2)})
    fc_total = sum(f["mean"] for f in fc)
    reg_total = sum(f["regression"] for f in fc)

    # how unusual was 2026? same calendar windows in each of the ten years
    normal = []
    hraw = load_daily(RAW_DIR / "nasa_power_daily_2016_2025.csv")
    for b, g in zip(bills.itertuples(), ghi_raw, strict=True):
        vals, rains = [], []
        for yr in range(HIST_YEARS[0], HIST_YEARS[1] + 1):
            s0 = b.period_start.replace(year=yr)
            s1 = b.period_end.replace(year=yr)
            win = hraw.loc[str(s0.date()):str(s1.date())]
            vals.append(win.ALLSKY_SFC_SW_DWN.mean())
            rains.append(win.PRECTOTCORR.sum())
        normal.append({"month": b.period_start.strftime("%b"), "ghi_2026": _r(g, 2),
                       "ghi_normal": _r(np.mean(vals), 2), "ghi_min": _r(np.min(vals), 2),
                       "ghi_max": _r(np.max(vals), 2), "pct": _r((g / np.mean(vals) - 1) * 100, 1),
                       "rain_2026": None, "rain_normal": _r(np.mean(rains), 0)})
    for n, m in zip(normal, monthly, strict=True):
        n["rain_2026"] = m["rain"]

    # ---------------------------------------------------------------- the long record
    ann = pd.read_csv(DATA_DIR / "bbsr_annual_climate_1984_2025.csv")
    tg, tc, tk = _trend(ann.year, ann.ghi), _trend(ann.year, ann.clr), _trend(ann.year, ann.kt)
    mon = pd.read_csv(RAW_DIR / "nasa_power_monthly_1984_2025.csv")
    season_of = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Pre-monsoon", 4: "Pre-monsoon", 5: "Pre-monsoon",
                 6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon", 10: "Post-monsoon", 11: "Post-monsoon"}
    mon["season"] = mon.month.map(season_of)
    seasons = []
    for sname in ["Pre-monsoon", "Monsoon", "Post-monsoon", "Winter"]:
        e = mon[(mon.season == sname) & (mon.year <= 1993)].ghi.mean()
        l_ = mon[(mon.season == sname) & (mon.year >= 2016)].ghi.mean()
        seasons.append({"season": sname, "early": _r(e, 2), "late": _r(l_, 2), "pct": _r((l_ / e - 1) * 100, 1)})
    recent_ghi = ann[ann.year >= 2016].ghi.mean()
    dim_rate = -tg["slope_decade"] / 10 / recent_ghi            # fraction per year
    life = []
    for k in range(0, LIFE_YEARS):
        age = 1 - AGEING_PER_YEAR * k
        dim = 1 - dim_rate * k
        life.append({"year": 2026 + k, "flat": _r(fc_total, 0), "age": _r(fc_total * age, 0),
                     "both": _r(fc_total * age * dim, 0)})

    # ---------------------------------------------------------------- white surface, money
    # The rear side's extra light is also extra heat. Rear irradiance rises by
    # gain / bifaciality relative to the front; the NOCT rise scales with it.
    dr = WHITE_GAIN / SITE.module.bifaciality
    t_w = hist["T2M"] + (SITE.module.noct - 20) / 800 * hist["g_w"] * (1 + dr)
    f_w = 1 + SITE.module.temp_coeff_pmax * (t_w - 25)
    hist["gen_white"] = hist["poa"] * (1 + WHITE_GAIN) * f_w * KWP * eta
    hist["t_cell_w"] = t_w
    hist["f_w"] = f_w
    wmo = hist.groupby([hist.index.year, hist.index.month])["gen_white"].mean().unstack()
    paint = []
    for f in fc:
        mo = f["month"]
        paint.append({"label": f["label"], "base": f["mean"], "light": _r(f["mean"] * (1 + WHITE_GAIN), 1),
                      "white": _r(wmo[mo].mean() * f["days"], 1)})
    paint_net = sum(p["white"] for p in paint) - fc_total
    # Other bound: cooler roof and air shave SURROUND_COOL off the cells while the sun is up.
    f_w2 = 1 + SITE.module.temp_coeff_pmax * (t_w - SURROUND_COOL - 25)
    g2 = hist["poa"] * (1 + WHITE_GAIN) * f_w2 * KWP * eta
    wmo2 = g2.groupby([hist.index.year, hist.index.month]).mean().unstack()
    paint_net_cool = sum(wmo2[f["month"]].mean() * f["days"] for f in fc) - fc_total
    heat_tab = []
    for mo in range(1, 13):
        h = hist[hist.index.month == mo]
        heat_tab.append({"month": calendar.month_abbr[mo],
                         "loss_now": _r((1 - (h.poa * h.f_temp).sum() / h.poa.sum()) * 100, 2),
                         "loss_white": _r((1 - (h.poa * h.f_w).sum() / h.poa.sum()) * 100, 2),
                         "rise_now": _r(((h.t_cell - h.T2M) * h.poa).sum() / h.poa.sum(), 1),
                         "rise_white": _r(((h.t_cell_w - h.T2M) * h.poa).sum() / h.poa.sum(), 1),
                         "cdd": _r((h.T2M - CDD_BASE).clip(lower=0).mean(), 2)})
    paint_kwh = paint_net
    paint_inr = paint_kwh * tariff.marginal_rate

    daily = [{"d": i.strftime("%Y-%m-%d"),
              "g": None if pd.isna(r.ALLSKY_SFC_SW_DWN) else _r(r.ALLSKY_SFC_SW_DWN, 2),
              "r": None if pd.isna(r.PRECTOTCORR) else _r(r.PRECTOTCORR, 1)}
             for i, r in raw.loc[str(bills.period_start.iloc[0].date()):str(bills.period_end.iloc[-1].date())].iterrows()]

    # ---------------------------------------------------------------- facts for prose
    tot = {k: float(M[k].sum()) for k in ["gen", "imp", "exp", "demand", "saved"]}
    tot_days = int(M.days.sum())
    self_tot = tot["gen"] - tot["exp"]
    may = M[M.occ_days < M.days].iloc[0] if (M.occ_days < M.days).any() else None
    cdd_raw = float(np.corrcoef(M.cdd, M.dem_day)[0, 1])
    cdd_occ = float(np.corrcoef(M.cdd, M.dem_occ)[0, 1])
    # Guests: fit demand-vs-heat on the other months, then see how far the guest month sits above it.
    host = M.month != GUEST_MONTH
    cdd_host = float(np.corrcoef(M.cdd[host], M.dem_occ[host])[0, 1])
    g = M[~host].iloc[0]
    ka, kb = np.polyfit(M.cdd[host], M.dem_occ[host], 1)
    guest_heat_dem = float(ka * g.cdd + kb)
    guest_excess = float((g.dem_occ - guest_heat_dem) * g.days)
    prev = M.iloc[list(M.month).index(GUEST_MONTH) - 1]
    sun_only = models[0]
    by_name = {m["name"]: m for m in models}
    norm = pd.DataFrame(normal)

    def f0(v):
        return f"{v:,.0f}"

    facts = {
        "n_months": len(M), "n_days": tot_days, "kwp": f"{KWP:g}",
        "first": bills.period_start.iloc[0].strftime("%-d %B %Y"),
        "last": bills.period_end.iloc[-1].strftime("%-d %B %Y"),
        "gen_total": f0(tot["gen"]), "imp_total": f0(tot["imp"]), "exp_total": f0(tot["exp"]),
        "dem_total": f0(tot["demand"]), "saved_total": f0(tot["saved"]),
        "saved_k": f"{tot['saved'] / 1000:.1f}",
        "yield_avg": f"{tot['gen'] / KWP / tot_days:.2f}",
        "offset_life": f"{tot['gen'] / tot['demand'] * 100:.0f}",
        "ss_life": f"{self_tot / tot['demand'] * 100:.0f}",
        "tilt": f"{SITE.tilt_deg:g}",
        "fit_a": f"{a:.2f}", "fit_c": f"{c:.2f}", "fit_r2": f"{r2:.2f}", "fit_r2_pct": f"{r2 * 100:.0f}",
        "fit_sd": f"{sd:.2f}",
        "sep_pred": f0(sep_pred), "sep_act": f0(actual[-1]),
        "sep_err": f"{(actual[-1] / sep_pred - 1) * 100:+.1f}".replace("-", "−"),
        "loo_mae": f"{sun_only['mae']:.0f}", "loo_worst": f"{sun_only['worst']:.0f}",
        "mae_sun": f"{by_name['Sunlight only']['mae']:.1f}",
        "mae_sun_t": f"{by_name['Sunlight + temperature']['mae']:.1f}",
        "mae_sun_rain": f"{by_name['Sunlight + rain']['mae']:.1f}",
        "mae_rain": f"{by_name['Rain only']['mae']:.1f}",
        "mae_temp": f"{by_name['Temperature only']['mae']:.1f}",
        "mae_poa": f"{by_name['Physics: panel-plane sun']['mae']:.1f}",
        "mae_phys": f"{by_name['Physics: panel-plane sun × heat']['mae']:.1f}",
        "eta": f"{eta:.3f}",
        "r_mar": f"{M.resid.iloc[1]:+.1f}".replace("-", "−"), "r_may": f"{M.resid.iloc[3]:+.1f}".replace("-", "−"),
        "r_sep": f"{M.resid.iloc[7]:+.1f}".replace("-", "−"),
        "may_gap": f0(M.expected.iloc[3] - M.gen.iloc[3]),
        "may_gap_days": f"{(M.expected.iloc[3] - M.gen.iloc[3]) / M.gen_day.iloc[3]:.1f}",
        "fc_total": f0(fc_total), "reg_total": f0(reg_total),
        "fc_start": fc[0]["label"], "fc_end": fc[-1]["label"],
        "yr_mean": f0(annual.mean()), "yr_min": f0(annual.min()), "yr_max": f0(annual.max()),
        "yr_min_year": str(int(annual.idxmin())), "yr_max_year": str(int(annual.idxmax())),
        "yr_cv": f"{annual.std() / annual.mean() * 100:.1f}",
        "jul_pct": f"{norm.pct.iloc[5]:+.0f}".replace("-", "−"), "aug_pct": f"{norm.pct.iloc[6]:+.0f}".replace("-", "−"),
        "y26_pct": f"{(np.average(norm.ghi_2026, weights=days) / np.average(norm.ghi_normal, weights=days) - 1) * 100:+.0f}".replace("-", "−"),
        "ghi_trend": f"{tg['slope_decade']:.2f}".replace("-", "−"), "clr_trend": f"{tc['slope_decade']:.2f}".replace("-", "−"),
        "kt_trend": f"{tk['slope_decade']:+.3f}".replace("-", "−"), "kt_p": f"{tk['p']:.2f}",
        "ghi_early": f"{ann[ann.year <= 1993].ghi.mean():.2f}", "ghi_late": f"{recent_ghi:.2f}",
        "dim_rate": f"{dim_rate * 100:.2f}",
        "life_end": f0(life[-1]["both"]), "life_drop": f"{(1 - life[-1]['both'] / fc_total) * 100:.0f}",
        "life_gap": f"{(life[-1]['age'] - life[-1]['both']) / fc_total * 100:.0f}",
        "paint_kwh": f0(paint_kwh), "paint_total": f0(fc_total * (1 + WHITE_GAIN)),
        "paint_inr": f0(round(paint_inr, -2)),
        "pay_lo": f"{PAINT_COST[0] / paint_inr:.1f}", "pay_hi": f"{PAINT_COST[1] / paint_inr:.1f}",
        "cdd_raw": f"{cdd_raw:+.2f}", "cdd_occ": f"{cdd_occ:+.2f}", "cdd_host": f"{cdd_host:+.2f}",
        "guest_month": GUEST_MONTH, "guest_dem": f"{g.dem_occ:.1f}", "guest_prev_dem": f"{prev.dem_occ:.1f}",
        "guest_prev": pd.Timestamp(prev.start).strftime("%B"), "guest_rise": f"{(g.dem_occ / prev.dem_occ - 1) * 100:.0f}",
        "guest_heat_dem": f"{guest_heat_dem:.1f}", "guest_excess": f0(round(guest_excess, -1)),
        "guest_per_day": f"{guest_excess / 7:.0f}",
        "dem_feb": f"{M.dem_day.iloc[0]:.0f}", "dem_jun": f"{M.dem_day.iloc[4]:.0f}",
        "dem_rise": f"{(M.dem_day.iloc[4] / M.dem_day.iloc[0] - 1) * 100:.0f}",
    }
    neg = lambda v: f"{v:+.1f}".replace("-", "−")  # noqa: E731
    for m in monthly:
        facts[f"r_{m['month'].lower()}"] = neg(m["resid"])
    facts.update({
        "unexpl": f"{(1 - r2) * 100:.0f}",
        "self_min": f"{M['self'].min():.0f}", "self_max": f"{M['self'].max():.0f}",
        "jul_rain": f0(normal[5]["rain_2026"]), "jul_rain_norm": f0(normal[5]["rain_normal"]),
        "phys_minus_reg": f"{(fc_total / reg_total - 1) * 100:.0f}",
        "fc_dec": f0(fc[[f['month'] for f in fc].index(12)]["mean"]),
        "fc_may": f0(fc[[f['month'] for f in fc].index(5)]["mean"]),
    })
    mfeb, mmay = monthly[0], monthly[3]
    facts.update({"feb_geo_abs": f"{abs(mfeb['geo'] - 1) * 100:.1f}", "may_geo_abs": f"{abs(mmay['geo'] - 1) * 100:.1f}",
                  "sep_band": f"{sd * days[-1]:.0f}",
                  "feb_gen": f"{mfeb['gen']:.1f}", "feb_days": str(mfeb["days"]),
                  "feb_gen_day": f"{mfeb['gen_day']:.1f}", "feb_ghi": f"{mfeb['ghi']:.2f}",
                  "feb_poa": f"{mfeb['poa']:.2f}", "may_poa": f"{mmay['poa']:.2f}", "may_ghi": f"{mmay['ghi']:.2f}"})
    H = {h["month"]: h for h in heat_tab}
    light_kwh = sum(p["light"] for p in paint) - fc_total
    peak = max(heat_tab, key=lambda h: h["loss_now"])
    facts.update({
        "feb_geo": f"{(mfeb['geo'] - 1) * 100:+.1f}".replace("-", "−"),
        "may_geo": f"{(mmay['geo'] - 1) * 100:+.1f}".replace("-", "−"),
        "feb_heat": f"{(1 - mfeb['heat']) * 100:.1f}", "may_heat": f"{(1 - mmay['heat']) * 100:.1f}",
        "feb_tmean": f"{mfeb['tmean']:.0f}", "may_tmean": f"{mmay['tmean']:.0f}",
        "feb_vs_may": f"{(mfeb['geo'] * mfeb['heat'] / (mmay['geo'] * mmay['heat']) - 1) * 100:.0f}",
        "pub_oct": f0(PUBLISHED_OCT_FORECAST),
        "pub_oct_err": f"{(actual[-1] / PUBLISHED_OCT_FORECAST - 1) * 100:+.1f}".replace("-", "−"),
        "loo_feb": f"{abs(loo_sun[0]):.0f}", "loo_may": f"{abs(loo_sun[3]):.0f}",
        "sep_sigma": f"{abs(actual[-1] - sep_pred) / (sd * days[-1]):.1f}",
        "used_share": f"{self_tot / tot['gen'] * 100:.0f}", "exp_share_life": f"{tot['exp'] / tot['gen'] * 100:.0f}",
        "credit_share": f"{tot['exp'] / tot['demand'] * 100:.0f}",
        "paid_share": f"{(tot['imp'] - tot['exp']) / tot['demand'] * 100:.0f}",
        "net_total": f0(tot["imp"] - tot["exp"]), "self_total": f0(self_tot),
        "light_kwh": f0(light_kwh), "heat_cost_kwh": f0(light_kwh - paint_net),
        "surround_cool": f"{SURROUND_COOL:.1f}",
        "peak_rise_net": f"{peak['rise_white'] - peak['rise_now'] - SURROUND_COOL:.1f}",
        "heat_cost_cool_kwh": f0(light_kwh - paint_net_cool), "paint_kwh_cool": f0(paint_net_cool),
        "white_net_pct": f"{paint_net / fc_total * 100:.0f}", "white_light_pct": f"{WHITE_GAIN * 100:.0f}",
        "peak_heat_month": {"Apr": "April", "May": "May", "Mar": "March", "Jun": "June"}.get(peak["month"], peak["month"]),
        "peak_heat_now": f"{peak['loss_now']:.1f}", "peak_heat_white": f"{peak['loss_white']:.1f}",
        "peak_rise_now": f"{peak['rise_now']:.0f}", "peak_rise_add": f"{peak['rise_white'] - peak['rise_now']:.1f}",
        "dec_heat_now": f"{H['Dec']['loss_now']:.1f}",
        "rear_increase": f"{WHITE_GAIN / SITE.module.bifaciality * 100:.0f}",
        "gamma": f"{SITE.module.temp_coeff_pmax * 100:.2f}".replace("-", "−"), "noct": f"{SITE.module.noct:g}",
        "bifaciality": f"{SITE.module.bifaciality * 100:.0f}", "albedo": f"{SITE.ground_albedo:.2f}",
        "lat": f"{SITE.latitude:.3f}", "lon": f"{SITE.longitude:.3f}",
        "life_years": str(LIFE_YEARS), "life_end_year": str(life[-1]["year"]),
        "warranty_end": f"{(1 - AGEING_PER_YEAR * (LIFE_YEARS - 1)) * 100:.1f}",
        "age_rate": f"{AGEING_PER_YEAR * 100:.1f}",
        "r_june": facts.get("r_jun", ""),
    })
    if may is not None:
        facts.update({
            "absent": f"{may.days - may.occ_days:g}", "may_dem_raw": f"{may.dem_day:.1f}",
            "may_dem_occ": f"{may.dem_occ:.1f}", "apr_dem": f"{M.dem_day.iloc[2]:.1f}",
            "may_vs_apr": f"{abs(may.dem_day / M.dem_day.iloc[2] - 1) * 100:.0f}",
            "may_cf_imp": f0(may.cf_imp - may.imp), "may_cf_exp": f0(may.exp - may.cf_exp),
            "may_cf_net": f0(may.cf_net - may.net), "may_cf_inr": f0(may.cf_charge),
            "may_scr": f"{may.scr:.0f}", "may_scr_occ": f"{may.scr_occ:.0f}",
            "exp_share": f"{may.exp / may.gen * 100:.0f}",
            "may_imp": f0(may.imp), "may_cf_imp_t": f0(may.cf_imp), "may_exp": f0(may.exp),
            "may_cf_exp_t": f0(may.cf_exp), "may_net": f0(may.net), "may_cf_net_t": f0(may.cf_net),
            "may_charge": f0(may.charge), "may_cf_charge_t": f0(may.charge + may.cf_charge),
        })

    # ---------------------------------------------------------------- the dust / heat / sky experiment
    X = _experiment(w26, hist, monthly, roll)
    T, P = X["tests"], X["pred"]

    def sg(v, n=2):
        return f"{v:+.{n}f}".replace("-", "−")

    def pdj(k):
        return float(np.mean([p[k] for p in P if p["label"] in ("Dec", "Jan")]))
    from scipy.stats import norm
    b_sd = (pdj("dust") + pdj("kt")) / 2          # verdict boundaries on the Dec-Jan mean residual
    b_sh = (pdj("kt") + pdj("tcell")) / 2
    se2 = X["sd"] / np.sqrt(2)                     # rough noise on a two-month mean
    X["rule"] = {"dust_below": b_sd, "heat_above": b_sh, "se": se2,
                 "miss_sky_dust": float(norm.cdf((b_sd - pdj("kt")) / se2)),
                 "miss_sky_heat": float(norm.sf((b_sh - pdj("kt")) / se2))}
    facts.update({
        "b_sd": sg(b_sd, 1), "b_sh": sg(b_sh, 1), "rule_se": f"{se2:.1f}",
        "miss_sd": f"{X['rule']['miss_sky_dust'] * 100:.0f}", "miss_sh": f"{X['rule']['miss_sky_heat'] * 100:.0f}",
        "prereg_date": "8 November 2026", "eta_frozen": f"{ETA_FROZEN:.3f}", "exp_n": str(EXP_N),
        "dust_mm": f"{DUST_RAIN_MM:.0f}", "exp_sd": f"{X['sd']:.1f}",
        **{f"rho_{k}": sg(T[k]["rho"]) for k in T},
        **{f"p_{k}": f"{T[k]['p']:.3f}" for k in T},
        **{f"ph_{k}": f"{T[k]['p_holm']:.3f}" for k in T},
        "part_dust_sky": sg(X["partial"]["dust_given_sky"]), "part_sky_dust": sg(X["partial"]["sky_given_dust"]),
        "part_heat_sky": sg(X["partial"]["heat_given_sky"]),
        "col_dust_kt": sg(X["collin"]["dust_kt"]), "col_dust_tcell": sg(X["collin"]["dust_tcell"]),
        **{f"pdj_{k}": sg(pdj(k), 1) for k in ("dust", "tcell", "kt")},
        "pnov_dust": sg(P[0]["dust"], 1), "pfeb_dust": sg(P[-1]["dust"], 1),
        "dust_nov_days": f"{P[0]['dust_x']:.0f}", "dust_feb_days": f"{P[-1]['dust_x']:.0f}",
        "dust_obs_max": f"{T['dust']['hi']:.0f}",
        "kt_winter_lo": f"{min(p['kt_x'] for p in P):.2f}", "kt_winter_hi": f"{max(p['kt_x'] for p in P):.2f}",
        "tc_winter_lo": f"{min(p['tcell_x'] for p in P):.0f}", "tc_winter_hi": f"{max(p['tcell_x'] for p in P):.0f}",
    })

    return {
        "experiment": X,
        "monthly": monthly, "daily": daily, "models": models,
        "fit": {"a": a, "c": c, "r2": r2, "sd": sd, "a7": a7, "c7": c7, "sep_pred": sep_pred,
                "loo": [_r(v, 1) for v in loo_sun]},
        "forecast": fc, "backtest": [{"year": int(k), "kwh": _r(v, 0)} for k, v in annual.items()],
        "weather_years": {int(yr): [_r(yr_mo.loc[yr, mo] * calendar.monthrange(2027, mo)[1], 1) for mo in range(1, 13)]
                          for yr in yr_mo.index},
        "normal": normal, "seasons": seasons,
        "annual": ann[["year", "ghi", "clr", "kt"]].round(3).to_dict("records"),
        "trends": {"ghi": tg, "clr": tc, "kt": tk},
        "paint": paint, "heat": heat_tab, "life": life, "eta": eta, "facts": facts,
    }
