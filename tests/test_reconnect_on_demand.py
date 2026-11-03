"""A dropped link is reconnected when it drops, and a write waits for it.

The coordinator owns reconnects (the controller runs with reconnect=False), and
it used to learn about a drop only on its next poll. Until then the device was
unavailable and every write failed at once with "connection not available",
with nothing retrying it: a morning automation turning the heating on simply
failed. Field log 2026-11-03: the link dropped 150 ms after an operation mode
write, two retries by hand failed instantly, and the reconnect only started
with the next poll 30 s later.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymadoka import ConnectionException, OperationModeEnum
from pymadoka.connection import ConnectionStatus
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant import config_entries
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.daikin_madoka import coordinator as coordinator_module
from custom_components.daikin_madoka.climate import DaikinMadokaClimate
from custom_components.daikin_madoka.const import (
    CONF_MAC,
    DEFAULT_DEVICE_TYPE,
    DOMAIN,
)
from custom_components.daikin_madoka.coordinator import (
    LINK_LOST_MIN_INTERVAL_S,
    LINK_LOST_RECONNECT_DELAY_S,
    MadokaCoordinator,
)

MAC = "D0:CF:13:0F:11:F6"


def _controller() -> MagicMock:
    controller = MagicMock()
    controller.connection.address = MAC
    controller.connection.name = "Daikin"
    controller.connection.connection_status = ConnectionStatus.CONNECTED
    controller.power_state.status = SimpleNamespace(turn_on=False)
    controller.power_state.update = AsyncMock()
    controller.operation_mode.status = SimpleNamespace(
        operation_mode=OperationModeEnum.HEAT
    )
    controller.operation_mode.update = AsyncMock()
    return controller


def _coordinator(hass: HomeAssistant, controller: MagicMock) -> MadokaCoordinator:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_MAC: MAC})
    entry.add_to_hass(hass)
    token = config_entries.current_entry.set(entry)
    try:
        coordinator = MadokaCoordinator(hass, controller, scan_interval=60)
    finally:
        config_entries.current_entry.reset(token)
    coordinator.async_boost = AsyncMock()
    return coordinator


def _entity(hass: HomeAssistant, coordinator: MadokaCoordinator) -> DaikinMadokaClimate:
    entity = DaikinMadokaClimate(coordinator, DEFAULT_DEVICE_TYPE)
    entity.hass = hass
    return entity


def _drop_link(controller: MagicMock):
    """side_effect: the link drops while this command waits for its reply."""

    async def _effect(*_args, **_kwargs):
        controller.connection.connection_status = ConnectionStatus.DISCONNECTED
        raise ConnectionException("Could not send command: connection lost")

    return _effect


def _reconnects(controller: MagicMock, succeeds: bool = True) -> AsyncMock:
    """async_refresh stand-in: a poll that does (or does not) reconnect."""

    async def _refresh() -> None:
        if succeeds:
            controller.connection.connection_status = ConnectionStatus.CONNECTED

    return AsyncMock(side_effect=_refresh)


def _advance(hass: HomeAssistant, seconds: float) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))


# --- Writes ----------------------------------------------------------------


async def test_a_write_cut_off_by_a_drop_is_sent_again_once_reconnected(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)
    drop = _drop_link(controller)
    calls = 0

    async def _drops_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            await drop()

    controller.operation_mode.update.side_effect = _drops_once

    await _entity(hass, coordinator).async_set_hvac_mode(HVACMode.HEAT)

    coordinator.async_refresh.assert_awaited_once()
    assert controller.operation_mode.update.await_count == 2
    controller.power_state.update.assert_awaited_once()
    assert controller.power_state.update.call_args[0][0].turn_on is True


async def test_a_write_with_the_link_already_down_reconnects_first(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)

    async def _needs_link(*_args, **_kwargs):
        if controller.connection.connection_status is not ConnectionStatus.CONNECTED:
            raise ConnectionException("Could not send command: connection lost")

    controller.operation_mode.update.side_effect = _needs_link
    controller.power_state.update.side_effect = _needs_link

    await _entity(hass, coordinator).async_set_hvac_mode(HVACMode.HEAT)

    coordinator.async_refresh.assert_awaited_once()
    assert controller.power_state.update.await_count == 1


async def test_a_write_fails_when_the_device_does_not_come_back(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller, succeeds=False)
    controller.operation_mode.update.side_effect = _drop_link(controller)

    with pytest.raises(HomeAssistantError):
        await _entity(hass, coordinator).async_set_hvac_mode(HVACMode.HEAT)

    assert controller.operation_mode.update.await_count == 1
    controller.power_state.update.assert_not_awaited()


async def test_a_write_is_retried_once_only(hass: HomeAssistant) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)
    controller.operation_mode.update.side_effect = _drop_link(controller)

    with pytest.raises(HomeAssistantError):
        await _entity(hass, coordinator).async_set_hvac_mode(HVACMode.HEAT)

    assert controller.operation_mode.update.await_count == 2


async def test_a_timeout_with_the_link_up_is_not_retried(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)
    controller.operation_mode.update.side_effect = TimeoutError()

    with pytest.raises(HomeAssistantError):
        await _entity(hass, coordinator).async_set_hvac_mode(HVACMode.HEAT)

    coordinator.async_refresh.assert_not_awaited()
    assert controller.operation_mode.update.await_count == 1


async def test_concurrent_writes_share_one_reconnect(hass: HomeAssistant) -> None:
    controller = _controller()
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED
    coordinator = _coordinator(hass, controller)
    gate = asyncio.Event()

    async def _slow_refresh() -> None:
        await gate.wait()
        controller.connection.connection_status = ConnectionStatus.CONNECTED

    coordinator.async_refresh = AsyncMock(side_effect=_slow_refresh)

    first = asyncio.create_task(coordinator.async_ensure_connected())
    second = asyncio.create_task(coordinator.async_ensure_connected())
    await asyncio.sleep(0)
    gate.set()

    assert await first is True
    assert await second is True
    coordinator.async_refresh.assert_awaited_once()


async def test_a_write_that_gives_up_does_not_cancel_the_reconnect(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED
    coordinator = _coordinator(hass, controller)
    gate = asyncio.Event()
    finished = asyncio.Event()

    async def _slow_refresh() -> None:
        await gate.wait()
        controller.connection.connection_status = ConnectionStatus.CONNECTED
        finished.set()

    coordinator.async_refresh = AsyncMock(side_effect=_slow_refresh)

    with patch.object(coordinator_module, "WRITE_RECONNECT_TIMEOUT_S", 0.01):
        assert await coordinator.async_ensure_connected() is False

    gate.set()
    await asyncio.wait_for(finished.wait(), 1)
    assert controller.connection.connection_status is ConnectionStatus.CONNECTED


async def test_a_write_right_after_a_drop_waits_for_the_device_to_settle(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED
    coordinator.async_on_link_lost()
    sleeps: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    with patch.object(coordinator_module.asyncio, "sleep", _fake_sleep):
        assert await coordinator.async_ensure_connected() is True

    assert len(sleeps) == 1
    assert 0 < sleeps[0] <= LINK_LOST_RECONNECT_DELAY_S
    coordinator.async_shutdown_extras()


# --- Drop-triggered reconnect ----------------------------------------------


async def test_a_drop_reconnects_after_the_settle_delay(hass: HomeAssistant) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED

    coordinator.async_on_link_lost()
    await hass.async_block_till_done()
    coordinator.async_refresh.assert_not_awaited()

    _advance(hass, LINK_LOST_RECONNECT_DELAY_S + 0.1)
    await hass.async_block_till_done()

    coordinator.async_refresh.assert_awaited_once()
    assert controller.connection.connection_status is ConnectionStatus.CONNECTED


async def test_no_reconnect_when_something_else_already_reconnected(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = _reconnects(controller)

    coordinator.async_on_link_lost()
    controller.connection.connection_status = ConnectionStatus.CONNECTED
    _advance(hass, LINK_LOST_RECONNECT_DELAY_S + 0.1)
    await hass.async_block_till_done()

    coordinator.async_refresh.assert_not_awaited()


async def test_a_link_that_keeps_dropping_falls_back_to_the_poll_cadence(
    hass: HomeAssistant,
) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = AsyncMock()
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED

    coordinator.async_on_link_lost()
    _advance(hass, LINK_LOST_RECONNECT_DELAY_S + 0.1)
    await hass.async_block_till_done()
    coordinator.async_on_link_lost()  # dropped again right away
    _advance(hass, 2 * LINK_LOST_RECONNECT_DELAY_S + 0.2)
    await hass.async_block_till_done()

    coordinator.async_refresh.assert_awaited_once()

    with patch.object(
        coordinator_module,
        "monotonic",
        return_value=coordinator_module.monotonic() + LINK_LOST_MIN_INTERVAL_S + 1,
    ):
        coordinator.async_on_link_lost()
    _advance(hass, 3 * LINK_LOST_RECONNECT_DELAY_S + 0.3)
    await hass.async_block_till_done()

    assert coordinator.async_refresh.await_count == 2


async def test_unload_cancels_a_pending_drop_reconnect(hass: HomeAssistant) -> None:
    controller = _controller()
    coordinator = _coordinator(hass, controller)
    coordinator.async_refresh = AsyncMock()
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED

    coordinator.async_on_link_lost()
    coordinator.async_shutdown_extras()
    _advance(hass, LINK_LOST_RECONNECT_DELAY_S + 0.1)
    await hass.async_block_till_done()

    coordinator.async_refresh.assert_not_awaited()
