# Rooftop solar in Bhubaneswar: seven months of bills, forty-two years of sky

A 3 kWp bifacial array on a fourth-floor terrace in Satya Vihar, Bhubaneswar,
commissioned 8 February 2026. Seven TPCODL billing periods joined to NASA POWER
daily satellite weather for the same dates, and set against the 1984–2025
irradiance record for the same coordinates.

**Compiled** 4 September 2026 · **Site** 20.30°N 85.82°E · **Data** 206 days of
bills, 15,341 days of weather

---

## The short version

The array is working. Sunlight explains 91% of its month-to-month output, and
after normalising for irradiance and cell temperature only two of seven months
fell meaningfully short of what the sky offered. The bill went up anyway,
because household demand doubled between February and June. The binding
constraint is system size, not system health.

The longer record adds a complication no warranty accounts for: the sky over
Bhubaneswar has dimmed about 10% since the mid-1980s, and the decline is in the
clear-sky baseline rather than in cloud cover — aerosols, not weather.

---

## What the seven months show

| Period | Days | Gen | Import | Export | Demand | Sun | Rain | Tmax | Residual |
|---|---|---|---|---|---|---|---|---|---|
| Feb | 22 | 321.9 | 279.0 | 161.7 | 439.1 | 5.25 | 5 | 32.7 | −3.3% |
| Mar | 31 | 389.6 | 487.0 | 183.2 | 693.3 | 5.12 | 19 | 36.8 | **−9.6%** |
| Apr | 30 | 436.3 | 719.6 | 192.4 | 963.6 | 5.58 | 75 | 40.5 | 0.0% |
| May | 31 | 436.5 | 598.4 | 192.6 | 842.3 | 6.16 | 59 | 39.3 | **−10.5%** |
| Jun | 30 | 364.7 | 794.9 | 112.0 | 1047.6 | 4.76 | 162 | 36.4 | 0.0% |
| Jul | 31 | 268.8 | 623.3 | 102.1 | 790.0 | 3.08 | 569 | 30.8 | +7.5% |
| Aug | 31 | 263.5 | 541.3 | 98.7 | 706.1 | 3.08 | 375 | 30.6 | +4.9% |
| **Total** | **206** | **2481.3** | **4043.5** | **1042.6** | **5482.1** | 4.72 | 1264 | 35.3 | |

Energy in kWh. Sun is mean daily horizontal irradiance in kWh/m²/day. Rain in mm
for the period. Tmax is the mean daily high in °C.

Every energy figure is a meter difference reconciled against cumulative readings
across all seven bills. They tie out exactly.

### Headline numbers

- **2,481 kWh** generated in 206 days
- **45%** of household demand offset on the bill, counting export credit
- **26%** used directly from the panels — the true self-sufficiency figure
- **₹15,500** estimated savings, about ₹2,210 a month
- **4.01** kWh/kWp/day average specific yield

The two percentage figures are not interchangeable. Bill offset counts every
generated unit, including those exported and credited back under net metering.
Self-sufficiency counts only what was consumed the moment it was made.
Conflating them overstates independence by nineteen points.

---

## Sunlight explains almost everything

Correlation between average daily irradiance and average daily generation across
the seven periods is **+0.96**; irradiance alone accounts for **91%** of the
variance.

```
generation per day = 2.09 × sunlight + 2.30     R² = 0.91, residual sd 0.78 kWh/day
```

Everything else — soiling, heat, shading, grid outages — lives in the remaining
9%. That residual is where the diagnostics are.

### Which features predict what

| Relationship | r |
|---|---|
| Demand → import | +0.98 |
| Sunlight → generation | +0.96 |
| Generation → export | +0.91 |
| Rain → generation | −0.91 |
| Sunlight → export | +0.84 |
| Cooling degree-days → import | +0.80 |
| Tmax → generation | +0.75 |
| Tmax → import | +0.43 |
| Cloud fraction → generation | −0.06 |

Cooling degree-days beat raw temperature for predicting import (+0.80 against
+0.43) because import follows air-conditioning runtime rather than heat itself.
Cloud fraction is useless at monthly resolution — it averages out. With n = 7
these are descriptive, not inferential.

---

## Two months genuinely under-delivered

After transposing horizontal irradiance to the plane of the array and correcting
for cell temperature, **March (−9.6%) and May (−10.5%)** are the only periods
that fell short of what the weather allowed.

Their raw yields differ by 12% — May looks far better — yet their residuals sit
within a point of each other. That is the entire argument for normalising.

**May is the more interesting case.** Most sunlight of any month (6.16
kWh/m²/day), worst conversion, hottest at 39.3 °C average daily high. The
module's −0.30%/°C coefficient explains part of it; peak pre-monsoon dust
plausibly explains the rest. June's residual returns to zero after the first
rains washed the panels — a soiling signature.

The two monsoon months run slightly positive, consistent with the Erbs
decomposition under-crediting diffuse light on a low-tilt plane under overcast
skies. Not a system effect.

### A correction worth recording

An earlier pass flagged March as an unexplained anomaly, reasoning from
climatology that March in Odisha is drier and sunnier than April. Fetching the
actual irradiance overturned that: **March 2026 received less sun than April**
(5.12 against 5.58 kWh/m²/day). Most of the March shortfall was weather. Only
the residual survived normalisation.

The lesson generalises. Do not infer irradiance from seasonal expectation when
a free satellite record exists for the exact coordinates and dates.

---

## The forty-two year record

Annual mean daily irradiance at these coordinates fell from **5.14** kWh/m²/day
in 1984–93 to **4.65** in 2016–25 — a decline of **0.15 per decade**
(p < 0.0001, r² = 0.77).

### It is not clouds

| Series | Trend per decade | p | r² |
|---|---|---|---|
| Measured irradiance | −0.151 | <0.0001 | 0.77 |
| Clear-sky irradiance | −0.179 | <0.0001 | 0.92 |
| Clearness index | −0.001 | 0.53 | 0.01 |

The clearness index — measured divided by clear-sky — barely moved, holding near
0.80 throughout. Had clouds been the cause, clearness would have dropped.
Instead the **clear-sky baseline itself fell, and faster than the measured
series**. The atmosphere has become less transparent on cloudless days.

This matches the published record. Studies using CERES and Indian ground
stations report persistent dimming across the subcontinent and specifically
attribute the eastern Indo-Gangetic Plain and eastern coastal decline to rising
aerosol loading. India has continued dimming while much of the world
transitioned to brightening after the 1990s.

### The clear seasons lost the most

| Season | 1984–93 | 2016–25 | Per decade | Change |
|---|---|---|---|---|
| Pre-monsoon (Mar–May) | 6.55 | 5.84 | −0.223 | −10.8% |
| Winter (Dec–Feb) | 4.77 | 4.13 | −0.195 | −13.4% |
| Post-monsoon (Oct–Nov) | 4.88 | 4.38 | −0.152 | −10.2% |
| Monsoon (Jun–Sep) | 4.49 | 4.27 | −0.063 | −4.9% |

All significant at p < 0.01. The monsoon was already dim and had less to lose;
the clear months carried the decline — precisely the months a rooftop array
earns most of its annual yield.

### Other trends

| Metric | 1984–93 | 2016–25 | Change |
|---|---|---|---|
| Rain days (>1 mm) | 128 | 157 | +23% |
| Annual rainfall | 1,470 mm | 1,555 mm | +6% |
| Relative humidity | 70.3% | 73.6% | +4.6% |
| Days above 40 °C | 55 | 35 | −36% |
| Days above 50 mm rain | 3.8 | 2.7 | −29% |

More frequent, lighter rain — rain days rose significantly (+7.7/decade,
p = 0.0003) while total rainfall barely changed.

### One number flagged, not reported

This dataset shows mean daily maxima **declining** 0.21 °C per decade and days
above 40 °C falling by more than a third. Indian station records show maxima
**rising** over the same period, and the dimming literature frames aerosols as
partly *masking* surface warming rather than reversing it.

Outright cooling is more likely a reanalysis artefact than a fact about
Bhubaneswar. The irradiance trend is well corroborated by independent work; the
temperature trend is not. Nothing in this analysis is built on it.

### What has not changed

- **Monsoon onset.** A rainfall-threshold proxy puts it near 18 June with no
  detectable trend across 42 years (p = 0.92).
- **Year-to-year variability.** The coefficient of variation of annual
  irradiance has held near 2.5% throughout. A bad year costs a few percent, not
  a fifth — which is why the residual method works.

---

## What to expect

### Next twelve months

Applying the fitted relationship to expected monthly irradiance:

**4,327 kWh** for September 2026 – August 2027, band **4,043–4,613**.
With a white surface under the array, approximately **4,850 kWh**.

September through January use regional seasonal irradiance rather than
measurement, so those five months carry more uncertainty than the band shows.
Refitting on twelve observed months will tighten it considerably.

### Over the asset's life

| Year | Age | Warranty floor | Projected irradiance | Combined | Expected |
|---|---|---|---|---|---|
| 2026 | 1 | 100% | 100% | 100% | 4,321 kWh |
| 2031 | 6 | 97.5% | 97.9% | 95.5% | 4,127 kWh |
| 2036 | 11 | 95.0% | 95.9% | 91.1% | 3,936 kWh |
| 2041 | 16 | 92.5% | 93.8% | 86.8% | 3,751 kWh |
| 2051 | 26 | 87.5% | 89.7% | 78.5% | 3,393 kWh |

Dimming subtracts roughly **10%** on top of the **12.5%** the panels lose to
age — about **−21% by 2051** rather than the −12.5% a warranty-only calculation
gives. Indian rooftop financial models that assume flat irradiance are
optimistic by around eight percentage points across an asset life.

**The honest limit:** aerosols are a policy variable, not a physical constant.
Europe and China both reversed their dimming within two decades of tightening
air-quality rules. This is the trend-continues case, not a forecast.

---

## Recommendations

1. **Paint the concrete under the array white.** These are bifacial modules over
   dark, often-wet concrete. The datasheet's rear-gain table runs 15–30%
   depending on ground reflectivity; the current surface likely yields about 5%.
   Estimated +12% energy for ₹8–12k, payback near three years. Best value
   available, and it lifts any future panels too.

2. **Photograph the array at 08:30 and 16:30 on a clear day.** The water tank
   and vent pipe sit close to the first row. Two photographs settle whether they
   cast a shadow; no amount of monthly billing data can.

3. **Measure tilt with a phone inclinometer.** Tilt is currently estimated at
   about 12°, the largest single uncertainty in every performance figure here.
   Measuring it would let performance ratio use plane-of-array irradiance
   properly and retire a standing caveat.

4. **Log outage start and end times for one month.** Roughly 2–3 hours lost
   every alternate week, during which a grid-tied inverter shuts down regardless
   of sunlight. Turns an anecdote into a kWh number.

5. **Check the inverter's DC input rating before expanding.** It decides whether
   4–4.5 kWp costs ₹47–60k or ₹100k. Expansion above 3 kW receives no further
   subsidy — PM Surya Ghar central assistance caps at ₹78,000 for 3 kW and
   above.

6. **Skip batteries.** Net metering already banks surplus at full retail value.
   A 5 kWh system costs about ₹5 lakh against ₹3,500–4,000 a year of avoided
   import.

---

## Method and limits

**Data sources.** TPCODL invoices, transcribed by hand and reconciled against
cumulative meter readings. NASA POWER daily point API for irradiance,
precipitation, temperature and humidity — free, no key, 1981 to present, roughly
two weeks behind real time.

**Performance ratio** uses horizontal irradiance in the denominator while the
panels are tilted, which inflates the figure in low-sun months. The residual
model in `scripts/generation_vs_weather.py` transposes to plane-of-array with
`pvlib` and is the rigorous version; the simple ratio is retained only for
month-to-month comparison.

**Sample size.** Seven monthly observations. Every correlation reported here is
descriptive. Nothing is fitted that requires more degrees of freedom than seven
rows can bear, and the system efficiency constant in the residual model is
fitted on the same seven periods — so only *relative* month-to-month health
survives, not absolute performance.

**Weather coverage.** The most recent billing period will always have missing
trailing days. Expected energy is scaled to full-period coverage and the day
count reported. Before this correction was added, August showed a +20% residual
that was purely an artefact of summing 27 days against a 31-day bill.

**Known bill quirk.** The July 2026 net-metering annexure printed export as
204.10 kWh, exactly double the meter's 102.05. The energy-charge slabs on that
bill sum to 521 units — the correct meter-derived figure. A print defect on the
summary page, not a mis-billing. A regression test asserts it is still detected.

## Open questions

1. **Separate heat from soiling in May.** Needs daily inverter output; monthly
   bills cannot distinguish two confounded effects.
2. **Quantify the tank shadow.** Two photographs, or a sun-path obstruction
   model using `pvlib.solarposition`.
3. **Measure tilt and azimuth.** Would retire the horizontal-irradiance caveat.
4. **Quantify outage loss.** One month of logged windows, valued against
   clear-sky output for those hours.
5. **Measure the bifacial rear gain.** Currently a datasheet estimate. Painting
   the surface would create a natural before-and-after experiment.
