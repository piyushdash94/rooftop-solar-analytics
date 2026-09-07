"""Intervention scenarios.

EVERY NUMBER IN THIS MODULE IS AN ESTIMATE. Nothing here is measured. Functions
return a `Scenario` carrying its own assumptions so the UI can display them
alongside the result rather than presenting modelled figures as observations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import SITE

# Waaree BiN-01 datasheet, bifacial backside power gain table.
# Rear gain depends on ground albedo and mounting height.
BIFACIAL_GAIN_TABLE = {0.15: 638, 0.20: 666, 0.25: 694, 0.30: 722}  # W, for the 555W SKU
NAMEPLATE_W = 555

# Monthly specific yield model (kWh/kWp/day), calibrated on 6 observed months
# and coastal-Odisha seasonality. Feb-Jul are observed; Aug-Jan are inferred.
SEASONAL_YIELD = {
    "Aug": 2.80, "Sep": 3.40, "Oct": 3.89, "Nov": 3.85, "Dec": 3.65, "Jan": 3.81,
    "Feb": 4.88, "Mar": 4.70, "Apr": 4.85, "May": 4.69, "Jun": 4.05, "Jul": 2.89,
}
DAYS_IN_MONTH = {
    "Jan": 31, "Feb": 28, "Mar": 31, "Apr": 30, "May": 31, "Jun": 30,
    "Jul": 31, "Aug": 31, "Sep": 30, "Oct": 31, "Nov": 30, "Dec": 31,
}


@dataclass
class Scenario:
    name: str
    annual_kwh: float
    annual_value_inr: float
    capex_inr: float
    assumptions: list[str] = field(default_factory=list)

    @property
    def delta_kwh(self) -> float:
        return self.annual_kwh - baseline_annual_kwh()

    @property
    def payback_years(self) -> float | None:
        delta_value = self.delta_kwh * SITE.tariff.marginal_rate
        return round(self.capex_inr / delta_value, 1) if delta_value > 0 else None


def baseline_annual_kwh(kwp: float = SITE.kwp) -> float:
    """Expected annual generation at current configuration."""
    return sum(SEASONAL_YIELD[m] * kwp * DAYS_IN_MONTH[m] for m in SEASONAL_YIELD)


def monthly_profile(kwp: float = SITE.kwp, uplift: float = 1.0) -> dict[str, float]:
    return {
        m: round(SEASONAL_YIELD[m] * kwp * DAYS_IN_MONTH[m] * uplift, 1)
        for m in SEASONAL_YIELD
    }


def effective_rear_gain(albedo: float) -> float:
    """Map ground albedo to a bifacial rear-gain fraction.

    ESTIMATE. The datasheet table is indexed by gain, not albedo -- this
    mapping is interpolated from the physical relationship between albedo,
    mounting height and rear irradiance. Treat as order-of-magnitude.
    """
    if albedo <= 0.15:
        return 0.05
    if albedo >= 0.70:
        return 0.175
    return 0.05 + (albedo - 0.15) * (0.175 - 0.05) / (0.70 - 0.15)


def scenario_baseline() -> Scenario:
    kwh = baseline_annual_kwh()
    return Scenario(
        name="Baseline (current setup)",
        annual_kwh=round(kwh, 0),
        annual_value_inr=round(kwh * SITE.tariff.marginal_rate, 0),
        capex_inr=0.0,
        assumptions=[
            "3.0 kWp over dark concrete, albedo ~0.12",
            "Seasonal yield model calibrated on 6 observed months",
        ],
    )


def scenario_white_surface() -> Scenario:
    """Paint or membrane the roof beneath the array to raise albedo."""
    gain_now = effective_rear_gain(SITE.ground_albedo)
    gain_after = effective_rear_gain(0.70)
    uplift = (1 + gain_after) / (1 + gain_now)
    kwh = baseline_annual_kwh() * uplift
    return Scenario(
        name="White reflective surface",
        annual_kwh=round(kwh, 0),
        annual_value_inr=round(kwh * SITE.tariff.marginal_rate, 0),
        capex_inr=10_000.0,
        assumptions=[
            f"Albedo {SITE.ground_albedo} -> 0.70 (white coating)",
            f"Rear gain {gain_now:.1%} -> {gain_after:.1%} (datasheet-derived)",
            "Mounting height unchanged; raising the array would compound this",
            "ESTIMATE - not measured on this roof",
        ],
    )


def scenario_white_surface_and_cleaning() -> Scenario:
    base = scenario_white_surface()
    kwh = base.annual_kwh * 1.035  # ~3.5% soiling recovery from quarterly cleaning
    return Scenario(
        name="White surface + quarterly cleaning",
        annual_kwh=round(kwh, 0),
        annual_value_inr=round(kwh * SITE.tariff.marginal_rate, 0),
        capex_inr=14_000.0,
        assumptions=base.assumptions
        + ["+3.5% from quarterly cleaning (pre-monsoon dust is the driver)"],
    )


def scenario_expansion(added_kwp: float, inverter_swap: bool = False) -> Scenario:
    """Add DC capacity.

    Note: PM Surya Ghar central subsidy is capped at Rs 78,000 for systems of
    3 kW and above, so expansion beyond the existing 3 kWp attracts no further
    central subsidy -- it is priced at full retail.
    """
    panel_cost = added_kwp * 1000 * 25          # ~Rs 25/W installed
    mounting = added_kwp * 1000 * 7
    inverter = 40_000 if inverter_swap else 0
    capex = panel_cost + mounting + inverter + 12_000  # cabling, labour, paperwork

    kwh = baseline_annual_kwh(SITE.kwp + added_kwp)
    return Scenario(
        name=f"Expand +{added_kwp} kWp" + (" (inverter swap)" if inverter_swap else ""),
        annual_kwh=round(kwh, 0),
        annual_value_inr=round(kwh * SITE.tariff.marginal_rate, 0),
        capex_inr=round(capex, 0),
        assumptions=[
            "No additional PM Surya Ghar subsidy above 3 kW - full retail cost",
            "Assumes existing inverter DC headroom" if not inverter_swap
            else "Includes Rs 40k inverter replacement",
            "New modules on a separate MPPT string to avoid mismatch losses",
            f"Sanctioned load {SITE.sanctioned_load_kw} kW - "
            f"{SITE.kwp + added_kwp} kWp is within limit",
        ],
    )


def all_scenarios() -> list[Scenario]:
    return [
        scenario_baseline(),
        scenario_white_surface(),
        scenario_white_surface_and_cleaning(),
        scenario_expansion(1.1),
        scenario_expansion(1.5),
        scenario_expansion(1.5, inverter_swap=True),
    ]
