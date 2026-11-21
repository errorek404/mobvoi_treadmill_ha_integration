from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DOMAIN, FTMS_SERVICE_UUID

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class MobvoiTreadmillConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, str] = {}
        self._discovered_titles: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {
            "name": discovery_info.name or "Mobvoi Home Treadmill Plus"
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
                data={CONF_ADDRESS: self._discovery_info.address},
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not MAC_REGEX.match(address):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                title = self._discovered_titles.get(
                    address, "Mobvoi Home Treadmill Plus"
                )
                return self.async_create_entry(
                    title=title,
                    data={CONF_ADDRESS: address},
                )

        current_addresses = self._async_current_ids()
        for info in bluetooth.async_discovered_service_info(self.hass):
            if info.address in current_addresses:
                continue
            name_lower = (info.name or "").lower()
            has_ftms = FTMS_SERVICE_UUID in [u.lower() for u in info.service_uuids]
            if (
                has_ftms
                or "mobvoi" in name_lower
                or "treadmill" in name_lower
                or "fs-" in name_lower
            ):
                display_name = info.name or "Mobvoi Home Treadmill Plus"
                self._discovered_titles[info.address.upper()] = display_name
                self._discovered_devices[info.address.upper()] = (
                    f"{display_name} ({info.address})"
                )

        if not self._discovered_devices:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
            errors=errors,
        )
