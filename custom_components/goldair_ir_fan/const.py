"""Constants for the Goldair IR Fan integration."""

from infrared_protocols.commands.nec import NECCommand

# Domain used by Home Assistant for this custom integration.
DOMAIN = "goldair_ir_fan"

# Config-entry key for the selected infrared emitter entity.
CONF_IR_EMITTER = "ir_emitter"

# Legacy key kept for backward compatibility with already-created entries.
CONF_IR_BLASTER_LEGACY = "ir_blaster"

# Friendly integration/entity name displayed in Home Assistant.
DEFAULT_NAME = "Goldair IR Fan"

# Supported user-facing preset mode labels.
PRESET_MODES = ["normal", "breeze", "night"]

# The Goldair remote uses a 38 kHz IR carrier with NEC protocol commands.
NEC_MODULATION = 38_000

# Toggle commands exposed by the Goldair fan remote.
IR_COMMAND_POWER_TOGGLE = NECCommand(
    address=0x00FF,
    command=0x20DF,
    modulation=NEC_MODULATION,
)
IR_COMMAND_SPEED_CYCLE = NECCommand(
    address=0x00FF,
    command=0xA05F,
    modulation=NEC_MODULATION,
)
IR_COMMAND_OSC_TOGGLE = NECCommand(
    address=0x00FF,
    command=0xE01F,
    modulation=NEC_MODULATION,
)
IR_COMMAND_MODE_CYCLE = NECCommand(
    address=0x00FF,
    command=0x609F,
    modulation=NEC_MODULATION,
)
