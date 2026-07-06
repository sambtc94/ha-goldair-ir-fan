"""Number entities for Goldair IR Fan runtime overrides."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    FAN_SPEEDS,
    IR_COMMAND_DELAY_MAX_SECONDS,
    IR_COMMAND_DELAY_MIN_SECONDS,
    IR_COMMAND_DELAY_STEP_SECONDS,
    state_update_signal,
)
from .state import GoldairIRFanRuntimeState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan number entities."""
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
            GoldairIRDelayNumberEntity(runtime_state, signal, device_info, entry.entry_id),
            GoldairIRSpeedOverrideNumberEntity(runtime_state, signal, device_info, entry.entry_id),
        ]
    )


class GoldairIRDelayNumberEntity(NumberEntity):
    """Configurable delay between consecutive IR commands."""

    _attr_has_entity_name = True
    _attr_name = "IR command delay"
    _attr_mode = NumberMode.BOX
    _attr_native_unit_of_measurement = "s"
    _attr_native_min_value = IR_COMMAND_DELAY_MIN_SECONDS
    _attr_native_max_value = IR_COMMAND_DELAY_MAX_SECONDS
    _attr_native_step = IR_COMMAND_DELAY_STEP_SECONDS

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize delay number entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_ir_command_delay"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Return current delay value."""
        return round(self._runtime_state.ir_command_delay_seconds, 2)

    async def async_set_native_value(self, value: float) -> None:
        """Set the command delay."""
        bounded_value = max(
            IR_COMMAND_DELAY_MIN_SECONDS,
            min(IR_COMMAND_DELAY_MAX_SECONDS, value),
        )
        self._runtime_state.ir_command_delay_seconds = bounded_value
        async_dispatcher_send(self.hass, self._signal)


class GoldairIRSpeedOverrideNumberEntity(NumberEntity):
    """Manual speed override for optimistic runtime state."""

    _attr_has_entity_name = True
    _attr_name = "Speed override"
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = "%"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize speed override number entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_speed_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Return current fan speed state."""
        return float(self._runtime_state.percentage)

    async def async_set_native_value(self, value: float) -> None:
        """Override fan speed state."""
        percentage = round(value)
        if percentage <= 0:
            self._runtime_state.is_on = False
            self._runtime_state.percentage = 0
            self._runtime_state.oscillating = False
            self._runtime_state.preset_mode = None
        else:
            self._runtime_state.is_on = True
            self._runtime_state.percentage = min(
                FAN_SPEEDS, key=lambda speed: abs(speed - percentage)
            )
            self._runtime_state.preset_mode = None
        async_dispatcher_send(self.hass, self._signal)
