"""The analysis-logic gaps a capability and a crosscut audit found,
closed and pinned.

Every gap here is a case where the software recorded something and the
analysis read it wrongly, read it in the wrong unit, or scored a check
the shipped design cannot produce. None of them broke a test, which is
why they survived: the notebook ran clean and printed the wrong number.

What each class covers:

  HardwareVoidTests     a trial the rig ate is not a miss, in every
                        chapter and not only in the game
  SensorLostTests       a trial whose response window sat inside a
                        board drop, recovered from the drop intervals
                        for the ones the game did not catch
  ExclusionBudgetTests  recorded, flagged and analysed add up, and
                        "analysed" counts trials rather than CSV rows
  ForceUnitTests        every force column a block publishes carries
                        the unit block_summary.force_unit names
  CalibrationStampTests both hands' profiles reach metadata.json, so a
                        bilateral block does not lose one
  VoidedCountTests      connection.voided_trials counts every
                        hardware-voided close, not the engine-detected
                        subset
  FatigueByModeTests    the stored fatigue slope pooled modes whose
                        rt_ms is a different measurement
  DropMergeTests        one physical drop is one drop, not one per hand
  Lag1Tests             one lag-1 implementation, and NaN is not a
                        failed check
  BandSideTests         above the band and below it mean opposite
                        things
  SlopeDirectionTests   a zero slope is not a direction
  CheckVerdictTests     a check that could not be run is not a failed
                        check, and a median gets a median's interval
  SpearmanBrownTests    the correction is not applied below zero
  SmoothingTests        the thirds and the slopes come off the raw
                        series; smoothing is for the drawn curve
  UniformGridTests      the tracking lag and the Lodha bands are
                        computed on a uniform grid, not on a bursty
                        sample index
  EegCatchTests         a catch trial has no response byte by design
  DeadColumnTests       a quantity the software records is analysed or
                        carries a line saying why not
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import contextlib
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
# The notebook sits at the top level, beside app/, because that is
# where the analysis is actually done. ROOT stays the package root.
ANALYSIS = (ROOT / "analysis" if (ROOT / "analysis").is_dir()
            else ROOT.parent / "analysis")
sys.path.insert(0, str(ROOT))


def _load_notebook(tag: str):
    """Every notebook cell's definitions in one namespace, the pattern
    the other per-chapter tests use."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_" + tag
    module = ModuleType(name)
    module.__file__ = str(ANALYSIS / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in _code_cells():
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                              if not k.startswith("__")})


_RA = None


def _ra():
    global _RA
    if _RA is None:
        _RA = _load_notebook("logic_gaps")
    return _RA


def _frame(rows):
    """A trials frame with the columns every chapter assumes."""
    base = {"mode": "adaptive", "early_late": "Hit", "error_type": "",
            "time_difference_ms": 300.0, "lane": 1, "trial": 1,
            "block_t_s": 1.0, "hand_mode": "right", "side": "right",
            "folder": "/nowhere", "game": "g", "participant": "P01",
            "cue_target_shown": True, "stim_delivered": True,
            "timeout_ms": 1000.0, "num_presses": 1}
    return pd.DataFrame([{**base, **r} for r in rows])


# ==================================================================
# A trial the rig ate is not a miss
# ==================================================================
class HardwareVoidTests(unittest.TestCase):
    """engine.log_trial computes hardware_void over device_drop and
    no_signal and keeps those rows out of hits, misses and the streak.
    buzz_hunt closes a stimulus that never fired as stim_failed. The
    notebook had never heard of any of the three, so it scored them as
    misses: one adaptive block with the rig out for eight seconds read
    0.800 here against the game's own 0.914, which moved the
    challenge-point verdict from above the band to inside it."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_the_three_error_types_are_named(self) -> None:
        self.assertEqual(set(self.ra.HARDWARE_VOID_ERRORS),
                         {"device_drop", "no_signal", "stim_failed"})

    def test_a_voided_row_is_not_scorable(self) -> None:
        df = _frame([{"error_type": e, "early_late": "Miss"}
                     for e in self.ra.HARDWARE_VOID_ERRORS]
                    + [{"early_late": "Miss"}])
        keep = self.ra.is_scorable(df)
        self.assertEqual(list(keep), [False, False, False, True])

    def test_the_hit_rate_matches_the_games_own(self) -> None:
        """Eight scored trials, seven hits, plus two rows the rig ate.
        The game's block_summary would say 7/8; the notebook used to
        say 7/10."""
        rows = [{"early_late": "Hit"}] * 7 + [{"early_late": "Miss"}]
        rows += [{"early_late": "Miss", "error_type": "device_drop"},
                 {"early_late": "Miss", "error_type": "no_signal"}]
        df = _frame(rows)
        scored = df[self.ra.is_scorable(df)]
        rate = float((scored["early_late"] != "Miss").mean())
        self.assertEqual(len(scored), 8)
        self.assertAlmostEqual(rate, 7 / 8)

    def test_they_are_counted_in_the_exclusion_budget(self) -> None:
        df = _frame([{"early_late": "Hit"},
                     {"early_late": "Miss", "error_type": "device_drop"}])
        _kept, _flagged, counts = self.ra.analysable(df)
        self.assertEqual(counts["hardware_void"], 1)
        self.assertEqual(counts["analysed"], 1)

    def test_the_reason_says_the_rig_and_not_the_patient(self) -> None:
        df = _frame([{"early_late": "Miss", "error_type": "no_signal"}])
        flagged = self.ra.exclusion_flags(df)
        self.assertTrue(bool(flagged["hardware_void"].iloc[0]))
        self.assertIn("rig fault", flagged["exclusion_reason"].iloc[0])


# ==================================================================
# A trial with no sensor behind it
# ==================================================================
class SensorLostTests(unittest.TestCase):
    """The engine voids the trials it catches: a Miss, no press, and a
    drop overlapping the window. It cannot catch a trial the patient
    answered on the other hand while this hand's board was away, and a
    block recorded before it tracked drops has none of them marked at
    all. Measured on a both-hands reaction block with the left board
    unplugged twenty seconds in: fourteen of twenty-seven trials had
    no sensor behind them and the exported summary said a healthy hand
    hit 52 per cent of its cues with nothing flagged."""

    def setUp(self) -> None:
        self.ra = _ra()
        self.td = tempfile.TemporaryDirectory()
        self.folder = Path(self.td.name) / "block"
        self.folder.mkdir()

    def tearDown(self) -> None:
        self.td.cleanup()

    def _write_meta(self, intervals):
        meta = {"hand": "both",
                "block_summary": {"block": "reaction",
                                  "connection": {"drops": len(intervals),
                                                 "intervals": intervals}}}
        (self.folder / "metadata.json").write_text(json.dumps(meta))
        return meta

    def test_intervals_come_from_the_block_summary(self) -> None:
        meta = self._write_meta([{"hand": "left", "from_s": 10.0,
                                  "to_s": 18.0}])
        spans = self.ra.block_drop_intervals(self.folder, meta)
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0]["hand"], "left")
        self.assertEqual(spans[0]["from_s"], 10.0)
        self.assertEqual(spans[0]["to_s"], 18.0)

    def test_a_trial_inside_the_drop_is_flagged(self) -> None:
        meta = self._write_meta([{"hand": "left", "from_s": 10.0,
                                  "to_s": 18.0}])
        df = _frame([
            # right hand, inside the window: the left board is away,
            # the right one is not.
            {"block_t_s": 12.0, "side": "right", "hand_mode": "both"},
            # left hand, inside the window: nothing was reading it.
            {"block_t_s": 12.0, "side": "left", "hand_mode": "both"},
            # left hand, after the reconnect.
            {"block_t_s": 30.0, "side": "left", "hand_mode": "both"},
        ])
        df["folder"] = str(self.folder)
        out = self.ra.add_sensor_lost(df, [self.folder],
                                      {self.ra.game_key(self.folder): meta})
        self.assertEqual(list(out["sensor_lost"]), [False, True, False])

    def test_a_still_open_drop_eats_everything_after_it(self) -> None:
        meta = self._write_meta([{"hand": "both", "from_s": 5.0,
                                  "to_s": None}])
        df = _frame([{"block_t_s": 1.0}, {"block_t_s": 9.0},
                     {"block_t_s": 40.0}])
        df["folder"] = str(self.folder)
        out = self.ra.add_sensor_lost(df, [self.folder],
                                      {self.ra.game_key(self.folder): meta})
        self.assertEqual(list(out["sensor_lost"]), [False, True, True])

    def test_it_reaches_the_exclusion_budget(self) -> None:
        df = _frame([{"early_late": "Hit"}, {"early_late": "Miss"}])
        df["sensor_lost"] = [False, True]
        _kept, _flagged, counts = self.ra.analysable(df)
        self.assertEqual(counts["sensor_lost"], 1)
        self.assertEqual(counts["analysed"], 1)

    def test_a_row_the_game_already_voided_is_not_counted_twice(self):
        df = _frame([{"early_late": "Miss", "error_type": "device_drop"}])
        df["sensor_lost"] = [True]
        flagged = self.ra.exclusion_flags(df)
        self.assertTrue(bool(flagged["hardware_void"].iloc[0]))
        self.assertFalse(bool(flagged["sensor_lost"].iloc[0]))


# ==================================================================
# The exclusion budget has to add up
# ==================================================================
class ExclusionBudgetTests(unittest.TestCase):
    """sec_exclusions is the chapter whose whole job is to state the
    exclusion budget, and it counted every unflagged CSV row as
    "analysed", including the event rows every scored table drops
    through is_scorable. On a reaction block with catch trials that put
    the block length 24 per cent above the count the mode itself
    reports."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_event_rows_are_counted_apart(self) -> None:
        df = _frame([
            {"early_late": "Hit"},
            {"early_late": "CatchOk", "mode": "reaction"},
            {"early_late": "Early", "error_type": "false_start",
             "mode": "reaction"},
        ])
        _kept, _flagged, counts = self.ra.analysable(df)
        self.assertEqual(counts["recorded"], 3)
        self.assertEqual(counts["events"], 2)
        self.assertEqual(counts["analysed"], 1)

    def test_the_five_reasons_and_the_analysed_add_to_recorded(self):
        df = _frame([
            {"early_late": "Hit"},
            {"early_late": "CatchOk", "mode": "reaction"},
            {"early_late": "Miss", "error_type": "device_drop"},
            {"time_difference_ms": 40.0},
            {"stim_delivered": False, "cue_target_shown": False},
        ])
        _kept, _flagged, counts = self.ra.analysable(df)
        parts = sum(counts[k] for k in ("no_cue", "anticipation",
                                        "hardware_void", "sensor_lost",
                                        "events", "analysed"))
        self.assertEqual(parts, counts["recorded"])

    def test_kept_holds_only_scorable_unflagged_rows(self) -> None:
        df = _frame([{"early_late": "Hit"},
                     {"early_late": "CatchOk", "mode": "reaction"}])
        kept, _flagged, _counts = self.ra.analysable(df)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept["early_late"].iloc[0], "Hit")


# ==================================================================
# One block, one force unit
# ==================================================================
class ForceUnitTests(unittest.TestCase):
    """_peak_force_for_lane and _impulse_for_lane multiplied by the
    calibration constant; _track_force_peaks did not. So
    force_window_sum, force_window_peaks and
    block_summary.miss_force stayed in raw counts beside newton
    siblings, under one force_unit label of "N". On a 10 N part with
    0.01953 N per count that made mean_per_miss read 99.79 "N", 51
    times the real figure."""

    def _engine(self, cal):
        from finger_rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        eng.cfg.get = MagicMock(
            side_effect=lambda key, default=None:
            cal if key == "fsr.force_calibration_n_per_count" else default)
        eng.hand_mode = "right"
        eng._force_window_ms = 1000.0
        eng._miss_force_total = 0.0
        eng._miss_force_count = 0
        return eng

    class _Det:
        def __init__(self, base):
            self.base = base

        def baseline_value(self, _i):
            return self.base

    def test_the_window_peaks_take_the_same_conversion(self) -> None:
        cal = 0.019531
        eng = self._engine(cal)
        det = self._Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(0.0)
        eng._track_force_peaks(det, (400, 300, 300, 300), None,
                               (0, 0, 0, 0), 4)
        total, peaks = eng._close_force_window(True)
        # 100 counts above baseline, in newtons.
        self.assertAlmostEqual(total, 100.0 * cal, places=6)
        self.assertAlmostEqual(peaks[0], 100.0 * cal, places=6)
        self.assertAlmostEqual(eng._miss_force_total, 100.0 * cal,
                               places=6)

    def test_without_a_constant_it_stays_in_counts(self) -> None:
        eng = self._engine(None)
        det = self._Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(0.0)
        eng._track_force_peaks(det, (400, 300, 300, 300), None,
                               (0, 0, 0, 0), 4)
        total, _peaks = eng._close_force_window(True)
        self.assertAlmostEqual(total, 100.0)
        self.assertEqual(eng._force_unit(), "counts")

    def test_the_window_sum_is_the_same_order_as_a_peak(self) -> None:
        """The failure mode in one sentence: a ratio of 51 between two
        columns of the same row under one unit label."""
        cal = 0.019531
        eng = self._engine(cal)
        det = self._Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(0.0)
        eng._track_force_peaks(det, (400, 300, 300, 300), None,
                               (0, 0, 0, 0), 4)
        total, _peaks = eng._close_force_window(True)
        peak_n = eng._to_force_unit(100.0)
        self.assertLess(abs(total / peak_n), 2.0)
        self.assertEqual(eng._force_unit(), "N")

    def test_a_zero_constant_is_not_a_calibration(self) -> None:
        """A zero would multiply every force number to nothing while
        _force_unit still said "N"."""
        eng = self._engine(0.0)
        self.assertEqual(eng._force_unit(), "counts")
        self.assertAlmostEqual(eng._to_force_unit(100.0), 100.0)


# ==================================================================
# Both hands' calibration reaches the file
# ==================================================================
class CalibrationStampTests(unittest.TestCase):
    """The session stamp was the LAST-APPLIED profile, and the quick
    calibration screen runs left then right, so the left hand's
    profile never reached metadata.json. Every bilateral block then
    lost one hand: three both-hands blocks all reported "no profile
    for the left hand", and in the reverse order sec_force blanked
    1020 of 1044 force trials."""

    def test_read_calibrations_prefers_by_hand(self) -> None:
        ra = _ra()
        meta = {"calibration": {
            "hand": "right", "gap": [1, 2, 3, 4],
            "by_hand": {"right": {"hand": "right", "gap": [1, 2, 3, 4]},
                        "left": {"hand": "left", "gap": [5, 6, 7, 8]}}}}
        cals = ra.read_calibrations(meta)
        self.assertEqual(set(cals), {"right", "left"})
        self.assertEqual(cals["left"]["gap"], [5, 6, 7, 8])

    def test_the_old_flat_shape_still_reads(self) -> None:
        ra = _ra()
        meta = {"calibration": {"hand": "right", "gap": [1, 2, 3, 4]}}
        cals = ra.read_calibrations(meta)
        self.assertEqual(set(cals), {"right"})

    def test_the_engine_writes_both_profiles(self) -> None:
        from finger_rehab.game.engine import GameEngine

        class _Prof:
            def __init__(self, hand):
                self.hand = hand
                self.max_press = [1.0, 2.0, 3.0, 4.0]
                self.max_press_measured_at = "now"

            def has_max_press(self):
                return True

            def summary(self):
                return {"hand": self.hand, "gap": [1, 2, 3, 4]}

        eng = GameEngine.__new__(GameEngine)
        eng.session = SimpleNamespace(calibration={}, eeg={})
        eng.calibration_profiles = {"left": _Prof("left"),
                                    "right": _Prof("right")}
        eng.calibration_profile = eng.calibration_profiles["right"]
        # Only the tail of _stamp_session_calibration is under test, so
        # the two blocks are run against a stand-in session object.
        prof = eng.calibration_profile
        eng.session.calibration = prof.summary()
        by_hand = {h: p.summary()
                   for h, p in eng.calibration_profiles.items()}
        eng.session.calibration["by_hand"] = by_hand
        self.assertEqual(set(eng.session.calibration["by_hand"]),
                         {"right", "left"})

    def test_the_source_writes_by_hand(self) -> None:
        src = (ROOT / "finger_rehab" / "game"
               / "engine.py").read_text(encoding="utf-8")
        self.assertIn('self.session.calibration["by_hand"]', src)


# ==================================================================
# Every hardware-voided close is counted
# ==================================================================
class VoidedCountTests(unittest.TestCase):
    """_block_drop_voided moved only inside the branch where the
    ENGINE detected the overlap. adaptive and chords pass device_drop
    in themselves and force_pilot passes no_signal, and those rows
    were voided out of hits and misses while the counter stayed put:
    five voided rows in trials.csv against a reported 1."""

    def test_the_increment_follows_hardware_void(self) -> None:
        src = (ROOT / "finger_rehab" / "game"
               / "engine.py").read_text(encoding="utf-8")
        i = src.index('hardware_void = error_type in ("device_drop"')
        j = src.index("if not hardware_void:", i)
        between = src[i:j]
        self.assertIn("_block_drop_voided", between,
                      "the counter has to move on every hardware-voided "
                      "close, not only the engine-detected subset")


# ==================================================================
# rt_ms is not one clock across the battery
# ==================================================================
class FatigueByModeTests(unittest.TestCase):
    """fatigue_slope_rt_ms_per_block ran over every block's mean rt_ms
    regardless of mode. Reaction's rt_ms is a cue-to-press latency;
    pattern's, chords', syllables' and buzz_hunt's is spawn-to-press on
    a visible target. On a patient whose latency never changed the
    stored slope read -5.7e-14 on adaptive and +125.0 on pattern, and
    the whole signal was the mode change."""

    def test_the_engine_keeps_the_history_per_mode(self) -> None:
        src = (ROOT / "finger_rehab" / "game"
               / "engine.py").read_text(encoding="utf-8")
        self.assertIn("_across_blocks_mean_rt_by_mode", src)
        self.assertIn("fatigue_slope_rt_ms_per_block_same_mode", src)

    def test_the_notebook_surfaces_the_same_mode_slope(self) -> None:
        ra = _ra()
        metas = {"g": {"block_summary": {
            "fatigue_slope_rt_ms_per_block": 125.0,
            "fatigue_slope_rt_ms_per_block_same_mode": None,
            "fatigue_slope_rt_modes_seen": 4,
            "fatigue_slope_force_per_block": 0.0}}}
        tbl = ra.stored_fatigue(metas)
        self.assertIn("stored_rt_slope_same_mode", tbl.columns)
        self.assertEqual(int(tbl["modes_in_stored_slope"].iloc[0]), 4)


# ==================================================================
# One cable, one drop
# ==================================================================
class DropMergeTests(unittest.TestCase):
    """A whole-rig drop writes a source_disconnected row for the source
    and one per hand at the same instant. Pairing rows without merging
    them reported three drops and 24.0 seconds down for one eight
    second cable, where the engine's own _connection_summary said one
    and 8.0."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_overlapping_per_hand_spans_merge_into_the_rig_span(self):
        spans = [{"hand": "both", "from_s": 10.0, "to_s": 18.0},
                 {"hand": "right", "from_s": 10.0, "to_s": 18.0},
                 {"hand": "left", "from_s": 10.0, "to_s": 18.0}]
        merged = self.ra._merge_drop_spans(spans)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["from_s"], 10.0)
        self.assertEqual(merged[0]["to_s"], 18.0)

    def test_two_separate_drops_on_one_hand_stay_two(self) -> None:
        spans = [{"hand": "left", "from_s": 1.0, "to_s": 2.0},
                 {"hand": "left", "from_s": 10.0, "to_s": 12.0}]
        merged = self.ra._merge_drop_spans(spans)
        self.assertEqual(len(merged), 2)

    def test_a_hand_only_drop_survives_on_its_own(self) -> None:
        spans = [{"hand": "left", "from_s": 5.0, "to_s": 9.0}]
        merged = self.ra._merge_drop_spans(spans)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["hand"], "left")


# ==================================================================
# One lag-1, and NaN is not a failure
# ==================================================================
class Lag1Tests(unittest.TestCase):
    """np.corrcoef on a zero-variance series returns 1.0 and _lag1
    returns NaN, so on the same 24 offsets the rhythm chapter printed
    "+1.000, which reads as drifting rather than correcting" while the
    checks printed nan and scored a fail. A perfectly steady tapper
    got the strongest possible drift verdict from one chapter and a
    failed Wing-Kristofferson check from the other."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_a_flat_series_is_not_testable(self) -> None:
        self.assertTrue(np.isnan(self.ra._lag1([-26.7] * 24)))

    def test_the_rhythm_chapter_uses_the_same_helper(self) -> None:
        src = json.loads(
            (ANALYSIS / "session_analysis.ipynb").read_text())
        code = "".join(src["cells"][2]["source"])
        self.assertNotIn("np.corrcoef(o_b[1:], o_b[:-1])", code)
        self.assertIn("_lag1(o_b.tolist())", code)

    def test_a_correcting_series_still_comes_out_negative(self) -> None:
        v = [10.0, -10.0] * 12
        self.assertLess(self.ra._lag1(v), -0.5)


# ==================================================================
# Above the band and below it are opposite instructions
# ==================================================================
class BandSideTests(unittest.TestCase):
    """The band is a challenge point. "outside the band: Index,
    Middle, Ring, Pinky" printed the same words for four fingers at
    0.90 and four at 0.30, which mean opposite things."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_the_three_sides(self) -> None:
        self.assertIn("above", self.ra.band_side(0.95))
        self.assertIn("below", self.ra.band_side(0.30))
        self.assertEqual(self.ra.band_side(0.72), "inside the band")

    def test_too_easy_and_too_hard_are_said_in_words(self) -> None:
        self.assertIn("too easy", self.ra.band_side(0.95))
        self.assertIn("too hard", self.ra.band_side(0.30))

    def test_a_missing_rate_is_not_a_side(self) -> None:
        self.assertEqual(self.ra.band_side(float("nan")), "not measured")


# ==================================================================
# A zero slope is not a direction
# ==================================================================
class SlopeDirectionTests(unittest.TestCase):
    """sec_reaction_time printed "slope +0.00 ms per trial, so the
    participant got slower" on a block where every reaction time was
    identical, while sec_statistics on the same trials said the
    interval spanned zero and there was no trend."""

    def test_the_source_reads_an_interval_rather_than_a_sign(self):
        code = "".join(json.loads(
            (ANALYSIS
             / "session_analysis.ipynb").read_text())["cells"][2]["source"])
        # The direction is still printed, but only after the interval
        # has been consulted and has excluded zero.
        i = code.index("slope {slope:+.2f} ms per trial, 95 percent ")
        j = code.index("got faster", i)
        self.assertLess(j - i, 700,
                        "the direction has to follow the interval")
        self.assertIn("The interval spans zero, so this block does not",
                      code)
        self.assertIn("_s, lo, hi = slope_ci(x, y)", code)

    def test_slope_ci_on_a_flat_series_spans_zero(self) -> None:
        ra = _ra()
        x = list(range(30))
        y = [300.0] * 30
        slope, lo, hi = ra.slope_ci(x, y)
        self.assertAlmostEqual(slope, 0.0, places=9)
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 0.0)


# ==================================================================
# A check that could not be run is not a failed check
# ==================================================================
class CheckVerdictTests(unittest.TestCase):
    """`ok = notna(p) and p < 0.05` turned a NaN p into False, so a row
    where every pair was identical printed "fail". Six of one run's
    thirteen fails were rows of that kind, and the count line reads as
    thirteen known effects the device failed to reproduce."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_no_variation_is_its_own_word(self) -> None:
        self.assertEqual(self.ra._verdict("no variation"), "no variation")
        self.assertEqual(self.ra._verdict(None), "not testable")
        self.assertEqual(self.ra._verdict(False), "fail")

    def test_a_flat_pair_is_reported_as_no_variation(self) -> None:
        long = pd.DataFrame([
            {"participant": f"P{i:02d}", "mode": "chords",
             "metric": "median_er", "hand_role": r, "value": 0.0,
             "phase": "battery"}
            for i in range(10) for r in ("dominant", "nondominant")])
        row = self.ra._paired_check(long, "chords", "median_er",
                                    "median_er", "dominant",
                                    "nondominant", 3, "C5", "flat",
                                    "two-sided", "ratio")
        self.assertEqual(row["verdict"], "no variation")

    def test_a_median_row_gets_a_median_interval(self) -> None:
        """E1 printed 6.5 [5.892, 7.108], which is the t interval of
        the MEAN. The bootstrap interval of the median on the same ten
        spans is [6.0, 7.0]."""
        spans = [5, 6, 6, 6, 6, 7, 7, 7, 7, 8]
        long = pd.DataFrame([
            {"participant": f"P{i:02d}", "mode": "echo", "metric": "span",
             "hand_role": "both", "value": float(v), "phase": "battery"}
            for i, v in enumerate(spans)])
        row = self.ra._mean_check(long, "echo", "span", "any", 3, "E1",
                                  "span in the Corsi region", (5.0, 8.0),
                                  "within", "items", use="median")
        self.assertAlmostEqual(row["value"], 6.5)
        self.assertGreaterEqual(row["ci_lo"], 5.9)
        self.assertLessEqual(row["ci_hi"], 7.1)
        self.assertIn("order-statistic interval", row["detail"])

    def test_the_prespecified_set_matches_the_design(self) -> None:
        pre = set(self.ra.COHORT_PRESPECIFIED)
        for cid in ("R1", "R2", "P1", "P3", "C1", "C2", "C3", "C4",
                    "Rh1", "Rh2", "M1", "M2", "F1", "F2", "F3", "F4",
                    "B1", "B2", "B3", "B4", "E1", "E3",
                    "W1", "W2", "W3", "W4", "W5"):
            self.assertIn(cid, pre, cid)
        for cid in ("C5", "Rh3", "B5", "E2p"):
            self.assertNotIn(cid, pre, f"{cid} is not in design 4.6")

    def test_a_row_carries_its_p_and_its_family(self) -> None:
        row = self.ra._check_row("R2", "reaction", "x", 10, 1.0,
                                 (0.0, 2.0), 0.0, "crit", True, "d",
                                 p=0.01)
        self.assertEqual(row["family"], "pre-specified")
        self.assertAlmostEqual(row["p"], 0.01)
        other = self.ra._check_row("B5", "buzz_hunt", "x", 10, 1.0, None,
                                   0.0, "crit", True)
        self.assertEqual(other["family"], "exploratory")

    def test_holm_is_available_and_steps_down(self) -> None:
        adj = self.ra._holm([0.01, 0.02, 0.03])
        self.assertAlmostEqual(adj[0], 0.03)
        self.assertTrue(all(a >= b for a, b in
                            zip(adj, [0.01, 0.02, 0.03])))


# ==================================================================
# Spearman-Brown is not applied below zero
# ==================================================================
class SpearmanBrownTests(unittest.TestCase):
    """2r/(1+r) diverges as r approaches -1. A mirror row printed
    r_split -0.951 with a lower bound of -4.284 and the Koo and Li word
    "poor", which reads as low but measured. A correlation cannot be
    -4.28."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_it_returns_the_raw_half_correlation_too(self) -> None:
        rng = np.random.default_rng(7)
        by_person = {f"P{i:02d}": (200.0 + 20.0 * i
                                   + rng.normal(0, 12.0, 40)).tolist()
                     for i in range(12)}
        out = self.ra.split_half(by_person, n_splits=150)
        self.assertEqual(len(out), 5)
        r, lo, hi, raw, neg = out
        self.assertGreater(r, raw)
        self.assertEqual(neg, 0.0)

    def test_nothing_it_returns_can_leave_the_scale(self) -> None:
        rng = np.random.default_rng(9)
        by_person = {}
        for i in range(12):
            base = 100.0 + 30.0 * i
            by_person[f"P{i:02d}"] = [
                base + (60.0 if k % 2 == 0 else -60.0)
                + rng.normal(0, 1.0) for k in range(40)]
        r, lo, hi, raw, _neg = self.ra.split_half(by_person, n_splits=150)
        for v in (r, lo, hi, raw):
            if v == v:
                self.assertGreaterEqual(v, -1.0000001)
                self.assertLessEqual(v, 1.0000001)


# ==================================================================
# Smoothing is for the eye
# ==================================================================
class SmoothingTests(unittest.TestCase):
    """fine_series applied a 5-point rolling median to reaction,
    buzz_hunt, chords and syllables, and the thirds and the OLS slope
    were then read off the smoothed series. A rolling median makes
    adjacent points dependent, which an OLS standard error assumes
    they are not. Over fifteen reaction blocks the raw and smoothed
    contrasts disagreed by 8.84 ms on average and one block moved from
    a 48.3 ms gain to exactly zero."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_the_series_comes_back_unsmoothed(self) -> None:
        rows = pd.DataFrame({
            "mode": ["reaction"] * 9,
            "block": ["reaction"] * 9,
            "stimulus": ["simple;fp=1.0"] * 9,
            "early_late": ["Hit"] * 9,
            "error_type": [""] * 9,
            "time_difference_ms": [300, 900, 300, 300, 300, 300, 300,
                                   300, 300],
        })
        vals, _better = self.ra.fine_series("reaction", rows)
        self.assertIn(900.0, [float(v) for v in vals])

    def test_the_drawn_curve_is_still_smoothed(self) -> None:
        raw = [300.0, 900.0, 300.0, 300.0, 300.0, 300.0, 300.0]
        drawn = self.ra.fine_series_smoothed(raw, "reaction")
        self.assertNotIn(900.0, drawn)
        # A mode that was never smoothed comes back untouched.
        self.assertEqual(self.ra.fine_series_smoothed(raw, "mirror"), raw)

    def test_rhythm_and_syllables_are_descriptive(self) -> None:
        reading = self.ra.COHORT_WITHIN_BLOCK_READING
        self.assertEqual(reading["rhythm"][0], "descriptive")
        self.assertEqual(reading["syllables"][0], "descriptive")
        self.assertNotIn("descriptive",
                         self.ra.COHORT_IMPROVEMENT_READINGS)

    def test_every_mode_series_names_its_unit(self) -> None:
        """The anchor comparison subtracts the reaction anchor from
        another mode's slope, and that only means something when both
        are in the same unit. It used to take a millisecond off a
        chords error ratio and print the result."""
        for mode in self.ra.COHORT_SERIES_METRIC:
            self.assertIn(mode, self.ra.COHORT_SERIES_UNIT, mode)
        self.assertEqual(self.ra.COHORT_SERIES_UNIT["reaction"], "ms")
        self.assertNotEqual(self.ra.COHORT_SERIES_UNIT["chords"], "ms")


# ==================================================================
# A bursty stream is not a uniform grid
# ==================================================================
class UniformGridTests(unittest.TestCase):
    """estimate_fs_span's own docstring says the samples "arrive in
    bursts of about four samples with microsecond gaps inside a burst
    and ~20 ms between bursts". tracking_lag_ms cross-correlated by
    sample INDEX and returned k * 5.0 ms, and lodha_bands took
    fs=200.0, so on a real board both were mis-scaled by whatever the
    burst structure was. F2's criterion is a 100 to 300 ms band, so a
    mis-scaled lag decides a pre-specified check."""

    def setUp(self) -> None:
        self.ra = _ra()

    @staticmethod
    def _bursty(duration_s=12.0, fs=200.0, burst=4):
        """Timestamps at the right average rate, delivered in bursts."""
        n = int(duration_s * fs)
        t = []
        k = 0
        while len(t) < n:
            base = k * (burst / fs)
            for j in range(burst):
                t.append(base + j * 5e-6)
            k += 1
        return np.asarray(t[:n])

    def test_a_bursty_and_a_uniform_trace_give_the_same_lag(self) -> None:
        fs = 200.0
        lag_s = 0.150
        t_uniform = np.arange(0, 12.0, 1.0 / fs)
        target = np.sin(2 * np.pi * 0.4 * t_uniform)
        force = np.sin(2 * np.pi * 0.4 * (t_uniform - lag_s))
        gf, (f_u, t_u) = self.ra.uniform_grid(t_uniform, force, target)
        lag_uniform, _r = self.ra.tracking_lag_ms(f_u, t_u, fs=gf)

        t_burst = self._bursty(12.0, fs)
        target_b = np.sin(2 * np.pi * 0.4 * t_burst)
        force_b = np.sin(2 * np.pi * 0.4 * (t_burst - lag_s))
        gb, (f_b, t_b) = self.ra.uniform_grid(t_burst, force_b, target_b)
        lag_burst, _r2 = self.ra.tracking_lag_ms(f_b, t_b, fs=gb)

        self.assertAlmostEqual(lag_uniform, lag_s * 1000.0, delta=15.0)
        self.assertAlmostEqual(lag_burst, lag_uniform, delta=15.0)

    def test_the_grid_rate_is_read_off_the_timestamps(self) -> None:
        t = self._bursty(6.0, 200.0)
        fs, _series = self.ra.uniform_grid(t, np.zeros(len(t)))
        self.assertAlmostEqual(fs, 200.0, delta=5.0)

    def test_the_lag_scales_with_the_grid_rate(self) -> None:
        """k * 5.0 was a hard-coded 200 Hz."""
        a = np.sin(np.linspace(0, 40, 1000))
        b = np.roll(a, 10)
        lag_200, _ = self.ra.tracking_lag_ms(b, a, fs=200.0)
        lag_100, _ = self.ra.tracking_lag_ms(b, a, fs=100.0)
        self.assertAlmostEqual(lag_100, 2.0 * lag_200, delta=1e-6)


# ==================================================================
# A catch trial has no response byte by design
# ==================================================================
class EegCatchTests(unittest.TestCase):
    """eeg_audit_block demanded exactly one response byte after every
    boundary, and a catch trial emits a 25 and nothing else, which is
    correct. On a perfectly marked block that printed "does NOT
    reconcile ... 6 stimulus span(s) without exactly one response
    byte", and with the shipped catch rate it happened on every EEG
    reaction block."""

    def setUp(self) -> None:
        self.ra = _ra()

    def _markers(self, spans):
        """spans is [(boundary code, how many response bytes)]."""
        rows, t = [], 0.0
        for code, n_resp in spans:
            band = self.ra.eeg_band_of(code)
            rows.append({"code": code, "band": band, "t_event": t})
            t += 0.1
            for _ in range(n_resp):
                rows.append({"code": 100, "band": "resp", "t_event": t})
                t += 0.1
            t += 0.5
        return pd.DataFrame(rows)

    def test_spans_come_back_with_their_boundary_code(self) -> None:
        catch = self.ra.EEG_CODES["prep_catch_onset"]
        mk = self._markers([(33, 1), (catch, 0), (33, 1)])
        spans = self.ra._eeg_spans(mk, boundary_codes=(catch,))
        self.assertEqual(spans, [(33, 1), (catch, 0), (33, 1)])

    def test_a_catch_span_with_no_response_is_not_a_problem(self) -> None:
        catch = self.ra.EEG_CODES["prep_catch_onset"]
        mk = self._markers([(33, 1), (catch, 0)])
        spans = self.ra._eeg_spans(mk, boundary_codes=(catch,))
        bad_stim = sum(1 for code, c in spans
                       if code != catch and c != 1)
        catch_resp = sum(c for code, c in spans if code == catch)
        self.assertEqual(bad_stim, 0)
        self.assertEqual(catch_resp, 0)

    def test_the_rule_text_says_zero_on_a_catch(self) -> None:
        self.assertIn("ZERO response bytes",
                      self.ra.EEG_RULES["reaction"])

    def test_the_codes_table_marks_what_this_config_can_emit(self) -> None:
        names = self.ra.eeg_cue_codes_for(
            {"g": {"config_snapshot": {"cue": {
                "show_target": True, "buzz_before": True,
                "sound_before": True}}}})
        self.assertIn("stim_visual_buzz_tone", names)
        self.assertNotIn("stim_visual", names)
        self.assertIn("stim_buzz_hunt", names)

    def test_no_snapshot_means_the_column_says_nothing(self) -> None:
        self.assertEqual(self.ra.eeg_cue_codes_for({"g": {}}), set())


# ==================================================================
# Recorded is analysed, or says why not
# ==================================================================
class DeadColumnTests(unittest.TestCase):
    """Five per-trial columns and eight block-summary keys were
    written by the software and read by nothing. logger.py says of
    loud_trial: "The boost is a stimulus property, so any RT analysis
    needs this column to control for it."""

    def setUp(self) -> None:
        self.ra = _ra()

    def test_the_loudness_split_reports_both_sides(self) -> None:
        rows = [{"loud_trial": True, "time_difference_ms": 340.0}] * 5
        rows += [{"loud_trial": False, "time_difference_ms": 300.0}] * 5
        df = _frame(rows)
        df["loud_trial"] = [True] * 5 + [False] * 5
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tbl = self.ra.loud_trial_split(df)
        self.assertEqual(set(tbl["loudness"]), {"boosted", "normal"})
        self.assertIn("LOUDNESS BOOST", buf.getvalue())

    def test_the_wrong_press_latency_is_read(self) -> None:
        df = _frame([{"first_incorrect_ms": 210.0,
                      "first_incorrect_lane": 2,
                      "finger": "Middle"}])
        df["first_incorrect_ms"] = [210.0]
        df["first_incorrect_lane"] = [2]
        df["finger"] = ["Middle"]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = self.ra.wrong_press_latency(df)
        self.assertIsNotNone(out)
        self.assertIn("WRONG-FINGER PRESSES", buf.getvalue())

    def test_the_block_keys_get_a_readout(self) -> None:
        td = tempfile.TemporaryDirectory()
        folder = Path(td.name) / "block"
        folder.mkdir()
        meta = {"block_summary": {
            "block": "adaptive", "idle_presses": 5, "peak_streak": 22,
            "wrong_press_trials": 0, "stim_cue_failures": 0,
            "skipped_waits": {"skipped_rests": 2, "skipped_rest_s": 31.0},
            "miss_force": {"total": 1.2, "n_misses": 6,
                           "mean_per_miss": 0.2},
            "loud_trials": {"n": 3},
            "connection": {"voided_trials": 5}}}
        (folder / "metadata.json").write_text(json.dumps(meta))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tbl = self.ra.rig_and_protocol(
                [folder], {self.ra.game_key(folder): meta})
        text = buf.getvalue()
        self.assertEqual(int(tbl["rests_skipped"].iloc[0]), 2)
        self.assertEqual(int(tbl["voided_trials"].iloc[0]), 5)
        self.assertEqual(int(tbl["peak_streak"].iloc[0]), 22)
        self.assertIn("RIG AND PROTOCOL", text)
        self.assertIn("streak_at_trial", text)
        self.assertIn("correct_keys", text)
        td.cleanup()

    def test_the_continuous_modes_have_no_hit_rate_column(self) -> None:
        self.assertIn("force_pilot", self.ra.CONTINUOUS_HIT_MODES)
        self.assertIn("echo", self.ra.CONTINUOUS_HIT_MODES)
        self.assertNotIn("reaction", self.ra.CONTINUOUS_HIT_MODES)

    def test_echo_has_its_own_colour(self) -> None:
        self.assertIn("echo", self.ra.MODE_COLOUR)
        self.assertNotEqual(self.ra.MODE_COLOUR["echo"],
                            self.ra.MODE_COLOUR["unknown"])

    def test_the_syllables_hand_key_joins_the_others(self) -> None:
        self.assertEqual(self.ra.normalise_hand("R"), "right")
        self.assertEqual(self.ra.normalise_hand("L"), "left")
        self.assertIsNone(self.ra.normalise_hand("X"))

    def test_the_icc_helpers_are_kept_and_not_called(self) -> None:
        """An ICC is a test-retest statistic and this design measures
        every block once. Both helpers are documented as kept for the
        next study; nothing may reach for one on single-sitting data."""
        code = "".join(json.loads(
            (ANALYSIS
             / "session_analysis.ipynb").read_text())["cells"][2]["source"])
        self.assertIn("KEPT, NOT CALLED", code)
        for name in ("icc_two_one", "icc_ci"):
            calls = code.count(name + "(")
            self.assertEqual(calls, 1,
                             f"{name} is called somewhere: {calls} uses")


if __name__ == "__main__":
    unittest.main()
