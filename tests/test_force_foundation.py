"""The shared foundation the continuous-force modes build on.

Four pieces, each pinned here before any mode uses them:

  - the session max press: probed in-mode, median of two or three
    maximal presses, stored on the hand's CalibrationProfile with a
    backward-compatible load, persisted, and stamped into metadata
  - continuous force access: per-frame baseline-subtracted counts and
    percent-of-max per lane, with a FROZEN reference so a sustained
    sub-threshold hold cannot be absorbed by the drifting baseline
  - timed motor pulses: shorter than the firmware's 150 ms hold via a
    scoped early STOP, longer via re-arming, floor clamped to the
    measured MIN_PULSE_MS rather than pretending
  - the logging contract: waveform, waveform_params, waveform_seed,
    segment_times trial columns plus segment_start / segment_end
    raw-stream markers, enough to rebuild every target trajectory and
    cut every scored window offline
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _profile(hand="right"):
    """A usable single-hand profile with easy numbers: resting 100,
    light press 160, so the gap is 60 counts everywhere."""
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    return CalibrationProfile(
        hand=hand,
        empty=[10.0] * 4, empty_noise=[1.0] * 4,
        resting=[100.0] * 4, press=[160.0] * 4,
    )


def _engine(hand_mode="right", cfg_extra=None):
    """Engine fixture in the house style: built via __new__, MagicMock
    config, command-recording source."""
    from finger_rehab.game.engine import GameEngine
    values = {
        "fsr.num_sensors_per_hand": 4,
        "motor.cue_ms": 150,
        "motor.pulse_interval_ms": 120,
        "cue.buzz_before": True,
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
    src.send_command = lambda c: (sent.append((c, time.perf_counter()))
                                   or True)
    e.source = src
    e._sent = sent
    e.hand_mode = hand_mode
    e.audio = None
    e.raw_logger = None
    e._screens = {}
    e.mode = None
    e.detectors = {}
    e.calibration_profiles = {}
    e._ensure_metric_state()
    return e


def _commands(e):
    return [c for c, _t in e._sent]


def _add_detector(e, hand):
    from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector
    det = FSRDetector(Calibration(num_sensors=4), hand=hand)
    e.detectors[hand] = det
    return det


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


# ---- session max press on the calibration profile ----------------------


class MaxPressFieldTests(unittest.TestCase):
    def test_defaults_mean_not_measured(self):
        prof = _profile()
        self.assertFalse(prof.has_max_press())
        self.assertIsNone(prof.percent_of_max(0, 50.0))
        self.assertIsNone(prof.max_press_age_s())

    def test_set_and_percent(self):
        prof = _profile()
        prof.set_max_press([200.0, 180.0, 150.0, 120.0])
        self.assertTrue(prof.has_max_press())
        self.assertAlmostEqual(prof.percent_of_max(0, 50.0), 25.0)
        self.assertAlmostEqual(prof.percent_of_max(3, 120.0), 100.0)

    def test_unprobed_finger_stays_unmeasured(self):
        # A zero entry keeps meaning "not measured" for that finger, so
        # a mode cannot score percent targets against it.
        prof = _profile()
        prof.set_max_press([200.0, 0.0, 150.0, 120.0])
        self.assertIsNone(prof.percent_of_max(1, 50.0))

    def test_negative_values_are_a_probe_fault(self):
        prof = _profile()
        prof.set_max_press([-5.0, 200.0, 200.0, 200.0])
        self.assertEqual(prof.max_press[0], 0.0)

    def test_old_file_without_the_field_loads(self):
        # Every profile saved before the field existed must keep
        # loading, with the max simply reading as not measured.
        from finger_rehab.hardware.calibration_profile import CalibrationProfile
        with TemporaryDirectory() as td:
            path = Path(td) / "current_right.json"
            old = {
                "created_at": "2026-01-01T10:00:00",
                "hand": "right",
                "empty": [10.0] * 4, "empty_noise": [1.0] * 4,
                "resting": [100.0] * 4, "press": [160.0] * 4,
                "press_all": [0.0] * 4, "notes": "",
            }
            path.write_text(json.dumps(old))
            prof = CalibrationProfile.load(path)
            self.assertIsNotNone(prof)
            self.assertFalse(prof.has_max_press())

    def test_round_trip_keeps_the_max(self):
        from finger_rehab.hardware.calibration_profile import CalibrationProfile
        prof = _profile()
        prof.set_max_press([210.0, 190.0, 160.0, 130.0])
        with TemporaryDirectory() as td:
            path = Path(td) / "current_right.json"
            prof.save(path)
            back = CalibrationProfile.load(path)
        self.assertEqual(back.max_press, [210.0, 190.0, 160.0, 130.0])
        self.assertEqual(back.max_press_measured_at,
                          prof.max_press_measured_at)

    def test_summary_carries_the_max_into_metadata(self):
        prof = _profile()
        prof.set_max_press([200.0] * 4)
        s = prof.summary()
        self.assertEqual(s["max_press"], [200.0] * 4)
        self.assertTrue(s["max_press_measured_at"])

    def test_age_counts_from_the_measurement(self):
        prof = _profile()
        prof.set_max_press([200.0] * 4,
                            measured_at="2026-01-01T10:00:00")
        measured = time.mktime(
            time.strptime("2026-01-01T10:00:00", "%Y-%m-%dT%H:%M:%S"))
        self.assertAlmostEqual(
            prof.max_press_age_s(now=measured + 90.0), 90.0)


class NeedsProbeTests(unittest.TestCase):
    def test_no_profile_needs_a_probe(self):
        from finger_rehab.game.force_stream import needs_max_press_probe
        self.assertTrue(needs_max_press_probe(None))

    def test_fresh_max_is_reused(self):
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.set_max_press([200.0] * 4)
        self.assertFalse(needs_max_press_probe(prof))

    def test_stale_max_is_re_probed(self):
        # A max persisted from yesterday reflects yesterday's strength
        # and fatigue, so it must be measured again.
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.set_max_press([200.0] * 4,
                            measured_at="2026-01-01T10:00:00")
        measured = time.mktime(
            time.strptime("2026-01-01T10:00:00", "%Y-%m-%dT%H:%M:%S"))
        day_later = measured + 24 * 3600.0
        self.assertTrue(needs_max_press_probe(prof, now=day_later))

    def test_values_without_a_timestamp_are_not_trusted(self):
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.max_press = [200.0] * 4       # bypasses set_max_press
        self.assertTrue(needs_max_press_probe(prof))

    def test_another_patients_max_is_re_probed(self):
        # The stored max is the denominator of every percent target.
        # A profile inherited from another patient (quick-cal skip
        # path) must never supply it, however fresh it is.
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.participant = "PatientA"
        prof.set_max_press([200.0] * 4)
        self.assertFalse(
            needs_max_press_probe(prof, participant="PatientA"))
        self.assertFalse(
            needs_max_press_probe(prof, participant="patienta"))
        self.assertTrue(
            needs_max_press_probe(prof, participant="PatientB"))

    def test_unstamped_max_fails_a_named_identity_check(self):
        # A max with no participant stamp cannot prove whose strength
        # it was; with a session identity in hand the gate re-probes.
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.participant = ""
        prof.set_max_press([200.0] * 4)
        self.assertTrue(
            needs_max_press_probe(prof, participant="PatientB"))
        # Callers with no session identity keep the old behaviour.
        self.assertFalse(needs_max_press_probe(prof))

    def test_two_anonymous_logins_do_not_share_a_max(self):
        # Anonymous sessions all stamp participant "NA", so the name
        # match alone let patient B (second anonymous login inside the
        # freshness window, quick-cal skipped) train percent targets
        # of patient A's strength. The login-session token separates
        # them: same login reuses, a different login re-probes.
        from finger_rehab.game.force_stream import needs_max_press_probe
        prof = _profile()
        prof.participant = "NA"
        prof.session_token = "20260824T010000-aaaaaa"
        prof.set_max_press([200.0] * 4)
        self.assertFalse(needs_max_press_probe(
            prof, participant="NA",
            session_token="20260824T010000-aaaaaa"))
        self.assertTrue(needs_max_press_probe(
            prof, participant="NA",
            session_token="20260824T020000-bbbbbb"))
        # An unstamped anonymous max cannot prove its login either.
        prof.session_token = ""
        self.assertTrue(needs_max_press_probe(
            prof, participant="NA",
            session_token="20260824T020000-bbbbbb"))
        # Named identities do not need the token: the name is the
        # identity, and reuse must survive an app restart mid-day.
        prof.participant = "PatientA"
        self.assertFalse(needs_max_press_probe(
            prof, participant="PatientA",
            session_token="20260824T020000-bbbbbb"))

    def test_summary_names_the_participant(self):
        prof = _profile()
        prof.participant = "PatientA"
        self.assertEqual(prof.summary().get("participant"), "PatientA")


# ---- the probe state machine -------------------------------------------


def _run_press(probe, t0, peak, hold_s=0.4, dt=0.02):
    """Feed one synthetic press: ramp up, plateau at `peak`, release.
    Returns the time after the release settles."""
    t = t0
    for frac in (0.3, 0.6, 0.9):
        probe.update(t, peak * frac)
        t += dt
    steps = int(hold_s / dt)
    for _ in range(steps):
        probe.update(t, peak)
        t += dt
    for frac in (0.5, 0.2, 0.05):
        probe.update(t, peak * frac)
        t += dt
    probe.update(t, 0.0)
    return t + dt


class MaxPressProbeTests(unittest.TestCase):
    def _probe(self, n=3):
        from finger_rehab.game.force_stream import MaxPressProbe
        return MaxPressProbe(n_presses=n, floor_counts=30.0)

    def test_three_presses_median(self):
        p = self._probe()
        t = 0.0
        for peak in (400.0, 380.0, 420.0):
            t = _run_press(p, t, peak)
            t += 0.5                       # rest between attempts
        self.assertEqual(p.state, "done")
        self.assertEqual(p.result(), 400.0)

    def test_two_press_probe_averages(self):
        p = self._probe(n=2)
        t = 0.0
        for peak in (300.0, 340.0):
            t = _run_press(p, t, peak)
            t += 0.5
        self.assertEqual(p.result(), 320.0)   # median of two = mean

    def test_median_tolerates_one_weak_attempt(self):
        # The whole point of the median: one half-effort must not
        # become the denominator of every force target in the session.
        p = self._probe()
        t = 0.0
        for peak in (100.0, 400.0, 420.0):
            t = _run_press(p, t, peak)
            t += 0.5
        self.assertEqual(p.result(), 400.0)

    def test_a_knock_is_not_an_attempt(self):
        # A rise shorter than min_press_s is a knock on the rig, not a
        # press; it must not consume one of the attempts.
        p = self._probe()
        p.update(0.0, 0.0)
        p.update(0.5, 0.0)                 # settled quiet
        p.update(0.52, 500.0)              # spike
        p.update(0.54, 0.0)                # gone within 20 ms
        self.assertEqual(p.peaks, [])
        self.assertEqual(p.state, "rest")

    def test_wobble_does_not_split_a_press(self):
        # A tremorous plateau dips well below peak but stays above the
        # release point; that is one attempt, not two.
        p = self._probe(n=2)
        t = 0.0
        p.update(t, 0.0)
        for counts in (200.0, 400.0, 150.0, 380.0, 400.0):
            t += 0.1
            p.update(t, counts)
        t += 0.1
        p.update(t, 0.0)                   # real release
        self.assertEqual(len(p.peaks), 1)
        self.assertEqual(p.peaks[0], 400.0)

    def test_result_is_none_until_done(self):
        p = self._probe()
        t = _run_press(p, 0.0, 400.0)
        self.assertIsNone(p.result())
        self.assertEqual(p.presses_remaining, 2)

    def test_one_press_is_refused(self):
        from finger_rehab.game.force_stream import MaxPressProbe
        with self.assertRaises(ValueError):
            MaxPressProbe(n_presses=1)

    def test_rest_window_ignores_the_release_tail(self):
        # The tail of an attempt can bounce back over the floor while
        # the finger lifts; inside min_rest_s that is not a new press.
        p = self._probe(n=2)
        t = _run_press(p, 0.0, 400.0)
        p.update(t + 0.05, 60.0)           # bounce inside the rest window
        self.assertEqual(p.state, "rest")
        self.assertEqual(len(p.peaks), 1)


# ---- continuous force access -------------------------------------------


class ForceViewTests(unittest.TestCase):
    def _view(self, e):
        from finger_rehab.game.force_stream import ForceView
        return ForceView(e)

    def _settle(self, det, value, n=200, t0=0.0, dt=0.005):
        t = t0
        for _ in range(n):
            det.feed(t, (value,) * 4)
            t += dt
        return t

    def test_counts_are_resting_subtracted(self):
        e = _engine()
        det = _add_detector(e, "right")
        e.calibration_profiles["right"] = _profile()
        self._settle(det, 150)
        v = self._view(e)
        r = v.read(0)
        self.assertIsNotNone(r)
        # Reference is the calibrated resting level (100), smoothed
        # value has settled at 150.
        self.assertAlmostEqual(r.counts, 50.0, delta=1.0)

    def test_percent_needs_a_probed_max(self):
        e = _engine()
        det = _add_detector(e, "right")
        e.calibration_profiles["right"] = _profile()
        self._settle(det, 150)
        v = self._view(e)
        self.assertIsNone(v.read(0).percent)
        e.calibration_profiles["right"].set_max_press([200.0] * 4)
        self.assertAlmostEqual(v.read(0).percent, 25.0, delta=1.0)

    def test_sustained_hold_is_not_absorbed(self):
        # The detector's baseline EMA follows a sub-threshold hold, so
        # subtracting the LIVE baseline would sag a low hold to
        # zero within a second. The view's frozen reference must not.
        e = _engine()
        det = _add_detector(e, "right")
        t = self._settle(det, 100)         # resting, no profile
        v = self._view(e)
        v.read(0)                          # freezes the reference at rest
        t = self._settle(det, 130, n=800, t0=t)   # held force, ~4 s
        # The live baseline has largely absorbed the hold by now...
        self.assertGreater(det.baseline[0], 120.0)
        # ...but the view still reports the force being produced.
        self.assertAlmostEqual(v.read(0).counts, 30.0, delta=2.0)

    def test_rebaseline_absorbs_drift_between_trials(self):
        e = _engine()
        det = _add_detector(e, "right")
        t = self._settle(det, 100)
        v = self._view(e)
        v.read(0)
        t = self._settle(det, 130, n=800, t0=t)
        v.rebaseline([0])                  # hand resting at the new level
        self.assertLess(v.read(0).counts, 3.0)

    def test_rebaseline_sheds_the_previous_hold(self):
        # The shipped baseline alpha (0.0005) gives the baseline EMA a
        # time constant near 10 s at 200 Hz, so after a 16 s
        # sub-threshold hold it still carries much of the held force
        # through a 6 s rest. Taring from that EMA froze part of the
        # previous trial's press into the next trial's reference
        # (about 25 counts after one 16 s low hold in the headless
        # drive). The tare must come from the resting hand's smoothed
        # value instead, which sheds the hold within a fraction of a
        # second of the release.
        from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector
        e = _engine()
        det = FSRDetector(Calibration(num_sensors=4,
                                      baseline_alpha=0.0005),
                          hand="right")
        e.detectors["right"] = det
        e.calibration_profiles["right"] = _profile()
        e.calibration_profiles["right"].set_max_press([300.0] * 4)
        t = self._settle(det, 100)                       # calibrated rest
        v = self._view(e)
        v.read(0)
        # A 16 s hold at 45 counts above rest, well under the press
        # threshold, then a 6 s rest: the trial-to-trial gap.
        t = self._settle(det, 145, n=3200, t0=t)
        t = self._settle(det, 100, n=1200, t0=t)
        self.assertGreater(det.baseline[0], 110.0)   # EMA still loaded
        v.rebaseline([0])
        # A press to 15 percent of max must read 15 percent, not 7.
        t = self._settle(det, 145, n=200, t0=t)
        self.assertAlmostEqual(v.read(0).percent, 15.0, delta=1.0)

    def test_negative_deltas_clamp_to_zero(self):
        e = _engine()
        det = _add_detector(e, "right")
        e.calibration_profiles["right"] = _profile()
        self._settle(det, 80)              # below the calibrated resting
        v = self._view(e)
        self.assertEqual(v.read(0).counts, 0.0)

    def test_bilateral_lane_maps_to_the_left_detector(self):
        e = _engine(hand_mode="both")
        _add_detector(e, "right")
        left = _add_detector(e, "left")
        e.calibration_profiles["left"] = _profile("left")
        self._settle(left, 150)
        v = self._view(e)
        self.assertEqual(v.active_lanes(), list(range(8)))
        r = v.read(5)                      # left middle
        self.assertIsNotNone(r)
        self.assertAlmostEqual(r.counts, 50.0, delta=1.0)

    def test_no_samples_yet_reads_none(self):
        e = _engine()
        _add_detector(e, "right")
        v = self._view(e)
        self.assertIsNone(v.read(0))

    def test_sample_age_reports_staleness(self):
        e = _engine()
        det = _add_detector(e, "right")
        v = self._view(e)
        self.assertIsNone(v.sample_age_s(0, now=1.0))
        det.feed(10.0, (100,) * 4)
        self.assertAlmostEqual(v.sample_age_s(0, now=10.5), 0.5)


# ---- timed motor pulses ------------------------------------------------


class PulseMotorTests(unittest.TestCase):
    def test_short_pulse_sends_stim_then_scoped_stop(self):
        e = _engine()
        self.assertTrue(e.pulse_motor(0, 40))
        self.assertIn("STIM:1", _commands(e))
        self.assertEqual(len(e._pulse_stops), 1)
        # Not due yet: draining now must not stop the motor early.
        e._drain_motor_queue()
        self.assertNotIn("STOP", _commands(e))
        e._pulse_stops["right"] = time.perf_counter() - 0.001
        e._drain_motor_queue()
        self.assertIn("STOP", _commands(e))
        self.assertEqual(e._pulse_stops, {})

    def test_stop_goes_out_once(self):
        e = _engine()
        e.pulse_motor(0, 40)
        e._pulse_stops["right"] = time.perf_counter() - 0.001
        e._drain_motor_queue()
        e._drain_motor_queue()
        self.assertEqual(_commands(e).count("STOP"), 1)

    def test_requests_below_the_floor_are_clamped(self):
        # A staircase asking for 5 ms would otherwise log a stimulus
        # level the hardware never produced.
        e = _engine()
        before = time.perf_counter()
        e.pulse_motor(0, 5)
        due = e._pulse_stops["right"]
        self.assertGreaterEqual((due - before) * 1000.0, e.MIN_PULSE_MS - 1)

    def test_floor_covers_the_drain_quantisation(self):
        # The early STOP rides the per-frame drain, so nothing shorter
        # than one 60 Hz frame is deliverable; the floor must say so.
        from finger_rehab.game.engine import GameEngine
        self.assertGreaterEqual(GameEngine.MIN_PULSE_MS, 1000.0 / 60.0)

    def test_delivered_length_matches_the_measurement(self):
        # Compact re-run of the measurement behind MIN_PULSE_MS: drain
        # at the display's 60 Hz cadence and time STIM to STOP for a
        # clamped request. Bounds are generous because CI boxes sleep
        # imprecisely; the claim is "one to a few frames", not "5 ms".
        e = _engine()
        e.pulse_motor(0, 10)               # clamps to MIN_PULSE_MS
        stim_t = e._sent[-1][1]
        deadline = time.perf_counter() + 0.5
        stop_t = None
        while time.perf_counter() < deadline and stop_t is None:
            time.sleep(1.0 / 60.0)
            e._drain_motor_queue()
            stops = [t for c, t in e._sent if c == "STOP"]
            if stops:
                stop_t = stops[0]
        self.assertIsNotNone(stop_t, "no STOP within 500 ms")
        gap_ms = (stop_t - stim_t) * 1000.0
        self.assertGreaterEqual(gap_ms, 15.0)
        self.assertLessEqual(gap_ms, 120.0)

    def test_long_pulse_rearms_and_trims_the_tail(self):
        e = _engine()
        e.pulse_motor(0, 400)
        # Re-arms carry the buzz past 150 ms; the scheduled stop trims
        # the final hold to the requested length instead of letting it
        # round up to a multiple of 150.
        self.assertGreater(len(e._motor_queue), 0)
        for lane, _due in e._motor_queue:
            self.assertEqual(lane, 0)
        self.assertEqual(len(e._pulse_stops), 1)

    def test_exactly_one_hold_needs_no_rearm(self):
        e = _engine()
        e.pulse_motor(0, 150)
        self.assertEqual(e._motor_queue, [])

    def test_new_pulse_supersedes_the_previous_one(self):
        # The old pulse's early stop would cut the new pulse short,
        # and its queued re-arms would restart the old finger.
        e = _engine()
        e.pulse_motor(0, 400)
        old_due = e._pulse_stops["right"]
        e.pulse_motor(1, 400)
        self.assertNotEqual(e._pulse_stops["right"], old_due)
        for lane, _due in e._motor_queue:
            self.assertEqual(lane, 1)

    def test_cross_hand_pulses_are_independent(self):
        # One motor per hand at an instant, but the two hands are two
        # boards: simultaneous cross-hand pulses are allowed and each
        # stop is scoped to its own board.
        e = _engine(hand_mode="both")
        e.pulse_motor(0, 40)               # right index
        e.pulse_motor(5, 40)               # left middle
        self.assertIn("STIM:1", _commands(e))
        self.assertIn("STIM:6", _commands(e))
        self.assertEqual(set(e._pulse_stops), {"right", "left"})
        now = time.perf_counter() - 0.001
        e._pulse_stops = {h: now for h in e._pulse_stops}
        e._drain_motor_queue()
        self.assertIn("RIGHT:STOP", _commands(e))
        self.assertIn("LEFT:STOP", _commands(e))

    def test_unilateral_stop_is_unscoped(self):
        # One board means a plain STOP; a LEFT:/RIGHT: prefix would
        # only exist to be routed between boards that are not there.
        e = _engine()
        e.pulse_motor(0, 40)
        e._pulse_stops["right"] = time.perf_counter() - 0.001
        e._drain_motor_queue()
        self.assertIn("STOP", _commands(e))
        self.assertNotIn("RIGHT:STOP", _commands(e))

    def test_stop_all_motors_clears_pulse_stops(self):
        e = _engine()
        e.pulse_motor(0, 40)
        e.stop_all_motors()
        self.assertEqual(e._pulse_stops, {})

    def test_a_cue_cancels_stale_pulse_stops(self):
        # A pending pulse stop surviving into a cue would cut the cue
        # short mid-trial.
        e = _engine()
        e.pulse_motor(0, 40)
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertEqual(e._pulse_stops, {})

    def test_pulse_events_reach_the_raw_log(self):
        e = _engine()
        e.raw_logger = _RawLoggerStub()
        e.pulse_motor(2, 60)
        evs = [ev for ev in e.raw_logger.events
               if ev["event"] == "pulse_motor"]
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["lane"], 2)
        self.assertIn("requested_ms=60", evs[0]["detail"])
        self.assertIn("delivered=yes", evs[0]["detail"])


# ---- the logging contract ----------------------------------------------


class TrialColumnTests(unittest.TestCase):
    def test_the_four_columns_exist_in_order(self):
        from finger_rehab.data.logger import TRIAL_COLUMNS
        tail = TRIAL_COLUMNS[-4:]
        self.assertEqual(tail, ["waveform", "waveform_params",
                                 "waveform_seed", "segment_times"])

    def test_they_come_after_the_existing_contract(self):
        # Appended, never inserted: every older analysis tool indexes
        # the columns it knows, and the pinned ones must not move.
        from finger_rehab.data.logger import TRIAL_COLUMNS
        self.assertLess(TRIAL_COLUMNS.index("cue_target_shown"),
                         TRIAL_COLUMNS.index("waveform"))


class PackingTests(unittest.TestCase):
    def test_params_round_trip(self):
        from finger_rehab.data.logger import (pack_waveform_params,
                                        parse_waveform_params)
        params = {"freq_hz": 0.4, "amplitude_pct": 30.0,
                  "max_press_counts": 412.5, "kind": "sine"}
        cell = pack_waveform_params(params)
        back = parse_waveform_params(cell)
        self.assertEqual(back["freq_hz"], 0.4)
        self.assertEqual(back["amplitude_pct"], 30.0)
        self.assertEqual(back["max_press_counts"], 412.5)
        self.assertEqual(back["kind"], "sine")

    def test_params_pack_sorted_for_stable_grouping(self):
        # Same condition, same string: the notebook groups trials by
        # equality on this cell, so insertion order must not leak in.
        from finger_rehab.data.logger import pack_waveform_params
        a = pack_waveform_params({"b": 1, "a": 2})
        b = pack_waveform_params({"a": 2, "b": 1})
        self.assertEqual(a, b)
        self.assertEqual(a, "a=2;b=1")

    def test_separators_in_params_fail_at_logging_time(self):
        from finger_rehab.data.logger import pack_waveform_params
        with self.assertRaises(ValueError):
            pack_waveform_params({"bad": "a;b"})
        with self.assertRaises(ValueError):
            pack_waveform_params({"al=so": 1})

    def test_segments_round_trip_at_microsecond_resolution(self):
        from finger_rehab.data.logger import pack_segments, parse_segments
        segs = [("lit", 12.345678, 27.345678),
                ("blind", 27.345678, 42.000001)]
        back = parse_segments(pack_segments(segs))
        self.assertEqual(back, segs)

    def test_malformed_segments_drop_not_raise(self):
        from finger_rehab.data.logger import parse_segments
        self.assertEqual(parse_segments("lit:1.0:2.0;garbage;x:y:z"),
                          [("lit", 1.0, 2.0)])

    def test_segment_names_with_separators_are_refused(self):
        from finger_rehab.data.logger import pack_segments
        with self.assertRaises(ValueError):
            pack_segments([("a:b", 0.0, 1.0)])


class ContinuousTrialRowTests(unittest.TestCase):
    def _loggable_engine(self):
        e = _engine()
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
        e.theme = MagicMock()
        e._per_lane_rts = {}
        e._per_lane_misses = {}
        e._per_lane_wrong = {}
        e.trial_logger = _TrialLoggerStub()
        return e

    def _trial(self):
        from finger_rehab.game.modes.classic import PendingTrial
        return PendingTrial(trial_id=7, lane=0, stim_t_perf=0.0,
                             keys_pressed=[0], incorrect_presses=[])

    def test_continuous_info_lands_in_the_row(self):
        from finger_rehab.data.logger import ContinuousTrialLog
        from finger_rehab.game.scoring import TrialResult
        e = self._loggable_engine()
        info = ContinuousTrialLog(
            waveform="sine",
            params={"freq_hz": 0.4, "amplitude_pct": 30.0},
            seed=1234,
            segments=[("track", 10.0, 40.0), ("release", 40.0, 55.0)])
        e.log_trial(self._trial(),
                     TrialResult(label="Great", points=5, rt_ms=200.0),
                     now=0.0, continuous=info)
        row = e.trial_logger.rows[0]
        self.assertEqual(row["waveform"], "sine")
        self.assertEqual(row["waveform_params"],
                          "amplitude_pct=30;freq_hz=0.4")
        self.assertEqual(row["waveform_seed"], "1234")
        self.assertEqual(row["segment_times"],
                          "track:10.000000:40.000000;"
                          "release:40.000000:55.000000")

    def test_threshold_modes_leave_the_cells_empty(self):
        from finger_rehab.game.scoring import TrialResult
        e = self._loggable_engine()
        e.log_trial(self._trial(),
                     TrialResult(label="Great", points=5, rt_ms=200.0),
                     now=0.0)
        row = e.trial_logger.rows[0]
        for col in ("waveform", "waveform_params", "waveform_seed",
                    "segment_times"):
            self.assertFalse(row.get(col, ""),
                              f"{col} should be empty outside the "
                              "continuous modes")


class SegmentMarkerTests(unittest.TestCase):
    def test_markers_bracket_a_scored_segment(self):
        e = _engine()
        e.raw_logger = _RawLoggerStub()
        e.log_segment_start("blind", trial_id=7, lane=2, t_perf=12.5)
        e.log_segment_end("blind", trial_id=7, lane=2, t_perf=27.5)
        events = e.raw_logger.events
        self.assertEqual([ev["event"] for ev in events],
                          ["segment_start", "segment_end"])
        for ev in events:
            self.assertEqual(ev["lane"], 2)
            self.assertEqual(ev["detail"], "trial_id=7;segment=blind")

    def test_no_raw_logger_is_a_no_op(self):
        e = _engine()
        e.raw_logger = None
        e.log_segment_start("blind", trial_id=1, lane=0, t_perf=0.0)
        e.log_segment_end("blind", trial_id=1, lane=0, t_perf=1.0)


class RecordMaxPressTests(unittest.TestCase):
    def test_records_persists_and_logs(self):
        e = _engine()
        e.raw_logger = _RawLoggerStub()
        e.calibration_profiles["right"] = _profile()
        with TemporaryDirectory() as td:
            e.cfg.resolve_path = lambda p: Path(td) / p
            e.record_max_press("right", [210.0, 190.0, 160.0, 130.0])
            prof = e.calibration_profiles["right"]
            self.assertEqual(prof.max_press, [210.0, 190.0, 160.0, 130.0])
            self.assertTrue(prof.max_press_measured_at)
            # Persisted next to the calibration so a restart mid-
            # session does not force a re-probe.
            from finger_rehab.hardware.calibration_profile import (
                CalibrationProfile)
            saved = CalibrationProfile.load(
                Path(td) / "config/calibration/current_right.json")
            self.assertEqual(saved.max_press,
                              [210.0, 190.0, 160.0, 130.0])
        evs = [ev for ev in e.raw_logger.events
               if ev["event"] == "max_press"]
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0]["detail"],
                          "1:210.0;2:190.0;3:160.0;4:130.0")

    def test_bare_profile_is_created_when_none_exists(self):
        e = _engine()
        with TemporaryDirectory() as td:
            e.cfg.resolve_path = lambda p: Path(td) / p
            e.record_max_press("left", [100.0] * 4)
        self.assertIn("left", e.calibration_profiles)
        self.assertTrue(e.calibration_profiles["left"].has_max_press())

    def test_failed_save_does_not_lose_the_session_value(self):
        e = _engine()
        e.cfg.resolve_path = MagicMock(side_effect=OSError("read only"))
        e.record_max_press("right", [200.0] * 4)
        self.assertTrue(
            e.calibration_profiles["right"].has_max_press())


class MetadataStampTests(unittest.TestCase):
    def test_both_hands_max_press_reaches_metadata(self):
        from finger_rehab.data.session import Session
        e = _engine(hand_mode="both")
        e.session = Session()
        right = _profile("right")
        right.set_max_press([210.0] * 4)
        left = _profile("left")
        left.set_max_press([150.0] * 4)
        e.calibration_profiles = {"right": right, "left": left}
        e.calibration_profile = right
        e._stamp_calibration()
        by_hand = e.session.calibration["max_press_by_hand"]
        self.assertEqual(by_hand["right"]["max_press"], [210.0] * 4)
        self.assertEqual(by_hand["left"]["max_press"], [150.0] * 4)

    def test_no_probe_leaves_metadata_unchanged(self):
        from finger_rehab.data.session import Session
        e = _engine()
        e.session = Session()
        e.calibration_profiles = {"right": _profile()}
        e.calibration_profile = None
        e._stamp_calibration()
        self.assertNotIn("max_press_by_hand", e.session.calibration)


if __name__ == "__main__":
    unittest.main()
