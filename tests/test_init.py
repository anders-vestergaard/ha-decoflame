"""Tests for connectivity and commands in the Decoflame coordinator."""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from bleak.backends.device import BLEDevice
from bleak.exc import BleakCharacteristicNotFoundError, BleakError
from bleak_retry_connector import BleakClientWithServiceCache
from habluetooth.const import UNAVAILABLE_TRACK_SECONDS
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from custom_components.decoflame import DecoflameCoordinator
from custom_components.decoflame.const import CMD_ON, DOMAIN

from . import ADDRESS, make_client

UNIQUE_ID_SUFFIXES = {
    "switch": "switch",
    "select": "flame_level",
    "binary_sensor": "connected",
    "sensor": "state"}

# A real advertisement from the fireplace at flame level 5 with a full tank:
# fuel 96 % (0x60), consumption 0.9 L/h (0x09)
MFR_DATA_LEVEL_5_FULL = bytes.fromhex("af059cca a4a5a6a7 a8a9aaab 05 60 09 00 0000f0".replace(" ", ""))


def _entity_id(hass: HomeAssistant, platform: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{ADDRESS}_{UNIQUE_ID_SUFFIXES[platform]}")
    assert entity_id is not None
    return entity_id


def _state(hass: HomeAssistant, platform: str) -> str:
    return hass.states.get(_entity_id(hass, platform)).state


async def test_unique_ids_unchanged(hass: HomeAssistant, coordinator: DecoflameCoordinator) -> None:
    for platform in UNIQUE_ID_SUFFIXES:
        _entity_id(hass, platform)


async def test_advertisement_marks_connected(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement) -> None:
    assert not coordinator.connected
    assert _state(hass, "binary_sensor") == STATE_OFF

    inject_advertisement()
    await hass.async_block_till_done()

    assert coordinator.connected
    assert _state(hass, "binary_sensor") == STATE_ON
    assert _state(hass, "sensor") == "on"
    assert _state(hass, "select") == "3"


async def test_identical_advertisements_stay_connected_and_are_logged(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement,
    caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="custom_components.decoflame")
    inject_advertisement()
    await hass.async_block_till_done()
    assert caplog.text.count("ADV mfr_data (14 bytes)") == 1

    # Home Assistant does not call the callback for identical data
    inject_advertisement()
    await hass.async_block_till_done()
    assert caplog.text.count("ADV mfr_data (14 bytes)") == 1

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.connected
    assert "ADV last seen" in caplog.text
    assert "03[12] 00[13]" in caplog.text.split("ADV last seen")[-1]


async def test_home_assistant_unavailable_marks_offline(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement) -> None:
    inject_advertisement()
    await hass.async_block_till_done()
    assert coordinator.connected

    # The device has not been seen by any scanner, so Home Assistant's
    # periodic sweep reports it unavailable.
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS + 1))
    await hass.async_block_till_done()

    assert not coordinator.connected
    assert _state(hass, "binary_sensor") == STATE_OFF
    assert _state(hass, "switch") == STATE_UNAVAILABLE
    assert _state(hass, "select") == STATE_UNAVAILABLE

    # Back at the next advertisement, even with the same data as before
    inject_advertisement()
    await hass.async_block_till_done()
    assert coordinator.connected
    assert _state(hass, "binary_sensor") == STATE_ON


async def test_successful_gatt_read_restores_connected(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    mock_establish_connection: MagicMock) -> None:
    assert not coordinator.connected
    client = make_client(echo=bytes([0x00, 0x10]))
    mock_establish_connection.side_effect = None
    mock_establish_connection.return_value = client

    with (
        patch(
            "custom_components.decoflame.async_ble_device_from_address",
            return_value=BLEDevice(ADDRESS, "Decoflame", {})),
        patch("custom_components.decoflame.time") as mock_time):
        # Past the backoff from the failed read during setup
        mock_time.monotonic.return_value = time.monotonic() + 3600
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    mock_establish_connection.assert_called_once()
    assert coordinator.connected
    assert coordinator.read_backoff == 60
    assert _state(hass, "binary_sensor") == STATE_ON
    assert _state(hass, "sensor") == "on"


async def test_read_backoff_doubles_up_to_ten_minutes(
    hass: HomeAssistant,
    enable_bluetooth: None,
    mock_establish_connection: MagicMock,
    mock_entry,
    inject_advertisement,
    caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger="custom_components.decoflame")
    with patch("custom_components.decoflame.time") as mock_time:
        now = 10_000.0
        mock_time.monotonic.return_value = now
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()
        coordinator: DecoflameCoordinator = hass.data[DOMAIN][mock_entry.entry_id]

        def attempts() -> int:
            return caplog.text.count("GATT read from")

        assert attempts() == 1
        assert "not seen by any connectable Bluetooth adapter or proxy" in caplog.text
        assert coordinator.last_gatt_error is not None

        # Waits after each failed attempt: 60, 120, 240, 480, then capped at 600
        for wait in (60, 120, 240, 480, 600, 600):
            count = attempts()
            mock_time.monotonic.return_value = now + wait - 30
            await coordinator.async_refresh()
            assert attempts() == count, f"read attempted before {wait}s"

            now += wait
            mock_time.monotonic.return_value = now
            await coordinator.async_refresh()
            assert attempts() == count + 1, f"no read after {wait}s"

        assert coordinator.read_backoff == 600
        mock_establish_connection.assert_not_called()

        # Any contact resets the backoff
        inject_advertisement()
        await hass.async_block_till_done()
        assert coordinator.connected
        assert coordinator.read_backoff == 60

    await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()


async def test_command_failure_raises_translated_error(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement,
    mock_establish_connection: MagicMock) -> None:
    inject_advertisement()
    await hass.async_block_till_done()
    mock_establish_connection.side_effect = BleakError("connection slots exhausted")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": _entity_id(hass, "switch")},
            blocking=True)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {"error": "connection slots exhausted"}
    assert "connection slots exhausted" in coordinator.last_gatt_error
    # State is unchanged when the command did not go through
    assert _state(hass, "switch") == STATE_ON
    assert coordinator.state == "on"


async def test_command_without_device_raises_translated_error(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator) -> None:
    with pytest.raises(HomeAssistantError) as exc_info:
        await coordinator.async_turn_on()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "device_not_found"


async def test_command_clears_service_cache_and_retries_once(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement,
    mock_establish_connection: MagicMock) -> None:
    inject_advertisement(mfr_data=bytes(12) + bytes([0x07, 0x1C]))
    await hass.async_block_till_done()
    assert coordinator.state == "off"

    client = make_client(echo=CMD_ON)
    client.write_gatt_char.side_effect = [BleakCharacteristicNotFoundError("fff1"), None]
    mock_establish_connection.side_effect = None
    mock_establish_connection.return_value = client

    await coordinator.async_turn_on()

    assert mock_establish_connection.call_count == 2
    for call in mock_establish_connection.call_args_list:
        assert call.args[0] is BleakClientWithServiceCache
        assert "use_services_cache" not in call.kwargs
    client.clear_cache.assert_awaited_once()
    assert client.write_gatt_char.await_count == 2
    assert coordinator.state == "warming_up"


async def test_command_gives_up_after_one_retry(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement,
    mock_establish_connection: MagicMock) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    client = make_client()
    client.write_gatt_char.side_effect = BleakCharacteristicNotFoundError("fff1")
    mock_establish_connection.side_effect = None
    mock_establish_connection.return_value = client

    with pytest.raises(HomeAssistantError) as exc_info:
        await coordinator.async_turn_off()

    assert exc_info.value.translation_key == "command_failed"
    assert mock_establish_connection.call_count == 2


async def test_switch_available_while_home_assistant_sees_address(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    coordinator._connected = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert _state(hass, "binary_sensor") == STATE_OFF
    assert _state(hass, "select") == STATE_UNAVAILABLE
    assert _state(hass, "switch") != STATE_UNAVAILABLE


@pytest.mark.parametrize("path", ["strings.json", "translations/da.json", "translations/en.json"])
def test_error_messages_are_translated(path: str) -> None:
    integration_dir = Path(__file__).parent.parent / "custom_components" / DOMAIN
    exceptions = json.loads((integration_dir / path).read_text(encoding="utf-8"))["exceptions"]
    assert exceptions["device_not_found"]["message"]
    assert "{error}" in exceptions["command_failed"]["message"]


def _sensor_state(hass: HomeAssistant, suffix: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{ADDRESS}_{suffix}")
    assert entity_id is not None
    return hass.states.get(entity_id).state


async def test_fuel_level_and_rate_from_advertisement(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement) -> None:
    inject_advertisement(MFR_DATA_LEVEL_5_FULL)
    await hass.async_block_till_done()

    assert coordinator.fuel_level == 96
    assert coordinator.fuel_rate == 0.9
    assert _sensor_state(hass, "fuel_level") == "96"
    assert float(_sensor_state(hass, "fuel_rate")) == 0.9
    assert _state(hass, "select") == "5"


async def test_fuel_rate_unknown_for_short_advertisement(
    hass: HomeAssistant,
    coordinator: DecoflameCoordinator,
    inject_advertisement) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    assert coordinator.fuel_rate is None
    assert _sensor_state(hass, "fuel_rate") == "unknown"


def test_flame_levels_ordered_by_output() -> None:
    from custom_components.decoflame.const import FLAME_LEVELS
    assert FLAME_LEVELS == ["ECO", "1", "2", "3", "4", "5"]
