"""A sensor dropout leaves a trace where the analyst looks.

The engine has handled a board falling off mid-block for a long time
(the press latch is cleared, the banner shows, play resumes on
reconnect) and wrote source_disconnected / source_reconnected rows to
raw.csv. Nothing reached metadata.json or trials.csv: a trial whose
response window overlapped the drop was written as an honest timeout
and pooled with the real ones. These drive a real reaction block on
the battery's fake rig, with the board away for twelve seconds, and
read the files back.
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_hand_support import patched_clock


def setUpModule() -> None:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    import pygame
    pygame.quit()


class DropRig:
    """measure_battery's fake rig with a board that can go away.

    While blacked out it delivers no samples and reports itself
    disconnected, which is what _check_source_connection watches. With
    `per_hand` set it instead reports one hand down through
    hands_connected while the rig as a whole stays up, which is the
    one-board-of-two case _check_per_hand_connection handles.
    """

    provides_samples = True
    name = "SimulatedTwoBoardRig"
    hand_modes_available = {"right", "left", "both"}
    hands: list = []

    def __init__(self, per_hand: bool = False) -> None:
        self._q: deque = deque()
        self.commands: list[str] = []
        self.blackout = False
        self.is_connected = True
        self.per_hand = per_hand
        self._hands_ok = {"right": True, "left": True}

    @property
    def hands_connected(self):
        return dict(self._hands_ok) if self.per_hand else None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def push(self, t_perf, values, hand_mode) -> None:
        if self.blackout and not self.per_hand:
            return
        from finger_rehab.hardware.source import Sample
        vals = values if hand_mode == "both" else values[0:4]
        self._q.append(Sample(t_perf=t_perf, values=tuple(vals)))

    def get_sample(self, timeout: float = 0.0):
        return self._q.popleft() if self._q else None

    def send_command(self, cmd: str) -> bool:
        self.commands.append(cmd)
        return True


DROP_AT_S = 4.0
DROP_FOR_S = 12.0
SEED = 3


def _reaction_block(root: Path, code: str, drop: bool, hand: str = "right",
                    per_hand: bool = False, down_hand: str = "left"):
    """One real reaction block, optionally with a drop part way in.
    Returns the session folder."""
    import measure_battery as mb

    rig = DropRig(per_hand=per_hand)
    model = mb.HandModel()
    with patched_clock() as clock:
        eng = mb.build_engine(code, "right", root, rig)
        eng.cfg.data["game"]["test_mode_enabled"] = True
        eng.cfg.data["game"]["test_mode_trials"] = 12
        # Reaction draws its waits and lanes from this seed. Fixed so
        # the drop window holds the same cues every run: the one-board
        # case needs a LEFT cue inside it, which an unseeded draw
        # sometimes never produces.
        eng.cfg.data.setdefault("reaction", {})["seed"] = SEED
        if hand == "right":
            eng.begin_reaction_block()
        else:
            assert eng.begin_game("reaction", hand)
        who = mb.Participant(model, random.Random(4))
        who.begin_block()
        t0 = clock.t
        next_sample = clock.t
        dt = 1.0 / 120.0
        sample_dt = 1.0 / mb.SAMPLE_HZ
        for _ in range(200000):
            if not eng.block_is_running():
                break
            clock.t += dt
            now = clock.t
            since = now - t0
            if drop:
                want = DROP_AT_S <= since < DROP_AT_S + DROP_FOR_S
                if want and not rig.blackout:
                    rig.blackout = True
                    if per_hand:
                        rig._hands_ok[down_hand] = False
                    else:
                        rig.is_connected = False
                elif not want and rig.blackout:
                    rig.blackout = False
                    if per_hand:
                        rig._hands_ok[down_hand] = True
                    else:
                        rig.is_connected = True
            while next_sample <= now:
                rig.push(next_sample, model.sample(next_sample),
                         eng.hand_mode)
                next_sample += sample_dt
            eng._pump_source()
            eng._drain_motor_queue()
            if eng.screen_obj is not None:
                eng.screen_obj.update(dt)
            eng.markers.tick()
            who.act(eng, now)
            if since > 400.0:
                break
        if eng.trial_logger is not None:
            eng.finish_block()
    folders = sorted(p for p in root.rglob(f"{code}_*_reaction")
                     if p.is_dir())
    assert len(folders) == 1, folders
    return folders[0]


def _summary(folder: Path) -> dict:
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    return meta["block_summary"]


def _rows(folder: Path) -> list[dict]:
    with (folder / "trials.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


class WholeRigDropTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.dropped = _reaction_block(root, "DRP1", drop=True)
        cls.clean = _reaction_block(root, "DRP0", drop=False)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_the_block_summary_records_the_drop(self) -> None:
        conn = _summary(self.dropped)["connection"]
        self.assertEqual(conn["drops"], 1)
        self.assertAlmostEqual(conn["seconds_down"], DROP_FOR_S, delta=0.5)
        self.assertEqual(conn["hands"], ["right"])
        self.assertFalse(conn["still_down_at_end"])
        self.assertEqual(len(conn["intervals"]), 1)
        span = conn["intervals"][0]
        self.assertAlmostEqual(span["from_s"], DROP_AT_S, delta=0.5)
        self.assertAlmostEqual(span["to_s"], DROP_AT_S + DROP_FOR_S,
                               delta=0.5)

    def test_trials_eaten_by_the_drop_are_voided_not_timeouts(self) -> None:
        rows = _rows(self.dropped)
        voided = [r for r in rows if r["error_type"] == "device_drop"]
        self.assertGreaterEqual(len(voided), 1, "no trial was voided")
        for r in voided:
            self.assertEqual(r["early_late"], "Miss")
            self.assertEqual(r["keys_pressed"], "")
        # A twelve second hole in a block whose patient answers every
        # cue cannot produce an honest timeout.
        self.assertEqual(
            [r["trial"] for r in rows if r["error_type"] == "timeout"], [])
        conn = _summary(self.dropped)["connection"]
        self.assertEqual(conn["voided_trials"], len(voided))

    def test_voided_trials_stay_out_of_the_tallies(self) -> None:
        rows = _rows(self.dropped)
        s = _summary(self.dropped)
        # Catch trials (no cue, nothing to press) are never in the
        # hit and miss tallies either, drop or no drop.
        counted = [r for r in rows if r["error_type"] != "device_drop"
                   and "catch" not in r["stimulus"]]
        self.assertEqual(s["trials"], len(counted))
        self.assertEqual(s["hits"] + s["misses"], len(counted))

    def test_a_clean_block_reports_no_drop(self) -> None:
        conn = _summary(self.clean)["connection"]
        self.assertEqual(conn["drops"], 0)
        self.assertEqual(conn["seconds_down"], 0.0)
        self.assertEqual(conn["hands"], [])
        self.assertEqual(conn["voided_trials"], 0)
        self.assertEqual(
            [r for r in _rows(self.clean)
             if r["error_type"] == "device_drop"], [])


class OneBoardOfTwoDropTests(unittest.TestCase):
    """The left board falls off during a both-hands block. The right
    hand keeps playing and its trials must stay honest."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.folder = _reaction_block(root, "DRP2", drop=True, hand="both",
                                     per_hand=True, down_hand="left")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_the_summary_names_the_hand(self) -> None:
        conn = _summary(self.folder)["connection"]
        self.assertEqual(conn["drops"], 1)
        self.assertEqual(conn["hands"], ["left"])
        self.assertAlmostEqual(conn["seconds_down"], DROP_FOR_S, delta=0.5)

    def test_only_the_dead_hands_trials_are_voided(self) -> None:
        rows = _rows(self.folder)
        voided = [r for r in rows if r["error_type"] == "device_drop"]
        self.assertGreaterEqual(len(voided), 1)
        self.assertEqual({r["hand"] for r in voided}, {"left"})
        right_during = [
            r for r in rows if r["hand"] == "right"
            and DROP_AT_S <= float(r["block_t_s"]) < DROP_AT_S + DROP_FOR_S]
        self.assertGreaterEqual(len(right_during), 1,
                                "no right-hand trial fell inside the drop")
        for r in right_during:
            self.assertNotEqual(r["early_late"], "Miss", r)


if __name__ == "__main__":
    unittest.main()
