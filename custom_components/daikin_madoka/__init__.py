"""The Daikin Madoka integration."""

from __future__ import annotations

import asyncio
import logging

from pymadoka import Controller, force_device_disconnect

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_FORCE_UPDATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_FRIENDLY_NAME,
    CONF_MAC,
    CONNECT_TIMEOUT,
    DEFAULT_ADAPTER,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import MadokaCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a single Madoka thermostat from a config entry."""
    options = {**entry.data, **entry.options}
    mac = entry.data[CONF_MAC]
    adapter = options.get(CONF_DEVICE, DEFAULT_ADAPTER)
    friendly_name = options.get(CONF_FRIENDLY_NAME) or None

    if options.get(CONF_FORCE_UPDATE, True):
        try:
            await force_device_disconnect(mac)
        except Exception as err:  # noqa: BLE001 - best-effort cleanup of a stale link
            _LOGGER.debug("Forced disconnect failed for %s, skipping: %s", mac, err)

    controller = Controller(mac, adapter=adapter, hass=hass, name=friendly_name)

    try:
        _LOGGER.debug("Connecting to Madoka device: %s", mac)
        await asyncio.wait_for(controller.start(), timeout=CONNECT_TIMEOUT)
    except Exception as err:
        try:
            await controller.stop()
        except Exception:  # noqa: BLE001 - stop is best-effort on a failed connect
            pass
        raise ConfigEntryNotReady(f"Could not connect to device {mac}: {err}") from err

    coordinator = MadokaCoordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MadokaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await coordinator.controller.stop()
        except Exception as err:  # noqa: BLE001 - always release the BLE connection
            _LOGGER.debug("Error stopping controller for %s: %s", coordinator.address, err)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
