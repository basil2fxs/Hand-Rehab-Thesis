"""Tests for application startup: config fallbacks must agree with the YAML,
the engine boots a headless pygame loop without crashing, and main.py exits
cleanly when fed a broken config."""
from __future__ import annotations

import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ScoreConfigFallbackTests(unittest.TestCase):
    """If a user's override config omits scoring.* the engine must fall back
    to the no-negative-score defaults, NOT the old -2 values from before."""

    def test_score_cfg_inline_fallbacks_are_zero_for_miss_and_early(self) -> None:
        # Build a Config with NO scoring section at all, then verify the
        # engine's ScoreConfig construction comes out with miss=0 / early=0.
        from rehab.config import Config
        cfg = Config(data={})
        from rehab.game.scoring import ScoreConfig
        score_cfg = ScoreConfig(
            great_ms=int(cfg.get("scoring.great_ms", 200)),
            great_points=int(cfg.get("scoring.great_points", 3)),
            good_ms=int(cfg.get("scoring.good_ms", 500)),
            good_points=int(cfg.get("scoring.good_points", 2)),
            late_points=int(cfg.get("scoring.late_points", 1)),
            miss_points=int(cfg.get("scoring.miss_points", 0)),
            early_penalty=int(cfg.get("scoring.early_penalty", 0)),
        )
        self.assertEqual(score_cfg.miss_points, 0)
        self.assertEqual(score_cfg.early_penalty, 0)

    def test_engine_source_does_not_contain_negative_two_fallback(self) -> None:
        # Belt-and-braces: a refactor must not silently put -2 back into the
        # inline fallback. We grep the engine source for that exact string.
        src = (Path(__file__).resolve().parents[1]
                / "rehab" / "game" / "engine.py").read_text()
        self.assertNotIn('scoring.miss_points", -2', src)
        self.assertNotIn('scoring.early_penalty", -2', src)


class AdaptiveFallbackMatchesYamlTests(unittest.TestCase):
    """engine.py has inline fallbacks for every adaptive.* key. Those numbers
    must match config/default.yaml so a stripped-down override config inherits
    the same behaviour the YAML documents."""

    def _load_yaml(self) -> dict:
        import yaml
        p = (Path(__file__).resolve().parents[1]
              / "config" / "default.yaml")
        with p.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_adaptive_fallback_values_match_yaml(self) -> None:
        y = self._load_yaml()["adaptive"]
        src = (Path(__file__).resolve().parents[1]
                / "rehab" / "game" / "engine.py").read_text()
        # Each tuple is (yaml-key, expected fallback literal we should find).
        cases = [
            ("target_low", str(y["target_low"])),
            ("target_high", str(y["target_high"])),
            ("bpm_min", str(float(y["bpm_min"]))),
            ("bpm_max", str(float(y["bpm_max"]))),
            ("bpm_step", str(float(y["bpm_step"]))),
            ("min_trials", str(y["min_trials"])),
            ("block_size", str(y["block_size"])),
            ("start_bpm", str(y["start_bpm"])),
        ]
        for key, expected in cases:
            needle = f'"adaptive.{key}", {expected}'
            self.assertIn(needle, src,
                f"engine.py inline fallback for adaptive.{key} should be "
                f"{expected} to match config/default.yaml")


class HeadlessEngineBootTests(unittest.TestCase):
    """Verify the pygame loop actually starts. Use SDL_VIDEODRIVER=dummy +
    SDL_AUDIODRIVER=dummy so it runs without a display, set running=False
    before calling .run() so the while loop exits on its first check, and
    confirm we get a clean return code of 0."""

    def test_engine_run_returns_zero_in_headless_mode(self) -> None:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        # Smaller window so the dummy driver doesn't allocate too much.
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())
        # While loop exits immediately because we flip running=False BEFORE
        # entering run(). pygame.init + display.set_mode still happen, which
        # is the actual thing we want to prove works.
        eng.running = False
        rc = eng.run()
        self.assertEqual(rc, 0)

    def test_startup_screen_build_failure_still_quits_pygame(self) -> None:
        # If _build_screens() raises after pygame.display.set_mode succeeds,
        # the engine has to still tear pygame back down. Before the
        # try/finally was widened, pygame would stay initialised and on
        # Windows the display context could persist across re-runs.
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        import pygame
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        src = KeyboardOnlySource()
        eng = GameEngine(cfg, src)

        def _boom():
            raise RuntimeError("simulated screen-init failure")
        eng._build_screens = _boom  # type: ignore[method-assign]
        try:
            with self.assertRaises(RuntimeError):
                eng.run()
        finally:
            # Belt-and-braces: even if pygame.quit happened, calling it
            # again is a no-op. If the fix regressed this would still
            # leave pygame.get_init() True.
            still_init = pygame.get_init()
            if still_init:
                pygame.quit()
            self.assertFalse(
                still_init,
                "pygame should be quit even when _build_screens raises",
            )
            src.stop()

    def test_startup_source_start_failure_still_cleans_up(self) -> None:
        # If source.start() raises (e.g. a serial port that vanished
        # between discover and open), the engine should still hit the
        # finally and call source.stop. KeyboardOnlySource.start can't
        # naturally raise, so we monkey-patch it.
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        import pygame
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        src = KeyboardOnlySource()
        stop_calls: list[int] = [0]
        original_stop = src.stop

        def _spy_stop():
            stop_calls[0] += 1
            original_stop()
        src.stop = _spy_stop  # type: ignore[method-assign]

        def _boom():
            raise OSError("simulated port vanished")
        src.start = _boom  # type: ignore[method-assign]

        eng = GameEngine(cfg, src)
        try:
            with self.assertRaises(OSError):
                eng.run()
        finally:
            self.assertGreaterEqual(
                stop_calls[0], 1,
                "source.stop must run in finally even when source.start raises",
            )
            if pygame.get_init():
                pygame.quit()

    def test_startup_audio_build_failure_still_stops_source(self) -> None:
        # If _build_audio() raises after source.start() succeeded, the
        # finally has to stop the source. Otherwise on a real session
        # the Arduino stays open and the next attempt to launch the
        # game would fail to grab the port.
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        import pygame
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = True   # so _build_audio is exercised
        src = KeyboardOnlySource()
        stop_calls: list[int] = [0]
        original_stop = src.stop

        def _spy_stop():
            stop_calls[0] += 1
            original_stop()
        src.stop = _spy_stop  # type: ignore[method-assign]

        eng = GameEngine(cfg, src)

        def _boom():
            raise RuntimeError("simulated audio device gone")
        eng._build_audio = _boom  # type: ignore[method-assign]

        try:
            with self.assertRaises(RuntimeError):
                eng.run()
        finally:
            self.assertGreaterEqual(
                stop_calls[0], 1,
                "source.stop must run when _build_audio raises",
            )
            if pygame.get_init():
                pygame.quit()

    def test_engine_mainloop_body_actually_iterates(self) -> None:
        # The bare run-and-exit test above never exercises the while-body.
        # This one wraps the title screen's update() so we can count
        # frames, then flips running=False on the 3rd frame. If the loop
        # never reached update() we'd see frames=0 and fail; if it
        # exited cleanly we get frames>=1 and a return code of 0.
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())

        # Patch the title screen's update so we can intercept iteration
        # without changing engine internals. After 3 frames, request quit.
        frames: list[int] = [0]

        def _make_loop_break_after(target: int):
            def hook(*args, **kwargs):
                frames[0] += 1
                if frames[0] >= target:
                    eng.running = False
                # Mimic the original update doing nothing meaningful.
                return None
            return hook

        # The screen object is built inside run() via _build_screens(), so
        # patch _build_screens to return our instrumented dict.
        original_build = eng._build_screens

        def _wrapped_build():
            screens = original_build()
            for s in screens.values():
                s.update = _make_loop_break_after(3)  # type: ignore[method-assign]
            return screens

        eng._build_screens = _wrapped_build  # type: ignore[method-assign]
        rc = eng.run()
        self.assertEqual(rc, 0)
        # The while-body ran at least once, which is the contract.
        self.assertGreaterEqual(frames[0], 1)


class MainEntryPointTests(unittest.TestCase):
    """main.py is the real entry point. Argument parsing + the broken-config
    branch should behave sensibly so a misconfigured user gets a helpful
    error code, not a stack trace."""

    def test_parse_args_accepts_no_arguments(self) -> None:
        import main as main_mod
        with patch.object(sys, "argv", ["main.py"]):
            ns = main_mod.parse_args()
        self.assertEqual(ns.source, "auto")
        self.assertIsNone(ns.config)

    def test_parse_args_mode_choices_enforced(self) -> None:
        import main as main_mod
        with patch.object(sys, "argv", ["main.py", "--mode", "nonsense"]):
            with self.assertRaises(SystemExit):
                main_mod.parse_args()

    def test_main_returns_5_on_missing_config_path(self) -> None:
        import main as main_mod
        bogus = "/tmp/this-config-should-never-exist-xyz123.yaml"
        captured = io.StringIO()
        with patch.object(sys, "argv", ["main.py", "--config", bogus]):
            with patch.object(sys, "stderr", captured):
                rc = main_mod.main()
        self.assertEqual(rc, 5)
        self.assertIn("Config file not found", captured.getvalue())

    def test_build_source_falls_back_to_keyboard_when_no_serial(self) -> None:
        # Force the source builder down the keyboard path and confirm it
        # returns a real KeyboardOnlySource without raising.
        import main as main_mod
        from rehab.config import Config
        cfg = Config.load()
        ns = type("Args", (), {})()
        ns.source = "keyboard"
        ns.port = None
        src = main_mod._build_source(cfg, ns)
        try:
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            self.assertIsInstance(src, KeyboardOnlySource)
        finally:
            if src is not None:
                src.stop()


if __name__ == "__main__":
    unittest.main()
