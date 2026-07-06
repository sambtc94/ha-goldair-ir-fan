"""Select entities for Goldair IR Fan runtime overrides."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN, FAN_SPEEDS, PRESET_MODES, state_update_signal
from .state import GoldairIRFanRuntimeState

SPEED_OPTIONS = ["off", "low", "medium", "high"]
SPEED_TO_PERCENTAGE = {
    "off": 0,
    "low": FAN_SPEEDS[0],
    "medium": FAN_SPEEDS[1],
    "high": FAN_SPEEDS[2],
}
PERCENTAGE_TO_SPEED = {value: key for key, value in SPEED_TO_PERCENTAGE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan select entities."""
    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    signal = state_update_signal(entry.entry_id)
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
    """Manual preset-state override for optimistic runtime state."""

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
        """Initialize preset override select entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_preset_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.schedule_update_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return current preset override option."""
        return self._runtime_state.preset_mode

    async def async_select_option(self, option: str) -> None:
        """Override preset state."""
        if option not in PRESET_MODES:
            return
        self._runtime_state.preset_mode = option
        if self._runtime_state.is_on and self._runtime_state.percentage == 0:
            self._runtime_state.percentage = FAN_SPEEDS[0]
        async_dispatcher_send(self.hass, self._signal)


class GoldairIRSpeedOverrideSelectEntity(SelectEntity):
    """Manual speed override for optimistic runtime state."""

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
        """Initialize speed override select entity."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_speed_override"

    async def async_added_to_hass(self) -> None:
        """Register runtime-state listener."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

    def _handle_runtime_state_update(self) -> None:
        """Handle shared runtime state updates."""
        self.schedule_update_ha_state()

    @property
    def current_option(self) -> str:
        """Return current speed override option."""
        if not self._runtime_state.is_on:
            return "off"
        return PERCENTAGE_TO_SPEED.get(self._runtime_state.percentage, "low")

    async def async_select_option(self, option: str) -> None:
        """Override speed state."""
        percentage = SPEED_TO_PERCENTAGE.get(option)
        if percentage is None:
            return

        if option == "off":
            self._runtime_state.is_on = False
            self._runtime_state.percentage = 0
            self._runtime_state.oscillating = False
            self._runtime_state.preset_mode = None
        else:
            self._runtime_state.is_on = True
            self._runtime_state.percentage = percentage
        async_dispatcher_send(self.hass, self._signal)
