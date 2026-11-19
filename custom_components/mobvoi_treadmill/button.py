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
    async_add_entities([MobvoiWakeButton(coordinator, entry)])


class MobvoiWakeButton(CoordinatorEntity[MobvoiTreadmillCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = "Wybudź bieżnię"
        self._attr_unique_id = f"{entry.entry_id}_wake_button"
        self._attr_icon = "mdi:power-standby"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Mobvoi Home Treadmill Plus",
            manufacturer="Mobvoi",
            model="T4225 Plus",
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.get("connected", False))

    async def async_press(self) -> None:
        await self.coordinator.async_wake_up()
