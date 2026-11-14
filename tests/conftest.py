"""Fixtures for the Decoflame tests."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.bluetooth import async_get_advertisement_callback
from homeassistant.core import HomeAssistant

from custom_components.decoflame import DecoflameCoordinator
from custom_components.decoflame.const import (
    CONF_ADDRESS,
    CONF_READ_CHAR_UUID,
    CONF_WRITE_CHAR_UUID,
    DOMAIN)

from . import ADDRESS, MFR_DATA_ON_LEVEL_3, READ_CHAR, WRITE_CHAR, make_service_info


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture(autouse=True)
def no_ble_delays() -> Generator[None]:
    """Skip the fixed BLE delays around commands."""
    with (
        patch("custom_components.decoflame.BLE_DELAY_AFTER_CONNECT_S", 0),
        patch("custom_components.decoflame.BLE_DELAY_AFTER_WRITE_S", 0)):
        yield


@pytest.fixture
def mock_establish_connection() -> Generator[MagicMock]:
    """Fail loudly if a test connects without setting up a client."""
    with patch(
        "custom_components.decoflame.establish_connection",
        side_effect=AssertionError("unexpected GATT connection")) as mock:
        yield mock


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Fireplace",
        unique_id=ADDRESS,
        data={CONF_ADDRESS: ADDRESS,
              "name": "Fireplace",
              CONF_WRITE_CHAR_UUID: WRITE_CHAR,
              CONF_READ_CHAR_UUID: READ_CHAR})
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def coordinator(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_establish_connection: MagicMock,
    mock_entry: MockConfigEntry) -> AsyncGenerator[DecoflameCoordinator]:
    """Set up the integration and return its coordinator."""
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    yield hass.data[DOMAIN][mock_entry.entry_id]
    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture
def inject_advertisement(hass: HomeAssistant) -> Callable[..., None]:
    """Feed an advertisement to Home Assistant's Bluetooth manager."""

    def _inject(mfr_data: bytes = MFR_DATA_ON_LEVEL_3, rssi: int = -60) -> None:
        async_get_advertisement_callback(hass)(make_service_info(mfr_data, rssi))

    return _inject
