"""Config flow for the Goldair IR Fan integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.infrared import DOMAIN as INFRARED_DOMAIN
from homeassistant.helpers import selector

from .const import CONF_IR_EMITTER, DEFAULT_NAME, DOMAIN


class GoldairIRFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldair IR Fan."""

    # Single step flow: pick the emitter entity that will transmit fan commands.
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        if user_input is not None:
            # Keep one integration entry per emitter entity.
            ir_emitter = user_input[CONF_IR_EMITTER]
            await self.async_set_unique_id(ir_emitter)
            self._abort_if_unique_id_configured()

            # Persist the selected emitter for entity command routing.
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_IR_EMITTER: ir_emitter},
            )

        # Only infrared-domain entities are valid for the new IR architecture.
        schema = vol.Schema(
            {
                vol.Required(CONF_IR_EMITTER): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[INFRARED_DOMAIN])
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
