"""Tests for classic-mode pattern parsing + the actual pygame mainloop
running for real frames. The existing startup test only verifies clean
exit; here we run the loop for ~0.2 s and confirm it ticks."""
from __future__ import annotations

import os
import sys
import threading
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class ParsePatternTests(unittest.TestCase):
    """_parse_pattern walks comma-separated lane numbers 1..max_lanes.
    Anything else (non-numeric, out of range, empty) gets dropped. If
    the whole string parses to nothing, it falls back to 0..max_lanes-1."""

    def _parse(self, s, max_lanes=4):
        from rehab.game.engine import GameEngine
        return GameEngine._parse_pattern(s, max_lanes)

    def test_simple_pattern(self) -> None:
        self.assertEqual(self._parse("1,2,3,4"), [0, 1, 2, 3])

    def test_pattern_with_spaces(self) -> None:
        self.assertEqual(self._parse(" 1 , 2 , 3 "), [0, 1, 2])

    def test_non_numeric_tokens_dropped(self) -> None:
        self.assertEqual(self._parse("1,abc,2,xyz,3"), [0, 1, 2])

    def test_out_of_range_dropped(self) -> None:
        # Lane 0 rejected (1..max), lane 99 rejected.
        self.assertEqual(self._parse("0,1,2,99"), [0, 1])

    def test_negative_tokens_dropped(self) -> None:
        self.assertEqual(self._parse("-1,1,2,-5,3"), [0, 1, 2])

    def test_empty_string_falls_back_to_default(self) -> None:
        # Empty after parsing -> 0..max_lanes-1.
        self.assertEqual(self._parse(""), [0, 1, 2, 3])
        self.assertEqual(self._parse(",,,"), [0, 1, 2, 3])

    def test_all_invalid_falls_back_to_default(self) -> None:
        self.assertEqual(self._parse("abc,xyz"), [0, 1, 2, 3])

    def test_bilateral_max_lanes_eight(self) -> None:
        self.assertEqual(self._parse("1,5,2,6,3,7,4,8", max_lanes=8),
                          [0, 4, 1, 5, 2, 6, 3, 7])


class ClassicModeConstructionTests(unittest.TestCase):
    """ClassicMode uses the slider-tuned pace + the configured pattern.
    Verify those land correctly."""

    def test_classic_mode_picks_up_slider_pace(self) -> None:
        from unittest.mock import MagicMock
        from rehab.game.modes.classic import ClassicMode
        from rehab.game.scoring import ScoreConfig
        mode = ClassicMode(
            engine=MagicMock(),
            pattern=[0, 1, 2, 3],
            repeat_count=2,
            trigger_interval_s=1.8,    # from slider
            timeout_s=1.0,
            early_window_s=0.1,
            score_cfg=ScoreConfig(),
        )
        self.assertEqual(mode.trigger_interval, 1.8)
        # Sequence is pattern * repeat_count.
        self.assertEqual(len(mode.sequence), 4 * 2)


class MainloopActuallyIteratesTests(unittest.TestCase):
    """The previous startup test only verified run() returns rc=0 when
    running=False before entry. That proves init works but not the
    frame loop. Here we let the loop tick for ~0.2 s in a thread,
    confirm it actually advanced frames, then signal stop."""

    def test_run_executes_frames_then_exits_cleanly(self) -> None:
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())

        rc_container: list[int] = []

        def runner():
            rc_container.append(eng.run())

        # Hook into the title screen so we know it rendered at least
        # one frame. Patch the title screen's draw to flip a flag.
        # We can't access _screens until run() builds them, so use a
        # tick hook on the audio engine which run() calls every frame.
        # Easier: just sleep then flip running.
        frames_drawn = []
        original_show_title = eng.show_title
        def wrapped_show_title():
            original_show_title()
            # After title is shown, replace its draw method to count frames.
            ts = eng._screens.get("title")
            if ts is not None and not hasattr(ts, "_test_orig_draw"):
                ts._test_orig_draw = ts.draw
                def counting_draw(surf):
                    frames_drawn.append(1)
                    ts._test_orig_draw(surf)
                ts.draw = counting_draw
        eng.show_title = wrapped_show_title

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        # Let the loop run ~0.2 s. At 120 Hz that's ~24 frames; we
        # expect comfortably > 5 even on a slow CI machine.
        time.sleep(0.25)
        eng.running = False
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive(),
            "mainloop did not exit within 2 seconds of running=False")
        self.assertEqual(rc_container, [0])
        # Loop ticked at least a handful of frames (much fewer than the
        # theoretical max because thread startup + display init both
        # eat into the 200 ms budget, but more than zero).
        self.assertGreater(len(frames_drawn), 3,
            f"mainloop only drew {len(frames_drawn)} frames in 200 ms")


class SourceDisconnectionTests(unittest.TestCase):
    """If the Arduino drops mid-session, the mainloop must keep running
    (so Esc still works) but the engine should log the disconnect to
    the raw CSV and warn-once via the logger."""

    def _make_engine_with_fake_source(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.source import Source
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]

        class FakeSource(Source):
            def __init__(self):
                self._is_connected = True
                self._provides = True
            def start(self): pass
            def stop(self): pass
            def get_sample(self, timeout: float = 0.0):
                return None
            def send_command(self, cmd: str) -> bool:
                return True
            @property
            def is_connected(self) -> bool:
                return self._is_connected
            @property
            def provides_samples(self) -> bool:
                return self._provides
            @property
            def name(self) -> str:
                return "FakeSerial"

        src = FakeSource()
        eng = GameEngine(cfg, src)
        return eng, src

    def test_disconnect_emits_raw_event_once(self) -> None:
        from unittest.mock import MagicMock
        eng, src = self._make_engine_with_fake_source()
        eng.raw_logger = MagicMock()
        # First call with src connected: no event.
        eng._check_source_connection()
        eng.raw_logger.queue_event.assert_not_called()
        # Now disconnect.
        src._is_connected = False
        eng._check_source_connection()
        eng.raw_logger.queue_event.assert_called_once()
        kwargs = eng.raw_logger.queue_event.call_args.kwargs
        self.assertEqual(kwargs["detail"], "FakeSerial")
        # Calling again while still disconnected does NOT re-fire.
        eng.raw_logger.queue_event.reset_mock()
        eng._check_source_connection()
        eng.raw_logger.queue_event.assert_not_called()

    def test_reconnect_does_not_log_a_disconnect_event(self) -> None:
        from unittest.mock import MagicMock
        eng, src = self._make_engine_with_fake_source()
        eng.raw_logger = MagicMock()
        # Disconnect then reconnect.
        src._is_connected = False
        eng._check_source_connection()
        eng.raw_logger.queue_event.reset_mock()
        src._is_connected = True
        eng._check_source_connection()
        # Reconnect should NOT emit a "source_disconnected" event.
        eng.raw_logger.queue_event.assert_not_called()

    def test_keyboard_source_does_not_warn(self) -> None:
        # Keyboard-only mode returns provides_samples=False; the check
        # should short-circuit and never inspect is_connected.
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        eng = GameEngine(cfg, KeyboardOnlySource())
        from unittest.mock import MagicMock
        eng.raw_logger = MagicMock()
        eng._check_source_connection()
        eng.raw_logger.queue_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
