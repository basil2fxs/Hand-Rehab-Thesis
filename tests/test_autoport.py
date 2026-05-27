"""Tests for auto-port discovery (Thread 4)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _FakePort:
    def __init__(self, device, vid, pid=0x0001, description=""):
        self.device = device
        self.vid = vid
        self.pid = pid
        self.description = description


class AutoPortTests(unittest.TestCase):
    def test_picks_single_arduino_match(self) -> None:
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.bluetooth", vid=0xABCD),
            _FakePort("/dev/cu.usbmodem1101", vid=0x2341, description="Arduino"),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_port(["0x2341"])
        self.assertEqual(picked, "/dev/cu.usbmodem1101")

    def test_returns_none_on_ambiguous_match(self) -> None:
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.a", vid=0x2341),
            _FakePort("/dev/cu.b", vid=0x2341),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_port(["0x2341"])
        self.assertIsNone(picked)

    def test_falls_back_to_only_port_when_no_vid_match(self) -> None:
        from rehab.hardware import serial_source
        ports = [_FakePort("/dev/cu.lonely", vid=0xDEAD)]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_port(["0x2341"])
        self.assertEqual(picked, "/dev/cu.lonely")

    def test_returns_none_when_no_ports_at_all(self) -> None:
        from rehab.hardware import serial_source
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = []
            picked = serial_source.discover_port(["0x2341"])
        self.assertIsNone(picked)

    def test_handles_bad_vid_string_in_config(self) -> None:
        from rehab.hardware import serial_source
        ports = [_FakePort("/dev/cu.ok", vid=0x2341)]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            # Bad string in the vid list shouldn't blow up the call.
            picked = serial_source.discover_port(["not_a_hex", "0x2341"])
        self.assertEqual(picked, "/dev/cu.ok")


class DiscoverPortsPluralTests(unittest.TestCase):
    """discover_ports (plural) is the one main.py actually uses for the
    MultiSerialSource bilateral case. Junk-port filter regression:
    /dev/cu.debug-console and /dev/cu.Bluetooth-Incoming-Port (Mac's
    always-present virtual serial ports) must never get auto-picked."""

    def test_skips_mac_junk_ports_even_with_no_vid_match(self) -> None:
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.debug-console", vid=None),
            _FakePort("/dev/cu.Bluetooth-Incoming-Port", vid=None),
            _FakePort("/dev/cu.Bluetooth-Outgoing-Port", vid=None),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_ports(["0x2341"])
        # No VID, all junk. Must return empty, not the junk ports.
        self.assertEqual(picked, [])

    def test_vid_matched_arduino_returned_even_alongside_junk(self) -> None:
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.debug-console", vid=None),
            _FakePort("/dev/cu.usbmodem1101", vid=0x2341),
            _FakePort("/dev/cu.Bluetooth-Incoming-Port", vid=None),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_ports(["0x2341"])
        self.assertEqual(picked, ["/dev/cu.usbmodem1101"])

    def test_two_arduinos_both_returned_for_bilateral(self) -> None:
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.usbmodemA", vid=0x2341),
            _FakePort("/dev/cu.usbmodemB", vid=0x2341),
            _FakePort("/dev/cu.debug-console", vid=None),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_ports(["0x2341"])
        self.assertEqual(picked, ["/dev/cu.usbmodemA", "/dev/cu.usbmodemB"])

    def test_unknown_vid_clone_picked_when_not_junk(self) -> None:
        # Unbranded Arduino clone with a VID that isn't on the
        # known-vendor list. Should still pick up via the "any real
        # USB device" pass.
        from rehab.hardware import serial_source
        ports = [
            _FakePort("/dev/cu.usbserial-CLONE", vid=0xBEEF),
            _FakePort("/dev/cu.Bluetooth-Incoming-Port", vid=None),
        ]
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = ports
            picked = serial_source.discover_ports(["0x2341"])
        self.assertEqual(picked, ["/dev/cu.usbserial-CLONE"])

    def test_empty_when_no_ports(self) -> None:
        from rehab.hardware import serial_source
        with patch.object(serial_source, "list_ports") as lp:
            lp.comports.return_value = []
            picked = serial_source.discover_ports(["0x2341"])
        self.assertEqual(picked, [])


class SerialLineParsingTests(unittest.TestCase):
    """SerialSource._consume parses 'FSR:v1,v2,v3,v4[,v5..v8]' lines into
    sample tuples. Garbage from EM interference / firmware drift must
    not crash the loop or push bogus samples."""

    def _make_source(self, num_sensors: int = 4):
        # SerialSource.__init__ calls _require_serial which raises if
        # pyserial is missing. We skip if so.
        try:
            from rehab.hardware.serial_source import SerialSource
        except RuntimeError:
            self.skipTest("pyserial not installed")
        # Construct without actually opening the port. _consume is a
        # pure-data method so we don't need a live serial handle.
        src = SerialSource.__new__(SerialSource)
        src.num_sensors = num_sensors
        src._q = __import__("queue").Queue(maxsize=4096)
        return src

    def _drain(self, src):
        import queue
        out = []
        while True:
            try:
                out.append(src._q.get_nowait())
            except queue.Empty:
                return out

    def test_valid_4_sensor_line_parses(self) -> None:
        src = self._make_source(4)
        buf = bytearray(b"FSR:10,20,30,40\n")
        src._consume(buf)
        samples = self._drain(src)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].values, (10, 20, 30, 40))

    def test_valid_8_sensor_line_parses(self) -> None:
        src = self._make_source(8)
        buf = bytearray(b"FSR:1,2,3,4,5,6,7,8\n")
        src._consume(buf)
        samples = self._drain(src)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0].values, (1, 2, 3, 4, 5, 6, 7, 8))

    def test_short_line_does_not_match_and_is_dropped(self) -> None:
        # The regex requires 4 mandatory groups. "FSR:1,2" has only 2.
        src = self._make_source(4)
        buf = bytearray(b"FSR:1,2\n")
        src._consume(buf)
        self.assertEqual(self._drain(src), [])

    def test_garbage_line_dropped_silently(self) -> None:
        src = self._make_source(4)
        buf = bytearray(b"\x01\x02\xff\xfe junk no newline yet")
        src._consume(buf)
        self.assertEqual(self._drain(src), [])
        # Buffer kept (still no newline).
        self.assertGreater(len(buf), 0)

    def test_oversize_buffer_garbage_protection(self) -> None:
        # If we accumulate > 4096 bytes with no newline, the front is
        # trimmed so we don't grow without bound.
        src = self._make_source(4)
        buf = bytearray(b"X" * 5000)
        src._consume(buf)
        self.assertLessEqual(len(buf), 4096)

    def test_two_lines_in_one_chunk(self) -> None:
        src = self._make_source(4)
        buf = bytearray(b"FSR:1,2,3,4\nFSR:5,6,7,8\n")
        src._consume(buf)
        samples = self._drain(src)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].values, (1, 2, 3, 4))
        self.assertEqual(samples[1].values, (5, 6, 7, 8))

    def test_partial_line_kept_in_buffer(self) -> None:
        src = self._make_source(4)
        buf = bytearray(b"FSR:1,2,3,")
        src._consume(buf)
        # No newline yet, nothing pushed, buffer preserved.
        self.assertEqual(self._drain(src), [])
        self.assertIn(b"FSR:1,2,3,", bytes(buf))


class SerialSendCommandTests(unittest.TestCase):
    def test_send_command_without_open_port_returns_false(self) -> None:
        try:
            from rehab.hardware.serial_source import SerialSource
        except RuntimeError:
            self.skipTest("pyserial not installed")
        src = SerialSource.__new__(SerialSource)
        src._serial = None
        self.assertFalse(src.send_command("STIM:1"))


if __name__ == "__main__":
    unittest.main()
