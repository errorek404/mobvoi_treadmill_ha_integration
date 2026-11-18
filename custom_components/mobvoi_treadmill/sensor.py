from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiCoordinator


@dataclass(frozen=True, kw_only=True)
class MobvoiSensorDescription(SensorEntityDescription):
    data_key: str


SENSORS: tuple[MobvoiSensorDescription, ...] = (
    MobvoiSensorDescription(
        key="speed",
        translation_key="speed",
        name="Prędkość",
        data_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
    ),
    MobvoiSensorDescription(
        key="distance",
        translation_key="distance",
        name="Dystans",
        data_key="distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:map-marker-distance",
    ),
    MobvoiSensorDescription(
        key="calories",
        translation_key="calories",
        name="Kalorie",
        data_key="calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:fire",
    ),
    MobvoiSensorDescription(
        key="elapsed_time",
        translation_key="elapsed_time",
        name="Czas treningu",
        data_key="elapsed_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:timer-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MobvoiSensor(coordinator, entry, description) for description in SENSORS
    )


class MobvoiSensor(CoordinatorEntity[MobvoiCoordinator], SensorEntity):
    entity_description: MobvoiSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MobvoiCoordinator,
        entry: ConfigEntry,
        description: MobvoiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name="Mobvoi Home Treadmill Plus",
            manufacturer="Mobvoi",
            model="Home Treadmill Plus",
        )

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)
