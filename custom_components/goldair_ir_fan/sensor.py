"""Sensor platform for Goldair IR Fan.

This module registers a :class:`GoldairIRFanPowerSensor` entity that displays
the current power reading received from the configured power-monitor sensor.

The entity is only created when the user has configured a power-monitor entity
in the integration options.  It mirrors the latest watts value from the external
sensor and gives it a proper Home Assistant device class (``SensorDeviceClass.POWER``)
so that HA can show it with the right unit and graph it in the Energy dashboard.

The power reading shown here is the same value used by the fan entity to decide
whether to auto-turn the fan on or off based on the configured threshold.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DEFAULT_NAME, DOMAIN, state_update_signal
from .state import GoldairIRFanRuntimeState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan sensor entities from a config entry.

    Only registers the power sensor when a power-monitor entity is configured.
    """
    runtime_state: GoldairIRFanRuntimeState = hass.data[DOMAIN][entry.entry_id]["runtime_state"]
    if not runtime_state.power_monitor_entity:
        return

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=DEFAULT_NAME,
        manufacturer="Goldair",
        model="IR Fan",
    )
    async_add_entities(
        [
            GoldairIRFanPowerSensor(
                runtime_state,
                state_update_signal(entry.entry_id),
                device_info,
                entry.entry_id,
            )
        ]
    )


class GoldairIRFanPowerSensor(SensorEntity):
    """Sensor that reports the current power reading watched by the integration.

    This sensor tracks the same power value that the fan entity uses when deciding
    whether to auto-turn on or off.  Displaying it here lets users easily confirm
    the integration is receiving power data and compare it against the configured
    threshold without digging through the logs.

    The sensor has ``SensorDeviceClass.POWER`` so HA records it with the correct
    unit (W) and can display it in energy dashboards and history graphs.
    """

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(
        self,
        runtime_state: GoldairIRFanRuntimeState,
        signal: str,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the power sensor."""
        self._runtime_state = runtime_state
        self._signal = signal
        self._attr_device_info = device_info
        self._attr_unique_id = f"{entry_id}_power"

    async def async_added_to_hass(self) -> None:
        """Subscribe to power-monitor and runtime-state updates."""
        # Refresh when the runtime state changes (e.g. on integration reload).
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._signal, self._handle_runtime_state_update)
        )

        # Subscribe directly to the power-monitor entity so we update promptly.
        if self._runtime_state.power_monitor_entity:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    [self._runtime_state.power_monitor_entity],
                    self._handle_power_sensor_state_change,
                )
            )

            # Seed the current value from the existing state (avoids showing
            # "unavailable" until the first state-change event arrives).
            state = self.hass.states.get(self._runtime_state.power_monitor_entity)
            if state is not None and state.state not in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
                try:
                    self._runtime_state.current_power_watts = float(state.state)
                except (ValueError, TypeError):
                    pass

    def _handle_runtime_state_update(self) -> None:
        """Refresh when the shared runtime state is updated."""
        self.schedule_update_ha_state()

    async def _handle_power_sensor_state_change(self, event: Event) -> None:
        """Update the displayed value when the external power sensor changes."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            self._runtime_state.current_power_watts = None
            self.async_write_ha_state()
            return

        try:
            self._runtime_state.current_power_watts = float(new_state.state)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Power sensor %s reported non-numeric state '%s'; ignoring",
                self._runtime_state.power_monitor_entity,
                new_state.state,
            )
            return

        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the latest power reading in watts."""
        return self._runtime_state.current_power_watts
