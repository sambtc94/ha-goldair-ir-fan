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
- Override entities for optimistic state resync: power, speed (dropdown), oscillation, and preset
- Override entities are exposed in the `diagnostic` category
- Uses `remote.send_command` with Broadlink-compatible raw IR payloads (`b64:` prefixed)

## Icons

This integration sets default icons for override helper entities in code (`_attr_icon` on each entity class).

To customize icons in Home Assistant:

1. Go to **Settings → Devices & services → Entities**.
2. Open an entity (for example, a Goldair override entity).
3. Select the gear icon, then set a custom icon in the **Icon** field.
4. Save.

## Not yet implemented

- Timer function
