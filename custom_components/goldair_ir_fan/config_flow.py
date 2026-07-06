"""Config flow for the Goldair IR Fan integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN

from .const import CONF_IR_BLASTER, DEFAULT_NAME, DOMAIN


class GoldairIRFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldair IR Fan."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        if user_input is not None:
            ir_blaster = user_input[CONF_IR_BLASTER]
            await self.async_set_unique_id(ir_blaster)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_IR_BLASTER: ir_blaster},
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_IR_BLASTER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[REMOTE_DOMAIN])
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
