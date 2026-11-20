"""Rebuild site/data.json, the only part of the article that changes month to month.

    python scripts/update_data.py

The article (site/index.html) is hand-written and published as it is. Its charts and the
numbers marked with data-k="..." read from site/data.json. When a new bill or new portal data
arrives: update the CSVs in data/, run this script, and edit prose only if a conclusion changed.
"""

from __future__ import annotations

import json
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
    daily = [{"d": i.strftime("%Y-%m-%d"), "gen": r(x.generation_kwh), "model": r(x.model),
              "imp": r(x.import_kwh), "exp": r(x.export_kwh), "sun": r(x.ALLSKY_SFC_SW_DWN, 2),
              "rain": r(x.PRECTOTCORR)} for i, x in d.iterrows()]

    both = d.dropna(subset=["generation_kwh", "model"])
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

    # ---- months: billed periods, then the current month to date from daily generation
    monthly = [{"label": m["month"], "start": m["start"], "days": m["days"], "gen": r(m["gen"]),
                "imp": r(m["imp"]), "exp": r(m["exp"]), "demand": r(m["demand"]), "sun": r(m["ghi"], 2),
                "expected": r(m["expected"]), "resid": r(m["resid"]), "bill": r(m["billed"], 0),
                "saved": r(m["saved"], 0)} for m in B["monthly"]]
    fc = [{"label": x["label"], "month": x["month"], "mean": r(x["mean"], 0), "p10": r(x["p10"], 0),
           "p90": r(x["p90"], 0)} for x in B["forecast"]]

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
        "latest": monthly[-1], "mtd": mtd, "tests": tests, "check": check,
        "monthly": monthly, "forecast": fc, "daily": daily,
        "hinge": {"base": r(hinge["base"]), "slope": r(hinge["slope"]), "tb": r(hinge["tb"]),
                  "points": [{"t": p["t"], "y": p["y"], "e": p["e"]} for p in hinge["points"]]},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB): "
          f"{len(monthly)} bills, {len(daily)} days, check n={check['n']}")


if __name__ == "__main__":
    main()
