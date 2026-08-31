"""The vs-last-time chip: this game against the participant's
previous completed game of the same mode and hand.

Three layers:

  1. data/history.py pure maths: which prior game counts, which
     number each mode compares on, and which direction is better
     (lower RT is better, higher accuracy is better, rhythm compares
     the mean ABSOLUTE beat offset).
  2. The real engine: finish_block computes engine.vs_last from the
     metadata already on disk, first plays get nothing, and history
     from another hand or mode never leaks in.
  3. The results screen: the chip is drawn when vs_last exists and is
     absent when it does not; one chip, never a table.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _write_game(root: Path, day: str, folder: str, participant: str,
                hand: str, block: str, status: str, finished_at: str,
                summary_extra: dict | None = None) -> Path:
    """One recorded game in the sessions-tree shape the app writes and
    the notebook catalogues: metadata.json with participant + hand at
    the top level, block + status inside block_summary."""
    d = root / day / folder
    d.mkdir(parents=True)
    summary = {"block": block, "status": status}
    summary.update(summary_extra or {})
    meta = {
        "participant": participant,
        "hand": hand,
        "started_at": finished_at,
        "finished_at": finished_at,
        "block_summary": summary,
    }
    (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


class PreviousLookupTests(unittest.TestCase):
    """previous_block_summary: who counts as "last time"."""

    def test_picks_the_latest_completed_matching_game(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_game(root, "2026-08-29", "Pat_100000_reaction", "Pat",
                        "right", "reaction", "completed",
                        "2026-08-29T10:00:00",
                        {"reaction": {"median_rt_ms": 500.0}})
            _write_game(root, "2026-08-30", "Pat_100000_reaction", "Pat",
                        "right", "reaction", "completed",
                        "2026-08-30T10:00:00",
                        {"reaction": {"median_rt_ms": 400.0}})
            prev = previous_block_summary(root, "Pat", "reaction", "right")
            self.assertIsNotNone(prev)
            self.assertEqual(prev["reaction"]["median_rt_ms"], 400.0)

    def test_abandoned_games_are_not_history(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_game(root, "2026-08-30", "Pat_100000_reaction", "Pat",
                        "right", "reaction", "abandoned",
                        "2026-08-30T10:00:00",
                        {"reaction": {"median_rt_ms": 400.0}})
            self.assertIsNone(
                previous_block_summary(root, "Pat", "reaction", "right"))

    def test_same_participant_only(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_game(root, "2026-08-30", "Sam_100000_reaction", "Sam",
                        "right", "reaction", "completed",
                        "2026-08-30T10:00:00",
                        {"reaction": {"median_rt_ms": 400.0}})
            self.assertIsNone(
                previous_block_summary(root, "Pat", "reaction", "right"))

    def test_same_mode_only(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_game(root, "2026-08-30", "Pat_100000_classic", "Pat",
                        "right", "classic", "completed",
                        "2026-08-30T10:00:00", {"hit_rate": 0.8})
            self.assertIsNone(
                previous_block_summary(root, "Pat", "reaction", "right"))

    def test_same_hand_only(self) -> None:
        # A right-hand game against a bilateral one compares different
        # tasks, so the hand mode is part of the identity.
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_game(root, "2026-08-30", "Pat_100000_reaction", "Pat",
                        "both", "reaction", "completed",
                        "2026-08-30T10:00:00",
                        {"reaction": {"median_rt_ms": 400.0}})
            self.assertIsNone(
                previous_block_summary(root, "Pat", "reaction", "right"))

    def test_the_current_game_is_never_its_own_history(self) -> None:
        # Metadata is saved at block start, so the current folder is
        # already on disk when the lookup runs.
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            own = _write_game(root, "2026-08-30", "Pat_1_reaction", "Pat",
                              "right", "reaction", "completed",
                              "2026-08-30T10:00:00",
                              {"reaction": {"median_rt_ms": 400.0}})
            self.assertIsNone(previous_block_summary(
                root, "Pat", "reaction", "right", exclude_root=own))

    def test_empty_or_missing_tree_is_a_first_play(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                previous_block_summary(Path(td), "Pat", "reaction",
                                       "right"))
            self.assertIsNone(
                previous_block_summary(Path(td) / "nope", "Pat",
                                       "reaction", "right"))

    def test_broken_metadata_is_skipped_not_fatal(self) -> None:
        from finger_rehab.data.history import previous_block_summary
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad = root / "2026-08-30" / "Pat_1_reaction"
            bad.mkdir(parents=True)
            (bad / "metadata.json").write_text("{not json",
                                               encoding="utf-8")
            _write_game(root, "2026-08-30", "Pat_2_reaction", "Pat",
                        "right", "reaction", "completed",
                        "2026-08-30T11:00:00",
                        {"reaction": {"median_rt_ms": 420.0}})
            prev = previous_block_summary(root, "Pat", "reaction",
                                          "right")
            self.assertEqual(prev["reaction"]["median_rt_ms"], 420.0)


class ChipDirectionTests(unittest.TestCase):
    """chip_for: each mode compares its own number in its own
    direction, with wording that says which way things moved."""

    def _chip(self, mode, cur, prev):
        from finger_rehab.data.history import chip_for
        return chip_for(mode, cur, prev)

    # -- lower is better -------------------------------------------------
    def test_reaction_faster_is_better(self) -> None:
        chip = self._chip("reaction",
                          {"reaction": {"median_rt_ms": 388.0}},
                          {"reaction": {"median_rt_ms": 400.0}})
        self.assertEqual(chip["text"], "12 ms faster than last time")
        self.assertTrue(chip["better"])

    def test_reaction_slower_is_worse(self) -> None:
        chip = self._chip("reaction",
                          {"reaction": {"median_rt_ms": 420.0}},
                          {"reaction": {"median_rt_ms": 400.0}})
        self.assertEqual(chip["text"], "20 ms slower than last time")
        self.assertFalse(chip["better"])

    def test_rhythm_compares_absolute_offset_down_is_better(self) -> None:
        chip = self._chip(
            "rhythm",
            {"beat_offset_stats": {"beat_offset_abs_mean_ms": 48.0}},
            {"beat_offset_stats": {"beat_offset_abs_mean_ms": 60.0}})
        self.assertEqual(chip["text"],
                         "12 ms tighter timing than last time")
        self.assertTrue(chip["better"])
        worse = self._chip(
            "rhythm",
            {"beat_offset_stats": {"beat_offset_abs_mean_ms": 70.0}},
            {"beat_offset_stats": {"beat_offset_abs_mean_ms": 60.0}})
        self.assertEqual(worse["text"],
                         "10 ms looser timing than last time")
        self.assertFalse(worse["better"])

    def test_mirror_smaller_sync_gap_is_better(self) -> None:
        chip = self._chip("mirror",
                          {"mirror": {"mean_gap_ms": 70.0}},
                          {"mirror": {"mean_gap_ms": 80.0}})
        self.assertEqual(chip["text"],
                         "10 ms tighter sync than last time")
        self.assertTrue(chip["better"])

    def test_lighthouse_compares_magnitude_of_lit_dark_delta(self) -> None:
        chip = self._chip(
            "lighthouse",
            {"lighthouse": {"overall": {"lit_dark_delta_pct": 2.8}}},
            {"lighthouse": {"overall": {"lit_dark_delta_pct": 4.0}}})
        self.assertEqual(chip["text"],
                         "1.2% steadier in the dark than last time")
        self.assertTrue(chip["better"])
        # Sign of the delta must not matter: -3.0 is a 3-point gap,
        # not an improvement over +2.8.
        signed = self._chip(
            "lighthouse",
            {"lighthouse": {"overall": {"lit_dark_delta_pct": -5.0}}},
            {"lighthouse": {"overall": {"lit_dark_delta_pct": 4.0}}})
        self.assertFalse(signed["better"])

    # -- higher is better ------------------------------------------------
    def test_classic_hit_rate_up_is_better(self) -> None:
        chip = self._chip("classic", {"hit_rate": 0.83},
                          {"hit_rate": 0.80})
        self.assertEqual(chip["text"],
                         "3% more accurate than last time")
        self.assertTrue(chip["better"])
        worse = self._chip("classic", {"hit_rate": 0.70},
                           {"hit_rate": 0.80})
        self.assertEqual(worse["text"],
                         "10% less accurate than last time")
        self.assertFalse(worse["better"])

    def test_adaptive_compares_top_pace_up_is_better(self) -> None:
        chip = self._chip("adaptive", {"bpm_max": 96.0},
                          {"bpm_max": 90.0})
        self.assertEqual(chip["text"],
                         "6 BPM faster pace than last time")
        self.assertTrue(chip["better"])

    def test_force_pilot_more_corridor_time_is_steadier(self) -> None:
        chip = self._chip(
            "force_pilot",
            {"force_pilot": {"overall": {"time_in_corridor": 0.65}}},
            {"force_pilot": {"overall": {"time_in_corridor": 0.62}}})
        self.assertEqual(chip["text"], "3% steadier than last time")
        self.assertTrue(chip["better"])

    def test_syllables_accuracy_up_is_better(self) -> None:
        chip = self._chip("syllables",
                          {"syllables": {"accuracy": 0.9}},
                          {"syllables": {"accuracy": 0.8}})
        self.assertEqual(chip["text"],
                         "10% more accurate than last time")
        self.assertTrue(chip["better"])

    def test_buzz_hunt_localisation_up_is_better(self) -> None:
        chip = self._chip("buzz_hunt",
                          {"buzz_hunt": {"loc": {"accuracy": 0.75}}},
                          {"buzz_hunt": {"loc": {"accuracy": 0.70}}})
        self.assertEqual(chip["text"],
                         "5% more accurate than last time")
        self.assertTrue(chip["better"])

    def test_chords_clean_rate_up_is_better(self) -> None:
        chip = self._chip(
            "chords",
            {"chords": {"chord_outcome_classes": {"hit": 8,
                                                  "late": 2}}},
            {"chords": {"chord_outcome_classes": {"hit": 6,
                                                  "leak_fail": 4}}})
        self.assertEqual(chip["text"],
                         "20% more clean hits than last time")
        self.assertTrue(chip["better"])

    def test_pattern_weighs_takes_like_the_results_card(self) -> None:
        cur = {"pattern": {"per_take": [
            {"kind": "warmup", "accuracy": 0.1, "n": 10},
            {"kind": "trained", "accuracy": 0.9, "n": 10},
        ]}}
        prev = {"pattern": {"per_take": [
            {"kind": "trained", "accuracy": 0.8, "n": 10},
        ]}}
        chip = self._chip("pattern", cur, prev)
        self.assertEqual(chip["text"],
                         "10% more accurate than last time")
        self.assertTrue(chip["better"])

    # -- silence cases ---------------------------------------------------
    def test_zero_change_says_nothing(self) -> None:
        self.assertIsNone(self._chip(
            "reaction",
            {"reaction": {"median_rt_ms": 400.2}},
            {"reaction": {"median_rt_ms": 400.0}}))

    def test_missing_numbers_say_nothing(self) -> None:
        self.assertIsNone(self._chip("reaction", {}, {"reaction": {
            "median_rt_ms": 400.0}}))
        self.assertIsNone(self._chip("reaction", {"reaction": {
            "median_rt_ms": 400.0}}, {}))

    def test_unknown_mode_says_nothing(self) -> None:
        self.assertIsNone(self._chip("mystery", {"hit_rate": 0.9},
                                     {"hit_rate": 0.5}))

    def test_no_banned_typography_in_any_wording(self) -> None:
        # House rule: plain ASCII in everything a patient can read.
        from finger_rehab.data import history
        for rule in history._RULES.values():
            for text in rule[3:]:
                self.assertTrue(text.isascii(), text)


class _Stats:
    def __init__(self, stats: dict) -> None:
        self._stats = dict(stats)

    def block_stats(self) -> dict:
        return dict(self._stats)


def _engine(td: str):
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["session"]["data_dir"] = td
    cfg.data.setdefault("report", {})["enabled"] = False
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng.show_results = lambda: None
    return eng


class EngineVsLastTests(unittest.TestCase):
    """finish_block wires the lookup into the real block lifecycle."""

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def _play_reaction(self, eng, median_ms: float) -> None:
        eng._begin_block("reaction")
        eng.mode = _Stats({"median_rt_ms": median_ms})
        eng.finish_block()

    def test_first_play_has_no_chip_and_second_compares(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)
            self.assertIsNone(eng.vs_last)
            self._play_reaction(eng, 388.0)
            self.assertIsNotNone(eng.vs_last)
            self.assertEqual(eng.vs_last["text"],
                             "12 ms faster than last time")
            self.assertTrue(eng.vs_last["better"])

    def test_worse_direction_reads_worse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)
            self._play_reaction(eng, 431.0)
            self.assertEqual(eng.vs_last["text"],
                             "31 ms slower than last time")
            self.assertFalse(eng.vs_last["better"])

    def test_other_hand_history_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)          # right hand
            eng.set_hand_mode("left")
            self._play_reaction(eng, 300.0)          # first LEFT game
            self.assertIsNone(eng.vs_last)

    def test_other_mode_history_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)
            # First classic game: reaction history must not leak in.
            eng._begin_block("classic")
            eng.mode = None
            eng.hits, eng.misses = 8, 2
            eng.finish_block()
            self.assertIsNone(eng.vs_last)

    def test_other_participant_history_does_not_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)
            eng.session.participant = "Sam"
            self._play_reaction(eng, 350.0)
            self.assertIsNone(eng.vs_last)

    def test_abandoned_game_leaves_no_history_and_no_chip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            eng._begin_block("reaction")
            eng.mode = _Stats({"median_rt_ms": 500.0})
            eng._abandon_if_in_block()
            self.assertIsNone(eng.vs_last)
            self._play_reaction(eng, 400.0)
            # The abandoned 500 ms game is not "last time".
            self.assertIsNone(eng.vs_last)

    def test_classic_compares_hit_rate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            eng._begin_block("classic")
            eng.hits, eng.misses = 8, 2
            eng.finish_block()
            eng._begin_block("classic")
            eng.hits, eng.misses = 9, 1
            eng.finish_block()
            self.assertEqual(eng.vs_last["text"],
                             "10% more accurate than last time")
            self.assertTrue(eng.vs_last["better"])

    def test_a_new_block_clears_the_stale_chip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            eng.session.participant = "Pat"
            self._play_reaction(eng, 400.0)
            self._play_reaction(eng, 388.0)
            self.assertIsNotNone(eng.vs_last)
            eng._begin_block("classic")
            self.assertIsNone(eng.vs_last)
            eng._abandon_if_in_block()


class ResultsScreenChipTests(unittest.TestCase):
    """The slim results screen draws exactly one chip, and only when
    there is a previous game to compare against."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        pygame.font.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.ui.screens import ResultsScreen
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.rs = ResultsScreen(self.eng)

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def _pill_texts(self) -> list[str]:
        import pygame
        import finger_rehab.ui.screens as screens_mod
        seen: list[str] = []
        original = screens_mod._strip_pill

        def recorder(surf, layout, left, cy, text, *args, **kwargs):
            seen.append(str(text))
            return original(surf, layout, left, cy, text,
                            *args, **kwargs)

        screens_mod._strip_pill = recorder
        try:
            self.rs.draw(pygame.display.set_mode((1280, 800)))
        finally:
            screens_mod._strip_pill = original
        return seen

    def test_chip_drawn_when_vs_last_exists(self) -> None:
        self.eng.vs_last = {"text": "12 ms faster than last time",
                            "better": True, "delta": -12.0}
        texts = self._pill_texts()
        self.assertIn("12 ms faster than last time", texts)

    def test_no_chip_on_a_first_play(self) -> None:
        self.eng.vs_last = None
        texts = self._pill_texts()
        self.assertFalse(
            any("than last time" in t for t in texts), texts)

    def test_one_chip_never_a_table(self) -> None:
        self.eng.vs_last = {"text": "3% steadier than last time",
                            "better": True, "delta": 3.0}
        texts = self._pill_texts()
        matches = [t for t in texts if "than last time" in t]
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
