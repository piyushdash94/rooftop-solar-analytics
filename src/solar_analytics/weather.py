"""Weather and irradiance providers.

Three free sources, one interface. NASA POWER is the default because it needs
no key, covers 1981-present globally, and returns clear-sky irradiance -- which
is what makes the clearness index computable.

Provider notes
--------------
NASAPower   : no key, daily, global. CLRSKY and CLOUD_AMT go NULL for recent
              dates (typically the trailing ~1-2 months). Missing = -999.0.
PVGIS       : EU JRC. Returns plane-of-array irradiance directly for a given
              tilt/azimuth -- the correct denominator for Performance Ratio.
              Use this once site tilt is measured.
OpenMeteo   : ERA5 reanalysis, hourly, free but aggressively rate-limited
              (429s are routine on shared IPs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from .config import RAW_DIR, SITE

NASA_PARAMS = [
    "ALLSKY_SFC_SW_DWN",   # measured GHI, kWh/m2/day
    "CLRSKY_SFC_SW_DWN",   # clear-sky GHI, kWh/m2/day
    "PRECTOTCORR",         # precipitation, mm/day
    "T2M",                 # mean air temperature, degC
    "T2M_MAX",
    "CLOUD_AMT",           # cloud fraction, %
]


class WeatherProvider(Protocol):
    def fetch(self, start: str, end: str) -> pd.DataFrame: ...


class NASAPower:
    """NASA POWER daily point API. Free, no authentication."""

    BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

    def __init__(self, lat: float = SITE.latitude, lon: float = SITE.longitude):
        self.lat, self.lon = lat, lon

    def fetch(self, start: str, end: str) -> pd.DataFrame:
        """start/end as YYYYMMDD."""
        resp = requests.get(
            self.BASE,
            params={
                "parameters": ",".join(NASA_PARAMS),
                "community": "RE",
                "latitude": self.lat,
                "longitude": self.lon,
                "start": start,
                "end": end,
                "format": "JSON",
            },
            timeout=90,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "properties" not in payload:
            raise RuntimeError(f"Unexpected NASA POWER response: {str(payload)[:400]}")

        df = pd.DataFrame(payload["properties"]["parameter"])
        df.index = pd.to_datetime(df.index, format="%Y%m%d")
        df.index.name = "date"
        return df.apply(pd.to_numeric, errors="coerce").replace(-999.0, pd.NA)


class OpenMeteoArchive:
    """Open-Meteo ERA5 archive. Free, no key, but rate-limited."""

    BASE = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, lat: float = SITE.latitude, lon: float = SITE.longitude):
        self.lat, self.lon = lat, lon

    def fetch(self, start: str, end: str) -> pd.DataFrame:
        """start/end as YYYY-MM-DD."""
        resp = requests.get(
            self.BASE,
            params={
                "latitude": self.lat,
                "longitude": self.lon,
                "start_date": start,
                "end_date": end,
                "daily": ",".join(
                    [
                        "shortwave_radiation_sum",
                        "precipitation_sum",
                        "temperature_2m_max",
                        "temperature_2m_mean",
                        "cloud_cover_mean",
                        "sunshine_duration",
                    ]
                ),
                "timezone": SITE.timezone,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            raise RuntimeError("Open-Meteo rate limit hit. Use NASAPower instead.")
        resp.raise_for_status()
        daily = resp.json()["daily"]
        df = pd.DataFrame(daily)
        df["date"] = pd.to_datetime(df.pop("time"))
        df = df.set_index("date")
        # MJ/m2/day -> kWh/m2/day
        df["ALLSKY_SFC_SW_DWN"] = df["shortwave_radiation_sum"] / 3.6
        df["T2M"] = df["temperature_2m_mean"]
        df["T2M_MAX"] = df["temperature_2m_max"]
        df["PRECTOTCORR"] = df["precipitation_sum"]
        return df


def load_or_fetch(
    start: str,
    end: str,
    provider: WeatherProvider | None = None,
    cache: Path | None = None,
) -> pd.DataFrame:
    """Return cached weather if present, else fetch and cache.

    Network calls in a portfolio repo are a reproducibility hazard -- a reviewer
    cloning this should get results without hitting an API. The cache is
    committed for that reason.
    """
    cache = cache or RAW_DIR / "nasa_power_daily.csv"
    if cache.exists():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        return df.apply(pd.to_numeric, errors="coerce")

    provider = provider or NASAPower()
    df = provider.fetch(start.replace("-", ""), end.replace("-", ""))
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache)
    return df
