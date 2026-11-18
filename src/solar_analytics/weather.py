"""Refresh the cached NASA POWER weather.

The article and the tests read only the committed CSVs in data/raw/, so nothing
here runs during a build. Use it when a new bill arrives:

    python -m solar_analytics.weather 2026-02-08 2026-10-31
    python -m solar_analytics.weather --daytime 2026-02-08 2026-10-31   # sun-weighted air temp

NASA POWER is free and needs no key. Sunlight (ALLSKY_SFC_SW_DWN, kWh/m²/day)
comes from CERES satellite products; temperature and rain from MERRA-2. Recent
weeks lag by about two weeks and are revised later, so re-download the latest
months before trusting them. Missing values arrive as -999 and become NaN.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

from .config import RAW_DIR, SITE

API = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = ["ALLSKY_SFC_SW_DWN", "CLRSKY_SFC_SW_DWN", "PRECTOTCORR", "T2M", "T2M_MAX", "CLOUD_AMT"]


def fetch_daily(start: str, end: str, lat: float = SITE.latitude,
                lon: float = SITE.longitude) -> pd.DataFrame:
    """Daily weather for [start, end] (ISO dates), indexed by date."""
    resp = requests.get(API, timeout=90, params={
        "parameters": ",".join(PARAMS), "community": "RE", "format": "JSON",
        "latitude": lat, "longitude": lon,
        "start": start.replace("-", ""), "end": end.replace("-", ""),
    })
    resp.raise_for_status()
    payload = resp.json()
    if "properties" not in payload:
        raise RuntimeError(f"Unexpected NASA POWER response: {str(payload)[:400]}")
    df = pd.DataFrame(payload["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    return df.apply(pd.to_numeric, errors="coerce").mask(lambda d: d <= -999)


def fetch_daytime_air(start: str, end: str, lat: float = SITE.latitude,
                      lon: float = SITE.longitude) -> pd.DataFrame:
    """Daily air temperature as the panels feel it: hourly T2M weighted by sunlight.

    The daily product's T2M is a 24-hour mean, nights included. Panels only work in daylight,
    so the physics model's heat derate is checked against two weightings of the hourly air
    temperature: by measured sunlight (`t_sun`, where NASA's hourly sunlight exists) and by
    clear-sky sunlight (`t_cs`, every day). Hours are local solar time.
    """
    import pvlib  # noqa: PLC0415  (only needed for this refresh)

    url = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    resp = requests.get(url, timeout=180, params={
        "parameters": "T2M,ALLSKY_SFC_SW_DWN", "community": "RE", "format": "JSON",
        "time-standard": "LST", "latitude": lat, "longitude": lon,
        "start": start.replace("-", ""), "end": end.replace("-", ""),
    })
    resp.raise_for_status()
    h = pd.DataFrame(resp.json()["properties"]["parameter"])
    h.index = pd.to_datetime(h.index, format="%Y%m%d%H")
    h = h.apply(pd.to_numeric, errors="coerce").mask(lambda d: d <= -999)
    loc = pvlib.location.Location(lat, lon, tz="Asia/Kolkata")
    mid = h.index.tz_localize("Asia/Kolkata") + pd.Timedelta(minutes=30)
    h["cs"] = loc.get_clearsky(mid)["ghi"].values
    day = h.resample("D")
    out = pd.DataFrame({
        "t_mean": day.T2M.mean(),
        "t_cs": (h.T2M * h.cs).resample("D").sum() / day.cs.sum(),
        "t_sun": (h.T2M * h.ALLSKY_SFC_SW_DWN).resample("D").sum()
        / day.ALLSKY_SFC_SW_DWN.sum(min_count=1),
    })
    out.index.name = "date"
    return out.round(3)


def refresh(start: str, end: str, path: Path | None = None) -> Path:
    """Download and overwrite the billed-period cache the article is built from."""
    path = path or RAW_DIR / "nasa_power_daily.csv"
    fetch_daily(start, end).to_csv(path)
    return path


if __name__ == "__main__":
    if sys.argv[1] == "--daytime":
        out = RAW_DIR / "nasa_power_daytemp_2026.csv"
        fetch_daytime_air(*sys.argv[2:4]).to_csv(out)
        print(f"wrote {out}")
    else:
        print(f"wrote {refresh(*sys.argv[1:3])}")
