"""IR commands for the Goldair fan, built from learned Broadlink codes.

The fan's codes were captured with a Broadlink remote (``remote.learn_command``)
and are stored in ``const.py`` as base64 Broadlink packets.  Home Assistant's
infrared platform works with raw timings instead, so this module decodes each
packet into a :class:`BroadlinkPacketCommand` that any infrared emitter
(Broadlink, ESPHome, …) can transmit.

Broadlink packet layout
-----------------------
* byte 0      – 0x26 for IR (0xb2 / 0xd7 are 433 / 315 MHz RF)
* byte 1      – repeat count
* bytes 2–3   – payload length, little-endian
* payload     – alternating mark/space durations in Broadlink ticks
                (269/8192 ms ≈ 32.84 µs).  A zero byte means the next two
                bytes hold a big-endian 16-bit duration.
"""

from __future__ import annotations

import base64
import math

from homeassistant.components.infrared import InfraredCommand

from .const import (
    IR_BLOB_MODE_CYCLE,
    IR_BLOB_OSC_TOGGLE,
    IR_BLOB_POWER_TOGGLE,
    IR_BLOB_SPEED_CYCLE,
)

BROADLINK_IR_PACKET_TYPE = 0x26
# Broadlink's tick length in microseconds (matches python-broadlink).
BROADLINK_TICK_US = 32.84
# Standard consumer IR carrier.  Broadlink learns demodulated timings only, so
# the carrier isn't stored in the packet; the Goldair remote uses 38 kHz.
DEFAULT_MODULATION_HZ = 38_000


def broadlink_packet_to_timings(packet_b64: str) -> list[int]:
    """Decode a base64 Broadlink IR packet into signed microsecond timings.

    Positive values are marks (IR on), negative values are spaces (IR off).

    Durations are rounded *up* to whole microseconds so that an emitter which
    converts back to Broadlink ticks with floor division (as Home Assistant's
    Broadlink emitter does) reproduces the original packet exactly.
    """
    packet = base64.b64decode(packet_b64.removeprefix("b64:"))
    if len(packet) < 4 or packet[0] != BROADLINK_IR_PACKET_TYPE:
        raise ValueError("Not a Broadlink IR packet")

    end = min(4 + int.from_bytes(packet[2:4], "little"), len(packet))
    timings: list[int] = []
    index = 4
    while index < end:
        ticks = packet[index]
        index += 1
        if ticks == 0:
            if index + 2 > len(packet):
                raise ValueError("Truncated Broadlink IR packet")
            ticks = int.from_bytes(packet[index : index + 2], "big")
            index += 2
        duration = math.ceil(ticks * BROADLINK_TICK_US)
        timings.append(duration if len(timings) % 2 == 0 else -duration)
    if not timings:
        raise ValueError("Empty Broadlink IR packet")
    return timings


class BroadlinkPacketCommand(InfraredCommand):
    """An infrared command replaying a learned Broadlink IR packet."""

    def __init__(
        self, packet_b64: str, *, modulation: int = DEFAULT_MODULATION_HZ
    ) -> None:
        """Decode the packet once; the timings are reused for every send."""
        super().__init__(modulation=modulation)
        self._timings = broadlink_packet_to_timings(packet_b64)

    def get_raw_timings(self) -> list[int]:
        """Return the signed microsecond timings."""
        return list(self._timings)


COMMAND_POWER_TOGGLE = BroadlinkPacketCommand(IR_BLOB_POWER_TOGGLE)
COMMAND_SPEED_CYCLE = BroadlinkPacketCommand(IR_BLOB_SPEED_CYCLE)
COMMAND_OSC_TOGGLE = BroadlinkPacketCommand(IR_BLOB_OSC_TOGGLE)
COMMAND_MODE_CYCLE = BroadlinkPacketCommand(IR_BLOB_MODE_CYCLE)
