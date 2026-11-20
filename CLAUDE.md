# CLAUDE.md — rooftop-solar-analytics

Context for Claude Code. Read fully before editing anything.

## What this repo is

A published article, plus the code that produces it: weather-normalised analytics for a
3 kWp bifacial rooftop array in Bhubaneswar, India, built from utility bills and free
satellite weather. It is Piyush's data-science portfolio project; the array belongs to his
family. Culture to preserve: every number traceable to data, every caveat visible, every
estimate labelled as one. The repo has already caught a utility print defect and several of
its own modelling mistakes, and the article says so.

## How the pieces fit (since 20 Nov 2026)

The article is HAND-WRITTEN and published as it is: `site/index.html`. Only `site/data.json`
is generated, by `scripts/update_data.py`, from the CSVs via `story.compute()`. The page's
charts and every changeable number (`data-k="path.in.json"`, with the current value as default
text) read from it. There is no templating, no PDF/blog build, no article.md any more.

```
data/                          bills.csv (hand-transcribed, CORRECTED dates), meter_readings.csv,
                               daily_meter.csv (portal daily import/export, exact),
                               daily_generation.csv (portal solar-meter chart, read ±0.2 kWh),
                               occupancy.csv, raw/ NASA POWER weather
src/solar_analytics/
  config.py     Site, Tariff, Module dataclasses. The only place site facts live.
  loaders.py    bills, meters, occupancy, daily portal data; validate_bills(), reconcile_daily()
  physics.py    daily weather -> sunlight on the panels -> heat derate -> E_eff; period rollup
  story.py      compute(): every number (facts dict); experiment; daily checks
  figures.py    Plotly figures, used only by the Streamlit app now
  cities.py     the frozen twelve-cities analysis (tests still run it)
  weather.py    NASA POWER download (daily; --daytime for sun-weighted air temperature)
scripts/update_data.py         the ONLY monthly rebuild: writes site/data.json
site/index.html                the article (edit prose by hand)
site/archive/index.html        the long technical article, frozen 18 Nov 2026 (do not edit)
site/cities/index.html         twelve-cities page, frozen (do not edit)
article/archive/               archived article as blog.md, PDF, figures, references.json
app/streamlit_app.py           interactive explorer
tests/                         39 tests; test_site.py keeps page and data.json in step
```

Prose numbers that will change belong in data.json with a data-k binding; add the field in
update_data.py. Historical facts (e.g. "March covered 29 days") may be typed.

## Site facts

In `config.py`. 3.0 kWp, commissioned 2026-02-08, Waaree BiN-01 bifacial TOPCon
(γ = −0.30 %/°C, NOCT 43 °C, bifaciality 0.80). **Panels are modelled at 12°, facing south.**
The article has one short tilt paragraph (owner asked, 20 Nov): data fits 10–15° best, and the
conclusions hold from 8° to 20°. Do not change the model's tilt without a measurement. Ground albedo 0.12 (dark concrete). TPCODL domestic LT
slabs 2.90 / 4.70 / 5.70 / 6.10 + 4% duty; top-slab value of a unit ₹6.34.

## Daily generation (added 2026-11-20)

`data/daily_generation.csv`: 21 Oct – 19 Nov from the portal's solar-meter (AS0210962) chart
screenshot, read on gridline-calibrated crops; the same method reproduced exact import to 0.05
kWh. Results: physics model (η frozen) within 1% over 26 days, R² 0.90, clear-day miss ~6%; the
sunlight line under-forecasts November ~6% (winter geometry). Export attenuation (0.54) is
household self-use rising with generation (0.37 kWh per kWh), not satellite error. Real daily
demand matched the modelled split (r 0.95). 18–19 Nov low output = cyclone (IMD watch 15 Nov).
Tilt test (5–30°): Nov daily fits best at 10–12°; ≥20° over-forecasts winter 4–7%; typical-year
forecast changes ≤1.5% for 12→20°. Owner thinks tilt may be >12°: unmeasured; keep 12°.

## Data state as of 2026-11-18 (through the October bill)

Nine billing periods, 2026-02-08 → 2026-10-31, 266 days (CORRECTED dates, see below). Cumulative: generation 3181.41,
import 5163.79, export 1362.35 kWh. All periods reconcile against `meter_readings.csv`.

**Billing dates are corrected (2026-11-18).** The bills print reading dates that are wrong. Daily
portal data (`daily_meter.csv`, 263 days, 12–13 Oct missing) reconciles to every complete period
within 0.01 kWh only on these periods: Feb = 8 Feb–2 Mar (23 d), Mar = 3–31 Mar (29 d, not 31),
then each calendar month (printed dates are one day late). `bills.csv` keeps `printed_start` /
`printed_end`; `meter_readings.csv` uses the corrected dates. `loaders.reconcile_daily` and
`test_daily_portal_reconciles_on_corrected_dates` prove it. Portal dates are right: daily export
correlates best with same-day GHI. Assumed: the generation meter is read on the same visit (fit
improves on corrected dates: R² 0.91→0.93, physics LOO 4.7→3.8%). A new bill: shift its printed
dates the same way and confirm against portal data before adding it.

Weather files: `raw/nasa_power_daily.csv` (billed days, complete through 2026-11-01, refreshed
2026-11-07), `raw/nasa_power_daily_2016_2025.csv` (ten weather-years),
`raw/nasa_power_monthly_1984_2025.csv` and `bbsr_annual_climate_1984_2025.csv` (long record).
NASA revises recent months: June 2026 changed ~2%, and on the 2026-11-07 refresh July rose
4.8% and August 8.7%. Re-download the
latest months before trusting them, and keep that caveat in the article.

## Models

1. **Sunlight line** — gen/day = a·GHI + b (a ≈ 2.17, b ≈ 1.92, R² 0.93), LOO mean miss 5.1%.
   Out-of-sample: the published typical-October forecast (PUBLISHED_OCT_FORECAST, 389) vs
   384 metered (−1.1%); the line fitted Feb–Sep with October weather: 379 (+1.5%).
   Feb under- (5%) and May over-predicted (15%): geometry and heat explain the opposite signs;
   May's extra is its real shortfall.
2. **Physics** — E = POA(12°, Erbs daily split) × f_temp × kWp × η. Cell temperature follows
   NOCT: T_cell = T_air + (NOCT−20)/800 × G, G the energy-weighted mean irradiance of the day
   (π²·POA/(8·day length)). η = median of the nine periods (≈0.919), so residuals are
   *relative* health only. Used for residuals and for the typical-year forecast run over
   2016–2025 weather. Its leave-one-out miss (3.8%) is the best of the set (it was 6.7% before
   NASA revised Jul/Aug, 4.7% before the date correction).

Feature selection was done by leave-one-out, not intuition. On the corrected dates adding
temperature HELPS (4.3% vs 5.1%); rain still hurts (7.3%). On the printed dates temperature looked
useless; the article tells that as a lesson. Do not add features without re-running that
comparison (`story.compute()["models"]`).

## Findings that hold (n = 9)

- Sunlight explains 93% of month-to-month generation.
- Residuals: May ≈ −9% is the only clear shortfall; Feb −5.7% (partly the part-day 8 Feb);
  Oct −4.7%; March +1.2%. March's old −7% was the 31-vs-29-day error. Never call March a shortfall.
  May: heat or dust; bills cannot separate them. Jul +4%, Aug −1% after NASA's revision. The old +7–10% and its "diffuse split"
  explanation were provisional-data artefacts; the article says so. Do not bring them back.
- July–August 2026 were ~19–21% darker than normal, darker than any year 2016–2025. Do not
  project from 2026 weather.
- Typical year ≈ 4,544 kWh (Nov 2026 – Oct 2027); 2016–2025 weather gives 4,280–4,670. The line
  gives ~4,375.
- White roof: +12% light (≈540 kWh). Heat is two bounds: model says extra rear light warms cells
  ~2.6 °C (April); cooler surroundings take back ~1.3 °C (Mahmood 2023, measured on MONOFACIAL
  panels). Net ≈ +1.3 °C, heat cost 16–36 kWh, net gain 509–530 kWh (article uses 509). The
  warming is a MODEL result: no cited source measures bifacial cells over dark vs white roof.
  Never write "field tests show the panels run warmer".
- Demand rose ~75% per day Feb→Jun (20→35 kWh/day). Bills rose because of demand.
- Temperature input is NASA's 24-h MEAN AIR temperature (not panel, not daytime). NOCT converts
  air to cell. Sun-weighted daytime air (`raw/nasa_power_daytemp_2026.csv`, from hourly data via
  `weather.py --daytime`) is ~6 °C above the mean Feb–Apr, 5 May, 2 monsoon; heat loss Apr
  7.0→8.8%. Sensitivity only (`daytime_air`): residuals move ≤0.9 pt, May −8.5%. Model keeps the
  24-h mean to match the ten-year files; the article admits heat losses read low. Don't swap the
  model input without also redoing 2016–2025 and amending the pre-registration.
- Daily corroboration (`daily_split`): within-month, modelled daily gen explains 44% of export
  swings (even split 0%, GHI 43%); only 1/262 days export > modelled gen; slope 0.54 (attenuation
  from single-day satellite error and/or sunny-day self-use, inseparable). Daily data cannot
  referee physics vs GHI (differences are seasonal).
- Daily demand (portal import + modelled solar used at home): flat 19 kWh/day until daily mean
  ~25.5 °C, then +2.2 kWh/°C (hinge, R² 0.42, sd ±6, no weekday effect). Confirms CDD base 25.
- May: house "kinda empty" (owner) 16–23 May (8 days, EVENTS["away"]); 156 kWh below the hinge
  line; import never below 7.5 kWh/day, so not fully empty. occupancy.csv = 8 days. The old
  7.5-day/~190 kWh calibration is retired. Generation is never adjusted.
- Bill offset 46% = self-sufficiency 26% + export credits 20%; shown as a donut chart.
- Guests (owner-confirmed): 30 Sep – 8 Oct (9 days, straddles two bills), +86 kWh vs the hinge
  line (~10 kWh/day). October's other days still ~3 kWh/day above the line: unexplained.
  Unexplained dip 10–11 July (−23 kWh). Likely long daytime outage: 2 Sep only; 2–3 h cuts are
  invisible in daily totals.
- Long record: GHI −0.15 kWh/m²/day per decade (p < 0.0001), clear-sky −0.18, clearness index
  flat (p = 0.53): at this grid cell the decline is clear-sky (aerosol). Nationally the
  literature finds clouds dominant (Jadhav 2024), with this region the most aerosol-affected.
  Do not write "aerosols, not clouds" without that scope. The record's falling Tmax
  contradicts IMD station data (Kumar 2023); flagged, never used.
- Lifetime: datasheet warranty 99% after year 1, 87.4% after year 30 (~0.4%/yr), over 30 years.

## Pre-registered experiment (registered 2026-11-08, AMENDED 2026-11-18) — do not edit either rule

Dust vs heat vs sky as the driver of residuals. Discovery set = first nine months (EXP_N), frozen.
Proxies are sunlight-weighted per period: dust = days since rain ≥ 5 mm, cell temperature,
clearness index. ORIGINAL (old, wrong periods; kept verbatim in PREREG_ORIGINAL): η 0.9132;
ρ dust −0.63, heat −0.66, sky −0.73; Dec–Jan forecasts dust −7.2, sky −2.2, heat +5.0; verdict
< −4.7 dust, > +1.4 heat, else sky. AMENDED before any winter bill, because the daily data showed
the periods were wrong: on corrected periods ρ dust −0.23 (p .28), heat −0.29 (.22), sky −0.55
(.066); none survives Holm. Forecasts dust −0.8, sky −2.6, heat +3.2. Dust and sky are within
noise (gap 1.8, ±3.0), so the amended rule only tests heat: Dec–Jan mean residual vs ETA_FROZEN
0.9186 above +1.2 → heat, else "not heat". A Nov→Feb fall ≥ 5 points still counts for dust.
Misclassification ~26% each way; the article says so. Score BOTH rules from `experiment["outcome"]`
(`frozen` and `frozen_original`); `experiment["verdict"]` appears when Dec and Jan are in. Never
refit. `test_preregistered_winter_test_is_frozen` guards both. Report the verdicts whichever way.

## Research page: same roof, twelve cities (2026-11-08)

`cities.py`: the Bhubaneswar array (12° S, albedo 0.12, η = story.ETA_FROZEN, 0.9186) run through NASA POWER 2016–2025 for
12 city centres (`data/cities.csv`, `data/raw/cities/`). Hypothesis written first: monsoon cloud
decides yield more than heat. Tests: (a) sun spread ≥ 2× heat spread — supported (7.4% vs 0.6%);
(b) Jun–Sep > 50% of between-city variance in panel sunlight — rejected (15%; winter 43%, pre 30%);
(c) yield ranks more with monsoon sun than heat loss — rejected (+0.47 vs +0.64; dry months +0.89).
Decomposition of ln GHI into latitude / haze (clear-sky ÷ TOA) / cloud (all-sky ÷ clear-sky):
annual 28/42/30%, dry months 43/39/18%. Ahmedabad 5,230 top, Kolkata 4,311 last, Bhubaneswar 10th
(within 0.1% of the article's 4,544). Tilt = latitude keeps the ranking (ρ 0.99). "Winter air
clarity separates cities" is a NEW hypothesis from the data, not a tested result; say so.
Settled-dust soiling is not modelled. No money on this page, kWh only.

## Metric definitions — do not drift

| name | formula | note |
|---|---|---|
| specific yield | gen / kWp / days | kWh/kWp/day |
| scr (self-consumption) | (gen − export) / gen | share of solar used at home |
| self-sufficiency | (gen − export) / demand | 26% lifetime |
| bill offset | gen / demand | 46% lifetime; counts export credit |
| residual | actual / expected − 1 | physics model; relative only |
| cooling-degree-days | mean of max(0, T_mean − 25 °C) per day | |

Self-sufficiency and bill offset are different numbers; prose must say which.

## Adding a bill or new daily data

1. Download the month's daily import/export from the TPCODL portal and append to
   `data/daily_meter.csv`; add daily solar-meter readings to `data/daily_generation.csv`.
   Append three cumulative readings to `data/meter_readings.csv` and one row to `data/bills.csv`
   on the CORRECTED dates (the calendar month; printed dates go in `printed_start`/`printed_end`),
   then confirm with `reconcile_daily` that the new period matches to ~0.01 kWh.
   Add an `occupancy.csv` row if the house was empty.
2. Append new days to `data/raw/nasa_power_daily.csv` (append-only: never rewrite earlier rows,
   or the frozen experiment shifts). NASA lags ~2 weeks and revises; note big revisions.
3. Bump counts in `tests/test_validation.py`; `python scripts/update_data.py`; `pytest`.
4. Read site/index.html in a browser. If a conclusion changed, edit that prose by hand.

## Things that were wrong and are fixed — don't reintroduce

- **July export print defect** (204.10 printed vs 102.05 metered). Energy charge used the right
  figure; it is not an under-billing. `test_detects_july_export_doubling` keeps detecting it.
- **Weather coverage.** Summing only available days faked a +20% August residual; scale by
  days / weather days.
- **Fixed +25 °C cell temperature** over-penalised cloudy months; replaced by the NOCT form.
- **Projecting from 2026 weather and guessed winter sunlight** gave 4,324 kWh; replaced by the
  ten-weather-year run.
- **Incomplete weather cache** (Aug 28/31, Sep 29/30 days) made the September test look like
  −1.6%; with complete data it was −3.4%, and after NASA's Jul/Aug revision about −1%.
- **"Diffuse split" explanation for Jul/Aug +7–10%**: the cause was provisional NASA data.
- **Printed billing dates** made March 31 days (really 29) and Feb 22 (really 23): a fake March
  shortfall, temperature looking useless, and an inflated dust/heat/sky correlation.
- **Lifetime ageing at 0.5%/yr over 25 years** was not the datasheet; it says ~0.4%/yr over 30.
- **Unquoted "Source Sans 3"** in a CSS font list is invalid (the "3"); keep it quoted in `FONT`.

## Article and site direction

The current article is the SIMPLE version for a general reader: plain words, five charts
(per-day monthly bars + forecast, sunlight scatter, daily meter vs model, where the electricity
goes, demand vs temperature), a month table, a short "what we got wrong" list. Technical depth
lives in the archive. Writing: plain, first-person plural, hunch → test → result. Short direct sentences; no
em-dash asides or stock phrases. Every chart has a one-line caption saying what it shows.
Every claim from outside this data links its source in the footer. No to-do lists or
suggestions to take photos or measurements in the article. GitHub user: piyushdash94.
Design: light theme only (white page, no dark mode, also in Streamlit), marigold for sun, monsoon blue for rain, deep green for PV, rust for
shortfalls; one typeface (Source Sans 3); hairline rules; colours as CSS tokens; chart colours mapped to the same tokens at runtime. No uppercase eyebrows, no numbered
section markers, no dark-SaaS cards.

## Simplification (v0.2.0)

The pre-article pipeline (metrics.py, scenarios.py, viz.py, cli.py and their tests) was removed;
nothing the article uses depended on it, and `story.compute()` output was verified identical
before and after. Do not resurrect parallel metric code: add numbers to `story.py`.

## Conventions

Python ≥ 3.10. `pip install -e ".[dev,app]"`. kWh everywhere; ₹ via `Tariff.cost()`.
Billing periods are closed intervals, ISO dates. Round for display only. Tests never fetch
weather.
