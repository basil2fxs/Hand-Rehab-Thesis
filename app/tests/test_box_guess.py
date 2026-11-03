"""The trigger box found without a person (3 November 2026).

The board scan took the laboratory's trigger box, an Arduino too, for a
hand board, so the box's port was set by hand. At launch the picker now
listens to the USB serial ports: a hand board sends its force stream
once it restarts, the box sends nothing, and when exactly one port stays
silent it is the box. Nothing is written to any port while listening.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.hardware import eeg_port  # noqa: E402


class _Port:
    def __init__(self, streams: bool) -> None:
        self.streams = streams
        self.written: list[bytes] = []

    def read(self, _n):
        time.sleep(0.01)
        return b"FSR: 265,270,268,290\n" if self.streams else b""

    def write(self, data):
        self.written.append(data)

    def close(self):
        pass


def _choice(dev: str, vid=0x1A86):
    return SimpleNamespace(device=dev, vid=vid)


class GuessTests(unittest.TestCase):
    def _open(self, table):
        return lambda dev: table[dev]

    def test_the_silent_port_is_the_box(self):
        ports = {"COM3": _Port(True), "COM10": _Port(False)}
        got = eeg_port.box_guess([_choice("COM3"), _choice("COM10")], listen_s=0.3,
                                 open_fn=self._open(ports))
        self.assertEqual(got, "COM10")
        self.assertTrue(all(p.written == [] for p in ports.values()))

    def test_two_boards_and_the_box(self):
        ports = {"COM3": _Port(True), "COM4": _Port(True), "COM10": _Port(False)}
        got = eeg_port.box_guess([_choice(d) for d in ports], listen_s=0.3,
                                 open_fn=self._open(ports))
        self.assertEqual(got, "COM10")

    def test_it_will_not_guess_when_it_cannot_tell(self):
        two_silent = {"COM3": _Port(False), "COM10": _Port(False)}
        self.assertIsNone(eeg_port.box_guess([_choice(d) for d in two_silent], listen_s=0.2,
                                             open_fn=self._open(two_silent)))
        one = {"COM10": _Port(False)}
        self.assertIsNone(eeg_port.box_guess([_choice("COM10")], listen_s=0.2,
                                             open_fn=self._open(one)))
        # a port with no USB identity is never a guess
        self.assertIsNone(eeg_port.box_guess([_choice("COM3"), _choice("/dev/ttyS0", vid=None)],
                                             listen_s=0.2, open_fn=self._open(
                                                 {"COM3": _Port(True), "/dev/ttyS0": _Port(False)})))


@unittest.skipUnless(hasattr(os, "openpty"), "pseudo-terminals")
class VirtualPortTests(unittest.TestCase):
    """Real serial opens, on two pseudo-terminals: one streams as a hand
    board does 0.4 s after it is opened, one is as silent as the box."""

    def test_the_virtual_box_is_found_among_virtual_ports(self):
        board_m, board_s = os.openpty()
        box_m, box_s = os.openpty()
        board, box = os.ttyname(board_s), os.ttyname(box_s)
        stop = threading.Event()

        # once the probe has closed the port nobody reads the board's
        # side, so its writes must not wait for room
        os.set_blocking(board_m, False)

        def stream():
            time.sleep(0.4)
            while not stop.is_set():
                try:
                    os.write(board_m, b"FSR: 265,270,268,290\r\n")
                except (BlockingIOError, OSError):
                    pass
                time.sleep(0.005)
        t = threading.Thread(target=stream, daemon=True)
        t.start()
        try:
            got = eeg_port.box_guess([_choice(board), _choice(box)], listen_s=1.5)
        finally:
            stop.set()
            t.join(1.0)
            for fd in (board_m, board_s, box_m, box_s):
                os.close(fd)
        self.assertEqual(got, box)
