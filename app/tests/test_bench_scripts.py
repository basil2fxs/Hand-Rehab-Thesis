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


if __name__ == "__main__":
    unittest.main()
