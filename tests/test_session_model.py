"""Basil's session model, end to end and headless.

Boot lands on the login screen: name and age typed once. LOG IN opens
game select, the session's home base. Every game's natural end and
every mid-game quit come back to game select with that game's files
closed; the logged-in identity never gets re-asked. The only place the
session-ending warning lives is leaving game select for the login
screen, and its confirm finalises the session (summary logged, EEG 241
sent, identity cleared) so the next player logs in fresh.

The data rule under all of it: every exit path (mid-game double Esc,
natural end, window close, session end) leaves trials.csv, raw.csv and
metadata.json complete on disk. Driven through the real engine and the
real screens, sessions folder in a temp dir.
"""
from __future__ import annotations

import csv
import json
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


class _SessionHarness(unittest.TestCase):
    """Real engine + real screens on the keyboard source. EEG runs the
    dummy backend so the session markers are observable on the wire."""

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
        cfg.data["eeg"] = {"enabled": True, "port": None,
                           "require_port": False,
                           "pulse_ms": 2, "gap_ms": 2}
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

    # ---- helpers ---------------------------------------------------------

    def _login(self, name: str = "P1", age: str = "63") -> None:
        self.eng.begin_session(name, age)

    def _play_one_game(self):
        """One classic block, one logged trial, natural finish."""
        self.eng.begin_classic_block()
        paths = self.eng.session_paths
        self._log_one_trial()
        self.eng.finish_block()
        return paths

    def _log_one_trial(self) -> None:
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        trial = PendingTrial(
            trial_id=1, lane=0, stim_t_perf=time.perf_counter(),
            keys_pressed=[0], incorrect_presses=[])
        self.eng.log_trial(
            trial, TrialResult(label="Great", points=6, rt_ms=180.0),
            now=time.perf_counter())

    def _wire_codes(self) -> list[int]:
        self.eng.markers.drain(0.3)
        return [c for _, c in self.eng.markers.backend.written if c != 0]

    def _confirm_dialog(self) -> None:
        """Keyboard-only confirm: Tab off the safe button, Enter."""
        import pygame
        self.eng._exit_confirm.handle_event(_key_event(pygame.K_TAB))
        self.eng._exit_confirm.handle_event(_key_event(pygame.K_RETURN))


class LoginFlowTests(_SessionHarness):
    def test_login_sets_identity_and_lands_on_game_select(self) -> None:
        self._login("Mara", "58")
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])
        self.assertEqual(self.eng.session.participant, "Mara")
        self.assertEqual(self.eng.session.age, "58")
        self.assertTrue(self.eng._session_active)

    def test_title_screen_login_button_commits_name_and_age(self) -> None:
        ts = self.eng._screens["title"]
        ts.name_input.text = "Mara"
        ts.age_input.text = "58"
        ts._begin()
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "Mara")
        self.assertEqual(self.eng.cfg.get("session.age"), "58")
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])

    def test_age_lands_in_the_saved_metadata(self) -> None:
        self._login("Mara", "58")
        paths = self._play_one_game()
        meta = json.loads(paths.metadata_json.read_text())
        self.assertEqual(meta["participant"], "Mara")
        self.assertEqual(meta["age"], "58")


class GameSelectHomeBaseTests(_SessionHarness):
    def test_natural_end_returns_towards_game_select_with_files_closed(
            self) -> None:
        self._login()
        paths = self._play_one_game()
        # Results first, then Play again goes home without re-asking
        # anything.
        self.assertIs(self.eng.screen_obj, self.eng._screens["results"])
        self.assertIsNone(self.eng.session_paths)
        self.eng.show_mode_select()
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])
        self.assertEqual(self.eng.session.participant, "P1")
        self.assertTrue(self.eng._session_active)
        meta = json.loads(paths.metadata_json.read_text())
        self.assertEqual(meta["notes"], "block completed")
        with paths.trials_csv.open() as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)

    def test_mid_game_double_esc_lands_on_game_select_session_intact(
            self) -> None:
        # Mid-game exit is the light guard: first Esc raises the chip,
        # second Esc inside its window ends the game. No modal here;
        # the session keeps its own dialog on game select.
        self._login()
        self.eng.begin_classic_block()
        paths = self.eng.session_paths
        self._log_one_trial()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        self.eng._handle_escape()
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])
        # The session survives the quit: same identity, still logged
        # in, and the cut-short game counted.
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "P1")
        self.assertEqual(self.eng._session_games, 1)
        meta = json.loads(paths.metadata_json.read_text())
        self.assertIn("abandoned mid-block", meta["notes"])
        with paths.trials_csv.open() as f:
            self.assertEqual(len(list(csv.DictReader(f))), 1)
        self.assertIn("block_abandoned", paths.raw_csv.read_text())

    def test_second_game_runs_under_the_same_identity(self) -> None:
        self._login("Mara", "58")
        first = self._play_one_game()
        self.eng.show_mode_select()
        second = self._play_one_game()
        self.assertNotEqual(first.root, second.root)
        for paths in (first, second):
            meta = json.loads(paths.metadata_json.read_text())
            self.assertEqual(meta["participant"], "Mara")
            self.assertEqual(meta["age"], "58")


class WindowCloseTests(_SessionHarness):
    def test_window_close_mid_game_saves_everything(self) -> None:
        import pygame
        self._login()
        self.eng.begin_classic_block()
        paths = self.eng.session_paths
        self._log_one_trial()
        self.eng._handle_global_event(pygame.event.Event(pygame.QUIT, {}))
        self.assertFalse(self.eng.running)
        self.assertIsNone(self.eng.session_paths)
        with paths.trials_csv.open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["feedback"], "Great")
        meta = json.loads(paths.metadata_json.read_text())
        self.assertIn("abandoned mid-block", meta["notes"])
        self.assertEqual(meta["block_summary"]["status"], "abandoned")
        self.assertIn("block_abandoned", paths.raw_csv.read_text())


class SessionEndDialogTests(_SessionHarness):
    def test_dialog_carries_the_session_summary(self) -> None:
        self._login()
        self._play_one_game()
        self.eng.show_mode_select()
        self._play_one_game()
        self.eng.show_mode_select()
        self.eng.request_end_session()
        dlg = self.eng._exit_confirm
        self.assertIsNotNone(dlg)
        self.assertEqual(dlg.question, "End this session?")
        self.assertIn("2 games played", dlg.detail)
        self.assertIn("min", dlg.detail)
        self.assertEqual(dlg.safe_btn.label, "Stay")
        self.assertEqual(dlg.danger_btn.label, "End session")

    def test_confirm_finalises_and_returns_to_login(self) -> None:
        self._login("Mara", "58")
        first = self._play_one_game()
        self.eng.show_mode_select()
        self.eng.request_end_session()
        self._confirm_dialog()
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["title"])
        self.assertFalse(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "NA")
        self.assertEqual(self.eng.session.age, "")
        self.assertIsNone(self.eng.cfg.get("session.participant"))
        # The finished game's record is untouched by the session close.
        meta = json.loads(first.metadata_json.read_text())
        self.assertEqual(meta["notes"], "block completed")
        self.assertEqual(meta["participant"], "Mara")

    def test_dismiss_keeps_the_session_open(self) -> None:
        self._login()
        self.eng.request_end_session()
        self.assertTrue(self.eng.exit_confirm_active)
        self.eng._handle_escape()      # Esc backs out of the dialog
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["mode_select"])
        self.assertTrue(self.eng._session_active)
        self.assertEqual(self.eng.session.participant, "P1")

    def test_results_and_game_select_buttons_route_via_the_warning(
            self) -> None:
        # Both screens' exit buttons go through request_end_session,
        # never straight to show_title: the warning cannot be skipped
        # by leaving from the results screen instead.
        results = self.eng._screens["results"]
        select = self.eng._screens["mode_select"]
        self.assertEqual(results.title_btn.label, "End session")
        self.assertEqual(results.title_btn.on_click,
                         self.eng.request_end_session)
        self.assertEqual(select.back_btn.label, "End session")
        self.assertEqual(select.back_btn.on_click,
                         self.eng.request_end_session)


class SessionCarryStateTests(_SessionHarness):
    """State a mode parks on the engine for the session (difficulty
    levels, personal bests, fatigue baselines, applied calibration)
    must die with the session. The end-session dialog promises "the
    next player logs in fresh"; before this was pinned, patient B's
    first reaction block opened at patient A's level with A's best RT
    as the on-screen target, and B's first block reported a fatigue
    slope computed from A's blocks."""

    CARRY_ATTRS = ("_reaction_level", "_reaction_clean_blocks",
                   "_reaction_best_ms", "_force_pilot_levels",
                   "_lighthouse_level", "_buzz_hunt_start_ms")

    def _plant_carry_state(self) -> None:
        self.eng._reaction_level = 3
        self.eng._reaction_clean_blocks = 1
        self.eng._reaction_best_ms = {("choice", "right"): 145.0}
        self.eng._force_pilot_levels = {("right", 1): 3}
        self.eng._lighthouse_level = 3
        self.eng._buzz_hunt_start_ms = {"right": 60.0}
        self.eng._across_blocks_mean_rt = [400.0, 350.0]
        self.eng._across_blocks_mean_peak = [120.0]

    def test_end_session_clears_every_mode_carry(self) -> None:
        self._login("PatientA", "60")
        self._plant_carry_state()
        self.eng.show_mode_select()
        self.eng.request_end_session()
        self._confirm_dialog()
        for attr in self.CARRY_ATTRS:
            self.assertIsNone(getattr(self.eng, attr, None), attr)
        self.assertEqual(self.eng._across_blocks_mean_rt, [])
        self.assertEqual(self.eng._across_blocks_mean_peak, [])

    def test_login_clears_leftovers_from_an_abnormal_end(self) -> None:
        # Belt and braces: even if a session never reached end_session
        # (crash path, test harness), a login must start clean.
        self._plant_carry_state()
        self._login("PatientB", "72")
        for attr in self.CARRY_ATTRS:
            self.assertIsNone(getattr(self.eng, attr, None), attr)
        self.assertEqual(self.eng._across_blocks_mean_rt, [])

    def test_end_session_drops_applied_calibration_profiles(self) -> None:
        # A leftover in-memory profile would normalise the next
        # patient's force quantities by this patient's light-press
        # gaps if they skip the quick flow.
        from finger_rehab.hardware.calibration_profile import (
            CalibrationProfile)
        self._login("PatientA", "60")
        self.eng.calibration_profiles = {
            "right": CalibrationProfile(hand="right",
                                        participant="PatientA")}
        self.eng.show_mode_select()
        self.eng.request_end_session()
        self._confirm_dialog()
        self.assertEqual(self.eng.calibration_profiles, {})
        self.assertIsNone(self.eng.calibration_profile)

    def test_next_patient_reaction_block_opens_at_level_one(self) -> None:
        self._login("PatientA", "60")
        self._plant_carry_state()
        self.eng.show_mode_select()
        self.eng.request_end_session()
        self._confirm_dialog()
        self._login("PatientB", "72")
        self.eng.begin_reaction_block()
        mode = self.eng.mode
        try:
            self.assertEqual(mode.level, 1)
            self.assertIsNone(mode.session_best_ms())
        finally:
            self.eng._abandon_if_in_block()


class EegSessionBoundaryTests(_SessionHarness):
    """240/241 bracket the login, not the app process."""

    def test_login_sends_240_and_session_end_sends_241_once(self) -> None:
        self.assertEqual(self._wire_codes(), [])   # boot sends nothing
        self._login()
        self.assertIn(240, self._wire_codes())
        self.eng.request_end_session()
        self.eng._confirm_end_session()
        codes = self._wire_codes()
        self.assertEqual(codes.count(241), 1)
        # App shutdown after a closed session must not double-fire.
        # Hold the backend: close() drops the writer's reference.
        backend = self.eng.markers.backend
        self.eng._eeg_shutdown()
        codes = [c for _, c in backend.written if c != 0]
        self.assertEqual(codes.count(241), 1)

    def test_app_quit_mid_session_still_closes_the_pair(self) -> None:
        self._login()
        backend = self.eng.markers.backend
        self.eng._eeg_shutdown()
        codes = [c for _, c in backend.written if c != 0]
        self.assertEqual(codes.count(240), 1)
        self.assertEqual(codes.count(241), 1)

    def test_two_logins_make_two_pairs(self) -> None:
        self._login("A", "")
        self.eng.request_end_session()
        self.eng._confirm_end_session()
        self._login("B", "")
        self.eng.request_end_session()
        self.eng._confirm_end_session()
        codes = self._wire_codes()
        self.assertEqual([c for c in codes if c in (240, 241)],
                         [240, 241, 240, 241])


class ResultsWordingTests(_SessionHarness):
    """The results screen closes a GAME, not the session. Its header
    used to say "Session complete", which contradicted the session
    model (the player is still logged in and lands back on game
    select) and the Play again / End session buttons under it."""

    def test_results_header_never_claims_the_session_ended(self) -> None:
        from finger_rehab.ui.screens import ResultsScreen
        title = ResultsScreen.RESULTS_TITLE
        self.assertNotIn("session", title.lower())
        self.assertIn("game", title.lower())

    def test_setup_subtitle_asks_about_this_game_not_the_session(
            self) -> None:
        """The hand is picked fresh on every pass through setup; the
        old subtitle said "this session", implying the pick was locked
        in for every game."""
        import pygame
        from finger_rehab.ui import screens as screens_mod
        self._login()
        captured = []
        real = screens_mod._draw_header

        def spy(surf, title, subtitle, *a, **kw):
            captured.append(subtitle)
            return real(surf, title, subtitle, *a, **kw)

        screens_mod._draw_header = spy
        try:
            self.eng._screens["setup"].draw(pygame.Surface((1280, 800)))
        finally:
            screens_mod._draw_header = real
        self.assertTrue(captured)
        self.assertNotIn("session", captured[0].lower())
        self.assertIn("game", captured[0].lower())

    def test_results_header_renders_after_a_finished_game(self) -> None:
        import pygame
        self._login()
        self._play_one_game()
        self.eng.show_results()
        surf = pygame.Surface((1280, 800))
        # Draw must go through without touching the old hard-coded
        # string; a crash here means the title refactor regressed.
        self.eng.screen_obj.draw(surf)


class BlockStartMetadataTests(_SessionHarness):
    """The 'block in progress' metadata.json written at block start
    must describe THIS block only. It used to carry the PREVIOUS
    block's block_summary (status 'completed', another mode's
    aggregates, even another patient's calibration and eeg stamps),
    so a hard kill left a wrong but plausible forensic record."""

    def test_initial_autosave_never_carries_the_previous_block(
            self) -> None:
        import json
        self._login("Alice", "60")
        self._play_one_game()          # classic, completed
        self.eng.end_session()
        self._login("Bob", "72")
        self.eng.begin_reaction_block()
        meta = json.loads(
            (self.eng.session_paths.root / "metadata.json").read_text())
        self.assertEqual(meta["participant"], "Bob")
        summary = meta.get("block_summary") or {}
        self.assertEqual(summary.get("block"), "reaction")
        self.assertEqual(summary.get("status"), "in_progress")
        self.assertNotIn("final_score", summary)
        self.eng.finish_block()


if __name__ == "__main__":
    unittest.main()
