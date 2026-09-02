"""Participant intake at login: codes, suggestions, the commit into
the Session, and what the analysis sees afterwards.

Three layers:

  1. data/intake.py pure functions: what counts as a study code, the
     next free code off the sessions tree, the visit number from the
     days already played, and the counterbalancing cell.
  2. The login screen through the real engine: every field lands in
     the Session and in metadata.json, the visit is worked out
     without a field, a code needs its main hand, a name does not,
     hand size and the pickers fill from the identity's last game,
     and the whole screen is keyboard-only drivable.
  3. The sessions tree and the notebook: a code keys the folders and
     the vs-last-time chip, and a session written before the intake
     fields existed still catalogues.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]


def _key_event(key: int, unicode: str = "", mod: int = 0):
    import pygame
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": key, "mod": mod, "unicode": unicode,
                         "scancode": 0})


def _game_folder(root: Path, day: str, who: str, mode: str = "reaction",
                 clock: str = "100000", meta: dict | None = None) -> Path:
    """One game folder in the shape the app writes."""
    d = root / day / f"{who}_{clock}_{mode}"
    d.mkdir(parents=True, exist_ok=True)
    if meta is not None:
        (d / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


# ---------------------------------------------------------------------
# 1. pure functions
# ---------------------------------------------------------------------
class CodeParsingTests(unittest.TestCase):
    def test_codes_and_names_are_told_apart(self) -> None:
        from finger_rehab.data.intake import is_study_code
        for code in ("P01", "p01", "P32", "P100", "HC01"):
            self.assertTrue(is_study_code(code), code)
        for name in ("Mara", "P1", "P", "01", "", "NA", "Pat 01",
                     "ABCD01", "P12345"):
            self.assertFalse(is_study_code(name), name)

    def test_normalise_upper_cases_the_prefix_only(self) -> None:
        from finger_rehab.data.intake import normalise_code
        self.assertEqual(normalise_code(" p07 "), "P07")
        # Digits are never rewritten: P07 and P007 are different seeds.
        self.assertEqual(normalise_code("p007"), "P007")
        self.assertEqual(normalise_code("  Mara "), "Mara")


class NextCodeSuggestionTests(unittest.TestCase):
    def test_empty_tree_suggests_p01(self) -> None:
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(suggest_next_code(td), "P01")
            self.assertEqual(suggest_next_code(Path(td) / "missing"), "P01")

    def test_next_code_is_one_past_the_highest(self) -> None:
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-09-01", "P01")
            _game_folder(root, "2026-09-01", "P02", mode="echo")
            _game_folder(root, "2026-09-02", "p02")
            self.assertEqual(suggest_next_code(root), "P03")

    def test_gaps_are_not_refilled(self) -> None:
        # A code assigned and never played (a no-show) stays retired.
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-09-01", "P01")
            _game_folder(root, "2026-09-01", "P05")
            self.assertEqual(suggest_next_code(root), "P06")

    def test_names_and_other_prefixes_do_not_count(self) -> None:
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-09-01", "Mara")
            _game_folder(root, "2026-09-01", "HC04")
            _game_folder(root, "2026-09-01", "NA")
            self.assertEqual(suggest_next_code(root), "P01")
            self.assertEqual(suggest_next_code(root, prefix="HC"), "HC05")

    def test_width_follows_the_tree(self) -> None:
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-09-01", "P099")
            self.assertEqual(suggest_next_code(root), "P100")
            _game_folder(root, "2026-09-01", "P100")
            self.assertEqual(suggest_next_code(root), "P101")

    def test_the_results_folder_is_ignored(self) -> None:
        from finger_rehab.data.intake import suggest_next_code
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "individual_patient_results" / "P09").mkdir(parents=True)
            self.assertEqual(suggest_next_code(root), "P01")


class VisitSuggestionTests(unittest.TestCase):
    def test_fresh_code_is_visit_one(self) -> None:
        from finger_rehab.data.intake import suggest_visit
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(suggest_visit(td, "P01"), 1)
            self.assertEqual(suggest_visit(td, ""), 1)
            self.assertEqual(suggest_visit(td, "NA"), 1)

    def test_each_earlier_day_is_a_visit(self) -> None:
        from finger_rehab.data.intake import suggest_visit
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "P03")
            _game_folder(root, "2026-08-20", "P03", mode="echo",
                         clock="101500")
            _game_folder(root, "2026-08-27", "p03")
            _game_folder(root, "2026-08-27", "P04")
            self.assertEqual(suggest_visit(root, "P03", today="2026-09-03"),
                             3)
            self.assertEqual(suggest_visit(root, "P04", today="2026-09-03"),
                             2)

    def test_today_does_not_count(self) -> None:
        # Relaunching the app mid-visit keeps the visit under way.
        from finger_rehab.data.intake import suggest_visit
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "P03")
            _game_folder(root, "2026-08-27", "P03")
            self.assertEqual(suggest_visit(root, "P03", today="2026-08-27"),
                             2)


class CellTests(unittest.TestCase):
    def test_codes_map_to_the_design_table(self) -> None:
        from finger_rehab.data.intake import cell_for
        expect = {
            "P01": ("A", "dominant"), "P02": ("B", "dominant"),
            "P03": ("A", "non_dominant"), "P04": ("B", "non_dominant"),
            "P05": ("A", "dominant"), "P08": ("B", "non_dominant"),
            "P28": ("B", "non_dominant"), "P32": ("B", "non_dominant"),
        }
        for code, (order, hand) in expect.items():
            cell = cell_for(code)
            self.assertEqual((cell["mode_order"], cell["hand_first"]),
                             (order, hand), code)
            self.assertEqual(cell["source"], "code")

    def test_seven_per_cell_at_twenty_eight(self) -> None:
        from finger_rehab.data.intake import cell_for
        counts: dict[tuple[str, str], int] = {}
        for n in range(1, 29):
            c = cell_for(f"P{n:02d}")
            key = (c["mode_order"], c["hand_first"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(sorted(counts.values()), [7, 7, 7, 7])

    def test_a_name_hashes_to_a_fixed_cell(self) -> None:
        from finger_rehab.data.intake import cell_for
        a = cell_for("Mara")
        b = cell_for("  mara ")
        self.assertEqual(a, b)
        self.assertEqual(a["source"], "hash")
        self.assertIn(a["mode_order"], ("A", "B"))
        self.assertIn(a["hand_first"], ("dominant", "non_dominant"))


# ---------------------------------------------------------------------
# 2. the login screen through the real engine
# ---------------------------------------------------------------------
class _LoginHarness(unittest.TestCase):
    """Real engine, real screens, keyboard source, temp sessions dir."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.eng = self._engine()

    def _engine(self, suggest: str | None = None, seed_tree=None):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        if seed_tree:
            seed_tree(self.root)
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(self.root)
        if suggest is not None:
            cfg.data["session"]["suggest_code"] = suggest
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = eng._build_screens()
        eng.show_title()
        return eng

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    @property
    def title(self):
        return self.eng._screens["title"]

    def _play_one_game(self, hit: bool = True):
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        self.eng.begin_classic_block()
        paths = self.eng.session_paths
        trial = PendingTrial(
            trial_id=1, lane=0, stim_t_perf=time.perf_counter(),
            keys_pressed=[0] if hit else [], incorrect_presses=[])
        result = (TrialResult(label="Great", points=6, rt_ms=180.0) if hit
                  else TrialResult(label="Miss", points=0, rt_ms=None))
        self.eng.log_trial(trial, result, now=time.perf_counter())
        self.eng.finish_block()
        return paths


class LoginCommitTests(_LoginHarness):
    def test_every_field_lands_in_the_session_and_the_metadata(self) -> None:
        t = self.title
        t.name_input.text = "p07"
        t.age_input.text = "23"
        t.sex_seg.set("female")
        t.hand_seg.set("left")
        t.length_input.text = "181"
        t.breadth_input.text = "80"
        t._begin()
        s = self.eng.session
        self.assertTrue(self.eng._session_active)
        self.assertEqual(s.participant, "P07")
        self.assertEqual(s.age, "23")
        self.assertEqual(s.sex, "female")
        self.assertEqual(s.dominant_hand, "left")
        # Not asked any more: recorded empty so old data reads on.
        self.assertEqual(s.edinburgh_lq, "")
        # Not typed: a fresh code is visit 1.
        self.assertEqual(s.visit, "1")
        self.assertEqual(s.hand_length_mm, "181")
        self.assertEqual(s.hand_breadth_mm, "80")
        self.assertEqual(self.eng.cfg.get("session.dominant_hand"), "left")
        self.assertEqual(self.eng.cfg.get("session.visit"), "1")
        paths = self._play_one_game()
        meta = json.loads(paths.metadata_json.read_text(encoding="utf-8"))
        for key, want in (("participant", "P07"), ("sex", "female"),
                          ("dominant_hand", "left"), ("edinburgh_lq", ""),
                          ("visit", "1"), ("hand_length_mm", "181"),
                          ("hand_breadth_mm", "80"), ("battery", {})):
            self.assertEqual(meta[key], want, key)
        # The folder and the index are keyed by the code.
        self.assertTrue(paths.root.name.startswith("P07_"))
        index = (self.root / "sessions_index.csv")
        if index.exists():
            self.assertIn("P07", index.read_text(encoding="utf-8"))

    def test_the_screen_has_no_visit_or_edinburgh_field(self) -> None:
        t = self.title
        labels = [getattr(f, "label", "") for f in t._fields]
        self.assertEqual(labels, ["PARTICIPANT CODE OR NAME", "AGE",
                                  "SEX  (optional)", "MAIN HAND",
                                  "HAND LENGTH mm", "HAND BREADTH mm"])
        self.assertFalse(hasattr(t, "visit_input"))
        self.assertFalse(hasattr(t, "ehi_input"))
        self.assertEqual([c for _k, c in t.hand_seg.options],
                         ["Left", "Right"])

    def test_a_code_needs_its_main_hand(self) -> None:
        t = self.title
        t.name_input.text = "P07"
        t._begin()
        self.assertFalse(self.eng._session_active)
        self.assertIn("main hand", t.begin_note)
        self.assertNotIn("dominant", t.begin_note)
        t.hand_seg.set("right")
        t._begin()
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.dominant_hand, "right")
        self.assertEqual(t.begin_note, "")

    def test_a_name_logs_in_without_a_hand(self) -> None:
        t = self.title
        t.name_input.text = "Mara"
        t._begin()
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "Mara")
        self.assertEqual(self.eng.session.dominant_hand, "")
        self.assertEqual(self.eng.session.sex, "")
        self.assertEqual(self.eng.session.visit, "1")

    def test_blank_name_still_warns_once(self) -> None:
        t = self.title
        t._begin()
        self.assertFalse(self.eng._session_active)
        self.assertIn("NA", t.begin_note)
        t._begin()
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "NA")

    def test_end_session_clears_the_intake_for_the_next_person(self) -> None:
        t = self.title
        t.name_input.text = "P07"
        t.hand_seg.set("left")
        t.sex_seg.set("male")
        t._begin()
        self.eng.end_session()
        s = self.eng.session
        self.assertEqual((s.participant, s.dominant_hand, s.sex, s.visit),
                         ("NA", "", "", ""))
        self.assertIsNone(self.eng.cfg.get("session.dominant_hand"))
        # And the screen came back clean.
        self.assertIsNone(self.title.hand_seg.value)
        self.assertEqual(self.title.sex_seg.value, "")
        self.assertEqual(self.title.name_input.text, "")

    def test_config_prefill_survives_a_login_that_leaves_it_alone(
            self) -> None:
        # A per-participant yaml can carry the dominant hand; the
        # engine keeps it when the caller has no field for it.
        self.eng.cfg.data["session"]["dominant_hand"] = "left"
        self.eng.begin_session("P09", "30")
        self.assertEqual(self.eng.session.dominant_hand, "left")
        self.eng.end_session()
        self.eng.begin_session("P09", "30", dominant_hand="")
        self.assertEqual(self.eng.session.dominant_hand, "")


class CodeSuggestionOnScreenTests(_LoginHarness):
    @staticmethod
    def _two_codes(root: Path) -> None:
        _game_folder(root, "2026-08-20", "P01")
        _game_folder(root, "2026-08-27", "P02")

    def test_auto_suggests_once_a_code_exists(self) -> None:
        self.eng = self._engine(seed_tree=self._two_codes)
        t = self.title
        self.assertEqual(t.name_input.text, "P03")
        self.assertTrue(t.name_input.select_all)

    def test_auto_stays_blank_on_a_clinic_machine(self) -> None:
        # Names only on disk: no code is ever suggested unasked.
        self.eng = self._engine(seed_tree=lambda r: _game_folder(
            r, "2026-08-20", "Mara"))
        self.assertEqual(self.title.name_input.text, "")

    def test_always_and_never(self) -> None:
        self.eng = self._engine(suggest="always")
        self.assertEqual(self.title.name_input.text, "P01")
        self.eng = self._engine(suggest="never", seed_tree=self._two_codes)
        self.assertEqual(self.title.name_input.text, "")

    def test_typing_replaces_the_suggestion(self) -> None:
        import pygame
        self.eng = self._engine(seed_tree=self._two_codes)
        t = self.title
        t.name_input.focused = True
        t.handle_event(_key_event(pygame.K_m, "M"))
        t.handle_event(_key_event(pygame.K_a, "a"))
        self.assertEqual(t.name_input.text, "Ma")
        self.assertFalse(t.name_input.select_all)

    def test_backspace_clears_the_suggestion_whole(self) -> None:
        import pygame
        self.eng = self._engine(seed_tree=self._two_codes)
        t = self.title
        t.name_input.focused = True
        t.handle_event(_key_event(pygame.K_BACKSPACE))
        self.assertEqual(t.name_input.text, "")

    def test_enter_on_the_suggestion_logs_that_code_in(self) -> None:
        import pygame
        self.eng = self._engine(seed_tree=self._two_codes)
        t = self.title
        t.hand_seg.set("right")
        t.handle_event(_key_event(pygame.K_RETURN))
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "P03")

    def test_the_suggestion_moves_on_after_a_session(self) -> None:
        self.eng = self._engine(seed_tree=self._two_codes)
        t = self.title
        t.hand_seg.set("right")
        t._begin()
        self._play_one_game()
        self.eng.end_session()
        self.assertEqual(self.title.name_input.text, "P04")


class VisitOnLoginTests(_LoginHarness):
    """The visit is recorded without a field: one more than the
    earlier days the code has played on."""

    @staticmethod
    def _history(root: Path) -> None:
        _game_folder(root, "2026-08-20", "P03")
        _game_folder(root, "2026-08-27", "P03")
        _game_folder(root, "2026-08-27", "P04")

    def _login(self, code: str) -> str:
        t = self.title
        t.name_input.text = code
        t.hand_seg.set("left")
        t._begin()
        visit = self.eng.session.visit
        self.eng.end_session()
        return visit

    def test_visit_follows_the_typed_code(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._history)
        self.assertEqual(self._login("P03"), "3")
        self.assertEqual(self._login("P04"), "2")
        self.assertEqual(self._login("P05"), "1")

    def test_a_config_visit_wins_over_the_derived_one(self) -> None:
        # A yaml passed as --config can pin session.visit; the login
        # honours it, and end_session clears it for the next person.
        self.eng = self._engine(suggest="never", seed_tree=self._history)
        self.eng.cfg.data["session"]["visit"] = "9"
        self.assertEqual(self._login("P03"), "9")
        self.assertEqual(self._login("P03"), "3")

    def test_visit_is_committed_without_a_frame_in_between(self) -> None:
        # The RA types the code and presses Enter at once: the visit
        # is still worked out for that code.
        self.eng = self._engine(suggest="never", seed_tree=self._history)
        t = self.title
        t.name_input.text = "P03"
        t.hand_seg.set("left")
        t._begin()
        self.assertEqual(self.eng.session.visit, "3")
        self.assertEqual(self.eng.cfg.get("session.visit"), "3")


def _meta(who: str, age: str = "30", **fields) -> dict:
    base = {"participant": who, "age": age, "hand": "right",
            "started_at": "2026-08-20T10:00:00",
            "finished_at": "2026-08-20T10:03:00",
            "block_summary": {"block": "reaction", "status": "completed"}}
    base.update(fields)
    return base


class PreviousIntakeTests(unittest.TestCase):
    """data/intake.previous_intake: the last recorded hand size and
    pickers for an identity."""

    def test_a_code_matches_on_the_code_alone(self) -> None:
        from finger_rehab.data.intake import previous_intake
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "P03", meta=_meta(
                "P03", "30", hand_length_mm="181", hand_breadth_mm="80",
                dominant_hand="left", sex="female"))
            found = previous_intake(root, "p03", "99")
            self.assertEqual(found["hand_length_mm"], "181")
            self.assertEqual(found["hand_breadth_mm"], "80")
            self.assertEqual(found["dominant_hand"], "left")
            self.assertEqual(found["sex"], "female")
            self.assertEqual(found["day"], "2026-08-20")
            self.assertIsNone(previous_intake(root, "P04"))
            self.assertIsNone(previous_intake(root, ""))
            self.assertIsNone(previous_intake(root, "NA"))

    def test_a_name_needs_the_age_to_match(self) -> None:
        from finger_rehab.data.intake import previous_intake
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "Sam_Lee", meta=_meta(
                "Sam Lee", "41", hand_length_mm="190"))
            self.assertEqual(previous_intake(root, "sam lee", "41")
                             ["hand_length_mm"], "190")
            self.assertIsNone(previous_intake(root, "Sam Lee", "42"))
            self.assertIsNone(previous_intake(root, "Sam Lee", ""))

    def test_the_newest_record_with_intake_wins(self) -> None:
        from finger_rehab.data.intake import previous_intake
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "P03", meta=_meta(
                "P03", hand_length_mm="181"))
            _game_folder(root, "2026-08-27", "P03", clock="090000",
                         meta=_meta("P03", hand_length_mm="183"))
            # A later game with nothing recorded is skipped, not
            # taken as "no hand size".
            _game_folder(root, "2026-08-27", "P03", clock="110000",
                         meta=_meta("P03"))
            self.assertEqual(previous_intake(root, "P03")
                             ["hand_length_mm"], "183")

    def test_broken_or_missing_metadata_is_skipped(self) -> None:
        from finger_rehab.data.intake import previous_intake
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _game_folder(root, "2026-08-20", "P03")
            d = _game_folder(root, "2026-08-21", "P03")
            (d / "metadata.json").write_text("{not json", encoding="utf-8")
            self.assertIsNone(previous_intake(root, "P03"))
            self.assertIsNone(previous_intake(root / "missing", "P03"))


class AutofillOnScreenTests(_LoginHarness):
    """Hand size, main hand and sex fill from the identity's last
    game, marked as carried, and never over a typed value."""

    @staticmethod
    def _tree(root: Path) -> None:
        _game_folder(root, "2026-08-20", "P03", meta=_meta(
            "P03", "30", hand_length_mm="181", hand_breadth_mm="80",
            dominant_hand="left", sex="female"))
        _game_folder(root, "2026-08-21", "Mara", meta=_meta(
            "Mara", "52", hand_length_mm="175", dominant_hand="right"))

    def test_a_code_fills_the_fields_and_marks_them(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "P03"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "181")
        self.assertEqual(t.breadth_input.text, "80")
        self.assertEqual(t.hand_seg.value, "left")
        self.assertEqual(t.sex_seg.value, "female")
        for f in (t.length_input, t.breadth_input, t.hand_seg, t.sex_seg):
            self.assertTrue(f.prefilled, f.label)
        note = t._prefill_note()
        self.assertIn("P03", note)
        self.assertIn("2026-08-20", note)
        self.assertIn("hand length", note.lower())

    def test_a_name_fills_only_with_its_age(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "Mara"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "")
        t.age_input.text = "52"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "175")
        self.assertEqual(t.hand_seg.value, "right")
        # Breadth was never recorded: stays empty and optional.
        self.assertEqual(t.breadth_input.text, "")
        self.assertFalse(t.breadth_input.prefilled)

    def test_changing_identity_drops_the_carried_values(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "P03"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "181")
        t.name_input.text = "P04"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "")
        self.assertIsNone(t.hand_seg.value)
        self.assertEqual(t.sex_seg.value, "")
        self.assertEqual(t._prefill_note(), "")

    def test_a_typed_value_is_never_overwritten(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.length_input.text = "200"
        t.hand_seg.set("right")
        t.name_input.text = "P03"
        t.update(0.016)
        self.assertEqual(t.length_input.text, "200")
        self.assertFalse(t.length_input.prefilled)
        self.assertEqual(t.hand_seg.value, "right")
        # The empty field still fills.
        self.assertEqual(t.breadth_input.text, "80")
        self.assertTrue(t.breadth_input.prefilled)

    def test_typing_over_replaces_the_carried_value_whole(self) -> None:
        import pygame
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "P03"
        t.update(0.016)
        t.length_input.focused = True
        t.handle_event(_key_event(pygame.K_1, "1"))
        t.handle_event(_key_event(pygame.K_9, "9"))
        t.handle_event(_key_event(pygame.K_0, "0"))
        self.assertEqual(t.length_input.text, "190")
        self.assertFalse(t.length_input.prefilled)
        # A picker pick clears its mark too.
        t.hand_seg.focused = True
        t.length_input.focused = False
        t.handle_event(_key_event(pygame.K_r, "r"))
        self.assertEqual(t.hand_seg.value, "right")
        self.assertFalse(t.hand_seg.prefilled)
        # And the hand-edited value is what the session records.
        t._begin()
        self.assertEqual(self.eng.session.hand_length_mm, "190")
        self.assertEqual(self.eng.session.hand_breadth_mm, "80")
        self.assertEqual(self.eng.session.dominant_hand, "right")

    def test_carried_values_reach_the_metadata(self) -> None:
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "P03"
        # Enter straight after typing: no frame in between.
        t._begin()
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.dominant_hand, "left")
        paths = self._play_one_game()
        meta = json.loads(paths.metadata_json.read_text(encoding="utf-8"))
        self.assertEqual(meta["hand_length_mm"], "181")
        self.assertEqual(meta["hand_breadth_mm"], "80")
        self.assertEqual(meta["sex"], "female")
        self.assertEqual(meta["visit"], "2")

    def test_the_tag_is_drawn_for_a_carried_field(self) -> None:
        import pygame
        from finger_rehab.ui import widgets
        self.eng = self._engine(suggest="never", seed_tree=self._tree)
        t = self.title
        t.name_input.text = "P03"
        t.update(0.016)
        seen: list[str] = []
        real_font = t.layout.font

        class _SpyFont:
            def __init__(self, font):
                self._font = font

            def render(self, text, *args, **kwargs):
                seen.append(str(text))
                return self._font.render(text, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._font, name)
        t.layout.font = lambda pt, bold=False: _SpyFont(real_font(pt, bold))
        try:
            t.draw(pygame.Surface((1280, 800)))
        finally:
            t.layout.font = real_font
        self.assertGreaterEqual(seen.count(widgets.PREFILLED_TAG), 4)


class KeyboardIntakeTests(_LoginHarness):
    def test_tab_walks_every_field_and_off_the_end(self) -> None:
        import pygame
        t = self.title
        order = [t.name_input, t.age_input, t.sex_seg, t.hand_seg,
                 t.length_input, t.breadth_input]
        for field in order:
            t.handle_event(_key_event(pygame.K_TAB))
            focused = [f for f in t._fields if f.focused]
            self.assertEqual(focused, [field])
        t.handle_event(_key_event(pygame.K_TAB))
        self.assertFalse(any(f.focused for f in t._fields))

    def test_shift_tab_walks_back(self) -> None:
        import pygame
        t = self.title
        t.handle_event(_key_event(pygame.K_TAB))
        t.handle_event(_key_event(pygame.K_TAB))
        self.assertTrue(t.age_input.focused)
        t.handle_event(_key_event(pygame.K_TAB, mod=pygame.KMOD_SHIFT))
        self.assertTrue(t.name_input.focused)
        self.assertFalse(t.age_input.focused)

    def test_hand_picker_takes_letters_and_arrows(self) -> None:
        import pygame
        t = self.title
        t.hand_seg.focused = True
        t.handle_event(_key_event(pygame.K_l, "l"))
        self.assertEqual(t.hand_seg.value, "left")
        t.handle_event(_key_event(pygame.K_RIGHT))
        self.assertEqual(t.hand_seg.value, "right")
        t.handle_event(_key_event(pygame.K_LEFT))
        self.assertEqual(t.hand_seg.value, "left")
        t.sex_seg.focused = True
        t.hand_seg.focused = False
        t.handle_event(_key_event(pygame.K_f, "f"))
        self.assertEqual(t.sex_seg.value, "female")

    def test_number_fields_refuse_a_minus(self) -> None:
        # Hand size is unsigned; the signed field (the Edinburgh LQ)
        # left the screen with the score.
        import pygame
        t = self.title
        t.length_input.focused = True
        t.handle_event(_key_event(pygame.K_MINUS, "-"))
        t.handle_event(_key_event(pygame.K_4, "4"))
        self.assertEqual(t.length_input.text, "4")

    def test_whole_login_by_keyboard_alone(self) -> None:
        import pygame
        t = self.title
        went = []
        self.eng.show_mode_select = lambda: went.append(True)
        t.handle_event(_key_event(pygame.K_TAB))          # code
        for ch, key in (("P", pygame.K_p), ("1", pygame.K_1),
                        ("1", pygame.K_1)):
            t.handle_event(_key_event(key, ch))
        t.handle_event(_key_event(pygame.K_TAB))          # age
        t.handle_event(_key_event(pygame.K_3, "3"))
        t.handle_event(_key_event(pygame.K_1, "1"))
        t.handle_event(_key_event(pygame.K_TAB))          # sex
        t.handle_event(_key_event(pygame.K_m, "m"))
        t.handle_event(_key_event(pygame.K_TAB))          # hand
        t.handle_event(_key_event(pygame.K_r, "r"))
        t.handle_event(_key_event(pygame.K_RETURN))
        self.assertEqual(went, [True])
        s = self.eng.session
        self.assertEqual((s.participant, s.age, s.sex, s.dominant_hand),
                         ("P11", "31", "male", "right"))

    def test_the_screen_draws_with_the_intake_card(self) -> None:
        import pygame
        surf = pygame.Surface((1280, 800))
        t = self.title
        t.name_input.text = "P07"
        t.begin_note = "Pick the main hand"
        t.draw(surf)
        # Every field sits inside the card, and the card clears the
        # hardware line above the utility strip.
        for f in t._fields:
            self.assertTrue(t.card_rect.contains(f.rect), f.label)
        self.assertTrue(t.card_rect.contains(t.start_btn.rect))
        rule_y = t.quit_rect.top - 26
        self.assertLess(t.card_rect.bottom, rule_y - 32)


# ---------------------------------------------------------------------
# 3. the sessions tree, the chip, the notebook
# ---------------------------------------------------------------------
class CodeKeysTheHistoryTests(_LoginHarness):
    def test_vs_last_chip_keys_by_code(self) -> None:
        self.title.name_input.text = "P05"
        self.title.hand_seg.set("right")
        self.title._begin()
        self._play_one_game()
        self.assertIsNone(self.eng.vs_last)
        self.eng.end_session()
        # Same code, next visit, a worse game: the chip compares
        # against the first (a change of zero draws no chip at all).
        self.title.name_input.text = "p05"
        self.title.hand_seg.set("right")
        self.title._begin()
        self.assertEqual(self.eng.session.participant, "P05")
        self._play_one_game(hit=False)
        self.assertIsNotNone(self.eng.vs_last)
        self.assertIn("less accurate than last time", self.eng.vs_last["text"])


def _load_ra():
    """The notebook's definitions as a namespace, the pattern
    tests/test_lighthouse_notebook_icc.py uses."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_intake"
    cells = _code_cells()
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in cells:
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                             if not k.startswith("__")})


class NotebookLoadsOldAndNewSessionsTests(unittest.TestCase):
    def test_old_metadata_without_intake_fields_still_catalogues(self):
        from finger_rehab.data.logger import TRIAL_COLUMNS
        header = ",".join(TRIAL_COLUMNS) + "\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = {
                "participant": "Pat", "age": "50", "hand": "right",
                "started_at": "2026-06-01T10:00:00",
                "finished_at": "2026-06-01T10:03:00",
                "block_summary": {"block": "reaction",
                                  "status": "completed", "trials": 1},
            }
            new = dict(old, participant="P07", sex="female",
                       dominant_hand="left", edinburgh_lq="-60",
                       visit="2",
                       battery={"id": "healthy_baseline_v1",
                                "position": 1, "of": 10},
                       started_at="2026-09-01T10:00:00",
                       finished_at="2026-09-01T10:03:00")
            d_old = _game_folder(root, "2026-06-01", "Pat", meta=old)
            d_new = _game_folder(root, "2026-09-01", "P07", meta=new)
            (d_old / "trials.csv").write_text(header, encoding="utf-8")
            (d_new / "trials.csv").write_text(header, encoding="utf-8")
            ra = _load_ra()
            cat = ra.build_catalogue(root=root)
            self.assertEqual(sorted(cat["who"]), ["P07", "Pat"])
            self.assertEqual(set(cat["mode"]), {"reaction"})
            # read_meta hands back what is there; missing keys are
            # simply missing, never an error.
            meta_old = ra.read_meta(d_old)
            self.assertNotIn("visit", meta_old)
            self.assertEqual(ra.read_meta(d_new)["visit"], "2")
            self.assertEqual(ra.read_meta(d_new)["battery"]["position"], 1)
            # And the code resolves as a pick on its own.
            picked = ra.resolve("P07", cat)
            self.assertEqual(list(picked["who"]), ["P07"])


if __name__ == "__main__":
    unittest.main()
