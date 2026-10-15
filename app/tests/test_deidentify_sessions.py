"""scripts/deidentify_sessions.py: the self-run sittings log in under a
name, and the analysis only reads codes, so the copy must swap every
name for a code without touching the data."""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import deidentify_sessions as D  # noqa: E402
from finger_rehab.data.intake import is_study_code  # noqa: E402


def _block(raw: Path, day: str, who: str, clock: str, mode: str, *,
           sitting=True, demo=False, started=None, extra=None) -> Path:
    folder = raw / day / f"{who}_{clock}_{mode}"
    folder.mkdir(parents=True)
    meta = {
        "participant": who, "visit": "1", "dominant_hand": "right",
        "started_at": started or f"{day}T{clock[:2]}:{clock[2:4]}:{clock[4:]}",
        "battery": {"phase": "pass1", "preset": "healthy_one_hand_v3"} if sitting else {},
        "calibration": {"participant": who, "by_hand": {"right": {"participant": who}}},
        "config_snapshot": {"session": {"participant": who},
                            "game": {"test_mode_enabled": demo}},
        "block_summary": {mode: {"status": "completed",
                                 "reference_basis": {"right": {"participant": who}}}},
    }
    meta.update(extra or {})
    (folder / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    with (folder / "trials.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["iso_ts", "block_t_s", "participant", "lane", "time_difference_ms"])
        w.writerow(["2026-10-16T10:15:01", "1.0", who, "2", "251.5"])
        w.writerow(["2026-10-16T10:15:02", "2.0", who, "0", "240.0"])
    with (folder / "summary.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows([["participant", "mode"], [who, mode]])
    (folder / "raw.csv").write_text("t,f0,f1,f2,f3\n0.000,10,3,4,30\n", encoding="utf-8")
    (folder / "report.html").write_text(f"<h1>{who}</h1>", encoding="utf-8")
    (folder / "charts").mkdir()
    (folder / "charts" / "rt.png").write_bytes(b"png")
    return folder


class Tree:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw = self.root / "raw"
        self.out = self.root / "coded"
        r = self.raw
        _block(r, "2026-10-16", "Sarah", "101500", "reaction")
        _block(r, "2026-10-16", "sarah ", "103000", "chords")
        _block(r, "2026-10-17", "Tom", "090000", "force_pilot")
        _block(r, "2026-10-17", "Tom", "091500", "chords", demo=True)
        _block(r, "2026-10-15", "Basil", "120000", "reaction")
        _block(r, "2026-10-15", "test", "110000", "reaction")
        _block(r, "2026-10-16", "Amy", "080000", "echo", sitting=False)

    def run(self, **kw):
        with redirect_stdout(io.StringIO()):
            return D.run(self.raw, self.out, **kw)

    def close(self):
        self.tmp.cleanup()


class DeidentifyTests(unittest.TestCase):

    def setUp(self):
        self.t = Tree()

    def tearDown(self):
        self.t.close()

    def test_codes_follow_the_first_sitting_and_skip_tests(self):
        shown = self.t.run(exclude=["Basil"])
        self.assertEqual(shown, {"Sarah": "P01", "sarah ": "P01", "Tom": "P02"})
        folders = sorted(p.name for p in self.t.out.rglob("*_*_*") if p.is_dir())
        self.assertEqual(folders, ["P01_101500_reaction", "P01_103000_chords",
                                   "P02_090000_force_pilot"])
        self.assertTrue(all(is_study_code(f.split("_")[0]) for f in folders))

    def test_every_participant_field_is_swapped_and_the_data_kept(self):
        self.t.run(exclude=["Basil"])
        block = self.t.out / "2026-10-16" / "P01_101500_reaction"
        meta = json.loads((block / "metadata.json").read_text())
        self.assertEqual(meta["participant"], "P01")
        self.assertEqual(meta["calibration"]["participant"], "P01")
        self.assertEqual(meta["calibration"]["by_hand"]["right"]["participant"], "P01")
        self.assertEqual(meta["config_snapshot"]["session"]["participant"], "P01")
        self.assertEqual(meta["block_summary"]["reaction"]["reference_basis"]["right"]["participant"], "P01")
        self.assertEqual(meta["battery"]["phase"], "pass1")
        rows = list(csv.reader((block / "trials.csv").open()))
        self.assertEqual([r[2] for r in rows[1:]], ["P01", "P01"])
        self.assertEqual([r[4] for r in rows[1:]], ["251.5", "240.0"])
        self.assertEqual((block / "raw.csv").read_text(),
                         "t,f0,f1,f2,f3\n0.000,10,3,4,30\n")

    def test_name_bearing_extras_are_not_copied(self):
        self.t.run(exclude=["Basil"])
        block = self.t.out / "2026-10-16" / "P01_101500_reaction"
        self.assertFalse((block / "report.html").exists())
        self.assertFalse((block / "charts").exists())

    def test_hub_only_demo_and_excluded_blocks_stay_behind(self):
        self.t.run(exclude=["Basil"])
        names = {p.name for p in self.t.out.rglob("*") if p.is_dir()}
        for gone in ("Amy_080000_echo", "Basil_120000_reaction",
                     "test_110000_reaction", "P02_091500_chords"):
            self.assertNotIn(gone, names)

    def test_numbering_can_start_after_an_earlier_set(self):
        shown = self.t.run(exclude=["Basil"], first=11)
        self.assertEqual(sorted(set(shown.values())), ["P11", "P12"])

    def test_a_name_left_in_another_field_stops_the_run(self):
        _block(self.t.raw, "2026-10-18", "Zoe", "100000", "echo",
               extra={"notes": "Zoe"})
        with self.assertRaises(SystemExit):
            self.t.run(exclude=["Basil"])
        self.assertFalse(self.t.out.exists())

    def test_an_existing_output_folder_is_never_overwritten(self):
        self.t.out.mkdir()
        with self.assertRaises(SystemExit):
            self.t.run()


if __name__ == "__main__":
    unittest.main()
