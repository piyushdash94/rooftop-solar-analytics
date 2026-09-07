"""Command-line entrypoint: python -m solar_analytics"""

from __future__ import annotations

import argparse

from .loaders import assert_cumulative_integrity, load_bills, load_meter_readings, validate_bills
from .metrics import summarise_periods
from .scenarios import all_scenarios
from .weather import load_or_fetch


def main() -> int:
    p = argparse.ArgumentParser(description="Rooftop solar performance report")
    p.add_argument("--start", default="2026-02-08")
    p.add_argument("--end", default="2026-09-01")
    p.add_argument("--scenarios", action="store_true", help="include intervention scenarios")
    args = p.parse_args()

    bills = load_bills()
    readings = load_meter_readings()

    print("\n=== DATA VALIDATION ===")
    issues = validate_bills(bills, readings)
    if issues:
        for i in issues:
            print(f"  FLAG  {i}")
    else:
        print("  All periods reconcile against meter readings.")
    print(f"  Cumulative totals: {assert_cumulative_integrity(bills)}")

    weather = load_or_fetch(args.start, args.end)
    summary = summarise_periods(bills, weather)

    print(f"\n=== PERFORMANCE SUMMARY (n={len(summary)}) ===")
    cols = ["month", "ghi", "kt", "specific_yield", "pr_ghi", "pr_ghi_tcorr",
            "scr", "self_sufficiency", "solar_offset", "rain_days"]
    print(summary[cols].to_string(index=False))
    print(f"\n  NOTE: {summary.attrs['caveat']}")

    if args.scenarios:
        print("\n=== SCENARIOS (all modelled estimates) ===")
        for s in all_scenarios():
            pb = f"{s.payback_years} yr" if s.payback_years else "-"
            print(f"  {s.name:<42} {s.annual_kwh:>7,.0f} kWh  "
                  f"capex Rs{s.capex_inr:>8,.0f}  payback {pb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
