"""Constants for the Rain History integration."""

from datetime import timedelta

DOMAIN = "rain_history"

CONF_LOCATION = "location"
CONF_RAIN_YEAR_START_MONTH = "rain_year_start_month"
CONF_INCLUDE_LAST_RAIN_YEAR = "include_last_rain_year"
CONF_RAIN_THRESHOLD = "rain_threshold"

# California water year: Oct 1 - Sep 30.
DEFAULT_RAIN_YEAR_START_MONTH = 10
DEFAULT_INCLUDE_LAST_RAIN_YEAR = True
# A day counts as rainy for "last rain" once it gets this much. Stored in mm; 0.1 in.
DEFAULT_RAIN_THRESHOLD_MM = 2.54
MM_PER_INCH = 25.4

# Poll once an hour at a random minute in this range, so we don't join the rush of
# clients hitting Open-Meteo at the top of the hour (which gets 503 "overloaded").
POLL_MINUTE_RANGE = (5, 55)

# Keep showing the last good totals through an Open-Meteo outage this long
# before the sensors go unavailable.
STALE_DATA_TOLERANCE = timedelta(hours=6)
