"""Weather-normalised performance analytics for residential rooftop PV."""

__version__ = "0.1.0"

from . import scenarios, viz
from .config import SITE, Module, Site, Tariff
from .loaders import ValidationIssue, load_bills, load_meter_readings, validate_bills
from .metrics import PR_TILT_CAVEAT, self_sufficiency, solar_offset_ratio, summarise_periods
from .weather import NASAPower, OpenMeteoArchive, load_or_fetch

__all__ = [
    "SITE", "Site", "Tariff", "Module",
    "load_bills", "load_meter_readings", "validate_bills", "ValidationIssue",
    "summarise_periods", "PR_TILT_CAVEAT", "self_sufficiency", "solar_offset_ratio",
    "NASAPower", "OpenMeteoArchive", "load_or_fetch",
    "scenarios", "viz",
]
