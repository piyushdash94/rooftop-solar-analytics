"""Load and validate utility billing data.

The validation here is not ceremonial. Real utility bills contain real errors:
this dataset has one (see `validate_bills`), and the pipeline is expected to
find it rather than silently propagate it into every downstream metric.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import DATA_DIR

TOLERANCE_KWH = 0.05  # meter readings are reported to 2dp


@dataclass
class ValidationIssue:
    period_start: str
    field: str
    expected: float
    found: float
    message: str

    @property
    def delta(self) -> float:
        return self.found - self.expected

    def __str__(self) -> str:
        return (
            f"[{self.period_start}] {self.field}: "
            f"printed {self.found:.2f}, meter-derived {self.expected:.2f} "
            f"(delta {self.delta:+.2f}) - {self.message}"
        )


def load_bills(path: Path | str | None = None) -> pd.DataFrame:
    """Load billing periods.

    Returns one row per billing cycle with generation, import and export in kWh.
    `export_kwh` is the meter-derived truth; `billed_export_printed_kwh` is what
    the utility printed on the Net Meter Billing summary. They should agree.
    """
    path = Path(path) if path else DATA_DIR / "bills.csv"
    df = pd.read_csv(path, parse_dates=["period_start", "period_end"])
    df["month"] = df["period_start"].dt.strftime("%b")
    return df


def load_meter_readings(path: Path | str | None = None) -> pd.DataFrame:
    """Load cumulative meter readings (the ground truth)."""
    path = Path(path) if path else DATA_DIR / "meter_readings.csv"
    return pd.read_csv(path, parse_dates=["reading_date"])


def derive_from_meters(readings: pd.DataFrame) -> pd.DataFrame:
    """Recompute per-period consumption from cumulative meter deltas.

    This is the independent check on the utility's arithmetic.
    """
    out = []
    for param, grp in readings.groupby("parameter"):
        grp = grp.sort_values("reading_date").reset_index(drop=True)
        deltas = grp["reading_kwh"].diff().iloc[1:]
        out.append(
            pd.DataFrame(
                {
                    # Meter reading dates are period END dates. The reading on
                    # date D closes the cycle ending on D, so join on period_end.
                    "period_end": grp["reading_date"].iloc[1:].values,
                    "prev_reading_date": grp["reading_date"].iloc[:-1].values,
                    "parameter": param,
                    "delta_kwh": deltas.values,
                }
            )
        )
    return pd.concat(out, ignore_index=True)


def validate_bills(
    bills: pd.DataFrame, readings: pd.DataFrame | None = None
) -> list[ValidationIssue]:
    """Cross-check printed bill figures against meter-derived values.

    Known defect in this dataset
    ----------------------------
    The July 2026 cycle (02.07-01.08) prints an export of 204.10 kWh on the
    Net Meter Billing summary. The meter annexure shows 841.93 -> 943.98,
    i.e. 102.05 kWh - exactly half. Net billable was computed as 419.21 kWh
    instead of 521.26 kWh, under-billing the consumer by roughly Rs 622.

    All five other cycles reconcile exactly.
    """
    issues: list[ValidationIssue] = []

    for _, row in bills.iterrows():
        printed = row.get("billed_export_printed_kwh")
        actual = row["export_kwh"]
        if pd.isna(printed):
            continue
        if abs(printed - actual) > TOLERANCE_KWH:
            ratio = printed / actual if actual else float("inf")
            hint = (
                "printed value is exactly 2x the meter delta"
                if abs(ratio - 2.0) < 0.01
                else "printed value disagrees with meter delta"
            )
            issues.append(
                ValidationIssue(
                    period_start=row["period_start"].date().isoformat(),
                    field="export_kwh",
                    expected=actual,
                    found=printed,
                    message=hint,
                )
            )

    if readings is not None:
        derived = derive_from_meters(readings)
        col_for = {"generation": "generation_kwh", "import": "import_kwh", "export": "export_kwh"}
        for _, d in derived.iterrows():
            col = col_for.get(d["parameter"])
            if col is None:
                continue
            match = bills[bills["period_end"] == d["period_end"]]
            if match.empty:
                continue
            billed = match.iloc[0][col]
            if abs(billed - d["delta_kwh"]) > TOLERANCE_KWH:
                issues.append(
                    ValidationIssue(
                        period_start=match.iloc[0]["period_start"].date().isoformat(),
                        field=col,
                        expected=float(d["delta_kwh"]),
                        found=float(billed),
                        message="bills.csv disagrees with cumulative meter reading",
                    )
                )

    return issues


def assert_cumulative_integrity(bills: pd.DataFrame) -> dict[str, float]:
    """Sum per-period values; these must equal the final cumulative readings.

    Expected at 2026-08-01: generation 2217.76, import 3502.22, export 943.98.
    """
    return {
        "generation_kwh": round(bills["generation_kwh"].sum(), 2),
        "import_kwh": round(bills["import_kwh"].sum(), 2),
        "export_kwh": round(bills["export_kwh"].sum(), 2),
    }
