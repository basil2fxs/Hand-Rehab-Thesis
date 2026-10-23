"""The laboratory's sequence task scored across players
(analysis/sequence_task.py): the laboratory's trial rule, the reversal
trials and the learning score. Plain pandas, so it runs without MNE."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(ANALYSIS))

from sequence_task import (errors, lab_kept, learning, lower_bound, mixed,  # noqa: E402
                           prediction, random_blocks, reversal)


def block(phase, number, lanes, rts, accuracy=None):
    n = len(lanes)
    return pd.DataFrame({"phase": phase, "block": number, "trial": range(1, n + 1),
                         "target_lane": list(lanes), "rt_ms": rts,
                         "accuracy": accuracy or ["correct"] * n})


class LabRuleTests(unittest.TestCase):

    def test_first_trial_wrong_and_slow_presses_are_left_out(self):
        t = pd.concat([block("practice", 1, "vbnm", [400, 300, 1200, 310],
                             ["correct", "correct", "correct", "incorrect"]),
                       block("learning", 1, "vbnm", [400, 250, 260, 999])], ignore_index=True)
        self.assertEqual(lab_kept(t).tolist(), [False, True, False, False, False, True, True, True])

    def test_reversals_are_a_b_a_inside_one_block(self):
        # v b v is a reversal; the first two trials of the next block have no
        # trial two back in their own block, whatever came before them.
        t = pd.concat([block("practice", 1, "vbvn", [300] * 4),
                       block("learning", 1, "vnv", [300] * 3)], ignore_index=True)
        self.assertEqual(reversal(t).tolist(), [False, False, True, False, False, False, True])

    def test_learning_score_is_post_test_minus_block_8(self):
        t = pd.concat([block("learning", 1, "vbnm", [0, 300, 300, 300]),
                       block("learning", 8, "vbnm", [0, 200, 210, 220]),
                       block("practice", 1, "vbnm", [0, 330, 340, 350]),
                       block("posttest", 1, "vbnm", [0, 290, 300, 310])], ignore_index=True)
        out = learning(t, lab_kept(t), np.random.default_rng(1))
        self.assertAlmostEqual(out["post_minus_block8_ms"], 300 - 210)
        self.assertEqual((out["block1_ms"], out["block8_ms"], out["post_ms"], out["practice_ms"]),
                         (300, 210, 300, 340))
        lo, hi = out["post_minus_block8_ci"]
        self.assertLessEqual(lo, 90)
        self.assertGreaterEqual(hi, 90)


class BoundTests(unittest.TestCase):

    PEOPLE = {"A": {"learning": {"practice_ms": 300, "post_ms": 280, "block8_ms": 200,
                                 "post_minus_block8_ci": [50, 110]}},
              "B": {"learning": {"practice_ms": 310, "post_ms": 360, "block8_ms": 260,
                                 "post_minus_block8_ci": [40, 160]}}}

    def test_the_lower_bound_takes_the_faster_random_block(self):
        out = lower_bound(self.PEOPLE)
        self.assertEqual(out["per_person"], {"A": 80, "B": 50})
        self.assertEqual(out["positive"], 2)

    def test_the_random_blocks_agree_as_a_repeat(self):
        out = random_blocks(self.PEOPLE)
        self.assertEqual(out["per_person"], {"A": -20.0, "B": 50.0})
        self.assertAlmostEqual(out["mean_ms"], 15.0)
        self.assertEqual(out["ci_halfwidths_ms"], [30.0, 60.0])


class EarlyPressTests(unittest.TestCase):

    def test_early_presses_are_scored_by_the_finger_they_chose(self):
        # Two sequence presses come too early to answer the flash, one on
        # the right finger and one before the flash on the wrong one.
        seq = block("learning", 1, "vbnm", [0, 40, -50, 300],
                    ["correct", "correct", "anticipatory_incorrect", "correct"])
        rnd = block("posttest", 1, "vbnm", [0, 300, 310, 320])
        out = prediction(pd.concat([seq, rnd], ignore_index=True))
        self.assertEqual((out["sequence"]["early"], out["sequence"]["right"]), (2, 1))
        self.assertEqual(out["random"]["early"], 0)
        self.assertIsNone(out["random"]["p_vs_chance"])

    def test_errors_are_read_on_answered_trials(self):
        t = pd.concat([block("practice", 1, "vbnmv", [0, 300, 300, 300, 300],
                             ["correct", "correct", "incorrect", "correct", "miss"]),
                       block("learning", 8, "vbnm", [0, 200, 200, 200]),
                       block("posttest", 1, "vbnm", [0, 300, 300, 300],
                             ["correct", "incorrect", "anticipatory_incorrect", "correct"])], ignore_index=True)
        out = errors(t)
        self.assertAlmostEqual(out["Practice"], 1 / 3)
        self.assertEqual(out["Sequence 8"], 0.0)
        self.assertAlmostEqual(out["Post-test"], 2 / 3)


class MixedModelTests(unittest.TestCase):

    def test_the_model_finds_a_shared_slowing_and_speed_up(self):
        # Four players at their own speed, each 2 ms faster per sequence
        # block and 60 ms slower in the post-test than in block 8.
        rng = np.random.default_rng(3)
        tables = []
        for base in (250, 300, 280, 330):
            parts = [block("practice", 1, "v" * 40, list(base + 30 + rng.normal(0, 20, 40)))]
            for b in range(1, 9):
                parts.append(block("learning", b, "v" * 40, list(base - 2 * b + rng.normal(0, 20, 40))))
            parts.append(block("posttest", 1, "v" * 40, list(base - 16 + 60 + rng.normal(0, 20, 40))))
            t = pd.concat(parts, ignore_index=True)
            tables.append(t[lab_kept(t)])
        out = mixed(tables)
        self.assertAlmostEqual(out["post_minus_block8"]["estimate"], 60, delta=8)
        self.assertLess(out["post_minus_block8"]["p"], 0.001)
        self.assertAlmostEqual(out["slope_per_block"]["estimate"], -2, delta=1.5)
        m = out["emmeans"]["Post-test"]
        self.assertLess(m["lower"], m["estimate"])
        self.assertLess(m["estimate"], m["upper"])
        self.assertAlmostEqual(m["estimate"], out["means"]["Post-test"])


if __name__ == "__main__":
    unittest.main()


class ChanceRecallTests(unittest.TestCase):
    def test_random_recalls_never_repeat_a_key_and_use_all_four(self):
        import numpy as np
        import sequence_task as st
        d = st.chance_recalls(np.random.default_rng(1), 2000, 10)
        self.assertEqual(d.shape, (2000, 10))
        self.assertFalse((d[:, 1:] == d[:, :-1]).any())
        self.assertEqual(set(np.unique(d)), {1, 2, 3, 4})
        # each of the three other keys follows a key about equally often
        after = [d[:, 1:][d[:, :-1] == 1].tolist().count(k) for k in (2, 3, 4)]
        self.assertLess(max(after) - min(after), 0.1 * sum(after))

