# CLAUDE.md — rooftop-solar-analytics

Context for Claude Code. Read fully before editing anything.

## What this repo is

A published article, plus the code that produces it: weather-normalised analytics for a
3 kWp bifacial rooftop array in Bhubaneswar, India, built from utility bills and free
satellite weather. It is Piyush's data-science portfolio project; the array belongs to his
family. Culture to preserve: every number traceable to data, every caveat visible, every
estimate labelled as one. The repo has already caught a utility print defect and several of
its own modelling mistakes, and the article says so.

## How the pieces fit

```
data/                          inputs only; bills.csv is hand-transcribed and authoritative
src/solar_analytics/
  config.py     Site, Tariff, Module dataclasses. The only place site facts live.
  loaders.py    bills, meter readings, occupancy; validate_bills() finds reconciliation defects
  physics.py    daily weather -> sunlight on the panels -> heat derate -> E_eff; period rollup
  story.py      compute(): EVERY number the article uses, as a JSON-able dict with `facts`
  figures.py    every chart, defined once in Plotly; FIGURES maps id -> (builder, caption)
  weather.py    refresh data/raw/nasa_power_daily.csv (python -m solar_analytics.weather START END)
article/article.md             the prose. [[fact]] placeholders, {{fig:id}} / {{figs:a,b}} markers,
                               {{ref:key}} citations (keys in article/references.json, all verified)
scripts/build_article.py       renders site/index.html, article/blog.md, article/figures/*.png,
                               article/rooftop-solar-article.pdf and FINDINGS.md
app/streamlit_app.py           interactive companion; same story + figures, plus what-if sliders
tests/                         31 tests; test_story.py pins the article's conclusions
```

Never hand-edit `site/index.html`, `article/blog.md`, `FINDINGS.md` or the PNGs/PDF. Edit
`article/article.md`, `story.py` or `figures.py`, then run `python scripts/build_article.py`.
A number in prose must come from `facts`; add it to `story.py` rather than typing it.

## Site facts

In `config.py`. 3.0 kWp, commissioned 2026-02-08, Waaree BiN-01 bifacial TOPCon
(γ = −0.30 %/°C, NOCT 43 °C, bifaciality 0.80). **Panels are fixed at 12°, facing south.
Treat that as given; the article does not discuss tilt** (the residual pattern is the same
anywhere from 8° to 25°, which is why). Ground albedo 0.12 (dark concrete). TPCODL domestic LT
slabs 2.90 / 4.70 / 5.70 / 6.10 + 4% duty; top-slab value of a unit ₹6.34.

## Data state as of 2026-10-06 (through the September bill)

Eight billing periods, 2026-02-08 → 2026-10-01, 236 days. Cumulative: generation 2797.03,
import 4559.42, export 1187.12 kWh. All periods reconcile against `meter_readings.csv`.

Weather files: `raw/nasa_power_daily.csv` (billed days, complete through 2026-10-01, refreshed
2026-10-06), `raw/nasa_power_daily_2016_2025.csv` (ten weather-years),
`raw/nasa_power_monthly_1984_2025.csv` and `bbsr_annual_climate_1984_2025.csv` (long record).
NASA revises recent months: between two downloads June 2026 changed by ~2%. Re-download the
latest months before trusting them, and keep that caveat in the article.

## Models

1. **Sunlight line** — gen/day = a·GHI + b (a ≈ 2.04, b ≈ 2.56, R² 0.91). Best leave-one-out
   forecaster (mean miss ~5%). September out-of-sample: 327 predicted vs 316 metered (−3.4%).
   Feb under- and May over-predicted because of panel geometry (+7.1% / −2.5% vs flat ground)
   and heat (5.0% / 7.2% loss) — the line cannot see either.
2. **Physics** — E = POA(12°, Erbs daily split) × f_temp × kWp × η. Cell temperature follows
   NOCT: T_cell = T_air + (NOCT−20)/800 × G, G the energy-weighted mean irradiance of the day
   (π²·POA/(8·day length)). η = median of the eight periods (≈0.93), so residuals are
   *relative* health only. Used for residuals and for the typical-year forecast run over
   2016–2025 weather. Its leave-one-out miss (~6.7%) is worse than the line's; it is kept for
   diagnosis and winter geometry, not forecasting accuracy. Say so.

Feature selection was done by leave-one-out, not intuition: adding temperature (7.2%) or rain
(6.8%) to the sunlight line made it worse. Do not add features without re-running that
comparison (`story.compute()["models"]`).

## Findings that hold (n = 8)

- Sunlight explains 91% of month-to-month generation.
- Residuals: March ≈ −8% and May ≈ −9% are the only shortfalls. March was mostly weather (it
  got less sun than April). May: heat or dust; bills cannot separate them. Jul/Aug ≈ +7–10%,
  likely the daily diffuse split under heavy overcast, a method limit.
- July–August 2026 were 23–28% darker than normal, darker than any year 2016–2025. Do not
  project from 2026 weather.
- Typical year ≈ 4,580 kWh (Oct 2026 – Sep 2027); 2016–2025 weather gives 4,300–4,700, CV 2.7%.
  The simple line gives ~4,400 because it has never seen a winter sun angle.
- White roof: +12% light (≈550 kWh). Heat is two bounds: model says extra rear light warms cells
  ~2.6 °C (April); cooler surroundings take back ~1.3 °C (Mahmood 2023, measured on MONOFACIAL
  panels). Net ≈ +1.3 °C, heat cost 16–37 kWh, net gain 513–534 kWh (article uses 513). The
  warming is a MODEL result: no cited source measures bifacial cells over dark vs white roof.
  Never write "field tests show the panels run warmer".
- Demand rose ~75% per day Feb→Jun (20→35 kWh/day). Bills rose because of demand.
- May: nobody home ~7.5 days (owner: "a week or more", ~200 fewer imported units; 7.5 days
  reproduces 191). Folded into demand as an assumption (per occupied day); not a separate
  section of the article. Generation is never adjusted, and the system ran normally.
- Bill offset 45% = self-sufficiency 26% + export credits 19%; shown as a donut chart.
- Long record: GHI −0.15 kWh/m²/day per decade (p < 0.0001), clear-sky −0.18, clearness index
  flat (p = 0.53): at this grid cell the decline is clear-sky (aerosol). Nationally the
  literature finds clouds dominant (Jadhav 2024), with this region the most aerosol-affected.
  Do not write "aerosols, not clouds" without that scope. The record's falling Tmax
  contradicts IMD station data (Kumar 2023); flagged, never used.
- Lifetime: datasheet warranty 99% after year 1, 87.4% after year 30 (~0.4%/yr), over 30 years.

## Metric definitions — do not drift

| name | formula | note |
|---|---|---|
| specific yield | gen / kWp / days | kWh/kWp/day |
| scr (self-consumption) | (gen − export) / gen | share of solar used at home |
| self-sufficiency | (gen − export) / demand | 26% lifetime |
| bill offset | gen / demand | 45% lifetime; counts export credit |
| residual | actual / expected − 1 | physics model; relative only |
| cooling-degree-days | mean of max(0, T_mean − 25 °C) per day | |

Self-sufficiency and bill offset are different numbers; prose must say which.

## Adding a bill

1. Append three cumulative readings to `data/meter_readings.csv` and one row to `data/bills.csv`
   (`export_kwh` is the meter diff; `billed_export_printed_kwh` is what the annexure says).
   Add an `occupancy.csv` row if the house was empty.
2. Refresh `data/raw/nasa_power_daily.csv` with `python -m solar_analytics.weather` (it lags ~2 weeks; `physics.period_rollup` scales
   partial coverage, keep that).
3. Bump counts in `tests/test_validation.py`; `pytest`.
4. `python scripts/build_article.py`; reread the article. If `tests/test_story.py` fails, a
   conclusion changed and the prose needs rewriting, not the test.

## Things that were wrong and are fixed — don't reintroduce

- **July export print defect** (204.10 printed vs 102.05 metered). Energy charge used the right
  figure; it is not an under-billing. `test_detects_july_export_doubling` keeps detecting it.
- **Weather coverage.** Summing only available days faked a +20% August residual; scale by
  days / weather days.
- **Fixed +25 °C cell temperature** over-penalised cloudy months; replaced by the NOCT form.
- **Projecting from 2026 weather and guessed winter sunlight** gave 4,324 kWh; replaced by the
  ten-weather-year run.
- **Incomplete weather cache** (Aug 28/31, Sep 29/30 days) made the September test look like
  −1.6%; with complete, revised data it is −3.4%.
- **Lifetime ageing at 0.5%/yr over 25 years** was not the datasheet; it says ~0.4%/yr over 30.
- **Unquoted "Source Sans 3"** in a CSS font list is invalid (the "3"); keep it quoted in `FONT`.

## Article and site direction

Writing: plain, first-person plural, hunch → test → result. Short direct sentences; no
em-dash asides or stock phrases. Every chart has a one-line caption saying what it shows.
Every claim from outside this data carries a {{ref:...}} citation. No to-do lists or
suggestions to take photos or measurements in the article. GitHub user: piyushdash94.
Design: light theme only (white page, no dark mode, also in Streamlit), marigold for sun, monsoon blue for rain, deep green for PV, rust for
shortfalls; one typeface (Source Sans 3); hairline rules; colours as CSS tokens; chart colours mapped to the same tokens at runtime. No uppercase eyebrows, no numbered
section markers, no dark-SaaS cards.

## Simplification (v0.2.0)

The pre-article pipeline (metrics.py, scenarios.py, viz.py, cli.py and their tests) was removed;
nothing the article uses depended on it, and `story.compute()` output was verified identical
before and after. Do not resurrect parallel metric code: add numbers to `story.py`.

## Conventions

Python ≥ 3.10. `pip install -e ".[dev,app,article]"`. kWh everywhere; ₹ via `Tariff.cost()`.
Billing periods are closed intervals, ISO dates. Round for display only. Tests never fetch
weather. Static PNGs need kaleido and a Chromium (`BROWSER_PATH`).
