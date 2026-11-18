import asyncio
import logging
import struct
from datetime import timedelta

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    TREADMILL_DATA_CHAR_UUID,
    CONTROL_POINT_CHAR_UUID,
)

_LOGGER = logging.getLogger(__name__)


class MobvoiTreadmillCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{address}",
            update_interval=timedelta(seconds=5),
        )
        self.address = address
        self._client: BleakClient | None = None
        self._lock = asyncio.Lock()
        self._keep_alive_task: asyncio.Task | None = None
        self._is_awake: bool = True
        self.data = {
            "speed": 0.0,
            "distance": 0,
            "calories": 0,
            "elapsed_time": 0,
            "running": False,
            "awake": True,
        }

    def _notification_handler(self, sender, data: bytearray) -> None:
        if len(data) < 4:
            return
        flags = struct.unpack_from("<H", data, 0)[0]
        offset = 2

        speed = 0.0
        if not (flags & (1 << 0)):
            if len(data) >= offset + 2:
                raw_speed = struct.unpack_from("<H", data, offset)[0]
                speed = round(raw_speed * 0.01, 2)
                offset += 2

        if flags & (1 << 1):
            offset += 2

        distance = self.data.get("distance", 0)
        if flags & (1 << 2):
            if len(data) >= offset + 3:
                distance = int.from_bytes(data[offset : offset + 3], "little")
                offset += 3

        if flags & (1 << 3):
            offset += 4
        if flags & (1 << 4):
            offset += 4
        if flags & (1 << 5):
            offset += 1
        if flags & (1 << 6):
            offset += 1

        calories = self.data.get("calories", 0)
        if flags & (1 << 7):
            if len(data) >= offset + 5:
                calories = struct.unpack_from("<H", data, offset)[0]
                offset += 5

        if flags & (1 << 8):
            offset += 1
        if flags & (1 << 9):
            offset += 1

        elapsed_time = self.data.get("elapsed_time", 0)
        if flags & (1 << 10):
            if len(data) >= offset + 2:
                elapsed_time = struct.unpack_from("<H", data, offset)[0]
                offset += 2

        self._is_awake = True
        new_data = {
            "speed": speed,
            "distance": distance,
            "calories": calories,
            "elapsed_time": elapsed_time,
            "running": speed > 0.0,
            "awake": True,
        }
        self.async_set_updated_data(new_data)

    async def _ensure_connected(self) -> bool:
        if self._client and self._client.is_connected:
            return True

        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if not ble_device:
            return False

        try:
            self._client = await establish_connection(
                BleakClient, ble_device, self.address
            )
            await self._client.start_notify(
                TREADMILL_DATA_CHAR_UUID, self._notification_handler
            )
            _LOGGER.info("Połączono z bieżnią Mobvoi (%s)", self.address)
            return True
        except Exception as err:
            _LOGGER.debug("Nie udało się połączyć z bieżnią: %s", err)
            self._client = None
            return False

    async def _async_update_data(self):
        connected = await self._ensure_connected()
        if not connected:
            self.data["speed"] = 0.0
            self.data["running"] = False
            self.data["awake"] = False
        return self.data

    async def send_command(self, payload: bytes) -> bool:
        async with self._lock:
            if not await self._ensure_connected():
                _LOGGER.warning("Brak połączenia BLE z bieżnią - próba wybudzenia nieudana")
                return False
            try:
                await self._client.write_gatt_char(
                    CONTROL_POINT_CHAR_UUID, b"\x00", response=True
                )
                await asyncio.sleep(0.15)
                await self._client.write_gatt_char(
                    CONTROL_POINT_CHAR_UUID, payload, response=True
                )
                return True
            except BleakError as err:
                _LOGGER.error("Błąd wysyłania komendy FTMS: %s", err)
                self._client = None
                return False

    async def async_wake_up(self) -> None:
        """Wybudza ekran/kontroler bieżni z trybu uśpienia poprzez żądanie kontroli FTMS."""
        async with self._lock:
            if await self._ensure_connected():
                try:
                    await self._client.write_gatt_char(
                        CONTROL_POINT_CHAR_UUID, b"\x00", response=True
                    )
                    self._is_awake = True
                    self.data["awake"] = True
                    self.async_set_updated_data(self.data)
                    _LOGGER.info("Wysłano sygnał wybudzenia (Wake-up) do bieżni Mobvoi")
                except BleakError as err:
                    _LOGGER.debug("Błąd wybudzania bieżni: %s", err)

    async def async_sleep(self) -> None:
        """Zatrzymuje pas i przełącza stan w tryb uśpienia / czuwania."""
        await self.async_stop()
        self._is_awake = False
        self.data["awake"] = False
        self.data["running"] = False
        self.async_set_updated_data(self.data)

    async def async_start(self) -> None:
        await self.send_command(b"\x07")
        self._is_awake = True
        self.data["awake"] = True
        self.data["running"] = True
        self.async_set_updated_data(self.data)

    async def async_stop(self) -> None:
        await self.send_command(b"\x08\x01")
        self.data["running"] = False
        self.data["speed"] = 0.0
        self.async_set_updated_data(self.data)

    async def async_set_speed(self, speed_kmh: float) -> None:
        raw_val = int(round(speed_kmh * 100))
        payload = struct.pack("<BH", 0x02, raw_val)
        await self.send_command(payload)

    async def async_disconnect(self) -> None:
        if self._client and self._client.is_connected:
            await self._client.disconnect()
