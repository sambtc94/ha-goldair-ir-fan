"""Switch entities for Goldair IR Fan runtime overrides.

These entities let you manually correct the integration's optimistic state when
it has drifted from the real fan state (e.g. after someone used the physical
remote or after a power cut).

Why optimistic state drifts
---------------------------
Because the fan is IR-only, there is no feedback channel.  If the fan is turned
on/off with the physical remote the integration has no way to know.  The override
switches/selects let you tell the integration "the fan is actually in *this*
state" so that the next automated command uses the right starting point when
counting cycle steps.

Entities provided
-----------------
* **Power override**       – force is_on = True / False
* **Oscillation override** – force oscillating = True / False
"""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import FAN_SPEEDS, PRESET_MODES
from .entity import GoldairIRFanConfigEntry, GoldairIRFanOverrideEntity

# Override entities only touch in-memory state, so they can run in parallel.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoldairIRFanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan switch entities from a config entry."""
    async_add_entities(
        [
            GoldairIRPowerOverrideSwitchEntity(entry, "power_override"),
            GoldairIROscillationOverrideSwitchEntity(entry, "oscillation_override"),
        ]
    )


class GoldairIRPowerOverrideSwitchEntity(GoldairIRFanOverrideEntity, SwitchEntity):
    """Diagnostic switch that manually overrides the optimistic power state.

    Turn this ON  → tell the integration "the fan is running at low speed".
    Turn this OFF → tell the integration "the fan is off".

    No IR command is sent; only the tracked state is updated.
    """

    _attr_name = "Power override"
    # DIAGNOSTIC hides this entity from the main dashboard and marks it as
    # an advanced/internal control in the entity list.
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:power"

    @property
    def is_on(self) -> bool:
        """Return True when the integration believes the fan is running."""
        return self._runtime_state.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Override state: mark fan as on at low speed, no oscillation, normal mode."""
        self._runtime_state.set_on_defaults()
        async_dispatcher_send(self.hass, self._signal)

    async def async_turn_off(self, **kwargs) -> None:
        """Override state: mark fan as off and reset all derived state."""
        self._runtime_state.set_off()
        async_dispatcher_send(self.hass, self._signal)


class GoldairIROscillationOverrideSwitchEntity(
    GoldairIRFanOverrideEntity, SwitchEntity
):
    """Diagnostic switch that manually overrides the optimistic oscillation state.

    Turn ON  → tell the integration "the fan is currently oscillating".
    Turn OFF → tell the integration "the fan is not oscillating".

    No IR command is sent; only the tracked state is updated.
    """

    _attr_name = "Oscillation override"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:rotate-3d-variant"

    @property
    def is_on(self) -> bool:
        """Return True when the integration believes oscillation is active."""
        return self._runtime_state.oscillating

    async def async_turn_on(self, **kwargs) -> None:
        """Override state: mark oscillation as active.

        Also ensures the power and speed are in a valid on state so that the
        fan entity is consistent (can't oscillate if off).
        """
        self._runtime_state.oscillating = True
        self._runtime_state.is_on = True
        if self._runtime_state.percentage <= 0:
            self._runtime_state.percentage = FAN_SPEEDS[0]
        if self._runtime_state.preset_mode is None:
            self._runtime_state.preset_mode = PRESET_MODES[0]
        async_dispatcher_send(self.hass, self._signal)

    async def async_turn_off(self, **kwargs) -> None:
        """Override state: mark oscillation as inactive."""
        self._runtime_state.oscillating = False
        async_dispatcher_send(self.hass, self._signal)
