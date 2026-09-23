"""The trigger box's port can be changed in the game, and nothing else
in the game can take it.

Before this, a lab PC that gave the box any COM number but 10 had one
way forward: quit, find eeg_lab.yaml, edit it in a text editor. And
the hand-board discovery would happily take the box as a hand board
when no Arduino was plugged in, which on Windows locked the marker
writer out of its own port.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from finger_rehab.hardware import eeg_port  # noqa: E402
from finger_rehab.hardware.eeg_trigger import (  # noqa: E402
    CODES, DummyBackend, MarkerWriter, TriggerBackend, writer_from_config)
from finger_rehab.hardware.serial_source import PortInfo  # noqa: E402

LAB_YAML = ROOT / "config" / "eeg_lab.yaml"


def _getter(values: dict):
    return lambda key, default=None: values.get(key, default)


class _OpenPort(TriggerBackend):
    name = "serial"

    def __init__(self, port: str) -> None:
        self.port = port
        self.written: list[int] = []
        self.closed = False

    def open(self) -> bool:
        return True

    def write_code(self, code: int) -> bool:
        self.written.append(code)
        return True

    def close(self) -> None:
        self.closed = True


# ---- the yaml line edit ----------------------------------------------------

class PortLineTests(unittest.TestCase):

    def test_the_lab_file_changes_on_one_line_only(self):
        before = LAB_YAML.read_text()
        after = eeg_port.set_port_line(before, "COM7")
        self.assertEqual(yaml.safe_load(after)["eeg"]["port"], "COM7")
        diff = [(a, b) for a, b in zip(before.splitlines(),
                                       after.splitlines()) if a != b]
        self.assertEqual(diff, [("  port: COM10", "  port: COM7")])
        # Every comment survives.
        self.assertEqual(before.count("#"), after.count("#"))

    def test_windows_line_endings_are_kept(self):
        # The lab's copy can come out of CI with CRLF.
        text = "eeg:\r\n  enabled: true\r\n  port: COM10\r\n"
        out = eeg_port.set_port_line(text, "COM3")
        self.assertIn("  port: COM3\r\n", out)
        self.assertNotIn("\n\n", out.replace("\r\n", "|"))

    def test_only_the_eeg_blocks_port_moves(self):
        text = ("serial:\n  port: auto\n"
                "eeg:\n  enabled: true\n  port: COM10  # the box\n"
                "other:\n  port: 5\n")
        out = yaml.safe_load(eeg_port.set_port_line(text, "COM4"))
        self.assertEqual(out["serial"]["port"], "auto")
        self.assertEqual(out["other"]["port"], 5)
        self.assertEqual(out["eeg"]["port"], "COM4")
        self.assertIn("COM4  # the box",
                      eeg_port.set_port_line(text, "COM4"))

    def test_a_missing_key_or_block_is_added(self):
        out = eeg_port.set_port_line("eeg:\n  enabled: true\n", "COM2")
        self.assertEqual(yaml.safe_load(out)["eeg"],
                         {"enabled": True, "port": "COM2"})
        out = eeg_port.set_port_line("reaction:\n  seed: 1\n", "COM2")
        self.assertEqual(yaml.safe_load(out)["eeg"]["port"], "COM2")

    def test_mac_and_odd_names_read_back_exactly(self):
        for name in ("/dev/cu.usbmodem1101", "COM12", "yes", "null"):
            with self.subTest(name=name):
                out = eeg_port.set_port_line("eeg:\n  port: COM10\n", name)
                self.assertEqual(yaml.safe_load(out)["eeg"]["port"], name)


# ---- saving ------------------------------------------------------------------

class SaveTests(unittest.TestCase):

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.dir = Path(td.name)

    def test_a_lab_folders_own_file_is_edited_in_place(self):
        lab = self.dir / "eeg_lab.yaml"
        lab.write_text(LAB_YAML.read_text())
        cfg = SimpleNamespace(data={"eeg": {"port": "COM10"}}, source=lab)
        path, line = eeg_port.save_port(cfg, "COM7")
        self.assertEqual(path, lab)
        self.assertEqual(yaml.safe_load(lab.read_text())["eeg"]["port"],
                         "COM7")
        self.assertEqual(cfg.data["eeg"]["port"], "COM7")
        self.assertIn("eeg_lab.yaml", line)

    def test_the_apps_own_copy_is_never_written(self):
        from finger_rehab import config as config_mod
        local = self.dir / "eeg_port.yaml"
        before = LAB_YAML.read_bytes()
        cfg = SimpleNamespace(data={"eeg": {}}, source=LAB_YAML)
        with patch.object(config_mod, "EEG_PORT_FILE", local):
            path, _ = eeg_port.save_port(cfg, "/dev/cu.usbmodem1101")
            self.assertEqual(path, local)
            self.assertEqual(LAB_YAML.read_bytes(), before)
            # And the next launch from the app's copy picks it up.
            loaded = config_mod.Config.load(LAB_YAML)
        self.assertEqual(loaded.get("eeg.port"), "/dev/cu.usbmodem1101")

    def test_a_lab_folders_file_ignores_the_local_pick(self):
        # The local file only ever applies over the app's own copy; a
        # lab folder's eeg_lab.yaml stays the one place its port lives.
        from finger_rehab import config as config_mod
        local = self.dir / "eeg_port.yaml"
        local.write_text("port: COM99\n")
        lab = self.dir / "eeg_lab.yaml"
        lab.write_text(LAB_YAML.read_text())
        with patch.object(config_mod, "EEG_PORT_FILE", local):
            loaded = config_mod.Config.load(lab)
        self.assertEqual(loaded.get("eeg.port"), "COM10")

    def test_an_unwritable_file_still_connects_for_this_run(self):
        missing = self.dir / "gone" / "eeg_lab.yaml"
        cfg = SimpleNamespace(data={"eeg": {}}, source=missing)
        path, line = eeg_port.save_port(cfg, "COM7")
        self.assertIsNone(path)
        self.assertEqual(cfg.data["eeg"]["port"], "COM7")
        self.assertIn("port: COM7", line)


# ---- the hand boards keep off the box ---------------------------------------

BOX = PortInfo(device="COM10", description="USB Serial Device",
               vid=0x0403, pid=0x6001)
ODD_BOX = PortInfo(device="COM7", description="USB Serial Device",
                   vid=0x1234, pid=0x0001)
NANO = PortInfo(device="COM3", description="USB-SERIAL CH340",
                vid=0x1A86, pid=0x7523)


class DiscoveryTests(unittest.TestCase):

    def _cfg(self, **eeg):
        from finger_rehab.config import Config
        cfg = Config.load()
        cfg.data["eeg"] = dict({"enabled": True, "port": "COM10"}, **eeg)
        cfg.data["serial"]["vendor_ids"] = ["0x0403", "0x1A86"]
        return cfg

    def _ports(self, *infos):
        return patch("finger_rehab.hardware.serial_source."
                     "list_available_ports", return_value=list(infos))

    def test_the_box_is_never_a_hand_board(self):
        from finger_rehab.hardware.discovery import hand_board_ports
        with self._ports(BOX, NANO):
            self.assertEqual(hand_board_ports(self._cfg()), ["COM3"])

    def test_no_unknown_usb_fallback_in_the_lab(self):
        # The box on an unexpected COM number with an unknown chip: the
        # old "any USB serial device" pass would have taken it.
        from finger_rehab.hardware.discovery import hand_board_ports
        with self._ports(ODD_BOX):
            self.assertEqual(hand_board_ports(self._cfg()), [])
            home = self._cfg(enabled=False)
            self.assertEqual(hand_board_ports(home), ["COM7"])

    def test_a_saved_hand_port_naming_the_box_is_dropped(self):
        from finger_rehab.hardware.discovery import build_source_from_config
        cfg = self._cfg()
        cfg.data["serial"]["right_port"] = "com10"
        with self._ports(BOX, NANO), patch(
                "finger_rehab.hardware.serial_source._HAVE_SERIAL", True):
            src = build_source_from_config(cfg)
        self.assertIsNotNone(src)
        self.assertEqual([h.port for h in src.hands], ["COM3"])

    def test_the_picker_lists_everything_but_the_hands(self):
        with self._ports(BOX, NANO, PortInfo(
                device="/dev/cu.Bluetooth-Incoming-Port", description="",
                vid=None, pid=None)):
            got = [c.device for c in eeg_port.candidates(exclude=["COM3"])]
        self.assertEqual(got, ["COM10"])


# ---- the writer waits for a port instead of exiting --------------------------

class WaitingWriterTests(unittest.TestCase):

    def _waiting(self):
        return writer_from_config(_getter({
            "eeg.enabled": True, "eeg.require_port": True,
            "eeg.port": "/dev/does-not-exist-eeg", "eeg.baud": 9600,
            "eeg.pulse_ms": 8, "eeg.gap_ms": 12}), defer_missing=True)

    def test_lab_mode_without_its_box_waits_and_sends_nothing(self):
        w = self._waiting()
        self.assertTrue(w.needs_port)
        self.assertFalse(w.active)
        self.assertIn("does-not-exist-eeg", w.port_problem)
        w.send(CODES["session_start"])   # a no-op, not a crash

    def test_a_picked_port_starts_clean(self):
        w = self._waiting()
        box = _OpenPort("COM7")
        w.use_backend(box)
        self.assertFalse(w.needs_port)
        self.assertTrue(w.active)
        self.assertIsNone(w.port_problem)
        self.assertEqual(w.status()["port"], "COM7")

    def test_moving_ports_resets_the_old_one_and_clears_degraded(self):
        old, new = _OpenPort("COM10"), _OpenPort("COM7")
        w = MarkerWriter(backend=old, enabled=True)
        w.degraded = True
        w.use_backend(new)
        self.assertEqual(old.written[-1], 0)
        self.assertTrue(old.closed)
        self.assertFalse(w.degraded)
        w.send(33)
        self.assertEqual(new.written, [33])

    def test_without_the_defer_flag_it_still_refuses(self):
        from finger_rehab.hardware.eeg_trigger import TriggerPortError
        with self.assertRaises(TriggerPortError):
            writer_from_config(_getter({
                "eeg.enabled": True, "eeg.require_port": True,
                "eeg.port": None}))


# ---- the picker screen -------------------------------------------------------

class PickerScreenTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import pygame
        pygame.init()

    def _screen(self, markers, started=False, hands=()):
        from finger_rehab.ui.eeg_port_screen import EegPortScreen
        from finger_rehab.ui.theme import CLINICAL
        from finger_rehab.ui.widgets import Layout
        engine = SimpleNamespace(
            theme=CLINICAL, layout=Layout(1280, 800), markers=markers,
            cfg=SimpleNamespace(data={"eeg": {}},
                                get=lambda k, d=None: 9600
                                if k == "eeg.baud" else d),
            source=SimpleNamespace(hands=[SimpleNamespace(port=p)
                                          for p in hands]),
            _hand_source_started=started, running=True,
            show_title=MagicMock(), eeg_port_ready=MagicMock())
        s = EegPortScreen(engine)
        s.scan = MagicMock(return_value=[
            eeg_port.PortChoice("COM7", "USB Serial Device", 0x0403, 1),
            eeg_port.PortChoice("COM3", "USB-SERIAL CH340", 0x1A86, 2)])
        s.saver = MagicMock(return_value=(Path("eeg_lab.yaml"),
                                          "Saved to eeg_lab.yaml."))
        return s, engine

    def _waiting(self):
        w = MarkerWriter(backend=None, enabled=True)
        w.port_problem = "could not open eeg.port COM10"
        return w

    def test_launch_shows_why_and_escape_quits(self):
        s, engine = self._screen(self._waiting())
        s.enter(None)
        self.assertIn("COM10", s.status)
        s.on_escape()
        self.assertFalse(engine.running)
        engine.show_title.assert_not_called()

    def test_picking_the_box_connects_saves_and_hands_back(self):
        markers = self._waiting()
        s, engine = self._screen(markers)
        box = _OpenPort("COM7")
        s.opener = MagicMock(return_value=(box, ""))
        s.enter(None)
        s.pick("COM7")
        self.assertIs(markers.backend, box)
        s.saver.assert_called_once_with(engine.cfg, "COM7")
        engine.eeg_port_ready.assert_called_once()
        self.assertIn("Connected on COM7", s.status)
        s.on_escape()
        engine.show_title.assert_called_once()
        self.assertTrue(engine.running)

    def test_a_port_that_will_not_open_changes_nothing(self):
        markers = self._waiting()
        s, engine = self._screen(markers)
        s.opener = MagicMock(return_value=(None, "Access is denied"))
        s.enter(None)
        s.pick("COM3")
        self.assertTrue(markers.needs_port)
        self.assertIn("Access is denied", s.status)
        s.saver.assert_not_called()
        engine.eeg_port_ready.assert_not_called()

    def test_running_hand_boards_are_not_offered(self):
        s, _ = self._screen(MarkerWriter(backend=_OpenPort("COM10"),
                                         enabled=True),
                            started=True, hands=("COM3",))
        s.enter(MagicMock())
        s.scan.assert_called_with(exclude=["COM3"])

    def test_at_launch_every_port_is_offered(self):
        # Nothing is open yet, and the box on a new COM number may be
        # the very port the start-up scan took for a hand board.
        s, _ = self._screen(self._waiting(), started=False,
                            hands=("COM3",))
        s.enter(None)
        s.scan.assert_called_with(exclude=[])

    def test_picking_the_port_in_use_reconnects_it(self):
        # A replugged cable leaves a handle that still says open.
        old = _OpenPort("COM7")
        markers = MarkerWriter(backend=old, enabled=True)
        s, _ = self._screen(markers)
        fresh = _OpenPort("COM7")
        s.opener = MagicMock(return_value=(fresh, ""))
        s.enter(MagicMock())
        s.pick("COM7")
        self.assertTrue(old.closed)
        self.assertIs(markers.backend, fresh)

    def test_from_settings_back_returns_there(self):
        back = MagicMock()
        s, engine = self._screen(MarkerWriter(backend=_OpenPort("COM10"),
                                              enabled=True))
        s.enter(back)
        s.on_escape()
        back.assert_called_once()
        self.assertTrue(engine.running)

    def test_it_draws_in_every_state(self):
        import pygame
        surf = pygame.Surface((1280, 800))
        s, _ = self._screen(self._waiting())
        s.enter(None)
        s.draw(surf)
        s.scan.return_value = []
        s.rescan()
        s.draw(surf)
        s, _ = self._screen(MarkerWriter(backend=DummyBackend(),
                                         enabled=True))
        s.enter(MagicMock())
        s.draw(surf)


# ---- FRN bytes follow the glyph and the mode ---------------------------------

class FeedbackMarkerTests(unittest.TestCase):

    def _engine(self, value):
        from finger_rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = SimpleNamespace(get=lambda k, d=None: value
                                  if k == "eeg.feedback_markers" else d)
        eng.feedback_delay_ms = 800
        eng._pending_feedback = []
        return eng

    def test_a_list_names_the_modes(self):
        eng = self._engine(["reaction", "chords", "force_pilot"])
        self.assertTrue(eng._feedback_markers_on("reaction"))
        self.assertFalse(eng._feedback_markers_on("syllables"))
        self.assertFalse(eng._feedback_markers_on(None))
        self.assertTrue(self._engine(True)._feedback_markers_on("rhythm"))
        self.assertFalse(self._engine(False)._feedback_markers_on("reaction"))

    def test_the_byte_is_the_ring_that_was_drawn(self):
        eng = self._engine(True)
        eng._eeg_feedback_markers = True
        for glyph, label, code in (("full", "Perfect", 140),
                                   ("half", "Late", 142),
                                   ("open", "Miss", 141)):
            with self.subTest(glyph=glyph):
                eng._pending_feedback = []
                eng._park_feedback("gameplay", 0, {"popup_glyph": glyph},
                                   (0, 0, 0), label)
                self.assertEqual(eng._pending_feedback[0][-1], code)

    def test_the_lab_config_names_only_the_sparse_modes(self):
        lab = yaml.safe_load(LAB_YAML.read_text())
        self.assertEqual(lab["eeg"]["feedback_markers"],
                         ["reaction", "chords", "force_pilot"])


if __name__ == "__main__":
    unittest.main()
