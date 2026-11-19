from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    async_add_entities([MobvoiEmergencyStopButton(coordinator)])


class MobvoiEmergencyStopButton(
    CoordinatorEntity[MobvoiTreadmillCoordinator], ButtonEntity
):
    _attr_has_entity_name = True
    _attr_name = "Stop awaryjny"
    _attr_icon = "mdi:stop-circle-outline"

    def __init__(self, coordinator: MobvoiTreadmillCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_emergency_stop"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.device_name,
            manufacturer="Mobvoi",
            model="T4225 Plus",
        )

    async def async_press(self) -> None:
        await self.coordinator.async_send_stop(emergency=True)
