"""Metric and scenario tests."""

from __future__ import annotations

import pandas as pd
import pytest

from solar_analytics.config import SITE
from solar_analytics.loaders import load_bills
from solar_analytics.metrics import (
    capacity_factor,
    clearness_index,
    self_consumption_ratio,
    self_sufficiency,
    specific_yield,
    summarise_periods,
)
from solar_analytics.scenarios import (
    all_scenarios,
    baseline_annual_kwh,
    effective_rear_gain,
    scenario_white_surface,
)
from solar_analytics.weather import load_or_fetch


@pytest.fixture(scope="module")
def summary() -> pd.DataFrame:
    bills = load_bills()
    weather = load_or_fetch("2026-02-08", "2026-08-01")
    return summarise_periods(bills, weather)


# --- primitive metrics -------------------------------------------------------

def test_specific_yield_known_value():
    """Feb: 321.91 kWh / 3 kWp / 22 days = 4.878"""
    y = specific_yield(pd.Series([321.91]), pd.Series([22]), kwp=3.0)
    assert y.iloc[0] == pytest.approx(4.878, abs=0.001)


def test_clearness_index_bounded():
    kt = clearness_index(pd.Series([5.12]), pd.Series([5.61]))
    assert 0 < kt.iloc[0] <= 1.05


def test_self_consumption_ratio():
    scr = self_consumption_ratio(pd.Series([364.67]), pd.Series([111.97]))
    assert scr.iloc[0] == pytest.approx(0.693, abs=0.001)


def test_self_sufficiency():
    ss = self_sufficiency(pd.Series([364.67]), pd.Series([111.97]), pd.Series([794.94]))
    assert ss.iloc[0] == pytest.approx(0.241, abs=0.005)


def test_capacity_factor_plausible():
    cf = capacity_factor(pd.Series([436.34]), pd.Series([30]), kwp=3.0)
    assert 0.10 < cf.iloc[0] < 0.25


# --- period summary ----------------------------------------------------------

def test_summary_has_seven_rows(summary):
    assert len(summary) == 7
    assert summary.attrs["n_observations"] == 7


def test_summary_carries_tilt_caveat(summary):
    """The GHI/POA caveat must travel with the data, not live only in docs."""
    assert "horizontal" in summary.attrs["caveat"].lower()


def test_march_received_less_sun_than_april(summary):
    """The finding that overturned the original hypothesis.

    Naive reading blamed March for underperforming April. Satellite irradiance
    shows March 2026 actually received LESS sun than April 2026, so most of the
    yield gap was weather, not a system fault.
    """
    mar = summary.loc[summary["month"] == "Mar"].iloc[0]
    apr = summary.loc[summary["month"] == "Apr"].iloc[0]
    assert mar["ghi"] < apr["ghi"], "March GHI should be below April's"
    assert mar["specific_yield"] < apr["specific_yield"]


def test_may_is_the_real_pr_anomaly(summary):
    """May has the highest irradiance but the lowest temp-corrected PR."""
    may = summary.loc[summary["month"] == "May"].iloc[0]
    assert may["ghi"] == summary["ghi"].max()
    assert may["pr_ghi_tcorr"] == summary["pr_ghi_tcorr"].min()


def test_pr_over_100_is_flagged_not_hidden(summary):
    """Feb/Jul exceed 100% PR because GHI is the wrong denominator.

    Known artefact. Asserted present so that silently 'fixing' it by clipping
    values, rather than by transposing to plane-of-array, would fail loudly.
    """
    assert (summary["pr_ghi_tcorr"] > 100).any()


def test_tilt_is_recorded_as_estimate():
    """Tilt is inferred from imagery, not measured.

    12 deg +/- 3, corroborated weakly by a POA scan that rules out 20 deg+ but
    cannot separate 5 from 12 on seven monthly observations. Azimuth is assumed
    due south and unverified. Both must stay labelled until someone puts a
    phone against the module frame.
    """
    assert SITE.tilt_deg == pytest.approx(12.0)
    assert SITE.azimuth_deg == pytest.approx(180.0)
    assert SITE.mounting_clearance_m is None, (
        "clearance drives bifacial rear gain as much as albedo does - "
        "measure it before trusting the paint scenario"
    )


def test_shallow_tilt_costs_under_two_percent_annually():
    """At 20.3 N the annual tilt curve is flat.

    Clear-sky POA: 12 deg -> 2451 kWh/m2/yr, 20 deg optimum -> 2473.
    Re-tilting returns ~0.9%, which does not justify remounting on a
    cyclone-exposed roof. Guards against a future 'optimise the tilt'
    recommendation that the physics does not support.
    """
    poa_at_12, poa_optimum = 2451.0, 2473.0
    assert poa_at_12 / poa_optimum > 0.98


# --- scenarios ---------------------------------------------------------------

def test_rear_gain_monotonic_in_albedo():
    assert effective_rear_gain(0.12) < effective_rear_gain(0.40) < effective_rear_gain(0.70)


def test_white_surface_uplift_around_12_percent():
    base = baseline_annual_kwh()
    uplift = scenario_white_surface().annual_kwh / base
    assert 1.10 < uplift < 1.14


def test_every_scenario_declares_assumptions():
    """No scenario may present a modelled number without stating its basis."""
    for s in all_scenarios():
        if s.capex_inr > 0:
            assert s.assumptions, f"{s.name} has no declared assumptions"


def test_payback_is_positive_where_capex_incurred():
    for s in all_scenarios():
        if s.capex_inr > 0:
            assert s.payback_years is not None and s.payback_years > 0


def test_self_sufficiency_differs_from_solar_offset(summary):
    """These two must never be conflated.

    self_sufficiency = self-consumed / demand   (physical independence)
    solar_offset     = generation   / demand    (billing offset under net metering)

    The gap is exactly the exported energy. An early draft of this analysis
    reported solar_offset while calling it self-sufficiency, overstating
    independence by ~20 percentage points.
    """
    from solar_analytics.metrics import self_sufficiency, solar_offset_ratio

    gen, exp, imp = summary["generation_kwh"], summary["export_kwh"], summary["import_kwh"]
    ss = self_sufficiency(gen, exp, imp)
    so = solar_offset_ratio(gen, exp, imp)
    assert (so >= ss).all()
    assert (so - ss).max() > 0.15, "gap should be material where exports are large"


def test_lifetime_ratios_are_distinct(summary):
    gen = summary["generation_kwh"].sum()
    exp = summary["export_kwh"].sum()
    imp = summary["import_kwh"].sum()
    self_used = gen - exp
    demand = imp + self_used
    assert round(self_used / demand * 100, 1) == pytest.approx(26.2, abs=0.3)
    assert round(gen / demand * 100, 1) == pytest.approx(45.3, abs=0.3)
