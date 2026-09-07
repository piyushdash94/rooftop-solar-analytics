# Rooftop Solar Performance Analytics

[![CI](https://github.com/YOUR_USERNAME/rooftop-solar-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/rooftop-solar-analytics/actions)
[![Pages](https://img.shields.io/badge/dashboard-live-2B6350)](https://YOUR_USERNAME.github.io/rooftop-solar-analytics/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Turn a utility bill into a weather-normalised diagnostic.** No inverter API, no
paid data, no hardware — just TPCODL bills joined to free NASA POWER satellite
irradiance for a 3 kWp bifacial array in Bhubaneswar, India.

**[→ Live dashboard](https://YOUR_USERNAME.github.io/rooftop-solar-analytics/)**  ·  **[→ Full findings](FINDINGS.md)**

---

## What it found

Across seven months (Feb–Aug 2026, 206 days):

- **Sunlight explains 91% of month-to-month generation** (r = +0.96). Everything
  else — dust, heat, shading, outages — lives in the other 9%.
- After normalising for irradiance and cell temperature, **only two months
  under-delivered**: March (−9.6%) and May (−10.5%). Their raw yields differ by
  12%; their residuals are within a point. That gap is the whole reason to
  normalise.
- **The bill rose because demand doubled**, not because the array weakened. It's
  undersized for summer cooling load, not underperforming.
- The 45% "solar covers nearly half my bill" figure is **bill offset** under net
  metering. True direct self-sufficiency is **26%**. They are not the same number.

And in the 42-year record for the same coordinates:

- **The sky has dimmed ~10% since the 1980s** (−0.15 kWh/m²/day per decade,
  p < 0.0001). It's aerosols, not clouds: the clearness index is flat while the
  *clear-sky* baseline itself fell. This subtracts ~10% over the asset's life on
  top of ~12.5% panel degradation — a cost most solar financial models ignore.

A worked correction is part of the story: an early pass flagged March as a fault
on climatological grounds. Fetching the actual irradiance showed March 2026 got
*less* sun than April. The hypothesis was wrong, and the repo says so.

---

## The dashboard

`site/index.html` is a single self-contained page (Chart.js via CDN, no build
step) in four parts: what happened, what explains it, the 42-year record, and
what comes next. It reads its numbers inline, so it works offline and deploys to
GitHub Pages as-is.

## Reproduce

```bash
pip install -e ".[dev,pv]"     # pv extra pulls in pvlib for the POA model
solar-report                   # bills + weather -> outputs/summary.json
python scripts/generation_vs_weather.py   # rigorous POA + temperature residuals
pytest                         # 25 tests, runs offline from cached weather
```

Weather is cached at `data/raw/nasa_power_daily.csv` so tests and CI never hit
the network. Delete it to force a fresh NASA POWER pull.

## Add a new bill

Three edits, in order (see `CLAUDE.md` for the full procedure):

1. Append three cumulative meter readings to `data/meter_readings.csv`.
2. Append one period row to `data/bills.csv`.
3. Bump the counts in `tests/` and the `--end` default in `cli.py`, then
   `pytest`.

## Layout

```
data/            bills, meter readings, cached weather, 42-yr climate series
src/solar_analytics/   config · loaders · weather · metrics · scenarios · viz · cli
scripts/         POA residual model, tilt estimation
site/index.html  the dashboard (GitHub Pages root)
FINDINGS.md      full narrative report
CLAUDE.md        context for AI-assisted work on this repo
tests/           25 tests
```

## Method, honestly

- **n = 7.** Every correlation is descriptive, not inferential.
- **Performance ratio** uses horizontal irradiance; the panels are tilted, so it
  reads high in low-sun months. `scripts/generation_vs_weather.py` does the
  rigorous plane-of-array version with `pvlib`.
- **Tilt is an estimate** (~12°) — the largest single uncertainty here.
- **The temperature trend is flagged, not used**: NASA POWER shows maxima
  falling, Indian station data shows them rising. Treated as a reanalysis
  artefact.
- **One bill quirk**: July's net-metering annexure double-printed export
  (204.10 vs a true 102.05 kWh). The energy charge used the correct figure — a
  print defect, not a mis-bill. A test asserts it's still detected.

## Data sources

- **Bills** — TPCODL (TP Central Odisha Distribution Ltd), hand-transcribed,
  reconciled against cumulative meter readings.
- **Weather** — [NASA POWER](https://power.larc.nasa.gov/) daily point API. Free,
  no key, 1981–present.
- **Module** — Waaree Elite N-type BiN-01 bifacial datasheet.

## License

MIT. The data describes one household's meter; the method is the point.
