from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DOMAIN, FTMS_SERVICE_UUID

_LOGGER = logging.getLogger(__name__)


class MobvoiTreadmillConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Mobvoi Treadmill Plus"
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery_info is not None
        name = self._discovery_info.name or "Mobvoi Home Treadmill Plus"
        if user_input is not None:
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: name,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": name,
                "address": self._discovery_info.address,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            info = self._discovered_devices[address]
            name = info.name or "Mobvoi Home Treadmill Plus"
            return self.async_create_entry(
                title=name,
                data={CONF_ADDRESS: address, CONF_NAME: name},
            )

        current_addresses = self._async_current_ids()
        for info in async_discovered_service_info(self.hass):
            if info.address in current_addresses:
                continue
            name_upper = (info.name or "").upper()
            has_ftms = FTMS_SERVICE_UUID in [u.lower() for u in info.service_uuids]
            if has_ftms or "MOBVOI" in name_upper or "T4225" in name_upper or "TREADMILL" in name_upper:
                self._discovered_devices[info.address] = info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            addr: f"{info.name or 'Mobvoi Treadmill'} ({addr})"
            for addr, info in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )
