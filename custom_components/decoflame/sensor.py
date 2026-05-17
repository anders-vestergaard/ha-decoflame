"""Sensor platform for Decoflame — fireplace state."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DecoflameCoordinator
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DecoflameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DecoflameStateSensor(coordinator, entry)])


class DecoflameStateSensor(CoordinatorEntity[DecoflameCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "state"

    def __init__(self, coordinator: DecoflameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_state"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": entry.title,
            "manufacturer": "Decoflame"}

    @property
    def native_value(self) -> str:
        return self.coordinator.state
