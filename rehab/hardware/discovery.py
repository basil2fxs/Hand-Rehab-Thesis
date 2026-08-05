"""Building a sample source from the config, in one place.

main.py did this at startup and nothing else could, so changing a port
on the Settings screen only took effect after restarting the whole app.
That is a bad thing to hit between two blocks of a session, and it also
meant a board unplugged and plugged back into a different socket needed
a restart even though the hardware was fine.

Putting it here lets the Settings screen rebuild the connection live
through GameEngine.reconnect_source, using exactly the same rules the
app used when it started.
"""
from __future__ import annotations

import logging


log = logging.getLogger(__name__)


def resolve_ports_and_hands(cfg, fallback_ports):
    """Which ports to open and which hand each one is.

    Honours the serial.left_port and serial.right_port overrides the
    Settings screen writes:

      both set    exactly those two, right then left
      one set     that hand gets its port, the other takes the first
                  remaining detected port if there is one
      neither     the detected ports in plug order
    """
    left = cfg.get("serial.left_port")
    right = cfg.get("serial.right_port")
    if not left and not right:
        return list(fallback_ports), None
    chosen: list[str] = []
    hands: list[str] = []
    if right:
        chosen.append(right)
        hands.append("right")
    if left:
        chosen.append(left)
        hands.append("left")
    if len(chosen) == 1:
        # One hand pinned. Give the other whichever detected port is
        # left over, so a bilateral rig still comes up with both boards
        # when only one of them has been named.
        spare = [p for p in fallback_ports if p not in chosen]
        if spare:
            chosen.append(spare[0])
            hands.append("left" if hands[0] == "right" else "right")
    return chosen, hands


def build_source_from_config(cfg):
    """A started-capable source matching the current config, or None.

    Returns an unstarted source; the caller decides when to start it.
    Raises nothing on a missing port: an unopenable port comes back as
    None so the caller can say so on screen rather than crash.
    """
    n_per_hand = int(cfg.get("fsr.num_sensors_per_hand", 4))
    try:
        from .serial_source import _HAVE_SERIAL, discover_ports
    except ImportError:
        return None
    if not _HAVE_SERIAL:
        return None

    forced = cfg.get("serial.port", "auto")
    ports = ([forced] if forced and forced != "auto"
             else discover_ports(cfg.get("serial.vendor_ids")))
    ports, hands = resolve_ports_and_hands(cfg, ports)
    if not ports:
        return None

    from .multi_serial import MultiSerialSource
    return MultiSerialSource(
        ports=ports,
        baud=int(cfg.get("serial.baud", 115200)),
        num_sensors_per_hand=n_per_hand,
        read_timeout_s=float(cfg.get("serial.read_timeout_s", 0.02)),
        open_retries=int(cfg.get("serial.open_retries", 3)),
        retry_delay_s=float(cfg.get("serial.open_retry_delay_s", 1.0)),
        hand_assignment=hands,
    )
