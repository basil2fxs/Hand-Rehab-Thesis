"""A wrong finger is marked when it lands, not when its trial closes.

Found by running the lab folder in real time against a virtual trigger
box: in classic the 113 reached the wire about a second after the
stimulus although the finger had pressed at 355 ms. Classic, adaptive,
mirror, pattern, chords and syllables keep a trial open after a wrong
press (the cue stays lit until the right finger or the deadline) and
sent the byte only when the trial was logged. raw.csv kept the press
time, but a lab epoching the BDF on the byte would have cut the ERN
hundreds of ms after the error it is locked to.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_eeg_contract import _EngineHarness  # noqa: E402


class TheByteLeavesAtThePress(_EngineHarness):

    def test_classic_wrong_finger_is_on_the_wire_before_the_trial_closes(self):
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_classic_block()
                mode = eng.mode
                self._settle(eng)
                mode._fire(now=100.0)
                eng._flush_eeg_stim()
                self._settle(eng)
                lane = mode.active.lane
                wrong = (lane + 1) % 4
                mode._handle_press(self._press(wrong, 100.35), now=100.35)
                self._settle(eng)
                # The trial is still open (the cue stays lit), and the
                # wrong byte is already out.
                self.assertIsNotNone(mode.active)
                self.assertIn(110 + wrong, self._wire_codes(eng))
                # The right finger then closes it: a Miss row, and no
                # second wrong byte and no correct byte.
                mode._handle_press(self._press(lane, 100.6), now=100.6)
                self._settle(eng)
                self.assertIsNone(mode.active)
                codes = self._wire_codes(eng)
                self.assertEqual(codes.count(110 + wrong), 1)
                self.assertFalse([c for c in codes if 100 <= c <= 107])
                eng.finish_block()
        finally:
            pygame.quit()

    def test_only_the_first_wrong_press_of_a_trial_is_marked(self):
        from finger_rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        sent = []
        eng._eeg_send = lambda code, lane=None, t_event=None: sent.append(
            (code, t_event))
        presses = [(2, 5.0)]
        eng.eeg_wrong_press(presses)
        presses.append((3, 5.2))
        eng.eeg_wrong_press(presses)
        self.assertEqual(sent, [(112, 5.0)])
        self.assertTrue(eng._eeg_wrong_already_sent(2, 5.0))
        self.assertFalse(eng._eeg_wrong_already_sent(3, 5.2))

    def test_every_mode_that_keeps_a_trial_open_marks_at_the_press(self):
        # Each mode appends to incorrect_presses and calls the engine
        # straight after, in that order.
        modes = ROOT / "finger_rehab" / "game" / "modes"
        for name in ("classic", "adaptive", "mirror", "pattern", "chords",
                     "syllables"):
            with self.subTest(mode=name):
                text = (modes / f"{name}.py").read_text()
                i = text.index("incorrect_presses.append((ev.lane, ev.t_perf))")
                nxt = text[i:i + 200]
                self.assertIn(
                    "self.engine.eeg_wrong_press(self.active.incorrect_presses)",
                    nxt)


class TheLabBuildLeavesTheMachineAlone(unittest.TestCase):

    def test_no_auto_start_in_the_lab_build(self):
        # The lab exe is the home exe beside eeg_lab.yaml; its first
        # launch must not register a logon task on a shared lab PC.
        import importlib.util
        spec = importlib.util.spec_from_file_location("app_main",
                                                      ROOT / "main.py")
        main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main)
        cfg = SimpleNamespace(get=lambda k, d=None: k == "eeg.enabled" or d)
        from unittest.mock import patch
        with patch("finger_rehab.hardware.autostart.sync") as sync:
            self.assertEqual(main._sync_autostart(cfg, None), "")
        sync.assert_not_called()

    def test_the_data_root_can_be_set_by_the_launcher(self):
        import os
        from unittest.mock import patch
        from finger_rehab import config
        with tempfile.TemporaryDirectory() as td, \
                patch.dict(os.environ, {config.DATA_ROOT_ENV: td}):
            self.assertEqual(config._user_root(), Path(td).resolve())


class TheBoxIsKnownByItsUsbIdentity(unittest.TestCase):

    def test_a_box_back_on_a_new_com_number_is_still_not_a_hand(self):
        from unittest.mock import patch
        from finger_rehab.config import Config
        from finger_rehab.hardware import eeg_trigger
        from finger_rehab.hardware.discovery import hand_board_ports
        from finger_rehab.hardware.serial_source import PortInfo
        cfg = Config.load()
        cfg.data["eeg"] = {"enabled": True, "port": "COM10"}
        cfg.data["serial"]["vendor_ids"] = ["0x0403", "0x1A86"]
        box_now = PortInfo("COM8", "USB Serial Device", 0x0403, 0x6001,
                           "MMBT1234")
        nano = PortInfo("COM5", "USB-SERIAL CH340", 0x1A86, 0x7523, None)
        with patch.object(eeg_trigger, "BOX_IDS", {box_now.hardware_id}), \
                patch("finger_rehab.hardware.serial_source."
                      "list_available_ports", return_value=[box_now, nano]):
            self.assertEqual(hand_board_ports(cfg, max_ports=8), ["COM5"])

    def test_bench_scripts_refuse_to_guess_between_two_devices(self):
        from unittest.mock import patch
        from finger_rehab.hardware.serial_source import PortInfo, bench_port
        box = PortInfo("COM10", "USB Serial Device", 0x0403, 0x6001, "X")
        nano = PortInfo("COM5", "USB-SERIAL CH340", 0x1A86, 0x7523, None)
        with patch("finger_rehab.hardware.serial_source."
                   "list_available_ports", return_value=[box, nano]):
            port, why = bench_port()
        self.assertIsNone(port)
        self.assertIn("trigger box", why)
        with patch("finger_rehab.hardware.serial_source."
                   "list_available_ports", return_value=[nano]):
            self.assertEqual(bench_port(), ("COM5", ""))


if __name__ == "__main__":
    unittest.main()
