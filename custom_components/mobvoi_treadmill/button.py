from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: MobvoiTreadmillCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MobvoiStartButton(coordinator, entry),
            MobvoiStopButton(coordinator, entry),
        ]
    )


class MobvoiBaseButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry, key, name, icon):
        super().__init__(coordinator)
        self._attr_name = f"Mobvoi {name}"
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Mobvoi Home Treadmill Plus",
            "manufacturer": "Mobvoi",
            "model": "T4225 Plus",
        }


class MobvoiStartButton(MobvoiBaseButton):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "start", "Start", "mdi:play")

    async def async_press(self) -> None:
        await self.coordinator.async_start()


class MobvoiStopButton(MobvoiBaseButton):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "stop", "Stop", "mdi:stop")

    async def async_press(self) -> None:
        await self.coordinator.async_stop()
