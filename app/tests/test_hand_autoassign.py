"""Plug-order hand auto-assignment and the stale-override fallback.

The contract these tests pin down:

  - No overrides: first detected board = RIGHT, second = LEFT.
  - An override naming a port that still exists wins for its hand.
  - An override naming a port the OS can no longer see is ignored
    (with a note) and that hand falls back to plug order. Before this
    rule, the stale name shunted the real board onto the wrong hand
    and the game had to be reconfigured in Settings after every
    replug, because macOS renames the port between plug-ins.
  - The game says which port went to which hand: on the title screen
    and on the Settings port panel.

Scenarios drive the real resolve_ports_and_hands / resolve_assignment
and the real build path (build_source_from_config feeding GameEngine),
with only the OS port list faked.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


A = "/dev/cu.usbmodemA"
B = "/dev/cu.usbmodemB"
# The exact shape of the stale line that sat in user_settings.yaml:
# a port name from a previous plug-in that no longer exists.
STALE = "/dev/cu.usbserial-130"


class _Cfg:
    """Minimal cfg exposing only dotted-get, like Config does."""

    def __init__(self, left=None, right=None):
        self.d = {"serial.left_port": left, "serial.right_port": right}

    def get(self, key, default=None):
        return self.d[key] if key in self.d else default


class _FakePort:
    def __init__(self, device, vid=0x2341, pid=0x0001, description="Arduino"):
        self.device = device
        self.vid = vid
        self.pid = pid
        self.description = description


def _patch_os_ports(devices):
    """Fake the OS port list for both discover_ports and
    list_available_ports (they share list_ports.comports)."""
    from finger_rehab.hardware import serial_source
    fakes = [_FakePort(d) for d in devices]
    p = patch.object(serial_source, "list_ports")
    lp = p.start()
    lp.comports.return_value = fakes
    return p


class ResolveAssignmentTests(unittest.TestCase):
    """The resolver on its own, every scenario in the contract."""

    def _resolve(self, cfg, detected, known=None):
        from finger_rehab.hardware.discovery import resolve_ports_and_hands
        return resolve_ports_and_hands(cfg, detected, known)

    def test_zero_config_two_boards_first_is_right(self) -> None:
        ports, hands = self._resolve(_Cfg(), [A, B])
        self.assertEqual(list(zip(hands, ports)),
                         [("right", A), ("left", B)])

    def test_zero_config_one_board_is_right(self) -> None:
        ports, hands = self._resolve(_Cfg(), [A])
        self.assertEqual(list(zip(hands, ports)), [("right", A)])

    def test_stale_right_override_one_board_still_right(self) -> None:
        # The bug this whole change exists for: with the stale yaml
        # line, the one real board used to come up as LEFT while the
        # phantom port held RIGHT and never connected.
        ports, hands = self._resolve(_Cfg(right=STALE), [A])
        self.assertEqual(list(zip(hands, ports)), [("right", A)])

    def test_stale_right_override_two_boards_plug_order(self) -> None:
        # Used to drop the second board entirely: the stale port took
        # right, board A took left, board B was never opened.
        ports, hands = self._resolve(_Cfg(right=STALE), [A, B])
        self.assertEqual(list(zip(hands, ports)),
                         [("right", A), ("left", B)])

    def test_both_overrides_stale_plug_order(self) -> None:
        cfg = _Cfg(left="/dev/cu.gone1", right="/dev/cu.gone2")
        ports, hands = self._resolve(cfg, [A, B])
        self.assertEqual(list(zip(hands, ports)),
                         [("right", A), ("left", B)])

    def test_valid_right_override_still_wins(self) -> None:
        # The Settings option that must keep working: pin board B to
        # the right hand, the spare board takes the left.
        ports, hands = self._resolve(_Cfg(right=B), [A, B])
        self.assertEqual(list(zip(hands, ports)),
                         [("right", B), ("left", A)])

    def test_valid_left_only_override(self) -> None:
        ports, hands = self._resolve(_Cfg(left=A), [A, B])
        self.assertEqual(sorted(zip(hands, ports)),
                         [("left", A), ("right", B)])

    def test_override_outside_detected_kept_when_os_knows_it(self) -> None:
        # A hand-assigned port the auto-detector filters (junk-listed
        # or beyond the detect cap) is still real; the override holds.
        junk = "/dev/cu.Bluetooth-Incoming-Port"
        ports, hands = self._resolve(_Cfg(right=junk), [A],
                                     known=[A, junk])
        self.assertEqual(list(zip(hands, ports)),
                         [("right", junk), ("left", A)])

    def test_no_boards_and_stale_overrides_yields_nothing(self) -> None:
        ports, hands = self._resolve(_Cfg(left=STALE, right=STALE), [])
        self.assertEqual(ports, [])
        self.assertEqual(hands, [])

    def test_stale_override_is_reported(self) -> None:
        from finger_rehab.hardware.discovery import resolve_assignment
        a = resolve_assignment(_Cfg(right=STALE), [A])
        self.assertEqual(a.stale, [("right", STALE)])
        self.assertIn("ignored", a.describe())
        self.assertIn("usbserial-130", a.describe())

    def test_pinned_hand_is_reported(self) -> None:
        from finger_rehab.hardware.discovery import resolve_assignment
        a = resolve_assignment(_Cfg(right=B), [A, B])
        self.assertEqual(a.pinned, ["right"])
        self.assertIn("set in Settings", a.describe())


class BuildSourceTests(unittest.TestCase):
    """build_source_from_config end to end with a faked OS port list.
    Sources are built but never started, so no port is opened."""

    def _build(self, cfg_serial: dict, os_ports: list[str]):
        from finger_rehab.config import Config
        from finger_rehab.hardware.discovery import build_source_from_config
        cfg = Config.load()
        cfg.data.setdefault("serial", {}).update(cfg_serial)
        p = _patch_os_ports(os_ports)
        try:
            return build_source_from_config(cfg)
        finally:
            p.stop()

    def _pairs(self, src):
        return [(h.hand, h.port) for h in src.hands]

    def test_zero_config_two_boards(self) -> None:
        src = self._build({"left_port": None, "right_port": None,
                           "port": "auto"}, [A, B])
        self.assertIsNotNone(src)
        self.assertEqual(self._pairs(src), [("right", A), ("left", B)])
        self.assertIn("right = usbmodemA", src.assignment_note)
        self.assertIn("left = usbmodemB", src.assignment_note)

    def test_stale_right_override_one_board(self) -> None:
        src = self._build({"left_port": None, "right_port": STALE,
                           "port": "auto"}, [A])
        self.assertIsNotNone(src)
        self.assertEqual(self._pairs(src), [("right", A)])
        self.assertIn("ignored", src.assignment_note)

    def test_valid_override_pins_the_hand(self) -> None:
        src = self._build({"left_port": None, "right_port": B,
                           "port": "auto"}, [A, B])
        self.assertEqual(self._pairs(src), [("right", B), ("left", A)])

    def test_stale_serial_port_falls_back_to_discovery(self) -> None:
        # serial.port saved to a dead name must not shadow the boards
        # that are actually plugged in.
        src = self._build({"left_port": None, "right_port": None,
                           "port": STALE}, [A, B])
        self.assertIsNotNone(src)
        self.assertEqual(self._pairs(src), [("right", A), ("left", B)])

    def test_valid_serial_port_still_forces(self) -> None:
        src = self._build({"left_port": None, "right_port": None,
                           "port": B}, [A, B])
        self.assertEqual(self._pairs(src), [("right", B)])

    def test_no_boards_no_source(self) -> None:
        src = self._build({"left_port": None, "right_port": STALE,
                           "port": "auto"}, [])
        self.assertIsNone(src)


class EngineBootShowsAssignmentTests(unittest.TestCase):
    """Boot the real engine on a faked two-board rig and check both
    places the contract says the assignment must be visible."""

    def _boot(self, cfg_serial: dict, os_ports: list[str]):
        import pygame
        pygame.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.discovery import build_source_from_config
        cfg = Config.load()
        cfg.data.setdefault("serial", {}).update(cfg_serial)
        cfg.data["ui"]["resolution"] = [1280, 800]
        p = _patch_os_ports(os_ports)
        try:
            src = build_source_from_config(cfg)
            self.assertIsNotNone(src)
            eng = GameEngine(cfg, src)
            return eng, p, pygame
        except Exception:
            p.stop()
            import pygame as pg
            pg.quit()
            raise

    def test_title_screen_says_which_port_is_which_hand(self) -> None:
        eng, p, pygame = self._boot(
            {"left_port": None, "right_port": None, "port": "auto"},
            [A, B])
        try:
            from finger_rehab.ui.screens import TitleScreen
            t = TitleScreen(eng)
            line, colour = t._hardware_status()
            self.assertIn("RIGHT = usbmodemA", line)
            self.assertIn("LEFT = usbmodemB", line)
            # And the draw path that shows it must not crash.
            t.draw(pygame.Surface((1280, 800)))
        finally:
            p.stop()
            pygame.quit()

    def test_title_screen_flags_ignored_stale_override(self) -> None:
        eng, p, pygame = self._boot(
            {"left_port": None, "right_port": STALE, "port": "auto"},
            [A])
        try:
            from finger_rehab.ui.screens import TitleScreen
            t = TitleScreen(eng)
            line, colour = t._hardware_status()
            self.assertIn("RIGHT = usbmodemA", line)
            self.assertIn("ignored", line.lower())
            self.assertEqual(colour, eng.theme.warning)
        finally:
            p.stop()
            pygame.quit()

    def test_settings_opens_with_assignment_on_status_line(self) -> None:
        eng, p, pygame = self._boot(
            {"left_port": None, "right_port": STALE, "port": "auto"},
            [A])
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            d = DiagnosticsScreen(eng)
            self.assertIn("ignored", d._port_status)
            self.assertIn("usbserial-130", d._port_status)
            # Dropdown default reads as the auto rule, not as "no
            # Arduino".
            for hand in ("left", "right"):
                value, label = d._port_dropdowns[hand].options[0]
                self.assertIsNone(value)
                self.assertIn("Auto", label)
            d.draw(pygame.Surface((1280, 800)))
        finally:
            p.stop()
            pygame.quit()

    def test_reconnect_reports_the_assignment(self) -> None:
        # The Settings Save path: reconnect_source rebuilds from config
        # and its status line must carry the hand-to-port mapping.
        eng, p, pygame = self._boot(
            {"left_port": None, "right_port": None, "port": "auto"},
            [A, B])
        try:
            class _FakeSource:
                assignment_note = "right = usbmodemA (auto)"
                def start(self):
                    pass
                def stop(self):
                    pass
            from finger_rehab.hardware import discovery
            with patch.object(discovery, "build_source_from_config",
                              return_value=_FakeSource()):
                msg = eng.reconnect_source()
            self.assertIn("right = usbmodemA", msg)
        finally:
            p.stop()
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
