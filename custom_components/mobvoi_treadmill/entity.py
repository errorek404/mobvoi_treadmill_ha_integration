from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MobvoiTreadmillCoordinator


class MobvoiTreadmillEntity(CoordinatorEntity[MobvoiTreadmillCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MobvoiTreadmillCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Mobvoi",
            model="Home Treadmill Plus",
            configuration_url="https://github.com/errorek404/mobvoi_treadmill_ha_integration",
        )

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data.get("connected", False))
