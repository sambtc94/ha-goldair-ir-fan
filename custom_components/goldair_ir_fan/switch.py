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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN, FAN_SPEEDS, PRESET_MODES, state_update_signal
from .state import GoldairIRFanRuntimeState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan switch entities from a config entry."""
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
            GoldairIRPowerOverrideSwitchEntity(runtime_state, signal, device_info, entry.entry_id),
            GoldairIROscillationOverrideSwitchEntity(
                runtime_state, signal, device_info, entry.entry_id
            ),
        ]
    )


class GoldairIRPowerOverrideSwitchEntity(SwitchEntity):
    """Diagnostic switch that manually overrides the optimistic power state.

    Turn this ON  → tell the integration "the fan is running at low speed".
    Turn this OFF → tell the integration "the fan is off".

    No IR command is sent; only the tracked state is updated.
    """

    _attr_has_entity_name = True
    _attr_name = "Power override"
    # DIAGNOSTIC hides this entity from the main dashboard and marks it as
    # an advanced/internal control in the entity list.
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:power"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the power override switch."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_power_override"

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates so the switch stays in sync."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when a sibling entity changes the runtime state."""
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True when the integration believes the fan is running."""
        return self._runtime_state.is_on

    async def async_turn_on(self, **kwargs) -> None:
        """Override state: mark fan as on at low speed, no oscillation, normal mode."""
        self._runtime_state.is_on = True
        self._runtime_state.percentage = FAN_SPEEDS[0]    # low = 33 %
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = PRESET_MODES[0]  # normal
        async_dispatcher_send(self.hass, self._signal)

    async def async_turn_off(self, **kwargs) -> None:
        """Override state: mark fan as off and reset all derived state."""
        self._runtime_state.is_on = False
        self._runtime_state.percentage = 0
        self._runtime_state.oscillating = False
        self._runtime_state.preset_mode = None
        async_dispatcher_send(self.hass, self._signal)


class GoldairIROscillationOverrideSwitchEntity(SwitchEntity):
    """Diagnostic switch that manually overrides the optimistic oscillation state.

    Turn ON  → tell the integration "the fan is currently oscillating".
    Turn OFF → tell the integration "the fan is not oscillating".

    No IR command is sent; only the tracked state is updated.
    """

    _attr_has_entity_name = True
    _attr_name = "Oscillation override"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:rotate-3d-variant"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the oscillation override switch."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_oscillation_override"

    async def async_added_to_hass(self) -> None:
        """Subscribe to runtime-state updates so the switch stays in sync."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Refresh HA state when a sibling entity changes the runtime state."""
        self.schedule_update_ha_state()

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
