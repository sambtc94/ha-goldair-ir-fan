"""Runtime state container for Goldair IR Fan entities."""

from __future__ import annotations

from dataclasses import dataclass

from .const import IR_COMMAND_DELAY_SECONDS


@dataclass
class GoldairIRFanRuntimeState:
    """Shared optimistic state for fan and helper entities."""

    is_on: bool = False
    percentage: int = 0
    oscillating: bool = False
    preset_mode: str | None = None
    ir_command_delay_seconds: float = IR_COMMAND_DELAY_SECONDS
