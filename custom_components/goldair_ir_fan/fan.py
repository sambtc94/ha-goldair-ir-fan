"""Fan platform for Goldair IR Fan."""

from __future__ import annotations

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.components.remote import (
    ATTR_COMMAND,
    DOMAIN as REMOTE_DOMAIN,
    SERVICE_SEND_COMMAND,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_IR_BLASTER,
    DEFAULT_NAME,
    IR_BLOCK_MODE_CYCLE,
    IR_BLOCK_OSC_TOGGLE,
    IR_BLOCK_POWER_TOGGLE,
    IR_BLOCK_SPEED_CYCLE,
    PRESET_MODES,
)

SPEEDS = [33, 67, 100]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan entity from a config entry."""
    async_add_entities([GoldairIRFanEntity(hass, entry.data[CONF_IR_BLASTER])])


class GoldairIRFanEntity(FanEntity):
    """Representation of a Goldair IR fan controlled by an IR blaster."""

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

    def __init__(self, hass: HomeAssistant, ir_blaster: str) -> None:
        """Initialize the fan."""
        self.hass = hass
        self._ir_blaster = ir_blaster
        self._attr_is_on = False
        self._attr_percentage = 0
        self._attr_oscillating = False
        self._attr_preset_mode = PRESET_MODES[0]

    async def _send_ir_block(self, block: dict[str, str]) -> None:
        """Send an infrared command block through the selected IR blaster."""
        await self.hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: self._ir_blaster,
                ATTR_COMMAND: [block],
            },
            blocking=True,
        )

    async def async_turn_on(self, percentage: int | None = None, **kwargs) -> None:
        """Turn the fan on."""
        if not self.is_on:
            await self._send_ir_block(IR_BLOCK_POWER_TOGGLE)
            self._attr_is_on = True
            self._attr_percentage = SPEEDS[0]

        if percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        if self.is_on:
            await self._send_ir_block(IR_BLOCK_POWER_TOGGLE)
            self._attr_is_on = False
            self._attr_percentage = 0
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set speed percentage by cycling through the 3 fan speeds."""
        if percentage <= 0:
            await self.async_turn_off()
            return

        if not self.is_on:
            await self.async_turn_on()

        current_index = 0
        if self.percentage in SPEEDS:
            current_index = SPEEDS.index(self.percentage)

        target_index = min(range(len(SPEEDS)), key=lambda i: abs(SPEEDS[i] - percentage))
        steps = (target_index - current_index) % len(SPEEDS)

        for _ in range(steps):
            await self._send_ir_block(IR_BLOCK_SPEED_CYCLE)

        self._attr_percentage = SPEEDS[target_index]
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Toggle fan oscillation."""
        if self.oscillating != oscillating:
            await self._send_ir_block(IR_BLOCK_OSC_TOGGLE)
            self._attr_oscillating = oscillating
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set fan mode by cycling normal -> breeze -> night."""
        if preset_mode not in PRESET_MODES:
            return

        if not self.is_on:
            await self.async_turn_on()

        current_index = PRESET_MODES.index(self.preset_mode)
        target_index = PRESET_MODES.index(preset_mode)
        steps = (target_index - current_index) % len(PRESET_MODES)

        for _ in range(steps):
            await self._send_ir_block(IR_BLOCK_MODE_CYCLE)

        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
