"""Config flow for the Daikin Madoka platform."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_DEVICE, CONF_FORCE_UPDATE
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_FRIENDLY_NAME,
    CONF_MAC,
    DEFAULT_ADAPTER,
    DOMAIN,
    MODEL_PREFIX,
)

MAC_REGEX = re.compile(r"[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\1[0-9a-f]{2}){4}$")


def _validate_mac(mac: str) -> bool:
    """Validate the MAC address format."""
    return bool(MAC_REGEX.match(mac.lower()))


class FlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    @property
    def schema(self) -> vol.Schema:
        """Return the user step schema."""
        return vol.Schema(
            {
                vol.Required(CONF_MAC): cv.string,
                vol.Optional(CONF_FRIENDLY_NAME, default=""): cv.string,
                vol.Optional(CONF_FORCE_UPDATE, default=True): cv.boolean,
                vol.Optional(CONF_DEVICE, default=DEFAULT_ADAPTER): cv.string,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user initiated config flow."""
        errors: dict[str, str] = {}

        if user_input is not None:
            mac = user_input[CONF_MAC].strip()
            if not _validate_mac(mac):
                errors[CONF_MAC] = "not_a_mac"

            if not errors:
                await self.async_set_unique_id(mac.upper())
                self._abort_if_unique_id_configured()

                friendly_name = user_input.get(CONF_FRIENDLY_NAME, "").strip()
                title = friendly_name or f"{MODEL_PREFIX} {mac}"
                return self.async_create_entry(
                    title=title,
                    data={
                        CONF_MAC: mac,
                        CONF_FRIENDLY_NAME: friendly_name,
                        CONF_DEVICE: user_input.get(CONF_DEVICE, DEFAULT_ADAPTER),
                        CONF_FORCE_UPDATE: user_input.get(CONF_FORCE_UPDATE, True),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=self.schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle editable options for a configured thermostat."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FRIENDLY_NAME,
                    default=current.get(CONF_FRIENDLY_NAME, ""),
                ): cv.string,
                vol.Optional(
                    CONF_FORCE_UPDATE,
                    default=current.get(CONF_FORCE_UPDATE, True),
                ): cv.boolean,
                vol.Optional(
                    CONF_DEVICE,
                    default=current.get(CONF_DEVICE, DEFAULT_ADAPTER),
                ): cv.string,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
