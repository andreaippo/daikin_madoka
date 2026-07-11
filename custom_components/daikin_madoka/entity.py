"""Base entity for the Daikin Madoka integration."""

from __future__ import annotations

from pymadoka.connection import ConnectionStatus

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MadokaCoordinator


class MadokaEntity(CoordinatorEntity[MadokaCoordinator]):
    """Base class wiring an entity to the shared coordinator and device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.controller = coordinator.controller

    @property
    def device_info(self) -> DeviceInfo:
        """Return the shared device registry info."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Return True when the coordinator is healthy and the link is up."""
        return (
            super().available
            and self.controller.connection.connection_status
            is ConnectionStatus.CONNECTED
        )
