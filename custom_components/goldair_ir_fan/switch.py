"""Switch entities for Goldair IR Fan runtime overrides."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
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
    """Set up Goldair IR Fan switch entities."""
    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    signal = state_update_signal(entry.entry_id)
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEFAULT_NAME,
        manufacturer="Goldair",
        model="IR Fan",
    )
    async_add_entities(
        [
            GoldairIRPowerOverrideSwitchEntity(runtime_state, signal, device_info, entry.entry_id),
            GoldairIROscillationOverrideSwitchEntity(
                runtime_state, signal, device_info, entry.entry_id
            ),
        ]
    )


class GoldairIRPowerOverrideSwitchEntity(SwitchEntity):
    """Manual power-state override for optimistic runtime state."""

    _attr_has_entity_name = True
    _attr_name = "Power override"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize power override switch entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_power_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return current power state."""
        return self._runtime_state.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Override power to on."""
        self._runtime_state.is_on = True
        self._runtime_state.percentage = FAN_SPEEDS[0]
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = PRESET_MODES[0]
        async_dispatcher_send(self.hass, self._signal)

    async def async_turn_off(self, **kwargs) -> None:
        """Override power to off."""
        self._runtime_state.is_on = False
        self._runtime_state.percentage = 0
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = None
        async_dispatcher_send(self.hass, self._signal)


class GoldairIROscillationOverrideSwitchEntity(SwitchEntity):
    """Manual oscillation-state override for optimistic runtime state."""

    _attr_has_entity_name = True
    _attr_name = "Oscillation override"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize oscillation override switch entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_oscillation_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return current oscillation state."""
        return self._runtime_state.oscillating

    async def async_turn_on(self, **kwargs) -> None:
        """Override oscillation to on."""
        self._runtime_state.oscillating = True
        self._runtime_state.is_on = True
        if self._runtime_state.percentage <= 0:
            self._runtime_state.percentage = FAN_SPEEDS[0]
        if self._runtime_state.preset_mode is None:
            self._runtime_state.preset_mode = PRESET_MODES[0]
        async_dispatcher_send(self.hass, self._signal)

    async def async_turn_off(self, **kwargs) -> None:
        """Override oscillation to off."""
        self._runtime_state.oscillating = False
        async_dispatcher_send(self.hass, self._signal)
