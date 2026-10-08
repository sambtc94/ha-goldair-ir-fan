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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FAN_SPEEDS, PRESET_MODES
from .entity import GoldairIRFanConfigEntry, GoldairIRFanOverrideEntity

_LOGGER = logging.getLogger(__name__)

# Override entities only touch in-memory state, so they can run in parallel.
PARALLEL_UPDATES = 0

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
    entry: GoldairIRFanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan select entities from a config entry."""
    async_add_entities(
        [
            GoldairIRPresetOverrideSelectEntity(entry, "preset_override"),
            GoldairIRSpeedOverrideSelectEntity(entry, "speed_override"),
        ]
    )


class GoldairIRPresetOverrideSelectEntity(GoldairIRFanOverrideEntity, SelectEntity):
    """Diagnostic select that manually overrides the optimistic preset mode.

    Selecting an option here does NOT send an IR command – it only updates the
    state record so that the next ``set_preset_mode`` call cycles from the
    correct starting point.
    """

    _attr_name = "Preset override"
    _attr_options = PRESET_MODES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:weather-windy"

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


class GoldairIRSpeedOverrideSelectEntity(GoldairIRFanOverrideEntity, SelectEntity):
    """Diagnostic select that manually overrides the optimistic speed state.

    Selecting an option here does NOT send an IR command – it only updates the
    tracked speed so that the next ``set_percentage`` call cycles from the
    correct starting point.
    """

    _attr_name = "Speed override"
    _attr_options = SPEED_OPTIONS
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:fan-chevron-up"

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
            self._runtime_state.set_off()
        else:
            # Any non-off speed implies the fan is running.
            self._runtime_state.is_on = True
            self._runtime_state.percentage = percentage
            if self._runtime_state.preset_mode is None:
                self._runtime_state.preset_mode = PRESET_MODES[0]
        async_dispatcher_send(self.hass, self._signal)
