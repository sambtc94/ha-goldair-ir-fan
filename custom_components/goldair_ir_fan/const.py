"""Constants for the Goldair IR Fan integration."""

# ---------------------------------------------------------------------------
# Integration identity
# ---------------------------------------------------------------------------

# Unique identifier for this integration.  Home Assistant uses this string
# as the key in hass.data and in entity/device unique-IDs, so it must not
# change after an initial install.
DOMAIN = "goldair_ir_fan"

# ---------------------------------------------------------------------------
# Config-entry keys
# ---------------------------------------------------------------------------

# Key used to store the selected remote entity (e.g. remote.broadlink_xxxx)
# inside the config-entry data dict.
CONF_REMOTE_ENTITY = "remote_entity"

# Key used to store the inter-command IR delay (in seconds) inside the
# config-entry options dict.  Options survive HA restarts and can be
# updated from the integration's "Configure" button without re-adding it.
CONF_IR_COMMAND_DELAY = "ir_command_delay"

# Legacy config-entry key written by earlier versions of this integration.
# Kept here so existing entries continue to work after an upgrade.
CONF_IR_EMITTER = "ir_emitter"

# Key for an optional power-monitor sensor entity.  When set, the integration
# watches this sensor and updates the optimistic power-override state based on
# whether the reported wattage is above or below CONF_POWER_THRESHOLD.
CONF_POWER_MONITOR_ENTITY = "power_monitor_entity"

# Key for the watt threshold used together with CONF_POWER_MONITOR_ENTITY.
# Readings above this value set override power state to on; at/below sets off.
CONF_POWER_THRESHOLD = "power_threshold"

# Key for the confirmation delay (seconds) used for power-monitor decisions.
CONF_POWER_LAG_SECONDS = "power_lag_seconds"

# ---------------------------------------------------------------------------
# Display name
# ---------------------------------------------------------------------------

# Human-readable name shown in the HA UI for the device and main entity.
DEFAULT_NAME = "Goldair IR Fan"

# ---------------------------------------------------------------------------
# Fan capabilities
# ---------------------------------------------------------------------------

# The three preset-mode labels exposed to HA automations and the UI.
# Sequence matters: the remote cycles forward through normal → breeze → night.
PRESET_MODES = ["normal", "breeze", "night"]

# Discrete speed steps as percentage values (Low=33 %, Medium=67 %, High=100 %).
# The fan remote cycles forward: 33 → 67 → 100 → 33 …
FAN_SPEEDS = [33, 67, 100]

# ---------------------------------------------------------------------------
# IR command delay – these values define the valid range and UI step for the
# "IR command delay" option in the integration's Configure form.
# ---------------------------------------------------------------------------

# Default delay (seconds) between consecutive IR blasts.  0.5 s gives the
# Broadlink emitter enough time to finish transmitting before the next burst.
IR_COMMAND_DELAY_SECONDS = 0.5
IR_COMMAND_DELAY_MIN_SECONDS = 0.0   # 0 = no forced delay (use with caution)
IR_COMMAND_DELAY_MAX_SECONDS = 5.0   # 5 s is a safe upper bound
IR_COMMAND_DELAY_STEP_SECONDS = 0.1  # step granularity for the UI slider

# ---------------------------------------------------------------------------
# Power-monitor thresholds – these values define the valid range and UI step
# for the "Power threshold" option in the integration's Configure form.
# ---------------------------------------------------------------------------

# Default wattage below which the fan is considered to be off.
DEFAULT_POWER_THRESHOLD = 10.0          # watts
POWER_THRESHOLD_MIN = 0.0              # watts
POWER_THRESHOLD_MAX = 500.0            # watts
POWER_THRESHOLD_STEP = 0.5            # step granularity for the UI slider

# Default confirmation delay for power decisions. Readings must remain beyond
# threshold for this long before toggling optimistic power override.
DEFAULT_POWER_LAG_SECONDS = 60.0       # 1 minute
POWER_LAG_MIN_SECONDS = 0.0            # 0 = immediate threshold handling
POWER_LAG_MAX_SECONDS = 3600.0         # 1 hour upper bound
POWER_LAG_STEP_SECONDS = 1.0           # step granularity for the UI slider

# ---------------------------------------------------------------------------
# Broadlink IR blobs
# ---------------------------------------------------------------------------
# These base-64 strings are raw Broadlink RF/IR codes captured from a physical
# Goldair fan remote.  Each one corresponds to a single button press:
#
#   IR_BLOB_POWER_TOGGLE  – power button (single press toggles on/off)
#   IR_BLOB_SPEED_CYCLE   – speed button (cycles Low → Medium → High → Low)
#   IR_BLOB_OSC_TOGGLE    – oscillation button (toggles swing on/off)
#   IR_BLOB_MODE_CYCLE    – mode button (cycles Normal → Breeze → Night)
#
# To capture new codes for a different Goldair model use the HA service:
#   remote.learn_command  (target your Broadlink remote entity)
# then replace the string below with the learned value.
IR_BLOB_POWER_TOGGLE = (
    "JgDCACkNKQ0OKSgOKQ0OKA8oDSkOKQ0oDikp6SkNKQ4NKSkNKQ0PKA4oDSoNKA4oDygo6ikNKQ4NKSkNKg0OKA0pDikNKA4pDigp6SkOKA4NKSkNKQ4OKA0qDSgOKA8oDCop6SkOKA4OKCkNKA8NKQ4pDSgOKQ4oDSkp6SkOKQ0NKSoNKA4NKg0oDigPKA0pDSoo6igOKQ0OKCkOKA4OKQ0oDikOKA0pDiko6igNKg0OKCkOKA4OKA4oDygNKQ0pDigpAA0F"
)
IR_BLOB_SPEED_CYCLE = (
    "JgC2ACgOKQ0OKCoNKA4OKQ0pDSkOKA4oKQ4NAAEFKQ4oDg0pKQ0pDg0pDSoNKA4oDygoDg4AAQQpDikODSgqDSkNDSoNKQ0oDygOKCkODQABBSkOKA4NKSkNKg0NKQ0qDSgOKA8oKA4NAAEFKQ4pDg0oKg0pDQ4pDSkNKA8oDigpDg0AAQUpDigODSgqDSoNDSkNKQ4oDigPKCgODgABBCkOKA8NKCoNKQ0NKg0pDSgPKA4oKQ4NAA0F"
)
# Oscillation / swing toggle
IR_BLOB_OSC_TOGGLE = (
    "JgC2ACkNKg0NKSkOKA0OKA8oKQ0OKQ0oDygOAAEEKQ0pDg0pKQ0pDQ8oDigpDg0pDSkOKA4AAQQqDSgODSonDioNDigNKigODSkOKA4oDQABBSgPKA4OKCkNKg0OKA0qKA0OKQ4oDigOAAEEKQ4pDg0oKg0pDQ0qDSkpDQ0pDigOKQ0AAQUoDikNDigqDSgODikNKCoNDigOKQ0pDQABBSkOKA0OKSkNKQ4NKQ0pKQ0OKQ0pDSkOAA0F"
)
# Mode / wind-type cycle (Normal → Breeze → Night → Normal)
IR_BLOB_MODE_CYCLE = (
    "JgCcACoNKQ0OKSgOKQ0OKA8oDigOKSgNDygOAAEEKQ0qDQ4oKQ4pDQ4oDigPKA0pKQ0OKA4AAQQqDSoMDikoDikNDigPKA4oDSooDg0pDgABBCkNKg0OKCkOKA0PKA4oDygNKSkNDigOAAEEKg0pDQ4pKA4pDQ4oDikOKA0pKQ4NKA8AAQMqDSoNDigpDigNDygOKA4pDSkpDg0oDgANBQ=="
)


def state_update_signal(entry_id: str) -> str:
    """Return the dispatcher signal name used to broadcast runtime-state changes.

    All entities belonging to the same config entry subscribe to this signal
    so that a change made via one entity (e.g. the fan) is immediately
    reflected on all sibling entities (e.g. the override switches/selects).
    """
    return f"{DOMAIN}_{entry_id}_state_update"
