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
            MadokaDisplayParametersSensor(coordinator),
            MadokaRingModeSensor(coordinator),
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

    The levels the device exposes are writable and live on the number platform;
    what stays here is what can only be read.
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


class MadokaRingModeSensor(MadokaEntity, SensorEntity):
    """Behaviour of the status ring, read only.

    The device accepts a write for this setting and pymadoka implements it, but
    it lives inside an array shared with settings whose meaning is unknown, so
    it is only read here until the write has been shown to be harmless.

    The whole array is published as attributes, next to the minimum and maximum
    the device declares for each entry: that is what a further setting of the
    same menu can be mapped against.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:circle-slice-8"

    OPTIONS = {0: "normal", 1: "hotel_1", 2: "hotel_2"}

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the ring mode sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_ring_mode"
        self._attr_name = "Ring Mode"

    @property
    def ring_mode_status(self):
        """Return the ring mode status, or None when the feature is missing."""
        ring_mode = getattr(self.controller, "ring_mode", None)
        if ring_mode is None:
            return None
        return ring_mode.status

    @property
    def native_value(self) -> str | None:
        """Return the behaviour the device reports."""
        status = self.ring_mode_status
        if status is None or status.mode is None:
            return None
        return self.OPTIONS.get(int(status.mode), str(int(status.mode)))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the raw array and the range the device declares for it."""
        status = self.ring_mode_status
        if status is None or status.values is None:
            return None
        return {
            "mode_index": status.MODE_INDEX,
            "values": status.values.hex(),
            "minimum": None if status.minimum is None else status.minimum.hex(),
            "maximum": None if status.maximum is None else status.maximum.hex(),
        }
