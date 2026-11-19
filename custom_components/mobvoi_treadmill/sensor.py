from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MobvoiSensor(coordinator, entry, "speed", "Prędkość", UnitOfSpeed.KILOMETERS_PER_HOUR, SensorDeviceClass.SPEED, "mdi:speedometer"),
            MobvoiSensor(coordinator, entry, "distance", "Dystans", UnitOfLength.METERS, SensorDeviceClass.DISTANCE, "mdi:map-marker-distance"),
            MobvoiSensor(coordinator, entry, "calories", "Kalorie", "kcal", None, "mdi:fire"),
            MobvoiSensor(coordinator, entry, "elapsed_time", "Czas treningu", UnitOfTime.SECONDS, SensorDeviceClass.DURATION, "mdi:timer-outline"),
        ]
    )


class MobvoiSensor(CoordinatorEntity[MobvoiTreadmillCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str,
        device_class: SensorDeviceClass | None,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Mobvoi Home Treadmill Plus",
            manufacturer="Mobvoi",
            model="T4225 Plus",
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.get("connected", False))

    @property
    def native_value(self) -> float | int:
        return self.coordinator.data.get(self._key, 0)
