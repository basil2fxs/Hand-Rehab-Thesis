"""The EEG contract: the code map, the wire protocol, the engine
wiring and the lab-mode parity, pinned in one place.

This test is what keeps the lab file and the game the same thing.
The lab entry point is main.py plus a config overlay; if anyone forks
the engine, adds a second entry point, breaks the band layout, or
regresses the single-byte encoding, this file fails before a session
is ever recorded under a wrong map.
"""
from __future__ import annotations

import csv
import os
import re
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


def _parse_detail(detail: str) -> dict:
    out = {}
    for part in detail.split(";"):
        key, _, val = part.partition("=")
        out[key] = val
    return out


class MapIntegrityTests(unittest.TestCase):
    """Section 1 of the spec: bands, uniqueness, 30 = stimulus onset,
    0 reserved for reset."""

    def test_codes_are_unique_bytes_and_zero_is_reserved(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES, RESET
        values = list(CODES.values())
        self.assertEqual(len(values), len(set(values)),
                         "duplicate marker codes")
        for name, code in CODES.items():
            self.assertIsInstance(code, int, name)
            self.assertTrue(1 <= code <= 255,
                            f"{name}={code} outside 1-255")
        self.assertEqual(RESET, 0)
        self.assertNotIn(0, values, "0 may only ever be the reset line")

    def test_every_code_sits_in_its_documented_band(self) -> None:
        from finger_rehab.hardware.eeg_trigger import BANDS, CODES
        for name, code in CODES.items():
            for prefix, (lo, hi) in BANDS.items():
                if name.startswith(prefix):
                    self.assertTrue(
                        lo <= code <= hi,
                        f"{name}={code} outside band {lo}-{hi}")
                    break
            else:
                self.fail(f"{name} matches no documented band")

    def test_30_is_a_stimulus_onset_code(self) -> None:
        # The lab's standing habit is "epoch on 30". The old prototype
        # used 30 for miss/timeout; that conflict is the reason this
        # assertion exists.
        from finger_rehab.hardware.eeg_trigger import CODES
        self.assertEqual(CODES["stim_visual"], 30)
        self.assertNotEqual(CODES["resp_timeout"], 30)

    def test_stim_code_covers_all_cue_conditions(self) -> None:
        from finger_rehab.hardware.eeg_trigger import stim_code
        seen = set()
        for sound in (False, True):
            for buzz in (False, True):
                for show in (False, True):
                    seen.add(stim_code(sound, buzz, show))
        self.assertEqual(seen, set(range(30, 38)))
        # The anchors named in the spec.
        self.assertEqual(stim_code(False, False, True), 30)
        self.assertEqual(stim_code(True, True, True), 33)
        self.assertEqual(stim_code(False, True, False), 36)

    def test_response_codes_carry_lane_and_reject_bad_lanes(self) -> None:
        from finger_rehab.hardware.eeg_trigger import response_code
        self.assertEqual(response_code("correct", 0), 100)
        self.assertEqual(response_code("correct", 7), 107)
        self.assertEqual(response_code("wrong", 3), 113)
        self.assertEqual(response_code("anticipation", 7), 127)
        for lane in (-1, 8, 100):
            self.assertIsNone(response_code("correct", lane))
        self.assertIsNone(response_code("nonsense", 0))

    def test_block_codes_cover_every_mode_without_hitting_219(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (CODES, MODE_IDS,
                                                block_code)
        emitted = set()
        for mode in MODE_IDS:
            start = block_code(mode, "start")
            end = block_code(mode, "end")
            self.assertTrue(200 <= start <= 211, mode)
            self.assertTrue(220 <= end <= 231, mode)
            emitted.update((start, end))
        self.assertNotIn(CODES["block_abandoned"], emitted)
        self.assertEqual(block_code("reaction", "abandoned"), 219)
        self.assertIsNone(block_code("not_a_mode", "start"))


class EncodingTests(unittest.TestCase):

    def test_write_code_emits_exactly_one_raw_byte(self) -> None:
        # Guards the chr()/UTF-8 regression: any code over 127 would
        # become two bytes and corrupt the trigger channel. 220 = 0xDC
        # is a block-end code, safely over the boundary.
        from finger_rehab.hardware.eeg_trigger import SerialBackend
        backend = SerialBackend("dummy")

        class _FakePort:
            is_open = True

            def __init__(self) -> None:
                self.data = bytearray()

            def write(self, payload: bytes) -> int:
                self.data += bytes(payload)
                return len(payload)

        port = _FakePort()
        backend._serial = port
        self.assertTrue(backend.write_code(220))
        self.assertEqual(bytes(port.data), b"\xdc")
        self.assertEqual(len(port.data), 1)


class ProtocolTests(unittest.TestCase):
    """Pulse-then-reset, the gap rule, and the degrade path, on a fake
    clock so the arithmetic is exact."""

    class _Clock:
        def __init__(self) -> None:
            self.t = 10.0

        def __call__(self) -> float:
            return self.t

    class _Backend:
        name = "fake"

        def __init__(self) -> None:
            self.written: list[int] = []
            self.fail = False
            self.reopen_calls = 0

        def open(self) -> bool:
            return True

        def write_code(self, code: int) -> bool:
            if self.fail:
                return False
            self.written.append(code)
            return True

        def reopen(self) -> bool:
            self.reopen_calls += 1
            return False

        def close(self) -> None:
            pass

    def _writer(self, records):
        from finger_rehab.hardware.eeg_trigger import MarkerWriter
        clock = self._Clock()
        backend = self._Backend()
        writer = MarkerWriter(backend=backend, enabled=True,
                              pulse_ms=10.0, gap_ms=10.0, clock=clock,
                              on_emit=records.append)
        return writer, backend, clock

    def test_pulse_then_reset_then_gap(self) -> None:
        records: list = []
        writer, backend, clock = self._writer(records)
        writer.send(30)
        self.assertEqual(backend.written, [30])
        clock.t += 0.011
        writer.tick()
        self.assertEqual(backend.written, [30, 0])
        # A send inside the gap queues rather than firing.
        writer.send(101)
        self.assertEqual(backend.written, [30, 0])
        clock.t += 0.011
        writer.tick()
        self.assertEqual(backend.written, [30, 0, 101])
        self.assertFalse(records[0].delayed)
        self.assertTrue(records[1].delayed)

    def test_write_failure_reopens_once_then_degrades(self) -> None:
        records: list = []
        writer, backend, clock = self._writer(records)
        backend.fail = True
        for _ in range(3):
            writer.send(30)
            clock.t += 0.05
        self.assertEqual(backend.reopen_calls, 1)
        self.assertTrue(writer.degraded)
        self.assertTrue(all(r.failed for r in records))
        # Still logging after degrade, still not crashing.
        writer.send(101)
        self.assertEqual(records[-1].code, 101)
        self.assertTrue(records[-1].failed)


class _EngineHarness(unittest.TestCase):
    """A real GameEngine on the keyboard source with the dummy EEG
    backend: the same path a lab session takes minus the amplifier."""

    def _make_engine(self, td: str, eeg_enabled: bool = True):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = td
        cfg.data["report"] = {"enabled": False}
        cfg.data["reaction"] = {"seed": 1234, "catch_rate": 0.0}
        # Screen-only cue so the expected stimulus code is exactly 30.
        cfg.data["cue"] = {"buzz_before": False, "sound_before": False,
                           "sound_after": False, "buzz_after": False,
                           "show_target": True}
        # Short pulse and gap so drain() pumps the queue quickly.
        cfg.data["eeg"] = {"enabled": eeg_enabled, "port": None,
                           "require_port": False,
                           "pulse_ms": 2, "gap_ms": 2}
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
    def _wire_codes(eng) -> list[int]:
        return [c for _, c in eng.markers.backend.written if c != 0]

    @staticmethod
    def _settle(eng) -> None:
        """Stand-in for the frame loop between game events: pump the
        writer until idle (run() ticks it every frame), then let the
        inter-marker gap age. The real game has seconds between a
        foreperiod arming and its stimulus; without this spacing the
        harness fires everything in the same microsecond and the
        priority queue reorders what real pacing keeps apart."""
        import time as _time
        eng.markers.drain(0.2)
        _time.sleep(0.01)

    @staticmethod
    def _eeg_rows(root: Path) -> list[dict]:
        with (root / "raw.csv").open() as f:
            return [r for r in csv.DictReader(f) if r["event"] == "eeg"]


class EngineWiringTests(_EngineHarness):

    def test_block_emits_required_sequence_and_log_rows(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                from finger_rehab.hardware.eeg_trigger import DummyBackend
                self.assertIsInstance(eng.markers.backend, DummyBackend)
                eng.eeg_session_start()
                self._settle(eng)
                eng.begin_reaction_block()
                mode = eng.mode
                self._settle(eng)
                # Trial 1: clean correct press.
                mode._begin_trial(now=100.0)
                self._settle(eng)
                mode._fire(now=103.0)
                eng._flush_eeg_stim()
                self._settle(eng)
                lane1 = mode.active.lane
                mode._handle_press(self._press(lane1, 103.3), now=103.3)
                self._settle(eng)
                # Trial 2: wrong finger (choice sub-mode: a Miss row
                # with the wrong press recorded).
                mode._begin_trial(now=110.0)
                self._settle(eng)
                mode._fire(now=113.0)
                eng._flush_eeg_stim()
                self._settle(eng)
                lane2 = mode.active.lane
                wrong2 = (lane2 + 1) % 4
                mode._handle_press(self._press(wrong2, 113.4), now=113.4)
                self._settle(eng)
                # Trial 3: timeout, no press at all.
                mode._begin_trial(now=120.0)
                self._settle(eng)
                mode._fire(now=123.0)
                eng._flush_eeg_stim()
                self._settle(eng)
                lane3 = mode.active.lane
                mode._close_scorable(None, now=126.0)
                self._settle(eng)
                root = Path(eng.session_paths.root)
                eng.finish_block()

                codes = self._wire_codes(eng)
                expected = [
                    240,            # session start
                    200 + 0,        # block start, reaction mode id 0
                    20,             # GET READY onset
                    21, 30,         # trial 1: foreperiod armed, stim
                    100 + lane1,    # correct press, lane in the byte
                    21, 30,
                    110 + wrong2,   # wrong finger
                    21, 30,
                    130,            # timeout
                    220 + 0,        # block end
                ]
                self.assertEqual(codes, expected)

                # Every emission wrote a raw.csv eeg row (session start
                # fired before the block, so it logs to the app log
                # instead; everything else must be in the file).
                rows = self._eeg_rows(root)
                row_codes = [int(_parse_detail(r["detail"])["code"])
                             for r in rows]
                self.assertEqual(row_codes, expected[1:])
                for row in rows:
                    detail = _parse_detail(row["detail"])
                    for key in ("code", "t_event", "t_wire", "delayed",
                                "failed", "dropped"):
                        self.assertIn(key, detail, row["detail"])
                    float(detail["t_event"])
                    float(detail["t_wire"])   # emitted, so both present
                    # The row's own t_perf is the event time, on the
                    # same clock as the sample stream.
                    self.assertAlmostEqual(float(row["t_perf"]),
                                           float(detail["t_event"]),
                                           places=6)
                # Stimulus rows carry the lane in the row, not the byte.
                stim_rows = [r for r in rows
                             if _parse_detail(r["detail"])["code"] == "30"]
                self.assertEqual([int(r["lane"]) for r in stim_rows],
                                 [lane1, lane2, lane3])
        finally:
            pygame.quit()

    def test_correct_press_t_event_is_the_press_time(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_reaction_block()
                mode = eng.mode
                eng.markers.drain(0.2)
                mode._begin_trial(now=100.0)
                mode._fire(now=103.0)
                eng._flush_eeg_stim()
                lane = mode.active.lane
                mode._handle_press(self._press(lane, 103.25), now=103.3)
                eng.markers.drain(0.2)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                rows = self._eeg_rows(root)
                resp = [r for r in rows
                        if _parse_detail(r["detail"])["code"]
                        == str(100 + lane)]
                self.assertEqual(len(resp), 1)
                # The marker's t_event is the press's own detector
                # timestamp (103.25), not the frame it was logged on.
                t_event = float(_parse_detail(resp[0]["detail"])["t_event"])
                self.assertAlmostEqual(t_event, 103.25, places=3)
        finally:
            pygame.quit()


class CorrectnessSplitTests(_EngineHarness):
    """Spec item 6: wrong-finger, anticipation and timeout must land
    in the 110 / 120 / 130 bands and never in the correct band."""

    def _run_block(self, drive) -> list[int]:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_reaction_block()
                eng.markers.drain(0.2)
                drive(eng, eng.mode)
                eng.markers.drain(0.2)
                eng.finish_block()
                return self._wire_codes(eng)
        finally:
            pygame.quit()

    def test_wrong_finger_is_110_band_never_100(self) -> None:
        seen = {}

        def drive(eng, mode):
            mode._begin_trial(now=100.0)
            mode._fire(now=103.0)
            eng._flush_eeg_stim()
            seen["wrong"] = (mode.active.lane + 1) % 4
            mode._handle_press(self._press(seen["wrong"], 103.4),
                               now=103.4)

        codes = self._run_block(drive)
        self.assertIn(110 + seen["wrong"], codes)
        self.assertFalse([c for c in codes if 100 <= c <= 107])

    def test_anticipation_is_120_band_never_100(self) -> None:
        seen = {}

        def drive(eng, mode):
            mode._begin_trial(now=100.0)
            mode._fire(now=103.0)
            eng._flush_eeg_stim()
            lane = mode.active.lane
            seen["lane"] = lane
            # 50 ms is under the 100 ms anticipation cut: a press that
            # fast cannot be a response to the stimulus.
            mode._handle_press(self._press(lane, 103.05), now=103.05)

        codes = self._run_block(drive)
        self.assertIn(120 + seen["lane"], codes)
        self.assertFalse([c for c in codes if 100 <= c <= 107])

    def test_timeout_is_130_never_100(self) -> None:
        def drive(eng, mode):
            mode._begin_trial(now=100.0)
            mode._fire(now=103.0)
            eng._flush_eeg_stim()
            mode._close_scorable(None, now=106.0)

        codes = self._run_block(drive)
        self.assertIn(130, codes)
        self.assertFalse([c for c in codes if 100 <= c <= 107])


class DisabledIsInertTests(_EngineHarness):
    """eeg.enabled false: zero markers, zero raw.csv rows, no backend."""

    def test_disabled_block_emits_nothing(self) -> None:
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td, eeg_enabled=False)
                self.assertFalse(eng.markers.active)
                self.assertIsNone(eng.markers.backend)
                eng.eeg_session_start()
                eng.begin_reaction_block()
                mode = eng.mode
                mode._begin_trial(now=100.0)
                mode._fire(now=103.0)
                eng._flush_eeg_stim()
                mode._handle_press(self._press(mode.active.lane, 103.3),
                                   now=103.3)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                self.assertEqual(self._eeg_rows(root), [])
                # Nothing pending either: the stim path never armed.
                self.assertEqual(eng._pending_eeg_stim, [])
        finally:
            pygame.quit()


class FixedForeperiodVariantTests(unittest.TestCase):
    """The CNV variant: constant wait, ready cue, catch virtual onset."""

    def _mode(self, **overrides):
        from finger_rehab.game.modes.reaction import ReactionMode
        from finger_rehab.game.scoring import ScoreConfig
        engine = MagicMock()
        engine.detectors = {}
        engine._screens = {}
        engine.hand_mode = "right"
        kwargs = dict(
            engine=engine, lanes_by_hand={"right": [0, 1, 2, 3]},
            sub_mode="choice", srt_finger=0, scorable_trials=3,
            attempt_cap=10, fp_min_s=1.5, fp_mean_extra_s=2.5,
            fp_max_s=9.0, fp_mode="exponential", catch_rate=0.0,
            catch_wait_s=8.0, anticipation_cut_ms=100.0, lapse_ms=500.0,
            response_window_s=2.0, level=1, max_level=3,
            level_up_lapse_rate=0.10, level_down_lapse_rate=0.30,
            rest_gate_s=0.3, feedback_s=1.2,
            false_start_feedback_s=1.5, inter_trial_gap_s=0.5,
            score_cfg=ScoreConfig(), seed=42,
        )
        kwargs.update(overrides)
        return engine, ReactionMode(**kwargs)

    def test_fixed_foreperiod_replaces_the_draw(self) -> None:
        _, mode = self._mode(fp_fixed_s=2.5)
        for _ in range(50):
            self.assertEqual(mode._draw_foreperiod(), 2.5)

    def test_null_keeps_the_exponential_draw(self) -> None:
        _, mode = self._mode(fp_fixed_s=None)
        draws = {mode._draw_foreperiod() for _ in range(50)}
        self.assertGreater(len(draws), 1)

    def test_foreperiod_onset_emits_21(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES
        engine, mode = self._mode(fp_fixed_s=2.5)
        mode._begin_trial(now=100.0)
        sent = [c.args[0] for c in engine._eeg_send.call_args_list]
        self.assertIn(CODES["prep_foreperiod"], sent)

    def test_catch_trial_emits_virtual_onset_25(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES
        engine, mode = self._mode(fp_fixed_s=2.5, catch_rate=1.0)
        mode._begin_trial(now=100.0)
        self.assertEqual(mode._phase, "catch")
        self.assertAlmostEqual(mode._catch_virtual_due, 102.5)
        # Before the virtual instant: nothing. After: exactly one 25.
        mode._presses.clear()
        mode._catch_virtual_due = 102.5
        import unittest.mock as um
        with um.patch("finger_rehab.game.modes.reaction.time") as fake_time:
            fake_time.perf_counter.return_value = 102.6
            mode.update(0.0)
        sent = [c.args[0] for c in engine._eeg_send.call_args_list]
        self.assertIn(CODES["prep_catch_onset"], sent)


class ParityTests(unittest.TestCase):
    """One engine, one entry point; lab mode is a config overlay."""

    def test_lab_overlay_loads_over_defaults(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load(REPO / "config" / "eeg_lab.yaml")
        self.assertTrue(cfg.get("eeg.enabled"))
        self.assertTrue(cfg.get("eeg.require_port"))
        port = cfg.get("eeg.port")
        self.assertIsInstance(port, str)
        self.assertTrue(port)
        self.assertGreater(float(cfg.get("reaction.fp_eeg_fixed_s")), 0)
        # The overlay must not fork gameplay settings: defaults still
        # supply everything it does not name.
        self.assertIsNotNone(cfg.get("game.timeout_s"))

    def test_launchers_run_main_py_and_nothing_else(self) -> None:
        # Basil removed the root EEG Lab.bat: on Windows the lab runs
        # the frozen exe from the CI lab package, so the source-based
        # launcher only exists for the Mac. The package's bat runs the
        # exe, which is main.py frozen from the same commit.
        text = (REPO / "EEG Lab.command").read_text()
        self.assertIn("main.py --config config/eeg_lab.yaml", text)
        # No other python entry point may be invoked. The basename
        # must be exactly main.py: an endswith check would let a
        # forked lab_main.py through, and the assertIn above is
        # satisfied by "lab_main.py --config ..." as a substring.
        for match in re.findall(r"\S+\.py\b", text):
            base = match.replace("\\", "/").rsplit("/", 1)[-1]
            self.assertEqual(base, "main.py",
                             f"EEG Lab.command invokes {match}")
        bat = (REPO / "docs" / "lab_package" / "EEG Lab.bat").read_text()
        self.assertIn('"Finger Rehab.exe" --config eeg_lab.yaml',
                      bat.replace("\\", "/"))
        self.assertNotIn(".py", bat,
                         "the lab package bat must run the exe, not a script")

    def test_exactly_one_game_engine_class_exists(self) -> None:
        hits = []
        for path in (REPO / "finger_rehab").rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if re.search(r"^class GameEngine\b", path.read_text(),
                         re.MULTILINE):
                hits.append(path.relative_to(REPO))
        self.assertEqual([str(p) for p in hits],
                         ["finger_rehab/game/engine.py"])

    def test_old_prototype_module_is_gone(self) -> None:
        # The conflicting map (30 = miss) must not linger importable
        # next to the new one.
        self.assertFalse((REPO / "finger_rehab" / "hardware" / "eeg.py").exists())


class LabPackageTests(unittest.TestCase):
    """docs/lab_package is the one folder that gets copied to the lab
    desktop. The exe and the yaml/setup copies are build products
    (gitignored, regenerated by the build scripts); anything present
    must match its source of truth, and a bare double-click of the
    frozen exe must find the sibling config on its own."""

    PKG = REPO / "docs" / "lab_package"

    def test_generated_copies_match_their_sources(self) -> None:
        pairs = (
            (self.PKG / "eeg_lab.yaml",
             REPO / "config" / "eeg_lab.yaml"),
            (self.PKG / "eeg_lab_setup.txt",
             REPO / "docs" / "eeg_lab_setup.txt"),
        )
        for copy, source in pairs:
            if not copy.exists():
                # Not built on this machine yet; the build scripts
                # create the copy, this test only forbids a fork.
                continue
            self.assertEqual(copy.read_text(), source.read_text(),
                             f"{copy.name} forked from {source}")

    def test_built_package_is_complete(self) -> None:
        # An exe without eeg_lab.yaml beside it would start the plain
        # game; the build scripts must never leave that state behind.
        if not (self.PKG / "Finger Rehab.exe").exists():
            self.skipTest("no exe in docs/lab_package on this machine")
        for name in ("eeg_lab.yaml", "eeg_lab_setup.txt", "EEG Lab.bat",
                     "README.txt", "run_from_source.py"):
            self.assertTrue((self.PKG / name).exists(),
                            f"lab package missing {name}")

    def test_frozen_exe_picks_up_sibling_lab_config(self) -> None:
        import main as entry
        with tempfile.TemporaryDirectory() as td:
            exe = Path(td) / "Finger Rehab.exe"
            exe.write_bytes(b"")
            had_frozen = getattr(sys, "frozen", None)
            old_exec = sys.executable
            sys.frozen = True  # type: ignore[attr-defined]
            sys.executable = str(exe)
            try:
                # Exe alone: nothing auto-loads.
                self.assertIsNone(entry._sibling_lab_config())
                sibling = Path(td) / "eeg_lab.yaml"
                sibling.write_text("eeg:\n  enabled: true\n")
                # resolve() both sides: macOS tempdirs reach /var
                # through a /private symlink.
                self.assertEqual(entry._sibling_lab_config(),
                                 sibling.resolve())
            finally:
                sys.executable = old_exec
                if had_frozen is None:
                    del sys.frozen  # type: ignore[attr-defined]
                else:
                    sys.frozen = had_frozen  # type: ignore[attr-defined]

    def test_source_runs_never_auto_load_the_lab_config(self) -> None:
        # Dev runs stay on the defaults; only the frozen exe hunts for
        # a sibling config.
        import main as entry
        self.assertFalse(getattr(sys, "frozen", False))
        self.assertIsNone(entry._sibling_lab_config())

    def test_run_from_source_invokes_main_py_only(self) -> None:
        # The Python courtesy ramp must not become a second entry
        # point: same rule as the launchers.
        text = (self.PKG / "run_from_source.py").read_text()
        for match in re.findall(r"\S+\.py\b", text):
            base = match.replace("\\", "/").rsplit("/", 1)[-1]
            # In source code the name arrives quoted: (repo / "main.py").
            self.assertEqual(base.strip("\"'"), "main.py",
                             f"run_from_source invokes {match}")


# ---------------------------------------------------------------------------
# Wire capture against the old lab file's semantics.
#
# The lab rig cannot sit inside a regression test, so this is the
# closest thing to running our output through Welber's setup: a fake
# trigger port records every byte the real SerialBackend writes, each
# with its own perf_counter stamp, while real headless blocks run on
# the real engine (reaction and pattern, keyboard input and fake
# sensor input). The assertions hold the stream to the old file's
# observable behaviour (SRT_Sequence_learning_Final_v2.py: one code at
# flash onset, reset 0 after every pulse), corrected where the spec
# documents the old file's two bugs: the frame-counted pulse that
# actually delivered 1-4 ms, and the chr()/UTF-8 encoding that writes
# two bytes for any code above 127.
# ---------------------------------------------------------------------------


class _CaptureTriggerPort:
    """Logic-analyser stand-in for the pyserial handle: keeps every
    write with a perf_counter stamp so pulse widths and gaps are
    measured off the wire, not inferred from the writer's own
    bookkeeping."""

    def __init__(self) -> None:
        self.is_open = True
        self.writes: list[tuple[float, bytes]] = []

    def write(self, payload) -> int:
        data = bytes(payload)
        self.writes.append((time.perf_counter(), data))
        return len(data)

    def close(self) -> None:
        self.is_open = False


def _capture_backend():
    """A real SerialBackend riding the capture port, so the bytes on
    the fake wire went through the exact write path the lab box sees,
    including the bytes([code]) encoding."""
    from finger_rehab.hardware.eeg_trigger import SerialBackend
    backend = SerialBackend("fake-lab-box")
    port = _CaptureTriggerPort()
    backend._serial = port
    return backend, port


def _fake_sensor_source():
    """A real MultiSerialSource whose board handle is a stub. The
    engine then treats the session as a force session; samples are
    pushed through engine._feed_detectors, the same call the frame
    loop makes when it drains the 200 Hz queue."""
    from finger_rehab.hardware.multi_serial import MultiSerialSource

    class _StubBoard:
        is_connected = True

        def send_command(self, cmd: str) -> bool:
            return True

        def get_sample(self, timeout: float = 0.0):
            return None

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    src = MultiSerialSource(ports=["fake"], hand_assignment=["right"])
    src.hands[0].source = _StubBoard()
    return src


class _WireResponder:
    """Answers stimuli the way a patient at the desk would.

    keyboard posts pygame KEYDOWN events into mode.handle_event, the
    shipped fallback input path, so key resolution and press queueing
    run for real. sensor feeds 200 Hz samples through the engine's
    _feed_detectors so the real FSR detector produces the PressEvent
    and its own crossing timestamp.
    """

    SAMPLE_DT = 0.005          # the boards' 200 Hz cadence
    REACT_S = 0.16             # clears the 100 ms anticipation cut
    HOLD_S = 0.06              # sensor press pulse length
    REST_VAL = 100             # resting ADC counts
    PRESS_VAL = 700            # over abs_on_min and baseline + on_delta

    def __init__(self, eng, script: list[str], input_kind: str) -> None:
        self.eng = eng
        self.script = script
        self.input_kind = input_kind
        self._keys = self._lane_keys(eng)
        self._stim_i = -1
        self._seen_trial: int | None = None
        self._acted = True
        self._stim_t = 0.0
        self._target = 0
        self._last_sample = 0.0
        self._press_lane: int | None = None
        self._press_until = 0.0
        self._rest_token: float | None = None

    @staticmethod
    def _lane_keys(eng) -> dict[int, int]:
        from finger_rehab.game.modes._keys import keymap_for_hand, resolve_key
        km = eng.cfg.get(keymap_for_hand(eng.hand_mode), {}) or {}
        out: dict[int, int] = {}
        for name, lane in km.items():
            code = resolve_key(name)
            if code is not None:
                out[int(lane)] = code
        return out

    def _press(self, lane: int, now: float) -> None:
        if self.input_kind == "keyboard":
            import pygame
            ev = pygame.event.Event(pygame.KEYDOWN,
                                    {"key": self._keys[lane]})
            self.eng.mode.handle_event(ev)
        else:
            self._press_lane = lane
            self._press_until = now + self.HOLD_S

    def _feed_samples(self, now: float) -> None:
        if self.input_kind != "sensor":
            return
        if now - self._last_sample < self.SAMPLE_DT:
            return
        self._last_sample = now
        vals = [self.REST_VAL] * 4
        if self._press_lane is not None:
            if now < self._press_until:
                vals[self._press_lane] = self.PRESS_VAL
            else:
                self._press_lane = None
        self.eng._feed_detectors(now, tuple(vals))

    def step(self, now: float) -> None:
        self._feed_samples(now)
        mode = self.eng.mode
        if mode is None:
            return
        active = getattr(mode, "active", None)
        if active is not None and active.trial_id != self._seen_trial:
            self._seen_trial = active.trial_id
            self._stim_i += 1
            self._stim_t = active.stim_t_perf
            self._target = active.lane
            self._acted = False
        if not self._acted and now >= self._stim_t + self.REACT_S:
            self._acted = True
            action = (self.script[self._stim_i]
                      if self._stim_i < len(self.script) else "correct")
            if action == "correct":
                self._press(self._target, now)
            elif action == "wrong":
                self._press((self._target + 1) % 4, now)
            # timeout: sit on the hands and let the window expire
        # Pattern rests are self-paced past the floor; one press
        # advances. The token stops the responder pressing every frame.
        rest_until = getattr(mode, "_rest_min_until", None)
        if (getattr(mode, "phase", None) == "rest"
                and rest_until is not None
                and now >= rest_until + 0.05
                and self._rest_token != rest_until):
            self._rest_token = rest_until
            self._press(0, now)


def _pump_block(eng, responder, timeout_s: float) -> None:
    """The frame loop, minus the drawing: input, mode update, then the
    flip-anchored stimulus flush and the marker tick, exactly the
    order run() uses. No sleep, so tick() runs at sub-millisecond
    cadence and the measured pulse width reflects the writer's wall
    clock hold rather than a test-loop artefact."""
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        mode = eng.mode
        if mode is None:
            break
        phase = getattr(mode, "_phase", None) or getattr(mode, "phase", None)
        if phase == "done":
            break
        responder.step(time.perf_counter())
        mode.update(0.0)
        eng._flush_eeg_stim()
        eng.markers.tick()
    eng.markers.drain(0.5)


def _run_wire_block(mode_name: str, input_kind: str) -> dict:
    import pygame
    pygame.init()
    try:
        with tempfile.TemporaryDirectory() as td:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [640, 480]
            cfg.data["audio"]["enabled"] = False
            cfg.data["session"]["data_dir"] = td
            cfg.data["session"]["participant"] = "WireProof"
            cfg.data["report"] = {"enabled": False}
            # Screen-only cue so reaction's expected stimulus byte is
            # exactly 30, the old file's anchor code.
            cfg.data["cue"] = {"buzz_before": False, "sound_before": False,
                               "sound_after": False, "buzz_after": False,
                               "show_target": True}
            cfg.data["eeg"] = {"enabled": True, "port": None,
                               "require_port": False,
                               "pulse_ms": 10, "gap_ms": 10}
            if mode_name == "reaction":
                # One trial in each correctness class the old file
                # could never mark: correct, wrong finger, timeout.
                script = ["correct", "wrong", "timeout", "correct"]
                cfg.data["reaction"] = {
                    "seed": 907, "catch_rate": 0.0,
                    "block_trials": len(script), "attempt_cap": 8,
                    "fp_min_s": 0.08, "fp_mean_extra_s": 0.0,
                    "fp_max_s": 1.0, "fp_mode": "exponential",
                    "rest_gate_s": 0.05, "feedback_s": 0.05,
                    "false_start_feedback_s": 0.05,
                    "inter_trial_gap_s": 0.05,
                    "response_windows_s": [0.5],
                }
            else:
                # Test Mode's two-take miniature: 4 trained + 2 probe
                # trials, so both 40 and 41 reach the wire. The rsi
                # keeps consecutive onsets over 200 ms apart so a
                # -200 ms baseline window never touches the previous
                # stimulus.
                script = ["correct", "timeout", "correct", "correct",
                          "correct", "correct"]
                cfg.data["game"]["test_mode_enabled"] = True
                cfg.data["game"]["test_mode_trials"] = len(script)
                cfg.data.setdefault("pattern", {})
                cfg.data["pattern"].update({
                    "seed": 907, "rsi_ms": 120, "timeout_ms": 500,
                    "rest_min_s": 0.3, "long_rest_s": 0.3,
                })
            source = (KeyboardOnlySource() if input_kind == "keyboard"
                      else _fake_sensor_source())
            eng = GameEngine(cfg, source)
            gp = MagicMock()
            gp.lanes = []
            eng._screens = {"gameplay": gp, "results": MagicMock()}
            backend, port = _capture_backend()
            eng.markers.backend = backend
            eng.eeg_session_start()
            if mode_name == "reaction":
                eng.begin_reaction_block()
            else:
                eng.begin_pattern_block()
            root = Path(eng.session_paths.root)
            responder = _WireResponder(eng, script, input_kind)
            _pump_block(eng, responder, timeout_s=30.0)
            done_phase = (getattr(eng.mode, "_phase", None)
                          or getattr(eng.mode, "phase", None))
            eng._eeg_shutdown()
            with (root / "trials.csv").open() as f:
                trial_rows = list(csv.DictReader(f))
            with (root / "raw.csv").open() as f:
                eeg_rows = [r for r in csv.DictReader(f)
                            if r["event"] == "eeg"]
            return {
                "mode": mode_name, "input": input_kind,
                "script": script, "writes": list(port.writes),
                "trial_rows": trial_rows, "eeg_rows": eeg_rows,
                "done_phase": done_phase,
            }
    finally:
        pygame.quit()


# Each scenario runs one real block, several wall-clock seconds of
# protocol time, so it runs once and every assertion reads the cache.
_WIRE_SCENARIOS: dict[tuple[str, str], dict] = {}


def _wire_scenario(mode_name: str, input_kind: str) -> dict:
    key = (mode_name, input_kind)
    if key not in _WIRE_SCENARIOS:
        _WIRE_SCENARIOS[key] = _run_wire_block(mode_name, input_kind)
    return _WIRE_SCENARIOS[key]


class _WireHarness(unittest.TestCase):
    SCENARIOS = (("reaction", "keyboard"), ("reaction", "sensor"),
                 ("pattern", "keyboard"), ("pattern", "sensor"))

    @staticmethod
    def _codes(scn) -> list[tuple[float, int]]:
        return [(t, payload[0]) for t, payload in scn["writes"]]

    @staticmethod
    def _stim_band(scn) -> tuple[int, int]:
        return (40, 41) if scn["mode"] == "pattern" else (30, 38)

    def _each(self):
        for mode_name, input_kind in self.SCENARIOS:
            scn = _wire_scenario(mode_name, input_kind)
            with self.subTest(mode=mode_name, input=input_kind):
                yield scn


class WireProtocolTests(_WireHarness):
    """Section 2 of the task: the old file's observable protocol,
    with the spec's corrections, measured on the fake wire."""

    def test_blocks_ran_to_completion(self) -> None:
        for scn in self._each():
            self.assertEqual(scn["done_phase"], "done")
            self.assertEqual(len(scn["trial_rows"]), len(scn["script"]))

    def test_every_marker_is_exactly_one_byte(self) -> None:
        # The old file's chr()/UTF-8 encoding would have written two
        # bytes for any code above 127; ours must never do that, and
        # the response and boundary codes in these blocks all sit
        # above 127.
        for scn in self._each():
            for _, payload in scn["writes"]:
                self.assertEqual(len(payload), 1, payload)
            self.assertTrue(any(p[0] > 127 for _, p in scn["writes"]),
                            "no code above 127 ever hit the wire, so "
                            "the encoding guard proved nothing")

    def test_every_pulse_is_followed_by_a_reset_zero(self) -> None:
        # The old file's one honest habit, kept: the line always
        # returns to 0 between markers, and the stream ends at 0 so
        # the trigger lines cannot stay latched after shutdown.
        for scn in self._each():
            codes = self._codes(scn)
            for i, (_, code) in enumerate(codes):
                if code == 0:
                    continue
                self.assertLess(i + 1, len(codes),
                                f"marker {code} never reset")
                self.assertEqual(codes[i + 1][1], 0,
                                 f"marker {code} followed by "
                                 f"{codes[i + 1][1]}, not reset")
            self.assertEqual(codes[-1][1], 0, "line left latched high")

    def test_pulse_width_is_ten_ms_within_two(self) -> None:
        # The old file held the code by frame counting and actually
        # delivered 1-4 ms; the spec's fix is 10 ms on the wall clock.
        # Measured on the wire: marker write to the reset that follows
        # it. The pump ticks at sub-millisecond cadence, so anything
        # outside 10 +/- 2 ms is the writer's fault, not the loop's.
        for scn in self._each():
            codes = self._codes(scn)
            widths = []
            for i, (t, code) in enumerate(codes):
                if code != 0 and i + 1 < len(codes):
                    widths.append(codes[i + 1][0] - t)
            self.assertTrue(widths)
            for w in widths:
                self.assertGreaterEqual(w, 0.008, f"pulse {w * 1000:.1f} ms")
                self.assertLessEqual(w, 0.012, f"pulse {w * 1000:.1f} ms")

    def test_no_marker_inside_the_minimum_gap(self) -> None:
        # A new code only goes out after the line has sat at 0 for
        # gap_ms, or a 250 Hz amplifier could read two pulses as one.
        for scn in self._each():
            codes = self._codes(scn)
            last_reset_t = None
            for t, code in codes:
                if code == 0:
                    last_reset_t = t
                    continue
                if last_reset_t is not None:
                    gap = t - last_reset_t
                    self.assertGreaterEqual(
                        gap, 0.010 - 0.0005,
                        f"marker {code} after {gap * 1000:.1f} ms low")

    def test_stimulus_marker_accompanies_every_scorable_stimulus(self) -> None:
        # The old file's core property: code 30 on EVERY flash, so an
        # epoch-on-stimulus pipeline sees every trial. Ours: a
        # stimulus-band code for every scorable stimulus, counts
        # matching trials.csv exactly.
        for scn in self._each():
            lo, hi = self._stim_band(scn)
            stim = [c for _, c in self._codes(scn) if lo <= c <= hi]
            self.assertEqual(len(stim), len(scn["trial_rows"]))
            if scn["mode"] == "reaction":
                # Screen-only cue: the anchor code 30 itself, the
                # closest analogue of the old file's plain flash.
                self.assertEqual(set(stim), {30})
            else:
                # Trained items ride 40, probe material 41; the
                # miniature block carries both.
                self.assertEqual(set(stim), {40, 41})

    def test_stimulus_marker_lands_within_one_frame_of_the_flip(self) -> None:
        # The marker is armed at stimulus dispatch and wired straight
        # after the flip that shows it. t_event is the flip return,
        # t_wire the serial write; more than a frame between them
        # would mean the marker lost its anchor to the photons.
        for scn in self._each():
            lo, hi = self._stim_band(scn)
            checked = 0
            for row in scn["eeg_rows"]:
                detail = _parse_detail(row["detail"])
                if not lo <= int(detail["code"]) <= hi:
                    continue
                lag = float(detail["t_wire"]) - float(detail["t_event"])
                self.assertGreaterEqual(lag, 0.0)
                self.assertLessEqual(lag, 1.0 / 60.0,
                                     f"stim marker {lag * 1000:.1f} ms "
                                     "after its flip")
                checked += 1
            self.assertEqual(checked, len(scn["trial_rows"]))

    def test_wire_stamps_agree_with_logged_wire_times(self) -> None:
        # The spec's software cross-check, run on the fake wire: the
        # capture stamps must match raw.csv's t_wire values code for
        # code, within a couple of milliseconds. Session start and end
        # (240/241) fire outside any block, so they bracket the logged
        # rows on the wire but never appear in raw.csv.
        for scn in self._each():
            wire = [(t, c) for t, c in self._codes(scn) if c != 0]
            self.assertEqual(wire[0][1], 240)
            self.assertEqual(wire[-1][1], 241)
            logged = [_parse_detail(r["detail"]) for r in scn["eeg_rows"]]
            sent = [d for d in logged
                    if d["failed"] == "0" and d["dropped"] == "0"]
            self.assertEqual([c for _, c in wire[1:-1]],
                             [int(d["code"]) for d in sent])
            for (t_stamp, _), detail in zip(wire[1:-1], sent):
                self.assertLess(abs(t_stamp - float(detail["t_wire"])),
                                0.002)


class EpochingPipelineSmokeTests(_WireHarness):
    """Section 4 of the task: parse the captured byte stream the way
    Welber's epoching script would, and reconcile against the
    behavioural record. Counts must match exactly."""

    @staticmethod
    def _epochs(codes, lo, hi):
        """Cut the stream at stimulus-band onsets; everything up to
        the next onset belongs to that trial's epoch, which is how an
        epoch-on-stimulus pipeline reads a trigger channel."""
        onsets = [i for i, (_, c) in enumerate(codes) if lo <= c <= hi]
        epochs = []
        for j, i in enumerate(onsets):
            end = onsets[j + 1] if j + 1 < len(onsets) else len(codes)
            resp = [(t, c) for t, c in codes[i + 1:end]
                    if 100 <= c <= 131]
            epochs.append({"t": codes[i][0], "code": codes[i][1],
                           "resp": resp})
        return epochs

    def test_epoch_counts_reconcile_with_trials_csv(self) -> None:
        for scn in self._each():
            lo, hi = self._stim_band(scn)
            epochs = self._epochs(self._codes(scn), lo, hi)
            self.assertEqual(len(epochs), len(scn["trial_rows"]))
            for ep in epochs:
                self.assertEqual(len(ep["resp"]), 1,
                                 f"epoch at code {ep['code']} carries "
                                 f"{len(ep['resp'])} response markers")

    def test_response_codes_match_logged_outcomes(self) -> None:
        # Correctness in the byte must agree with the CSV row for the
        # same trial: correct rows carry 100 + lane, wrong-finger
        # misses 110 + the finger actually pressed, timeouts 130.
        for scn in self._each():
            lo, hi = self._stim_band(scn)
            epochs = self._epochs(self._codes(scn), lo, hi)
            for ep, row in zip(epochs, scn["trial_rows"]):
                code = ep["resp"][0][1]
                if row["feedback"] != "Miss":
                    self.assertEqual(code, 100 + int(row["lane"]) - 1, row)
                elif row["error_type"] == "wrong_finger":
                    self.assertEqual(
                        code, 110 + int(row["first_incorrect_lane"]) - 1,
                        row)
                else:
                    self.assertEqual(row["error_type"], "timeout", row)
                    self.assertEqual(code, 130, row)

    def test_pattern_band_tracks_the_pattern_trial_column(self) -> None:
        # 40 = trained item, 41 = random or probe material, and the
        # CSV's pattern_trial column is the same split, so the two
        # records must agree trial for trial.
        for input_kind in ("keyboard", "sensor"):
            scn = _wire_scenario("pattern", input_kind)
            with self.subTest(input=input_kind):
                epochs = self._epochs(self._codes(scn), 40, 41)
                for ep, row in zip(epochs, scn["trial_rows"]):
                    expected = 40 if row["pattern_trial"] == "TRUE" else 41
                    self.assertEqual(ep["code"], expected, row)

    def test_epochs_never_reach_back_into_the_previous_stimulus(self) -> None:
        # A -200 ms baseline window is the standard cut; consecutive
        # onsets closer than that would fold one trial's stimulus into
        # the next trial's baseline.
        for scn in self._each():
            lo, hi = self._stim_band(scn)
            onsets = [t for t, c in self._codes(scn) if lo <= c <= hi]
            for a, b in zip(onsets, onsets[1:]):
                self.assertGreater(b - a, 0.2)


if __name__ == "__main__":
    unittest.main()
