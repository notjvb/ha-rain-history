"""Rain total and last-rain sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfPrecipitationDepth, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RainTotals
from .const import DOMAIN
from .coordinator import RainHistoryConfigEntry, RainHistoryCoordinator


@dataclass(frozen=True, kw_only=True)
class RainSensorDescription(SensorEntityDescription):
    value_fn: Callable[[RainTotals], float | date | None]
    # Rain totals get their unit and precision from HA's unit system.
    device_class: SensorDeviceClass | None = SensorDeviceClass.PRECIPITATION
    state_class: SensorStateClass | str | None = SensorStateClass.MEASUREMENT


# The device is named "Rain", so these become sensor.rain_today, sensor.rain_last_3_days, ...
# matching the entity IDs of the old configuration.yaml REST sensors.
SENSORS: tuple[RainSensorDescription, ...] = (
    RainSensorDescription(key="today", translation_key="today", value_fn=lambda t: t.today),
    RainSensorDescription(
        key="last_3_days", translation_key="last_3_days", value_fn=lambda t: t.last_3_days
    ),
    RainSensorDescription(
        key="last_7_days", translation_key="last_7_days", value_fn=lambda t: t.last_7_days
    ),
    RainSensorDescription(
        key="last_30_days", translation_key="last_30_days", value_fn=lambda t: t.last_30_days
    ),
    RainSensorDescription(
        key="this_rain_year",
        translation_key="this_rain_year",
        value_fn=lambda t: t.this_rain_year,
    ),
    # sensor.rain_last_rain and sensor.rain_days_since_rain.
    RainSensorDescription(
        key="last_rain",
        translation_key="last_rain",
        device_class=SensorDeviceClass.DATE,
        state_class=None,
        value_fn=lambda t: t.last_rain,
    ),
    RainSensorDescription(
        key="days_since_rain",
        translation_key="days_since_rain",
        device_class=None,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=0,
        value_fn=lambda t: t.days_since_rain,
    ),
)

LAST_RAIN_YEAR = RainSensorDescription(
    key="last_rain_year", translation_key="last_rain_year", value_fn=lambda t: t.last_rain_year
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainHistoryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    descriptions = list(SENSORS)
    if coordinator.include_last_rain_year:
        descriptions.append(LAST_RAIN_YEAR)
    async_add_entities(RainSensor(coordinator, d) for d in descriptions)


class RainSensor(CoordinatorEntity[RainHistoryCoordinator], SensorEntity):
    """A rain total over a fixed window, or when it last rained."""

    _attr_has_entity_name = True
    _attr_attribution = "Weather data by Open-Meteo.com"
    entity_description: RainSensorDescription

    def __init__(
        self, coordinator: RainHistoryCoordinator, description: RainSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        if description.device_class == SensorDeviceClass.PRECIPITATION:
            self._attr_native_unit_of_measurement = (
                UnitOfPrecipitationDepth.INCHES
                if coordinator.inches
                else UnitOfPrecipitationDepth.MILLIMETERS
            )
            self._attr_suggested_display_precision = 2 if coordinator.inches else 1
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Rain",
            manufacturer="Open-Meteo",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://open-meteo.com/",
        )

    @property
    def native_value(self) -> float | date | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str | float | None]:
        totals = self.coordinator.data
        attrs: dict[str, str | float | None] = {"as_of": totals.as_of.isoformat()}
        if self.entity_description.key == "this_rain_year":
            attrs["rain_year_start"] = totals.rain_year_start.isoformat()
        elif self.entity_description.key == "last_rain_year":
            start = totals.rain_year_start
            attrs["rain_year_start"] = start.replace(year=start.year - 1).isoformat()
        elif self.entity_description.key in ("last_rain", "days_since_rain"):
            # Amount and threshold are in the same unit as the rain total sensors.
            attrs["last_rain"] = totals.last_rain.isoformat() if totals.last_rain else None
            attrs["amount"] = totals.last_rain_amount
            attrs["threshold"] = self.coordinator.rain_threshold
            attrs["unit"] = "in" if self.coordinator.inches else "mm"
            attrs["searched_since"] = totals.last_rain_searched_since.isoformat()
        return attrs
