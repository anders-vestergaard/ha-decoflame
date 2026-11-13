"""Diagnostics support for Decoflame."""
from __future__ import annotations

import re
import time
from typing import Any

from homeassistant.components.bluetooth import async_address_present, async_scanner_by_source
from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from . import DecoflameCoordinator
from .const import ADV_COMPANY_ID, CONF_ADDRESS, DOMAIN

TO_REDACT = {CONF_ADDRESS, CONF_NAME}


def _redact_address(text: str | None, address: str) -> str | None:
    """Bleak error messages often include the device address."""
    if text is None:
        return None
    return re.sub(re.escape(address), REDACTED, text, flags=re.IGNORECASE)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DecoflameCoordinator = hass.data[DOMAIN][entry.entry_id]
    now = time.monotonic()

    advertisement = None
    if (service_info := coordinator.last_service_info) is not None:
        mfr_data = service_info.manufacturer_data.get(ADV_COMPANY_ID)
        scanner = async_scanner_by_source(hass, service_info.source)
        advertisement = {
            "manufacturer_data": mfr_data.hex(" ") if mfr_data is not None else None,
            "source": service_info.source,
            "scanner": scanner.name if scanner is not None else None,
            "connectable": service_info.connectable,
            "rssi": service_info.rssi,
            "seconds_since_last": round(now - service_info.time, 1)}

    last_error_at = coordinator.last_gatt_error_at
    gatt = {
        "last_error": _redact_address(coordinator.last_gatt_error, coordinator.address),
        "seconds_since_last_error": round(now - last_error_at, 1) if last_error_at is not None else None,
        "read_backoff_seconds": coordinator.read_backoff,
        "seconds_until_next_read": max(0.0, round(coordinator.next_read_at - now, 1))}

    return async_redact_data(
        {"entry": dict(entry.data),
         "connected": coordinator.connected,
         "address_present": async_address_present(hass, coordinator.address, connectable=True),
         "state": coordinator.state,
         "is_on": coordinator.is_on,
         "flame_level": coordinator.flame_level,
         "advertisement": advertisement,
         "gatt": gatt},
        TO_REDACT)
