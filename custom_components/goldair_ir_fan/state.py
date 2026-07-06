"""Runtime state container for Goldair IR Fan entities.

Because the Goldair fan is controlled entirely by IR (no feedback channel),
Home Assistant has no way to *read* the current fan state from the device.
We therefore maintain an *optimistic* in-memory state that tracks what we
*believe* the fan is doing based on the commands we have sent.

All platform entities (fan, switch, select) share a single instance of
:class:`GoldairIRFanRuntimeState` so they all stay in sync.  When any entity
changes the state it publishes a dispatcher signal (see :func:`state_update_signal`)
so that sibling entities can refresh their HA state.
"""

from __future__ import annotations

from .const import (
    DEFAULT_POWER_LAG_SECONDS,
    DEFAULT_POWER_THRESHOLD,
    IR_COMMAND_DELAY_SECONDS,
)


class GoldairIRFanRuntimeState:
    """Shared optimistic state for all Goldair IR Fan entities.

    Attributes
    ----------
    is_on
        Whether we believe the fan is currently running.
    percentage
        Last speed percentage sent to the fan (0 = off, 33/67/100 = low/med/high).
    oscillating
        Whether the fan's oscillation / swing is active.
    preset_mode
        Active wind-mode preset: "normal", "breeze", or "night" (None when off).
    ir_command_delay_seconds
        Minimum pause between consecutive IR blasts.  Populated from the config
        entry options so that it survives HA restarts.
    power_monitor_entity
        Optional sensor entity ID (e.g. ``sensor.fan_power``) whose state (in
        watts) is watched to update optimistic power-override state.  ``None``
        means no power-monitor integration.
    power_threshold
        Wattage threshold used together with ``power_monitor_entity``.  Readings
        strictly above this value set override power state to on; readings at
        or below it set override power state to off.
    power_lag_seconds
        Lag window (seconds) used to average power readings before applying
        threshold decisions.  A value of ``0`` disables averaging.
    """

    def __init__(
        self,
        ir_command_delay_seconds: float = IR_COMMAND_DELAY_SECONDS,
        power_monitor_entity: str | None = None,
        power_threshold: float = DEFAULT_POWER_THRESHOLD,
        power_lag_seconds: float = DEFAULT_POWER_LAG_SECONDS,
    ) -> None:
        """Initialize state with the configured IR delay and optional power monitor."""
        self.is_on: bool = False
        self.percentage: int = 0
        self.oscillating: bool = False
        self.preset_mode: str | None = None
        # Initialized from the config entry; can be updated live when options change.
        self.ir_command_delay_seconds: float = ir_command_delay_seconds
        # Power-monitor settings (populated from config entry options/data).
        self.power_monitor_entity: str | None = power_monitor_entity
        self.power_threshold: float = power_threshold
        self.power_lag_seconds: float = power_lag_seconds
