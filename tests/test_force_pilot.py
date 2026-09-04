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
        span_pct=40.0,
        base_pct=8.0,
        visual_gain=1.0,
        ring_interval_s=1.5,
        ring_points=2,
        exit_buzz_ms=80.0,
        exit_buzz_cooldown_s=1.0,
        probe_presses=3,
        probe_floor_counts=30.0,
        probe_max_age_s=6 * 3600.0,
        announce_s=0.5,
        mid_rest_s=15.0,
        step_grace_s=0.6,
        passes=1,
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


# ---- the wave ladder ---------------------------------------------------


# The spec table the thesis levels rest on: level, slug, finger, corridor
# half-width, run seconds, top component Hz, and the percent-of-max range
# the target covers. Changing a number here is changing the study, so it
# is written out once and pinned rather than derived from the code.
LADDER_TABLE = [
    (1, "slow_breath", 0, 8.0, 14.8333, 0.15, 8.0, 20.0),
    (2, "tide", 1, 8.0, 13.5, 0.0, 8.0, 28.0),
    (3, "swell", 2, 8.0, 16.0, 0.20, 8.0, 26.0),
    (4, "stairs", 3, 6.0, 14.7, 0.0, 8.0, 26.0),
    (5, "hills", 0, 6.0, 13.8, 0.0, 8.0, 24.0),
    (6, "beach_waves", 1, 6.0, 13.0, 0.3333, 8.0, 22.0),
    (7, "heartbeat", 2, 5.0, 13.5, 0.50, 10.0, 25.0),
    (8, "dunes", 3, 5.0, 14.0, 0.0, 8.0, 26.0),
    (9, "chop", 1, 5.0, 14.3333, 0.45, 8.0, 26.0),
    (10, "open_ocean", 2, 4.0, 15.0, 0.47, 8.0, 30.7),
    (11, "storm", 0, 4.0, 15.0, 0.50, 8.0, 27.8),
    (12, "uncharted", 0, 4.0, 15.0, 0.50, 8.0, 32.1),
]


def _level_sections(lvl, seed=7, pass_idx=1):
    from finger_rehab.game.modes.force_pilot import (
        LADDER_BY_LVL, params_from_level, sections_from_params,
        uncharted_phases)
    w = LADDER_BY_LVL[lvl]
    phases = (uncharted_phases(seed, pass_idx)
              if w.slug == "uncharted" else ())
    p = params_from_level(w, pass_idx, base_pct=8.0, span_pct=40.0,
                          gain=1.0, max_press_counts=400.0,
                          grace_s=0.6, phases=phases)
    return p, sections_from_params(p)


class LadderTests(unittest.TestCase):
    """The twelve waves themselves: the table, the maths, and the
    promise that every participant flies the same ladder."""

    def test_ladder_matches_the_spec_table(self):
        from finger_rehab.game.modes.force_pilot import (
            LADDER, run_duration_s, target_pct)
        self.assertEqual(len(LADDER), 12)
        for row, w in zip(LADDER_TABLE, LADDER):
            lvl, slug, finger, hw, dur, fmax, lo, hi = row
            self.assertEqual((w.lvl, w.slug, w.finger, w.hw_pct),
                             (lvl, slug, finger, hw), slug)
            _p, secs = _level_sections(lvl)
            self.assertAlmostEqual(run_duration_s(secs), dur, places=3,
                                   msg=slug)
            top = max([max(s.freqs_hz) for s in secs if s.kind == "osc"]
                      or [0.0])
            self.assertAlmostEqual(top, fmax, places=4, msg=slug)
            vals = [target_pct(secs, i * dur / 1500.0)
                    for i in range(1501)]
            self.assertAlmostEqual(min(vals), lo, delta=0.05, msg=slug)
            self.assertLessEqual(max(vals), hi + 0.05, slug)
            # The whole ladder lives inside the 0 to span altitude map.
            self.assertGreaterEqual(min(vals), 0.0, slug)
            self.assertLessEqual(max(vals), 40.0, slug)

    def test_the_top_frequency_is_half_a_hertz(self):
        # Above about 0.5 Hz an unpredictable target stops measuring
        # tracking and starts measuring lag (McRuer and Jex 1967 via
        # Drop 2016; Slifkin 2000 on 1 Hz correction bursts).
        for lvl in range(1, 13):
            _p, secs = _level_sections(lvl)
            for s in secs:
                for f in s.freqs_hz:
                    self.assertLessEqual(f, 0.5 + 1e-9, lvl)

    def test_sections_are_continuous(self):
        # A step between sections would be an uncontrolled stimulus.
        # Stairs is the exception the mode names: its steps ARE the
        # level, which is why they carry a grace window.
        from finger_rehab.game.modes.force_pilot import target_pct
        for lvl in range(1, 13):
            _p, secs = _level_sections(lvl)
            for k in range(1, len(secs)):
                before = target_pct(secs, secs[k].start_s - 1e-7)
                after = target_pct(secs, secs[k].start_s + 1e-7)
                if lvl == 4:
                    continue
                self.assertAlmostEqual(before, after, places=3,
                                       msg=f"{lvl} {secs[k].name}")

    def test_fingers_and_corridors_climb_the_way_the_design_says(self):
        from finger_rehab.game.modes.force_pilot import LADDER
        counts = {f: sum(1 for w in LADDER if w.finger == f)
                  for f in range(4)}
        # Index carries both storms (the novel-versus-repeated pair
        # must be one finger or it is a finger comparison).
        self.assertEqual(counts, {0: 4, 1: 3, 2: 3, 3: 2})
        self.assertEqual([w.finger for w in LADDER if w.lvl in (11, 12)],
                         [0, 0])
        widths = [w.hw_pct for w in LADDER]
        self.assertEqual(widths, sorted(widths, reverse=True))
        self.assertEqual(sorted(set(widths), reverse=True),
                         [8.0, 6.0, 5.0, 4.0])

    def test_stairs_is_the_only_level_with_grace_windows(self):
        from finger_rehab.game.modes.force_pilot import grace_windows
        for lvl in range(1, 13):
            p, secs = _level_sections(lvl)
            wins = grace_windows(secs, float(p["grace_s"]))
            if lvl == 4:
                self.assertEqual(len(wins), 6)
                self.assertEqual([round(a, 2) for a, _b in wins],
                                 [1.5, 3.7, 5.9, 8.1, 10.3, 12.5])
                self.assertTrue(all(abs(b - a - 0.6) < 1e-9
                                    for a, b in wins))
            else:
                self.assertEqual(wins, [], lvl)

    def test_every_level_rebuilds_from_the_packed_cell(self):
        # The offline contract: the notebook parses waveform_params
        # and rebuilds the target with no seed and no import. Every
        # number in the ladder is written to six significant digits or
        # fewer, so the round trip is exact rather than merely close.
        from finger_rehab.data.logger import (pack_waveform_params,
                                              parse_waveform_params)
        from finger_rehab.game.modes.force_pilot import (
            run_duration_s, sections_from_params, target_pct)
        for lvl in range(1, 13):
            p, secs = _level_sections(lvl)
            cell = pack_waveform_params(p)
            self.assertLess(len(cell), 1024, lvl)
            back = sections_from_params(parse_waveform_params(cell))
            self.assertEqual([s.name for s in back],
                             [s.name for s in secs], lvl)
            dur = run_duration_s(secs)
            worst = max(abs(target_pct(secs, dur * i / 999.0)
                            - target_pct(back, dur * i / 999.0))
                        for i in range(1000))
            self.assertLess(worst, 1e-4, f"level {lvl} drifted {worst}")

    def test_legacy_params_still_rebuild(self):
        # Sessions recorded before the ladder carry the seven-section
        # draw. They must still re-score, in the game and in the
        # notebook's copy of this builder.
        from finger_rehab.data.logger import (pack_waveform_params,
                                              parse_waveform_params)
        from finger_rehab.game.modes.force_pilot import (
            run_duration_s, sections_from_params, target_pct)
        p = _params()
        secs = sections_from_params(p)
        self.assertEqual([s.name for s in secs],
                         ["hold_in", "ramp_up", "hold_top", "release",
                          "sine", "pre_assess", "assess_sos"])
        back = sections_from_params(
            parse_waveform_params(pack_waveform_params(p)))
        dur = run_duration_s(secs)
        worst = max(abs(target_pct(secs, dur * i / 399.0)
                        - target_pct(back, dur * i / 399.0))
                    for i in range(400))
        self.assertLess(worst, 1e-3)

    def test_params_carry_the_header_the_notebook_reads(self):
        p, _secs = _level_sections(4)
        self.assertEqual(p["ladder"], "waves_v1")
        self.assertEqual(p["lvl"], 4)
        self.assertEqual(p["wave"], "stairs")
        self.assertEqual(p["pass"], 1)
        self.assertEqual(p["fixed"], 1)
        self.assertEqual(p["hw_pct"], 6.0)
        self.assertEqual(p["grace_s"], 0.6)
        self.assertEqual(p["n_sec"], 7)
        p12, _s12 = _level_sections(12)
        self.assertEqual(p12["fixed"], 0)     # the one novel level
        self.assertEqual(p12["grace_s"], 0.0)

    def test_uncharted_matches_the_storm_except_for_its_phases(self):
        from finger_rehab.game.modes.force_pilot import run_duration_s
        _p11, storm = _level_sections(11)
        _p12, unch = _level_sections(12)
        self.assertAlmostEqual(run_duration_s(storm),
                               run_duration_s(unch), places=6)
        s_osc = [s for s in storm if s.kind == "osc"][0]
        u_osc = [s for s in unch if s.kind == "osc"][0]
        self.assertEqual(s_osc.freqs_hz, u_osc.freqs_hz)
        self.assertEqual(s_osc.amps_pct, u_osc.amps_pct)
        self.assertNotEqual(s_osc.phases_rad, u_osc.phases_rad)

    def test_uncharted_redraws_per_block_and_the_rest_never_moves(self):
        from finger_rehab.game.modes.force_pilot import uncharted_phases
        a = uncharted_phases(11111)
        b = uncharted_phases(22222)
        self.assertNotEqual(a, b)
        self.assertEqual(a, uncharted_phases(11111))     # same seed
        for lvl in (1, 5, 11):
            _pa, sa = _level_sections(lvl, seed=11111)
            _pb, sb = _level_sections(lvl, seed=22222)
            self.assertEqual(
                [(s.name, s.dur_s, s.a_pct, s.b_pct, s.freqs_hz,
                  s.amps_pct, s.phases_rad) for s in sa],
                [(s.name, s.dur_s, s.a_pct, s.b_pct, s.freqs_hz,
                  s.amps_pct, s.phases_rad) for s in sb], lvl)


class LadderOrderTests(unittest.TestCase):
    """Basil's brief: the same levels in the same order every play."""

    def _plan(self, m):
        return [(w.lvl, w.slug, hand, p) for w, hand, p in m._plan]

    def test_the_plan_is_identical_across_blocks_and_participants(self):
        hands = {"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]}
        e1 = _engine("both")
        e1.session.participant = "P01"
        e2 = _engine("both")
        e2.session.participant = "SOMEBODY-ELSE"
        m1 = _mode(e1, hands=hands, seed=1)
        m2 = _mode(e2, hands=hands, seed=987654321)
        self.assertEqual(self._plan(m1), self._plan(m2))
        self.assertEqual(len(m1._plan), 24)

    def test_one_hand_climbs_one_to_twelve(self):
        m = _mode(_engine())
        self.assertEqual([w.lvl for w, _h, _p in m._plan],
                         list(range(1, 13)))
        self.assertEqual({h for _w, h, _p in m._plan}, {"right"})

    def test_both_hands_fly_each_level_back_to_back(self):
        m = _mode(_engine("both"),
                  hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        pairs = [(w.lvl, h) for w, h, _p in m._plan]
        first = m.hand_order[0]
        other = m.hand_order[1]
        self.assertEqual(pairs[:4], [(1, first), (1, other),
                                     (2, first), (2, other)])
        # Every level is flown once by each hand, and the finger is
        # the level's finger on both sides.
        for lvl in range(1, 13):
            got = [h for lv, h in pairs if lv == lvl]
            self.assertEqual(got, [first, other], lvl)

    def test_passes_repeat_the_whole_ladder(self):
        m = _mode(_engine(), passes=2)
        self.assertEqual(m.total_runs, 24)
        self.assertEqual([p for _w, _h, p in m._plan],
                         [1] * 12 + [2] * 12)
        self.assertEqual([w.lvl for w, _h, _p in m._plan],
                         list(range(1, 13)) * 2)

    def test_a_selected_hand_flies_its_own_lanes(self):
        m = _mode(_engine("left"), hands={"left": [4, 5, 6, 7]})
        lanes = []
        for _ in range(len(m._plan)):
            m._prepare_run()
            lanes.append(m.lane)
        self.assertEqual(lanes, [4 + w.finger for w in m.levels])


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
        e.finish_block = lambda: None
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
        # The Davidson 2026 marker: error during a ramp DOWN must be
        # separable from error during a ramp up. The split is by
        # direction, not by section name, so it works on every ramp
        # level of the ladder (Tide, Hills, Dunes).
        m = self._ready_mode(levels=[2])         # Tide: flood then ebb
        t = _to_run_phase(m)
        release = next(s for s in m.sections
                       if s.kind == "ramp" and s.b_pct < s.a_pct)

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
        # The plan for the NEXT run replaced m.sections at close, so
        # the count comes from the level that actually played.
        names = [s.name for s in _level_sections(1)[1]]
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


class BlockFlowTests(unittest.TestCase):
    """The shape of a block: one short card between runs, one rest,
    and the whole ladder inside the clinic's time promise."""

    def _drive(self, m, t=1000.0, force=None):
        """Play the block to the end, collecting every enforced wait."""
        force = force or (lambda t_run, target: target)
        from finger_rehab.game.modes.force_pilot import target_pct
        waits = []
        m._tick(t)
        guard = 0
        while m.phase != "done" and guard < 5000:
            guard += 1
            if m.phase in ("announce", "rest"):
                view = m.wait_view(t)
                waits.append((view["kind"], round(view["total"], 3),
                              view["show"]))
                t = (m._phase_until or t) + 0.001
                m._tick(t)
                continue
            if m.phase == "run":
                while m.phase == "run":
                    t += 1.0 / 60.0
                    t_run = t - (m.run_t0 or t)
                    m.view.pct = force(t_run,
                                       target_pct(m.sections, t_run))
                    m._tick(t)
                continue
            break
        return t, waits

    def _mode_both(self, **over):
        e = _engine(hand_mode="both")
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        return _mode(e, hands={"right": [0, 1, 2, 3],
                               "left": [4, 5, 6, 7]},
                     announce_s=1.8, **over)

    def test_only_one_wait_in_the_block_is_longer_than_a_card(self):
        # Basil's brief: not much time between runs. Every gap is the
        # 1.8 s card except one rest at the halfway point, and only
        # that rest is long enough to draw the skip chip.
        m = self._mode_both()
        _t, waits = self._drive(m)
        self.assertEqual(m.runs_done, 24)
        cards = [w for w in waits if w[0] == "announce"]
        rests = [w for w in waits if w[0] == "rest"]
        self.assertEqual(len(cards), 24)
        self.assertEqual(len(rests), 1)
        self.assertTrue(all(w[1] == 1.8 and w[2] is False for w in cards))
        self.assertEqual(rests[0][1], 15.0)
        self.assertTrue(rests[0][2])          # the chip is drawn

    def test_the_rest_lands_halfway_up_the_ladder(self):
        m = self._mode_both()
        seen = []
        t = 1000.0
        m._tick(t)
        guard = 0
        from finger_rehab.game.modes.force_pilot import target_pct
        while m.phase != "done" and guard < 5000:
            guard += 1
            if m.phase == "rest":
                seen.append(m.runs_done)
            if m.phase in ("announce", "rest"):
                t = (m._phase_until or t) + 0.001
                m._tick(t)
                continue
            if m.phase == "run":
                while m.phase == "run":
                    t += 1.0 / 60.0
                    t_run = t - (m.run_t0 or t)
                    m.view.pct = target_pct(m.sections, t_run)
                    m._tick(t)
                continue
            break
        # After level 6 on both hands: 6 levels x 2 hands = 12 runs.
        self.assertEqual(sorted(set(seen)), [12])

    def test_a_both_hands_block_fits_the_clinic_promise(self):
        m = self._mode_both()
        t, _waits = self._drive(m)
        minutes = (t - 1000.0) / 60.0
        self.assertLess(minutes, 7.0)
        self.assertGreater(minutes, 6.0)

    def test_one_hand_is_twelve_runs_and_half_the_time(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, announce_s=1.8)
        t, waits = self._drive(m)
        self.assertEqual(m.runs_done, 12)
        self.assertEqual(len([w for w in waits if w[0] == "rest"]), 1)
        self.assertLess((t - 1000.0) / 60.0, 4.0)

    def test_every_level_is_flown_once_in_ladder_order(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, announce_s=1.8)
        self._drive(m)
        self.assertEqual([r.level for r in m._records],
                         list(range(1, 13)))
        self.assertEqual([r.wave for r in m._records][:3],
                         ["slow_breath", "tide", "swell"])
        self.assertEqual([r.finger for r in m._records],
                         [0, 1, 2, 3, 0, 1, 2, 3, 1, 2, 0, 0])

    def test_the_card_shows_the_last_run_and_the_next_wave(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        # One card, carrying both halves: the run just flown and the
        # rung coming next.
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m._last_result["wave"], "Slow breath")
        self.assertAlmostEqual(m._last_result["tic"], 1.0, places=3)
        self.assertEqual(m.level, 2)
        self.assertEqual(m.wave.slug, "tide")

    def test_the_demo_plays_four_rungs_on_one_hand(self):
        e = _engine(hand_mode="both")
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
                  demo_trials=6, demo_levels=[1, 4, 7, 12])
        self.assertTrue(m.demo)
        self.assertEqual([w.lvl for w in m.levels], [1, 4, 7, 12])
        self.assertEqual(len(m.hand_order), 1)
        self.assertEqual(m.total_runs, 4)
        self.assertEqual(m.mid_rest_s, 0.0)
        t, waits = self._drive(m)
        self.assertEqual([w[0] for w in waits], ["announce"] * 4)
        self.assertTrue(m.block_stats()["demo"])


class GraceWindowTests(unittest.TestCase):
    """Stairs only: the target jumps in zero time and no finger can
    follow it, so that window is not scored at all."""

    def _stairs(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        return _mode(e, levels=[4])

    def test_an_exit_inside_the_grace_window_costs_nothing(self):
        m = self._stairs()
        t = _to_run_phase(m)
        self.assertEqual(m.level, 4)
        self.assertEqual(len(m.grace), 6)

        def force(t_run, target):
            inside = any(a <= t_run < b for a, b in m.grace)
            return target + (20.0 if inside else 0.0)

        _play_run(m, t, force)
        rec = m._records[0]
        self.assertEqual(rec.stalls, 0)
        self.assertGreaterEqual(rec.tic_frac, 0.999)
        self.assertLess(rec.mae_pct, 1e-6)
        # The graced seconds are dropped from the scored time, not
        # scored as if they were tracked well.
        self.assertAlmostEqual(rec.scored_s, m.duration_s - 6 * 0.6,
                               delta=0.1)

    def test_still_being_out_after_the_grace_window_stalls(self):
        m = self._stairs()
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target + 20.0)
        rec = m._records[0]
        # One stall on the opening exit plus one at each step edge
        # where the grace ends and the trace is still outside.
        self.assertEqual(rec.stalls, 7)

    def test_no_ring_sits_inside_a_grace_window(self):
        m = self._stairs()
        _to_run_phase(m)
        for t_ring in m.ring_times:
            self.assertFalse(any(a <= t_ring < b for a, b in m.grace),
                             t_ring)

    def test_the_grace_length_is_logged_with_the_run(self):
        m = self._stairs()
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        row = m.engine.trial_logger.rows[0]
        self.assertIn("grace_s=3.6", row["stimulus"])
        self.assertIn("grace_s=0.6", row["waveform_params"])


# ---- hands ------------------------------------------------------------


class HandMatrixTests(unittest.TestCase):
    def test_left_hand_flies_left(self):
        e = _engine(hand_mode="left")
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"left": [0, 1, 2, 3]})
        m._tick(0.0)
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.hand, "left")
        self.assertEqual(m.total_runs, 12)

    def test_both_hands_means_all_eight_fingers(self):
        e = _engine(hand_mode="both")
        e.calibration_profiles["right"] = _fresh_profile()
        e.calibration_profiles["left"] = _fresh_profile("left")
        m = _mode(e, hands={"right": [0, 1, 2, 3],
                            "left": [4, 5, 6, 7]})
        self.assertEqual(m.total_runs, 24)
        lanes = set()
        hand_counts = {"right": 0, "left": 0}
        for _ in range(24):
            m._prepare_run()
            lanes.add(m.lane)
            hand_counts[m.hand] += 1
        self.assertEqual(lanes, set(range(8)))
        # Each hand flies every level once, so the counts match by
        # construction rather than by a balanced draw.
        self.assertEqual(hand_counts["right"], 12)
        self.assertEqual(hand_counts["left"], 12)

    def test_the_hand_order_follows_the_study_cell(self):
        # hand1 from the battery's counterbalancing cell flies first,
        # so a participant's hand order is the same every play and
        # matches the order the rest of the battery used.
        from finger_rehab.data.intake import cell_for
        for who in ("P01", "P02", "P03", "P04"):
            e = _engine(hand_mode="both")
            e.session.participant = who
            e.session.dominant_hand = "right"
            m = _mode(e, hands={"right": [0, 1, 2, 3],
                                "left": [4, 5, 6, 7]})
            first = ("right" if cell_for(who)["hand_first"] == "dominant"
                     else "left")
            self.assertEqual(m.hand_order, [first,
                                            "left" if first == "right"
                                            else "right"], who)

    def test_a_finger_flies_the_levels_its_table_row_says(self):
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        by_finger = {}
        for _ in range(m.total_runs):
            m._prepare_run()
            by_finger.setdefault(m.finger, []).append(m.level)
        self.assertEqual(by_finger, {0: [1, 5, 11, 12], 1: [2, 6, 9],
                                     2: [3, 7, 10], 3: [4, 8]})


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
        e = _engine()
        e.calibration_profiles["right"] = _fresh_profile()
        finished = []
        e.finish_block = lambda: finished.append(True)
        m = _mode(e, levels=[1])
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
        self.assertIn(stats["best_section"], ("settle", "breath"))
        # Nothing carries between blocks any more: the ladder is fixed.
        self.assertEqual(m.engine._force_pilot_levels, {})

    def test_block_stats_carry_the_ladder_and_the_per_level_table(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        # Two rungs, no mid rest: the halfway rest would otherwise
        # land after the first of two levels.
        m = _mode(e, levels=[1, 2], mid_rest_s=0.0)
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target)
        t = m._phase_until + 0.01
        m._tick(t)                                 # card -> run
        self.assertEqual(m.phase, "run")
        _play_run(m, t, lambda t_run, target: target)
        stats = m.block_stats()
        self.assertEqual(stats["ladder"]["id"], "waves_v1")
        self.assertEqual(stats["ladder"]["passes"], 1)
        self.assertEqual([lv["wave"] for lv in stats["ladder"]["levels"]],
                         ["slow_breath", "tide"])
        self.assertEqual(stats["ladder"]["hand_order"], ["right"])
        self.assertEqual(set(stats["per_level"]), {"1", "2"})
        self.assertEqual(stats["per_level"]["1"]["runs"], 1)
        self.assertEqual(set(stats["per_level_by_hand"]["right"]),
                         {"1", "2"})
        self.assertEqual(stats["step_grace_s"], 0.6)
        # Nothing pools two levels into one row.
        by_level = stats["per_lane"][str(m._records[0].lane)]["by_level"]
        self.assertEqual(set(by_level), {"1"})
        self.assertEqual(set(stats["section_mae_pct_by_level"]),
                         {"1", "2"})


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

    def test_current_section_is_announced_in_words(self):
        """Half a second into Slow breath the plan is inside its
        opening hold, so the screen must name that section and say
        what it asks for. The words come from the section's SHAPE, so
        every wave in the ladder gets them without a name table."""
        import time as _time
        import finger_rehab.ui.force_pilot_screen as fps
        sc, m, surf, _t = self._screen_and_mode()
        # The screen reads run time off the wall clock; anchor the
        # run's start half a second ago so the draw lands in the hold.
        m.run_t0 = _time.perf_counter() - 0.5
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
        self.assertIn("SETTLE", joined)
        self.assertIn("hold it steady", joined)
        self.assertIn("Slow breath", joined)

    def test_the_card_names_the_wave_and_previews_its_shape(self):
        """The one card between runs: the level number and name, the
        coaching line, and the band about to scroll past."""
        import finger_rehab.ui.force_pilot_screen as fps
        sc, m, surf, _t = self._screen_and_mode()
        m.phase = "announce"
        m._last_result = {"label": "Great", "tic": 0.87, "mae": 1.2,
                          "rings": 4, "rings_total": 8,
                          "hand": "right", "finger": 0,
                          "level": 1, "wave": "Slow breath"}
        m._prepare_run()
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
        self.assertIn("NEXT", joined)
        self.assertIn(m.wave.coach, joined)
        self.assertIn("87% in corridor", joined)
        self.assertIn("4 of 8 rings", joined)
        # Nothing on the card may say the order repeats.
        for word in ("fixed", "same order", "random", "repeat"):
            self.assertNotIn(word, joined.lower())

    def test_time_in_corridor_is_the_hero_readout(self):
        """The in-band share is the one large number on the run
        screen: a percent drawn at the hero point size."""
        import finger_rehab.ui.force_pilot_screen as fps
        from finger_rehab.ui.force_pilot_screen import ForcePilotScreen
        sc, m, surf, _t = self._screen_and_mode()
        seen = []
        original = fps.draw_text

        def recorder(s, text, pos, *a, **k):
            seen.append((str(text), k.get("pt", 0)))
            return original(s, text, pos, *a, **k)

        fps.draw_text = recorder
        try:
            sc.draw(surf)
        finally:
            fps.draw_text = original
        heroes = [t for t, pt in seen
                  if t.endswith("%") and pt >= ForcePilotScreen.HERO_PT]
        self.assertEqual(len(heroes), 1)
        self.assertIn("TIME IN CORRIDOR",
                      " | ".join(t for t, _pt in seen))

    def test_release_sections_bake_in_a_distinct_band(self):
        """A ramp asking for LESS force renders in its own colours, so
        easing off reads differently from pressing on. Tide has one of
        each, and the rule is the ramp's direction, not its name."""
        from finger_rehab.game.modes.force_pilot import target_pct
        sc, m, surf, _t = self._screen_and_mode()
        m._next_idx = 1                     # level 2, Tide
        m._prepare_run()
        corridor = sc._build_corridor(m)
        cols = sc._corridor_colours()
        lead_s = sc.MARKER_X / sc.PX_PER_S
        by_name = {sec.name: sec for sec in m.sections}
        for name, want in (("ebb", cols["band_release"]),
                           ("flood", cols["band"]),
                           ("low", cols["band"])):
            sec = by_name[name]
            t_mid = sec.start_s + sec.dur_s / 2.0
            x = int((t_mid + lead_s) * sc.PX_PER_S)
            y = sc._y(target_pct(m.sections, t_mid), m.span_pct) \
                - sc.PLOT_TOP
            got = corridor.get_at((x, y))[:3]
            self.assertEqual(got, tuple(want), name)

    def test_a_step_edge_grace_window_draws_paler(self):
        """Stairs: the unscored window after each step edge is drawn
        in its own tint, so the patient can see the jump is not being
        held against them."""
        from finger_rehab.game.modes.force_pilot import target_pct
        sc, m, surf, _t = self._screen_and_mode()
        m._next_idx = 3                     # level 4, Stairs
        m._prepare_run()
        corridor = sc._build_corridor(m)
        cols = sc._corridor_colours()
        lead_s = sc.MARKER_X / sc.PX_PER_S
        a, b = m.grace[0]
        for t_probe, want in ((a + 0.3, cols["band_grace"]),
                              (b + 0.5, cols["band"])):
            x = int((t_probe + lead_s) * sc.PX_PER_S)
            y = sc._y(target_pct(m.sections, t_probe), m.span_pct) \
                - sc.PLOT_TOP
            self.assertEqual(corridor.get_at((x, y))[:3], tuple(want),
                             t_probe)


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
            m = _mode(e)       # the whole ladder: no _end() here
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

    def _starved_run(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
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
        # The rung is not counted, and it replays after one card.
        self.assertEqual(m.runs_done, 0)
        self.assertEqual(m._last_result["label"], "NoSignal")
        self.assertEqual(m.phase, "announce")
        self.assertEqual(m.level, 1)

    def test_dead_device_gives_the_slot_up_eventually(self):
        e, m, t = self._starved_run()
        for _ in range(m.MAX_NO_SIGNAL_RETRIES):
            t += m.announce_s + 0.05
            m._tick(t)
            self.assertEqual(m.phase, "run")
            self.assertEqual(m.level, 1)     # the same rung replays
            t = _play_run(m, t, lambda t_run, target: target)
        # After the retries the rung is given up and the ladder moves
        # on, with the gap visible as a missing level offline.
        self.assertEqual(m.runs_done, 1)
        self.assertEqual(m._records, [])
        self.assertEqual(m.level, 2)

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
        self.assertIn("OFF THE LINE (mixed levels)", values)

    def test_a_ladder_block_carries_no_level_annotation(self):
        # The wave ladder has no staircase, so block_stats publishes
        # `ladder` and no `levels` map. Every finger flies several
        # rungs, so a single level number per bar would be a lie: the
        # charts draw plain finger labels and the pooled cards carry
        # no mixed-level warning.
        fp = self._fp_summary()
        fp.pop("levels")
        fp["ladder"] = {"id": "waves_v1", "passes": 1,
                        "hand_order": ["right"],
                        "levels": [{"lvl": 1, "wave": "slow_breath"},
                                   {"lvl": 2, "wave": "tide"}]}
        fp["per_level"] = {"1": {"runs": 1, "mae_pct": 4.0},
                           "2": {"runs": 1, "mae_pct": 3.0}}
        chart_calls, cards = self._draw(fp)
        values = dict(cards)
        self.assertIn("IN CORRIDOR", values)
        self.assertNotIn("IN CORRIDOR (mixed levels)", values)
        fp_calls = [c for c in chart_calls if "FINGER" in c["title"]]
        self.assertTrue(fp_calls)
        for c in fp_calls:
            self.assertEqual(c["kw"].get("levels"), [0, 0, 0, 0])

    def test_same_level_fingers_get_no_mixed_note(self):
        fp = self._fp_summary()
        fp["levels"]["right:1"]["final"] = 1   # both fingers at level 1
        _chart_calls, cards = self._draw(fp)
        values = dict(cards)
        self.assertIn("IN CORRIDOR", values)
        self.assertNotIn("IN CORRIDOR (mixed levels)", values)


class ModeSelectHardwareBadgeTests(unittest.TestCase):
    """Audit finding #111: Force Pilot (with Buzz Hunt)
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
                         {"force_pilot", "buzz_hunt"})

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
