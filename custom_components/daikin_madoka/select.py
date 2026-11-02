"""Support for Daikin Madoka selects."""

from typing import Any

from pymadoka import RingModeEnum, RingModeStatus

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MadokaConfigEntry, MadokaCoordinator
from .entity import MadokaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MadokaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin Madoka selects based on config_entry."""
    async_add_entities(
        MadokaRingModeSelect(coordinator)
        for coordinator in entry.runtime_data.values()
    )


class MadokaRingModeSelect(MadokaEntity, SelectEntity):
    """Behaviour of the status ring, as the official app names it.

    Normal: the ring blinks on an error and shows the status while the screen
    is dimmed. Hotel 1: it does not blink on an error. Hotel 2: it does not
    blink on an error and shows no status while the screen is dimmed.

    The coordinator reads it every RING_MODE_POLL_CYCLES polls only: the device
    returns it inside an edit session, three round trips per read.
    """

    _attr_translation_key = "ring_mode"
    _attr_entity_category = EntityCategory.CONFIG

    # Keyed by the value the device reports, in the app's order.
    OPTIONS = {
        RingModeEnum.NORMAL: "normal",
        RingModeEnum.HOTEL_1: "hotel_1",
        RingModeEnum.HOTEL_2: "hotel_2",
    }
    _attr_options = list(OPTIONS.values())

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        super().__init__(coordinator, "ring_mode")

    @property
    def current_option(self) -> str | None:
        """Return the behaviour the device reports."""
        status = self.controller.ring_mode.status
        if status is None or status.mode is None:
            return None
        return self.OPTIONS.get(status.mode)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the raw array the setting lives in, with its declared range.

        Fifteen of its sixteen entries are not mapped yet: this is what a
        further setting of the same menu can be identified against.
        """
        status = self.controller.ring_mode.status
        if status is None or status.values is None:
            return None
        return {
            "values": status.values.hex(),
            "minimum": None if status.minimum is None else status.minimum.hex(),
            "maximum": None if status.maximum is None else status.maximum.hex(),
        }

    async def async_select_option(self, option: str) -> None:
        """Write the behaviour; pymadoka reads the array back afterwards."""
        mode = next(value for value, name in self.OPTIONS.items() if name == option)
        await self._async_execute(
            "set ring behaviour",
            lambda: self.controller.ring_mode.update(RingModeStatus(mode=mode)),
        )
