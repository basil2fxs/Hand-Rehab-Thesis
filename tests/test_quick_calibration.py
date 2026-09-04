"""The gamified quick calibration that runs when a session starts.

What has to hold, in order of how expensive it would be to get wrong:

  - the trigger rule: calibration is a session event and it runs when
    the session starts. Logging in measures every hand the attached
    boards can serve, left first, then hands over to the hub; a board
    plugged in later in the session runs the same flow for its own
    hand alone, triggered by the connection. Games never open it. The
    memory is session state on the engine, cleared at session end,
    never disk. A keyboard session never sees it at all (there is no
    force to calibrate);
  - the guard left on the game path: a hand with no measured profile
    at all would be scored against config defaults, so the game stops
    and says so instead of recording it quietly;
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


class _FakeHand:
    """One board on the fake rig: which hand it drives, on what port."""

    def __init__(self, hand: str, port: str) -> None:
        self.hand = hand
        self.port = port


class FakeFsrSource(Source):
    """A hardware-shaped source the tests drive by hand. Samples are
    queued by the test and drained by the engine's own pump, so the
    wiring under test is the real one.

    hand_modes_available is the boards on the rig, which is what the
    login pass reads to decide which hands to calibrate: one entry is
    a single board, all three is a two-board rig.
    """

    def __init__(self, hands=("right",)) -> None:
        self.queued = []
        self.port = "/dev/fake"
        self.hands_served = list(hands)
        # Same shape as MultiSerialSource.hands, so the engine's
        # hotplug bookkeeping reads this rig the way it reads a real
        # one.
        self.hands = [_FakeHand(h, f"/dev/fake-{h}")
                      for h in self.hands_served]

    @property
    def hand_modes_available(self) -> set:
        if len(self.hands_served) == 1:
            return {self.hands_served[0]}
        return {"right", "left", "both"}

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
    """Engine on a rig whose boards match `hand`: one board for left
    or right, two for both."""
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("bilateral", {})["hand"] = hand
    cfg.data.setdefault("game", {})["mode"] = "adaptive"
    boards = ("left", "right") if hand == "both" else (hand,)
    eng = GameEngine(cfg, source or FakeFsrSource(boards))
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


# ---- when the flow runs --------------------------------------------------

def _save(tmp_path: Path, hand: str) -> CalibrationProfile:
    """A usable profile on disk for one hand, as a finished pass would
    have left it."""
    prof = _usable_profile(hand)
    prof.save(tmp_path / f"config/calibration/current_{hand}.json")
    return prof


class TestLoginTrigger:
    """Calibration is a session event, and this is the session
    starting. Logging in measures every hand the rig can serve, then
    hands over to the hub."""

    def test_one_board_calibrates_that_hand_then_hubs(self, tmp_path):
        eng = _engine(tmp_path, hand="right")
        eng.begin_session("P1", "63")
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["right"]
        # The continuation is the hub, not a game.
        eng.screen_obj._skip()
        assert eng.screen_obj is eng._screens["mode_select"]

    def test_two_boards_calibrate_both_hands_left_first(self, tmp_path):
        eng = _engine(tmp_path, hand="both")
        eng.begin_session("P1", "63")
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["left", "right"]
        eng.screen_obj._skip()
        assert eng.screen_obj is eng._screens["mode_select"]
        assert eng._session_cal_hands == {"left", "right"}

    def test_a_left_only_rig_calibrates_the_left_hand(self, tmp_path):
        eng = _engine(tmp_path, hand="left")
        eng.begin_session("P1", "")
        assert eng.screen_obj.hands == ["left"]

    def test_the_boards_decide_it_not_the_saved_hand_mode(self, tmp_path):
        """Both boards attached, config remembering a right-hand
        session. Both hands still get measured: either could be picked
        later and neither game may stop to ask."""
        eng = _engine(tmp_path, hand="both")
        eng.hand_mode = "right"
        eng.begin_session("P1", "")
        assert eng.screen_obj.hands == ["left", "right"]

    def test_keyboard_login_skips_silently(self, tmp_path):
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["mode_select"]
        assert not (tmp_path / "config/calibration").exists()

    def test_turned_off_in_config_logs_straight_into_the_hub(self, tmp_path):
        eng = _engine(tmp_path)
        eng.cfg.data.setdefault("quick_cal", {})["enabled"] = False
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["mode_select"]

    def test_a_returning_player_still_gets_the_pass(self, tmp_path):
        """A saved profile feeds the detectors on the way past, but it
        does not stand in for the session's own measurement."""
        eng = _engine(tmp_path)
        prof = _save(tmp_path, "right")
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["quick_cal"]
        det = eng.detectors["right"]
        assert det.cal.on_delta[:N_FINGERS] == prof.on_delta()

    def test_skip_at_login_proceeds_and_is_remembered(self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        assert eng.screen_obj is eng._screens["mode_select"]
        assert eng._session_cal_hands == {"right"}
        # Skip writes nothing: any profile saved before is untouched
        # and none is invented.
        assert not (tmp_path
                    / "config/calibration/current_right.json").exists()

    def test_a_skipped_hand_is_not_asked_again_this_session(self, tmp_path):
        eng = _engine(tmp_path)
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        # Nothing else in the session re-opens it for that hand.
        assert eng.quick_cal_hands_needed() == []

    def test_abandoning_the_login_pass_marks_nothing(self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_session("P1", "")
        eng._handle_escape()          # raises the guard
        eng._handle_escape()          # confirms
        assert eng.screen_obj is eng._screens["mode_select"]
        assert eng._session_cal_hands == set()

    def test_session_end_clears_the_memory_and_the_next_login_runs(
            self, tmp_path):
        eng = _engine(tmp_path)
        eng.begin_session("P1", "")
        eng._session_cal_hands = {"left", "right"}
        eng.end_session()
        assert eng._session_cal_hands == set()
        eng.begin_session("P2", "")
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng._session_cal_hands == set()


class TestBoardJoiningMidSession:
    """A board plugged in after login could not have been in the login
    pass, so the connection itself triggers its calibration. One hand,
    no game involved."""

    def _join(self, eng, hands):
        """Drive the engine's reaction to a rebuilt source, with the
        rebuild itself stubbed: what is under test is the reaction."""
        new_src = FakeFsrSource(tuple(hands))

        def fake_reconnect():
            eng.source = new_src
            return "Connected: fake."

        eng.reconnect_source = fake_reconnect
        eng._apply_autoconnect()

    def test_a_second_board_calibrates_that_hand_alone(self, tmp_path):
        eng = _engine(tmp_path, hand="right")
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        assert eng.screen_obj is eng._screens["mode_select"]
        self._join(eng, ["right", "left"])
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["left"]

    def test_it_lands_back_on_the_screen_it_interrupted(self, tmp_path):
        eng = _engine(tmp_path, hand="right")
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        eng.screen_obj = eng._screens["setup"]
        self._join(eng, ["right", "left"])
        eng.screen_obj._skip()
        assert eng.screen_obj is eng._screens["setup"]
        assert eng._session_cal_hands == {"left", "right"}

    def test_the_first_board_of_a_keyboard_session_calibrates(self, tmp_path):
        """Logged in with no hardware, so the login pass had nothing to
        measure. The board that turns up still gets its pass."""
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["mode_select"]
        self._join(eng, ["right"])
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["right"]

    def test_no_session_means_no_flow(self, tmp_path):
        """Nobody logged in: the login screen's own pass is seconds
        away and covers the new board."""
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        eng.show_title()
        self._join(eng, ["right"])
        assert eng.screen_obj is eng._screens["title"]
        assert eng._session_cal_hands == set()

    class _FakeWatcher:
        """Stands in for PortWatcher: a port list and a generation the
        engine can compare against."""

        def __init__(self, ports):
            self.ports = list(ports)
            self.generation = 1

    def test_a_board_arriving_mid_calibration_waits_for_it(self, tmp_path):
        """The running flow is reading live samples off the source the
        rebuild would swap out, and its captures are half taken. So the
        join queues and lands the moment the flow hands over."""
        eng = _engine(tmp_path, hand="right")
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["quick_cal"]
        applied = []
        eng._apply_autoconnect = lambda: applied.append(1)
        eng._autoconnect_wanted = lambda ports: True
        eng.port_watcher = self._FakeWatcher(["/dev/a", "/dev/b"])
        eng.maybe_autoconnect()
        assert applied == []
        assert eng._pending_autoconnect is True
        assert "calibration" in eng.autoconnect_notice()
        eng.screen_obj._skip()
        eng.maybe_autoconnect()
        assert applied == [1]

    def test_a_hand_already_measured_this_session_is_left_alone(
            self, tmp_path):
        """A board unplugged and plugged back in was calibrated at
        login; asking again would be a nag."""
        eng = _engine(tmp_path, hand="right")
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        eng._calibrate_joined_hands(["right"])
        assert eng.screen_obj is eng._screens["mode_select"]


class TestGamesNeverOpenTheFlow:
    """The old first-game gate is gone, not moved. After login, no
    start path opens the calibration screen."""

    def _ready(self, tmp_path, hand="right"):
        """Logged in with the login pass skipped over saved profiles,
        which is the ordinary state a game starts in."""
        eng = _engine(tmp_path, hand=hand)
        for h in (("left", "right") if hand == "both" else (hand,)):
            _save(tmp_path, h)
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        return eng

    def test_the_hand_picker_starts_the_block_straight_away(self, tmp_path):
        eng = self._ready(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        assert begun == [1]
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_mirror_starts_straight_away(self, tmp_path):
        eng = self._ready(tmp_path, hand="both")
        begun = []
        eng.begin_mirror_block = lambda: begun.append(1)
        eng._screens["mode_select"]._pick("mirror")
        assert begun == [1]
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_a_hand_mode_change_mid_session_asks_nothing(self, tmp_path):
        """The old rule ran the flow the first time a game needed a
        hand, so a right-handed game followed by a bilateral one
        opened it again. Login covered both boards, so nothing does."""
        eng = self._ready(tmp_path, hand="both")
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        eng._screens["setup"]._pick("both")
        assert begun == [1, 1]
        assert eng.screen_obj is not eng._screens["quick_cal"]

    def test_a_mirror_retry_opens_nothing(self, tmp_path):
        eng = self._ready(tmp_path, hand="both")
        begun = []
        eng.begin_mirror_block = lambda: begun.append(1)
        eng.current_block = "mirror"
        eng.retry_last_block()
        assert begun == [1]
        assert eng.screen_obj is not eng._screens["quick_cal"]


class TestUncalibratedGuard:
    """The one calibration check left on the game path. A hand with no
    measured profile at all (login pass skipped, nothing saved) would
    have its force scored against config defaults measured on somebody
    else's hand, so the game stops and the clinician chooses."""

    def _skipped_with_nothing_saved(self, tmp_path, hand="right"):
        eng = _engine(tmp_path, hand=hand)
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        return eng

    def test_it_stops_the_game_and_names_the_hand(self, tmp_path):
        eng = self._skipped_with_nothing_saved(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        assert begun == []
        dlg = eng._exit_confirm
        assert dlg is not None
        assert dlg.question == "Right hand has no calibration"
        assert dlg.safe_btn.label == "Calibrate now"
        assert dlg.danger_btn.label == "Play anyway"

    def test_calibrate_now_measures_then_starts_the_game(self, tmp_path):
        eng = self._skipped_with_nothing_saved(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        eng._exit_confirm.safe_btn.on_click()
        assert eng._exit_confirm is None
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["right"]
        assert begun == []
        # Whatever the flow ends with, the game it was holding starts.
        eng.screen_obj._skip()
        assert begun == [1]

    def test_calibrate_now_works_with_the_automatic_pass_switched_off(
            self, tmp_path):
        """The click asks for the flow directly, so the config switch
        that turns the login pass off does not silence it."""
        eng = _engine(tmp_path)
        eng.cfg.data.setdefault("quick_cal", {})["enabled"] = False
        eng.begin_session("P1", "")
        assert eng.screen_obj is eng._screens["mode_select"]
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        eng._exit_confirm.safe_btn.on_click()
        assert eng.screen_obj is eng._screens["quick_cal"]
        assert eng.screen_obj.hands == ["right"]

    def test_play_anyway_starts_it_and_asks_once_per_session(self, tmp_path):
        eng = self._skipped_with_nothing_saved(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        eng._exit_confirm.danger_btn.on_click()
        assert begun == [1]
        assert eng._exit_confirm is None
        eng._screens["setup"]._pick("right")
        assert begun == [1, 1]
        assert eng._exit_confirm is None

    def test_esc_backs_out_of_the_question_and_starts_nothing(self, tmp_path):
        eng = self._skipped_with_nothing_saved(tmp_path)
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        eng._handle_escape()
        assert eng._exit_confirm is None
        assert begun == []

    def test_a_saved_profile_means_no_question(self, tmp_path):
        eng = _engine(tmp_path)
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        assert begun == [1]
        assert eng._exit_confirm is None

    def test_only_the_hand_without_a_profile_is_named(self, tmp_path):
        eng = _engine(tmp_path, hand="both")
        _save(tmp_path, "right")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        begun = []
        eng.begin_mirror_block = lambda: begun.append(1)
        eng._screens["mode_select"]._pick("mirror")
        assert begun == []
        assert eng._exit_confirm.question == "Left hand has no calibration"

    def test_a_keyboard_session_is_never_asked(self, tmp_path):
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = _engine(tmp_path, source=KeyboardOnlySource())
        eng.begin_session("P1", "")
        begun = []
        eng.begin_adaptive_block = lambda: begun.append(1)
        eng._screens["setup"]._pick("right")
        assert begun == [1]
        assert eng._exit_confirm is None

    def test_an_unusable_saved_profile_does_not_count(self, tmp_path):
        eng = _engine(tmp_path)
        bad = CalibrationProfile(
            hand="right", empty=list(EMPTY),
            empty_noise=[1.1] * N_FINGERS,
            resting=list(RESTING),
            press=[RESTING[i] + 5 for i in range(N_FINGERS)])
        assert not bad.usable()[0]
        bad.save(tmp_path / "config/calibration/current_right.json")
        eng.begin_session("P1", "")
        eng.screen_obj._skip()
        assert eng.uncalibrated_hands("right") == ["right"]


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

    def test_a_login_measurement_survives_a_hand_mode_change(self,
                                                             tmp_path):
        """Now that the measuring happens at login, a hand can be
        measured while the session is set to the other one. The
        detector rebuild that follows a hand pick must put the
        measured thresholds back, or the block runs on config
        defaults while the metadata still records a calibration."""
        eng = _engine(tmp_path, hand="both")
        eng.begin_session("P1", "")
        sc = eng.screen_obj
        _run_whole_flow(eng, sc)
        sc._finish()
        measured = {h: eng.calibration_profiles[h].on_delta()
                    for h in ("left", "right")}
        eng.set_hand_mode("right")
        eng.set_hand_mode("both")
        for hand in ("left", "right"):
            det = eng.detectors[hand]
            assert det.cal.on_delta[:N_FINGERS] == measured[hand]

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
        # The lead the step owes the player runs on top of the quiet
        # clock, so a settled rig still waits it out. Backdated here
        # because the point of this test is the QUIET gate; the lead
        # has TestLeadAndRing to itself.
        sc._phase_started_at -= sc._lead_s() + 0.1
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


class TestLeadAndRing:
    """The rest steps give the player time before they take anything.

    The captures start themselves the moment the sensors agree nothing
    is happening, and with hands already off the pads that agreement
    is there in a frame: the step would flash up and be measuring
    before the instruction had been read. So each step owes a lead,
    counted down on the ring, and only then may it capture.
    """

    def _screen(self, tmp_path, hand="right"):
        eng = _engine(tmp_path, hand=hand)
        eng.maybe_start_quick_calibration(lambda: None)
        return eng, eng.screen_obj

    def _settle(self, sc, vals, n=90, t0=0.0, dt=0.01):
        t = t0
        for _ in range(n):
            sc.on_sample(t, tuple(vals))
            t += dt
        return t

    def test_a_settled_rig_still_waits_out_the_lead(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        self._settle(sc, EMPTY)
        assert sc._settled()
        assert sc._lead_left() > 0
        for _ in range(40):                       # well past QUIET_HOLD_S
            sc.update(0.05)
        assert not sc._collecting, (
            "the capture started before the player was given time")
        sc._phase_started_at -= sc._lead_s() + 0.1
        sc._quiet_since -= q_hold() + 0.1
        sc.update(0.02)
        assert sc._collecting

    def test_the_resting_step_gets_its_own_lead(self, tmp_path):
        from finger_rehab.ui import quick_calibration_screen as q
        eng, sc = self._screen(tmp_path)
        _finish_rest_step(eng, sc, EMPTY)
        assert sc.phase == q.PHASE_REST
        # Entering the step restarts the clock, so step two is as
        # readable as step one.
        assert sc._lead_left() > 0

    def test_the_lead_is_a_config_knob(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        eng.cfg.data.setdefault("quick_cal", {})["lead_s"] = 0.0
        assert sc._lead_s() == 0.0
        assert sc._lead_left() == 0.0

    def test_the_ring_counts_the_lead_then_the_capture(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        self._settle(sc, EMPTY)
        left, span, _ = sc._ring_state()
        assert span == sc._lead_s()
        assert 0 < left <= span
        sc._start_collecting()
        left, span, _ = sc._ring_state()
        assert span == sc._rest_capture_s()
        assert 0 < left <= span

    def test_a_lane_still_down_parks_the_ring_and_says_so(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        t = self._settle(sc, EMPTY)
        down = list(EMPTY)
        down[2] += 40
        self._settle(sc, down, t0=t)
        left, span, colour = sc._ring_state()
        assert (left, span) == (0.0, 0.0), (
            "a blocked step must not run a countdown it cannot honour")
        assert colour == eng.theme.warning
        head, sub, _ = sc._rest_words()
        assert "RING" in head and sub == ""


class TestRestStepIsFourWords:
    """Somebody holding their hands off a pad cannot read a sentence
    while doing it. Every state on the two rest steps is a thing to do
    plus, at most, two words saying how; the ring carries the timing
    and the hand picture carries which finger."""

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

    def _states(self, eng, sc):
        """Every state the two rest steps can be in, as (label, words)."""
        from finger_rehab.ui import quick_calibration_screen as q
        out = [("no signal", sc._rest_words())]
        self._feed(sc, EMPTY)
        out.append(("hands off", sc._rest_words()))
        sc._collecting = True
        out.append(("hands off, measuring", sc._rest_words()))
        sc._collecting = False
        down = list(EMPTY)
        down[2] += 40
        self._feed(sc, down)
        out.append(("a lane still down", sc._rest_words()))
        _finish_rest_step(eng, sc, EMPTY)
        assert sc.phase == q.PHASE_REST
        self._feed(sc, RESTING)
        out.append(("hands resting", sc._rest_words()))
        sc._collecting = True
        out.append(("resting, measuring", sc._rest_words()))
        sc._collecting = False
        lean = list(RESTING)
        lean[1] += 90
        self._feed(sc, lean)
        out.append(("a finger pressing", sc._rest_words()))
        return out

    def test_no_state_spends_more_than_four_words(self, tmp_path):
        eng, sc = self._screen(tmp_path)
        for label, (head, sub, _colour) in self._states(eng, sc):
            words = len(head.split()) + len(sub.split())
            assert head, f"{label}: nothing to do"
            assert words <= 4, (
                f"{label}: {words} words on a step that gets four "
                f"({head!r} / {sub!r})")

    def test_the_state_is_the_headline_and_it_names_the_problem(
            self, tmp_path):
        eng, sc = self._screen(tmp_path)
        seen = dict(self._states(eng, sc))
        assert seen["hands off"][0] == "HANDS OFF"
        assert seen["hands resting"][0] == "HANDS RESTING"
        assert "still" in seen["hands off, measuring"][1]
        assert seen["a lane still down"][0] == "LIFT YOUR RING FINGER"
        assert seen["a finger pressing"][0] == "RELAX YOUR MIDDLE FINGER"
        assert seen["no signal"][2] == eng.theme.warning

    def test_the_step_stopped_being_a_wall_of_readouts(self, tmp_path):
        """It used to draw a headline, a body line, a hand picture, a
        panel of four live sensor traces each with a number and a tick,
        and a status strip. The traces were a therapist's diagnostic on
        a patient's screen, and the clinical calibration on the menu is
        where that job lives."""
        import pygame
        from finger_rehab.ui import quick_calibration_screen as q
        eng, sc = self._screen(tmp_path)
        self._feed(sc, EMPTY)
        drawn: list[str] = []
        original = q.draw_text
        original_bold = q.QuickCalibrationScreen._bold

        def rec_text(surf, text, pos, *a, **k):
            drawn.append(str(text))
            return original(surf, text, pos, *a, **k)

        def rec_bold(self, surf, text, pos, pt, colour, centre=True):
            drawn.append(str(text))
            return original_bold(self, surf, text, pos, pt, colour,
                                 centre=centre)

        q.draw_text = rec_text
        q.QuickCalibrationScreen._bold = rec_bold
        try:
            sc.draw(pygame.Surface((1280, 800)))
        finally:
            q.draw_text = original
            q.QuickCalibrationScreen._bold = original_bold
        assert len(drawn) <= 12, (
            f"{len(drawn)} pieces of text on a step that says one "
            f"thing: {drawn}")
        assert "HANDS OFF" in drawn
