"""Smaller faults from the 27 September 2026 code review, outside the
modes that have their own review file."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class ClassicPauseTests(unittest.TestCase):

    def test_a_pause_shifts_the_wrong_presses_with_the_stim(self) -> None:
        # Shifting only the stim made first_incorrect_ms shrink by the
        # pause and go negative after a long one.
        from finger_rehab.game.modes.classic import ClassicMode
        from finger_rehab.game.scoring import ScoreConfig
        engine = MagicMock()
        mode = ClassicMode(engine, pattern=[0, 1, 2, 3], repeat_count=1,
                           trigger_interval_s=1.0, timeout_s=1.0,
                           early_window_s=0.1, score_cfg=ScoreConfig())
        mode._fire(10.0)
        mode.active.incorrect_presses.append((2, 10.3))
        mode.on_resume(20.0)
        self.assertAlmostEqual(mode.active.stim_t_perf, 30.0)
        lane, t = mode.active.incorrect_presses[0]
        self.assertEqual(lane, 2)
        self.assertAlmostEqual(t - mode.active.stim_t_perf, 0.3)


if __name__ == "__main__":
    unittest.main()
