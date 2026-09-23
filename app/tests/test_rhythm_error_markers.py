"""Rhythm has to be able to supply error trials to an ERN analysis.

The EEG research plan lists rhythm among the error-rich modes the ERN
(error-related negativity) is drawn from, and the ERN is made by
comparing error trials against correct ones. Every wrong-finger press
in rhythm used to go out as 131, "idle press, artifact bookkeeping", so
epoching errors on 110 to 117 found none from rhythm at all.

Two different things had shared that code:
  - the wrong finger pressed while another finger's note was due: a
    commission error, which belongs in the wrong-press band;
  - a press with no note due anywhere: genuinely idle, which stays 131.
These tests hold that apart, through the real rhythm matching.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_rhythm_tactile import (FRAME_S, _drive,  # noqa: E402
                                       _fake_clock, _make_mode, _press)


class RhythmDecidesWhatKindOfWrongPressItIs(unittest.TestCase):

    def test_wrong_finger_on_the_beat_is_an_error(self):
        # Default chart: note 0 is lane 0 at t = 1.0. Press lane 2 on
        # that beat. Lane 2 has nothing due, lane 0 does.
        def go(clock):
            mode, engine, bm = _make_mode()
            _drive(mode, clock, 1.1)
            beat = mode._t_start + bm.notes[0].t + 0.040
            mode.queue_press(_press(2, beat))
            clock.t += FRAME_S
            mode.update(FRAME_S)
            engine.log_rhythm_unmatched.assert_called_once()
            self.assertTrue(
                engine.log_rhythm_unmatched.call_args.kwargs["wrong_finger"])

        _fake_clock(go)

    def test_a_press_with_nothing_due_is_idle(self):
        from finger_rehab.audio.beatmap import Note
        # Two notes four seconds apart, a press in the middle: nothing
        # in any lane is inside its window.
        notes = [Note(t=1.0, lane=0), Note(t=5.0, lane=1)]

        def go(clock):
            mode, engine, bm = _make_mode(notes=notes)
            _drive(mode, clock, 3.0)
            mode.queue_press(_press(2, mode._t_start + 3.0 + 0.040))
            clock.t += FRAME_S
            mode.update(FRAME_S)
            engine.log_rhythm_unmatched.assert_called_once()
            self.assertFalse(
                engine.log_rhythm_unmatched.call_args.kwargs["wrong_finger"])

        _fake_clock(go)

    def test_the_right_finger_is_still_a_hit(self):
        # The change only looks at presses no same-lane note claims.
        def go(clock):
            mode, engine, bm = _make_mode()
            _drive(mode, clock, 1.1)
            beat = mode._t_start + bm.notes[0].t + 0.040
            mode.queue_press(_press(0, beat))
            clock.t += FRAME_S
            mode.update(FRAME_S)
            engine.log_rhythm_hit.assert_called_once()
            engine.log_rhythm_unmatched.assert_not_called()

        _fake_clock(go)


class TheEngineSendsTheMatchingByte(unittest.TestCase):

    def _engine(self):
        from finger_rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng._block_rhythm_spurious_presses = 0
        eng._per_lane_wrong = {}
        eng.raw_logger = None
        eng.hand_mode = "right"
        eng.audio = None
        eng._screens = {}
        eng.sent = []
        eng._eeg_send = lambda code, **kw: eng.sent.append(code)
        eng.apply_wrong_press_penalty = MagicMock()
        return eng

    def test_wrong_finger_goes_out_in_the_wrong_press_band(self):
        from finger_rehab.hardware import eeg_trigger
        eng = self._engine()
        eng.log_rhythm_unmatched(3, 0.0, t_press_perf=10.0, wrong_finger=True)
        self.assertEqual(eng.sent, [eeg_trigger.response_code("wrong", 3)])
        self.assertTrue(110 <= eng.sent[0] <= 117)

    def test_idle_press_stays_131(self):
        from finger_rehab.hardware import eeg_trigger
        eng = self._engine()
        eng.log_rhythm_unmatched(3, 0.0, t_press_perf=10.0)
        self.assertEqual(eng.sent, [eeg_trigger.CODES["resp_idle"]])

    def test_both_still_count_and_cost_the_same(self):
        # Score and counters are unchanged: only the marker differs.
        for wrong in (True, False):
            with self.subTest(wrong_finger=wrong):
                eng = self._engine()
                eng.log_rhythm_unmatched(1, 0.0, t_press_perf=10.0,
                                         wrong_finger=wrong)
                self.assertEqual(eng._block_rhythm_spurious_presses, 1)
                self.assertEqual(eng._per_lane_wrong, {1: 1})
                eng.apply_wrong_press_penalty.assert_called_once()


if __name__ == "__main__":
    unittest.main()
