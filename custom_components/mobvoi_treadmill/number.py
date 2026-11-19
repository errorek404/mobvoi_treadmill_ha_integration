from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
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
    async_add_entities([MobvoiTargetSpeedNumber(coordinator, entry)])


class MobvoiTargetSpeedNumber(CoordinatorEntity[MobvoiTreadmillCoordinator], NumberEntity):
    _attr_has_entity_name = True
    _attr_native_min_value = 1.0
    _attr_native_max_value = 12.0
    _attr_native_step = 0.1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Prędkość docelowa"
        self._attr_unique_id = f"{entry.entry_id}_target_speed"
        self._attr_icon = "mdi:speedometer"
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
    def native_value(self) -> float:
        return float(self.coordinator.data.get("target_speed", 1.0))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_speed(value)
