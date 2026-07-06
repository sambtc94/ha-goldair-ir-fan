"""Select entities for Goldair IR Fan runtime overrides."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN, FAN_SPEEDS, PRESET_MODES, state_update_signal
from .state import GoldairIRFanRuntimeState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan select entities."""
    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    signal = state_update_signal(entry.entry_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEFAULT_NAME,
        manufacturer="Goldair",
        model="IR Fan",
    )
    async_add_entities(
        [GoldairIRPresetOverrideSelectEntity(runtime_state, signal, device_info, entry.entry_id)]
    )


class GoldairIRPresetOverrideSelectEntity(SelectEntity):
    """Manual preset-state override for optimistic runtime state."""

    _attr_has_entity_name = True
    _attr_name = "Preset override"
    _attr_options = PRESET_MODES

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize preset override select entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_preset_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return current preset override option."""
        return self._runtime_state.preset_mode

    async def async_select_option(self, option: str) -> None:
        """Override preset state."""
        if option not in PRESET_MODES:
            return
        self._runtime_state.preset_mode = option
        self._runtime_state.is_on = True
        if self._runtime_state.percentage <= 0:
            self._runtime_state.percentage = FAN_SPEEDS[0]
        self._runtime_state.oscillating = False
        async_dispatcher_send(self.hass, self._signal)
