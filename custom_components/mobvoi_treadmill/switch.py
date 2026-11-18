from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
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
            MobvoiPowerWakeSwitch(coordinator, entry),
            MobvoiBeltRunSwitch(coordinator, entry),
        ]
    )


class MobvoiPowerWakeSwitch(CoordinatorEntity, SwitchEntity):
    """Przycisk Power (Wybudzanie / Czuwanie bieżni po BLE bez ruszania pasa)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Mobvoi Power"
        self._attr_unique_id = f"{entry.entry_id}_power_wake"
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:power"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Mobvoi Home Treadmill Plus",
            "manufacturer": "Mobvoi",
            "model": "T4225 Plus",
        }

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("awake", False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_wake_up()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_sleep()


class MobvoiBeltRunSwitch(CoordinatorEntity, SwitchEntity):
    """Przełącznik Start/Stop pasa biegowego."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_name = "Mobvoi Start Pasa"
        self._attr_unique_id = f"{entry.entry_id}_belt_run"
        self._attr_device_class = SwitchDeviceClass.SWITCH
        self._attr_icon = "mdi:run"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Mobvoi Home Treadmill Plus",
            "manufacturer": "Mobvoi",
            "model": "T4225 Plus",
        }

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("running", False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_start()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_stop()
