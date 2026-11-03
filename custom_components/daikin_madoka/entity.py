"""Base entity for Daikin Madoka."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from pymadoka import ConnectionException, Controller
from pymadoka.connection import ConnectionStatus

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MadokaCoordinator

_LOGGER = logging.getLogger(__name__)

_COMMAND_ERRORS = (ConnectionAbortedError, ConnectionException, TimeoutError)


class MadokaEntity(CoordinatorEntity[MadokaCoordinator]):
    """Common base: coordinator-backed, device-grouped, stable unique_id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MadokaCoordinator, suffix: str | None = None) -> None:
        """Initialize the entity; suffix=None claims the device unique_id (climate)."""
        super().__init__(coordinator)
        address = coordinator.address
        self._attr_unique_id = address if suffix is None else f"{address}_{suffix}"

    @property
    def controller(self) -> Controller:
        """Return the pymadoka controller."""
        return self.coordinator.controller

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return self.coordinator.device_info

    async def _async_execute(
        self, action: str, *calls: Callable[[], Awaitable[Any]]
    ) -> None:
        """Run device write commands, surface failures, refresh shared state.

        Each call is a zero-arg callable returning an awaitable, so a failure
        in an earlier command never leaves an unawaited coroutine behind.

        A failure with the link down (it dropped mid-command, or was already
        down) waits for the coordinator to reconnect and runs every call once
        more: the commands carry absolute values, so repeating one the device
        already applied is harmless. A failure with the link up (a timeout)
        is not retried here.
        """
        try:
            await self._async_run_calls(calls)
        except _COMMAND_ERRORS as err:
            if (
                self.controller.connection.connection_status
                is ConnectionStatus.CONNECTED
                or not await self.coordinator.async_ensure_connected()
            ):
                raise self._command_failed(action) from err
            _LOGGER.info(
                "%s: link back up, retrying %s",
                self.coordinator.device_name,
                action,
            )
            try:
                await self._async_run_calls(calls)
            except _COMMAND_ERRORS as retry_err:
                raise self._command_failed(action) from retry_err
        # pymadoka stores the written status once the unit acknowledges it, so
        # show it now: the boost's re-poll is a full BLE round of every
        # feature and used to hold the card on the old state for seconds.
        self.coordinator.async_update_listeners()
        # Refresh now and again shortly after, so the UI reflects the device
        # applying the command without waiting a full poll interval.
        await self.coordinator.async_boost()

    @staticmethod
    async def _async_run_calls(calls: tuple[Callable[[], Awaitable[Any]], ...]) -> None:
        for call in calls:
            await call()

    def _command_failed(self, action: str) -> HomeAssistantError:
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={
                "action": action,
                "device": self.coordinator.device_name,
            },
        )
