"""Tests for the Decoflame config flow."""
from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.decoflame.config_flow import _discover_gatt_characteristics
from custom_components.decoflame.const import (
    CONF_ADDRESS,
    CONF_READ_CHAR_UUID,
    CONF_WRITE_CHAR_UUID,
    DEFAULT_NAME,
    DOMAIN)

from . import ADDRESS, READ_CHAR, WRITE_CHAR, make_client

INTEGRATION_DIR = Path(__file__).parent.parent / "custom_components" / DOMAIN
TRANSLATION_FILES = ["strings.json", "translations/en.json", "translations/da.json"]


@pytest.fixture(autouse=True)
def bluetooth(enable_bluetooth: None) -> None:
    """The flow looks up discovered devices through the Bluetooth manager."""


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[AsyncMock]:
    """Do not set up the coordinator when the flow creates an entry."""
    with patch("custom_components.decoflame.async_setup_entry", return_value=True) as mock:
        yield mock


@pytest.fixture
def mock_gatt_discovery() -> Generator[AsyncMock]:
    with patch(
        "custom_components.decoflame.config_flow._discover_gatt_characteristics",
        return_value=(WRITE_CHAR, READ_CHAR)) as mock:
        yield mock


def _schema_key(result: dict, name: str) -> vol.Marker:
    return next(key for key in result["data_schema"].schema if key == name)


async def _start_manual(hass: HomeAssistant) -> dict:
    """With nothing discovered, the flow opens on manual entry."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    return result


async def test_manual_address_field_is_empty(hass: HomeAssistant) -> None:
    result = await _start_manual(hass)
    assert _schema_key(result, CONF_ADDRESS).default is vol.UNDEFINED
    assert result["errors"] == {}


async def test_invalid_address_shows_error(hass: HomeAssistant, mock_gatt_discovery: AsyncMock) -> None:
    result = await _start_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "AA:BB:CC:DD:EE", CONF_NAME: DEFAULT_NAME})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {CONF_ADDRESS: "invalid_mac"}
    mock_gatt_discovery.assert_not_called()


async def test_failed_connection_keeps_address(hass: HomeAssistant, mock_gatt_discovery: AsyncMock) -> None:
    mock_gatt_discovery.return_value = None
    result = await _start_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS.lower(), CONF_NAME: "Living room"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert result["errors"] == {"base": "cannot_connect"}
    assert _schema_key(result, CONF_ADDRESS).default() == ADDRESS
    assert _schema_key(result, CONF_NAME).default() == "Living room"


async def test_manual_setup_creates_entry(hass: HomeAssistant, mock_gatt_discovery: AsyncMock) -> None:
    result = await _start_manual(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS, CONF_NAME: "Living room"})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living room"
    assert result["data"] == {CONF_ADDRESS: ADDRESS,
                              CONF_NAME: "Living room",
                              CONF_WRITE_CHAR_UUID: WRITE_CHAR,
                              CONF_READ_CHAR_UUID: READ_CHAR}
    assert result["result"].unique_id == ADDRESS


async def test_discovered_devices_and_manual_option(hass: HomeAssistant, inject_advertisement) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["description_placeholders"] == {"count": "1"}

    config = result["data_schema"].schema[CONF_ADDRESS].config
    assert config["translation_key"] == "address"
    assert [option["value"] for option in config["options"]] == [ADDRESS, "manual"]
    assert config["options"][0]["label"] == f"Decoflame ({ADDRESS})"


async def test_manual_option_leads_to_manual_entry(hass: HomeAssistant, inject_advertisement) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "manual"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "manual"
    assert _schema_key(result, CONF_ADDRESS).default is vol.UNDEFINED


async def test_discovered_device_creates_entry(
    hass: HomeAssistant,
    inject_advertisement,
    mock_gatt_discovery: AsyncMock) -> None:
    inject_advertisement()
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: ADDRESS})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Decoflame"
    assert result["data"][CONF_ADDRESS] == ADDRESS
    assert result["data"][CONF_WRITE_CHAR_UUID] == WRITE_CHAR


@pytest.mark.parametrize("path", TRANSLATION_FILES)
def test_manual_option_is_translated(path: str) -> None:
    translations = json.loads((INTEGRATION_DIR / path).read_text(encoding="utf-8"))
    assert translations["selector"]["address"]["options"]["manual"]


def _characteristic(uuid: str, properties: list[str]) -> MagicMock:
    return MagicMock(uuid=uuid, properties=properties)


async def test_gatt_discovery_returns_write_and_read(hass: HomeAssistant) -> None:
    client = make_client()
    client.services = [MagicMock(characteristics=[
        _characteristic(WRITE_CHAR, ["write"]),
        _characteristic(READ_CHAR, ["read", "write"])])]
    with (
        patch(
            "custom_components.decoflame.config_flow.async_ble_device_from_address",
            return_value=MagicMock()),
        patch(
            "custom_components.decoflame.config_flow.establish_connection",
            return_value=client)):
        assert await _discover_gatt_characteristics(hass, ADDRESS) == (WRITE_CHAR, READ_CHAR)


async def test_gatt_discovery_without_write_characteristic(hass: HomeAssistant) -> None:
    client = make_client()
    client.services = [MagicMock(characteristics=[_characteristic(READ_CHAR, ["read", "write"])])]
    with (
        patch(
            "custom_components.decoflame.config_flow.async_ble_device_from_address",
            return_value=MagicMock()),
        patch(
            "custom_components.decoflame.config_flow.establish_connection",
            return_value=client)):
        assert await _discover_gatt_characteristics(hass, ADDRESS) is None
