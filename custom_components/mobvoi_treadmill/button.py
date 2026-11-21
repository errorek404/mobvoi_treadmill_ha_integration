from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([MobvoiEmergencyStopButton(entry.runtime_data, entry)])


class MobvoiEmergencyStopButton(MobvoiTreadmillEntity, ButtonEntity):
    _attr_translation_key = "emergency_stop"
    _attr_icon = "mdi:octagon"

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: MobvoiConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "emergency_stop")

    async def async_press(self) -> None:
        if not await self.coordinator.async_send_stop(emergency=True):
            raise HomeAssistantError(
                "Failed to trigger emergency stop on Mobvoi treadmill."
            )
