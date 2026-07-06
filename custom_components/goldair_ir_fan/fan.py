"""Fan platform for Goldair IR Fan."""

from __future__ import annotations

import asyncio
from time import monotonic

from infrared_protocols.commands import Command as InfraredCommand

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_IR_EMITTER,
    DEFAULT_NAME,
    IR_COMMAND_MODE_CYCLE,
    IR_COMMAND_DELAY_SECONDS,
    IR_COMMAND_OSC_TOGGLE,
    IR_COMMAND_POWER_TOGGLE,
    IR_COMMAND_SPEED_CYCLE,
    PRESET_MODES,
)

# Three discrete physical speed states exposed by the remote cycle button.
SPEEDS = [33, 67, 100]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan entity from a config entry."""
    ir_emitter = entry.data.get(CONF_IR_EMITTER)
    if ir_emitter is None:
        return

    async_add_entities([GoldairIRFanEntity(ir_emitter)])


class GoldairIRFanEntity(InfraredEmitterConsumerEntity, FanEntity):
    """Representation of a Goldair IR fan controlled by an IR emitter entity."""

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

    def __init__(self, ir_emitter: str) -> None:
        """Initialize the fan entity."""
        # InfraredEmitterConsumerEntity uses this field to track availability.
        self._infrared_emitter_entity_id = ir_emitter

        # Stable unique ID derived from selected emitter.
        self._attr_unique_id = f"{ir_emitter}_goldair_ir_fan"

        # Optimistic default state because IR fans do not provide state feedback.
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_oscillating = False
        self._attr_preset_mode = None
        self._last_ir_command_at: float | None = None

    async def _send_ir_command(self, command: InfraredCommand) -> None:
        """Send a single IR command through the configured emitter."""
        if self._last_ir_command_at is not None:
            elapsed = monotonic() - self._last_ir_command_at
            if elapsed < IR_COMMAND_DELAY_SECONDS:
                await asyncio.sleep(IR_COMMAND_DELAY_SECONDS - elapsed)

        await self._send_command(command)
        self._last_ir_command_at = monotonic()

    async def _async_power_on_if_needed(self) -> None:
        """Ensure the fan is on before issuing cycle-based commands."""
        if self.is_on:
            return

        # Goldair power is a toggle; turning on always lands at lowest speed.
        await self._send_ir_command(IR_COMMAND_POWER_TOGGLE)
        self._attr_is_on = True
        self._attr_percentage = SPEEDS[0]

        # Assumed default mode after power on for optimistic state tracking.
        self._attr_preset_mode = PRESET_MODES[0]

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

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off using the power toggle command."""
        if not self.is_on:
            return

        await self._send_ir_command(IR_COMMAND_POWER_TOGGLE)
        self._attr_is_on = False
        self._attr_percentage = 0

        # Off state clears active preset in line with fan entity guidance.
        self._attr_preset_mode = None
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by cycling until the nearest discrete speed is reached."""
        if percentage <= 0:
            await self.async_turn_off()
            return

        await self._async_power_on_if_needed()

        # Manual speed changes must clear preset mode per fan entity docs.
        self._attr_preset_mode = None

        # If state drift happened, start from low-speed index as safe fallback.
        current_index = SPEEDS.index(self.percentage) if self.percentage in SPEEDS else 0

        # Convert requested percentage to nearest discrete Goldair speed bucket.
        target_speed = min(SPEEDS, key=lambda speed: abs(speed - percentage))
        target_index = SPEEDS.index(target_speed)

        # Remote only supports forward cycling (low -> mid -> high -> low).
        steps = (target_index - current_index) % len(SPEEDS)
        for _ in range(steps):
            await self._send_ir_command(IR_COMMAND_SPEED_CYCLE)

        self._attr_percentage = target_speed
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Toggle fan oscillation to match the requested boolean state."""
        if self.oscillating == oscillating:
            return

        await self._async_power_on_if_needed()
        await self._send_ir_command(IR_COMMAND_OSC_TOGGLE)
        self._attr_oscillating = oscillating
        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set fan mode by cycling normal -> breeze -> night."""
        if preset_mode not in PRESET_MODES:
            return

        await self._async_power_on_if_needed()

        # Resolve optimistic current mode; default to normal when unknown.
        current_mode = self.preset_mode if self.preset_mode in PRESET_MODES else PRESET_MODES[0]
        current_index = PRESET_MODES.index(current_mode)
        target_index = PRESET_MODES.index(preset_mode)

        # Mode key also cycles forward through all modes.
        steps = (target_index - current_index) % len(PRESET_MODES)
        for _ in range(steps):
            await self._send_ir_command(IR_COMMAND_MODE_CYCLE)

        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
