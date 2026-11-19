from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    async_add_entities([MobvoiBeltSwitch(coordinator, entry)])


class MobvoiBeltSwitch(
    CoordinatorEntity[MobvoiTreadmillCoordinator], SwitchEntity
):
    _attr_has_entity_name = True
    _attr_name = "Start pasa"
    _attr_icon = "mdi:run-fast"

    def __init__(
        self, coordinator: MobvoiTreadmillCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_belt_switch"
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
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("belt_running", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        ok = await self.coordinator.async_send_start()
        if not ok:
            _LOGGER.warning("Nie udało się uruchomić pasa bieżni Mobvoi.")

    async def async_turn_off(self, **kwargs: Any) -> None:
        ok = await self.coordinator.async_send_stop(emergency=False)
        if not ok:
            _LOGGER.warning("Nie udało się zatrzymać pasa bieżni Mobvoi.")
