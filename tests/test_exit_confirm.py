"""Leaving a live game is light; leaving the session is heavy.

Mid-game Esc used to raise a modal dialog. That was the right weight
for ending a SESSION but too much ceremony for ending one game of
many: the session model made game select the home base, so backing
out of a game is ordinary navigation. Esc now runs a double-press
guard instead: the first Esc pauses the block through the normal
pause path and shows a small chip ("Esc again to end this game -
press any key to keep playing") for about two seconds; a second Esc
inside that window ends the game through the existing abandon path
(completed trials on disk, metadata marked cut short, straight back
to game select); any other key, a click, or the timeout dismisses the
chip and resumes. No modal, no mouse target to hunt.

The heavy exit is unchanged: leaving game select for the login screen
still raises the full "End this session?" dialog, covered in
test_session_model.py and asserted unchanged here.

The guard must be provably pause-safe: no trial ticks away under the
chip, in-flight timestamps shift forward on resume, and the EEG
pause/resume markers bracket the chip exactly as they did the modal.

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
    """Real engine + real screens, sessions folder in a temp dir. EEG
    runs the dummy backend so pause/resume markers are observable."""

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
        cfg.data["eeg"] = {"enabled": True, "port": None,
                           "require_port": False,
                           "pulse_ms": 2, "gap_ms": 2}
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


class EscRaisesChipTests(_EngineHarness):
    def test_esc_mid_block_shows_chip_and_keeps_the_block(self) -> None:
        paths = self._begin_classic()
        mode = self.eng.mode
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        # A chip, not a modal: no dialog object exists, so there is no
        # mouse target to hunt and no button to mis-click. The session
        # dialog slot stays empty.
        self.assertIsNone(self.eng._exit_confirm)
        # Block untouched underneath: same loggers, same mode, still on
        # the gameplay screen, frozen through the pause path.
        self.assertIs(self.eng.session_paths, paths)
        self.assertIs(self.eng.mode, mode)
        self.assertIs(self.eng.screen_obj, self.eng._screens["gameplay"])
        self.assertTrue(self.eng.paused)

    def test_chip_window_is_about_two_seconds(self) -> None:
        self._begin_classic()
        before = time.perf_counter()
        self.eng._handle_escape()
        remaining = self.eng._exit_chip_until - before
        self.assertGreaterEqual(remaining, 1.5)
        self.assertLessEqual(remaining, 3.0)

    def test_esc_raises_the_chip_on_syllables_and_rhythm_too(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        self.eng.begin_syllables_block()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        self.eng._handle_escape()
        self.assertFalse(self.eng.exit_chip_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])

        bm = procedural_beatmap(bpm=110, beats=16, difficulty="easy")
        self.eng.begin_rhythm_block(bm)
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)

    def test_all_block_screen_keys_exist(self) -> None:
        # The scope list must name real screens; a typo here would
        # silently drop a mode out of the exit guard.
        for key in self.eng._BLOCK_SCREEN_KEYS:
            self.assertIn(key, self.eng._screens)


class DismissResumesTests(_EngineHarness):
    def test_any_key_dismisses_and_resumes_with_state_intact(self) -> None:
        import pygame
        from finger_rehab.game.modes.classic import PendingTrial
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
        self.eng._handle_global_event(_key_event(pygame.K_a))
        self.assertFalse(self.eng.exit_chip_active)
        self.assertFalse(self.eng.paused)
        self.assertIs(self.eng.session_paths, paths)
        # Same trial count, and the active trial's clock shifted
        # forward by the chip time (the pause convention), so it does
        # not instantly time out on resume.
        self.assertEqual(mode.idx, idx_before)
        shift = mode.active.stim_t_perf - t0
        self.assertGreaterEqual(shift, 0.1)
        self.assertLess(shift, 5.0)
        # The chip counted as exactly one pause in the bookkeeping.
        self.assertEqual(self.eng._block_pause_count, 1)
        self.assertGreaterEqual(self.eng._block_paused_s, 0.1)

    def test_timeout_dismisses_and_resumes(self) -> None:
        self._begin_classic()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        # Before the window ends the tick is a no-op.
        self.eng._tick_exit_chip(time.perf_counter())
        self.assertTrue(self.eng.exit_chip_active)
        # The frame after the deadline dismisses and resumes.
        self.eng._tick_exit_chip(self.eng._exit_chip_until + 0.001)
        self.assertFalse(self.eng.exit_chip_active)
        self.assertFalse(self.eng.paused)
        self.assertIsNotNone(self.eng.session_paths)

    def test_mouse_click_dismisses_and_resumes(self) -> None:
        self._begin_classic()
        self.eng._handle_escape()
        self.eng._handle_global_event(_click_event((640, 400)))
        self.assertFalse(self.eng.exit_chip_active)
        self.assertFalse(self.eng.paused)
        self.assertIsNotNone(self.eng.session_paths)

    def test_dismiss_after_a_deliberate_pause_stays_paused(self) -> None:
        import pygame
        self._begin_classic()
        self.eng._pause_now()
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        self.eng._handle_global_event(_key_event(pygame.K_a))
        # The chip is gone but the player's own pause is not ended
        # for them.
        self.assertFalse(self.eng.exit_chip_active)
        self.assertTrue(self.eng.paused)

    def test_eeg_pause_and_resume_markers_bracket_the_chip(self) -> None:
        """Same wire contract the modal kept: raising the guard fires
        the pause code, dismissing it fires the resume code, exactly
        once each."""
        import pygame
        from finger_rehab.hardware.eeg_trigger import CODES
        self._begin_classic()
        before = self._wire_codes()
        self.eng._handle_escape()
        self.eng._handle_global_event(_key_event(pygame.K_a))
        after = self._wire_codes()
        new = after[len(before):]
        self.assertEqual(new.count(CODES["pause"]), 1)
        self.assertEqual(new.count(CODES["resume"]), 1)
        self.assertLess(new.index(CODES["pause"]),
                        new.index(CODES["resume"]))


class SecondEscEndsCleanlyTests(_EngineHarness):
    def test_second_esc_ends_with_trials_on_disk_and_cut_short_marker(
            self) -> None:
        paths = self._begin_classic()
        self._log_one_trial()
        self.eng._handle_escape()
        self.eng._handle_escape()
        # Chip gone, block closed, back on game select, not paused.
        self.assertFalse(self.eng.exit_chip_active)
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
        # chip plus the abandon marker, so the timeline reads whole.
        raw = paths.raw_csv.read_text()
        self.assertIn("pause", raw)
        self.assertIn("resume", raw)
        self.assertIn("block_abandoned", raw)

    def test_esc_after_the_window_expires_only_re_arms_the_guard(
            self) -> None:
        self._begin_classic()
        self.eng._handle_escape()
        self.eng._tick_exit_chip(self.eng._exit_chip_until + 0.001)
        self.assertFalse(self.eng.exit_chip_active)
        # The window is gone, so this Esc is a first press again: it
        # raises a fresh chip and must not end anything.
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_chip_active)
        self.assertIsNotNone(self.eng.session_paths)
        self.assertIs(self.eng.screen_obj, self.eng._screens["gameplay"])


class ChipConsumesInputTests(_EngineHarness):
    def test_p_key_dismisses_instead_of_toggling_pause(self) -> None:
        # "Press any key to keep playing" includes P: one press, one
        # state change. The chip's dismiss resumes; the P handler must
        # not also run and re-pause on the same event.
        import pygame
        self._begin_classic()
        self.eng._handle_escape()
        self.assertTrue(self.eng.paused)
        self.eng._handle_global_event(_key_event(pygame.K_p))
        self.assertFalse(self.eng.exit_chip_active)
        self.assertFalse(self.eng.paused)

    def test_mainloop_gate_swallows_the_dismissing_event(self) -> None:
        # The run() loop delivers an event to the screen only when
        # neither guard owned it. Recreate that gate for the frame the
        # chip is dismissed on: the flag read BEFORE the global
        # handler must mark the event as the chip's.
        import pygame
        self._begin_classic()
        self.eng._handle_escape()
        e = _key_event(pygame.K_a)
        exit_chip_had_event = self.eng._exit_chip_until is not None
        self.eng._handle_global_event(e)
        self.assertTrue(exit_chip_had_event)
        # Gate order: dialog branch, chip branch, then the screen.
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertTrue(exit_chip_had_event
                        or self.eng._exit_chip_until is not None)


class SessionModalUnchangedTests(_EngineHarness):
    def test_leaving_game_select_still_raises_the_full_dialog(self) -> None:
        # The heavy exit keeps its modal exactly where it was: game
        # select -> login. The chip exists only mid-block.
        self.eng.begin_session("P1", "")
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])
        self.eng._handle_escape()
        self.assertTrue(self.eng.exit_confirm_active)
        self.assertFalse(self.eng.exit_chip_active)
        dlg = self.eng._exit_confirm
        self.assertEqual(dlg.question, "End this session?")
        self.assertEqual(dlg.safe_btn.label, "Stay")
        self.assertEqual(dlg.danger_btn.label, "End session")
        # Esc still backs out of it, never through it.
        self.eng._handle_escape()
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])


class ResultsNavigationUnaffectedTests(_EngineHarness):
    def test_esc_on_results_between_blocks_needs_no_guard(self) -> None:
        self._begin_classic()
        self._log_one_trial()
        self.eng.finish_block()
        self.assertIs(self.eng.screen_obj, self.eng._screens["results"])
        self.assertIsNone(self.eng.session_paths)
        self.eng._handle_escape()
        # The block is over and saved; results keeps its one-Esc-to-
        # mode-select navigation with no chip in the way.
        self.assertFalse(self.eng.exit_chip_active)
        self.assertFalse(self.eng.exit_confirm_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])


class ChipDrawTests(_EngineHarness):
    def test_chip_draws_over_the_frozen_screen(self) -> None:
        import pygame
        surf = pygame.display.set_mode((1280, 800))
        self._begin_classic()
        self.eng._handle_escape()
        # Engine draw order: screen first, chip on top.
        self.eng.screen_obj.draw(surf)
        self.eng._draw_exit_chip(surf)
        th = self.eng.theme
        # Chip card body is opaque background at its centre...
        centre = surf.get_at((640, 110))[:3]
        self.assertEqual(centre, th.background)
        # ...and unlike the old modal there is NO full-screen dim: the
        # field below the chip is whatever the frozen screen drew.
        self.eng.screen_obj.draw(surf)
        clean = surf.get_at((10, 700))[:3]
        self.eng._draw_exit_chip(surf)
        self.assertEqual(surf.get_at((10, 700))[:3], clean)

    def test_chip_draws_on_syllables_too(self) -> None:
        import pygame
        surf = pygame.display.set_mode((1280, 800))
        self.eng.begin_syllables_block()
        self.eng._handle_escape()
        self.eng.screen_obj.draw(surf)
        self.eng._draw_exit_chip(surf)
        self.assertEqual(surf.get_at((640, 110))[:3],
                         self.eng.theme.background)

    def test_paused_overlay_yields_to_the_chip(self) -> None:
        # While the chip is up the screens must not stack their own
        # PAUSED layer under it; when the pause is a plain pause they
        # must still draw it.
        self._begin_classic()
        self.eng._handle_escape()
        self.assertTrue(self.eng.paused)
        self.assertTrue(self.eng.exit_chip_active)
        gameplay = self.eng._screens["gameplay"]
        # The gate the draw path uses, exactly as written there.
        self.assertFalse(self.eng.paused
                         and not self.eng.exit_overlay_active)
        self.eng._handle_escape()      # second Esc ends the game
        self.eng.begin_classic_block()
        self.eng._pause_now()
        self.assertTrue(self.eng.paused
                        and not self.eng.exit_overlay_active)
        self.assertTrue(hasattr(gameplay, "_draw_paused_overlay"))


if __name__ == "__main__":
    unittest.main()
