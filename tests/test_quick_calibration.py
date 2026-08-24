"""The gamified quick calibration that gates each session's first game.

What has to hold, in order of how expensive it would be to get wrong:

  - the trigger rule: calibration is a session event. A hand runs the
    flow the first time a game in the session needs it (no usable
    profile, or the session has not put the flow in front of that
    hand yet) and every later game in the session skips it at zero
    cost, hand-mode changes included. The memory is session state on
    the engine, cleared at session end, never disk. A keyboard
    session never sees it at all (there is no force to calibrate);
  - the maths: the profile the game builds is the SAME profile the
    clinical CalibrationScreen would build from the same captures,
    because both go through CalibrationProfile and neither forks the
    threshold logic;
  - the plumbing: the finished profile saves to the same per-hand file
    and applies through the same engine path, so the block that starts
    right afterwards runs on the thresholds just measured;
  - the escape hatches: Skip writes nothing and leaves whatever was
    saved before untouched, and Esc asks before abandoning.

Everything runs headless through the real engine and the real screen,
with calibration files redirected to tmp paths.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from finger_rehab.hardware.calibration_profile import (
    CalibrationProfile, N_FINGERS,
)
from finger_rehab.hardware.source import Source


# Same bench numbers test_calibration.py uses, measured on the device.
EMPTY = [245.0, 250.0, 248.0, 235.0]
REST = [2.5, 8.9, 11.5, 30.7]
RESTING = [EMPTY[i] + REST[i] for i in range(N_FINGERS)]
# A light press 60 counts above resting sits inside the goal band on
# every finger of this device: the three clean pads get 20..80 and the
# preloaded pinky 44..175, both derived from these captures by
# target_gap_band.
PRESS_GAP = 60.0


class FakeFsrSource(Source):
    """A hardware-shaped source the tests drive by hand. Samples are
    queued by the test and drained by the engine's own pump, so the
    wiring under test is the real one."""

    def __init__(self) -> None:
        self.queued = []
        self.port = "/dev/fake"

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def get_sample(self, timeout: float = 0.0):
        return self.queued.pop(0) if self.queued else None

    def send_command(self, cmd: str) -> bool:
        return True

    @property
    def is_connected(self) -> bool:
        return True


def _redirect_calibration_files(cfg, tmp_path: Path) -> None:
    """Route every config/calibration path into tmp so a test can
    never touch the machine's real saved profiles."""
    orig = cfg.resolve_path

    def rp(value):
        p = str(value)
        if p.startswith("config/calibration"):
            return tmp_path / p
        return orig(value)

    cfg.resolve_path = rp


def _engine(tmp_path: Path, hand: str = "right", source=None):
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("bilateral", {})["hand"] = hand
    cfg.data.setdefault("game", {})["mode"] = "adaptive"
    eng = GameEngine(cfg, source or FakeFsrSource())
    _redirect_calibration_files(cfg, tmp_path)
    eng._screens = eng._build_screens()
    return eng


def _usable_profile(hand: str) -> CalibrationProfile:
    return CalibrationProfile(
        hand=hand,
        empty=list(EMPTY),
        empty_noise=[1.1] * N_FINGERS,
        resting=list(RESTING),
        press=[RESTING[i] + PRESS_GAP for i in range(N_FINGERS)],
    )


# ---- driving the flow ----------------------------------------------------

def _finish_rest_step(eng, sc, values) -> None:
    """Run one rest capture (hands off / hands resting) on real
    samples pushed through the screen's own intake."""
    sc._start_collecting()
    for k in range(60):
        sc.on_sample(k * 0.005, tuple(values))
    sc._collect_until = 0.0          # the capture window has elapsed
    sc.update(0.0)


def _hold_current_finger(eng, sc, hand: str) -> None:
    """Press the current finger 60 counts above resting and hold until
    the meter fills, feeding the detector through the engine's real
    feed path so the screen reads the same values a block would."""
    i = sc._finger_idx
    vals = list(RESTING)
    vals[i] = RESTING[i] + PRESS_GAP
    if hand == "left" and eng.hand_mode == "both":
        n = int(eng.cfg.get("fsr.num_sensors_per_hand", 4))
        vals = list(RESTING) + vals
        vals[:n] = RESTING
    t = 0.0
    for _ in range(80):
        eng._feed_detectors(t, tuple(vals))
        sc.update(0.05)
        sc.on_sample(t, tuple(vals))
        t += 0.05
        if sc._landed:
            break
    assert sc._landed, f"finger {i} never landed"
    sc._advance_at = 0.0             # skip the celebration pause
    sc.update(0.0)


def _run_whole_flow(eng, sc) -> None:
    from finger_rehab.ui import quick_calibration_screen as q
    _finish_rest_step(eng, sc, EMPTY * (2 if len(sc.hands) > 1 else 1))
    assert sc.phase == q.PHASE_REST
    _finish_rest_step(eng, sc, RESTING * (2 if len(sc.hands) > 1 else 1))
    assert sc.phase == q.PHASE_PRESS
    total = len(sc.hands) * N_FINGERS
    for _ in range(total):
        _hold_current_finger(eng, sc, sc._current_hand())
    assert sc.phase == q.PHASE_DONE


# ---- trigger rule --------------------------------------------------------

class TestTriggerRule:
    def test_missing_profile_runs_the_flow(self, tmp_path):
        eng = _engine(tmp_path)
        calls = []
        assert eng.maybe_start_quick_calibration(lambda: calls.append(1))
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["right"]
        assert calls == []           # the block must wait for the flow

    def test_applied_profile_still_runs_the_sessions_first_pass(
            self, tmp_path):
        # Calibration is a session event: a returning player with a
        # usable profile still gets the visual flow once, on the
        # session's first game that needs the hand.
        eng = _engine(tmp_path)
        eng.apply_calibration(_usable_profile("right"))
        assert eng.maybe_start_quick_calibration(lambda: None)
        assert eng.screen_obj is eng._screens["quick_cal"]

    def test_session_calibrated_hand_skips_every_later_game(self, tmp_path):
        eng = _engine(tmp_path)
        eng.apply_calibration(_usable_profile("right"))
        eng._session_cal_hands = {"right"}    # first game already ran it
        calls = []
        assert not eng.maybe_start_quick_calibration(lambda: calls.append(1))
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_usable_profile_on_disk_is_applied_by_the_check(self, tmp_path):
        # The disk profile feeds the detectors either way; what it no
        # longer does is stand in for the session's first visual pass.
        eng = _engine(tmp_path)
        prof = _usable_profile("right")
        prof.save(tmp_path / "config/calibration/current_right.json")
        assert eng.maybe_start_quick_calibration(lambda: None)
        applied = eng.calibration_profiles.get("right")
        assert applied is not None
        assert applied.on_delta() == prof.on_delta()
        # The detector runs on the loaded thresholds, not the defaults.
        det = eng.detectors["right"]
        assert det.cal.on_delta[:N_FINGERS] == prof.on_delta()
        # With the session pass done, the disk profile carries the skip.
        eng._session_cal_hands = {"right"}
        eng.screen_obj = None
        assert not eng.maybe_start_quick_calibration(lambda: None)

    def test_keyboard_session_skips_with_no_notice(self, tmp_path):
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        calls = []
        assert not eng.maybe_start_quick_calibration(lambda: calls.append(1))
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_bilateral_covers_only_the_uncalibrated_hand(self, tmp_path):
        # Session calibrated the right hand in an earlier game; a
        # later game adds the left, so only the LEFT hand's flow runs.
        eng = _engine(tmp_path, hand="both")
        eng.apply_calibration(_usable_profile("right"))
        eng._session_cal_hands = {"right"}
        assert eng.maybe_start_quick_calibration(lambda: None)
        assert eng.screen_obj.hands == ["left"]

    def test_flow_marks_hands_as_the_sessions_on_handover(self, tmp_path):
        # Finishing (or skipping) the gated flow is what stamps the
        # hands into the session; an Esc abandon must not.
        eng = _engine(tmp_path)
        assert eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        assert eng._session_cal_hands == set()
        sc._skip()
        assert eng._session_cal_hands == {"right"}

    def test_abandon_does_not_mark_the_session(self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_session("P1", "")
        assert eng.maybe_start_quick_calibration(lambda: None)
        eng._handle_escape()
        eng._handle_escape()
        assert eng._session_cal_hands == set()

    def test_session_end_clears_the_session_memory(self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_session("P1", "")
        eng._session_cal_hands = {"left", "right"}
        eng.end_session()
        assert eng._session_cal_hands == set()
        # And the next login starts clean too.
        eng._session_cal_hands = {"right"}
        eng.begin_session("P2", "")
        assert eng._session_cal_hands == set()

    def test_skipped_hand_without_profile_keeps_triggering(self, tmp_path):
        # Skip is an escape hatch, not a calibration: with no usable
        # profile behind it there is nothing to run the next game on,
        # so the flow comes back.
        eng = _engine(tmp_path)
        assert eng.maybe_start_quick_calibration(lambda: None)
        eng.screen_obj._skip()
        assert eng._session_cal_hands == {"right"}
        eng.screen_obj = None
        assert eng.maybe_start_quick_calibration(lambda: None)
        assert eng.screen_obj is eng._screens["quick_cal"]

    def test_unusable_saved_profile_still_triggers(self, tmp_path):
        # A saved file whose gaps are too small to run on must not
        # count as "has calibrated before".
        eng = _engine(tmp_path)
        bad = CalibrationProfile(
            hand="right", empty=list(EMPTY),
            empty_noise=[1.1] * N_FINGERS,
            resting=list(RESTING),
            press=[RESTING[i] + 5 for i in range(N_FINGERS)])
        assert not bad.usable()[0]
        bad.save(tmp_path / "config/calibration/current_right.json")
        assert eng.maybe_start_quick_calibration(lambda: None)

    def test_setup_screen_gates_the_block_start(self, tmp_path):
        eng = _engine(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        setup = eng._screens["setup"]
        setup._pick("right")
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert begun == []
        # Skipping hands over to the block start exactly once.
        eng.screen_obj._skip()
        assert begun == [1]

    def test_mirror_pick_gates_the_block_start(self, tmp_path):
        # Mirror bypasses the setup screen (bilateral-only, no hand
        # pick), so its start path must run the same session gate
        # itself. It used to call begin_mirror_block directly, making
        # a mirror-first hardware session the one flow that never
        # calibrated either hand.
        eng = _engine(tmp_path)
        begun = []
        eng.begin_mirror_block = lambda: begun.append(1)
        eng._screens["mode_select"]._pick("mirror")
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert begun == []
        # Both hands are in front of the flow (mirror forces bilateral).
        assert sorted(eng.screen_obj.hands) == ["left", "right"]
        # Skipping hands over to the block start exactly once.
        eng.screen_obj._skip()
        assert begun == [1]

    def test_mirror_pick_skips_the_gate_on_keyboard(self, tmp_path):
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        begun = []
        eng.begin_mirror_block = lambda: begun.append(1)
        eng._screens["mode_select"]._pick("mirror")
        assert begun == [1]
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_setup_screen_starts_straight_away_on_keyboard(self, tmp_path):
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        assert begun == [1]
        assert eng.screen_obj is not eng._screens["quick_cal"]


# ---- the flow itself, end to end -----------------------------------------

class TestFlowEndToEnd:
    def test_full_run_saves_and_applies_through_the_real_engine(
            self, tmp_path):
        eng = _engine(tmp_path)
        calls = []
        assert eng.maybe_start_quick_calibration(lambda: calls.append(1))
        sc = eng.screen_obj
        _run_whole_flow(eng, sc)
        assert not sc._problems
        sc._finish()

        # Saved to the same per-hand file the clinical screen writes.
        path = tmp_path / "config/calibration/current_right.json"
        assert path.exists()
        saved = CalibrationProfile.load(path)
        assert saved is not None and saved.usable()[0]
        assert saved.hand == "right"
        for i in range(N_FINGERS):
            assert saved.gap()[i] == pytest.approx(PRESS_GAP, abs=2.0)
        # A dated history copy exists so this run never destroys the
        # previous one silently.
        assert list((tmp_path / "config/calibration/history").glob("*.json"))

        # Applied through the same path: engine holds it, the detector
        # runs on it, and the continuation fired exactly once.
        applied = eng.calibration_profiles["right"]
        assert applied.on_delta() == saved.on_delta()
        det = eng.detectors["right"]
        assert det.cal.on_delta[:N_FINGERS] == saved.on_delta()
        assert det.cal.off_delta[:N_FINGERS] == saved.off_delta()
        assert calls == [1]

    def test_bilateral_runs_left_hand_first_and_saves_both(self, tmp_path):
        eng = _engine(tmp_path, hand="both")
        calls = []
        assert eng.maybe_start_quick_calibration(lambda: calls.append(1))
        sc = eng.screen_obj
        # Left first, matching the lane strips' left-on-the-left layout.
        assert sc.hands == ["left", "right"]
        _run_whole_flow(eng, sc)
        sc._finish()
        for hand in ("left", "right"):
            path = tmp_path / f"config/calibration/current_{hand}.json"
            assert path.exists(), f"{hand} profile not saved"
            assert eng.calibration_profiles[hand].hand == hand
        assert calls == [1]

    def test_profile_maths_identical_to_the_clinical_path(self, tmp_path):
        """Feed the SAME captures through the quick flow and through
        the clinical screen's collection; the resulting thresholds
        must be identical, because both are CalibrationProfile and
        neither forks the maths."""
        import finger_rehab.ui.calibration_screen as cs

        # Quick flow, driven for real.
        eng = _engine(tmp_path)
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        _run_whole_flow(eng, sc)
        quick = sc._profiles["right"]

        # Clinical flow on the same numbers, same driving pattern as
        # test_calibration.TestScreenFlow.
        clin = cs.CalibrationScreen(eng)
        clin.hand = "right"
        clin.job = cs.JOB_SENSORS
        clin._begin()
        for step_vals in (EMPTY, RESTING):
            clin._start_collecting(0.0)
            for _ in range(60):
                clin.on_sample(0.0, tuple(step_vals))
            clin.update(0.0)
        for i in range(N_FINGERS):
            vals = list(RESTING)
            vals[i] = RESTING[i] + PRESS_GAP
            clin._start_collecting(0.0)
            for _ in range(60):
                clin.on_sample(0.0, tuple(vals))
            clin.update(0.0)
        clinical = clin.profile

        assert quick.on_delta() == clinical.on_delta()
        assert quick.off_delta() == clinical.off_delta()
        for i in range(N_FINGERS):
            assert quick.gap()[i] == pytest.approx(clinical.gap()[i],
                                                   abs=0.5)

    def test_pump_pushes_samples_into_the_quick_flow(self, tmp_path):
        """The engine's own pump must feed this screen every sample,
        the same wiring the clinical screen relies on."""
        from finger_rehab.hardware.source import Sample
        src = FakeFsrSource()
        eng = _engine(tmp_path, source=src)
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        sc._start_collecting()
        src.queued = [Sample(t_perf=k * 0.005, values=tuple(EMPTY))
                      for k in range(10)]
        eng._pump_source()
        assert len(sc._rest_buffers.get("right", [])) == 10

    def test_too_hard_a_press_does_not_fill_the_meter(self, tmp_path):
        """The band ceiling is the teaching: pressing well above it
        must stall the capture rather than reward a slam."""
        eng = _engine(tmp_path)
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        _finish_rest_step(eng, sc, EMPTY)
        _finish_rest_step(eng, sc, RESTING)
        vals = list(RESTING)
        vals[0] = RESTING[0] + 400.0     # way over zone_max_counts
        t = 0.0
        for _ in range(40):
            eng._feed_detectors(t, tuple(vals))
            sc.update(0.05)
            sc.on_sample(t, tuple(vals))
            t += 0.05
        assert not sc._landed
        assert sc._hold == 0.0


# ---- skip and the Esc guard ----------------------------------------------

class TestSkipAndEscape:
    def test_skip_writes_nothing_and_keeps_prior_profiles(self, tmp_path):
        eng = _engine(tmp_path, hand="both")
        # Right hand already calibrated this session; its saved file
        # must survive byte for byte.
        prof = _usable_profile("right")
        right_path = tmp_path / "config/calibration/current_right.json"
        prof.save(right_path)
        eng._session_cal_hands = {"right"}
        before = right_path.read_bytes()
        calls = []
        assert eng.maybe_start_quick_calibration(lambda: calls.append(1))
        sc = eng.screen_obj
        assert sc.hands == ["left"]
        # Part-run then skip: captures in memory must not leak to disk.
        _finish_rest_step(eng, sc, EMPTY * 2)
        sc._skip()
        assert calls == [1]
        assert right_path.read_bytes() == before
        assert not (tmp_path / "config/calibration/current_left.json").exists()
        assert "left" not in eng.calibration_profiles

    def test_escape_asks_before_abandoning(self, tmp_path):
        eng = _engine(tmp_path)
        # The gate fires on a game start, so the player is logged in.
        eng.begin_session("P1", "")
        calls = []
        eng.maybe_start_quick_calibration(lambda: calls.append(1))
        sc = eng.screen_obj
        eng._handle_escape()
        # First Esc raises the guard and stays on the flow.
        assert sc._confirm
        assert eng.screen_obj is sc
        sc._keep_going()
        assert not sc._confirm
        # Esc twice abandons to game select (the session's home base)
        # without saving or starting.
        eng._handle_escape()
        eng._handle_escape()
        assert eng.screen_obj is eng._screens["mode_select"]
        assert calls == []
        assert not (tmp_path / "config/calibration").exists()

    def test_escape_abandon_without_login_lands_on_title(self, tmp_path):
        # A menu launch from the login screen's Calibrate flow has no
        # session behind it, so abandoning cannot strand the player on
        # game select with nobody logged in.
        eng = _engine(tmp_path)
        eng.show_quick_calibration()
        eng._handle_escape()
        eng._handle_escape()
        assert eng.screen_obj is eng._screens["title"]

    def test_flow_is_frozen_while_the_guard_is_up(self, tmp_path):
        eng = _engine(tmp_path)
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        sc._start_collecting()
        eng._handle_escape()
        sc.on_sample(0.0, tuple(EMPTY))
        sc._collect_until = 0.0
        sc.update(0.0)
        # Neither the sample nor the elapsed timer moved the flow on.
        assert sc._rest_buffers.get("right", []) == []
        from finger_rehab.ui import quick_calibration_screen as q
        assert sc.phase == q.PHASE_OFF


# ---- drawing stays alive in every state ----------------------------------

class TestDrawing:
    def test_every_phase_draws_headless(self, tmp_path):
        import pygame
        from finger_rehab.ui import quick_calibration_screen as q
        eng = _engine(tmp_path)
        surf = pygame.Surface((1280, 800))
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        sc.draw(surf)                        # hands off, idle
        sc._start_collecting()
        sc.draw(surf)                        # hands off, counting down
        _finish_rest_step(eng, sc, EMPTY)
        sc.draw(surf)                        # resting prompt
        _finish_rest_step(eng, sc, RESTING)
        sc.draw(surf)                        # press game, idle bar
        _hold_current_finger(eng, sc, "right")
        sc.draw(surf)                        # press game, one tick down
        for _ in range(3):
            _hold_current_finger(eng, sc, "right")
        assert sc.phase == q.PHASE_DONE
        sc.draw(surf)                        # summary
        sc.on_escape()
        sc.draw(surf)                        # confirm overlay


# ---- the goal band -------------------------------------------------------

class TestGoalBand:
    """The band the screen coaches against is not a visual tuning knob.
    It is the threshold maths' own answer to "what gap does this finger
    need", so a press held anywhere in it always yields a profile
    usable() accepts, and no config key can pull the two apart."""

    def _at_press_phase(self, tmp_path, hand="right"):
        from finger_rehab.ui import quick_calibration_screen as q
        eng = _engine(tmp_path, hand=hand)
        eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        n = 2 if len(sc.hands) > 1 else 1
        _finish_rest_step(eng, sc, EMPTY * n)
        _finish_rest_step(eng, sc, RESTING * n)
        assert sc.phase == q.PHASE_PRESS
        return eng, sc

    def test_band_is_the_threshold_maths_not_a_second_rule(self, tmp_path):
        from finger_rehab.hardware.calibration_profile import (
            target_gap_band,
        )
        eng, sc = self._at_press_phase(tmp_path)
        cap = sc._captures["right"]
        for i in range(N_FINGERS):
            preload = cap["resting"][i] - cap["empty"][i]
            assert sc._band("right", i) == target_gap_band(
                preload, cap["empty_noise"][i])

    def test_band_rises_with_the_pads_resting_load(self, tmp_path):
        # The pinky pad carries 30 counts at rest and the index under 3,
        # so the pinky is asked for a firmer press. That is not a
        # judgement about pinkies: it is where its trigger has to sit.
        eng, sc = self._at_press_phase(tmp_path)
        assert sc._band("right", 3)[0] > sc._band("right", 0)[0]
        assert sc._band("right", 3)[1] > sc._band("right", 0)[1]

    def test_any_press_inside_the_band_gives_a_usable_profile(self,
                                                              tmp_path):
        """The whole point of deriving the band: hitting it cannot
        produce a profile the maths then rejects."""
        eng, sc = self._at_press_phase(tmp_path)
        cap = sc._captures["right"]
        for where in (0.0, 0.5, 1.0):
            prof = CalibrationProfile(
                hand="right", empty=list(cap["empty"]),
                empty_noise=list(cap["empty_noise"]),
                resting=list(cap["resting"]),
                press=[cap["resting"][i]
                       + sc._band("right", i)[0]
                       + where * (sc._band("right", i)[1]
                                  - sc._band("right", i)[0])
                       for i in range(N_FINGERS)])
            ok, problems = prof.usable()
            assert ok, f"press at {where} of the band rejected: {problems}"

    def test_no_config_key_can_move_the_band(self, tmp_path):
        # The old build took the band from quick_cal.zone_*_counts, which
        # let a settings edit ask for a press the profile would refuse.
        eng, sc = self._at_press_phase(tmp_path)
        before = [sc._band("right", i) for i in range(N_FINGERS)]
        eng.cfg.data.setdefault("quick_cal", {})["zone_min_counts"] = 400
        eng.cfg.data["quick_cal"]["zone_max_counts"] = 900
        assert [sc._band("right", i) for i in range(N_FINGERS)] == before

    def test_capture_refuses_a_press_under_the_band_floor(self, tmp_path):
        eng, sc = self._at_press_phase(tmp_path)
        lo, _ = sc._band("right", 0)
        sc._zone_buffer = [RESTING[0] + lo - 4.0] * 20
        sc._hold = 1.0
        sc._capture_press()
        assert not sc._landed
        assert sc._captures["right"]["press"][0] == 0.0


# ---- what the press step refuses to reward -------------------------------

class TestPressCoaching:
    def _at_press_phase(self, tmp_path):
        return TestGoalBand()._at_press_phase(tmp_path)

    def _drive(self, eng, sc, vals, steps=40):
        t = 0.0
        for _ in range(steps):
            eng._feed_detectors(t, tuple(vals))
            sc.update(0.05)
            sc.on_sample(t, tuple(vals))
            t += 0.05

    def test_over_the_ceiling_pauses_instead_of_capturing(self, tmp_path):
        """A crush press sets a trigger the same finger cannot reach
        when it is tired, so the hold has to stall rather than bank it."""
        eng, sc = self._at_press_phase(tmp_path)
        _, hi = sc._band("right", 0)
        vals = list(RESTING)
        vals[0] = RESTING[0] + hi * 2
        self._drive(eng, sc, vals)
        assert not sc._in_zone
        assert not sc._landed
        assert sc._hold == 0.0
        assert sc._zone_buffer == []
        assert sc._captures["right"]["press"][0] == 0.0

    def test_easing_back_into_the_band_then_captures(self, tmp_path):
        # The pause is a pause, not a lockout.
        eng, sc = self._at_press_phase(tmp_path)
        lo, hi = sc._band("right", 0)
        vals = list(RESTING)
        vals[0] = RESTING[0] + hi * 2
        self._drive(eng, sc, vals, steps=20)
        assert not sc._landed
        vals[0] = RESTING[0] + (lo + hi) / 2
        self._drive(eng, sc, vals, steps=80)
        assert sc._landed
        gap = sc._captures["right"]["press"][0] - RESTING[0]
        assert lo <= gap <= hi

    def test_a_wrong_finger_is_named_and_stalls_the_hold(self, tmp_path):
        """Another finger loaded past its own goal floor is a second
        force folded into this finger's level, so it stops the capture
        and the screen says which finger it is."""
        eng, sc = self._at_press_phase(tmp_path)
        lo, hi = sc._band("right", 0)
        vals = list(RESTING)
        vals[0] = RESTING[0] + (lo + hi) / 2      # correct finger, in band
        vals[2] = RESTING[2] + sc._band("right", 2)[0] + 20
        self._drive(eng, sc, vals)
        assert sc._wrong == 2                     # the ring finger
        assert not sc._in_zone
        assert not sc._landed
        assert sc._hold == 0.0

    def test_a_resting_neighbour_is_not_called_a_wrong_finger(self,
                                                              tmp_path):
        eng, sc = self._at_press_phase(tmp_path)
        lo, hi = sc._band("right", 0)
        vals = list(RESTING)
        vals[0] = RESTING[0] + (lo + hi) / 2
        self._drive(eng, sc, vals, steps=60)
        assert sc._wrong is None
        assert sc._landed

    def test_under_the_band_never_fills_the_ring(self, tmp_path):
        eng, sc = self._at_press_phase(tmp_path)
        lo, _ = sc._band("right", 0)
        vals = list(RESTING)
        vals[0] = RESTING[0] + lo * 0.5
        self._drive(eng, sc, vals)
        assert sc._hold == 0.0
        assert not sc._landed


# ---- the quiet gate on the two rest captures -----------------------------

class TestQuietGate:
    """A rest capture taken while a finger is still down averages that
    press into the zero, and every threshold in the session is then
    built on it. So the capture starts itself, and only once the
    sensors agree nothing is happening."""

    def _screen(self, tmp_path, hand="right"):
        eng = _engine(tmp_path, hand=hand)
        eng.maybe_start_quick_calibration(lambda: None)
        return eng, eng.screen_obj

    def _feed(self, sc, vals, n=90, t0=0.0, dt=0.01):
        t = t0
        for _ in range(n):
            sc.on_sample(t, tuple(vals))
            t += dt
        return t

    def test_a_loaded_lane_blocks_the_capture_and_is_named(self, tmp_path):
        from finger_rehab.ui import quick_calibration_screen as q
        eng, sc = self._screen(tmp_path)
        t = self._feed(sc, EMPTY)                 # establishes the floor
        down = list(EMPTY)
        down[2] += 40                             # ring finger still on
        t = self._feed(sc, down, t0=t)
        assert sc._blockers()[0] == ("right", 2)
        assert not sc._settled()
        for _ in range(30):
            sc.update(0.02)
        assert not sc._collecting
        assert sc.phase == q.PHASE_OFF

    def test_it_starts_itself_once_the_lane_comes_off(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        t = self._feed(sc, EMPTY)
        down = list(EMPTY)
        down[2] += 40
        t = self._feed(sc, down, t0=t)
        sc.update(0.02)
        assert not sc._collecting
        # Finger lifts, readings settle back onto the floor.
        t = self._feed(sc, EMPTY, t0=t)
        assert sc._settled()
        sc.update(0.02)                           # starts the quiet clock
        assert sc._quiet_since > 0
        assert not sc._collecting                 # not long enough yet
        sc._quiet_since -= q_hold() + 0.1
        sc.update(0.02)
        assert sc._collecting

    def test_a_moving_reading_is_not_quiet(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        t = 0.0
        for k in range(90):                       # ramping, not settled
            sc.on_sample(t, tuple(v + k * 0.5 for v in EMPTY))
            t += 0.01
        assert not sc._settled()
        for _ in range(30):
            sc.update(0.02)
        assert not sc._collecting

    def test_a_silent_device_says_so_instead_of_waiting(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        assert sc._stale()
        assert not sc._settled()
        sc.update(0.02)
        assert not sc._collecting

    def test_the_resting_step_names_a_finger_that_is_pressing(self,
                                                              tmp_path):
        """On step 2 the zero is known, so a pad loaded past what the
        maths can carry is a press, and it is named rather than
        averaged in as "rest"."""
        from finger_rehab.ui import quick_calibration_screen as q
        eng, sc = self._screen(tmp_path)
        _finish_rest_step(eng, sc, EMPTY)
        assert sc.phase == q.PHASE_REST
        lean = list(RESTING)
        lean[1] += 90                             # middle finger pushing
        self._feed(sc, lean)
        assert sc._blockers()[0] == ("right", 1)
        assert not sc._settled()
        for _ in range(30):
            sc.update(0.02)
        assert not sc._collecting
        assert sc.phase == q.PHASE_REST
        # Relaxed, it goes ahead.
        self._feed(sc, RESTING)
        assert sc._blockers() == []
        assert sc._settled()

    def test_bilateral_blocks_on_either_board(self, tmp_path):
        eng, sc = self._screen(tmp_path, hand="both")
        t = self._feed(sc, EMPTY * 2)
        down = EMPTY * 2
        down = list(down)
        down[7] += 40                             # LEFT pinky
        self._feed(sc, down, t0=t)
        assert sc._blockers()[0] == ("left", 3)
        assert not sc._settled()


def q_hold() -> float:
    from finger_rehab.ui import quick_calibration_screen as q
    return q.QUIET_HOLD_S


class TestSettleScope:
    def test_the_other_hand_cannot_hold_up_this_hands_capture(self,
                                                              tmp_path):
        """A bilateral rig sends all eight sensors whichever hand is
        being calibrated. A left-only run watching the right board would
        wait on a hand that is not in the run at all."""
        eng = _engine(tmp_path, hand="both")
        eng.apply_calibration(_usable_profile("right"))
        eng._session_cal_hands = {"right"}
        assert eng.maybe_start_quick_calibration(lambda: None)
        sc = eng.screen_obj
        assert sc.hands == ["left"]
        t = 0.0
        for k in range(90):
            vals = list(EMPTY) + list(EMPTY)      # right then left
            vals[1] += k * 3.0                    # RIGHT middle moving
            sc.on_sample(t, tuple(vals))
            t += 0.01
        assert sc._settled()
        assert sc._blockers() == []


class TestOneMessagePerFrame:
    """The screen's own rule: it says the ONE thing to do next and
    nothing else competes with it. Two colour choices used to break
    that, and both are cheap to get wrong again."""

    def _screen(self, tmp_path, hand="right"):
        eng = _engine(tmp_path, hand=hand)
        eng.maybe_start_quick_calibration(lambda: None)
        return eng, eng.screen_obj

    def test_a_second_finger_down_takes_the_bar_out_of_the_goal(
            self, tmp_path):
        """A press sitting inside the band while another finger leans
        on its pad is not being counted: the hold ring stops and the
        line says which finger is wrong. So the bar must not read
        green underneath that. It did, because the fill only looked at
        the target finger's own level."""
        eng, sc = self._screen(tmp_path)
        th = eng.theme
        lo, hi = 22.0, 88.0
        mid = (lo + hi) / 2
        sc._wrong = None
        assert sc._fill_colour(lo, hi, mid) == th.success
        sc._wrong = 1
        assert sc._fill_colour(lo, hi, mid) == th.warning, (
            "the bar still says 'that's it' while the screen says "
            "'wrong finger'")
        # The other two zones are unchanged.
        sc._wrong = None
        assert sc._fill_colour(lo, hi, hi + 30) == th.warning
        assert sc._fill_colour(lo, hi, lo - 10) == sc._too_light_colour()

    def test_a_settled_lane_never_draws_in_the_alert_colour(self,
                                                            tmp_path):
        """theme.warning means "this lane is holding the capture up".
        The pinky's lane colour is byte-identical to theme.warning in
        both shipped colour themes, so at the old fade a quiet pinky
        drew in exactly the alert colour and only the tick beside it
        said otherwise."""
        from finger_rehab.hardware.calibration_profile import FINGER_NAMES
        from finger_rehab.ui.theme import THEMES
        eng, sc = self._screen(tmp_path)
        for name, theme in THEMES.items():
            sc.theme = theme
            for i in range(N_FINGERS):
                quiet = sc._quiet_trace_colour(i)
                assert quiet != theme.warning, (
                    f"{name}: a settled {FINGER_NAMES[i]} draws in the "
                    "alert colour")
                # Not a near miss either: the two have to be tellable
                # apart down a column of four rows at a glance.
                gap = sum(abs(a - b)
                          for a, b in zip(quiet, theme.warning))
                assert gap >= 60, (
                    f"{name}: settled {FINGER_NAMES[i]} is only {gap} "
                    "away from the alert colour")
