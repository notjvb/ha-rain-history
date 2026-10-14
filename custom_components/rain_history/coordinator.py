"""Data update coordinator for Rain History."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .api import OpenMeteoError, OpenMeteoRainClient, RainTotals
from .const import (
    CONF_INCLUDE_LAST_RAIN_YEAR,
    CONF_LOCATION,
    CONF_RAIN_YEAR_START_MONTH,
    DEFAULT_INCLUDE_LAST_RAIN_YEAR,
    DEFAULT_RAIN_YEAR_START_MONTH,
    DOMAIN,
    STALE_DATA_TOLERANCE,
    UPDATE_INTERVAL,
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
            update_interval=UPDATE_INTERVAL,
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
        self.client = OpenMeteoRainClient(
            async_get_clientsession(hass),
            location[CONF_LATITUDE],
            location[CONF_LONGITUDE],
            self.inches,
        )
        self._last_success: datetime | None = None

    async def _async_update_data(self) -> RainTotals:
        try:
            totals = await self.client.async_get_totals(
                self.start_month, self.include_last_rain_year
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
