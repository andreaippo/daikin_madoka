"""The coordinator's drop handler must actually reach pymadoka.

Kept apart from test_reconnect_on_demand.py because this sets an entry up for
real (and so needs HA's bluetooth stack), as test_allowed_sources_wiring.py
does for its callback.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pymadoka.connection import ConnectionStatus
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.daikin_madoka.const import CONF_MAC, DOMAIN

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
    controller.connection.disconnected_callback = None
    controller.info = {}
    controller.start = AsyncMock()
    controller.stop = AsyncMock()
    controller.read_info = AsyncMock()
    controller.update = AsyncMock()
    controller.refresh_status.return_value = {}
    return controller


async def test_setup_hands_the_drop_handler_to_the_connection(
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

    coordinator = entry.runtime_data[MAC]
    assert controller.connection.disconnected_callback == coordinator.async_on_link_lost
