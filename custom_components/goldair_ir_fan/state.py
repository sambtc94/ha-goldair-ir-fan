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

from dataclasses import dataclass, field

from .const import IR_COMMAND_DELAY_SECONDS


@dataclass
class GoldairIRFanRuntimeState:
    """Shared optimistic state for all Goldair IR Fan entities.

    Fields
    ------
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
    """

    is_on: bool = False
    percentage: int = 0
    oscillating: bool = False
    preset_mode: str | None = None
    # Initialised from the config entry; can be overridden at runtime.
    ir_command_delay_seconds: float = field(default=IR_COMMAND_DELAY_SECONDS)

    def __init__(self, ir_command_delay_seconds: float = IR_COMMAND_DELAY_SECONDS) -> None:
        """Initialise state with the configured IR delay."""
        self.is_on = False
        self.percentage = 0
        self.oscillating = False
        self.preset_mode = None
        self.ir_command_delay_seconds = ir_command_delay_seconds
