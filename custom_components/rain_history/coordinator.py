"""Data update coordinator for Rain History."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .api import OpenMeteoError, OpenMeteoRainClient, RainTotals
from .const import (
    CONF_INCLUDE_LAST_RAIN_YEAR,
    CONF_LOCATION,
    CONF_RAIN_THRESHOLD,
    CONF_RAIN_YEAR_START_MONTH,
    DEFAULT_INCLUDE_LAST_RAIN_YEAR,
    DEFAULT_RAIN_THRESHOLD_MM,
    DEFAULT_RAIN_YEAR_START_MONTH,
    DOMAIN,
    MM_PER_INCH,
    POLL_MINUTE_RANGE,
    STALE_DATA_TOLERANCE,
)

_LOGGER = logging.getLogger(__name__)

type RainHistoryConfigEntry = ConfigEntry[RainHistoryCoordinator]


class RainHistoryCoordinator(DataUpdateCoordinator[RainTotals]):
    """Fetches rain totals from Open-Meteo once an hour (or on update_entity)."""

    config_entry: RainHistoryConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RainHistoryConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            # No interval: async_start_polling runs refreshes on a fixed minute instead.
            update_interval=None,
        )
        settings = {**entry.data, **entry.options}
        location = settings[CONF_LOCATION]
        self.inches = hass.config.units is US_CUSTOMARY_SYSTEM
        self.start_month = int(
            settings.get(CONF_RAIN_YEAR_START_MONTH, DEFAULT_RAIN_YEAR_START_MONTH)
        )
        self.include_last_rain_year = settings.get(
            CONF_INCLUDE_LAST_RAIN_YEAR, DEFAULT_INCLUDE_LAST_RAIN_YEAR
        )
        # Stored in mm; the client works in inches when HA does.
        threshold_mm = float(settings.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD_MM))
        self.rain_threshold = (
            round(threshold_mm / MM_PER_INCH, 2) if self.inches else threshold_mm
        )
        self.client = OpenMeteoRainClient(
            async_get_clientsession(hass),
            location[CONF_LATITUDE],
            location[CONF_LONGITUDE],
            self.inches,
        )
        self._last_success: datetime | None = None

    def async_start_polling(self) -> Callable[[], None]:
        """Refresh hourly at a random minute:second. Returns the unsubscribe callback."""
        minute = random.randrange(*POLL_MINUTE_RANGE)
        second = random.randrange(60)
        _LOGGER.debug("Polling Open-Meteo hourly at :%02d:%02d", minute, second)

        async def _poll(_now: datetime) -> None:
            await self.async_refresh()

        return async_track_time_change(self.hass, _poll, minute=minute, second=second)

    async def _async_update_data(self) -> RainTotals:
        try:
            totals = await self.client.async_get_totals(
                self.start_month, self.include_last_rain_year, self.rain_threshold
            )
        except OpenMeteoError as err:
            if (
                self.data is not None
                and self._last_success is not None
                and dt_util.utcnow() - self._last_success < STALE_DATA_TOLERANCE
            ):
                _LOGGER.warning(
                    "Open-Meteo request failed, keeping totals from %s: %s",
                    self._last_success.isoformat(timespec="minutes"),
                    err,
                )
                return self.data
            raise UpdateFailed(f"Open-Meteo request failed: {err}") from err
        self._last_success = dt_util.utcnow()
        if totals.this_rain_year is None:
            _LOGGER.warning("Couldn't fetch rain-year history from Open-Meteo; will retry")
        return totals
