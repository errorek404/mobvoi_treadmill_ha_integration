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

from .const import (
    CMD_REQUEST_CONTROL,
    CMD_SET_TARGET_SPEED,
    CMD_START_OR_RESUME,
    CMD_STOP_OR_PAUSE,
    CONTROL_POINT_UUID,
    DOMAIN,
    STOP_PARAM_STOP,
    TREADMILL_DATA_UUID,
)

_LOGGER = logging.getLogger(__name__)


class MobvoiTreadmillCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
        )
        self.address = address
        self.device_name = name
        self._client: BleakClient | None = None
        self._connect_lock = asyncio.Lock()
        self._gatt_lock = asyncio.Lock()
        self._cmd_queue: asyncio.Queue[tuple[str, float | None]] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._enforce_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._stopped = False

        self._pending_target_speed: float | None = None
        self._stopping_until: float = 0.0
        self._control_requested: bool = False

        self.data: dict[str, Any] = {
            "connected": False,
            "running": False,
            "speed": 0.0,
            "target_speed": 1.0,
            "distance": 0,
            "elapsed_time": 0,
            "calories": 0,
        }

    async def async_start(self) -> None:
        self._stopped = False
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = self.hass.async_create_task(self._command_worker())
        if self._enforce_task is None or self._enforce_task.done():
            self._enforce_task = self.hass.async_create_task(self._speed_enforcer_loop())
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = self.hass.async_create_task(self._connection_loop())

    async def async_stop(self) -> None:
        self._stopped = True
        for task in (self._worker_task, self._enforce_task, self._reconnect_task):
            if task and not task.done():
                task.cancel()
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError:
                pass
        self._client = None

    async def _connection_loop(self) -> None:
        while not self._stopped:
            if self._client is None or not self._client.is_connected:
                await self._try_connect()
            await asyncio.sleep(5.0)

    async def _try_connect(self) -> None:
        if self._connect_lock.locked():
            return
        async with self._connect_lock:
            if self._client and self._client.is_connected:
                return
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if not ble_device:
                if self.data.get("connected"):
                    self._update_state(connected=False, running=False, speed=0.0)
                return
            try:
                client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self.device_name,
                    disconnected_callback=self._on_disconnect,
                )
                self._client = client
                self._control_requested = False
                await client.start_notify(TREADMILL_DATA_UUID, self._handle_treadmill_data)
                try:
                    await client.start_notify(CONTROL_POINT_UUID, self._handle_control_point)
                except BleakError:
                    pass
                self._update_state(connected=True)
                _LOGGER.info("Połączono z bieżnią Mobvoi (%s)", self.address)
            except Exception as err:
                _LOGGER.debug("Nieudana próba połączenia z %s: %s", self.address, err)
                self._client = None
                if self.data.get("connected"):
                    self._update_state(connected=False, running=False, speed=0.0)

    @callback
    def _on_disconnect(self, _client: BleakClient) -> None:
        _LOGGER.info("Rozłączono z bieżnią Mobvoi (%s)", self.address)
        self._client = None
        self._control_requested = False
        self._pending_target_speed = None
        self._update_state(connected=False, running=False, speed=0.0)

    @callback
    def _handle_control_point(self, _sender: Any, data: bytearray) -> None:
        _LOGGER.debug("FTMS Control Point response: %s", data.hex())

    @callback
    def _handle_treadmill_data(self, _sender: Any, data: bytearray) -> None:
        if len(data) < 4:
            return
        flags = struct.unpack_from("<H", data, 0)[0]
        offset = 2

        speed_raw = struct.unpack_from("<H", data, offset)[0]
        speed_kmh = round(speed_raw / 100.0, 2)
        offset += 2

        # Bit 1: Average Speed present (uint16)
        if flags & (1 << 1) and len(data) >= offset + 2:
            offset += 2

        # Bit 2: Total Distance present (uint24 in meters)
        distance = self.data["distance"]
        if flags & (1 << 2) and len(data) >= offset + 3:
            b0, b1, b2 = data[offset], data[offset + 1], data[offset + 2]
            distance = b0 | (b1 << 8) | (b2 << 16)
            offset += 3

        # Bit 3: Inclination & Ramp Angle (2x int16)
        if flags & (1 << 3) and len(data) >= offset + 4:
            offset += 4

        # Bit 4: Elevation Gain (2x uint16)
        if flags & (1 << 4) and len(data) >= offset + 4:
            offset += 4

        # Bit 5: Instantaneous Pace (uint8)
        if flags & (1 << 5) and len(data) >= offset + 1:
            offset += 1

        # Bit 6: Average Pace (uint8)
        if flags & (1 << 6) and len(data) >= offset + 1:
            offset += 1

        # Bit 7: Expended Energy (Total uint16, Per Hour uint16, Per Min uint8)
        calories = self.data["calories"]
        if flags & (1 << 7) and len(data) >= offset + 2:
            calories = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            if len(data) >= offset + 3:
                offset += 3

        # Bit 8: Heart Rate (uint8)
        if flags & (1 << 8) and len(data) >= offset + 1:
            offset += 1

        # Bit 9: Metabolic Equivalent (uint8)
        if flags & (1 << 9) and len(data) >= offset + 1:
            offset += 1

        # Bit 10: Elapsed Time (uint16 seconds)
        elapsed_time = self.data["elapsed_time"]
        if flags & (1 << 10) and len(data) >= offset + 2:
            elapsed_time = struct.unpack_from("<H", data, offset)[0]
            offset += 2

        now = time.monotonic()
        if now < self._stopping_until:
            running = False
        else:
            running = speed_kmh > 0.0

        target_speed = self.data["target_speed"]
        if running and self._pending_target_speed is None and speed_kmh >= 1.0:
            target_speed = round(speed_kmh, 1)

        self._update_state(
            connected=True,
            running=running,
            speed=speed_kmh,
            target_speed=target_speed,
            distance=distance,
            elapsed_time=elapsed_time,
            calories=calories,
        )

    def _update_state(self, **kwargs: Any) -> None:
        new_data = {**self.data, **kwargs}
        self.async_set_updated_data(new_data)

    def _clear_queue(self) -> None:
        while not self._cmd_queue.empty():
            try:
                self._cmd_queue.get_nowait()
                self._cmd_queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def async_send_start(self) -> None:
        self._stopping_until = 0.0
        await self._cmd_queue.put(("start", None))

    async def async_send_stop(self, emergency: bool = False) -> None:
        self._pending_target_speed = None
        self._stopping_until = time.monotonic() + 4.5
        self._clear_queue()
        self._update_state(running=False)
        if emergency and self._client and self._client.is_connected:
            await self._write_ftms(bytes([CMD_STOP_OR_PAUSE, STOP_PARAM_STOP]))
        else:
            await self._cmd_queue.put(("stop", None))

    async def async_set_speed(self, speed_kmh: float) -> None:
        clamped = round(max(1.0, min(12.0, speed_kmh)), 1)
        self._stopping_until = 0.0
        self._pending_target_speed = clamped
        self._update_state(target_speed=clamped)
        await self._cmd_queue.put(("speed", clamped))

    async def _write_ftms(self, payload: bytes) -> bool:
        if not self._client or not self._client.is_connected:
            return False
        async with self._gatt_lock:
            try:
                if not self._control_requested:
                    await self._client.write_gatt_char(
                        CONTROL_POINT_UUID, bytes([CMD_REQUEST_CONTROL]), response=True
                    )
                    self._control_requested = True
                    await asyncio.sleep(0.20)
                await self._client.write_gatt_char(
                    CONTROL_POINT_UUID, payload, response=True
                )
                await asyncio.sleep(0.25)
                return True
            except Exception as err:
                _LOGGER.debug("Błąd zapisu FTMS (%s): %s", payload.hex(), err)
                self._control_requested = False
                return False

    async def _command_worker(self) -> None:
        while not self._stopped:
            cmd, val = await self._cmd_queue.get()
            try:
                if not self._client or not self._client.is_connected:
                    await self._try_connect()
                if not self._client or not self._client.is_connected:
                    continue

                if cmd == "start":
                    await self._write_ftms(bytes([CMD_START_OR_RESUME]))
                elif cmd == "stop":
                    await self._write_ftms(bytes([CMD_STOP_OR_PAUSE, STOP_PARAM_STOP]))
                elif cmd == "speed" and val is not None:
                    if self.data.get("speed", 0.0) == 0.0:
                        await self._write_ftms(bytes([CMD_START_OR_RESUME]))
                        await asyncio.sleep(1.5)
                    raw_val = int(round(val * 100))
                    payload = struct.pack("<BH", CMD_SET_TARGET_SPEED, raw_val)
                    await self._write_ftms(payload)
            finally:
                self._cmd_queue.task_done()

    async def _speed_enforcer_loop(self) -> None:
        while not self._stopped:
            await asyncio.sleep(1.2)
            target = self._pending_target_speed
            if target is None:
                continue
            if not self._client or not self._client.is_connected:
                continue
            current = self.data.get("speed", 0.0)
            if abs(current - target) <= 0.15:
                self._pending_target_speed = None
                continue
            if current > 0.0 and self._cmd_queue.empty():
                raw_val = int(round(target * 100))
                payload = struct.pack("<BH", CMD_SET_TARGET_SPEED, raw_val)
                await self._write_ftms(payload)
