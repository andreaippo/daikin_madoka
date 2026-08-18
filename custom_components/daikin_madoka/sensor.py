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
            MadokaFanParametersSensor(coordinator),
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


class MadokaFanParametersSensor(MadokaEntity, SensorEntity):
    """Every fan speed parameter whose meaning is not known yet.

    Two parameters of the block turned out to be a mask of the speeds the unit
    accepts, and bit 0 of them is the automatic speed: that much is mapped and
    drives which options the climate entity offers. The masks are published here
    all the same, next to the parameters still unaccounted for, because nothing
    is claimed about their remaining bits.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-braces"
    _attr_name = "Fan Parameters"

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the raw fan parameters sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_fan_parameters"

    @property
    def fan_status(self):
        """Return the fan speed status, or None when it has not been read."""
        return self.controller.fan_speed.status

    @property
    def native_value(self) -> int | None:
        """Return how many unidentified parameters the device reported."""
        status = self.fan_status
        if status is None:
            return None
        return len(getattr(status, "other", {}))

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return each unidentified parameter, by id, as hex, integer and bits.

        The binary form is there because a parameter that says which speeds are
        accepted is most likely a bit per speed.
        """
        status = self.fan_status
        if status is None:
            return None
        attributes = {
            f"param_{param_id:#04x}": (
                f"{value.hex()} ({int.from_bytes(value, 'big')}) "
                f"{int.from_bytes(value, 'big'):#010b}"
            )
            for param_id, value in sorted(getattr(status, "other", {}).items())
        }
        attributes["cooling_speed"] = str(status.cooling_fan_speed)
        attributes["heating_speed"] = str(status.heating_fan_speed)

        for label, mask in (
            ("cooling_speeds", status.cooling_speeds),
            ("heating_speeds", status.heating_speeds),
        ):
            attributes[label] = None if mask is None else f"{mask:#04x} {mask:#010b}"

        attributes["supports_auto"] = status.supports_auto
        return attributes
