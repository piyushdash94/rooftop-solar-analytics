# Reading a rooftop against the sky

*Eight months of electricity bills, ten years of satellite weather, and what they say about one bifacial solar array in Bhubaneswar.*

By Piyush Dash · October 2026

In February 2026 a 3 kWp array of bifacial panels went up on the roof of our family home in Satya Vihar, Bhubaneswar. Eight months later we had a folder of bills and a few questions that sounded simple. Is the system working as it should? Why did the bills go up when the panels were new? What will it make next year?

**The data.** Eight monthly TPCODL bills, [[first]] to [[last]], each listing cumulative readings from the solar generation meter and the import–export net meter; a month's units are the difference between two consecutive readings.

We had no inverter app logging output minute by minute, only those monthly numbers. This piece is about how far they can go once you join them to the weather, and about the hunches we had to test, drop or keep along the way.

<div class="glance" markdown="1">

- **[[gen_total]] kWh** generated over [[n_days]] days, [[first]] to [[last]].
- **[[fit_r2_pct]]%** of the month-to-month variation is explained by sunlight alone.
- **[[sep_err]]%** miss on a month the model had never seen. Its typical miss across all months is about [[loo_mae]]%.
- **[[fc_total]] kWh** expected in a typical weather year. The last ten years of weather range from [[yr_min]] to [[yr_max]].
- **₹[[saved_total]]** saved on bills so far.
- **+[[paint_kwh]] kWh** a year, modelled, if the roof under the panels is painted white.

</div>

## Hunch one: the sun does nearly all the work

The first hunch was the obvious one: more sun, more power. To test it we needed the sunlight that fell on this roof on each billed day. Bills do not carry that, so we took it from NASA's POWER service {{ref:nasa_power}}. For any latitude and longitude, POWER returns a daily estimate of the solar energy reaching a horizontal surface at the ground, in kilowatt-hours per square metre per day (the parameter called ALLSKY_SFC_SW_DWN). The estimate comes from satellite measurements of clouds and the atmosphere, processed by NASA's CERES programme on a grid of 1° by 1°, about 110 km on a side. Air temperature and rainfall come from NASA's MERRA-2 reanalysis on a finer grid. We requested daily values for [[lat]]° N, [[lon]]° E through the POWER web API; it is free, needs no key, and runs a few days behind real time.

{{fig:daily}}

The shape of the year is plain. Through spring the roof received 5 to 6 kWh of sunlight per square metre each day. Rain builds from the second week of June, and by July the daily average was close to 3.

{{fig:calendar}}

Each billing month then becomes two numbers. **Generation per day** is the month's metered generation divided by the number of days in the billing period. **Sunlight per day** is the average of NASA's daily values over exactly the same dates. For the first bill, that is [[feb_gen]] kWh over [[feb_days]] days, or [[feb_gen_day]] kWh a day, against an average of [[feb_ghi]] kWh/m² of sunlight a day. Dividing by days matters because billing periods run from 22 to 31 days.

Plotted month by month, the two move together almost in a straight line.

{{figs:gen,scatter}}

    generation per day = [[fit_a]] × sunlight + [[fit_c]]
    (generation in kWh/day; sunlight in kWh per m² per day)

Sunlight accounts for [[fit_r2_pct]]% of the variation between months (R² = [[fit_r2]]). Everything else, including dust, heat, shading and power cuts, has to fit in the remaining [[unexpl]]%.

## Choosing what to leave out

A line through eight points is easy to draw and easy to fool yourself with. With so few months, every extra variable is another way to fit noise. So instead of asking which features sounded reasonable, we asked which ones helped predict a month the model had not seen.

The test is called leave-one-out. Fit the model on seven months, predict the eighth, and repeat for every month. The average miss is the number to beat.

{{fig:models}}

Sunlight alone missed by [[mae_sun]]% on average. Adding temperature made it worse, at [[mae_sun_t]]%, and so did adding rain, at [[mae_sun_rain]]%. Rain on its own ([[mae_rain]]%) and temperature on its own ([[mae_temp]]%) were far worse. Rain matters, but its effect is already inside the sunlight number, because rainy days are dull days. Adding it a second time only gives the fit another way to chase noise.

We kept two models. The simple sunlight line is the better forecaster at this resolution. The physics model described below misses by [[mae_phys]]% on average, so we do not keep it for its forecasting record. We keep it because it can do two things the line cannot: judge the panels' health month by month, and forecast winter months the line has never seen.

Every analysis is a list of decisions about what to ignore. Here is ours.

| Feature | Decision | Why |
|---|---|---|
| Sunlight on the ground | Kept | Explains [[fit_r2_pct]]% on its own. |
| Panel angle | Simplified | Fixed at the installed [[tilt]]°, facing south. Used to convert horizontal sunlight into sunlight on the panels. |
| Direct and diffuse light | Simplified | Split with a standard daily formula, because there is no hourly data. |
| Panel temperature | Kept, physics model only | The datasheet gives a 0.30% loss per °C, and panels run hotter in strong sun. Monthly data is too coarse to see it clearly, but physics says it is there. |
| Rain | Left out | Its effect is already in sunlight. Adding it worsened predictions. |
| Cloud cover | Left out | Carries the same information as sunlight. |
| Humidity and wind | Left out | No measurable signal at monthly resolution. |
| Dust and soiling | Not modelled | Appears in the residuals instead. |
| Power cuts | Not modelled | No logs. The family estimates about 5 hours a month in daylight. |
| Ground reflectivity | Fixed at [[albedo]] | Dark concrete. Changed only in the white-paint scenario. |
| Panel ageing | Ignored for 8 months | About 0.4% a year. Included in the lifetime outlook. |
| Who is at home | Demand only | The house stood empty for about a week in May. That changes what the house used, never what the panels made. |

## Did the line see the future?

The cleanest test of a model is a month that did not exist when it was built. We fitted the line on February to August and waited for September's bill. Given September's measured sunlight, it predicted [[sep_pred]] kWh. The meter recorded [[sep_act]], a miss of [[sep_err]]%, well inside the line's usual scatter of about ±[[sep_band]] kWh for a month that long.

{{fig:loo}}

One good result can be luck, so the leave-one-out chart is the fairer picture. A typical month lands within about [[loo_mae]]%. The two worst misses point in opposite directions: February was under-predicted by [[loo_feb]]% and May over-predicted by [[loo_may]]%.

**Why February was under-predicted.** The line only knows the sunlight that reaches flat ground. The panels are not flat, and they are not at air temperature. In February the sun stays low in the southern sky, so panels tilted [[tilt]]° towards it catch it more squarely: they received [[feb_geo_abs]]% more sunlight than flat ground. In May the sun is almost overhead at noon, and the same tilt costs a little: [[may_geo_abs]]% less. February was also cooler (a mean of [[feb_tmean]] °C against [[may_tmean]] °C in May), so the cells lost [[feb_heat]]% of their output to heat against [[may_heat]]% in May. Put together, each unit of ground-level sunlight was worth about [[feb_vs_may]]% more electricity in February than in May. That is the size of both misses. The chart below follows each month from sunlight to kilowatt-hours and shows where the two months part company.

{{fig:chain}}

## The physics model, input by input

To judge the panels themselves we needed an estimate of what the weather allowed each month, built from physics rather than fitted to the bills. It runs one day at a time and adds the days up for each billing period.

    expected energy = sunlight on the panels × heat derate × 3 kWp × η

**Step 1: sunlight on the panels.** NASA gives sunlight on flat ground. For each day we first compute how much sunlight would arrive at the top of the atmosphere at this latitude on that date; the ratio of the two, the clearness index, says how clear the day was. A standard formula from Erbs, Klein and Duffie {{ref:erbs}} turns the clearness index into the share of light that was diffuse, scattered across the sky, rather than direct from the sun. Direct light is then projected onto panels tilted [[tilt]]° to the south, using the sun's position through the day {{ref:pvlib,duffie}}. Diffuse light is counted from the part of the sky the tilted panels can see {{ref:liujordan}}, and a small amount of light is added for reflection off the roof.

**Step 2: heat.** These modules lose 0.30% of their output for every degree their cells run above 25 °C {{ref:waaree}}. Cell temperature is estimated with the datasheet's nominal operating cell temperature (NOCT) of [[noct]] °C, the temperature the cells reach under 800 W/m² of sunlight with the air at 20 °C {{ref:waaree,duffie}}. Cells warm above the air in proportion to the sunlight on them, so the panels run hot in clear spring weather and stay near air temperature under monsoon cloud.

**Step 3: one fitted number.** One kilowatt-hour of sunlight per square metre on the panels would give about one kilowatt-hour per kilowatt-peak at test conditions. Real systems lose some of that in the inverter, the wiring, light reflected off the glass, and dust. We let the data set that single factor, η, as the median of the eight months' metered generation divided by the energy the first two steps predicted. It comes out at [[eta]].

| Input | Value | Where it comes from |
|---|---|---|
| Daily sunlight on the ground | kWh/m² per day | NASA POWER {{ref:nasa_power}} |
| Daily mean air temperature | °C | NASA POWER, MERRA-2 {{ref:nasa_power}} |
| Site location | [[lat]]° N, [[lon]]° E | The roof's coordinates |
| Panel tilt and direction | [[tilt]]°, facing south | The installed angle, taken as fixed |
| Ground reflectivity | [[albedo]] | Assumed for dark, often damp concrete |
| Power loss with temperature | [[gamma]]% per °C | Module datasheet {{ref:waaree}} |
| NOCT | [[noct]] °C | Module datasheet {{ref:waaree}} |
| Array rating | 3 kWp | The installation |
| System efficiency, η | [[eta]] | Fitted: median of metered ÷ predicted over the eight months |

Because η is fitted on the same months the model judges, the model can only compare months with one another. It cannot say how good the system is in absolute terms.

## Two months that fell short

{{fig:resid}}

March ([[r_mar]]%) and May ([[r_may]]%) are the only real shortfalls.

March is the story of a hunch that was wrong. Early on we flagged it as suspicious, reasoning that March in Odisha is usually drier and sunnier than April. The satellite record said otherwise: March 2026 received less sun than April. Most of March's low output was weather, and only the residual in the chart survived once the weather was accounted for.

May had the most sun of any month, the highest mean air temperature and the worst conversion, even after the model's heat correction. Heat beyond what the model captures, and pre-monsoon dust, are the candidates. April and June, which followed 75 and 162 mm of rain, both recovered to between +1% and +2%, which fits dust being washed off. But May itself had 59 mm of rain and still fell short, so monthly bills cannot separate the two.

July and August came in [[r_jul]]% and [[r_aug]]% above expectation. Under heavy overcast most light is diffuse, and a daily formula for splitting direct from diffuse light is least reliable there. We treat that as a limit of the method rather than a property of the panels.

## 2026 was not a normal year

Our first projection for the next twelve months simply reused 2026's weather. That turned out to be a mistake worth explaining.

{{fig:normal}}

Comparing each billing month with the same calendar dates over the previous ten years shows how unusual 2026 was. July and August received [[jul_pct]]% and [[aug_pct]]% less sunlight than normal, darker than any of the previous ten years. July's rainfall was [[jul_rain]] mm against a ten-year average of [[jul_rain_norm]] mm. Across the eight billed months, sunlight ran [[y26_pct]]% below normal.

NASA revises its most recent months as processing completes. Between our first and second download, June's values changed, so July to September may still shift slightly. The rainfall, which comes from a separate dataset, tells the same story.

## What a normal year should look like

So instead of projecting from one unusual year, we ran the physics model over every day of the last ten years of weather at the site (2016 to 2025), with η fitted on 2026.

{{fig:forecast}}

A typical year comes to about [[fc_total]] kWh for [[fc_start]] to [[fc_end]]. The simple sunlight line gives [[reg_total]] kWh for the same months, about [[phys_minus_reg]]% lower, and most of the gap falls in the low-sun months from October to March. That is the February effect again. In winter the sun is low, and panels tilted towards it collect more than flat-ground sunlight suggests. The line was fitted on February to September and has never seen a winter sun. The physics model knows the geometry.

{{fig:backtest}}

Year to year, the weather moves the total by only [[yr_cv]]%. The worst of the last ten years, [[yr_min_year]], would have given [[yr_min]] kWh; the best, [[yr_max_year]], [[yr_max]] kWh. A bad year costs a few percent, not a fifth.

## Where the units went, and what they were worth

{{fig:balance}}

Solar used at home was steady, at [[self_min]] to [[self_max]] kWh a month. Demand was not. It rose about [[dem_rise]]% per day from February to June ([[dem_feb]] to [[dem_jun]] kWh a day) as the air conditioning came on, then eased with the rains. The bills went up because the house used more, not because the panels made less. A 3 kWp system against a 1,000 kWh month is undersized for summer rather than underperforming.

{{fig:demand}}

Demand follows the heat. Measured by cooling-degree-days, how far the daily mean temperature sat above 25 °C, the correlation is [[cdd_occ]]. Demand here is counted per occupied day, because the house stood empty for about a week in May, and the family recalls importing roughly 200 fewer units than usual. An absence of [[absent]] days reproduces that figure, so May's demand is spread over its occupied days only.

{{fig:money}}

Under net metering, every exported unit is credited against an imported one, so the bill follows imports minus exports. Comparing each bill with what it would have been without solar, slab by slab at the domestic tariff {{ref:tariff}}, solar has saved ₹[[saved_total]] so far.

{{fig:pies}}

Two percentages are easy to confuse, and the left-hand chart shows both. Of all the electricity the house used, [[ss_life]]% came from the panels at the moment they were producing; that green slice is **self-sufficiency**. Another [[credit_share]]% came from the grid but was cancelled on the bill by units the panels had exported earlier; that is the gold slice. Together they make the **bill offset**: generation equal to [[offset_life]]% of household demand. The remaining [[paid_share]]% was bought and paid for. The right-hand chart shows the same solar from the other side: [[used_share]]% was used at home and [[exp_share_life]]% went to the grid.

## A cheap experiment: paint the roof white

These panels are bifacial: they collect light on the back as well as the front, from sunlight reflected off the surface below. Today that surface is dark, often damp concrete, which reflects roughly 12% of the light falling on it. White paint reflects about 70%. The module datasheet's rear-gain table runs from 15% to 30% depending on the ground {{ref:waaree}}, and on the current surface the rear side probably adds about 5%. Our estimate for a white surface is about [[white_light_pct]]% more light-driven output.

**Would it also keep the panels cooler in summer?** This was worth checking, because heat is what costs these panels most in exactly the months with the highest cooling-degree-days. In a typical year, heat takes [[peak_heat_now]]% of output in [[peak_heat_month]], when the cells run about [[peak_rise_now]] °C above the air, against [[dec_heat_now]]% in December.

{{fig:heat}}

Probably not, though the evidence here is thinner than for the light gain. Two effects pull in opposite directions.

- **The back of the panel gets hotter.** Reflected light that reaches the back is absorbed, and absorbed light that does not become electricity becomes heat. With bifaciality of [[bifaciality]]% {{ref:waaree}}, a [[white_light_pct]]% output gain means about [[rear_increase]]% more light landing on the module. In our model, which applies the NOCT relation to that extra light, the cells run about [[peak_rise_add]] °C warmer in [[peak_heat_month]] and the heat loss rises from [[peak_heat_now]]% to [[peak_heat_white]]%. This is a model result, not a measurement.
- **The surroundings get cooler.** A white roof stays cooler in the sun {{ref:jbe2023}}, so it radiates less heat at the panels and warms the air around them less. Over a cool-roof coating, monofacial panels, which cannot use the reflected light and so show only this effect, ran [[surround_cool]] °C cooler {{ref:mahmood2023}}.

So at the summer peak the cells end up between [[peak_rise_net]] °C warmer (if the cooling measured on another roof applies here) and [[peak_rise_add]] °C warmer (if it does not). We found no published test that measures bifacial cell temperature over a dark roof and a white one side by side. What the field tests agree on is that the energy gain from a reflective roof comes mostly from extra light, not from lower temperatures {{ref:altan2019,jbe2023}}, and the bifacial gain is much larger than the monofacial one {{ref:mahmood2023}}. For this array the paint boosts the light. It is not a coolant.

The heat costs between [[heat_cost_cool_kwh]] and [[heat_cost_kwh]] kWh a year, depending on which bound holds. Either way that is small next to the [[light_kwh]] kWh of extra light.

{{fig:paint}}

Net of that heat, a white surface adds [[paint_kwh]] to [[paint_kwh_cool]] kWh in a typical year (we use the lower figure), roughly [[white_net_pct]]%, worth up to ₹[[paint_inr]] a year at the top tariff slab of ₹6.34 per unit {{ref:tariff}}. Winter units fall in cheaper slabs, so treat that as a ceiling. On ₹8,000 to ₹12,000 of paint and labour, the payback is roughly [[pay_lo]] to [[pay_hi]] years. Paint on the parts of the roof not covered by panels could also keep the rooms below a little cooler in summer {{ref:jbe2023}}, but we have no data to put a number on that for this house.

## The sky is getting darker

The last hunch came from a longer view. If sunlight drives everything, is the sunlight itself changing? NASA's record for these coordinates goes back to 1984.

{{fig:dimming}}

Average sunlight fell from [[ghi_early]] kWh/m² per day in 1984–93 to [[ghi_late]] in 2016–25, a decline of [[ghi_trend]] per decade (p < 0.0001). Ground stations have recorded the same dimming across India for decades {{ref:padma2007,soni2012}}. The natural suspect is cloud. But at these coordinates the clear-sky series, the sunlight a cloudless day would deliver, fell even faster, at [[clr_trend]] per decade.

{{figs:kt,seasons}}

The clearness index, measured sunlight divided by clear-sky sunlight, is flat ([[kt_trend]] per decade, p = [[kt_p]]). Over this grid cell, cloud cover has not changed; the air itself has become less transparent. That fits a 2024 study that found clouds dominate dimming across India as a whole, but named the region containing Bhubaneswar as the country's most aerosol-affected {{ref:jadhav2024}}. The dry seasons lost the most here, and those are the months in which a rooftop array earns most of its keep.

The same NASA record shows daily maximum temperatures falling, while India's own station network shows them rising {{ref:kumar2023}}. We treat that as an artefact of the dataset and build nothing on it.

## Over the panels' life

{{fig:life}}

Two slow losses compound. The panels age: the datasheet warrants at least 99% of rated power after the first year and 87.4% after 30 years, about [[age_rate]]% a year {{ref:waaree}}. And if the dimming trend continues at [[dim_rate]]% a year, sunlight falls further over the same period. By [[life_end_year]] the array would make about [[life_end]] kWh, [[life_drop]]% below year one, about [[life_gap]] percentage points worse than ageing alone. Aerosol pollution is a policy choice rather than a law of nature. Europe has brightened since the 1980s as air pollution was cut {{ref:wild2005,wild2009}}, and eastern China has brightened since its 2013 Clean Air Action {{ref:shi2021}}, after decades in which pollution had measurably cut solar output {{ref:sweerts2019}}. The lower line is a downside case, not a forecast.

## How we worked

- **Data.** Eight TPCODL bills, [[first]] to [[last]], reconciled against cumulative meter readings. NASA POWER daily weather for the billed days, ten years of daily history (2016 to 2025), and the monthly and annual record back to 1984 {{ref:nasa_power}}.
- **Model one, for forecasting.** Generation per day = a × sunlight + b, fitted by least squares on the eight months.
- **Model two, for diagnosis and the typical-year forecast.** Sunlight on the panels × heat derate × kWp × η, with η the only fitted number.
- **Validation.** One genuine out-of-sample month (September) and leave-one-out across all eight.
- **Assumptions.** Panels fixed at [[tilt]]° facing south. Ground reflectivity [[albedo]]. Cell temperature from a NOCT of [[noct]] °C. Tariff slabs of ₹2.90, 4.70, 5.70 and 6.10 per unit plus 4% duty. The house empty for [[absent]] days in May (demand only). White-surface gain of [[white_light_pct]]% from the datasheet's rear-gain table.
- **Limits.** Eight monthly points. An efficiency fitted on the same months it judges. Satellite estimates for a grid cell rather than a sensor on the roof. No inverter-level data.

Every number and chart in this piece is regenerated from the project's data with a single command.
