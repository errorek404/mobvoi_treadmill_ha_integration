from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MobvoiConfigEntry
from .coordinator import MobvoiTreadmillCoordinator
from .entity import MobvoiTreadmillEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MobvoiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([MobvoiBeltSwitch(entry.runtime_data, entry)])


class MobvoiBeltSwitch(MobvoiTreadmillEntity, SwitchEntity):
    _attr_translation_key = "belt"
    _attr_icon = "mdi:run-fast"

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: MobvoiConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "belt_switch")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("belt_running", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if not await self.coordinator.async_send_start():
            raise HomeAssistantError("Failed to start Mobvoi treadmill belt.")

    async def async_turn_off(self, **kwargs: Any) -> None:
        if not await self.coordinator.async_send_stop(emergency=False):
            raise HomeAssistantError("Failed to stop Mobvoi treadmill belt.")
