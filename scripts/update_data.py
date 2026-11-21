"""Rebuild site/data.json, the only part of the article that changes month to month.

    python scripts/update_data.py

The article (site/index.html) is hand-written and published as it is. Its charts and the
numbers marked with data-k="..." read from site/data.json. When a new bill or new portal data
arrives: update the CSVs in data/, run this script, and edit prose only if a conclusion changed.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from solar_analytics import physics  # noqa: E402
from solar_analytics.config import SITE  # noqa: E402
from solar_analytics.loaders import load_daily_meter  # noqa: E402
from solar_analytics.story import ETA_FROZEN, PUBLISHED_OCT_FORECAST, compute  # noqa: E402

OUT = ROOT / "site" / "data.json"


def r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def main() -> None:
    B = compute()
    f = B["facts"]

    # ---- daily: exact portal import/export, metered generation where we have it, model always
    w = physics.effective_irradiation(physics.load_daily())
    w.index = w.index.tz_localize(None).normalize()
    meter = load_daily_meter()
    gen = pd.read_csv(ROOT / "data" / "daily_generation.csv", parse_dates=["date"], index_col="date")
    d = pd.DataFrame(index=pd.date_range(meter.index.min(), max(meter.index.max(), gen.index.max())))
    d = d.join(meter).join(gen[["generation_kwh"]]).join(gen[["import_kwh"]].rename(columns={"import_kwh": "imp_chart"}))
    d["import_kwh"] = d.import_kwh.fillna(d.imp_chart)
    d = d.join(w[["ALLSKY_SFC_SW_DWN", "PRECTOTCORR", "T2M", "e_eff"]])
    d["model"] = d.e_eff * SITE.kwp * ETA_FROZEN
    fa, fc0 = float(f["fit_a"]), float(f["fit_c"])
    d["line"] = fa * d.ALLSKY_SFC_SW_DWN + fc0          # the sunlight regression, applied day by day
    daily = [{"d": i.strftime("%Y-%m-%d"), "gen": r(x.generation_kwh), "model": r(x.model), "line": r(x.line),
              "imp": r(x.import_kwh), "exp": r(x.export_kwh), "sun": r(x.ALLSKY_SFC_SW_DWN, 2),
              "rain": r(x.PRECTOTCORR)} for i, x in d.iterrows()]

    both = d.dropna(subset=["generation_kwh", "model", "line"])
    clear = both[both.ALLSKY_SFC_SW_DWN >= 4]
    rr = np.corrcoef(both.generation_kwh, both.model)[0, 1]
    over = d.dropna(subset=["generation_kwh", "export_kwh"])
    self_use = over.generation_kwh - over.export_kwh
    check = {"n": len(both), "from": both.index.min().strftime("%-d %b"), "to": both.index.max().strftime("%-d %b"),
             "total_err": r((both.generation_kwh.sum() / both.model.sum() - 1) * 100),
             "total_err_abs": r(abs(both.generation_kwh.sum() / both.model.sum() - 1) * 100),
             "r2": r(rr * rr * 100, 0), "mae": r((both.generation_kwh - both.model).abs().mean()),
             "clear_mae_pct": r(((clear.generation_kwh / clear.model) - 1).abs().mean() * 100, 0),
             "self_share": r(self_use.sum() / over.generation_kwh.sum() * 100, 0),
             "self_kwh": r(self_use.mean()), "overlap_days": len(over)}
    rl = np.corrcoef(both.generation_kwh, both.line)[0, 1]
    check["line_total_err"] = r((both.generation_kwh.sum() / both.line.sum() - 1) * 100)
    check["line_r2"] = r(rl * rl * 100, 0)
    check["line_mae"] = r((both.generation_kwh - both.line).abs().mean())
    # signed "model vs meter": positive means the model expected more than the panels made
    check["phys_vs_meter"] = r((both.model.sum() / both.generation_kwh.sum() - 1) * 100)
    check["line_vs_meter"] = r((both.line.sum() / both.generation_kwh.sum() - 1) * 100)
    check["line_under"] = r(-check["line_vs_meter"])
    sg = lambda v: f"{v:+.1f}%".replace("-", "−")  # noqa: E731
    check["phys_vs_meter_s"], check["line_vs_meter_s"] = sg(check["phys_vs_meter"]), sg(check["line_vs_meter"])
    check["exact_days"] = int((gen.get("gen_source", pd.Series(dtype=str)) == "portal table, exact").sum())

    # ---- the two models side by side, month by month (leave-one-out: each month predicted
    #      by the model fitted on the other months), and their twelve-month forecasts
    mods = {m["name"]: m for m in B["models"]}
    line_m, phys_m = mods["Sunlight only"], mods["Physics: panel-plane sun × heat"]
    compare = {
        "months": [{"label": m["month"], "actual": r(m["gen"] / m["days"], 2),
                    "line": r(m["gen"] / m["days"] * (1 + le / 100), 2),
                    "phys": r(m["gen"] / m["days"] * (1 + pe / 100), 2), "line_err": le, "phys_err": pe}
                   for m, le, pe in zip(B["monthly"], line_m["errs"], phys_m["errs"], strict=True)],
        "line": {"mae": r(line_m["mae"]), "worst": r(line_m["worst"]), "year": f["reg_total"]},
        "phys": {"mae": r(phys_m["mae"]), "worst": r(phys_m["worst"]), "year": f["fc_total"]},
        "temp_mae": r(mods["Sunlight + temperature"]["mae"]), "rain_mae": r(mods["Sunlight + rain"]["mae"]),
    }

    # ---- months: billed periods, then the current month to date from daily generation
    monthly = [{"label": m["month"], "start": m["start"], "days": m["days"], "gen": r(m["gen"]),
                "imp": r(m["imp"]), "exp": r(m["exp"]), "demand": r(m["demand"]), "sun": r(m["ghi"], 2),
                "expected": r(m["expected"]), "resid": r(m["resid"]), "bill": r(m["billed"], 0),
                "saved": r(m["saved"], 0)} for m in B["monthly"]]
    fc = [{"label": x["label"], "month": x["month"], "mean": r(x["mean"], 0), "p10": r(x["p10"], 0),
           "p90": r(x["p90"], 0), "line": r(x["regression"], 0)} for x in B["forecast"]]

    last_end = pd.Timestamp(B["monthly"][-1]["end"]) if "end" in B["monthly"][-1] else None
    cur = d[d.index > (last_end if last_end is not None else d.index.min())].dropna(subset=["generation_kwh"])
    mtd = None
    if len(cur):
        mo = cur.index[0].month
        fmo = next((x for x in fc if x["month"] == mo), None)
        dim = cur.index[0].days_in_month
        mtd = {"label": cur.index[0].strftime("%B"), "days": len(cur), "dim": dim,
               "gen": r(cur.generation_kwh.sum(), 0), "per_day": r(cur.generation_kwh.mean()),
               "fc": fmo["mean"] if fmo else None, "fc_per_day": r(fmo["mean"] / dim) if fmo else None,
               "imp": r(cur.import_kwh.sum(), 0), "to": cur.index[-1].strftime("%-d %B")}

    winter = [x for x in fc if x["month"] in (11, 12, 1, 2)]
    compare["gap_year"] = r(sum(x["mean"] - x["line"] for x in fc), 0)
    compare["gap_winter"] = r(sum(x["mean"] - x["line"] for x in winter), 0)

    tests = [{"label": "October", "kind": "published forecast", "fc": round(PUBLISHED_OCT_FORECAST),
              "actual": r(B["monthly"][-1]["gen"], 0) if B["monthly"][-1]["month"] == "Oct" else None}]

    hinge = B["daily_demand"]
    out = {
        "updated": date.today().isoformat(),
        "bills_through": B["facts"]["last"],
        "headline": {"gen": f["gen_total"], "saved": f["saved_total"], "offset": f["offset_life"],
                     "self": f["ss_life"], "credit": f["credit_share"], "year": f["fc_total"],
                     "year_lo": f["yr_min"], "year_hi": f["yr_max"], "r2": f["fit_r2_pct"],
                     "bills": len(B["monthly"]), "days": f["n_days"], "fit_a": f["fit_a"], "fit_c": f["fit_c"],
                     "may": f["r_may"], "jul": f["jul_pct"].lstrip("−-"), "aug": f["aug_pct"].lstrip("−-"),
                     "white": f["paint_kwh"]},
        "latest": monthly[-1], "mtd": mtd, "tests": tests, "check": check, "compare": compare,
        "coverage": {"bill_from": B["monthly"][0]["start"], "bills": len(monthly),
                     "meter_days": int(meter.import_kwh.notna().sum()),
                     "meter_from": meter.index.min().strftime("%-d %b"), "meter_to": meter.index.max().strftime("%-d %b"),
                     "gen_days": int(gen.generation_kwh.notna().sum()),
                     "gen_from": gen.index.min().strftime("%-d %b"), "gen_to": gen.index.max().strftime("%-d %b"),
                     "sun_to": w.ALLSKY_SFC_SW_DWN.last_valid_index().strftime("%-d %b")},
        "monthly": monthly, "forecast": fc, "daily": daily,
        "hinge": {"base": r(hinge["base"]), "slope": r(hinge["slope"]), "tb": r(hinge["tb"]),
                  "points": [{"t": p["t"], "y": p["y"], "e": p["e"]} for p in hinge["points"]]},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    n = sync_defaults(out)
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB): "
          f"{len(monthly)} bills, {len(daily)} days, check n={check['n']}; {n} fallback numbers refreshed")


def _jsfmt(v) -> str:
    """Mirror of the page's fmt(): thousands get separators, whole numbers drop the .0."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if abs(v) >= 1000:
            return f"{round(v):,}"
        return str(int(v)) if float(v).is_integer() else repr(float(v))
    return str(v)


def sync_defaults(data: dict) -> int:
    """Refresh the fallback text of every data-k number in site/index.html. Prose is untouched."""
    page = ROOT / "site" / "index.html"
    html = page.read_text(encoding="utf-8")

    def get(path):
        d = data
        for k in path.split("."):
            d = d[int(k)] if isinstance(d, list) else d[k]
        return d

    changed = 0

    def sub(m):
        nonlocal changed
        want = _jsfmt(get(m.group(1)))
        changed += want != m.group(2)
        return f'data-k="{m.group(1)}">{want}<'

    page.write_text(re.sub(r'data-k="([\w.]+)">([^<]*)<', sub, html), encoding="utf-8")
    return changed


if __name__ == "__main__":
    main()
