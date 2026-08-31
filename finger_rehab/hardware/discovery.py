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
  3. A hand that already had a board this run keeps it, as long as
     that port is still there. Only matters for a board unplugged and
     plugged back in mid-run: the OS hands the ports back in whatever
     order it likes, and without this rule the patient's left hand
     could come back driving the right lanes.
  4. With nothing pinned and nothing remembered, plug order decides:
     first detected board is the RIGHT hand, second is the LEFT.

PortWatcher at the bottom is the other half of the same job: it polls
the OS port list on its own thread so a board plugged in at any screen
is noticed without anyone pressing Refresh.
"""
from __future__ import annotations

import logging
import threading
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
    # Hands that kept the port they already had this run, ahead of
    # plug order. Only ever set on a rebuild, never at boot.
    kept: list[str] = field(default_factory=list)

    def pairs(self) -> list[tuple[str, str]]:
        return list(zip(self.hands, self.ports))

    def describe(self) -> str:
        """One status line: which port went to which hand and why."""
        if self.ports:
            bits = []
            for hand, port in self.pairs():
                if hand in self.pinned:
                    how = "set in Settings"
                elif hand in self.kept:
                    how = "same as before"
                else:
                    how = "auto"
                bits.append(f"{hand} = {short_port(port)} ({how})")
            line = ", ".join(bits)
        else:
            line = "no Arduino found"
        for hand, port in self.stale:
            line += (f"; ignored saved {hand} port {short_port(port)} "
                     "(not present)")
        return line


def resolve_assignment(cfg, detected, known_ports=None,
                       remembered=None) -> PortAssignment:
    """Decide which ports to open and which hand each one is.

    `detected` is the plug-ordered list from discover_ports. It is
    also the ground truth for whether a saved override still exists,
    unless `known_ports` (the full OS port list, junk included) is
    given: a user who deliberately assigned a port the auto-detector
    filters out should keep it.

    `remembered` is {hand: port} for the boards this run already had.
    It sits between the saved overrides and plug order, and only a
    port that is still detected counts. It exists because a board
    unplugged and plugged back in mid-run comes back in whatever
    order the OS feels like: with plug order alone, a two-board rig
    could hand the patient's left board the right hand's lanes
    halfway through a session, and every press after that is
    attributed to the wrong hand in the data.
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
    sticky: dict[str, str] = {}
    for hand in ("right", "left"):
        if hand in valid:
            continue
        port = (remembered or {}).get(hand)
        if port and port in detected and port not in used:
            sticky[hand] = port
            used.add(port)
    spares = [p for p in detected if p not in used]
    # Right first so the plug-order rule reads first = right,
    # second = left.
    for hand in ("right", "left"):
        if hand in valid:
            out.ports.append(valid[hand])
            out.hands.append(hand)
            out.pinned.append(hand)
        elif hand in sticky:
            out.ports.append(sticky[hand])
            out.hands.append(hand)
            out.kept.append(hand)
        elif spares:
            out.ports.append(spares.pop(0))
            out.hands.append(hand)
    if out.stale:
        log.warning("Ignoring stale saved port assignment(s): %s. "
                    "Falling back to plug order.",
                    ["%s=%s" % s for s in out.stale])
    return out


def resolve_ports_and_hands(cfg, fallback_ports, known_ports=None,
                            remembered=None):
    """Tuple form of resolve_assignment for callers that only need the
    (ports, hands) pair. Same rules, same code path."""
    a = resolve_assignment(cfg, fallback_ports, known_ports, remembered)
    return a.ports, a.hands


def build_source_from_config(cfg, forced_port: str | None = None,
                             remembered=None):
    """A started-capable source matching the current config, or None.

    Returns an unstarted source; the caller decides when to start it.
    Raises nothing on a missing port: an unopenable port comes back as
    None so the caller can say so on screen rather than crash.

    `forced_port` is the CLI --port escape hatch. It is used verbatim,
    typos and all, because the user typed it this run and a silent
    substitute would be worse than the error. A serial.port value
    saved in a yaml file gets the stale check instead.

    `remembered` is the engine's {hand: port} map from before this
    rebuild, so a board that was unplugged and plugged back in lands
    on the hand it already had. See resolve_assignment.
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
    assignment = resolve_assignment(cfg, detected, known_ports=known,
                                    remembered=remembered)
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


class PortWatcher:
    """Polls the OS serial port list on a background thread.

    Plugging a board in used to do nothing until somebody found the
    Settings screen and pressed Refresh, which is a silly thing to ask
    of a therapist mid-clinic and an easy thing to forget: the session
    then ran one-handed with no sign anything was wrong beyond a hand
    that never registered a press.

    The scan itself (pyserial's comports) measures well under 2 ms on
    this Mac, but it touches the OS and can spike on rigs with more
    ports, so it does NOT run on the render path. This thread does it on an interval and publishes two things
    the main loop can read for free:

      - `ports`, the latest detected list
      - `generation`, bumped only when the SET of ports changes

    Consumers keep their own copy of the generation they last acted on,
    so the engine and the Settings screen can both react to the same
    change without stealing it from each other.

    A pure reorder of the same boards is deliberately not a change.
    The OS enumerates ports in whatever order it likes and a reshuffle
    that moved a patient's hands mid-session would be worse than doing
    nothing at all.
    """

    DEFAULT_INTERVAL_S = 1.0

    def __init__(self, cfg=None, *, scan=None,
                 interval_s: float | None = None) -> None:
        self._cfg = cfg
        self._scan = scan or self._default_scan
        if interval_s is None:
            interval_s = self.DEFAULT_INTERVAL_S
            if cfg is not None:
                try:
                    interval_s = float(cfg.get("serial.autoconnect_poll_s",
                                               self.DEFAULT_INTERVAL_S))
                except (TypeError, ValueError):
                    interval_s = self.DEFAULT_INTERVAL_S
        # Floor the interval so a mistyped 0 in a yaml file cannot turn
        # this into a spin loop hammering the USB subsystem.
        self.interval_s = max(0.1, float(interval_s))
        self._lock = threading.Lock()
        self._ports: list[str] = []
        self._generation = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _default_scan(self) -> list[str]:
        from .serial_source import discover_ports
        vids = self._cfg.get("serial.vendor_ids") if self._cfg else None
        return discover_ports(vids)

    @property
    def ports(self) -> list[str]:
        with self._lock:
            return list(self._ports)

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def poll_once(self) -> list[str]:
        """One scan, publishing the result. Safe to call directly; the
        thread is only a timer around this."""
        try:
            found = list(self._scan())
        except Exception as e:
            # A failing scan must not kill the watcher: a USB stack
            # hiccup would otherwise leave autoconnect dead for the
            # rest of the run with nothing on screen to say so.
            log.debug("Port scan failed: %s", e)
            return self.ports
        with self._lock:
            if set(found) != set(self._ports):
                self._ports = found
                self._generation += 1
            elif found != self._ports:
                self._ports = found
            return list(self._ports)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="PortWatcher")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        t = self._thread
        if t is not None:
            t.join(timeout=2.0)
        self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.poll_once()
            self._stop.wait(self.interval_s)
