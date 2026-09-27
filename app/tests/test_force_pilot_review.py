"""Force Pilot faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: a restarted or replayed run kept a zero read from the force
frozen at the pause or the drop; a pause in the max-press check could
end the block; a replay shared its trial id with the voided run; the
coverage floor counted Stairs grace time as lost signal; the walk-in
ramps before a multisine sat in the press error; the exit byte 141
was tied to a buzz neither config turns on; the mid-ladder rest sent
no rest bytes; a restarted run's old trace sat ahead of the now-line;
and the engine pushed a card armed on resume out by the whole pause.

Notebook side: voided runs were re-scored beside their replays; sample
gaps were bridged with straight lines before the grid measures; the
ladder chapter kept idle runs and its rank correlation needed ten
levels; a paused run's bytes failed the EEG audit; the Lodha split had
three definitions; F6 was decided on a first play; and a passes: 2
block read as one play.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_force_pilot import _engine, _fresh_profile, _mode  # noqa: E402

REST, MAX = 100.0, 400.0


def _real_detector_rig(levels, **over):
    """A mode on the real ForceView and a real FSRDetector: rest 100
    counts, max 400, press threshold rest + 45 (11 percent of max), so
    a light tracking force is not a press."""
    from finger_rehab.game.force_stream import ForceView
    from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector
    e = _engine()
    e.finish_block = lambda: None
    e.calibration_profiles["right"] = _fresh_profile()
    det = FSRDetector(Calibration(num_sensors=4, baseline_alpha=0.0005,
                                  value_alpha=0.35, on_delta=[45] * 4,
                                  off_delta=[35] * 4, abs_on_min=[0] * 4,
                                  abs_off_max=[100000] * 4), hand="right")
    e.detectors["right"] = det
    kw = dict(levels=levels, mid_rest_s=0.0, announce_s=1.8)
    kw.update(over)
    m = _mode(e, **kw)
    m.view = ForceView(e)
    return e, det, m


class _Feeder:
    """Feeds one lane at pct_fn(t) percent of max at 200 Hz and ticks
    the mode every 1/60 s, on the perf_counter clock the mode's
    on_resume reads."""

    def __init__(self, m, det, lane_of=lambda m: m.lane):
        self.m, self.det, self.lane_of = m, det, lane_of
        self.t = time.perf_counter()
        for i in range(400):
            det.feed(self.t - 2.0 + i * 0.005, (int(REST),) * 4)

    def until(self, t_end, pct_fn, board_up=lambda _t: True, dt=0.005):
        nxt = self.t
        while self.t < t_end:
            if board_up(self.t):
                vals = [int(REST)] * 4
                vals[self.lane_of(self.m)] = int(round(
                    REST + pct_fn(self.t) / 100.0 * MAX))
                self.det.feed(self.t, tuple(vals))
            if self.t >= nxt:
                self.m._tick(self.t)
                nxt += 1.0 / 60.0
            self.t += dt
        self.m._tick(self.t)


def _stim(row):
    out = {}
    for part in str(row["stimulus"]).split(";"):
        k, _, v = part.partition("=")
        out[k] = v
    return out


class RestartZeroTests(unittest.TestCase):

    def test_a_pause_mid_run_keeps_the_runs_card_zero(self):
        from finger_rehab.game.modes.force_pilot import target_pct
        e, det, m = _real_detector_rig([1, 5])
        f = _Feeder(m, det)
        m._tick(f.t)
        card_zero = m.view.reference(0)
        f.until(m._phase_until + 0.01, lambda _t: 0.0)
        self.assertEqual(m.phase, "run")
        t0 = m.run_t0
        f.until(t0 + 2.2, lambda tt: target_pct(m.sections, tt - t0))
        # Under the press threshold, so the old tare would take it.
        self.assertFalse(det.pressed[0])
        self.assertGreater(det.val_ema[0], REST + 20)
        m.on_resume(2.0)
        f.t = m._phase_until - m.announce_s
        self.assertEqual(m.phase, "announce")
        self.assertAlmostEqual(m.view.reference(0), card_zero, places=6)
        f.until(m._phase_until + 0.01, lambda _t: 0.0)
        t0 = m.run_t0
        f.until(t0 + m.duration_s + 0.05,
                lambda tt: target_pct(m.sections, tt - t0))
        kv = _stim(e.trial_logger.rows[-1])
        self.assertGreater(float(kv["tic"]), 0.95)
        self.assertLess(float(kv["mae"]), 1.0)

    def test_a_no_signal_replay_keeps_the_zero_and_takes_a_new_id(self):
        from finger_rehab.game.modes.force_pilot import target_pct
        e, det, m = _real_detector_rig([2, 5])      # Tide, middle finger
        f = _Feeder(m, det)
        m._tick(f.t)
        card_zero = m.view.reference(m.lane)
        f.until(m._phase_until + 0.01, lambda _t: 0.0)
        t0 = m.run_t0
        f.until(t0 + m.duration_s + 0.02,
                lambda tt: target_pct(m.sections, tt - t0),
                board_up=lambda tt: not (1.3 <= tt - t0 < 9.5))
        first = e.trial_logger.rows[-1]
        self.assertEqual(first["error_type"], "no_signal")
        self.assertAlmostEqual(m.view.reference(m.lane), card_zero,
                               places=6)
        f.until(m._phase_until + 0.01, lambda _t: 0.0)
        t0 = m.run_t0
        f.until(t0 + m.duration_s + 0.02,
                lambda tt: target_pct(m.sections, tt - t0))
        replay = e.trial_logger.rows[-1]
        self.assertNotEqual(replay["trial"], first["trial"])
        kv = _stim(replay)
        self.assertEqual(kv.get("replays"), str(first["trial"]))
        self.assertGreater(float(kv["tic"]), 0.95)


class ProbePauseTests(unittest.TestCase):

    def test_a_long_pause_in_the_max_press_check_keeps_the_block(self):
        from finger_rehab.hardware.calibration_profile import \
            CalibrationProfile
        e = _engine()
        e.calibration_profiles["right"] = CalibrationProfile(
            hand="right", participant="T", resting=[100.0] * 4,
            press=[160.0] * 4)
        e.record_max_press = lambda hand, vals: None
        calls = []
        e._abandon_if_in_block = lambda: calls.append("abandoned")
        e.show_mode_select = lambda: calls.append("mode_select")
        e.finish_block = lambda: calls.append("finished")
        m = _mode(e)
        m.view.pct = None
        m.view.counts = 0.0
        t = 1000.0
        m._tick(t)
        t += 1.3
        m._tick(t)
        self.assertEqual(m.phase, "probe")
        for _ in range(180):
            t += 1 / 60
            m._tick(t)
        t += 30.0
        m.on_resume(30.0)
        t += 1 / 60
        m._tick(t)
        self.assertEqual(m.phase, "probe")
        self.assertIsNone(m.end_reason)
        self.assertEqual(calls, [])
        left = m.PROBE_STALL_S - (t - m._probe_progress_t)
        self.assertGreater(left, 21.0)


class CoverageFloorTests(unittest.TestCase):

    def _close_with(self, level, scored_frac, grace_frac):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, levels=[level], mid_rest_s=0.0)
        m.view.pct = 10.0
        t = 1000.0
        m._tick(t)
        t = m._phase_until + 0.01
        m._tick(t)
        self.assertEqual(m.phase, "run")
        m._scored_s = scored_frac * m.duration_s
        m._grace_s = grace_frac * m.duration_s
        m._close_run(t + m.duration_s)
        return e.trial_logger.rows[-1]

    def test_grace_time_counts_as_covered(self):
        # Stairs: 45 percent scored plus 10 percent in step-edge grace
        # had a live signal for 55 percent of the plan.
        row = self._close_with(4, 0.45, 0.10)
        self.assertNotEqual(row["error_type"], "no_signal")

    def test_a_run_under_half_covered_is_still_voided(self):
        row = self._close_with(4, 0.35, 0.10)
        self.assertEqual(row["error_type"], "no_signal")


class WalkInRampTests(unittest.TestCase):

    def test_the_walk_in_ramp_stays_out_of_the_press_split(self):
        from finger_rehab.game.modes.force_pilot import WALK_IN_RAMPS
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, levels=[10], mid_rest_s=0.0)      # Open ocean
        m.view.pct = 8.0
        t = 1000.0
        m._tick(t)
        t = m._phase_until + 0.01
        m._tick(t)
        first = m.sections[0]
        self.assertIn(first.name, WALK_IN_RAMPS)
        self.assertEqual(first.kind, "ramp")
        m._sec_idx = 0
        for i in range(30):
            m._score_frame(0.02 * i, 30.0, 1 / 60)
        self.assertEqual(m._press_acc, [0.0, 0.0])
        self.assertEqual(m._release_acc, [0.0, 0.0])
        # The same frames still count towards the run's own error.
        self.assertGreater(m._abs_err_int, 0.0)


class ExitFeedbackTests(unittest.TestCase):

    def _mode(self, buzz_after, markers):
        from finger_rehab.game.modes.force_pilot import target_pct
        e = _engine(cfg_extra={"cue.buzz_after": buzz_after})
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        e._eeg_feedback_markers = markers
        codes, pulses = [], []
        e._eeg_send = lambda code, lane=None, t_event=None: codes.append(code)
        e.pulse_motor = lambda lane, ms: pulses.append(lane)
        m = _mode(e, levels=[2], mid_rest_s=0.0)
        t = 1000.0
        m._tick(t)
        t = m._phase_until + 0.01
        m._tick(t)
        # Leave the corridor three times, 2 s apart.
        while m.phase == "run":
            t += 1 / 60
            t_run = t - m.run_t0
            off = 20.0 if int(t_run) in (3, 6, 9) else 0.0
            m.view.pct = target_pct(m.sections, t_run) + off
            m._tick(t)
        return e, codes, pulses

    def test_the_exit_is_marked_with_the_buzz_off(self):
        _e, codes, pulses = self._mode(buzz_after=False, markers=True)
        self.assertEqual(codes.count(141), 3)
        self.assertEqual(pulses, [])

    def test_nothing_is_sent_with_both_off(self):
        _e, codes, pulses = self._mode(buzz_after=False, markers=False)
        self.assertNotIn(141, codes)
        self.assertEqual(pulses, [])

    def test_the_buzz_still_rides_its_switch(self):
        _e, codes, pulses = self._mode(buzz_after=True, markers=False)
        self.assertEqual(len(pulses), 3)
        self.assertNotIn(141, codes)

    def test_a_run_ends_without_a_confirmation_buzz(self):
        from finger_rehab.game.modes.force_pilot import target_pct
        e = _engine(cfg_extra={"cue.buzz_after": True})
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, levels=[2], mid_rest_s=0.0)
        t = 1000.0
        m._tick(t)
        t = m._phase_until + 0.01
        m._tick(t)
        while m.phase == "run":
            t += 1 / 60
            m.view.pct = target_pct(m.sections, t - m.run_t0)
            m._tick(t)
        self.assertEqual(e.trial_logger.rows[-1]["early_late"], "Great")
        self.assertEqual([c for c in e._sent if str(c).startswith("STIM")],
                         [])


class RestMarkerTests(unittest.TestCase):

    def test_the_mid_ladder_rest_is_bracketed(self):
        from finger_rehab.game.modes.force_pilot import target_pct
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        codes = []
        e._eeg_send = lambda code, lane=None, t_event=None: codes.append(code)
        m = _mode(e, levels=[1, 2], mid_rest_s=5.0)
        m._rest_after = {0}
        t = 1000.0
        m._tick(t)
        while m.phase != "done":
            t += 1 / 60
            if m.phase == "run":
                m.view.pct = target_pct(m.sections, t - m.run_t0)
            m._tick(t)
        self.assertEqual(codes.count(244), 1)
        self.assertEqual(codes.count(245), 1)
        self.assertLess(codes.index(244), codes.index(245))


class ResumeOrderTests(unittest.TestCase):

    def test_a_card_armed_on_resume_is_not_pushed_out_by_the_pause(self):
        e = _engine()
        e.finish_block = lambda: None
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e, levels=[1, 5], mid_rest_s=0.0, announce_s=1.8)
        t = time.perf_counter()
        m._tick(t)
        m._tick(m._phase_until + 0.01)
        self.assertEqual(m.phase, "run")
        e.mode = m
        e.paused = True
        e._pause_started_at = time.perf_counter() - 60.0
        e._block_paused_s = 0.0
        e._force_window_start = None
        e._eeg_send = lambda *a, **k: None
        e._resume_now()
        w = m.armed_wait()
        left = w.remaining(time.perf_counter())
        self.assertLess(left, 2.0)
        self.assertAlmostEqual(left, m._phase_until - time.perf_counter(),
                               delta=0.05)


class TraceTests(unittest.TestCase):

    def test_a_restarted_run_starts_a_fresh_trace(self):
        import pygame
        from finger_rehab.ui.force_pilot_screen import ForcePilotScreen
        theme = SimpleNamespace(muted=(120, 120, 120),
                                background=(250, 250, 250),
                                foreground=(10, 10, 10),
                                lane_active=[(200, 0, 0)] * 4)
        eng = SimpleNamespace(theme=theme,
                              layout=SimpleNamespace(width=1280, height=800))
        scr = ForcePilotScreen(eng)
        mode = SimpleNamespace(trial_counter=3, run_t0=50.0,
                               craft_display_pct=12.0, span_pct=40.0,
                               finger=0, stalled=False, sections=[])
        surf = pygame.Surface((1280, 800))
        for i in range(540):
            scr._draw_trace(surf, mode, i / 60.0)
        mode.run_t0 = 62.0          # the same run, restarted
        scr._draw_trace(surf, mode, 0.05)
        self.assertEqual(len(scr._trace), 1)


# ---- notebook ------------------------------------------------------------


def _write_block(root, drive, n_trials, levels, meta_extra=None, **over):
    """Play a block through the real mode with a synchronous raw log
    and a trial log on disk, the way test_force_pilot_notebook_levels
    does, and return the folder. `drive(m, e, raw, clock)` plays it."""
    from finger_rehab.data.logger import TrialLogger
    from finger_rehab.hardware import eeg_trigger
    from tests.test_force_pilot_notebook_levels import _RealRawLogger
    folder = root / "2026-08-10" / "Pat_100000_force_pilot"
    folder.mkdir(parents=True)
    e = _engine()
    e.finish_block = lambda: None
    e.calibration_profiles["right"] = _fresh_profile()
    e.trial_logger = TrialLogger(folder / "trials.csv")
    raw = _RealRawLogger(folder / "raw.csv")
    e.raw_logger = raw

    def eeg_send(code, lane=None, t_event=None):
        rec = eeg_trigger.MarkerEmission(code=int(code), lane=lane,
                                         t_event=float(t_event or 0.0),
                                         t_wire=float(t_event or 0.0),
                                         delayed=False, failed=False)
        raw.queue_event("eeg", lane=lane, t_perf=rec.t_event,
                        detail=eeg_trigger.format_detail(rec))

    e._eeg_send = eeg_send
    kw = dict(levels=levels, mid_rest_s=0.0, announce_s=1.8)
    kw.update(over)
    m = _mode(e, **kw)
    m.view.reference = lambda lane: REST
    drive(m, e, raw)
    raw.close()
    meta = {"participant": "Pat", "age": "30", "hand": "right",
            "started_at": "2026-08-10T10:00:00",
            "finished_at": "2026-08-10T10:03:00",
            "source_name": "MultiSerialSource", "software_version": "1.0.0",
            "eeg": {"enabled": True, "pulse_ms": 2, "gap_ms": 2},
            "block_summary": {"block": "force_pilot", "status": "completed",
                              "trials": n_trials, "demo": False,
                              "force_unit": "sensor units"}}
    meta.update(meta_extra or {})
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder, meta


class _Stepper:
    def __init__(self, m, raw):
        self.m, self.raw, self.t = m, raw, 1000.0
        # The real RawLogger stamps an event with the clock at the
        # moment it is queued; here that clock is the simulated one.
        queue_event = raw.queue_event

        def stamped(event, lane=None, detail="", t_perf=None,
                    fsr_vals=None, hand="right"):
            return queue_event(event, lane=lane, detail=detail,
                               t_perf=self.t if t_perf is None else t_perf,
                               fsr_vals=fsr_vals, hand=hand)
        raw.queue_event = stamped
        for i in range(300):
            raw.queue_sample(self.t - 1.5 + i * 0.005, [REST] * 4)
        m._tick(self.t)

    def until(self, t_end, pct_fn, silent=lambda _tr: False):
        m, nxt = self.m, self.t
        while self.t < t_end:
            tr = (self.t - m.run_t0) if (m.phase == "run" and m.run_t0) \
                else -1.0
            gone = m.phase == "run" and silent(tr)
            m.view.gone = gone
            pct = pct_fn(tr) if m.phase == "run" else 0.0
            m.view.pct = pct
            if not gone:
                vals = [REST] * 4
                vals[m.lane] = REST + max(0.0, pct) / 100.0 * MAX
                self.raw.queue_sample(self.t, vals)
            if self.t >= nxt:
                m._tick(self.t)
                nxt += 1 / 60
            self.t += 0.005
        m._tick(self.t)


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def _load(self, root):
        ra = self.ra
        cat = ra.build_catalogue(root=root)
        folders = [Path(p) for p in cat["folder"]]
        trials = ra.load_games(folders, cat)
        metas = ra.load_metas(folders)
        return folders, trials, metas

    def _dropout_block(self, root):
        """Tide voided for lost signal then replayed (with a 1 s gap
        the game rides out), then Hills paused 5 s in and restarted."""
        from finger_rehab.game.modes.force_pilot import target_pct

        def drive(m, e, raw):
            s = _Stepper(m, raw)
            s.until(m._phase_until + 0.01, lambda tr: 0.0)
            s.until(m.run_t0 + m.duration_s + 0.02,
                    lambda tr: target_pct(m.sections, tr),
                    silent=lambda tr: 1.3 <= tr < 9.5)
            s.until(m._phase_until + 0.01, lambda tr: 0.0)
            s.until(m.run_t0 + m.duration_s + 0.02,
                    lambda tr: target_pct(m.sections, tr) + 1.0,
                    silent=lambda tr: 3.0 <= tr < 3.6)
            s.until(m._phase_until + 0.01, lambda tr: 0.0)
            s.until(m.run_t0 + 5.0,
                    lambda tr: target_pct(m.sections, tr) + 1.0)
            raw.queue_event("pause", detail="force_pilot", t_perf=s.t)
            s.t += 2.0
            raw.queue_event("resume", detail="paused_s=2.000", t_perf=s.t)
            m.on_resume(2.0)
            m._phase_until = s.t + m.announce_s
            m.clear_wait()
            s.until(m._phase_until + 0.01, lambda tr: 0.0)
            s.until(m.run_t0 + m.duration_s + 0.02,
                    lambda tr: target_pct(m.sections, tr) + 1.0)

        return _write_block(root, drive, 3, [2, 5])

    def test_voided_runs_are_left_out_and_gaps_blank_the_grid(self):
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder, _meta = self._dropout_block(root)
            folders, trials, metas = self._load(root)
            runs, _dropped = ra.force_tracking_runs(folders, trials, metas)
            self.assertEqual(runs.attrs.get("voided"), 1)
            self.assertEqual(sorted(runs["level"].tolist()), [2, 5])
            tide = runs[runs["level"] == 2].iloc[0]
            # The replay rode out a 0.6 s gap: error kept, grid blank.
            self.assertGreater(tide["max_gap_s"], 0.5)
            self.assertTrue(math.isfinite(tide["mae"]))
            self.assertTrue(math.isnan(tide["lag_ms"]))
            self.assertTrue(math.isnan(tide["low_n"]))
            hills = runs[runs["level"] == 5].iloc[0]
            self.assertTrue(math.isfinite(hills["lag_ms"]))
            self.assertAlmostEqual(hills["mae"], 1.0, delta=0.3)

    def test_the_segment_check_and_eeg_audit_reconcile(self):
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder, meta = self._dropout_block(root)
            folders, trials, metas = self._load(root)
            checked, bad = ra.segment_marker_check(
                folder, ra.continuous_rows(trials))
            self.assertGreater(checked, 0)
            self.assertEqual(bad, 0)
            rows = trials[trials["game"] == ra.game_key(folder)]
            with contextlib.redirect_stdout(io.StringIO()):
                a = ra.eeg_audit_block(folder, meta, rows)
            self.assertTrue(a["ok"], a["problems"])
            self.assertGreater(a["n_restart_bytes"], 0)

    def test_the_rank_correlation_reads_a_short_climb(self):
        rho = self.ra.fp_rank_corr(list(range(1, 10)),
                                   [9 - i for i in range(9)])
        self.assertAlmostEqual(rho, -1.0)
        self.assertTrue(math.isnan(self.ra.fp_rank_corr([1, 2, 3],
                                                        [1, 2, 3])))

    def _passes_block(self, root):
        from finger_rehab.game.modes.force_pilot import target_pct

        def drive(m, e, raw):
            s = _Stepper(m, raw)

            def pct(tr):
                off = (3.0 if m.pass_idx == 1
                       else (1.0 if m.level == 11 else 3.0))
                return target_pct(m.sections, tr) + off
            while m.phase != "done":
                s.until(s.t + 0.5, pct)

        return _write_block(root, drive, 4, [11, 12], passes=2)

    def test_a_passes_2_block_is_two_plays_and_decides_f6(self):
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._passes_block(root)
            folders, trials, metas = self._load(root)
            runs, _ = ra.force_tracking_runs(folders, trials, metas)
            self.assertEqual(sorted(runs["play_idx"].unique().tolist()),
                             [1, 2])
            self.assertTrue((runs.loc[runs["pass"] == 2, "play_idx"]
                             == 2).all())
            with contextlib.redirect_stdout(io.StringIO()):
                out = ra.sec_force_pilot_checks(folders, trials, metas)
            f6 = out["checks"].set_index("id").loc["F6"]
            self.assertIn("latest play", f6["value"])
            self.assertEqual(f6["verdict"], ra.lit_verdict(True))

    def test_f6_waits_for_a_second_play(self):
        ra = self.ra
        g = ra.sec_force_pilot_checks.__globals__
        real = g["force_tracking_runs"]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._passes_block(root)
            folders, trials, metas = self._load(root)
            runs, _ = real(folders, trials, metas)
            one = runs[runs["play_idx"] == 1].copy()
            one.attrs["voided"] = 0
            g["force_tracking_runs"] = lambda *a, **k: (one, 0)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    out = ra.sec_force_pilot_checks(folders, trials, metas)
            finally:
                g["force_tracking_runs"] = real
            f6 = out["checks"].set_index("id").loc["F6"]
            self.assertIn("not decided", f6["value"])
            self.assertEqual(f6["verdict"], ra.lit_verdict(None))

    def test_the_lodha_split_is_one_number(self):
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._passes_block(root)
            folders, trials, metas = self._load(root)
            runs, _ = ra.force_tracking_runs(folders, trials, metas)
            both = runs["low_n"] + runs["high_n"]
            share = float((runs["low_n"] / both).mean())
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                out = ra.sec_force_pilot_checks(folders, trials, metas)
            f5 = out["checks"].set_index("id").loc["F5"]
            self.assertIn(f"{share:.2f}", f5["value"])
            self.assertIn("PLoS ONE", f5["source"])
            meta = metas[next(iter(metas))] if hasattr(metas, "keys") \
                else None
            folder = folders[0]
            block = {"game": ra.game_key(folder), "folder": folder,
                     "meta": meta, "bs": (meta or {}).get("block_summary"),
                     "rows": trials, "hand": "right", "calset": None,
                     "extra": {}}
            emitted = {m: v for _h, m, v, _n in ra._cohort_force_pilot(block)}
            self.assertAlmostEqual(emitted["lodha_ratio"], share, places=6)


if __name__ == "__main__":
    unittest.main()
