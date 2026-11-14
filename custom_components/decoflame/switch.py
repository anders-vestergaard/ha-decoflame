"""Switch platform for Decoflame — tænd/sluk."""
from __future__ import annotations

from homeassistant.components.bluetooth import async_address_present
from homeassistant.components.switch import SwitchEntity
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
    async_add_entities([DecoflameSwitch(coordinator, entry)])


class DecoflameSwitch(CoordinatorEntity[DecoflameCoordinator], SwitchEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "fireplace"

    def __init__(self, coordinator: DecoflameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": entry.title,
            "manufacturer": "Decoflame"}

    @property
    def is_on(self) -> bool:
        return self.coordinator.is_on

    @property
    def available(self) -> bool:
        # Usable while Home Assistant can still connect, so a command can wake the fireplace
        return self.coordinator.connected or async_address_present(
            self.hass, self.coordinator.address, connectable=True)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_turn_off()
