"""scripts/latency_check.py drives the rig on the schedule it claims.

The bench procedure counts camera frames from the Nano's RX LED flash
to the pad moving, so the script must send exactly the pulses it says,
exactly when it says, and nothing else. Pinned here on a fake port and
a fake clock so the schedule is checked without a board or a wait.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]


def _load_script():
    path = REPO / "scripts" / "latency_check.py"
    spec = importlib.util.spec_from_file_location("latency_check", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeClock:
    def __init__(self) -> None:
        self.t = 100.0

    def now(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.t += max(0.0, float(s))


class _FakePort:
    def __init__(self, clock: _FakeClock) -> None:
        self.clock = clock
        self.writes: list[tuple[float, bytes]] = []

    def write(self, data: bytes) -> int:
        self.writes.append((self.clock.t, bytes(data)))
        return len(data)


class ScheduleTests(unittest.TestCase):

    def test_exactly_reps_stims_and_stops_at_the_requested_spacing(self):
        mod = _load_script()
        clock = _FakeClock()
        port = _FakePort(clock)
        rows = mod.run_pulses(port, reps=5, every_s=2.0, pulse_ms=300.0,
                              channel=3, clock=clock.now, sleep=clock.sleep)
        stims = [(t, d) for t, d in port.writes if d.startswith(b"STIM")]
        stops = [(t, d) for t, d in port.writes if d == b"STOP\n"]
        self.assertEqual(len(stims), 5)
        self.assertEqual(len(stops), 5)
        self.assertEqual(len(port.writes), 10, "nothing but STIM and STOP")
        self.assertTrue(all(d == b"STIM:3\n" for _t, d in stims))
        # Onsets 2 s apart, each STOP 300 ms after its STIM.
        onsets = [t for t, _d in stims]
        for a, b in zip(onsets, onsets[1:]):
            self.assertAlmostEqual(b - a, 2.0, places=9)
        for (ts, _s), (tp, _p) in zip(stims, stops):
            self.assertAlmostEqual(tp - ts, 0.300, places=9)
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]["rep"], 1)
        self.assertEqual(rows[-1]["achieved_pulse_ms"], "300.00")

    def test_tile_callbacks_run_before_the_matching_write(self) -> None:
        mod = _load_script()
        clock = _FakeClock()
        port = _FakePort(clock)
        events: list[str] = []
        port_write = port.write

        def write(data):
            events.append(data.decode().strip())
            return port_write(data)

        port.write = write
        mod.run_pulses(port, reps=2, every_s=1.0, pulse_ms=100.0,
                       channel=1, clock=clock.now, sleep=clock.sleep,
                       on_stim=lambda: events.append("tile on"),
                       on_stop=lambda: events.append("tile off"))
        self.assertEqual(events, ["tile on", "STIM:1", "tile off", "STOP",
                                  "tile on", "STIM:1", "tile off", "STOP"])

    def test_default_output_lives_in_calibration_never_sessions(self):
        mod = _load_script()
        out = mod.default_out_path(REPO)
        self.assertEqual(out.parent, REPO / "config" / "calibration")
        self.assertNotIn("sessions", out.parts)
        self.assertTrue(out.name.startswith("latency_check_"))
        self.assertTrue(out.name.endswith(".csv"))

    def test_docstring_carries_the_bench_procedure(self) -> None:
        mod = _load_script()
        doc = mod.__doc__ or ""
        for needle in ("240 fps", "piezo", "latency.buzzer_ms",
                       "latency.visual_ms", "--display"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
