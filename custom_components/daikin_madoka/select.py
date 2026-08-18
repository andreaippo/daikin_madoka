"""Support for the behaviour of the Daikin Madoka status ring."""

from __future__ import annotations

import logging
from typing import Any

from pymadoka import RingModeEnum, RingModeStatus
from pymadoka.feature import ConnectionException

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Daikin Madoka selects based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MadokaRingModeSelect(coordinator)])


class MadokaRingModeSelect(MadokaEntity, SelectEntity):
    """Behaviour of the status ring.

    The device keeps this setting inside a sixteen byte array shared with
    settings whose meaning is still unknown. Writing it is safe because every
    other entry is sent as 0xff, which the device leaves alone: a capture of the
    official app changing this one entry shows the other fifteen unchanged in
    the read taken right after.

    The device only returns the array with the edit session open, so reading it
    costs three BLE round-trips where every other feature costs one. It is read
    every RING_MODE_POLL_CYCLES poll cycles rather than every one, so a change
    made from the thermostat or the official app shows up within that window.

    The whole array is published as attributes, next to the minimum and maximum
    the device declares for each entry: that is what a further setting of the
    same menu can be mapped against.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:circle-slice-8"
    _attr_name = "Ring Mode"

    # Keyed by the value the device reports. The names are the ones the official
    # app uses, in its order.
    OPTIONS = {
        RingModeEnum.NORMAL: "normal",
        RingModeEnum.HOTEL_1: "hotel_1",
        RingModeEnum.HOTEL_2: "hotel_2",
    }

    # What each behaviour does, as the official app documents it.
    BEHAVIOURS = {
        "normal": "The ring blinks on an error and shows the status while the screen is dimmed",
        "hotel_1": "The ring does not blink on an error",
        "hotel_2": "The ring does not blink on an error and shows no status while the screen is dimmed",
    }

    _attr_options = list(OPTIONS.values())

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the ring mode select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_ring_mode"

    @property
    def ring_mode_status(self) -> RingModeStatus | None:
        """Return the ring mode status, or None when the feature is missing."""
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
        return self.OPTIONS.get(RingModeEnum(status.mode))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return what the behaviour does, plus the raw array and its range."""
        status = self.ring_mode_status
        if status is None or status.values is None:
            return None
        return {
            "behaviour": self.BEHAVIOURS.get(self.current_option),
            "mode_index": status.MODE_INDEX,
            "values": status.values.hex(),
            "minimum": None if status.minimum is None else status.minimum.hex(),
            "maximum": None if status.maximum is None else status.maximum.hex(),
        }

    async def async_select_option(self, option: str) -> None:
        """Write the behaviour to the device.

        pymadoka brackets the write in the edit session the official app uses
        and reads the array back afterwards, because the response to a write
        does not carry it.
        """
        ring_mode = getattr(self.controller, "ring_mode", None)
        if ring_mode is None:
            return
        mode = next(
            (value for value, name in self.OPTIONS.items() if name == option), None
        )
        if mode is None:
            return
        try:
            await ring_mode.update(RingModeStatus(mode=mode))
            self.coordinator.async_update_listeners()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug(
                "Could not set the ring behaviour on %s: %s",
                self.coordinator.device_name,
                err,
            )
