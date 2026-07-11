"""Support for Daikin Madoka buttons."""

from __future__ import annotations

import logging

from pymadoka.feature import ConnectionException
from pymadoka.features.clean_filter import ResetCleanFilterTimerStatus

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MadokaCoordinator
from .entity import MadokaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin Madoka buttons based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadokaResetFilterButton(coordinator)])


class MadokaResetFilterButton(MadokaEntity, ButtonEntity):
    """Button to reset the clean filter timer."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:air-filter"
    _attr_name = "Reset Filter"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_reset_filter"

    async def async_press(self) -> None:
        """Reset the clean filter timer."""
        try:
            await self.controller.reset_clean_filter_timer.update(
                ResetCleanFilterTimerStatus()
            )
            await self.coordinator.async_request_refresh()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug(
                "Could not reset filter timer on %s: %s",
                self.coordinator.device_name,
                err,
            )
