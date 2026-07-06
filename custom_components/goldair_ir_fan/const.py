"""Constants for the Goldair IR Fan integration."""

# Domain used by Home Assistant for this custom integration.
DOMAIN = "goldair_ir_fan"

# Config-entry key for the selected remote entity.
CONF_REMOTE_ENTITY = "remote_entity"

# Legacy config-entry key used by earlier infrared-emitter versions.
CONF_IR_EMITTER = "ir_emitter"

# Friendly integration/entity name displayed in Home Assistant.
DEFAULT_NAME = "Goldair IR Fan"

# Supported user-facing preset mode labels.
PRESET_MODES = ["normal", "breeze", "night"]

# Discrete speed percentages supported by the Goldair fan.
FAN_SPEEDS = [33, 67, 100]

# Delay required between consecutive IR commands sent to the emitter.
IR_COMMAND_DELAY_SECONDS = 0.5
IR_COMMAND_DELAY_MIN_SECONDS = 0.0
IR_COMMAND_DELAY_MAX_SECONDS = 5.0
IR_COMMAND_DELAY_STEP_SECONDS = 0.1

# Hardcoded Broadlink raw IR blobs (base64) for Goldair fan controls.
IR_BLOB_POWER_TOGGLE = (
    "JgDCACkNKQ0OKSgOKQ0OKA8oDSkOKQ0oDikp6SkNKQ4NKSkNKQ0PKA4oDSoNKA4oDygo6ikNKQ4NKSkNKg0OKA0pDikNKA4pDigp6SkOKA4NKSkNKQ4OKA0qDSgOKA8oDCop6SkOKA4OKCkNKA8NKQ4pDSgOKQ4oDSkp6SkOKQ0NKSoNKA4NKg0oDigPKA0pDSoo6igOKQ0OKCkOKA4OKQ0oDikOKA0pDiko6igNKg0OKCkOKA4OKA4oDygNKQ0pDigpAA0F"
)
IR_BLOB_SPEED_CYCLE = (
    "JgC2ACgOKQ0OKCoNKA4OKQ0pDSkOKA4oKQ4NAAEFKQ4oDg0pKQ0pDg0pDSoNKA4oDygoDg4AAQQpDikODSgqDSkNDSoNKQ0oDygOKCkODQABBSkOKA4NKSkNKg0NKQ0qDSgOKA8oKA4NAAEFKQ4pDg0oKg0pDQ4pDSkNKA8oDigpDg0AAQUpDigODSgqDSoNDSkNKQ4oDigPKCgODgABBCkOKA8NKCoNKQ0NKg0pDSgPKA4oKQ4NAA0F"
)
IR_BLOB_OSC_TOGGLE = (
    "JgC2ACkNKg0NKSkOKA0OKA8oKQ0OKQ0oDygOAAEEKQ0pDg0pKQ0pDQ8oDigpDg0pDSkOKA4AAQQqDSgODSonDioNDigNKigODSkOKA4oDQABBSgPKA4OKCkNKg0OKA0qKA0OKQ4oDigOAAEEKQ4pDg0oKg0pDQ0qDSkpDQ0pDigOKQ0AAQUoDikNDigqDSgODikNKCoNDigOKQ0pDQABBSkOKA0OKSkNKQ4NKQ0pKQ0OKQ0pDSkOAA0F"
)
IR_BLOB_MODE_CYCLE = (
    "JgCcACoNKQ0OKSgOKQ0OKA8oDigOKSgNDygOAAEEKQ0qDQ4oKQ4pDQ4oDigPKA0pKQ0OKA4AAQQqDSoMDikoDikNDigPKA4oDSooDg0pDgABBCkNKg0OKCkOKA0PKA4oDygNKSkNDigOAAEEKg0pDQ4pKA4pDQ4oDikOKA0pKQ4NKA8AAQMqDSoNDigpDigNDygOKA4pDSkpDg0oDgANBQ=="
)


def state_update_signal(entry_id: str) -> str:
    """Return dispatcher signal used for runtime state updates."""
    return f"{DOMAIN}_{entry_id}_state_update"
