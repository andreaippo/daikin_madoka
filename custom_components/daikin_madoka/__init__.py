"""Platform for the Daikin AC."""
import asyncio
from datetime import timedelta
import logging

from pymadoka import Controller, force_device_disconnect
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    CONF_FORCE_UPDATE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant

from . import config_flow  # noqa: F401
from .const import CONTROLLERS, DOMAIN, CONF_MAC, CONF_FRIENDLY_NAME

PARALLEL_UPDATES = 0
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

COMPONENT_TYPES = ["climate", "sensor", "binary_sensor", "button"]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_MAC): cv.string,
                    vol.Optional(CONF_FRIENDLY_NAME, default=""): cv.string,
                    vol.Optional(CONF_FORCE_UPDATE, default=True): bool,
                    vol.Optional(CONF_DEVICE, default="hci0"): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up a single Madoka thermostat from a config entry."""
    mac = entry.data[CONF_MAC]
    adapter = entry.data.get(CONF_DEVICE, "hci0")
    friendly_name = entry.data.get(CONF_FRIENDLY_NAME) or None

    if entry.data.get(CONF_FORCE_UPDATE, True):
        try:
            await force_device_disconnect(mac)
        except Exception:
            _LOGGER.debug("Forced disconnect failed for %s, skipping...", mac)

    controller = Controller(mac, adapter=adapter, hass=hass, name=friendly_name)

    try:
        _LOGGER.info("Connecting to Madoka device: %s", mac)
        await asyncio.wait_for(controller.start(), timeout=15)
    except Exception as connection_error:
        _LOGGER.error(
            "Could not connect to device %s: %s",
            mac,
            str(connection_error),
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {CONTROLLERS: {mac: controller}}

    await hass.config_entries.async_forward_entry_setups(entry, COMPONENT_TYPES)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, COMPONENT_TYPES)
