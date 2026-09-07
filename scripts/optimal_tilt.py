import json

import pandas as pd
import pvlib

LAT, LON, TZ = 20.312069, 85.867744, "Asia/Kolkata"
loc = pvlib.location.Location(LAT, LON, tz=TZ)
times = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h", tz=TZ)
cs = loc.get_clearsky(times, model="ineichen")
sp = loc.get_solarposition(times)
dni_extra = pvlib.irradiance.get_extra_radiation(times)

res = {}
for tilt in list(range(0,41,2))+[5,12]:
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=180,
        solar_zenith=sp["apparent_zenith"], solar_azimuth=sp["azimuth"],
        dni=cs["dni"], ghi=cs["ghi"], dhi=cs["dhi"],
        dni_extra=dni_extra, albedo=0.12, model="haydavies")
    res[tilt] = poa["poa_global"].sum()/1000
base = res[0]
opt = max(res, key=res.get)
print(f"optimal tilt (annual, clear-sky, south-facing): {opt} deg")
for t in [0,10,12,14,16,20,24,30]:
    print(f"  {t:>2}deg : {res[t]:>7.0f} kWh/m2/yr   ({res[t]/res[opt]*100:5.1f}% of optimum)")
with open("opt_tilt.json","w") as fh:
    json.dump({str(k): round(v,1) for k,v in res.items()}, fh)

# monthly profile at 12 vs 20 deg
rows=[]
for tilt in [12, 20]:
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=180,
        solar_zenith=sp["apparent_zenith"], solar_azimuth=sp["azimuth"],
        dni=cs["dni"], ghi=cs["ghi"], dhi=cs["dhi"],
        dni_extra=dni_extra, albedo=0.12, model="haydavies")
    m = (poa["poa_global"]/1000).resample("ME").sum()
    rows.append(pd.Series(m.values, index=[d.strftime("%b") for d in m.index], name=f"{tilt}deg"))
comp = pd.concat(rows, axis=1)
comp["delta_%"] = ((comp["20deg"]/comp["12deg"]-1)*100).round(1)
print("\nMonthly clear-sky POA, 12deg vs 20deg (kWh/m2):")
print(comp.round(1).to_string())
comp.round(2).to_json("monthly_tilt.json")
