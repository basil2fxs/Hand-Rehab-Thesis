"""Calibration profile maths, buzzer channel remapping, and the guided
screen flow."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from rehab.hardware.calibration_profile import (
    CalibrationProfile, N_FINGERS, PRESS_FRACTION, MIN_USABLE_GAP,
)


# Measured on the device, 29 July 2026. Counts above the empty reading.
REST = [2.5, 8.9, 11.5, 30.7]
PRESS = [51.5, 40.9, 41.5, 145.7]
EMPTY = [245.0, 250.0, 248.0, 235.0]
NOISE = [1.1, 1.1, 1.1, 1.1]


def make_profile(**kw) -> CalibrationProfile:
    p = CalibrationProfile(
        empty=list(EMPTY),
        empty_noise=list(NOISE),
        resting=[EMPTY[i] + REST[i] for i in range(N_FINGERS)],
        press=[EMPTY[i] + PRESS[i] for i in range(N_FINGERS)],
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


class TestProfileMaths:
    def test_gap_is_resting_to_press(self):
        p = make_profile()
        for i in range(N_FINGERS):
            assert p.gap()[i] == pytest.approx(PRESS[i] - REST[i], abs=0.01)

    def test_preload_is_empty_to_resting(self):
        p = make_profile()
        for i in range(N_FINGERS):
            assert p.preload()[i] == pytest.approx(REST[i], abs=0.01)

    def test_threshold_does_not_double_count_the_resting_load(self):
        """The bug this whole change fixes. The baseline already sits at
        the resting level, so a trigger of (resting + 40% of gap) makes
        every finger harder than intended and the pinky unusable."""
        p = make_profile()
        for i in range(N_FINGERS):
            double_counted = REST[i] + PRESS_FRACTION * p.gap()[i]
            assert p.on_delta()[i] < double_counted + 0.5

    def test_pinky_trigger_is_under_the_healthy_maximum(self):
        """Demouche records 5.60 N as the maximum for a HEALTHY little
        finger. A trigger above that cannot be reached by the patients
        this device is for. The old 77-count value was 6.77 N."""
        p = make_profile()
        n_per_count = 0.0879
        assert p.on_delta()[3] * n_per_count < 5.60

    def test_release_point_never_falls_to_or_below_the_baseline(self):
        """Regression. FSRDetector clamps off_thr to (on_thr - 10). If
        on_delta is under 10 that puts the release point below a resting
        hand, so a finger that registers one press can only release by
        lifting off the device. It latches for the rest of the block and
        every later trial on it is scored a miss, which reads as a
        paralysed finger rather than a threshold fault."""
        from rehab.hardware.calibration_profile import DETECTOR_HYSTERESIS
        for gap in range(MIN_USABLE_GAP, 200, 3):
            for noise in (0.2, 1.1, 3.0):
                for preload in (0.0, 2.5, 30.7):
                    p = CalibrationProfile(
                        empty=[245.0] * 4, empty_noise=[noise] * 4,
                        resting=[245.0 + preload] * 4,
                        press=[245.0 + preload + gap] * 4)
                    on, off = p.on_delta()[0], p.off_delta()[0]
                    effective = min(off, on - DETECTOR_HYSTERESIS)
                    assert effective > 0, (
                        f"gap={gap} noise={noise} preload={preload}: "
                        f"on={on} off={off} puts release at base{effective:+d}")

    def test_latching_does_not_happen_end_to_end(self):
        """Drive the real detector: press, then rest, and confirm the
        finger actually releases."""
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        p = make_profile()
        cal = Calibration(num_sensors=4, on_delta=p.on_delta(),
                          off_delta=p.off_delta(), baseline_alpha=0.0005,
                          value_alpha=1.0, debounce_ms=0,
                          abs_on_min=[0] * 4, abs_off_max=[10000] * 4)
        det = FSRDetector(cal)
        rest = p.resting[0]
        t = 0.0
        def feed(v, secs):
            nonlocal t
            for _ in range(int(secs * 200)):
                t += 1 / 200
                det.feed(t, (v,) * 4)
        feed(rest, 5)
        feed(rest + 300, 0.5)
        assert det.pressed[0], "press should register"
        feed(rest, 5)
        assert not det.pressed[0], "finger latched: never released back to rest"

    def test_a_gap_too_small_for_a_valid_threshold_is_rejected(self):
        p = make_profile()
        for i in range(N_FINGERS):
            p.press[i] = p.resting[i] + (MIN_USABLE_GAP - 1)
        ok, problems = p.usable()
        assert not ok and len(problems) >= N_FINGERS

    def test_release_sits_below_press(self):
        p = make_profile()
        for i in range(N_FINGERS):
            assert p.off_delta()[i] < p.on_delta()[i], (
                f"{i}: release must be below press or the finger chatters")

    def test_noise_floor_protects_a_finger_that_barely_moved(self):
        p = make_profile()
        p.press[1] = p.resting[1] + 2.0       # 2 counts of travel
        p.empty_noise[1] = 3.0
        assert p.on_delta()[1] >= 3.0 * 8.0

    def test_preload_floor_covers_a_hand_landing_mid_block(self):
        """If a block starts with the hand off the device, the baseline
        initialises to empty and the hand landing looks like a rise. No
        trigger may sit below its own resting load."""
        p = make_profile()
        for i in range(N_FINGERS):
            assert p.on_delta()[i] > p.preload()[i]

    def test_multi_finger_deficit(self):
        p = make_profile()
        # Each finger reaches only half its solo press when all four go.
        p.press_all = [p.resting[i] + p.gap()[i] * 0.5
                       for i in range(N_FINGERS)]
        assert p.multi_finger_deficit() == pytest.approx(0.5, abs=0.001)

    def test_multi_finger_deficit_is_none_when_step_skipped(self):
        assert make_profile().multi_finger_deficit() is None

    def test_usable_flags_a_finger_with_no_travel(self):
        p = make_profile()
        p.press[2] = p.resting[2] + 3.0
        ok, problems = p.usable()
        assert not ok and any("ring" in s for s in problems)

    def test_usable_flags_a_dead_sensor(self):
        p = make_profile()
        p.empty[0] = 0.0
        ok, problems = p.usable()
        assert not ok and any("index" in s for s in problems)

    def test_good_profile_is_usable(self):
        assert make_profile().usable()[0] is True


class TestPersistence:
    def test_round_trip(self, tmp_path: Path):
        p = make_profile(notes="bench check")
        p.press_all = [p.resting[i] + 5 for i in range(N_FINGERS)]
        p.save(tmp_path / "cal.json")
        back = CalibrationProfile.load(tmp_path / "cal.json")
        assert back.resting == p.resting
        assert back.press_all == p.press_all
        assert back.notes == "bench check"
        assert back.on_delta() == p.on_delta()

    def test_missing_file_returns_none(self, tmp_path: Path):
        assert CalibrationProfile.load(tmp_path / "nope.json") is None

    def test_corrupt_file_returns_none(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{not json")
        assert CalibrationProfile.load(f) is None

    def test_unknown_keys_are_ignored(self, tmp_path: Path):
        f = tmp_path / "future.json"
        f.write_text(json.dumps({"resting": [1, 2, 3, 4],
                                 "some_future_field": 99}))
        back = CalibrationProfile.load(f)
        assert back is not None and back.resting == [1, 2, 3, 4]

    def test_no_partial_file_left_when_save_fails(self, tmp_path: Path):
        p = make_profile()
        target = tmp_path / "sub" / "cal.json"
        p.save(target)
        assert not list(target.parent.glob("*.tmp"))

    def test_summary_carries_what_analysis_needs(self):
        s = make_profile().summary()
        for key in ("empty", "resting", "press", "gap", "preload",
                    "on_delta", "off_delta", "created_at"):
            assert key in s, f"summary is missing {key}"

    def test_summary_is_json_serialisable(self):
        """It goes straight into metadata.json, so it must survive
        json.dumps without a custom encoder."""
        json.dumps(make_profile().summary())


class TestBuzzerChannelMap:
    """Arduino_20251111.ino is final and maps STIM:1..4 onto pins
    3,4,5,6 in that order. If a motor is wired elsewhere the host has
    to send a different channel, because the sketch is not changing."""

    def _engine(self, channel_map):
        from rehab.game.engine import GameEngine

        class Cfg:
            def __init__(self, cmap):
                self._cmap = cmap

            def get(self, key, default=None):
                if key == "motor.channel_map":
                    return self._cmap
                if key == "fsr.num_sensors_per_hand":
                    return 4
                return default

        e = GameEngine.__new__(GameEngine)
        e.cfg = Cfg(channel_map)
        return e

    def test_straight_through_by_default(self):
        e = self._engine([1, 2, 3, 4])
        assert [e._stim_channel(i) for i in range(4)] == [1, 2, 3, 4]

    def test_remap_sends_the_channel_that_reaches_the_finger(self):
        # Wiring found by calibration: the index motor answers to
        # channel 4, the pinky to channel 1.
        e = self._engine([4, 2, 3, 1])
        assert e._stim_channel(0) == 4
        assert e._stim_channel(3) == 1

    def test_bad_map_falls_back_to_straight_through(self):
        for bad in (None, [], [0, 0, 0, 0], [9, 9, 9, 9], "nonsense",
                    [1, 2], [1, 2, "x", 4]):
            e = self._engine(bad)
            assert e._stim_channel(1) in (2,), f"{bad!r} broke the fallback"

    def test_second_hand_keeps_its_global_lane_offset(self):
        """Lanes stay global (1..8). multi_serial splits them across the
        two boards, so remapping must not collapse the left hand onto
        the right one."""
        e = self._engine([4, 3, 2, 1])
        assert e._stim_channel(0) == 4          # right index
        assert e._stim_channel(4) == 8          # left index, offset by 4
        assert e._stim_channel(7) == 5          # left pinky

    def test_straight_through_map_matches_the_old_numbering(self):
        e = self._engine([1, 2, 3, 4])
        assert [e._stim_channel(i) for i in range(8)] == list(range(1, 9))


class TestScreenFlow:
    """The guided flow, driven headless."""

    def _screen(self):
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.game.engine import GameEngine
        from rehab.ui.theme import THEMES
        from rehab.ui.widgets import Layout
        from rehab.ui.calibration_screen import CalibrationScreen

        sent = []

        class Src:
            port = "/dev/mock"

            def send_command(self, c):
                sent.append(c)
                return True

        class Cfg:
            data = {}

            def get(self, key, default=None):
                return default

            def resolve_path(self, v):
                return Path(v)

            def save_user_overrides(self, o):
                return Path("x")

        e = GameEngine.__new__(GameEngine)
        e.cfg = Cfg()
        e.theme = list(THEMES.values())[0]
        e.layout = Layout(1280, 800, 1.0)
        e.source = Src()
        e.detectors = {}
        e.session = type("S", (), {"participant": "T1"})()
        return CalibrationScreen(e), sent

    def _feed(self, screen, values, n=200):
        for _ in range(n):
            screen.on_sample(0.0, values)

    def test_flow_reaches_review_with_a_saveable_profile(self):
        import rehab.ui.calibration_screen as cs
        screen, _ = self._screen()
        screen._begin()
        assert screen.step == cs.STEP_EMPTY

        screen._start_collecting(0.0)
        self._feed(screen, EMPTY)
        screen.update(0.0)
        assert screen.step == cs.STEP_RESTING

        resting = [EMPTY[i] + REST[i] for i in range(4)]
        screen._start_collecting(0.0)
        self._feed(screen, resting)
        screen.update(0.0)
        assert screen.step == cs.STEP_PRESS

        for i in range(4):
            vals = list(resting)
            vals[i] = EMPTY[i] + PRESS[i]
            screen._start_collecting(0.0)
            self._feed(screen, vals)
            screen.update(0.0)
        assert screen.step == cs.STEP_ALL

        screen._start_collecting(0.0)
        self._feed(screen, [EMPTY[i] + PRESS[i] * 0.6 for i in range(4)])
        screen.update(0.0)
        assert screen.step == cs.STEP_BUZZ

        for _ in range(4):
            screen._record_felt(0)
        assert screen.step == cs.STEP_REVIEW
        assert screen.profile.usable()[0] is True

    def test_a_finger_that_barely_moves_does_not_advance(self):
        """The therapist is asked to press again rather than being let
        through with a threshold that will not work."""
        import rehab.ui.calibration_screen as cs
        screen, _ = self._screen()
        screen._begin()
        screen.profile.resting = list(EMPTY)
        screen.step = cs.STEP_PRESS
        screen.finger_idx = 0
        screen._start_collecting(0.0)
        self._feed(screen, [EMPTY[0] + 2.0] + EMPTY[1:])
        screen.update(0.0)
        assert screen.finger_idx == 0
        assert screen.step == cs.STEP_PRESS

    def test_no_samples_reports_a_disconnected_device(self):
        import rehab.ui.calibration_screen as cs
        screen, _ = self._screen()
        screen._begin()
        screen._start_collecting(0.0)
        screen.update(0.0)
        assert screen.step == cs.STEP_EMPTY
        assert "connected" in screen._status.lower()

    def test_samples_only_collected_while_a_step_is_running(self):
        screen, _ = self._screen()
        self._feed(screen, EMPTY, n=50)
        assert screen._buffer == []

    def test_buzz_sends_the_channel_under_test(self):
        import rehab.ui.calibration_screen as cs
        screen, sent = self._screen()
        screen.step = cs.STEP_BUZZ
        screen.buzz_channel = 3
        screen._buzz_now()
        assert sent and all(c == "STIM:3" for c in sent)

    def test_channel_map_inverts_what_was_felt(self):
        screen, _ = self._screen()
        # Channel 1 was felt on the pinky, channel 4 on the index.
        screen._felt = {1: 3, 2: 1, 3: 2, 4: 0}
        assert screen.channel_map() == [4, 2, 3, 1]

    def test_finger_felt_nothing_keeps_straight_through(self):
        screen, _ = self._screen()
        screen._felt = {1: 0, 2: 1}
        cmap = screen.channel_map()
        assert cmap[0] == 1 and cmap[1] == 2
        assert cmap[2] == 3 and cmap[3] == 4

    def test_every_step_has_an_instruction(self):
        import rehab.ui.calibration_screen as cs
        screen, _ = self._screen()
        for step in (cs.STEP_INTRO, cs.STEP_EMPTY, cs.STEP_RESTING,
                     cs.STEP_PRESS, cs.STEP_ALL, cs.STEP_BUZZ,
                     cs.STEP_REVIEW):
            screen.step = step
            head, body = screen._instruction()
            assert head and body, f"{step} has no instruction"

    def test_back_is_offered_at_every_step(self):
        """Nobody gets trapped part way through the flow."""
        import rehab.ui.calibration_screen as cs
        for step in (cs.STEP_INTRO, cs.STEP_EMPTY, cs.STEP_RESTING,
                     cs.STEP_PRESS, cs.STEP_ALL, cs.STEP_BUZZ,
                     cs.STEP_REVIEW):
            screen, _ = self._screen()
            screen.step = step
            screen._rebuild_buttons()
            assert any(b.label == "Back" for b in screen._buttons), step


class TestApplyToEngine:
    def test_apply_writes_thresholds_and_primes_the_baseline(self):
        from rehab.game.engine import GameEngine
        from rehab.hardware.fsr_detector import Calibration, FSRDetector

        det = FSRDetector(Calibration(num_sensors=4))
        e = GameEngine.__new__(GameEngine)
        e.detectors = {"right": det}

        prof = make_profile()
        GameEngine.apply_calibration(e, prof)

        assert list(det.cal.on_delta) == prof.on_delta()
        assert list(det.cal.off_delta) == prof.off_delta()
        # Baseline primed to the measured resting level, so the first
        # block starts tared instead of chasing the resting load.
        for i in range(4):
            assert det.baseline[i] == pytest.approx(prof.resting[i])
        assert e.calibration_profile is prof

    def test_stamp_writes_the_profile_into_session_metadata(self):
        from rehab.game.engine import GameEngine
        from rehab.data.session import Session

        e = GameEngine.__new__(GameEngine)
        e.session = Session(participant="T1")
        e.calibration_profile = make_profile()
        GameEngine._stamp_calibration(e)
        assert e.session.calibration["on_delta"] == \
            e.calibration_profile.on_delta()

    def test_stamp_is_empty_when_nothing_was_calibrated(self):
        from rehab.game.engine import GameEngine
        from rehab.data.session import Session

        e = GameEngine.__new__(GameEngine)
        e.session = Session(participant="T1")
        GameEngine._stamp_calibration(e)
        assert e.session.calibration == {}


class TestReviewFixes:
    """Regressions for bugs an adversarial review found in the first cut of
    the calibration flow. Each one silently corrupted data rather than
    failing loudly, which is why they get their own tests."""

    def _screen(self, hand="right", n_per_hand=4, root=None):
        import pygame
        import tempfile
        pygame.init()
        pygame.font.init()
        # Writes must never land in the repository. resolve_path below
        # sends everything under this temp root.
        root = Path(root or tempfile.mkdtemp(prefix="cal-test-"))
        from rehab.game.engine import GameEngine
        from rehab.ui.theme import THEMES
        from rehab.ui.widgets import Layout
        from rehab.ui.calibration_screen import CalibrationScreen

        sent = []

        class Src:
            port = "/dev/mock"

            def send_command(self, c):
                sent.append(c)
                return True

        class Cfg:
            data = {}

            def get(self, key, default=None):
                if key == "bilateral.hand":
                    return hand
                if key == "fsr.num_sensors_per_hand":
                    return n_per_hand
                return default

            def resolve_path(self, v):
                return root / v

            def save_user_overrides(self, o):
                return root / "user_settings.yaml"

        e = GameEngine.__new__(GameEngine)
        e.cfg = Cfg()
        e.theme = list(THEMES.values())[0]
        e.layout = Layout(1280, 800, 1.0)
        e.source = Src()
        e.detectors = {}
        e.session = type("S", (), {"participant": "T1"})()
        return CalibrationScreen(e), sent

    # ---- channel map must be a permutation --------------------------

    def test_felt_nothing_cannot_leave_two_fingers_on_one_channel(self):
        """A dead motor used to leave its finger on a straight-through
        default that another channel already owned, so cueing one finger
        buzzed a different one and the patient pressed the wrong finger
        while the data recorded it as their error."""
        s, _ = self._screen()
        s._felt = {1: 0, 2: 1, 3: 3}          # channel 4 felt nothing
        cmap = s.channel_map()
        assert sorted(cmap) == [1, 2, 3, 4], f"not a permutation: {cmap}"

    def test_same_finger_named_twice_still_yields_a_permutation(self):
        s, _ = self._screen()
        s._felt = {1: 0, 2: 0, 3: 2, 4: 3}    # index claimed twice
        cmap = s.channel_map()
        assert sorted(cmap) == [1, 2, 3, 4], f"not a permutation: {cmap}"

    def test_confirmed_answers_are_honoured(self):
        s, _ = self._screen()
        s._felt = {1: 3, 2: 1, 3: 2, 4: 0}
        assert s.channel_map() == [4, 2, 3, 1]

    def test_no_answers_at_all_is_straight_through(self):
        s, _ = self._screen()
        s._felt = {}
        assert s.channel_map() == [1, 2, 3, 4]

    def test_unconfirmed_fingers_are_reported(self):
        s, _ = self._screen()
        s._felt = {1: 0, 2: 1}
        assert set(s.unmapped_fingers()) == {"ring", "pinky"}

    # ---- which hand is actually being measured -----------------------

    def test_left_hand_reads_the_left_half_of_the_sample_vector(self):
        """With two boards the vector is [right 0..3, left 4..7]. Reading
        the first four regardless of hand measured the right board's idle
        sensors while the patient pressed with their left, producing a
        profile of near-zero gaps taken from a hand nobody touched."""
        s, _ = self._screen(hand="left")
        assert s.hand == "left"
        assert s._sensor_offset() == 4
        s._start_collecting(0.0)
        s.on_sample(0.0, [1, 2, 3, 4, 50, 60, 70, 80])
        assert s._buffer[0] == [50.0, 60.0, 70.0, 80.0]

    def test_right_hand_reads_the_first_half(self):
        s, _ = self._screen(hand="right")
        assert s._sensor_offset() == 0
        s._start_collecting(0.0)
        s.on_sample(0.0, [1, 2, 3, 4, 50, 60, 70, 80])
        assert s._buffer[0] == [1.0, 2.0, 3.0, 4.0]

    def test_profile_records_the_hand_that_was_calibrated(self):
        """profile.hand used to come from a config key that does not
        exist, so every profile was stamped right whatever was measured."""
        for hand in ("right", "left"):
            s, _ = self._screen(hand=hand)
            s.profile.resting = [245.0] * 4
            s.profile.press = [295.0] * 4
            s.profile.empty = [243.0] * 4
            s.profile.empty_noise = [1.0] * 4
            s._save()
            assert s.profile.hand == hand

    # ---- stale state between participants ---------------------------

    def test_reset_returns_to_the_opening_step(self):
        """Without this the next participant opened straight onto the
        previous participant's review table, where the only buttons were
        Done and Back."""
        import rehab.ui.calibration_screen as cs
        s, _ = self._screen()
        s.step = cs.STEP_REVIEW
        s._saved_path = Path("x")
        s._felt = {1: 0}
        s.reset()
        assert s.step == cs.STEP_INTRO
        assert s._saved_path is None
        assert s._felt == {}
        assert any(b.label == "Start calibration" for b in s._buttons)

    def test_leaving_mid_measurement_discards_the_partial_buffer(self):
        """Leaving used to keep _collecting True with a part-filled
        buffer, which the next visit's first update() wrote in as though
        the step had completed."""
        import rehab.ui.calibration_screen as cs
        s, _ = self._screen()
        s._begin()
        s._start_collecting(5.0)
        for _ in range(30):
            s.on_sample(0.0, [999.0] * 4)
        assert s._buffer
        s._abort_collection()
        assert not s._collecting and s._buffer == []
        s.update(0.0)
        assert s.step == cs.STEP_EMPTY, "partial buffer was finalised"

    # ---- outlier rejection on the press level ------------------------

    def test_one_glitched_sample_does_not_set_the_press_level(self):
        """max() over the window meant a single corrupt I2C frame reading
        800 counts became the press level, and the threshold derived from
        it was one the finger could never reach."""
        import rehab.ui.calibration_screen as cs
        s, _ = self._screen()
        s._begin()
        s.profile.resting = [245.0] * 4
        s.step = cs.STEP_PRESS
        s.finger_idx = 0
        s._start_collecting(0.0)
        for _ in range(600):
            s.on_sample(0.0, [295.0] * 4)     # steady held press
        s.on_sample(0.0, [800.0] * 4)         # one corrupt frame
        s.update(0.0)
        assert s.profile.press[0] < 400, (
            f"outlier set the press level: {s.profile.press[0]}")

    def test_percentile_helper(self):
        from rehab.ui.calibration_screen import _percentile
        assert _percentile([], 0.95) == 0.0
        assert _percentile([5.0], 0.95) == 5.0
        assert _percentile([1, 2, 3, 4, 5], 0.0) == 1.0
        assert _percentile([1, 2, 3, 4, 5], 1.0) == 5.0

    # ---- buzz length --------------------------------------------------

    def test_test_buzz_is_long_enough_to_feel(self):
        """The firmware sets an absolute deadline per command, so four
        commands sent inside one 150 ms window all resolve to the same
        stop time and the motor runs once, not four times. A single
        150 ms pulse is easy for an impaired hand to miss, and a missed
        pulse is recorded as felt nothing."""
        import rehab.ui.calibration_screen as cs
        s, sent = self._screen()
        s.step = cs.STEP_BUZZ
        s.buzz_channel = 2
        s._buzz_now()
        assert len(sent) >= 3, f"only {len(sent)} pulses, too short to feel"
        assert all(c == "STIM:2" for c in sent)


class TestEngineApplicationFixes:
    def _engine(self, hands=("right", "left")):
        from rehab.game.engine import GameEngine
        from rehab.hardware.fsr_detector import Calibration, FSRDetector

        class Cfg:
            def __init__(self):
                self.data = {}

            def get(self, key, default=None):
                return default

        e = GameEngine.__new__(GameEngine)
        e.cfg = Cfg()
        e.calibration_profiles = {}
        e.detectors = {h: FSRDetector(Calibration(num_sensors=4)) for h in hands}
        return e

    def test_calibration_applies_only_to_the_hand_it_measured(self):
        """A profile describes one hand's pads. Writing it onto both
        detectors pushed the calibrated hand's thresholds onto the other
        hand's differently-placed sensors, where the same counts are a
        different fraction of that hand's travel."""
        from rehab.game.engine import GameEngine
        e = self._engine()
        before = list(e.detectors["left"].cal.on_delta)
        prof = make_profile()
        prof.hand = "right"
        GameEngine.apply_calibration(e, prof)
        assert list(e.detectors["right"].cal.on_delta) == prof.on_delta()
        assert list(e.detectors["left"].cal.on_delta) == before, \
            "left hand was overwritten by the right hand's calibration"

    def test_thresholds_are_never_written_into_the_shared_config(self):
        """A config value is read by BOTH detectors when they are rebuilt,
        so writing one hand's thresholds there hands them to the other
        hand. On a bilateral rig the affected hand would then run on the
        unaffected hand's numbers, which it cannot reach, and every one of
        its trials would score a miss."""
        from rehab.game.engine import GameEngine
        e = self._engine()
        prof = make_profile()
        prof.hand = "right"
        GameEngine.apply_calibration(e, prof)
        assert "fsr" not in e.cfg.data, (
            "thresholds leaked into the shared config")

    def test_calibration_survives_a_detector_rebuild(self):
        """Detectors get rebuilt from config in several places (mirror
        forces both hands, _ensure_both_detectors fills a missing side).
        The calibration has to be re-applied or it silently reverts while
        the session metadata still records it as active."""
        from rehab.game.engine import GameEngine
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        e = self._engine()
        prof = make_profile()
        prof.hand = "right"
        GameEngine.apply_calibration(e, prof)
        # Rebuild, as mirror mode does.
        e.detectors = {h: FSRDetector(Calibration(num_sensors=4))
                       for h in ("right", "left")}
        GameEngine.reapply_calibrations(e)
        assert list(e.detectors["right"].cal.on_delta) == prof.on_delta()

    def test_two_hands_keep_separate_thresholds(self):
        from rehab.game.engine import GameEngine
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        e = self._engine()
        right = make_profile(); right.hand = "right"
        left = CalibrationProfile(
            empty=[245.0] * 4, empty_noise=[1.1] * 4,
            resting=[247.0] * 4, press=[247.0 + g for g in (70, 60, 55, 80)])
        left.hand = "left"
        GameEngine.apply_calibration(e, right)
        GameEngine.apply_calibration(e, left)
        e.detectors = {h: FSRDetector(Calibration(num_sensors=4))
                       for h in ("right", "left")}
        GameEngine.reapply_calibrations(e)
        assert list(e.detectors["right"].cal.on_delta) == right.on_delta()
        assert list(e.detectors["left"].cal.on_delta) == left.on_delta()
        assert right.on_delta() != left.on_delta()

    def test_both_hands_are_primed(self):
        from rehab.game.engine import GameEngine
        e = self._engine()
        for hand, gaps in (("right", (49, 32, 30, 115)),
                           ("left", (70, 60, 55, 80))):
            pr = CalibrationProfile(
                empty=[245.0] * 4, empty_noise=[1.1] * 4,
                resting=[247.0] * 4,
                press=[247.0 + g for g in gaps])
            pr.hand = hand
            GameEngine.apply_calibration(e, pr)
        for d in e.detectors.values():
            d.reset()
        GameEngine._prime_baselines(e)
        assert e.detectors["right"].baseline[0] is not None
        assert e.detectors["left"].baseline[0] is not None

    def test_baselines_are_primed_from_the_calibrated_resting_level(self):
        from rehab.game.engine import GameEngine
        e = self._engine()
        prof = make_profile()
        prof.hand = "right"
        GameEngine.apply_calibration(e, prof)
        for i in range(N_FINGERS):
            assert e.detectors["right"].baseline[i] == pytest.approx(
                prof.resting[i])

    def test_priming_survives_a_block_start_reset(self):
        """reset() clears the baseline to None. Without re-priming, a block
        that starts with the hand off the pads seeds the baseline from the
        empty device, so the hand landing reads as a rise and the first
        trials run under a lower effective trigger than the rest."""
        from rehab.game.engine import GameEngine
        e = self._engine()
        prof = make_profile()
        prof.hand = "right"
        GameEngine.apply_calibration(e, prof)
        e.detectors["right"].reset()
        assert e.detectors["right"].baseline[0] is None
        GameEngine._prime_baselines(e)
        for i in range(N_FINGERS):
            assert e.detectors["right"].baseline[i] == pytest.approx(
                prof.resting[i])

    def test_priming_without_a_profile_is_a_no_op(self):
        from rehab.game.engine import GameEngine
        e = self._engine()
        GameEngine._prime_baselines(e)
        assert e.detectors["right"].baseline[0] is None

    def test_missing_detector_for_the_hand_does_not_crash(self):
        from rehab.game.engine import GameEngine
        e = self._engine(hands=("right",))
        prof = make_profile()
        prof.hand = "left"
        GameEngine.apply_calibration(e, prof)
        GameEngine._prime_baselines(e)


class TestUnreachableTrigger:
    """A pad carrying more load at rest than the finger can add makes the
    trigger unreachable. Every trial on that finger is then a miss, which
    reads as a paralysed finger rather than a placement fault."""

    def _profile(self, gaps, preloads):
        return CalibrationProfile(
            empty=[245.0] * 4, empty_noise=[1.1] * 4,
            resting=[245.0 + p for p in preloads],
            press=[245.0 + p + g for p, g in zip(preloads, gaps)])

    def test_trigger_above_the_gap_is_refused(self):
        p = self._profile([49, 32, 30, 28], [2.5, 8.9, 11.5, 30.7])
        ok, problems = p.usable()
        assert not ok
        assert any("pinky" in s for s in problems)

    def test_the_real_device_still_calibrates(self):
        p = self._profile([49, 32, 30, 115], [2.5, 8.9, 11.5, 30.7])
        assert p.usable()[0] is True
        assert p.on_delta() == [20, 13, 15, 46]

    def test_no_usable_profile_has_an_unreachable_trigger(self):
        from rehab.hardware.calibration_profile import MAX_TRIGGER_FRACTION
        for gap in range(20, 160, 4):
            for preload in (0.0, 5.0, 15.0, 30.7, 60.0):
                p = self._profile([gap] * 4, [preload] * 4)
                if not p.usable()[0]:
                    continue
                for i in range(N_FINGERS):
                    assert p.on_delta()[i] <= p.gap()[i] * MAX_TRIGGER_FRACTION
