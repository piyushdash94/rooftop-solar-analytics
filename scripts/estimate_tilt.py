"""Estimate site tilt by transposing GHI -> POA and testing which tilt
produces the most physically plausible Performance Ratio series.

Method
------
1. Decompose daily GHI into DNI + DHI using the Erbs correlation.
2. Transpose to plane-of-array for candidate tilts using the Hay-Davies model.
3. Recompute PR against POA.
4. Score each tilt: a correct tilt should push all PR values below 100%
   (physically required) while keeping the series as flat as possible --
   a systematically wrong tilt introduces a seasonal sawtooth into PR.
"""

import pandas as pd
import pvlib

LAT, LON, TZ = 20.312069, 85.867744, "Asia/Kolkata"
KWP = 3.0
ALBEDO = 0.12

PERIODS = {
    "Feb": ("2026-02-08", "2026-03-01", 321.91, 22),
    "Mar": ("2026-03-02", "2026-04-01", 389.55, 31),
    "Apr": ("2026-04-02", "2026-05-01", 436.34, 30),
    "May": ("2026-05-02", "2026-06-01", 436.53, 31),
    "Jun": ("2026-06-02", "2026-07-01", 364.67, 30),
    "Jul": ("2026-07-02", "2026-08-01", 268.76, 31),
}

w = pd.read_csv("data/raw/nasa_power_daily.csv", index_col=0, parse_dates=True)
w = w.apply(pd.to_numeric, errors="coerce")
w.index = w.index.tz_localize(TZ)

# Hourly grid: expand daily GHI into an hourly clear-sky-shaped profile,
# because transposition needs solar position, which varies within the day.
loc = pvlib.location.Location(LAT, LON, tz=TZ)


def daily_poa(tilt: float, azimuth: float = 180.0) -> pd.Series:
    """Return daily POA irradiation (kWh/m2/day) for a given tilt."""
    out = {}
    for day, ghi_day in w["ALLSKY_SFC_SW_DWN"].items():
        if pd.isna(ghi_day):
            continue
        times = pd.date_range(day.normalize(), periods=24, freq="h", tz=TZ)
        cs = loc.get_clearsky(times, model="ineichen")
        solpos = loc.get_solarposition(times)

        # Shape the measured daily total using the clear-sky hourly profile
        shape = cs["ghi"] / cs["ghi"].sum() if cs["ghi"].sum() > 0 else cs["ghi"]
        ghi_h = shape * (ghi_day * 1000)  # kWh/m2/day -> Wh/m2 across the day

        # Erbs decomposition needs GHI + zenith
        erbs = pvlib.irradiance.erbs(ghi_h, solpos["zenith"], times)
        dni, dhi = erbs["dni"].fillna(0), erbs["dhi"].fillna(0)

        poa = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt,
            surface_azimuth=azimuth,
            solar_zenith=solpos["apparent_zenith"],
            solar_azimuth=solpos["azimuth"],
            dni=dni,
            ghi=ghi_h,
            dhi=dhi,
            dni_extra=pvlib.irradiance.get_extra_radiation(times),
            albedo=ALBEDO,
            model="haydavies",
        )
        out[day] = poa["poa_global"].sum() / 1000.0  # back to kWh/m2/day
    return pd.Series(out)


def pr_series(poa_daily: pd.Series) -> pd.DataFrame:
    rows = []
    for m, (s, e, gen, days) in PERIODS.items():
        poa = poa_daily.loc[s:e].mean()
        ghi = w.loc[s:e, "ALLSKY_SFC_SW_DWN"].mean()
        t = w.loc[s:e, "T2M"].mean()
        yld = gen / KWP / days
        pr_ghi = yld / ghi
        pr_poa = yld / poa
        derate = 1 + (-0.0030) * ((t + 25) - 25)
        rows.append(
            dict(month=m, ghi=round(ghi, 2), poa=round(poa, 2),
                 gain=round(poa / ghi, 3), yield_=round(yld, 2),
                 pr_ghi=round(pr_ghi * 100, 1),
                 pr_poa=round(pr_poa * 100, 1),
                 pr_poa_t=round(pr_poa / derate * 100, 1))
        )
    return pd.DataFrame(rows)


results = {}
for tilt in [0, 5, 10, 12, 15, 20, 25]:
    poa_d = daily_poa(tilt)
    df = pr_series(poa_d)
    over = (df["pr_poa_t"] > 100).sum()
    spread = df["pr_poa_t"].max() - df["pr_poa_t"].min()
    cv = df["pr_poa_t"].std() / df["pr_poa_t"].mean()
    results[tilt] = dict(df=df, over100=over, spread=round(spread, 1),
                         cv=round(cv, 4), mean_pr=round(df["pr_poa_t"].mean(), 1))
    print(f"tilt={tilt:>2}deg  mean PR={results[tilt]['mean_pr']:>5.1f}%  "
          f"spread={spread:>5.1f}  CV={cv:.4f}  months>100%={over}")

print("\n=== DETAIL AT 12 deg ===")
print(results[12]["df"].to_string(index=False))

import json

summary = {str(k): {"mean_pr": v["mean_pr"], "spread": v["spread"],
                    "cv": v["cv"], "over100": int(v["over100"]),
                    "rows": v["df"].to_dict("records")}
           for k, v in results.items()}
with open("data/raw/tilt_scan.json", "w") as f:
    json.dump(summary, f, indent=1)
print("\nsaved tilt_scan.json")
