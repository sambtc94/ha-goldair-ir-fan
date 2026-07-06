# ha-goldair-ir-fan

Home Assistant integration for the Goldair IR fan.

## Setup

Add the integration and select your IR blaster (`remote` entity) during setup.

## Functionality

> This integration uses optimistic state tracking (IR devices do not report state), so Home Assistant assumes command state changes were successful.
- Fan entity with power toggle support
- 3-speed cycling (`speed` control)
- Oscillation toggle (`osc` control)
- 3-mode cycling (`mode`: normal, breeze, night)
- Uses Home Assistant's infrared command block format

## Not yet implemented

- Timer function
