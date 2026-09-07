"""Performance metrics.

Naming convention: any metric computed against *horizontal* irradiance carries
the `_ghi` suffix and is systematically biased (see `PR_TILT_CAVEAT`). Do not
strip the suffix until plane-of-array transposition is implemented.
"""

from __future__ import annotations

import warnings

import pandas as pd

from .config import SITE

PR_TILT_CAVEAT = (
    "PR computed against horizontal irradiance (GHI). Tilted panels receive "
    "plane-of-array irradiance, which exceeds GHI in low-sun months. This "
    "INFLATES apparent PR in winter -- values >100% are an artefact, not "
    "overperformance. Fix requires site tilt/azimuth + pvlib transposition."
)


def specific_yield(generation_kwh: pd.Series, days: pd.Series, kwp: float = SITE.kwp) -> pd.Series:
    """kWh per kWp per day. Removes system size, not weather."""
    return generation_kwh / kwp / days


def clearness_index(ghi: pd.Series, clear_sky_ghi: pd.Series) -> pd.Series:
    """Kt = measured / clear-sky irradiance. Pure atmosphere metric, 0..1."""
    return ghi / clear_sky_ghi


def performance_ratio_ghi(yield_per_kwp: pd.Series, ghi: pd.Series) -> pd.Series:
    """PR against horizontal irradiance. Biased -- see PR_TILT_CAVEAT."""
    warnings.warn(PR_TILT_CAVEAT, UserWarning, stacklevel=2)
    return yield_per_kwp / ghi


def cell_temperature(ambient_c: pd.Series, noct: float = SITE.module.noct) -> pd.Series:
    """Crude NOCT-style cell temperature proxy.

    ASSUMPTION: cells run ~25 degC above ambient under load. A proper model
    (Faiman, or pvlib's SAPM) needs wind speed and irradiance. Documented as
    an assumption, not a measurement.
    """
    return ambient_c + 25.0


def temperature_corrected_pr(
    pr: pd.Series,
    ambient_c: pd.Series,
    temp_coeff: float = SITE.module.temp_coeff_pmax,
) -> pd.Series:
    """Divide out thermal derating using the datasheet Pmax coefficient."""
    t_cell = cell_temperature(ambient_c)
    derate = 1 + temp_coeff * (t_cell - 25.0)
    return pr / derate


def self_consumption_ratio(generation: pd.Series, export: pd.Series) -> pd.Series:
    """Share of generation used on site. Measures load-profile matching."""
    return (generation - export) / generation


def self_sufficiency(generation: pd.Series, export: pd.Series, imp: pd.Series) -> pd.Series:
    """PHYSICAL self-sufficiency: share of demand met by solar *at the moment of use*.

    Excludes exported units, which were generated but consumed elsewhere.
    This is the honest "how independent am I?" number.
    """
    self_used = generation - export
    return self_used / (imp + self_used)


def solar_offset_ratio(generation: pd.Series, export: pd.Series, imp: pd.Series) -> pd.Series:
    """BILLING offset: generation as a share of demand.

    Under 1:1 net metering an exported unit cancels an imported unit, so this
    is what the bill effectively reflects. It is ALWAYS >= self_sufficiency and
    the two must never be conflated -- the gap between them is exactly the
    energy you exported rather than used.
    """
    self_used = generation - export
    return generation / (imp + self_used)


def capacity_factor(generation_kwh: pd.Series, days: pd.Series, kwp: float = SITE.kwp) -> pd.Series:
    return generation_kwh / (kwp * 24 * days)


def summarise_periods(bills: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Join billing periods to daily weather and compute all metrics.

    Returns one row per billing cycle.
    """
    rows = []
    for _, b in bills.iterrows():
        window = weather.loc[
            b["period_start"].strftime("%Y-%m-%d") : b["period_end"].strftime("%Y-%m-%d")
        ]
        ghi = window["ALLSKY_SFC_SW_DWN"].mean()
        clr = window.get("CLRSKY_SFC_SW_DWN", pd.Series(dtype=float)).mean()
        kt = (
            (window["ALLSKY_SFC_SW_DWN"] / window["CLRSKY_SFC_SW_DWN"]).mean()
            if "CLRSKY_SFC_SW_DWN" in window
            else float("nan")
        )
        t_mean = window["T2M"].mean()
        yld = b["generation_kwh"] / SITE.kwp / b["days"]
        pr = yld / ghi
        t_cell = t_mean + 25.0
        pr_t = pr / (1 + SITE.module.temp_coeff_pmax * (t_cell - 25.0))
        self_used = b["generation_kwh"] - b["export_kwh"]

        rows.append(
            {
                "month": b["month"],
                "period_start": b["period_start"],
                "days": b["days"],
                "generation_kwh": b["generation_kwh"],
                "import_kwh": b["import_kwh"],
                "export_kwh": b["export_kwh"],
                "self_used_kwh": round(self_used, 2),
                "demand_kwh": round(b["import_kwh"] + self_used, 2),
                "ghi": round(ghi, 3),
                "clear_sky_ghi": round(clr, 3) if pd.notna(clr) else None,
                "kt": round(kt, 3) if pd.notna(kt) else None,
                "specific_yield": round(yld, 3),
                "pr_ghi": round(pr * 100, 1),
                "pr_ghi_tcorr": round(pr_t * 100, 1),
                "scr": round(self_used / b["generation_kwh"] * 100, 1),
                "self_sufficiency": round(self_used / (b["import_kwh"] + self_used) * 100, 1),
                "solar_offset": round(
                    b["generation_kwh"] / (b["import_kwh"] + self_used) * 100, 1
                ),
                "capacity_factor": round(
                    b["generation_kwh"] / (SITE.kwp * 24 * b["days"]) * 100, 1
                ),
                "rain_mm": round(window["PRECTOTCORR"].sum(), 1),
                "rain_days": int((window["PRECTOTCORR"] > 1).sum()),
                "tmax_mean": round(window["T2M_MAX"].mean(), 1),
                "savings_inr": round(b["generation_kwh"] * SITE.tariff.marginal_rate, 0),
            }
        )

    out = pd.DataFrame(rows)
    out.attrs["caveat"] = PR_TILT_CAVEAT
    out.attrs["n_observations"] = len(out)
    return out
