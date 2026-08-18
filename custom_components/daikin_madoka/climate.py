"""Support for the Daikin Madoka HVAC."""

from __future__ import annotations

import logging
from typing import Any

from pymadoka import (
    ConnectionException,
    FanSpeedEnum,
    FanSpeedStatus,
    OperationModeEnum,
    OperationModeStatus,
    PowerStateStatus,
    SetPointStatus,
)

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, MAX_TEMP, MIN_TEMP, TARGET_TEMP_STEP
from .coordinator import MadokaCoordinator
from .entity import MadokaEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

HA_MODE_TO_DAIKIN = {
    HVACMode.FAN_ONLY: OperationModeEnum.FAN,
    HVACMode.DRY: OperationModeEnum.DRY,
    HVACMode.COOL: OperationModeEnum.COOL,
    HVACMode.HEAT: OperationModeEnum.HEAT,
    HVACMode.AUTO: OperationModeEnum.AUTO,
    HVACMode.OFF: OperationModeEnum.AUTO,
}

DAIKIN_TO_HA_MODE = {
    OperationModeEnum.FAN: HVACMode.FAN_ONLY,
    OperationModeEnum.DRY: HVACMode.DRY,
    OperationModeEnum.COOL: HVACMode.COOL,
    OperationModeEnum.HEAT: HVACMode.HEAT,
    OperationModeEnum.AUTO: HVACMode.AUTO,
}

HA_FAN_MODE_TO_DAIKIN = {
    FAN_LOW: FanSpeedEnum.LOW,
    FAN_MEDIUM: FanSpeedEnum.MID,
    FAN_HIGH: FanSpeedEnum.HIGH,
    FAN_AUTO: FanSpeedEnum.AUTO,
}

DAIKIN_TO_HA_FAN_MODE = {
    FanSpeedEnum.LOW: FAN_LOW,
    FanSpeedEnum.MID: FAN_MEDIUM,
    FanSpeedEnum.HIGH: FAN_HIGH,
    FanSpeedEnum.AUTO: FAN_AUTO,
}

DAIKIN_TO_HA_CURRENT_HVAC_MODE = {
    OperationModeEnum.FAN: HVACAction.FAN,
    OperationModeEnum.DRY: HVACAction.DRYING,
    OperationModeEnum.COOL: HVACAction.COOLING,
    OperationModeEnum.HEAT: HVACAction.HEATING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin climate based on a config entry."""
    coordinator: MadokaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DaikinMadokaClimate(coordinator)])


class DaikinMadokaClimate(MadokaEntity, ClimateEntity):
    """Representation of a Daikin Madoka HVAC."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TARGET_TEMP_STEP
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_hvac_modes = list(HA_MODE_TO_DAIKIN)

    def __init__(self, coordinator: MadokaCoordinator) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.address

    @property
    def current_temperature(self) -> float | None:
        """Return the current indoor temperature."""
        if self.controller.temperatures.status is None:
            return None
        return self.controller.temperatures.status.indoor

    @property
    def _targets_heating_set_point(self) -> bool:
        """Whether the heating set point is the one this entity reads and writes.

        The device keeps a set point per mode and, when configured for two
        distinct ones, memorizes them separately. Reads and writes must agree on
        which of the two is in play, otherwise editing the temperature would
        change a value the UI is not showing.
        """
        return self.hvac_mode == HVACMode.HEAT

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        if self.controller.set_point.status is None:
            return None
        if self._targets_heating_set_point:
            return self.controller.set_point.status.heating_set_point
        return self.controller.set_point.status.cooling_set_point

    async def _publish_written_state(self) -> None:
        """Publish the state the device just confirmed, then re-read the device.

        pymadoka stores the written status on the feature as soon as the device
        acknowledges the command, so the entity properties already return the new
        values. Publishing them right away matters: a coordinator refresh is
        debounced by several seconds, and until it lands the frontend still shows
        the previous value - a user acting again in that window (e.g. switching
        back to the mode the UI still displays) produces no service call at all,
        because the frontend treats it as a no-op.

        Every entity of this device is refreshed, not just this one, since a
        single command changes several of them (mode, power, set point). The
        coordinator refresh still runs afterwards so that a command the device
        acknowledges but does not apply is eventually corrected by a real read.
        """
        self.coordinator.async_update_listeners()
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        try:
            if self.controller.set_point.status is None:
                return
            if self.controller.operation_mode.status is None:
                return

            target_temperature = kwargs.get(ATTR_TEMPERATURE)
            if target_temperature is None:
                return

            # Only the set point this entity exposes is written: the other one
            # keeps the value the device memorized for its own mode. Writing both
            # would collapse a dual set-point configuration to a single value as
            # soon as the temperature is changed outside heating and cooling.
            new_cooling_set_point = self.controller.set_point.status.cooling_set_point
            new_heating_set_point = self.controller.set_point.status.heating_set_point
            if self._targets_heating_set_point:
                new_heating_set_point = round(target_temperature)
            else:
                new_cooling_set_point = round(target_temperature)

            await self.controller.set_point.update(
                SetPointStatus(new_cooling_set_point, new_heating_set_point)
            )
            await self._publish_written_state()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug("Could not set target temperature on %s: %s", self.coordinator.device_name, err)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return current operation ie. heat, cool, idle."""
        if self.controller.power_state.status is None:
            return None
        if self.controller.operation_mode.status is None:
            return None
        if self.controller.power_state.status.turn_on is False:
            return HVACMode.OFF
        return DAIKIN_TO_HA_MODE.get(
            self.controller.operation_mode.status.operation_mode
        )

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the HVAC current action."""
        if self.controller.power_state.status is None:
            return None
        if self.controller.operation_mode.status is None:
            return None
        if self.controller.power_state.status.turn_on is False:
            return HVACAction.OFF

        if (
            self.controller.operation_mode.status.operation_mode
            == OperationModeEnum.AUTO
        ):
            if self.target_temperature is None or self.current_temperature is None:
                return None
            if self.target_temperature >= self.current_temperature:
                return HVACAction.HEATING
            return HVACAction.COOLING

        return DAIKIN_TO_HA_CURRENT_HVAC_MODE.get(
            self.controller.operation_mode.status.operation_mode
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        try:
            if hvac_mode != HVACMode.OFF:
                await self.controller.operation_mode.update(
                    OperationModeStatus(HA_MODE_TO_DAIKIN.get(hvac_mode))
                )
            await self.controller.power_state.update(
                PowerStateStatus(hvac_mode != HVACMode.OFF)
            )
            await self._publish_written_state()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug("Could not set HVAC mode on %s: %s", self.coordinator.device_name, err)

    @property
    def fan_modes(self) -> list[str]:
        """Return the fan speeds this indoor unit accepts.

        Not every unit takes the automatic speed: the ones that do not refuse
        the command and snap back to the speed they were on, which is no use as
        an option in the UI. The device says so in the fan speed block, so the
        option is dropped for those units.

        The full list is returned until the unit has said otherwise, so a speed
        is never withheld on the strength of a value not read yet.
        """
        modes = list(HA_FAN_MODE_TO_DAIKIN)
        status = self.controller.fan_speed.status
        if status is not None and not getattr(status, "supports_auto", True):
            modes.remove(FAN_AUTO)
        return modes

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        if self.controller.fan_speed.status is None:
            return None
        if self.hvac_mode == HVACMode.HEAT:
            return DAIKIN_TO_HA_FAN_MODE.get(
                self.controller.fan_speed.status.heating_fan_speed
            )
        return DAIKIN_TO_HA_FAN_MODE.get(
            self.controller.fan_speed.status.cooling_fan_speed
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        speed = HA_FAN_MODE_TO_DAIKIN.get(fan_mode)
        if speed is None:
            # A status with no speed set is how the whole block is asked for,
            # so it must never reach the write.
            _LOGGER.debug("Unknown fan mode %s, ignored", fan_mode)
            return
        try:
            await self.controller.fan_speed.update(FanSpeedStatus(speed, speed))
            await self._publish_written_state()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug("Could not set fan mode on %s: %s", self.coordinator.device_name, err)

    async def async_turn_on(self) -> None:
        """Turn device on."""
        try:
            await self.controller.power_state.update(PowerStateStatus(True))
            await self._publish_written_state()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug("Could not turn on %s: %s", self.coordinator.device_name, err)

    async def async_turn_off(self) -> None:
        """Turn device off."""
        try:
            await self.controller.power_state.update(PowerStateStatus(False))
            await self._publish_written_state()
        except (ConnectionAbortedError, ConnectionException) as err:
            _LOGGER.debug("Could not turn off %s: %s", self.coordinator.device_name, err)
