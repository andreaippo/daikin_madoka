"""Support for Daikin Madoka binary sensors."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from . import DOMAIN
from .const import CONTROLLERS

from pymadoka import Controller
from pymadoka.feature import ConnectionException, ConnectionStatus


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin Madoka binary sensors based on config_entry."""
    entities = []
    for controller in hass.data[DOMAIN][entry.entry_id][CONTROLLERS].values():
        entities.append(MadokaFilterBinarySensor(controller))
    async_add_entities(entities)


class MadokaFilterBinarySensor(BinarySensorEntity):
    """Binary sensor for the clean filter indicator."""

    def __init__(self, controller: Controller) -> None:
        self.controller = controller

    @property
    def available(self):
        return self.controller.connection.connection_status is ConnectionStatus.CONNECTED

    @property
    def unique_id(self):
        return f"{self.controller.connection.address}_clean_filter"

    @property
    def name(self):
        base_name = (
            self.controller.connection.name
            if self.controller.connection.name is not None
            else self.controller.connection.address
        )
        return f"{base_name} Clean Filter"

    @property
    def device_class(self):
        return BinarySensorDeviceClass.PROBLEM

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.controller.connection.address)},
            "name": (
                self.controller.connection.name
                if self.controller.connection.name is not None
                else self.controller.connection.address
            ),
            "manufacturer": "DAIKIN",
            "model": "BRC1H",
        }

    @property
    def is_on(self):
        if self.controller.clean_filter_indicator.status is None:
            return None
        return self.controller.clean_filter_indicator.status.clean_filter_indicator

    async def async_update(self):
        try:
            await self.controller.clean_filter_indicator.query()
        except ConnectionAbortedError:
            pass
        except ConnectionException:
            pass
