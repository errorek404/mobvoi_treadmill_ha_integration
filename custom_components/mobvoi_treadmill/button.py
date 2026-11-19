from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MobvoiEmergencyStopButton(coordinator, entry)])


class MobvoiEmergencyStopButton(
    CoordinatorEntity[MobvoiTreadmillCoordinator], ButtonEntity
):
    _attr_has_entity_name = True
    _attr_name = "Stop awaryjny"
    _attr_icon = "mdi:octagon"

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_emergency_stop"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Mobvoi",
            model="Home Treadmill Plus",
        )

    @property
    def available(self) -> bool:
        return self.coordinator.data.get("connected", False)

    async def async_press(self) -> None:
        ok = await self.coordinator.async_send_stop(emergency=True)
        if not ok:
            _LOGGER.warning("Nie udało się wykonać zatrzymania awaryjnego bieżni Mobvoi.")
