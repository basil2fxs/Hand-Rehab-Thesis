"""Force Pilot's offline scoring against runs whose answers are known.

Three faults the real ladder runs of 25 September 2026 exposed, each
pinned with a synthetic run:

- The zero. The notebook re-tared each run from the second before it
  started, which catches a finger already pressing toward the first
  hold. The game logs its own zero now, and an older run rebuilds it
  at the announce card's opening.
- The lag. The cross-correlation summed over a shrinking overlap put
  a cusp at zero lag, so a ramp wave read 0 ms whatever the true lag.
- The press and release split pooled Dunes, whose 12 %/s drop turns a
  normal lag into a release deficit.

The Parkinson's-linked measures (sec_force_pilot_pd) are checked the
same way: a follower with a set gain, lag or decrement must read back
that gain, lag or decrement.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_analysis_logic_gaps import _load_notebook  # noqa: E402

_RA = None
FS = 200.0


def _ra():
    global _RA
    if _RA is None:
        _RA = _load_notebook("force_pilot_pd")
    return _RA


def _level(slug):
    """The notebook's section plan for one ladder level, built from the
    game's own logged params so the two cannot drift."""
    from finger_rehab.game.modes import force_pilot as fp
    wave = next(w for w in fp.LADDER if w.slug == slug)
    p = fp.params_from_level(wave, 1, base_pct=8.0, span_pct=40.0,
                             gain=1.0, max_press_counts=300.0,
                             grace_s=0.6, phases=fp.uncharted_phases(7))
    return _ra().fp_sections_from_params(p)


def _run(slug, force_fn, noise=0.0, seed=1):
    """Score a synthetic run: force_fn(t, target_fn) gives the force."""
    ra = _ra()
    secs = _level(slug)
    t = np.arange(0.0, secs[-1]["end"], 1.0 / FS)
    tgt = ra.fp_target_vec(secs, t)
    pct = force_fn(t, lambda x: ra.fp_target_vec(secs, x))
    if noise:
        pct = pct + np.random.default_rng(seed).normal(0.0, noise, len(t))
    pct = np.maximum(pct, 0.0)
    roles = ra.fp_section_roles(secs, 8.0)
    sc = np.ones(len(t), dtype=bool)
    return ra.fp_pd_measures(t, pct, tgt, sc, secs, roles), secs, roles


def _delayed(lag_s, gain=1.0):
    def f(t, T):
        tt = T(t)
        mid = 0.5 * (tt.max() + tt.min())
        return mid + gain * (T(t - lag_s) - mid)
    return f


class TheZero(unittest.TestCase):
    FOLDER = "/nowhere/Pat_000000_force_pilot"

    def _samples(self):
        # Resting at 100 counts; the previous run ends at 8.2 s, the
        # card opens then, and the run starts at 10.0 s. From 9.3 s the
        # finger presses toward the first hold at +30 counts.
        t = np.arange(0.0, 12.0, 0.005)
        v = np.full(len(t), 100.0)
        v[(t >= 9.3) & (t < 10.0)] = 130.0
        _ra().FP_EVENT_CACHE[self.FOLDER] = np.array([8.2])
        return pd.DataFrame({"t_perf": t, "fsr1": v})

    def test_the_card_zero_is_the_resting_level_not_the_pre_press(self):
        ra = _ra()
        samp = self._samples()
        ref, src = ra.fp_run_tare(samp, "fsr1", 10.0, {}, self.FOLDER, 1.8)
        self.assertEqual(src, "card")
        self.assertAlmostEqual(ref, 100.0, delta=0.5)
        # The window it replaced sits on the pre-press.
        self.assertGreater(ra.trial_tare(samp, "fsr1", 10.0), 120.0)

    def test_a_logged_zero_wins(self):
        ra = _ra()
        ref, src = ra.fp_run_tare(self._samples(), "fsr1", 10.0,
                                  {"ref_counts": 97.5}, self.FOLDER, 1.8)
        self.assertEqual((ref, src), (97.5, "logged"))

    def test_the_card_length_is_the_game_s(self):
        import yaml
        shipped = yaml.safe_load((ROOT / "config" / "default.yaml")
                                 .read_text())["force_pilot"]["announce_s"]
        self.assertEqual(_ra().FP_ANNOUNCE_S, float(shipped))
        self.assertEqual(_ra().fp_announce_s({}), float(shipped))


class TheLag(unittest.TestCase):
    def test_a_ramp_wave_reads_its_true_lag(self):
        ra = _ra()
        secs = _level("tide")
        t = np.arange(0.0, secs[-1]["end"], 1.0 / FS)
        tgt = ra.fp_target_vec(secs, t)
        for lag in (0.05, 0.15, 0.25):
            force = ra.fp_target_vec(secs, t - lag)
            got, r = ra.tracking_lag_ms(force, tgt, fs=FS)
            self.assertAlmostEqual(got, lag * 1000.0, delta=10.0)
            self.assertGreater(r, 0.99)

    def test_force_leading_reads_negative(self):
        ra = _ra()
        secs = _level("swell")
        t = np.arange(0.0, secs[-1]["end"], 1.0 / FS)
        got, _r = ra.tracking_lag_ms(ra.fp_target_vec(secs, t + 0.1),
                                     ra.fp_target_vec(secs, t), fs=FS)
        self.assertAlmostEqual(got, -100.0, delta=10.0)


class TheShapes(unittest.TestCase):
    ROLES = {
        "tide": ["hold", "sym_ramp", "steady_hold", "sym_ramp",
                 "terminal_hold"],
        "hills": ["hold"] + ["sym_ramp"] * 4,
        "dunes": ["hold"] + ["asym_ramp"] * 4 + ["terminal_hold"],
        "heartbeat": ["hold"] + ["pulse", "terminal_hold"] * 4,
        "stairs": ["hold"] + ["steady_hold"] * 5 + ["hold"],
        "storm": ["transition", "osc"],
        "swell": ["hold", "osc"],
    }
    CLASSES = {"slow_breath": "periodic", "tide": "ramp_step",
               "swell": "periodic", "stairs": "ramp_step",
               "hills": "ramp_step", "beach_waves": "periodic",
               "heartbeat": "periodic", "dunes": "ramp_step",
               "chop": "periodic", "open_ocean": "nonperiodic",
               "storm": "nonperiodic", "uncharted": "nonperiodic"}

    def test_each_section_measures_what_its_shape_asks(self):
        ra = _ra()
        for slug, want in self.ROLES.items():
            got = ra.fp_section_roles(_level(slug), 8.0)
            self.assertEqual(got, want, slug)

    def test_lag_classes(self):
        ra = _ra()
        for slug, want in self.CLASSES.items():
            secs = _level(slug)
            roles = ra.fp_section_roles(secs, 8.0)
            self.assertEqual(ra.fp_lag_class(roles, secs, "waves_v1"),
                             want, slug)

    def test_the_vector_target_is_the_scalar_one(self):
        ra = _ra()
        for slug in self.CLASSES:
            secs = _level(slug)
            ts = np.concatenate([np.linspace(-0.5, secs[-1]["end"] + 0.5,
                                             3001),
                                 [s["start"] for s in secs],
                                 [s["end"] for s in secs]])
            np.testing.assert_allclose(ra.fp_target_vec(secs, ts),
                                       ra.fp_target_array(secs, ts),
                                       atol=1e-12, err_msg=slug)


class PressAndRelease(unittest.TestCase):
    def test_a_lagged_follower_releases_as_well_as_it_presses(self):
        m, _s, _r = _run("hills", _delayed(0.15))
        self.assertAlmostEqual(m["release_ratio"], 1.0, delta=0.1)

    def test_dunes_is_kept_out_and_shows_the_lag_as_a_rate_effect(self):
        m, _s, _r = _run("dunes", _delayed(0.15))
        self.assertTrue(np.isnan(m["press_mae"]))
        self.assertTrue(np.isnan(m["release_mae"]))
        self.assertGreater(m["asym_fall_mae"], 2.0 * m["asym_rise_mae"])


class SineFit(unittest.TestCase):
    def test_gain_and_lag_come_back_on_one_sine(self):
        m, _s, _r = _run("swell", _delayed(0.15, gain=0.8))
        self.assertAlmostEqual(m["gain"], 0.8, delta=0.02)
        self.assertAlmostEqual(m["fit_lag_ms"], 150.0, delta=10.0)

    def test_every_multisine_component_comes_back(self):
        m, _s, _r = _run("storm", _delayed(0.15, gain=0.8))
        comps = m["sine_fit"]
        self.assertEqual(len(comps), 8)
        for c in comps:
            self.assertAlmostEqual(c["gain"], 0.8, delta=0.05)
            self.assertAlmostEqual(c["lag_ms"], 150.0, delta=25.0)


class Heartbeat(unittest.TestCase):
    def test_a_perfect_follower_reads_one_and_no_delay(self):
        m, _s, _r = _run("heartbeat", lambda t, T: T(t), noise=0.3)
        self.assertAlmostEqual(m["pulse_rise_gain"], 1.0, delta=0.1)
        self.assertAlmostEqual(m["pulse_fall_gain"], 1.0, delta=0.1)
        self.assertAlmostEqual(m["pulse_peak_gain"], 1.0, delta=0.05)
        self.assertAlmostEqual(m["pulse_relax_lag_ms"], 0.0, delta=25.0)
        self.assertAlmostEqual(m["pulse_decrement"], 0.0, delta=0.01)
        self.assertAlmostEqual(m["term_twr5"], 1.0, delta=0.05)

    def test_shrinking_beats_read_as_a_decrement(self):
        ra = _ra()
        secs = _level("heartbeat")
        beats = [s for s in secs if s["kind"] == "osc"]

        def shrink(t, T):
            out = T(t)
            for k, sec in enumerate(beats):
                m = (t >= sec["start"]) & (t <= sec["end"])
                lo = sec["a"] - sec["amps"][0]
                out[m] = lo + (1.0 - 0.1 * k) * (out[m] - lo)
            return out
        m, _s, _r = _run("heartbeat", shrink)
        self.assertAlmostEqual(m["pulse_decrement"], -0.1, delta=0.02)

    def test_a_slow_release_reads_below_one(self):
        # Relaxation takes twice as long as the beat asks for.
        ra = _ra()
        secs = _level("heartbeat")

        def slow(t, T):
            out = T(t)
            for sec in (s for s in secs if s["kind"] == "osc"):
                top = sec["start"] + sec["dur"] / 2.0
                m = (t >= top) & (t <= sec["end"] + sec["dur"] / 2.0)
                out[m] = T(top + (t[m] - top) / 2.0)
            return out
        m, _s, _r = _run("heartbeat", slow)
        self.assertLess(m["pulse_fall_gain"], 0.6)
        self.assertGreater(m["pulse_relax_lag_ms"], 200.0)


class Steadiness(unittest.TestCase):
    def test_heartbeat_rests_are_not_steadiness(self):
        m, _s, _r = _run("heartbeat", lambda t, T: T(t), noise=0.5)
        self.assertTrue(np.isnan(m["cv_hold"]))

    def test_the_slack_hold_reads_its_noise(self):
        m, _s, _r = _run("tide", lambda t, T: T(t), noise=0.5, seed=3)
        self.assertAlmostEqual(m["sd_hold"], 0.5, delta=0.1)
        self.assertAlmostEqual(m["cv_hold"], 0.5 / 28.0, delta=0.005)


class Segmentation(unittest.TestCase):
    def test_a_smooth_ramp_has_no_pauses(self):
        m, _s, _r = _run("tide", lambda t, T: T(t))
        self.assertEqual(m["ramp_up_steps"], 0.0)
        self.assertEqual(m["release_steps"], 0.0)

    def test_plateaus_inserted_in_a_climb_are_counted(self):
        ra = _ra()
        secs = _level("tide")
        flood = next(s for s in secs if s["name"] == "flood")

        def stepped(t, T):
            # The climb stops twice for 0.4 s, then catches up.
            tt = t.copy()
            for a in (flood["start"] + 1.0, flood["start"] + 2.5):
                m = (t >= a) & (t < a + 0.4)
                tt[m] = a
            return T(tt)
        m, _s, _r = _run("tide", stepped)
        self.assertEqual(m["ramp_up_steps"], 2.0)
        self.assertEqual(m["release_steps"], 0.0)


class Regularity(unittest.TestCase):
    def test_a_sine_is_more_regular_than_noise(self):
        ra = _ra()
        t = np.arange(0, 14, 0.01)
        sine = np.sin(2 * np.pi * 0.5 * t)
        noise = np.random.default_rng(0).normal(size=len(t))
        self.assertLess(ra.fp_sample_entropy(sine),
                        ra.fp_sample_entropy(noise))


class IdleRuns(unittest.TestCase):
    def test_idle_and_demo_runs_are_left_out(self):
        ra = _ra()
        runs = pd.DataFrame({"demo": [False, True, False],
                             "idle": [False, False, True],
                             "level": [1, 2, 3]})
        kept = ra.fp_real_runs(runs, say=False)
        self.assertEqual(kept["level"].tolist(), [1])


if __name__ == "__main__":
    unittest.main()
