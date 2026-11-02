"""Support for Daikin Madoka numbers."""

from pymadoka import DisplayStatus

from homeassistant.components.number import NumberEntity, NumberMode
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
    """Set up Daikin Madoka numbers based on config_entry."""
    async_add_entities(
        entity
        for coordinator in entry.runtime_data.values()
        for entity in (
            MadokaRingBrightnessNumber(coordinator),
            MadokaDisplayBrightnessNumber(coordinator),
            MadokaDisplayContrastNumber(coordinator),
        )
    )


class MadokaDisplayLevelNumber(MadokaEntity, NumberEntity):
    """A level of the display feature, on the device's own 0-19 scale.

    Each level is one parameter of function 0x0302, and a write carries that
    parameter alone, as the official app does.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 19
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    #: DisplayStatus attribute this entity reads and writes.
    _level: str

    @property
    def native_value(self) -> int | None:
        """Return the level read from the device."""
        status = self.controller.display.status
        if status is None:
            return None
        return getattr(status, self._level)

    async def async_set_native_value(self, value: float) -> None:
        """Write the level to the device."""
        await self._async_execute(
            f"set {self._level.replace('_', ' ')}",
            lambda: self.controller.display.update(
                DisplayStatus(**{self._level: int(value)})
            ),
        )


class MadokaRingBrightnessNumber(MadokaDisplayLevelNumber):
    """Brightness of the status ring around the display (parameter 0x33)."""

    _attr_translation_key = "ring_brightness"
    _level = "ring_brightness"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        # Released as "eye_brightness": the unique_id keeps that suffix so the
        # entity, its entity_id and its history survive the rename.
        super().__init__(coordinator, "eye_brightness")


class MadokaDisplayBrightnessNumber(MadokaDisplayLevelNumber):
    """Brightness of the display (parameter 0x32)."""

    _attr_translation_key = "display_brightness"
    _level = "brightness"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        super().__init__(coordinator, "display_brightness")


class MadokaDisplayContrastNumber(MadokaDisplayLevelNumber):
    """Contrast of the display (parameter 0x31)."""

    _attr_translation_key = "display_contrast"
    _level = "contrast"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        super().__init__(coordinator, "display_contrast")
