"""Buzz Hunt: the vibrotactile perception suite.

What is pinned here, in dependency order:

  - the staircase: 2-down 1-up mechanics, floor and ceiling clamps,
    reversal recording, and convergence near a simulated observer's
    true threshold (the gap stage still runs one; localisation only
    under the legacy flag)
  - the window ladder (2026-09): promote on 6 of the last 8, demote
    on 2 of the last 4, clamped at both ends, the trace per trial
  - pure stimulus reconstruction: pulses_from_params rebuilds every
    waveform (buzz, catch, distractor, sequence, gap) from the params
    dict alone, matched-envelope gap trials included, and the packed
    cell round-trips
  - the Hebb material: participant-name seeding is deterministic and
    case-folded, sequences avoid immediate repeats and stay inside
    the lane pool
  - localisation trials: the buzz goes out through pulse_motor
    (bypassing the cue switches by design) at ONE fixed pulse that
    success never shortens, a correct press scores, a wrong finger
    logs a Miss with the confusion matrix updated, a timeout is a
    miss on the ladder, the row carries the window and the level,
    and cue_target_shown is FALSE
  - the legacy duration staircase (buzz_hunt.duration_staircase)
    reproduces the recorded level sequence of the pre-2026-09 build
    exactly, so an earlier block can be replayed
  - catch trials: no STIM is ever sent, waiting is rewarded through
    log_reaction_event, a press is a false alarm in the matrix
  - the hand matrix: one hand rotates its four fingers at equal
    counts, both hands run all eight balanced per hand, distractors
    exist only bilaterally and sit on the other hand
  - span trials: replay scoring, the span ladder, and every third
    trial secretly replaying the participant's Hebb sequence
  - gap trials: tap-count judging, the gap staircase, and reversal
    events in the raw log
  - the trial rows: waveform buzz / buzz_seq / buzz_gap with params
    and segment bounds that parse back
  - the screen: trial frames show a focus point only (nothing that
    names a finger), and steady-state frames allocate no surfaces
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _engine(hand_mode="right", cfg_extra=None):
    """Engine fixture in the house style: built via __new__, MagicMock
    config, command-recording source, loggable."""
    from finger_rehab.game.engine import GameEngine
    values = {
        "fsr.num_sensors_per_hand": 4,
        "motor.cue_ms": 150,
        "motor.pulse_interval_ms": 120,
        "cue.buzz_before": False,
        "cue.buzz_after": False,
        "cue.sound_before": False,
        "cue.sound_after": False,
        "cue.show_target": True,
        "game.timeout_s": 1.0,
    }
    values.update(cfg_extra or {})
    e = GameEngine.__new__(GameEngine)
    e.cfg = MagicMock()
    e.cfg.get = MagicMock(side_effect=lambda k, d=None: values.get(k, d))
    sent = []
    src = MagicMock()
    src.provides_samples = True
    src.send_command = lambda c: (sent.append(c) or True)
    e.source = src
    e._sent = sent
    e.hand_mode = hand_mode
    e.audio = None
    e.raw_logger = _RawLoggerStub()
    e._screens = {}
    e.mode = None
    e.detectors = {}
    e.calibration_profiles = {}
    e.score = 0
    e.hits = 0
    e.misses = 0
    e.hit_streak = 0
    e.miss_streak = 0
    e._streak_fired = set()
    e._streak_thresholds = ()
    e._block_rt_sum = 0.0
    e._block_rt_count = 0
    e._block_bpm_min = None
    e._block_bpm_max = None
    e._block_wrong_press_trials = 0
    e._block_peak_streak = 0
    e._last_gained = 0
    e.current_block = "buzz_hunt"
    e.session_paths = None
    e.session = MagicMock()
    e.session.participant = "Test"
    e.session.age = ""
    e._per_lane_rts = {}
    e._per_lane_misses = {}
    e._per_lane_wrong = {}
    e.trial_logger = _TrialLoggerStub()
    e._ensure_metric_state()
    return e


class _RawLoggerStub:
    def __init__(self):
        self.events = []

    def queue_event(self, event, lane=None, detail="", t_perf=None,
                    fsr_vals=None, hand="right"):
        self.events.append({"event": event, "lane": lane,
                            "detail": detail, "hand": hand})


class _TrialLoggerStub:
    def __init__(self):
        self.rows = []

    def write(self, row):
        self.rows.append(row)


def _press_event(lane, t):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                      hand="right")


class _DetectorStub:
    """Just enough of an FSR detector for _fingers_down: the pressed
    flags, one per finger on that hand's board, plus the peak-force
    accessor log_trial reaches for once a detector dict exists."""

    def __init__(self, n: int = 4):
        self.pressed = [False] * n

    def current_peak(self, sensor_idx: int):
        return None

    def current_impulse(self, sensor_idx: int):
        return None


def _attach_detectors(e, hands=("right",), n=4):
    e.detectors = {h: _DetectorStub(n) for h in hands}
    return e.detectors


def _run_frames(m, t, seconds, dt=1.0 / 60.0, hook=None):
    """Tick the mode through `seconds` of virtual frames. `hook` is
    called with (mode, now) before each tick so a test can play the
    part of a patient, a pause, or a long frame."""
    end = t + seconds
    while t < end:
        step = dt
        if hook is not None:
            got = hook(m, t)
            if got:
                step = got
        t += step
        m._tick(t)
        if m.phase == "done":
            break
    return t


def _tap_along(react_s=0.3):
    """A patient who replays what they feel as they feel it: one
    press react_s after every playback starts, then normal answers
    once the window is open. This is the natural way to play the span
    and gap stages and it used to lock the block up for good."""
    seen = {"t0": None}

    def hook(m, now):
        if m.phase != "trial":
            return None
        if m.sub == "play" and m._play_t0 is not None:
            if now >= m._play_t0 + react_s and seen["t0"] != m._play_t0:
                seen["t0"] = m._play_t0
                m.queue_press(_press_event(m.lane, now))
        elif m.sub == "respond":
            m.queue_press(_press_event(m.lane, now))
        return None

    return hook


def _press_train(period_s=1.0, lane=1):
    state = {"next": None}

    def hook(m, now):
        if state["next"] is None:
            state["next"] = now
        if now >= state["next"]:
            state["next"] = now + period_s
            m.queue_press(_press_event(lane, now))
        return None

    return hook


def _mode(e, hands=None, **over):
    from finger_rehab.game.modes.buzz_hunt import (BuzzHuntMode,
                                            participant_hebb_seed)
    from finger_rehab.game.scoring import ScoreConfig
    kw = dict(
        engine=e,
        lanes_by_hand=hands or {"right": [0, 1, 2, 3]},
        participant_seed=participant_hebb_seed("Test"),
        loc_trials_per_hand=8,
        catch_rate=0.0,
        start_ms=300.0,
        step_ms=40.0,
        floor_ms=40.0,
        ceil_ms=500.0,
        threshold_reversals=6,
        distractor_trials_per_hand=2,
        distractor_lead_ms=150.0,
        span_trials=3,
        span_start=2,
        span_pulse_ms=150.0,
        span_ioi_ms=400.0,
        hebb_every=3,
        gap_trials_per_hand=4,
        gap_start_ms=200.0,
        gap_step_ms=25.0,
        gap_floor_ms=35.0,
        gap_short_ms=80.0,
        wait_lo_s=0.5,
        wait_hi_s=0.8,
        response_window_s=2.0,
        replay_item_s=1.0,
        announce_s=0.5,
        rest_s=0.5,
        stage_intro_s=0.6,
        score_cfg=ScoreConfig(),
        seed=7,
        demo_trials=None,
        # The 2026-09 shape: a fixed pulse and a window ladder whose
        # first level equals response_window_s, so the timeouts the
        # older tests drive with response_window_s still time out.
        loc_pulse_ms=150.0,
        window_levels_s=[2.0, 1.5, 1.2, 1.0],
        duration_staircase=False,
    )
    kw.update(over)
    return BuzzHuntMode(**kw)


def _stim_requests(m) -> list[float]:
    """Every pulse length asked of the motor so far, from the raw
    log's pulse_motor events (one per delivered pulse)."""
    out = []
    for ev in m.engine.raw_logger.events:
        if ev["event"] != "pulse_motor":
            continue
        fields = dict(p.partition("=")[::2] for p in ev["detail"].split(";"))
        out.append(float(fields["requested_ms"]))
    return out


def _answer_loc(m, t, correct=True, rt=0.3):
    """One localisation answer at the open window: the right finger
    or a wrong one, then the tick that closes the trial."""
    lane = m.lane if correct else next(
        l for l in m.hands[m.hand] if l != m.lane)
    m.queue_press(_press_event(lane, t + rt))
    m._tick(t + rt + 0.01)
    return t + rt + 0.01


def _only_stage(m, stage, n):
    """Restrict a built mode to one stage for a focused test."""
    m._stage_plan = [stage] * n
    m.total_trials = n
    return m


def _to_trial(m, t0=1000.0):
    """Drive a fresh mode into its first trial's wait sub-phase."""
    m._tick(t0)
    assert m.phase == "stage", m.phase
    t = t0 + m.stage_intro_s + 0.01
    m._tick(t)
    assert m.phase == "announce", m.phase
    t += m.announce_s + 0.01
    m._tick(t)
    assert m.phase == "trial", m.phase
    return t


def _to_respond(m, t, dt=1.0 / 60.0):
    """Advance through the wait and the stimulus until the response
    window is open."""
    guard = t + 30.0
    while m.sub != "respond" and t < guard:
        t += dt
        m._tick(t)
    assert m.sub == "respond", m.sub
    return t


def _next_trial(m, t):
    """From feedback into the next trial's wait sub-phase."""
    assert m.phase == "feedback", m.phase
    t += m.rest_s + 0.01
    m._tick(t)
    if m.phase == "stage":
        t += m.stage_intro_s + 0.01
        m._tick(t)
    assert m.phase == "announce", m.phase
    t += m.announce_s + 0.01
    m._tick(t)
    return t


# ---- the staircase ------------------------------------------------------


class StaircaseTests(unittest.TestCase):
    def _stair(self, **over):
        from finger_rehab.game.modes.buzz_hunt import Staircase
        kw = dict(start=300.0, step=40.0, floor=40.0, ceiling=500.0)
        kw.update(over)
        return Staircase(**kw)

    def test_two_down_one_up(self):
        s = self._stair()
        s.record(True)
        self.assertEqual(s.level, 300.0)     # one correct holds
        s.record(True)
        self.assertEqual(s.level, 260.0)     # two correct steps down
        s.record(False)
        self.assertEqual(s.level, 300.0)     # one wrong steps up

    def test_floor_and_ceiling_clamp(self):
        s = self._stair(start=60.0)
        for _ in range(10):
            s.record(True)
        self.assertEqual(s.level, 40.0)
        s2 = self._stair(start=480.0)
        for _ in range(5):
            s2.record(False)
        self.assertEqual(s2.level, 500.0)

    def test_reversals_are_recorded_at_the_turn(self):
        s = self._stair()
        s.record(True)
        s.record(True)                        # down, no reversal yet
        self.assertEqual(s.reversals, [])
        s.record(False)                       # up: first reversal
        self.assertEqual(s.reversals, [260.0])
        s.record(True)
        s.record(True)                        # down: second reversal
        self.assertEqual(s.reversals, [260.0, 300.0])

    def test_step_floor_is_one_frame(self):
        from finger_rehab.game.modes.buzz_hunt import MIN_STEP_MS
        s = self._stair(step=5.0)
        self.assertEqual(s.step, MIN_STEP_MS)

    def test_converges_near_a_simulated_observer(self):
        # Simulated observer: reliably correct above the true
        # threshold, at four-alternative chance below it. The 2-down
        # 1-up rule should settle the reversal average within about a
        # step of the truth.
        import random
        rng = random.Random(3)
        true_ms = 140.0
        s = self._stair()
        for _ in range(120):
            p = 0.97 if s.level >= true_ms else 0.25
            s.record(rng.random() < p)
        est = s.estimate(8)
        self.assertIsNotNone(est)
        self.assertLess(abs(est - true_ms), 2.5 * s.step)

    def test_estimate_needs_two_reversals(self):
        s = self._stair()
        self.assertIsNone(s.estimate(6))
        s.record(True)
        s.record(True)
        s.record(False)
        self.assertIsNone(s.estimate(6))      # one reversal only
        s.record(True)
        s.record(True)
        self.assertIsNotNone(s.estimate(6))


class FastStartTests(unittest.TestCase):
    """The accelerated approach (Levitt 1971 section IV; Leek 2001):
    until the first reversal a single correct steps down and the step
    is doubled, then the plain 2-down 1-up takes over at the base
    step. Measured on the shipped localisation stage this moved the
    first 8-trial bin from a mean of 240 ms dealt to 120, and the
    loc trials spent within 1.5x of a simulated 90 ms observer's
    threshold from 6 of 28 to 25 of 28."""

    def _stair(self, **over):
        from finger_rehab.game.modes.buzz_hunt import Staircase
        kw = dict(start=300.0, step=40.0, floor=40.0, ceiling=500.0,
                  fast_start=True)
        kw.update(over)
        return Staircase(**kw)

    def test_single_correct_steps_double_until_first_reversal(self):
        s = self._stair()
        s.record(True)
        self.assertEqual(s.level, 220.0)     # one correct, double step
        s.record(True)
        self.assertEqual(s.level, 140.0)

    def test_first_error_reverses_at_the_base_step(self):
        s = self._stair()
        s.record(True)
        s.record(True)                        # 300 -> 220 -> 140
        rev = s.record(False)
        self.assertTrue(rev)
        self.assertEqual(s.reversals, [140.0])
        # The recovery step is the BASE step: a doubled climb would
        # overshoot the region the descent just found.
        self.assertEqual(s.level, 180.0)

    def test_after_first_reversal_the_plain_rule_runs(self):
        s = self._stair()
        s.record(True)
        s.record(True)
        s.record(False)                       # reversal, level 180
        s.record(True)
        self.assertEqual(s.level, 180.0)      # one correct holds now
        s.record(True)
        self.assertEqual(s.level, 140.0)      # two correct: base step

    def test_default_stays_the_plain_rule(self):
        from finger_rehab.game.modes.buzz_hunt import Staircase
        s = Staircase(start=300.0, step=40.0, floor=40.0, ceiling=500.0)
        s.record(True)
        self.assertEqual(s.level, 300.0)      # one correct holds

    def test_reaches_the_threshold_region_in_fewer_trials(self):
        import random

        def trials_to_region(fast: bool) -> int:
            rng = random.Random(5)
            s = self._stair(fast_start=fast)
            true_ms = 90.0
            for i in range(60):
                if s.level <= 1.5 * true_ms:
                    return i
                p = 0.97 if s.level >= true_ms else 0.25
                s.record(rng.random() < p)
            return 60

        self.assertLess(trials_to_region(True),
                        trials_to_region(False))
        self.assertLessEqual(trials_to_region(True), 4)

    def test_still_converges_near_a_simulated_observer(self):
        import random
        rng = random.Random(3)
        true_ms = 140.0
        s = self._stair()
        for _ in range(120):
            p = 0.97 if s.level >= true_ms else 0.25
            s.record(rng.random() < p)
        est = s.estimate(8)
        self.assertIsNotNone(est)
        self.assertLess(abs(est - true_ms), 2.5 * s.step)


# ---- pure stimulus reconstruction ---------------------------------------


class PulseReconstructionTests(unittest.TestCase):
    def test_plain_buzz(self):
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        p = {"catch": 0, "lane": 2, "dur_ms": 180.0, "window_ms": 3000.0}
        self.assertEqual(pulses_from_params("buzz", p),
                         [(2, 0.0, 180.0)])

    def test_catch_has_no_pulses(self):
        from finger_rehab.game.modes.buzz_hunt import (pulses_from_params,
                                                stimulus_span_s)
        p = {"catch": 1, "window_ms": 3000.0}
        self.assertEqual(pulses_from_params("buzz", p), [])
        self.assertEqual(stimulus_span_s("buzz", p), 0.0)

    def test_distractor_leads_the_target(self):
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        p = {"catch": 0, "lane": 1, "dur_ms": 120.0,
             "distractor_lane": 5, "distractor_ms": 120.0,
             "distractor_lead_ms": 150.0, "window_ms": 3000.0}
        pulses = pulses_from_params("buzz", p)
        self.assertEqual(pulses[0], (5, 0.0, 120.0))
        self.assertEqual(pulses[1], (1, 0.15, 120.0))

    def test_sequence_pulses_follow_the_ioi(self):
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        p = {"seq": "0-2-1", "len": 3, "pulse_ms": 150.0,
             "ioi_ms": 400.0, "hebb": 0}
        pulses = pulses_from_params("buzz_seq", p)
        self.assertEqual([l for l, _o, _d in pulses], [0, 2, 1])
        self.assertAlmostEqual(pulses[1][1], 0.4)
        self.assertAlmostEqual(pulses[2][1], 0.8)

    def test_gap_envelopes_are_length_matched(self):
        # The design promise: total stimulus length never gives the
        # answer away, so one long buzz spans exactly two shorts plus
        # the gap.
        from finger_rehab.game.modes.buzz_hunt import (pulses_from_params,
                                                stimulus_span_s)
        one = {"lane": 3, "two": 0, "short_ms": 80.0, "gap_ms": 60.0,
               "window_ms": 2000.0}
        two = {"lane": 3, "two": 1, "short_ms": 80.0, "gap_ms": 60.0,
               "window_ms": 2000.0}
        self.assertEqual(pulses_from_params("buzz_gap", one),
                         [(3, 0.0, 220.0)])
        self.assertEqual(pulses_from_params("buzz_gap", two),
                         [(3, 0.0, 80.0), (3, 0.14, 80.0)])
        self.assertAlmostEqual(stimulus_span_s("buzz_gap", one),
                               stimulus_span_s("buzz_gap", two))

    def test_params_round_trip_through_the_packed_cell(self):
        from finger_rehab.data.logger import (pack_waveform_params,
                                       parse_waveform_params)
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        p = {"seq": "0-2-1-3", "len": 4, "pulse_ms": 150.0,
             "ioi_ms": 400.0, "hebb": 1}
        back = parse_waveform_params(pack_waveform_params(p))
        self.assertEqual(pulses_from_params("buzz_seq", p),
                         pulses_from_params("buzz_seq", back))

    def test_unknown_waveform_raises(self):
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        with self.assertRaises(ValueError):
            pulses_from_params("hold", {})


# ---- the Hebb material --------------------------------------------------


class HebbMaterialTests(unittest.TestCase):
    def test_name_seed_is_case_and_space_folded(self):
        from finger_rehab.game.modes.buzz_hunt import participant_hebb_seed
        self.assertEqual(participant_hebb_seed("Basil "),
                         participant_hebb_seed("basil"))
        self.assertNotEqual(participant_hebb_seed("basil"),
                            participant_hebb_seed("someone else"))

    def test_hebb_sequence_is_stable_and_legal(self):
        from finger_rehab.game.modes.buzz_hunt import hebb_sequence
        lanes = [0, 1, 2, 3]
        a = hebb_sequence(12345, 5, lanes)
        b = hebb_sequence(12345, 5, lanes)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)
        self.assertTrue(all(l in lanes for l in a))
        for x, y in zip(a, a[1:]):
            self.assertNotEqual(x, y)

    def test_hebb_differs_by_length_and_seed(self):
        from finger_rehab.game.modes.buzz_hunt import hebb_sequence
        lanes = list(range(8))
        self.assertNotEqual(hebb_sequence(1, 6, lanes),
                            hebb_sequence(2, 6, lanes))

    def test_fresh_sequences_come_from_the_trial_seed(self):
        from finger_rehab.game.modes.buzz_hunt import draw_sequence
        lanes = [0, 1, 2, 3]
        self.assertEqual(draw_sequence(9, 4, lanes),
                         draw_sequence(9, 4, lanes))
        self.assertNotEqual(draw_sequence(9, 6, lanes),
                            draw_sequence(10, 6, lanes))


# ---- localisation trials ------------------------------------------------


class LocalisationTests(unittest.TestCase):
    def _loc_mode(self, e=None, n=4, **over):
        m = _mode(e or _engine(), **over)
        return _only_stage(m, "loc", n)

    def test_correct_press_scores_and_fills_the_diagonal(self):
        m = self._loc_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        lane = m.lane
        m.queue_press(_press_event(lane, t + 0.3))
        m._tick(t + 0.31)
        self.assertEqual(m.phase, "feedback")
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "buzz")
        self.assertNotEqual(row["early_late"], "Miss")
        self.assertEqual(m._confusion[str(lane)][str(lane)], 1)
        self.assertTrue(m._loc_records[0]["correct"])
        self.assertIsNotNone(m._loc_records[0]["rt_ms"])

    def test_the_buzz_bypasses_the_cue_switches(self):
        # cue.buzz_before is OFF in the fixture, and the stimulus
        # still goes out: the buzz is the stimulus, not a cue.
        m = self._loc_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        stims = [c for c in m.engine._sent if str(c).startswith("STIM")]
        self.assertEqual(len(stims), 1)
        self.assertEqual(stims[0], f"STIM:{m.lane + 1}")
        pulse_events = [ev for ev in m.engine.raw_logger.events
                        if ev["event"] == "pulse_motor"]
        self.assertEqual(len(pulse_events), 1)

    def test_nothing_on_screen_names_the_target(self):
        m = self._loc_mode()
        t = _to_trial(m)
        _to_respond(m, t)
        self.assertFalse(m.engine._last_target_shown)

    def test_wrong_finger_logs_miss_and_the_matrix_cell(self):
        m = self._loc_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        lane = m.lane
        wrong = next(l for l in [0, 1, 2, 3] if l != lane)
        m.queue_press(_press_event(wrong, t + 0.3))
        m._tick(t + 0.31)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(row["had_incorrect_press"], "TRUE")
        self.assertEqual(m._confusion[str(lane)][str(wrong)], 1)
        self.assertFalse(m._loc_records[0]["correct"])

    def test_timeout_is_a_miss_on_the_ladder_and_the_row_says_the_window(
            self):
        # A silent window is a miss for the ladder (one miss alone
        # moves nothing; two in four demote), the confusion matrix
        # gets its "none" cell, and the row carries the window it ran
        # under plus the level, with timeout_ms stamped from the
        # window.
        m = self._loc_mode()
        t = _to_trial(m)
        self.assertEqual(m.engine._last_stim_timeout_ms,
                         m.window_levels_s[0] * 1000.0)
        t = _to_respond(m, t)
        t += m._respond_window_s() + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        self.assertEqual(m._window[m.hand].level, 0)
        self.assertEqual(m._confusion[str(m._loc_records[0]['lane'])]
                         ["none"], 1)
        row = m.engine.trial_logger.rows[0]
        self.assertIn("window_ms=2000", row["stimulus"])
        self.assertIn("level=0", row["stimulus"])
        self.assertNotIn("stair_ms", row["stimulus"])
        self.assertEqual(row["timeout_ms"], "2000")

    def test_the_pulse_never_shortens_with_success(self):
        # The 2026-09 rule: a run of correct answers used to walk the
        # staircase down until the buzz could not be felt. Now every
        # localisation pulse the motor is asked for is loc_pulse_ms,
        # eight correct answers in a row included.
        m = self._loc_mode(n=8)
        t = _to_trial(m)
        for i in range(8):
            t = _to_respond(m, t)
            self.assertEqual(float(m.params["dur_ms"]), 150.0)
            t = _answer_loc(m, t, correct=True)
            if i < 7:
                t = _next_trial(m, t)
        self.assertEqual(_stim_requests(m), [150.0] * 8)
        stims = [c for c in m.engine._sent if str(c).startswith("STIM")]
        self.assertEqual(len(stims), 8)
        self.assertEqual(m._dur_stair["right"].level, m.start_ms,
                         "the legacy staircase must not have moved")

    def test_six_of_eight_promote_and_the_row_carries_the_level(self):
        m = self._loc_mode(n=8)
        t = _to_trial(m)
        for i in range(7):
            t = _to_respond(m, t)
            t = _answer_loc(m, t, correct=True)
            if i < 6:
                t = _next_trial(m, t)
        rows = m.engine.trial_logger.rows
        self.assertEqual(len(rows), 7)
        for row in rows[:6]:
            self.assertIn("level=0", row["stimulus"])
            self.assertIn("window_ms=2000", row["stimulus"])
        # The sixth correct answer promoted, so the seventh trial
        # ran at level 1 and its shorter window.
        self.assertIn("level=1", rows[6]["stimulus"])
        self.assertIn("window_ms=1500", rows[6]["stimulus"])
        self.assertEqual(m._window["right"].level, 1)
        moves = [ev for ev in m.engine.raw_logger.events
                 if ev["event"] == "buzz_hunt_window"]
        self.assertEqual(len(moves), 1)
        self.assertIn("move=up", moves[0]["detail"])
        self.assertIn("level=1", moves[0]["detail"])
        self.assertEqual(m._window["right"].trace, [0] * 6 + [1])

    def test_two_misses_in_four_demote(self):
        m = self._loc_mode(n=10)
        t = _to_trial(m)
        # Climb one level, then miss twice: back down, logged.
        for i in range(6):
            t = _to_respond(m, t)
            t = _answer_loc(m, t, correct=True)
            t = _next_trial(m, t)
        self.assertEqual(m._window["right"].level, 1)
        t = _to_respond(m, t)
        t = _answer_loc(m, t, correct=False)
        self.assertEqual(m._window["right"].level, 1)
        t = _next_trial(m, t)
        t = _to_respond(m, t)
        t += m._respond_window_s() + 0.05        # timeout: a miss too
        m._tick(t)
        self.assertEqual(m._window["right"].level, 0)
        moves = [ev["detail"] for ev in m.engine.raw_logger.events
                 if ev["event"] == "buzz_hunt_window"]
        self.assertEqual(len(moves), 2)
        self.assertIn("move=down", moves[1])
        self.assertEqual(m._window["right"].n_demotions, 1)
        # No duration reversal was ever logged: the staircase is off.
        self.assertEqual([ev for ev in m.engine.raw_logger.events
                          if ev["event"] == "buzz_hunt_reversal"], [])

    def test_early_press_restarts_the_wait_without_a_trial(self):
        m = self._loc_mode()
        t = _to_trial(m)
        m._tick(t + 0.01)
        m.queue_press(_press_event(0, t + 0.02))
        m._tick(t + 0.03)
        self.assertEqual(m.sub, "wait")
        self.assertEqual(m.trials_done, 0)
        self.assertEqual(m._early_presses, {"loc": 1})
        self.assertEqual(m.engine.trial_logger.rows, [])

    def test_trial_row_carries_the_reconstruction_contract(self):
        from finger_rehab.data.logger import (parse_segments,
                                       parse_waveform_params)
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        m = self._loc_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        seed = m.trial_seed
        dur = float(m.params["dur_ms"])
        m.queue_press(_press_event(m.lane, t + 0.3))
        m._tick(t + 0.31)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform_seed"], str(seed))
        params = parse_waveform_params(row["waveform_params"])
        pulses = pulses_from_params("buzz", params)
        self.assertEqual(pulses, [(m._loc_records[0]["lane"], 0.0, dur)])
        segs = parse_segments(row["segment_times"])
        names = [s[0] for s in segs]
        self.assertIn("stim", names)
        self.assertIn("respond", names)
        stim = next(s for s in segs if s[0] == "stim")
        self.assertAlmostEqual(stim[2] - stim[1], dur / 1000.0,
                               delta=0.05)
        self.assertEqual(row["cue_target_shown"], "FALSE")
        # The response window is the RT censoring limit.
        self.assertEqual(row["timeout_ms"],
                         f"{m.response_window_s * 1000.0:.0f}")

    def test_a_dropped_stimulus_is_voided_not_scored_as_a_miss(self) -> None:
        """When pulse_motor reports the hardware never accepted the
        STIM, the trial cannot be a perception sample either way: it
        must not be logged as a normal correct/incorrect response,
        must not move the staircase, and must not enter the
        localisation records (audit finding #93)."""
        e = _engine()
        e.source.send_command = lambda c: (e._sent.append(c) or False)
        m = _mode(e)
        m = _only_stage(m, "loc", 1)
        t = _to_trial(m)
        t = _to_respond(m, t)
        before = m._window[m.hand].level
        # Even a press on the correct lane must not read as a hit:
        # nothing buzzed for it to correctly localise.
        m.queue_press(_press_event(m.lane, t + 0.1))
        m._tick(t + 0.11)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["stim_delivered"], "FALSE")
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(m._window[m.hand].level, before)
        self.assertEqual(m._window[m.hand].trace, [],
                         "a voided trial never reaches the ladder")
        self.assertEqual(m._loc_records, [])
        self.assertEqual(m.engine._block_stim_failures, 1)
        # The patient DID press, so the derived 'timeout' next to a
        # non-empty keys_pressed was internally inconsistent; the row
        # carries the hardware taxonomy instead.
        self.assertEqual(row["error_type"], "stim_failed")


# ---- catch trials -------------------------------------------------------


class CatchTrialTests(unittest.TestCase):
    def _catch_mode(self):
        # The constructor clamps catch_rate at 0.5 (a config guard),
        # so force every trial to a catch after construction.
        m = _mode(_engine())
        m.catch_rate = 1.0
        return _only_stage(m, "loc", 2)

    def test_no_stim_is_ever_sent(self):
        m = self._catch_mode()
        t = _to_trial(m)
        self.assertTrue(m.catch)
        t = _to_respond(m, t)
        self.assertFalse([c for c in m.engine._sent
                          if str(c).startswith("STIM")])

    def test_waiting_is_rewarded_off_the_hit_counters(self):
        m = self._catch_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        t += m.response_window_s + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        self.assertEqual(m.engine.score, m.CATCH_REWARD)
        self.assertEqual(m.engine.hits, 0)     # counters untouched
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "CatchOk")
        # Catch rows ride log_reaction_event, which stamps the LIVE
        # show_target toggle by default; this mode's screen never
        # names a finger whatever that toggle says, so the row must
        # say FALSE like every other Buzz Hunt row.
        self.assertEqual(row["cue_target_shown"], "FALSE")

    def test_a_press_is_a_false_alarm(self):
        m = self._catch_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        m.queue_press(_press_event(2, t + 0.4))
        m._tick(t + 0.41)
        self.assertEqual(m._catch_fa, 1)
        self.assertEqual(m._confusion["none"]["2"], 1)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["error_type"], "catch_false_start")
        self.assertEqual(row["cue_target_shown"], "FALSE")
        stats = m.block_stats()
        self.assertEqual(stats["loc"]["catch"]["false_alarms"], 1)
        self.assertEqual(stats["loc"]["catch"]["fa_rate"], 1.0)

    def test_catch_hand_draws_from_both_in_bilateral_play(self):
        # A catch trial has no real lane, but in bilateral play it
        # still logically stands in for one hand's worth of waiting.
        # Before the fix this was always hand_names[0] ("right"), so
        # a left-hand false alarm could never be counted against the
        # left hand. Drive enough catch trials through _prepare_trial
        # that both hands must appear if the draw is fair.
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m.catch_rate = 1.0
        m = _only_stage(m, "loc", 40)
        seen = set()
        for i in range(40):
            m.trials_done = i
            m._prepare_trial()
            self.assertTrue(m.catch)
            seen.add(m.hand)
        self.assertEqual(seen, {"right", "left"})

    def test_catch_false_alarm_is_logged_against_the_left_hand(self):
        # Force the per-trial draw to land on "left" and confirm the
        # false alarm reaches the CSV row as "left", not silently
        # falling back to the session-level hand_mode ("both", which
        # is not a real hand and would drop the false alarm out of
        # both hands' FA rates).
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m.catch_rate = 1.0
        m = _only_stage(m, "loc", 2)
        t = _to_trial(m)
        self.assertIn(m.hand, ("right", "left"))
        m.hand = "left"  # pin the draw for a deterministic assertion
        t = _to_respond(m, t)
        m.queue_press(_press_event(5, t + 0.4))
        m._tick(t + 0.41)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["error_type"], "catch_false_start")
        self.assertEqual(row["hand"], "left")

    def test_single_hand_session_catch_still_uses_hand_names_zero(self):
        # Unilateral play has only one hand to stand in for, so the
        # fix must not change that case.
        m = self._catch_mode()
        m = _only_stage(m, "loc", 5)
        for i in range(5):
            m.trials_done = i
            m._prepare_trial()
            self.assertEqual(m.hand, "right")


# ---- the hand matrix ----------------------------------------------------


class HandMatrixTests(unittest.TestCase):
    def test_one_hand_rotates_its_four_fingers_equally(self):
        m = _mode(_engine(), loc_trials_per_hand=8, catch_rate=0.0)
        m._stage_plan = ["loc"] * 8
        m.total_trials = 8
        lanes = []
        for i in range(8):
            m.trials_done = i
            m._prepare_trial()
            lanes.append(m.lane)
        self.assertEqual(sorted(lanes), [0, 0, 1, 1, 2, 2, 3, 3])

    def test_both_hands_means_all_eight_balanced(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
                  loc_trials_per_hand=8, catch_rate=0.0)
        m._stage_plan = ["loc"] * 16
        m.total_trials = 16
        lanes = []
        hand_counts = {"right": 0, "left": 0}
        for i in range(16):
            m.trials_done = i
            m._prepare_trial()
            lanes.append(m.lane)
            hand_counts[m.hand] += 1
        self.assertEqual(sorted(lanes), sorted(list(range(8)) * 2))
        self.assertEqual(hand_counts["right"], 8)
        self.assertEqual(hand_counts["left"], 8)

    def test_distractor_stage_exists_only_bilaterally(self):
        single = _mode(_engine())
        self.assertEqual(single._stage_counts["distractor"], 0)
        self.assertNotIn("distractor", single._stage_plan)
        e = _engine(hand_mode="both")
        both = _mode(e, hands={"right": [0, 1, 2, 3],
                               "left": [4, 5, 6, 7]})
        self.assertGreater(both._stage_counts["distractor"], 0)

    def test_distractor_sits_on_the_other_hand(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m._stage_plan = ["distractor"] * 4
        m.total_trials = 4
        for i in range(4):
            m.trials_done = i
            m._prepare_trial()
            target_right = m.lane in (0, 1, 2, 3)
            d_lane = int(m.params["distractor_lane"])
            self.assertNotEqual(d_lane in (0, 1, 2, 3), target_right)

    def test_distractor_trials_hold_the_ladder_at_the_fixed_pulse(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        for ladder in m._window.values():
            ladder.level = 2                   # a level the loc stage reached
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        # Decoy and target at the fixed pulse, under the held window.
        self.assertEqual(float(m.params["dur_ms"]), 150.0)
        self.assertEqual(float(m.params["distractor_ms"]), 150.0)
        self.assertEqual(float(m.params["window_ms"]), 1200.0)
        self.assertEqual(int(m.params["level"]), 2)
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.3))
        m._tick(t + 0.31)
        self.assertEqual({h: w.level for h, w in m._window.items()},
                         {"right": 2, "left": 2})
        self.assertEqual({h: w.trace for h, w in m._window.items()},
                         {"right": [], "left": []})
        self.assertEqual(len(m._dis_records), 1)
        self.assertEqual(m._dis_records[0]["level"], 2)
        # Both pulses went out: the decoy and the target.
        stims = [c for c in m.engine._sent if str(c).startswith("STIM")]
        self.assertEqual(len(stims), 2)
        self.assertEqual(_stim_requests(m), [150.0, 150.0])

    def test_pressing_the_decoy_finger_counts_as_lured(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        t = _to_respond(m, t)
        d_lane = int(m.params["distractor_lane"])
        m.queue_press(_press_event(d_lane, t + 0.3))
        m._tick(t + 0.31)
        rec = m._dis_records[0]
        self.assertTrue(rec["lured"])
        self.assertFalse(rec["correct"])
        # The cross-hand confusion cell is the point of the DISTRACTOR
        # matrix. It must not land in the localisation matrix
        # (m._confusion, the Weber 2023 analogue and the Results
        # screen's MISREFERRALS PER FINGER source): a decoy lure is a
        # designed attention failure, not an uncued localisation error
        # (audit finding #95).
        self.assertEqual(
            m._distractor_confusion[str(rec["lane"])][str(d_lane)], 1)
        self.assertEqual(m._confusion, {})

    def test_pressing_the_decoy_during_the_decoy_pulse_scores_lured_not_a_free_retry(self) -> None:
        """A press during the decoy pulse itself (before the response
        window opens, since respond opens at TARGET onset) is the
        patient falling for the decoy -- the natural failure mode this
        stage exists to measure. It must land in the distractor tallies
        as a lured miss, not silently reset the same trial for a free
        retry that then reports as a clean, unlured hit."""
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        dt = 1.0 / 60.0
        guard = t + 5.0
        while m.sub != "play" and t < guard:
            t += dt
            m._tick(t)
        self.assertEqual(m.sub, "play")
        d_lane = int(m.params["distractor_lane"])
        # Press the decoy finger while still inside the decoy window
        # (before target onset opens the response).
        self.assertLess(t, m._target_on)
        m.queue_press(_press_event(d_lane, t))
        m._tick(t + dt)
        self.assertEqual(len(m._dis_records), 1,
                          "the lured press must be scored, not silently "
                          "retried on a fresh copy of the same trial")
        rec = m._dis_records[0]
        self.assertTrue(rec["lured"])
        self.assertFalse(rec["correct"])
        stats = m.block_stats()
        self.assertEqual(stats["distractor"]["trials"], 1)
        self.assertEqual(stats["distractor"]["lured"], 1)

    def test_a_lucky_press_on_the_target_finger_during_the_decoy_window_scores_nothing(
            self) -> None:
        """A press during the decoy window that lands on a lane OTHER
        than the decoy -- including the finger that is about to
        become the target -- must not be scored as a response to a
        target that has not fired yet. Before the fix this produced a
        Perfect hit with a negative RT and inflated distractor
        accuracy (audit finding #89)."""
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        dt = 1.0 / 60.0
        guard = t + 5.0
        while m.sub != "play" and t < guard:
            t += dt
            m._tick(t)
        self.assertEqual(m.sub, "play")
        self.assertLess(t, m._target_on)
        target_lane = m.lane
        # Guess the finger that is about to buzz, before it has.
        m.queue_press(_press_event(target_lane, t))
        m._tick(t + dt)
        self.assertEqual(m._dis_records, [],
                          "a pre-onset guess must not become a scored "
                          "distractor trial")
        stats = m.block_stats()
        self.assertEqual(stats["distractor"]["trials"], 0)
        self.assertEqual(stats["distractor"]["accuracy"], None)
        row = e.trial_logger.rows[-1]
        self.assertEqual(row["error_type"], "anticipation")
        self.assertEqual(row["early_late"], "Early")
        self.assertEqual(row["points"], 0)

    def test_early_press_during_a_distractor_wait_is_attributed_to_that_stage(self) -> None:
        """An early press that happens during a DISTRACTOR trial's wait
        must not be reported under block_stats()['loc']['early_presses']
        when zero loc trials have run yet -- each stage's early presses
        belong under its own section."""
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        m._tick(t + 0.01)
        m.queue_press(_press_event(0, t + 0.02))
        m._tick(t + 0.03)
        self.assertEqual(m.sub, "wait")
        stats = m.block_stats()
        self.assertEqual(stats["loc"]["early_presses"], 0)
        self.assertEqual(stats["distractor"]["early_presses"], 1)


# ---- span trials --------------------------------------------------------


class SpanTests(unittest.TestCase):
    def _span_mode(self, n=6, **over):
        m = _mode(_engine(), **over)
        return _only_stage(m, "span", n)

    def _replay(self, m, t, lanes):
        for i, lane in enumerate(lanes):
            m.queue_press(_press_event(lane, t + 0.2 + i * 0.1))
        m._tick(t + 0.2 + len(lanes) * 0.1 + 0.01)

    def test_correct_replay_grows_the_span(self):
        m = self._span_mode()
        t = _to_trial(m)
        self.assertEqual(len(m.sequence), 2)
        t = _to_respond(m, t)
        self._replay(m, t, m.sequence)
        self.assertEqual(m.phase, "feedback")
        self.assertTrue(m._span_records[0]["correct"])
        self.assertEqual(m.span_len, 3)
        self.assertEqual(m._span_max_correct, 2)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "buzz_seq")
        self.assertEqual(row["early_late"], "Great")

    def test_wrong_order_shrinks_the_span_to_the_floor(self):
        m = self._span_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        wrong = list(reversed(m.sequence))
        if wrong == m.sequence:
            wrong = [m.sequence[0]] * len(m.sequence)
        self._replay(m, t, wrong)
        self.assertFalse(m._span_records[0]["correct"])
        self.assertEqual(m.span_len, 2)       # floor holds at 2

    def test_every_third_span_trial_is_the_hidden_sequence(self):
        from finger_rehab.game.modes.buzz_hunt import hebb_sequence
        m = self._span_mode(n=6)
        hebb_flags = []
        seqs = []
        for i in range(6):
            m.trials_done = i
            m._prepare_trial()
            hebb_flags.append(m.is_hebb)
            seqs.append(list(m.sequence))
            m._span_records.append({"len": len(m.sequence),
                                    "hebb": m.is_hebb, "correct": False,
                                    "n_right": 0})
        self.assertEqual(hebb_flags, [False, False, True,
                                      False, False, True])
        expected = hebb_sequence(m.p_seed, m.span_len, [0, 1, 2, 3])
        self.assertEqual(seqs[2], expected)
        self.assertEqual(seqs[5], expected)   # same length, same seq

    def test_sequence_plays_every_pulse_before_the_window(self):
        m = self._span_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        stims = [c for c in m.engine._sent if str(c).startswith("STIM")]
        self.assertEqual(len(stims), len(m.sequence))

    def test_a_press_during_playback_redraws_a_fresh_sequence(self):
        """An early press mid-playback must not silently replay the
        identical sequence: that gives a novel-span trial an extra,
        uncounted exposure before it is scored as a normal
        single-exposure trial (audit finding #92)."""
        m = self._span_mode()
        t = _to_trial(m)
        self.assertFalse(m.is_hebb)
        orig_seq = list(m.sequence)
        orig_seed = m.trial_seed
        dt = 1.0 / 60.0
        guard = t + 5.0
        while m._pulse_idx == 0 and t < guard:
            t += dt
            m._tick(t)
        self.assertEqual(m._pulse_idx, 1, "the first pulse must have "
                         "fired before the early press lands")
        m.queue_press(_press_event(orig_seq[0], t))
        m._tick(t + dt)
        self.assertEqual(m.sub, "wait")
        self.assertNotEqual(m.trial_seed, orig_seed)
        self.assertNotEqual(m.sequence, orig_seq,
                            "the retry must not replay the exact same "
                            "sequence the player already heard part of")

    def test_a_hebb_span_trial_keeps_its_material_across_a_restart(self):
        """A Hebb trial's sequence is deterministic from the
        participant, not the trial seed, so a mid-playback redraw
        must not turn it into a different (non-Hebb-comparable)
        sequence."""
        m = self._span_mode(n=6)
        # Two ordinary trials first, then the hidden-sequence one, the
        # same direct-draw pattern used elsewhere in this file to
        # inspect a specific trial's material without driving the
        # full phase machine (is_hebb keys off span_done, the number
        # of recorded span trials, not trials_done).
        for i in range(2):
            m.trials_done = i
            m._prepare_trial()
            m._span_records.append({"len": len(m.sequence), "hebb": False,
                                    "correct": False, "n_right": 0})
        m.trials_done = 2
        m._prepare_trial()
        self.assertTrue(m.is_hebb)
        orig_seq = list(m.sequence)
        m._redraw_interrupted_material()
        self.assertTrue(m.is_hebb)
        self.assertEqual(m.sequence, orig_seq)

    def test_span_row_parses_back_to_the_played_sequence(self):
        from finger_rehab.data.logger import parse_waveform_params
        from finger_rehab.game.modes.buzz_hunt import parse_lanes
        m = self._span_mode()
        t = _to_trial(m)
        played = list(m.sequence)
        t = _to_respond(m, t)
        self._replay(m, t, played)
        row = m.engine.trial_logger.rows[0]
        params = parse_waveform_params(row["waveform_params"])
        self.assertEqual(parse_lanes(params["seq"]), played)
        self.assertEqual(int(params["hebb"]), 0)

    def test_a_dropped_span_stimulus_is_voided_not_scored(self) -> None:
        """A span trial whose pulse train never fired must not enter
        the span curve or move the span ladder, whatever the player
        happened to press (audit finding #93)."""
        e = _engine()
        e.source.send_command = lambda c: (e._sent.append(c) or False)
        m = _mode(e)
        m = _only_stage(m, "span", 1)
        t = _to_trial(m)
        played = list(m.sequence)
        before_len = m.span_len
        t = _to_respond(m, t)
        self._replay(m, t, played)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["stim_delivered"], "FALSE")
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(m._span_records, [])
        self.assertEqual(m.span_len, before_len)
        self.assertEqual(m.engine._block_stim_failures, 1)


# ---- gap trials ---------------------------------------------------------


class GapTests(unittest.TestCase):
    def _gap_mode(self, n=4, **over):
        m = _mode(_engine(), **over)
        return _only_stage(m, "gap", n)

    def _answer(self, m, t, taps):
        for i in range(taps):
            m.queue_press(_press_event(m.lane, t + 0.2 + i * 0.15))
        t += m.response_window_s + 0.05
        m._tick(t)
        return t

    def _run_gap_trial(self, m, t, taps):
        t = _to_respond(m, t)
        t = self._answer(m, t, taps)
        self.assertEqual(m.phase, "feedback")
        return t

    def test_tap_count_judges_the_trial(self):
        m = self._gap_mode(n=8)
        t = _to_trial(m)
        results = []
        for i in range(4):
            two = m.gap_two
            t = self._run_gap_trial(m, t, taps=2 if two else 1)
            results.append(m._gap_records[-1]["correct"])
            if i < 3:
                t = _next_trial(m, t)
        self.assertTrue(all(results))

    def test_wrong_count_is_a_miss_and_raises_the_gap(self):
        m = self._gap_mode()
        t = _to_trial(m)
        two = m.gap_two
        before = m._gap_stair[m.hand].level
        self._run_gap_trial(m, t, taps=1 if two else 2)
        rec = m._gap_records[0]
        self.assertFalse(rec["correct"])
        # First move of the block sits in the accelerated approach,
        # so the wrong answer climbs at the doubled step.
        self.assertEqual(m._gap_stair[rec["hand"]].level,
                         before + 2 * m.gap_step_ms)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(row["waveform"], "buzz_gap")

    def test_no_response_holds_the_staircase(self):
        m = self._gap_mode()
        t = _to_trial(m)
        before = m._gap_stair["right"].level
        self._run_gap_trial(m, t, taps=0)
        self.assertEqual(m._gap_stair["right"].level, before)
        self.assertFalse(m._gap_records[0]["responded"])

    def test_a_dropped_gap_stimulus_is_voided_not_scored(self) -> None:
        """A gap trial whose pulse train never fired must not enter
        the gap accuracy or move the gap staircase (audit finding
        #93)."""
        e = _engine()
        e.source.send_command = lambda c: (e._sent.append(c) or False)
        m = _mode(e)
        m = _only_stage(m, "gap", 1)
        t = _to_trial(m)
        before = m._gap_stair["right"].level
        self._run_gap_trial(m, t, taps=2 if m.gap_two else 1)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["stim_delivered"], "FALSE")
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(m._gap_records, [])
        self.assertEqual(m._gap_stair["right"].level, before)
        self.assertEqual(m.engine._block_stim_failures, 1)

    def test_a_press_during_gap_playback_redraws_a_fresh_kind(self):
        """An early press mid-playback of a gap stimulus must not
        silently replay the identical (seed, kind) pair: it gives the
        trial an extra, uncounted exposure to the same stimulus
        before it scores as a normal single-exposure trial (audit
        finding #92, the gap-stage half). The fresh kind comes from
        the balanced bag, not a coin flip, so repeated redraws cannot
        unbalance the one/two distribution the staircase reads."""
        m = self._gap_mode()
        t = _to_trial(m)
        orig_seed = m.trial_seed
        dt = 1.0 / 60.0
        guard = t + 5.0
        while m._pulse_idx == 0 and t < guard:
            t += dt
            m._tick(t)
        self.assertEqual(m._pulse_idx, 1, "the first pulse must have "
                         "fired before the early press lands")
        bag_next = m._gap_kind_bag.next()
        m._gap_kind_bag.next = lambda _v=bag_next: _v
        m.queue_press(_press_event(m.lane, t))
        m._tick(t + dt)
        self.assertEqual(m.sub, "wait")
        self.assertNotEqual(m.trial_seed, orig_seed)
        self.assertEqual(m.gap_two, bool(bag_next))
        self.assertEqual(int(m.params["two"]), 1 if bag_next else 0)

    def test_a_gap_redraw_comes_from_the_balanced_bag(self):
        """Forty redraws must stay balanced. A fresh coin flip here
        meant that a patient who kept pressing during playback, or a
        therapist who kept pausing, quietly biased the one/two mix and
        the staircase read the bias as perception."""
        m = self._gap_mode()
        _to_trial(m)
        kinds = []
        for _ in range(40):
            m._redraw_interrupted_material()
            kinds.append(bool(m.gap_two))
        n_two = sum(1 for k in kinds if k)
        self.assertEqual(len(kinds), 40)
        # A balanced bag can never drift more than its own bag size
        # from even; a coin flip drifts without limit.
        self.assertLessEqual(abs(n_two - 20), 2)

    def test_gap_reversals_reach_the_raw_log(self):
        m = self._gap_mode(n=8)
        t = _to_trial(m)
        # Two correct answers (down), then a wrong one (up): reversal.
        for i in range(3):
            two = m.gap_two
            right = 2 if two else 1
            wrong = 1 if two else 2
            t = self._run_gap_trial(m, t, taps=right if i < 2 else wrong)
            if i < 2:
                t = _next_trial(m, t)
        revs = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "buzz_hunt_reversal"]
        self.assertEqual(len(revs), 1)
        self.assertIn("stair=gap", revs[0]["detail"])


# ---- block flow and stats -----------------------------------------------


class BlockFlowTests(unittest.TestCase):
    def test_stage_ladder_runs_in_order(self):
        m = _mode(_engine(), loc_trials_per_hand=1, span_trials=1,
                  gap_trials_per_hand=1)
        self.assertEqual(m._stage_plan, ["loc", "span", "gap"])

    def test_zero_count_stages_are_skipped_and_the_block_still_ends(self):
        """The study battery's short form runs localisation and span
        only (distractor and gap counts of zero). The block has to
        walk loc into span without a distractor card in between, end
        after the last span trial, and write block_stats with the
        empty stages reported as zero rather than missing or raising
        on an untouched gap staircase."""
        m = _mode(_engine(), catch_rate=0.0, loc_trials_per_hand=1,
                  distractor_trials_per_hand=0, span_trials=1,
                  gap_trials_per_hand=0)
        self.assertEqual(m._stage_plan, ["loc", "span"])
        self.assertEqual(m.total_trials, 2)
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        # Localisation trial: one correct press.
        t = _to_trial(m)
        self.assertEqual(m.stage, "loc")
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        self.assertEqual(m.phase, "feedback")
        # Straight to the span stage card, no distractor stage.
        t = _next_trial(m, t + 0.21)
        self.assertEqual(m.stage, "span")
        self.assertEqual(m.stage_shown, "span")
        t = _to_respond(m, t)
        seq = list(m.sequence)
        for i, lane in enumerate(seq):
            m.queue_press(_press_event(lane, t + 0.2 + i * 0.1))
        m._tick(t + 0.2 + len(seq) * 0.1 + 0.01)
        self.assertEqual(m.phase, "feedback")
        m._tick(t + 0.2 + len(seq) * 0.1 + 0.01 + m.rest_s + 0.05)
        self.assertEqual(m.phase, "done")
        self.assertTrue(finished)
        stats = m.block_stats()
        self.assertEqual(stats["stages"], {"loc": 1, "distractor": 0,
                                           "span": 1, "gap": 0})
        self.assertEqual(stats["loc"]["trials"], 1)
        self.assertEqual(stats["distractor"]["trials"], 0)
        self.assertEqual(stats["span"]["trials"], 1)
        self.assertEqual(stats["gap"]["trials"], 0)
        self.assertEqual(stats["gap"]["threshold"]["right"]["n_reversals"],
                         0)

    def test_block_ends_and_carries_the_window_level(self):
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "loc", 1)
        m._window["right"].level = 2
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        t = _to_trial(m)
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        m._tick(t + 0.21 + m.rest_s + 0.05)
        self.assertEqual(m.phase, "done")
        self.assertTrue(finished)
        self.assertEqual(m.engine._buzz_hunt_window_level, {"right": 2})
        # The duration carry belongs to the legacy flag only, so a
        # window block can never seed a staircase block.
        self.assertFalse(hasattr(m.engine, "_buzz_hunt_start_ms"))

    def test_carried_level_seeds_the_next_block(self):
        e = _engine()
        e._buzz_hunt_window_level = {"right": 2}
        m = _mode(e)
        self.assertEqual(m._window["right"].level, 2)
        self.assertEqual(m._window["right"].window_s, 1.2)
        # An out-of-range carry clamps to the ladder.
        e._buzz_hunt_window_level = {"right": 9}
        self.assertEqual(_mode(e)._window["right"].level, 3)

    def test_block_stats_carry_the_results_summary(self):
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "loc", 2)
        m.engine.finish_block = lambda: None
        t = _to_trial(m)
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        t = _next_trial(m, t + 0.21)
        t = _to_respond(m, t)
        wrong = next(l for l in range(4) if l != m.lane)
        m.queue_press(_press_event(wrong, t + 0.2))
        m._tick(t + 0.21)
        stats = m.block_stats()
        self.assertEqual(stats["loc"]["trials"], 2)
        self.assertEqual(stats["loc"]["accuracy"], 0.5)
        self.assertIsNotNone(stats["loc"]["median_rt_ms"])
        self.assertEqual(stats["span"]["trials"], 0)
        self.assertIn("confusion", stats)
        # The 2026-09 summary: the pulse, the window ladder per hand,
        # the per-hand localisation block, and NO threshold dict (an
        # untouched staircase start must never read as a measurement).
        self.assertEqual(stats["pulse_ms"], 150.0)
        self.assertFalse(stats["duration_staircase"])
        self.assertEqual(stats["threshold"], {})
        self.assertTrue(stats["window"]["active"])
        self.assertEqual(stats["window"]["levels_s"], [2.0, 1.5, 1.2, 1.0])
        right = stats["window"]["per_hand"]["right"]
        self.assertEqual(right["top_level"], 0)
        self.assertEqual(right["trace"], [0, 0])
        self.assertEqual(stats["window"]["top_level"], 0)
        loc_r = stats["loc"]["per_hand"]["right"]
        self.assertEqual(loc_r["trials"], 2)
        self.assertEqual(loc_r["accuracy"], 0.5)
        self.assertEqual(loc_r["by_level"]["0"]["n"], 2)
        self.assertEqual(loc_r["by_level"]["0"]["window_s"], 2.0)
        # No catch trials, so no false-alarm rate and no d-prime.
        self.assertIsNone(loc_r["d_prime"])
        self.assertIsNone(stats["loc"]["d_prime"])

    def test_d_prime_comes_from_the_catch_trials_per_hand(self):
        from statistics import NormalDist
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "loc", 3)
        m.engine.finish_block = lambda: None
        t = _to_trial(m)
        t = _to_respond(m, t)
        t = _answer_loc(m, t, correct=True)
        # The next two trials are catch trials (the rate is read at
        # draw time): one waited out, one false alarm.
        m.catch_rate = 1.0
        t = _next_trial(m, t)
        self.assertTrue(m.catch)
        t = _to_respond(m, t)
        t += m._respond_window_s() + 0.05
        m._tick(t)
        t = _next_trial(m, t)
        self.assertTrue(m.catch)
        t = _to_respond(m, t)
        m.queue_press(_press_event(2, t + 0.4))
        m._tick(t + 0.41)
        stats = m.block_stats()
        loc_r = stats["loc"]["per_hand"]["right"]
        self.assertEqual(loc_r["catch_n"], 2)
        self.assertEqual(loc_r["false_alarms"], 1)
        self.assertEqual(loc_r["fa_rate"], 0.5)
        z = NormalDist().inv_cdf
        want = round(z((1 + 0.5) / 2.0) - z((1 + 0.5) / 3.0), 3)
        self.assertEqual(loc_r["d_prime"], want)
        self.assertEqual(stats["loc"]["d_prime"], want)

    def test_frame_stall_across_a_gap_voids_the_trial(self):
        # A stall longer than the silent gap dispatches the overdue
        # STOP and the next STIM in one frame, delivering one merged
        # buzz; the trial used to score the patient against 'two' on a
        # stimulus that was never two buzzes. Late-past-half-the-gap
        # voids it like a dropped pulse.
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "gap", 2)
        t = _to_trial(m)
        # Reach the play sub-phase, force a two-pulse plan so a gap
        # exists to collapse, let the FIRST pulse go out, then stall a
        # whole second across the silent gap. (The dispatcher sends at
        # most one pulse per frame now, so the stall has to land
        # between the two rather than before both.)
        guard = t + 30.0
        while m.sub != "play" and t < guard:
            t += 1.0 / 60.0
            m._tick(t)
        if len(m._pulse_plan) < 2:
            m.gap_two = True
            m.params["two"] = 1
            from finger_rehab.game.modes.buzz_hunt import (
                pulses_from_params)
            m._pulse_plan = pulses_from_params(m.waveform, m.params)
        t += 1.0 / 60.0
        m._tick(t)
        self.assertEqual(m._pulse_idx, 1, "the first short must be out")
        m._tick(t + 1.0)
        self.assertEqual(m._pulse_idx, 2, "the second short follows")
        self.assertIs(m._stim_delivered, False)
        events = [ev for ev in m.engine.raw_logger.events
                  if ev["event"] == "stim_late_pulse"]
        self.assertEqual(len(events), 1)

    def test_span_rows_stamp_the_real_response_window(self):
        # timeout_ms is documented as the RT censoring limit, and a
        # span trial's real window is response_window_s plus replay
        # time per item; the bare response_window_s used to be
        # stamped on every stage.
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "span", 1)
        _to_trial(m)
        want = (m.response_window_s
                + m.replay_item_s * len(m.sequence)) * 1000.0
        self.assertEqual(m.engine._last_stim_timeout_ms, want)
        self.assertGreater(want, m.response_window_s * 1000.0)

    def test_session_cap_ends_between_trials_data_kept(self):
        # The cap fires at a card, never mid-trial: a trial in flight
        # finishes and is scored, then the block ends with everything
        # played kept and end_reason time_cap. The constructor floors
        # the cap at one minute, so the fake clock jumps past that.
        m = _mode(_engine(), catch_rate=0.0, session_cap_min=1.0)
        m = _only_stage(m, "loc", 50)
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        t = _to_trial(m)
        t = _to_respond(m, t)
        # Past the cap mid-trial: the trial must still close normally.
        t += 61.0
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        self.assertEqual(m.phase, "feedback",
            "the in-flight trial must finish and be scored first")
        self.assertEqual(len(m.engine.trial_logger.rows), 1)
        # The next between-trial tick ends the block instead of
        # dealing trial two.
        m._tick(t + 0.21 + m.rest_s + 0.05)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "time_cap")
        self.assertTrue(finished)
        self.assertEqual(m.block_stats()["end_reason"], "time_cap")
        self.assertEqual(m.block_stats()["loc"]["trials"], 1)

    def test_session_cap_fires_on_a_parked_card_too(self):
        # Nobody at the pads: the block sits on the stage card
        # forever. The cap must end it anyway (the lesson chords
        # learnt: a cap that only ticks at trial closes never fires
        # when no trial ever closes).
        m = _mode(_engine(), catch_rate=0.0, session_cap_min=1.0)
        m = _only_stage(m, "loc", 50)
        m.engine.finish_block = lambda: None
        m._tick(1000.0)
        self.assertEqual(m.phase, "stage")
        m._tick(1000.0 + 61.0)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "time_cap")

    def test_config_ships_the_cap(self):
        from finger_rehab.config import Config
        self.assertEqual(
            float(Config.load().get("buzz_hunt.session_cap_min")), 15.0)

    def test_distractor_overlap_is_not_voided_at_sixty_hz(self):
        # A distractor trial's two pulses sit on different boards and
        # at the fixed 150 ms pulse with the 150 ms lead their planned
        # silence is zero, well under one display frame; the
        # same-board void guard used to void these on every ordinary
        # frame (measured: half the distractor stage voided when the
        # old staircase sat near 150 ms). Cross-board plans skip the
        # void; the gap trial's same-board guard is pinned by
        # test_frame_stall_across_a_gap_voids.
        hands = {"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]}
        m = _mode(_engine("both"), hands=hands, catch_rate=0.0)
        m = _only_stage(m, "distractor", 2)
        t = _to_trial(m)
        t = _to_respond(m, t)
        self.assertEqual(m._pulse_idx, 2, "both pulses dispatched")
        self.assertIs(m._stim_delivered, True)
        late = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "stim_late_pulse"]
        self.assertEqual(late, [])
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        self.assertEqual(len(m._dis_records), 1,
            "the trial must land in the distractor records, not void")

    def test_pause_mid_trial_restarts_it(self):
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "loc", 2)
        t = _to_trial(m)
        t = _to_respond(m, t)
        trial_before = m.trial_counter
        m.on_resume(5.0)
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.trial_counter, trial_before)
        self.assertEqual(m.engine.trial_logger.rows, [])
        restarts = [ev for ev in m.engine.raw_logger.events
                    if ev["event"] == "trial_restart"]
        self.assertEqual(len(restarts), 1)

    def test_pause_restart_redraws_the_material(self):
        # The restart used to keep the same seed and plan, so a span
        # or gap trial could be heard twice and scored as a single
        # exposure; on a gap trial the replayed kind IS the answer,
        # making the Esc chip a repeatable exploit. The retry draws
        # fresh material for the same trial slot, exactly like the
        # early-press path.
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "gap", 2)
        t = _to_trial(m)
        t = _to_respond(m, t)
        seed_before = m.trial_seed
        m.on_resume(5.0)
        self.assertEqual(m.phase, "announce")
        self.assertNotEqual(m.trial_seed, seed_before)

    def test_pause_restart_keeps_a_hebb_sequence(self):
        # The hidden Hebb sequence is derived from the participant,
        # not the trial seed: its repetition across the session is the
        # measurement, so the redraw must not touch it.
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "span", 6)
        t = _to_trial(m)
        guard = t + 60.0
        while not m.is_hebb and t < guard:
            t = _to_respond(m, t)
            m.queue_press(_press_event(m.sequence[0], t + 0.2))
            t += 0.3
            m._tick(t)
            while m.phase != "trial" and t < guard:
                t += 1.0 / 60.0
                m._tick(t)
        self.assertTrue(m.is_hebb)
        seq_before = list(m.sequence)
        m.on_resume(5.0)
        self.assertEqual(list(m.sequence), seq_before)

    def test_keyboard_source_is_refused_plainly(self):
        e = _engine()
        e.source.provides_samples = False
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "no_input")

    def test_demo_cap_compresses_every_stage(self):
        m = _mode(_engine(), demo_trials=6)
        self.assertLessEqual(m.total_trials, 8)
        for stage in ("loc", "span", "gap"):
            self.assertGreaterEqual(m._stage_counts[stage], 1)

    def test_staircase_floor_respects_the_hardware(self):
        from finger_rehab.game.modes.buzz_hunt import LEVEL_FLOOR_MS
        m = _mode(_engine(), floor_ms=5.0, start_ms=50.0)
        self.assertEqual(m.floor_ms, LEVEL_FLOOR_MS)

    def test_fixed_pulses_and_the_gap_floor_respect_the_motor(self):
        # Every fixed pulse is a felt pulse (Kaaresoja and Linjama's
        # 50 ms) and a silent gap is never shorter than the motor's
        # spin-down (120 ms), whatever the config asks for.
        from finger_rehab.game.modes.buzz_hunt import (FELT_PULSE_FLOOR_MS,
                                                        GAP_FLOOR_MS)
        m = _mode(_engine(), loc_pulse_ms=20.0, span_pulse_ms=30.0,
                  gap_short_ms=25.0, gap_floor_ms=35.0, gap_start_ms=60.0)
        self.assertEqual(m.loc_pulse_ms, FELT_PULSE_FLOOR_MS)
        self.assertEqual(m.span_pulse_ms, FELT_PULSE_FLOOR_MS)
        self.assertEqual(m.gap_short_ms, FELT_PULSE_FLOOR_MS)
        self.assertEqual(m.gap_floor_ms, GAP_FLOOR_MS)
        self.assertEqual(m.gap_start_ms, GAP_FLOOR_MS)
        self.assertEqual(m._gap_stair["right"].floor, GAP_FLOOR_MS)

    def test_config_ships_the_fixed_pulse_and_the_ladder(self):
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(float(cfg.get("buzz_hunt.loc_pulse_ms")), 150.0)
        self.assertEqual([float(v) for v in
                          cfg.get("buzz_hunt.window_levels_s")],
                         [3.0, 2.0, 1.5, 1.2])
        self.assertEqual(list(cfg.get("buzz_hunt.window_promote")), [6, 8])
        self.assertEqual(list(cfg.get("buzz_hunt.window_demote")), [2, 4])
        self.assertFalse(bool(cfg.get("buzz_hunt.duration_staircase")))
        self.assertEqual(float(cfg.get("buzz_hunt.gap_floor_ms")), 150.0)
        self.assertEqual(float(cfg.get("buzz_hunt.gap_short_ms")), 150.0)
        self.assertGreater(float(cfg.get("buzz_hunt.gap_start_ms")),
                           float(cfg.get("buzz_hunt.gap_floor_ms")))


# ---- nothing may stall the block ----------------------------------------


class BlockAlwaysAdvancesTests(unittest.TestCase):
    """The reliability floor: no player behaviour, and no hardware
    behaviour, may leave the block sitting with no trial running and
    no buzz coming.

    Every case here reproduced a permanent freeze before the per-trial
    wall existed. They shared one root cause: nothing inside
    phase 'trial' had a deadline, so a trial that could not close took
    the whole block down with it and the block never ended, never
    buzzed again and never wrote a summary. Measured on the shipped
    settings, a stuck finger sat fifty minutes past a fifteen minute
    cap at nine trials of sixty-two.
    """

    def _loc(self, n=20, **over):
        kw = dict(catch_rate=0.0)
        kw.update(over)
        m = _mode(_engine(), **kw)
        m.engine.finish_block = lambda: None
        return _only_stage(m, "loc", n)

    def test_a_finger_left_on_a_pad_does_not_freeze_the_block(self):
        m = self._loc()
        dets = _attach_detectors(m.engine)
        t = _to_trial(m)
        dets["right"].pressed[2] = True
        t = _run_frames(m, t, 60.0)
        self.assertTrue(dets["right"].pressed[2], "the finger stayed down")
        self.assertGreater(m.trials_done, 0,
                           "the wall must start the trial anyway")
        forced = [ev for ev in m.engine.raw_logger.events
                  if ev["event"] == "buzz_hunt_gate_forced"]
        self.assertTrue(forced)
        self.assertIn("reason=fingers_down", forced[0]["detail"])
        self.assertGreater(m.forced_starts, 0)

    def test_a_finger_on_the_other_hand_does_not_freeze_the_block(self):
        # _fingers_down scans every detector, not the trial's hand, so
        # in bilateral play a resting left hand blocked a right-hand
        # trial. The wall covers that too.
        hands = {"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]}
        m = _mode(_engine("both"), hands=hands, catch_rate=0.0)
        m.engine.finish_block = lambda: None
        m = _only_stage(m, "loc", 20)
        dets = _attach_detectors(m.engine, hands=("right", "left"))
        t = _to_trial(m)
        dets["left"].pressed[0] = True
        _run_frames(m, t, 60.0)
        self.assertGreater(m.trials_done, 0)

    def test_a_stuck_finger_still_reaches_the_session_cap(self):
        # The cap used to be checked only on cards, so a gate that
        # never opened held the cap off as well as the block.
        m = self._loc(n=200, session_cap_min=1.0)
        dets = _attach_detectors(m.engine)
        t = _to_trial(m)
        dets["right"].pressed[0] = True
        _run_frames(m, t, 400.0)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "time_cap")

    def test_a_press_train_cannot_hold_the_wait_gate_forever(self):
        # Any press faster than REST_GATE_S plus the drawn foreperiod
        # (up to 2.7 s shipped) restarted the gate for good: measured
        # 1764 early-press events, two trials of sixty-two, and half
        # an hour of silence.
        m = self._loc()
        _attach_detectors(m.engine)
        t = _to_trial(m)
        seen = {"play": False}

        def hook(mode, now):
            if mode.sub == "play":
                seen["play"] = True
            return None

        train = _press_train(period_s=1.0)

        def both(mode, now):
            train(mode, now)
            return hook(mode, now)

        _run_frames(m, t, 90.0, hook=both)
        self.assertTrue(seen["play"], "the stimulus must reach the hand")
        self.assertGreater(m.trials_done, 0)

    def test_a_tap_during_gap_playback_cannot_replay_forever(self):
        # The gap stimulus runs 420 to 620 ms at the shipped
        # staircase, so anyone with an ordinary simple reaction time
        # taps inside it. Every tap was an abort and a replay, and the
        # next replay drew the same tap: 582 aborted playbacks over
        # thirty minutes and one trial of twenty-one.
        m = _mode(_engine(), catch_rate=0.0)
        m.engine.finish_block = lambda: None
        m = _only_stage(m, "gap", 20)
        _attach_detectors(m.engine)
        t = _to_trial(m)
        _run_frames(m, t, 300.0, hook=_tap_along(0.3))
        self.assertGreaterEqual(m.trials_done, 5)

    def test_a_tap_during_span_playback_cannot_replay_forever(self):
        m = _mode(_engine(), catch_rate=0.0)
        m.engine.finish_block = lambda: None
        m = _only_stage(m, "span", 20)
        _attach_detectors(m.engine)
        t = _to_trial(m)
        _run_frames(m, t, 300.0, hook=_tap_along(0.3))
        self.assertGreaterEqual(m.trials_done, 5)

    def test_the_abort_still_protects_a_single_exposure(self):
        # Before the wall is spent the old behaviour is unchanged: one
        # early press redraws the material and re-waits, so a partial
        # exposure is never scored as a full one.
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "gap", 2)
        t = _to_trial(m)
        while m._pulse_idx == 0 and t < 1100.0:
            t += 1.0 / 60.0
            m._tick(t)
        seed_before = m.trial_seed
        m.queue_press(_press_event(m.lane, t))
        m._tick(t + 1.0 / 60.0)
        self.assertEqual(m.sub, "wait")
        self.assertEqual(m.trials_done, 0)
        self.assertNotEqual(m.trial_seed, seed_before)
        self.assertEqual(m._wall_forced, "")

    def test_a_press_past_the_wall_becomes_the_answer(self):
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "gap", 2)
        t = _to_trial(m)
        while m._pulse_idx == 0 and t < 1100.0:
            t += 1.0 / 60.0
            m._tick(t)
        # Spend the wall, then press mid-playback.
        m._trial_wall = t - 0.001
        m.queue_press(_press_event(m.lane, t))
        m._tick(t + 1.0 / 60.0)
        self.assertEqual(m.phase, "feedback")
        self.assertEqual(m.trials_done, 1)
        early = [ev for ev in m.engine.raw_logger.events
                 if ev["event"] == "buzz_hunt_early"
                 and "trial_wall_spent=True" in ev["detail"]]
        self.assertTrue(early)
        row = m.engine.trial_logger.rows[-1]
        self.assertIn("wall_forced=play:trial_wall_spent",
                      row["stimulus"])

    def test_the_watchdog_closes_a_trial_that_cannot_end(self):
        # Belt and braces: if a sub-phase deadline ever grows a hole,
        # the trial closes and says so rather than the block sitting.
        m = self._loc(n=4)
        _attach_detectors(m.engine)
        t = _to_trial(m)
        t = _to_respond(m, t)
        m._respond_t0 = t + 1e6            # a window that never closes
        t += m._trial_watchdog_s() + 1.0
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        forced = [ev for ev in m.engine.raw_logger.events
                  if ev["event"] == "buzz_hunt_trial_forced"]
        self.assertTrue(forced)
        self.assertIn("reason=watchdog", forced[0]["detail"])

    def test_a_pause_before_the_stimulus_does_not_restart_the_trial(self):
        # Restarting a trial that had delivered nothing cost a whole
        # announce card plus a fresh foreperiod for nothing: a patient
        # pausing every six seconds played eight trials of sixty-two.
        m = self._loc(n=4)
        t = _to_trial(m)
        self.assertEqual(m.sub, "wait")
        self.assertEqual(m._pulse_idx, 0)
        counter_before = m.trial_counter
        m.on_resume(5.0)
        self.assertEqual(m.phase, "trial")
        self.assertEqual(m.sub, "wait")
        self.assertEqual(m.trial_counter, counter_before)
        restarts = [ev for ev in m.engine.raw_logger.events
                    if ev["event"] == "trial_restart"]
        self.assertEqual(restarts, [])

    def test_a_pause_after_the_stimulus_still_restarts_the_trial(self):
        m = self._loc(n=4)
        t = _to_trial(m)
        _to_respond(m, t)
        m.on_resume(5.0)
        self.assertEqual(m.phase, "announce")
        restarts = [ev for ev in m.engine.raw_logger.events
                    if ev["event"] == "trial_restart"]
        self.assertEqual(len(restarts), 1)

    def test_a_restart_ties_off_the_stimulus_segment(self):
        # An unbalanced segment leaves the notebook pairing this
        # trial's stim start with the NEXT trial's stim end.
        m = self._loc(n=4)
        t = _to_trial(m)
        _to_respond(m, t)
        m._stim_seg_open = True
        m.engine.log_segment_end = lambda *a, **k: ends.append(a)
        ends = []
        m.on_resume(5.0)
        self.assertTrue(ends, "the open stim marker must be closed")
        self.assertFalse(m._stim_seg_open)

    def test_a_board_that_stops_accepting_stim_ends_the_block(self):
        # 45 silent trials and an end_reason of "completed" was the
        # worst version of this: the block claimed a result it never
        # measured. Three delivery failures in a row end it honestly.
        e = _engine()
        state = {"ok": True}
        e.source.send_command = lambda c: (e._sent.append(c)
                                           or state["ok"])
        m = _mode(e, catch_rate=0.0)
        m.engine.finish_block = lambda: None
        m = _only_stage(m, "loc", 30)
        _attach_detectors(e)
        t = _to_trial(m)
        for i in range(12):
            if m.phase == "done":
                break
            if i == 2:
                state["ok"] = False
            t = _to_respond(m, t)
            t = _answer_loc(m, t)
            if m.phase == "feedback":
                t += m.rest_s + 0.01
                m._tick(t)
                if m.phase in ("stage", "announce"):
                    t += m.stage_intro_s + m.announce_s + 0.02
                    m._tick(t)
                    if m.phase == "announce":
                        t += m.announce_s + 0.01
                        m._tick(t)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "stim_lost")
        lost = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "stim_lost"]
        self.assertTrue(lost)
        first = [ev for ev in m.engine.raw_logger.events
                 if ev["event"] == "buzz_hunt_stim_fail"]
        self.assertTrue(first, "raw.csv must carry the moment it went")
        self.assertGreater(m.trials_done, 0, "what played is kept")
        self.assertTrue(m.block_stats()["reliability"]["stim_lost"])

    def test_a_good_trial_clears_the_dead_board_run(self):
        # A single dropped pulse is not a dead board.
        e = _engine()
        state = {"ok": False}
        e.source.send_command = lambda c: (e._sent.append(c)
                                           or state["ok"])
        m = _mode(e, catch_rate=0.0)
        m.engine.finish_block = lambda: None
        m = _only_stage(m, "loc", 10)
        _attach_detectors(e)
        t = _to_trial(m)
        t = _to_respond(m, t)
        t = _answer_loc(m, t)
        self.assertEqual(m._stim_fail_run, 1)
        state["ok"] = True
        t = _next_trial(m, t)
        t = _to_respond(m, t)
        _answer_loc(m, t)
        self.assertEqual(m._stim_fail_run, 0)
        self.assertFalse(m._stim_lost)

    def test_a_long_frame_never_burst_fires_a_span_train(self):
        # One 2 s frame used to dispatch every overdue pulse at once.
        # Each pulse_motor landed inside the previous lane's firmware
        # hold, so _send_stim wrote a STOP first and three span items
        # of exactly 0 ms went out. One pulse per frame, and the rest
        # of the plan shifts out by the lateness instead of
        # compressing.
        m = _mode(_engine(), catch_rate=0.0, span_start=5)
        m = _only_stage(m, "span", 1)
        t = _to_trial(m)
        while m._pulse_idx < 1 and t < 1100.0:
            t += 1.0 / 60.0
            m._tick(t)
        before = len(_stim_requests(m))
        respond_before = m._respond_t0
        m._tick(t + 2.0)
        after = len(_stim_requests(m))
        self.assertEqual(after - before, 1,
                         "at most one pulse may go out per frame")
        self.assertGreater(m._plan_shift_s, 0.0, "the plan re-anchored")
        self.assertGreater(m._respond_t0, respond_before,
                           "the window moves with the stimulus")

    def test_a_late_pulse_still_voids_the_trial(self):
        # The re-anchor must not hide the disturbance: the event and
        # the voided row both survive it.
        m = _mode(_engine(), catch_rate=0.0, span_start=4)
        m = _only_stage(m, "span", 1)
        t = _to_trial(m)
        while m._pulse_idx < 1 and t < 1100.0:
            t += 1.0 / 60.0
            m._tick(t)
        m._tick(t + 2.0)
        self.assertIs(m._stim_delivered, False)
        late = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "stim_late_pulse"]
        self.assertTrue(late)
        t = _to_respond(m, t + 2.0)
        t += m._respond_window_s() + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        row = m.engine.trial_logger.rows[-1]
        self.assertIn("stim_failed=True", row["stimulus"])
        self.assertEqual(m._span_records, [])

    def test_no_player_behaviour_can_stall_the_block(self):
        """The point of all of it: whatever the patient, the
        therapist or the hardware does, the block reaches phase
        'done' with an end_reason recorded."""
        def never_responds(m, now):
            return None

        def presses_constantly(m, now):
            return _press_train(period_s=0.5)(m, now)

        def pauses_often(state={}):
            def hook(m, now):
                nxt = state.setdefault("next", now + 5.0)
                if now >= nxt:
                    state["next"] = now + 5.0
                    m.on_resume(0.5)
                return None
            return hook

        def long_frames(state={}):
            def hook(m, now):
                nxt = state.setdefault("next", now + 7.0)
                if now >= nxt:
                    state["next"] = now + 7.0
                    return 2.0
                return None
            return hook

        cases = {
            "never responds": (never_responds, None, False),
            "presses every 0.5 s": (presses_constantly, None, False),
            "taps 300 ms into every playback": (_tap_along(0.3), None,
                                                False),
            "leaves a finger on a pad": (never_responds, None, True),
            "pauses every 5 s": (pauses_often(), None, False),
            "two second frames": (long_frames(), None, False),
            "a board that dies": (never_responds, 6, False),
        }
        for label, (hook, die_after, stick) in cases.items():
            with self.subTest(behaviour=label):
                e = _engine()
                calls = {"n": 0}

                def send(c, _e=e, _n=die_after, _c=calls):
                    _c["n"] += 1
                    _e._sent.append(c)
                    return not (_n is not None and _c["n"] > _n)

                e.source.send_command = send
                m = _mode(e, catch_rate=0.1, session_cap_min=2.0,
                          gap_trials_per_hand=3, span_trials=3,
                          loc_trials_per_hand=6)
                m.engine.finish_block = lambda: None
                dets = _attach_detectors(e)
                t = _to_trial(m)
                if stick:
                    dets["right"].pressed[1] = True
                _run_frames(m, t, 1800.0, hook=hook)
                self.assertEqual(m.phase, "done", label)
                self.assertIsNotNone(m.end_reason, label)


# ---- the window ladder --------------------------------------------------


class WindowLadderTests(unittest.TestCase):
    """The mastery rule that replaced the duration staircase for
    localisation: promote on 6 correct of the last 8 at a level,
    demote on 2 misses in the last 4, clamped at both ends, history
    cleared on every move, the level traced per trial."""

    def _ladder(self, **over):
        from finger_rehab.game.modes.buzz_hunt import WindowLadder
        kw = dict(levels_s=[3.0, 2.0, 1.5, 1.2])
        kw.update(over)
        return WindowLadder(**kw)

    def test_six_straight_corrects_promote(self):
        w = self._ladder()
        moves = [w.record(True) for _ in range(6)]
        self.assertEqual(moves, [None] * 5 + ["up"])
        self.assertEqual(w.level, 1)
        self.assertEqual(w.window_s, 2.0)
        self.assertEqual(w.trace, [0] * 6)

    def test_six_of_eight_promote_with_misses_spread_out(self):
        w = self._ladder()
        # Two misses inside eight, never two within four.
        pattern = [True, True, False, True, True, True, False, True]
        moves = [w.record(c) for c in pattern]
        self.assertEqual(w.level, 1)
        self.assertEqual(moves[-1], "up")

    def test_two_misses_in_four_demote_and_the_bottom_holds(self):
        w = self._ladder(start_level=1)
        self.assertEqual([w.record(c) for c in (True, False, True, False)],
                         [None, None, None, "down"])
        self.assertEqual(w.level, 0)
        self.assertEqual([w.record(False) for _ in range(4)],
                         [None] * 4)
        self.assertEqual(w.level, 0)
        self.assertEqual(w.n_demotions, 1)

    def test_the_top_holds(self):
        w = self._ladder(start_level=3)
        self.assertTrue(w.top)
        self.assertEqual([w.record(True) for _ in range(8)], [None] * 8)
        self.assertEqual(w.level, 3)
        self.assertEqual(w.top_level, 3)

    def test_history_clears_on_a_move(self):
        w = self._ladder()
        for _ in range(6):
            w.record(True)
        self.assertEqual(w.level, 1)
        # A fresh level starts from nothing: six more are needed.
        self.assertEqual([w.record(True) for _ in range(5)], [None] * 5)
        self.assertEqual(w.record(True), "up")
        self.assertEqual(w.level, 2)
        self.assertEqual(w.n_promotions, 2)

    def test_summary_names_the_shape(self):
        w = self._ladder()
        for c in (True,) * 6 + (False, False):
            w.record(c)
        s = w.summary()
        self.assertEqual(s["start_level"], 0)
        self.assertEqual(s["top_level"], 1)
        self.assertEqual(s["final_level"], 0)
        self.assertEqual(s["top_window_s"], 2.0)
        self.assertEqual(s["final_window_s"], 3.0)
        self.assertEqual(s["trace"], [0] * 6 + [1, 1])

    def test_start_level_clamps_and_levels_sort_longest_first(self):
        w = self._ladder(start_level=7)
        self.assertEqual(w.level, 3)
        m = _mode(_engine(), window_levels_s=[1.0, 3.0, 2.0])
        self.assertEqual(m.window_levels_s, [3.0, 2.0, 1.0])
        self.assertEqual(m._window["right"].window_s, 3.0)


# ---- the legacy duration staircase --------------------------------------


class LegacyDurationStaircaseTests(unittest.TestCase):
    """buzz_hunt.duration_staircase true replays the pre-2026-09
    localisation exactly: the pulse walks the 2-down 1-up staircase,
    the window stays flat, rows carry stair_ms and the reversal flag,
    block_stats carries the threshold dict and the duration carry.
    The recorded level sequence below was captured on the build that
    shipped the staircase (tests/test_buzz_hunt.py at 2811166, seed
    7, one hand, 24 trials: correct except a wrong finger on trials
    3, 8, 13, 18, 23 and a timeout on trials 7, 14, 21)."""

    RECORDED_LEVELS = [300.0, 220.0, 140.0, 180.0, 180.0, 140.0, 140.0,
                       180.0, 220.0, 220.0, 180.0, 180.0, 140.0, 180.0,
                       220.0, 220.0, 180.0, 180.0, 220.0, 220.0, 180.0,
                       220.0, 220.0, 260.0]
    RECORDED_REVERSALS = [140.0, 180.0, 140.0, 220.0, 140.0, 220.0,
                          180.0, 220.0, 180.0]

    def _legacy(self, e=None, n=4, **over):
        over.setdefault("duration_staircase", True)
        m = _mode(e or _engine(), **over)
        return _only_stage(m, "loc", n)

    def test_flag_reproduces_the_recorded_level_sequence(self):
        m = self._legacy(n=24, seed=7, catch_rate=0.0)
        m.engine.finish_block = lambda: None
        t = _to_trial(m)
        levels = []
        for i in range(24):
            levels.append(float(m.params["dur_ms"]))
            t = _to_respond(m, t)
            if i % 7 == 6:
                t += m.response_window_s + 0.05
                m._tick(t)
            else:
                t = _answer_loc(m, t, correct=(i % 5 != 2))
            if i < 23:
                t = _next_trial(m, t)
        self.assertEqual(levels, self.RECORDED_LEVELS)
        stats = m.block_stats()
        thr = stats["threshold"]["right"]
        self.assertEqual(thr["final_ms"], 260.0)
        self.assertEqual(thr["estimate_ms"], 193.3)
        self.assertEqual(thr["reversals_ms"], self.RECORDED_REVERSALS)
        self.assertTrue(stats["duration_staircase"])
        self.assertFalse(stats["window"]["active"])
        self.assertEqual(_stim_requests(m), self.RECORDED_LEVELS)

    def test_timeout_raises_the_staircase(self):
        # Still inside the accelerated approach (no reversal yet), so
        # the up-move runs at the doubled step; FastStartTests pins
        # the rule itself.
        m = self._legacy()
        t = _to_trial(m)
        t = _to_respond(m, t)
        before = m._dur_stair[m.hand].level
        t += m.response_window_s + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        self.assertEqual(m._dur_stair[m.hand].level,
                         before + 2 * m.step_ms)
        row = m.engine.trial_logger.rows[0]
        self.assertIn("stair_ms=", row["stimulus"])
        self.assertIn("reversal=False", row["stimulus"])
        self.assertNotIn("level=", row["stimulus"])

    def test_correct_answers_lower_the_duration(self):
        # During the accelerated approach every single correct steps
        # down at double size, so two corrects descend four base
        # steps (see Staircase.fast_start).
        m = self._legacy(n=3)
        t = _to_trial(m)
        start = m._dur_stair["right"].level
        for i in range(2):
            t = _to_respond(m, t)
            t = _answer_loc(m, t, correct=True, rt=0.2)
            if i < 1:
                t = _next_trial(m, t)
        self.assertEqual(m._dur_stair["right"].level,
                         start - 4 * m.step_ms)
        # And the window ladder never moved: the flag owns difficulty.
        self.assertEqual(m._window["right"].trace, [])

    def test_reversal_is_logged_as_an_event(self):
        m = self._legacy(n=6)
        t = _to_trial(m)
        for i in range(3):
            t = _to_respond(m, t)
            if i < 2:
                t = _answer_loc(m, t, correct=True, rt=0.2)
                t = _next_trial(m, t)
            else:
                t += m.response_window_s + 0.05
                m._tick(t)
        revs = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "buzz_hunt_reversal"]
        self.assertEqual(len(revs), 1)
        self.assertIn("stair=duration", revs[0]["detail"])

    def test_distractor_trials_hold_the_staircase_still(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
                  duration_staircase=True)
        m._stage_plan = ["distractor"] * 2
        m.total_trials = 2
        t = _to_trial(m)
        t = _to_respond(m, t)
        before = {h: s.level for h, s in m._dur_stair.items()}
        m.queue_press(_press_event(m.lane, t + 0.3))
        m._tick(t + 0.31)
        self.assertEqual({h: s.level for h, s in m._dur_stair.items()},
                         before)
        self.assertEqual(len(m._dis_records), 1)

    def test_block_carries_the_duration_and_seeds_the_next(self):
        m = self._legacy(n=1, catch_rate=0.0)
        m.engine.finish_block = lambda: None
        t = _to_trial(m)
        t = _to_respond(m, t)
        t = _answer_loc(m, t, correct=True, rt=0.2)
        m._tick(t + m.rest_s + 0.05)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.engine._buzz_hunt_start_ms["right"],
                         m._dur_stair["right"].level)
        e = _engine()
        e._buzz_hunt_start_ms = {"right": 180.0}
        self.assertEqual(self._legacy(e)._dur_stair["right"].level, 180.0)


# ---- the screen ---------------------------------------------------------


class ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 200))

    def _screen_and_mode(self):
        import pygame
        from finger_rehab.ui.buzz_hunt_screen import BuzzHuntScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        e = _engine()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.paused = False
        m = _mode(e, catch_rate=0.0)
        m = _only_stage(m, "loc", 4)
        e.mode = m
        sc = BuzzHuntScreen(e)
        sc._countdown_until = 0.0
        surf = pygame.Surface((1280, 800))
        return sc, m, surf

    def test_trial_frames_never_name_a_finger(self):
        import finger_rehab.ui.buzz_hunt_screen as bs
        sc, m, surf = self._screen_and_mode()
        t = _to_trial(m)
        _to_respond(m, t)
        seen = []
        original = bs.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        bs.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            bs.draw_text = original
        joined = " | ".join(seen).upper()
        for word in ("INDEX", "MIDDLE", "RING", "LITTLE",
                     "LEFT", "RIGHT"):
            self.assertNotIn(word, joined)

    def test_steady_trial_frames_allocate_no_surfaces(self):
        sc, m, surf = self._screen_and_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        sc.draw(surf)                        # warm the halo scratch
        calls = []
        original = sc._new_surface
        sc._new_surface = lambda *a, **k: (calls.append(a)
                                           or original(*a, **k))
        for _ in range(30):
            t += 1.0 / 60.0
            m._tick(t)
            sc.draw(surf)
        self.assertEqual(calls, [])

    def test_feedback_names_the_buzzed_and_pressed_fingers(self):
        import finger_rehab.ui.buzz_hunt_screen as bs
        sc, m, surf = self._screen_and_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.3))
        m._tick(t + 0.31)
        self.assertEqual(m.phase, "feedback")
        seen = []
        original = bs.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        bs.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            bs.draw_text = original
        joined = " | ".join(seen)
        self.assertIn("FOUND IT", joined)
        self.assertIn("The buzz was on", joined)

    def test_a_blocked_gate_says_so_on_screen(self):
        # A quiet gate that keeps resetting used to show nothing at
        # all: no banner, no skip chip (the foreperiod is deliberately
        # unarmed) and a frozen score, so a therapist could not tell a
        # running block from a dead one.
        import finger_rehab.ui.buzz_hunt_screen as bs
        sc, m, surf = self._screen_and_mode()
        dets = _attach_detectors(m.engine)
        t = _to_trial(m)
        dets["right"].pressed[1] = True
        for _ in range(5):
            t += 1.0 / 60.0
            m._tick(t)
        self.assertEqual(m.sub, "wait")
        seen = []
        original = bs.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        bs.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            bs.draw_text = original
        joined = " | ".join(seen)
        self.assertIn("Rest your fingers on the pads", joined)
        for word in ("INDEX", "MIDDLE", "RING", "LITTLE", "LEFT",
                     "RIGHT"):
            self.assertNotIn(word, joined.upper().replace(
                "BUZZ HUNT", ""))

    def test_the_forced_start_count_reaches_the_screen(self):
        import finger_rehab.ui.buzz_hunt_screen as bs
        sc, m, surf = self._screen_and_mode()
        _attach_detectors(m.engine)
        _to_trial(m)
        m.forced_starts = 3
        seen = []
        original = bs.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        bs.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            bs.draw_text = original
        self.assertIn("Forced starts: 3", " | ".join(seen))

    def test_a_clean_trial_frame_says_nothing_extra(self):
        # Nothing on the gate line may hint that a buzz is coming: the
        # foreperiod is part of the stimulus and a "get ready" here
        # would hand over the onset the jitter exists to hide.
        import finger_rehab.ui.buzz_hunt_screen as bs
        sc, m, surf = self._screen_and_mode()
        _attach_detectors(m.engine)
        t = _to_trial(m)
        _to_respond(m, t)
        seen = []
        original = bs.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        bs.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            bs.draw_text = original
        joined = " | ".join(seen)
        self.assertNotIn("Rest your fingers", joined)
        self.assertNotIn("Forced starts", joined)

    def test_breathing_stays_far_below_the_flash_limit(self):
        from finger_rehab.ui.buzz_hunt_screen import BuzzHuntScreen
        self.assertLess(BuzzHuntScreen.BREATHE_HZ, 1.0)

    def test_mode_select_and_setup_know_the_mode(self):
        from finger_rehab.ui.screens import ModeSelectScreen
        keys = [k for k, _t, _d in ModeSelectScreen.MODES]
        self.assertIn("buzz_hunt", keys)
        self.assertIn("buzz_hunt", ModeSelectScreen.MODE_ACCENTS)


# ---- results screen ------------------------------------------------------


class ResultsCardTests(unittest.TestCase):
    """Audit finding #94: THRESHOLD and GAP used to average both
    hands into one number and fall back to a still-descending
    staircase level when a block had fewer than 2 reversals, so a
    clean flawless block could show the 40 ms hardware floor labelled
    as a measured threshold, and a bilateral block's two very
    different hand levels blended into a number representing
    neither."""

    def _draw(self, bh_summary, hand_mode="right"):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.ui.screens import ResultsScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.hits, e.misses, e.score = 8, 0, 800
        e.current_block, e.hand_mode = "buzz_hunt", hand_mode
        e.best_streak, e.per_lane_stats = 0, {}
        e.hit_streak = 0
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"buzz_hunt": bh_summary}})()
        e.stop_all_motors = lambda *a, **k: None
        e.overall_mean_rt = lambda: 0.0
        e.overall_best_rt = lambda: 0.0
        r = ResultsScreen(e)
        r._shown_t = 1.0
        # These assertions are about the FULL read-out (every card
        # this mode produces, plus its per-finger charts), which is
        # what the More detail view draws. The finished screen shows
        # the three ResultsScreen.SLIM_CARDS picks out of the same
        # list; test_session_flow covers that view.
        r.show_details = True
        cards = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: cards.append((lbl, val)))
        r._draw_per_lane_chart = lambda *a, **k: None
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        return cards

    def test_a_still_descending_staircase_reads_not_reached(self):
        bh = {
            "hands": ["right"],
            "loc": {"accuracy": 1.0, "catch": {"false_alarms": 0}},
            "threshold": {"right": {"start_ms": 300.0, "final_ms": 100.0,
                                    "estimate_ms": None, "n_reversals": 0,
                                    "reversals_ms": []}},
            "span": {"max_correct": 4},
            "gap": {"threshold": {}},
        }
        cards = dict(self._draw(bh))
        self.assertEqual(cards.get("THRESHOLD"), "not reached")
        self.assertNotIn("100 ms", cards.values())

    def test_bilateral_hands_get_their_own_cards_not_an_average(self):
        bh = {
            "hands": ["right", "left"],
            "loc": {"accuracy": 1.0, "catch": {"false_alarms": 0}},
            "threshold": {
                "right": {"start_ms": 300.0, "final_ms": 300.0,
                          "estimate_ms": 300.0, "n_reversals": 6,
                          "reversals_ms": [300.0] * 6},
                "left": {"start_ms": 120.0, "final_ms": 120.0,
                         "estimate_ms": 120.0, "n_reversals": 6,
                         "reversals_ms": [120.0] * 6},
            },
            "span": {"max_correct": 4},
            "gap": {"threshold": {}},
        }
        cards = dict(self._draw(bh, hand_mode="both"))
        self.assertEqual(cards.get("THRESHOLD R"), "300 ms")
        self.assertEqual(cards.get("THRESHOLD L"), "120 ms")
        self.assertNotIn("THRESHOLD", cards)
        self.assertNotIn("210 ms", cards.values())

    def test_a_window_ladder_block_gets_window_cards_not_thresholds(self):
        # 2026-09: the difficulty summary is the shortest window each
        # hand reached; the THRESHOLD card only exists for a block
        # that ran the legacy staircase.
        bh = {
            "hands": ["right", "left"],
            "loc": {"accuracy": 0.95, "catch": {"false_alarms": 1}},
            "pulse_ms": 150.0,
            "duration_staircase": False,
            "threshold": {},
            "window": {
                "levels_s": [3.0, 2.0, 1.5, 1.2], "active": True,
                "top_level": 3,
                "per_hand": {
                    "right": {"top_level": 3, "top_window_s": 1.2,
                              "final_level": 2, "final_window_s": 1.5},
                    "left": {"top_level": 1, "top_window_s": 2.0,
                             "final_level": 1, "final_window_s": 2.0},
                },
            },
            "span": {"max_correct": 4},
            "gap": {"threshold": {}},
        }
        cards = dict(self._draw(bh, hand_mode="both"))
        self.assertEqual(cards.get("WINDOW R"), "1.2 s (L4/4)")
        self.assertEqual(cards.get("WINDOW L"), "2.0 s (L2/4)")
        self.assertFalse(any(k.startswith("THRESHOLD") for k in cards))


if __name__ == "__main__":
    unittest.main()
