# CLAUDE.md — rooftop-solar-analytics

Context for Claude Code. Read fully before editing anything.

## What this repo is

Weather-normalised performance analytics for a 3 kWp residential rooftop PV
array in Bhubaneswar, India, built from utility bills and free satellite
irradiance. It is a data-science portfolio project for Piyush; the array
belongs to a family member. The analysis is real, the numbers are audited,
and the repo has already caught one utility print defect and one of its own
modelling bugs. Preserve that culture: every number traceable, every caveat
visible, every estimate labelled.

## Layout and what each part owns

```
data/bills.csv             one row per billing period; hand-transcribed; authoritative
data/meter_readings.csv    cumulative meter readings; bills must reconcile to these
data/raw/nasa_power_daily.csv   cached NASA POWER daily weather; committed so tests run offline
src/solar_analytics/
  config.py     Site, Tariff, Module dataclasses — the only place facts live
  loaders.py    load bills/readings; validate_bills() finds reconciliation defects
  weather.py    NASAPower / OpenMeteoArchive providers; load_or_fetch() with cache
  metrics.py    yield, PR (GHI-based, flagged), Kt, SCR, self-sufficiency vs solar offset
  scenarios.py  albedo, cleaning, expansion — every Scenario carries `assumptions`
  viz.py        plotly figures; caveats enforced in subtitles
  cli.py        `solar-report` / `python -m solar_analytics.cli --scenarios`
scripts/
  generation_vs_weather.py   POA + temperature residual model (the rigorous one)
  estimate_tilt.py, optimal_tilt.py
tests/          25 tests; pytest runs offline from the cached weather
outputs/        generated html/csv/json — regenerate, don't hand-edit
site/index.html static dashboard for GitHub Pages (Chart.js, no build)
FINDINGS.md     consolidated narrative report — the human-readable output
```

## Site facts

Live in `src/solar_analytics/config.py`. Don't duplicate them elsewhere.
Key ones: 3.0 kWp, commissioned 2026-02-08, Waaree BiN-01 bifacial TOPCon
(γ = −0.30 %/°C, bifaciality 0.80), tilt ≈ 12° (estimate ±3), azimuth 180°
(assumed), ground albedo 0.12 (bare damp concrete), sanctioned load 7 kW,
TPCODL domestic LT slabs 2.90/4.70/5.70/6.10 + 4% duty. Owner-reported
outages ~5 h/month daytime; grid-tied inverter drops out on outage.

The bill field "Solar Capacity (KWp): 0.00" is a TPCODL data-entry gap.

## Data state as of 2026-09-04

Seven billing periods, 2026-02-08 → 2026-09-01, 206 days.
Cumulative: generation 2481.26, import 4043.47, export 1042.63 kWh.
All seven periods reconcile against `meter_readings.csv`.

Adding a bill means three edits, in this order:
1. Append the three new cumulative readings to `data/meter_readings.csv`
   (import, export, generation — same date, same order as existing rows).
2. Append one row to `data/bills.csv`. `export_kwh` is the meter diff;
   `billed_export_printed_kwh` is whatever the annexure says, even if wrong.
3. Bump `--end` default in `cli.py`, the `PERIODS` list in
   `scripts/generation_vs_weather.py`, and the counts in
   `tests/test_metrics.py` / `tests/test_validation.py`. Run `pytest`.
Then refresh `data/raw/nasa_power_daily.csv` via `weather.load_or_fetch`
(delete the cache first) and regenerate `outputs/`.

## Two things that were wrong and are now fixed — don't reintroduce

**July 2026 export.** The Net Meter Billing annexure prints 204.10 kWh;
the meter says 102.05. An early README called this a ₹650 under-billing.
It is not: the energy-charge slabs on the bill front sum to 521 units, the
correct figure. It is a print defect on the summary page only.
`test_detects_july_export_doubling` still asserts detection. Keep the
detection; keep the corrected interpretation.

**Weather coverage.** NASA POWER lags ~2 weeks. The most recent period will
have missing trailing days. `rollup()` in `generation_vs_weather.py` now
scales `e_eff_total` by `days / weather_days` and reports both. Before that
fix August showed +20% residual (real: ~+5%). Any new aggregation over
daily weather must handle partial coverage the same way.

## Metric definitions — do not drift

| name | formula | note |
|---|---|---|
| specific_yield | gen / kWp / days | kWh/kWp/day |
| pr_ghi | yield / GHI | GHI is horizontal; tilt inflates winter PR. Name keeps `_ghi_` so the bias stays visible. |
| pr_ghi_tcorr | pr_ghi / (1 + γ(T_cell − 25)) | T_cell = T_air + 25, a proxy |
| kt | GHI_allsky / GHI_clearsky | pure weather; NaN where clear-sky missing |
| scr | (gen − export) / gen | load-match |
| self_sufficiency | (gen − export) / demand | physical independence, **26.2%** lifetime |
| solar_offset | gen / demand | net-metering bill offset, **45.3%** lifetime |
| residual_pct | (actual − expected)/expected, expected = E_eff·kWp·η_median | POA-based; η fitted on the same periods, so only relative health survives |

`self_sufficiency` and `solar_offset` are not the same and a test guards it.
Public prose must say which one it means.

`FINDINGS.md` is the prose companion to `site/index.html`; they share the same
numbers and must be updated together. If you change a figure in one, change it
in the other, or they will drift.

## Findings that hold (n = 7)

- Generation tracks the sun until monsoon onset (2nd week June); Jul/Aug GHI
  is half of May and generation halves with it.
- After POA + temperature normalisation, **March (−9.6%) and May (−10.5%)**
  are the only under-delivering months. May: most sun, worst conversion,
  hottest. June residual returns to ~0 after first rains — soiling signature.
- Demand, not generation, drove the bill: demand doubled Feb→Jun with
  cooling load. The array is undersized for summer, not underperforming.
- SCR rose 50% → 69% as AC pulled load into daylight.
- Monsoon months run slightly positive residual — plausibly the Erbs
  decomposition under-credits diffuse on a 12° plane. Not a system effect.

## Long-record climate context (1984-2025, NASA POWER, same coordinates)

Fetched and analysed separately; the annual series is in
`data/bbsr_annual_climate_1984_2025.csv`.

- Irradiance fell 5.14 -> 4.65 kWh/m2/day between the first and last decade,
  -0.151/decade, p<0.0001, r2=0.77.
- **It is aerosols, not clouds.** Clearness index flat (0.80, p=0.53) while
  clear-sky irradiance fell *faster* than measured (-0.179/decade, r2=0.92).
  Corroborated by published CERES/station work on eastern-coastal India.
- Dry seasons lost most: pre-monsoon -10.8%, winter -13.4%, monsoon only -4.9%.
- Monsoon onset shows no trend (p=0.92). Annual CV steady near 2.5%.
- Over 25 years, dimming costs ~10% on top of ~12.5% panel degradation.
- **Do not build on the temperature trend.** POWER shows Tmax *falling*
  0.21 C/decade; Indian station records show it rising. Treat as reanalysis
  artefact. Flagged as such in FINDINGS.md and the dashboard.

## Open questions

1. Separate heat from soiling in May — needs daily inverter output.
2. Tank-and-pipe shadow on row 1 — two photos at ~08:30/16:30 on a clear
   day, or a sun-path obstruction model.
3. Measured tilt and azimuth — a phone inclinometer. Would let PR use POA
   properly and retire the `_ghi_` caveat.
4. Outage loss — one month of logged outage windows.
5. Bifacial rear-gain if concrete is painted white — currently a datasheet
   estimate (+12%), unmeasured.

## Scenarios (all modelled)

Baseline 4,321 kWh/yr. White surface +12% (₹10k, ~3.1 yr). Expansion to
4–4.5 kWp is unsubsidised (PM Surya Ghar CFA caps at 3 kW) and hinges on
inverter DC headroom: ₹47–60k without swap, ₹100k with. Batteries are not
recommended; net metering makes them uneconomic here.

## Conventions

- Python ≥3.10. `pip install -e ".[dev,pv]"`. `pvlib` needed for scripts/.
- kWh everywhere. ₹ with slab-aware costing via `Tariff.cost()`.
- Billing periods are closed intervals. ISO dates.
- Every figure gets a one-line source/caveat caption.
- Round for display only.
- Don't fetch weather in tests. Don't commit outputs by hand.
- `ruff` line-length 100; `scripts/` may exceed it in embedded HTML.

## Site (dashboard) direction

Light stone background, marigold for sun, monsoon blue for rain, deep green
for PV. One typeface. Left-aligned, hairline rules, generous whitespace. The
hero is the sun-and-rain strip: daily GHI as a filled area, rain as bars
pointing down, monthly generation as dots on a right axis. No dark-mode SaaS
cards, no uppercase eyebrow labels, no numbered section markers.
