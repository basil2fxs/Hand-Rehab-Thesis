"""Echo faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: a silent turn while the board was away spent the spare
life, could end the game and counted as an omission; the press
offsets on the row went negative across a pause and inside the frame
after a fast reply; the gold Longest echo chip was drawn under the
laboratory's neutral style; the prior-game count compared the raw
name while the seed normalised it; and the feedback byte left at the
close under a feedback delay that draws nothing for an echo trial.

Notebook side: the frame counted rows the rig had voided; the offset
parser read a minus sign as a separator; E2p was decided by two
criteria in two tables; the per-selection E1 band and E3 verdict did
not know the one-board rig; and the run compression counted
ascending runs only.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_echo_mode import (_Pump, _make_wire_engine, _press,  # noqa: E402
                                  _simon_mode, _simon_play, patched_clock,
                                  setUpModule, tearDownModule)

__all__ = ["setUpModule", "tearDownModule"]


def _until(mode, clock, pred, step_s: float = 0.05,
           max_steps: int = 4000, responder=None) -> None:
    for _ in range(max_steps):
        if pred():
            return
        clock.t += step_s
        mode.update(step_s)
        if responder is not None:
            responder(clock)
    raise AssertionError("condition never met")


class DropVoidTests(unittest.TestCase):

    def test_a_silent_turn_during_a_drop_is_replayed_not_scored(self):
        eng, mode = _simon_mode(max_len=3)
        eng._drop_overlaps = lambda hand, t_from, t_to: True
        with patched_clock() as clock:
            _until(mode, clock, lambda: mode.phase == "respond")
            first = list(mode.sequence)
            _until(mode, clock, lambda: len(mode._records) >= 1)
            rec = mode._records[0]
            self.assertTrue(rec["void"])
            self.assertEqual(rec["outcome"], "omission")
            self.assertEqual(mode.lives_left, 1)
            self.assertFalse(mode.life_trial)
            self.assertEqual(mode.misses, [])
            kw = eng.log_trial.call_args.kwargs
            self.assertEqual(kw["error_type"], "device_drop")
            self.assertIn(";void=1", kw["stimulus"])
            st = mode.block_stats()
            self.assertEqual(st["n_omissions"], 0)
            self.assertEqual(st["n_voided"], 1)
            self.assertEqual(st["n_trials"], 0)
            self.assertEqual(st["per_length"], [])
            # The board is back: the same length, the same sequence.
            eng._drop_overlaps = lambda hand, t_from, t_to: False
            _until(mode, clock, lambda: mode.phase == "respond"
                   and mode.active is not None
                   and mode.trial_counter == 2)
            self.assertEqual(list(mode.sequence), first)

    def test_a_plain_silent_turn_still_spends_the_life(self):
        eng, mode = _simon_mode(max_len=3)
        with patched_clock() as clock:
            _until(mode, clock, lambda: len(mode._records) >= 1)
            self.assertFalse(mode._records[0]["void"])
            self.assertEqual(mode.lives_left, 0)
            self.assertTrue(mode.life_trial)
            self.assertEqual(len(mode.misses), 1)
            self.assertIsNone(eng.log_trial.call_args.kwargs["error_type"])
            self.assertEqual(mode.block_stats()["n_omissions"], 1)

    def test_the_wire_engine_keeps_the_game_after_a_drop(self):
        # The reviewer's reproduction: the board goes away one second
        # into the first reproduction and is back four seconds later;
        # the hand never answers, because it could not. Then the
        # replay and one more turn are left silent so the block ends
        # and the CSV lands.
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng, rig = _make_wire_engine(td, clock, buzz_after=False)
            pump = _Pump(eng, rig, clock)
            pump.until(lambda: eng.detectors.get("right") is not None
                       and eng.detectors["right"].baseline[0] is not None,
                       300)
            eng.begin_echo_block()
            mode = eng.mode
            pump.until(lambda: mode.phase == "respond")
            for _ in range(60):
                pump.frame()
            eng._note_drop("right")
            for _ in range(240):
                pump.frame()
            eng._note_reconnect("right")
            pump.until(lambda: len(mode._records) >= 1, 2000)
            self.assertTrue(mode._records[0]["void"])
            self.assertEqual(mode.lives_left, 1)
            self.assertFalse(mode.life_trial)
            self.assertEqual(eng.misses, 0)
            pump.until(lambda: eng.trial_logger is None, 8000)
            root = Path(eng.last_session_root)
            with (root / "trials.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual([r["error_type"] for r in rows],
                             ["device_drop", "timeout", "timeout"])
            self.assertIn("void=1", rows[0]["stimulus"])
            meta = json.loads((root / "metadata.json")
                              .read_text(encoding="utf-8"))
            bs = meta["block_summary"]
            ec = bs["echo"]
            self.assertEqual(ec["n_voided"], 1)
            self.assertEqual(ec["n_omissions"], 2)
            self.assertEqual(ec["n_trials"], 2)
            self.assertEqual(ec["games_played"][0]["life_used_at"], 1)
            self.assertEqual(ec["games_played"][0]["n_trials"], 2)
            self.assertEqual(bs["misses"], 2)
            self.assertEqual(bs["connection"]["voided_trials"], 1)


class OffsetTests(unittest.TestCase):

    def _to_two_items(self, mode, clock):
        for _ in range(400):
            clock.t += 0.05
            mode.update(0.05)
            if mode.phase == "respond" and len(mode.sequence) == 1:
                mode.queue_press(_press(mode.sequence[0], clock.t))
                mode.update(0.0)
                break
        _until(mode, clock, lambda: mode.phase == "respond"
               and len(mode.sequence) == 2)

    def test_a_pause_mid_turn_leaves_the_offsets_alone(self):
        eng, mode = _simon_mode(max_len=3)
        with patched_clock() as clock:
            self._to_two_items(mode, clock)
            r0 = mode._respond_t0
            clock.t = r0 + 0.6
            mode.queue_press(_press(mode.sequence[0], clock.t))
            mode.update(0.0)
            clock.t += 30.0
            mode.shift_wait(30.0)
            mode.on_resume(30.0)
            clock.t += 0.5
            mode.queue_press(_press(mode.sequence[1], clock.t))
            mode.update(0.0)
        stim = eng.log_trial.call_args.kwargs["stimulus"]
        self.assertIn(";pt=600-1100;", stim)

    def test_a_fast_reply_measures_from_the_grid(self):
        eng, mode = _simon_mode(max_len=3, item_on_ms=400.0, ioi_ms=800.0)
        with patched_clock() as clock:
            for _ in range(400):
                clock.t += 0.02
                mode.update(0.02)
                if (mode.phase == "play"
                        and mode._item_idx >= len(mode.sequence)):
                    break
            self.assertEqual(mode.phase, "play")
            last_off = mode._last_offset_due()
            t_press = last_off + 0.001
            clock.t = last_off + 0.012
            mode.queue_press(_press(mode.sequence[0], t_press))
            mode.update(0.0)
        kw = eng.log_trial.call_args.kwargs
        self.assertIn(";pt=1;", kw["stimulus"])
        self.assertAlmostEqual(kw["continuous"].segments[1][1], last_off,
                               places=9)

    def test_the_turn_opens_on_the_grid_in_the_ordinary_path(self):
        eng, mode = _simon_mode(max_len=3, item_on_ms=400.0, ioi_ms=800.0)
        with patched_clock() as clock:
            _until(mode, clock, lambda: mode.phase == "respond",
                   step_s=0.017)
            self.assertAlmostEqual(mode._respond_t0,
                                   mode._last_offset_due(), places=9)
            self.assertLessEqual(mode._respond_t0, clock.t)


class NeutralStyleTests(unittest.TestCase):

    def _best_chips(self, style):
        eng, mode = _simon_mode(max_len=2)
        eng.feedback_style = style
        gp = MagicMock()
        eng._screens = {"gameplay": gp}
        with patched_clock() as clock:
            _until(mode, clock, lambda: len(mode._records) >= 1,
                   step_s=0.1, responder=_simon_play(mode, clock))
        self.assertEqual(mode._records[0]["outcome"], "correct")
        return [c for c in gp.set_message.call_args_list
                if c.kwargs.get("kind") == "best"]

    def test_no_best_chip_under_the_neutral_style(self):
        self.assertEqual(self._best_chips("neutral"), [])
        self.assertEqual(len(self._best_chips("encouraging")), 1)


class PriorGameNameTests(unittest.TestCase):

    def test_the_count_reads_the_name_as_the_seed_does(self):
        from finger_rehab.game.modes.echo import count_prior_echo_games
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / "a"
            folder.mkdir()
            meta = {"participant": "Basil",
                    "block_summary": {"block": "echo", "status": "completed",
                                      "echo": {"rule": "simon",
                                               "games_played": [
                                                   {"span": 4}, {"span": 5}]}}}
            (folder / "metadata.json").write_text(json.dumps(meta),
                                                  encoding="utf-8")
            for name in ("Basil", "basil", "Basil ", " BASIL"):
                self.assertEqual(count_prior_echo_games(root, name), 2,
                                 name)


class FeedbackByteTests(unittest.TestCase):

    def _feedback_codes(self, delay_ms):
        eng, mode = _simon_mode(max_len=2)
        eng._eeg_feedback_markers = True
        eng.feedback_delay_ms = delay_ms
        eng._eeg_send = MagicMock()
        with patched_clock() as clock:
            _until(mode, clock, lambda: len(mode._records) >= 1,
                   step_s=0.1, responder=_simon_play(mode, clock))
        self.assertEqual(mode._records[0]["outcome"], "correct")
        return [c.args[0] for c in eng._eeg_send.call_args_list
                if c.args and c.args[0] in (140, 141, 142)]

    def test_no_feedback_byte_under_a_feedback_delay(self):
        self.assertEqual(self._feedback_codes(800), [])
        self.assertEqual(self._feedback_codes(0), [140])


# ---- notebook ------------------------------------------------------------


def _echo_row(i, played, pressed, outcome, pos=0, miss="none", pt="",
              life=0, lives_left=1, err="", void=False, hand_mode="right",
              game="g1", session="s1", seed="1"):
    n = len(played)
    n_right = sum(1 for a, b in zip(played, pressed) if a == b) \
        if outcome != "wrong" else max(0, len(pressed) - 1)
    stim = (f"echo;len={n};trial=1;run=1;hebb=0;"
            f"played={'-'.join(str(x) for x in played)};"
            f"pressed={'-'.join(str(x) for x in pressed)};"
            f"n_right={n_right};outcome={outcome};pt={pt};rule=simon;"
            f"game=1;seed={seed};life={life};lives_left={lives_left};"
            f"pos={pos};miss={miss}")
    if void:
        stim += ";void=1"
    return dict(mode="echo", game=game, session=session, trial=i,
                stimulus=stim, error_type=err, hand_mode=hand_mode,
                participant="P01", early_late="Great"
                if outcome == "correct" else "Miss",
                waveform_params=(f"game_seed={seed};hebb=0;ioi_ms=800;"
                                 f"pulse_ms=400;rule=simon;seq="
                                 + "-".join(str(x) for x in played)))


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_voided_rows_leave_the_frame(self):
        import pandas as pd
        rows = [_echo_row(1, [0], [0], "correct"),
                _echo_row(2, [0, 1], [], "omission", pos=1,
                          miss="omission", err="device_drop", void=True),
                _echo_row(3, [0, 1], [0, 1], "correct"),
                _echo_row(4, [0, 1, 2], [], "omission", pos=1,
                          miss="omission", err="timeout")]
        ef = self.ra.echo_frame(pd.DataFrame(rows))
        self.assertEqual(len(ef), 3)
        self.assertEqual(int((ef["outcome"] == "omission").sum()), 1)
        block = {"game": "g1", "folder": Path("."), "meta": {},
                 "bs": {"echo": {"rule": "simon"}},
                 "rows": pd.DataFrame(rows), "hand": "right",
                 "calset": None, "extra": {}}
        emitted = {m: (v, n) for _h, m, v, n
                   in self.ra._cohort_echo(block)}
        self.assertEqual(emitted["n_omissions"][0], 1)
        self.assertEqual(emitted["span"][0], 2)

    def test_signed_offsets_parse(self):
        import pandas as pd
        rows = [_echo_row(1, [0, 1], [0, 1], "correct", pt="600-1100"),
                _echo_row(2, [0, 1], [0, 1], "correct", pt="-29400-1100"),
                _echo_row(3, [0, 1], [0, 1], "correct", pt="-11-589")]
        ef = self.ra.echo_frame(pd.DataFrame(rows))
        self.assertEqual(ef["press_ms"].tolist(),
                         [[600.0, 1100.0], [-29400.0, 1100.0],
                          [-11.0, 589.0]])

    def test_compress_run_counts_a_run_in_either_direction(self):
        import pandas as pd
        down = [_echo_row(i + 1, [3, 2, 1, 0][:i + 1], [3, 2, 1, 0][:i + 1],
                          "correct", game="g1") for i in range(4)]
        hill = [_echo_row(i + 1, [0, 1, 2, 1, 0][:i + 1],
                          [0, 1, 2, 1, 0][:i + 1], "correct", game="g2",
                          session="s2") for i in range(5)]
        ef = self.ra.echo_frame(pd.DataFrame(down + hill))
        pg = self.ra._echo_simon_tables(ef)["per_game"].set_index("game")
        self.assertEqual(int(pg.loc["g1", "compress_run"]), 4)
        self.assertEqual(int(pg.loc["g1", "compress_n_runs"]), 1)
        self.assertEqual(int(pg.loc["g2", "compress_run"]), 3)
        self.assertEqual(int(pg.loc["g2", "compress_n_runs"]), 2)

    def test_e2p_is_the_newest_item_share_against_chance(self):
        import pandas as pd
        ra = self.ra
        # Ten misses at length nine, four on the newest item: 0.40
        # against a chance share of 0.11 is a concentration on the
        # newest item, though the prefix share (0.60) sits above 0.5.
        played = [0, 1, 2, 3, 0, 1, 2, 3, 0]
        rows = []
        for i in range(10):
            pos = 9 if i < 4 else 2
            pressed = played[:pos - 1] + [3 if played[pos - 1] != 3 else 2]
            rows.append(_echo_row(i + 1, played, pressed, "wrong",
                                  pos=pos, miss="transposition",
                                  game=f"g{i}", session=f"s{i}",
                                  lives_left=0))
        block = {"game": "g", "folder": Path("."), "meta": {},
                 "bs": {"echo": {"rule": "simon"}},
                 "rows": pd.DataFrame(rows), "hand": "right",
                 "calset": None, "extra": {}}
        emitted = {m: (v, n) for _h, m, v, n in ra._cohort_echo(block)}
        self.assertAlmostEqual(emitted["newest_miss_excess"][0],
                               0.4 - 1.0 / 9.0)
        self.assertEqual(emitted["newest_miss_excess"][1], 10)
        self.assertAlmostEqual(emitted["prefix_miss_share"][0], 0.6)
        # The cohort row is decided on that number, above zero.
        cols = ra.COHORT_LONG_COLS
        long = []
        for i in range(6):
            for metric, val in (("newest_miss_excess", 0.4 - 1.0 / 9.0),
                                ("prefix_miss_share", 0.6),
                                ("span", 6.0)):
                r = {c: None for c in cols}
                r.update(participant=f"P{i:02d}", phase="pass1",
                         hand="right", hand_role="dominant", mode="echo",
                         metric=metric, value=val, n_trials=10)
                long.append(r)
        cohort = {"long": pd.DataFrame(long, columns=cols),
                  "sel": pd.DataFrame(), "trials": pd.DataFrame(),
                  "min_n": 3, "metas": {}, "tables": {}, "frames": {}}
        with contextlib.redirect_stdout(io.StringIO()):
            v = ra.sec_cohort_validity(cohort).set_index("id")
        self.assertIn("newest item", str(v.loc["E2p", "check"]))
        self.assertEqual(v.loc["E2p", "verdict"], "pass")
        self.assertAlmostEqual(float(v.loc["E2p", "value"]),
                               0.4 - 1.0 / 9.0)

    def test_the_selection_checks_follow_the_one_board_rig(self):
        import pandas as pd
        seq = [0, 1, 2, 3, 0, 2, 1, 3, 0, 2]
        rows = [_echo_row(i + 1, seq[:i + 1], seq[:i + 1], "correct")
                for i in range(9)]
        wrong = seq[:9] + [1]
        rows.append(_echo_row(10, seq, wrong, "wrong", pos=10,
                              miss="transposition", lives_left=0))
        with contextlib.redirect_stdout(io.StringIO()):
            out = self.ra.sec_echo_checks(pd.DataFrame(rows))
        checks = out["checks"].set_index("id")
        self.assertEqual(checks.loc["E1", "verdict"], "pass")
        self.assertIn("5 to 9", str(checks.loc["E1", "value"]))
        self.assertEqual(checks.loc["E3", "verdict"], "dropped")


if __name__ == "__main__":
    unittest.main()
