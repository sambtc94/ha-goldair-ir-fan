# ha-goldair-ir-fan

Home Assistant integration for the Goldair IR fan.

## Requirements

- Home Assistant 2026.6 or later.
- An IR blaster that provides an **infrared emitter** entity (`infrared.*`), such as a Broadlink remote or an ESPHome IR transmitter.

## Setup

Add the integration, give the fan a name (e.g. "Office Fan") and choose the infrared emitter it should send commands through. You can add several Goldair fans on the same IR blaster.

### Upgrading from 0.1.x

Earlier versions sent codes with `remote.send_command`. On upgrade, existing fans are moved automatically to the infrared emitter on the same device as their old remote entity (for a Broadlink, `remote.x` → `infrared.x_ir_emitter`). Entity IDs, automations and options carry over unchanged.

If no emitter is found on that device, the entry shows a migration error in **Settings → Devices & services**; delete it and add the fan again.

## Functionality

> This integration uses optimistic state tracking (IR fans do not report full runtime state), so Home Assistant assumes command state changes were successful.

- Fan entity with power toggle support
- 3-speed cycling (`speed` control)
- Oscillation toggle (`osc` control)
- 3-mode cycling (`mode`: normal, breeze, night)
- Commands sent through Home Assistant's infrared platform; the learned Broadlink codes are decoded to raw IR timings, so any infrared emitter can send them
- The fan's tracked state is restored after a restart or an options change
- Commands are queued, so rapid or overlapping changes never send the wrong number of cycle presses
- The fan shows as unavailable while its infrared emitter is unavailable
- Configurable IR command delay (default 500 ms) in the integration's options
- Optional power monitor: a power sensor and threshold that correct the tracked on/off state when the fan is switched with its physical remote
- Override entities for optimistic state resync: power, speed (dropdown), oscillation, and preset
- Override entities are exposed in the `diagnostic` category

## Icons

This integration sets default icons for override helper entities in code (`_attr_icon` on each entity class).

To customize icons in Home Assistant:

1. Go to **Settings → Devices & services → Entities**.
2. Open an entity (for example, a Goldair override entity).
3. Select the gear icon, then set a custom icon in the **Icon** field.
4. Save.

## Not yet implemented

- Timer function
