"""Support for Daikin Madoka buttons."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from . import DOMAIN
from .const import CONTROLLERS

from pymadoka import Controller
from pymadoka.feature import ConnectionException, ConnectionStatus
from pymadoka.features.clean_filter import ResetCleanFilterTimerStatus


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Daikin Madoka buttons based on config_entry."""
    entities = []
    for controller in hass.data[DOMAIN][entry.entry_id][CONTROLLERS].values():
        entities.append(MadokaResetFilterButton(controller))
    async_add_entities(entities)


class MadokaResetFilterButton(ButtonEntity):
    """Button to reset the clean filter timer."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, controller: Controller) -> None:
        self.controller = controller

    @property
    def available(self):
        return self.controller.connection.connection_status is ConnectionStatus.CONNECTED

    @property
    def unique_id(self):
        return f"{self.controller.connection.address}_reset_filter"

    @property
    def name(self):
        base_name = (
            self.controller.connection.name
            if self.controller.connection.name is not None
            else self.controller.connection.address
        )
        return f"{base_name} Reset Filter"

    @property
    def icon(self):
        return "mdi:air-filter"

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

    async def async_press(self) -> None:
        try:
            await self.controller.reset_clean_filter_timer.update(
                ResetCleanFilterTimerStatus()
            )
        except ConnectionAbortedError:
            pass
        except ConnectionException:
            pass
