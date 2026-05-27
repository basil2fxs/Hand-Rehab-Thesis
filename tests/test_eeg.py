"""Tests for the EEGMarker. The serial port is faked via a small stub
class so we don't need a real amplifier or pyserial installed."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakeSerial:
    """Stand-in for serial.Serial. Captures everything written so the
    test can check which byte codes were emitted."""

    def __init__(self) -> None:
        self.is_open = True
        self.written = bytearray()
        self.closed = False
        self.write_should_raise = False
        self.close_should_raise = False

    def write(self, data: bytes) -> int:
        if self.write_should_raise:
            raise IOError("simulated write failure")
        self.written += bytes(data)
        return len(data)

    def close(self) -> None:
        if self.close_should_raise:
            raise IOError("simulated close failure")
        self.is_open = False
        self.closed = True


def _make_marker(reset_after_s: float = 0.020):
    """Build an EEGMarker with a fake serial port already attached. Skips
    the normal init() path so we don't need pyserial installed."""
    from rehab.hardware.eeg import EEGMarker
    m = EEGMarker(port="dummy", enabled=True, reset_after_s=reset_after_s)
    m._serial = _FakeSerial()
    return m


class InitGuardTests(unittest.TestCase):
    """init() must fail safe across every disabled / unavailable path."""

    def test_disabled_init_returns_false(self) -> None:
        from rehab.hardware.eeg import EEGMarker
        m = EEGMarker(port="dummy", enabled=False)
        self.assertFalse(m.init())
        self.assertFalse(m.is_open)

    def test_no_port_init_returns_false(self) -> None:
        from rehab.hardware.eeg import EEGMarker
        m = EEGMarker(port=None, enabled=True)
        self.assertFalse(m.init())
        self.assertFalse(m.is_open)

    def test_idempotent_init_when_already_open(self) -> None:
        # If _serial is already open, init() returns True without
        # opening again.
        m = _make_marker()
        self.assertTrue(m.init())
        # And the stub didn't get clobbered.
        self.assertIsInstance(m._serial, _FakeSerial)


class NoOpBeforeInitTests(unittest.TestCase):
    """Every send_* method must be a no-op when the port isn't open.
    The engine calls these unconditionally - the silence is the point."""

    def test_all_send_methods_noop(self) -> None:
        from rehab.hardware.eeg import EEGMarker
        m = EEGMarker(port=None, enabled=False)
        # None of these should raise, and none should crash on a None _serial.
        m.block_start()
        m.block_end()
        m.block_abandoned()
        m.stim(0)
        m.response(0)
        m.miss()
        m.tick()
        m.close()  # idempotent close on uninitialised marker

    def test_close_when_never_opened_is_safe(self) -> None:
        from rehab.hardware.eeg import EEGMarker
        m = EEGMarker(port=None, enabled=False)
        m.close()
        # And again, just to make sure.
        m.close()


class EventCodeTests(unittest.TestCase):
    """Each event method must emit the documented byte code."""

    def test_block_start_writes_1(self) -> None:
        m = _make_marker()
        m.block_start()
        self.assertEqual(bytes(m._serial.written)[:1], bytes([1]))

    def test_block_end_writes_2(self) -> None:
        m = _make_marker()
        m.block_end()
        self.assertEqual(bytes(m._serial.written)[:1], bytes([2]))

    def test_block_abandoned_writes_3(self) -> None:
        m = _make_marker()
        m.block_abandoned()
        self.assertEqual(bytes(m._serial.written)[:1], bytes([3]))

    def test_miss_writes_30(self) -> None:
        m = _make_marker()
        m.miss()
        self.assertEqual(bytes(m._serial.written)[:1], bytes([30]))

    def test_stim_encodes_lane_correctly(self) -> None:
        # Lane 0 -> 11, lane 1 -> 12, ..., lane 7 -> 18.
        m = _make_marker()
        for lane in range(8):
            m._serial = _FakeSerial()
            m.stim(lane)
            self.assertEqual(bytes(m._serial.written)[:1], bytes([11 + lane]))

    def test_response_encodes_lane_correctly(self) -> None:
        # Lane 0 -> 21, lane 1 -> 22, ..., lane 7 -> 28.
        m = _make_marker()
        for lane in range(8):
            m._serial = _FakeSerial()
            m.response(lane)
            self.assertEqual(bytes(m._serial.written)[:1], bytes([21 + lane]))

    def test_stim_ignores_out_of_range_lane(self) -> None:
        m = _make_marker()
        m.stim(-1)
        m.stim(8)
        m.stim(100)
        self.assertEqual(bytes(m._serial.written), b"")

    def test_response_ignores_out_of_range_lane(self) -> None:
        m = _make_marker()
        m.response(-1)
        m.response(8)
        m.response(100)
        self.assertEqual(bytes(m._serial.written), b"")


class ResetTickTests(unittest.TestCase):
    """tick() must drop a reset byte after reset_after_s so the amp
    line returns to idle between markers."""

    def test_tick_sends_reset_after_delay(self) -> None:
        m = _make_marker(reset_after_s=0.005)
        m.stim(0)
        first_len = len(m._serial.written)
        # Before the delay elapses, tick is a no-op.
        m.tick()
        self.assertEqual(len(m._serial.written), first_len)
        # After the delay, tick emits one reset byte.
        time.sleep(0.010)
        m.tick()
        self.assertEqual(bytes(m._serial.written)[-1:], bytes([0]))

    def test_tick_noop_when_no_pending(self) -> None:
        m = _make_marker(reset_after_s=0.005)
        # No sends yet -> no resets pending -> tick writes nothing.
        m.tick()
        self.assertEqual(bytes(m._serial.written), b"")

    def test_tick_emits_only_one_reset_per_call(self) -> None:
        # Two rapid sends queue two resets, but tick collapses them into
        # a single reset byte - the amp only needs to return to idle once.
        m = _make_marker(reset_after_s=0.005)
        m.stim(0)
        m.stim(1)
        before_reset = len(m._serial.written)
        time.sleep(0.010)
        m.tick()
        # Exactly one reset byte appended.
        self.assertEqual(len(m._serial.written), before_reset + 1)
        self.assertEqual(bytes(m._serial.written)[-1:], bytes([0]))


class CloseTests(unittest.TestCase):

    def test_close_sends_final_reset_and_closes_port(self) -> None:
        m = _make_marker()
        fake = m._serial
        m.close()
        # Last byte must be the reset code so the amp doesn't latch on
        # whatever marker happened to fire last.
        self.assertEqual(bytes(fake.written)[-1:], bytes([0]))
        self.assertTrue(fake.closed)
        self.assertIsNone(m._serial)

    def test_close_is_idempotent(self) -> None:
        m = _make_marker()
        m.close()
        # Second close must not raise even though _serial is now None.
        m.close()
        self.assertIsNone(m._serial)

    def test_close_clears_pending_resets(self) -> None:
        m = _make_marker(reset_after_s=1.0)
        m.stim(0)
        self.assertTrue(m._pending_resets)
        m.close()
        self.assertEqual(m._pending_resets, [])

    def test_close_survives_underlying_close_failure(self) -> None:
        # If the underlying port raises during close, the marker should
        # still null out its handle - otherwise a session shutdown gets
        # stuck on a stale half-open port.
        m = _make_marker()
        m._serial.close_should_raise = True
        m.close()
        self.assertIsNone(m._serial)


class WriteFailureTests(unittest.TestCase):
    """A serial write that raises (cable yanked mid-session, amp
    crashed) must not propagate up to the engine."""

    def test_write_failure_swallowed_by_send(self) -> None:
        m = _make_marker()
        m._serial.write_should_raise = True
        # Calling any send method must not raise.
        m.block_start()
        m.stim(0)
        m.response(0)
        m.miss()
        m.tick()

    def test_write_failure_does_not_block_close(self) -> None:
        # Regression: with no write_timeout the final reset byte in
        # close() could hang on a dead amp. We test the simulated raise
        # path - the timeout setting itself is verified at the
        # serial.Serial(...) call site.
        m = _make_marker()
        m._serial.write_should_raise = True
        m.close()
        self.assertIsNone(m._serial)


class WriteTimeoutConfiguredTests(unittest.TestCase):
    """The write_timeout kwarg must be passed when init() opens the
    port - otherwise a wedged amp can hang the per-frame tick."""

    def test_init_passes_write_timeout(self) -> None:
        # Patch in a fake serial module and capture the open kwargs.
        from rehab.hardware import eeg
        captured: dict = {}

        class _StubSerial:
            EIGHTBITS = 8
            PARITY_NONE = "N"
            STOPBITS_ONE = 1

            class Serial:
                def __init__(self, port, baud, **kwargs):
                    captured["port"] = port
                    captured["baud"] = baud
                    captured.update(kwargs)
                    self.is_open = True

                def close(self): self.is_open = False
                def write(self, data): return len(data)

        original_serial = eeg.serial
        original_have = eeg._HAVE_SERIAL
        eeg.serial = _StubSerial
        eeg._HAVE_SERIAL = True
        try:
            m = eeg.EEGMarker(port="dummy", enabled=True)
            self.assertTrue(m.init())
            # The whole point of this audit: write_timeout must be set
            # so a stuck write can never freeze close() / tick().
            self.assertIn("write_timeout", captured)
            self.assertGreater(captured["write_timeout"], 0)
            self.assertLessEqual(captured["write_timeout"], 1.0)
        finally:
            eeg.serial = original_serial
            eeg._HAVE_SERIAL = original_have


if __name__ == "__main__":
    unittest.main()
