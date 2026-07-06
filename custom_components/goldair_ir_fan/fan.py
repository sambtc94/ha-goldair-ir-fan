"""Fan platform for Goldair IR Fan."""

from __future__ import annotations

import asyncio
import logging
from time import monotonic

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN, SERVICE_SEND_COMMAND
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_IR_EMITTER,
    CONF_REMOTE_ENTITY,
    DEFAULT_NAME,
    DOMAIN,
    FAN_SPEEDS,
    IR_BLOB_MODE_CYCLE,
    IR_BLOB_OSC_TOGGLE,
    IR_BLOB_POWER_TOGGLE,
    IR_BLOB_SPEED_CYCLE,
    PRESET_MODES,
    state_update_signal,
)
from .state import GoldairIRFanRuntimeState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan entity from a config entry."""
    # Fallback keeps existing entries created with the old `ir_emitter` key working.
    remote_entity = entry.data.get(CONF_REMOTE_ENTITY) or entry.data.get(CONF_IR_EMITTER)
    if remote_entity is None:
        return

    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    async_add_entities([GoldairIRFanEntity(entry.entry_id, remote_entity, runtime_state)])


class GoldairIRFanEntity(FanEntity):
    """Representation of a Goldair IR fan controlled through a remote entity."""

    # Fan feature flags mapped to implemented async methods below.
    _attr_name = DEFAULT_NAME
    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
    )
    _attr_speed_count = 3
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        entry_id: str,
        remote_entity: str,
        runtime_state: GoldairIRFanRuntimeState,
    ) -> None:
        """Initialize the fan entity."""
        self._entry_id = entry_id
        self._runtime_state = runtime_state
        self._state_update_signal = state_update_signal(entry_id)

        self._remote_entity_id = remote_entity

        # Stable unique ID derived from selected remote entity.
        self._attr_unique_id = f"{remote_entity}_goldair_ir_fan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Goldair",
            model="IR Fan",
        )

        self._sync_attrs_from_runtime_state()
        self._last_ir_command_at: float | None = None

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._state_update_signal,
                self._handle_runtime_state_update,
            )
        )

    def _sync_attrs_from_runtime_state(self) -> None:
        """Sync entity attributes from shared runtime state."""
        self._attr_is_on = self._runtime_state.is_on
        self._attr_percentage = self._runtime_state.percentage
        self._attr_oscillating = self._runtime_state.oscillating
        self._attr_preset_mode = self._runtime_state.preset_mode

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self._sync_attrs_from_runtime_state()
        self.async_write_ha_state()

    def _publish_runtime_state(self) -> None:
        """Notify all entities that runtime state has changed."""
        async_dispatcher_send(self.hass, self._state_update_signal)

    async def _send_ir_command(self, command: str) -> None:
        """Send a single IR command through the configured remote entity."""
        if self._last_ir_command_at is not None:
            elapsed = monotonic() - self._last_ir_command_at
            if elapsed < self._runtime_state.ir_command_delay_seconds:
                await asyncio.sleep(self._runtime_state.ir_command_delay_seconds - elapsed)

        await self.hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: self._remote_entity_id,
                "command": command,
            },
            blocking=True,
        )
        self._last_ir_command_at = monotonic()

    async def _async_power_on_if_needed(self) -> None:
        """Ensure the fan is on before issuing cycle-based commands."""
        if self.is_on:
            return

        # Goldair power is a toggle; turning on always lands at lowest speed.
        await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
        self._runtime_state.is_on = True
        self._runtime_state.percentage = FAN_SPEEDS[0]
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = PRESET_MODES[0]
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn the fan on and optionally apply speed or preset mode."""
        await self._async_power_on_if_needed()

        # Prioritize explicit preset requests over percentage requests.
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)

        self._sync_attrs_from_runtime_state()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off using the power toggle command."""
        if not self.is_on:
            return

        await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
        self._runtime_state.is_on = False
        self._runtime_state.percentage = 0
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = None
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by cycling until the nearest discrete speed is reached."""
        if percentage <= 0:
            await self.async_turn_off()
            return

        await self._async_power_on_if_needed()

        # Manual speed changes must clear preset mode per fan entity docs.
        self._runtime_state.preset_mode = None

        # If state drift happened, start from low-speed index as safe fallback.
        if self.percentage not in FAN_SPEEDS:
            _LOGGER.warning(
                "Fan speed state drift detected (%s); defaulting cycle base to %s",
                self.percentage,
                FAN_SPEEDS[0],
            )
            current_index = 0
        else:
            current_index = FAN_SPEEDS.index(self.percentage)

        # Convert requested percentage to nearest discrete Goldair speed bucket.
        target_speed = min(FAN_SPEEDS, key=lambda speed: abs(speed - percentage))
        target_index = FAN_SPEEDS.index(target_speed)

        # Remote only supports forward cycling (low -> mid -> high -> low).
        steps = (target_index - current_index) % len(FAN_SPEEDS)
        for _ in range(steps):
            await self._send_ir_command(IR_BLOB_SPEED_CYCLE)

        self._runtime_state.percentage = target_speed
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Toggle fan oscillation to match the requested boolean state."""
        if self.oscillating == oscillating:
            return

        await self._async_power_on_if_needed()
        await self._send_ir_command(IR_BLOB_OSC_TOGGLE)
        self._runtime_state.oscillating = oscillating
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set fan mode by cycling normal -> breeze -> night."""
        if preset_mode not in PRESET_MODES:
            return

        await self._async_power_on_if_needed()

        # Resolve optimistic current mode; default to normal when unknown.
        if self.preset_mode not in PRESET_MODES:
            _LOGGER.warning(
                "Fan preset state drift detected (%s); defaulting cycle base to %s",
                self.preset_mode,
                PRESET_MODES[0],
            )
            current_mode = PRESET_MODES[0]
        else:
            current_mode = self.preset_mode
        current_index = PRESET_MODES.index(current_mode)
        target_index = PRESET_MODES.index(preset_mode)

        # Mode key also cycles forward through all modes.
        steps = (target_index - current_index) % len(PRESET_MODES)
        for _ in range(steps):
            await self._send_ir_command(IR_BLOB_MODE_CYCLE)

        self._runtime_state.preset_mode = preset_mode
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()
