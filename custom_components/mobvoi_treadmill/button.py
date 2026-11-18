from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: MobvoiCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MobvoiStartButton(coordinator, entry),
            MobvoiStopButton(coordinator, entry),
        ]
    )


class MobvoiBaseButton(CoordinatorEntity[MobvoiCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MobvoiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name="Mobvoi Home Treadmill Plus",
            manufacturer="Mobvoi",
            model="Home Treadmill Plus",
        )


class MobvoiStartButton(MobvoiBaseButton):
    _attr_name = "Start"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator: MobvoiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_start"

    async def async_press(self) -> None:
        await self.coordinator.async_start_treadmill()


class MobvoiStopButton(MobvoiBaseButton):
    _attr_name = "Stop"
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator: MobvoiCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_stop"

    async def async_press(self) -> None:
        await self.coordinator.async_stop_treadmill()
