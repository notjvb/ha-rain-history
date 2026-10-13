"""Config and options flow for Rain History."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    LocationSelector,
    LocationSelectorConfig,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_INCLUDE_LAST_RAIN_YEAR,
    CONF_LOCATION,
    CONF_RAIN_YEAR_START_MONTH,
    DEFAULT_INCLUDE_LAST_RAIN_YEAR,
    DEFAULT_RAIN_YEAR_START_MONTH,
    DOMAIN,
)

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]  # fmt: skip


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION, default=defaults[CONF_LOCATION]): LocationSelector(
                LocationSelectorConfig(radius=False)
            ),
            vol.Required(
                CONF_RAIN_YEAR_START_MONTH,
                default=str(defaults[CONF_RAIN_YEAR_START_MONTH]),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=str(i), label=name)
                        for i, name in enumerate(MONTHS, start=1)
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_INCLUDE_LAST_RAIN_YEAR,
                default=defaults[CONF_INCLUDE_LAST_RAIN_YEAR],
            ): BooleanSelector(),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    location = user_input[CONF_LOCATION]
    return {
        CONF_LOCATION: {
            CONF_LATITUDE: round(float(location[CONF_LATITUDE]), 4),
            CONF_LONGITUDE: round(float(location[CONF_LONGITUDE]), 4),
        },
        CONF_RAIN_YEAR_START_MONTH: int(user_input[CONF_RAIN_YEAR_START_MONTH]),
        CONF_INCLUDE_LAST_RAIN_YEAR: user_input[CONF_INCLUDE_LAST_RAIN_YEAR],
    }


def _home_defaults(hass: HomeAssistant) -> dict[str, Any]:
    return {
        CONF_LOCATION: {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        },
        CONF_RAIN_YEAR_START_MONTH: DEFAULT_RAIN_YEAR_START_MONTH,
        CONF_INCLUDE_LAST_RAIN_YEAR: DEFAULT_INCLUDE_LAST_RAIN_YEAR,
    }


class RainHistoryConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up Rain History from the UI."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            data = _clean(user_input)
            loc = data[CONF_LOCATION]
            await self.async_set_unique_id(f"{loc[CONF_LATITUDE]},{loc[CONF_LONGITUDE]}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Rain History", data=data)

        return self.async_show_form(
            step_id="user", data_schema=_schema(_home_defaults(self.hass))
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> RainHistoryOptionsFlow:
        return RainHistoryOptionsFlow()


class RainHistoryOptionsFlow(OptionsFlow):
    """Change location or rain-year settings after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=_clean(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
