"""Multi-Arduino source. Aiden's firmware exposes one hand (4 sensors)
per board, so bilateral training needs two boards plugged in. This
module fans out the standard Source interface over 1 or 2 underlying
SerialSource instances and merges their sample streams into a single
4- or 8-value vector for the engine.

Hand assignment is plug-order based: the first Arduino discovered is
the right hand, the second is the left. The user can swap by unplugging
in the reverse order before starting, or pin a port to a hand from the
Settings screen. discovery.resolve_assignment owns those rules,
including ignoring a saved port that no longer exists.

The engine sees this as a normal Source: start / stop / get_sample /
send_command / is_connected. No engine-side changes needed beyond
swapping which Source class main.py constructs.

TWO BOARDS, EACH ON ITS OWN CLOCK (the Mirror review of 1 October
2026). Until then the merger kept only each board's LATEST sample,
paired the two when they fell within 50 ms and stamped the pair with
the later board's time. A board that sends in packets lost all but
the last sample of each packet (43 percent of samples when both did,
in simulation), and one stamp for both hands put a bias of up to
9 ms between a bursting and a smooth board, enough to decide which
hand "leads" in Mirror. Now every sample of either board is queued
per board and sent on once, in time order, with that board's own
stamp (Sample.t_hands names whose sample it is); the other hand's
last values ride along held, so the 8-value shape is unchanged, and
the engine feeds a hand's detector only that hand's own samples. A
board silent for SAMPLE_PAIR_WINDOW_S still reads as zeros, as
before. The one-board path forwards samples exactly as it did.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass

from .serial_source import SerialSource
from .source import Sample, Source


log = logging.getLogger(__name__)


@dataclass
class HandPort:
    """One Arduino + the hand it's assigned to."""
    hand: str            # "right" | "left"
    port: str
    source: SerialSource


class MultiSerialSource(Source):
    """Aggregates 1 or 2 SerialSource instances into one combined Source.

    Each underlying Arduino streams 4 sensor values; this class merges
    them into the engine's expected sample shape:

        - 1 board, hand=right or left: forwards the 4 values as-is.
        - 2 boards (right + left): combines into 8 values
          [right_0..3, left_0..3] matching engine._feed_detectors in
          the "both" hand_mode.

    Hot-unplug behaviour: each underlying source manages its own thread
    and `is_connected` flag. If one drops, the other keeps flowing.
    The engine's per-frame _check_source_connection will log a warning.
    """

    SAMPLE_PAIR_WINDOW_S = 0.05
    """With two boards: how long a sample waits for the OTHER board,
    which may still send one stamped earlier, before it goes on alone;
    and how long a board may be silent before its hand reads as
    zeros."""

    def __init__(self, ports: list[str], *,
                 baud: int = 115200, num_sensors_per_hand: int = 4,
                 read_timeout_s: float = 0.02,
                 open_retries: int = 3, retry_delay_s: float = 1.0,
                 hand_assignment: list[str] | None = None) -> None:
        super().__init__()
        if not ports:
            raise ValueError("MultiSerialSource needs at least one port")
        if len(ports) > 2:
            log.warning("More than two ports passed; only the first two "
                         "will be used (%s)", ports)
            ports = ports[:2]
        if hand_assignment is None:
            hand_assignment = (["right"] if len(ports) == 1
                                else ["right", "left"])
        if len(hand_assignment) != len(ports):
            raise ValueError(
                f"hand_assignment length {len(hand_assignment)} must "
                f"match port count {len(ports)}"
            )
        self.num_sensors_per_hand = num_sensors_per_hand
        # One line saying which port went to which hand and why, set
        # by discovery.build_source_from_config. The title screen and
        # the Settings port panel show it so plug-order auto-assignment
        # is never a mystery. Empty for hand-built sources.
        self.assignment_note: str = ""
        self.hands: list[HandPort] = []
        for port, hand in zip(ports, hand_assignment):
            src = SerialSource(
                port=port, baud=baud,
                num_sensors=num_sensors_per_hand,
                read_timeout_s=read_timeout_s,
                open_retries=open_retries, retry_delay_s=retry_delay_s,
            )
            self.hands.append(HandPort(hand=hand, port=port, source=src))
        self._q: queue.Queue[Sample] = queue.Queue(maxsize=4096)
        self._stop = threading.Event()
        self._merger_thread: threading.Thread | None = None
        # Two boards: the last sample RECEIVED per board (its stamp
        # says whether the board is alive), each board's queue of
        # samples not yet sent on, and the last values SENT per hand,
        # which ride along held while the other board's samples go.
        self._last_right: tuple[float, tuple[int, ...]] | None = None
        self._last_left:  tuple[float, tuple[int, ...]] | None = None
        self._reset_pairing()
        # perf_counter timestamp of the last sample we actually pushed
        # onto the queue. Used to distinguish "port open + data flowing"
        # from "port open but the device on the other end is silent"
        # (e.g. /dev/cu.Bluetooth-Incoming-Port that opens fine but
        # never produces FSR lines). Starts at None so a fresh source
        # reads as no-data until the first sample arrives.
        self._last_sample_t: float | None = None

    @property
    def name(self) -> str:
        if len(self.hands) == 1:
            return f"MultiSerial({self.hands[0].hand}@{self.hands[0].port})"
        parts = ",".join(f"{h.hand}@{h.port}" for h in self.hands)
        return f"MultiSerial({parts})"

    @property
    def is_connected(self) -> bool:
        # At least one underlying source must be alive.
        return any(h.source.is_connected for h in self.hands)

    @property
    def hands_connected(self) -> dict[str, bool]:
        """Per-hand connection state, {hand: alive}. is_connected
        (any board alive) hides a one-board drop in a bilateral
        block, and the merger keeps zero-filling the dead hand, so
        without this view the engine cannot tell a silent board from
        a resting hand: the zeros slid that hand's baseline down and
        the reconnect fired phantom presses that latched every lane.
        The engine's per-frame check reads this to log the drop, park
        the dead hand's detector and re-prime it on reconnect."""
        return {h.hand: h.source.is_connected for h in self.hands}

    @property
    def provides_samples(self) -> bool:
        return True

    @property
    def hand_modes_available(self) -> set[str]:
        """Which game hand_mode values this source can handle. One
        Arduino -> only its assigned hand. Two -> all three."""
        if len(self.hands) == 1:
            return {self.hands[0].hand}
        return {"right", "left", "both"}

    def start(self) -> None:
        # Idempotent: if a merger thread is already running (start was
        # called twice without an intervening stop) DON'T spawn a second
        # one. Before this guard, calling start() twice leaked a daemon
        # thread AND made both mergers drain the same per-hand queues,
        # which surfaced as duplicated samples on the output queue.
        if self._merger_thread is not None and self._merger_thread.is_alive():
            log.debug("MultiSerial.start: merger already running, no-op")
            return
        # Reset pair-cache state so a stop -> swap Arduinos -> start
        # cycle doesn't get a stale right/left pair from the previous
        # session on its first frame.
        self._last_right = None
        self._last_left = None
        self._last_sample_t = None
        self._reset_pairing()
        for h in self.hands:
            try:
                h.source.start()
            except (OSError, RuntimeError, ValueError) as e:
                # OSError covers serial-open failures (port busy,
                # permission denied, port disappeared between
                # discovery and start). RuntimeError + ValueError
                # cover pyserial config edge cases (baud rate
                # mismatch, etc). The other hand may still start
                # cleanly so we log and carry on rather than
                # cancelling the whole session.
                log.error("Failed to start %s source on %s: %s",
                           h.hand, h.port, e)
        self._stop.clear()
        self._merger_thread = threading.Thread(
            target=self._merge_loop, daemon=True,
            name="MultiSerialMerger",
        )
        self._merger_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._merger_thread:
            self._merger_thread.join(timeout=2.0)
        self._merger_thread = None
        for h in self.hands:
            try:
                h.source.stop()
            except Exception as e:
                log.warning("Stopping %s source raised: %s", h.hand, e)
        # Drain remaining queued samples.
        try:
            while True:
                self._q.get_nowait()
        except queue.Empty:
            pass
        # Reset pair cache + freshness clock. A subsequent start() will
        # also reset these defensively, but doing it here too means a
        # caller who only invokes stop (e.g. on engine teardown) gets
        # a clean state object too.
        self._last_right = None
        self._last_left = None
        self._last_sample_t = None
        self._reset_pairing()

    def _reset_pairing(self) -> None:
        self._q_right: deque = deque(maxlen=2048)
        self._q_left: deque = deque(maxlen=2048)
        self._held_right: tuple[float, tuple[int, ...]] | None = None
        self._held_left: tuple[float, tuple[int, ...]] | None = None

    def get_sample(self, timeout: float = 0.0):
        try:
            if timeout > 0:
                return self._q.get(timeout=timeout)
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def relabel_single(self, hand: str) -> bool:
        """Name the only board's hand. Plug order calls a lone board
        the right hand; when the person says it is their left, this
        makes it so, without reopening the port (a reopen resets the
        Nano). Refused with two boards, where plug order and the
        Settings dropdowns decide."""
        if len(self.hands) != 1 or hand not in ("left", "right"):
            return False
        self.hands[0].hand = hand
        return True

    def send_command(self, cmd: str) -> bool:
        """Routes STIM commands to the matching Arduino.

        Three cases:
          - `LEFT:STIM:n` or `RIGHT:STIM:n`: routed to that specific hand
            (the prefix is stripped before forwarding to the underlying
            source).
          - Plain `STIM:n` with two boards: lanes 1..N go to the right
            board as local STIM:n, lanes N+1..2N go to the left board as
            local STIM:n-N.
          - Plain `STIM:n` with one board: lanes 1..N are forwarded
            verbatim to that single board regardless of which hand it
            represents. This is what makes unilateral left-hand-only
            sessions work, since the engine sends STIM:1..N for both
            left and right unilateral modes.
          - Anything else (STOP, RESET, etc.): broadcast.
        """
        if cmd.startswith("LEFT:") or cmd.startswith("RIGHT:"):
            prefix, _, rest = cmd.partition(":")
            target = prefix.lower()
            for h in self.hands:
                if h.hand == target:
                    return h.source.send_command(rest)
            return False
        if cmd.startswith("STIM:"):
            try:
                lane = int(cmd.split(":", 1)[1])
            except (ValueError, IndexError):
                return False
            n = self.num_sensors_per_hand
            # Single board: forward STIM:1..n verbatim. The engine numbers
            # unilateral lanes 1..n regardless of left/right, so the only
            # sane mapping is "whichever board is plugged in handles it".
            if len(self.hands) == 1:
                if 1 <= lane <= n:
                    return self.hands[0].source.send_command(cmd)
                return False
            # Two boards: split lanes between hands.
            if 1 <= lane <= n:
                target_hand = "right"
                local_cmd = f"STIM:{lane}"
            elif n + 1 <= lane <= 2 * n:
                target_hand = "left"
                local_cmd = f"STIM:{lane - n}"
            else:
                return False
            for h in self.hands:
                if h.hand == target_hand:
                    return h.source.send_command(local_cmd)
            return False
        # STOP and anything else: broadcast.
        ok = False
        for h in self.hands:
            if h.source.send_command(cmd):
                ok = True
        return ok

    def _merge_loop(self) -> None:
        """Read samples from each underlying source and combine them
        into the unified vector the engine expects.

        Body is wrapped in try / except so any unexpected error (e.g.
        an underlying source raising on get_sample because its port
        got pulled mid-read, or a queue.Full + queue.Empty race that
        escapes the inner handlers) doesn't silently kill the thread.
        Before this, a thread crash showed up as a frozen game (engine
        thought is_connected was still True per the per-hand flag, but
        the output queue had stopped getting samples). Now we log and
        keep spinning."""
        n = self.num_sensors_per_hand
        only_one = len(self.hands) == 1
        if not hasattr(self, "_q_right"):
            self._reset_pairing()
        while not self._stop.is_set():
            try:
                any_consumed = False
                for h in self.hands:
                    s = h.source.get_sample(timeout=0)
                    if s is None:
                        continue
                    any_consumed = True
                    if only_one:
                        # Single board: forward verbatim. The engine
                        # knows which hand it's assigned via
                        # cfg.bilateral.hand.
                        try:
                            self._q.put_nowait(s)
                            self._last_sample_t = time.perf_counter()
                        except queue.Full:
                            try:
                                self._q.get_nowait()
                                self._q.put_nowait(s)
                                self._last_sample_t = time.perf_counter()
                            except queue.Empty:
                                pass
                    else:
                        # Two boards: queue every sample on its board's
                        # own stamp; nothing is overwritten.
                        item = (s.t_perf, tuple(s.values[:n]))
                        if h.hand == "right":
                            self._last_right = item
                            self._q_right.append(item)
                        else:
                            self._last_left = item
                            self._q_left.append(item)
                # Run the pair-emit check EVERY iteration in bilateral
                # mode, not just when a new sample arrived. Without
                # this, a solo hand that goes silent never triggers
                # the window-expiry fallback (the function would only
                # be called once when its first sample arrived, at
                # which point the window hadn't yet elapsed).
                if not only_one:
                    self._emit_paired_if_ready()
                if not any_consumed:
                    # No data this tick; nap so we don't burn a CPU core.
                    time.sleep(0.002)
            except Exception as e:
                # Unexpected error in the merge body. Log and keep the
                # thread alive so a transient hardware glitch doesn't
                # take the whole input pipeline down.
                log.warning("Merger loop swallowed error: %s", e)
                time.sleep(0.01)

    def _emit_paired_if_ready(self) -> None:
        """Two boards: send on every queued sample, oldest first, each
        on its own board's stamp (t_hands names it) with the other
        hand's last sent values held beside it. A sample waits while
        the other board's queue is empty, up to SAMPLE_PAIR_WINDOW_S,
        because that board may still send one stamped earlier. A hand
        whose board has been silent longer than the window reads as
        zeros, so the live hand still plays."""
        n = self.num_sensors_per_hand
        now = time.perf_counter()
        while True:
            r = self._q_right[0] if self._q_right else None
            left = self._q_left[0] if self._q_left else None
            if r is None and left is None:
                return
            if r is not None and (left is None or r[0] <= left[0]):
                hand, (t, v), other_waiting = "right", r, left is None
            else:
                hand, (t, v), other_waiting = "left", left, r is None
            if other_waiting and now - t < self.SAMPLE_PAIR_WINDOW_S:
                return
            if hand == "right":
                self._q_right.popleft()
                self._held_right = (t, tuple(v))
                t_hands = (t, None)
            else:
                self._q_left.popleft()
                self._held_left = (t, tuple(v))
                t_hands = (None, t)
            values = (self._side(self._held_right, self._last_right, t, n)
                      + self._side(self._held_left, self._last_left, t, n))
            self._push_combined(t, values, t_hands)

    def _side(self, held, last, t: float, n: int) -> tuple[int, ...]:
        """One hand's values for a sample at time t: its last sent
        values, or zeros when its board has sent nothing yet or has
        been silent longer than the window."""
        if held is None or last is None:
            return (0,) * n
        if t - last[0] > self.SAMPLE_PAIR_WINDOW_S:
            return (0,) * n
        return tuple(held[1])

    def _push_combined(self, t_perf: float, values: tuple[int, ...],
                       t_hands: tuple | None = None) -> None:
        s = Sample(t_perf=t_perf, values=values, t_hands=t_hands)
        try:
            self._q.put_nowait(s)
            self._last_sample_t = time.perf_counter()
        except queue.Full:
            try:
                self._q.get_nowait()
                self._q.put_nowait(s)
                self._last_sample_t = time.perf_counter()
            except queue.Empty:
                pass

    def has_recent_data(self, window_s: float = 1.0) -> bool:
        """True if a sample landed on the output queue within the last
        `window_s` seconds. Distinguishes a real Arduino streaming
        FSR lines from a junk port that's open but silent (which would
        otherwise show CONNECTED forever)."""
        if self._last_sample_t is None:
            return False
        return (time.perf_counter() - self._last_sample_t) <= window_s

    def get_startup_latency(self) -> dict[str, float | None]:
        """Per-port time-to-first-sample latency, keyed by port path
        and reported in milliseconds. Used by the per-block summary
        builder so session.json records how long each Arduino took
        from open to first frame. Returns None per port when that
        port hasn't seen a valid frame yet."""
        out: dict[str, float | None] = {}
        for h in self.hands:
            getter = getattr(h.source, "get_startup_latency_ms", None)
            if callable(getter):
                try:
                    out[h.port] = getter()
                except Exception:
                    out[h.port] = None
            else:
                out[h.port] = None
        return out
