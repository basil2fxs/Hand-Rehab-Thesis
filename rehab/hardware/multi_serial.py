"""Multi-Arduino source. Aiden's firmware exposes one hand (4 sensors)
per board, so bilateral training needs two boards plugged in. This
module fans out the standard Source interface over 1 or 2 underlying
SerialSource instances and merges their sample streams into a single
4- or 8-value vector for the engine.

Hand assignment is plug-order based: the first Arduino discovered is
the right hand, the second is the left. The user can swap by unplugging
in the reverse order before starting, or override via cfg.

The engine sees this as a normal Source: start / stop / get_sample /
send_command / is_connected. No engine-side changes needed beyond
swapping which Source class main.py constructs.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
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
    """How long to wait for the OTHER hand's sample to pair with the
    current one in bilateral mode. If the second sample doesn't arrive
    in this window we fall back to the last-known values or zeros."""

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
        # Last sample seen per hand, used to pair up bilateral samples
        # that arrive at slightly different times.
        self._last_right: tuple[float, tuple[int, ...]] | None = None
        self._last_left:  tuple[float, tuple[int, ...]] | None = None

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
        for h in self.hands:
            try:
                h.source.start()
            except Exception as e:
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

    def get_sample(self, timeout: float = 0.0):
        try:
            if timeout > 0:
                return self._q.get(timeout=timeout)
            return self._q.get_nowait()
        except queue.Empty:
            return None

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
        into the unified vector the engine expects."""
        n = self.num_sensors_per_hand
        only_one = len(self.hands) == 1
        while not self._stop.is_set():
            any_consumed = False
            for h in self.hands:
                s = h.source.get_sample(timeout=0)
                if s is None:
                    continue
                any_consumed = True
                if only_one:
                    # Single board: forward verbatim. The engine knows
                    # which hand it's assigned via cfg.bilateral.hand.
                    try:
                        self._q.put_nowait(s)
                    except queue.Full:
                        try:
                            self._q.get_nowait()
                            self._q.put_nowait(s)
                        except queue.Empty:
                            pass
                else:
                    # Two boards: cache for pairing.
                    if h.hand == "right":
                        self._last_right = (s.t_perf, tuple(s.values[:n]))
                    else:
                        self._last_left = (s.t_perf, tuple(s.values[:n]))
            # Run the pair-emit check EVERY iteration in bilateral mode,
            # not just when a new sample arrived. Without this, a solo
            # hand that goes silent never triggers the window-expiry
            # fallback (the function would only be called once when its
            # first sample arrived, at which point the window hadn't
            # yet elapsed).
            if not only_one:
                self._emit_paired_if_ready()
            if not any_consumed:
                # No data this tick; nap so we don't burn a CPU core.
                time.sleep(0.002)

    def _emit_paired_if_ready(self) -> None:
        """For the two-Arduino case: emit one combined 8-value sample
        whenever we have a recent reading from BOTH hands. If one hand
        hasn't reported in SAMPLE_PAIR_WINDOW_S, fill its slots with
        zeros so the patient still sees the active hand's data."""
        n = self.num_sensors_per_hand
        zeros = (0,) * n
        now = time.perf_counter()
        right = self._last_right
        left = self._last_left
        # Decide the timestamp + values for the combined sample.
        if right is not None and left is not None:
            # Pair them if their timestamps are within the window.
            tr, vr = right
            tl, vl = left
            if abs(tr - tl) <= self.SAMPLE_PAIR_WINDOW_S:
                t = max(tr, tl)
                values = tuple(vr) + tuple(vl)
                # Consume both so we don't re-emit the same pair.
                self._last_right = None
                self._last_left = None
                self._push_combined(t, values)
                return
        # No pair available yet. If the freshest single sample is
        # already past the pair window, emit it solo and zero the
        # other hand so the engine still sees activity.
        freshest = None
        if right is not None and (left is None
                                    or right[0] >= left[0]):
            freshest = ("right", right)
        elif left is not None:
            freshest = ("left", left)
        if freshest is None:
            return
        hand, (t, v) = freshest
        if now - t < self.SAMPLE_PAIR_WINDOW_S:
            # Still within the pair window; wait for the other hand.
            return
        if hand == "right":
            self._push_combined(t, tuple(v) + zeros)
            self._last_right = None
        else:
            self._push_combined(t, zeros + tuple(v))
            self._last_left = None

    def _push_combined(self, t_perf: float, values: tuple[int, ...]) -> None:
        s = Sample(t_perf=t_perf, values=values)
        try:
            self._q.put_nowait(s)
        except queue.Full:
            try:
                self._q.get_nowait()
                self._q.put_nowait(s)
            except queue.Empty:
                pass
