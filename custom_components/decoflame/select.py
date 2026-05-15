"""Select platform for Decoflame — flammeniveau."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DecoflameCoordinator
from .const import DOMAIN, FLAME_LEVELS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback) -> None:
    coordinator: DecoflameCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DecoflameSelect(coordinator, entry)])


class DecoflameSelect(CoordinatorEntity[DecoflameCoordinator], SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "flame_level"
    _attr_options = FLAME_LEVELS

    def __init__(self, coordinator: DecoflameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_flame_level"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": entry.title,
            "manufacturer": "Decoflame"}

    @property
    def current_option(self) -> str:
        return self.coordinator.flame_level

    @property
    def available(self) -> bool:
        return self.coordinator.connected

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_flame_level(option)
