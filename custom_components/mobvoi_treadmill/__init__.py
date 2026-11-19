from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import MobvoiTreadmillCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    address: str = entry.data[CONF_ADDRESS]

    coordinator = MobvoiTreadmillCoordinator(hass, address, entry.title)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    try:
        await coordinator.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        # Sprzątanie po częściowym setupie – nie zostawiamy wiszącego workera
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await coordinator.async_stop()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_stop()
    return unload_ok