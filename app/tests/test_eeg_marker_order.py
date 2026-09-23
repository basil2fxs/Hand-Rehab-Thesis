"""A block must open on the recording before anything inside it.

Welber segments a BioSemi recording by block: from a 200-something byte
to its matching 220-something. The engine sends a block start and its
GET READY in the same frame, and markers that land within one pulse
plus gap of each other queue by priority. When block starts sat at the
bottom of that priority list, the queue put GET READY ahead of them,
so every block opened with a 20 lying just outside the block it
belonged to. These tests pin the order on the wire, which is what the
amplifier records and the only order that matters to the lab.

Compared against Welber's own demo (archive/Webler EEG past program),
which opened COM10 at 9600 8N1, wrote one raw byte right after the
flip, held it, then wrote 0. The byte and reset tests below pin that
contract for every code, not just his 30.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.hardware.eeg_trigger import (  # noqa: E402
    CODES, MarkerWriter, TriggerBackend, block_code, priority_for)


class _Clock:
    """A clock the test moves by hand, so collisions are deliberate."""

    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


class _Wire(TriggerBackend):
    """Records exactly what would reach the trigger box."""

    def __init__(self) -> None:
        self.bytes: list[bytes] = []

    def open(self) -> bool:
        return True

    def is_open(self) -> bool:
        return True

    def write_code(self, code: int) -> bool:
        self.bytes.append(bytes([code]))
        return True

    def close(self) -> None:
        pass


def _writer():
    clock, wire = _Clock(), _Wire()
    w = MarkerWriter(backend=wire, enabled=True, pulse_ms=8, gap_ms=12,
                     clock=clock, max_queue=16)
    return w, clock, wire


def _drain(w, clock, steps=200):
    for _ in range(steps):
        clock.t += 0.001
        w.tick()


def _codes(wire):
    """Every non-zero byte, in wire order."""
    return [b[0] for b in wire.bytes if b != b"\x00"]


class OpenersGoFirstTests(unittest.TestCase):

    def test_session_and_block_starts_outrank_everything(self):
        for opener in (CODES["session_start"], block_code("reaction", "start"),
                       block_code("echo", "start")):
            with self.subTest(opener=opener):
                self.assertLess(priority_for(opener), priority_for(33))
                self.assertLess(priority_for(opener), priority_for(20))
                self.assertLess(priority_for(opener), priority_for(101))

    def test_a_block_start_is_not_overtaken_by_its_own_get_ready(self):
        # Exactly what the engine does: block start, then GET READY,
        # in the same frame.
        w, clock, wire = _writer()
        w.send(CODES["session_start"])
        w.send(block_code("pattern", "start"))
        w.send(CODES["prep_countdown"])
        _drain(w, clock)
        self.assertEqual(_codes(wire),
                         [240, block_code("pattern", "start"), 20])

    def test_nothing_inside_a_block_reaches_the_wire_before_it(self):
        # The worst case: a stimulus and a response requested in the
        # same instant as the block start. The block must still open
        # first, or the lab assigns those events to no block at all.
        w, clock, wire = _writer()
        start = block_code("adaptive", "start")
        w.send(CODES["session_start"])
        w.send(start)
        w.send(33)
        w.send(101)
        w.send(CODES["prep_countdown"])
        _drain(w, clock)
        order = _codes(wire)
        self.assertEqual(order[:2], [240, start])
        for inside in (33, 101, 20):
            self.assertGreater(order.index(inside), order.index(start))

    def test_closing_a_block_still_waits_for_what_is_inside(self):
        # Openers moved up; closers did not. A block end requested
        # alongside a late stimulus must not jump it.
        w, clock, wire = _writer()
        end = block_code("chords", "end")
        w.send(33)
        w.send(end)
        _drain(w, clock)
        order = _codes(wire)
        self.assertLess(order.index(33), order.index(end))


class DemoContractTests(unittest.TestCase):
    """What Welber's demo did on the wire, held for every code."""

    def test_every_code_is_one_raw_byte(self):
        # The demo wrote bytes(chr(30), 'UTF-8'). For any code over 127
        # that idiom sends TWO bytes and the box raises the wrong lines.
        # Ours writes bytes([code]) for all of them.
        for code in sorted(set(CODES.values())):
            if code == 0:
                continue
            with self.subTest(code=code):
                w, clock, wire = _writer()
                w.send(code)
                _drain(w, clock)
                self.assertEqual(wire.bytes[0], bytes([code]))
                self.assertEqual(len(wire.bytes[0]), 1)

    def test_every_pulse_is_followed_by_a_zero(self):
        # The demo held its 30 then wrote 0 to drop the lines. Without
        # the 0 a box in Simple Mode holds the code until the next one.
        w, clock, wire = _writer()
        for code in (240, 200, 20, 33, 101, 140, 220, 241):
            w.send(code)
            _drain(w, clock, steps=40)
        highs = [b for b in wire.bytes if b != b"\x00"]
        zeros = [b for b in wire.bytes if b == b"\x00"]
        self.assertEqual(len(highs), 8)
        self.assertGreaterEqual(len(zeros), len(highs))

    def test_the_visual_onset_code_is_the_demos_30(self):
        # The demo's MARKER_FLASH_ONSET. Ours means the same thing:
        # visual onset. With a tone and a buzz as well the code rises
        # by 1 and 2, so the lab config sends 33, not 30.
        self.assertEqual(CODES["stim_visual"], 30)


class NothingThatOpensIsDroppedTests(unittest.TestCase):

    def test_a_burst_never_drops_the_session_start(self):
        # The old priority made 240 the lowest-value byte, so a queue
        # overflow threw away the very marker the session is cut from.
        dropped = []
        clock, wire = _Clock(), _Wire()
        w = MarkerWriter(backend=wire, enabled=True, pulse_ms=8, gap_ms=12,
                         clock=clock, max_queue=3,
                         on_emit=lambda e: dropped.append(e.code)
                         if e.dropped else None)
        w.send(30)
        for code in (100, 101, 102, CODES["session_start"]):
            w.send(code)
        self.assertNotIn(CODES["session_start"], dropped)
        self.assertNotIn(block_code("reaction", "start"), dropped)


if __name__ == "__main__":
    unittest.main()
