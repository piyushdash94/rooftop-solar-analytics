"""Validation tests.

The headline test here is `test_detects_july_export_doubling`. This dataset
contains a genuine utility billing error; the pipeline is expected to find it.
If that test ever fails, either the data was silently corrected upstream or the
validator regressed -- both are worth knowing about.
"""

from __future__ import annotations

import pandas as pd
import pytest

from solar_analytics.loaders import (
    assert_cumulative_integrity,
    derive_from_meters,
    load_bills,
    load_meter_readings,
    validate_bills,
)

# Final cumulative meter readings at 2026-08-01. Independent ground truth.
EXPECTED_CUMULATIVE = {
    "generation_kwh": 2481.26,
    "import_kwh": 4043.47,
    "export_kwh": 1042.63,
}


@pytest.fixture(scope="module")
def bills() -> pd.DataFrame:
    return load_bills()


@pytest.fixture(scope="module")
def readings() -> pd.DataFrame:
    return load_meter_readings()


def test_bills_load_seven_periods(bills):
    assert len(bills) == 7
    assert bills["days"].sum() == 206


def test_cumulative_totals_match_meters(bills):
    """Per-period values must sum to the final cumulative readings."""
    totals = assert_cumulative_integrity(bills)
    for key, expected in EXPECTED_CUMULATIVE.items():
        assert totals[key] == pytest.approx(expected, abs=0.05), (
            f"{key}: bills sum to {totals[key]}, meter reads {expected}"
        )


def test_meter_deltas_are_monotonic(readings):
    """Cumulative meters can only increase."""
    for _, grp in readings.groupby("parameter"):
        vals = grp.sort_values("reading_date")["reading_kwh"]
        assert (vals.diff().dropna() >= 0).all()


def test_derived_deltas_match_bills(bills, readings):
    """Meter-derived per-period values must equal what bills.csv records."""
    derived = derive_from_meters(readings)
    col_for = {"generation": "generation_kwh", "import": "import_kwh", "export": "export_kwh"}
    for _, d in derived.iterrows():
        billed = bills.loc[bills["period_end"] == d["period_end"], col_for[d["parameter"]]]
        assert not billed.empty, f"no bill row for period ending {d['period_end']}"
        assert billed.iloc[0] == pytest.approx(d["delta_kwh"], abs=0.05)


def test_detects_july_export_doubling(bills):
    """The known defect: July's printed export is exactly 2x the meter delta.

    Meter annexure : 841.93 -> 943.98 = 102.05 kWh
    Bill summary   : 204.10 kWh
    Effect         : net billable 419.21 instead of 521.26 kWh (~Rs 622 under-billed)
    """
    issues = validate_bills(bills)
    assert len(issues) == 1, f"expected exactly one defect, got {len(issues)}"

    issue = issues[0]
    assert issue.period_start == "2026-07-02"
    assert issue.field == "export_kwh"
    assert issue.expected == pytest.approx(102.05, abs=0.01)
    assert issue.found == pytest.approx(204.10, abs=0.01)
    assert issue.found / issue.expected == pytest.approx(2.0, abs=0.01)
    assert "2x" in issue.message


def test_all_other_periods_reconcile(bills):
    """Only July is defective; the other five cycles are clean."""
    issues = validate_bills(bills)
    flagged = {i.period_start for i in issues}
    assert flagged == {"2026-07-02"}


def test_under_billing_amount(bills):
    """Quantify the financial impact of the defect."""
    issue = validate_bills(bills)[0]
    over_credited_units = issue.found - issue.expected
    marginal_rate = 6.10 * 1.04
    assert over_credited_units == pytest.approx(102.05, abs=0.01)
    assert over_credited_units * marginal_rate == pytest.approx(647.4, abs=5)
