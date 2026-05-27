"""Tests for KeyboardOnlySource. It's a sentinel - its only contract is
provides_samples=False so the engine switches to pygame KEYDOWN events,
plus normal start/stop lifecycle. No real Arduino needed."""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class KeyboardSourceContractTests(unittest.TestCase):

    def test_provides_samples_is_false(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        # The engine reads this flag to decide between FSR samples and
        # KEYDOWN events as the press surrogate. Flipping it would break
        # every keyboard-fallback session.
        self.assertFalse(KeyboardOnlySource().provides_samples)

    def test_name_property(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        self.assertEqual(KeyboardOnlySource().name, "KeyboardOnlySource")


class KeyboardSourceLifecycleTests(unittest.TestCase):

    def test_start_marks_connected_then_stop_clears(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        src = KeyboardOnlySource()
        self.assertFalse(src.is_connected)
        src.start()
        try:
            # Give the worker thread a moment to set _connected.
            for _ in range(50):
                if src.is_connected:
                    break
                time.sleep(0.01)
            self.assertTrue(src.is_connected)
        finally:
            src.stop()
        self.assertFalse(src.is_connected)

    def test_get_sample_always_returns_none(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        src = KeyboardOnlySource()
        src.start()
        try:
            time.sleep(0.02)
            # Queue never gets pushed to; every read must be None so
            # the engine reliably falls through to its KEYDOWN handling.
            self.assertIsNone(src.get_sample())
            self.assertIsNone(src.get_sample(timeout=0.01))
        finally:
            src.stop()

    def test_double_start_is_safe(self) -> None:
        # start() must early-return on an already-running thread (the
        # base class handles this) - calling twice must not spawn a
        # second worker.
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        src = KeyboardOnlySource()
        src.start()
        first_thread = src._thread
        src.start()
        self.assertIs(src._thread, first_thread)
        src.stop()

    def test_stop_before_start_is_safe(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        src = KeyboardOnlySource()
        # Calling stop() on a never-started source must not raise.
        src.stop()


class KeyboardSourceCommandTests(unittest.TestCase):

    def test_send_command_always_returns_false(self) -> None:
        # Keyboard mode has no motor, so STIM / STOP / anything else
        # cannot succeed. Returning False lets the engine log it and
        # move on without expecting a motor pulse.
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        src = KeyboardOnlySource()
        self.assertFalse(src.send_command("STIM:1"))
        self.assertFalse(src.send_command("STOP"))
        self.assertFalse(src.send_command("anything"))
        # Empty / weird strings must not crash either.
        self.assertFalse(src.send_command(""))
        self.assertFalse(src.send_command("a" * 1000))


class KeyboardFallbackEndToEndTests(unittest.TestCase):
    """When no Arduino is plugged in, FDSA + JKL; must still drive the
    game in the right way. These tests build a real ClassicMode against
    a KeyboardOnlySource and fire each lane key, asserting the press
    queue gets the matching lane index."""

    def _build_classic(self, hand_mode: str):
        import os as _os
        _os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.game.modes.classic import ClassicMode
        from rehab.game.scoring import ScoreConfig
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data.setdefault("bilateral", {})["hand"] = hand_mode
        src = KeyboardOnlySource()
        eng = GameEngine(cfg, src)
        mode = ClassicMode(
            engine=eng,
            pattern=[0, 1, 2, 3],
            repeat_count=1,
            trigger_interval_s=1.0,
            timeout_s=1.0,
            early_window_s=0.1,
            score_cfg=ScoreConfig(),
        )
        return eng, mode, pygame

    def test_right_hand_jkl_semicolon_each_queue_correct_lane(self) -> None:
        # j -> lane 0, k -> 1, l -> 2, ; -> 3.
        eng, mode, pygame = self._build_classic("right")
        for key_attr, expected_lane in (("K_j", 0), ("K_k", 1),
                                           ("K_l", 2), ("K_SEMICOLON", 3)):
            mode._presses.clear()
            ev = pygame.event.Event(pygame.KEYDOWN,
                                       {"key": getattr(pygame, key_attr),
                                        "mod": 0, "unicode": "",
                                        "scancode": 0})
            mode.handle_event(ev)
            self.assertEqual(len(mode._presses), 1,
                              f"{key_attr} did not queue a press")
            self.assertEqual(mode._presses[0].lane, expected_lane,
                              f"{key_attr} mapped to lane "
                              f"{mode._presses[0].lane}, expected "
                              f"{expected_lane}")

    def test_left_hand_fdsa_each_queue_correct_lane(self) -> None:
        # f -> lane 0 (index), d -> 1, s -> 2, a -> 3 (little).
        eng, mode, pygame = self._build_classic("left")
        for key_attr, expected_lane in (("K_f", 0), ("K_d", 1),
                                           ("K_s", 2), ("K_a", 3)):
            mode._presses.clear()
            ev = pygame.event.Event(pygame.KEYDOWN,
                                       {"key": getattr(pygame, key_attr),
                                        "mod": 0, "unicode": "",
                                        "scancode": 0})
            mode.handle_event(ev)
            self.assertEqual(len(mode._presses), 1,
                              f"{key_attr} did not queue a press")
            self.assertEqual(mode._presses[0].lane, expected_lane,
                              f"{key_attr} mapped to lane "
                              f"{mode._presses[0].lane}, expected "
                              f"{expected_lane}")

    def test_bilateral_eight_keys_queue_correct_lanes(self) -> None:
        # Right hand: j k l ; -> lanes 0-3. Left hand: f d s a -> 4-7.
        eng, mode, pygame = self._build_classic("both")
        cases = [
            ("K_j", 0), ("K_k", 1), ("K_l", 2), ("K_SEMICOLON", 3),
            ("K_f", 4), ("K_d", 5), ("K_s", 6), ("K_a", 7),
        ]
        for key_attr, expected_lane in cases:
            mode._presses.clear()
            ev = pygame.event.Event(pygame.KEYDOWN,
                                       {"key": getattr(pygame, key_attr),
                                        "mod": 0, "unicode": "",
                                        "scancode": 0})
            mode.handle_event(ev)
            self.assertEqual(len(mode._presses), 1,
                              f"{key_attr} did not queue a press")
            self.assertEqual(mode._presses[0].lane, expected_lane,
                              f"{key_attr} mapped to lane "
                              f"{mode._presses[0].lane}, expected "
                              f"{expected_lane}")


class KeyboardAlwaysOnWithArduinoTests(unittest.TestCase):
    """Regression: when an Arduino is plugged in (source.provides_samples
    == True), the keyboard fallback must STILL fire. Without this, a
    busted auto-detect (Mac grabbing Bluetooth-Incoming-Port as if it
    were an Arduino) left the therapist with no working input."""

    def _build_with_fake_arduino_source(self, hand_mode: str = "right"):
        import os as _os
        _os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.game.modes.classic import ClassicMode
        from rehab.game.scoring import ScoreConfig
        from rehab.hardware.source import Source

        class FakeArduino(Source):
            """Pretends to be a real Arduino source: provides_samples=True
            and is_connected=True. No actual data flows."""

            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

            def get_sample(self, timeout: float = 0.0):
                return None

            def send_command(self, cmd: str) -> bool:
                return True

            @property
            def is_connected(self) -> bool:
                return True

            @property
            def provides_samples(self) -> bool:
                return True

            @property
            def name(self) -> str:
                return "FakeArduino"

        cfg = Config.load()
        cfg.data.setdefault("bilateral", {})["hand"] = hand_mode
        eng = GameEngine(cfg, FakeArduino())
        mode = ClassicMode(
            engine=eng,
            pattern=[0, 1, 2, 3],
            repeat_count=1,
            trigger_interval_s=1.0,
            timeout_s=1.0,
            early_window_s=0.1,
            score_cfg=ScoreConfig(),
        )
        return eng, mode, pygame

    def test_keyboard_queues_press_even_with_arduino_source(self) -> None:
        # The whole point of this regression: provides_samples=True
        # used to gate the keyboard handler off. Now it doesn't.
        eng, mode, pygame = self._build_with_fake_arduino_source("right")
        ev = pygame.event.Event(pygame.KEYDOWN,
                                   {"key": pygame.K_j,
                                    "mod": 0, "unicode": "",
                                    "scancode": 0})
        mode.handle_event(ev)
        self.assertEqual(len(mode._presses), 1)
        self.assertEqual(mode._presses[0].lane, 0)

    def test_keyboard_works_in_all_three_modes_with_arduino(self) -> None:
        # Same check for adaptive + rhythm so the guard removal applies
        # uniformly. We just check that handle_event accepts KEYDOWN
        # without depending on provides_samples.
        import inspect
        from rehab.game.modes import classic, adaptive, rhythm
        for module in (classic, adaptive, rhythm):
            src = inspect.getsource(
                next(c for n, c in inspect.getmembers(module)
                     if inspect.isclass(c)
                     and getattr(c, "name", "") in
                     ("Classic", "Adaptive", "Rhythm"))
            )
            self.assertNotIn("not self.engine.source.provides_samples", src,
                              f"{module.__name__} still guards keyboard "
                              f"on provides_samples")


if __name__ == "__main__":
    unittest.main()
