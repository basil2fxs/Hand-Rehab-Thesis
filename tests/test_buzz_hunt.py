"""Buzz Hunt: the vibrotactile perception suite.

What is pinned here, in dependency order:

  - the staircase: 2-down 1-up mechanics, floor and ceiling clamps,
    reversal recording, and convergence near a simulated observer's
    true threshold
  - pure stimulus reconstruction: pulses_from_params rebuilds every
    waveform (buzz, catch, distractor, sequence, gap) from the params
    dict alone, matched-envelope gap trials included, and the packed
    cell round-trips
  - the Hebb material: participant-name seeding is deterministic and
    case-folded, sequences avoid immediate repeats and stay inside
    the lane pool
  - localisation trials: the buzz goes out through pulse_motor
    (bypassing the cue switches by design), a correct press scores,
    a wrong finger logs a Miss with the confusion matrix updated,
    a timeout raises the staircase, and cue_target_shown is FALSE
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
    )
    kw.update(over)
    return BuzzHuntMode(**kw)


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

    def test_timeout_raises_the_staircase(self):
        m = self._loc_mode()
        t = _to_trial(m)
        t = _to_respond(m, t)
        before = m._dur_stair[m.hand].level
        t += m.response_window_s + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "feedback")
        self.assertEqual(m._dur_stair[m.hand].level, before + m.step_ms)
        self.assertEqual(m._confusion[str(m._loc_records[0]['lane'])]
                         ["none"], 1)

    def test_two_correct_lower_the_duration(self):
        m = self._loc_mode(n=3)
        t = _to_trial(m)
        start = m._dur_stair["right"].level
        for i in range(2):
            t = _to_respond(m, t)
            m.queue_press(_press_event(m.lane, t + 0.2))
            m._tick(t + 0.21)
            t = _next_trial(m, t + 0.21) if i < 1 else t + 0.21
        self.assertEqual(m._dur_stair["right"].level, start - m.step_ms)

    def test_reversal_is_logged_as_an_event(self):
        m = self._loc_mode(n=6)
        t = _to_trial(m)
        # Two correct (down), then a timeout (up): that turn is the
        # first reversal and must land in the raw log.
        for i in range(3):
            t = _to_respond(m, t)
            if i < 2:
                m.queue_press(_press_event(m.lane, t + 0.2))
                m._tick(t + 0.21)
                t = _next_trial(m, t + 0.21)
            else:
                t += m.response_window_s + 0.05
                m._tick(t)
        revs = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "buzz_hunt_reversal"]
        self.assertEqual(len(revs), 1)
        self.assertIn("stair=duration", revs[0]["detail"])

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
        before = m._dur_stair[m.hand].level
        # Even a press on the correct lane must not read as a hit:
        # nothing buzzed for it to correctly localise.
        m.queue_press(_press_event(m.lane, t + 0.1))
        m._tick(t + 0.11)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["stim_delivered"], "FALSE")
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(m._dur_stair[m.hand].level, before)
        self.assertEqual(m._loc_records, [])
        self.assertEqual(m.engine._block_stim_failures, 1)


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

    def test_distractor_trials_hold_the_staircase_still(self):
        e = _engine(hand_mode="both")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
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
        # Both pulses went out: the decoy and the target.
        stims = [c for c in m.engine._sent if str(c).startswith("STIM")]
        self.assertEqual(len(stims), 2)

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
        self.assertEqual(m._gap_stair[rec["hand"]].level,
                         before + m.gap_step_ms)
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
        finding #92, the gap-stage half)."""
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
        m.queue_press(_press_event(m.lane, t))
        m._tick(t + dt)
        self.assertEqual(m.sub, "wait")
        self.assertNotEqual(m.trial_seed, orig_seed)
        import random as _random
        expected_kind = (_random.Random(m.trial_seed).random() < 0.5)
        self.assertEqual(m.gap_two, expected_kind)
        self.assertEqual(int(m.params["two"]), 1 if expected_kind else 0)

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

    def test_block_ends_and_carries_the_staircase(self):
        m = _mode(_engine(), catch_rate=0.0)
        m = _only_stage(m, "loc", 1)
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        t = _to_trial(m)
        t = _to_respond(m, t)
        m.queue_press(_press_event(m.lane, t + 0.2))
        m._tick(t + 0.21)
        m._tick(t + 0.21 + m.rest_s + 0.05)
        self.assertEqual(m.phase, "done")
        self.assertTrue(finished)
        self.assertEqual(m.engine._buzz_hunt_start_ms["right"],
                         m._dur_stair["right"].level)

    def test_carried_start_seeds_the_next_block(self):
        e = _engine()
        e._buzz_hunt_start_ms = {"right": 180.0}
        m = _mode(e)
        self.assertEqual(m._dur_stair["right"].level, 180.0)

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
        self.assertIn("right", stats["threshold"])
        self.assertIn("reversals_ms", stats["threshold"]["right"])
        self.assertIsNotNone(stats["loc"]["median_rt_ms"])
        self.assertEqual(stats["span"]["trials"], 0)
        self.assertIn("confusion", stats)

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


if __name__ == "__main__":
    unittest.main()
