"""The EEG analysis's pairing of a recording with the game's marker log
(analysis/eeg/align.py): plain numpy and pandas, so it runs here
without MNE. A simulated block: the game writes bytes on its own
clock, the amplifier samples them at 512 Hz on a clock that runs 40
parts per million slow and starts 12 s later."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(ANALYSIS))

from eeg.align import align, shifted_samples, wire_rows  # noqa: E402

SF = 512.0


def _game(n=300, seed=1):
    rng = np.random.default_rng(seed)
    codes = np.where(np.arange(n) % 2 == 0, 30, 100 + rng.integers(0, 4, n))
    t_wire = 1000.0 + np.cumsum(rng.uniform(0.3, 0.6, n))
    return pd.DataFrame({
        "onset": t_wire - 1000.0, "value": codes, "t_event": t_wire - 0.0001,
        "t_wire": t_wire, "failed": 0, "dropped": 0,
        "press_offset_ms": np.where(codes >= 100, -7.0, np.nan),
        "onset_offset_ms": np.where(codes >= 100, -50.0, np.nan),
        "trial_type": ["x"] * n, "lane": np.nan})


def _eeg(game, slope=1 - 40e-6, start=12.0):
    t = start + slope * (game.t_wire.to_numpy() - game.t_wire.iloc[0])
    return np.round(t * SF), game.value.to_numpy()


class AlignTests(unittest.TestCase):

    def test_pairs_every_byte_and_recovers_the_clocks(self):
        g = wire_rows(_game())
        s, c = _eeg(g)
        a = align(s, c, SF, g)
        self.assertTrue(a.codes_agree)
        self.assertEqual(a.matched, len(g))
        self.assertAlmostEqual(a.drift_ppm, -40.0, delta=2.0)
        # Rounding to a 512 Hz sample is the only scatter, so every
        # marker lands within one sample of the fitted line.
        self.assertLessEqual(np.abs(a.residual_ms).max(), 1000 / SF)

    def test_a_lost_byte_is_reported_not_repaired(self):
        g = wire_rows(_game())
        s, c = _eeg(g)
        a = align(np.delete(s, 50), np.delete(c, 50), SF, g)
        self.assertFalse(a.codes_agree)
        self.assertLess(a.matched, len(g))

    def test_failed_and_dropped_rows_never_reached_the_wire(self):
        g = _game()
        g.loc[5, "failed"] = 1
        g.loc[9, "dropped"] = 1
        w = wire_rows(g)
        self.assertEqual(len(w), len(g) - 2)
        self.assertNotIn(g.t_wire[5], w.t_wire.to_numpy())

    def test_rows_come_in_wire_order(self):
        g = _game()
        g.loc[[3, 4], "t_wire"] = g.loc[[4, 3], "t_wire"].to_numpy()
        w = wire_rows(g)
        self.assertTrue(np.all(np.diff(w.t_wire.to_numpy()) > 0))

    def test_game_times_map_into_the_recording(self):
        g = wire_rows(_game())
        s, c = _eeg(g)
        a = align(s, c, SF, g)
        t = g.t_wire.iloc[100] + 0.25
        want = 12.0 + (1 - 40e-6) * (t - g.t_wire.iloc[0])
        self.assertAlmostEqual(float(a.to_eeg_seconds(t)), want, delta=0.002)

    def test_offsets_move_a_response_byte_back(self):
        g = wire_rows(_game())
        s, c = _eeg(g)
        a = align(s, c, SF, g)
        press = shifted_samples(a.pairs, SF, "press_offset_ms")
        onset = shifted_samples(a.pairs, SF, "onset_offset_ms")
        r = np.flatnonzero(a.pairs.code_eeg.to_numpy() >= 100)
        k = np.flatnonzero(a.pairs.code_eeg.to_numpy() == 30)
        self.assertTrue(np.isnan(press[k]).all())
        lag = (a.pairs.eeg_s.to_numpy()[r] * SF - onset[r]) / SF * 1000
        self.assertTrue(np.allclose(lag, 50.0, atol=1000 / SF))


if __name__ == "__main__":
    unittest.main()
