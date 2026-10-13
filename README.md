# Rain History

A Home Assistant integration that reports how much rain has fallen at a location, using [Open-Meteo](https://open-meteo.com/). It needs no API key and no YAML.

## Sensors

All sensors belong to one device named **Rain**:

| Entity | What it is |
|---|---|
| `sensor.rain_today` | Today's rain, including any still forecast for the rest of today |
| `sensor.rain_last_3_days` | Today plus the previous 2 days |
| `sensor.rain_last_7_days` | Today plus the previous 6 days |
| `sensor.rain_last_30_days` | Today plus the previous 29 days |
| `sensor.rain_this_rain_year` | Since the start of the current rain year |
| `sensor.rain_last_rain_year` | All of the previous rain year (optional) |

Values are in inches when Home Assistant uses US customary units, and in millimetres otherwise.

The integration updates once an hour. To get fresh numbers right before an automation decides something, call `homeassistant.update_entity` on any of the sensors first.

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

To change these later, open the integration and click **Configure**.
