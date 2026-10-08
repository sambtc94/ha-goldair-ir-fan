"""Fan platform for Goldair IR Fan.

This module registers a single :class:`GoldairIRFanEntity` that exposes the
Goldair IR fan as a standard HA fan entity with speed, oscillation and preset-
mode support.

How it works
------------
The Goldair fan remote only has *toggle / cycle* buttons – there is no
discrete "set speed 2" command.  Instead the integration tracks the *last
known state* in a shared :class:`~.state.GoldairIRFanRuntimeState` object and
sends the minimum number of cycle presses to reach the requested target.

For example: if the fan is currently at low speed (33 %) and the user requests
high speed (100 %), the integration sends two speed-cycle IR blasts to advance
low → medium → high.

Because there is no feedback channel (it is IR-only), the integration is
*optimistic*: it trusts its own state record unless the user manually corrects
it via the override switch/select entities, or a power monitor reports that
the fan has been switched on or off some other way.

Commands are serialised with a lock: each cycle calculation starts from the
state left by the previous command, so overlapping calls (a dragged speed
slider, two automations firing together) can't send too many presses.
"""

from __future__ import annotations

import asyncio
import logging
from time import monotonic
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN, SERVICE_SEND_COMMAND
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_IR_EMITTER,
    CONF_REMOTE_ENTITY,
    FAN_SPEEDS,
    IR_BLOB_MODE_CYCLE,
    IR_BLOB_OSC_TOGGLE,
    IR_BLOB_POWER_TOGGLE,
    IR_BLOB_SPEED_CYCLE,
    PRESET_MODES,
    state_update_signal,
)
from .entity import GoldairIRFanConfigEntry, goldair_device_info

_LOGGER = logging.getLogger(__name__)

# The entity serialises its own commands with a lock (see module docstring).
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoldairIRFanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Goldair IR Fan entity from a config entry."""
    # Backwards-compat: old entries used the key CONF_IR_EMITTER.
    remote_entity = entry.data.get(CONF_REMOTE_ENTITY) or entry.data.get(CONF_IR_EMITTER)
    if remote_entity is None:
        return
    async_add_entities([GoldairIRFanEntity(entry, remote_entity)])


class GoldairIRFanEntity(FanEntity, RestoreEntity):
    """Representation of a Goldair IR fan controlled through a remote entity.

    Supported features
    ------------------
    TURN_ON / TURN_OFF  – power toggle via IR_BLOB_POWER_TOGGLE
    SET_SPEED           – forward-cycle to the nearest of 33 / 67 / 100 %
    OSCILLATE           – toggle swing on/off via IR_BLOB_OSC_TOGGLE
    PRESET_MODE         – forward-cycle through normal / breeze / night modes
    """

    # The fan is the device's main feature, so it takes the device name.
    _attr_name = None
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
    )
    # Three discrete speed steps – HA maps a 0-100 % slider to these buckets.
    _attr_speed_count = len(FAN_SPEEDS)
    _attr_preset_modes = PRESET_MODES

    def __init__(self, entry: GoldairIRFanConfigEntry, remote_entity: str) -> None:
        """Initialize the fan entity with its config entry and remote entity."""
        self._runtime_state = entry.runtime_data
        # The dispatcher signal key shared with sibling override entities.
        self._state_update_signal = state_update_signal(entry.entry_id)
        self._remote_entity_id = remote_entity

        # Keyed on the config entry so several fans can share one IR blaster.
        self._attr_unique_id = f"{entry.entry_id}_fan"
        # DeviceInfo groups this entity (and the override entities) under a
        # single device card in the HA device registry.
        self._attr_device_info = goldair_device_info(entry)

        self._sync_attrs_from_runtime_state()
        # Serialises IR command sequences (see module docstring).
        self._command_lock = asyncio.Lock()
        # Track when the last IR command was sent so we can enforce the delay.
        self._last_ir_command_at: float | None = None
        # Last numeric power sensor reading seen by this entity.
        self._latest_power_watts: float | None = None
        # Pending delayed confirmation task for threshold handling.
        self._pending_override_task: asyncio.Task | None = None
        self._pending_override_target_is_on: bool | None = None

    # ------------------------------------------------------------------
    # HA lifecycle hooks
    # ------------------------------------------------------------------

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to updates once the entity is registered."""
        await super().async_added_to_hass()

        # Restore the optimistic state recorded before the last restart or
        # reload, so we don't assume "off" while the fan is actually running.
        self._restore_runtime_state(await self.async_get_last_state())

        # Mirror the remote entity's availability.
        self._attr_available = self._remote_is_available(
            self.hass.states.get(self._remote_entity_id)
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._remote_entity_id], self._handle_remote_state_change
            )
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._state_update_signal,
                self._handle_runtime_state_update,
            )
        )

        # Subscribe to the power-monitor sensor if one is configured, and
        # evaluate its current reading now rather than waiting for a change.
        if power_entity := self._runtime_state.power_monitor_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [power_entity], self._handle_power_sensor_state_change
                )
            )
            self._evaluate_power_state(self.hass.states.get(power_entity))

        # Let sibling entities that were added before us pick up the restored state.
        self._publish_runtime_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending delayed power-confirmation work on entity removal."""
        self._cancel_pending_override_confirmation()
        await super().async_will_remove_from_hass()

    @callback
    def _restore_runtime_state(self, last_state: State | None) -> None:
        """Seed the shared runtime state from the last recorded fan state."""
        if last_state is None or last_state.state not in (STATE_ON, STATE_OFF):
            return

        if last_state.state == STATE_OFF:
            self._runtime_state.set_off()
            return

        attrs = last_state.attributes
        percentage = attrs.get("percentage")
        preset_mode = attrs.get("preset_mode")
        self._runtime_state.is_on = True
        self._runtime_state.percentage = (
            percentage if percentage in FAN_SPEEDS else FAN_SPEEDS[0]
        )
        self._runtime_state.preset_mode = (
            preset_mode if preset_mode in PRESET_MODES else PRESET_MODES[0]
        )
        self._runtime_state.oscillating = bool(attrs.get("oscillating", False))

    @staticmethod
    def _remote_is_available(state: State | None) -> bool:
        """Return True if the remote entity is usable."""
        return state is not None and state.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}

    @callback
    def _handle_remote_state_change(self, event: Event[EventStateChangedData]) -> None:
        """Update availability when the remote entity goes on/offline."""
        available = self._remote_is_available(event.data["new_state"])
        if available != self._attr_available:
            self._attr_available = available
            self.async_write_ha_state()

    # ------------------------------------------------------------------
    # Runtime state helpers
    # ------------------------------------------------------------------

    @callback
    def _sync_attrs_from_runtime_state(self) -> None:
        """Copy the current runtime state into the HA entity attribute cache."""
        self._attr_is_on = self._runtime_state.is_on
        self._attr_percentage = self._runtime_state.percentage
        self._attr_oscillating = self._runtime_state.oscillating
        self._attr_preset_mode = self._runtime_state.preset_mode

    @callback
    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when the shared runtime state changes."""
        self._sync_attrs_from_runtime_state()
        self.async_write_ha_state()

    @callback
    def _publish_runtime_state(self) -> None:
        """Broadcast a runtime-state-changed signal to all entities, this one included."""
        async_dispatcher_send(self.hass, self._state_update_signal)

    # ------------------------------------------------------------------
    # Power monitor
    # ------------------------------------------------------------------

    @callback
    def _handle_power_sensor_state_change(self, event: Event[EventStateChangedData]) -> None:
        """React to power-sensor state changes."""
        self._evaluate_power_state(event.data["new_state"])

    @callback
    def _evaluate_power_state(self, state: State | None) -> None:
        """Compare a power reading against the threshold and the believed state.

        When the reading crosses the threshold relative to the current optimistic
        power state, a delayed confirmation timer is started.  Once that timer
        elapses we re-check the latest reading and only apply the override if it
        is still on the same side of the threshold.

        States that cannot be parsed as a number (unavailable, unknown, etc.)
        are ignored.
        """
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return

        try:
            watts = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Power sensor %s reported non-numeric state '%s'; ignoring",
                self._runtime_state.power_monitor_entity,
                state.state,
            )
            return

        self._latest_power_watts = watts
        threshold = self._runtime_state.power_threshold
        lag_seconds = max(0.0, self._runtime_state.power_lag_seconds)
        target_is_on = watts > threshold

        # No change needed; cancel any previously pending opposite confirmation.
        if target_is_on == self._runtime_state.is_on:
            self._cancel_pending_override_confirmation()
            return

        # Keep existing timer if it is already waiting for the same target.
        if self._pending_override_target_is_on == target_is_on:
            return

        self._cancel_pending_override_confirmation()
        self._pending_override_target_is_on = target_is_on
        self._pending_override_task = self.hass.async_create_background_task(
            self._confirm_and_apply_power_override(target_is_on, threshold, lag_seconds),
            f"goldair_ir_fan power override {self.entity_id}",
        )

    async def _confirm_and_apply_power_override(
        self,
        target_is_on: bool,
        threshold: float,
        lag_seconds: float,
    ) -> None:
        """Wait lag duration, re-check latest power, then apply override if still valid."""
        try:
            if lag_seconds > 0.0:
                await asyncio.sleep(lag_seconds)

            watts = self._latest_power_watts
            if watts is None:
                return

            still_matches = watts > threshold if target_is_on else watts <= threshold
            if not still_matches:
                _LOGGER.debug(
                    "Power %.1f W no longer matches delayed target after %.1f s; skipping override",
                    watts,
                    lag_seconds,
                )
                return

            # Don't fight a command that is being sent right now; the next
            # power reading will re-evaluate once it has finished.
            if target_is_on == self._runtime_state.is_on or self._command_lock.locked():
                return

            _LOGGER.debug(
                "Power %.1f W still %s threshold after %.1f s; setting power override %s",
                watts,
                ">" if target_is_on else "<=",
                lag_seconds,
                "on" if target_is_on else "off",
            )
            if target_is_on:
                self._runtime_state.set_on_defaults()
            else:
                self._runtime_state.set_off()
            self._publish_runtime_state()
        finally:
            if asyncio.current_task() is self._pending_override_task:
                self._pending_override_task = None
                self._pending_override_target_is_on = None

    @callback
    def _cancel_pending_override_confirmation(self) -> None:
        """Cancel any in-flight delayed threshold confirmation task."""
        if self._pending_override_task is not None:
            self._pending_override_task.cancel()
            self._pending_override_task = None
            self._pending_override_target_is_on = None

    # ------------------------------------------------------------------
    # IR sending (call only while holding self._command_lock)
    # ------------------------------------------------------------------

    async def _send_ir_command(self, command: str) -> None:
        """Send a single Broadlink raw IR command via the configured remote entity.

        If not enough time has elapsed since the previous command, this method
        sleeps for the remaining delay before transmitting.  This gives the
        Broadlink hardware time to finish the previous transmission.
        """
        if self._last_ir_command_at is not None:
            elapsed = monotonic() - self._last_ir_command_at
            if elapsed < self._runtime_state.ir_command_delay_seconds:
                await asyncio.sleep(self._runtime_state.ir_command_delay_seconds - elapsed)

        # The Broadlink HA integration expects the payload prefixed with "b64:".
        command_payload = command if command.startswith("b64:") else f"b64:{command}"
        await self.hass.services.async_call(
            REMOTE_DOMAIN,
            SERVICE_SEND_COMMAND,
            {"command": [command_payload]},
            target={"entity_id": self._remote_entity_id},
            blocking=True,
            context=self._context,
        )
        self._last_ir_command_at = monotonic()

    async def _power_on_if_needed(self) -> None:
        """Send a power-on command if the fan is currently believed to be off.

        Turning the fan on always lands at the lowest speed (33 %), no
        oscillation, normal mode – matching the physical remote behaviour.
        """
        if self._runtime_state.is_on:
            return
        await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
        self._runtime_state.set_on_defaults()
        self._publish_runtime_state()

    async def _set_percentage(self, percentage: int) -> None:
        """Forward-cycle the speed to the bucket nearest ``percentage``."""
        await self._power_on_if_needed()

        # Guard against state drift where the stored speed is not one of the
        # three known values.
        if self._runtime_state.percentage not in FAN_SPEEDS:
            _LOGGER.warning(
                "Fan speed state drift detected (%s); defaulting cycle base to %s",
                self._runtime_state.percentage,
                FAN_SPEEDS[0],
            )
            self._runtime_state.percentage = FAN_SPEEDS[0]

        target_speed = min(FAN_SPEEDS, key=lambda speed: abs(speed - percentage))
        current_index = FAN_SPEEDS.index(self._runtime_state.percentage)
        target_index = FAN_SPEEDS.index(target_speed)

        # Forward-only step count: e.g. from high (2) to low (0) = 1 press.
        steps = (target_index - current_index) % len(FAN_SPEEDS)
        for step in range(1, steps + 1):
            await self._send_ir_command(IR_BLOB_SPEED_CYCLE)
            # Record each press as it lands, so a failure part-way through
            # leaves the tracked state matching what the fan actually received.
            self._runtime_state.percentage = FAN_SPEEDS[
                (current_index + step) % len(FAN_SPEEDS)
            ]
        self._publish_runtime_state()

    async def _set_preset_mode(self, preset_mode: str) -> None:
        """Forward-cycle the wind mode to ``preset_mode``."""
        await self._power_on_if_needed()

        if self._runtime_state.preset_mode not in PRESET_MODES:
            _LOGGER.warning(
                "Fan preset state drift detected (%s); defaulting cycle base to %s",
                self._runtime_state.preset_mode,
                PRESET_MODES[0],
            )
            self._runtime_state.preset_mode = PRESET_MODES[0]

        current_index = PRESET_MODES.index(self._runtime_state.preset_mode)
        target_index = PRESET_MODES.index(preset_mode)

        steps = (target_index - current_index) % len(PRESET_MODES)
        for step in range(1, steps + 1):
            await self._send_ir_command(IR_BLOB_MODE_CYCLE)
            self._runtime_state.preset_mode = PRESET_MODES[
                (current_index + step) % len(PRESET_MODES)
            ]
        self._publish_runtime_state()

    # ------------------------------------------------------------------
    # FanEntity service methods (called by HA automations / the UI)
    # ------------------------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on, optionally setting speed or preset at the same time."""
        async with self._command_lock:
            await self._power_on_if_needed()
            # If both percentage and preset are provided, preset takes priority.
            if preset_mode is not None:
                await self._set_preset_mode(preset_mode)
            elif percentage is not None and percentage > 0:
                await self._set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off using the power-toggle IR command."""
        async with self._command_lock:
            if not self._runtime_state.is_on:
                return  # already off; nothing to do
            await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
            self._runtime_state.set_off()
            self._publish_runtime_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by forward-cycling until the target speed is reached."""
        if percentage <= 0:
            await self.async_turn_off()
            return
        async with self._command_lock:
            await self._set_percentage(percentage)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Toggle oscillation to match the requested state."""
        async with self._command_lock:
            if self._runtime_state.oscillating == oscillating:
                return  # already in the requested state
            await self._power_on_if_needed()
            await self._send_ir_command(IR_BLOB_OSC_TOGGLE)
            self._runtime_state.oscillating = oscillating
            self._publish_runtime_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the wind-mode preset by forward-cycling to the requested mode."""
        # FanEntity's service handler validates preset_mode against
        # preset_modes before this is called.
        async with self._command_lock:
            await self._set_preset_mode(preset_mode)
