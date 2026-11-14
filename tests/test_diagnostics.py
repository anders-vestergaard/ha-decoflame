"""Tests for Decoflame diagnostics."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from bleak.exc import BleakError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.decoflame import DecoflameCoordinator

from . import ADDRESS


async def test_diagnostics_without_address(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    coordinator: DecoflameCoordinator,
    mock_entry: MockConfigEntry,
    inject_advertisement,
    mock_establish_connection: MagicMock) -> None:
    inject_advertisement(rssi=-71)
    await hass.async_block_till_done()
    mock_establish_connection.side_effect = BleakError(f"{ADDRESS.lower()}: out of connection slots")
    with pytest.raises(HomeAssistantError):
        await coordinator.async_turn_off()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, mock_entry)

    assert ADDRESS.lower() not in json.dumps(diagnostics).lower()
    assert diagnostics["connected"] is True
    advertisement = diagnostics["advertisement"]
    assert advertisement["manufacturer_data"] == "00 00 00 00 00 00 00 00 00 00 00 00 03 00"
    assert advertisement["source"] == "local"
    assert advertisement["rssi"] == -71
    assert advertisement["seconds_since_last"] >= 0
    assert "out of connection slots" in diagnostics["gatt"]["last_error"]
    assert diagnostics["gatt"]["seconds_since_last_error"] >= 0
