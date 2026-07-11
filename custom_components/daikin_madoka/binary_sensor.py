"""Support for Daikin Madoka binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MadokaCoordinator
from .entity import MadokaEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin Madoka binary sensors based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadokaFilterBinarySensor(coordinator)])


class MadokaFilterBinarySensor(MadokaEntity, BinarySensorEntity):
    """Binary sensor for the clean filter indicator."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Clean Filter"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_clean_filter"

    @property
    def is_on(self) -> bool | None:
        """Return True when the filter needs cleaning."""
        if self.controller.clean_filter_indicator.status is None:
            return None
        return self.controller.clean_filter_indicator.status.clean_filter_indicator
