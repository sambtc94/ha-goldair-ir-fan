# ha-goldair-ir-fan

Home Assistant integration for the Goldair IR fan.

## Setup

Add the integration and select your remote emitter (`remote` entity) during setup.

## Functionality

> This integration uses optimistic state tracking (IR fans do not report full runtime state), so Home Assistant assumes command state changes were successful.

- Fan entity with power toggle support
- 3-speed cycling (`speed` control)
- Oscillation toggle (`osc` control)
- 3-mode cycling (`mode`: normal, breeze, night)
- Adjustable IR command delay entity (default 500ms)
- Override entities for optimistic state resync: power, speed, oscillation, and preset
- Uses `remote.send_command` with Broadlink-compatible raw IR payloads (`b64:` prefixed)

## Not yet implemented

- Timer function
