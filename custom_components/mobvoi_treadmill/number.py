from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MobvoiTargetSpeedNumber(coordinator, entry)])


class MobvoiTargetSpeedNumber(CoordinatorEntity, NumberEntity):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Mobvoi Prędkość docelowa"
        self._attr_unique_id = f"{entry.entry_id}_target_speed"
        self._attr_native_min_value = 1.0
        self._attr_native_max_value = 12.0
        self._attr_native_step = 0.5
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_icon = "mdi:run-fast"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Mobvoi Home Treadmill Plus",
            "manufacturer": "Mobvoi",
            "model": "T4225 Plus",
        }

    @property
    def native_value(self) -> float:
        speed = self.coordinator.data.get("speed", 1.0)
        return max(1.0, float(speed))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_speed(value)
