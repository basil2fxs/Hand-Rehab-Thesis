"""The SRT timing group is the computer's, not the participant's.

The setup screen opens on the group last picked on this computer,
whoever logs in and however many sessions pass, and a new pick is
saved for next time (Basil, 2 October 2026). One file per computer,
outside every app folder, so the code run, the installed app and the
lab folder's exe share it and a refreshed lab folder keeps it.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from finger_rehab.game import srt_setup as ss  # noqa: E402
from tests.test_srt_mode import _engine, _fast_cfg  # noqa: E402


class WhereTheChoiceLives(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.shared = self.root / "shared" / "Finger Rehab" / "srt_setups.json"
        self.user_root = self.root / "app_folder"
        env = {k: v for k, v in os.environ.items() if k != ss.SETUPS_ENV}
        self.patches = [
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(ss, "shared_store_path",
                              return_value=self.shared),
            mock.patch("finger_rehab.config.USER_ROOT", self.user_root),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.td.cleanup()

    def test_one_file_for_the_computer(self):
        self.assertEqual(ss.store_path(None), self.shared)
        self.assertTrue(self.shared.parent.is_dir())

    def test_a_file_kept_beside_the_app_is_carried_over_once(self):
        local = self.user_root / "config" / "srt_setups.json"
        old = ss.SetupStore(local)
        self.assertEqual(old.set_current(ss.SRTSetup(
            "x", "random", 500, ss.LAB_SEQUENCE)), "")
        path = ss.store_path(None)
        self.assertEqual(path, self.shared)
        self.assertEqual(ss.SetupStore(path).current.group, "random")
        # Later picks go to the computer's file; the old one is left be.
        ss.SetupStore(path).set_current(ss.SRTSetup(
            "y", "cyclical", 500, ss.LAB_SEQUENCE))
        self.assertEqual(ss.SetupStore(ss.store_path(None)).current.group,
                         "cyclical")

    def test_falls_back_beside_the_app_when_it_cannot_write(self):
        with mock.patch.object(ss, "_shared_folder_ready",
                               return_value=False):
            self.assertEqual(ss.store_path(None),
                             self.user_root / "config" / "srt_setups.json")

    def test_a_test_run_or_a_config_can_point_it_elsewhere(self):
        with mock.patch.dict(os.environ, {ss.SETUPS_ENV: str(
                self.root / "elsewhere.json")}):
            self.assertEqual(ss.store_path(None),
                             self.root / "elsewhere.json")
        cfg = mock.MagicMock()
        cfg.get = mock.MagicMock(return_value=str(self.root / "cfg.json"))
        self.assertEqual(ss.store_path(cfg), self.root / "cfg.json")


class TheScreenRemembersTheGroup(unittest.TestCase):
    """Three logins on one computer: each opens on the group the last
    one picked, and a pick is saved straight away."""

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()
        pygame.quit()

    def _screen(self, who):
        eng = _engine(self.root, **_fast_cfg())
        eng.cfg.data["session"]["participant"] = who
        eng.set_hand_mode("right")
        eng.show_srt_setup()
        return eng, eng._screens["srt_setup"]

    def _pick(self, sc, group):
        sc.group_seg.set(group)
        sc.handle_event(pygame.event.Event(pygame.USEREVENT, {}))

    def test_the_last_pick_carries_to_the_next_login(self):
        _eng, sc = self._screen("P01")
        self.assertEqual(sc.group, "constant")
        self._pick(sc, "cyclical")
        _eng, sc = self._screen("P02")
        self.assertEqual(sc.group, "cyclical")
        self.assertEqual(sc.group_seg.value, "cyclical")
        self._pick(sc, "random")
        _eng, sc = self._screen("P03")
        self.assertEqual(sc.group, "random")
        saved = json.loads((self.root / "srt_setups.json").read_text())
        self.assertEqual(saved["current"]["group"], "random")

    def test_start_keeps_the_group_and_the_block_plays_it(self):
        eng, sc = self._screen("P01")
        self._pick(sc, "cyclical")
        sc._start()
        self.addCleanup(eng._abandon_if_in_block)
        self.assertEqual(eng.mode.setup.group, "cyclical")
        _eng2, sc2 = self._screen("P02")
        self.assertEqual(sc2.group, "cyclical")


if __name__ == "__main__":
    unittest.main()
