"""Config flow for the Goldair IR Fan integration.

Home Assistant calls this module in two situations:

1. **Initial setup** (async_step_user) – the user names the fan, picks the
   infrared emitter (e.g. a Broadlink's IR emitter entity) and optionally sets
   the IR delay and power-monitor settings.
   The result is stored in ``entry.data``.

2. **Options** (GoldairIRFanOptionsFlowHandler) – the user presses
   "Configure" on the integration card to change the IR delay or power-monitor
   settings without removing and re-adding the integration.  The result is
   stored in ``entry.options`` and the entry reloads automatically.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import infrared
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_INFRARED_ENTITY,
    CONF_IR_COMMAND_DELAY,
    CONF_POWER_LAG_SECONDS,
    CONF_POWER_MONITOR_ENTITY,
    CONF_POWER_THRESHOLD,
    DEFAULT_NAME,
    DEFAULT_POWER_LAG_SECONDS,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
    IR_COMMAND_DELAY_MAX_SECONDS,
    IR_COMMAND_DELAY_MIN_SECONDS,
    IR_COMMAND_DELAY_SECONDS,
    IR_COMMAND_DELAY_STEP_SECONDS,
    POWER_LAG_MAX_SECONDS,
    POWER_LAG_MIN_SECONDS,
    POWER_LAG_STEP_SECONDS,
    POWER_THRESHOLD_MAX,
    POWER_THRESHOLD_MIN,
    POWER_THRESHOLD_STEP,
)


def _number_selector(
    minimum: float, maximum: float, step: float, unit: str
) -> selector.NumberSelector:
    """Return a box-style number selector."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            mode=selector.NumberSelectorMode.BOX,
            unit_of_measurement=unit,
        )
    )


def _settings_schema(
    delay: float,
    power_entity: str | None,
    threshold: float,
    lag_seconds: float,
) -> dict:
    """Return the schema fields shared by the setup and options forms."""
    return {
        vol.Required(CONF_IR_COMMAND_DELAY, default=delay): _number_selector(
            IR_COMMAND_DELAY_MIN_SECONDS,
            IR_COMMAND_DELAY_MAX_SECONDS,
            IR_COMMAND_DELAY_STEP_SECONDS,
            "s",
        ),
        # suggested_value (not default) so the field can be cleared to turn
        # the power monitor off.
        vol.Optional(
            CONF_POWER_MONITOR_ENTITY,
            description={"suggested_value": power_entity},
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(CONF_POWER_THRESHOLD, default=threshold): _number_selector(
            POWER_THRESHOLD_MIN, POWER_THRESHOLD_MAX, POWER_THRESHOLD_STEP, "W"
        ),
        vol.Required(CONF_POWER_LAG_SECONDS, default=lag_seconds): _number_selector(
            POWER_LAG_MIN_SECONDS, POWER_LAG_MAX_SECONDS, POWER_LAG_STEP_SECONDS, "s"
        ),
    }


def _settings_from_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Extract the shared settings from a submitted form."""
    return {
        CONF_IR_COMMAND_DELAY: user_input.get(
            CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS
        ),
        CONF_POWER_MONITOR_ENTITY: user_input.get(CONF_POWER_MONITOR_ENTITY) or None,
        CONF_POWER_THRESHOLD: user_input.get(
            CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD
        ),
        CONF_POWER_LAG_SECONDS: user_input.get(
            CONF_POWER_LAG_SECONDS, DEFAULT_POWER_LAG_SECONDS
        ),
    }


class GoldairIRFanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Goldair IR Fan."""

    # Bumping VERSION/MINOR_VERSION runs async_migrate_entry for older entries.
    VERSION = 2
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step shown when the user adds the integration."""
        emitters = infrared.async_get_emitters(self.hass)
        if not emitters:
            return self.async_abort(reason="no_emitters")

        if user_input is not None:
            # Store the emitter by registry ID so renaming it doesn't break the fan.
            emitter = user_input[CONF_INFRARED_ENTITY]
            if (registry_entry := er.async_get(self.hass).async_get(emitter)) is not None:
                emitter = registry_entry.id
            # No unique ID: several fans may share the same IR blaster.
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_INFRARED_ENTITY: emitter,
                    **_settings_from_input(user_input),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): selector.TextSelector(),
                vol.Required(
                    CONF_INFRARED_ENTITY,
                    default=emitters[0] if len(emitters) == 1 else vol.UNDEFINED,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain=infrared.DOMAIN, include_entities=emitters
                    )
                ),
                **_settings_schema(
                    IR_COMMAND_DELAY_SECONDS,
                    None,
                    DEFAULT_POWER_THRESHOLD,
                    DEFAULT_POWER_LAG_SECONDS,
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> GoldairIRFanOptionsFlowHandler:
        """Return the options-flow handler."""
        return GoldairIRFanOptionsFlowHandler()


class GoldairIRFanOptionsFlowHandler(OptionsFlowWithReload):
    """Handle the *Configure* button flow for an existing Goldair IR Fan entry."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form and save the result when submitted."""
        if user_input is not None:
            return self.async_create_entry(data=_settings_from_input(user_input))

        # Pre-fill with the currently active values: options (from a previous
        # options-flow run) > data (from initial setup) > built-in default.
        entry = self.config_entry

        def _current(key: str, default=None):
            return entry.options.get(key, entry.data.get(key, default))

        schema = vol.Schema(
            _settings_schema(
                _current(CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS),
                _current(CONF_POWER_MONITOR_ENTITY),
                _current(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD),
                _current(CONF_POWER_LAG_SECONDS, DEFAULT_POWER_LAG_SECONDS),
            )
        )
        return self.async_show_form(step_id="init", data_schema=schema)
