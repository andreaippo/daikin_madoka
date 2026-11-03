"""Setup hands pymadoka the short-attempt command policy.

Kept apart because it sets an entry up for real (and so needs HA's bluetooth
stack), as test_allowed_sources_wiring.py does for its callback.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymadoka.connection import ConnectionStatus
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.daikin_madoka.const import (
    COMMAND_MAX_TRIES,
    COMMAND_TIMEOUT_S,
    CONF_MAC,
    DOMAIN,
)

MAC = "D0:CF:13:0F:11:F6"
BLUETOOTH = "homeassistant.components.bluetooth"


@pytest.fixture
def expected_lingering_timers() -> bool:
    """HA's bluetooth scanner schedules a device-expiry timer that outlives
    the test (same waiver as test_allowed_sources_wiring)."""
    return True


def _controller() -> MagicMock:
    controller = MagicMock()
    controller.connection.address = MAC
    controller.connection.name = "Daikin"
    controller.connection.connection_status = ConnectionStatus.DISCONNECTED
    controller.connection.connected_source = None
    controller.connection.pairing_timeout_rounds = 0
    controller.info = {}
    controller.start = AsyncMock()
    controller.stop = AsyncMock()
    controller.read_info = AsyncMock()
    controller.update = AsyncMock()
    controller.refresh_status.return_value = {}
    return controller


async def test_setup_sets_three_short_attempts(
    hass: HomeAssistant,
    enable_bluetooth: None,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_MAC: MAC})
    entry.add_to_hass(hass)
    controller = _controller()
    with (
        patch(
            "custom_components.daikin_madoka.Controller",
            MagicMock(return_value=controller),
        ),
        patch("custom_components.daikin_madoka.async_register_card", AsyncMock()),
        patch("custom_components.daikin_madoka.COMPONENT_TYPES", []),
        patch(f"{BLUETOOTH}.async_address_present", return_value=False),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert controller.connection.command_timeout == COMMAND_TIMEOUT_S == 2.0
    assert controller.connection.command_max_tries == COMMAND_MAX_TRIES == 3
