"""Support for Daikin Madoka temperature sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
        [MadokaIndoorSensor(coordinator), MadokaOutdoorSensor(coordinator)]
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
