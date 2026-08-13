"""Support for the behaviour of the Daikin Madoka status ring."""

from __future__ import annotations

import logging

from pymadoka.feature import ConnectionException
from pymadoka.features.ringmode import RingModeEnum, RingModeStatus

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MadokaCoordinator
from .entity import MadokaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# The names the official app gives the three behaviours, in its own order.
RING_MODE_TO_OPTION = {
    RingModeEnum.HOME: "home",
    RingModeEnum.HOTEL_1: "hotel_1",
    RingModeEnum.HOTEL_2: "hotel_2",
}
OPTION_TO_RING_MODE = {option: mode for mode, option in RING_MODE_TO_OPTION.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Daikin Madoka selects based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadokaRingModeSelect(coordinator)])


class MadokaRingModeSelect(MadokaEntity, SelectEntity):
    """Behaviour of the status ring around the display."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:circle-slice-8"
    _attr_translation_key = "ring_mode"
    _attr_options = list(RING_MODE_TO_OPTION.values())

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_ring_mode"
        self._attr_name = "Ring Mode"

    @property
    def ring_mode_status(self) -> RingModeStatus | None:
        """Return the ring mode status, or None when the feature is missing.

        The feature was added to pymadoka after this integration shipped, so an
        older library must not break the whole select platform.
        """
        ring_mode = getattr(self.controller, "ring_mode", None)
        if ring_mode is None:
            return None
        return ring_mode.status

    @property
    def current_option(self) -> str | None:
        """Return the behaviour the device reports."""
        status = self.ring_mode_status
        if status is None or status.mode is None:
            return None
        return RING_MODE_TO_OPTION.get(status.mode)

    async def async_select_option(self, option: str) -> None:
        """Write the behaviour to the device."""
        ring_mode = getattr(self.controller, "ring_mode", None)
        if ring_mode is None:
            return
        mode = OPTION_TO_RING_MODE.get(option)
        if mode is None:
            return
        try:
            # The feature reads the device back on its own, since the response
            # to a write does not carry the array.
            await ring_mode.update(RingModeStatus(mode=mode))
            self.coordinator.async_update_listeners()
            await self.coordinator.async_request_refresh()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug(
                "Could not set the ring mode on %s: %s",
                self.coordinator.device_name,
                err,
            )
