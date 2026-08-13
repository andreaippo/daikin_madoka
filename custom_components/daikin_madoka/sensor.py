"""Support for Daikin Madoka temperature sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
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
    """Set up Daikin Madoka sensors based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MadokaIndoorSensor(coordinator),
            MadokaOutdoorSensor(coordinator),
            MadokaDisplayBrightnessSensor(coordinator),
            MadokaDisplayContrastSensor(coordinator),
            MadokaDisplayParametersSensor(coordinator),
        ]
    )


class MadokaSensor(MadokaEntity, SensorEntity):
    """Base representation of a Madoka temperature sensor."""

    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    def __init__(self, coordinator: MadokaCoordinator, suffix: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{suffix}"
        self._attr_name = name


class MadokaIndoorSensor(MadokaSensor):
    """Indoor temperature sensor."""

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the indoor sensor."""
        super().__init__(coordinator, "indoor_temperature", "Indoor Temperature")

    @property
    def native_value(self) -> float | None:
        """Return the indoor temperature."""
        if self.controller.temperatures.status is None:
            return None
        return self.controller.temperatures.status.indoor


class MadokaOutdoorSensor(MadokaSensor):
    """Outdoor temperature sensor."""

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the outdoor sensor."""
        super().__init__(coordinator, "outdoor_temperature", "Outdoor Temperature")

    @property
    def native_value(self) -> float | None:
        """Return the outdoor temperature."""
        if self.controller.temperatures.status is None:
            return None
        return self.controller.temperatures.status.outdoor


class MadokaDisplaySensor(MadokaEntity, SensorEntity):
    """Base representation of a read-only view on the on-board display settings.

    These sensors exist to check the mapping recovered from the capture of the
    official app against what the device reports: change a setting from the
    app, then read the value here. Nothing is ever written back.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MadokaCoordinator, suffix: str, name: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_{suffix}"
        self._attr_name = name

    @property
    def display_status(self):
        """Return the display status, or None when the feature is unavailable.

        The feature was added to pymadoka after this integration shipped, so an
        older library must not break the whole sensor platform.
        """
        display = getattr(self.controller, "display", None)
        if display is None:
            return None
        return display.status


class MadokaDisplayLevelSensor(MadokaDisplaySensor):
    """A display level reported on the device's own 0-19 scale.

    The official app shows these settings on a 0-100 scale, so both plausible
    conversions are published as attributes: which one the app uses can be told
    by setting a value there and comparing.
    """

    _attr_native_unit_of_measurement = "step"
    _attr_icon = "mdi:brightness-6"

    WIRE_MAX = 19

    @property
    def raw_value(self) -> int | None:
        """Return the value read from the device. Overridden by subclasses."""
        raise NotImplementedError

    @property
    def native_value(self) -> int | None:
        """Return the level as the device reports it."""
        return self.raw_value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the candidate conversions to the app's 0-100 scale."""
        value = self.raw_value
        if value is None:
            return None
        return {
            "raw": value,
            "percent_full_scale": round(value * 100 / self.WIRE_MAX),
            "percent_five_per_step": value * 5,
        }


class MadokaDisplayBrightnessSensor(MadokaDisplayLevelSensor):
    """Brightness of the on-board display (parameter 0x32)."""

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the brightness sensor."""
        super().__init__(coordinator, "display_brightness", "Display Brightness")

    @property
    def raw_value(self) -> int | None:
        """Return the brightness read from the device."""
        status = self.display_status
        return None if status is None else status.brightness


class MadokaDisplayContrastSensor(MadokaDisplayLevelSensor):
    """Contrast of the on-board display (parameter 0x31)."""

    _attr_icon = "mdi:contrast-circle"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the contrast sensor."""
        super().__init__(coordinator, "display_contrast", "Display Contrast")

    @property
    def raw_value(self) -> int | None:
        """Return the contrast read from the device."""
        status = self.display_status
        return None if status is None else status.contrast


class MadokaDisplayParametersSensor(MadokaDisplaySensor):
    """Every display parameter whose meaning is not known yet.

    The device answers a display query with fifteen parameters and only two of
    them are identified. The rest are published here so a setting changed from
    the official app can be tied to the parameter id that moved with it.
    """

    _attr_icon = "mdi:code-braces"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the raw parameters sensor."""
        super().__init__(coordinator, "display_parameters", "Display Parameters")

    @property
    def native_value(self) -> int | None:
        """Return how many unidentified parameters the device reported."""
        status = self.display_status
        if status is None:
            return None
        return len(status.other)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return each unidentified parameter, by id, as hex and as an integer."""
        status = self.display_status
        if status is None:
            return None
        return {
            f"param_{param_id:#04x}": f"{value.hex()} ({int.from_bytes(value, 'big')})"
            for param_id, value in sorted(status.other.items())
        }
