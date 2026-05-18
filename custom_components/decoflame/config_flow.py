"""Config flow for Decoflame."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak import BleakClient, BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    async_discovered_service_info)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ADDRESS,
    CONF_READ_CHAR_UUID,
    CONF_WRITE_CHAR_UUID,
    DECOFLAME_NAME_PREFIX,
    DEFAULT_NAME,
    DOMAIN)

_LOGGER = logging.getLogger(__name__)


def _is_decoflame_device(info: BluetoothServiceInfoBleak) -> bool:
    return DECOFLAME_NAME_PREFIX in (info.name or "").lower()


async def _discover_gatt_characteristics(
    hass: HomeAssistant,
    address: str) -> tuple[str, str, str | None] | None:
    """Connect via proxy and discover service + write + read characteristic UUIDs."""
    try:
        ble_device = async_ble_device_from_address(hass, address, connectable=True)
        if ble_device is None:
            _LOGGER.warning("BLE device %s not found via proxy", address)
            return None

        client = await establish_connection(BleakClient, ble_device, address)
        async with client:
            services = list(client.services)

            service_uuid: str | None = None
            write_uuid: str | None = None
            read_uuid: str | None = None

            for service in services:
                for char in service.characteristics:
                    props = set(char.properties)
                    if props == {"write"}:
                        write_uuid = str(char.uuid)
                        service_uuid = str(service.uuid)
                    elif props == {"read", "write"}:
                        read_uuid = str(char.uuid)

            _LOGGER.info(
                "GATT discovery %s — service=%s  write=%s  read=%s",
                address,
                service_uuid,
                write_uuid,
                read_uuid)

            if service_uuid and write_uuid:
                return service_uuid, write_uuid, read_uuid
    except (BleakError, Exception) as err:
        _LOGGER.warning("GATT discovery failed for %s: %s", address, err)
    return None


class DecoflameConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Decoflame."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._address: str | None = None
        self._name: str = DEFAULT_NAME

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        discovered: dict[str, str] = {}
        for info in async_discovered_service_info(self.hass, connectable=True):
            if _is_decoflame_device(info):
                discovered[info.address] = f"{info.name} ({info.address})"
                self._discovered_devices[info.address] = info

        if not discovered:
            return await self.async_step_manual()

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == "manual":
                return await self.async_step_manual()
            self._address = address
            info = self._discovered_devices[address]
            self._name = info.name or DEFAULT_NAME
            return await self.async_step_connect()

        choices = {**discovered, "manual": "Indtast MAC manuelt"}
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(choices)}),
            description_placeholders={"count": str(len(discovered))})

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            parts = address.split(":")
            if len(parts) != 6 or not all(
                len(p) == 2 and all(c in "0123456789ABCDEF" for c in p)
                for p in parts):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                self._address = address
                self._name = user_input.get(CONF_NAME, DEFAULT_NAME)
                return await self.async_step_connect()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default="0C:43:14:9C:05:AF"): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}),
            errors=errors)

    async def async_step_connect(
        self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._address is not None

        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()

        result = await _discover_gatt_characteristics(self.hass, self._address)
        if result is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS, default=self._address): str,
                    vol.Optional(CONF_NAME, default=self._name): str}),
                errors={"base": "cannot_connect"})

        service_uuid, write_uuid, read_uuid = result

        data: dict[str, Any] = {
            CONF_ADDRESS: self._address,
            CONF_NAME: self._name,
            CONF_WRITE_CHAR_UUID: write_uuid}
        if read_uuid:
            data[CONF_READ_CHAR_UUID] = read_uuid

        return self.async_create_entry(title=self._name, data=data)

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        if not _is_decoflame_device(discovery_info):
            return self.async_abort(reason="not_supported")

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._address = discovery_info.address
        self._name = discovery_info.name or DEFAULT_NAME
        self._discovered_devices[discovery_info.address] = discovery_info

        self.context["title_placeholders"] = {
            "name": self._name,
            "address": self._address}

        return await self.async_step_connect()
