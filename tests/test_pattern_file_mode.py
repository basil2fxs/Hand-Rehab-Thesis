"""Patterns driven by a researcher's sequence file, from the mode's
layout through to the CSV and metadata a real session writes.

The point of these tests is that a file changes the MATERIAL and the
TIMING and nothing else. Every column the analysis reads keeps its
meaning: the stimulus cell still packs kind, take label, material id
and cycle position; pattern_trial is still TRUE only for trained
trials; the EEG bytes are still 40 for sequence and 41 for everything
else. On top of that the file's own promises are pinned: the same gap
list plays on every repeat (that repetition is the only reason a
rhythm can be learnt at all), a file that does not match the hand
picked is refused rather than remapped, and a file that goes missing
or unreadable between blocks falls back to the built-in riff with the
reason stamped in the data instead of vanishing.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO = Path(__file__).resolve().parents[1]
REAL_PATHS = (REPO / "config" / "pattern_sequence.yaml",
              REPO / "config" / "pattern_sequence.json",
              REPO / "config" / "pattern_sequences")
_REAL_BEFORE: dict = {}


def setUpModule() -> None:
    for p in REAL_PATHS:
        _REAL_BEFORE[p] = p.exists()


def tearDownModule() -> None:
    for p in REAL_PATHS:
        if p.exists() != _REAL_BEFORE.get(p, False):
            raise AssertionError(
                f"the run changed {p}; point pattern.sequence_file, "
                f"pattern.sequence_pointer and pattern.sequence_drop_dir "
                f"at a temp path")


ONE_HAND = """\
pattern_file: 1
name: Riff A
hands: one
timeout_ms: 1500
defaults:
  gaps_ms: 500
  rest_after_s: 10
blocks:
  - name: warm
    kind: warmup
    trials: 4
  - name: base
    kind: random
    trials: 8
  - name: riff_1
    kind: seq
    sequence: [2, 4, 1, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
  - name: fresh
    kind: probe
    sequence: [1, 4, 2, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
  - name: riff_2
    kind: seq
    sequence: [2, 4, 1, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
    rest_after_s: 30
"""

BOTH_HANDS = """\
pattern_file: 1
name: Riff B
hands: both
blocks:
  - name: riff_1
    kind: seq
    sequence: [1, 5, 2, 6, 3, 7, 4, 8]
    gaps_ms: 300
    repeats: 2
  - name: fresh
    kind: probe
    sequence: [5, 1, 6, 2, 7, 3, 8, 4]
    gaps_ms: 300
    repeats: 2
  - name: riff_2
    kind: seq
    sequence: [1, 5, 2, 6, 3, 7, 4, 8]
    gaps_ms: 300
    repeats: 2
"""

EXPLICIT = ONE_HAND.replace(
    "hands: one", "hands: one\nexplicit: true\nshow_sequence: true")


def _press(lane: int, t: float = 0.0):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                      hand="right")


def _plan(text: str, name: str = "riffA.yaml"):
    from finger_rehab.data.pattern_file import parse_plan
    return parse_plan(text, file_name=name)


def _build_mode(plan=None, lanes=None, **overrides):
    """A PatternMode on a MagicMock engine, driven with explicit `now`
    values. Same harness shape as tests/test_pattern_mode.py."""
    from finger_rehab.game.modes.pattern import PatternMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
    kwargs = dict(
        engine=engine,
        lanes=lanes if lanes is not None else [0, 1, 2, 3],
        p_seed=1234,
        block_seed=99,
        soc_cycles_per_block=5,
        warmup_trials=20,
        random_block_trials=60,
        probe_pool_size=4,
        rsi_s=0.5,
        timeout_s=2.0,
        rest_min_s=10.0,
        long_rest_s=30.0,
        fatigue_rest_s=45.0,
        fatigue_timeout_run=5,
        session_cap_min=30.0,
        short_session=False,
        score_cfg=ScoreConfig(),
        demo_trials=None,
        plan=plan,
    )
    kwargs.update(overrides)
    return engine, PatternMode(**kwargs)


def _play_trial(mode, now: float) -> float:
    """One clean trial: fire the cue, press the lit lane 200 ms later.
    Returns the press time."""
    mode._fire(now=now)
    lane = mode.active.lane
    mode._handle_press(_press(lane=lane, t=now + 0.2), now=now + 0.2)
    return now + 0.2


def _seg_index(mode, name_or_kind: str) -> int:
    for i, s in enumerate(mode.segments):
        if s.kind == name_or_kind or s.soc_id == f"file:{name_or_kind}":
            return i
    raise AssertionError(f"no segment {name_or_kind}")


class PlanLayoutTests(unittest.TestCase):
    """One take per file block, in file order, with the built-in take
    labels so the notebook's grouping by b= needs no change."""

    def test_one_segment_per_block_with_file_labels_and_ids(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        self.assertEqual([s.kind for s in mode.segments],
                         ["warmup", "random", "seq", "probe", "seq"])
        self.assertEqual([s.label for s in mode.segments],
                         ["W", "1", "2", "3", "4"])
        self.assertEqual([s.soc_id for s in mode.segments],
                         ["", "", "file:riff_1", "file:fresh", "file:riff_2"])
        self.assertEqual([len(s.fingers) for s in mode.segments],
                         [4, 8, 12, 12, 12])
        self.assertEqual(mode.n_takes, 4)
        self.assertEqual(mode.cycle_len, 4)

    def test_the_file_owns_the_timeout_and_the_default_gap(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        self.assertEqual(mode.timeout, 1.5)
        self.assertEqual(mode.current_timeout_s, 1.5)
        self.assertEqual(mode.rsi, 0.5)

    def test_a_seq_take_plays_the_riff_over_and_over(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        seg = mode.segments[_seg_index(mode, "riff_1")]
        # File lanes 2 4 1 3, stored 0-based, three repeats.
        self.assertEqual(seg.fingers, [1, 3, 0, 2] * 3)

    def test_random_and_warmup_material_is_still_drawn_fresh(self) -> None:
        # The file says how many baseline trials, not which ones: a
        # fixed random list would be the same order for everybody and
        # the baseline would stop being a baseline.
        _, a = _build_mode(plan=_plan(ONE_HAND), block_seed=1)
        _, b = _build_mode(plan=_plan(ONE_HAND), block_seed=2)
        ia = _seg_index(a, "random")
        self.assertNotEqual(a.segments[ia].fingers, b.segments[ia].fingers)
        self.assertEqual(sorted(a.segments[ia].fingers), [0, 0, 1, 1,
                                                          2, 2, 3, 3])

    def test_the_start_trim_follows_the_file_cycle(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        self.assertEqual(mode.start_trim, 4)

    def test_both_hands_uses_all_eight_lanes(self) -> None:
        _, mode = _build_mode(plan=_plan(BOTH_HANDS),
                              lanes=[0, 1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(mode.n_fingers, 8)
        self.assertEqual(mode.cycle_len, 8)
        seg = mode.segments[_seg_index(mode, "riff_1")]
        self.assertEqual(seg.fingers, [0, 4, 1, 5, 2, 6, 3, 7] * 2)
        # Every trial maps through the engine's lane list, so the lanes
        # that light are the eight real ones.
        self.assertEqual(sorted({mode.lanes[f] for f in seg.fingers}),
                         [0, 1, 2, 3, 4, 5, 6, 7])

    def test_a_file_never_halves_the_repeats_on_both_hands(self) -> None:
        # The built-in bimanual layout halves its cycle count to keep
        # takes the same length. A file says repeats and means repeats.
        _, mode = _build_mode(plan=_plan(BOTH_HANDS),
                              lanes=[0, 1, 2, 3, 4, 5, 6, 7],
                              soc_cycles_per_block=5)
        self.assertEqual(len(mode.segments[0].fingers), 16)


class GapTimingTests(unittest.TestCase):
    """The per-press gap list, which is the whole point of the file."""

    def test_each_gap_is_the_one_for_the_item_just_answered(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = _seg_index(mode, "riff_1")
        mode._begin_segment(now=100.0)
        want = [0.4, 0.4, 0.8, 1.2] * 3
        now = 100.0 + mode.SEGMENT_LEAD_S
        for i, gap in enumerate(want):
            pressed = _play_trial(mode, now)
            self.assertAlmostEqual(mode._next_stim_due - pressed, gap,
                                   places=6, msg=f"trial {i}")
            now = mode._next_stim_due

    def test_a_timeout_uses_the_same_gap_as_a_press(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = _seg_index(mode, "riff_1")
        mode._begin_segment(now=0.0)
        mode._fire(now=2.0)
        mode._close(None, now=3.5)
        self.assertAlmostEqual(mode._next_stim_due - 3.5, 0.4, places=6)

    def test_a_single_number_applies_to_every_press(self) -> None:
        _, mode = _build_mode(plan=_plan(BOTH_HANDS),
                              lanes=[0, 1, 2, 3, 4, 5, 6, 7])
        mode._seg_idx = _seg_index(mode, "riff_1")
        mode._begin_segment(now=0.0)
        now = mode.SEGMENT_LEAD_S
        for _ in range(5):
            pressed = _play_trial(mode, now)
            self.assertAlmostEqual(mode._next_stim_due - pressed, 0.3,
                                   places=6)
            now = mode._next_stim_due

    def test_with_no_file_the_single_rsi_still_rules(self) -> None:
        _, mode = _build_mode(plan=None)
        mode._seg_idx = _seg_index(mode, "seq")
        mode._begin_segment(now=0.0)
        pressed = _play_trial(mode, mode.SEGMENT_LEAD_S)
        self.assertAlmostEqual(mode._next_stim_due - pressed, 0.5, places=6)


class TrialLabellingTests(unittest.TestCase):
    """The columns the measurement lives in."""

    def _log_one(self, mode, seg_name: str):
        mode._seg_idx = _seg_index(mode, seg_name)
        mode._begin_segment(now=0.0)
        _play_trial(mode, 2.0)
        return mode.engine.log_trial.call_args

    def test_a_trained_trial_is_labelled_and_packed_as_before(self) -> None:
        engine, mode = _build_mode(plan=_plan(ONE_HAND))
        call = self._log_one(mode, "riff_1")
        self.assertTrue(call.kwargs["pattern_trial"])
        self.assertEqual(call.kwargs["stimulus"],
                         "seq;b=2;soc=file:riff_1;pos=0")

    def test_a_probe_trial_is_not_a_pattern_trial(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        call = self._log_one(mode, "fresh")
        self.assertFalse(call.kwargs["pattern_trial"])
        self.assertEqual(call.kwargs["stimulus"],
                         "probe;b=3;soc=file:fresh;pos=0")

    def test_a_random_trial_carries_no_material_id(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        call = self._log_one(mode, "random")
        self.assertFalse(call.kwargs["pattern_trial"])
        self.assertEqual(call.kwargs["stimulus"], "random;b=1")

    def test_the_cycle_position_wraps_on_the_file_cycle(self) -> None:
        engine, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = _seg_index(mode, "riff_1")
        mode._begin_segment(now=0.0)
        now = mode.SEGMENT_LEAD_S
        seen = []
        for _ in range(6):
            _play_trial(mode, now)
            seen.append(engine.log_trial.call_args.kwargs["stimulus"])
            now = mode._next_stim_due
        self.assertEqual([s.rsplit("=", 1)[1] for s in seen],
                         ["0", "1", "2", "3", "0", "1"])

    def test_the_eeg_bytes_do_not_move(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        for name, want in (("riff_1", CODES["stim_pattern_sequence"]),
                           ("fresh", CODES["stim_pattern_random"]),
                           ("random", CODES["stim_pattern_random"]),
                           ("warmup", CODES["stim_pattern_random"])):
            mode._seg_idx = _seg_index(mode, name)
            self.assertEqual(mode.eeg_stim_code(), want, name)
        self.assertEqual(CODES["stim_pattern_sequence"], 40)
        self.assertEqual(CODES["stim_pattern_random"], 41)


class RestTests(unittest.TestCase):
    def test_the_rest_after_a_block_is_the_files_own_floor(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = _seg_index(mode, "riff_1")
        mode._begin_segment(now=0.0)
        mode._trial_in_seg = len(mode.segments[mode._seg_idx].fingers)
        mode._after_segment(now=50.0)
        self.assertEqual(mode.phase, "rest")
        self.assertAlmostEqual(mode._rest_min_until, 60.0)

    def test_a_long_rest_in_the_file_arms_the_long_rest_wait(self) -> None:
        text = ONE_HAND.replace("    rest_after_s: 30",
                                "    rest_after_s: 30\n  - name: tail\n"
                                "    kind: seq\n    sequence: [2, 4, 1, 3]\n"
                                "    repeats: 2")
        _, mode = _build_mode(plan=_plan(text))
        mode._seg_idx = _seg_index(mode, "riff_2")
        mode._begin_segment(now=0.0)
        mode._trial_in_seg = len(mode.segments[mode._seg_idx].fingers)
        mode._after_segment(now=10.0)
        self.assertAlmostEqual(mode._rest_min_until, 40.0)
        self.assertEqual(mode._skip_state().armed.kind, "long_rest")

    def test_the_last_block_ends_the_session_with_no_rest(self) -> None:
        engine, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = len(mode.segments) - 1
        mode._begin_segment(now=0.0)
        mode._trial_in_seg = len(mode.segments[mode._seg_idx].fingers)
        mode._after_segment(now=10.0)
        self.assertEqual(mode.phase, "done")
        self.assertEqual(mode.end_reason, "completed")
        engine.finish_block.assert_called_once()


class BlockStatsTests(unittest.TestCase):
    def _played(self, text=ONE_HAND, **kw):
        _, mode = _build_mode(plan=_plan(text), **kw)
        now = 0.0
        for idx in range(len(mode.segments)):
            mode._seg_idx = idx
            mode._begin_segment(now=now)
            now += mode.SEGMENT_LEAD_S
            for _ in range(len(mode.segments[idx].fingers)):
                _play_trial(mode, now)
                now = mode._next_stim_due
        return mode

    def test_the_summary_names_the_file_and_its_schedule(self) -> None:
        plan = _plan(ONE_HAND)
        mode = self._played()
        st = mode.block_stats()
        self.assertEqual(st["material"], "file")
        self.assertEqual(st["schedule_id"], plan.schedule_id)
        self.assertEqual(st["explicit"], False)
        self.assertIsNone(st["sequence_file_error"])
        self.assertEqual(st["sequence_file"]["name"], "Riff A")
        self.assertEqual(st["sequence_file"]["total_trials"], 48)
        self.assertEqual(st["cycle_len"], 4)
        self.assertEqual(st["start_trim"], 4)
        self.assertEqual(st["n_trials"], 48)
        json.dumps(st)

    def test_every_take_carries_the_timing_it_ran_on(self) -> None:
        mode = self._played()
        by_label = {r["block"]: r for r in mode.block_stats()["per_take"]}
        riff = by_label["2"]
        self.assertEqual(riff["gap_ms_min"], 400.0)
        self.assertEqual(riff["gap_ms_max"], 1200.0)
        self.assertEqual(riff["gap_ms_mean"], 700.0)
        self.assertEqual(riff["n_items"], 4)
        self.assertEqual(riff["rest_after_s"], 10.0)
        self.assertEqual(by_label["4"]["rest_after_s"], 30.0)
        self.assertEqual(by_label["1"]["n_items"], 8)

    def test_an_explicit_file_is_stamped_so_it_is_never_pooled(self) -> None:
        mode = self._played(EXPLICIT)
        st = mode.block_stats()
        self.assertTrue(st["explicit"])
        self.assertTrue(st["sequence_file"]["show_sequence"])

    def test_probes_are_still_scored_against_their_flankers(self) -> None:
        mode = self._played()
        scores = mode.block_stats()["probe_scores"]
        self.assertEqual([d["block"] for d in scores], ["3"])
        self.assertEqual(scores[0]["n_flankers"], 2)

    def test_with_no_file_the_summary_says_generated(self) -> None:
        _, mode = _build_mode(plan=None)
        st = mode.block_stats()
        self.assertEqual(st["material"], "generated")
        self.assertEqual(st["schedule_id"], "builtin")
        self.assertIsNone(st["sequence_file"])
        self.assertFalse(st["explicit"])
        self.assertFalse(st["battery_overrides_ignored"])

    def test_a_fallback_says_so_in_the_data(self) -> None:
        _, mode = _build_mode(plan=None,
                              sequence_file_error="riffA.yaml is not valid")
        st = mode.block_stats()
        self.assertEqual(st["material"], "builtin_fallback")
        self.assertEqual(st["sequence_file_error"], "riffA.yaml is not valid")


class BuiltInPathUnchangedTests(unittest.TestCase):
    """The generator path must be byte-identical with no file loaded:
    every participant already in the study keeps their material."""

    def test_the_layout_and_material_are_what_they_always_were(self) -> None:
        from finger_rehab.game.modes.pattern import build_sequences
        _, mode = _build_mode(plan=None)
        self.assertEqual([s.kind for s in mode.segments],
                         ["warmup", "random", "seq", "seq", "seq", "probe",
                          "seq", "seq", "seq", "probe", "seq"])
        self.assertEqual([s.label for s in mode.segments],
                         ["W", "1", "2", "3", "4", "5", "6", "7", "8",
                          "9", "10"])
        trained, _pool = build_sequences(1234, 4, n_lanes=4)
        self.assertEqual(mode.trained, trained)
        self.assertEqual(mode.cycle_len, 12)
        self.assertEqual(mode.rsi, 0.5)
        self.assertEqual(mode.timeout, 2.0)
        self.assertIsNone(mode.plan)
        for seg in mode.segments:
            self.assertIsNone(seg.gaps_s)
            self.assertIsNone(seg.rest_after_s)

    def test_two_builds_with_the_same_seeds_agree(self) -> None:
        _, a = _build_mode(plan=None)
        _, b = _build_mode(plan=None)
        self.assertEqual([s.fingers for s in a.segments],
                         [s.fingers for s in b.segments])
        self.assertEqual(a.probe_offset, b.probe_offset)


class DemoTests(unittest.TestCase):
    def test_a_demo_from_a_file_still_writes_both_labels(self) -> None:
        engine, mode = _build_mode(plan=_plan(ONE_HAND), demo_trials=6)
        self.assertEqual([s.kind for s in mode.segments], ["seq", "probe"])
        self.assertEqual([s.soc_id for s in mode.segments],
                         ["file:riff_1", "file:fresh"])
        self.assertEqual(mode.start_trim, 0)
        # Rests cut so a demo stays under a minute.
        self.assertLessEqual(mode.segments[0].rest_after_s, 2.0)
        seen = set()
        for idx in (0, 1):
            mode._seg_idx = idx
            mode._begin_segment(now=idx * 100.0)
            _play_trial(mode, idx * 100.0 + 2.0)
            seen.add(engine.log_trial.call_args.kwargs["pattern_trial"])
        self.assertEqual(seen, {True, False})

    def test_a_demo_from_a_file_with_no_probe_falls_back_to_random(
            self) -> None:
        text = ONE_HAND.replace("    kind: probe", "    kind: seq")
        _, mode = _build_mode(plan=_plan(text), demo_trials=6)
        self.assertEqual([s.kind for s in mode.segments], ["seq", "warmup"])


class ShowSequenceTests(unittest.TestCase):
    """Digits on screen are gated twice on purpose: telling a patient
    the sequence exists is what Boyd and Winstein found impairs
    implicit learning after stroke."""

    def test_hidden_by_default(self) -> None:
        _, mode = _build_mode(plan=_plan(ONE_HAND))
        mode._seg_idx = _seg_index(mode, "riff_1")
        self.assertEqual(mode.sequence_digits(), "")

    def test_hidden_with_no_file_at_all(self) -> None:
        _, mode = _build_mode(plan=None)
        mode._seg_idx = _seg_index(mode, "seq")
        self.assertEqual(mode.sequence_digits(), "")

    def test_shown_when_the_file_says_so_twice(self) -> None:
        _, mode = _build_mode(plan=_plan(EXPLICIT))
        mode._seg_idx = _seg_index(mode, "riff_1")
        self.assertEqual(mode.sequence_digits(), "2 4 1 3")
        # Never for a baseline take: there is no riff to show.
        self.assertEqual(mode.sequence_digits(_seg_index(mode, "random")), "")


class EngineTests(unittest.TestCase):
    """The real engine, a real config and real files on disk."""

    def _cfg(self, td: str, **pattern_keys):
        from finger_rehab.config import Config
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = str(Path(td) / "sessions")
        cfg.data["report"] = {"enabled": False}
        cfg.data["session"]["participant"] = "Basil"
        pat = cfg.data.setdefault("pattern", {})
        pat["sequence_file"] = str(Path(td) / "active.yaml")
        pat["sequence_pointer"] = str(Path(td) / "active.json")
        pat["sequence_drop_dir"] = str(Path(td) / "drop")
        pat.update(pattern_keys)
        return cfg

    def _engine(self, cfg):
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng.session.participant = "Basil"
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock(),
                        "setup": MagicMock(), "mode_select": MagicMock()}
        return eng

    def _load(self, cfg, text: str, td: str, name: str = "riffA.yaml"):
        from finger_rehab.data import pattern_file as pf
        src = Path(td) / name
        src.write_text(text, encoding="utf-8")
        res = pf.import_file(src, cfg)
        self.assertTrue(res.ok, res.errors)
        return res.plan

    def test_a_loaded_file_drives_a_real_block(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                plan = self._load(cfg, ONE_HAND, td)
                eng = self._engine(cfg)
                eng.begin_pattern_block()
                self.assertEqual(eng.current_block, "pattern")
                mode = eng.mode
                self.assertIsNotNone(mode.plan)
                self.assertEqual(mode.plan.name, "Riff A")
                mode._seg_idx = _seg_index(mode, "riff_1")
                mode._begin_segment(now=100.0)
                _play_trial(mode, 102.0)
                mode._seg_idx = _seg_index(mode, "fresh")
                mode._begin_segment(now=200.0)
                _play_trial(mode, 202.0)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                with (root / "trials.csv").open() as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0]["pattern_trial"], "TRUE")
                self.assertEqual(rows[0]["stimulus"],
                                 "seq;b=2;soc=file:riff_1;pos=0")
                self.assertEqual(rows[1]["pattern_trial"], "FALSE")
                self.assertEqual(rows[1]["stimulus"],
                                 "probe;b=3;soc=file:fresh;pos=0")
                meta = json.loads((root / "metadata.json").read_text())
                st = meta["block_summary"]["pattern"]
                self.assertEqual(st["material"], "file")
                self.assertEqual(st["schedule_id"], plan.schedule_id)
                self.assertEqual(st["sequence_file"]["file_name"],
                                 "riffA.yaml")
                self.assertEqual(
                    [b["label"] for b in st["sequence_file"]["blocks"]],
                    ["W", "1", "2", "3", "4"])
                with (root / "raw.csv").open() as f:
                    raw = f.read()
                self.assertIn("material=file", raw)
                self.assertIn(f"schedule={plan.schedule_id}", raw)
                self.assertIn("file=riffA.yaml", raw)
        finally:
            pygame.quit()

    def test_the_file_survives_an_engine_restart(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, ONE_HAND, td)
                for _ in range(2):
                    # A fresh Config and a fresh engine each time round:
                    # nothing in memory carries the file over, only the
                    # files on disk.
                    cfg2 = self._cfg(td)
                    eng = self._engine(cfg2)
                    eng.begin_pattern_block()
                    self.assertIsNotNone(eng.mode.plan)
                    self.assertEqual(eng.mode.plan.name, "Riff A")
                    eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_a_both_hands_file_refuses_a_one_hand_session(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, BOTH_HANDS, td, "riffB.yaml")
                eng = self._engine(cfg)
                eng.set_hand_mode("right")
                eng.begin_pattern_block()
                self.assertNotEqual(eng.current_block, "pattern")
                self.assertIn("needs both hands", eng.pattern_refusal)
                self.assertIs(eng.screen_obj, eng._screens["setup"])
                # No block opened means no session folder was made.
                sessions = Path(td) / "sessions"
                self.assertFalse(sessions.exists()
                                 and any(sessions.iterdir()))
        finally:
            pygame.quit()

    def test_the_same_file_runs_once_both_hands_are_picked(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, BOTH_HANDS, td, "riffB.yaml")
                eng = self._engine(cfg)
                eng.set_hand_mode("both")
                eng.begin_pattern_block()
                self.assertEqual(eng.current_block, "pattern")
                self.assertEqual(eng.pattern_refusal, "")
                self.assertEqual(eng.mode.n_fingers, 8)
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_a_one_hand_file_refuses_a_bimanual_session(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, ONE_HAND, td)
                eng = self._engine(cfg)
                eng.set_hand_mode("both")
                eng.begin_pattern_block()
                self.assertNotEqual(eng.current_block, "pattern")
                self.assertIn("is for one hand", eng.pattern_refusal)
        finally:
            pygame.quit()

    def test_a_corrupted_active_file_falls_back_and_says_so(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, ONE_HAND, td)
                # Someone edits the active copy in place between blocks.
                Path(cfg.data["pattern"]["sequence_file"]).write_text(
                    "pattern_file: 1\nblocks: [\n", encoding="utf-8")
                eng = self._engine(cfg)
                eng.begin_pattern_block()
                self.assertEqual(eng.current_block, "pattern")
                self.assertIsNone(eng.mode.plan)
                st = eng.mode.block_stats()
                self.assertEqual(st["material"], "builtin_fallback")
                self.assertIn("not valid", st["sequence_file_error"])
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_the_config_switch_pins_the_builtin_riff(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td, sequence_file_enabled=False)
                self._load(cfg, ONE_HAND, td)
                eng = self._engine(cfg)
                eng.begin_pattern_block()
                self.assertIsNone(eng.mode.plan)
                self.assertEqual(eng.mode.block_stats()["material"],
                                 "generated")
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_a_battery_stamps_that_its_overrides_were_ignored(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                self._load(cfg, ONE_HAND, td)
                eng = self._engine(cfg)
                eng._battery = {"steps": [], "position": 1}
                eng.begin_pattern_block()
                self.assertTrue(
                    eng.mode.block_stats()["battery_overrides_ignored"])
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_a_dropped_file_loads_outside_a_block(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                eng = self._engine(cfg)
                src = Path(td) / "dropped.yaml"
                src.write_text(ONE_HAND, encoding="utf-8")
                ev = pygame.event.Event(pygame.DROPFILE, {"file": str(src)})
                eng._handle_global_event(ev)
                plan, reason = eng._pattern_plan()
                self.assertIsNotNone(plan, reason)
                self.assertEqual(plan.name, "Riff A")
                self.assertIn("Loaded Riff A", eng.pattern_file_note)
        finally:
            pygame.quit()

    def test_a_file_dropped_during_a_block_is_ignored(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                eng = self._engine(cfg)
                eng.begin_pattern_block()
                self.assertTrue(eng.block_is_running())
                src = Path(td) / "dropped.yaml"
                src.write_text(ONE_HAND, encoding="utf-8")
                eng._handle_global_event(
                    pygame.event.Event(pygame.DROPFILE, {"file": str(src)}))
                self.assertIsNone(eng._pattern_plan()[0])
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_a_dropped_file_of_the_wrong_kind_is_ignored(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                eng = self._engine(cfg)
                song = Path(td) / "song.mp3"
                song.write_bytes(b"not yaml")
                eng._handle_global_event(
                    pygame.event.Event(pygame.DROPFILE, {"file": str(song)}))
                self.assertEqual(eng.pattern_file_note, "")
                self.assertIsNone(eng._pattern_plan()[0])
        finally:
            pygame.quit()

    def test_the_hub_picks_up_a_file_saved_into_the_drop_folder(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                from finger_rehab.data.pattern_file import DROP_NAME
                cfg = self._cfg(td)
                eng = self._engine(cfg)
                drop = Path(td) / "drop"
                drop.mkdir()
                (drop / DROP_NAME).write_text(ONE_HAND, encoding="utf-8")
                eng.show_mode_select()
                plan, reason = eng._pattern_plan()
                self.assertIsNotNone(plan, reason)
                self.assertEqual(plan.name, "Riff A")
        finally:
            pygame.quit()

    def test_the_headline_names_the_file_for_the_screens(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = self._cfg(td)
                eng = self._engine(cfg)
                self.assertEqual(eng.pattern_plan_headline(), "")
                self._load(cfg, ONE_HAND, td)
                line = eng.pattern_plan_headline()
                self.assertTrue(line.startswith("Riff A (one hand, 4 takes,"),
                                line)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()


def _captured_text(draw_fn, monkeypatchable) -> list[str]:
    """Every string a screen renders through draw_text, so a test can
    read the whole screen the way a patient does."""
    import finger_rehab.ui.screens as screens_mod
    seen: list[str] = []
    original = screens_mod.draw_text

    def recorder(surf, text, pos, theme, layout, **kw):
        seen.append(str(text))
        return original(surf, text, pos, theme, layout, **kw)

    screens_mod.draw_text = recorder
    try:
        draw_fn()
    finally:
        screens_mod.draw_text = original
    return seen


class ScreenTests(unittest.TestCase):
    """What the screens say about a loaded file, and what they must
    never say. The secrecy rule is the constraint: with explicit false
    the participant reading over the therapist's shoulder must not
    learn that a sequence exists (Boyd and Winstein 2003, 2004)."""

    def _engine(self, td, text=None, mode="pattern"):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.data import pattern_file as pf
        pygame.display.set_mode((1280, 800))
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = str(Path(td) / "sessions")
        cfg.data["report"] = {"enabled": False}
        cfg.data.setdefault("game", {})["mode"] = mode
        p = cfg.data.setdefault("pattern", {})
        p["sequence_file"] = str(Path(td) / "active.yaml")
        p["sequence_pointer"] = str(Path(td) / "active.json")
        p["sequence_drop_dir"] = str(Path(td) / "drop")
        if text is not None:
            src = Path(td) / "riffA.yaml"
            src.write_text(text, encoding="utf-8")
            self.assertTrue(pf.import_file(src, cfg).ok)
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng.session.participant = "Mara"
        return eng

    def test_the_settings_button_names_what_is_loaded(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td)
                s = DiagnosticsScreen(eng)
                s.draw(pygame.Surface((1280, 800)))
                self.assertEqual([b.label for b in s._riff_buttons],
                                 ["Riff file: built-in"])
                # The button lives in the session data panel, not in
                # the ports panel its neighbours are hit-tested against.
                self.assertTrue(
                    s._data_rect().contains(s._riff_buttons[0].rect))
                self.assertNotIn(s._riff_buttons[0], s._panel_buttons)
        finally:
            pygame.quit()

    def test_the_settings_button_names_the_file(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td, ONE_HAND)
                s = DiagnosticsScreen(eng)
                s.draw(pygame.Surface((1280, 800)))
                self.assertIn("Riff A", s._riff_buttons[0].label)
        finally:
            pygame.quit()

    def test_the_card_opens_loads_and_clears(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td)
                s = DiagnosticsScreen(eng)
                s.draw(pygame.Surface((1280, 800)))
                self.assertFalse(s._riff_panel.open)
                s._riff_buttons[0].on_click()
                self.assertTrue(s._riff_panel.open)
                self.assertEqual(s._riff_panel.status,
                                 "Built-in riff in use")
                src = Path(td) / "typed.yaml"
                src.write_text(ONE_HAND, encoding="utf-8")
                s._riff_panel.load_path(f'  "{src}"  ')
                self.assertFalse(s._riff_panel.status_is_error)
                self.assertIsNotNone(eng._pattern_plan()[0])
                s._riff_panel._clear_clicked()
                self.assertIsNone(eng._pattern_plan()[0])
        finally:
            pygame.quit()

    def test_the_card_reports_a_bad_file_without_loading_it(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td)
                s = DiagnosticsScreen(eng)
                s._riff_panel.show()
                bad = Path(td) / "bad.yaml"
                bad.write_text("pattern_file: 1\nname: B\nhands: sideways\n"
                               "blocks: []\n", encoding="utf-8")
                s._riff_panel.load_path(str(bad))
                self.assertTrue(s._riff_panel.status_is_error)
                self.assertIn("not loaded", s._riff_panel.status)
                self.assertIsNone(eng._pattern_plan()[0])
                # A path that is not there at all says so plainly
                # instead of raising.
                s._riff_panel.load_path(str(Path(td) / "nope.yaml"))
                self.assertIn("There is no file at",
                              s._riff_panel.status)
        finally:
            pygame.quit()

    def test_the_card_blocks_clicks_reaching_the_screen(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td)
                s = DiagnosticsScreen(eng)
                s.draw(pygame.Surface((1280, 800)))
                s._riff_panel.show()
                fired = []
                s.lanes and setattr(s, "_buzz_finger",
                                    lambda ls: fired.append(ls))
                tile = s.lanes[0].rect.center if s.lanes else (100, 400)
                s.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": tile}))
                self.assertEqual(fired, [])
        finally:
            pygame.quit()

    def test_the_hub_tags_the_card_without_naming_a_sequence(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import ModeSelectScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td, ONE_HAND)
                hub = ModeSelectScreen(eng)
                surf = pygame.Surface((1280, 800))
                seen = _captured_text(lambda: hub.draw(surf), None)
                joined = " ".join(seen).lower()
                self.assertIn("custom riff: riff a", joined)
                # The two words the patient must never read on this
                # screen. "Muscle Memory" is the card's own title and
                # says nothing about repeating material.
                self.assertNotIn("sequence", joined)
                self.assertNotIn("pattern", joined)
        finally:
            pygame.quit()

    def test_the_hub_says_nothing_when_no_file_is_loaded(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import ModeSelectScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td)
                hub = ModeSelectScreen(eng)
                seen = _captured_text(
                    lambda: hub.draw(pygame.Surface((1280, 800))), None)
                self.assertNotIn("custom riff", " ".join(seen).lower())
        finally:
            pygame.quit()

    def test_the_hand_picker_warns_before_the_click(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import SetupScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td, BOTH_HANDS)
                st = SetupScreen(eng)
                seen = _captured_text(
                    lambda: st.draw(pygame.Surface((1280, 800))), None)
                joined = " ".join(seen)
                self.assertIn("RIFF FILE NEEDS BOTH HANDS", joined)
                self.assertIn("Riff file: Riff B", joined)
                self.assertEqual(
                    sum(1 for s in seen
                        if s == "RIFF FILE NEEDS BOTH HANDS"), 2)
        finally:
            pygame.quit()

    def test_the_hand_picker_stays_quiet_for_other_modes(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import SetupScreen
            with tempfile.TemporaryDirectory() as td:
                eng = self._engine(td, BOTH_HANDS, mode="chords")
                eng.pattern_refusal = "should not show here"
                st = SetupScreen(eng)
                seen = " ".join(_captured_text(
                    lambda: st.draw(pygame.Surface((1280, 800))), None))
                self.assertNotIn("RIFF FILE", seen)
                self.assertNotIn("should not show here", seen)
        finally:
            pygame.quit()

    def test_the_take_chip_hides_the_digits_unless_told_twice(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import GameplayScreen
            for text, want in ((ONE_HAND, False), (EXPLICIT, True)):
                with tempfile.TemporaryDirectory() as td:
                    eng = self._engine(td, text)
                    gp = GameplayScreen(eng)
                    eng._screens = {"gameplay": gp, "results": MagicMock(),
                                    "setup": MagicMock(),
                                    "mode_select": MagicMock()}
                    eng.begin_pattern_block()
                    m = eng.mode
                    m._seg_idx = _seg_index(m, "riff_1")
                    m._begin_segment(now=0.0)
                    m.phase = "play"
                    seen = " ".join(_captured_text(
                        lambda: gp.draw(pygame.Surface((1280, 800))), None))
                    self.assertEqual("Fingers: 2 4 1 3" in seen, want, text[:20])
                    self.assertNotIn("sequence", seen.lower())
                    eng._abandon_if_in_block()
        finally:
            pygame.quit()
