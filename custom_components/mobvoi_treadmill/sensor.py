from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MobvoiConfigEntry
from .coordinator import MobvoiTreadmillCoordinator
from .entity import MobvoiTreadmillEntity


@dataclass(frozen=True, kw_only=True)
class MobvoiSensorDescription(SensorEntityDescription):
    data_key: str


SENSORS: tuple[MobvoiSensorDescription, ...] = (
    MobvoiSensorDescription(
        key="speed",
        data_key="speed",
        translation_key="speed",
        icon="mdi:speedometer",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
    MobvoiSensorDescription(
        key="distance",
        data_key="distance",
        translation_key="distance",
        icon="mdi:map-marker-distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    MobvoiSensorDescription(
        key="calories",
        data_key="calories",
        translation_key="calories",
        icon="mdi:fire",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    MobvoiSensorDescription(
        key="elapsed_time",
        data_key="elapsed_time",
        translation_key="elapsed_time",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MobvoiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        MobvoiTreadmillSensor(coordinator, entry, desc) for desc in SENSORS
    )


class MobvoiTreadmillSensor(MobvoiTreadmillEntity, SensorEntity):
    entity_description: MobvoiSensorDescription

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: MobvoiConfigEntry,
        description: MobvoiSensorDescription,
    ) -> None:
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)
