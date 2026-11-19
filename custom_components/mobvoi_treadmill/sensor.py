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
from .coordinator import MobvoiTreadmillCoordinator


@dataclass(frozen=True, kw_only=True)
class MobvoiSensorDescription(SensorEntityDescription):
    data_key: str


SENSORS: tuple[MobvoiSensorDescription, ...] = (
    MobvoiSensorDescription(
        key="speed",
        data_key="speed",
        name="Prędkość",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MobvoiSensorDescription(
        key="distance",
        data_key="distance",
        name="Dystans",
        icon="mdi:map-marker-distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MobvoiSensorDescription(
        key="calories",
        data_key="calories",
        name="Kalorie",
        icon="mdi:fire",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    MobvoiSensorDescription(
        key="elapsed_time",
        data_key="elapsed_time",
        name="Czas treningu",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MobvoiTreadmillSensor(coordinator, entry, desc) for desc in SENSORS
    )


class MobvoiTreadmillSensor(
    CoordinatorEntity[MobvoiTreadmillCoordinator], SensorEntity
):
    entity_description: MobvoiSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: ConfigEntry,
        description: MobvoiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Mobvoi",
            model="Home Treadmill Plus",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.data.get("connected", False)

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)
