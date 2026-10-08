"""Shared entity helpers for the Goldair IR Fan integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, state_update_signal
from .state import GoldairIRFanRuntimeState

type GoldairIRFanConfigEntry = ConfigEntry[GoldairIRFanRuntimeState]


def goldair_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return the device info shared by every entity of one config entry.

    The device is named after the config entry title (e.g. "Office Fan"), so
    several Goldair fans can be told apart in the UI.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Goldair",
        model="IR Fan",
    )


class GoldairIRFanOverrideEntity(Entity):
    """Base for the diagnostic override entities.

    These entities only read and write the shared runtime state; they never
    send IR commands.  They refresh themselves whenever any entity of the same
    config entry publishes a runtime-state change.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: GoldairIRFanConfigEntry, key: str) -> None:
        """Initialize the override entity."""
        self._runtime_state = entry.runtime_data
        self._signal = state_update_signal(entry.entry_id)
        self._attr_device_info = goldair_device_info(entry)
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates so the entity stays in sync."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._signal, self._handle_runtime_state_update
            )
        )

    @callback
    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when a sibling entity changes the runtime state."""
        self.async_write_ha_state()
