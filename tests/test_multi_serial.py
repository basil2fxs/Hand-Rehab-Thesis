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
    # Has-recent-data tracker; None means no sample has landed yet.
    multi._last_sample_t = None
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


class HasRecentDataTests(unittest.TestCase):
    """has_recent_data distinguishes a real Arduino streaming FSR lines
    from a port that's open but silent (the Mac Bluetooth-Incoming-Port
    failure mode). DiagnosticsScreen uses this to pick CONNECTED vs
    NO DATA for the badge so the therapist gets honest feedback."""

    def test_no_data_before_any_sample(self) -> None:
        multi, _ = _make_multi(["/dev/cu.A"])
        # Fresh source; nothing's been pushed.
        self.assertFalse(multi.has_recent_data())

    def test_true_immediately_after_a_sample(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.A"])
        multi.start()
        try:
            fakes[0].push(time.perf_counter(), (10, 20, 30, 40))
            time.sleep(0.05)   # Let the merger pick it up.
            _ = multi.get_sample()
            self.assertTrue(multi.has_recent_data(window_s=1.0))
        finally:
            multi.stop()

    def test_false_after_window_expires(self) -> None:
        multi, fakes = _make_multi(["/dev/cu.A"])
        multi.start()
        try:
            fakes[0].push(time.perf_counter(), (10, 20, 30, 40))
            time.sleep(0.05)
            _ = multi.get_sample()
            # window=0.01s should already have expired.
            time.sleep(0.05)
            self.assertFalse(multi.has_recent_data(window_s=0.01))
            # Larger window still sees it.
            self.assertTrue(multi.has_recent_data(window_s=10.0))
        finally:
            multi.stop()


class StartupLatencyTests(unittest.TestCase):
    """MultiSerialSource.get_startup_latency() returns a per-port dict
    of time-to-first-sample latencies in milliseconds. Each underlying
    SerialSource records its own port_open_ts / first_sample_ts; the
    multi-source aggregates them."""

    def test_no_latency_before_underlying_source_has_data(self) -> None:
        # Fake source doesn't expose get_startup_latency_ms because
        # it's not a real SerialSource. The multi-source must
        # gracefully return None per port instead of crashing.
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        latencies = multi.get_startup_latency()
        self.assertEqual(set(latencies.keys()), {"/dev/cu.A", "/dev/cu.B"})
        self.assertIsNone(latencies["/dev/cu.A"])
        self.assertIsNone(latencies["/dev/cu.B"])

    def test_underlying_source_latency_surfaces_through_multi(self) -> None:
        # Stub a getter on the fake so the multi-source picks up a
        # non-None value. Confirms the wiring works for real
        # SerialSources without needing pyserial.
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        fakes[0].get_startup_latency_ms = lambda: 1234.5
        fakes[1].get_startup_latency_ms = lambda: 980.0
        latencies = multi.get_startup_latency()
        self.assertAlmostEqual(latencies["/dev/cu.A"], 1234.5)
        self.assertAlmostEqual(latencies["/dev/cu.B"], 980.0)

    def test_getter_exception_yields_none_not_crash(self) -> None:
        # A broken underlying source must not break the whole
        # multi-source latency report.
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        def _raise():
            raise RuntimeError("simulated probe failure")
        fakes[0].get_startup_latency_ms = _raise
        fakes[1].get_startup_latency_ms = lambda: 500.0
        latencies = multi.get_startup_latency()
        self.assertIsNone(latencies["/dev/cu.A"])
        self.assertAlmostEqual(latencies["/dev/cu.B"], 500.0)


class SerialSourceLatencyAccessorTests(unittest.TestCase):
    """SerialSource.get_startup_latency_ms returns None until both
    timestamps are stamped, then (first_sample - port_open) * 1000.
    We can't open a real port in the test, so we drive the timestamps
    by hand."""

    def _bare_source(self):
        from rehab.hardware.serial_source import SerialSource
        s = SerialSource.__new__(SerialSource)
        s._port_open_ts = None
        s._first_sample_ts = None
        return s

    def test_none_until_both_stamps_set(self) -> None:
        s = self._bare_source()
        self.assertIsNone(s.get_startup_latency_ms())
        s._port_open_ts = 100.0
        self.assertIsNone(s.get_startup_latency_ms())  # half-stamped
        s._first_sample_ts = 100.5
        self.assertAlmostEqual(s.get_startup_latency_ms(), 500.0)

    def test_returns_correct_delta_in_ms(self) -> None:
        # port_open at t=2.0s, first_sample at t=3.234s -> 1234 ms.
        s = self._bare_source()
        s._port_open_ts = 2.0
        s._first_sample_ts = 3.234
        self.assertAlmostEqual(s.get_startup_latency_ms(), 1234.0,
                                places=3)



class ShutdownLifecycleTests(unittest.TestCase):
    """The merger thread must not double-spawn, must clean up on stop,
    and must survive an exception bubbling out of a per-hand source."""

    def test_double_start_does_not_spawn_two_mergers(self) -> None:
        # Before the idempotency guard, calling start() twice in a row
        # leaked a thread and made both mergers drain the same queues,
        # which surfaced as duplicated samples on the output queue.
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        multi.start()
        first_thread = multi._merger_thread
        self.assertIsNotNone(first_thread)
        multi.start()
        second_thread = multi._merger_thread
        # Same thread object both times; no new spawn.
        self.assertIs(first_thread, second_thread)
        self.assertTrue(second_thread.is_alive())
        multi.stop()

    def test_stop_then_start_resets_pair_state(self) -> None:
        # A patient who unplugs and replugs an Arduino mid-session
        # triggers a stop/start cycle on this source. Stale right/left
        # pair-cache entries would emit a phantom paired sample on
        # the first frame of the new run. Reset state on both stop
        # AND start so either entry point gets a clean slate.
        multi, fakes = _make_multi(["/dev/cu.A", "/dev/cu.B"])
        multi.start()
        # Park stale cache values directly (would normally be set by
        # the running merger).
        multi._last_right = (1.0, (10, 20, 30, 40))
        multi._last_left = (1.0, (50, 60, 70, 80))
        multi._last_sample_t = 1.0
        multi.stop()
        # stop() clears these.
        self.assertIsNone(multi._last_right)
        self.assertIsNone(multi._last_left)
        self.assertIsNone(multi._last_sample_t)
        # And start() also clears them defensively.
        multi._last_right = (5.0, (1, 2, 3, 4))
        multi.start()
        self.assertIsNone(multi._last_right)
        multi.stop()

    def test_stop_unsets_merger_thread_reference(self) -> None:
        # After stop, the dead thread reference shouldn't linger. A
        # later is_alive() check (e.g. in start's idempotency guard)
        # has to see _merger_thread as None so the next start can
        # spawn a fresh one.
        multi, fakes = _make_multi(["/dev/cu.A"])
        multi.start()
        self.assertIsNotNone(multi._merger_thread)
        multi.stop()
        self.assertIsNone(multi._merger_thread)

    def test_merge_loop_survives_exception_from_get_sample(self) -> None:
        # If an underlying source raises during get_sample (port pulled
        # mid-read, OSError, etc.) the merger used to die silently and
        # the engine would freeze. Wrapping the body in try / except
        # keeps the thread alive across transient hardware glitches.
        multi, fakes = _make_multi(["/dev/cu.A"])
        # Make the fake raise once, then start returning normally.
        raise_count = [0]
        original_get = fakes[0].get_sample

        def _flaky_get(timeout: float = 0.0):
            if raise_count[0] < 1:
                raise_count[0] += 1
                raise OSError("simulated port-yanked mid-read")
            return original_get(timeout=timeout)
        fakes[0].get_sample = _flaky_get
        multi.start()
        # Push a sample after the simulated raise. If the merger died
        # the sample never reaches the output queue.
        time.sleep(0.05)
        fakes[0].push(1.0, (10, 20, 30, 40))
        time.sleep(0.05)
        sample = multi.get_sample(timeout=0.2)
        multi.stop()
        self.assertIsNotNone(
            sample,
            "merger thread should have survived the OSError and "
            "delivered the next sample",
        )
        self.assertEqual(raise_count[0], 1)


if __name__ == "__main__":
    unittest.main()
