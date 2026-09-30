"""Echo after the deep research of 1 October 2026.

The mean of the block's games leads and the best of them rides beside
it; E1 is a feasibility check and a span at the ceiling counts inside
its band; a block that played fewer games than it was set to is
flagged; the spare life is read by what it recovered and added, not
by how often it was spent; the replay is no longer set against first
attempts at the same lengths; the between-game agreement carries an
ICC with its interval; the fine series follows the longest correct
length; and the wrong presses are set against chance by where they
went.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOTEBOOK = (Path(__file__).resolve().parents[2] / "analysis"
            / "session_analysis.ipynb")


def _row(i, played, pressed, outcome, game_n=1, pos=0, pt="900", life=0,
         lives_left=1, block="g1", session="s1", hand_mode="right"):
    n_right = (max(0, len(pressed) - 1) if outcome == "wrong"
               else sum(1 for a, b in zip(played, pressed) if a == b))
    miss = {"correct": "none", "omission": "omission"}.get(
        outcome, "transposition")
    stim = (f"echo;len={len(played)};trial=1;run={game_n};hebb=0;"
            f"played={'-'.join(str(x) for x in played)};"
            f"pressed={'-'.join(str(x) for x in pressed)};"
            f"n_right={n_right};outcome={outcome};pt={pt};rule=simon;"
            f"game={game_n};seed=1;life={life};lives_left={lives_left};"
            f"pos={pos};miss={miss}")
    return dict(mode="echo", game=block, session=session, trial=i,
                stimulus=stim, error_type="", hand_mode=hand_mode,
                participant="P01",
                early_late="Great" if outcome == "correct" else "Miss",
                waveform_params=("game_seed=1;hebb=0;ioi_ms=800;"
                                 "pulse_ms=400;rule=simon;seq="
                                 + "-".join(str(x) for x in played)))


def _two_games(block="g1", session="s1"):
    """Game 1 reaches 4 with the life spent and recovered at 4; game 2
    reaches 2 and loses the replay at 3."""
    a = [0, 1, 2, 3, 0, 1]
    b = [3, 2, 1, 0, 3, 2]
    kw = dict(block=block, session=session)
    return [
        _row(1, a[:1], a[:1], "correct", 1, pt="800", **kw),
        _row(2, a[:2], a[:2], "correct", 1, pt="900-1400", **kw),
        _row(3, a[:3], a[:3], "correct", 1, pt="1000-1500-2000", **kw),
        _row(4, a[:4], [0, 1, 2, 1], "wrong", 1, pos=4,
             pt="1600-2100-2600-3100", **kw),
        _row(5, a[:4], a[:4], "correct", 1, life=1, lives_left=0,
             pt="1200-1700-2200-2700", **kw),
        _row(6, a[:5], [0, 2], "wrong", 1, pos=2, lives_left=0,
             pt="1800-2300", **kw),
        _row(7, b[:1], b[:1], "correct", 2, pt="700", **kw),
        _row(8, b[:2], b[:2], "correct", 2, pt="800-1300", **kw),
        _row(9, b[:3], [3, 2, 0], "wrong", 2, pos=3,
             pt="1500-2000-2500", **kw),
        _row(10, b[:3], [3, 2, 3], "wrong", 2, pos=3, life=1,
             lives_left=0, pt="1700-2200-2700", **kw),
    ]


def _block(rows, games=2):
    import pandas as pd
    return {"game": "g1", "folder": Path("."), "meta": {},
            "bs": {"echo": {"rule": "simon", "games": games}},
            "rows": pd.DataFrame(rows), "hand": "right",
            "calset": None, "extra": {}}


class EchoResearchNotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def _emitted(self, rows, games=2):
        return {m: (v, n) for _h, m, v, n
                in self.ra._cohort_echo(_block(rows, games))}

    def test_the_mean_of_the_games_is_the_headline(self):
        heads = [m for (md, m), s in self.ra.COHORT_METRICS.items()
                 if md == "echo" and s.get("headline")]
        self.assertEqual(heads, ["span_mean"])
        # E1 still reads the best of two, as registered.
        self.assertIn(("echo", "span"), self.ra.COHORT_METRICS)
        self.assertNotIn(("echo", "life_used_share"),
                         self.ra.COHORT_METRICS)
        for metric in ("total_items", "edit_score_mean",
                       "life_recovered_share", "life_gain_items",
                       "ftl_median_ms", "short_block"):
            self.assertIn(("echo", metric), self.ra.COHORT_DESCRIBE_ONLY)

    def test_the_block_reports_the_mean_best_and_life(self):
        em = self._emitted(_two_games())
        self.assertEqual(em["span_mean"][0], 3.0)
        self.assertEqual(em["span"][0], 4)
        self.assertEqual(em["games_played"][0], 2)
        self.assertEqual(em["short_block"][0], 0.0)
        # Both games spent the life; game 1's replay came back.
        self.assertEqual(em["life_recovered_share"][0], 0.5)
        # Game 1 scored 4 where a first-error stop would have scored 3;
        # game 2's failed replay added nothing.
        self.assertEqual(em["life_gain_items"][0], 0.5)
        self.assertNotIn("life_used_share", em)
        # Game medians of the first press: 1100 and 1150 ms.
        self.assertEqual(em["ftl_median_ms"][0], 1125.0)

    def test_a_one_game_block_is_flagged(self):
        em = self._emitted(_two_games()[:6], games=2)
        self.assertEqual(em["games_played"][0], 1)
        self.assertEqual(em["short_block"][0], 1.0)
        self.assertEqual(em["span_mean"][0], em["span"][0])

    def test_the_chapter_leads_with_the_mean_and_drops_the_old_comparison(
            self):
        import pandas as pd
        ra = self.ra
        rows = _two_games()
        ef = ra.echo_frame(pd.DataFrame(rows))
        stored = {"g1": {"rule": "simon", "games": 3, "span": 4,
                         "span_mean": 3.0, "total_items": 20,
                         "games_played": [{}, {}], "lives": 1,
                         "n_lanes": 4, "playback_presses": 2}}
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ra._sec_echo_simon(ef, stored)
        text = out.getvalue()
        self.assertIn("spans [4, 2], mean 3.0, best 4", text)
        self.assertNotIn("first attempts at the same lengths", text)
        self.assertIn("41 to 59", text)
        self.assertIn("added 0.5 item(s)", text)
        self.assertIn("SHORT BLOCK: g1 played 2 of 3", text)
        self.assertIn("presses during playback", text)
        self.assertIn("593 ms", text)
        self.assertNotIn("about 600 ms", text)

    def test_between_games_steps_the_icc_up_to_two_games(self):
        import numpy as np
        g1 = [3, 4, 5, 6, 7, 5]
        g2 = [4, 4, 6, 6, 8, 5]
        st = self.ra.echo_between_games(g1, g2)
        icc = st["icc21"]
        self.assertTrue(0 < icc < 1)
        self.assertAlmostEqual(st["sb_two"], 2 * icc / (1 + icc))
        self.assertAlmostEqual(st["shift"], float(np.mean(
            np.subtract(g2, g1))))
        self.assertIn("lo21", st)
        self.assertIn("shift_ci_lo", st)

    def test_the_fixed_split_pairs_each_persons_two_games(self):
        import pandas as pd
        ra = self.ra
        people = []
        for k, who in enumerate(("P01", "P02", "P03")):
            rows = pd.DataFrame(_two_games(block=f"g{k}",
                                           session=f"s{k}"))
            people.append((who, "right", rows))
        one_game = pd.DataFrame(_two_games(block="g9", session="s9")[:6])
        people.append(("P09", "right", one_game))
        g = ra.cohort_echo_game_pairs.__globals__
        before = g["_cohort_block_rows"]
        g["_cohort_block_rows"] = lambda cohort, mode: people
        try:
            pairs = ra.cohort_echo_game_pairs({}, ra.COHORT_POOLED_ROLE)
        finally:
            g["_cohort_block_rows"] = before
        self.assertEqual(pairs, {"P01": (4.0, 2.0), "P02": (4.0, 2.0),
                                 "P03": (4.0, 2.0)})
        self.assertIn(("echo", "span_mean"), ra.COHORT_FIXED_SPLITS)
        self.assertNotIn("span_mean", ra.COHORT_NO_SPLIT_REASON)

    def test_the_fine_series_is_the_longest_correct_length_per_game(self):
        import pandas as pd
        vals, better = self.ra.fine_series("echo",
                                           pd.DataFrame(_two_games()))
        self.assertEqual(vals, [1, 2, 3, 3, 4, 4, 1, 2, 2, 2])
        self.assertEqual(better, "higher")

    def test_wrong_presses_are_set_against_their_own_chance(self):
        import pandas as pd
        rows = [
            # right 3, pressed the finger just pressed: repeat.
            _row(1, [0, 1, 2, 3], [0, 1, 2, 2], "wrong", pos=4),
            # right 2, went back to the item two before: return.
            _row(2, [0, 1, 0, 2], [0, 1, 0, 1], "wrong", pos=4),
            # right 2, jumped to the next item: ahead.
            _row(3, [0, 1, 2, 3], [0, 1, 3], "wrong", pos=3),
            # An omission has no finger and is left out.
            _row(4, [0, 1, 2], [], "omission", pos=1),
        ]
        ef = self.ra.echo_frame(pd.DataFrame(rows))
        tbl = self.ra.echo_wrong_press_table(ef).set_index("relation")
        self.assertEqual(tbl["observed"].to_dict(),
                         {"repeat": 1, "return": 1, "ahead": 1,
                          "other": 0, "neighbour": 3})
        self.assertEqual(tbl["expected"].to_dict(),
                         {"repeat": 1.0, "return": 1.0, "ahead": 0.3,
                          "other": 0.7, "neighbour": 1.7})

    def test_e1_counts_a_span_at_the_ceiling_inside_the_band(self):
        import pandas as pd
        ra = self.ra
        seq = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1]
        rows = [_row(i + 1, seq[:i + 1], seq[:i + 1], "correct")
                for i in range(10)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            res = ra.sec_echo_checks(pd.DataFrame(rows))
        e1 = res["checks"].set_index("id").loc["E1"]
        self.assertIn("ceiling", str(e1["value"]))
        self.assertEqual(e1["verdict"], ra.lit_verdict(True))

    def test_the_wording_the_research_contradicted_is_gone(self):
        nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        src = "".join("".join(c["source"]) for c in nb["cells"])
        self.assertNotIn("motor- or fatigue-limited", src)
        self.assertNotIn("Gonthier 2022", src)
        self.assertNotIn("healthy-adult reference about 600 ms", src)
        self.assertIn("Chekaf, M., Gauvrit, N.", src)


class EchoGetReadyTests(unittest.TestCase):

    def test_the_card_says_the_rule_speed_and_guess(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from finger_rehab.ui.screens import GameplayScreen
        text = " ".join(GameplayScreen.GET_READY_LINES["echo"])
        for phrase in ("adds one more to the end", "Speed doesn't count",
                       "make your best guess"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
