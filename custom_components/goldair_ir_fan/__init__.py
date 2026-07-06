"""The Goldair IR Fan integration.

This module is the entry point for the integration.  Home Assistant calls:

* ``async_setup_entry``   – when the integration is first loaded (or HA restarts).
* ``async_unload_entry``  – when the user removes the integration.
* ``async_update_options`` – when the user saves changes from the "Configure"
                              button (options flow).

The integration sets up a shared :class:`GoldairIRFanRuntimeState` object in
``hass.data`` so that all platform entities (fan, switch, select) can read and
write a single in-memory state without going through the entity registry.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_IR_COMMAND_DELAY,
    CONF_POWER_MONITOR_ENTITY,
    CONF_POWER_THRESHOLD,
    DEFAULT_POWER_THRESHOLD,
    DOMAIN,
    IR_COMMAND_DELAY_SECONDS,
)
from .state import GoldairIRFanRuntimeState

# All platform modules that this integration loads entity from.
PLATFORMS: list[str] = ["fan", "switch", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Goldair IR Fan from a config entry.

    Called once per config entry on HA startup or when the entry is first added.
    Creates the shared runtime-state container and forwards setup to each platform.
    """
    hass.data.setdefault(DOMAIN, {})

    # Resolve the IR delay: prefer options (set via the Configure button) over
    # the value stored during initial setup, falling back to the built-in default.
    ir_delay = entry.options.get(
        CONF_IR_COMMAND_DELAY,
        entry.data.get(CONF_IR_COMMAND_DELAY, IR_COMMAND_DELAY_SECONDS),
    )

    # Resolve power-monitor settings (optional; None if not configured).
    power_monitor_entity = entry.options.get(
        CONF_POWER_MONITOR_ENTITY,
        entry.data.get(CONF_POWER_MONITOR_ENTITY),
    ) or None  # treat empty string as "not set"

    power_threshold = entry.options.get(
        CONF_POWER_THRESHOLD,
        entry.data.get(CONF_POWER_THRESHOLD, DEFAULT_POWER_THRESHOLD),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "runtime_state": GoldairIRFanRuntimeState(
            ir_command_delay_seconds=ir_delay,
            power_monitor_entity=power_monitor_entity,
            power_threshold=power_threshold,
        ),
    }

    # Register the options-update listener so changes from the "Configure"
    # button take effect without requiring an HA restart.
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    # Load fan, switch and select platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when the user saves the options flow.

    A full reload is the cleanest way to apply changed settings (especially a
    new power-monitor entity, which requires re-subscribing to state changes).
    """
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and clean up hass.data.

    Home Assistant calls this when the user removes the integration or when HA
    is restarting.  We unload all platform entities and delete our data bucket.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
