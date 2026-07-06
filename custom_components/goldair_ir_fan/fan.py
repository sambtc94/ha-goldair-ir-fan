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
it via the override switch/select entities.
"""

from __future__ import annotations

import asyncio
import logging
from time import monotonic

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN, SERVICE_SEND_COMMAND
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

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
    """Set up the Goldair IR Fan entity from a config entry.

    Called once by HA when the integration loads.  We retrieve the remote
    entity ID and shared runtime state from the data bucket created in
    ``__init__.async_setup_entry``, then hand a new entity to HA.
    """
    # Backwards-compat: old entries used the key CONF_IR_EMITTER.
    remote_entity = entry.data.get(CONF_REMOTE_ENTITY) or entry.data.get(CONF_IR_EMITTER)
    if remote_entity is None:
        return

    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    async_add_entities([GoldairIRFanEntity(entry.entry_id, remote_entity, runtime_state)])


class GoldairIRFanEntity(FanEntity):
    """Representation of a Goldair IR fan controlled through a remote entity.

    Supported features
    ------------------
    TURN_ON / TURN_OFF  – power toggle via IR_BLOB_POWER_TOGGLE
    SET_SPEED           – forward-cycle to the nearest of 33 / 67 / 100 %
    OSCILLATE           – toggle swing on/off via IR_BLOB_OSC_TOGGLE
    PRESET_MODE         – forward-cycle through normal / breeze / night modes
    """

    # HA reads these class attributes to know what the entity supports.
    _attr_name = DEFAULT_NAME
    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.OSCILLATE
        | FanEntityFeature.PRESET_MODE
    )
    # Three discrete speed steps – HA maps a 0-100 % slider to these buckets.
    _attr_speed_count = 3
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        entry_id: str,
        remote_entity: str,
        runtime_state: GoldairIRFanRuntimeState,
    ) -> None:
        """Initialize the fan entity with its config-entry ID and remote entity."""
        self._entry_id = entry_id
        self._runtime_state = runtime_state
        # The dispatcher signal key shared with sibling override entities.
        self._state_update_signal = state_update_signal(entry_id)

        self._remote_entity_id = remote_entity

        # Unique ID is derived from the remote entity so it survives HA restarts.
        self._attr_unique_id = f"{remote_entity}_goldair_ir_fan"
        # DeviceInfo groups this entity (and the override entities) under a
        # single device card in the HA device registry.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=DEFAULT_NAME,
            manufacturer="Goldair",
            model="IR Fan",
        )

        # Populate HA entity attributes from the current runtime state.
        self._sync_attrs_from_runtime_state()
        # Track when the last IR command was sent so we can enforce the delay.
        self._last_ir_command_at: float | None = None

    # ------------------------------------------------------------------
    # HA lifecycle hooks
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True only when the configured remote entity is reachable.

        If the Broadlink device goes offline the remote entity state becomes
        ``unavailable``; we reflect that here so HA shows the fan as unavailable
        too rather than silently accepting commands that will never be sent.
        """
        remote_state = self.hass.states.get(self._remote_entity_id)
        if remote_state is None:
            return False
        return remote_state.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates once the entity is registered."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._state_update_signal,
                self._handle_runtime_state_update,
            )
        )

        # Subscribe to the power-monitor sensor if one is configured.
        if self._runtime_state.power_monitor_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._runtime_state.power_monitor_entity],
                    self._handle_power_sensor_state_change,
                )
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sync_attrs_from_runtime_state(self) -> None:
        """Copy the current runtime state into the HA entity attribute cache.

        HA reads ``_attr_*`` attributes when building the entity state; calling
        this method keeps them in sync after any change to ``_runtime_state``.
        """
        self._attr_is_on = self._runtime_state.is_on
        self._attr_percentage = self._runtime_state.percentage
        self._attr_oscillating = self._runtime_state.oscillating
        self._attr_preset_mode = self._runtime_state.preset_mode

    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when the shared runtime state is updated by another entity."""
        self._sync_attrs_from_runtime_state()
        self.schedule_update_ha_state()

    async def _handle_power_sensor_state_change(self, event: Event) -> None:
        """React to power-sensor state changes to keep the fan in sync.

        If the reported wattage rises above the configured threshold and the
        integration believes the fan is off, the fan is turned on at low speed.

        If the reported wattage drops to or below the threshold and the
        integration believes the fan is on, the fan is turned off.

        States that cannot be parsed as a number (unavailable, unknown, etc.)
        are silently ignored to avoid spurious commands.
        """
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            return

        try:
            watts = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Power sensor %s reported non-numeric state '%s'; ignoring",
                self._runtime_state.power_monitor_entity,
                new_state.state,
            )
            return

        threshold = self._runtime_state.power_threshold

        if watts > threshold and not self._runtime_state.is_on:
            _LOGGER.debug(
                "Power sensor reads %.1f W (> %.1f W threshold); turning fan on",
                watts,
                threshold,
            )
            await self.async_turn_on()
        elif watts <= threshold and self._runtime_state.is_on:
            _LOGGER.debug(
                "Power sensor reads %.1f W (<= %.1f W threshold); turning fan off",
                watts,
                threshold,
            )
            await self.async_turn_off()

    def _publish_runtime_state(self) -> None:
        """Broadcast a runtime-state-changed signal to all sibling entities."""
        async_dispatcher_send(self.hass, self._state_update_signal)

    async def _send_ir_command(self, command: str) -> None:
        """Send a single Broadlink raw IR command via the configured remote entity.

        If not enough time has elapsed since the previous command, this method
        sleeps for the remaining delay before transmitting.  This gives the
        Broadlink hardware time to finish the previous transmission.

        The command string is expected to be a base-64 blob (as stored in
        ``const.py``).  The ``b64:`` prefix required by the Broadlink integration
        is added automatically if it is missing.
        """
        if not isinstance(command, str):
            raise TypeError("IR command must be a string")

        # Enforce the inter-command delay if a previous command was sent recently.
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
        )
        self._last_ir_command_at = monotonic()

    async def _async_power_on_if_needed(self) -> None:
        """Send a power-on command if the fan is currently believed to be off.

        Turning the fan on always lands at the lowest speed (33 %), no
        oscillation, normal mode – matching the physical remote behaviour.
        """
        if self.is_on:
            return

        await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
        # Update optimistic state to reflect the expected post-power-on condition.
        self._runtime_state.is_on = True
        self._runtime_state.percentage = FAN_SPEEDS[0]   # lowest speed
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = PRESET_MODES[0]  # normal
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    # ------------------------------------------------------------------
    # FanEntity service methods (called by HA automations / the UI)
    # ------------------------------------------------------------------

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn the fan on, optionally setting speed or preset at the same time."""
        await self._async_power_on_if_needed()

        # If both percentage and preset are provided, preset takes priority.
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None and percentage > 0:
            await self.async_set_percentage(percentage)

        self._sync_attrs_from_runtime_state()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the fan off using the power-toggle IR command."""
        if not self.is_on:
            return  # already off; nothing to do

        await self._send_ir_command(IR_BLOB_POWER_TOGGLE)
        # Reset all state to the "off" baseline.
        self._runtime_state.is_on = False
        self._runtime_state.percentage = 0
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = None
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by forward-cycling until the target speed is reached.

        The Goldair remote only has a single speed key that cycles through three
        steps: low (33 %) → medium (67 %) → high (100 %) → low …

        We calculate the number of forward steps needed to go from the current
        speed to the closest discrete speed and send that many IR blasts.
        """
        if percentage <= 0:
            await self.async_turn_off()
            return

        await self._async_power_on_if_needed()

        # Guard against state drift where the stored speed is not one of the
        # three known values (e.g. after an external power-cycle).
        if self.percentage not in FAN_SPEEDS:
            _LOGGER.warning(
                "Fan speed state drift detected (%s); defaulting cycle base to %s",
                self.percentage,
                FAN_SPEEDS[0],
            )
            current_index = 0
        else:
            current_index = FAN_SPEEDS.index(self.percentage)

        # Round the requested percentage to the nearest supported speed bucket.
        target_speed = min(FAN_SPEEDS, key=lambda speed: abs(speed - percentage))
        target_index = FAN_SPEEDS.index(target_speed)

        # Modular arithmetic gives us the forward-only step count:
        # e.g. from index 2 (high) to index 0 (low) = (0 - 2) % 3 = 1 step.
        steps = (target_index - current_index) % len(FAN_SPEEDS)
        for _ in range(steps):
            await self._send_ir_command(IR_BLOB_SPEED_CYCLE)

        self._runtime_state.percentage = target_speed
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Toggle oscillation to match the requested state.

        The remote only has a toggle, so we only send the command if the
        requested state differs from the current state.
        """
        if self.oscillating == oscillating:
            return  # already in the requested state

        await self._async_power_on_if_needed()
        await self._send_ir_command(IR_BLOB_OSC_TOGGLE)
        self._runtime_state.oscillating = oscillating
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the wind-mode preset by forward-cycling to the requested mode.

        Like speed, the Goldair remote cycles through presets with a single key:
        normal → breeze → night → normal …
        """
        if preset_mode not in PRESET_MODES:
            return

        await self._async_power_on_if_needed()

        # Guard against state drift in the same way as async_set_percentage.
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

        # Forward-only step count using modular arithmetic.
        steps = (target_index - current_index) % len(PRESET_MODES)
        for _ in range(steps):
            await self._send_ir_command(IR_BLOB_MODE_CYCLE)

        self._runtime_state.preset_mode = preset_mode
        self._sync_attrs_from_runtime_state()
        self._publish_runtime_state()
