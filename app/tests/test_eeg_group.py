"""The two-session EEG statistics (analysis/eeg/group.py): each person's
own difference between two conditions, averaged over people, tested by
shuffling the condition labels within each person only. Plain numpy, so
it runs here without MNE."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(ANALYSIS))

from eeg.group import group, holm, rt_matched, stratified_perm  # noqa: E402


class StratifiedPermTests(unittest.TestCase):

    def test_a_shared_shift_is_found_and_its_size_kept(self):
        rng = np.random.default_rng(1)
        people = [(rng.normal(-2.0, 3.0, 60), rng.normal(0.0, 3.0, 200)),
                  (rng.normal(-2.0, 3.0, 40), rng.normal(0.0, 3.0, 150))]
        r = stratified_perm(people, n=2000, seed=3)
        self.assertLess(r["p"], 0.01)
        self.assertAlmostEqual(r["diff"], np.mean([a.mean() - b.mean() for a, b in people]))
        self.assertEqual(r["per_person"], [a.mean() - b.mean() for a, b in people])

    def test_no_shift_is_not_called_an_effect(self):
        rng = np.random.default_rng(2)
        people = [(rng.normal(0, 3, 60), rng.normal(0, 3, 200)),
                  (rng.normal(0, 3, 40), rng.normal(0, 3, 150))]
        self.assertGreater(stratified_perm(people, n=2000, seed=3)["p"], 0.05)

    def test_labels_never_cross_between_people(self):
        # One person far above the other: a pooled shuffle would mix the
        # two levels and call it an effect, a within-person shuffle does not.
        rng = np.random.default_rng(4)
        people = [(rng.normal(50, 1, 30), rng.normal(50, 1, 30)),
                  (rng.normal(0, 1, 30), rng.normal(0, 1, 30))]
        self.assertGreater(stratified_perm(people, n=2000, seed=5)["p"], 0.05)


class GroupTests(unittest.TestCase):

    def test_the_time_check_is_reported_but_kept_out_of_holm(self):
        # The P3 against the random post-test asks whether a practice-to-late
        # drop is time on the task; it is a check, so Holm stays on the two
        # planned tests and their adjusted p values do not move.
        rng = np.random.default_rng(6)
        conds = ("random_practice", "sequence_early", "sequence_late", "random_posttest")
        person = {c: {k: rng.normal(0, 3, 60) for k in conds} for c in ("N2", "P3", "beta")}
        out = group([person, person])
        check = "P3: random_posttest vs sequence_late"
        self.assertIn(check, out)
        self.assertNotIn("p_holm", out[check])
        planned = ["N2: random_posttest vs sequence_late", "P3: random_practice vs sequence_late"]
        self.assertEqual([out[k]["p_holm"] for k in planned], holm([out[k]["p"] for k in planned]))


class RtMatchTests(unittest.TestCase):

    def test_each_trial_gets_its_nearest_unused_partner(self):
        # Random trials are slower than learned ones; the match picks, for
        # every random trial, a different learned trial of about the same RT.
        rng = np.random.default_rng(8)
        slow = rng.normal(360, 40, 30)
        fast = rng.normal(300, 60, 140)
        idx = rt_matched(slow, fast)
        self.assertEqual(len(idx), len(slow))
        self.assertEqual(len(set(idx.tolist())), len(idx))
        self.assertLess(abs(np.median(fast[idx]) - np.median(slow)), 8)
        self.assertGreater(np.median(slow) - np.median(fast), 40)

    def test_too_few_partners_is_refused(self):
        with self.assertRaises(ValueError):
            rt_matched(np.arange(10.0), np.arange(5.0))


class HolmTests(unittest.TestCase):

    def test_holm_steps_down_and_stays_monotone(self):
        self.assertEqual([round(p, 3) for p in holm([0.02, 0.01, 0.04])], [0.04, 0.03, 0.04])
        self.assertEqual(holm([0.6, 0.01]), [0.6, 0.02])


if __name__ == "__main__":
    unittest.main()
