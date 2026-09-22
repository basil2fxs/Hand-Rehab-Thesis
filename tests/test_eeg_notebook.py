"""The EEG markers chapter of the notebook, on blocks the real engine
wrote under config/eeg_lab.yaml with the dummy trigger backend.

The chapter audits the game's side of the wire: the eeg rows of
raw.csv against the trial rows, the cue-to-response latency the
markers imply against time_difference_ms, the gap between wire
times, and the events export. Everything it prints is pinned here on
a reaction block and a mirror block driven through the real
GameEngine, and on the same tree with the markers stripped out, which
is what a keyboard or EEG-off session looks like.

The game runs on a virtual clock that also moves in real time inside
a frame, and the marker writer runs on that same clock, so the wire
times and the event times are comparable the way they are in a real
session. The scripted lab session in tests/test_eeg_markers_logged.py
keeps the writer on the real clock instead, which is right for its
byte-order checks and wrong for the delay figure this chapter prints.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_eeg_markers_logged import (_drive_lane_block, _lab_engine,
                                           _set, REAL_PERF)


class _HybridClock:
    """The scripted session's frame clock, with real time running
    inside a frame. The drivers advance `t` once per frame; a read
    between two advances returns the frame time plus the real seconds
    since it, so the writer's pulse and gap can run out and a wire
    time sits a few milliseconds after its event, never seconds."""

    def __init__(self, t0: float = 10_000.0) -> None:
        self._t = t0
        self._anchor = REAL_PERF()

    @property
    def t(self) -> float:
        return self._t

    @t.setter
    def t(self, value: float) -> None:
        now = REAL_PERF()
        # Never step back past real time already spent in the frame,
        # or the next wire time could precede the last one.
        self._t = max(float(value), self._t + (now - self._anchor))
        self._anchor = now

    def __call__(self) -> float:
        return self._t + (REAL_PERF() - self._anchor)


def _build_tree(root: Path) -> dict:
    """A reaction block and a mirror block under the lab overlay on
    the dummy backend, written into root as the game lays them out."""
    import pygame
    from finger_rehab.hardware.eeg_trigger import DummyBackend
    pygame.init()
    clock = _HybridClock()
    real = time.perf_counter
    time.perf_counter = clock
    out = {}
    try:
        eng, port = _lab_engine(str(root), "NbEeg")
        eng.markers.backend = DummyBackend()
        eng.markers._clock = clock
        eng.eeg_session_start()
        eng.markers.drain(0.5)
        cfg = eng.cfg
        _set(cfg, "reaction.seed", 907)
        _set(cfg, "reaction.catch_rate", 0.0)
        _set(cfg, "reaction.block_trials", 4)
        _set(cfg, "reaction.attempt_cap", 8)
        out["reaction"] = _drive_lane_block(
            eng, port, "reaction", "begin_reaction_block",
            ["correct", "wrong", "timeout", "correct"], clock)
        _set(cfg, "game.test_mode_enabled", True)
        _set(cfg, "game.test_mode_trials", 4)
        out["mirror"] = _drive_lane_block(
            eng, port, "mirror", "begin_mirror_block",
            ["correct", "right_only", "correct", "correct"], clock,
            hand="both")
        eng._eeg_shutdown()
    finally:
        time.perf_counter = real
        pygame.quit()
    return out


def _strip_markers(src: Path, dst: Path) -> None:
    """The same tree as a session recorded with markers off: no eeg
    rows, eeg.enabled false, no export files."""
    shutil.copytree(src, dst)
    for raw in dst.rglob("raw.csv"):
        lines = raw.read_text().splitlines(keepends=True)
        raw.write_text("".join(l for l in lines if ",eeg," not in l))
        folder = raw.parent
        meta = json.loads((folder / "metadata.json").read_text())
        meta.setdefault("eeg", {})["enabled"] = False
        (folder / "metadata.json").write_text(json.dumps(meta))
        for name in ("events.tsv", "events.json", "markers_codes.csv"):
            (folder / name).unlink(missing_ok=True)


def _eeg_rows(folder: Path) -> list[dict]:
    with (folder / "raw.csv").open(newline="") as f:
        return [r for r in csv.DictReader(f) if r["event"] == "eeg"]


class EegChapterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        from tests.test_mode_checks_notebook import _load_notebook
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name) / "sessions"
        cls.root.mkdir()
        cls.blocks = _build_tree(cls.root)
        cls.ra = _load_notebook()
        cls.ctx = cls.ra.prepare("all", root=str(cls.root))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.res = cls.ra.sec_eeg(cls.ctx["folders"], cls.ctx["trials"],
                                     cls.ctx["metas"])
        cls.text = buf.getvalue()
        cls.folders = {Path(f).name.split("_")[-1]: Path(f)
                       for f in cls.ctx["folders"]}

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_both_blocks_ran_to_the_end(self) -> None:
        for name, scn in self.blocks.items():
            self.assertTrue(scn["ended"], name)
        self.assertEqual(set(self.folders), {"reaction", "mirror"})

    def test_count_table_reconciles_with_the_rows(self) -> None:
        audit = self.res["audit"].set_index("mode")
        self.assertEqual(set(audit.index), {"reaction", "mirror"})
        for mode in ("reaction", "mirror"):
            self.assertTrue(audit.loc[mode, "ok"], audit.loc[mode, "problems"])
            self.assertEqual(audit.loc[mode, "n_failed"], 0)
            self.assertEqual(audit.loc[mode, "n_dropped"], 0)
        self.assertEqual(audit.loc["reaction", "n_rows"], 4)
        self.assertEqual(audit.loc["reaction", "n_stim"], 4)
        # One response byte per stimulus: correct, wrong, timeout, correct.
        self.assertEqual(audit.loc["reaction", "n_resp"], 4)
        # Mirror: one byte per hand that pressed; one pair was right only.
        self.assertEqual(audit.loc["mirror", "n_resp"], 7)
        counts = self.res["counts"]
        stim = counts[(counts["mode"] == "reaction")
                      & counts["band"].isin(["stim", "stim_pattern"])]
        self.assertEqual(int(stim["n"].sum()), 4)
        self.assertIn("reconciles", self.text)
        self.assertNotIn("does NOT reconcile", self.text)
        self.assertIn("rule: one stimulus byte per pair row", self.text)

    def test_every_marker_row_has_its_meaning_in_the_table(self) -> None:
        names = set(self.res["counts"]["name"])
        lab = self.res["lab"]
        listed = set(lab["name"])
        for name in names:
            base = name
            for prefix in ("resp_correct_lane", "resp_wrong_lane",
                           "resp_anticipation_lane"):
                if name.startswith(prefix):
                    base = prefix.replace("lane", "base")
            if name.startswith("block_start_"):
                base = "block_start_base"
            if name.startswith("block_end_"):
                base = "block_end_base"
            self.assertIn(base, listed, name)
        self.assertTrue((lab["meaning"] != "").all())
        self.assertTrue((lab["sent_by"] != "").all())
        self.assertIn("reaction", lab.set_index("name").loc[
            "prep_foreperiod", "seen_in"])

    def test_latency_agrees_with_the_trial_rows(self) -> None:
        lat = self.res["latency"]
        both = lat.dropna(subset=["csv_ms"])
        self.assertGreaterEqual(len(both[both["mode"] == "reaction"]), 2)
        # Both numbers come from the same press sample.
        self.assertLessEqual(float(both["diff_ms"].abs().max()),
                             self.ra.EEG_AGREE_MS)
        mirror = both[both["mode"] == "mirror"]
        self.assertEqual(set(mirror["hand"]), {"right", "left"})
        # The right-only pair contributes one line, not two.
        self.assertEqual(len(mirror), 7)
        self.assertIn("0 over that", self.text)

    def test_wire_gap_honours_pulse_plus_gap(self) -> None:
        wire = self.res["wire"].set_index("mode")
        for mode in ("reaction", "mirror"):
            self.assertGreaterEqual(wire.loc[mode, "min_gap_ms"],
                                    wire.loc[mode, "need_ms"] - 0.05, mode)
            # The lab overlay's widths are replaced by the harness's
            # 2 ms and 2 ms; the check is against what metadata says.
            self.assertEqual(wire.loc[mode, "need_ms"], 4.0)
        # Writer and game share a clock here, so a reaction byte that
        # did not wait for the line left within a couple of frames, and
        # a stimulus byte straight after its flip.
        self.assertLess(wire.loc["reaction", "max_prompt_delay_ms"], 100.0)
        self.assertLess(wire.loc["reaction", "max_prompt_stim_delay_ms"],
                        self.ra.EEG_STIM_DELAY_MS)
        # Mirror is the exception the chapter has to name: both hands'
        # bytes leave when the pair closes, so the right-only pair's
        # byte trailed its press by the pair window.
        self.assertGreater(wire.loc["mirror", "max_prompt_delay_ms"],
                           self.ra.EEG_FRAME_MS)
        self.assertIn("mirror sends both hands' response bytes", self.text)
        self.assertNotIn("UNDER THE GAP", self.text)

    def test_offsets_and_claim_limit_print(self) -> None:
        self.assertIn("measured: False", self.text)
        self.assertIn("datasheet estimates", self.text)
        self.assertIn("Nothing comes back from the amplifier", self.text)
        self.assertIn("from first_failure_t onward", self.text)

    def test_export_writes_bids_layout_one_row_per_marker(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (EVENT_COLUMNS,
                                                       export_events)
        for mode, folder in self.folders.items():
            paths = self.res["exports"][self.ra.game_key(folder)]
            self.assertEqual(paths["events"], folder / "events.tsv")
            self.assertIn(str(paths["events"]), self.text)
            with paths["events"].open() as f:
                header = f.readline().rstrip("\n").split("\t")
                body = f.read().splitlines()
            self.assertEqual(header[:2], ["onset", "duration"])
            self.assertEqual(header, EVENT_COLUMNS)
            self.assertEqual(len(body), len(_eeg_rows(folder)), mode)
            # The notebook's copy of the export writes what the package
            # writes, byte for byte, so a folder rebuilt on a machine
            # without the package is the same folder.
            with tempfile.TemporaryDirectory() as td:
                twin = Path(td) / folder.name
                shutil.copytree(folder, twin)
                export_events(twin)
                for name in ("events.tsv", "events.json"):
                    self.assertEqual((twin / name).read_text(),
                                     (folder / name).read_text(), (mode, name))

    def test_codes_csv_lists_every_code_the_map_can_produce(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES, codes_table
        for folder in self.folders.values():
            with (folder / "markers_codes.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            codes = {int(r["code"]) for r in rows}
            for name, code in CODES.items():
                self.assertIn(code, codes, name)
            self.assertEqual(codes, {r["code"] for r in codes_table()})
        # The notebook's own table, used when the folder has none,
        # covers the same bytes.
        own = {r["code"] for r in self.ra.eeg_codes_table()}
        self.assertEqual(own, {r["code"] for r in codes_table()})

    def test_literature_row_is_decided_by_the_audit(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ra.print_lit_checks("reaction")
            self.ra.print_lit_checks("mirror")
            self.ra.print_lit_checks("echo")
        lines = buf.getvalue().splitlines()
        eeg = [l for l in lines if l.strip().startswith("EEG")]
        self.assertEqual(len(eeg), 3, lines)
        self.assertIn("pass", eeg[0])
        self.assertIn("pass", eeg[1])
        self.assertIn("not testable", eeg[2])
        self.assertIn("not audited", buf.getvalue())

    def test_a_session_without_markers_says_so_in_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "sessions"
            _strip_markers(self.root, root)
            ctx = self.ra.prepare("all", root=str(root))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                res = self.ra.sec_eeg(ctx["folders"], ctx["trials"],
                                      ctx["metas"])
            self.assertIsNone(res)
            body = [l for l in buf.getvalue().splitlines()
                    if l.strip() and not l.startswith("=")
                    and l.strip() != "EEG MARKERS"]
            self.assertEqual(len(body), 1, body)
            self.assertIn("No EEG markers", body[0])
            for folder in root.rglob("raw.csv"):
                self.assertFalse((folder.parent / "events.tsv").exists())
            # The literature row then says the mode was not audited.
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.ra.print_lit_checks("reaction")
            self.assertIn("not audited", buf.getvalue())
        # Back to the marked tree for the tests that follow.
        type(self).ctx = self.ra.prepare("all", root=str(self.root))


if __name__ == "__main__":
    unittest.main()
