"""Engine and battery faults from the 27 September 2026 code review,
each reproduced before it was fixed.

A lone board picked as Left at login was renamed Right by PLAY ALL
without switching the hand, so the quick calibration it opened read a
detector fed with zeros and could not capture a press, and Skip ran
the sitting on the previous participant's saved profile. A relaunch
inside the rest between the passes started the next block at once
with a rest of zero logged and the sitting's clock back at zero. A
redo of the abandoned rest step logged the abandoned block and the
hub as rest. The strip's clock ran from PLAY ALL while the budget is
counted from login. Enter on the results screen replayed the block
just played as an unstamped free block.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_study_battery import (N_STEPS, REST_POSITION,  # noqa: E402
                                      _BatteryHarness, _Rig)

RESTING = 265.0
PRELOAD = (14.0, 32.0, 12.0, 13.0)
EMPTY_NOISE = (1.2, 1.4, 0.7, 0.5)
LIGHT_PRESS = 60.0


class _SampleRig(_Rig):
    """The study rig, delivering the samples a test pushes."""

    def __init__(self) -> None:
        super().__init__()
        self._q: deque = deque()

    @property
    def hands_connected(self) -> dict:
        return {h.hand: True for h in self.hands}

    def push(self, t_perf: float, values) -> None:
        self._q.append(SimpleNamespace(
            t_perf=t_perf, values=tuple(int(v) for v in values)))

    def get_sample(self, timeout: float = 0.0):
        return self._q.popleft() if self._q else None


class _SimClock:
    """time.perf_counter, time.time and time.strftime follow one clock
    the test advances, so metadata stamps and the performance clock
    agree the way they do in a real sitting."""

    def __init__(self) -> None:
        self._perf, self._time = time.perf_counter, time.time
        self._strftime, self._localtime = time.strftime, time.localtime
        self.t = self._perf()
        self.t0 = self.t
        self.wall0 = self._time()
        time.perf_counter = lambda: self.t
        time.time = lambda: self.wall0 + (self.t - self.t0)

        def strftime(fmt, tup=None):
            if tup is None:
                tup = self._localtime(time.time())
            return self._strftime(fmt, tup)

        time.strftime = strftime

    def advance(self, s: float) -> None:
        self.t += s

    def restore(self) -> None:
        time.perf_counter, time.time = self._perf, self._time
        time.strftime = self._strftime


def _profile(hand: str, code: str):
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    prof = CalibrationProfile(hand=hand, participant=code,
                              empty=[RESTING - p for p in PRELOAD],
                              empty_noise=list(EMPTY_NOISE),
                              resting=[RESTING] * 4,
                              press=[RESTING + LIGHT_PRESS] * 4)
    prof.set_max_press([400.0] * 4)
    return prof


class RelabelTests(_BatteryHarness):

    def _engine_with_calibration(self, rig):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(self.root / "sessions")
        cfg.data["session"]["calibration_dir"] = str(self.root / "cal")
        cfg.data.setdefault("srt", {})["setups_file"] = str(
            self.root / "srt_setups.json")
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        cfg.data["eeg"] = {"enabled": False}
        cfg.data.setdefault("quick_cal", {})["enabled"] = True
        cfg.data.setdefault("serial", {})["watch_ports"] = False
        eng = GameEngine(cfg, rig)
        eng._screens = eng._build_screens()
        self.eng = eng
        return eng

    def test_a_board_picked_as_left_is_calibrated_on_the_right(self):
        self._stub_rhythm()
        rig = _SampleRig()
        eng = self._engine_with_calibration(rig)
        # The previous participant's right-hand calibration is on the
        # laptop, as it is on every study day after the first person.
        prev = _profile("right", "P00")
        prev.press = [RESTING + 100.0] * 4
        prev.save(eng.cfg.calibration_path("current_right.json"))
        clock = _SimClock()
        self.addCleanup(clock.restore)
        eng.begin_session("P01", "25", dominant_hand="right", visit="1")
        self.assertTrue(eng.choose_session_hand("left"))
        self.assertEqual((rig.hands[0].hand, eng.hand_mode),
                         ("left", "left"))
        eng.apply_calibration(_profile("left", "P01"))
        eng._session_cal_hands = {"left"}
        eng.show_mode_select()
        self.assertTrue(eng.start_battery())
        self.assertEqual(rig.hands[0].hand, "right")
        self.assertEqual(eng.hand_mode, "right")
        qc = eng._screens["quick_cal"]
        self.assertIs(eng.screen_obj, qc)
        self.assertEqual(qc.hands, ["right"])
        next_sample = [clock.t]

        def frames(seconds: float, values) -> None:
            dt = 1.0 / 60.0
            for _ in range(int(seconds * 60)):
                clock.advance(dt)
                while next_sample[0] <= clock.t:
                    rig.push(next_sample[0], values)
                    next_sample[0] += 1.0 / 200.0
                eng._pump_source()
                qc.update(dt)

        frames(9.0, [RESTING - p for p in PRELOAD])
        frames(9.0, [RESTING] * 4)
        frames(6.0, [RESTING + LIGHT_PRESS, RESTING, RESTING, RESTING])
        # The board's samples reach the right hand's detector and the
        # flow captures the light press on the index finger.
        self.assertGreater(eng.detectors["right"].val_ema[0], RESTING + 40)
        self.assertGreater(qc._captures["right"]["press"][0], RESTING + 40)


class RelaunchTests(_BatteryHarness):

    def _to_the_rest(self, eng, clock) -> None:
        for _ in range(N_STEPS):
            clock.advance(150.0)
            eng.finish_block()
            step = eng.pending_protocol_step()
            if step and step["position"] == REST_POSITION:
                return
            clock.advance(10.0)
            self.assertTrue(eng.continue_protocol())
        self.fail("never reached the rest step")

    def test_the_clock_runs_from_login(self):
        self._stub_rhythm()
        clock = _SimClock()
        self.addCleanup(clock.restore)
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        clock.advance(300.0)
        self.assertTrue(eng.start_battery())
        self.assertAlmostEqual(eng.battery_progress()["minutes"], 5.0,
                               places=2)

    def test_a_relaunch_in_the_rest_holds_the_step_and_logs_the_rest(self):
        self._stub_rhythm()
        clock = _SimClock()
        self.addCleanup(clock.restore)
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        clock.advance(300.0)
        self.assertTrue(eng.start_battery())
        self._to_the_rest(eng, clock)
        held, left = eng.battery_rest_hold()
        self.assertTrue(held)
        self.assertAlmostEqual(left, 180.0, delta=1.0)
        # The app closes 30 s into the rest; the relaunch and the
        # login take a minute.
        clock.advance(30.0)
        eng._close_loggers()
        eng2 = self._engine(_Rig())
        clock.advance(60.0)
        self._login(eng2, "P01", "right")
        self.assertTrue(eng2.start_battery())
        self.assertFalse(eng2.block_is_running())
        self.assertEqual(eng2.pending_protocol_step()["position"],
                         REST_POSITION)
        held, left = eng2.battery_rest_hold()
        self.assertFalse(held)
        self.assertAlmostEqual(left, 90.0, delta=2.0)
        # The clock carries on from the sitting's first block, not
        # from the relaunch: every pass 1 block, the gaps between them,
        # and the 90 s of the close and the relaunch.
        carried = ((REST_POSITION - 1) * 150.0
                   + (REST_POSITION - 2) * 10.0 + 90.0) / 60.0
        self.assertAlmostEqual(eng2.battery_progress()["minutes"], carried,
                               delta=0.2)
        clock.advance(10.0)
        self.assertTrue(eng2.continue_protocol())
        self.assertEqual(eng2.session.battery["position"], REST_POSITION)
        self.assertAlmostEqual(eng2.session.battery["rest_before_s"],
                               100.0, delta=2.0)

    def test_a_redo_after_an_abandon_keeps_the_rest_it_was_given(self):
        self._stub_rhythm()
        clock = _SimClock()
        self.addCleanup(clock.restore)
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        self.assertTrue(eng.start_battery())
        self._to_the_rest(eng, clock)
        clock.advance(100.0)
        self.assertTrue(eng.continue_protocol())
        self.assertAlmostEqual(eng._rest_taken_s, 100.0, delta=1.0)
        clock.advance(40.0)
        eng._abandon_if_in_block()
        eng.show_mode_select()
        clock.advance(20.0)
        self.assertTrue(eng.start_battery())
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng.session.battery["position"], REST_POSITION)
        self.assertAlmostEqual(eng._rest_taken_s, 100.0, delta=1.0)
        self.assertAlmostEqual(eng.session.battery["rest_before_s"], 100.0,
                               delta=1.0)
        clock.advance(30.0)
        eng.finish_block()
        done = [r for r in eng.battery_progress()["log"]
                if r["position"] == REST_POSITION
                and r["status"] == "completed"]
        self.assertEqual(len(done), 1)
        self.assertAlmostEqual(done[0]["rest_taken_s"], 100.0, delta=1.0)


class ResultsScreenTests(_BatteryHarness):

    def test_enter_takes_the_next_step_inside_a_battery(self):
        import pygame
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        self.assertTrue(eng.start_battery())
        self.assertEqual(eng.current_block, "reaction")
        eng.finish_block()
        results = eng._screens["results"]
        self.assertIs(eng.screen_obj, results)
        self.assertFalse(results._can_retry())
        results.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0,
                             "unicode": "\r", "scancode": 0}))
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng.session.battery["position"], 2)
        self.assertEqual(eng._current_phase, "pass1")
        statuses = [r["status"] for r in eng.battery_progress()["log"]]
        self.assertEqual(statuses, ["completed"])


class NotebookTests(unittest.TestCase):

    def test_the_feasibility_read_carries_the_login_allowance(self):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        ra = _load_ra()
        self.assertEqual(ra.COHORT_PLAN_LOGIN_MIN, 5.0)


if __name__ == "__main__":
    unittest.main()
