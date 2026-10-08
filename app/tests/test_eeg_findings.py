"""The EEG results page's headlines (analysis/eeg/findings.py): an
effect is claimed only when its primary test passes, the N2 and P3 are
Holm-corrected as a pair, and nothing about one session is written
into the code. Plain Python, so it runs here without MNE."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(ANALYSIS))

from eeg.findings import (ERN_TEST, N2_TEST, P3_TEST, TOUCH_TEST, build,  # noqa: E402
                          holm)

BASE = {
    "participant": "P07",
    "srt_look": "lab",
    "markers_total": 900, "markers_matched": 900,
    "recordings": [
        {"mode": "srt", "sfreq": 512.0, "codes_agree": True, "residual_sd_ms": 0.56,
         "residual_max_ms": 1.0, "drift_ppm": -40.0, "bads": [], "bad_reasons": {},
         "unconnected": []},
    ],
    "srt": {
        "learning": {"post_minus_block8_ms": 60.0, "post_minus_block8_ci": [30.0, 90.0],
                     "block1_ms": 260.0, "block8_ms": 210.0, "post_ms": 270.0},
        "recall": {"items": 10, "correct": 4, "cyclic_correct": 5, "cyclic_start": 2,
                   "chance_p": 0.6, "recalled": "V-B-N-M-V-B-N-M-V-B",
                   "actual": "V-N-B-V-M-N-B-M-V-N"},
        "behaviour": [{"segment": "Practice", "n": 48, "anticipations": 0.0},
                      {"segment": "Sequence 1", "n": 100, "anticipations": 0.0},
                      {"segment": "Sequence 8", "n": 100, "anticipations": 0.1},
                      {"segment": "Post-test", "n": 48, "anticipations": 0.0}],
        "stim_tests": {N2_TEST: {"diff": -4.0, "p": 0.01}, P3_TEST: {"diff": 2.0, "p": 0.02}},
        "band_tests": {"beta C3": {"diff": 1.0, "p": 0.001},
                       "alpha C3": {"diff": 0.5, "p": 0.2},
                       "theta FCz/Cz": {"diff": 0.1, "p": 0.7}},
        "block_power": [{"segment": "Practice", "beta_C3_dB": -5.0},
                        {"segment": "Sequence 1", "beta_C3_dB": -6.0},
                        {"segment": "Post-test", "beta_C3_dB": -5.2}],
        "resp_tests": {ERN_TEST: {"diff": -2.0, "p": 0.01}},
        "resp_n": {"error": 40, "correct": 600},
        "ern_clusters": [],
        "rerp": {},
    },
    "buzz": {
        "measures": [{"measure": "N1 contra", "mean_uV": -3.0, "sme_uV": 0.8},
                     {"measure": "N1 ipsi", "mean_uV": -1.0, "sme_uV": 0.9},
                     {"measure": "P3", "mean_uV": 6.0, "sme_uV": 1.2}],
        "tests": {TOUCH_TEST: {"diff": -2.0, "p": 0.01, "n": 32}},
    },
}


def _with(**changes) -> dict:
    s = copy.deepcopy(BASE)
    for path, value in changes.items():
        keys = path.split("__")
        d = s
        for k in keys[:-1]:
            d = d[k]
        d[keys[-1]] = value
    return s


def _heads(s) -> list[str]:
    return [i["head"] for i in build(s)["items"]]


class HolmTests(unittest.TestCase):

    def test_adjusts_in_the_order_given(self):
        out = holm([0.01, 0.04, 0.03])
        for got, want in zip(out, [0.03, 0.06, 0.06]):
            self.assertAlmostEqual(got, want)

    def test_a_missing_test_stays_missing(self):
        self.assertEqual(holm([None, 0.02]), [None, 0.02])


class FindingsTests(unittest.TestCase):

    def test_a_passing_error_test_is_claimed(self):
        self.assertIn("Wrong presses carried an error signal.", _heads(BASE))

    def test_a_failing_error_test_is_never_claimed(self):
        s = _with(srt__resp_tests={ERN_TEST: {"diff": -1.2, "p": 0.072}})
        heads = _heads(s)
        self.assertNotIn("Wrong presses carried an error signal.", heads)
        self.assertIn("The error signal points the right way but is not yet reliable.", heads)
        self.assertIn("not yet reliable", build(s)["plain"])

    def test_the_n2_must_survive_holm_across_the_pair(self):
        # p .04 passes alone but is .08 once the P3 shares the question
        s = _with(srt__stim_tests={N2_TEST: {"diff": -3.0, "p": 0.04},
                                   P3_TEST: {"diff": 0.5, "p": 0.30}})
        self.assertIn("The flash response did not reliably separate learned from random order.",
                      _heads(s))

    def test_an_effect_the_wrong_way_is_not_claimed(self):
        s = _with(srt__band_tests={"beta C3": {"diff": -1.0, "p": 0.001}})
        self.assertIn("Motor-cortex beta did not reliably separate random from learned trials.",
                      _heads(s))

    def test_learning_needs_the_interval_above_zero(self):
        s = _with(srt__learning__post_minus_block8_ci=[-10.0, 50.0])
        self.assertIn("The reaction times show no clear sequence learning.", _heads(s))

    def test_a_guessable_recall_is_not_called_explicit(self):
        fd = build(BASE)
        self.assertIn("P07 learned the sequence, without being able to recall it.", _heads(BASE))
        self.assertIn("does not show explicit knowledge", fd["notes"]["recall"])

    def test_a_whole_recall_is(self):
        s = _with(srt__recall__cyclic_correct=10, srt__recall__chance_p=0.0001)
        self.assertIn("P07 learned the sequence, and recalled all of it.", _heads(s))

    def test_the_touch_response_needs_its_test(self):
        s = _with(buzz__tests={TOUCH_TEST: {"diff": -2.1, "p": 0.148, "n": 32}})
        self.assertIn("The buzz drew a clear P3; the left-right touch response is not yet reliable.",
                      _heads(s))
        self.assertIn("does not pass its test", build(s)["notes"]["touch_caveat"])

    def test_lost_markers_are_flagged(self):
        s = _with(markers_matched=899)
        self.assertIn("Some markers did not line up.", _heads(s))

    def test_the_name_comes_from_the_session(self):
        text = " ".join(i["head"] + i["text"] for i in build(BASE)["items"])
        self.assertIn("P07", text)

    def test_rebuilt_channels_are_listed_with_their_side(self):
        s = _with(recordings=[dict(BASE["recordings"][0], bads=["C4", "FC6"],
                                   bad_reasons={"C4": "unlike its neighbours (r 0.20)",
                                                "FC6": "unlike its neighbours (r 0.30)"})])
        q = build(s)["notes"]["quality"]
        self.assertIn("SRT: C4, FC6", q)
        self.assertIn("all on the right side", q)

    def test_the_display_note_follows_the_look(self):
        self.assertNotIn("game's own Reaction look", build(BASE)["notes"]["display"])
        s = _with(srt_look="app")
        self.assertIn("game's own Reaction look", build(s)["notes"]["display"])


if __name__ == "__main__":
    unittest.main()
