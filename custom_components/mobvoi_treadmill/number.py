from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MAX_SPEED, MIN_SPEED, SPEED_STEP
from .coordinator import MobvoiTreadmillCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MobvoiTargetSpeedNumber(coordinator, entry)])


class MobvoiTargetSpeedNumber(
    CoordinatorEntity[MobvoiTreadmillCoordinator], NumberEntity
):
    _attr_has_entity_name = True
    _attr_name = "Prędkość docelowa"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = MIN_SPEED
    _attr_native_max_value = MAX_SPEED
    _attr_native_step = SPEED_STEP
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_target_speed"
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
    def native_value(self) -> float:
        return float(self.coordinator.data.get("target_speed", MIN_SPEED))

    async def async_set_native_value(self, value: float) -> None:
        ok = await self.coordinator.async_set_target_speed(value)
        if not ok:
            _LOGGER.warning("Nie udało się ustawić prędkości docelowej %.1f km/h.", value)
