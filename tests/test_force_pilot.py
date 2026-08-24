"""Force Pilot: the visuomotor force tracking mode.

What is pinned here, in dependency order:

  - the trajectory generator: deterministic from its seed, continuous
    across section boundaries, inside the 0 to span band, and exactly
    rebuildable from the packed waveform_params cell alone (the
    offline-reconstruction contract)
  - the probe gate: no session max means max-press probes run first
    and land in engine.record_max_press; a fresh max skips them
  - run scoring against synthetic force traces: perfect tracking
    scores full corridor time, an offset trace scores a stall and the
    exit buzz respects cue.buzz_after, release error is scored apart
    from press error
  - the trial row: waveform corridor, seed, params and segment bounds
    that parse back to the sections that ran
  - the hand matrix: one hand flies its four fingers, both hands fly
    all eight with runs alternating hands, and the weakest finger
    draws extra runs without starving anyone
  - the screen: corridor geometry is cached per run and steady-state
    frames create no new surfaces
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DRAW_KW = dict(
    seed=42, level=1, freq_ceiling_hz=0.3, corridor_hw_pct=8.0,
    gain=1.0, span_pct=40.0, base_pct=8.0, plateau_pct=28.0,
    ramp_rates_pct_s=[5.0, 10.0], sine_amp_pct=9.0, sine_s=6.0,
    sos_amps_pct=[6.0, 3.5, 2.5], sos_s=8.0, hold_in_s=3.0,
    hold_top_s=3.0, pre_assess_s=1.0, max_press_counts=400.0)


def _params(**over):
    from finger_rehab.game.modes.force_pilot import draw_run_params
    kw = dict(DRAW_KW)
    kw.update(over)
    return draw_run_params(**kw)


def _engine(hand_mode="right", cfg_extra=None):
    """Engine fixture in the house style: built via __new__, MagicMock
    config, command-recording source, loggable."""
    from finger_rehab.game.engine import GameEngine
    values = {
        "fsr.num_sensors_per_hand": 4,
        "motor.cue_ms": 150,
        "motor.pulse_interval_ms": 120,
        "cue.buzz_before": False,
        "cue.buzz_after": True,
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
    e.current_block = "force_pilot"
    e.session_paths = None
    e.session = MagicMock()
    # The probe gate is an identity gate too: the fixtures share one
    # participant name so a fresh max is reusable, and the mismatch
    # test can stamp a different name to force probes.
    e.session.participant = "T"
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


class _ViewStub:
    """Scripted stand-in for ForceView: the test sets counts and pct
    and the mode reads them like live sensor data."""

    def __init__(self):
        from finger_rehab.game.force_stream import ForceReading
        self._reading_cls = ForceReading
        self.counts = 0.0
        self.pct: float | None = None
        self.gone = False           # simulate a source dropout
        self.rebaselined: list = []

    def read(self, lane):
        if self.gone:
            return None
        return self._reading_cls(counts=self.counts, percent=self.pct)

    def sample_age_s(self, lane, now):
        return None if self.gone else 0.0

    def rebaseline(self, lanes=None):
        self.rebaselined.append(lanes)


def _mode(e, hands=None, **over):
    from finger_rehab.game.modes.force_pilot import ForcePilotMode
    from finger_rehab.game.scoring import ScoreConfig
    kw = dict(
        engine=e,
        lanes_by_hand=hands or {"right": [0, 1, 2, 3]},
        level=1,
        corridor_hw_by_level=[8.0, 6.0, 4.0],
        freq_ceiling_by_level=[0.3, 0.45, 0.6],
        runs_per_finger=2,
        min_finger_share=0.15,
        span_pct=40.0,
        base_pct=8.0,
        plateau_pct=28.0,
        ramp_rates_pct_s=[10.0],
        sine_amp_pct=9.0,
        sine_s=6.0,
        sos_amps_pct=[6.0, 3.5, 2.5],
        sos_s=8.0,
        hold_in_s=3.0,
        hold_top_s=3.0,
        pre_assess_s=1.0,
        visual_gain=1.0,
        ring_interval_s=1.5,
        ring_points=2,
        exit_buzz_ms=80.0,
        exit_buzz_cooldown_s=1.0,
        promote_frac=0.8,
        demote_frac=0.4,
        probe_presses=3,
        probe_floor_counts=30.0,
        probe_max_age_s=6 * 3600.0,
        announce_s=0.5,
        rest_s=1.0,
        score_cfg=ScoreConfig(),
        seed=7,
        demo_trials=None,
    )
    kw.update(over)
    m = ForcePilotMode(**kw)
    m.view = _ViewStub()
    return m


def _fresh_profile(hand="right"):
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    prof = CalibrationProfile(hand=hand, participant="T",
                              resting=[100.0] * 4,
                              press=[160.0] * 4)
    prof.set_max_press([400.0] * 4)
    return prof


def _to_run_phase(m, t0=1000.0):
    """Drive a probe-free mode from init into the run phase and return
    the run start time."""
    m._tick(t0)
    assert m.phase == "announce", m.phase
    t = t0 + m.announce_s + 0.01
    m._tick(t)
    assert m.phase == "run", m.phase
    return t


def _play_run(m, t_start, force_fn, dt=1.0 / 60.0):
    """Feed one full run with force from force_fn(t_run, target)."""
    from finger_rehab.game.modes.force_pilot import target_pct
    t = t_start
    while m.phase == "run":
        t += dt
        t_run = t - (m.run_t0 or t_start)
        target = target_pct(m.sections, t_run)
        m.view.pct = force_fn(t_run, target)
        m._tick(t)
    return t


# ---- trajectory generation ---------------------------------------------


class TrajectoryTests(unittest.TestCase):
    def test_same_seed_same_plan(self):
        self.assertEqual(_params(), _params())

    def test_different_seed_different_plan(self):
        a, b = _params(seed=1), _params(seed=2)
        self.assertNotEqual(a["sine_freq_hz"], b["sine_freq_hz"])

    def test_sections_are_continuous(self):
        # A step between sections would be an uncontrolled stimulus:
        # the corridor is designed with no jumps, and the approach
        # ramp exists exactly to walk into the assessment's start.
        from finger_rehab.game.modes.force_pilot import (
            sections_from_params, target_pct)
        secs = sections_from_params(_params())
        for k in range(1, len(secs)):
            before = target_pct(secs, secs[k].start_s - 1e-7)
            after = target_pct(secs, secs[k].start_s + 1e-7)
            self.assertAlmostEqual(before, after, places=3,
                                   msg=secs[k].name)

    def test_duration_inside_the_brief_window(self):
        # 20 to 30 s runs, both configured ramp rates.
        from finger_rehab.game.modes.force_pilot import (
            run_duration_s, sections_from_params)
        for seed in range(12):
            secs = sections_from_params(_params(seed=seed))
            dur = run_duration_s(secs)
            self.assertGreaterEqual(dur, 20.0)
            self.assertLessEqual(dur, 30.0)

    def test_target_stays_inside_the_span(self):
        from finger_rehab.game.modes.force_pilot import (
            run_duration_s, sections_from_params, target_pct)
        for seed in range(8):
            secs = sections_from_params(_params(seed=seed))
            dur = run_duration_s(secs)
            for i in range(500):
                v = target_pct(secs, dur * i / 499.0)
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 40.0)

    def test_frequencies_respect_the_level_band(self):
        from finger_rehab.game.modes.force_pilot import (
            SINE_FREQ_FLOOR_HZ, SOS_FREQ_FLOOR_HZ)
        for seed in range(20):
            p = _params(seed=seed, freq_ceiling_hz=0.45)
            self.assertGreaterEqual(p["sine_freq_hz"], SINE_FREQ_FLOOR_HZ)
            self.assertLessEqual(p["sine_freq_hz"], 0.45)
            freqs = [p["sos_f1_hz"], p["sos_f2_hz"], p["sos_f3_hz"]]
            self.assertEqual(freqs, sorted(freqs))
            for f in freqs:
                self.assertGreaterEqual(f, SOS_FREQ_FLOOR_HZ)
                self.assertLessEqual(f, 0.45)

    def test_rebuild_from_the_packed_cell(self):
        # The offline contract: the notebook parses waveform_params
        # and rebuilds the target without this module's rng. The
        # packed cell trims floats to 6 significant digits, so the
        # rebuild is exact to well under a hundredth of a percent.
        from finger_rehab.data.logger import (pack_waveform_params,
                                       parse_waveform_params)
        from finger_rehab.game.modes.force_pilot import (
            run_duration_s, sections_from_params, target_pct)
        p = _params()
        secs = sections_from_params(p)
        back = sections_from_params(
            parse_waveform_params(pack_waveform_params(p)))
        dur = run_duration_s(secs)
        worst = max(abs(target_pct(secs, dur * i / 399.0)
                        - target_pct(back, dur * i / 399.0))
                    for i in range(400))
        self.assertLess(worst, 1e-3)


# ---- the probe gate ----------------------------------------------------


class ProbeGateTests(unittest.TestCase):
    def _press(self, m, t, peak=400.0):
        """Feed one synthetic maximal press through the mode's tick."""
        for frac, dt in ((0.4, 0.05), (1.0, 0.05)):
            m.view.counts = peak * frac
            t += dt
            m._tick(t)
        for _ in range(8):                    # hold 0.4 s
            t += 0.05
            m._tick(t)
        m.view.counts = 0.0
        for _ in range(12):                   # release + rest 0.6 s
            t += 0.05
            m._tick(t)
        return t

    def test_missing_max_runs_probes_first(self):
        e = _engine()
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "probe_gap")
        self.assertEqual(len(m._probe_queue), 4)

    def test_probes_record_and_hand_over_to_runs(self):
        e = _engine()
        recorded = {}
        e.record_max_press = lambda hand, maxes: recorded.update(
            {hand: list(maxes)})
        m = _mode(e)
        t = 0.0
        m._tick(t)
        for _ in range(4):
            t += 1.3                          # through the probe gap
            m._tick(t)
            self.assertEqual(m.phase, "probe")
            for peak in (390.0, 400.0, 410.0):
                t = self._press(m, t, peak)
        self.assertEqual(recorded["right"], [400.0] * 4)
        # The trailing rest ticks may already have crossed the short
        # test announce window; either way the probes are over and the
        # run flow owns the block.
        self.assertIn(m.phase, ("announce", "run"))

    def test_fresh_max_skips_probes(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "announce")

    def test_keyboard_source_is_refused_plainly(self):
        # No keyboard fallback by design: the mode parks on a message
        # instead of pretending a keyboard can make force.
        e = _engine()
        e.source.provides_samples = False
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "no_input")


# ---- run scoring against synthetic traces ------------------------------


class RunScoringTests(unittest.TestCase):
    def _ready_mode(self, e=None, **over):
        e = e or _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        return _mode(e, **over)

    def test_perfect_tracking_scores_full_corridor_time(self):
        m = self._ready_mode()
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        rec = m._records[0]
        self.assertGreaterEqual(rec.tic_frac, 0.999)
        self.assertLess(rec.mae_pct, 1e-6)
        self.assertEqual(rec.stalls, 0)
        self.assertEqual(rec.rings_collected, rec.rings_total)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Great")

    def test_offset_trace_stalls_once_and_buzzes(self):
        m = self._ready_mode()
        t = _to_run_phase(m)
        lane = m.lane
        _play_run(m, t, lambda t_run, target: target + 20.0)
        rec = m._records[0]
        self.assertEqual(rec.tic_frac, 0.0)
        self.assertEqual(rec.stalls, 1)
        self.assertEqual(rec.rings_collected, 0)
        self.assertIn(f"STIM:{lane + 1}", m.engine._sent)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")

    def test_exit_buzz_respects_the_cue_switch(self):
        e = _engine(cfg_extra={"cue.buzz_after": False})
        m = self._ready_mode(e)
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target + 20.0)
        self.assertEqual(m._records[0].stalls, 1)
        self.assertFalse([c for c in m.engine._sent
                          if str(c).startswith("STIM")])

    def test_release_error_is_scored_apart_from_press(self):
        # The Davidson 2026 marker: error during the ramp-down must be
        # separable from error during the ramp-up.
        m = self._ready_mode()
        t = _to_run_phase(m)
        release = next(s for s in m.sections if s.name == "release")

        def force(t_run, target):
            if release.start_s <= t_run < release.end_s:
                return target + 5.0
            return target

        _play_run(m, t, force)
        rec = m._records[0]
        self.assertLess(rec.press_mae_pct, 0.5)
        self.assertAlmostEqual(rec.release_mae_pct, 5.0, delta=0.5)

    def test_dropout_pauses_scoring_instead_of_judging_it(self):
        m = self._ready_mode()
        t = _to_run_phase(m)
        seen = {"scored_before": None}

        def force(t_run, target):
            # The source vanishes for the middle third of the run.
            third = m.duration_s / 3.0
            m.view.gone = third <= t_run < 2 * third
            return target

        _play_run(m, t, force)
        rec = m._records[0]
        del seen
        # The dropped third contributes no scored time, and what was
        # scored is still perfect.
        self.assertLess(rec.scored_s, m.duration_s * 0.75)
        self.assertGreaterEqual(rec.tic_frac, 0.999)
        self.assertEqual(rec.stalls, 0)

    def test_trial_row_carries_the_reconstruction_contract(self):
        from finger_rehab.data.logger import (parse_segments,
                                       parse_waveform_params)
        m = self._ready_mode()
        t = _to_run_phase(m)
        run_t0 = m.run_t0
        sections = list(m.sections)
        seed = m.run_seed
        _play_run(m, t, lambda t_run, target: target)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "corridor")
        self.assertEqual(row["waveform_seed"], str(seed))
        params = parse_waveform_params(row["waveform_params"])
        self.assertEqual(params["max_press_counts"], 400.0)
        self.assertEqual(params["hw_pct"], 8.0)
        self.assertEqual(params["gain"], 1.0)
        segs = parse_segments(row["segment_times"])
        self.assertEqual([s[0] for s in segs],
                         [s.name for s in sections])
        for (name, start, end), sec in zip(segs, sections):
            self.assertAlmostEqual(start - run_t0, sec.start_s, places=4)
            self.assertAlmostEqual(end - run_t0, sec.end_s, places=4)

    def test_segment_markers_bracket_the_run_in_raw(self):
        m = self._ready_mode()
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        events = [ev for ev in m.engine.raw_logger.events
                  if ev["event"] in ("segment_start", "segment_end")]
        names = [s.name for s in m.sections]
        # The plan for the NEXT run replaced m.sections at close; the
        # logged names still describe the run that played.
        starts = [ev for ev in events if ev["event"] == "segment_start"]
        ends = [ev for ev in events if ev["event"] == "segment_end"]
        self.assertEqual(len(starts), len(names))
        self.assertEqual(len(ends), len(names))

    def test_rt_censoring_column_stays_empty(self):
        # A run has no reaction-time window, so timeout_ms must not
        # inherit a stale value from a previous cadence block.
        m = self._ready_mode()
        m.engine._last_stim_timeout_ms = 750.0
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        self.assertEqual(m.engine.trial_logger.rows[0]["timeout_ms"], "")

    def test_demo_cap_trims_runs_and_length(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, demo_trials=2)
        self.assertEqual(m.total_runs, 2)
        t = _to_run_phase(m)
        self.assertLess(m.duration_s, 20.0)


# ---- difficulty --------------------------------------------------------


class LevelTests(unittest.TestCase):
    def _m(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        return _mode(e)

    def test_two_strong_runs_promote_and_announce(self):
        m = self._m()
        m._move_level(0.9)
        self.assertEqual(m.level, 1)
        m._move_level(0.85)
        self.assertEqual(m.level, 2)
        self.assertIn("narrows", m.level_msg)
        self.assertIn("level 2", m.level_msg)
        evs = [ev for ev in m.engine.raw_logger.events
               if ev["event"] == "force_pilot_level"]
        self.assertEqual(len(evs), 1)

    def test_one_weak_run_demotes(self):
        m = self._m()
        m.level = 2
        m._move_level(0.2)
        self.assertEqual(m.level, 1)
        self.assertIn("widens", m.level_msg)

    def test_level_is_capped_both_ways(self):
        m = self._m()
        m.level = 3
        for _ in range(4):
            m._move_level(0.95)
        self.assertEqual(m.level, 3)
        m.level = 1
        m._move_level(0.0)
        self.assertEqual(m.level, 1)

    def test_next_run_uses_the_new_corridor(self):
        m = self._m()
        t = _to_run_phase(m)
        hand, finger = m.hand, m.finger
        m._recent_tic_by_hf[(hand, finger)] = [0.9]
        _play_run(m, t, lambda t_run, target: target)   # promotes
        # The finger that just ran is the one that moved, regardless
        # of which finger the scheduler hands out next.
        self.assertEqual(m._level_by_hf[(hand, finger)], 2)
        # Force the same finger back so its own promoted corridor is
        # visible on its very next run (a different finger's next run
        # must still be whatever ITS OWN level says, which the
        # per-finger-level tests below cover).
        m._finger_sched[hand].next = lambda weights=None: finger
        m._prepare_run()
        self.assertEqual(m.hand, hand)
        self.assertEqual(m.finger, finger)
        self.assertEqual(m.level, 2)
        self.assertEqual(m.corridor_hw, 6.0)
        self.assertEqual(m.params["lvl"], 2)

    def test_one_fingers_promotion_does_not_move_another(self):
        # The headline finding this fixes: level was one shared value
        # per hand (and across hands in bilateral play), so the
        # strongest finger's runs forced the same corridor onto the
        # weakest finger's runs. Two strong runs on finger 0 must not
        # touch finger 1's level, which a finger that has never played
        # should still hold at the configured start.
        m = self._m()
        m._move_level(0.9)     # finger (right, 0), first strong run
        m._move_level(0.85)    # second strong run: promotes to 2
        self.assertEqual(m._level_by_hf[("right", 0)], 2)
        self.assertEqual(m._level_by_hf[("right", 1)], 1)
        self.assertEqual(m._level_by_hf[("right", 2)], 1)
        self.assertEqual(m._level_by_hf[("right", 3)], 1)

    def test_bilateral_hands_keep_independent_levels(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        m.hand, m.finger = "right", 0
        m._move_level(0.9)
        m._move_level(0.85)    # promotes the right index finger to 2
        self.assertEqual(m._level_by_hf[("right", 0)], 2)
        self.assertEqual(m._level_by_hf[("left", 0)], 1)


# ---- hands and scheduling ----------------------------------------------


class HandMatrixTests(unittest.TestCase):
    def test_left_hand_flies_left(self):
        e = _engine(hand_mode="left")
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"left": [0, 1, 2, 3]})
        m._tick(0.0)
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.hand, "left")
        self.assertEqual(m.total_runs, 8)

    def test_both_hands_means_all_eight_fingers(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"right": [0, 1, 2, 3],
                            "left": [4, 5, 6, 7]})
        self.assertEqual(m.total_runs, 16)
        lanes = set()
        hand_counts = {"right": 0, "left": 0}
        for _ in range(16):
            m._prepare_run()
            lanes.add(m.lane)
            hand_counts[m.hand] += 1
        self.assertEqual(lanes, set(range(8)))
        # Balanced hand bag: equal run counts across the block.
        self.assertEqual(hand_counts["right"], 8)
        self.assertEqual(hand_counts["left"], 8)

    def test_weakest_finger_draws_extra_runs_with_a_floor(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m._mae_by_hf = {("right", 0): [10.0], ("right", 1): [1.0],
                        ("right", 2): [1.0], ("right", 3): [1.0]}
        counts = [0, 0, 0, 0]
        for _ in range(200):
            m._prepare_run()
            counts[m.finger] += 1
        self.assertEqual(max(counts), counts[0])
        # The floor keeps every finger analysable.
        for c in counts:
            self.assertGreaterEqual(c / 200.0, 0.10)

    def test_unmeasured_finger_is_not_starved(self):
        # A finger with no runs yet weighs in at the current worst, so
        # early weighting cannot lock it out.
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m._mae_by_hf = {("right", 1): [4.0]}
        counts = [0, 0, 0, 0]
        for _ in range(80):
            m._prepare_run()
            counts[m.finger] += 1
        for c in counts:
            self.assertGreater(c, 0)


# ---- pause and block stats ---------------------------------------------


class PauseAndStatsTests(unittest.TestCase):
    def _ready(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        return _mode(e)

    def test_pause_mid_run_restarts_the_run(self):
        m = self._ready()
        t = _to_run_phase(m)
        m.view.pct = m.base_pct
        m._tick(t + 2.0)
        self.assertEqual(m.phase, "run")
        trial_before = m.trial_counter
        seed_before = m.run_seed
        m.on_resume(5.0)
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.trial_counter, trial_before)
        self.assertEqual(m.run_seed, seed_before)
        self.assertEqual(m.engine.trial_logger.rows, [])
        restarts = [ev for ev in m.engine.raw_logger.events
                    if ev["event"] == "run_restart"]
        self.assertEqual(len(restarts), 1)

    def test_block_stats_carry_the_results_summary(self):
        m = self._ready()
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        m.total_runs = 1
        t = _to_run_phase(m)
        lane = m.lane
        _play_run(m, t, lambda t_run, target: target)
        self.assertEqual(m.phase, "done")
        self.assertTrue(finished)
        stats = m.block_stats()
        self.assertEqual(stats["runs"], 1)
        self.assertGreaterEqual(
            stats["overall"]["time_in_corridor"], 0.999)
        self.assertIn(str(lane), stats["per_lane"])
        self.assertIn(stats["best_section"],
                      ("low hold", "press ramp", "high hold",
                       "release ramp", "waves", "approach",
                       "assessment"))
        # The session-carrying level hook for the next block: now a
        # dict keyed by (hand, finger), not one shared value.
        self.assertEqual(m.engine._force_pilot_levels[(m.hand, m.finger)],
                         m.level)

    def test_demo_block_writes_no_level_carry(self):
        # A supervisor's Test Mode demo must not seed the next real
        # patient's difficulty.
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, demo_trials=1)
        m.engine.finish_block = lambda: None
        m._end("completed")
        self.assertFalse(hasattr(m.engine, "_force_pilot_levels"))

    def test_block_stats_splits_per_lane_and_section_by_level(self):
        # A run at the easiest level and a run at the hardest level
        # earn differently-scaled outcomes for the same real tracking
        # quality, so per_lane and section_mae must not silently pool
        # across a level change mid-block.
        m = self._ready()
        m.engine.finish_block = lambda: None
        m.total_runs = 2
        t = _to_run_phase(m)
        lane, hand, finger = m.lane, m.hand, m.finger
        # Force the same finger back every time so the second run
        # plays at whatever level its own promotion left it at.
        m._finger_sched[hand].next = lambda weights=None: finger
        # Force a promotion after the first run so the second run at
        # this same finger plays at a different level.
        m._recent_tic_by_hf[(hand, finger)] = [0.9]
        _play_run(m, t, lambda t_run, target: target)
        self.assertEqual(m._level_by_hf[(hand, finger)], 2)
        self.assertEqual(m.phase, "feedback")
        t = m._phase_until + 0.01
        m._tick(t)                                 # feedback -> announce
        self.assertEqual(m.phase, "announce")
        t = m._phase_until + 0.01
        m._tick(t)                                 # announce -> run
        self.assertEqual(m.phase, "run")
        self.assertEqual(m.level, 2)
        _play_run(m, t, lambda t_run, target: target)
        stats = m.block_stats()
        by_level = stats["per_lane"][str(lane)]["by_level"]
        self.assertEqual(set(by_level), {"1", "2"})
        self.assertEqual(by_level["1"]["runs"], 1)
        self.assertEqual(by_level["2"]["runs"], 1)
        sec_by_level = stats["section_mae_pct_by_level"]
        self.assertEqual(set(sec_by_level), {"1", "2"})
        self.assertEqual(stats["levels"][f"{hand}:{finger}"]["start"], 1)
        self.assertEqual(stats["levels"][f"{hand}:{finger}"]["final"], 2)
        self.assertEqual(stats["levels"][f"{hand}:{finger}"]["trace"],
                         [1, 2])


# ---- the screen --------------------------------------------------------


class ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 200))

    def _screen_and_mode(self):
        """A real screen over a stub engine carrying a scripted mode
        in the run phase."""
        import pygame
        from finger_rehab.ui.force_pilot_screen import ForcePilotScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.paused = False
        m = _mode(e)
        e.mode = m
        sc = ForcePilotScreen(e)
        sc._countdown_until = 0.0
        t = _to_run_phase(m)
        m.view.pct = m.base_pct
        m._tick(t + 0.5)
        surf = pygame.Surface((1280, 800))
        return sc, m, surf, t

    def test_corridor_geometry_is_cached_per_run(self):
        sc, m, surf, _t = self._screen_and_mode()
        sc.draw(surf)
        first = sc._corridor_surf
        self.assertIsNotNone(first)
        sc.draw(surf)
        self.assertIs(sc._corridor_surf, first)

    def test_steady_frames_allocate_no_new_surfaces(self):
        sc, m, surf, t = self._screen_and_mode()
        sc.draw(surf)                        # warm the caches
        calls = []
        original = sc._new_surface
        sc._new_surface = lambda *a, **k: (calls.append(a)
                                           or original(*a, **k))
        for k in range(30):
            m.view.pct = m.base_pct + (k % 5)
            m._tick(t + 0.5 + k / 60.0)
            sc.draw(surf)
        self.assertEqual(calls, [])

    def test_active_finger_is_named_on_screen(self):
        import finger_rehab.ui.force_pilot_screen as fps
        sc, m, surf, _t = self._screen_and_mode()
        seen = []
        original = fps.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        fps.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            fps.draw_text = original
        joined = " | ".join(seen)
        self.assertIn("Run 1 of", joined)
        self.assertIn("Corridor +/-", joined)
        # The finger chip and the mode pill render through their own
        # font path (not draw_text), so pin the chip's words directly.
        self.assertEqual(
            sc._hand_finger_words(m.hand, m.finger),
            f"{m.hand.upper()} "
            f"{['INDEX', 'MIDDLE', 'RING', 'LITTLE'][m.finger]}")


# ---- audit fixes: error_type and dropout ring gating ---------------------


class ErrorTypeTests(unittest.TestCase):
    """Audit finding #78: a Miss caused by low time-in-corridor is a
    completed run scored poorly, not a timeout (there is no stim
    deadline in a continuous tracking run, and timeout_ms stays empty
    on every row). The generic engine.log_trial derivation labels
    every no-incorrect-press Miss "timeout", which would pull clean
    low-tracking runs into cross-mode error_type=="timeout" filters
    that mean "no press before the deadline"."""

    def test_low_tracking_miss_is_not_logged_as_timeout(self):
        import csv
        import tempfile
        from pathlib import Path
        from finger_rehab.data.logger import TrialLogger
        from finger_rehab.game.modes.force_pilot import target_pct

        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            e.trial_logger = TrialLogger(folder / "trials.csv")
            m = _mode(e)
            m.total_runs = 2   # never let this run trigger _end()
            finger, hand = 0, "right"
            m._finger_sched[hand].next = lambda weights=None: finger

            t0 = 1000.0
            m._tick(t0)
            t = t0 + m.announce_s + 0.01
            m._tick(t)
            self.assertEqual(m.phase, "run")

            dt = 1.0 / 60.0
            t_run = t0
            while m.phase == "run":
                t_run += dt
                run_elapsed = t_run - (m.run_t0 or t0)
                target = target_pct(m.sections, run_elapsed)
                m.view.pct = max(0.0, target - 40.0)  # always far off
                m._tick(t_run)

            with open(folder / "trials.csv") as f:
                rows = list(csv.DictReader(f))
        row = rows[-1]
        self.assertEqual(row["early_late"], "Miss")
        self.assertEqual(row["timeout_ms"], "")
        self.assertNotEqual(row["error_type"], "timeout")

    def test_great_run_leaves_error_type_empty(self):
        import csv
        import tempfile
        from pathlib import Path
        from finger_rehab.data.logger import TrialLogger

        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            e.trial_logger = TrialLogger(folder / "trials.csv")
            m = _mode(e)
            m.total_runs = 2
            t = _to_run_phase(m)
            _play_run(m, t, lambda t_run, target: target)  # perfect
            with open(folder / "trials.csv") as f:
                rows = list(csv.DictReader(f))
        self.assertIn(rows[-1]["early_late"], ("Great", "Good"))
        self.assertEqual(rows[-1]["error_type"], "")


class ProbeGuardRailTests(unittest.TestCase):
    """The probe phase must neither hang forever on a finger that
    cannot reach the floor, nor silently accept a max so small the
    percent targets sit inside sensor noise."""

    def _probe_mode(self):
        e = _engine()
        # No stored max: probes must run.
        m = _mode(e)
        m._tick(1000.0)
        t = 1000.0 + m.probe_gap_s + 0.01 \
            if hasattr(m, "probe_gap_s") else 1000.5
        guard = t + 10.0
        while m.phase != "probe" and t < guard:
            t += 0.1
            m._tick(t)
        assert m.phase == "probe", m.phase
        return e, m, t

    def test_stalled_probe_ends_the_block_gently(self):
        e, m, t = self._probe_mode()
        e.finish_block = lambda: None
        # The finger never clears the floor: force sits at 5 counts.
        end = t + m.PROBE_STALL_S + 2.0
        while m.phase == "probe" and t < end:
            t += 0.25
            m.view.counts = 5.0
            m.view.pct = 1.0
            m._tick(t)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "probe_timeout")

    def test_low_max_is_flagged_not_silent(self):
        e, m, t = self._probe_mode()
        # Three just-over-floor presses: max lands ~35 counts, far
        # under LOW_MAX_FLOOR_MULT x floor (150).
        end = t + 60.0
        pressing = True
        flips = 0
        while m.phase == "probe" and t < end and flips < 40:
            t += 0.5
            m.view.counts = 35.0 if pressing else 0.0
            m.view.pct = 1.0
            pressing = not pressing
            flips += 1
            m._tick(t)
        events = [ev for ev in e.raw_logger.events
                  if ev["event"] == "max_press_low"]
        self.assertGreaterEqual(len(events), 1)
        self.assertIn("max_counts=35.0", events[0]["detail"])


class NoSignalRunTests(unittest.TestCase):
    """A run whose force signal covered under half the plan is
    hardware evidence, not tracking: scoring it used to log mae=0.00
    (a perfect-looking error), pull the per-finger MAE toward zero,
    show the patient ROUGH RIDE with 'Mean error 0.0% of max', and
    demote the staircase for a device fault."""

    def _starved_run(self, level=2):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, level=level)
        t = _to_run_phase(m)
        m.view.gone = True
        t = _play_run(m, t, lambda t_run, target: target)
        return e, m, t

    def test_starved_run_scores_nothing_and_replays(self):
        e, m, t = self._starved_run()
        row = e.trial_logger.rows[-1]
        self.assertEqual(row["error_type"], "no_signal")
        self.assertIn("no_signal=True", row["stimulus"])
        # No RunRecord: the per-finger and overall MAE stay clean.
        self.assertEqual(m._records, [])
        self.assertEqual(m.block_stats()["overall"]["mae_pct"], None)
        self.assertEqual(m.block_stats()["no_signal_runs"], 1)
        # No staircase move, and the slot replays.
        self.assertEqual(m.runs_done, 0)
        self.assertEqual(m._last_result["label"], "NoSignal")
        t += m.rest_s + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "announce")

    def test_dead_device_gives_the_slot_up_eventually(self):
        e, m, t = self._starved_run()
        for _ in range(m.MAX_NO_SIGNAL_RETRIES):
            t += m.rest_s + 0.05
            m._tick(t)
            t += m.announce_s + 0.05
            m._tick(t)
            self.assertEqual(m.phase, "run")
            t = _play_run(m, t, lambda t_run, target: target)
        # After the retries the slot is abandoned and play moves on.
        self.assertEqual(m.runs_done, 1)
        self.assertEqual(m._records, [])

    def test_partial_coverage_above_half_still_scores(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        t = _to_run_phase(m)
        dur = m.duration_s

        def force(t_run, target):
            m.view.gone = t_run > dur * 0.75    # last quarter lost
            return target

        _play_run(m, t, force)
        m.view.gone = False
        self.assertEqual(len(m._records), 1)
        self.assertEqual(m.runs_done, 1)


class DropoutRingGatingTests(unittest.TestCase):
    """Audit finding #81: rings due WHILE the signal is stale must be
    retired as unjudged (no points) as the gap happens, not judged all
    at once on the first frame after recovery using that one frame's
    in-corridor state."""

    def test_ring_due_during_dropout_is_not_collected_on_recovery(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m.total_runs = 5
        finger, hand = 0, "right"
        m._finger_sched[hand].next = lambda weights=None: finger
        t0 = 1000.0
        m._tick(t0)
        t = t0 + m.announce_s + 0.01
        m._tick(t)
        self.assertEqual(m.phase, "run")

        class _View:
            def __init__(self):
                self.pct = None
                self.live = True

            def read(self, lane):
                if not self.live:
                    return None
                from types import SimpleNamespace
                return SimpleNamespace(percent=self.pct)

            def sample_age_s(self, lane, now):
                return 0.0 if self.live else None

        m.view = _View()
        ring0 = m.ring_times[0]
        self.assertLess(ring0, 3.0)

        from finger_rehab.game.modes.force_pilot import target_pct
        dt = 1.0 / 60.0
        t_run = t0
        while m.phase == "run":
            t_run += dt
            run_elapsed = t_run - (m.run_t0 or t0)
            if run_elapsed > m.duration_s:
                break
            target = target_pct(m.sections, run_elapsed)
            if 0.3 < run_elapsed < 3.0:
                m.view.live = False       # dropout spans ring 0
            else:
                m.view.live = True
                m.view.pct = target       # perfect otherwise
            m._tick(t_run)

        self.assertFalse(m.ring_state[0])
        self.assertNotIn(True, [m.ring_state[0]])

    def test_ring_before_any_dropout_still_scores_normally(self):
        """A dropout fix must not gutter rings judged while the signal
        was live: only rings due DURING the stale window are affected."""
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m.total_runs = 5
        finger, hand = 0, "right"
        m._finger_sched[hand].next = lambda weights=None: finger
        t = _to_run_phase(m)
        m.view.pct = m.base_pct
        dt = 1.0 / 60.0
        t_run = t
        # Run to just past the first ring with perfect tracking and no
        # dropout at all.
        while m._ring_idx == 0 and m.phase == "run":
            t_run += dt
            m._tick(t_run)
        self.assertGreaterEqual(m._ring_idx, 1)
        self.assertTrue(m.ring_state[0])


# ---- audit fixes: Results screen level annotation, mode-select badge -----


class ResultsScreenLevelAnnotationTests(unittest.TestCase):
    """Audit finding #80: block_stats' own docstring says pooling a
    lane's stats across corridor levels misrepresents both, and it
    publishes a by_level split for exactly that reason, but the per-
    finger charts and the IN CORRIDOR / MEAN ERROR cards drew the
    pooled values with no level annotation, so fingers sitting at
    different levels were compared with nothing on screen to say so."""

    @staticmethod
    def _fp_summary():
        return {
            "runs": 4,
            "levels": {
                "right:0": {"start": 1, "final": 1, "trace": []},
                "right:1": {"start": 1, "final": 3, "trace": [1, 2, 3]},
            },
            "per_lane": {
                "0": {"runs": 2, "mae_pct": 4.0, "time_in_corridor": 0.9},
                "1": {"runs": 2, "mae_pct": 3.0, "time_in_corridor": 0.6},
            },
            "overall": {"mae_pct": 3.5, "time_in_corridor": 0.75,
                       "stalls": 0},
            "best_section": "sine",
        }

    def _draw(self, fp_summary):
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
        e.hits, e.misses, e.score = 4, 0, 400
        e.current_block, e.hand_mode = "force_pilot", "right"
        e.best_streak, e.per_lane_stats = 0, {}
        e.hit_streak = 0
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"force_pilot": fp_summary}})()
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
        chart_calls = []
        orig = r._draw_per_lane_chart

        def recorder(surf, rect, title, values, unit, high_is_bad,
                     *a, **kw):
            chart_calls.append({"title": title, "kw": kw})
            return orig(surf, rect, title, values, unit, high_is_bad,
                       *a, **kw)
        r._draw_per_lane_chart = recorder
        cards = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: cards.append((lbl, val)))
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        return chart_calls, cards

    def test_per_finger_charts_carry_the_finger_level(self):
        chart_calls, _cards = self._draw(self._fp_summary())
        fp_calls = [c for c in chart_calls if "FINGER" in c["title"]]
        self.assertTrue(fp_calls)
        for c in fp_calls:
            self.assertEqual(c["kw"].get("levels"), [1, 3, 0, 0])

    def test_pooled_cards_flag_mixed_levels(self):
        _chart_calls, cards = self._draw(self._fp_summary())
        values = dict(cards)
        self.assertIn("IN CORRIDOR (mixed levels)", values)
        self.assertIn("MEAN ERROR (mixed levels)", values)

    def test_same_level_fingers_get_no_mixed_note(self):
        fp = self._fp_summary()
        fp["levels"]["right:1"]["final"] = 1   # both fingers at level 1
        _chart_calls, cards = self._draw(fp)
        values = dict(cards)
        self.assertIn("IN CORRIDOR", values)
        self.assertNotIn("IN CORRIDOR (mixed levels)", values)


class ModeSelectHardwareBadgeTests(unittest.TestCase):
    """Audit finding #111: Force Pilot (with Lighthouse and Buzz Hunt)
    gave no needs-hardware indication until after a keyboard-only
    block had already run setup and the GET READY countdown, leaving
    behind an abandoned session folder. The mode-select card must say
    so before the click."""

    @staticmethod
    def _screen(provides_samples):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.ui.screens import ModeSelectScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        src = MagicMock()
        src.provides_samples = provides_samples
        e.source = src
        return ModeSelectScreen(e)

    def test_needs_hardware_set_names_all_three_hardware_only_modes(
            self):
        sc = self._screen(True)
        self.assertEqual(sc.NEEDS_HARDWARE,
                         {"force_pilot", "lighthouse", "buzz_hunt"})

    def test_badge_drawn_on_keyboard_only_source(self):
        sc = self._screen(False)
        import pygame
        surf = pygame.Surface((1280, 800))
        seen = []
        import finger_rehab.ui.screens as screens_mod
        original = screens_mod.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)
        screens_mod.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            screens_mod.draw_text = original
        pygame.quit()
        self.assertIn("NEEDS SENSOR HARDWARE", seen)

    def test_no_badge_when_a_real_source_is_connected(self):
        sc = self._screen(True)
        import pygame
        surf = pygame.Surface((1280, 800))
        seen = []
        import finger_rehab.ui.screens as screens_mod
        original = screens_mod.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)
        screens_mod.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            screens_mod.draw_text = original
        pygame.quit()
        self.assertNotIn("NEEDS SENSOR HARDWARE", seen)


if __name__ == "__main__":
    unittest.main()
