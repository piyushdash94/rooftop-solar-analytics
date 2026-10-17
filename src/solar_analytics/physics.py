"""Weather -> expected energy, in one physical variable.

    E_eff = POA(sunlight, sky, panel angle) x f_temp(air temperature)   [kWh/m2/day]

POA       sunlight landing on the plane of the panels. Starts from measured
          horizontal sunlight (GHI), splits it into direct and diffuse light
          with Erbs' daily correlation, and tilts each part onto the panels.
f_temp    the heat derate: these modules lose 0.30% of output per degree of
          cell temperature above 25 C. Cell temperature follows the datasheet
          NOCT model, so panels run hot under strong sun and stay near air
          temperature under cloud: T_cell = T_air + (NOCT - 20)/800 x G,
          with G the energy-weighted mean irradiance of the day.

Multiply E_eff by kWp and one fitted system efficiency (eta) and you have the
energy the array should have made. The panels are taken as fixed at the
installed angle in config.Site; nothing here estimates it.

NASA POWER supplies daily totals, not hourly. Rather than invent an hourly
profile, the direct-light tilt factor is integrated over each day's solar
geometry at 15-minute resolution, weighted by clear-sky direct light.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import RAW_DIR, SITE

TEMP_COEFF = SITE.module.temp_coeff_pmax   # per degC (negative)
NOCT = SITE.module.noct                    # degC at 800 W/m2, 20 degC air, 1 m/s wind


def load_daily(path: Path | str | None = None) -> pd.DataFrame:
    """Daily NASA POWER CSV -> tz-aware frame (columns as NASA names them)."""
    path = Path(path) if path else RAW_DIR / "nasa_power_daily.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    df.index = df.index.tz_localize(SITE.timezone)
    df.index.name = "date"
    return df


def _beam_tilt_factor(days: pd.DatetimeIndex, tilt: float, azimuth: float) -> pd.Series:
    import pvlib

    loc = pvlib.location.Location(SITE.latitude, SITE.longitude, tz=SITE.timezone)
    times = pd.date_range(days[0].normalize(), days[-1].normalize() + pd.Timedelta("1D"),
                          freq="15min", tz=SITE.timezone)[:-1]
    sp = loc.get_solarposition(times)
    cs = loc.get_clearsky(times, model="ineichen", solar_position=sp)
    aoi = pvlib.irradiance.aoi(tilt, azimuth, sp["apparent_zenith"], sp["azimuth"])
    cos_aoi = np.cos(np.radians(aoi)).clip(lower=0)
    cos_zen = np.cos(np.radians(sp["apparent_zenith"])).clip(lower=0.03)
    w = cs["dni"].clip(lower=0)
    num = (w * cos_aoi).groupby(times.date).sum()
    den = (w * cos_zen).groupby(times.date).sum()
    rb = (num / den.replace(0, np.nan)).fillna(1.0)
    rb.index = pd.to_datetime(rb.index).tz_localize(SITE.timezone)
    return rb.clip(0.4, 2.5)


def effective_irradiation(w: pd.DataFrame, tilt: float | None = None,
                          azimuth: float | None = None,
                          albedo: float | None = None) -> pd.DataFrame:
    """Add kt, poa, f_temp and e_eff columns to a daily NASA POWER frame."""
    tilt = SITE.tilt_deg if tilt is None else tilt
    azimuth = SITE.azimuth_deg if azimuth is None else azimuth
    albedo = SITE.ground_albedo if albedo is None else albedo

    ghi = w["ALLSKY_SFC_SW_DWN"]
    doy = w.index.dayofyear
    decl = np.radians(23.45 * np.sin(np.radians(360 * (284 + doy) / 365)))
    lat = np.radians(SITE.latitude)
    ws = np.arccos(np.clip(-np.tan(lat) * np.tan(decl), -1, 1))
    h0 = (24 / np.pi) * 1367.0 * (1 + 0.033 * np.cos(np.radians(360 * doy / 365))) * (
        np.cos(lat) * np.cos(decl) * np.sin(ws) + ws * np.sin(lat) * np.sin(decl)) / 1000.0
    kt = (ghi / h0).clip(0, 1)

    fd = pd.Series(index=kt.index, dtype=float)              # Erbs daily diffuse fraction
    lo, hi = kt <= 0.22, kt > 0.80
    mid = ~lo & ~hi
    fd[lo] = 1.0 - 0.09 * kt[lo]
    k = kt[mid]
    fd[mid] = 0.9511 - 0.1604 * k + 4.388 * k**2 - 16.638 * k**3 + 12.336 * k**4
    fd[hi] = 0.165
    fd = fd.clip(0, 1)

    diffuse = ghi * fd
    beam = ghi - diffuse
    rb = _beam_tilt_factor(w.index, tilt, azimuth).reindex(w.index).ffill()
    t = np.radians(tilt)
    poa = beam * rb + diffuse * (1 + np.cos(t)) / 2 + ghi * albedo * (1 - np.cos(t)) / 2

    out = w.copy()
    out["kt"], out["diffuse_fraction"], out["rb"], out["poa"] = kt, fd, rb, poa
    # Energy-weighted mean irradiance for a sine-shaped day of length L hours
    # carrying `poa` kWh/m2: G = pi^2 * poa / (8 L), in kW/m2.
    day_len = 24 * ws / np.pi
    g_w = np.pi ** 2 * poa / (8 * day_len) * 1000.0
    out["g_w"] = g_w
    out["t_cell"] = out["T2M"] + (NOCT - 20) / 800 * g_w
    out["f_temp"] = 1 + TEMP_COEFF * (out["t_cell"] - 25.0)
    out["e_eff"] = out["poa"] * out["f_temp"]
    return out


def period_rollup(w: pd.DataFrame, bills: pd.DataFrame, kwp: float = SITE.kwp) -> pd.DataFrame:
    """Aggregate daily E_eff to billing periods and compute residuals.

    NASA POWER lags real time by about two weeks, so the latest period can miss
    trailing days. Expected energy is scaled to full coverage (days / weather
    days) rather than summed over the days that exist, which would fake an
    over-performance.
    """
    rows = []
    for b in bills.itertuples():
        win = w.loc[str(b.period_start.date()):str(b.period_end.date())]
        n = int(win["e_eff"].notna().sum())
        cov = n / b.days
        rows.append({
            "period_start": b.period_start, "days": b.days, "weather_days": n, "coverage": cov,
            "actual_kwh": b.generation_kwh,
            "ghi_mean": win["ALLSKY_SFC_SW_DWN"].mean(), "poa_mean": win["poa"].mean(),
            "e_eff_total": win["e_eff"].sum() / cov if n else np.nan,
            "f_temp_mean": win["f_temp"].mean(), "t_air_mean": win["T2M"].mean(),
            "rain_mm": win["PRECTOTCORR"].sum(),
        })
    d = pd.DataFrame(rows)
    d["eta_implied"] = d["actual_kwh"] / (d["e_eff_total"] * kwp)
    eta = float(d["eta_implied"].median())
    d["expected_kwh"] = d["e_eff_total"] * kwp * eta
    d["residual_pct"] = (d["actual_kwh"] / d["expected_kwh"] - 1) * 100
    d.attrs["eta_ref"] = eta
    return d
