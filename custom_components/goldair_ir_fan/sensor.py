"""Sensor platform for Goldair IR Fan.

This module registers a :class:`GoldairIRFanPowerSensor` entity that displays
the current power reading received from the configured power-monitor sensor.

The entity is only created when the user has configured a power-monitor entity
in the integration options.  It mirrors the latest watts value from the external
sensor and gives it a proper Home Assistant device class (``SensorDeviceClass.POWER``)
so that HA can show it with the right unit and graph it.

The power reading shown here is the same value used by the fan entity to update
power-override state based on the configured threshold.
"""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, UnitOfPower
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .entity import GoldairIRFanConfigEntry, GoldairIRFanOverrideEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoldairIRFanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Goldair IR Fan sensor entities from a config entry.

    Only registers the power sensor when a power-monitor entity is configured.
    """
    if not entry.runtime_data.power_monitor_entity:
        return
    async_add_entities([GoldairIRFanPowerSensor(entry, "power")])


class GoldairIRFanPowerSensor(GoldairIRFanOverrideEntity, SensorEntity):
    """Sensor that reports the current power reading watched by the integration.

    This sensor tracks the same power value that the fan entity uses when updating
    optimistic power-override state.  Displaying it here lets users easily confirm
    the integration is receiving power data and compare it against the configured
    threshold without digging through the logs.
    """

    _attr_name = "Power"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry: GoldairIRFanConfigEntry, key: str) -> None:
        """Initialize the power sensor."""
        super().__init__(entry, key)
        # Latest power reading, updated on each sensor state-change event.
        self._current_watts: float | None = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to power-monitor and runtime-state updates."""
        await super().async_added_to_hass()

        power_entity = self._runtime_state.power_monitor_entity
        if not power_entity:
            return

        # Subscribe directly to the power-monitor entity so we update promptly.
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [power_entity], self._handle_power_sensor_state_change
            )
        )
        # Seed the current value from the existing state (avoids showing
        # "unknown" until the first state-change event arrives).
        self._update_from_state(self.hass.states.get(power_entity))

    @callback
    def _update_from_state(self, state: State | None) -> None:
        """Store the watts value from a power-monitor state, if it is numeric."""
        if state is None or state.state in {STATE_UNAVAILABLE, STATE_UNKNOWN}:
            self._current_watts = None
            return
        try:
            self._current_watts = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.debug(
                "Power sensor %s reported non-numeric state '%s'; ignoring",
                self._runtime_state.power_monitor_entity,
                state.state,
            )

    @callback
    def _handle_power_sensor_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Update the displayed value when the external power sensor changes."""
        self._update_from_state(event.data["new_state"])
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the latest power reading in watts."""
        return self._current_watts
