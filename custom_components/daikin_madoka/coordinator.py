"""DataUpdateCoordinator for the Daikin Madoka integration."""

from __future__ import annotations

import logging

from pymadoka import Controller
from pymadoka.feature import ConnectionException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    MANUFACTURER,
    MODEL_PREFIX,
    RING_MODE_POLL_CYCLES,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class MadokaCoordinator(DataUpdateCoordinator[None]):
    """Coordinate a single BLE poll cycle for one Madoka thermostat.

    A single controller shares one BLE connection, so all entities read from
    the cached feature status refreshed here once per interval instead of
    querying the device independently.
    """

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, controller: Controller
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.controller = controller
        self._info: dict[str, str] = {}
        # Zero so the first cycle reads it, then counted down between reads.
        self._ring_mode_countdown = 0

    @property
    def address(self) -> str:
        """Return the device BLE address."""
        return self.controller.connection.address

    @property
    def device_name(self) -> str:
        """Return the friendly name or, failing that, the address."""
        return self.controller.connection.name or self.address

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry info shared by every entity."""
        model = (
            MODEL_PREFIX + self._info["Model Number String"]
            if "Model Number String" in self._info
            else MODEL_PREFIX
        )
        return DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            name=self.device_name,
            manufacturer=MANUFACTURER,
            model=model,
            sw_version=self._info.get("Software Revision String"),
        )

    async def _async_update_data(self) -> None:
        """Fetch all feature statuses in a single BLE round-trip."""
        try:
            if not self._info:
                self._info = await self.controller.read_info()
            await self.controller.update()
        except (ConnectionAbortedError, ConnectionException) as err:
            raise UpdateFailed(f"Error communicating with {self.address}: {err}") from err
        await self._read_ring_mode()

    async def _read_ring_mode(self) -> None:
        """Read the ring behaviour, which pymadoka keeps out of the poll cycle.

        The device only returns it with the edit session open, so the read costs
        three BLE round-trips against one for every other feature. It is read
        once every RING_MODE_POLL_CYCLES cycles instead of every one, which is
        still often enough to notice it being changed from the thermostat or the
        official app.

        It is read after the poll and its failures are swallowed: losing this
        one value must not throw away a cycle that read everything else. A
        failed read leaves the countdown alone, so it is retried on the next
        cycle rather than waited out.
        """
        if self._ring_mode_countdown > 0:
            self._ring_mode_countdown -= 1
            return
        try:
            await self.controller.ring_mode.query()
        except Exception as err:  # noqa: BLE001 - one diagnostic value, never fatal
            _LOGGER.debug(
                "Could not read the ring behaviour of %s: %s", self.address, err
            )
            return
        self._ring_mode_countdown = RING_MODE_POLL_CYCLES
