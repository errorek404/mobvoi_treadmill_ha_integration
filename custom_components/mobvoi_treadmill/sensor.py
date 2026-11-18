from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfLength, UnitOfSpeed, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator

SENSORS = [
    ("speed", "Prędkość", UnitOfSpeed.KILOMETERS_PER_HOUR, SensorDeviceClass.SPEED, "mdi:speedometer"),
    ("distance", "Dystans", UnitOfLength.METERS, SensorDeviceClass.DISTANCE, "mdi:map-marker-distance"),
    ("calories", "Kalorie", UnitOfEnergy.KILO_CALORIE, SensorDeviceClass.ENERGY, "mdi:fire"),
    ("elapsed_time", "Czas treningu", UnitOfTime.SECONDS, SensorDeviceClass.DURATION, "mdi:timer-outline"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MobvoiSensor(coordinator, entry, key, name, unit, dev_class, icon)
        for key, name, unit, dev_class, icon in SENSORS
    )


class MobvoiSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, key, name, unit, dev_class, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"Mobvoi {name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Mobvoi Home Treadmill Plus",
            "manufacturer": "Mobvoi",
            "model": "T4225 Plus",
        }

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key, 0)
