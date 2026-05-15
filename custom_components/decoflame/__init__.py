"""Decoflame BLE fireplace integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    BLE_DELAY_AFTER_CONNECT_S,
    BLE_DELAY_AFTER_WRITE_S,
    CONF_ADDRESS,
    CONF_READ_CHAR_UUID,
    CONF_WRITE_CHAR_UUID,
    DOMAIN,
    ECHO_TO_STATE,
    OFFLINE_TIMEOUT_SECONDS,
    PING_INTERVAL_SECONDS)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BINARY_SENSOR]


class DecoflameCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages BLE connection, command dispatch, and connectivity state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=entry.data.get(CONF_NAME, DOMAIN),
            update_interval=timedelta(seconds=PING_INTERVAL_SECONDS))
        self.entry = entry
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
        self._last_seen: datetime | None = None
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
    def connected(self) -> bool:
        if self._last_seen is None:
            return False
        age = (datetime.now() - self._last_seen).total_seconds()
        return age < OFFLINE_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hook — called on schedule (ping)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Read device state to keep connectivity and state fresh."""
        reachable = await self._read_state()
        if reachable:
            self._last_seen = datetime.now()
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
                self._last_seen = datetime.now()
            except (BleakError, asyncio.TimeoutError) as err:
                raise UpdateFailed(f"BLE write failed: {err}") from err

    async def async_turn_on(self) -> None:
        from .const import CMD_ON
        await self.send_command(CMD_ON)
        self._is_on = True
        self.async_update_listeners()

    async def async_turn_off(self) -> None:
        from .const import CMD_OFF
        await self.send_command(CMD_OFF)
        self._is_on = False
        self.async_update_listeners()

    async def async_set_flame_level(self, level: str) -> None:
        from .const import FLAME_LEVEL_COMMANDS
        await self.send_command(FLAME_LEVEL_COMMANDS[level])
        self._flame_level = level
        self.async_update_listeners()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Decoflame from a config entry."""
    coordinator = DecoflameCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False
