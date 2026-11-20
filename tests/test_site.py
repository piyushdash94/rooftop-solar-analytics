"""The published article is hand-written (site/index.html); only site/data.json is rebuilt.

These tests make sure the two stay in step: every number the page binds exists in the data,
the data matches the bills, and the frozen archive pages are still there.
"""

import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "site" / "index.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def data():
    return json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))


def _get(d, path):
    for k in path.split("."):
        d = d[int(k)] if isinstance(d, list) else d[k]
    return d


def test_every_bound_number_exists_in_data(data):
    keys = set(re.findall(r'data-k="([\w.]+)"', HTML))
    assert keys, "the page binds no numbers"
    for k in keys:
        assert _get(data, k) is not None, k


def test_data_is_current_with_the_bills(data):
    """Run scripts/update_data.py after adding a bill; this fails until you do."""
    bills = pd.read_csv(ROOT / "data" / "bills.csv")
    assert len(data["monthly"]) == len(bills)
    assert data["latest"]["gen"] == pytest.approx(bills.generation_kwh.iloc[-1], abs=0.06)
    assert data["latest"]["start"] == bills.period_start.iloc[-1]


def test_daily_generation_is_used(data):
    gen = pd.read_csv(ROOT / "data" / "daily_generation.csv")
    metered = [x for x in data["daily"] if x["gen"] is not None]
    assert len(metered) == len(gen)
    assert data["check"]["n"] >= 20 and abs(data["check"]["total_err"]) < 5


def test_charts_and_theme():
    assert HTML.count('class="plot') == 5
    assert "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/4.1.1/plotly-cartesian.min.js" in HTML
    assert "prefers-color-scheme: dark" not in HTML
    assert '<meta name="color-scheme" content="light">' in HTML


def test_archive_pages_are_frozen_and_linked():
    for p in ("site/archive/index.html", "site/cities/index.html"):
        assert "Archived snapshot" in (ROOT / p).read_text(encoding="utf-8")
    assert 'href="archive/"' in HTML and 'href="cities/"' in HTML
