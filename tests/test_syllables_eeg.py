"""The syllables marker contract, run through the real engine.

tests/test_eeg_contract.py owns the map itself (bands, uniqueness, the
wire protocol). This file owns the one thing that map cannot check:
that a real syllables block emits the choice band the way the mode's
design says it does.

  - one 50 (or 51 on a returned word) per trials.csv row, one for one:
    the option-set onset IS the trial, so an analyst epoching on 50
    gets exactly the sets the CSV describes;
  - exactly one response code after each of them, and no 30-band byte
    in between;
  - the model's rolls carry the ordinary 30-band cue-condition code
    and are EXCLUDED from that count: they are the word being
    presented, not a trial, and pooling them with the choice sets
    would mix a cued stimulus with an uncued one;
  - 50 and 51 sit inside the documented 50-59 band and nothing else
    moved (CODES_VERSION 1.3).
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _stim_key(cell: str, key: str) -> str:
    """One key out of a packed stimulus cell."""
    for part in cell.split(";"):
        k, _, v = part.partition("=")
        if k == key:
            return v
    return ""


def _parse_detail(detail: str) -> dict:
    out = {}
    for part in detail.split(";"):
        key, _, val = part.partition("=")
        out[key] = val
    return out


def _run_block(words: int = 4, answer: str = "correct") -> dict:
    """One real syllables block with markers on, driven on a virtual
    clock. Returns the eeg rows, the trial rows and the codes in the
    order they were written."""
    import pygame
    pygame.init()
    try:
        with tempfile.TemporaryDirectory() as td:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.fsr_detector import PressEvent
            from finger_rehab.hardware.keyboard_source import (
                KeyboardOnlySource)
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [640, 480]
            cfg.data["audio"]["enabled"] = False
            cfg.data["session"]["data_dir"] = td
            cfg.data["session"]["participant"] = "EegProof"
            cfg.data["report"] = {"enabled": False}
            cfg.data["eeg"] = {"enabled": True, "port": None,
                               "require_port": False,
                               "pulse_ms": 2, "gap_ms": 2}
            cfg.data["syllables"]["speech"] = {"backend": "off"}
            cfg.data["syllables"]["words_per_block"] = words
            cfg.data["syllables"]["warmup_taps"] = 0
            cfg.data["syllables"]["break_s"] = 0
            cfg.data["syllables"]["seed"] = 21
            eng = GameEngine(cfg, KeyboardOnlySource())
            gp = MagicMock()
            gp.lanes = []
            eng._screens = {"gameplay": gp, "results": MagicMock(),
                            "syllables": MagicMock()}
            eng.show_results = lambda: None
            eng.begin_syllables_block()
            mode = eng.mode
            root = Path(eng.session_paths.root)
            answered: set = set()
            # The mode runs on a virtual clock passed straight into
            # _tick, so a block takes a moment instead of minutes,
            # while the marker writer keeps the real clock its pulse
            # and gap rules are written against.
            vt = 1000.0
            for _ in range(60000):
                if mode.phase == "done":
                    break
                vt += 1.0 / 120.0
                mode._tick(vt)
                eng._flush_eeg_stim()
                # Pump the writer empty every frame. A real session
                # has seconds between markers; this loop has
                # microseconds, so without draining, the queue (which
                # holds each code for its pulse plus the inter-marker
                # gap on the REAL clock) would still be emptying after
                # the block-end byte and the order on the wire would
                # be a harness artefact rather than the mode's.
                eng.markers.drain(0.5)
                if (mode.phase == "choose" and mode.option_set is not None
                        and mode._set_close_t is None):
                    key = (mode.word.word, mode.pos, mode.ret,
                           mode.trial_counter)
                    if (vt >= mode._spawn_t + 0.4
                            and key not in answered):
                        answered.add(key)
                        if answer == "correct":
                            lane = mode.option_set.target_lane
                        elif answer == "wrong":
                            lane = [o.lane for o in mode.option_set.options
                                    if o.lane != mode.option_set.target_lane
                                    ][0]
                        else:
                            continue
                        mode.queue_press(PressEvent(
                            lane=lane, t_perf=vt, value=0,
                            baseline=0.0, hand=mode.word_hand))
            eng.markers.drain(0.5)
            eng.finish_block()
            with (root / "raw.csv").open() as f:
                rows = list(csv.DictReader(f))
            with (root / "trials.csv").open() as f:
                trials = list(csv.DictReader(f))
            eeg_rows = [r for r in rows if r["event"] == "eeg"]
            return {
                "eeg": eeg_rows,
                "codes": [int(_parse_detail(r["detail"])["code"])
                          for r in eeg_rows],
                "trials": trials,
                "raw": rows,
                "phase": mode.phase,
            }
    finally:
        pygame.quit()


class SyllablesMarkerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.run_ok = _run_block(4, "correct")
        cls.run_miss = _run_block(4, "none")

    def test_the_block_ran(self) -> None:
        self.assertEqual(self.run_ok["phase"], "done")
        self.assertTrue(self.run_ok["trials"])

    def test_choice_codes_sit_in_the_documented_band(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (BANDS, CODES,
                                                       CODES_VERSION)
        self.assertEqual(CODES["stim_choice_set"], 50)
        self.assertEqual(CODES["stim_choice_set_return"], 51)
        lo, hi = BANDS["stim_choice_"]
        self.assertEqual((lo, hi), (50, 59))
        for name in ("stim_choice_set", "stim_choice_set_return"):
            self.assertTrue(lo <= CODES[name] <= hi)
        self.assertEqual(CODES_VERSION, "1.3")
        # Nothing else moved into the new band.
        for name, code in CODES.items():
            if 50 <= code <= 59:
                self.assertTrue(name.startswith("stim_choice_"), name)

    def test_one_choice_marker_per_trial_row(self) -> None:
        codes = self.run_ok["codes"]
        choice = [c for c in codes if c in (50, 51)]
        self.assertEqual(len(choice), len(self.run_ok["trials"]))
        self.assertGreater(len(choice), 3)

    def test_each_choice_marker_is_followed_by_one_response(self) -> None:
        codes = self.run_ok["codes"]
        idx = [i for i, c in enumerate(codes) if c in (50, 51)]
        for i, start in enumerate(idx):
            end = idx[i + 1] if i + 1 < len(idx) else len(codes)
            between = codes[start + 1:end]
            responses = [c for c in between if 100 <= c <= 131]
            self.assertEqual(len(responses), 1,
                             f"set {i} carried {responses}")
            self.assertTrue(100 <= responses[0] <= 107,
                            f"a clean set should mark a correct press, "
                            f"got {responses[0]}")

    def test_a_missed_set_marks_a_timeout_and_nothing_else(self) -> None:
        codes = self.run_miss["codes"]
        idx = [i for i, c in enumerate(codes) if c in (50, 51)]
        self.assertTrue(idx)
        for i, start in enumerate(idx):
            end = idx[i + 1] if i + 1 < len(idx) else len(codes)
            responses = [c for c in codes[start + 1:end]
                         if 100 <= c <= 131]
            self.assertEqual(responses, [130],
                             f"missed set {i} carried {responses}")

    def test_model_rolls_are_thirty_band_and_outside_the_count(
            self) -> None:
        # The word being modelled is a cued stimulus (screen, tone and
        # a four-finger tactile roll), so it keeps the ordinary
        # cue-condition byte and has no trial row. Pooling it with the
        # uncued choice sets would average two different stimuli.
        codes = self.run_ok["codes"]
        model = [c for c in codes if 30 <= c <= 39]
        self.assertTrue(model, "no 30-band model markers were emitted")
        # One per syllable modelled, which for a block every word of
        # which was completed is one per trial row.
        n_syll = sum(int(_stim_key(t["stimulus"], "nsyll"))
                     for t in self.run_ok["trials"]
                     if _stim_key(t["stimulus"], "pos") == "0")
        self.assertEqual(len(model), n_syll)
        # And they sit BEFORE the sets, never between a set and its
        # response: the first byte after a 50 that is either kind must
        # be the response, or an epoch on 50 reaches into a model
        # stimulus.
        idx = [i for i, c in enumerate(codes) if c in (50, 51)]
        for i, start in enumerate(idx):
            end = idx[i + 1] if i + 1 < len(idx) else len(codes)
            tail = [c for c in codes[start + 1:end]
                    if 30 <= c <= 39 or 100 <= c <= 131]
            self.assertTrue(tail, f"set {i} marked no response")
            self.assertTrue(100 <= tail[0] <= 131,
                            f"a model byte landed inside set {i}")
        self.assertEqual(len([c for c in codes if c in (50, 51)]),
                         len(self.run_ok["trials"]))

    def test_the_target_lane_is_recoverable_from_the_stream(self) -> None:
        # The 50-band byte carries no lane, and its raw row names the
        # lowest lane of the SET (the marker call arms the whole hand,
        # because a call naming only the target would put the answer
        # in the cue path). The target lane rides the set_spawn event
        # and the trial row instead, and the two must agree.
        spawns = [r for r in self.run_ok["raw"]
                  if r["event"] == "set_spawn"]
        trials = self.run_ok["trials"]
        self.assertEqual(len(spawns), len(trials))
        for spawn, trial in zip(spawns, trials):
            # trials.csv writes lanes 1-indexed, raw rows 0-indexed.
            self.assertEqual(int(spawn["lane"]) + 1, int(trial["lane"]))
            self.assertEqual(
                _stim_key(trial["stimulus"], "tlane"),
                str(int(spawn["lane"]) + 1))

    def test_the_set_spawn_event_matches_the_marker(self) -> None:
        spawns = [r for r in self.run_ok["raw"] if r["event"] == "set_spawn"]
        self.assertEqual(len(spawns), len(self.run_ok["trials"]))
        for row in spawns:
            detail = _parse_detail(row["detail"])
            self.assertIn("trial_id", detail)
            self.assertIn("rung", detail)
            self.assertIn("ret", detail)

    def test_returned_words_would_carry_the_return_code(self) -> None:
        # The all-miss run parks and returns words, so 51 has to be
        # reachable; if the return queue never fires in two words the
        # code path is still checked by the mode hook.
        from finger_rehab.hardware.eeg_trigger import CODES
        codes = self.run_miss["codes"]
        rets = [t for t in self.run_miss["trials"]
                if "ret=1" in t["stimulus"] or "ret=2" in t["stimulus"]]
        if rets:
            self.assertIn(CODES["stim_choice_set_return"], codes)
        else:
            self.skipTest("no return came due inside the block")


if __name__ == "__main__":
    unittest.main()
