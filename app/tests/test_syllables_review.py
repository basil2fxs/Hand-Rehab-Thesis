"""Syllables faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: a right answer given after the prompt buzz lowered the
foil rung (eight of twelve simulated blocks drifted off the rung the
design pins); a pause on the COMPLETE card replayed the finished word
and logged every set twice; a pause during a returned word past the
word budget ended the block from inside the resume; a set that timed
out while the board was away was a miss, parked the word and broke
the streak; the model's stimulus bytes carried the previous word's
set id; the print flag on a row followed the rung at scoring time;
the adult threshold's last-12 mean counted replayed sets; and a
press inside the spawn lockout left no byte while the engine wrote
a deadline-expired byte for the set.

Notebook side: the set frame counted rows the rig had voided.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_syllables_mode import (_answer_set, _build_mode, _press,  # noqa: E402
                                       _run_to_choose, _wait_for_next_set)


def _rung_changes(engine):
    return [c.kwargs["detail"]
            for c in engine.raw_logger.queue_event.call_args_list
            if c.args and c.args[0] == "rung_change"]


def _stimuli(engine):
    return [c.kwargs["stimulus"] for c in engine.log_trial.call_args_list]


def _field(stim, key):
    for part in stim.split(";")[1:]:
        k, _, v = part.partition("=")
        if k == key:
            return v
    return None


class _VirtualClock:
    """The mode reads time.perf_counter only on resume; the tests
    drive _tick with their own time, so the two are kept together."""

    def __init__(self):
        self.t = 0.0

    def __enter__(self):
        import finger_rehab.game.modes.syllables as syl
        self._patch = patch.object(syl.time, "perf_counter",
                                   lambda: self.t)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()


class StaircaseTests(unittest.TestCase):

    def test_a_prompted_right_answer_moves_the_rung_neither_way(self):
        engine, mode = _build_mode(rung=5)
        t = _run_to_choose(mode)
        t = _answer_set(mode, t, delay=0.4)
        self.assertEqual(mode._sets[-1].pclass, "unprompted_correct")
        self.assertEqual(mode._run, 1)
        t = _wait_for_next_set(mode, t)
        t0, fall = mode._spawn_t, mode.fall_s
        mode._tick(t0 + 0.8 * fall)
        self.assertTrue(engine.on_prompt_buzz.called)
        t = _answer_set(mode, t0 + 0.85 * fall, delay=0.85 * fall)
        rec = mode._sets[-1]
        self.assertEqual(rec.pclass, "prompted_correct")
        self.assertEqual(rec.err, "ok")
        self.assertEqual(mode.rung, 5)
        self.assertEqual(mode._run, 1)
        self.assertEqual(_rung_changes(engine), [])
        # The run of answers found alone carries on past it.
        t = _wait_for_next_set(mode, t)
        t = _answer_set(mode, t, delay=0.4)
        t = _wait_for_next_set(mode, t)
        t = _answer_set(mode, t, delay=0.4)
        self.assertEqual(mode.rung, 6)


class PauseTests(unittest.TestCase):

    def test_a_pause_on_the_complete_card_does_not_replay_the_word(self):
        engine, mode = _build_mode(rung=3)
        with _VirtualClock() as clock:
            t = _run_to_choose(mode)
            word, n = mode.word.word, mode.n_syll
            for k in range(n):
                t = _answer_set(mode, t, delay=0.4)
                if k < n - 1:
                    t = _wait_for_next_set(mode, t)
            while mode.phase != "complete":
                clock.t = t
                mode._tick(t)
                t += 0.02
            rows_before = len(_stimuli(engine))
            t += 5.0
            clock.t = t
            mode.on_resume(5.0)
            self.assertEqual(mode.phase, "complete")
            t = _wait_for_next_set(mode, t)
        self.assertEqual(len(_stimuli(engine)), rows_before)
        self.assertEqual(mode.words_done, 1)
        self.assertEqual([(w.word, len(w.sets)) for w in mode._records],
                         [(word, n)])
        self.assertEqual(mode.ret, 0)

    def test_a_pause_in_a_return_past_the_budget_keeps_the_block(self):
        engine, mode = _build_mode(rung=3, words_total=3)
        with _VirtualClock() as clock:
            t = _run_to_choose(mode)
            first = mode.word.word
            # Word 1: its first set is left to time out, so it is
            # parked and comes back after two other words.
            t = mode._spawn_t + mode.fall_s + 0.01
            mode._tick(t)
            t += mode.MISS_GLOW_S + 0.05
            mode._tick(t)
            self.assertEqual([e["word"].word for e in mode._parked],
                             [first])
            for _ in range(2):
                t = _wait_for_next_set(mode, t)
                for k in range(mode.n_syll):
                    t = _answer_set(mode, t, delay=0.4)
                    if k < mode.n_syll - 1:
                        t = _wait_for_next_set(mode, t)
                # The word counts once its COMPLETE card is over.
                while mode.phase == "complete":
                    clock.t = t
                    mode._tick(t)
                    t += 0.02
            self.assertEqual(mode.words_done, 3)
            t = _wait_for_next_set(mode, t)
            self.assertEqual((mode.word.word, mode.ret), (first, 1))
            t = _answer_set(mode, t, delay=0.4)
            t = _wait_for_next_set(mode, t)
            self.assertEqual(mode.pos, 1)
            t += 3.0
            clock.t = t
            mode.on_resume(3.0)
            self.assertNotEqual(mode.phase, "done")
            self.assertIsNone(mode.end_reason)
            self.assertFalse(engine.finish_block.called)
            # The return starts again from ATTEND and plays out.
            t = _wait_for_next_set(mode, t)
            self.assertEqual((mode.word.word, mode.ret, mode.pos),
                             (first, 1, 0))
            for k in range(mode.n_syll):
                t = _answer_set(mode, t, delay=0.4)
                if k < mode.n_syll - 1:
                    t = _wait_for_next_set(mode, t)
            for _ in range(400):
                if mode.phase == "done":
                    break
                clock.t = t
                mode._tick(t)
                t += 0.05
        self.assertEqual(mode.phase, "done")
        self.assertEqual(mode.end_reason, "completed")
        ret = [w for w in mode._records if w.ret == 1]
        self.assertEqual(len(ret), 1)
        self.assertTrue(ret[0].completed)


class DropVoidTests(unittest.TestCase):

    def _time_out_first_set(self, overlaps):
        engine, mode = _build_mode(rung=3)
        engine._drop_overlaps = lambda hand, t_from, t_to: overlaps
        t = _run_to_choose(mode)
        word, pos, tid = mode.word.word, mode.pos, mode.trial_counter
        t = mode._spawn_t + mode.fall_s + 0.01
        mode._tick(t)
        t += mode.MISS_GLOW_S + 0.05
        mode._tick(t)
        return engine, mode, t, word, pos, tid

    def test_a_set_the_rig_ate_is_replayed_not_missed(self):
        engine, mode, t, word, pos, tid = self._time_out_first_set(True)
        kw = engine.log_trial.call_args.kwargs
        self.assertEqual(kw["error_type"], "device_drop")
        self.assertEqual(_field(kw["stimulus"], "err"), "device_drop")
        self.assertEqual(_field(kw["stimulus"], "pclass"), "void")
        self.assertEqual(mode._sets, [])
        self.assertEqual(len(mode._voided_sets), 1)
        self.assertEqual(mode._records, [])
        self.assertEqual(mode._parked, [])
        self.assertEqual(mode._miss_run, 0)
        self.assertEqual(mode.rung, 3)
        self.assertEqual(mode._prompt_state.get(word, {"step": 0})["step"],
                         0)
        t = _wait_for_next_set(mode, t)
        self.assertEqual((mode.word.word, mode.pos), (word, pos))
        self.assertEqual(mode.trial_counter, tid + 1)
        st = mode.block_stats()
        self.assertEqual(st["n_voided_sets"], 1)
        self.assertEqual(st["n_sets"], 0)

    def test_a_plain_timeout_still_parks_the_word(self):
        engine, mode, t, word, pos, tid = self._time_out_first_set(False)
        self.assertEqual(engine.log_trial.call_args.kwargs["error_type"],
                         "miss")
        self.assertEqual(len(mode._sets), 1)
        self.assertEqual([e["word"].word for e in mode._parked], [word])
        self.assertEqual(mode._records[-1].error, "miss")

    def test_the_real_engine_voids_the_row(self):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["session"]["participant"] = "DropProof"
                cfg.data["report"] = {"enabled": False}
                cfg.data["syllables"]["speech"] = {"backend": "off"}
                cfg.data["syllables"]["words_per_block"] = 2
                # The fixed probe that opens the sitting is not what
                # this test is about.
                cfg.data["syllables"]["probe"] = False
                cfg.data["syllables"]["break_s"] = 0
                cfg.data["syllables"]["seed"] = 21
                eng = GameEngine(cfg, KeyboardOnlySource())
                gp = MagicMock()
                gp.lanes = []
                eng._screens = {"gameplay": gp, "results": MagicMock(),
                                "syllables": MagicMock()}
                eng.show_results = lambda: None
                eng.begin_syllables_block()
                mode = eng.mode
                vt = 1000.0
                while not (mode.phase == "choose"
                           and mode.option_set is not None):
                    vt += 1 / 120
                    mode._tick(vt)
                eng._block_drops = [{"hand": "right",
                                     "t_down": mode._spawn_t + 0.1,
                                     "t_up": None}]
                streak = eng.hit_streak
                root = Path(eng.session_paths.root)
                while mode.option_set is not None:
                    vt += 1 / 120
                    mode._tick(vt)
                self.assertEqual((eng.hits, eng.misses), (0, 0))
                self.assertEqual(eng._block_drop_voided, 1)
                self.assertEqual(eng.hit_streak, streak)
                self.assertEqual(mode._parked, [])
                self.assertEqual(mode._records, [])
                eng.finish_block()
                with (root / "trials.csv").open(encoding="utf-8") as fh:
                    rows = list(csv.DictReader(fh))
                self.assertEqual(rows[0]["error_type"], "device_drop")
                bs = eng.session.block_summary
                self.assertEqual(bs["misses"], 0)
                self.assertEqual(bs["connection"]["voided_trials"], 1)
                self.assertEqual(bs["syllables"]["n_voided_sets"], 1)
        finally:
            pygame.quit()


class RowTests(unittest.TestCase):

    def test_the_model_bytes_carry_the_next_set_id(self):
        engine, mode = _build_mode(rung=3)
        t = _run_to_choose(mode)
        ids = [c.args[1] for c in engine.on_stim_multi.call_args_list]
        self.assertTrue(ids)
        self.assertEqual(set(ids), {mode.trial_counter})
        n = mode.n_syll
        for k in range(n):
            t = _answer_set(mode, t, delay=0.4)
            if k < n - 1:
                t = _wait_for_next_set(mode, t)
        engine.on_stim_multi.reset_mock()
        t = _wait_for_next_set(mode, t)
        ids = [c.args[1] for c in engine.on_stim_multi.call_args_list]
        self.assertTrue(ids)
        self.assertEqual(set(ids), {mode.trial_counter})

    def test_the_print_flag_says_what_the_word_showed(self):
        engine, mode = _build_mode(rung=3, age_band="6-9", seed=11)
        self.assertEqual(mode.profile.print_rungs, 3)
        t = _run_to_choose(mode)
        while mode.n_syll < 3 or mode.pos != 0:
            t = _answer_set(mode, t, delay=0.4)
            t = _wait_for_next_set(mode, t)
            if mode.pos == 0:
                mode.rung, mode._run = 3, 0
        mode._word_printed = mode.show_print
        self.assertTrue(mode._word_printed)
        mode._run = 2
        n = mode.n_syll
        for k in range(n):
            t = _answer_set(mode, t, delay=0.4)
            if k == 0:
                self.assertEqual(mode.rung, 4)
            if k < n - 1:
                t = _wait_for_next_set(mode, t)
        rows = _stimuli(engine)[-n:]
        self.assertEqual([_field(s, "print") for s in rows], ["1"] * n)

    def test_the_adult_threshold_leaves_replayed_sets_out(self):
        engine, mode = _build_mode(rung=3, age_band="16+", seed=5)
        self.assertTrue(mode.fall_mode)
        t = _run_to_choose(mode)
        n_replayed = 0
        for i in range(14):
            if i % 3 == 1:
                self.assertTrue(mode.replay())
                n_replayed += 1
            t = _answer_set(mode, t, delay=0.5)
            t = _wait_for_next_set(mode, t)
        self.assertEqual(len(mode._sets), 14)
        self.assertEqual(n_replayed, 5)
        self.assertEqual(len(mode._set_falls), 9)


class EegByteTests(unittest.TestCase):

    def _codes(self, engine):
        return [(c.args[0], c.kwargs.get("t_event"))
                for c in engine._eeg_send.call_args_list]

    def test_a_press_inside_the_lockout_is_a_false_start_byte(self):
        engine, mode = _build_mode(rung=3)
        t = _run_to_choose(mode)
        lane = mode.option_set.target_lane
        t_press = mode._spawn_t + 0.5 * mode.spawn_lockout_s
        mode.queue_press(_press(lane, t_press, hand=mode._hand_of_lane(lane)))
        mode._tick(t_press)
        self.assertIn((120 + lane, t_press), self._codes(engine))
        # The set then times out: a press happened, so no 130.
        t = mode._spawn_t + mode.fall_s + 0.01
        mode._tick(t)
        kw = engine.log_trial.call_args.kwargs
        self.assertEqual(kw["response_t_perf"], t_press)
        self.assertEqual(kw["error_type"], "miss")

    def test_a_press_with_no_set_open_is_an_idle_byte(self):
        engine, mode = _build_mode(rung=3)
        t = _run_to_choose(mode)
        t = _answer_set(mode, t, delay=0.4)
        engine._eeg_send.reset_mock()
        # Between sets: nothing on screen to answer.
        self.assertIsNone(mode.option_set)
        mode.queue_press(_press(0, t, hand="right"))
        mode._tick(t)
        self.assertEqual([c for c, _t in self._codes(engine)], [131])


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_voided_sets_leave_the_frame(self):
        import pandas as pd

        def row(i, err, error_type, first="none"):
            stim = (f"flower;pos=0;nsyll=2;syl=flow;band=A;rung=3;hand=R;"
                    f"fall=2500;respeak=0;ret=0;"
                    f"opts=1:flow:target,2:flo:F1,3:flou:F2,4:flaw:F3;"
                    f"tlane=1;presses=;first={first};err={err};rt=;"
                    f"streak=0;sup=1;pon=1;pstep=0;prompt=0;pat=;"
                    f"pclass={'no_response' if err == 'miss' else 'void'};"
                    f"prof=classic;lex=word;print=1;replay=0")
            return dict(mode="syllables", session="s1", block="b1",
                        trial=i, stimulus=stim, error_type=error_type,
                        early_late="Miss")

        rows = [row(1, "device_drop", "device_drop"),
                row(2, "miss", "miss")]
        sy = self.ra.syllable_set_frame(pd.DataFrame(rows))
        self.assertEqual(len(sy), 1)
        self.assertEqual(sy["err"].tolist(), ["miss"])


if __name__ == "__main__":
    unittest.main()
