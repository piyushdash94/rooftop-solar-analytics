"""The article's claims, as tests.

If new data changes one of these conclusions, the test should fail so the prose
gets rewritten rather than silently going stale.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pvlib")

from solar_analytics.config import SITE  # noqa: E402
from solar_analytics.loaders import load_bills  # noqa: E402
from solar_analytics.story import compute  # noqa: E402


@pytest.fixture(scope="module")
def B() -> dict:
    return compute()


def test_totals_match_bills(B):
    bills = load_bills()
    gen = sum(m["gen"] for m in B["monthly"])
    assert gen == pytest.approx(bills["generation_kwh"].sum(), abs=0.05)
    assert len(B["monthly"]) == len(bills)


def test_panels_fixed_at_installed_angle():
    """The article takes the angle as given and never discusses tilt."""
    assert (SITE.tilt_deg, SITE.azimuth_deg) == (12.0, 180.0)


def test_self_sufficiency_is_not_bill_offset(B):
    """The two percentages the article separates: 26% used directly, 45% offset on the bill."""
    f = B["facts"]
    assert (f["ss_life"], f["offset_life"]) == ("26", "45")
    assert int(f["ss_life"]) + int(f["credit_share"]) == int(f["offset_life"])


def test_march_got_less_sun_than_april(B):
    """Why March's low output was mostly weather."""
    mo = {m["month"]: m for m in B["monthly"]}
    assert mo["Mar"]["ghi"] < mo["Apr"]["ghi"]


def test_sunlight_explains_most_variation(B):
    assert B["fit"]["r2"] > 0.85


def test_september_out_of_sample_close(B):
    sep = B["monthly"][-1]
    assert abs(sep["gen"] / B["fit"]["sep_pred"] - 1) < 0.05


def test_extra_features_do_not_beat_sunlight(B):
    m = {x["name"]: x["mae"] for x in B["models"]}
    assert m["Sunlight only"] <= m["Sunlight + temperature"]
    assert m["Sunlight only"] <= m["Sunlight + rain"]
    assert m["Rain only"] > m["Sunlight only"]


def test_march_and_may_are_the_shortfalls(B):
    worst = sorted(B["monthly"], key=lambda m: m["resid"])[:2]
    assert {w["month"] for w in worst} == {"Mar", "May"}
    assert all(w["resid"] < -5 for w in worst)


def test_monsoon_2026_darker_than_any_recent_year(B):
    for n in B["normal"]:
        if n["month"] in ("Jul", "Aug"):
            assert n["ghi_2026"] < n["ghi_min"]


def test_typical_year_inside_weather_range(B):
    years = [b["kwh"] for b in B["backtest"]]
    total = sum(f["mean"] for f in B["forecast"])
    assert min(years) <= total <= max(years)
    assert len(B["forecast"]) == 12


def test_dimming_is_aerosol_not_cloud(B):
    t = B["trends"]
    assert t["ghi"]["slope_decade"] < 0 and t["ghi"]["p"] < 0.001
    assert t["clr"]["slope_decade"] < t["ghi"]["slope_decade"]
    assert t["kt"]["p"] > 0.05


def test_every_fact_used_by_article_exists(B):
    import re
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "article" / "article.md"
    text = path.read_text(encoding="utf-8")
    used = set(re.findall(r"\[\[(\w+)\]\]", text))
    assert used <= set(B["facts"]), used - set(B["facts"])


def test_citations_resolve_and_every_source_is_cited():
    import json
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    text = (root / "article" / "article.md").read_text(encoding="utf-8")
    refs = json.loads((root / "article" / "references.json").read_text(encoding="utf-8"))
    cited = {k for m in re.findall(r"\{\{ref:([a-z0-9_,]+)\}\}", text) for k in m.split(",")}
    assert cited <= set(refs), cited - set(refs)
    assert set(refs) <= cited, f"listed but never cited: {set(refs) - cited}"
    assert all(r["url"].startswith("https://") for r in refs.values())


def test_white_roof_heat_bounds(B):
    """Model output, not a measured claim.

    Rear-light heating outweighs the measured surroundings cooling, and the net gain sits
    between the two bounds and below the pure light gain.
    """
    f = B["facts"]
    assert float(f["peak_rise_net"]) > 0
    kwh = {k: int(f[k].replace(",", "")) for k in ("paint_kwh", "paint_kwh_cool", "light_kwh")}
    assert kwh["paint_kwh"] <= kwh["paint_kwh_cool"] < kwh["light_kwh"]
    for h in B["heat"]:
        assert h["loss_white"] > h["loss_now"]
    base = sum(f["mean"] for f in B["forecast"])
    net = sum(p["white"] for p in B["paint"]) - base
    assert 0 < net < base * 0.12
