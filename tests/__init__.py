"""Tests for the Decoflame integration."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

from bleak.backends.device import BLEDevice

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

from custom_components.decoflame.const import ADV_COMPANY_ID

ADDRESS = "AA:BB:CC:DD:EE:FF"
WRITE_CHAR = "0000fff1-0000-1000-8000-00805f9b34fb"
READ_CHAR = "0000fff2-0000-1000-8000-00805f9b34fb"

# Flame level 3, burning
MFR_DATA_ON_LEVEL_3 = bytes(12) + bytes([0x03, 0x00])


def make_service_info(
    mfr_data: bytes = MFR_DATA_ON_LEVEL_3,
    rssi: int = -60,
    source: str = "local") -> BluetoothServiceInfoBleak:
    return BluetoothServiceInfoBleak(
        name="Decoflame",
        address=ADDRESS,
        rssi=rssi,
        manufacturer_data={ADV_COMPANY_ID: mfr_data},
        service_data={},
        service_uuids=[],
        source=source,
        device=BLEDevice(ADDRESS, "Decoflame", {}),
        advertisement=None,
        connectable=True,
        time=time.monotonic(),
        tx_power=None)


def make_client(echo: bytes | None = None) -> MagicMock:
    """A connected BLE client usable as an async context manager."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.write_gatt_char = AsyncMock()
    client.read_gatt_char = AsyncMock(return_value=bytearray(echo or b""))
    client.clear_cache = AsyncMock(return_value=True)
    return client
