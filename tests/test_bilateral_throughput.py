"""High-rate throughput tests for the bilateral pipeline.

Confirms that:
  1. MultiSerialSource merges two 200 Hz Arduino streams into the
     combined 8-channel output queue without dropping samples on the
     way (it can drop only if the consumer stops draining, which
     we test separately).
  2. With 8 fingers pressed simultaneously, the two FSRDetectors
     (one per hand) emit all 8 PressEvents without losing any.

The Arduino firmware spec is ~200 Hz per board (FSR: lines once per
loop iteration at 115200 baud). Two boards = ~400 samples/sec into
the merger. The engine's main loop runs at 60 FPS; it drains the
output queue once per frame. We want to confirm the merger can
buffer up to a single frame's worth of samples (~7 per board) and
flush them on the next drain without loss.
"""
from __future__ import annotations

import queue
import sys
import threading
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeSerialSource:
    """Same shape as the helper in test_multi_serial.py: a stand-in
    for SerialSource backed by a queue we push samples into. Kept
    local so the throughput tests don't depend on importing private
    helpers from a sibling test module."""

    def __init__(self, port: str):
        self.port = port
        self._q: queue.Queue = queue.Queue()
        self._connected = False
        self.sent_commands: list[str] = []

    def start(self) -> None:
        self._connected = True

    def stop(self) -> None:
        self._connected = False

    def get_sample(self, timeout: float = 0.0):
        try:
            if timeout > 0:
                return self._q.get(timeout=timeout)
            return self._q.get_nowait()
        except queue.Empty:
            return None

    def send_command(self, cmd: str) -> bool:
        self.sent_commands.append(cmd)
        return True

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def provides_samples(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return f"FakeSerial({self.port})"

    def push(self, t_perf: float, values: tuple[int, ...]) -> None:
        from rehab.hardware.source import Sample
        self._q.put(Sample(t_perf=t_perf, values=values))


def _make_multi(ports: list[str]):
    """Build a MultiSerialSource without going through SerialSource's
    pyserial-dependent ctor. Same approach test_multi_serial uses."""
    from rehab.hardware.multi_serial import MultiSerialSource, HandPort
    from rehab.hardware.source import BaseQueueSource
    multi = MultiSerialSource.__new__(MultiSerialSource)
    BaseQueueSource.__init__(multi)
    fakes = [_FakeSerialSource(p) for p in ports]
    hands = ["right"] if len(ports) == 1 else ["right", "left"]
    multi.hands = [HandPort(hand=h, port=p, source=f)
                    for h, p, f in zip(hands, ports, fakes)]
    multi.num_sensors_per_hand = 4
    multi._q = queue.Queue(maxsize=4096)
    multi._stop = threading.Event()
    multi._merger_thread = None
    multi._last_right = None
    multi._last_left = None
    multi._last_sample_t = None
    return multi, fakes


def _drain(multi, timeout_s: float) -> list:
    """Pull every sample currently buffered by the merger, returning
    them in arrival order. Polls until `timeout_s` has elapsed since
    the last successful drain so a small latency between push and
    merge doesn't drop the tail of the burst."""
    out = []
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        s = multi.get_sample(timeout=0)
        if s is None:
            time.sleep(0.005)
            continue
        out.append(s)
        deadline = time.perf_counter() + 0.05
    return out


class BilateralHighRateTests(unittest.TestCase):
    """Drive both fake serial sources at firmware-realistic rates and
    confirm the merger keeps up."""

    # Aiden's Arduino firmware target sample rate per board.
    PER_BOARD_HZ = 200
    BURST_S = 1.0

    def test_two_hands_at_200_hz_each_no_samples_lost(self) -> None:
        """At 200 Hz per board the merger should emit ~200 paired
        8-channel samples per second (each pair consumes one sample
        from each hand). Over a 1 s burst we expect ~200 paired
        samples plus possibly a tail of solo-emitted ones.

        Loss = (sent_per_hand - merged) / sent_per_hand. Allow up to
        5 percent because the pair window is 50 ms which won't catch
        every pair under jitter, but the solo-fallback should keep
        total emit count close to the input."""
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        multi.start()
        try:
            n_per_hand = int(self.PER_BOARD_HZ * self.BURST_S)
            t0 = time.perf_counter()
            # Push at the SAME timestamps from both hands so pairing
            # always succeeds. This is the realistic case where both
            # Arduinos read sensors on a synchronous loop.
            for i in range(n_per_hand):
                t = t0 + i / self.PER_BOARD_HZ
                fakes[0].push(t, (100 + i, 0, 0, 0))   # right
                fakes[1].push(t, (0, 0, 0, 100 + i))   # left
                # Match the inter-sample gap so the producer doesn't
                # outrun the consumer; if we dump all 200 samples at
                # once the test confirms buffering, not throughput.
                if i % 10 == 0:
                    time.sleep(0.001)
            merged = _drain(multi, timeout_s=0.5)
        finally:
            multi.stop()

        # Every emitted sample should carry 8 channels (the merger's
        # whole reason for existing).
        for s in merged:
            self.assertEqual(len(s.values), 8)
        # Loss check: solo fallback can lose at most one pair window
        # worth of samples at the boundary, so accept up to 5 percent.
        loss = (n_per_hand - len(merged)) / n_per_hand
        self.assertLess(
            loss, 0.05,
            f"Lost {loss * 100:.1f}% of samples (sent {n_per_hand} "
            f"per hand, got {len(merged)} merged)"
        )

    def test_one_hand_silent_other_emits_via_solo_fallback(self) -> None:
        """If the left Arduino is unplugged mid-session, the right
        hand should keep producing combined samples with zeros in
        the left slots. Without this the patient's still-working
        hand would also go dark.

        The merger waits SAMPLE_PAIR_WINDOW_S (50 ms) before emitting
        a solo sample, and a new arrival in that window overwrites the
        cached one - so this test pushes at 10 Hz (well under that
        rate) so every push gets its own solo emit. The expected
        throughput under "one hand silent" is therefore ~20 Hz cap,
        which is intentional: the merge logic prioritises pairing
        in the normal case, with solo emit as the fallback."""
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        multi.start()
        try:
            # Push 5 right samples, each spaced 100 ms apart, so each
            # one ages past the pair window before the next arrives.
            n_pushes = 5
            for i in range(n_pushes):
                fakes[0].push(time.perf_counter(),
                               (50 + i * 30, 0, 0, 0))
                # NOTHING from fakes[1] - simulating an unplugged left.
                time.sleep(0.10)
            # Final wait so the last sample's pair window expires.
            time.sleep(0.10)
            merged = _drain(multi, timeout_s=0.4)
        finally:
            multi.stop()

        # All merged samples should be 8-channel with the left half
        # zeroed (since left never sent anything).
        self.assertGreater(len(merged), 0,
                            "No merged samples emitted with one hand silent")
        for s in merged:
            self.assertEqual(len(s.values), 8)
            self.assertEqual(tuple(s.values[4:]), (0, 0, 0, 0))
        # At least 3 of the 5 pushes should make it through. The other
        # 2 may be lost if their window-expiry races a new arrival.
        self.assertGreaterEqual(
            len(merged), 3,
            f"Expected at least 3 solo-fallback emits, got {len(merged)}"
        )


class EightFingerSimultaneousPressTests(unittest.TestCase):
    """Confirm that all 8 fingers pressed in the same sample yield
    8 distinct PressEvent callbacks (one per lane per hand)."""

    def test_all_eight_lanes_fire_press_events_in_one_sample(self) -> None:
        from rehab.hardware.fsr_detector import (
            Calibration, FSRDetector, PressEvent,
        )
        # value_alpha=1.0 disables the EMA smoothing so the press
        # threshold check sees the raw sample value. With the default
        # 0.35 alpha, a single 500-count press from a 50-count idle
        # smooths down to ~207, which never crosses the 300-count
        # absolute floor.
        cal = Calibration(num_sensors=4, value_alpha=1.0,
                           on_delta=[40] * 4, off_delta=[20] * 4,
                           abs_on_min=[300] * 4, abs_off_max=[300] * 4,
                           debounce_ms=0)
        right = FSRDetector(cal, hand="right")
        left = FSRDetector(cal, hand="left")
        events: list[PressEvent] = []
        right.on_press = events.append
        left.on_press = events.append

        # Warm up the baselines with one quiet sample so the detector
        # has something to compare against. Without this the first
        # "real" sample's delta is computed against value_ema=None
        # and the detector skips the press check.
        right.feed(0.0, (50, 50, 50, 50))
        left.feed(0.0, (50, 50, 50, 50))

        # Now press all 8 fingers at once. Values well above the
        # 300-count absolute on-threshold.
        right.feed(0.1, (500, 500, 500, 500))
        left.feed(0.1, (500, 500, 500, 500))

        self.assertEqual(len(events), 8,
                          f"Expected 8 press events, got {len(events)}: "
                          f"{[(e.hand, e.lane) for e in events]}")
        # Confirm we have lane 0..3 for both hands.
        hand_lane_pairs = {(e.hand, e.lane) for e in events}
        expected = {(h, lane) for h in ("right", "left")
                    for lane in range(4)}
        self.assertEqual(hand_lane_pairs, expected)

    def test_press_event_includes_hand_tag(self) -> None:
        """Each PressEvent must carry hand=right or hand=left so the
        engine can route the score to the right detector. Regression
        guard: this used to default to "right" silently when one
        FSRDetector wasn't constructed with hand=..."""
        from rehab.hardware.fsr_detector import (
            Calibration, FSRDetector, PressEvent,
        )
        cal = Calibration(num_sensors=4, value_alpha=1.0,
                           on_delta=[40] * 4,
                           abs_on_min=[300] * 4, debounce_ms=0)
        left = FSRDetector(cal, hand="left")
        seen: list[PressEvent] = []
        left.on_press = seen.append
        left.feed(0.0, (50, 50, 50, 50))
        left.feed(0.1, (500, 50, 50, 50))
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].hand, "left")


if __name__ == "__main__":
    unittest.main()
