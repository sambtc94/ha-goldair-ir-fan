"""The Goldair IR Fan integration.

This module is the entry point for the integration.  Home Assistant calls:

* ``async_migrate_entry`` – before setup, when a config entry was created by an
                            older version of this integration.
* ``async_setup_entry``   – when the integration is first loaded (or HA restarts).
* ``async_unload_entry``  – when the integration is removed or reloaded.

The integration stores a shared :class:`GoldairIRFanRuntimeState` object on
``entry.runtime_data`` so that all platform entities (fan, sensor, switch,
select) can read and write a single in-memory state.

Saving the options form reloads the entry automatically (the options flow is
an ``OptionsFlowWithReload``).
"""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_IR_COMMAND_DELAY,
    CONF_IR_EMITTER,
    CONF_POWER_LAG_SECONDS,
    CONF_POWER_MONITOR_ENTITY,
    CONF_POWER_THRESHOLD,
    CONF_REMOTE_ENTITY,
    DEFAULT_POWER_LAG_SECONDS,
    DEFAULT_POWER_THRESHOLD,
    IR_COMMAND_DELAY_SECONDS,
)
from .entity import GoldairIRFanConfigEntry
from .state import GoldairIRFanRuntimeState

_LOGGER = logging.getLogger(__name__)

# All platform modules that this integration loads entities from.
PLATFORMS: list[str] = ["fan", "sensor", "switch", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: GoldairIRFanConfigEntry) -> bool:
    """Set up Goldair IR Fan from a config entry.

    Creates the shared runtime-state container and forwards setup to each platform.
    """

    def _option(key: str, default=None):
        # Prefer options (set via the Configure button) over the value stored
        # during initial setup, falling back to the built-in default.
        return entry.options.get(key, entry.data.get(key, default))

    entry.runtime_data = GoldairIRFanRuntimeState(
        ir_command_delay_seconds=_option(CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS),
        # Treat an empty string as "not set".
        power_monitor_entity=_option(CONF_POWER_MONITOR_ENTITY) or None,
        power_threshold=_option(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD),
        power_lag_seconds=_option(CONF_POWER_LAG_SECONDS, DEFAULT_POWER_LAG_SECONDS),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoldairIRFanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: GoldairIRFanConfigEntry) -> bool:
    """Migrate a config entry created by an older version of this integration."""
    if entry.version > 1:
        # Downgraded from a newer version; we can't read its data.
        return False

    if entry.minor_version < 2:
        # 1.1 → 1.2: the fan's unique ID was built from the remote entity ID,
        # and the config entry's unique ID *was* the remote entity ID.  That
        # prevented two fans sharing one IR blaster.  Key both on the entry.
        remote_entity = entry.data.get(CONF_REMOTE_ENTITY) or entry.data.get(
            CONF_IR_EMITTER
        )
        old_fan_unique_id = f"{remote_entity}_goldair_ir_fan"
        new_fan_unique_id = f"{entry.entry_id}_fan"

        @callback
        def _migrate_unique_id(entity_entry: er.RegistryEntry) -> dict | None:
            if entity_entry.unique_id == old_fan_unique_id:
                return {"new_unique_id": new_fan_unique_id}
            return None

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)
        hass.config_entries.async_update_entry(entry, unique_id=None, minor_version=2)
        _LOGGER.debug("Migrated %s to version 1.2", entry.title)

    return True
