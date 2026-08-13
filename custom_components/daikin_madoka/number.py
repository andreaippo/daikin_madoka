"""Support for the settings of the Daikin Madoka on-board display."""

from __future__ import annotations

import logging

from pymadoka import DisplayStatus
from pymadoka.feature import ConnectionException

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import MadokaCoordinator
from .entity import MadokaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# The device keeps both display levels as a single byte on a 0-19 scale. The
# official app shows them as a percentage, but exposing the same 20 steps here
# avoids a lossy conversion: two neighbouring percentages would otherwise map to
# the same step and the value would jump back on the next read.
DISPLAY_LEVEL_MIN = 0
DISPLAY_LEVEL_MAX = 19


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Daikin Madoka display settings based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MadokaDisplayBrightnessNumber(coordinator),
            MadokaDisplayContrastNumber(coordinator),
        ]
    )


class MadokaDisplayLevelNumber(MadokaEntity, NumberEntity):
    """A level of the on-board display, on the device's own 0-19 scale."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = DISPLAY_LEVEL_MIN
    _attr_native_max_value = DISPLAY_LEVEL_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "step"

    def __init__(self, coordinator: MadokaCoordinator, suffix: str, name: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{suffix}"
        self._attr_name = name

    @property
    def display_status(self):
        """Return the display status, or None when the feature is unavailable."""
        display = getattr(self.controller, "display", None)
        if display is None:
            return None
        return display.status

    def build_update(self, value: int) -> DisplayStatus:
        """Return the status carrying only the level this entity writes."""
        raise NotImplementedError

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        """Return the level as the official app shows it.

        Confirmed against the device: the app's 0-100 slider is the 0-19 scale
        rescaled, 100 % being step 19 and 50 % step 10.
        """
        value = self.native_value
        if value is None:
            return None
        return {"percent": round(value * 100 / DISPLAY_LEVEL_MAX)}

    async def async_set_native_value(self, value: float) -> None:
        """Write the level to the device.

        The command carries a single parameter, as the official app does. That
        leaves the feature status holding only the parameter just written, so
        the device is read back straight away: the sibling entity would
        otherwise go unknown until the next poll.
        """
        display = getattr(self.controller, "display", None)
        if display is None:
            return
        try:
            await display.update(self.build_update(round(value)))
            await display.query()
            self.coordinator.async_update_listeners()
            await self.coordinator.async_request_refresh()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug(
                "Could not set %s on %s: %s",
                self.name,
                self.coordinator.device_name,
                err,
            )


class MadokaDisplayBrightnessNumber(MadokaDisplayLevelNumber):
    """Brightness of the on-board display (parameter 0x32)."""

    _attr_icon = "mdi:brightness-6"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the brightness entity."""
        super().__init__(coordinator, "display_brightness_level", "Display Brightness")

    @property
    def native_value(self) -> int | None:
        """Return the brightness read from the device."""
        status = self.display_status
        return None if status is None else status.brightness

    def build_update(self, value: int) -> DisplayStatus:
        """See base class."""
        return DisplayStatus(brightness=value)


class MadokaDisplayContrastNumber(MadokaDisplayLevelNumber):
    """Contrast of the on-board display (parameter 0x31)."""

    _attr_icon = "mdi:contrast-circle"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the contrast entity."""
        super().__init__(coordinator, "display_contrast_level", "Display Contrast")

    @property
    def native_value(self) -> int | None:
        """Return the contrast read from the device."""
        status = self.display_status
        return None if status is None else status.contrast

    def build_update(self, value: int) -> DisplayStatus:
        """See base class."""
        return DisplayStatus(contrast=value)
