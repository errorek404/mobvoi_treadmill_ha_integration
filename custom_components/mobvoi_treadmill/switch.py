from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([MobvoiBeltSwitch(coordinator)])


class MobvoiBeltSwitch(
    CoordinatorEntity[MobvoiTreadmillCoordinator], SwitchEntity
):
    _attr_has_entity_name = True
    _attr_name = "Start pasa"
    _attr_icon = "mdi:run-fast"

    def __init__(self, coordinator: MobvoiTreadmillCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_belt_running"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.device_name,
            manufacturer="Mobvoi",
            model="T4225 Plus",
        )

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_start()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_send_stop(emergency=False)
