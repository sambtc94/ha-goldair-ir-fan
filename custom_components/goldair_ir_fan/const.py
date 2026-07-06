"""Constants for the Goldair IR Fan integration."""

DOMAIN = "goldair_ir_fan"

CONF_IR_BLASTER = "ir_blaster"

DEFAULT_NAME = "Goldair IR Fan"

PRESET_MODES = ["normal", "breeze", "night"]

# Infrared command blocks (Home Assistant 2024.3+ block format)
IR_BLOCK_POWER_TOGGLE = {"protocol": "NEC", "address": "0x00FF", "command": "0x20DF"}
IR_BLOCK_SPEED_CYCLE = {"protocol": "NEC", "address": "0x00FF", "command": "0xA05F"}
IR_BLOCK_OSC_TOGGLE = {"protocol": "NEC", "address": "0x00FF", "command": "0xE01F"}
IR_BLOCK_MODE_CYCLE = {"protocol": "NEC", "address": "0x00FF", "command": "0x609F"}
