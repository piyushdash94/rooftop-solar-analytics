"""Pins the twelve-cities research page: its pre-stated tests and the conclusions it draws."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from solar_analytics.cities import HYPOTHESIS, compute_cities  # noqa: E402


@pytest.fixture(scope="module")
def R():
    return compute_cities()


def test_twelve_complete_cities(R):
    assert len(R["cities"]) == 12
    assert all(len(v) == 10 for v in R["years"].values())


def test_bhubaneswar_matches_the_bill_calibrated_article(R):
    """A fresh download run through the same model must land on the article's typical year."""
    assert float(R["facts"]["art_diff"]) < 1.0


def test_hypothesis_written_before_results():
    assert set(HYPOTHESIS) == {"statement", "a", "b", "c"}


def test_verdicts(R):
    """One of three pre-stated tests passes: heat is small, but the monsoon is not the separator."""
    assert R["verdict"] == {"a": True, "b": False, "c": False}
    assert R["tests"]["ratio"] > 2
    assert R["season_share"]["winter"] > R["season_share"]["monsoon"]


def test_shares_add_up(R):
    for d in (R["season_share"], R["decomp"], R["decomp_dry"]):
        assert sum(d.values()) == pytest.approx(1.0, abs=1e-9)


def test_haze_beats_cloud_in_dry_months(R):
    assert R["decomp_dry"]["haze"] > R["decomp_dry"]["cloud"]


def test_ranking_survives_latitude_tilt(R):
    assert R["tests"]["rho_tilt"] > 0.95
