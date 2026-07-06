"""Select entities for Goldair IR Fan runtime overrides.

These diagnostic entities complement the switch overrides by letting the user
set the current **speed** and **preset mode** to match the physical fan state
when the integration's optimistic state has drifted.

Entities provided
-----------------
* **Preset override**  – set the tracked preset to normal / breeze / night
* **Speed override**   – set the tracked speed to off / low / medium / high

Neither entity sends an IR command; they only update the shared runtime state.
"""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN, FAN_SPEEDS, PRESET_MODES, state_update_signal
from .state import GoldairIRFanRuntimeState

_LOGGER = logging.getLogger(__name__)

# Human-readable speed option labels used in the HA UI.
SPEED_OPTIONS = ["off", "low", "medium", "high"]

# Map from the UI label to the percentage value stored in runtime state.
SPEED_TO_PERCENTAGE = {
    "off": 0,
    "low": FAN_SPEEDS[0],
    "medium": FAN_SPEEDS[1],
    "high": FAN_SPEEDS[2],
}
# Reverse map: percentage → UI label, built automatically from the above.
PERCENTAGE_TO_SPEED = {value: key for key, value in SPEED_TO_PERCENTAGE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan select entities from a config entry."""
    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    signal = state_update_signal(entry.entry_id)
    # Reuse the same DeviceInfo so all entities appear under one device card.
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEFAULT_NAME,
        manufacturer="Goldair",
        model="IR Fan",
    )
    async_add_entities(
        [
            GoldairIRPresetOverrideSelectEntity(runtime_state, signal, device_info, entry.entry_id),
            GoldairIRSpeedOverrideSelectEntity(runtime_state, signal, device_info, entry.entry_id),
        ]
    )


class GoldairIRPresetOverrideSelectEntity(SelectEntity):
    """Diagnostic select that manually overrides the optimistic preset mode.

    Selecting an option here does NOT send an IR command – it only updates the
    state record so that the next ``set_preset_mode`` call cycles from the
    correct starting point.
    """

    _attr_has_entity_name = True
    _attr_name = "Preset override"
    _attr_options = PRESET_MODES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:weather-windy"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the preset override select."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_preset_override"

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates so the select stays in sync."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when a sibling entity changes the runtime state."""
        self.schedule_update_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the currently tracked preset mode."""
        return self._runtime_state.preset_mode

    async def async_select_option(self, option: str) -> None:
        """Override the tracked preset mode without sending any IR command."""
        if option not in PRESET_MODES:
            return
        self._runtime_state.preset_mode = option
        # If the power state says it's on but speed is 0, that's an inconsistency
        # we should repair so subsequent cycle commands start from a valid index.
        if self._runtime_state.is_on and self._runtime_state.percentage == 0:
            _LOGGER.warning(
                "Preset override state drift detected (on with 0%% speed); defaulting speed to %s",
                FAN_SPEEDS[0],
            )
            self._runtime_state.percentage = FAN_SPEEDS[0]
        async_dispatcher_send(self.hass, self._signal)


class GoldairIRSpeedOverrideSelectEntity(SelectEntity):
    """Diagnostic select that manually overrides the optimistic speed state.

    Selecting an option here does NOT send an IR command – it only updates the
    tracked speed so that the next ``set_percentage`` call cycles from the
    correct starting point.
    """

    _attr_has_entity_name = True
    _attr_name = "Speed override"
    _attr_options = SPEED_OPTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:fan-chevron-up"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the speed override select."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_speed_override"

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates so the select stays in sync."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when a sibling entity changes the runtime state."""
        self.schedule_update_ha_state()

    @property
    def current_option(self) -> str:
        """Return the current speed as a human-readable label.

        Falls back to "low" (with a warning) if the stored percentage is not
        one of the three known discrete values.
        """
        if not self._runtime_state.is_on:
            return "off"
        if self._runtime_state.percentage not in PERCENTAGE_TO_SPEED:
            _LOGGER.warning(
                "Speed override state drift detected (%s); defaulting option to low",
                self._runtime_state.percentage,
            )
            return "low"
        return PERCENTAGE_TO_SPEED[self._runtime_state.percentage]

    async def async_select_option(self, option: str) -> None:
        """Override the tracked speed without sending any IR command."""
        percentage = SPEED_TO_PERCENTAGE.get(option)
        if percentage is None:
            return

        if option == "off":
            # "off" resets the whole fan state (consistent with power override).
            self._runtime_state.is_on = False
            self._runtime_state.percentage = 0
            self._runtime_state.oscillating = False
            self._runtime_state.preset_mode = None
        else:
            # Any non-off speed implies the fan is running.
            self._runtime_state.is_on = True
            self._runtime_state.percentage = percentage
        async_dispatcher_send(self.hass, self._signal)
