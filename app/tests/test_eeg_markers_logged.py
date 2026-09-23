"""Markers on disk and the lab export.

Every byte the marker writer sends is also a raw.csv eeg row, written
from the same emission, so the log and the wire cannot disagree. This
file pins the parts of that record the lab uses: the resolved code
name on every row, the code table, the BIDS events export written at
block end and rebuildable from any session folder, the marker gaps the
research pass found (Force Pilot runs with no byte, the last trial's
feedback byte lost under the lab style, a feedback byte parked for a
continuous row), and a scripted lab session under config/eeg_lab.yaml
on a fake trigger port with every mode played once, asserting the
bytes on the wire equal the codes in the log.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO = Path(__file__).resolve().parents[1]
LAB_YAML = REPO / "config" / "eeg_lab.yaml"
DT = 1.0 / 120.0
REAL_PERF = time.perf_counter


def _eeg_rows(root: Path) -> list[dict]:
    from finger_rehab.hardware.eeg_trigger import parse_detail
    out = []
    with (root / "raw.csv").open(newline="") as f:
        for r in csv.DictReader(f):
            if r["event"] == "eeg":
                d = parse_detail(r["detail"])
                d["lane"] = r["lane"]
                d["t_perf"] = r["t_perf"]
                out.append(d)
    return out


def _trial_rows(root: Path) -> list[dict]:
    path = root / "trials.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def _tsv_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ---------------------------------------------------------------------------
# The record itself: names, detail cell, code table
# ---------------------------------------------------------------------------

class NameTests(unittest.TestCase):

    def test_names_resolve_lane_and_mode(self) -> None:
        from finger_rehab.hardware.eeg_trigger import name_of
        self.assertEqual(name_of(30), "stim_visual")
        self.assertEqual(name_of(100), "resp_correct_lane0")
        self.assertEqual(name_of(103), "resp_correct_lane3")
        self.assertEqual(name_of(117), "resp_wrong_lane7")
        self.assertEqual(name_of(125), "resp_anticipation_lane5")
        self.assertEqual(name_of(130), "resp_timeout")
        self.assertEqual(name_of(200), "block_start_reaction")
        self.assertEqual(name_of(212), "block_start_echo")
        self.assertEqual(name_of(219), "block_abandoned")
        self.assertEqual(name_of(232), "block_end_echo")
        self.assertEqual(name_of(23), "prep_run_start")
        self.assertEqual(name_of(24), "prep_segment_edge")
        self.assertEqual(name_of(7), "unknown")

    def test_every_named_code_round_trips(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES, name_of
        for name, code in CODES.items():
            got = name_of(code)
            if name.endswith("_base"):
                # The base byte is lane 0 or mode id 0 in resolved form.
                self.assertTrue(got.endswith("lane0")
                                or got.endswith("_reaction"), (name, got))
            else:
                self.assertEqual(got, name)

    def test_detail_cell_carries_the_name_and_parses_back(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (MarkerEmission,
                                                       format_detail,
                                                       parse_detail)
        rec = MarkerEmission(code=113, lane=3, t_event=10.5, t_wire=10.5012,
                             delayed=True, failed=False)
        detail = format_detail(rec)
        self.assertTrue(detail.endswith(";name=resp_wrong_lane3"), detail)
        parsed = parse_detail(detail)
        self.assertEqual(parsed["code"], "113")
        self.assertEqual(parsed["delayed"], "1")
        self.assertEqual(parsed["name"], "resp_wrong_lane3")
        # The fields the contract test has always parsed are still
        # there, in the same order, so an old reader keeps working.
        self.assertEqual(list(parsed)[:6],
                         ["code", "t_event", "t_wire", "delayed", "failed",
                          "dropped"])


class CodesTableTests(unittest.TestCase):

    def test_table_covers_every_byte_the_map_can_produce(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (CODES, CODES_VERSION,
                                                       MODE_IDS, codes_table)
        rows = codes_table()
        codes = [r["code"] for r in rows]
        self.assertEqual(codes, sorted(codes))
        self.assertEqual(len(codes), len(set(codes)))
        for name, code in CODES.items():
            self.assertIn(code, codes, name)
        for base in (100, 110, 120):
            for lane in range(8):
                self.assertIn(base + lane, codes)
        for mode_id in MODE_IDS.values():
            self.assertIn(200 + mode_id, codes)
            self.assertIn(220 + mode_id, codes)
        self.assertTrue(all(r["codes_version"] == CODES_VERSION for r in rows))
        self.assertTrue(all(r["band"] != "unknown" for r in rows))

    def test_every_code_has_a_note(self) -> None:
        # A code without a note is a code the lab cannot interpret.
        from finger_rehab.hardware.eeg_trigger import CODES, CODE_NOTES
        self.assertEqual(set(CODE_NOTES), set(CODES))
        for name, (locks, _offset, meaning, _notes) in CODE_NOTES.items():
            self.assertTrue(locks, name)
            self.assertTrue(meaning, name)

    def test_offset_keys_exist_in_marker_offsets(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (CODE_NOTES,
                                                       marker_offsets)
        offsets = marker_offsets(45, 20, 12)
        for name, (_l, key, _m, _n) in CODE_NOTES.items():
            if key:
                self.assertIn(key, offsets, name)


# ---------------------------------------------------------------------------
# The export, from a hand-written raw.csv
# ---------------------------------------------------------------------------

RAW_HEADER = ("iso_ts,t_perf,sample_idx,fsr1,fsr2,fsr3,fsr4,fsr5,fsr6,fsr7,"
              "fsr8,hand,event,lane,detail\n")


def _raw_line(t: float, event: str = "", lane: str = "",
              detail: str = "") -> str:
    return f"x,{t:.6f},1,0,0,0,0,0,0,0,0,right,{event},{lane},{detail}\n"


def _eeg_line(t: float, code: int, lane: str = "", t_wire: str | None = None,
              delayed: int = 0, failed: int = 0, dropped: int = 0,
              name: str | None = None) -> str:
    wire = f"{t + 0.0005:.6f}" if t_wire is None else t_wire
    detail = (f"code={code};t_event={t:.6f};t_wire={wire};"
              f"delayed={delayed};failed={failed};dropped={dropped}")
    if name is not None:
        detail += f";name={name}"
    return _raw_line(t, "eeg", lane, detail)


class ExportFileTests(unittest.TestCase):

    def setUp(self) -> None:
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        (self.root / "raw.csv").write_text(
            RAW_HEADER
            + _raw_line(100.0, "block_start", "", "reaction")
            + _raw_line(100.5)                       # first force sample
            + _eeg_line(100.6, 200, name="block_start_reaction")
            + _eeg_line(100.55, 20, delayed=1)       # queued, out of order
            + _eeg_line(103.0, 30, lane="2")
            + _eeg_line(103.3, 102, lane="2", t_wire="", failed=1))
        (self.root / "metadata.json").write_text(json.dumps({
            "eeg": {"pulse_ms": 8, "gap_ms": 12, "codes_version": "1.4",
                    "box": "mmbt-s", "box_mode": "pulse",
                    "backend": "serial", "degraded": False}}))

    def test_bids_columns_and_row_order(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (EVENT_COLUMNS,
                                                       export_events)
        paths = export_events(self.root)
        self.assertEqual(paths["events"], self.root / "events.tsv")
        rows = _tsv_rows(paths["events"])
        with paths["events"].open() as f:
            header = f.readline().rstrip("\n").split("\t")
        self.assertEqual(header[:2], ["onset", "duration"])
        self.assertEqual(header, EVENT_COLUMNS)
        # One row per eeg row, sorted by the intended event time, so
        # the queued 20 comes before the 200 it left the wire behind.
        self.assertEqual([int(r["value"]) for r in rows], [20, 200, 30, 102])
        self.assertEqual([r["trial_type"] for r in rows],
                         ["prep_countdown", "block_start_reaction",
                          "stim_visual", "resp_correct_lane2"])
        # onset counts from the first force sample, not the first row.
        self.assertAlmostEqual(float(rows[0]["onset"]), 0.05, places=6)
        self.assertAlmostEqual(float(rows[2]["onset"]), 2.5, places=6)
        self.assertEqual(rows[0]["duration"], "0.008")
        self.assertEqual(rows[0]["sample"], "n/a")
        self.assertEqual(rows[0]["lane"], "n/a")
        self.assertEqual(rows[2]["lane"], "2")
        self.assertEqual(rows[0]["delayed"], "1")
        # The failed write stays in, flagged, with no wire time.
        self.assertEqual(rows[3]["failed"], "1")
        self.assertEqual(rows[3]["t_wire"], "n/a")

    def test_sample_column_follows_the_amplifier_rate(self) -> None:
        from finger_rehab.hardware.eeg_trigger import export_events
        paths = export_events(self.root, sample_rate_hz=2048)
        rows = _tsv_rows(paths["events"])
        self.assertEqual(rows[2]["sample"], str(round(2.5 * 2048)))
        side = json.loads(paths["sidecar"].read_text())
        self.assertEqual(side["sample"]["AmplifierRateHz"], 2048.0)

    def test_sidecar_and_code_table_travel_with_the_events(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (CODES_VERSION,
                                                       codes_table,
                                                       export_events)
        paths = export_events(self.root)
        side = json.loads(paths["sidecar"].read_text())
        for col in ("onset", "duration", "trial_type", "value"):
            self.assertIn("Description", side[col])
        self.assertEqual(side["CodesVersion"], "1.4")
        self.assertEqual(side["PulseMs"], 8)
        self.assertIn("first raw.csv force sample", side["onset"]["Description"])
        with paths["codes"].open(newline="") as f:
            table = list(csv.DictReader(f))
        self.assertEqual(len(table), len(codes_table()))
        self.assertEqual(table[0]["codes_version"], CODES_VERSION)

    def test_missing_raw_is_an_error_not_an_empty_file(self) -> None:
        from finger_rehab.hardware.eeg_trigger import export_events
        with self.assertRaises(FileNotFoundError):
            export_events(self.root / "nowhere")

    def test_keyboard_block_counts_from_the_block_start_row(self) -> None:
        # No force samples in a keyboard block: the block_start event
        # is the reference instead, and the sidecar says which.
        from finger_rehab.hardware.eeg_trigger import export_events
        (self.root / "raw.csv").write_text(
            RAW_HEADER
            + _raw_line(50.0, "block_start", "", "classic")
            + _eeg_line(51.0, 201))
        rows = _tsv_rows(export_events(self.root)["events"])
        self.assertAlmostEqual(float(rows[0]["onset"]), 1.0, places=6)


# ---------------------------------------------------------------------------
# The engine: files at block end, the gaps closed
# ---------------------------------------------------------------------------

class _EngineHarness(unittest.TestCase):
    """A real GameEngine on the keyboard source with the dummy EEG
    backend, the contract test's harness."""

    def _make_engine(self, td: str, eeg_enabled: bool = True,
                     feedback_delay_ms: int = 0,
                     feedback_markers: bool = False):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["ui"]["feedback_delay_ms"] = feedback_delay_ms
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = td
        cfg.data["report"] = {"enabled": False}
        cfg.data["reaction"] = {"seed": 1234, "catch_rate": 0.0}
        cfg.data["cue"] = {"buzz_before": False, "sound_before": False,
                           "sound_after": False, "buzz_after": False,
                           "show_target": True}
        cfg.data["eeg"] = {"enabled": eeg_enabled, "port": None,
                           "require_port": False,
                           "pulse_ms": 2, "gap_ms": 2,
                           "feedback_markers": feedback_markers}
        eng = GameEngine(cfg, KeyboardOnlySource())
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock()}
        return eng

    @staticmethod
    def _press(lane: int, t: float):
        from finger_rehab.hardware.fsr_detector import PressEvent
        return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                          hand="right")

    @staticmethod
    def _settle(eng) -> None:
        eng.markers.drain(0.2)
        time.sleep(0.01)

    @staticmethod
    def _trial(lane=0, stim_t=100.0):
        from finger_rehab.game.modes.classic import PendingTrial
        return PendingTrial(trial_id=1, lane=lane, stim_t_perf=stim_t,
                            keys_pressed=[lane], incorrect_presses=[])

    def _one_reaction_trial(self, eng) -> None:
        mode = eng.mode
        self._settle(eng)
        mode._begin_trial(now=100.0)
        self._settle(eng)
        mode._fire(now=103.0)
        eng._flush_eeg_stim()
        self._settle(eng)
        mode._handle_press(self._press(mode.active.lane, 103.3), now=103.3)
        self._settle(eng)


class EngineExportTests(_EngineHarness):

    def test_block_end_writes_the_three_files_from_the_log(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.eeg_session_start()
                eng.begin_reaction_block()
                self._one_reaction_trial(eng)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                for name in ("events.tsv", "events.json",
                             "markers_codes.csv"):
                    self.assertTrue((root / name).is_file(), name)
                logged = _eeg_rows(root)
                exported = _tsv_rows(root / "events.tsv")
                self.assertEqual(len(exported), len(logged))
                self.assertGreaterEqual(len(exported), 5)
                logged.sort(key=lambda d: float(d["t_event"]))
                self.assertEqual([int(r["value"]) for r in exported],
                                 [int(d["code"]) for d in logged])
                self.assertEqual([r["trial_type"] for r in exported],
                                 [d["name"] for d in logged])
                # Every row carries the resolved name in the log too.
                for d in logged:
                    self.assertTrue(d.get("name"), d)
                meta = json.loads((root / "metadata.json").read_text())
                from finger_rehab.hardware.eeg_trigger import CODES
                self.assertEqual(meta["eeg"]["codes"], CODES)
                self.assertEqual(meta["eeg"]["codes_version"], "1.5")
        finally:
            pygame.quit()

    def test_abandoned_block_exports_too(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_reaction_block()
                self._one_reaction_trial(eng)
                root = Path(eng.session_paths.root)
                eng._abandon_if_in_block()
                rows = _tsv_rows(root / "events.tsv")
                self.assertIn(219, [int(r["value"]) for r in rows])
        finally:
            pygame.quit()

    def test_disabled_markers_write_no_events_files(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td, eeg_enabled=False)
                eng.begin_reaction_block()
                self._one_reaction_trial(eng)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                self.assertTrue((root / "trials.csv").is_file())
                for name in ("events.tsv", "events.json",
                             "markers_codes.csv"):
                    self.assertFalse((root / name).exists(), name)
        finally:
            pygame.quit()

    def test_export_rebuilds_from_any_folder(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_reaction_block()
                self._one_reaction_trial(eng)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                first = (root / "events.tsv").read_text()
                (root / "events.tsv").unlink()
                from finger_rehab.hardware.eeg_trigger import export_events
                export_events(root)
                self.assertEqual((root / "events.tsv").read_text(), first)
        finally:
            pygame.quit()


class FeedbackGapTests(_EngineHarness):
    """The lab style parks the glyph for feedback_delay_ms. Two gaps
    the research pass found are closed here."""

    def test_a_glyph_cut_short_by_the_block_end_sends_no_byte(self) -> None:
        # The last glyph still shows, but early and under the results
        # screen: no FRN trial, and a BDF-only pipeline could not tell
        # it from a good one, so it must not reach the wire.
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td, feedback_delay_ms=800,
                                        feedback_markers=True)
                eng.begin_classic_block()
                from finger_rehab.game.scoring import TrialResult
                eng.log_trial(self._trial(lane=1),
                              TrialResult(label="Great", points=6,
                                          rt_ms=200.0),
                              now=100.2)
                self._settle(eng)
                root = Path(eng.session_paths.root)
                # The block closes well inside the 800 ms delay.
                eng.finish_block()
                codes = [int(d["code"]) for d in _eeg_rows(root)]
                self.assertIn(221, codes)
                self.assertFalse([c for c in codes if 140 <= c <= 149],
                                 codes)
        finally:
            pygame.quit()

    def test_continuous_rows_park_no_feedback_byte(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td, feedback_delay_ms=800,
                                        feedback_markers=True)
                eng.begin_classic_block()
                from finger_rehab.data.logger import ContinuousTrialLog
                from finger_rehab.game.scoring import TrialResult
                eng.log_trial(self._trial(lane=1),
                              TrialResult(label="Great", points=6,
                                          rt_ms=None),
                              now=100.2,
                              continuous=ContinuousTrialLog(
                                  waveform="corridor"))
                self._settle(eng)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                codes = [int(d["code"]) for d in _eeg_rows(root)]
                self.assertFalse([c for c in codes if 140 <= c <= 149],
                                 codes)
        finally:
            pygame.quit()


# ---------------------------------------------------------------------------
# A scripted lab session on the fake wire, every mode once
# ---------------------------------------------------------------------------

class _Clock:
    def __init__(self, t0: float = 10_000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t


class _CapturePort:
    """pyserial stand-in: every write kept, stamped on the real clock."""

    def __init__(self) -> None:
        self.is_open = True
        self.writes: list[tuple[float, bytes]] = []

    def write(self, payload) -> int:
        data = bytes(payload)
        self.writes.append((REAL_PERF(), data))
        return len(data)

    def close(self) -> None:
        self.is_open = False


def _capture_backend():
    from finger_rehab.hardware.eeg_trigger import SerialBackend
    backend = SerialBackend("fake-lab-box")
    port = _CapturePort()
    backend._serial = port
    return backend, port


def _press(lane: int, t: float, hand: str = "right"):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0, hand=hand)


def _set(cfg, dotted: str, val) -> None:
    node = cfg.data
    parts = dotted.split(".")
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = val


def _lab_engine(td: str, participant: str, source=None,
                overrides: dict | None = None, real_screens: bool = False):
    """The real engine under config/eeg_lab.yaml over default.yaml,
    with the fake box in place of COM10. Everything else the overlay
    sets stays: the fixed foreperiod, the neutral feedback with its
    800 ms delay, no after-press sounds, no Force Pilot music."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load(LAB_YAML)
    _set(cfg, "ui.resolution", [1280, 800] if real_screens else [640, 480])
    _set(cfg, "audio.enabled", False)
    _set(cfg, "session.data_dir", td)
    _set(cfg, "session.participant", participant)
    _set(cfg, "report.enabled", False)
    _set(cfg, "quick_cal.enabled", False)
    _set(cfg, "serial.watch_ports", False)
    _set(cfg, "eeg.port", None)
    _set(cfg, "eeg.require_port", False)
    # Short pulse and gap so the per-frame drain is quick; the shape
    # of the sequence does not depend on the widths.
    _set(cfg, "eeg.pulse_ms", 2)
    _set(cfg, "eeg.gap_ms", 2)
    _set(cfg, "eeg.feedback_markers", True)
    for k, v in (overrides or {}).items():
        _set(cfg, k, v)
    eng = GameEngine(cfg, source or KeyboardOnlySource())
    if real_screens:
        eng._screens = eng._build_screens()
    else:
        eng._screens = {k: MagicMock(lanes=[]) for k in
                        ("gameplay", "syllables", "force_pilot",
                         "buzz_hunt", "rhythm", "results")}
    eng.show_results = lambda: None
    backend, port = _capture_backend()
    eng.markers.backend = backend
    # The writer's pulse and gap run on the real clock whatever the
    # game clock is doing: with the virtual clock in place its default
    # clock could be bound to the frozen one and drain() would never
    # see the pulse end.
    eng.markers._clock = REAL_PERF
    return eng, port


def _frame(eng, dt: float) -> None:
    """One frame in run()'s order minus the drawing."""
    if eng.mode is not None:
        eng.mode.update(dt)
    eng._drain_feedback()
    eng._drain_motor_queue()
    eng._flush_eeg_stim()
    # Real seconds separate markers in a session; this loop has
    # microseconds, so pump the writer empty each frame or the wire
    # order would be a harness artefact.
    eng.markers.drain(0.5)


def _collect(eng, port, root: Path, wire_from: int) -> dict:
    """Everything one block left behind, once its loggers closed."""
    codes = [b[0] for _, b in port.writes[wire_from:]]
    trials = _trial_rows(root)
    meta = json.loads((root / "metadata.json").read_text())
    return {
        "wire": codes,
        "nonzero": [c for c in codes if c != 0],
        "multi_byte": sum(1 for _, b in port.writes[wire_from:]
                          if len(b) != 1),
        "eeg_rows": _eeg_rows(root),
        "trials": trials,
        "events": _tsv_rows(root / "events.tsv"),
        "sidecar": json.loads((root / "events.json").read_text()),
        "codes_csv": (root / "markers_codes.csv").is_file(),
        "meta_eeg": meta.get("eeg", {}),
    }


def _drive_lane_block(eng, port, name: str, begin: str, script: list[str],
                      clock: _Clock, hand: str = "right",
                      react_s: float = 0.16) -> dict:
    """classic / adaptive / reaction / pattern / mirror: one
    PendingTrial with lane, trial_id and stim_t_perf; a press answers."""
    if hand == "both":
        eng.hand_mode = "both"
        eng._build_detectors()
    wire_from = len(port.writes)
    getattr(eng, begin)()
    root = Path(eng.session_paths.root)
    mode = eng.mode
    seen = None
    idx = -1
    acted = True
    rest_token = None
    start = clock.t
    while eng.trial_logger is not None and clock.t - start < 3000.0:
        clock.t += DT
        active = getattr(mode, "active", None)
        if active is not None and active.trial_id != seen:
            seen = active.trial_id
            idx += 1
            acted = False
        if (not acted and active is not None
                and clock.t >= active.stim_t_perf + react_s):
            acted = True
            action = script[idx] if idx < len(script) else "correct"
            if name == "mirror":
                finger = active.finger
                if action in ("correct", "right_only"):
                    mode.queue_press(_press(finger, clock.t, "right"))
                if action == "correct":
                    mode.queue_press(_press(finger + 4, clock.t + 0.02,
                                            "left"))
            else:
                lane = active.lane
                if action == "correct":
                    mode.queue_press(_press(lane, clock.t))
                elif action == "wrong":
                    mode.queue_press(_press((lane + 1) % 4, clock.t))
        rest_until = getattr(mode, "_rest_min_until", None)
        phase = getattr(mode, "phase", None) or getattr(mode, "_phase", None)
        if (phase == "rest" and rest_until is not None
                and clock.t >= rest_until + 0.05
                and rest_token != rest_until):
            rest_token = rest_until
            mode.queue_press(_press(0, clock.t))
        _frame(eng, DT)
    out = _collect(eng, port, root, wire_from)
    out["ended"] = eng.trial_logger is None
    if hand == "both":
        eng.hand_mode = "right"
        eng._build_detectors()
    return out


def _drive_chords(eng, port, clock: _Clock) -> dict:
    wire_from = len(port.writes)
    eng.begin_chords_block()
    root = Path(eng.session_paths.root)
    mode = eng.mode
    mode._hand_quiet = lambda: True
    script = ["correct", "timeout", "correct", "correct"]
    seen = None
    idx = -1
    pending: list[tuple[float, int]] = []
    start = clock.t
    while eng.trial_logger is not None and clock.t - start < 3000.0:
        clock.t += DT
        active = getattr(mode, "active", None)
        if active is not None and active.trial_id != seen:
            seen = active.trial_id
            idx += 1
            action = script[idx] if idx < len(script) else "correct"
            if action == "correct":
                t = active.stim_t_perf + 0.3
                for lane in active.targets:
                    pending.append((t, lane))
                    t += 0.03
        for t, lane in list(pending):
            if clock.t >= t:
                mode.queue_press(_press(lane, t))
                pending.remove((t, lane))
        _frame(eng, DT)
    out = _collect(eng, port, root, wire_from)
    out["ended"] = eng.trial_logger is None
    return out


def _drive_syllables(eng, port, clock: _Clock) -> dict:
    wire_from = len(port.writes)
    eng.begin_syllables_block()
    root = Path(eng.session_paths.root)
    mode = eng.mode
    answered: set = set()
    n_sets = 0
    start = clock.t
    while eng.trial_logger is not None and clock.t - start < 3000.0:
        clock.t += DT
        _frame(eng, DT)
        if (mode.phase == "choose" and mode.option_set is not None
                and mode._set_close_t is None):
            key = (mode.word.word, mode.pos, mode.ret, mode.trial_counter)
            if clock.t >= mode._spawn_t + 0.4 and key not in answered:
                answered.add(key)
                n_sets += 1
                # Second set answered wrong so the returned-word path
                # (51) is exercised.
                if n_sets == 2:
                    lane = [o.lane for o in mode.option_set.options
                            if o.lane != mode.option_set.target_lane][0]
                else:
                    lane = mode.option_set.target_lane
                mode.queue_press(_press(lane, clock.t, mode.word_hand))
    out = _collect(eng, port, root, wire_from)
    out["ended"] = eng.trial_logger is None
    return out


def _drive_echo(clock: _Clock) -> dict:
    with tempfile.TemporaryDirectory() as td:
        eng, port = _lab_engine(td, "LabEcho", real_screens=True,
                                overrides={"game.test_mode_enabled": True,
                                           "game.test_mode_trials": 6})
        eng.eeg_session_start()
        # 240 out before the block's slice of the wire starts; in a
        # session seconds separate login from the first block.
        eng.markers.drain(0.5)
        wire_from = len(port.writes)
        eng.begin_echo_block()
        root = Path(eng.session_paths.root)
        mode = eng.mode
        answered = {"n": 0}
        pending: list[tuple[float, int]] = []
        start = clock.t
        while eng.trial_logger is not None and clock.t - start < 3000.0:
            clock.t += DT
            if (mode.phase == "respond" and mode.active is not None
                    and mode.trial_counter != answered["n"]):
                answered["n"] = mode.trial_counter
                t = clock.t + 0.3
                for lane in mode.sequence:
                    pending.append((t, lane))
                    t += 0.25
            for t, lane in list(pending):
                if clock.t >= t:
                    mode.queue_press(_press(lane, t))
                    pending.remove((t, lane))
            _frame(eng, DT)
        out = _collect(eng, port, root, wire_from)
        out["ended"] = eng.trial_logger is None
        eng._eeg_shutdown()
        return out


def _drive_force_pilot(clock: _Clock) -> dict:
    from finger_rehab.game.force_stream import ForceReading
    from finger_rehab.game.modes.force_pilot import target_pct
    from finger_rehab.hardware.calibration_profile import CalibrationProfile

    class _View:
        def __init__(self):
            self.counts = 400.0
            self.pct = 0.0

        def read(self, lane):
            return ForceReading(counts=self.counts, percent=self.pct)

        def sample_age_s(self, lane, now):
            return 0.0

        def rebaseline(self, lanes=None):
            return None

    class _Src:
        provides_samples = True
        is_connected = True
        name = "stub"

        def send_command(self, c):
            return True

        def get_sample(self, timeout=0.0):
            return None

        def start(self):
            pass

        def stop(self):
            pass

    with tempfile.TemporaryDirectory() as td:
        eng, port = _lab_engine(td, "LabFP", source=_Src(), overrides={
            "game.test_mode_enabled": True, "game.test_mode_trials": 4,
            "force_pilot.demo_levels": [1, 4],
            "force_pilot.mid_rest_s": 1.0})
        profiles = {}
        for hand in ("right", "left"):
            prof = CalibrationProfile(hand=hand, participant="LabFP",
                                      resting=[100.0] * 4,
                                      press=[160.0] * 4)
            prof.set_max_press([400.0] * 4)
            profiles[hand] = prof
        eng.calibration_profiles = profiles
        eng.eeg_session_start()
        # 240 out before the block's slice of the wire starts; in a
        # session seconds separate login from the first block.
        eng.markers.drain(0.5)
        wire_from = len(port.writes)
        eng.begin_force_pilot_block()
        root = Path(eng.session_paths.root)
        m = eng.mode
        m.view = _View()
        start = clock.t
        while eng.trial_logger is not None and clock.t - start < 4000.0:
            if m.phase in ("done", "no_input"):
                break
            clock.t += DT
            if m.phase == "run" and m.run_t0 is not None:
                t_run = clock.t - m.run_t0
                m.view.pct = target_pct(m.sections, t_run)
                if 2.0 <= t_run < 2.5:
                    m.view.pct = m.view.pct + 45.0
            _frame(eng, DT)
        out = _collect(eng, port, root, wire_from)
        out["ended"] = eng.trial_logger is None
        eng._eeg_shutdown()
        return out


def _drive_buzz_hunt(clock: _Clock) -> dict:
    from tests.test_echo_mode import RESTING, TAP, _WireRig
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    rig = _WireRig(clock)
    with tempfile.TemporaryDirectory() as td:
        eng, port = _lab_engine(td, "LabBuzz", source=rig, real_screens=True,
                                overrides={
            "game.test_mode_enabled": False,
            "buzz_hunt.loc_trials_per_hand": 4, "buzz_hunt.catch_rate": 0.0,
            "buzz_hunt.distractor_trials_per_hand": 0,
            "buzz_hunt.span_trials": 1, "buzz_hunt.gap_trials_per_hand": 1,
            "buzz_hunt.wait_lo_s": 0.3, "buzz_hunt.wait_hi_s": 0.4,
            "buzz_hunt.announce_s": 0.5, "buzz_hunt.rest_s": 0.5,
            "buzz_hunt.stage_intro_s": 0.5, "buzz_hunt.seed": 5})
        eng.begin_session("LabBuzz", "30", dominant_hand="right", visit="1")
        prof = CalibrationProfile(hand="right", participant="LabBuzz",
                                  resting=[RESTING] * 4,
                                  press=[RESTING + 60] * 4)
        prof.set_max_press([RESTING + 300] * 4)
        prof.session_token = str(getattr(eng, "_session_token", ""))
        eng.apply_calibration(prof)
        eng._uncal_ack = {"left", "right"}
        next_sample = clock.t
        press_until: dict[int, float] = {}

        def pump_frame():
            nonlocal next_sample
            clock.t += 1.0 / 60.0
            while next_sample <= clock.t:
                t = next_sample
                vals = [TAP if press_until.get(lane, -1.0) > t else RESTING
                        for lane in range(4)]
                rig.push(t, vals)
                next_sample += 1.0 / 200.0
            eng._pump_source()
            if eng.screen_obj is not None:
                eng.screen_obj.update(1.0 / 60.0)
            _frame(eng, 1.0 / 60.0)

        for _ in range(3000):
            if (eng.detectors.get("right") is not None
                    and eng.detectors["right"].baseline[0] is not None):
                break
            pump_frame()
        eng.eeg_session_start()
        # 240 out before the block's slice of the wire starts; in a
        # session seconds separate login from the first block.
        eng.markers.drain(0.5)
        wire_from = len(port.writes)
        eng.begin_buzz_hunt_block()
        root = Path(eng.session_paths.root)
        mode = eng.mode
        answered: set[int] = set()
        seq_pending: list[tuple[float, int]] = []
        start = clock.t
        while eng.trial_logger is not None and clock.t - start < 4000.0:
            pump_frame()
            if (mode.phase == "trial" and mode.sub == "respond"
                    and mode.trial_counter not in answered):
                answered.add(mode.trial_counter)
                stage = getattr(mode, "stage", None)
                seq = getattr(mode, "_seq", None) or getattr(
                    mode, "sequence", None)
                if stage == "span" and seq:
                    t = clock.t + 0.1
                    for lane in seq:
                        seq_pending.append((t, int(lane)))
                        t += 0.35
                else:
                    press_until[int(mode.lane)] = clock.t + 0.10
            for t, lane in list(seq_pending):
                if clock.t >= t:
                    press_until[lane] = clock.t + 0.10
                    seq_pending.remove((t, lane))
        out = _collect(eng, port, root, wire_from)
        out["ended"] = eng.trial_logger is None
        eng._eeg_shutdown()
        return out


def _drive_rhythm() -> dict:
    """Real clock: rhythm's song time is perf_counter minus the start."""
    from tests.test_rhythm_tactile import _beatmap, _fake_audio, _fake_source
    with tempfile.TemporaryDirectory() as td:
        source, board = _fake_source()
        eng, port = _lab_engine(td, "LabRhythm", source=source, overrides={
            "cue.buzz_before": True, "cue.sound_before": True,
            "cue.show_target": True,
            "motor.cue_ms": 150, "game.start_countdown_s": 0,
            "rhythm.pre_song_lead_s": 0, "rhythm.audio_offset_ms": 40,
            "rhythm.metronome_offset_ms": 12, "rhythm.tactile_mode": "lead",
            "rhythm.buzz_lead_ms": 150, "rhythm.buzz_lead_adapt": False})
        eng.audio = _fake_audio()
        eng.eeg_session_start()
        # 240 out before the block's slice of the wire starts; in a
        # session seconds separate login from the first block.
        eng.markers.drain(0.5)
        wire_from = len(port.writes)
        bm = _beatmap(4)
        eng.begin_rhythm_block(bm)
        root = Path(eng.session_paths.root)
        mode = eng.mode
        zeros = [mode._t_start + n.t + 0.012 for n in bm.notes]
        plan = {0: 0.0, 2: 0.2, 3: 0.0}   # note 1 missed on purpose
        pressed: set[int] = set()
        end = REAL_PERF() + 6.0
        last = REAL_PERF()
        while eng.trial_logger is not None and REAL_PERF() < end:
            now = REAL_PERF()
            dt = now - last
            last = now
            for i, off in plan.items():
                if i not in pressed and now >= zeros[i] + off:
                    pressed.add(i)
                    mode.queue_press(_press(bm.notes[i].lane, now))
            if eng.mode is not None:
                eng.mode.update(dt)
            eng._drain_feedback()
            eng._drain_motor_queue()
            eng._flush_eeg_stim()
            eng.markers.tick()
            time.sleep(max(0.0, 1.0 / 60.0 - (REAL_PERF() - now)))
        out = _collect(eng, port, root, wire_from)
        out["ended"] = eng.trial_logger is None
        eng._eeg_shutdown()
        return out


def _run_lab_session() -> dict:
    """One login, seven keyboard blocks, one logout on one engine; the
    modes that need a rig or the real clock on engines of their own,
    each bracketed by its own 240/241."""
    import pygame
    pygame.init()
    results: dict = {}
    clock = _Clock()
    real = time.perf_counter
    time.perf_counter = clock
    try:
        with tempfile.TemporaryDirectory() as td:
            eng, port = _lab_engine(td, "LabProof")
            eng.eeg_session_start()
            eng.markers.drain(0.5)
            cfg = eng.cfg
            _set(cfg, "reaction.seed", 907)
            _set(cfg, "reaction.catch_rate", 0.0)
            _set(cfg, "reaction.block_trials", 4)
            _set(cfg, "reaction.attempt_cap", 8)
            results["reaction"] = _drive_lane_block(
                eng, port, "reaction", "begin_reaction_block",
                ["correct", "wrong", "timeout", "correct"], clock)
            _set(cfg, "game.test_mode_enabled", True)
            _set(cfg, "game.test_mode_trials", 4)
            results["classic"] = _drive_lane_block(
                eng, port, "classic", "begin_classic_block",
                ["correct", "wrong", "timeout", "correct"], clock)
            _set(cfg, "adaptive.seed", 3)
            results["adaptive"] = _drive_lane_block(
                eng, port, "adaptive", "begin_adaptive_block",
                ["correct", "wrong", "timeout", "correct"], clock)
            results["mirror"] = _drive_lane_block(
                eng, port, "mirror", "begin_mirror_block",
                ["correct", "right_only", "correct", "correct"], clock,
                hand="both")
            _set(cfg, "game.test_mode_trials", 6)
            _set(cfg, "pattern.seed", 907)
            results["pattern"] = _drive_lane_block(
                eng, port, "pattern", "begin_pattern_block",
                ["correct", "timeout", "correct", "correct", "correct",
                 "correct"], clock)
            _set(cfg, "game.test_mode_trials", 4)
            _set(cfg, "chords.seed", 11)
            results["chords"] = _drive_chords(eng, port, clock)
            _set(cfg, "syllables.speech", {"backend": "off"})
            _set(cfg, "syllables.words_per_block", 3)
            _set(cfg, "syllables.warmup_taps", 0)
            _set(cfg, "syllables.break_s", 0)
            _set(cfg, "syllables.seed", 21)
            results["syllables"] = _drive_syllables(eng, port, clock)
            eng._eeg_shutdown()
            results["_session_wire"] = [b[0] for _, b in port.writes]
        results["echo"] = _drive_echo(clock)
        results["force_pilot"] = _drive_force_pilot(clock)
        results["buzz_hunt"] = _drive_buzz_hunt(clock)
    finally:
        time.perf_counter = real
    try:
        results["rhythm"] = _drive_rhythm()
    finally:
        pygame.quit()
    return results


_LAB: dict = {}


def _lab() -> dict:
    if not _LAB:
        _LAB.update(_run_lab_session())
    return _LAB


MODES = ("reaction", "classic", "adaptive", "mirror", "pattern", "chords",
         "syllables", "echo", "force_pilot", "buzz_hunt", "rhythm")
# Modes whose stimulus-band byte count equals the trials.csv row count.
ONE_STIM_PER_ROW = ("reaction", "classic", "adaptive", "mirror", "pattern",
                    "chords")


class LabSessionTests(unittest.TestCase):

    def _each(self, check) -> None:
        """Run check(name, scenario) for every mode as a subtest."""
        lab = _lab()
        for name in MODES:
            with self.subTest(mode=name):
                check(name, lab[name])

    def test_every_block_ran_to_the_end(self) -> None:
        def check(name, scn):
            self.assertTrue(scn["ended"], name)
            self.assertTrue(scn["trials"], name)
        self._each(check)

    def test_wire_bytes_equal_logged_codes(self) -> None:
        # The proof the lab needs: what left the port is exactly what
        # raw.csv says left it, byte for byte, in the same order.
        def check(name, scn):
            logged = [int(d["code"]) for d in scn["eeg_rows"]]
            self.assertEqual(scn["nonzero"], logged, name)
            for d in scn["eeg_rows"]:
                self.assertEqual(d["failed"], "0", name)
                self.assertEqual(d["dropped"], "0", name)
                self.assertTrue(d["t_wire"], name)
                self.assertTrue(d["name"], name)
        self._each(check)

    def test_single_bytes_each_reset_to_zero(self) -> None:
        def check(name, scn):
            self.assertEqual(scn["multi_byte"], 0, name)
            wire = scn["wire"]
            for i, c in enumerate(wire):
                if c != 0:
                    self.assertLess(i + 1, len(wire), name)
                    self.assertEqual(wire[i + 1], 0, (name, c))
        self._each(check)

    def test_block_edges_present_once(self) -> None:
        from finger_rehab.hardware.eeg_trigger import MODE_IDS

        def check(name, scn):
            codes = scn["nonzero"]
            self.assertEqual(codes.count(200 + MODE_IDS[name]), 1, name)
            self.assertEqual(codes.count(220 + MODE_IDS[name]), 1, name)
            self.assertEqual(codes.count(20), 1, name)
            self.assertEqual(codes[-1], 220 + MODE_IDS[name], name)
        self._each(check)

    def test_session_is_bracketed_once(self) -> None:
        wire = [c for c in _lab()["_session_wire"] if c != 0]
        self.assertEqual(wire[0], 240)
        self.assertEqual(wire[-1], 241)
        self.assertEqual(wire.count(240), 1)
        self.assertEqual(wire.count(241), 1)

    def test_events_export_matches_the_log(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES, CODES_VERSION

        def check(name, scn):
            events = scn["events"]
            self.assertEqual(len(events), len(scn["eeg_rows"]), name)
            self.assertEqual(sorted(int(r["value"]) for r in events),
                             sorted(scn["nonzero"]), name)
            onsets = [float(r["onset"]) for r in events]
            self.assertEqual(onsets, sorted(onsets), name)
            # The block-start byte's t_event is the block clock zero,
            # which can sit a fraction of a frame before the first
            # force sample; anything earlier is a wrong reference.
            self.assertGreaterEqual(onsets[0], -1.0 / 60.0, name)
            self.assertEqual(scn["sidecar"]["CodesVersion"], CODES_VERSION)
            self.assertTrue(scn["codes_csv"], name)
            self.assertEqual(scn["meta_eeg"]["codes"], CODES, name)
            self.assertEqual(scn["meta_eeg"]["pulse_ms"], 2.0, name)
        self._each(check)

    def test_stimulus_bytes_reconcile_with_the_rows(self) -> None:
        lab = _lab()
        for name in ONE_STIM_PER_ROW:
            scn = lab[name]
            with self.subTest(mode=name):
                stim = [c for c in scn["nonzero"] if 30 <= c <= 49]
                self.assertEqual(len(stim), len(scn["trials"]))
        # Syllables: one 50/51 per row; the model rolls are 30-band
        # bytes with no row.
        syl = lab["syllables"]
        choice = [c for c in syl["nonzero"] if 50 <= c <= 59]
        self.assertEqual(len(choice), len(syl["trials"]))
        self.assertIn(51, choice)
        self.assertGreater(len([c for c in syl["nonzero"] if 30 <= c <= 39]),
                           0)
        # Echo: one 33 per played item, at least one per row.
        echo = lab["echo"]
        played = [c for c in echo["nonzero"] if 30 <= c <= 39]
        self.assertGreaterEqual(len(played), len(echo["trials"]))
        # Buzz Hunt: 38 per pulse and no response byte on scored trials.
        bh = lab["buzz_hunt"]
        self.assertGreaterEqual(bh["nonzero"].count(38), len(bh["trials"]))
        self.assertFalse([c for c in bh["nonzero"] if 100 <= c <= 131])
        # Rhythm: a 22 ahead of every 31, one per note.
        rh = lab["rhythm"]
        self.assertEqual(rh["nonzero"].count(22), rh["nonzero"].count(31))
        self.assertEqual(rh["nonzero"].count(31), len(rh["trials"]))

    def test_response_bytes_one_per_scored_stimulus(self) -> None:
        for name in ("reaction", "classic", "adaptive", "pattern", "chords"):
            scn = _lab()[name]
            with self.subTest(mode=name):
                codes = scn["nonzero"]
                stim_i = [i for i, c in enumerate(codes) if 30 <= c <= 49]
                for j, i in enumerate(stim_i):
                    end = stim_i[j + 1] if j + 1 < len(stim_i) else len(codes)
                    resp = [c for c in codes[i + 1:end] if 100 <= c <= 131]
                    self.assertEqual(len(resp), 1, (name, codes[i:end]))

    def test_force_pilot_runs_carry_start_and_edge_bytes(self) -> None:
        from finger_rehab.data.logger import parse_segments
        fp = _lab()["force_pilot"]
        codes = fp["nonzero"]
        self.assertEqual(codes.count(23), len(fp["trials"]))
        edges = sum(len(parse_segments(r["segment_times"]))
                    for r in fp["trials"])
        self.assertEqual(codes.count(24), edges)
        self.assertGreater(edges, 0)
        # Still no stimulus, response or trial-close feedback byte for a
        # continuous run.
        self.assertFalse([c for c in codes if 30 <= c <= 59])
        self.assertFalse([c for c in codes if 100 <= c <= 131])
        self.assertEqual(codes.count(140), 0)
        # 23 rides the raw.csv row with the run's lane.
        starts = [d for d in fp["eeg_rows"] if d["code"] == "23"]
        self.assertTrue(all(d["lane"] != "" for d in starts))

    def test_every_feedback_byte_is_a_full_delay_one(self) -> None:
        # Under the overlay's 800 ms delay a glyph the block end cuts
        # short still shows but sends no byte: it lands early, under the
        # results screen, and a lab reading the BDF alone could not tell
        # it from a good one. Every byte that is sent sits the full
        # delay after the response it follows, one per trial at most.
        delay = 0.8
        for name in ("reaction", "classic", "adaptive", "pattern"):
            scn = _lab()[name]
            with self.subTest(mode=name):
                rows = scn["eeg_rows"]
                fb = [d for d in rows if 140 <= int(d["code"]) <= 142]
                self.assertTrue(fb)
                self.assertLessEqual(len(fb), len(scn["trials"]))
                if name != "reaction":
                    # In the fast modes the next trial's press can land
                    # before this trial's glyph, so a byte cannot be
                    # paired with the press before it. That overlap is
                    # why the lab sends FRN bytes in reaction, chords
                    # and force_pilot only.
                    continue
                last_response = None
                for d in rows:
                    code = int(d["code"])
                    if 100 <= code <= 131:
                        last_response = float(d["t_event"])
                    elif 140 <= code <= 142 and last_response is not None:
                        self.assertGreaterEqual(
                            float(d["t_event"]) - last_response,
                            delay - 0.02, (name, d))

if __name__ == "__main__":
    unittest.main()
