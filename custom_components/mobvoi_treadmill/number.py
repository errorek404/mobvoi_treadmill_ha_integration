from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MobvoiConfigEntry
from .const import MAX_SPEED, MIN_SPEED, SPEED_STEP
from .coordinator import MobvoiTreadmillCoordinator
from .entity import MobvoiTreadmillEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MobvoiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MobvoiTargetSpeedNumber(entry.runtime_data, entry)])


class MobvoiTargetSpeedNumber(MobvoiTreadmillEntity, NumberEntity):
    _attr_translation_key = "target_speed"
    _attr_icon = "mdi:gauge"
    _attr_native_min_value = MIN_SPEED
    _attr_native_max_value = MAX_SPEED
    _attr_native_step = SPEED_STEP
    _attr_native_unit_of_measurement = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: MobvoiConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "target_speed")

    @property
    def native_value(self) -> float:
        return float(self.coordinator.data.get("target_speed", MIN_SPEED))

    async def async_set_native_value(self, value: float) -> None:
        if not await self.coordinator.async_set_target_speed(value):
            raise HomeAssistantError(
                f"Failed to set target speed to {value:.1f} km/h."
            )
