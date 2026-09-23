"""scripts/virtual_trigger_box.py stands in for the lab's MMBT-S box on
a Mac: a pseudo-terminal the game's own SerialBackend opens like any
serial port. Every byte has to arrive raw (a 10, a 13 or a 17 would be
turned into something else by a terminal line discipline), and the
comparison has to pair each logged marker with its byte in order and
call the session codes no block logs by name rather than a mismatch.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


@unittest.skipIf(os.name != "posix", "a pseudo-terminal needs POSIX")
class VirtualBoxTests(unittest.TestCase):

    def setUp(self) -> None:
        import virtual_trigger_box as vtb
        self.vtb = vtb
        self.box = vtb.VirtualBox().start()

    def tearDown(self) -> None:
        self.box.stop()

    def _send(self, codes) -> list[float]:
        from finger_rehab.hardware.eeg_trigger import SerialBackend
        b = SerialBackend(self.box.port, 9600)
        self.assertTrue(b.open(), b.last_error)
        sent = []
        for c in codes:
            self.assertTrue(b.write_code(c))
            sent.append(time.perf_counter())
            time.sleep(0.005)
        b.close()
        time.sleep(0.2)
        return sent

    def test_every_byte_arrives_raw(self) -> None:
        codes = [240, 10, 0, 13, 0, 17, 0, 19, 0, 200, 0, 255, 0, 241, 0]
        self._send(codes)
        self.assertEqual([b for _t, _w, b in self.box.bytes], codes)

    def test_markers_pair_in_order_and_session_codes_are_named(self):
        codes = [240, 0, 203, 0, 33, 0, 150, 0, 223, 0, 241, 0]
        sent = self._send(codes)
        markers = [{"t_wire": t, "code": c, "name": str(c), "block": "b1"}
                   for t, c in zip(sent, codes) if c not in (0, 240, 241)]
        rep = self.vtb.compare(self.box, markers)
        self.assertEqual(rep["matched"], 4)
        self.assertEqual(rep["missing"], [])
        self.assertEqual(rep["extra_codes"], [240, 241])
        self.assertEqual(rep["extra_outside_flow_band"], [])
        self.assertLess(abs(rep["lag_ms_median"]), 50.0)

    def test_a_marker_that_never_reached_the_box_is_reported(self) -> None:
        sent = self._send([33, 0])
        markers = [{"t_wire": sent[0], "code": 33, "name": "a",
                    "block": "b"},
                   {"t_wire": sent[0] + 0.1, "code": 36, "name": "b",
                    "block": "b"}]
        rep = self.vtb.compare(self.box, markers)
        self.assertEqual([m["code"] for m in rep["missing"]], [36])

    def test_no_game_played_is_not_called_a_mismatch(self) -> None:
        import contextlib
        import io
        rep = self.vtb.compare(self.box, [])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = self.vtb.print_report(rep)
        self.assertFalse(ok)
        self.assertIn("no game was played", buf.getvalue())
        self.assertNotIn("MISMATCH", buf.getvalue())

    def test_the_byte_log_is_written(self) -> None:
        import tempfile
        self._send([240, 0])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "eeg" / "box.csv"
            self.box.save(path)
            lines = path.read_text().splitlines()
        self.assertEqual(lines[0], "t_perf,wall_time,code,name")
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[1].endswith(",240,session_start"))


if __name__ == "__main__":
    unittest.main()
