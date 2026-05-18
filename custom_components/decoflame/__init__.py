"""Decoflame BLE fireplace integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_register_callback)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ADV_COMPANY_ID,
    ADV_FLAME_LEVEL,
    ADV_FLAME_TURNING_OFF,
    ADV_FLAME_WARMING,
    ADV_FLAME_WARMING2,
    ADV_STATUS_OFF,
    ADV_TIMEOUT_SECONDS,
    BLE_DELAY_AFTER_CONNECT_S,
    BLE_DELAY_AFTER_WRITE_S,
    CMD_OFF,
    CMD_ON,
    CONF_ADDRESS,
    CONF_READ_CHAR_UUID,
    CONF_WRITE_CHAR_UUID,
    DOMAIN,
    ECHO_TO_STATE,
    FLAME_LEVEL_COMMANDS,
    PING_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.SENSOR]


class DecoflameCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages BLE connection, command dispatch, and connectivity state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data.get(CONF_NAME, DOMAIN),
            update_interval=timedelta(seconds=PING_INTERVAL_SECONDS))
        self.address: str = entry.data[CONF_ADDRESS]
        self.write_char: str = entry.data[CONF_WRITE_CHAR_UUID]
        self.read_char: str | None = entry.data.get(CONF_READ_CHAR_UUID)

        _LOGGER.info(
            "Decoflame %s — write: %s  read: %s",
            self.address,
            self.write_char,
            self.read_char)

        self._is_on: bool = False
        self._flame_level: str = "1"
        self._state: str = "off"
        self._last_advertisement: datetime | None = None
        self._turn_off_cancel = None
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Public state (read by entities)
    # ------------------------------------------------------------------

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def flame_level(self) -> str:
        return self._flame_level

    @property
    def state(self) -> str:
        return self._state

    @property
    def connected(self) -> bool:
        if self._last_advertisement is None:
            return False
        return (datetime.now() - self._last_advertisement).total_seconds() < ADV_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # Advertisement callback
    # ------------------------------------------------------------------

    @callback
    def handle_advertisement(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange) -> None:
        self._last_advertisement = datetime.now()
        mfr_data = service_info.manufacturer_data.get(ADV_COMPANY_ID)
        if mfr_data is None or len(mfr_data) < 14:
            self.async_update_listeners()
            return

        _LOGGER.debug(
            "ADV mfr_data (%d bytes): %s",
            len(mfr_data),
            " ".join(f"{b:02X}[{i}]" for i, b in enumerate(mfr_data)))

        flame_byte = mfr_data[12]
        status_byte = mfr_data[13]

        if flame_byte == ADV_FLAME_TURNING_OFF:
            self._state = "turning_off"
            self._is_on = False
        elif flame_byte == ADV_FLAME_WARMING and status_byte == ADV_STATUS_OFF:
            if self._state != "warming_up":
                self._state = "off"
                self._is_on = False
        elif flame_byte in (ADV_FLAME_WARMING, ADV_FLAME_WARMING2):
            if self._state in ("warming_up", "on"):
                self._state = "warming_up"
                self._is_on = True
            else:
                self.async_update_listeners()
                return
        elif flame_byte in ADV_FLAME_LEVEL:
            self._state = "on"
            self._is_on = True
            self._flame_level = ADV_FLAME_LEVEL[flame_byte]

        self.async_update_listeners()

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hook — called on schedule (ping)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Read device state. Skip BLE connection if advertisement is recent."""
        if self.connected:
            return {
                "is_on": self._is_on,
                "flame_level": self._flame_level,
                "connected": self.connected}

        await self._read_state()
        return {
            "is_on": self._is_on,
            "flame_level": self._flame_level,
            "connected": self.connected}

    # ------------------------------------------------------------------
    # BLE helpers
    # ------------------------------------------------------------------

    async def _get_ble_device(self):
        return async_ble_device_from_address(self.hass, self.address, connectable=True)

    async def _read_state(self) -> bool:
        """Connect, read state from echo char, disconnect. Returns True on success."""
        async with self._lock:
            try:
                ble_device = await self._get_ble_device()
                if ble_device is None:
                    return False
                client = await establish_connection(
                    BleakClient, ble_device, ble_device.address)
                async with client:
                    if self.read_char:
                        echo = bytes(await client.read_gatt_char(self.read_char))
                        if len(echo) >= 2:
                            last_cmd = bytes(echo[-2:])
                            if last_cmd in ECHO_TO_STATE:
                                is_on, level = ECHO_TO_STATE[last_cmd]
                                self._is_on = is_on
                                self._state = "on" if is_on else "off"
                                if level is not None:
                                    self._flame_level = level
                                _LOGGER.debug(
                                    "State from device: is_on=%s flame=%s (echo=%s)",
                                    is_on,
                                    level,
                                    echo.hex())
                return True
            except (BleakError, asyncio.TimeoutError):
                return False

    async def send_command(self, command: bytes) -> None:
        """Connect, write command, read-back verify, disconnect."""
        async with self._lock:
            ble_device = await self._get_ble_device()
            if ble_device is None:
                raise UpdateFailed(f"BLE device {self.address} not found")
            _LOGGER.debug(
                "send_command %s via %s",
                command.hex(),
                getattr(ble_device, "source", "unknown"))
            try:
                client = await establish_connection(
                    BleakClient,
                    ble_device,
                    ble_device.address,
                    use_services_cache=False)
                async with client:
                    await asyncio.sleep(BLE_DELAY_AFTER_CONNECT_S)
                    _LOGGER.debug("send_command %s to %s", command.hex(), ble_device.address)
                    await client.write_gatt_char(
                        self.write_char,
                        command,
                        response=True)
                    if self.read_char:
                        echo = bytes(await client.read_gatt_char(self.read_char))
                        last = echo[-2:] if len(echo) >= 2 else b""
                        if last == command:
                            _LOGGER.debug("Write verified: echo=%s", echo.hex())
                        else:
                            _LOGGER.warning(
                                "Write mismatch — sent %s, echo=%s",
                                command.hex(),
                                echo.hex())
                    await asyncio.sleep(BLE_DELAY_AFTER_WRITE_S)
            except (BleakError, asyncio.TimeoutError) as err:
                raise UpdateFailed(f"BLE write failed: {err}") from err

    @callback
    def _on_turn_off_timeout(self, _now) -> None:
        if self._state == "turning_off":
            _LOGGER.debug("Forcing off state after 420s timeout")
            self._state = "off"
            self._is_on = False
            self.async_update_listeners()
        self._turn_off_cancel = None

    def _cancel_turn_off_timeout(self) -> None:
        if self._turn_off_cancel is not None:
            self._turn_off_cancel()
            self._turn_off_cancel = None

    async def async_turn_on(self) -> None:
        self._cancel_turn_off_timeout()
        await self.send_command(CMD_ON)
        self._is_on = True
        self._state = "warming_up"
        self.async_update_listeners()

    async def async_turn_off(self) -> None:
        self._cancel_turn_off_timeout()
        await self.send_command(CMD_OFF)
        self._is_on = False
        self._state = "turning_off"
        self._turn_off_cancel = async_call_later(self.hass, 420, self._on_turn_off_timeout)
        self.async_update_listeners()

    async def async_set_flame_level(self, level: str) -> None:
        self._cancel_turn_off_timeout()
        await self.send_command(FLAME_LEVEL_COMMANDS[level])
        self._flame_level = level
        self.async_update_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Decoflame from a config entry."""
    coordinator = DecoflameCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    cancel_advertisement = async_register_callback(
        hass,
        coordinator.handle_advertisement,
        BluetoothCallbackMatcher(address=coordinator.address),
        BluetoothScanningMode.ACTIVE)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(cancel_advertisement)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: DecoflameCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator._cancel_turn_off_timeout()
        return True
    return False
