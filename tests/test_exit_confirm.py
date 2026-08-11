"""Leaving a live game takes a deliberate choice, never a stray Esc.

Esc used to abandon a running block on the spot: partial data was
saved, but one key press ended a patient's game with no way back. Now
Esc from any screen a block runs on raises the End-game dialog: the
block pauses through the normal pause path underneath (no trial ticks
away), Esc or Keep playing backs out and resumes, and only a
deliberate End game (a click on it, or an explicit focus move plus
Enter) walks the existing abandon path, so completed trials are on
disk and the metadata marks the block cut short exactly as before.

The confirm lands on game select, never the login screen: in the
session model a mid-game quit only ends that game, and the session
(with its own End-session warning) lives on game select. The
session-level dialog is covered in test_session_model.py.

All driven headless through the real engine and screens, same as the
pause and keyboard-only navigation tests.
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


def _click_event(pos: tuple[int, int]):
    import pygame
    return pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})


class _EngineHarness(unittest.TestCase):
    """Real engine + real screens, sessions folder in a temp dir."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        self._td = tempfile.TemporaryDirectory()
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = self._td.name
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.eng._screens = self.eng._build_screens()
        self.eng.hand_mode = "right"

    def tearDown(self) -> None:
        import pygame
        # Close any block a failed assertion left open so the raw-
        # logger thread never outlives the test.
        try:
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    # ---- helpers ---------------------------------------------------------

    def _begin_classic(self):
        self.eng.begin_classic_block()
        self.assertIs(self.eng.screen_obj, self.eng._screens["gameplay"])
        self.assertIsNotNone(self.eng.session_paths)
        return self.eng.session_paths

    def _log_one_trial(self) -> None:
        from rehab.game.modes.classic import PendingTrial
        from rehab.game.scoring import TrialResult
        trial = PendingTrial(
            trial_id=1, lane=0, stim_t_perf=time.perf_counter(),
            keys_pressed=[0], incorrect_presses=[])
        self.eng.log_trial(
            trial, TrialResult(label="Great", points=6, rt_ms=180.0),
            now=time.perf_counter())

    def _confirm_via_keyboard(self) -> None:
        """Tab moves focus off Keep playing, Enter fires End game."""
        import pygame
        self.eng._exit_confirm.handle_event(_key_event(pygame.K_TAB))
        self.eng._exit_confirm.handle_event(_key_event(pygame.K_RETURN))


class EscRaisesDialogTests(_EngineHarness):
    def test_esc_mid_block_shows_dialog_and_keeps_the_block(self) -> None:
        paths = self._begin_classic()
        mode = self.eng.mode
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_confirm_active)
        # The dialog asks about THIS game, not the session: a mid-game
        # quit only ends the game, and the session warning lives on
        # game select.
        self.assertEqual(self.eng._exit_confirm.question, "End this game?")
        self.assertEqual(self.eng._exit_confirm.danger_btn.label,
                         "End game")
        # Block untouched underneath: same loggers, same mode, still on
        # the gameplay screen, frozen through the pause path.
        self.assertIs(self.eng.session_paths, paths)
        self.assertIs(self.eng.mode, mode)
        self.assertIs(self.eng.screen_obj, self.eng._screens["gameplay"])
        self.assertTrue(self.eng.paused)

    def test_esc_raises_the_dialog_on_syllables_and_rhythm_too(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        self.eng.begin_syllables_block()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_confirm_active)
        self.eng._confirm_exit_to_menu()
        self.assertFalse(self.eng.exit_confirm_active)

        bm = procedural_beatmap(bpm=110, beats=16, difficulty="easy")
        self.eng.begin_rhythm_block(bm)
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_confirm_active)

    def test_all_block_screen_keys_exist(self) -> None:
        # The scope list must name real screens; a typo here would
        # silently drop a mode out of the exit guard.
        for key in self.eng._BLOCK_SCREEN_KEYS:
            self.assertIn(key, self.eng._screens)


class DismissResumesTests(_EngineHarness):
    def test_esc_again_dismisses_and_resumes_with_state_intact(self) -> None:
        from rehab.game.modes.classic import PendingTrial
        paths = self._begin_classic()
        mode = self.eng.mode
        # Synthesise an in-flight trial so the resume shift is visible.
        t0 = time.perf_counter()
        mode.active = PendingTrial(
            trial_id=1, lane=0, stim_t_perf=t0,
            keys_pressed=[], incorrect_presses=[])
        mode.last_trigger_t = t0
        idx_before = mode.idx
        self.eng._handle_escape()
        time.sleep(0.12)
        self.eng._handle_escape()
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertFalse(self.eng.paused)
        self.assertIs(self.eng.session_paths, paths)
        # Same trial count, and the active trial's clock shifted
        # forward by the dialog time (the pause convention), so it
        # does not instantly time out on resume.
        self.assertEqual(mode.idx, idx_before)
        shift = mode.active.stim_t_perf - t0
        self.assertGreaterEqual(shift, 0.1)
        self.assertLess(shift, 5.0)
        # The dialog counted as exactly one pause in the bookkeeping.
        self.assertEqual(self.eng._block_pause_count, 1)
        self.assertGreaterEqual(self.eng._block_paused_s, 0.1)

    def test_keep_playing_click_resumes(self) -> None:
        self._begin_classic()
        self.eng._handle_escape()
        dlg = self.eng._exit_confirm
        self.eng._exit_confirm.handle_event(
            _click_event(dlg.safe_btn.rect.center))
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertFalse(self.eng.paused)
        self.assertIsNotNone(self.eng.session_paths)

    def test_enter_with_default_focus_keeps_playing(self) -> None:
        import pygame
        self._begin_classic()
        self.eng._handle_escape()
        # Focus starts on the safe button, so a reflex Enter cannot
        # end the session.
        self.assertEqual(self.eng._exit_confirm.focus, 0)
        self.eng._exit_confirm.handle_event(_key_event(pygame.K_RETURN))
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertFalse(self.eng.paused)
        self.assertIsNotNone(self.eng.session_paths)

    def test_dismiss_after_a_deliberate_pause_stays_paused(self) -> None:
        self._begin_classic()
        self.eng._pause_now()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_confirm_active)
        self.eng._handle_escape()
        # The dialog is gone but the player's own pause is not ended
        # for them.
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertTrue(self.eng.paused)


class ConfirmEndsCleanlyTests(_EngineHarness):
    def test_confirm_ends_with_trials_on_disk_and_cut_short_marker(
            self) -> None:
        paths = self._begin_classic()
        self._log_one_trial()
        self.eng._handle_escape()
        self._confirm_via_keyboard()
        # Dialog gone, block closed, back on mode select, not paused.
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIsNone(self.eng.session_paths)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])
        self.assertFalse(self.eng.paused)
        # The completed trial is on disk.
        with paths.trials_csv.open() as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["feedback"], "Great")
        # Metadata records the block as cut short via the existing
        # early-quit path, not a second invention.
        meta = json.loads(paths.metadata_json.read_text())
        self.assertIn("abandoned mid-block", meta["notes"])
        self.assertEqual(meta["block_summary"]["status"], "abandoned")
        # Raw event log holds a matched pause/resume pair for the
        # dialog plus the abandon marker, so the timeline reads whole.
        raw = paths.raw_csv.read_text()
        self.assertIn("pause", raw)
        self.assertIn("resume", raw)
        self.assertIn("block_abandoned", raw)

    def test_confirm_via_mouse_click_on_end_session(self) -> None:
        paths = self._begin_classic()
        dlg_raise = self.eng._handle_escape()
        dlg = self.eng._exit_confirm
        self.assertIsNone(dlg_raise)
        self.eng._exit_confirm.handle_event(
            _click_event(dlg.danger_btn.rect.center))
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIsNone(self.eng.session_paths)
        self.assertTrue(paths.metadata_json.exists())


class DialogModalityTests(_EngineHarness):
    def test_p_key_is_inert_while_the_dialog_is_up(self) -> None:
        import pygame
        self._begin_classic()
        self.eng._handle_escape()
        self.eng._handle_global_event(_key_event(pygame.K_p))
        # P must not resume the block under the card.
        self.assertTrue(self.eng.exit_confirm_active)
        self.assertTrue(self.eng.paused)

    def test_arrow_keys_move_focus_both_ways(self) -> None:
        import pygame
        self._begin_classic()
        self.eng._handle_escape()
        dlg = self.eng._exit_confirm
        self.assertEqual(dlg.focus, 0)
        dlg.handle_event(_key_event(pygame.K_RIGHT))
        self.assertEqual(dlg.focus, 1)
        dlg.handle_event(_key_event(pygame.K_LEFT))
        self.assertEqual(dlg.focus, 0)
        dlg.handle_event(_key_event(pygame.K_TAB))
        self.assertEqual(dlg.focus, 1)


class ResultsNavigationUnaffectedTests(_EngineHarness):
    def test_esc_on_results_between_blocks_needs_no_dialog(self) -> None:
        self._begin_classic()
        self._log_one_trial()
        self.eng.finish_block()
        self.assertIs(self.eng.screen_obj, self.eng._screens["results"])
        self.assertIsNone(self.eng.session_paths)
        self.eng._handle_escape()
        # The block is over and saved; results keeps its one-Esc-to-
        # mode-select navigation with no dialog in the way.
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])


class DialogDrawTests(_EngineHarness):
    def test_dialog_draws_over_the_frozen_screen(self) -> None:
        import pygame
        surf = pygame.display.set_mode((1280, 800))
        self._begin_classic()
        self.eng._handle_escape()
        # Engine draw order: screen first, dialog on top.
        self.eng.screen_obj.draw(surf)
        self.eng._exit_confirm.draw(surf)
        th = self.eng.theme
        # Card centre is the opaque dialog body...
        centre = surf.get_at((640, 400))[:3]
        self.assertEqual(centre, th.background)
        # ...and the field behind it is dimmed, not raw background.
        corner = surf.get_at((10, 700))[:3]
        self.assertNotEqual(corner, th.background)

    def test_paused_overlay_yields_to_the_dialog(self) -> None:
        # While the dialog is up the screens must not stack their own
        # PAUSED layer under it; when the dialog is a plain pause they
        # must still draw it.
        self._begin_classic()
        self.eng._handle_escape()
        self.assertTrue(self.eng.paused)
        self.assertTrue(self.eng.exit_confirm_active)
        gameplay = self.eng._screens["gameplay"]
        # The gate the draw path uses, exactly as written there.
        self.assertFalse(self.eng.paused
                         and not self.eng.exit_confirm_active)
        self.eng._handle_escape()      # dismiss
        self.eng._pause_now()
        self.assertTrue(self.eng.paused
                        and not self.eng.exit_confirm_active)
        self.assertTrue(hasattr(gameplay, "_draw_paused_overlay"))


if __name__ == "__main__":
    unittest.main()
