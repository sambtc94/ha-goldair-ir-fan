"""Config flow for the Goldair IR Fan integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.helpers import selector

from .const import CONF_REMOTE_ENTITY, DEFAULT_NAME, DOMAIN


class GoldairIRFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldair IR Fan."""

    # Single step flow: pick the emitter entity that will transmit fan commands.
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial step."""
        if user_input is not None:
            # Keep one integration entry per emitter entity.
            remote_entity = user_input[CONF_REMOTE_ENTITY]
            await self.async_set_unique_id(remote_entity)
            self._abort_if_unique_id_configured()

            # Persist the selected emitter for entity command routing.
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={CONF_REMOTE_ENTITY: remote_entity},
            )

        # Only remote-domain entities are valid for Broadlink raw command sending.
        schema = vol.Schema(
            {
                vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[REMOTE_DOMAIN])
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
