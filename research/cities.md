# Same roof, twelve cities

*We ran one 3 kWp rooftop array through ten years of weather in twelve Indian cities to ask what really decides how much it makes: monsoon cloud or summer heat. The answer was neither.*

By Piyush Dash · November 2026

Our [first article](https://piyushdash94.github.io/rooftop-solar-analytics/) followed one bifacial array on a roof in Bhubaneswar, using nine months of bills. It left us wondering how ordinary that roof is. Would the same panels make more in Jaipur, or less in Kolkata? And if they would, why?

The obvious guesses are the two things everyone talks about in India: the monsoon, which buries the sky under cloud for four months, and the summer heat, which makes solar panels less efficient. We wrote down a hypothesis before running anything.

## The hunch, written down first

**Hypothesis.** Across Indian cities, monsoon cloud decides rooftop yield far more than summer heat.

We set three tests and the bar each had to clear, before looking at any results.

| Test | What would support the hypothesis |
|---|---|
| (a) Sun or heat | The spread across cities in sunlight on the panels is at least twice the spread caused by heat. |
| (b) The monsoon's share | June to September explains more than half of the difference in annual panel sunlight between cities. |
| (c) Ranking | A city's output ranks more closely with its monsoon sunlight than with its heat loss. |

## How we ran it

We kept everything about the array fixed and changed only the weather. Same [[kwp]] kWp of bifacial panels, same 12° tilt facing south, same dark concrete underneath, and the same system efficiency of [[eta]] that we fitted to the Bhubaneswar bills. For each city we downloaded ten years of daily NASA POWER satellite weather, 2016 to 2025 {{ref:nasa_power}}, and ran it through the physics model from the first article: sunlight on the panel plane, a heat correction from the module's datasheet {{ref:waaree}}, then kilowatt-hours.

Two checks before trusting it. Our fresh download for Bhubaneswar gives [[bbsr_kwh]] kWh a year, within [[art_diff]]% of the [[art_kwh]] kWh typical year in the first article, which was calibrated on real bills. And the twelve cities average [[mean_daily_yield]] kWh per kWp a day, inside the 3.5 to 4.5 band the World Bank reports for India {{ref:worldbank2020}}.

One limitation matters. A fixed 12° tilt is close to ideal in the south and a little flat for the north, where the cities sit at up to [[lat_hi]]° latitude. Tilting every array to its own latitude instead barely changes the order: the two rankings correlate at [[rho_tilt]].

## The ranking

{{fig:c_rank}}

[[top_city]] comes first at [[top_kwh]] kWh a year and [[bot_city]] last at [[bot_kwh]], a gap of [[spread_pct]]% from nothing but weather. Bhubaneswar is [[bbsr_rank]]th of [[n_cities]]. The same panels on a roof in [[top_city]] would make about [[bbsr_vs_top]]% more.

## Heat is a tax, not a verdict

Test (a) passed easily. The spread in panel sunlight across cities is [[spread_sun]]%; the spread in the heat factor is [[spread_heat]]%, about [[spread_ratio]] times smaller. Heat costs between [[heat_lo]]% ([[heat_lo_city]]) and [[heat_hi]]% ([[heat_hi_city]]) of output, and that range is narrow.

{{fig:c_heat}}

The surprise is the direction. The cities that lose most to heat produce the most. [[hot_city]]'s cells reach about [[hot_tcell]] °C in its hottest month, against [[cool_tcell]] °C in [[cool_city]], yet [[hot_city]] tops the table. Output and heat loss rank together at [[rho_heat]]. Heat is a tax on sunshine, and the sunniest cities can most afford it.

## The monsoon is not what separates cities

Tests (b) and (c) failed. June to September explains only [[mon_share]]% of the difference in annual panel sunlight between cities. Output ranks with monsoon sunlight at [[rho_mon]], below heat, and far below the dry months, at [[rho_rest]].

{{fig:c_seasons}}

{{fig:c_shares}}

The monsoon dims every city, but it dims them by similar amounts, so it does little to change their order. Delhi has the [[delhi_mon_rank]]nd brightest monsoon of the twelve and still finishes [[delhi_rank]]th. The difference is made in winter, which explains [[ss_winter]]% of the gap, and the pre-monsoon months, which explain [[ss_pre]]%. Bhubaneswar's panels collect [[bbsr_winter]] kWh/m² from December to February; Bengaluru's collect [[beng_winter]], [[winter_gap]]% more.

So the hypothesis, as written, is rejected. One of its three tests held.

## Haze, more than cloud

If the dry season decides, what decides the dry season? Sunlight can be lost in three places on the way down. Latitude sets how much arrives at the top of the atmosphere. The air itself scatters and absorbs some, even with no cloud in sight: dust, smoke, pollution and water vapour. Clouds take the rest. NASA's data gives all three: sunlight at the top of the atmosphere, sunlight under a cloud-free sky, and sunlight that actually arrived. Their ratios split the gap between cities into latitude, haze and cloud.

Over the whole year, haze explains [[dc_haze]]% of the gap in ground sunlight, cloud [[dc_cloud]]% and latitude [[dc_latitude]]%. In the dry months cloud falls to [[dd_cloud]]%, and haze ([[dd_haze]]%) and latitude ([[dd_latitude]]%) do almost all the work.

{{fig:c_haze}}

The haziest dry-season skies belong to [[hazy_list]], the eastern cities and the Indo-Gangetic Plain. A cloud-free sky over these cities lets through as little as [[haze_lo]] of the sunlight arriving at the top of the atmosphere, against up to [[haze_hi]] over the clearest. Bhubaneswar's figure is [[bbsr_haze]]. This fits what field studies have found. Particles in the air and dust settled on the glass each cut solar output in India by similar amounts {{ref:bergin2017}}, and aerosols during winter fog over the Indo-Gangetic Plain reduced surface sunlight by 5 to 35% in one detailed case study {{ref:bharali2024}}. It also fits the first article, where Bhubaneswar's 42-year decline in sunlight was in the cloud-free sky, not in cloudiness.

## A new hypothesis

The data points to a different story from the one we started with. **Winter air clarity, not the monsoon or the heat, is what separates Indian cities for rooftop solar.** That is a new claim, found in the data rather than tested on it, so it needs its own test. The natural one is independent: aerosol measurements from a different satellite instrument should rank the twelve cities' winter skies the same way NASA's clear-sky ratio does.

Two smaller results are worth recording. Output is steady from year to year everywhere: its coefficient of variation is [[cv_lo]] to [[cv_hi]]%. And the cities that lean hardest on the monsoon are not the ones whose output swings most (rank correlation [[rho_cv_mon]]).

## How we worked

- **Data.** NASA POWER daily point data for each city centre, 2016 to 2025. Sunlight comes from CERES satellite products at 1° resolution, so each "city" is really a 100 km grid cell.
- **Model.** The physics model from the first article: daily diffuse split, sunlight on a 12° south-facing plane, NOCT cell temperature, one efficiency of [[eta]] fitted on Bhubaneswar's bills and applied everywhere.
- **Tests.** Three criteria written before running. Spreads are standard deviations of logarithms, so they read as percentages. Season and haze shares are covariance shares, which add up to 100%.
- **Limits.** Twelve cities. The same tilt, roof and efficiency everywhere. Dust that settles on the panels is not modelled, and it can be as large a loss as dust in the air {{ref:bergin2017}}. No tariffs or money: this is about kilowatt-hours only.
