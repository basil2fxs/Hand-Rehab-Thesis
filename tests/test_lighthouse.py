"""Lighthouse: the precision hold mode with feedback fade and echo
trials.

What is pinned here, in dependency order:

  - fade scheduling: the dark-window planner is deterministic from
    its seed, honours the lit lead / gap / tail guarantees, tiles the
    hold exactly, matches feedback_lit, drops windows that cannot
    fit, and rebuilds bit-close from the packed waveform_params cell
  - the probe gate: no session max means max-press probes run first;
    a fresh max skips them; the keyboard source is refused plainly
  - drift scoring on synthetic traces: a perfect hold scores clean
    lit and dark windows, a trace that drifts in the dark shows up
    in dark MAE, the per-window drift and the lit-dark delta, and
    the relight reveal fires
  - the child-safe register: gutters and misses never buzz, and with
    the confirmation cue off a whole trial produces no STIM at all
  - echo error maths: the settled blind reproduction scores signed
    and absolute error, and block_stats splits constant and variable
    error by delay
  - the hand matrix: one hand rotates its four fingers, both hands
    rotate all eight at equal counts, and cross-hand echoes study
    with the mirror finger
  - the level ladder: moves on the lit-dark delta (lit accuracy at
    level 1), announced plainly, and never moves on a guttered hold
  - the trial rows: waveform hold / reproduce with params and
    segment bounds that parse back to the windows that ran
  - the screen: steady-state frames allocate no new surfaces, in the
    lit and the dark state both
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


HOLD_KW = dict(
    seed=42, level=3, target_lo_pct=5.0, target_hi_pct=25.0,
    hold_s=16.0, n_dark=2, dark_frac=0.45, lit_lead_s=3.0,
    lit_gap_s=2.0, lit_tail_s=2.0, tol_pct=3.0, max_press_counts=400.0)


def _hold_params(**over):
    from finger_rehab.game.modes.lighthouse import draw_hold_params
    kw = dict(HOLD_KW)
    kw.update(over)
    return draw_hold_params(**kw)


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
    e.current_block = "lighthouse"
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
    and the mode reads them like live sensor data. `pct_by_lane`
    overrides pct for a specific lane (cross-hand echoes read two)."""

    def __init__(self):
        from finger_rehab.game.force_stream import ForceReading
        self._reading_cls = ForceReading
        self.counts = 0.0
        self.pct: float | None = None
        self.pct_by_lane: dict[int, float] = {}
        self.gone = False
        self.rebaselined: list = []

    def read(self, lane):
        if self.gone:
            return None
        pct = self.pct_by_lane.get(lane, self.pct)
        return self._reading_cls(counts=self.counts, percent=pct)

    def sample_age_s(self, lane, now):
        return None if self.gone else 0.0

    def rebaseline(self, lanes=None):
        self.rebaselined.append(lanes)


def _mode(e, hands=None, **over):
    from finger_rehab.game.modes.lighthouse import LighthouseMode
    from finger_rehab.game.scoring import ScoreConfig
    kw = dict(
        engine=e,
        lanes_by_hand=hands or {"right": [0, 1, 2, 3]},
        level=1,
        dark_windows_by_level=[0, 1, 2],
        dark_frac_by_level=[0.0, 0.25, 0.45],
        holds_per_finger=2,
        echoes_per_finger=1,
        target_lo_pct=5.0,
        target_hi_pct=25.0,
        hold_s=16.0,
        tol_pct=3.0,
        lit_lead_s=3.0,
        lit_gap_s=2.0,
        lit_tail_s=2.0,
        ignite_hold_s=0.5,
        ignite_timeout_s=10.0,
        echo_show_s=3.0,
        echo_delays_s=[2.0, 5.0],
        echo_reproduce_s=4.0,
        echo_settle_s=2.0,
        promote_lit_mae_pct=1.5,
        promote_delta_pct=1.5,
        demote_delta_pct=6.0,
        dark_bonus_points=2,
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
    m = LighthouseMode(**kw)
    m.view = _ViewStub()
    return m


def _fresh_profile(hand="right"):
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    prof = CalibrationProfile(hand=hand, participant="T",
                              resting=[100.0] * 4,
                              press=[160.0] * 4)
    prof.set_max_press([400.0] * 4)
    return prof


def _ready_mode(e=None, hands=None, **over):
    e = e or _engine()
    e.calibration_profiles.setdefault("right", _fresh_profile())
    return _mode(e, hands=hands, **over)


def _to_trial(m, t0=1000.0):
    """Drive a probe-free mode from init into the trial phase and
    return the time of the first trial tick."""
    m._tick(t0)
    assert m.phase == "announce", m.phase
    t = t0 + m.announce_s + 0.01
    m._tick(t)
    assert m.phase == "trial", m.phase
    return t


def _play_hold(m, t_start, force_fn, dt=1.0 / 60.0):
    """Feed one full hold trial. force_fn(t_hold, target, lit) gives
    the percent-of-max force; t_hold is None while igniting."""
    from finger_rehab.game.modes.lighthouse import feedback_lit
    t = t_start
    while m.phase == "trial":
        t += dt
        if m.sub == "ignite" or m.hold_t0 is None:
            m.view.pct = force_fn(None, m.target_pct, True)
        else:
            t_h = t - m.hold_t0
            lit = feedback_lit(m.params, t_h)
            m.view.pct = force_fn(t_h, m.target_pct, lit)
        m._tick(t)
    return t


def _play_echo(m, t_start, repro_pct, dt=1.0 / 60.0):
    """Feed one full echo trial: in band while studying, released in
    the delay, then a blind press at repro_pct."""
    t = t_start
    while m.phase == "trial":
        t += dt
        if m.sub in ("enter", "study"):
            m.view.pct = m.target_pct
        elif m.sub == "delay":
            m.view.pct = 0.0
        else:
            m.view.pct = repro_pct
        m._tick(t)
    return t


# ---- fade scheduling ----------------------------------------------------


class FadeSchedulingTests(unittest.TestCase):
    def test_same_seed_same_plan(self):
        self.assertEqual(_hold_params(), _hold_params())

    def test_different_seed_different_plan(self):
        a, b = _hold_params(seed=1), _hold_params(seed=2)
        self.assertNotEqual(a["target_pct"], b["target_pct"])

    def test_level_one_is_fully_lit(self):
        from finger_rehab.game.modes.lighthouse import (feedback_lit,
                                                 hold_segments_from_params)
        p = _hold_params(level=1, n_dark=0, dark_frac=0.0)
        self.assertEqual(p["n_dark"], 0)
        segs = hold_segments_from_params(p)
        self.assertEqual([s[0] for s in segs], ["lit1"])
        for i in range(50):
            self.assertTrue(feedback_lit(p, 16.0 * i / 49.0))

    def test_dark_windows_honour_lead_gap_and_tail(self):
        from finger_rehab.game.modes.lighthouse import hold_segments_from_params
        for seed in range(20):
            p = _hold_params(seed=seed)
            segs = hold_segments_from_params(p)
            darks = [(a, b) for n, a, b in segs if n.startswith("dark")]
            self.assertEqual(len(darks), 2)
            self.assertGreaterEqual(darks[0][0], 3.0 - 1e-9)
            self.assertGreaterEqual(darks[1][0] - darks[0][1], 2.0 - 1e-9)
            self.assertGreaterEqual(16.0 - darks[1][1], 2.0 - 1e-9)
            dark_total = sum(b - a for a, b in darks)
            self.assertAlmostEqual(dark_total, 0.45 * 16.0, places=6)

    def test_segments_tile_the_hold_exactly(self):
        from finger_rehab.game.modes.lighthouse import hold_segments_from_params
        for seed in range(8):
            segs = hold_segments_from_params(_hold_params(seed=seed))
            self.assertAlmostEqual(segs[0][1], 0.0)
            self.assertAlmostEqual(segs[-1][2], 16.0)
            for (n1, _a1, b1), (n2, a2, _b2) in zip(segs, segs[1:]):
                self.assertAlmostEqual(b1, a2, msg=f"{n1}->{n2}")

    def test_feedback_lit_matches_the_segments(self):
        from finger_rehab.game.modes.lighthouse import (feedback_lit,
                                                 hold_segments_from_params)
        p = _hold_params()
        for name, a, b in hold_segments_from_params(p):
            mid = (a + b) / 2.0
            self.assertEqual(feedback_lit(p, mid),
                             name.startswith("lit"), msg=name)

    def test_short_holds_drop_windows_not_shrink_them(self):
        # A demo-length hold cannot fit two darks plus the lit
        # guarantees; the planner drops to what fits rather than
        # planning windows too short to drift in.
        from finger_rehab.game.modes.lighthouse import (MIN_DARK_S,
                                                 hold_segments_from_params)
        p = _hold_params(hold_s=6.0)
        self.assertLess(p["n_dark"], 2)
        if p["n_dark"]:
            self.assertGreaterEqual(p["dark_s"], MIN_DARK_S)
        segs = hold_segments_from_params(p)
        self.assertAlmostEqual(segs[-1][2], 6.0)

    def test_misconfigured_hold_warns_instead_of_lying_on_screen(self):
        """Audit finding #87: a hold_s too short to fit a dark window
        at a level with dark_frac > 0 used to leave the top strip and
        the announce line quoting the level's configured dark share
        while the planner silently drew zero dark windows. The mode
        now warns at construction, and the screen-facing helper reads
        the drawn params instead of the static config."""
        from finger_rehab.ui.lighthouse_screen import _dark_frac_and_windows
        with self.assertLogs("finger_rehab.game.modes.lighthouse",
                             level="WARNING") as cm:
            m = _ready_mode(level=2, hold_s=5.0,
                            dark_windows_by_level=[0, 1, 2],
                            dark_frac_by_level=[0.0, 0.25, 0.45],
                            holds_per_finger=1, echoes_per_finger=0)
        self.assertTrue(any("cannot fit" in msg for msg in cm.output))
        m._kind_bag = ["hold"]
        t = _to_trial(m)
        self.assertEqual(m.params.get("n_dark"), 0)
        frac, n = _dark_frac_and_windows(m)
        self.assertEqual(n, 0)
        self.assertAlmostEqual(frac, 0.0)

    def test_well_configured_hold_does_not_warn(self):
        with self.assertRaises(AssertionError):
            with self.assertLogs("finger_rehab.game.modes.lighthouse",
                                 level="WARNING"):
                _ready_mode(level=3, holds_per_finger=1,
                           echoes_per_finger=0)

    def test_rebuild_from_the_packed_cell(self):
        # The offline contract: the notebook parses waveform_params
        # and rebuilds the lit / dark schedule without this module's
        # rng. The packed cell trims floats to 6 significant digits.
        from finger_rehab.data.logger import (pack_waveform_params,
                                       parse_waveform_params)
        from finger_rehab.game.modes.lighthouse import hold_segments_from_params
        p = _hold_params()
        segs = hold_segments_from_params(p)
        back = hold_segments_from_params(
            parse_waveform_params(pack_waveform_params(p)))
        self.assertEqual([s[0] for s in segs], [s[0] for s in back])
        for (n, a, b), (_n, a2, b2) in zip(segs, back):
            self.assertLess(abs(a - a2), 1e-3, msg=n)
            self.assertLess(abs(b - b2), 1e-3, msg=n)


# ---- the probe gate -----------------------------------------------------


class ProbeGateTests(unittest.TestCase):
    def test_missing_max_runs_probes_first(self):
        m = _mode(_engine())
        m._tick(0.0)
        self.assertEqual(m.phase, "probe_gap")
        self.assertEqual(len(m._probe_queue), 4)

    def test_fresh_max_skips_probes(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "announce")

    def test_keyboard_source_is_refused_plainly(self):
        e = _engine()
        e.source.provides_samples = False
        m = _mode(e)
        m._tick(0.0)
        self.assertEqual(m.phase, "no_input")


# ---- drift scoring on synthetic traces ----------------------------------


class HoldScoringTests(unittest.TestCase):
    def _hold_mode(self, e=None, level=3, **over):
        m = _ready_mode(e, level=level, **over)
        m._kind_bag = ["hold"] * m.total_trials
        return m

    def test_perfect_hold_scores_clean_everywhere(self):
        m = self._hold_mode()
        t = _to_trial(m)
        _play_hold(m, t, lambda t_h, target, lit: target)
        rec = m._holds[0]
        self.assertFalse(rec.guttered)
        self.assertGreaterEqual(rec.tib_frac, 0.999)
        self.assertLess(rec.lit_mae_pct, 1e-6)
        self.assertLess(rec.dark_mae_pct, 1e-6)
        self.assertLess(abs(rec.delta_pct), 1e-6)
        self.assertEqual(len(rec.drifts_pct), 2)
        for d in rec.drifts_pct:
            self.assertLess(abs(d), 1e-6)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Great")

    def test_dark_drift_is_scored_and_revealed(self):
        m = self._hold_mode()
        t = _to_trial(m)
        reveals = []

        def force(t_h, target, lit):
            if not lit:
                return target + 5.0
            if m.reveal_msg:
                reveals.append(m.reveal_msg)
            return target

        _play_hold(m, t, force)
        rec = m._holds[0]
        self.assertAlmostEqual(rec.dark_mae_pct, 5.0, delta=0.3)
        self.assertLess(rec.lit_mae_pct, 0.5)
        self.assertAlmostEqual(rec.delta_pct, rec.dark_mae_pct
                               - rec.lit_mae_pct, places=6)
        self.assertEqual(len(rec.drifts_pct), 2)
        for d in rec.drifts_pct:
            self.assertAlmostEqual(d, 5.0, delta=0.5)
        self.assertTrue(rec.drift_rate_pct_s > 0)
        # The relight reveal fired and said the drift plainly.
        self.assertTrue(reveals)
        self.assertIn("drifted", reveals[0])

    def test_consistently_off_target_hold_earns_no_dark_bonus(self) -> None:
        """dark_bonus_points must reward staying ACCURATE in the dark,
        not merely staying put. A hold sitting at a constant target+8%
        offset the whole time (lit and dark) has zero within-window
        drift -- the old "steady" test on drift alone -- but is 100%
        off-target and zero time in band. It must not out-score a real
        Good hold, and no dark bonus should be earned at all."""
        m = self._hold_mode()
        t = _to_trial(m)
        _play_hold(m, t, lambda t_h, target, lit: target + 8.0)
        rec = m._holds[0]
        self.assertLess(rec.tib_frac, 0.01)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertLess(row["points"], m.score_cfg.good_points)

    def test_gutter_is_silent_and_logged_as_miss(self):
        # Child-safe register: a hold that never ignites gutters with
        # no buzz at all, even with the confirmation cue switched on.
        e = _engine(cfg_extra={"cue.buzz_after": True})
        m = self._hold_mode(e)
        t = _to_trial(m)
        end = t + m.ignite_timeout_s + 1.0
        while m.phase == "trial" and t < end:
            t += 1.0 / 60.0
            m.view.pct = 0.0
            m._tick(t)
        rec = m._holds[0]
        self.assertTrue(rec.guttered)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertIn("guttered=True", row["stimulus"])
        self.assertFalse([c for c in m.engine._sent
                          if str(c).startswith("STIM")])
        self.assertEqual(m.level, 3)   # gutters never move the ladder

    def test_no_buzz_at_all_with_the_cue_off(self):
        m = self._hold_mode()
        t = _to_trial(m)
        _play_hold(m, t, lambda t_h, target, lit: target)
        self.assertFalse([c for c in m.engine._sent
                          if str(c).startswith("STIM")])

    def test_dropout_pauses_scoring_instead_of_judging_it(self):
        m = self._hold_mode()
        t = _to_trial(m)

        def force(t_h, target, lit):
            if t_h is not None:
                third = float(m.params["hold_s"]) / 3.0
                m.view.gone = third <= t_h < 2 * third
            return target

        _play_hold(m, t, force)
        m.view.gone = False
        rec = m._holds[0]
        self.assertFalse(rec.guttered)
        self.assertGreaterEqual(rec.tib_frac, 0.999)

    def test_stalled_probe_ends_the_block_gently(self):
        # The probe state machine only leaves rest/press on force
        # crossings, so a finger that cannot produce 30 counts used
        # to leave the block on MAX PRESS CHECK forever with
        # Esc-abandon as the only exit; worst here because the 5-25%
        # band targets exactly the low-force patients.
        e = _engine()
        e.finish_block = lambda: None
        m = _mode(e)          # no stored max: probes must run
        t = 1000.0
        m._tick(t)
        guard = t + 10.0
        while m.phase != "probe" and t < guard:
            t += 0.1
            m._tick(t)
        self.assertEqual(m.phase, "probe")
        end = t + m.PROBE_STALL_S + 2.0
        while m.phase == "probe" and t < end:
            t += 0.25
            m.view.counts = 5.0     # never clears the floor
            m.view.pct = 1.0
            m._tick(t)
        self.assertEqual(m.phase, "done")
        self.assertEqual(m.end_reason, "probe_timeout")

    def test_dropout_through_a_dark_window_fabricates_no_drift(self):
        # A dropout spanning a whole dark window used to capture the
        # same stale _last_pct at entry and exit, so the patient was
        # shown "drifted +0.0%", the steady-dark bonus was paid, and
        # drift 0.0 flowed into block_stats as real data.
        m = self._hold_mode()
        t = _to_trial(m)
        reveals = []

        def force(t_h, target, lit):
            if t_h is not None:
                m.view.gone = not lit    # device gone in every dark
                if m.reveal_msg and (not reveals
                                     or reveals[-1] != m.reveal_msg):
                    reveals.append(m.reveal_msg)
            return target

        _play_hold(m, t, force)
        m.view.gone = False
        rec = m._holds[0]
        self.assertEqual(rec.drifts_pct, [])
        self.assertIsNone(rec.drift_rate_pct_s)
        self.assertIsNone(rec.dark_mae_pct)
        row = m.engine.trial_logger.rows[0]
        # No steady-dark bonus: base points only.
        self.assertEqual(row["points"], m.score_cfg.great_points)
        # The reveal says what happened instead of inventing a number.
        self.assertTrue(any("Signal lost" in r for r in reveals))
        self.assertFalse(any("drifted" in r for r in reveals))

    def test_trial_row_carries_the_reconstruction_contract(self):
        from finger_rehab.data.logger import (parse_segments,
                                       parse_waveform_params)
        m = self._hold_mode()
        t = _to_trial(m)
        seed = m.trial_seed
        windows = list(m.hold_windows)
        _play_hold(m, t, lambda t_h, target, lit: target)
        hold_t0 = None
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "hold")
        self.assertEqual(row["waveform_seed"], str(seed))
        params = parse_waveform_params(row["waveform_params"])
        self.assertEqual(params["max_press_counts"], 400.0)
        self.assertEqual(params["n_dark"], 2.0)
        segs = parse_segments(row["segment_times"])
        self.assertEqual([s[0] for s in segs],
                         ["ignite"] + [w[0] for w in windows])
        hold_t0 = segs[0][2]           # ignite end is the hold start
        for (name, start, end), (wname, wa, wb) in zip(segs[1:], windows):
            self.assertAlmostEqual(start - hold_t0, wa, places=4)
            self.assertAlmostEqual(end - hold_t0, wb, places=4)
        # RT censoring does not apply to a hold.
        self.assertEqual(row["timeout_ms"], "")

    def test_bilateral_hold_row_names_the_one_hand_that_played(self):
        # Audit finding #86: a hold in a both-hands block used to log
        # hand="both" (the block-level default) even though every hold
        # is one hand's finger, making the trial row's own hand column
        # unusable for a per-trial side filter.
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = self._hold_mode(e, hands={"right": [0, 1, 2, 3],
                                      "left": [4, 5, 6, 7]},
                            holds_per_finger=1, echoes_per_finger=0)
        t = _to_trial(m)
        lane = m.lane
        _play_hold(m, t, lambda t_h, target, lit: target)
        row = m.engine.trial_logger.rows[0]
        self.assertIn(row["hand"], ("right", "left"))
        self.assertEqual(row["hand"], "right" if lane < 4 else "left")

    def test_segment_markers_bracket_the_hold_in_raw(self):
        m = self._hold_mode()
        t = _to_trial(m)
        n_windows = len(m.hold_windows)
        _play_hold(m, t, lambda t_h, target, lit: target)
        starts = [ev for ev in m.engine.raw_logger.events
                  if ev["event"] == "segment_start"]
        ends = [ev for ev in m.engine.raw_logger.events
                if ev["event"] == "segment_end"]
        # ignite plus every lit / dark window, each opened and closed.
        self.assertEqual(len(starts), n_windows + 1)
        self.assertEqual(len(ends), n_windows + 1)

    def test_demo_cap_trims_trials_and_length(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, demo_trials=2)
        self.assertLessEqual(m.total_trials, 2)
        self.assertLessEqual(m.hold_s, 6.0)


# ---- echo error maths ---------------------------------------------------


class EchoTests(unittest.TestCase):
    def _echo_mode(self, e=None, hands=None, **over):
        m = _ready_mode(e, hands=hands, **over)
        m._kind_bag = ["echo"]
        m.total_trials = 1
        # The single echo ends the block; the real finish_block needs
        # full engine state this fixture does not carry.
        m.engine.finish_block = lambda: None
        return m

    def test_echo_phases_run_in_order(self):
        m = self._echo_mode()
        t = _to_trial(m)
        seen = []

        def watch():
            if not seen or seen[-1] != m.sub:
                seen.append(m.sub)

        while m.phase == "trial":
            t += 1.0 / 60.0
            if m.sub in ("enter", "study"):
                m.view.pct = m.target_pct
            elif m.sub == "delay":
                m.view.pct = 0.0
            else:
                m.view.pct = m.target_pct + 4.0
            m._tick(t)
            if m.phase == "trial":
                watch()
        self.assertEqual(seen, ["enter", "study", "delay", "reproduce"])

    def test_reproduction_error_is_the_settled_offset(self):
        m = self._echo_mode()
        t = _to_trial(m)
        _play_echo(m, t, repro_pct=m.target_pct + 4.0)
        rec = m._echoes[0]
        self.assertFalse(rec.guttered)
        self.assertAlmostEqual(rec.signed_err_pct, 4.0, delta=0.1)
        self.assertAlmostEqual(rec.abs_err_pct, 4.0, delta=0.1)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "reproduce")
        self.assertEqual(row["early_late"], "Good")   # inside 2x tol
        self.assertIn("delay_s=", row["stimulus"])

    def test_echo_row_segments_parse_back(self):
        from finger_rehab.data.logger import (parse_segments,
                                       parse_waveform_params)
        m = self._echo_mode()
        t = _to_trial(m)
        _play_echo(m, t, repro_pct=m.target_pct)
        row = m.engine.trial_logger.rows[0]
        params = parse_waveform_params(row["waveform_params"])
        self.assertEqual(params["cross"], 0.0)
        segs = parse_segments(row["segment_times"])
        self.assertEqual([s[0] for s in segs],
                         ["enter", "study", "delay", "reproduce"])
        study = next(s for s in segs if s[0] == "study")
        delay = next(s for s in segs if s[0] == "delay")
        repro = next(s for s in segs if s[0] == "reproduce")
        self.assertAlmostEqual(study[2] - study[1], m.echo_show_s,
                               delta=0.05)
        self.assertAlmostEqual(delay[2] - delay[1], params["delay_s"],
                               delta=0.05)
        self.assertAlmostEqual(repro[2] - repro[1], m.echo_reproduce_s,
                               delta=0.05)

    def test_holding_through_the_delay_gutters_instead_of_scoring_great(
            self):
        # Audit finding #84: a finger that never releases through the
        # delay used to arm reproduce instantly (its resting force
        # already clears ENTRY_FLOOR_PCT) and score a perfect echo.
        # The standard force-sense paradigm needs a real release
        # between encode and reproduce.
        m = self._echo_mode()
        t = _to_trial(m)
        dt = 1.0 / 60.0
        while m.phase == "trial":
            t += dt
            m.view.pct = m.target_pct   # never lets go, ever
            m._tick(t)
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertIn("released=False", row["stimulus"])
        rec = m._echoes[0]
        self.assertTrue(rec.guttered)
        self.assertIsNone(rec.signed_err_pct)

    def test_a_genuine_release_still_arms_reproduce_normally(self):
        # The release check must not break the ordinary path: dipping
        # below the floor for a moment during the delay still lets
        # reproduce arm and score normally.
        m = self._echo_mode()
        t = _to_trial(m)
        _play_echo(m, t, repro_pct=m.target_pct)
        row = m.engine.trial_logger.rows[0]
        self.assertIn("released=True", row["stimulus"])
        self.assertNotEqual(row["early_late"], "Miss")

    def test_no_blind_press_gutters_gently(self):
        m = self._echo_mode()
        t = _to_trial(m)
        end_guard = t + 60.0

        def run():
            nonlocal t
            while m.phase == "trial" and t < end_guard:
                t += 1.0 / 60.0
                if m.sub in ("enter", "study"):
                    m.view.pct = m.target_pct
                else:
                    m.view.pct = 0.0        # never presses again
                m._tick(t)

        run()
        rec = m._echoes[0]
        self.assertTrue(rec.guttered)
        self.assertIsNone(rec.signed_err_pct)
        self.assertFalse([c for c in m.engine._sent
                          if str(c).startswith("STIM")])

    def test_constant_and_variable_error_split_by_delay(self):
        from finger_rehab.game.modes.lighthouse import EchoRecord
        m = self._echo_mode()

        def rec(delay, err):
            return EchoRecord(hand="right", finger=0, lane=0, set_lane=0,
                              cross=False, delay_s=delay, target_pct=15.0,
                              guttered=False, signed_err_pct=err,
                              abs_err_pct=abs(err))

        m._echoes = [rec(2.0, 1.0), rec(2.0, 3.0),
                     rec(5.0, -2.0), rec(5.0, -6.0)]
        by_delay = m.block_stats()["echo"]["by_delay"]
        self.assertAlmostEqual(by_delay["2"]["constant_err_pct"], 2.0)
        self.assertAlmostEqual(by_delay["2"]["variable_err_pct"], 1.414,
                               places=3)
        self.assertAlmostEqual(by_delay["5"]["constant_err_pct"], -4.0)
        self.assertAlmostEqual(by_delay["5"]["abs_err_pct"], 4.0)

    def test_cross_hand_echo_studies_with_the_mirror_finger(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = self._echo_mode(e, hands={"right": [0, 1, 2, 3],
                                      "left": [4, 5, 6, 7]})
        t = _to_trial(m)
        self.assertTrue(m.cross)
        self.assertNotEqual(m.hand, m.set_hand)
        self.assertEqual(m.set_lane % 4, m.lane % 4)
        self.assertEqual(float(m.params["cross"]), 1.0)
        # Both the studying and the matching lane were re-tared for
        # the trial.
        tared = [ln for lanes in m.view.rebaselined
                 for ln in (lanes or [])]
        self.assertIn(m.lane, tared)
        self.assertIn(m.set_lane, tared)
        # The study half reads the SET lane: force on the match lane
        # alone must not ignite the study.
        m.view.pct = 0.0
        m.view.pct_by_lane = {m.lane: m.target_pct}
        for _ in range(120):
            t += 1.0 / 60.0
            m._tick(t)
        self.assertEqual(m.sub, "enter")
        m.view.pct_by_lane = {m.set_lane: m.target_pct}
        for _ in range(120):
            t += 1.0 / 60.0
            m._tick(t)
        self.assertIn(m.sub, ("study", "delay"))

    def _cross_mode(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        return self._echo_mode(e, hands={"right": [0, 1, 2, 3],
                                         "left": [4, 5, 6, 7]})

    def _drive_cross(self, m, hold_set_in_delay, press_set_in_repro):
        """One full cross echo: study normally, then either hold or
        release the SET lane through the delay and reproduce. The set
        lane's force is resolved against the LIVE target (the trial
        draws its target at prep, so a captured-early value would
        silently feed the wrong lane)."""
        t = _to_trial(m)
        self.assertTrue(m.cross)
        guard = t + 120.0
        while m.phase == "trial" and t < guard:
            t += 1.0 / 60.0
            if m.sub in ("enter", "study"):
                m.view.pct = 0.0
                m.view.pct_by_lane = {m.set_lane: m.target_pct,
                                      m.lane: 0.0}
            elif m.sub == "delay":
                m.view.pct_by_lane = {
                    m.set_lane: (m.target_pct if hold_set_in_delay
                                 else 0.0),
                    m.lane: 0.0}
            else:
                m.view.pct_by_lane = {
                    m.set_lane: (m.target_pct if press_set_in_repro
                                 else 0.0),
                    m.lane: m.target_pct}
            m._tick(t)
        return m.engine.trial_logger.rows[0], m._echoes[0]

    def test_cross_echo_study_hand_holding_through_gutters(self):
        # The release gate must cover the STUDY lane too. Watching
        # only the reproduce lane let the study finger hold the
        # reference force through the delay and the blind window, so
        # the trial became live hand-to-hand matching, scored Great
        # with err 0.000, and logged released=True.
        m = self._cross_mode()
        row, rec = self._drive_cross(m, hold_set_in_delay=True,
                                     press_set_in_repro=True)
        self.assertEqual(row["early_late"], "Miss")
        self.assertTrue(rec.guttered)
        self.assertIsNone(rec.signed_err_pct)
        self.assertIn("study_released=False", row["stimulus"])

    def test_cross_echo_repress_during_reproduce_gutters(self):
        # Letting go for the delay and then re-pressing the study
        # finger inside the blind window is the same exploit a beat
        # later, so it gutters too.
        m = self._cross_mode()
        row, rec = self._drive_cross(m, hold_set_in_delay=False,
                                     press_set_in_repro=True)
        self.assertEqual(row["early_late"], "Miss")
        self.assertTrue(rec.guttered)
        self.assertIn("study_released=True", row["stimulus"])

    def test_cross_echo_honest_release_scores_normally(self):
        m = self._cross_mode()
        row, rec = self._drive_cross(m, hold_set_in_delay=False,
                                     press_set_in_repro=False)
        self.assertNotEqual(row["early_late"], "Miss")
        self.assertFalse(rec.guttered)
        self.assertIn("released=True", row["stimulus"])
        self.assertIn("study_released=True", row["stimulus"])
        # The logged rest covers most of the delay, so the analysis
        # can confirm a real memory gap rather than a brief dip.
        rested = float(row["stimulus"].split("rested_s=")[1])
        self.assertGreater(rested, float(m.params["delay_s"]) * 0.8)


# ---- hand matrix --------------------------------------------------------


class HandMatrixTests(unittest.TestCase):
    def test_one_hand_rotates_its_four_fingers(self):
        m = _ready_mode(holds_per_finger=1, echoes_per_finger=1)
        self.assertEqual(m.total_trials, 8)
        lanes = {"hold": [], "echo": []}
        for i in range(m.total_trials):
            m.trials_done = i
            m._prepare_trial()
            lanes[m.kind].append(m.lane)
        self.assertEqual(sorted(lanes["hold"]), [0, 1, 2, 3])
        self.assertEqual(sorted(lanes["echo"]), [0, 1, 2, 3])

    def test_both_hands_means_all_eight_fingers(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
                  holds_per_finger=1, echoes_per_finger=1)
        self.assertEqual(m.total_trials, 16)
        hold_lanes = []
        hold_hands = {"right": 0, "left": 0}
        for i in range(m.total_trials):
            m.trials_done = i
            m._prepare_trial()
            if m.kind == "hold":
                hold_lanes.append(m.lane)
                hold_hands[m.hand] += 1
        # Paired balancing: every finger exactly once, hands equal.
        self.assertEqual(sorted(hold_lanes), list(range(8)))
        self.assertEqual(hold_hands["right"], 4)
        self.assertEqual(hold_hands["left"], 4)

    def test_delays_are_dealt_evenly(self):
        m = _ready_mode(holds_per_finger=1, echoes_per_finger=2,
                        echo_delays_s=[2.0, 5.0])
        delays = []
        for i in range(m.total_trials):
            m.trials_done = i
            m._prepare_trial()
            if m.kind == "echo":
                delays.append(m.delay_s)
        self.assertEqual(delays.count(2.0), delays.count(5.0))


# ---- the level ladder ---------------------------------------------------


class LevelLadderTests(unittest.TestCase):
    def test_level_one_promotes_on_lit_accuracy(self):
        m = _ready_mode(level=1)
        m._move_level(1.0, None)
        self.assertEqual(m.level, 1)
        m._move_level(1.2, None)
        self.assertEqual(m.level, 2)
        self.assertIn("darkens", m.level_msg)
        self.assertIn("level 2", m.level_msg)
        evs = [ev for ev in m.engine.raw_logger.events
               if ev["event"] == "lighthouse_level"]
        self.assertEqual(len(evs), 1)

    def test_higher_levels_move_on_the_lit_dark_delta(self):
        m = _ready_mode(level=2)
        m._move_level(0.5, 1.0)
        self.assertEqual(m.level, 2)
        m._move_level(0.5, 1.2)
        self.assertEqual(m.level, 3)
        self.assertIn("level 3", m.level_msg)
        m._move_level(0.5, 8.0)               # one bad delta drops back
        self.assertEqual(m.level, 2)
        self.assertIn("light returns", m.level_msg)

    def test_level_is_capped_both_ways(self):
        m = _ready_mode(level=3)
        for _ in range(4):
            m._move_level(0.1, 0.1)
        self.assertEqual(m.level, 3)
        m.level = 1
        m._move_level(9.0, None)
        self.assertEqual(m.level, 1)


# ---- pause and block stats ----------------------------------------------


class PauseAndStatsTests(unittest.TestCase):
    def test_pause_mid_trial_restarts_the_trial(self):
        m = _ready_mode(level=2)
        m._kind_bag = ["hold"] * m.total_trials
        t = _to_trial(m)
        m.view.pct = m.target_pct
        m._tick(t + 1.0)
        self.assertEqual(m.phase, "trial")
        trial_before = m.trial_counter
        seed_before = m.trial_seed
        m.on_resume(5.0)
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.trial_counter, trial_before)
        self.assertEqual(m.trial_seed, seed_before)
        self.assertEqual(m.engine.trial_logger.rows, [])
        restarts = [ev for ev in m.engine.raw_logger.events
                    if ev["event"] == "trial_restart"]
        self.assertEqual(len(restarts), 1)

    def test_block_stats_carry_the_results_summary(self):
        m = _ready_mode(level=3)
        finished = []
        m.engine.finish_block = lambda: finished.append(True)
        m._kind_bag = ["hold"]
        m.total_trials = 1
        t = _to_trial(m)
        lane = m.lane
        _play_hold(m, t, lambda t_h, target, lit: target)
        self.assertEqual(m.phase, "done")
        self.assertTrue(finished)
        stats = m.block_stats()
        self.assertEqual(stats["holds"], 1)
        self.assertEqual(stats["gutters"], 0)
        overall = stats["overall"]
        self.assertLess(overall["lit_mae_pct"], 1e-6)
        self.assertLess(overall["dark_drift_pct"], 1e-6)
        self.assertAlmostEqual(overall["lit_dark_delta_pct"], 0.0)
        self.assertIsNotNone(overall["lit_cov"])
        self.assertIn(str(lane), stats["per_lane"])
        self.assertEqual(stats["per_lane"][str(lane)]["delta_level"],
                         m.level)
        # The session-carrying level hook for the next block.
        self.assertEqual(m.engine._lighthouse_level, m.level)

    def test_per_lane_delta_compares_fingers_at_the_same_level(self):
        # Audit finding #85: pooling a lane's delta across every level
        # the global ladder happened to sit at while that finger's
        # holds ran compares fingers on different amounts of dark
        # exposure, since dark MAE grows with dark duration. Two
        # fingers held at levels [1, 3] and two at [2, 3] (as in the
        # audit's own reproduction) must all resolve to level 3, the
        # highest level every finger reached.
        from finger_rehab.game.modes.lighthouse import HoldRecord

        def h(lane, level, delta):
            return HoldRecord(hand="right", finger=lane, lane=lane,
                              level=level, target_pct=15.0,
                              guttered=False, tib_frac=1.0,
                              lit_mae_pct=1.0, lit_cov=0.1,
                              dark_mae_pct=1.0, delta_pct=delta)

        m = _ready_mode()
        m._holds = [
            h(2, 1, 0.5), h(2, 3, 9.0),
            h(3, 1, 0.6), h(3, 3, 9.5),
            h(0, 2, 2.0), h(0, 3, 8.0),
            h(1, 2, 2.5), h(1, 3, 8.5),
        ]
        per_lane = m.block_stats()["per_lane"]
        for lane, expect in (("0", 8.0), ("1", 8.5), ("2", 9.0),
                             ("3", 9.5)):
            self.assertEqual(per_lane[lane]["delta_level"], 3)
            self.assertAlmostEqual(per_lane[lane]["delta_pct"], expect)

    def test_per_lane_delta_falls_back_to_pooling_with_no_common_level(
            self):
        # No level has every played lane represented (early in a
        # block): fall back to pooling that lane's own holds rather
        # than reporting nothing, and say so via delta_level=None.
        from finger_rehab.game.modes.lighthouse import HoldRecord

        def h(lane, level, delta):
            return HoldRecord(hand="right", finger=lane, lane=lane,
                              level=level, target_pct=15.0,
                              guttered=False, tib_frac=1.0,
                              lit_mae_pct=1.0, lit_cov=0.1,
                              dark_mae_pct=1.0, delta_pct=delta)

        m = _ready_mode()
        m._holds = [h(0, 1, 1.0), h(1, 2, 3.0)]
        per_lane = m.block_stats()["per_lane"]
        self.assertIsNone(per_lane["0"]["delta_level"])
        self.assertAlmostEqual(per_lane["0"]["delta_pct"], 1.0)
        self.assertAlmostEqual(per_lane["1"]["delta_pct"], 3.0)


# ---- the screen ---------------------------------------------------------


class ScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()
        pygame.display.set_mode((320, 200))

    def _screen_and_mode(self, level=3):
        import pygame
        from finger_rehab.ui.lighthouse_screen import LighthouseScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.paused = False
        m = _mode(e, level=level)
        m._kind_bag = ["hold"] * m.total_trials
        e.mode = m
        sc = LighthouseScreen(e)
        sc._countdown_until = 0.0
        t = _to_trial(m)
        m.view.pct = m.target_pct
        m._tick(t + 0.5)
        surf = pygame.Surface((1280, 800))
        return sc, m, surf, t

    def _drive_to(self, m, t, lit_wanted):
        """Advance the hold until the feedback state matches."""
        from finger_rehab.game.modes.lighthouse import feedback_lit
        guard = t + 30.0
        while t < guard:
            t += 1.0 / 60.0
            m.view.pct = m.target_pct
            m._tick(t)
            if m.sub == "hold" and m.hold_t0 is not None:
                if feedback_lit(m.params, t - m.hold_t0) == lit_wanted:
                    return t
        raise AssertionError("never reached the wanted state")

    def test_steady_frames_allocate_no_new_surfaces(self):
        sc, m, surf, t = self._screen_and_mode()
        t = self._drive_to(m, t, lit_wanted=True)
        sc.draw(surf)                       # warm the lit caches
        t = self._drive_to(m, t, lit_wanted=False)
        sc.draw(surf)                       # warm the dark overlay
        calls = []
        original = sc._new_surface
        sc._new_surface = lambda *a, **k: (calls.append(a)
                                           or original(*a, **k))
        for k in range(30):
            t += 1.0 / 60.0
            m.view.pct = m.target_pct + (k % 5) * 0.2
            m._tick(t)
            sc.draw(surf)
        self.assertEqual(calls, [])

    def test_dark_frame_draws_the_dark_room(self):
        import finger_rehab.ui.lighthouse_screen as ls
        sc, m, surf, t = self._screen_and_mode()
        t = self._drive_to(m, t, lit_wanted=False)
        seen = []
        original = ls.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        ls.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            ls.draw_text = original
        joined = " | ".join(seen)
        self.assertIn("Hold steady in the dark", joined)
        # The blind display never prints the live force.
        self.assertNotIn(f"{m.target_pct:.1f}", joined)

    def test_trial_furniture_names_the_trial(self):
        import finger_rehab.ui.lighthouse_screen as ls
        sc, m, surf, t = self._screen_and_mode()
        seen = []
        original = ls.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append(str(text))
            return original(s, text, pos, *a, **k)

        ls.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            ls.draw_text = original
        joined = " | ".join(seen)
        self.assertIn("Trial 1 of", joined)
        self.assertIn("Level", joined)
        self.assertEqual(
            sc._hand_finger_words(m.hand, m.finger),
            f"{m.hand.upper()} "
            f"{['INDEX', 'MIDDLE', 'RING', 'LITTLE'][m.finger]}")


# ---- results screen ------------------------------------------------------


class ResultsCardTests(unittest.TestCase):
    """Audit finding #107 (lighthouse half): the LIT STEADINESS card
    printed the coefficient of variation, where higher means LESS
    steady, under a label that reads as higher-is-better with no CoV
    qualifier, unlike the per-lane chart right below it."""

    @staticmethod
    def _lh_summary():
        return {
            "holds": 8,
            "levels": {"start": 1, "final": 2, "trace": [1, 2]},
            "hands": ["right"],
            "per_lane": {},
            "overall": {"lit_cov": 0.12, "dark_drift_pct": 1.5,
                       "lit_dark_delta_pct": 2.0},
            "echo": {"overall": {"abs_err_pct": 1.1}},
        }

    def _draw(self, lh_summary):
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
        e.current_block, e.hand_mode = "lighthouse", "right"
        e.best_streak, e.per_lane_stats = 0, {}
        e.hit_streak = 0
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"lighthouse": lh_summary}})()
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

    def test_lit_variability_card_names_the_cov(self):
        cards = self._draw(self._lh_summary())
        labels = [lbl for lbl, _val in cards]
        self.assertIn("LIT VARIABILITY (CoV)", labels)
        self.assertNotIn("LIT STEADINESS", labels)
        value = dict(cards)["LIT VARIABILITY (CoV)"]
        self.assertEqual(value, "12.0%")

    def test_delta_card_flags_mixed_levels(self):
        # A block whose ladder moved pools holds measured under
        # different dark exposure into one delta: say so on the card,
        # same rule as Force Pilot's pooled cards.
        cards = self._draw(self._lh_summary())    # trace [1, 2]
        labels = [lbl for lbl, _val in cards]
        self.assertIn("LIT VS DARK (mixed levels)", labels)
        one_level = self._lh_summary()
        one_level["levels"] = {"start": 2, "final": 2, "trace": [2, 2]}
        labels = [lbl for lbl, _val in self._draw(one_level)]
        self.assertIn("LIT VS DARK", labels)
        self.assertNotIn("LIT VS DARK (mixed levels)", labels)


if __name__ == "__main__":
    unittest.main()
