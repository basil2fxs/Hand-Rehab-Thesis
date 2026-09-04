"""Nothing the patient reads is allowed to be a judgement.

Three layers, because one alone would leak:

1. The bank itself (finger_rehab/ui/feedback_bank.py). Every entry,
   with its placeholders filled, is checked against the banned list.
2. A static scan. Every string constant handed straight to a call that
   puts text on the screen (set_message, add_encouragement, draw_text,
   _bold, flash_lane's popup_text), plus the display tables and the
   functions that return display text, is checked the same way. This
   catches a screen that writes its own wording instead of asking the
   bank.
3. A real engine. Each mode is driven through a hit, a near, a
   timeout, an early press, a late press and a wrong finger with a
   recording screen, and everything the screen was handed is checked.
   The same run asserts the trials.csv vocabulary is UNCHANGED: the
   labels "Miss", "Late", "Early", "Good" are data and the analysis
   depends on them.

Why this matters and not just the wording: feedback aimed at the task
and the next action improves performance, feedback aimed at the person
is the kind that makes it worse (Kluger and DeNisi 1996, Psychol Bull,
607 effect sizes, over a third of interventions harmful). For a device
whose whole value depends on people coming back, "too slow" costs more
than it buys.
"""
from __future__ import annotations

import ast
import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from finger_rehab.ui import feedback_bank as fb  # noqa: E402


REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "finger_rehab"

# Sample values for every placeholder the bank uses, so an entry can be
# rendered and checked without a live trial.
SLOTS = {
    "target": "index", "pressed": "ring", "n": 2, "of": 5, "ms": 480,
    "value": "212 ms", "stat": "reaction time",
    "TARGET": "INDEX", "ASKED": "TWO BUZZES",
}


def _clean(text: str) -> list[str]:
    return fb.offending(text)


# ---------------------------------------------------------------------------
# 1. The bank
# ---------------------------------------------------------------------------

class BankTests(unittest.TestCase):

    def test_every_situation_has_enough_variants(self) -> None:
        """Six or more of each form, so nothing repeats inside a block.

        The three summary situations are message-chip only, and `dip`
        has three because there are only three honest ways to say a
        round came in under the last one without saying it was worse.
        """
        line_only = {"block_end", "personal_best", "no_change", "dip"}
        for situation in fb.SITUATIONS:
            want = 3 if situation == "dip" else 6
            self.assertGreaterEqual(
                len(fb.LINE.get(situation, ())), want,
                f"{situation} has too few LINE variants")
            if situation in line_only:
                continue
            self.assertGreaterEqual(
                len(fb.POPUP.get(situation, ())), 6,
                f"{situation} has too few POPUP variants")

    def test_every_bank_entry_is_clean(self) -> None:
        for name, table in (("POPUP", fb.POPUP), ("LINE", fb.LINE)):
            for situation, entries in table.items():
                for entry in entries:
                    text = fb.render(entry, **SLOTS)
                    self.assertEqual(
                        _clean(text), [],
                        f"{name}[{situation}]: {text!r}")

    def test_every_mode_line_is_clean(self) -> None:
        for mode, sub in fb.MODE_LINES.items():
            for situation, entries in sub.items():
                for entry in entries:
                    text = fb.render(entry, **SLOTS)
                    self.assertEqual(
                        _clean(text), [],
                        f"MODE_LINES[{mode}][{situation}]: {text!r}")

    def test_offending_rules(self) -> None:
        # "too" meaning "also" at the end of a clause is fine.
        self.assertEqual(_clean("a firm press, lighter is fine too"), [])
        self.assertEqual(_clean("Lighter is enough."), [])
        # "too" plus a word is the judgement.
        self.assertIn("too", _clean("too slow"))
        self.assertIn("too", _clean("One tap too many"))
        # Labels are data, never display text.
        self.assertIn("miss", _clean("Miss"))
        self.assertIn("late", _clean("Late"))
        self.assertIn("early", _clean("Early"))
        self.assertIn("wrong", _clean("Wrong finger"))
        self.assertIn("time's up", _clean("Time's up. 2 of 5"))
        self.assertIn("stall", _clean("STALL - press harder"))
        self.assertIn("tough", _clean("Tough one - try again"))
        # Case does not matter and partial words do not count.
        self.assertEqual(_clean("Timing is the thing"), [])
        self.assertEqual(_clean("A slower song next"), ["slower"])

    def test_placeholders_are_filled(self) -> None:
        text = fb.render("That was the {pressed}. {target} next.",
                          target="index", pressed="ring")
        self.assertIn("index", text)
        self.assertIn("ring", text)
        self.assertNotIn("{", text)

    def test_a_missing_slot_raises_instead_of_reaching_the_screen(
            self) -> None:
        with self.assertRaises(KeyError):
            fb.render("{target} next.", pressed="ring")

    def test_deck_never_repeats_and_uses_every_variant(self) -> None:
        import random
        deck = fb.PhraseDeck()
        rng = random.Random(11)
        drawn = [deck.draw("miss", "line", rng) for _ in range(200)]
        for a, b in zip(drawn, drawn[1:]):
            self.assertNotEqual(a, b, "the same line landed twice running")
        self.assertEqual(set(drawn), set(fb.LINE["miss"]))

    def test_deck_is_reproducible_from_a_seed(self) -> None:
        import random
        first = [fb.PhraseDeck().draw("hit", "popup", random.Random(7))
                 for _ in range(1)]
        deck_a, deck_b = fb.PhraseDeck(), fb.PhraseDeck()
        rng_a, rng_b = random.Random(99), random.Random(99)
        seq_a = [deck_a.draw("late", "line", rng_a) for _ in range(20)]
        seq_b = [deck_b.draw("late", "line", rng_b) for _ in range(20)]
        self.assertEqual(seq_a, seq_b)
        self.assertTrue(first)

    def test_situation_mapping(self) -> None:
        s = fb.situation_for
        self.assertEqual(s("Perfect"), "hit")
        self.assertEqual(s("Great"), "hit")
        self.assertEqual(s("Good"), "hit")
        self.assertEqual(s("Late"), "late")
        self.assertEqual(s("Early"), "early")
        # The three kinds of Miss need three different things said.
        self.assertEqual(s("Miss", pressed=True, incorrect=True),
                          "wrong_finger")
        self.assertEqual(s("Miss", pressed=False), "timeout")
        self.assertEqual(s("Miss", pressed=True), "miss")
        # A rhythm Good well off centre reads as a near.
        self.assertEqual(s("Good", rt_ms=160.0, mode="rhythm"), "near")
        self.assertEqual(s("Good", rt_ms=20.0, mode="rhythm"), "hit")

    def test_neutral_glyph_covers_every_outcome_situation(self) -> None:
        for situation in ("hit", "near", "late", "early", "miss",
                          "timeout", "wrong_finger"):
            self.assertIn(fb.NEUTRAL_GLYPH[situation], fb.GLYPHS)


# ---------------------------------------------------------------------------
# 2. Static scan of every call site that puts text on the screen
# ---------------------------------------------------------------------------

# Calls whose string arguments end up in front of a patient.
DISPLAY_CALLS = {"set_message", "_set_message", "add_encouragement",
                 "draw_text", "_bold", "flash_lane"}
# Functions whose return value is display text.
DISPLAY_RETURNS = {"_feedback_text", "_grade_for", "_kind_words",
                   "_stage", "_hands_line", "section_coach",
                   "_title_for"}
# Module-level tables of display text.
DISPLAY_TABLES = {"SECTION_COACH", "STAGE_LINES", "_ENCOURAGEMENT",
                  "ERROR_SUBS", "MODE_HINTS"}

# Text a patient never reads: it is on the RA's protocol card or a
# diagnostics readout, and the words there are the therapist's own
# vocabulary. Keyed by (file stem, the exact string).
THERAPIST_TEXT = {
    ("screens", "4. Finish every block. Quitting early leaves "
                "gaps in the data."),
    ("screens", "Buzzer send error: "),
    ("screens", "STIM send error: "),
}


def _strings_directly_in(node: ast.AST) -> list[str]:
    """String constants in `node`, not descending into nested calls.

    A nested call's own arguments are that call's business: a bank key
    like "early" passed to self._phrase("early") is not display text,
    and the phrase it returns is checked where the bank is checked.
    """
    if isinstance(node, ast.Call):
        # The argument IS another call: whatever it returns is checked
        # where that function is checked, and its own arguments are
        # bank keys, not words.
        return []
    out: list[str] = []

    def walk(n: ast.AST) -> None:
        if isinstance(n, ast.Call):
            return
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
            return
        for child in ast.iter_child_nodes(n):
            walk(child)

    walk(node)
    return out


class DisplayCallSiteTests(unittest.TestCase):
    """Every string a screen is handed directly, checked in one pass.

    Anything that fails here is a screen writing its own verdict
    instead of asking the bank for wording.
    """

    def _offences(self) -> list[str]:
        bad: list[str] = []
        for path in sorted(PKG.rglob("*.py")):
            if "__pycache__" in str(path) or path.name == "feedback_bank.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            docstrings = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef,
                                     ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(node, clean=False)
                    if doc:
                        docstrings.add(doc)
            for text, lineno in self._display_strings(tree):
                if text in docstrings:
                    continue
                if (path.stem, text) in THERAPIST_TEXT:
                    continue
                found = fb.offending(text)
                if found:
                    bad.append(f"{path.name}:{lineno}: {text!r} -> {found}")
        return bad

    @staticmethod
    def _display_strings(tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = (func.attr if isinstance(func, ast.Attribute)
                        else func.id if isinstance(func, ast.Name)
                        else None)
                # Logging is for the therapist and the log file.
                if isinstance(func, ast.Attribute) and isinstance(
                        func.value, ast.Name) and func.value.id == "log":
                    continue
                if name in DISPLAY_CALLS:
                    for arg in list(node.args):
                        for s in _strings_directly_in(arg):
                            yield s, node.lineno
                    for kw in node.keywords:
                        if kw.arg in ("popup_text", "text", "title",
                                       "label"):
                            for s in _strings_directly_in(kw.value):
                                yield s, node.lineno
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name not in DISPLAY_RETURNS:
                    continue
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Return) and sub.value is not None:
                        for s in _strings_directly_in(sub.value):
                            yield s, sub.lineno
            elif isinstance(node, ast.Assign):
                names = {t.id for t in node.targets
                         if isinstance(t, ast.Name)}
                if not (names & DISPLAY_TABLES):
                    continue
                for s in _strings_directly_in(node.value):
                    yield s, node.lineno

    def test_no_call_site_shows_a_banned_word(self) -> None:
        bad = self._offences()
        self.assertEqual(bad, [], "\n".join(bad))

    def test_the_scan_actually_finds_things(self) -> None:
        """Guard against a scan that silently matches nothing."""
        tree = ast.parse(
            'self.set_message("too slow", 1.0)\n'
            'draw_text(surf, "Miss", pos)\n')
        found = [s for s, _ in self._display_strings(tree)]
        self.assertIn("too slow", found)
        self.assertIn("Miss", found)

    def test_the_scan_ignores_bank_keys(self) -> None:
        tree = ast.parse('self._set_message(self._phrase("early"), 1.0)\n')
        found = [s for s, _ in self._display_strings(tree)]
        self.assertEqual(found, [])


# ---------------------------------------------------------------------------
# 3. A real engine, one block per mode
# ---------------------------------------------------------------------------

class _RecordingScreen:
    """Stands in for a gameplay or rhythm screen and keeps every word.

    Only the four methods the engine calls are implemented, which is
    also the list of ways text can reach a lane screen.
    """

    def __init__(self) -> None:
        self.lanes: list = []
        self.messages: list[tuple[str, str]] = []
        self.banners: list[str] = []
        self.popups: list[str] = []
        self.glyphs: list[tuple[str, float]] = []
        self.message = ""

    def set_message(self, text, duration_s, kind="info") -> None:
        self.messages.append((str(text), kind))
        self.message = str(text)

    def add_encouragement(self, text) -> None:
        self.banners.append(str(text))

    def flash_lane(self, lane, colour, duration_s, now,
                   popup_text=None, popup_glyph=None) -> None:
        import time as _t
        if popup_glyph:
            self.glyphs.append((popup_glyph, _t.perf_counter()))
        if popup_text:
            self.popups.append(str(popup_text))

    def start_countdown(self, seconds) -> None:
        pass

    def all_text(self) -> list[str]:
        return ([m for m, _ in self.messages] + self.banners
                + self.popups)


def _make_engine(td: str, *, style: str = "encouraging",
                 delay_ms: int = 0):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [640, 480]
    cfg.data["ui"]["feedback_style"] = style
    cfg.data["ui"]["feedback_delay_ms"] = delay_ms
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = td
    cfg.data["report"] = {"enabled": False}
    eng = GameEngine(cfg, KeyboardOnlySource())
    gp, rs = _RecordingScreen(), _RecordingScreen()
    # Only the two lane screens record; the menus are stubs, because
    # nothing a patient reads as feedback is drawn on them.
    from unittest.mock import MagicMock
    eng._screens = {"gameplay": gp, "rhythm": rs,
                    "mode_select": MagicMock(), "results": MagicMock(),
                    "hub": MagicMock()}
    return eng, gp, rs


def _trial(trial_id: int, lane: int, *, pressed: bool,
           wrong_lane: int | None = None):
    from finger_rehab.game.modes.classic import PendingTrial
    keys = [lane] if pressed else []
    wrong: list[tuple[int, float]] = []
    if wrong_lane is not None:
        keys = [wrong_lane]
        wrong = [(wrong_lane, 100.4)]
    return PendingTrial(trial_id=trial_id, lane=lane,
                        stim_t_perf=100.0, keys_pressed=keys,
                        incorrect_presses=wrong)


# The seven trial shapes any classic-style mode can produce. Each is
# (label, pressed, wrong_lane, rt_ms).
TRIAL_SHAPES = (
    ("Perfect", True, None, 90.0),
    ("Great", True, None, 160.0),
    ("Good", True, None, 400.0),
    ("Late", True, None, 700.0),
    ("Early", True, None, -60.0),
    ("Miss", True, None, 900.0),
    ("Miss", False, None, None),
    ("Miss", True, 2, None),
)

# Every mode that routes its outcomes through engine.log_trial.
LOG_TRIAL_MODES = ("classic", "adaptive", "pattern", "mirror", "chords",
                   "syllables", "force_pilot", "buzz_hunt", "echo",
                   "reaction")


class RealEngineWordingTests(unittest.TestCase):

    def test_every_mode_shows_clean_words(self) -> None:
        from finger_rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td)
            for block in LOG_TRIAL_MODES:
                eng._begin_block(block)
                for i, (label, pressed, wrong, rt) in enumerate(
                        TRIAL_SHAPES):
                    trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                    outcome = TrialResult(label=label, points=1, rt_ms=rt)
                    eng.log_trial(trial, outcome, 100.0 + i)
                for text in gp.all_text():
                    self.assertEqual(
                        fb.offending(text), [],
                        f"{block} put {text!r} on the screen")
                self.assertTrue(gp.popups, f"{block} showed no feedback")

    def test_a_wrong_finger_names_the_finger_to_use(self) -> None:
        from finger_rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td)
            eng._begin_block("classic")
            # Cue on lane 2 (the ring), pressed lane 0 (the index).
            trial = _trial(1, 2, pressed=True, wrong_lane=0)
            eng.log_trial(trial, TrialResult("Miss", 0, None), 100.0)
            joined = " ".join(gp.popups).lower()
            self.assertIn("ring", joined)
            self.assertEqual(fb.offending(joined), [])

    def test_rhythm_shows_clean_words(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, _gp, rs = _make_engine(td)
            eng._begin_block("rhythm")
            for i, (label, offset, pressed) in enumerate((
                    ("Perfect", 10.0, True), ("Great", 60.0, True),
                    ("Good", 140.0, True), ("Late", 180.0, True),
                    ("Early", -180.0, True), ("Miss", 400.0, False))):
                eng.log_rhythm_hit(_FakeNote(lane=1, index=i), offset,
                                   label, 1, 5.0, was_pressed=pressed)
            for text in rs.all_text():
                self.assertEqual(fb.offending(text), [],
                                  f"rhythm put {text!r} on the screen")

    def test_streak_banners_name_the_count_not_the_person(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td)
            eng._begin_block("classic")
            for _ in range(5):
                eng._update_streak(was_hit=True, screen_key="gameplay")
            self.assertEqual(gp.banners, ["3 in a row", "5 in a row, nice"])
            for text in gp.banners:
                self.assertEqual(fb.offending(text), [])

    def test_the_csv_vocabulary_is_unchanged(self) -> None:
        """The labels are data. The analysis reads them; the patient
        does not."""
        from finger_rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng, _gp, _rs = _make_engine(td)
            eng.begin_session("TEST", "30")
            eng._begin_block("classic")
            eng._open_loggers()
            for i, (label, pressed, wrong, rt) in enumerate(TRIAL_SHAPES):
                trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                eng.log_trial(trial, TrialResult(label, 1, rt), 100.0 + i)
            eng._close_loggers()
            rows = self._trial_rows(Path(td))
            labels = [r["early_late"] for r in rows]
            self.assertEqual(
                labels,
                ["Perfect", "Great", "Good", "Late", "Early",
                 "Miss", "Miss", "Miss"])

    @staticmethod
    def _trial_rows(root: Path) -> list[dict]:
        paths = sorted(root.rglob("trials.csv"))
        with paths[-1].open(newline="") as f:
            return list(csv.DictReader(f))


class _FakeNote:
    """The shape log_rhythm_hit reads off a scheduled note."""

    def __init__(self, lane: int, index: int = 0) -> None:
        self.note = type("N", (), {"lane": lane, "t": 1.0})()
        self.t_hit = 1.0
        self.index = index


class ReactionWordingTests(unittest.TestCase):
    """Reaction writes its own chips: the RT readout, the false start,
    the wrong finger and the lapse line."""

    def _mode(self, td: str):
        eng, gp, _rs = _make_engine(td)
        eng.cfg.data["reaction"] = {"seed": 4321, "catch_rate": 0.0}
        eng.begin_reaction_block()
        return eng, eng.mode, gp

    @staticmethod
    def _press(lane: int, t: float):
        from finger_rehab.hardware.fsr_detector import PressEvent
        return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                          hand="right")

    def test_a_false_start_says_what_to_wait_for(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _eng, mode, gp = self._mode(td)
            mode._begin_trial(now=100.0)
            mode._handle_press(self._press(0, 100.5), now=100.5)
            texts = [m for m, _ in gp.messages]
            self.assertTrue(texts)
            for text in texts:
                self.assertEqual(fb.offending(text), [], text)
            # Never the amber alarm colour: that belongs to hardware.
            self.assertNotIn("warn", [k for _, k in gp.messages])

    def test_a_lapse_keeps_the_number_and_drops_the_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _eng, mode, gp = self._mode(td)
            mode._show_rt_feedback(620.0)
            text = gp.messages[-1][0]
            self.assertIn("620", text)
            self.assertEqual(fb.offending(text), [], text)

    def test_a_wrong_finger_names_the_one_to_use(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _eng, mode, gp = self._mode(td)
            mode.sub_mode = "choice"
            mode._begin_trial(now=200.0)
            mode._fire(now=203.0)
            lane = mode.active.lane
            other = (lane + 1) % 4
            mode._handle_press(self._press(other, 203.4), now=203.4)
            text = gp.messages[-1][0]
            self.assertEqual(fb.offending(text), [], text)
            self.assertIn(fb.finger_words(lane), text.lower())


class ChordsWordingTests(unittest.TestCase):

    def test_every_failure_branch_is_clean_and_names_a_finger(
            self) -> None:
        from unittest.mock import MagicMock
        from finger_rehab.game.modes.chords import ChordsMode
        mode = ChordsMode.__new__(ChordsMode)
        mode.engine = MagicMock()
        mode.bilateral = False
        mode.hands = {"right": [0, 1, 2, 3]}
        mode.lanes = [0, 1, 2, 3]
        trial = MagicMock()
        trial.kind = "chord"
        trial.onsets = {1: 0.2}
        trial.hold_released = [1]
        trial.incorrect_presses = [(1, 0.3)]
        trial.fingers = [0, 1]
        trial.targets = [0, 1]
        trial.keys_pressed = []
        for cls in ("late_chord", "no_hold", "leak_fail", "partial"):
            text = mode._feedback_text(trial, cls, False, False, 1)
            self.assertEqual(fb.offending(text), [], f"{cls}: {text!r}")
            self.assertTrue(text)
        over = mode._feedback_text(trial, "over_force", True, False)
        self.assertEqual(fb.offending(over), [], over)


class EchoWordingTests(unittest.TestCase):

    def test_a_run_out_of_time_keeps_the_credit(self) -> None:
        line = fb.phrase_via(None, "omission", "line", "echo", n=2, of=5)
        self.assertEqual(fb.offending(line), [], line)
        self.assertIn("2", line)
        self.assertIn("5", line)


class BuzzHuntWordingTests(unittest.TestCase):

    def test_titles_say_where_the_buzz_was(self) -> None:
        for situation in ("wrong", "wrong_count", "no_response"):
            for entry in fb.MODE_LINES["buzz_hunt"][situation]:
                text = fb.render(entry, **SLOTS)
                self.assertEqual(fb.offending(text), [], text)


class ForcePilotWordingTests(unittest.TestCase):

    def test_the_live_tag_says_which_way_to_move(self) -> None:
        lift = fb.MODE_LINES["force_pilot"]["lift"][0]
        ease = fb.MODE_LINES["force_pilot"]["ease"][0]
        self.assertEqual(fb.offending(lift), [], lift)
        self.assertEqual(fb.offending(ease), [], ease)
        self.assertIn("more", lift)
        self.assertIn("off", ease)


class PopupFitsOnScreenTests(unittest.TestCase):
    """The wording is longer than the label it replaced.

    "Switch to Middle" is 348 px at 42 pt against about 130 px for
    "Miss", and in bilateral play the outer lane centres sit 100 px
    from the edge, so an unclamped popup would lose its first word.
    """

    def test_every_popup_fits_the_page(self) -> None:
        import pygame
        from finger_rehab.ui.widgets import FloatingText, Layout
        pygame.init()
        pygame.display.set_mode((1280, 800))
        layout = Layout(1280, 800, 1.0)
        surf = pygame.Surface((1280, 800))
        widest = max(
            (fb.render(e, target="Middle", pressed="Ring")
             for entries in fb.POPUP.values() for e in entries),
            key=lambda t: layout.font(42).size(t)[0])
        # Both outer bilateral lane centres, and the middle.
        for cx in (100, 640, 1177):
            popup = FloatingText(widest, (cx, 200),
                                  (0, 0, 0), font_pt=42)
            popup.draw(surf, layout)
            rect = layout.font(42).render(
                widest, True, (0, 0, 0)).get_rect(center=(cx, 200))
            self.assertLess(rect.width, 1280,
                             f"{widest!r} is wider than the page")

    def test_the_clamp_keeps_the_whole_word_on_screen(self) -> None:
        import pygame
        from finger_rehab.ui.widgets import FloatingText, Layout
        pygame.init()
        pygame.display.set_mode((1280, 800))
        layout = Layout(1280, 800, 1.0)
        # A wide popup on the leftmost bilateral lane: its natural rect
        # starts off the page, and the drawn one must not.
        text = "Switch to Middle"
        natural = layout.font(42).render(
            text, True, (0, 0, 0)).get_rect(center=(100, 200))
        self.assertLess(natural.left, 0)
        drawn = _drawn_rect(FloatingText(text, (100, 200), (255, 0, 0),
                                          font_pt=42), layout)
        self.assertGreaterEqual(drawn.left, 0)
        self.assertLessEqual(drawn.right, 1280)


    def test_the_mode_titles_and_chips_fit_the_page(self) -> None:
        """Longer wording than the labels it replaced, so the widest
        line of each kind is measured against where it is drawn."""
        import pygame
        from finger_rehab.game.modes.force_pilot import FINGER_WORDS
        from finger_rehab.ui.widgets import (
            FONT_BODY, FONT_H1, FONT_TITLE, Layout)
        pygame.init()
        pygame.display.set_mode((1280, 800))
        layout = Layout(1280, 800, 1.0)
        # Buzz Hunt titles: centred at 640, FONT_H1 + 6.
        title_font = layout.font(FONT_H1 + 6)
        for situation in ("wrong", "wrong_count", "no_response"):
            for entry in fb.MODE_LINES["buzz_hunt"][situation]:
                for word in FINGER_WORDS:
                    text = fb.render(entry, TARGET=word, ASKED=word)
                    self.assertLess(title_font.size(text)[0], 1200, text)
        # Force Pilot's live tag starts at x = MARKER_X + 26 = 326.
        body_font = layout.font(FONT_BODY)
        for key in ("lift", "ease"):
            for entry in fb.MODE_LINES["force_pilot"][key]:
                self.assertLess(326 + body_font.size(entry)[0], 1280,
                                 entry)
        # Streak banners: centred, FONT_TITLE - 4.
        from finger_rehab.game.engine import GameEngine
        banner_font = layout.font(FONT_TITLE - 4)
        for text in GameEngine._ENCOURAGEMENT.values():
            self.assertLess(banner_font.size(text)[0], 1200, text)


def _drawn_rect(popup, layout):
    """Where a FloatingText actually put its ink on a blank surface."""
    import pygame
    surf = pygame.Surface((layout.width, layout.height))
    surf.fill((0, 0, 0))
    popup.draw(surf, layout)
    return surf.get_bounding_rect()


class ResultsAdviceTests(unittest.TestCase):
    """The vs-last chip and the study-battery progress row.

    These are the lines a participant reads at the end of a block, so
    they follow the same rule as the in-play wording: the number is
    kept, the verdict is not.
    """

    def test_every_vs_last_line_is_clean(self) -> None:
        from finger_rehab.data import history
        for mode, rule in history._RULES.items():
            for template in rule[3:]:
                text = template.format(d="22")
                self.assertEqual(fb.offending(text), [],
                                  f"{mode}: {text!r}")

    def test_every_vs_last_line_keeps_a_retailable_ending(self) -> None:
        """The battery panel retails these words with its own tail."""
        from finger_rehab.data import history
        from finger_rehab.game.battery import _HISTORY_TAILS
        for mode, rule in history._RULES.items():
            for template in rule[3:]:
                self.assertTrue(
                    any(template.endswith(t) for t in _HISTORY_TAILS),
                    f"{mode}: {template!r} has no retailable ending")

    def test_the_battery_same_wording_is_clean(self) -> None:
        from finger_rehab.game.battery import SAME_SHORT, SAME_TEXT
        for text in (SAME_SHORT, SAME_TEXT):
            self.assertEqual(fb.offending(text), [], text)

    def test_a_round_that_came_in_under_still_reads_forward(self) -> None:
        from finger_rehab.data import history
        chip = history.chip_for(
            "reaction",
            {"reaction": {"median_rt_ms": 320.0}},
            {"reaction": {"median_rt_ms": 290.0}})
        self.assertIsNotNone(chip)
        self.assertFalse(chip["better"])
        self.assertEqual(fb.offending(chip["text"]), [], chip["text"])
        self.assertIn("30", chip["text"])


class GradeBlurbTests(unittest.TestCase):

    def test_every_grade_blurb_is_clean(self) -> None:
        from finger_rehab.ui.screens import ResultsScreen
        letters = []
        for rate in (1.0, 0.9, 0.75, 0.6, 0.4, 0.1):
            letter, blurb = ResultsScreen._grade_for(rate)
            letters.append(letter)
            self.assertEqual(fb.offending(blurb), [],
                              f"{letter}: {blurb!r}")
        # The letters are the pinned part and do not move.
        self.assertEqual(letters, ["S", "A", "B", "C", "D", "E"])


# ---------------------------------------------------------------------------
# 4. The EEG lab style
# ---------------------------------------------------------------------------

class NeutralStyleTests(unittest.TestCase):

    def test_no_words_and_a_glyph_per_outcome(self) -> None:
        from finger_rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td, style="neutral",
                                         delay_ms=500)
            eng._begin_block("classic")
            for i, (label, pressed, wrong, rt) in enumerate(TRIAL_SHAPES):
                trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                eng.log_trial(trial, TrialResult(label, 1, rt), 100.0 + i)
            self.assertEqual(gp.popups, [], "words reached a lab block")
            self.assertEqual(gp.banners, [])
            # Nothing is drawn until the delay is up.
            self.assertEqual(gp.glyphs, [])
            self.assertEqual(len(eng._pending_feedback), len(TRIAL_SHAPES))

    def test_the_glyph_waits_out_the_delay(self) -> None:
        import time
        from finger_rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td, style="neutral",
                                         delay_ms=500)
            eng._begin_block("classic")
            t0 = time.perf_counter()
            eng.log_trial(_trial(1, 1, pressed=True),
                          TrialResult("Great", 1, 150.0), 100.0)
            eng._drain_feedback()
            self.assertEqual(gp.glyphs, [], "the glyph jumped the delay")
            # Shorten the wait rather than sleeping half a second.
            due, *rest = eng._pending_feedback[0]
            eng._pending_feedback[0] = (t0 - 0.001, *rest)
            eng._drain_feedback()
            self.assertEqual(len(gp.glyphs), 1)
            self.assertEqual(gp.glyphs[0][0], "full")
            self.assertEqual(eng._pending_feedback, [])
            self.assertGreater(due, t0 + 0.4)

    def test_each_outcome_gets_its_own_glyph(self) -> None:
        from finger_rehab.game.scoring import TrialResult
        want = ["full", "full", "full", "half", "half", "open", "open",
                "open"]
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td, style="neutral",
                                         delay_ms=500)
            eng._begin_block("classic")
            for i, (label, pressed, wrong, rt) in enumerate(TRIAL_SHAPES):
                trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                eng.log_trial(trial, TrialResult(label, 1, rt), 100.0 + i)
            for entry in eng._pending_feedback:
                entry_list = list(entry)
                entry_list[0] = 0.0
                eng._pending_feedback[
                    eng._pending_feedback.index(entry)] = tuple(entry_list)
            eng._drain_feedback()
            self.assertEqual([g for g, _ in gp.glyphs], want)

    def test_the_glyph_is_the_same_colour_for_every_outcome(self) -> None:
        """Only the fill may differ. Size, position, colour and
        lifetime are identical, or the feedback ERP is confounded with
        a low-level visual difference."""
        import pygame
        from finger_rehab.game.scoring import TrialResult
        from finger_rehab.ui.screens import GameplayScreen
        pygame.init()
        pygame.display.set_mode((1280, 800))
        with tempfile.TemporaryDirectory() as td:
            eng, _gp, _rs = _make_engine(td, style="neutral",
                                          delay_ms=500)
            gp = GameplayScreen(eng)
            eng._screens["gameplay"] = gp
            eng._begin_block("classic")
            for i, (label, pressed, wrong, rt) in enumerate(TRIAL_SHAPES):
                trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                eng.log_trial(trial, TrialResult(label, 1, rt), 100.0 + i)
            eng._pending_feedback = [(0.0, *rest) for (_d, *rest)
                                      in eng._pending_feedback]
            eng._drain_feedback()
            popups = [p for p in gp._popups if p.glyph]
            self.assertEqual(len(popups), len(TRIAL_SHAPES))
            self.assertEqual({p.colour for p in popups},
                              {eng.theme.foreground})
            self.assertEqual({p.font_pt for p in popups}, {42})
            self.assertEqual({p.lifetime_s for p in popups}, {0.9})
            self.assertEqual({p.start_pos for p in popups},
                              {popups[0].start_pos})

    def test_the_labels_are_identical_under_both_styles(self) -> None:
        """Style changes what is SHOWN, never what is recorded."""
        from finger_rehab.game.scoring import TrialResult
        rows: list[list[str]] = []
        for style, delay in (("encouraging", 0), ("neutral", 800)):
            with tempfile.TemporaryDirectory() as td:
                eng, _gp, _rs = _make_engine(td, style=style,
                                              delay_ms=delay)
                eng.begin_session("TEST", "30")
                eng._begin_block("classic")
                eng._open_loggers()
                for i, (label, pressed, wrong, rt) in enumerate(
                        TRIAL_SHAPES):
                    trial = _trial(i, 1, pressed=pressed, wrong_lane=wrong)
                    eng.log_trial(trial, TrialResult(label, 1, rt),
                                  100.0 + i)
                eng._close_loggers()
                got = RealEngineWordingTests._trial_rows(Path(td))
                rows.append([f"{r['early_late']}|{r['feedback']}"
                             for r in got])
        self.assertEqual(rows[0], rows[1])

    def test_reaction_shows_the_plain_readout_in_the_lab(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, gp, _rs = _make_engine(td, style="neutral",
                                         delay_ms=800)
            eng.cfg.data["reaction"] = {"seed": 4321, "catch_rate": 0.0}
            eng.begin_reaction_block()
            eng.mode._show_rt_feedback(212.0)
            eng.mode._show_rt_feedback(620.0)
            texts = [m for m, _ in gp.messages][-2:]
            self.assertEqual(texts, ["212 ms", "620 ms"])
            self.assertEqual([k for _, k in gp.messages][-2:],
                              ["info", "info"])


class StyleConfigTests(unittest.TestCase):

    class _Cfg:
        def __init__(self, data: dict) -> None:
            self.data = data

        def get(self, key, default=None):
            node = self.data
            for part in key.split("."):
                if isinstance(node, dict) and part in node:
                    node = node[part]
                else:
                    return default
            return node

    def test_missing_keys_behave_as_the_shipping_game(self) -> None:
        cfg = self._Cfg({})
        self.assertEqual(fb.style(cfg), "encouraging")
        self.assertEqual(fb.delay_ms(cfg), 0)
        fb.check_style_config(cfg)

    def test_a_neutral_delay_outside_the_bounds_is_refused(self) -> None:
        for delay in (0, 200, 6000):
            cfg = self._Cfg({"ui": {"feedback_style": "neutral",
                                     "feedback_delay_ms": delay}})
            with self.assertRaises(ValueError) as ctx:
                fb.check_style_config(cfg)
            self.assertIn("500", str(ctx.exception))
            self.assertIn("5000", str(ctx.exception))

    def test_a_neutral_delay_inside_the_bounds_loads(self) -> None:
        cfg = self._Cfg({"ui": {"feedback_style": "neutral",
                                 "feedback_delay_ms": 800}})
        fb.check_style_config(cfg)
        self.assertEqual(fb.style(cfg), "neutral")
        self.assertEqual(fb.delay_ms(cfg), 800)

    def test_an_unknown_style_is_refused(self) -> None:
        cfg = self._Cfg({"ui": {"feedback_style": "cheerful"}})
        with self.assertRaises(ValueError):
            fb.check_style_config(cfg)

    def test_the_lab_preset_is_the_neutral_set(self) -> None:
        import yaml
        with (REPO / "config" / "eeg_lab.yaml").open() as f:
            lab = yaml.safe_load(f)
        self.assertEqual(lab["ui"]["feedback_style"], "neutral")
        self.assertGreaterEqual(lab["ui"]["feedback_delay_ms"], 500)
        self.assertLessEqual(lab["ui"]["feedback_delay_ms"], 5000)
        # No chime and no thunk: both are auditory events inside the
        # feedback window, and the thunk only ever fires on a miss.
        self.assertIs(lab["cue"]["sound_after"], False)

    def test_the_default_config_ships_the_encouraging_style(self) -> None:
        import yaml
        with (REPO / "config" / "default.yaml").open() as f:
            default = yaml.safe_load(f)
        self.assertEqual(default["ui"]["feedback_style"], "encouraging")
        self.assertEqual(default["ui"]["feedback_delay_ms"], 0)


if __name__ == "__main__":
    unittest.main()


class TargetSlotTests(unittest.TestCase):
    """A pool whose caller always passes a finger name must never hold
    a variant that drops it. One such variant in chords' no_hold pool
    made the feedback name a finger only two runs in three, which read
    as a flaky test rather than as the patient losing the one piece of
    information the line carries."""

    def test_every_variant_keeps_the_target(self):
        from finger_rehab.ui import feedback_bank
        bad = []
        checked = 0
        # MODE_LINES is the per-mode table: mode -> situation ->
        # variants. LINE and POPUP are the generic pools and are
        # deliberately allowed to mix (see below).
        tables = [("MODE_LINES", feedback_bank.MODE_LINES)]
        for name, table in tables:
            for key, value in table.items():
                # Only the mode-specific pools are checked. A top-level
                # generic pool is allowed to mix: "Clean press." is a
                # fine thing to say on a hit in a mode that has no one
                # finger to name. The rule bites where the line exists
                # to identify a finger, which is the mode pools.
                if isinstance(value, (tuple, list)):
                    continue
                pools = value
                for situation, variants in pools.items():
                    if not isinstance(variants, (tuple, list)):
                        continue
                    checked += 1
                    uses = [v for v in variants if "{target}" in v]
                    if uses and len(uses) != len(variants):
                        missing = [v for v in variants
                                   if "{target}" not in v]
                        bad.append((name, key, situation, missing))
        # Guard the guard: if the tables are ever restructured so that
        # nothing is checked, this test must fail rather than pass
        # vacuously.
        self.assertGreater(checked, 10, "no mode pools were checked")
        self.assertEqual(bad, [], f"variants drop the finger name: {bad}")
