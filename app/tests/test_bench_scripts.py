"""The two bench scripts run on real hardware, so what is pinned here
is their arithmetic, on signals with a known answer: the audio delay
found by lining a recording up with its source, sound onsets found in
a recording, and the pads' counts-per-gram line."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


class AudioLatencyMathTests(unittest.TestCase):

    def _signal(self, seconds=3.0, seed=4):
        import numpy as np
        rng = np.random.default_rng(seed)
        sr = 44100
        n = int(seconds * sr)
        sig = np.zeros(n, dtype=np.float32)
        # Percussive hits at irregular times, like a song's attacks.
        for t in rng.uniform(0.05, seconds - 0.1, 25):
            i = int(t * sr)
            k = np.arange(800)
            sig[i:i + 800] += (np.sin(2 * np.pi * 600 * k / sr)
                               * np.exp(-k / 150.0))
        return sig

    def test_a_known_delay_is_found_on_the_waveform_and_envelope(self):
        import numpy as np
        import audio_latency as al
        ref = self._signal()
        for delay_ms in (37.0, 118.0):
            d = int(delay_ms / 1000 * al.SR)
            rec = np.concatenate([np.zeros(d + 2000, np.float32), ref * 0.3,
                                  np.zeros(al.SR, np.float32)])
            rec += np.random.default_rng(1).normal(
                0, 0.002, len(rec)).astype(np.float32)
            t_rec0 = 100.0
            t_play = t_rec0 + 2000 / al.SR
            for env in (False, True):
                lag, strength = al._lag(rec, ref, t_rec0, t_play,
                                        envelope=env)
                self.assertAlmostEqual(lag, delay_ms, delta=1.5)
                self.assertGreater(strength, 6.0)

    def test_silence_is_not_a_measurement(self):
        import numpy as np
        import audio_latency as al
        ref = self._signal(1.0)
        lag, strength = al._lag(np.zeros(3 * al.SR, np.float32), ref, 0.0,
                                0.1)
        self.assertNotEqual(lag, lag)          # NaN
        self.assertEqual(strength, 0.0)

    def test_onsets_are_found_once_each(self):
        import numpy as np
        import audio_latency as al
        rec = np.random.default_rng(2).normal(
            0, 0.001, 3 * al.SR).astype(np.float32)
        for t in (0.5, 1.2, 2.1):
            i = int(t * al.SR)
            rec[i:i + 400] += 0.5
        got = al._mic_onsets(rec, 10.0)
        self.assertEqual(len(got), 3)
        for g, want in zip(got, (10.5, 11.2, 12.1)):
            self.assertAlmostEqual(g, want, delta=0.003)


class PadBenchMathTests(unittest.TestCase):

    def test_the_line_through_the_masses(self):
        import pad_bench as pb
        slope, icpt, r2 = pb._fit([0, 50, 100, 200],
                                  [250.0, 275.0, 300.5, 349.5])
        self.assertAlmostEqual(slope, 0.497, places=2)
        self.assertAlmostEqual(icpt, 250.1, places=0)
        self.assertGreater(r2, 0.999)

    def test_the_characterisation_goes_up_and_back_down(self):
        import pad_bench as pb
        self.assertEqual(pb.load_order([500, 100, 1000, 250]),
                         [("load", 0.0), ("load", 100), ("load", 250),
                          ("load", 500), ("load", 1000), ("unload", 500),
                          ("unload", 250), ("unload", 100),
                          ("unload", 0.0)])

    def _pad(self, per_n=51.2, rest=280.0, down_gap=0.0, bow=0.0):
        """A pad's readings on the characterisation's path: per_n counts
        per newton, down_gap counts higher on the way down, and bow
        counts added at 250 g on the way up."""
        import pad_bench as pb
        pts = []
        for phase, g in pb.load_order(pb.CHAR_MASSES_G):
            c = rest + per_n * pb.newtons(g)
            if phase == "unload":
                c += down_gap
            elif g == 250:
                c += bow
            pts.append((g, phase, c, 1.3 if g == 0 else 0.5))
        return pts

    def test_a_straight_pad_reads_its_slope_and_nothing_else(self):
        import pad_bench as pb
        fig = pb.characterise_pad(self._pad())
        self.assertAlmostEqual(fig["slope_counts_per_n"], 51.2, places=6)
        self.assertAlmostEqual(fig["full_scale_counts"], 512.0, places=4)
        self.assertAlmostEqual(fig["linearity_pct_fs"], 0.0, places=6)
        self.assertAlmostEqual(fig["hysteresis_pct_fs"], 0.0, places=6)
        self.assertEqual(fig["rest_sd_counts"], 1.3)

    def test_hysteresis_and_linearity_are_percent_of_full_scale(self):
        import pad_bench as pb
        # 5.12 counts high on the way down is 1 percent of 512.
        fig = pb.characterise_pad(self._pad(down_gap=5.12))
        self.assertAlmostEqual(fig["hysteresis_pct_fs"], 1.0, places=6)
        self.assertAlmostEqual(fig["linearity_pct_fs"], 0.0, places=6)
        bowed = pb.characterise_pad(self._pad(bow=10.24))
        self.assertGreater(bowed["linearity_pct_fs"], 1.0)
        self.assertLess(bowed["linearity_pct_fs"], 2.0)

    def test_a_pad_that_does_not_respond_has_no_figures(self):
        import pad_bench as pb
        self.assertIsNone(pb.characterise_pad(self._pad(per_n=0.0)))
        self.assertIsNone(pb.characterise_pad(self._pad()[:2]))

    def test_drift_is_percent_of_full_scale_from_the_first_window(self):
        import pad_bench as pb
        # 0.01 counts a second for ten minutes on a 512 count scale,
        # read every half second. The first window's mean is at 0.75 s,
        # the one ending at 60 s at 59 s, the one ending at 600 s at 599.
        held = [(t * 0.5, 300.0 + 0.01 * t * 0.5) for t in range(1201)]
        got = pb.drift_pct(held, 51.2, (60.0, 600.0))
        self.assertAlmostEqual(got[60.0], 100 * (0.59 - 0.0075) / 512,
                               places=9)
        self.assertAlmostEqual(got[600.0], 100 * (5.99 - 0.0075) / 512,
                               places=9)
        self.assertEqual(pb.drift_pct([], 51.2, (60.0,)), {})

    def test_a_whole_characterisation_on_a_fake_board(self):
        import csv
        import io
        import tempfile
        from contextlib import redirect_stdout
        from pathlib import Path
        from unittest import mock
        import pad_bench as pb

        class FakeBoard:
            """Answers each read with the load the last prompt asked
            for: 51.2 counts per newton over 280 on every pad."""
            def __init__(self):
                self.grams = 0.0

            def read(self, seconds):
                c = 280.0 + 51.2 * pb.newtons(self.grams)
                n = int(min(seconds, 3.0) * 200)
                step = seconds / max(n, 1)
                return [(i * step, [c + (i % 3 - 1) * 0.5] * 4)
                        for i in range(n)]

        board = FakeBoard()

        def answer(prompt):
            if "nothing on it" in prompt:
                board.grams = 0.0
            else:
                board.grams = float(prompt.split(" g")[0].split()[-1])
            return ""

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(pb, "APP", Path(tmp)), \
                mock.patch("builtins.input", side_effect=answer), \
                mock.patch.object(pb.time, "sleep"), \
                redirect_stdout(io.StringIO()) as out:
            code = pb.run_characterise(board, [100.0, 250.0, 500.0, 1000.0],
                                       500.0, 10.0, "calibrated")
            files = sorted(p.name for p in
                           (Path(tmp) / "config" / "calibration").iterdir())
            summary = next(p for p in
                           (Path(tmp) / "config" / "calibration").iterdir()
                           if p.name.endswith("_summary.csv"))
            rows = list(csv.DictReader(summary.open(encoding="utf-8")))
        self.assertEqual(code, 0)
        self.assertEqual(len(files), 2)
        self.assertTrue(all(f.startswith("pad_bench_calibrated_")
                            for f in files))
        slopes = [float(r["value"]) for r in rows
                  if r["measure"] == "slope_counts_per_n"]
        self.assertEqual(len(slopes), 4)
        for s in slopes:
            self.assertAlmostEqual(s, 51.2, places=2)
        self.assertIn("drift_1min_pct_fs", {r["measure"] for r in rows})
        self.assertIn("counts per N", out.getvalue())


if __name__ == "__main__":
    unittest.main()
