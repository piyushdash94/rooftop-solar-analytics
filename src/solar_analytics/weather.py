"""Refresh the cached NASA POWER weather.

The article and the tests read only the committed CSVs in data/raw/, so nothing
here runs during a build. Use it when a new bill arrives:

    python -m solar_analytics.weather 2026-02-08 2026-10-31

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


def refresh(start: str, end: str, path: Path | None = None) -> Path:
    """Download and overwrite the billed-period cache the article is built from."""
    path = path or RAW_DIR / "nasa_power_daily.csv"
    fetch_daily(start, end).to_csv(path)
    return path


if __name__ == "__main__":
    print(f"wrote {refresh(*sys.argv[1:3])}")
