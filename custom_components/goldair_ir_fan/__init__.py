"""The Goldair IR Fan integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

# Integration domain constant shared across all modules.
from .const import DOMAIN

# This integration only exposes a fan platform entity.
PLATFORMS: list[str] = ["fan"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Goldair IR Fan from a config entry."""
    # Forward config entry setup to the fan platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload all platform entities created from this config entry.
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
