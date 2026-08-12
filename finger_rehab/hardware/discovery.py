"""Building a sample source from the config, in one place.

main.py did this at startup and nothing else could, so changing a port
on the Settings screen only took effect after restarting the whole app.
That is a bad thing to hit between two blocks of a session, and it also
meant a board unplugged and plugged back into a different socket needed
a restart even though the hardware was fine.

Putting it here lets the Settings screen rebuild the connection live
through GameEngine.reconnect_source, using exactly the same rules the
app used when it started.

The assignment rules, in the order they apply:

  1. A saved serial.left_port / serial.right_port override wins for
     its hand, but only while the named port actually exists. Ports
     rename themselves between plug-ins (usbserial-130 one day,
     usbserial-110 the next), so a saved name goes stale easily.
  2. A stale override is ignored, with a note, and that hand falls
     back to plug order. Before this rule the stale name sat on one
     hand forever: the real board got shunted onto the OTHER hand and
     the named hand showed disconnected until the user re-did the
     Settings screen. That is exactly the "configure it every boot"
     trap this module exists to remove.
  3. With nothing pinned, plug order decides: first detected board is
     the RIGHT hand, second is the LEFT.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field


log = logging.getLogger(__name__)


def short_port(p: str) -> str:
    """Strip /dev/cu. style prefixes so a port fits in a status line."""
    for prefix in ("/dev/cu.", "/dev/tty.", "/dev/", "\\\\.\\"):
        if p.startswith(prefix):
            return p[len(prefix):]
    return p


@dataclass
class PortAssignment:
    """The outcome of one port-to-hand resolution, plus the story of
    how it was reached so the UI can say it out loud."""

    ports: list[str] = field(default_factory=list)
    hands: list[str] = field(default_factory=list)
    # Hands whose port came from a saved override that named a port
    # which still exists.
    pinned: list[str] = field(default_factory=list)
    # Saved overrides that named a port the OS can no longer see, as
    # (hand, stale_port) pairs. These hands fell back to plug order.
    stale: list[tuple[str, str]] = field(default_factory=list)

    def pairs(self) -> list[tuple[str, str]]:
        return list(zip(self.hands, self.ports))

    def describe(self) -> str:
        """One status line: which port went to which hand and why."""
        if self.ports:
            bits = []
            for hand, port in self.pairs():
                how = "set in Settings" if hand in self.pinned else "auto"
                bits.append(f"{hand} = {short_port(port)} ({how})")
            line = ", ".join(bits)
        else:
            line = "no Arduino found"
        for hand, port in self.stale:
            line += (f"; ignored saved {hand} port {short_port(port)} "
                     "(not present)")
        return line


def resolve_assignment(cfg, detected, known_ports=None) -> PortAssignment:
    """Decide which ports to open and which hand each one is.

    `detected` is the plug-ordered list from discover_ports. It is
    also the ground truth for whether a saved override still exists,
    unless `known_ports` (the full OS port list, junk included) is
    given: a user who deliberately assigned a port the auto-detector
    filters out should keep it.
    """
    detected = list(detected)
    known = set(detected)
    if known_ports:
        known.update(known_ports)
    out = PortAssignment()
    valid: dict[str, str] = {}
    for hand in ("right", "left"):
        port = cfg.get(f"serial.{hand}_port")
        if not port:
            continue
        if port in known:
            valid[hand] = port
        else:
            out.stale.append((hand, port))
    used = set(valid.values())
    spares = [p for p in detected if p not in used]
    # Right first so the plug-order rule reads first = right,
    # second = left.
    for hand in ("right", "left"):
        if hand in valid:
            out.ports.append(valid[hand])
            out.hands.append(hand)
            out.pinned.append(hand)
        elif spares:
            out.ports.append(spares.pop(0))
            out.hands.append(hand)
    if out.stale:
        log.warning("Ignoring stale saved port assignment(s): %s. "
                    "Falling back to plug order.",
                    ["%s=%s" % s for s in out.stale])
    return out


def resolve_ports_and_hands(cfg, fallback_ports, known_ports=None):
    """Tuple form of resolve_assignment for callers that only need the
    (ports, hands) pair. Same rules, same code path."""
    a = resolve_assignment(cfg, fallback_ports, known_ports)
    return a.ports, a.hands


def build_source_from_config(cfg, forced_port: str | None = None):
    """A started-capable source matching the current config, or None.

    Returns an unstarted source; the caller decides when to start it.
    Raises nothing on a missing port: an unopenable port comes back as
    None so the caller can say so on screen rather than crash.

    `forced_port` is the CLI --port escape hatch. It is used verbatim,
    typos and all, because the user typed it this run and a silent
    substitute would be worse than the error. A serial.port value
    saved in a yaml file gets the stale check instead.
    """
    n_per_hand = int(cfg.get("fsr.num_sensors_per_hand", 4))
    try:
        from .serial_source import (
            _HAVE_SERIAL, discover_ports, list_available_ports,
        )
    except ImportError:
        return None
    if not _HAVE_SERIAL:
        return None

    known = [p.device for p in list_available_ports()]
    forced = forced_port or cfg.get("serial.port", "auto")
    if forced and forced != "auto":
        if forced_port or forced in known:
            detected = [forced]
        else:
            # Saved serial.port names a port the OS cannot see. Same
            # stale rule as the per-hand overrides: ignore it and let
            # discovery find the boards that are actually plugged in.
            log.warning("serial.port %s is not present; "
                        "using auto-discovery instead", forced)
            detected = discover_ports(cfg.get("serial.vendor_ids"))
    else:
        detected = discover_ports(cfg.get("serial.vendor_ids"))
    assignment = resolve_assignment(cfg, detected, known_ports=known)
    if not assignment.ports:
        return None

    from .multi_serial import MultiSerialSource
    src = MultiSerialSource(
        ports=assignment.ports,
        baud=int(cfg.get("serial.baud", 115200)),
        num_sensors_per_hand=n_per_hand,
        read_timeout_s=float(cfg.get("serial.read_timeout_s", 0.02)),
        open_retries=int(cfg.get("serial.open_retries", 3)),
        retry_delay_s=float(cfg.get("serial.open_retry_delay_s", 1.0)),
        hand_assignment=assignment.hands,
    )
    src.assignment_note = assignment.describe()
    log.info("Port assignment: %s", src.assignment_note)
    return src
