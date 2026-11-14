"""Sensor platform for Decoflame — fireplace state, fuel level and consumption."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfVolumeFlowRate
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
    async_add_entities([
        DecoflameStateSensor(coordinator, entry),
        DecoflameFuelLevelSensor(coordinator, entry),
        DecoflameFuelRateSensor(coordinator, entry)])


class DecoflameSensor(CoordinatorEntity[DecoflameCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _unique_id_suffix: str

    def __init__(self, coordinator: DecoflameCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{self._unique_id_suffix}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.address)},
            "name": entry.title,
            "manufacturer": "Decoflame"}


class DecoflameStateSensor(DecoflameSensor):
    _attr_translation_key = "state"
    _unique_id_suffix = "state"

    @property
    def native_value(self) -> str:
        return self.coordinator.state


class DecoflameFuelLevelSensor(DecoflameSensor):
    """Fuel left in the tank, as reported in the advertisement."""

    _attr_translation_key = "fuel_level"
    _unique_id_suffix = "fuel_level"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.coordinator.fuel_level


class DecoflameFuelRateSensor(DecoflameSensor):
    """Current fuel consumption, as reported in the advertisement."""

    _attr_translation_key = "fuel_rate"
    _unique_id_suffix = "fuel_rate"
    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_native_unit_of_measurement = UnitOfVolumeFlowRate.LITERS_PER_HOUR
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        return self.coordinator.fuel_rate
