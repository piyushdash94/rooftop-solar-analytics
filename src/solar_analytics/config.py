"""Site configuration.

All values here are measured or documented facts about a specific installation.
Change these to point the pipeline at a different site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"


@dataclass(frozen=True)
class Tariff:
    """TPCODL Domestic LT tariff, effective 1 April 2025."""

    slabs: tuple[tuple[float, float], ...] = (
        (50, 2.90),      # first 50 units
        (150, 4.70),     # next 150 (51-200)
        (200, 5.70),     # next 200 (201-400)
        (float("inf"), 6.10),   # above 400
    )
    electricity_duty: float = 0.04
    meter_rent_monthly: float = 60.0

    @property
    def marginal_rate(self) -> float:
        """Rate applied to the next avoided unit, incl. duty.

        Used for savings estimates. Valid only while monthly consumption
        stays in the top slab, which it has for every observed month.
        """
        return self.slabs[-1][1] * (1 + self.electricity_duty)

    def cost(self, units: float) -> float:
        """Energy charge for a given number of units, incl. duty."""
        remaining, total = units, 0.0
        for width, rate in self.slabs:
            take = min(remaining, width)
            total += take * rate
            remaining -= take
            if remaining <= 0:
                break
        return total * (1 + self.electricity_duty)


@dataclass(frozen=True)
class Module:
    """Waaree Elite N-type BiN-01 series, framed dual-glass bifacial TOPCon."""

    model: str = "Waaree BiN-01 (555-585W)"
    temp_coeff_pmax: float = -0.0030   # %/degC, datasheet
    noct: float = 43.0                 # degC
    bifaciality: float = 0.80          # +/- 10
    efficiency_stc: float = 0.2207     # mid-range of series


@dataclass(frozen=True)
class Site:
    name: str = "Satya Vihar, Rasulgarh, Bhubaneswar"
    latitude: float = 20.312069
    longitude: float = 85.867744
    timezone: str = "Asia/Kolkata"

    kwp: float = 3.0
    commissioned: str = "2026-02-08"

    # Installed angle, taken as fixed throughout the analysis.
    tilt_deg: float = 12.0
    azimuth_deg: float = 180.0             # facing due south

    # Roof surface beneath the array. Drives bifacial rear gain.
    # Bare, often-damp dark concrete as of 2026-08.
    ground_albedo: float = 0.12

    module: Module = field(default_factory=Module)
    tariff: Tariff = field(default_factory=Tariff)


SITE = Site()
