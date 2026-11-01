# Rain History

A Home Assistant integration that reports how much rain has fallen at a location, using [Open-Meteo](https://open-meteo.com/). It needs no API key and no YAML.

## Sensors

All sensors belong to one device named **Rain**:

| Entity | What it is |
|---|---|
| `sensor.rain_today` | Today's rain, including any still forecast for the rest of today |
| `sensor.rain_so_far_today` | Today's rain up to the last full hour, with no forecast |
| `sensor.rain_last_3_days` | Today plus the previous 2 days |
| `sensor.rain_last_7_days` | Today plus the previous 6 days |
| `sensor.rain_last_30_days` | Today plus the previous 29 days |
| `sensor.rain_this_rain_year` | Since the start of the current rain year |
| `sensor.rain_last_rain_year` | All of the previous rain year (optional) |
| `sensor.rain_last_rain` | The most recent day that got at least the rain threshold (0.1 in by default) |
| `sensor.rain_days_since_rain` | Days since that day; 0 if today counts |

Values are in inches when Home Assistant uses US customary units, and in millimetres otherwise.

`sensor.rain_today` can go up and down during the day. Open-Meteo reruns its weather models through the day, and each run can change how much rain it expects for the rest of today. `sensor.rain_so_far_today` only adds up hours that are over, so it mostly climbs, and by the end of the day it matches `sensor.rain_today`. It can still shift a little, because past hours are modeled too. Use it when you want rain that has actually fallen. The 3, 7 and 30 day totals include the whole-day value for today, like `sensor.rain_today`.

The last-rain sensors look back at least a year. If no day in that window reached the threshold, they show unknown. For today they use `sensor.rain_so_far_today`, so today only counts as the last rain once that much rain has fallen, not when it's just forecast. The `amount` attribute for today is the rain so far, and it can go up later in the day.

The integration updates once an hour, at a random minute picked at startup (never near the top of the hour, when Open-Meteo is busiest). To get fresh numbers right before an automation decides something, call `homeassistant.update_entity` on any of the sensors first.

Daily totals for the last 30 days come from Open-Meteo's forecast API. Older days come from its historical forecast archive, which is fetched once a day. These are modeled values for the location, not readings from a rain gauge.

## Install

1. In HACS, open the ⋮ menu → **Custom repositories**. Add `https://github.com/notjvb/ha-rain-history` with type **Integration**.
2. Search HACS for **Rain History** and download it.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration → Rain History**.

## Settings

- **Location:** defaults to your home location.
- **Rain year starts in:** defaults to October, which matches the California water year (Oct 1 to Sep 30).
- **Also show last rain year's total:** on by default.
- **Counts as rain at:** how much rain a day needs to count for the last-rain sensors. Defaults to 0.1 in (2.54 mm).

To change these later, open the integration and click **Configure**.
