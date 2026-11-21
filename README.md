# Satya Vihar rooftop solar

[![CI](https://github.com/piyushdash94/rooftop-solar-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/piyushdash94/rooftop-solar-analytics/actions)
[![Article](https://img.shields.io/badge/article-live-2B6350)](https://piyushdash94.github.io/rooftop-solar-analytics/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A 3 kW bifacial solar system went up on a family roof in Bhubaneswar, India, in February 2026.
It has no app and no data logger. This project reads it from three free sources: the monthly
electricity bills, the utility's daily meter data, and NASA satellite weather.

**[Read the article](https://piyushdash94.github.io/rooftop-solar-analytics/)** ·
[full technical version (archived)](https://piyushdash94.github.io/rooftop-solar-analytics/archive/) ·
[same roof, twelve cities](https://piyushdash94.github.io/rooftop-solar-analytics/cities/)

## What it shows (to 20 November 2026)

- **Made 3,181 kWh** in its first nine bills and took **₹19,926** off them. The sun paid for
  46% of what the house used: 26% used directly, 20% as export credits.
- **Sunlight explains 93%** of month-to-month output. A physics model (sunlight on the tilted
  panels, a heat loss, one fitted efficiency) forecasts it well: October came in at 384 kWh
  against 389 forecast before the bill, and over 26 days of daily solar-meter readings the
  model's total was within 1%.
- **A typical year should give about 4,540 kWh** (4,280–4,670 across ten years of weather).
- **Bills rose because the house used more**, mostly air conditioning: use is flat at about
  19 kWh a day until the daily mean temperature passes ~25.5 °C, then rises 2.2 kWh per degree.
- **Only May fell clearly short** (−9% against the weather). Heat or dust; a test registered
  before winter will check.
- **The bills print the wrong reading dates.** The daily portal data matches every bill to
  0.01 kWh only on corrected dates (March covered 29 days, not 31).

## How the repo works

The article is a hand-written page, published as it is. Only its numbers and charts change
when new data arrives, and they all come from one file:

```
data/*.csv  ──►  scripts/update_data.py  ──►  site/data.json  ──►  site/index.html (charts + numbers)
```

Every number in the page that can change carries a `data-k="..."` key into `data.json`, and
its current value as default text, so the page reads correctly even before the data loads.

### When a new bill or new portal data arrives

1. Add the data:
   - `data/bills.csv` and `data/meter_readings.csv`, on the corrected dates (each bill covers
     one calendar month; keep the printed dates in `printed_start` / `printed_end`);
   - `data/daily_meter.csv`, the portal's daily import and export spreadsheet;
   - `data/daily_generation.csv`, daily solar-meter readings (from the portal chart).
2. Append new days to the weather: `python -m solar_analytics.weather <start> <end>` writes a
   fresh file; keep earlier rows as they are so the frozen winter test does not shift.
3. `python scripts/update_data.py`, then `pytest`.
4. Read the page. If a conclusion changed, edit that sentence in `site/index.html`.

`tests/test_site.py` fails if `data.json` is older than the bills or if the page binds a
number the data does not have.

## Layout

```
site/index.html          the article (hand-written) · site/data.json (generated)
site/archive/            the long technical article, frozen on 18 Nov 2026
site/cities/             the twelve-cities research page, frozen
data/                    bills, meter readings, daily portal data, daily generation, weather
src/solar_analytics/     analysis: loaders, physics model, story.compute() (all numbers),
                         cities, weather download; figures.py for the Streamlit app
scripts/update_data.py   the monthly rebuild
app/streamlit_app.py     interactive explorer (streamlit run app/streamlit_app.py)
article/archive/         the archived article as Markdown, PDF and figures
tests/                   39 tests: bill reconciliation, model conclusions, page/data in step
```

## Run it

```bash
pip install -e ".[dev,app]"
python scripts/update_data.py
pytest
cd site && python -m http.server   # open http://localhost:8000
```

## Sources

- **Bills and meter data:** TP Central Odisha Distribution Ltd (TPCODL).
- **Weather:** [NASA POWER](https://power.larc.nasa.gov/) daily and hourly API.
- **Module:** Waaree Elite N-type BiN-01 bifacial datasheet.
- **Literature:** cited in the archived article (`article/archive/references.json`).

## License

MIT. The data describes one household's meter; the method is the point.
