from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONTROL_POINT_UUID, TREADMILL_DATA_UUID

_LOGGER = logging.getLogger(__name__)


class MobvoiCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Mobvoi Treadmill ({address})",
        )
        self.address = address
        self._client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._running = True
        self._bg_task: asyncio.Task | None = None
        self.data = {
            "connected": False,
            "speed": 0.0,
            "distance": 0,
            "calories": 0,
            "elapsed_time": 0,
        }

    def start(self) -> None:
        self._bg_task = self.hass.async_create_background_task(
            self._connection_loop(), name="mobvoi_ble_loop"
        )

    async def stop(self) -> None:
        self._running = False
        if self._bg_task:
            self._bg_task.cancel()
        if self._client and self._client.is_connected:
            await self._client.disconnect()

    async def _connection_loop(self) -> None:
        while self._running:
            if not self._client or not self._client.is_connected:
                await self._connect()
            await asyncio.sleep(5)

    async def _connect(self) -> None:
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return

            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if not ble_device:
                if self.data.get("connected"):
                    self.data = {**self.data, "connected": False, "speed": 0.0}
                    self.async_set_updated_data(self.data)
                return

            try:
                self._client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self.address,
                    disconnected_callback=self._on_disconnect,
                )
                await self._client.start_notify(
                    TREADMILL_DATA_UUID, self._notification_handler
                )
                await self._client.write_gatt_char(
                    CONTROL_POINT_UUID, bytearray([0x00]), response=True
                )
                self.data = {**self.data, "connected": True}
                self.async_set_updated_data(self.data)
                _LOGGER.info("Połączono z bieżnią Mobvoi (%s)", self.address)
            except Exception as err:
                _LOGGER.debug("Błąd połączenia z bieżnią Mobvoi: %s", err)
                self._client = None

    @callback
    def _on_disconnect(self, client: BleakClient) -> None:
        _LOGGER.info("Rozłączono z bieżnią Mobvoi (%s)", self.address)
        self.data = {**self.data, "connected": False, "speed": 0.0}
        self.async_set_updated_data(self.data)

    @callback
    def _notification_handler(self, _sender: int, data: bytearray) -> None:
        if len(data) < 4:
            return

        flags = struct.unpack_from("<H", data, 0)[0]
        offset = 2

        speed = self.data.get("speed", 0.0)
        distance = self.data.get("distance", 0)
        calories = self.data.get("calories", 0)
        elapsed_time = self.data.get("elapsed_time", 0)

        # Bit 0 == 0 oznacza obecność Instantaneous Speed
        if not (flags & (1 << 0)) and len(data) >= offset + 2:
            raw_speed = struct.unpack_from("<H", data, offset)[0]
            speed = round(raw_speed / 100.0, 2)
            offset += 2

        # Bit 1: Average Speed
        if (flags & (1 << 1)) and len(data) >= offset + 2:
            offset += 2

        # Bit 2: Total Distance (3 bajty)
        if (flags & (1 << 2)) and len(data) >= offset + 3:
            distance = data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)
            offset += 3

        # Bit 3: Inclination & Ramp Angle (4 bajty)
        if (flags & (1 << 3)) and len(data) >= offset + 4:
            offset += 4

        # Bit 4: Elevation Gain (4 bajty)
        if (flags & (1 << 4)) and len(data) >= offset + 4:
            offset += 4

        # Bit 5: Instantaneous Pace (1 bajt)
        if (flags & (1 << 5)) and len(data) >= offset + 1:
            offset += 1

        # Bit 6: Average Pace (1 bajt)
        if (flags & (1 << 6)) and len(data) >= offset + 1:
            offset += 1

        # Bit 7: Expended Energy (5 bajtów: Total 2B, Per Hour 2B, Per Min 1B)
        if (flags & (1 << 7)) and len(data) >= offset + 5:
            calories = struct.unpack_from("<H", data, offset)[0]
            offset += 5

        # Bit 8: Heart Rate (1 bajt)
        if (flags & (1 << 8)) and len(data) >= offset + 1:
            offset += 1

        # Bit 9: Metabolic Equivalent (1 bajt)
        if (flags & (1 << 9)) and len(data) >= offset + 1:
            offset += 1

        # Bit 10: Elapsed Time (2 bajty)
        if (flags & (1 << 10)) and len(data) >= offset + 2:
            elapsed_time = struct.unpack_from("<H", data, offset)[0]
            offset += 2

        self.data = {
            "connected": True,
            "speed": speed,
            "distance": distance,
            "calories": calories,
            "elapsed_time": elapsed_time,
        }
        self.async_set_updated_data(self.data)

    async def async_send_command(self, payload: bytes) -> None:
        if not self._client or not self._client.is_connected:
            await self._connect()
        if self._client and self._client.is_connected:
            try:
                await self._client.write_gatt_char(
                    CONTROL_POINT_UUID, bytearray([0x00]), response=True
                )
                await self._client.write_gatt_char(
                    CONTROL_POINT_UUID, bytearray(payload), response=True
                )
            except Exception as err:
                _LOGGER.error("Błąd wysyłania komendy do bieżni: %s", err)

    async def async_start_treadmill(self) -> None:
        await self.async_send_command(b"")

    async def async_stop_treadmill(self) -> None:
        await self.async_send_command(b"")

    async def async_set_speed(self, speed_kmh: float) -> None:
        val = int(round(speed_kmh * 100))
        payload = struct.pack("<BH", 0x02, val)
        await self.async_send_command(payload)
