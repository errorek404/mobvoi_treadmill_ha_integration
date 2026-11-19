from __future__ import annotations

import asyncio
import logging
import struct
import time
from typing import Any

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONTROL_POINT_UUID, DOMAIN, TREADMILL_DATA_UUID

_LOGGER = logging.getLogger(__name__)


class MobvoiTreadmillCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=None,
        )
        self.address = address
        self._client: BleakClient | None = None
        self._running = False
        self._connect_task: asyncio.Task | None = None
        self._worker_task: asyncio.Task | None = None

        self._cmd_lock = asyncio.Lock()
        self._command_queue: asyncio.Queue[tuple[str, float | None]] = asyncio.Queue()

        self._pending_target_speed: float | None = None
        self._stop_in_progress_until: float = 0.0
        self._last_speed_cmd_time: float = 0.0

        self.data: dict[str, Any] = {
            "connected": False,
            "speed": 0.0,
            "distance": 0,
            "calories": 0,
            "elapsed_time": 0,
            "target_speed": 1.0,
            "belt_running": False,
        }

    async def async_start(self) -> None:
        self._running = True
        self._connect_task = self.hass.async_create_task(self._connection_loop())
        self._worker_task = self.hass.async_create_task(self._command_worker())

    async def async_stop(self) -> None:
        self._running = False
        for task in (self._worker_task, self._connect_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError:
                pass

    async def _connection_loop(self) -> None:
        while self._running:
            if not self._client or not self._client.is_connected:
                try:
                    ble_device = bluetooth.async_ble_device_from_address(
                        self.hass, self.address, connectable=True
                    )
                    if ble_device is None:
                        await asyncio.sleep(5)
                        continue

                    _LOGGER.debug("Connecting to Mobvoi Treadmill at %s", self.address)
                    self._client = await establish_connection(
                        BleakClient,
                        ble_device,
                        self.address,
                        disconnected_callback=self._on_disconnect,
                    )
                    await self._client.start_notify(
                        TREADMILL_DATA_UUID, self._handle_treadmill_data
                    )
                    try:
                        await self._client.start_notify(
                            CONTROL_POINT_UUID, self._handle_control_point_indication
                        )
                    except BleakError:
                        pass

                    self.data["connected"] = True
                    self.async_set_updated_data(dict(self.data))
                    _LOGGER.info("Connected to Mobvoi Treadmill %s", self.address)
                except Exception as err:
                    _LOGGER.debug("Connection attempt failed: %s", err)
                    self.data["connected"] = False
                    self.async_set_updated_data(dict(self.data))
                    await asyncio.sleep(5)
            else:
                await self._check_pending_speed()
                await asyncio.sleep(1.0)

    @callback
    def _on_disconnect(self, client: BleakClient) -> None:
        _LOGGER.info("Disconnected from Mobvoi Treadmill %s", self.address)
        self._pending_target_speed = None
        self.data["connected"] = False
        self.data["belt_running"] = False
        self.data["speed"] = 0.0
        self.async_set_updated_data(dict(self.data))

    @callback
    def _handle_control_point_indication(self, sender: Any, data: bytearray) -> None:
        _LOGGER.debug("FTMS Control Point response: %s", data.hex())

    @callback
    def _handle_treadmill_data(self, sender: Any, data: bytearray) -> None:
        if len(data) < 4:
            return
        flags = struct.unpack_from("<H", data, 0)[0]
        offset = 2

        speed_raw = struct.unpack_from("<H", data, offset)[0]
        speed_kmh = round(speed_raw * 0.01, 2)
        offset += 2

        if flags & (1 << 1):
            offset += 2

        if flags & (1 << 2):
            if len(data) >= offset + 3:
                dist = data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)
                self.data["distance"] = dist
            offset += 3

        if flags & (1 << 3):
            offset += 4

        if flags & (1 << 4):
            offset += 1

        if flags & (1 << 5):
            offset += 4

        if flags & (1 << 6):
            offset += 2

        if flags & (1 << 7):
            if len(data) >= offset + 2:
                kcal = struct.unpack_from("<H", data, offset)[0]
                self.data["calories"] = kcal
            offset += 5

        if flags & (1 << 8):
            offset += 1

        if flags & (1 << 9):
            offset += 1

        if flags & (1 << 10):
            if len(data) >= offset + 2:
                elapsed = struct.unpack_from("<H", data, offset)[0]
                self.data["elapsed_time"] = elapsed
            offset += 2

        now = time.monotonic()
        self.data["speed"] = speed_kmh

        if now < self._stop_in_progress_until:
            self.data["belt_running"] = False
        else:
            self.data["belt_running"] = speed_kmh > 0.05

        if self._pending_target_speed is not None:
            if abs(speed_kmh - self._pending_target_speed) <= 0.15:
                _LOGGER.debug(
                    "Target speed %.1f km/h confirmed by treadmill",
                    self._pending_target_speed,
                )
                self._pending_target_speed = None

        self.async_set_updated_data(dict(self.data))

    async def _check_pending_speed(self) -> None:
        if self._pending_target_speed is None:
            return
        now = time.monotonic()
        if now - self._last_speed_cmd_time < 1.2:
            return
        if self.data.get("speed", 0.0) >= 0.8:
            _LOGGER.debug(
                "Retrying pending target speed %.1f km/h (current: %.1f km/h)",
                self._pending_target_speed,
                self.data.get("speed", 0.0),
            )
            self._last_speed_cmd_time = now
            await self._command_queue.put(("SPEED", self._pending_target_speed))

    async def _command_worker(self) -> None:
        while self._running:
            cmd, val = await self._command_queue.get()
            try:
                async with self._cmd_lock:
                    await self._execute_ble_command(cmd, val)
            except Exception as err:
                _LOGGER.warning("Failed executing FTMS command %s: %s", cmd, err)
            finally:
                self._command_queue.task_done()
            await asyncio.sleep(0.25)

    async def _write_cp(self, payload: bytes) -> None:
        if not self._client or not self._client.is_connected:
            raise BleakError("Treadmill not connected")
        await self._client.write_gatt_char(CONTROL_POINT_UUID, payload, response=True)

    async def _execute_ble_command(self, cmd: str, val: float | None) -> None:
        if not self._client or not self._client.is_connected:
            return

        if cmd == "START":
            self._stop_in_progress_until = 0.0
            await self._write_cp(bytes([0x00]))
            await asyncio.sleep(0.18)
            await self._write_cp(bytes([0x07]))
            await asyncio.sleep(0.35)

        elif cmd == "STOP":
            self._pending_target_speed = None
            self._stop_in_progress_until = time.monotonic() + 4.5
            self.data["belt_running"] = False
            self.async_set_updated_data(dict(self.data))
            await self._write_cp(bytes([0x00]))
            await asyncio.sleep(0.15)
            await self._write_cp(bytes([0x08, 0x01]))
            await asyncio.sleep(0.3)

        elif cmd == "SPEED" and val is not None:
            clamped = max(1.0, min(12.0, round(val, 1)))
            self.data["target_speed"] = clamped
            self.async_set_updated_data(dict(self.data))

            if self.data.get("speed", 0.0) < 0.5:
                self._stop_in_progress_until = 0.0
                await self._write_cp(bytes([0x00]))
                await asyncio.sleep(0.18)
                await self._write_cp(bytes([0x07]))
                await asyncio.sleep(1.3)

            raw_val = int(round(clamped * 100))
            payload = struct.pack("<BH", 0x02, raw_val)
            await self._write_cp(bytes([0x00]))
            await asyncio.sleep(0.15)
            await self._write_cp(payload)
            self._last_speed_cmd_time = time.monotonic()

        elif cmd == "WAKE":
            await self._write_cp(bytes([0x00]))
            await asyncio.sleep(0.15)
            await self._write_cp(bytes([0x07]))
            await asyncio.sleep(0.22)
            await self._write_cp(bytes([0x08, 0x01]))
            await asyncio.sleep(0.25)

    async def async_start_belt(self, target_speed: float | None = None) -> None:
        if target_speed is not None:
            clamped = max(1.0, min(12.0, round(target_speed, 1)))
            self._pending_target_speed = clamped
            self.data["target_speed"] = clamped
            await self._command_queue.put(("START", None))
            await self._command_queue.put(("SPEED", clamped))
        else:
            await self._command_queue.put(("START", None))

    async def async_stop_belt(self) -> None:
        self._pending_target_speed = None
        while not self._command_queue.empty():
            try:
                self._command_queue.get_nowait()
                self._command_queue.task_done()
            except asyncio.QueueEmpty:
                break
        await self._command_queue.put(("STOP", None))

    async def async_set_speed(self, speed_kmh: float) -> None:
        clamped = max(1.0, min(12.0, round(speed_kmh, 1)))
        self._pending_target_speed = clamped
        self.data["target_speed"] = clamped
        self.async_set_updated_data(dict(self.data))
        await self._command_queue.put(("SPEED", clamped))

    async def async_wake_up(self) -> None:
        await self._command_queue.put(("WAKE", None))
