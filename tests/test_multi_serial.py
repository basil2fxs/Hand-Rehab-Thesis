"""Tests for MultiSerialSource. Each underlying SerialSource is faked
with a queue we can push samples into, so we don't need a real Arduino
or pyserial."""
from __future__ import annotations

import queue
import sys
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeSerialSource:
    """Stand-in for SerialSource that exposes the same interface but
    reads samples from an internal queue we feed from the test."""

    def __init__(self, port: str):
        self.port = port
        self._q: queue.Queue = queue.Queue()
        self._connected = False
        self.sent_commands: list[str] = []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True
        self._connected = True

    def stop(self) -> None:
        self.stopped = True
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


def _make_multi(ports: list[str],
                 hand_assignment: list[str] | None = None):
    """Build a MultiSerialSource and swap its SerialSource instances
    for fakes. Returns (multi, list[_FakeSerialSource]).

    `hand_assignment` overrides the default plug-order assignment
    (first=right, second=left). Useful for testing the lone-left-hand
    case where only the left Arduino is plugged in."""
    from rehab.hardware.multi_serial import MultiSerialSource
    # We can't construct MultiSerialSource normally without pyserial
    # installed (its __init__ builds SerialSources). Build via __new__
    # and assemble the state manually.
    multi = MultiSerialSource.__new__(MultiSerialSource)
    # super().__init__() does queue setup; emulate it.
    from rehab.hardware.source import BaseQueueSource
    BaseQueueSource.__init__(multi)
    fakes = [_FakeSerialSource(p) for p in ports]
    from rehab.hardware.multi_serial import HandPort
    if hand_assignment is None:
        hands = ["right"] if len(ports) == 1 else ["right", "left"]
    else:
        hands = hand_assignment
    multi.hands = [HandPort(hand=h, port=p, source=f)
                    for h, p, f in zip(hands, ports, fakes)]
    multi.num_sensors_per_hand = 4
    multi._q = queue.Queue(maxsize=4096)
    import threading
    multi._stop = threading.Event()
    multi._merger_thread = None
    multi._last_right = None
    multi._last_left = None
    return multi, fakes


class SingleArduinoTests(unittest.TestCase):
    """One Arduino plugged in (right hand only). Samples forward
    through unchanged."""

    def test_forwards_single_hand_samples(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.A"])
        multi.start()
        try:
            fakes[0].push(1.0, (100, 200, 300, 400))
            # Give the merger thread a moment.
            time.sleep(0.05)
            s = multi.get_sample(timeout=0.5)
            self.assertIsNotNone(s)
            self.assertEqual(s.values, (100, 200, 300, 400))
        finally:
            multi.stop()

    def test_hand_modes_available_single_arduino(self) -> None:
        multi, _ = _make_multi(["/dev/cu.A"])
        # With one Arduino assigned to the right hand, only "right" is
        # available. "left" and "both" should be excluded.
        self.assertEqual(multi.hand_modes_available, {"right"})

    def test_is_connected_reflects_underlying(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.A"])
        # Before start: not connected.
        self.assertFalse(multi.is_connected)
        multi.start()
        try:
            self.assertTrue(multi.is_connected)
            # Simulate the underlying source dropping.
            fakes[0]._connected = False
            self.assertFalse(multi.is_connected)
        finally:
            multi.stop()


class DualArduinoTests(unittest.TestCase):
    """Two Arduinos: combines into an 8-value sample stream."""

    def test_pairs_simultaneous_samples_into_8_values(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.RIGHT", "/dev/cu.LEFT"])
        multi.start()
        try:
            # Use real perf_counter timestamps so the merger doesn't
            # treat the samples as stale relative to wall-clock now.
            t = time.perf_counter()
            fakes[0].push(t, (10, 20, 30, 40))         # right
            fakes[1].push(t + 0.005, (50, 60, 70, 80))  # left, 5 ms later
            time.sleep(0.03)
            s = multi.get_sample(timeout=0.5)
            self.assertIsNotNone(s)
            self.assertEqual(s.values, (10, 20, 30, 40, 50, 60, 70, 80))
        finally:
            multi.stop()

    def test_one_hand_only_zeros_the_other(self) -> None:
        # If only one hand reports and the pair window elapses with no
        # second sample, the merger emits a solo sample with zeros for
        # the missing hand so the engine still sees activity.
        multi, fakes = _make_multi(["/dev/cu.RIGHT", "/dev/cu.LEFT"])
        multi.start()
        try:
            fakes[0].push(time.perf_counter(), (10, 20, 30, 40))
            time.sleep(0.15)         # well past SAMPLE_PAIR_WINDOW_S
            s = multi.get_sample(timeout=0.5)
            self.assertIsNotNone(s)
            self.assertEqual(s.values[:4], (10, 20, 30, 40))
            self.assertEqual(s.values[4:], (0, 0, 0, 0))
        finally:
            multi.stop()

    def test_hand_modes_available_dual_arduino(self) -> None:
        multi, _ = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        self.assertEqual(multi.hand_modes_available, {"right", "left", "both"})


class StimRoutingTests(unittest.TestCase):
    """send_command translates global lane numbers into hand-local
    STIM:n calls so each Arduino only fires its own motor."""

    def test_stim_lane_1_routes_to_right(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        multi.send_command("STIM:1")
        self.assertEqual(fakes[0].sent_commands, ["STIM:1"])
        self.assertEqual(fakes[1].sent_commands, [])

    def test_stim_lane_5_routes_to_left_as_local_1(self) -> None:
        # Lane 5 globally = lane 1 on the left hand.
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        multi.send_command("STIM:5")
        self.assertEqual(fakes[0].sent_commands, [])
        self.assertEqual(fakes[1].sent_commands, ["STIM:1"])

    def test_stop_broadcasts_to_all(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        multi.send_command("STOP")
        self.assertEqual(fakes[0].sent_commands, ["STOP"])
        self.assertEqual(fakes[1].sent_commands, ["STOP"])

    def test_explicit_hand_prefix(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        multi.send_command("LEFT:STIM:2")
        self.assertEqual(fakes[0].sent_commands, [])
        self.assertEqual(fakes[1].sent_commands, ["STIM:2"])

    def test_stim_out_of_range_returns_false(self) -> None:
        # Lane 9 is past 2N for N=4. Should be rejected, not routed.
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        self.assertFalse(multi.send_command("STIM:9"))
        self.assertEqual(fakes[0].sent_commands, [])
        self.assertEqual(fakes[1].sent_commands, [])

    def test_malformed_stim_returns_false(self) -> None:
        # Bad integer must not crash and must not send anything.
        multi, fakes = _make_multi(["/dev/cu.R", "/dev/cu.L"])
        self.assertFalse(multi.send_command("STIM:abc"))
        self.assertFalse(multi.send_command("STIM:"))
        self.assertEqual(fakes[0].sent_commands, [])
        self.assertEqual(fakes[1].sent_commands, [])

    def test_explicit_prefix_to_missing_hand_returns_false(self) -> None:
        # LEFT:... when only the right board is plugged in must not crash.
        multi, fakes = _make_multi(["/dev/cu.R"])  # default: right
        self.assertFalse(multi.send_command("LEFT:STIM:1"))
        self.assertEqual(fakes[0].sent_commands, [])


class SingleArduinoStimRoutingTests(unittest.TestCase):
    """The engine sends STIM:1..N for both unilateral hands. With one
    Arduino plugged in, those commands must reach it regardless of which
    hand it represents - otherwise unilateral-left sessions silently
    fail to fire the motors."""

    def test_stim_routes_to_single_right_arduino(self) -> None:
        # Plug-order default: single board is right. STIM:1..4 should
        # forward verbatim, no rewriting needed.
        multi, fakes = _make_multi(["/dev/cu.R"])
        for lane in range(1, 5):
            multi.send_command(f"STIM:{lane}")
        self.assertEqual(fakes[0].sent_commands,
                          ["STIM:1", "STIM:2", "STIM:3", "STIM:4"])

    def test_stim_routes_to_single_left_arduino(self) -> None:
        # Regression: previously the routing logic always picked
        # target_hand="right" for lanes 1..N, so a lone left Arduino
        # never received STIM commands. STIM:1..4 must now reach it.
        multi, fakes = _make_multi(["/dev/cu.L"], hand_assignment=["left"])
        for lane in range(1, 5):
            multi.send_command(f"STIM:{lane}")
        self.assertEqual(fakes[0].sent_commands,
                          ["STIM:1", "STIM:2", "STIM:3", "STIM:4"])

    def test_stim_out_of_range_on_single_board_returns_false(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.R"])
        self.assertFalse(multi.send_command("STIM:5"))
        self.assertFalse(multi.send_command("STIM:0"))
        self.assertEqual(fakes[0].sent_commands, [])

    def test_explicit_prefix_still_works_on_single_left(self) -> None:
        # Even with a single left board, an explicit LEFT:STIM:n still
        # routes correctly. RIGHT:... silently no-ops.
        multi, fakes = _make_multi(["/dev/cu.L"], hand_assignment=["left"])
        self.assertTrue(multi.send_command("LEFT:STIM:3"))
        self.assertFalse(multi.send_command("RIGHT:STIM:3"))
        self.assertEqual(fakes[0].sent_commands, ["STIM:3"])


if __name__ == "__main__":
    unittest.main()
