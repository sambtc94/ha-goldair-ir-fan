"""Config flow for the Goldair IR Fan integration.

Home Assistant calls this module in two situations:

1. **Initial setup** (async_step_user) – the user picks a remote entity and
   optionally sets the inter-command IR delay.  The result is stored in
   ``entry.data``.

2. **Reconfigure / Options** (GoldairIRFanOptionsFlowHandler) – the user
   presses "Configure" on the integration card to change the IR delay without
   having to remove and re-add the integration.  The result is stored in
   ``entry.options``.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.helpers import selector

from .const import (
    CONF_IR_COMMAND_DELAY,
    CONF_REMOTE_ENTITY,
    DEFAULT_NAME,
    DOMAIN,
    IR_COMMAND_DELAY_MAX_SECONDS,
    IR_COMMAND_DELAY_MIN_SECONDS,
    IR_COMMAND_DELAY_SECONDS,
    IR_COMMAND_DELAY_STEP_SECONDS,
)


class GoldairIRFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldair IR Fan.

    The flow has a single step (``user``) that collects the minimum required
    information to set up the integration:

    * ``remote_entity`` – the Home Assistant remote entity that will transmit
      the IR signals (e.g. ``remote.broadlink_living_room``).
    * ``ir_command_delay`` – how long (in seconds) to wait between consecutive
      IR commands.  The default of 0.5 s works well for most Broadlink devices.
    """

    # Bumping VERSION triggers a migration flow when the schema changes.
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Handle the initial setup step shown when the user adds the integration."""
        if user_input is not None:
            # Prevent duplicate entries for the same emitter entity.
            remote_entity = user_input[CONF_REMOTE_ENTITY]
            await self.async_set_unique_id(remote_entity)
            self._abort_if_unique_id_configured()

            # Persist both the remote entity and the chosen IR delay.
            return self.async_create_entry(
                title=DEFAULT_NAME,
                data={
                    CONF_REMOTE_ENTITY: remote_entity,
                    CONF_IR_COMMAND_DELAY: user_input.get(
                        CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS
                    ),
                },
            )

        # Build the form schema shown in the HA UI.
        # Only remote-domain entities can transmit Broadlink raw commands.
        schema = vol.Schema(
            {
                vol.Required(CONF_REMOTE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=[REMOTE_DOMAIN])
                ),
                vol.Optional(
                    CONF_IR_COMMAND_DELAY,
                    default=IR_COMMAND_DELAY_SECONDS,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=IR_COMMAND_DELAY_MIN_SECONDS,
                        max=IR_COMMAND_DELAY_MAX_SECONDS,
                        step=IR_COMMAND_DELAY_STEP_SECONDS,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "GoldairIRFanOptionsFlowHandler":
        """Return an options-flow handler so the user can reconfigure the delay."""
        return GoldairIRFanOptionsFlowHandler(config_entry)


class GoldairIRFanOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the *Configure* button flow for an existing Goldair IR Fan entry.

    This lets the user change the IR command delay after the integration is
    already set up, without removing and re-adding it.
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the existing config entry so we can pre-fill the form."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None):
        """Show the options form and save the result when submitted."""
        if user_input is not None:
            # Merge the new option into the existing options dict and save.
            return self.async_create_entry(
                title="",
                data={CONF_IR_COMMAND_DELAY: user_input[CONF_IR_COMMAND_DELAY]},
            )

        # Pre-fill with the currently active delay value.
        # Preference order: options (set by a previous options-flow run) >
        # data (set during initial setup) > built-in default.
        current_delay = self._config_entry.options.get(
            CONF_IR_COMMAND_DELAY,
            self._config_entry.data.get(CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS),
        )

        schema = vol.Schema(
            {
                vol.Required(CONF_IR_COMMAND_DELAY, default=current_delay): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=IR_COMMAND_DELAY_MIN_SECONDS,
                        max=IR_COMMAND_DELAY_MAX_SECONDS,
                        step=IR_COMMAND_DELAY_STEP_SECONDS,
                        mode=selector.NumberSelectorMode.BOX,
                        unit_of_measurement="s",
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
