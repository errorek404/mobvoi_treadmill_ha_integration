from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import MobvoiTreadmillCoordinator

type MobvoiConfigEntry = ConfigEntry[MobvoiTreadmillCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MobvoiConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    coordinator = MobvoiTreadmillCoordinator(hass, address, entry.title)
    entry.runtime_data = coordinator

    try:
        await coordinator.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await coordinator.async_stop()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MobvoiConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok
