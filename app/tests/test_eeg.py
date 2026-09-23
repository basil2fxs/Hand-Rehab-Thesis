"""Unit tests for finger_rehab.hardware.eeg_trigger: backends and the
MarkerWriter's pulse, gap, queue and failure behaviour. The map and
the engine wiring are pinned separately in test_eeg_contract.py.

These replaced the tests for the old finger_rehab/hardware/eeg.py prototype
when its code map (30 = miss, 11-18 stimulus) was retired in favour of
the lab convention (30 = stimulus onset)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeClock:
    """Hand-cranked perf_counter so pulse and gap arithmetic is tested
    exactly, not against real sleeps."""

    def __init__(self, t: float = 100.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


class _RecordingBackend:
    """Backend double that records codes and can be told to fail."""

    name = "fake"

    def __init__(self) -> None:
        self.written: list[int] = []
        self.fail = False
        self.reopen_calls = 0
        self.reopen_result = False
        self.closed = False

    def open(self) -> bool:
        return True

    def write_code(self, code: int) -> bool:
        if self.fail:
            return False
        self.written.append(code)
        return True

    def reopen(self) -> bool:
        self.reopen_calls += 1
        if self.reopen_result:
            self.fail = False
        return self.reopen_result

    def close(self) -> None:
        self.closed = True


def _writer(clock=None, backend=None, **kwargs):
    from finger_rehab.hardware.eeg_trigger import MarkerWriter
    clock = clock or _FakeClock()
    backend = backend or _RecordingBackend()
    defaults = dict(backend=backend, enabled=True, pulse_ms=10.0,
                    gap_ms=10.0, clock=clock)
    defaults.update(kwargs)
    return MarkerWriter(**defaults), backend, clock


class DisabledSilenceTests(unittest.TestCase):
    """The engine calls send/tick/close unconditionally; a disabled or
    backend-less writer must be a no-op, never an error."""

    def test_disabled_writer_noops(self) -> None:
        from finger_rehab.hardware.eeg_trigger import MarkerWriter
        w = MarkerWriter(backend=None, enabled=False)
        self.assertFalse(w.active)
        w.send(30)
        w.tick()
        w.drain(0.01)
        w.close()

    def test_enabled_without_backend_noops(self) -> None:
        from finger_rehab.hardware.eeg_trigger import MarkerWriter
        w = MarkerWriter(backend=None, enabled=True)
        self.assertFalse(w.active)
        w.send(30)
        w.tick()

    def test_disabled_writer_emits_no_records(self) -> None:
        from finger_rehab.hardware.eeg_trigger import MarkerWriter
        records = []
        w = MarkerWriter(backend=None, enabled=False,
                         on_emit=records.append)
        w.send(30)
        w.tick()
        self.assertEqual(records, [])


class PulseProtocolTests(unittest.TestCase):
    """Write code, hold pulse_ms on the clock, write 0."""

    def test_send_puts_code_on_wire_immediately(self) -> None:
        w, backend, _ = _writer()
        w.send(33)
        self.assertEqual(backend.written, [33])

    def test_reset_after_pulse_width(self) -> None:
        w, backend, clock = _writer()
        w.send(33)
        # Inside the pulse: no reset yet.
        clock.advance(0.005)
        w.tick()
        self.assertEqual(backend.written, [33])
        # Past the pulse: exactly one reset byte.
        clock.advance(0.006)
        w.tick()
        self.assertEqual(backend.written, [33, 0])

    def test_close_resets_line_and_closes_backend(self) -> None:
        w, backend, _ = _writer()
        w.send(50)
        w.close()
        self.assertEqual(backend.written[-1], 0)
        self.assertTrue(backend.closed)
        # Idempotent: a second close must not blow up.
        w.close()


class GapAndQueueTests(unittest.TestCase):
    """A second send inside the pulse-plus-gap window queues and emits
    once the line has been low for gap_ms."""

    def test_collision_queues_then_emits(self) -> None:
        w, backend, clock = _writer()
        w.send(30)
        w.send(101)                    # line still high: queues
        self.assertEqual(backend.written, [30])
        clock.advance(0.011)
        w.tick()                       # reset fires
        self.assertEqual(backend.written, [30, 0])
        w.tick()                       # gap not yet served
        self.assertEqual(backend.written, [30, 0])
        clock.advance(0.011)
        w.tick()                       # gap served: queued marker out
        self.assertEqual(backend.written, [30, 0, 101])

    def test_priority_orders_queued_markers(self) -> None:
        # Boundary (204) sent before a stimulus (30) while the line is
        # busy: the stimulus must still emit first.
        w, backend, clock = _writer()
        w.send(101)
        w.send(204)
        w.send(30)
        clock.advance(0.011)
        w.tick()
        clock.advance(0.011)
        w.tick()
        self.assertEqual(backend.written, [101, 0, 30])
        clock.advance(0.011)
        w.tick()
        clock.advance(0.011)
        w.tick()
        self.assertEqual(backend.written, [101, 0, 30, 0, 204])

    def test_queue_overflow_drops_lowest_priority(self) -> None:
        from finger_rehab.hardware.eeg_trigger import MarkerWriter
        records = []
        clock = _FakeClock()
        backend = _RecordingBackend()
        w = MarkerWriter(backend=backend, enabled=True, pulse_ms=10.0,
                         gap_ms=10.0, clock=clock, max_queue=3,
                         on_emit=records.append)
        w.send(30)                     # on the wire
        for code in (100, 101, 102, 240):
            w.send(code)               # 4 queued: one over the cap
        dropped = [r for r in records if r.dropped]
        self.assertEqual(len(dropped), 1)
        # The control code is the lowest priority in the queue.
        self.assertEqual(dropped[0].code, 240)
        self.assertIsNone(dropped[0].t_wire)
        self.assertEqual(w.dropped_count, 1)

    def test_delayed_flag_rides_the_record(self) -> None:
        records = []
        w, backend, clock = _writer(on_emit=records.append)
        w.send(30)
        w.send(101)
        clock.advance(0.011)
        w.tick()
        clock.advance(0.011)
        w.tick()
        by_code = {r.code: r for r in records}
        self.assertFalse(by_code[30].delayed)
        self.assertTrue(by_code[101].delayed)
        # Wire times are logged for both, on the shared clock.
        self.assertIsNotNone(by_code[30].t_wire)
        self.assertIsNotNone(by_code[101].t_wire)


class FailurePolicyTests(unittest.TestCase):
    """3 consecutive failures, one reopen, then degrade and keep
    logging. The behavioural session must never crash for the marker
    channel."""

    def test_three_failures_trigger_single_reopen(self) -> None:
        records = []
        w, backend, clock = _writer(on_emit=records.append)
        backend.fail = True
        for _ in range(3):
            w.send(30)
            clock.advance(0.05)
        self.assertEqual(backend.reopen_calls, 1)
        self.assertTrue(w.degraded)
        self.assertTrue(all(r.failed for r in records))
        self.assertIsNotNone(w.first_failure_t)

    def test_successful_reopen_recovers(self) -> None:
        w, backend, clock = _writer()
        backend.reopen_result = True
        backend.fail = True
        for _ in range(3):
            w.send(30)
            clock.advance(0.05)
        self.assertEqual(backend.reopen_calls, 1)
        self.assertFalse(w.degraded)
        w.send(31)
        self.assertIn(31, backend.written)

    def test_degraded_still_logs_every_intended_marker(self) -> None:
        records = []
        w, backend, clock = _writer(on_emit=records.append)
        backend.fail = True
        for _ in range(3):
            w.send(30)
            clock.advance(0.05)
        wire_len = len(backend.written)
        w.send(101)
        clock.advance(0.05)
        # Nothing new on the wire, but the intent is on the record.
        self.assertEqual(len(backend.written), wire_len)
        self.assertEqual(records[-1].code, 101)
        self.assertTrue(records[-1].failed)

    def test_writer_survives_backend_raising(self) -> None:
        class _RaisingBackend(_RecordingBackend):
            def write_code(self, code: int) -> bool:
                raise IOError("simulated cable yank")

        w, backend, clock = _writer(backend=_RaisingBackend())
        w.send(30)          # must not propagate
        clock.advance(0.011)
        w.tick()            # reset write also raises: still contained
        w.close()


class SerialBackendTests(unittest.TestCase):

    def test_write_code_is_single_raw_byte(self) -> None:
        from finger_rehab.hardware.eeg_trigger import SerialBackend
        backend = SerialBackend("dummy")

        class _FakePort:
            is_open = True

            def __init__(self) -> None:
                self.data = bytearray()

            def write(self, payload: bytes) -> int:
                self.data += bytes(payload)
                return len(payload)

        port = _FakePort()
        backend._serial = port
        # 220 sits above 127: a chr()/UTF-8 regression would emit two
        # bytes here and corrupt every code past 127.
        self.assertTrue(backend.write_code(220))
        self.assertEqual(bytes(port.data), bytes([0xDC]))

    def test_open_passes_write_timeout(self) -> None:
        # A wedged box must never hang the frame loop: the open call
        # has to cap single writes.
        from finger_rehab.hardware import eeg_trigger
        captured: dict = {}

        class _StubSerialModule:
            EIGHTBITS = 8
            PARITY_NONE = "N"
            STOPBITS_ONE = 1

            class Serial:
                def __init__(self, port, baud, **kwargs):
                    captured["port"] = port
                    captured.update(kwargs)
                    self.is_open = True

                def close(self):
                    self.is_open = False

        original = eeg_trigger.serial
        original_have = eeg_trigger._HAVE_SERIAL
        eeg_trigger.serial = _StubSerialModule
        eeg_trigger._HAVE_SERIAL = True
        try:
            backend = eeg_trigger.SerialBackend("COM10")
            self.assertTrue(backend.open())
            self.assertIn("write_timeout", captured)
            self.assertGreater(captured["write_timeout"], 0)
            self.assertLessEqual(captured["write_timeout"], 1.0)
        finally:
            eeg_trigger.serial = original
            eeg_trigger._HAVE_SERIAL = original_have


class DummyBackendTests(unittest.TestCase):
    """The dummy discards nothing: every code is kept with a
    timestamp so a no-hardware session still has a checkable marker
    record."""

    def test_dummy_keeps_every_write(self) -> None:
        from finger_rehab.hardware.eeg_trigger import DummyBackend
        backend = DummyBackend()
        self.assertTrue(backend.open())
        for code in (30, 0, 101, 0):
            self.assertTrue(backend.write_code(code))
        self.assertEqual([c for _, c in backend.written], [30, 0, 101, 0])


class ConfigFactoryTests(unittest.TestCase):

    @staticmethod
    def _get_from(mapping):
        return lambda key, default=None: mapping.get(key, default)

    def test_disabled_config_returns_inert_writer(self) -> None:
        from finger_rehab.hardware.eeg_trigger import writer_from_config
        w = writer_from_config(self._get_from({"eeg.enabled": False}))
        self.assertFalse(w.active)

    def test_enabled_without_port_falls_back_to_dummy(self) -> None:
        from finger_rehab.hardware.eeg_trigger import DummyBackend, writer_from_config
        w = writer_from_config(self._get_from({
            "eeg.enabled": True, "eeg.require_port": False}))
        self.assertTrue(w.active)
        self.assertIsInstance(w.backend, DummyBackend)

    def test_require_port_refuses_without_a_box(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (TriggerPortError,
                                                writer_from_config)
        with self.assertRaises(TriggerPortError):
            writer_from_config(self._get_from({
                "eeg.enabled": True, "eeg.require_port": True,
                "eeg.port": None}))
        with self.assertRaises(TriggerPortError):
            # A port that cannot open must refuse too, not fall back.
            writer_from_config(self._get_from({
                "eeg.enabled": True, "eeg.require_port": True,
                "eeg.port": "/dev/does-not-exist-eeg"}))


if __name__ == "__main__":
    unittest.main()
