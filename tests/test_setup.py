"""Tests for the setup screen: name + age input must flow through to the
session metadata, the CSV `participant` column, and the session folder
name. TextInput widget behaviour is exercised directly."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class TextInputTests(unittest.TestCase):
    def _make(self, **kw):
        import pygame
        pygame.init()
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout, TextInput
        layout = Layout(1280, 800)
        theme = get_theme("clinical")
        rect = pygame.Rect(0, 0, 300, 50)
        return TextInput(rect, theme, layout, **kw)

    def _press(self, ti, key, ch=""):
        import pygame
        # Simulate a click first so the field is focused.
        ti.focused = True
        ev = pygame.event.Event(pygame.KEYDOWN,
                                 {"key": key, "unicode": ch, "mod": 0,
                                  "scancode": 0})
        ti.handle_event(ev)

    def test_value_strips_whitespace(self) -> None:
        ti = self._make(initial="   basil   ")
        self.assertEqual(ti.value, "basil")

    def test_typing_appends_characters(self) -> None:
        import pygame
        ti = self._make()
        self._press(ti, pygame.K_b, "B")
        self._press(ti, pygame.K_a, "a")
        self._press(ti, pygame.K_s, "s")
        self.assertEqual(ti.value, "Bas")

    def test_backspace_removes_last_char(self) -> None:
        import pygame
        ti = self._make(initial="Bas")
        self._press(ti, pygame.K_BACKSPACE)
        self.assertEqual(ti.value, "Ba")

    def test_numeric_only_blocks_letters(self) -> None:
        import pygame
        ti = self._make(numeric=True)
        self._press(ti, pygame.K_5, "5")
        self._press(ti, pygame.K_a, "a")        # rejected
        self._press(ti, pygame.K_7, "7")
        self.assertEqual(ti.value, "57")

    def test_max_len_enforced(self) -> None:
        import pygame
        ti = self._make(max_len=3)
        for ch in "abcdefg":
            self._press(ti, pygame.K_a, ch)
        self.assertEqual(len(ti.value), 3)

    def test_enter_and_escape_defocus_without_typing(self) -> None:
        import pygame
        ti = self._make(initial="abc")
        self._press(ti, pygame.K_RETURN, "\r")
        self.assertFalse(ti.focused)
        self.assertEqual(ti.value, "abc")     # value unchanged
        ti.focused = True
        self._press(ti, pygame.K_ESCAPE, "\x1b")
        self.assertFalse(ti.focused)

    def test_unfocused_field_ignores_keypress(self) -> None:
        import pygame
        ti = self._make()
        ti.focused = False
        ev = pygame.event.Event(pygame.KEYDOWN,
                                 {"key": pygame.K_x, "unicode": "x",
                                  "mod": 0, "scancode": 0})
        ti.handle_event(ev)
        self.assertEqual(ti.value, "")


class TitleScreenNameFlowTests(unittest.TestCase):
    """Title screen now owns the participant name. Typing a name and
    pressing Start must push it into both the Session struct and the
    config so every block this app session inherits the same name."""

    def _make_engine(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        return GameEngine(cfg, KeyboardOnlySource())

    def test_name_flows_into_session_on_begin(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import TitleScreen
            eng = self._make_engine()
            calls = []
            eng.show_mode_select = lambda: calls.append("mode_select")
            screen = TitleScreen(eng)
            screen.name_input.text = "Test Patient"
            screen._begin()
            self.assertEqual(eng.session.participant, "Test Patient")
            self.assertEqual(eng.cfg.get("session.participant"), "Test Patient")
            self.assertEqual(calls, ["mode_select"])
        finally:
            pygame.quit()

    def test_empty_name_falls_back_to_NA(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import TitleScreen
            eng = self._make_engine()
            eng.show_mode_select = lambda: None
            screen = TitleScreen(eng)
            screen.name_input.text = ""
            screen._begin()
            self.assertEqual(eng.session.participant, "NA")
        finally:
            pygame.quit()


class SetupScreenHasNoNameInputTests(unittest.TestCase):
    """The setup screen used to own the name input. Now the title screen
    does. SetupScreen should NOT expose a name_input field anymore so a
    future refactor can't accidentally split the name across screens."""

    def test_setup_screen_does_not_have_name_or_age_inputs(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import SetupScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource())
            sc = SetupScreen(eng)
            self.assertFalse(hasattr(sc, "name_input"))
            self.assertFalse(hasattr(sc, "age_input"))
        finally:
            pygame.quit()


class SessionPathsUseTypedNameTests(unittest.TestCase):
    """End-to-end check: the typed name reaches SessionPaths.for_session
    and the resulting folder name reflects it. No age component anymore."""

    def test_session_folder_name_uses_typed_participant(self) -> None:
        import tempfile
        from rehab.data.logger import SessionPaths
        with tempfile.TemporaryDirectory() as td:
            paths = SessionPaths.for_session(Path(td), "Patient One")
            self.assertIn("Patient_One", paths.root.name)

    def test_session_paths_signature_dropped_age(self) -> None:
        # If someone later re-adds an age parameter the schema diverges
        # again. Guard the signature so the change is intentional.
        import inspect
        from rehab.data.logger import SessionPaths
        sig = inspect.signature(SessionPaths.for_session)
        params = list(sig.parameters)
        self.assertNotIn("age", params)
        self.assertEqual(params, ["data_dir", "participant"])


class GlobalParticipantPersistenceTests(unittest.TestCase):
    """The participant name set on the title screen must survive the
    whole app session. Going to a block and coming back to title should
    re-show the same name in the input field."""

    def test_title_screen_prefills_from_persisted_participant(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import TitleScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("session", {})["participant"] = "Returning"
            eng = GameEngine(cfg, KeyboardOnlySource())
            sc = TitleScreen(eng)
            self.assertEqual(sc.name_input.text, "Returning")
        finally:
            pygame.quit()

    def test_trial_columns_no_longer_include_age(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertNotIn("age", TRIAL_COLUMNS)
        self.assertIn("participant", TRIAL_COLUMNS)


class SliderWidgetTests(unittest.TestCase):
    """Slider clamps to [min, max], snaps to step grid, and persists its
    value across drag interactions."""

    def _make(self, **kw):
        import pygame
        pygame.init()
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout, Slider
        layout = Layout(1280, 800)
        theme = get_theme("clinical")
        rect = pygame.Rect(0, 0, 400, 30)
        return Slider(rect, theme, layout,
                       min_value=0.4, max_value=3.0,
                       initial=1.2, step=0.1, **kw)

    def test_initial_value_is_snapped_to_step_grid(self) -> None:
        sl = self._make()
        try:
            # 1.2 lands cleanly on a 0.1 grid from 0.4.
            self.assertAlmostEqual(sl.value, 1.2, places=6)
        finally:
            import pygame
            pygame.quit()

    def test_value_clamped_to_max(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.ui.theme import get as get_theme
            from rehab.ui.widgets import Layout, Slider
            layout = Layout(1280, 800)
            theme = get_theme("clinical")
            sl = Slider(pygame.Rect(0, 0, 400, 30), theme, layout,
                         min_value=0.4, max_value=3.0,
                         initial=99.0, step=0.1)
            self.assertEqual(sl.value, 3.0)
        finally:
            pygame.quit()

    def test_click_jumps_knob_to_position(self) -> None:
        import pygame
        sl = self._make()
        try:
            # Click 1px inside the right edge (pygame collidepoint is
            # right-exclusive, so .right itself is just outside the rect).
            ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
                "button": 1, "pos": (sl.rect.right - 1, sl.rect.centery),
            })
            sl.handle_event(ev)
            self.assertAlmostEqual(sl.value, 3.0, places=6)
            ev2 = pygame.event.Event(pygame.MOUSEBUTTONUP, {
                "button": 1, "pos": (sl.rect.right - 1, sl.rect.centery),
            })
            sl.handle_event(ev2)
            self.assertFalse(sl._dragging)
        finally:
            pygame.quit()


class ClassicPaceFlowTests(unittest.TestCase):
    """When the user picks classic mode, the setup screen shows the
    pace slider. Choosing a hand pushes the slider's value into
    cfg.game.trigger_interval_s so ClassicMode reads it on start."""

    def test_slider_value_persists_to_config_on_hand_pick(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import SetupScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data["game"]["mode"] = "classic"
            eng = GameEngine(cfg, KeyboardOnlySource())
            screen = SetupScreen(eng)
            # User drags the slider to 2.0 s.
            screen.pace_slider.value = 2.0
            # Stub the block kick-off.
            calls = []
            eng.begin_classic_block = lambda: calls.append("classic")
            screen._pick("right")
            self.assertEqual(eng.cfg.get("game.trigger_interval_s"), 2.0)
            self.assertEqual(calls, ["classic"])
        finally:
            pygame.quit()

    def test_adaptive_mode_does_not_overwrite_trigger_interval(self) -> None:
        # When the user picked adaptive, the slider value should NOT
        # land in trigger_interval_s (adaptive ignores it but the YAML
        # might still want the classic default preserved).
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import SetupScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data["game"]["mode"] = "adaptive"
            cfg.data["game"]["trigger_interval_s"] = 1.2
            eng = GameEngine(cfg, KeyboardOnlySource())
            screen = SetupScreen(eng)
            screen.pace_slider.value = 2.5
            eng.begin_adaptive_block = lambda: None
            screen._pick("right")
            self.assertEqual(eng.cfg.get("game.trigger_interval_s"), 1.2)
        finally:
            pygame.quit()


class EscNavigationTests(unittest.TestCase):
    """Two-step exit so a therapist can run several blocks for the same
    patient without retyping the name. Esc on a block / setup / results
    backs out to mode-select (name persists). Esc on mode-select goes
    back to title AND clears the participant name."""

    def _make_engine_with_screens(self):
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        from rehab.ui.screens import (
            TitleScreen, ModeSelectScreen, SetupScreen,
            RhythmSetupScreen, GameplayScreen, RhythmScreen, ResultsScreen,
        )
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = {
            "title": TitleScreen(eng),
            "mode_select": ModeSelectScreen(eng),
            "setup": SetupScreen(eng),
            "rhythm_setup": RhythmSetupScreen(eng),
            "gameplay": GameplayScreen(eng),
            "rhythm": RhythmScreen(eng),
            "results": ResultsScreen(eng),
        }
        return eng

    def test_esc_from_gameplay_goes_to_mode_select_and_keeps_name(self) -> None:
        eng = self._make_engine_with_screens()
        try:
            eng.session.participant = "Basil"
            eng.cfg.data["session"]["participant"] = "Basil"
            eng.screen_obj = eng._screens["gameplay"]
            eng._handle_escape()
            self.assertIs(eng.screen_obj, eng._screens["mode_select"])
            self.assertEqual(eng.session.participant, "Basil")
            self.assertEqual(eng.cfg.get("session.participant"), "Basil")
        finally:
            import pygame
            pygame.quit()

    def test_esc_from_rhythm_goes_to_mode_select_and_keeps_name(self) -> None:
        eng = self._make_engine_with_screens()
        try:
            eng.session.participant = "Basil"
            eng.cfg.data["session"]["participant"] = "Basil"
            eng.screen_obj = eng._screens["rhythm"]
            eng._handle_escape()
            self.assertIs(eng.screen_obj, eng._screens["mode_select"])
            self.assertEqual(eng.session.participant, "Basil")
        finally:
            import pygame
            pygame.quit()

    def test_esc_from_setup_goes_to_mode_select_and_keeps_name(self) -> None:
        eng = self._make_engine_with_screens()
        try:
            eng.session.participant = "Basil"
            eng.cfg.data["session"]["participant"] = "Basil"
            eng.screen_obj = eng._screens["setup"]
            eng._handle_escape()
            self.assertIs(eng.screen_obj, eng._screens["mode_select"])
            self.assertEqual(eng.session.participant, "Basil")
        finally:
            import pygame
            pygame.quit()

    def test_esc_from_mode_select_clears_name_and_goes_to_title(self) -> None:
        eng = self._make_engine_with_screens()
        try:
            eng.session.participant = "Basil"
            eng.cfg.data["session"]["participant"] = "Basil"
            eng.screen_obj = eng._screens["mode_select"]
            eng._handle_escape()
            self.assertIs(eng.screen_obj, eng._screens["title"])
            # Name cleared so the next patient enters their own.
            self.assertEqual(eng.session.participant, "NA")
            self.assertIsNone(eng.cfg.get("session.participant"))
        finally:
            import pygame
            pygame.quit()

    def test_title_screen_input_clears_after_esc_from_mode_select(self) -> None:
        # End-to-end: type a name, go to mode-select, Esc back. The name
        # input on title must show empty, not the old name.
        eng = self._make_engine_with_screens()
        try:
            ts = eng._screens["title"]
            ts.name_input.text = "Basil"
            ts._begin()
            self.assertIs(eng.screen_obj, eng._screens["mode_select"])
            eng._handle_escape()
            # Title screen now active and its input has been refreshed.
            self.assertIs(eng.screen_obj, eng._screens["title"])
            self.assertEqual(ts.name_input.text, "")
        finally:
            import pygame
            pygame.quit()

    def test_esc_from_title_quits_app(self) -> None:
        eng = self._make_engine_with_screens()
        try:
            eng.screen_obj = eng._screens["title"]
            eng._handle_escape()
            self.assertFalse(eng.running)
        finally:
            import pygame
            pygame.quit()


class DiagnosticsPortPanelTests(unittest.TestCase):
    """Settings screen with the COM port mapper: must build, draw, and
    cycle assignments without crashing. Stubs out the port scan so the
    test runs the same way on every dev machine."""

    def _build(self, hand_mode: str = "right"):
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        from rehab.ui.screens import DiagnosticsScreen
        cfg = Config.load()
        cfg.data.setdefault("bilateral", {})["hand"] = hand_mode
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        # Don't run the mainloop. Build just the screen we want.
        d = DiagnosticsScreen(eng)
        return eng, d, pygame

    def test_panel_builds_with_zero_ports(self) -> None:
        from unittest.mock import patch
        with patch("rehab.hardware.serial_source.list_available_ports",
                    return_value=[]):
            eng, d, pygame = self._build()
            try:
                d.refresh_ports()
                self.assertEqual(d._detected_ports, [])
                # 2 test STIM + Refresh + Save = 4 buttons.
                self.assertEqual(len(d._panel_buttons), 4)
                # 2 dropdowns (left, right).
                self.assertEqual(len(d._port_dropdowns), 2)
                # Each dropdown gets a "None" option even with zero
                # ports detected.
                for hand in ("left", "right"):
                    dd = d._port_dropdowns[hand]
                    self.assertEqual(len(dd.options), 1)
                    self.assertEqual(dd.options[0][0], None)
            finally:
                pygame.quit()

    def test_dropdown_select_stages_change_save_persists(self) -> None:
        # Selecting a port via the dropdown should stage the change in
        # _pending_ports + flip _has_unsaved True. Calling _save_ports
        # writes it to disk + clears the flag.
        from unittest import mock
        import tempfile
        from pathlib import Path
        from rehab.hardware.serial_source import PortInfo
        fake_ports = [
            PortInfo(device="/dev/cu.usbmodemA",
                      description="", vid=0x2341, pid=0),
            PortInfo(device="/dev/cu.usbmodemB",
                      description="", vid=0x2341, pid=0),
        ]
        with tempfile.TemporaryDirectory() as td:
            override = Path(td) / "user_settings.yaml"
            with mock.patch(
                "rehab.hardware.serial_source.list_available_ports",
                return_value=fake_ports,
            ), mock.patch("rehab.config.USER_OVERRIDES", override):
                eng, d, pygame = self._build()
                try:
                    d.refresh_ports()
                    d.rebuild_panel()
                    # No changes yet.
                    self.assertFalse(d._has_unsaved)
                    self.assertEqual(d._pending_ports, {})
                    # Simulate the dropdown picking a port.
                    d._on_port_chosen("right", "/dev/cu.usbmodemA")
                    self.assertTrue(d._has_unsaved)
                    self.assertEqual(
                        d._pending_ports["right"], "/dev/cu.usbmodemA")
                    # Not yet written to disk.
                    self.assertFalse(override.exists())
                    # Save: writes to disk + clears the dirty flag.
                    d._save_ports()
                    self.assertFalse(d._has_unsaved)
                    self.assertTrue(override.exists())
                    self.assertEqual(eng.cfg.get("serial.right_port"),
                                      "/dev/cu.usbmodemA")
                finally:
                    pygame.quit()

    def test_dropdown_excludes_junk_mac_ports(self) -> None:
        # /dev/cu.debug-console and Bluetooth-Incoming-Port must never
        # show up in the dropdown - that was the whole point of moving
        # the Settings panel onto discover_ports instead of the raw
        # list_available_ports.
        from unittest.mock import patch
        from rehab.hardware.serial_source import PortInfo
        ports = [
            PortInfo(device="/dev/cu.debug-console",
                      description="", vid=None, pid=None),
            PortInfo(device="/dev/cu.Bluetooth-Incoming-Port",
                      description="", vid=None, pid=None),
            PortInfo(device="/dev/cu.usbmodem1101",
                      description="Arduino", vid=0x2341, pid=0),
        ]
        with patch("rehab.hardware.serial_source.list_ports") as lp:
            lp.comports.return_value = ports
            eng, d, pygame = self._build()
            try:
                d.refresh_ports()
                d.rebuild_panel()
                self.assertEqual(d._detected_ports,
                                  ["/dev/cu.usbmodem1101"])
                # Dropdown has "None" + the real Arduino, no junk.
                for hand in ("left", "right"):
                    values = [v for v, _ in
                              d._port_dropdowns[hand].options]
                    self.assertEqual(values,
                                      [None, "/dev/cu.usbmodem1101"])
            finally:
                pygame.quit()

    def test_start_stim_test_queues_four_pulses(self) -> None:
        from unittest.mock import patch
        with patch("rehab.hardware.serial_source.list_available_ports",
                    return_value=[]):
            eng, d, pygame = self._build()
            try:
                d._start_stim_test("right")
                self.assertEqual(len(d._stim_queue), 4)
                # Each pulse targets RIGHT:STIM:1..4 in order.
                lanes = [lane for _, lane, _ in d._stim_queue]
                self.assertEqual(lanes, [1, 2, 3, 4])
                self.assertTrue(
                    all(prefix == "RIGHT"
                        for prefix, _, _ in d._stim_queue))
            finally:
                pygame.quit()

    def test_draw_does_not_crash(self) -> None:
        # Belt-and-braces: build the screen, give it a surface, draw.
        from unittest.mock import patch
        with patch("rehab.hardware.serial_source.list_available_ports",
                    return_value=[]):
            eng, d, pygame = self._build()
            try:
                surf = pygame.Surface((1280, 800))
                d.draw(surf)
                d.update(0.016)
            finally:
                pygame.quit()


class DiagnosticsConnectionStateTests(unittest.TestCase):
    """Four-state connection badge: KEYBOARD, DISCONNECTED, NO DATA, CONNECTED."""

    def _build_with_source(self, source):
        import os as _os
        _os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.ui.screens import DiagnosticsScreen
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, source)
        return eng, DiagnosticsScreen(eng), pygame

    def test_keyboard_source_reads_as_KEYBOARD(self) -> None:
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        eng, d, pygame = self._build_with_source(KeyboardOnlySource())
        try:
            text, _ = d._connection_state()
            self.assertEqual(text, "KEYBOARD")
        finally:
            pygame.quit()

    def test_open_port_no_data_reads_as_NO_DATA(self) -> None:
        # FakeArduino: provides_samples=True, is_connected=True, but no
        # has_recent_data => NO DATA. This is the Mac Bluetooth case.
        from rehab.hardware.source import Source

        class SilentArduino(Source):
            def start(self): pass
            def stop(self): pass
            def get_sample(self, timeout=0.0): return None
            def send_command(self, cmd): return True
            @property
            def is_connected(self): return True
            @property
            def provides_samples(self): return True
            @property
            def name(self): return "SilentArduino"

            def has_recent_data(self, window_s=1.0):
                return False

        eng, d, pygame = self._build_with_source(SilentArduino())
        try:
            text, _ = d._connection_state()
            self.assertEqual(text, "NO DATA")
        finally:
            pygame.quit()

    def test_open_port_with_data_reads_as_CONNECTED(self) -> None:
        from rehab.hardware.source import Source

        class HealthyArduino(Source):
            def start(self): pass
            def stop(self): pass
            def get_sample(self, timeout=0.0): return None
            def send_command(self, cmd): return True
            @property
            def is_connected(self): return True
            @property
            def provides_samples(self): return True
            @property
            def name(self): return "HealthyArduino"

            def has_recent_data(self, window_s=1.0):
                return True

        eng, d, pygame = self._build_with_source(HealthyArduino())
        try:
            text, _ = d._connection_state()
            self.assertEqual(text, "CONNECTED")
        finally:
            pygame.quit()

    def test_closed_port_reads_as_DISCONNECTED(self) -> None:
        from rehab.hardware.source import Source

        class DeadArduino(Source):
            def start(self): pass
            def stop(self): pass
            def get_sample(self, timeout=0.0): return None
            def send_command(self, cmd): return False
            @property
            def is_connected(self): return False
            @property
            def provides_samples(self): return True
            @property
            def name(self): return "DeadArduino"

        eng, d, pygame = self._build_with_source(DeadArduino())
        try:
            text, _ = d._connection_state()
            self.assertEqual(text, "DISCONNECTED")
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
