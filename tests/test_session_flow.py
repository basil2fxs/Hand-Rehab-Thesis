"""Session continuity: the loop between a finished game and the next.

Basil's complaint was that a session read as a stack of unrelated
games -- menu, game, start, back to the menu, nothing carried over,
and an end screen so dense the one number that mattered was buried in
five that did not. Four things close that loop and this file pins all
four:

  1. The end screen shows a headline and at most two supporting
     numbers. The per-mode CHOICES are unchanged and stay research
     driven (median RT for reaction, accuracy rather than RT for
     Muscle Memory); only the density moved. The full read-out is
     behind More detail and every mode test still asserts on it.
  2. NEXT UP suggests one game, prefers one not played this session,
     rotates for variety, and starts it in one press with the hand
     already set -- through engine.begin_game, the same path the hand
     picker takes, so nothing about the block can differ.
  3. The session strip shows what has been played, and its chips come
     from the same log that feeds the End-session dialog's count, so
     the two can never disagree.
  4. Game select can re-run the quick calibration on demand, through
     the same screen and the same continuation the automatic gate
     uses.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _key_event(key: int):
    import pygame
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0})


class _TwoBoardSource:
    """Stand-in for a two-Arduino rig: every mode is playable and both
    hands can be calibrated."""
    provides_samples = True
    is_connected = True
    name = "fake-two-board"
    hand_modes_available = {"right", "left", "both"}


class _OneBoardSource(_TwoBoardSource):
    name = "fake-one-board"
    hand_modes_available = {"right"}


# ---------------------------------------------------------------------
# NEXT UP: which game gets suggested
# ---------------------------------------------------------------------
class NextUpChoiceTests(unittest.TestCase):
    """next_up_mode is pure enough to drive with a stub engine: it
    reads the source (for what is playable) and the session log (for
    what has been played)."""

    class _Eng:
        def __init__(self, source, played=()):
            self.source = source
            self._played = list(played)

        def second_board_missing(self):
            avail = getattr(self.source, "hand_modes_available", None)
            return isinstance(avail, set) and "both" not in avail

        def session_modes_played(self):
            return list(self._played)

    def test_first_suggestion_is_the_first_card(self) -> None:
        from finger_rehab.ui.screens import next_up_mode
        eng = self._Eng(_TwoBoardSource())
        self.assertEqual(next_up_mode(eng, None), "reaction")

    def test_prefers_a_mode_not_played_this_session(self) -> None:
        from finger_rehab.ui.screens import next_up_mode, ModeSelectScreen
        order = [k for k, _t, _d in ModeSelectScreen.MODES]
        # Everything up to and including chords is done; the search
        # starts after the game just played and lands on the first
        # unplayed card it meets.
        played = order[:order.index("chords") + 1]
        eng = self._Eng(_TwoBoardSource(), played)
        suggestion = next_up_mode(eng, "chords")
        self.assertNotIn(suggestion, played)
        self.assertEqual(suggestion, "rhythm")

    def test_it_skips_played_modes_even_when_they_come_first(self) -> None:
        from finger_rehab.ui.screens import next_up_mode
        eng = self._Eng(_TwoBoardSource(), ["reaction", "adaptive"])
        # Just finished buzz_hunt (the last card), so the rotation
        # wraps to the top and has to step over both played modes.
        self.assertEqual(next_up_mode(eng, "buzz_hunt"), "pattern")

    def test_it_rotates_rather_than_repeating_one_card(self) -> None:
        from finger_rehab.ui.screens import next_up_mode
        eng = self._Eng(_TwoBoardSource())
        first = next_up_mode(eng, None)
        eng._played.append(first)
        second = next_up_mode(eng, first)
        self.assertNotEqual(first, second)

    def test_all_played_still_suggests_something_but_not_this_one(
            self) -> None:
        from finger_rehab.ui.screens import next_up_mode, ModeSelectScreen
        order = [k for k, _t, _d in ModeSelectScreen.MODES]
        eng = self._Eng(_TwoBoardSource(), order)
        suggestion = next_up_mode(eng, "rhythm")
        self.assertIsNotNone(suggestion)
        self.assertNotEqual(suggestion, "rhythm")

    def test_never_suggests_a_mode_this_rig_refuses(self) -> None:
        """A suggestion the patient cannot press would be worse than
        no suggestion: the three sensor-only modes need real hardware
        and mirror needs a second board, which is exactly what the
        cards badge before the click."""
        from finger_rehab.ui.screens import next_up_mode, playable_modes
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        keys = self._Eng(KeyboardOnlySource())
        playable = playable_modes(keys)
        for key in ("force_pilot", "lighthouse", "buzz_hunt"):
            self.assertNotIn(key, playable)
        for _ in range(12):
            pick = next_up_mode(keys, None)
            self.assertIn(pick, playable)
            keys._played.append(pick)
        one_board = self._Eng(_OneBoardSource())
        self.assertNotIn("mirror", playable_modes(one_board))


# ---------------------------------------------------------------------
# NEXT UP: the one press
# ---------------------------------------------------------------------
class _EngineHarness(unittest.TestCase):
    """Real engine + real screens, keyboard source, sessions in a temp
    dir. Same shape as the session-model harness."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        self._td = tempfile.TemporaryDirectory()
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = self._td.name
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.eng._screens = self.eng._build_screens()
        self.eng.hand_mode = "right"

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    def _log_one_trial(self) -> None:
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        trial = PendingTrial(
            trial_id=1, lane=0, stim_t_perf=time.perf_counter(),
            keys_pressed=[0], incorrect_presses=[])
        self.eng.log_trial(
            trial, TrialResult(label="Great", points=6, rt_ms=180.0),
            now=time.perf_counter())


class NextUpOnePressTests(_EngineHarness):

    def test_one_press_lands_in_the_suggested_mode_on_the_same_hand(
            self) -> None:
        import pygame
        results = self.eng._screens["results"]
        self.eng.begin_session("Mara", "58")
        self.eng.set_hand_mode("left")
        self.eng.current_block = "reaction"
        self.eng._session_log = [{"mode": "reaction", "hand": "left",
                                  "score": 100, "stars": 3,
                                  "status": "completed"}]
        key, hand = results._next_up_plan()
        self.assertEqual(key, "adaptive")
        self.assertEqual(hand, "left")
        results.handle_event(_key_event(pygame.K_n))
        # A real block is open, in the suggested mode, on the hand the
        # last game used. No hand picker in between.
        self.assertEqual(self.eng.current_block, "adaptive")
        self.assertEqual(self.eng.hand_mode, "left")
        self.assertEqual(self.eng.cfg.get("game.mode"), "adaptive")
        self.assertIsNotNone(self.eng.session_paths)

    def test_mirror_is_suggested_on_both_hands(self) -> None:
        from finger_rehab.ui.screens import ModeSelectScreen
        results = self.eng._screens["results"]
        self.eng.begin_session("Mara", "58")
        self.eng.set_hand_mode("right")
        # Everything except mirror already played, so mirror is the
        # only unplayed card left.
        order = [k for k, _t, _d in ModeSelectScreen.MODES]
        self.eng._session_log = [
            {"mode": k, "hand": "right", "score": 0, "stars": 0,
             "status": "completed"}
            for k in order if k != "mirror"]
        self.eng.current_block = "syllables"
        key, hand = results._next_up_plan()
        self.assertEqual(key, "mirror")
        self.assertEqual(hand, "both", "mirror is bilateral-only")
        results._start_next_up()
        self.assertEqual(self.eng.hand_mode, "both")
        self.assertEqual(self.eng.current_block, "mirror")

    def test_next_up_goes_through_the_shared_start_path(self) -> None:
        """Not a shortcut: the block markers, the GET READY countdown
        and the quick-calibration gate all hang off begin_game, so a
        NEXT UP game and a hand-picked game must be the same call."""
        results = self.eng._screens["results"]
        setup = self.eng._screens["setup"]
        calls = []
        self.eng.begin_game = lambda *a, **k: calls.append((a, k))
        self.eng.current_block = "reaction"
        results._start_next_up()
        self.eng.cfg.data.setdefault("game", {})["mode"] = "chords"
        setup._pick("right")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], (("chords", "right"), {}))

    def test_rhythm_is_suggested_into_its_song_picker(self) -> None:
        """Rhythm has no block to start until a track is chosen, so
        its one press lands on the song screen, which is its prep."""
        self.eng.begin_session("Mara", "58")
        self.eng.begin_game("rhythm", "right")
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["rhythm_setup"])

    def test_a_refused_bilateral_pick_starts_nothing(self) -> None:
        self.eng.source = _OneBoardSource()
        started = self.eng.begin_game("mirror")
        self.assertFalse(started)
        self.assertIsNone(self.eng.session_paths)


# ---------------------------------------------------------------------
# The session strip
# ---------------------------------------------------------------------
class SessionStripTests(_EngineHarness):

    def _play_classic(self) -> None:
        self.eng.begin_classic_block()
        self._log_one_trial()
        self.eng.finish_block()

    def test_the_strip_counts_match_the_logged_games(self) -> None:
        self.eng.begin_session("Mara", "58")
        for _ in range(3):
            self._play_classic()
        rows = self.eng.session_games_log()
        self.assertEqual(len(rows), 3)
        # The End-session dialog's count and the strip's chips are
        # written in the same place, so they cannot drift.
        self.assertEqual(len(rows), self.eng._session_games)
        self.assertEqual(self.eng.session_modes_played(), ["classic"])
        self.assertEqual(self.eng.session_points(),
                         sum(r["score"] for r in rows))
        self.assertEqual(self.eng.session_stars(),
                         sum(r["stars"] for r in rows))

    def test_a_cut_short_game_is_on_the_strip_too(self) -> None:
        """It produced data and took the participant's time, which is
        exactly what _session_games already counts."""
        self.eng.begin_session("Mara", "58")
        self.eng.begin_classic_block()
        self._log_one_trial()
        self.eng._abandon_if_in_block()
        rows = self.eng.session_games_log()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "abandoned")
        self.assertEqual(len(rows), self.eng._session_games)

    def test_the_log_dies_with_the_session(self) -> None:
        self.eng.begin_session("Mara", "58")
        self._play_classic()
        self.assertEqual(len(self.eng.session_games_log()), 1)
        self.eng.end_session()
        self.assertEqual(self.eng.session_games_log(), [])
        self.assertEqual(self.eng.session_points(), 0)
        self.eng.begin_session("Sam", "44")
        self.assertEqual(self.eng.session_games_log(), [])

    def test_stars_use_the_same_bands_as_the_results_grade(self) -> None:
        """The strip's stars are the grade the ring already showed,
        added up. Two independently written band tables would drift,
        so this pins them together."""
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.ui.screens import ResultsScreen
        rs = self.eng._screens["results"]
        for cut, letter in zip(GameEngine.SESSION_STAR_BANDS,
                               ("A", "B", "C")):
            self.assertEqual(rs._grade_for(cut)[0], letter)
        for hits, misses, want in ((19, 1, 3), (8, 2, 2), (6, 4, 1),
                                   (2, 8, 0), (0, 0, 0)):
            self.eng.hits, self.eng.misses = hits, misses
            self.assertEqual(self.eng._session_stars_for_block(), want)
        self.assertIsNotNone(ResultsScreen.RESULTS_TITLE)

    def test_the_strip_draws_a_chip_per_game_played(self) -> None:
        import pygame
        import finger_rehab.ui.screens as screens_mod
        self.eng.begin_session("Mara", "58")
        self.eng._session_log = [
            {"mode": "reaction", "hand": "right", "score": 900,
             "stars": 3, "status": "completed"},
            {"mode": "chords", "hand": "right", "score": 400,
             "stars": 2, "status": "completed"},
        ]
        seen: list[str] = []
        original = screens_mod._strip_pill

        def recorder(surf, layout, left, cy, text, fg, **kw):
            seen.append(text)
            return original(surf, layout, left, cy, text, fg, **kw)

        screens_mod._strip_pill = recorder
        try:
            surf = pygame.Surface((1280, 800))
            screens_mod.draw_session_strip(
                surf, pygame.Rect(40, 132, 1200, 52), self.eng,
                self.eng.theme, self.eng.layout)
        finally:
            screens_mod._strip_pill = original
        self.assertEqual(seen, ["Reaction", "Chords"])

    def test_the_hub_ticks_the_modes_already_played(self) -> None:
        import pygame
        self.eng.begin_session("Mara", "58")
        self.eng._session_log = [
            {"mode": "chords", "hand": "right", "score": 400,
             "stars": 2, "status": "completed"}]
        hub = self.eng._screens["mode_select"]
        ticked: list[int] = []
        hub._draw_done_tick = staticmethod(
            lambda surf, cx, cy, colour: ticked.append(cx))
        hub.draw(pygame.Surface((1280, 800)))
        self.assertEqual(len(ticked), 1)

    def test_the_hub_grid_still_clears_its_buttons(self) -> None:
        hub = self.eng._screens["mode_select"]
        lowest = max(b.rect.bottom for b in hub.buttons)
        self.assertLess(lowest, hub.back_btn.rect.top)
        self.assertLess(lowest, hub.cal_btn.rect.top)
        self.assertGreater(hub.buttons[0].rect.top,
                           hub.STRIP_TOP + 52)
        self.assertFalse(hub.cal_btn.rect.colliderect(
            hub.back_btn.rect))


# ---------------------------------------------------------------------
# Calibrate on demand
# ---------------------------------------------------------------------
class HubCalibrateTests(_EngineHarness):

    def _fake_quick_cal(self):
        calls = []

        class FakeQC:
            def begin(self, hands, continue_cb=None):
                calls.append((list(hands), continue_cb))

        self.eng._screens["quick_cal"] = FakeQC()
        self.eng._ensure_both_detectors = lambda: None
        self.eng.reapply_calibrations = lambda: None
        return calls

    def test_the_button_is_wired_to_the_engine_entry(self) -> None:
        hub = self.eng._screens["mode_select"]
        self.assertEqual(hub.cal_btn.label, "Calibrate")
        self.assertEqual(hub.cal_btn.on_click, hub._calibrate)

    def test_it_re_runs_even_for_a_hand_already_done_this_session(
            self) -> None:
        """The whole point of the button: the automatic gate has
        already covered these hands, and the therapist wants the flow
        again anyway (strap moved, a press stopped registering)."""
        calls = self._fake_quick_cal()
        self.eng.source = _TwoBoardSource()
        self.eng.begin_session("Mara", "58")
        self.eng._session_cal_hands = {"left", "right"}
        self.assertTrue(self.eng.start_manual_calibration())
        self.assertEqual(len(calls), 1)
        self.assertEqual(sorted(calls[0][0]), ["left", "right"])
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["quick_cal"])

    def test_it_goes_through_the_same_screen_the_gate_uses(self) -> None:
        """Capture, threshold maths and the per-hand save must not
        fork: the manual entry hands the same screen the same shape of
        continuation the automatic gate does."""
        calls = self._fake_quick_cal()
        self.eng.source = _TwoBoardSource()
        self.eng.begin_session("Mara", "58")
        self.eng._session_cal_hands = set()
        # Bilateral so the automatic gate covers the same two hands
        # the deliberate button always covers; the seam under both is
        # what this is checking.
        self.eng.hand_mode = "both"
        self.eng.maybe_start_quick_calibration(lambda: None)
        gate_hands, gate_cb = calls[0]
        self.eng.start_manual_calibration()
        manual_hands, manual_cb = calls[1]
        self.assertEqual(sorted(gate_hands), sorted(manual_hands))
        self.assertTrue(callable(gate_cb) and callable(manual_cb))

    def test_finishing_marks_the_hands_and_returns_to_the_hub(
            self) -> None:
        calls = self._fake_quick_cal()
        self.eng.source = _TwoBoardSource()
        self.eng.begin_session("Mara", "58")
        self.eng._session_cal_hands = set()
        self.eng.start_manual_calibration()
        _hands, continue_cb = calls[0]
        continue_cb()
        self.assertEqual(self.eng._session_cal_hands, {"left", "right"})
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])
        # Session-once is unchanged: the next game asks for nothing.
        self.eng.hand_mode = "right"
        self.assertEqual(self.eng.quick_cal_hands_needed(), [])

    def test_one_board_calibrates_only_the_hand_it_serves(self) -> None:
        calls = self._fake_quick_cal()
        self.eng.source = _OneBoardSource()
        self.eng.begin_session("Mara", "58")
        self.eng.start_manual_calibration()
        self.assertEqual(calls[0][0], ["right"])

    def test_a_keyboard_session_says_why_instead_of_opening_it(
            self) -> None:
        calls = self._fake_quick_cal()
        hub = self.eng._screens["mode_select"]
        self.assertEqual(self.eng.calibratable_hands(), [])
        self.assertFalse(self.eng.start_manual_calibration())
        hub._calibrate()
        self.assertEqual(calls, [])
        self.assertIn("sensor", hub.cal_note.lower())

    def test_c_calibrates_from_the_keyboard(self) -> None:
        import pygame
        calls = self._fake_quick_cal()
        self.eng.source = _TwoBoardSource()
        self.eng.begin_session("Mara", "58")
        hub = self.eng._screens["mode_select"]
        hub.handle_event(_key_event(pygame.K_c))
        self.assertEqual(len(calls), 1)


# ---------------------------------------------------------------------
# The slim end screen
# ---------------------------------------------------------------------
# One plausible block summary per mode, enough for that mode's branch
# to fire, plus the label its headline card must carry. The label
# choices are the ones the mode tests already defend; this only pins
# that the SLIM view keeps them as the headline.
_MODE_CASES = {
    "reaction": ({"reaction": {"median_rt_ms": 262.0, "p10_rt_ms": 208.0,
                               "accuracy": 0.94}}, "MEDIAN RT"),
    "pattern": ({"pattern": {"three_star_streak_best": 3,
                             "per_take": [{"kind": "seq", "n": 60,
                                           "accuracy": 0.9}]}},
                "ACCURACY"),
    "chords": ({"chords": {"chord_outcome_classes": {"hit": 30,
                                                     "late_chord": 30},
                           "median_er": 0.1, "level_highest": 4,
                           "over_force_trials": 0}}, "CLEAN HIT RATE"),
    "syllables": ({"syllables": {"level": 3, "accuracy": 0.8,
                                 "band_final": "B",
                                 "asyn_mean_ms": 20.0,
                                 "asyn_sd_ms": 35.0}}, "WORDS CORRECT"),
    "mirror": ({"mirror": {"mean_gap_ms": 44.0,
                           "right_hand_mean_rt_ms": 300.0,
                           "left_hand_mean_rt_ms": 320.0}}, "SYNC GAP"),
    "adaptive": ({"bpm_final": 74.0, "bpm_max": 88.0}, "TOP PACE"),
    "force_pilot": ({"force_pilot": {
        "runs": 4,
        "levels": {"right:0": {"final": 1}},
        "per_lane": {"0": {"mae_pct": 4.0, "time_in_corridor": 0.9}},
        "overall": {"mae_pct": 3.5, "time_in_corridor": 0.75,
                    "stalls": 0},
        "best_section": "sine"}}, "IN CORRIDOR"),
    "lighthouse": ({"lighthouse": {
        "levels": {"trace": [1, 1]},
        "per_lane": {"0": {"lit_cov": 0.1, "delta_pct": 2.0}},
        "overall": {"lit_cov": 0.12, "dark_drift_pct": 3.0,
                    "lit_dark_delta_pct": 2.0},
        "echo": {"overall": {"abs_err_pct": 1.1}}}}, "LIT VS DARK"),
    "buzz_hunt": ({"buzz_hunt": {
        "hands": ["right"],
        "loc": {"accuracy": 0.9, "catch": {"false_alarms": 0},
                "per_lane": {}},
        "threshold": {"right": {"estimate_ms": 120.0,
                                "n_reversals": 6}},
        "span": {"max_correct": 4},
        "gap": {"threshold": {}}}}, "LOCALISATION"),
    "classic": ({}, "SCORE"),
    "rhythm": ({}, "SCORE"),
}


class SlimEndScreenTests(unittest.TestCase):
    """The finished screen is a headline plus at most two supporting
    numbers, for every mode. Everything else the block measured is
    still computed (the mode tests assert on the full list) and is one
    press away behind More detail."""

    def _results(self, block: str, summary: dict):
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
        e.hits, e.misses, e.score = 41, 5, 1840
        e.current_block, e.hand_mode = block, "right"
        e.best_streak, e.per_lane_stats, e.hit_streak = 9, {}, 9
        e.last_session_root = None
        e.mode = None
        e.source = _TwoBoardSource()
        e._per_lane_rts = {0: [280.0]}
        e._per_lane_misses = {1: 1}
        e._per_lane_wrong = {}
        e._session_log = [{"mode": block, "hand": "right", "score": 1840,
                           "stars": 3, "status": "completed"}]
        e.session = type("S", (), {"participant": "T", "age": "60",
                                   "hand": "right",
                                   "block_summary": summary})()
        e.stop_all_motors = lambda *a, **k: None
        e.overall_mean_rt = lambda: 298.5
        e.overall_best_rt = lambda: 202.4
        r = ResultsScreen(e)
        r._shown_t = 1.0
        return r, e

    def _draw(self, r):
        import pygame
        cards, charts = [], []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col, **kw:
            cards.append((lbl, val)))
        r._draw_per_lane_chart = (
            lambda surf, rect, title, *a, **k: charts.append(title))
        r.draw(pygame.Surface((1280, 800)))
        return cards, charts

    def test_every_mode_renders_a_headline_and_at_most_two_more(
            self) -> None:
        import pygame
        try:
            for block, (summary, headline) in _MODE_CASES.items():
                with self.subTest(block=block):
                    r, _e = self._results(block, summary)
                    cards, charts = self._draw(r)
                    self.assertTrue(cards, f"{block} drew no numbers")
                    self.assertLessEqual(
                        len(cards), 3,
                        f"{block} still shows a wall of {len(cards)}")
                    self.assertTrue(
                        cards[0][0].startswith(headline),
                        f"{block} headline is {cards[0][0]!r}, "
                        f"expected {headline!r}")
                    self.assertEqual(
                        charts, [],
                        f"{block} still draws per-finger charts on the "
                        "finished screen")
        finally:
            pygame.quit()

    def test_the_full_read_out_is_one_press_away(self) -> None:
        import pygame
        try:
            for block, (summary, _headline) in _MODE_CASES.items():
                with self.subTest(block=block):
                    r, _e = self._results(block, summary)
                    slim, _ = self._draw(r)
                    r._toggle_details()
                    full, _ = self._draw(r)
                    self.assertGreaterEqual(len(full), len(slim))
                    slim_labels = [lbl for lbl, _v in slim]
                    full_labels = [lbl for lbl, _v in full]
                    for lbl in slim_labels:
                        self.assertIn(lbl, full_labels)
        finally:
            pygame.quit()

    def test_the_headline_is_the_first_card_drawn(self) -> None:
        """Order matters: the headline card is drawn wider and with a
        larger number, so it has to be index 0 of the slim list."""
        import pygame
        try:
            r, _e = self._results("reaction", _MODE_CASES["reaction"][0])
            full = r._stat_cards(1.0)
            slim = r._slim_cards(full)
            self.assertEqual(slim[0][0], "MEDIAN RT")
            self.assertLessEqual(len(slim), 3)
        finally:
            pygame.quit()

    def test_details_folds_away_when_a_new_game_lands(self) -> None:
        import pygame
        try:
            r, _e = self._results("classic", {})
            r._toggle_details()
            self.assertTrue(r.show_details)
            r.on_show()
            self.assertFalse(r.show_details)
            self.assertEqual(r.detail_btn.label, "More detail")
        finally:
            pygame.quit()

    def test_d_toggles_detail_and_enter_still_retries(self) -> None:
        import pygame
        try:
            r, e = self._results("classic", {})
            retried = []
            e.retry_last_block = lambda: retried.append(True)
            r.handle_event(_key_event(pygame.K_d))
            self.assertTrue(r.show_details)
            r.handle_event(_key_event(pygame.K_d))
            self.assertFalse(r.show_details)
            r.handle_event(_key_event(pygame.K_RETURN))
            self.assertEqual(retried, [True])
        finally:
            pygame.quit()

    def test_the_slim_screen_keeps_its_furniture_on_screen(self) -> None:
        import pygame
        try:
            r, _e = self._results("reaction", _MODE_CASES["reaction"][0])
            card = pygame.Rect(*r.NEXT_CARD_RECT)
            strip = pygame.Rect(*r.SLIM_STRIP_RECT)
            self.assertTrue(card.contains(r.next_btn.rect))
            self.assertLess(card.bottom, strip.top)
            for btn in (r.retry_btn, r.again_btn, r.folder_btn,
                        r.detail_btn, r.title_btn):
                self.assertLessEqual(btn.rect.bottom, 800)
                self.assertGreater(btn.rect.top, strip.bottom)
                self.assertFalse(btn.rect.colliderect(card))
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
