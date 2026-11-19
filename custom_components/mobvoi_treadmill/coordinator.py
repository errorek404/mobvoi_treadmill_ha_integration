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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CMD_REQUEST_CONTROL,
    CMD_SET_TARGET_SPEED,
    CMD_START_OR_RESUME,
    CMD_STOP_OR_PAUSE,
    CONTROL_POINT_UUID,
    DOMAIN,
    MAX_SPEED,
    MIN_SPEED,
    TREADMILL_DATA_UUID,
)

_LOGGER = logging.getLogger(__name__)

CONTROL_TTL_SECONDS = 30.0
MAX_ENFORCE_ATTEMPTS = 5
CMD_TIMEOUT_SECONDS = 5.0
# Backoff reconnectu (sekundy): rośnie przy kolejnych niepowodzeniach, resetuje się po sukcesie
RECONNECT_BACKOFF = (5.0, 10.0, 30.0, 60.0)


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
        self._gatt_lock = asyncio.Lock()
        self._cmd_queue: asyncio.Queue[tuple[bytes, asyncio.Future[bool] | None]] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._enforce_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._running = False
        self._reconnect_backoff_idx = 0

        self._control_requested = False
        self._control_granted_at: float = 0.0
        self._pending_target_speed: float | None = None
        self._enforce_attempts: int = 0
        self._stopping_until: float = 0.0

        self.data: dict[str, Any] = {
            "connected": False,
            "speed": 0.0,
            "target_speed": MIN_SPEED,
            "distance": 0,
            "calories": 0,
            "elapsed_time": 0,
            "belt_running": False,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        # Dana jest pushowana przez _handle_treadmill_data; tutaj tylko oddajemy bieżący stan.
        return self.data

    async def async_start(self) -> None:
        self._running = True
        self._worker_task = self.hass.async_create_task(self._command_worker())
        self._enforce_task = self.hass.async_create_task(self._speed_enforcer_loop())
        self._reconnect_task = self.hass.async_create_task(self._connection_loop())

    async def async_stop(self) -> None:
        self._running = False
        tasks = [
            t
            for t in (self._worker_task, self._enforce_task, self._reconnect_task)
            if t and not t.done()
        ]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._worker_task = None
        self._enforce_task = None
        self._reconnect_task = None

        while not self._cmd_queue.empty():
            _, fut = self._cmd_queue.get_nowait()
            if fut and not fut.done():
                fut.set_result(False)
            self._cmd_queue.task_done()

        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except BleakError:
                pass
        self._client = None
        self._control_requested = False

    def _on_disconnect(self, _client: BleakClient) -> None:
        _LOGGER.debug("Rozłączono z bieżnią %s", self.address)
        self._control_requested = False
        self._control_granted_at = 0.0
        self._pending_target_speed = None
        self._enforce_attempts = 0
        new_data = dict(self.data)
        new_data["connected"] = False
        new_data["speed"] = 0.0
        new_data["belt_running"] = False
        self.async_set_updated_data(new_data)

    async def _connection_loop(self) -> None:
        while self._running:
            try:
                if self._client is None or not self._client.is_connected:
                    ble_device = bluetooth.async_ble_device_from_address(
                        self.hass, self.address, connectable=True
                    )
                    if ble_device is not None:
                        _LOGGER.debug("Łączenie z bieżnią %s...", self.address)
                        client = await establish_connection(
                            BleakClient,
                            ble_device,
                            self.device_name,
                            disconnected_callback=self._on_disconnect,
                        )
                        self._client = client
                        self._control_requested = False
                        self._control_granted_at = 0.0
                        await client.start_notify(
                            TREADMILL_DATA_UUID, self._handle_treadmill_data
                        )
                        new_data = dict(self.data)
                        new_data["connected"] = True
                        self.async_set_updated_data(new_data)
                        _LOGGER.info("Połączono z bieżnią %s", self.address)
                        # Sukces — resetujemy backoff
                        self._reconnect_backoff_idx = 0
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.debug("Błąd połączenia z bieżnią %s: %s", self.address, err)
                self._client = None
                self._control_requested = False
                # Backoff rośnie tylko przy faktycznym niepowodzeniu
                if self._reconnect_backoff_idx < len(RECONNECT_BACKOFF) - 1:
                    self._reconnect_backoff_idx += 1

            delay = RECONNECT_BACKOFF[self._reconnect_backoff_idx]
            await asyncio.sleep(delay)

    def _handle_treadmill_data(self, _sender: Any, data: bytearray) -> None:
        if len(data) < 4:
            return
        try:
            flags = struct.unpack_from("<H", data, 0)[0]
            offset = 2

            # Instantaneous Speed (uint16, 0.01 km/h) — obowiązkowe
            speed_raw = struct.unpack_from("<H", data, offset)[0]
            speed_kmh = round(speed_raw / 100.0, 2)
            offset += 2

            # Average Speed (uint16)
            if flags & (1 << 1):
                offset += 2

            # Total Distance (uint24, m)
            distance_m = self.data.get("distance", 0)
            if flags & (1 << 2):
                if offset + 3 <= len(data):
                    d_bytes = data[offset : offset + 3]
                    distance_m = d_bytes[0] | (d_bytes[1] << 8) | (d_bytes[2] << 16)
                offset += 3

            # Inclination (sint16) + Ramp Angle Setting (sint16) = 4 B
            if flags & (1 << 3):
                offset += 4

            # Positive/Negative Elevation Gain (uint16 x2) = 4 B
            if flags & (1 << 4):
                offset += 4

            # Instantaneous Pace (uint8) = 1 B
            if flags & (1 << 5):
                offset += 1

            # Average Pace (uint8) = 1 B
            if flags & (1 << 6):
                offset += 1

            # Expended Energy (uint16 total + uint16 per hour + uint8 per minute) = 5 B
            calories_kcal = self.data.get("calories", 0)
            if flags & (1 << 7):
                if offset + 2 <= len(data):
                    calories_kcal = struct.unpack_from("<H", data, offset)[0]
                offset += 5

            # Heart Rate (uint8) = 1 B
            if flags & (1 << 8):
                offset += 1

            # Metabolic Equivalent (uint8) = 1 B
            if flags & (1 << 9):
                offset += 1

            # Elapsed Time (uint16, s)
            elapsed_s = self.data.get("elapsed_time", 0)
            if flags & (1 << 10):
                if offset + 2 <= len(data):
                    elapsed_s = struct.unpack_from("<H", data, offset)[0]
                offset += 2

            # Remaining Time (uint16, s)
            if flags & (1 << 11):
                offset += 2

            # Force on Belt (sint16) + Power Output (sint16) = 4 B
            if flags & (1 << 12):
                offset += 4

            # Diagnostyka: bity 13–15 zarezerwowane
            unknown = flags & 0xE000
            if unknown:
                _LOGGER.debug("Nieznane bity flag FTMS: 0x%04X", unknown)

            now = time.monotonic()
            if now < self._stopping_until:
                belt_running = False
            else:
                belt_running = speed_kmh > 0.0

            # target_speed: nie nadpisujemy „aktualną” w trakcie zatrzymywania
            target_speed = self.data.get("target_speed", MIN_SPEED)
            if (
                now >= self._stopping_until
                and speed_kmh >= MIN_SPEED
                and self._pending_target_speed is None
            ):
                target_speed = speed_kmh

            if (
                self._pending_target_speed is not None
                and abs(speed_kmh - self._pending_target_speed) <= 0.15
            ):
                self._pending_target_speed = None
                self._enforce_attempts = 0

            new_data = {
                "connected": True,
                "speed": speed_kmh,
                "target_speed": target_speed,
                "distance": distance_m,
                "calories": calories_kcal,
                "elapsed_time": elapsed_s,
                "belt_running": belt_running,
            }
            self.async_set_updated_data(new_data)
        except Exception as err:
            _LOGGER.warning("Błąd parsowania pakietu FTMS: %s", err)

    async def _write_control_point(self, payload: bytes) -> bool:
        async with self._gatt_lock:
            if not self._client or not self._client.is_connected:
                self._control_requested = False
                return False
            try:
                now = time.monotonic()
                if (
                    not self._control_requested
                    or (now - self._control_granted_at) > CONTROL_TTL_SECONDS
                ):
                    await self._client.write_gatt_char(
                        CONTROL_POINT_UUID, bytes([CMD_REQUEST_CONTROL]), response=True
                    )
                    self._control_requested = True
                    self._control_granted_at = time.monotonic()
                    await asyncio.sleep(0.25)

                await self._client.write_gatt_char(
                    CONTROL_POINT_UUID, payload, response=True
                )
                await asyncio.sleep(0.25)
                return True
            except Exception as err:
                _LOGGER.warning("Nieudany zapis komendy FTMS (%s): %s", payload.hex(), err)
                self._control_requested = False
                self._control_granted_at = 0.0
                return False

    async def _enqueue_cmd(
        self, payload: bytes, timeout: float = CMD_TIMEOUT_SECONDS
    ) -> bool:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()
        await self._cmd_queue.put((payload, fut))
        try:
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            if not fut.done():
                fut.cancel()
            _LOGGER.warning("Timeout wysyłania komendy FTMS (%s)", payload.hex())
            return False

    async def _command_worker(self) -> None:
        current_fut: asyncio.Future[bool] | None = None
        while self._running:
            try:
                payload, fut = await self._cmd_queue.get()
                current_fut = fut
                try:
                    # Blokada komend, które przyszły po STOP a przed upływem _stopping_until
                    # (wyjątek: same komendy STOP mogą przejść — na wypadek podwójnego stopu)
                    if (
                        time.monotonic() < self._stopping_until
                        and payload
                        and payload[0] != CMD_STOP_OR_PAUSE
                    ):
                        if fut and not fut.done():
                            fut.set_result(False)
                        continue

                    ok = await self._write_control_point(payload)
                    if fut and not fut.done():
                        fut.set_result(ok)
                except Exception:
                    if fut and not fut.done():
                        fut.set_result(False)
                finally:
                    current_fut = None
                    self._cmd_queue.task_done()
            except asyncio.CancelledError:
                # Nie zostawiamy wiszącego future — wołający nie może czekać wiecznie
                if current_fut and not current_fut.done():
                    current_fut.set_result(False)
                break

    async def _speed_enforcer_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(1.2)
                target = self._pending_target_speed
                if target is None:
                    self._enforce_attempts = 0
                    continue
                if not self.data.get("connected"):
                    continue
                if time.monotonic() < self._stopping_until:
                    # Trwa zatrzymywanie — nie wymuszamy prędkości
                    continue

                current_speed = self.data.get("speed", 0.0)
                if abs(current_speed - target) <= 0.15:
                    self._pending_target_speed = None
                    self._enforce_attempts = 0
                    continue

                if self._enforce_attempts >= MAX_ENFORCE_ATTEMPTS:
                    _LOGGER.warning(
                        "Przekroczono limit %d prób ustawienia prędkości %.1f km/h "
                        "(aktualna: %.1f km/h). Anulowanie.",
                        MAX_ENFORCE_ATTEMPTS,
                        target,
                        current_speed,
                    )
                    self._pending_target_speed = None
                    self._enforce_attempts = 0
                    continue

                self._enforce_attempts += 1
                if current_speed == 0.0:
                    await self._enqueue_cmd(bytes([CMD_START_OR_RESUME]))
                else:
                    speed_raw = int(round(target * 100))
                    payload = struct.pack("<BH", CMD_SET_TARGET_SPEED, speed_raw)
                    await self._enqueue_cmd(payload)
            except asyncio.CancelledError:
                break

    async def async_send_start(self) -> bool:
        self._stopping_until = 0.0
        new_data = dict(self.data)
        new_data["belt_running"] = True
        self.async_set_updated_data(new_data)

        ok = await self._enqueue_cmd(bytes([CMD_START_OR_RESUME]))
        if not ok:
            # Cofamy optymistyczny stan, skoro komenda się nie powiodła
            rollback = dict(self.data)
            rollback["belt_running"] = False
            self.async_set_updated_data(rollback)
        return ok

    async def async_send_stop(self, emergency: bool = False) -> bool:
        self._pending_target_speed = None
        self._enforce_attempts = 0
        self._stopping_until = time.monotonic() + 4.5

        while not self._cmd_queue.empty():
            _, fut = self._cmd_queue.get_nowait()
            if fut and not fut.done():
                fut.set_result(False)
            self._cmd_queue.task_done()

        new_data = dict(self.data)
        new_data["belt_running"] = False
        self.async_set_updated_data(new_data)

        payload = bytes([CMD_STOP_OR_PAUSE, 0x01])
        if emergency:
            return await self._write_control_point(payload)
        return await self._enqueue_cmd(payload)

    async def async_set_target_speed(self, speed_kmh: float) -> bool:
        clamped = max(MIN_SPEED, min(MAX_SPEED, round(speed_kmh, 1)))
        self._stopping_until = 0.0
        self._pending_target_speed = clamped
        self._enforce_attempts = 0

        new_data = dict(self.data)
        new_data["target_speed"] = clamped
        new_data["belt_running"] = True
        self.async_set_updated_data(new_data)

        if self.data.get("speed", 0.0) == 0.0:
            await self._enqueue_cmd(bytes([CMD_START_OR_RESUME]))

        speed_raw = int(round(clamped * 100))
        payload = struct.pack("<BH", CMD_SET_TARGET_SPEED, speed_raw)
        return await self._enqueue_cmd(payload)
