"""The gaps a whole simulated collection day left open, closed.

A ten-student day was run through the shipped engine and read end to
end by the notebook. Twelve things came back: some were faults in the
analysis, some were checks the shipped battery can never decide, and
some were the simulated hand being perfect where a real one is not.
This file pins the fixes for the first two kinds, driving real blocks
through the real engine and handing the folders to the real notebook
functions rather than asserting on a docstring.

What each class covers:

  BoardDropTests        a rig that falls off mid-block, and the Data
                        quality chapter saying so
  DominanceRefusalTests two different reasons for having no dominant
                        hand, said in two different sets of words
  ManualPortTests       a hand-set serial port only counts against a
                        block that actually ran on a serial rig
  LadderBandwidthTests  F1 read off the wave ladder, which the battery
                        does play, instead of off segments it does not
  DroppedCheckTests     E2 as DROPPED with its reason, not as no data
  UndecidedMessageTests every "cannot decide" message names its cause
  SyllableReturnTests   a missed word really does come back, so the
                        spaced-return check has a second term on a
                        real day even though a perfect model gives it
                        none
  FeasibilityClockTests a sitting shorter than its own blocks is
                        called out rather than quoted
  ForestMarkerTests     a mode with no variation gets a marker saying
                        so, not an empty line
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from tests.test_hand_support import (make_engine, drive, patched_clock,
                                     _press)


def setUpModule() -> None:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    import pygame
    pygame.quit()


def _notebook_code() -> str:
    """The notebook's own code as text.

    inspect.getsource cannot reach a function compiled out of a cell,
    so a test that has to prove a call site exists reads the file.
    """
    nb = json.loads((ROOT / "analysis"
                     / "session_analysis.ipynb").read_text(
                         encoding="utf-8"))
    return "".join("".join(c["source"]) for c in nb["cells"]
                   if c["cell_type"] == "code")


def _load_notebook(tag: str):
    """Every notebook cell's definitions in one namespace, the pattern
    the other per-chapter tests use."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_" + tag
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in _code_cells():
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                              if not k.startswith("__")})


# ==================================================================
# A board that falls off mid-block
# ==================================================================
class DropRig:
    """measure_battery's fake rig with a board that can go away.

    Not a doctored CSV: while blacked out it stops delivering samples
    AND reports itself disconnected, which is what
    GameEngine._check_source_connection watches for. The engine writes
    its own source_disconnected and source_reconnected rows, and the
    hole in t_perf appears on its own because nothing was pushed.
    """

    provides_samples = True
    name = "SimulatedTwoBoardRig"
    hand_modes_available = {"right", "left", "both"}
    hands: list = []

    def __init__(self) -> None:
        from collections import deque
        self._q: deque = deque()
        self.commands: list[str] = []
        self.blackout = False
        self.is_connected = True

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def push(self, t_perf, values, hand_mode) -> None:
        if self.blackout:
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


def _reaction_block_with_drop(root: Path, drop: bool):
    """One real reaction block on the fake rig, optionally with the
    board falling off for DROP_FOR_S seconds part way in. Returns the
    session folder."""
    import measure_battery as mb

    code = "GAP1" if drop else "GAP0"
    rig = DropRig()
    hand = mb.HandModel()
    with patched_clock() as clock:
        eng = mb.build_engine(code, "right", root, rig)
        eng.cfg.data["game"]["test_mode_enabled"] = True
        eng.cfg.data["game"]["test_mode_trials"] = 10
        eng.begin_reaction_block()
        who = mb.Participant(hand, random.Random(4))
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
                    rig.is_connected = False
                elif not want and rig.blackout:
                    rig.blackout = False
                    rig.is_connected = True
            while next_sample <= now:
                rig.push(next_sample, hand.sample(next_sample),
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
    # Both runs land in the same tree, so pick this run's own folder
    # by its code rather than by sort order.
    folders = sorted(p for p in root.rglob(f"{code}_*_reaction")
                     if p.is_dir())
    assert len(folders) == 1, folders
    return folders[0]


class BoardDropTests(unittest.TestCase):
    """The one thing on a collection day an analyst has to be told.

    The engine already wrote the disconnect into raw.csv; the notebook
    read the file and said nothing, so a 25 second hole in a chords
    block came back as ordinary force data.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        root = Path(cls._td.name)
        cls.dropped = _reaction_block_with_drop(root, drop=True)
        cls.clean = _reaction_block_with_drop(root, drop=False)
        cls.ra = _load_notebook("drop")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _events(self, folder):
        raw = pd.read_csv(Path(folder) / "raw.csv")
        ev = raw["event"].fillna("").astype(str)
        return raw, ev

    def test_the_engine_wrote_the_drop_into_the_raw_log(self) -> None:
        _raw, ev = self._events(self.dropped)
        self.assertEqual(int((ev == "source_disconnected").sum()), 1)
        self.assertEqual(int((ev == "source_reconnected").sum()), 1)

    def test_the_clean_block_has_no_drop_to_find(self) -> None:
        _raw, ev = self._events(self.clean)
        self.assertEqual(int((ev == "source_disconnected").sum()), 0)

    def test_the_notebook_counts_the_drop_and_the_hole(self) -> None:
        tbl = self.ra.stream_gaps([self.dropped])
        self.assertEqual(len(tbl), 1)
        row = tbl.iloc[0]
        self.assertEqual(int(row["disconnects"]), 1)
        self.assertEqual(int(row["reconnects"]), 1)
        self.assertEqual(int(row["still_down_at_end"]), 0)
        # The board was away for DROP_FOR_S; both the paired events and
        # the hole in the sample stream have to agree about that.
        self.assertAlmostEqual(float(row["seconds_down"]), DROP_FOR_S,
                               delta=0.5)
        self.assertGreaterEqual(int(row["sample_gaps"]), 1)
        self.assertAlmostEqual(float(row["worst_gap_s"]), DROP_FOR_S,
                               delta=0.5)

    def test_a_clean_block_produces_no_row_at_all(self) -> None:
        tbl = self.ra.stream_gaps([self.clean])
        self.assertTrue(tbl.empty)

    def test_the_data_quality_chapter_names_the_block(self) -> None:
        folders = [self.dropped, self.clean]
        metas = self.ra.load_metas(folders)
        trials = self.ra.load_trials(folders) \
            if hasattr(self.ra, "load_trials") else None
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ra.stream_gaps(folders)
        out = buf.getvalue()
        self.assertIn("BOARD DROPS AND STREAM GAPS", out)
        self.assertIn(self.ra.game_key(self.dropped), out)
        self.assertIn("missing, not zero", out)
        # And the clean block is not accused of anything.
        self.assertNotIn(self.ra.game_key(self.clean), out)
        self.assertIsNotNone(metas)
        del trials

    def test_a_clean_selection_says_so_in_one_line(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ra.stream_gaps([self.clean])
        self.assertIn("board drops", buf.getvalue())
        self.assertIn("none", buf.getvalue())

    def test_sec_quality_calls_it(self) -> None:
        """The report is wired into the chapter, not just available."""
        self.assertIn("stream_gaps(folders)", _notebook_code())


# ==================================================================
# Two different ways to have no dominant hand
# ==================================================================
class DominanceRefusalTests(unittest.TestCase):
    """session_dominant returned None for two unrelated reasons and
    the caller printed the first one for both. On a ten-student day it
    said the login recorded no dominant hand, with ten of them on
    disk."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("dom")

    def _metas(self, hands):
        return {f"g{i}": {"dominant_hand": h, "participant": f"P{i:02d}"}
                for i, h in enumerate(hands, start=1)}

    def test_one_hand_comes_back_with_no_reason(self) -> None:
        got = self.ra.session_dominant(self._metas(["right", "right"]),
                                       with_reason=True)
        self.assertEqual(got, ("right", ""))

    def test_nothing_recorded_says_nothing_recorded(self) -> None:
        hand, why = self.ra.session_dominant(self._metas(["", ""]),
                                             with_reason=True)
        self.assertIsNone(hand)
        self.assertEqual(why, "none recorded")

    def test_two_hands_say_mixed_not_missing(self) -> None:
        hand, why = self.ra.session_dominant(
            self._metas(["right", "left", "right"]), with_reason=True)
        self.assertIsNone(hand)
        self.assertEqual(why, "mixed")

    def test_the_old_call_shape_still_works(self) -> None:
        # Every existing caller passes one argument and expects a hand
        # or None back, not a tuple.
        self.assertEqual(
            self.ra.session_dominant(self._metas(["left"])), "left")
        self.assertIsNone(self.ra.session_dominant(
            self._metas(["left", "right"])))

    def test_the_two_refusals_read_differently(self) -> None:
        rows = pd.DataFrame({"side": ["left", "right"], "rt": [1.0, 2.0]})
        missing = self.ra.per_hand_pair(rows, "rt", None,
                                        reason="none recorded")[2]
        mixed = self.ra.per_hand_pair(rows, "rt", None,
                                      reason="mixed")[2]
        self.assertIn("recorded no dominant hand", missing)
        self.assertIn("more than one dominant hand", mixed)
        self.assertIn("cohort table pairs within participant", mixed)
        self.assertNotEqual(missing, mixed)

    def test_an_unknown_reason_falls_back_to_the_safe_wording(self):
        rows = pd.DataFrame({"side": ["left", "right"], "rt": [1.0, 2.0]})
        note = self.ra.per_hand_pair(rows, "rt", None, reason="???")[2]
        self.assertEqual(
            note, self.ra.DOMINANCE_REFUSALS["none recorded"])


# ==================================================================
# The manual serial port count
# ==================================================================
class ManualPortTests(unittest.TestCase):
    """The feasibility chapter called 106 simulated blocks "sessions
    where somebody had to intervene", because the config snapshot
    carries serial.right_port whatever the source was."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("port")

    def _count(self, source_name, port):
        self.assertIn("on_serial", _notebook_code())
        meta = {"source_name": source_name,
                "config_snapshot": {"serial": {"left_port": None,
                                               "right_port": port}}}
        on_serial = str(meta.get("source_name") or "").startswith(
            ("SerialSource", "MultiSerial"))
        serial = meta["config_snapshot"]["serial"]
        return bool(on_serial and (serial.get("left_port")
                                   or serial.get("right_port")))

    def test_a_simulated_rig_is_never_a_manual_port(self) -> None:
        self.assertFalse(self._count("SimulatedTwoBoardRig",
                                     "/dev/cu.usbserial-140"))

    def test_a_keyboard_block_is_never_a_manual_port(self) -> None:
        self.assertFalse(self._count("KeyboardOnlySource",
                                     "/dev/cu.usbserial-140"))

    def test_a_real_serial_block_with_a_set_port_still_counts(self):
        self.assertTrue(self._count("MultiSerial(right@/dev/cu.x)",
                                    "/dev/cu.x"))
        self.assertTrue(self._count("SerialSource(/dev/cu.x@115200)",
                                    "/dev/cu.x"))

    def test_a_real_serial_block_on_autoport_does_not_count(self) -> None:
        self.assertFalse(self._count("MultiSerial(right@/dev/cu.x)", None))


# ==================================================================
# F1 read off the ladder the battery actually plays
# ==================================================================
def _long_rows(rho_sign: float, n=6, levels=8, seed=3):
    """A cohort long table holding only per-level force pilot MAE, with
    error rising (rho_sign +1) or falling (-1) with the level.

    Jittered on a fixed seed: a perfectly straight ladder gives every
    participant a rho of exactly 1, and a signed-rank test on identical
    values is a degenerate case rather than the one the check meets.
    """
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        who = f"P{i:02d}"
        for lvl in range(1, levels + 1):
            rows.append({"participant": who, "mode": "force_pilot",
                         "hand_role": "both", "phase": "battery",
                         "metric": f"lvl{lvl}_mae_pct",
                         "value": (5.0 + rho_sign * 0.4 * lvl
                                   + rng.gauss(0.0, 0.22)),
                         "n": 1})
    return pd.DataFrame(rows)


class LadderBandwidthTests(unittest.TestCase):
    """F1 could never be decided: it asked for assessment and sine
    segments the battery does not play, and its refusal named the
    wrong missing file into the bargain."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("f1")

    def test_error_rising_with_level_passes(self) -> None:
        row = self.ra._ladder_bandwidth_row(_long_rows(+1.0), 3, 0)
        self.assertEqual(row["id"], "F1")
        self.assertEqual(row["verdict"], "pass")
        self.assertGreater(row["value"], 0.8)
        self.assertEqual(row["n"], 6)

    def test_error_falling_with_level_fails(self) -> None:
        row = self.ra._ladder_bandwidth_row(_long_rows(-1.0), 3, 0)
        self.assertEqual(row["verdict"], "fail")
        self.assertLess(row["value"], 0.0)

    def test_the_refusal_names_the_metric_that_is_missing(self) -> None:
        # Not an empty table: a real selection that holds force pilot
        # blocks with no per-level metric on them.
        other = _long_rows(+1.0)
        other["metric"] = "mae_pct"
        row = self.ra._ladder_bandwidth_row(other, 3, 0)
        self.assertEqual(row["verdict"], "not testable")
        self.assertIn("lvl<n>_mae_pct", row["detail"])
        # And it never blames raw.csv again: raw.csv was present in
        # every force pilot folder on the day this was found.
        self.assertNotIn("raw.csv", row["detail"])

    def test_it_says_why_it_is_reading_the_ladder(self) -> None:
        row = self.ra._ladder_bandwidth_row(_long_rows(+1.0), 3, 0)
        self.assertIn("one ladder climb", row["detail"])

    def test_a_participant_with_too_few_levels_is_not_counted(self):
        thin = _long_rows(+1.0, n=6, levels=3)
        row = self.ra._ladder_bandwidth_row(thin, 3, 0)
        self.assertEqual(row["n"], 0)
        self.assertEqual(row["verdict"], "not testable")


# ==================================================================
# Checks the battery cannot decide, said as dropped
# ==================================================================
class DroppedCheckTests(unittest.TestCase):
    """E2 needs echo's ladder rule. The battery plays Simon. That is a
    design fact, not a thin selection, and printing "no data" sent a
    reader looking for a file that was never going to exist."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("dropped")

    def test_the_config_really_does_play_simon(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(cfg.get("echo.rule"), "simon")
        preset = cfg.get("protocol.presets.study_battery") or {}
        over = (preset.get("overrides") or {}).get("echo") or {}
        self.assertNotIn("rule", over,
                         "the preset now overrides the echo rule, so E2 "
                         "may be live again and this row should move")

    def test_echo_only_marks_a_hebb_trial_under_the_ladder_rule(self):
        src = (ROOT / "finger_rehab" / "game" / "modes"
               / "echo.py").read_text(encoding="utf-8")
        self.assertIn('self.rule == "ladder"', src)

    def test_e2_is_a_dropped_row_beside_r3_and_p2(self) -> None:
        self.assertIn("E2", self.ra.COHORT_DROPPED_CHECKS)
        row = self.ra._dropped_row("E2")
        self.assertEqual(row["verdict"], "dropped")
        self.assertIn("ladder", row["detail"])
        self.assertIn("simon", row["detail"])
        self.assertIn("Simon rule", row["criterion"])

    def test_the_two_repeat_rows_keep_their_own_reason(self) -> None:
        for cid in ("R3", "P2"):
            row = self.ra._dropped_row(cid)
            self.assertEqual(row["verdict"], "dropped")
            self.assertIn("played twice", row["detail"])
            self.assertIn("no block is repeated", row["criterion"])

    def test_the_design_document_carries_the_same_three(self) -> None:
        doc = (ROOT / "docs" / "research"
               / "healthy_baseline_study.txt").read_text(encoding="utf-8")
        self.assertIn("E2  echo,", doc)
        self.assertIn("E2 DROPPED", doc)
        self.assertIn("Three rows carry the word DROPPED", doc)
        # The survivor list must not still claim E2.
        self.assertNotIn("B1 B2 B3 B4, E1 E2", doc)

    def test_the_legend_no_longer_says_dropped_means_a_repeat(self):
        self.assertIn("shipped battery cannot produce the comparison",
                      _notebook_code())


class UndecidedMessageTests(unittest.TestCase):
    """Every remaining "cannot decide" prints its own cause. Three of
    them used to print the word "no data", which is only true when the
    selection is thin."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("absent")

    def _spec(self, mode, cid):
        for spec in self.ra.MODE_LIT[mode]:
            if spec["id"] == cid:
                return spec
        self.fail(f"{cid} is not in MODE_LIT[{mode}]")

    def test_hick_says_only_the_choice_sub_mode_is_played(self) -> None:
        spec = self._spec("reaction", "R-hick")
        self.assertIn("absent", spec)
        value, _ok, detail = spec["absent"]
        self.assertNotIn("no data", value)
        self.assertIn("sub_mode: choice", detail)

    def test_ras_says_there_is_no_control_block(self) -> None:
        value, _ok, detail = self._spec("rhythm", "Rh-ras")["absent"]
        self.assertNotIn("no data", value)
        self.assertIn("fixed-cadence control", detail)

    def test_the_two_runtime_refusals_say_it_is_the_design(self) -> None:
        """A selection that DOES hold the block still fills these two
        rows from the chapter, not from the registry, so the chapter's
        own wording has to carry the design reason as well. Both used
        to read as though another selection might decide them."""
        # The wording is split across adjacent string literals in the
        # cell, so the joined text is what to search.
        src = " ".join(_notebook_code().replace('"', " ").split())
        for phrase in (
                "the battery pins reaction.sub_mode: choice",
                "the battery carries no control block",
                "the design says so in Section 1.1",
                "puts the comparison out of scope in Section 1.6"):
            self.assertIn(phrase, src)
        self.assertEqual(
            src.count("cannot be decided by adding participants"), 2)

    def test_e2_says_dropped(self) -> None:
        value, verdict, detail = self._spec("echo", "E2")["absent"]
        self.assertEqual(self.ra.lit_verdict(verdict), "dropped")
        self.assertIn("simon", detail)

    def test_print_lit_checks_uses_the_absent_line(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = self.ra.print_lit_checks("rhythm")
        out = buf.getvalue()
        self.assertIn("not available in this design", out)
        self.assertIn("fixed-cadence control", out)
        row = got[got["id"] == "Rh-ras"].iloc[0]
        self.assertEqual(row["value"], "not available in this design")

    def test_a_check_with_no_absent_line_still_says_no_data(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = self.ra.print_lit_checks("rhythm")
        row = got[got["id"] == "Rh1"].iloc[0]
        self.assertEqual(row["value"], "no data")
        self.assertEqual(row["verdict"], "not testable")


# ==================================================================
# The word that comes back
# ==================================================================
class SyllableReturnTests(unittest.TestCase):
    """The spaced-return check had nothing to read on the simulated
    day, and the first diagnosis blamed words_per_block. It is not
    that: syllables parks a word for a later return only when the word
    is MISSED, so a reader who never errs produces no return at all.
    This drives a real block with deliberate wrong presses and shows
    the return arrives."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name)
        cls.folder = cls._play(cls.root)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    @staticmethod
    def _play(root: Path) -> Path:
        """One real syllables block where the first press on the first
        few words goes to a foil."""
        wrong_words = {"n": 0}

        with patched_clock() as clock:
            eng = make_engine("right", str(root))
            eng.cfg.data["syllables"].update(
                {"words_per_block": 8, "round_size": 8, "break_s": 0,
                 "warmup_taps": 0, "rung": 3})
            eng.begin_syllables_block()
            seen = {"key": None}

            def respond(clk):
                mode = eng.mode
                opts = getattr(mode, "option_set", None)
                if opts is None or getattr(mode, "phase", "") != "choose":
                    return
                key = (getattr(mode, "trial_counter", 0), opts.pos)
                if seen["key"] == key:
                    return
                seen["key"] = key
                spawn = getattr(mode, "_spawn_t", None)
                lock = float(getattr(mode, "spawn_lockout_s", 0.25) or 0.25)
                t = max(clk.t, float(spawn if spawn is not None else clk.t)
                        + lock) + 0.30
                lane = int(opts.target_lane)
                # Miss the first syllable of the first three words, so
                # those words are parked and come back later.
                if opts.pos == 0 and wrong_words["n"] < 3:
                    wrong_words["n"] += 1
                    foils = [int(o.lane) for o in opts.options
                             if int(o.lane) != lane]
                    if foils:
                        lane = foils[0]
                mode.queue_press(_press(lane, t, "right"))

            drive(eng, clock, responder=respond, max_steps=200000,
                  stop=lambda: eng.trial_logger is None)
            if eng.trial_logger is not None:
                eng.finish_block()
        folders = sorted(p for p in root.rglob("*_syllables") if p.is_dir())
        return folders[-1]

    def _stimulus_fields(self):
        rows = pd.read_csv(Path(self.folder) / "trials.csv")
        out = []
        for text in rows["stimulus"].fillna("").astype(str):
            out.append(dict(part.split("=", 1) for part in text.split(";")
                            if "=" in part))
        return out

    def test_the_block_recorded_wrong_first_presses(self) -> None:
        fields = self._stimulus_fields()
        self.assertTrue(fields, "the block wrote no option sets")
        firsts = [f.get("first") for f in fields]
        self.assertIn("wrong", firsts)

    def test_a_missed_word_is_parked_and_comes_back(self) -> None:
        raw = pd.read_csv(Path(self.folder) / "raw.csv")
        ev = raw["event"].fillna("").astype(str)
        self.assertGreaterEqual(int((ev == "word_parked").sum()), 1)
        rets = {int(f.get("ret", 0)) for f in self._stimulus_fields()}
        self.assertTrue(any(r > 0 for r in rets),
                        f"no return trial was played; ret values {rets}")

    def test_the_return_is_the_same_word(self) -> None:
        by_ret = {}
        for f in self._stimulus_fields():
            by_ret.setdefault(int(f.get("ret", 0)), set()).add(
                f.get("word"))
        returned = set().union(*[v for k, v in by_ret.items() if k > 0])
        self.assertTrue(returned <= by_ret.get(0, set()),
                        "a returned word was never met first time")

    def test_the_notebook_can_decide_s4_on_this_block(self) -> None:
        """The point of the whole class: with returns on disk the
        spaced-return check has two terms and prints a verdict."""
        ra = _load_notebook("s4")
        trials = pd.read_csv(Path(self.folder) / "trials.csv")
        trials["mode"] = "syllables"
        sets = ra.syllable_set_frame(trials)
        self.assertIn("ret", sets.columns)
        self.assertGreater(int((sets["ret"] > 0).sum()), 0,
                           "no return set reached the notebook frame")
        first = sets[sets["ret"] == 0]["first_ok"]
        again = sets[sets["ret"] > 0]["first_ok"]
        self.assertGreaterEqual(len(first), 5)
        self.assertGreaterEqual(len(again), 5)

    def test_the_simulator_can_be_told_to_err(self) -> None:
        """scripts/measure_battery.py keeps a perfect reader so the
        timing number does not move; the cohort simulator overrides
        it, which is what gives a simulated day anything to read."""
        import measure_battery as mb
        import simulate_cohort as sc
        self.assertEqual(mb.Participant.SYLLABLE_ERROR_RATE, 0.0)
        who = sc.CohortParticipant(mb.HandModel(), random.Random(1),
                                   {"read_acc": 0.80}, 0)
        who._syl_rung = 1
        easy = who.syllable_error_rate()
        who._syl_rung = 8
        hard = who.syllable_error_rate()
        self.assertGreater(easy, 0.0)
        self.assertGreater(hard, easy)
        self.assertLessEqual(hard, 0.45)


# ==================================================================
# The clock guard on the feasibility table
# ==================================================================
class FeasibilityClockTests(unittest.TestCase):
    """door_to_door_min read 0.07 minutes against 33 minutes of blocks
    on the simulated day, because the blocks time themselves on the
    performance clock and the folder stamps come off the wall clock.
    A number that impossible should be refused, not printed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("feas")

    def test_the_guard_is_in_the_chapter(self) -> None:
        src = _notebook_code()
        self.assertIn("shorter door to", src)
        # The headline range must be computed off the usable rows only.
        self.assertIn('tbl.loc[tbl["door_to_door_min"] >= '
                      'tbl["playing_min"]', src)


# ==================================================================
# The figure row that drew nothing
# ==================================================================
class ForestMarkerTests(unittest.TestCase):
    """Chords and syllables took a tick label on the within-block
    figure and drew no marker, because dz is undefined when nobody's
    first third differs from their last third. A blank line reads as
    missing data; it is the opposite."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook("forest")

    def _frame(self, dzs):
        return pd.DataFrame([
            {"mode": m, "hand_role": "both", "better": "lower",
             "gate": "reported", "reading": "clean", "dz": dz,
             "dz_lo": (dz - 0.3 if pd.notna(dz) else float("nan")),
             "dz_hi": (dz + 0.3 if pd.notna(dz) else float("nan"))}
            for m, dz in zip(("reaction", "mirror", "chords",
                              "syllables"), dzs)])

    def _markers(self, ax):
        filled = sum(len(l.get_xdata()) for l in ax.lines
                     if l.get_marker() == "o"
                     and l.get_markerfacecolor() != "none")
        empty = sum(len(l.get_xdata()) for l in ax.lines
                    if l.get_marker() == "o"
                    and l.get_markerfacecolor() == "none")
        return filled, empty

    def test_every_row_gets_a_marker(self) -> None:
        nan = float("nan")
        ax = self.ra.within_block_forest(
            self._frame([-0.5, -0.2, nan, nan]))
        self.assertIsNotNone(ax)
        filled, empty = self._markers(ax)
        self.assertEqual(filled, 2)
        self.assertEqual(empty, 2)
        self.assertEqual(len(ax.get_yticklabels()), 4)

    def test_the_open_markers_sit_on_zero(self) -> None:
        nan = float("nan")
        ax = self.ra.within_block_forest(
            self._frame([-0.5, -0.2, nan, nan]))
        opens = [l for l in ax.lines if l.get_marker() == "o"
                 and l.get_markerfacecolor() == "none"]
        self.assertEqual(len(opens), 1)
        self.assertEqual(list(opens[0].get_xdata()), [0.0, 0.0])

    def test_the_legend_names_what_the_open_marker_means(self) -> None:
        nan = float("nan")
        ax = self.ra.within_block_forest(
            self._frame([-0.5, -0.2, nan, nan]))
        texts = [t.get_text() for t in ax.get_legend().get_texts()]
        self.assertIn("no variation to measure (dz undefined)", texts)

    def test_a_table_with_every_dz_present_draws_no_legend(self) -> None:
        ax = self.ra.within_block_forest(
            self._frame([-0.5, -0.2, 0.1, 0.3]))
        filled, empty = self._markers(ax)
        self.assertEqual(filled, 4)
        self.assertEqual(empty, 0)
        self.assertIsNone(ax.get_legend())

    def test_one_row_is_not_a_forest(self) -> None:
        self.assertIsNone(self.ra.within_block_forest(
            self._frame([-0.5])))
        self.assertIsNone(self.ra.within_block_forest(None))

    def test_the_chapter_calls_the_helper(self) -> None:
        self.assertIn("within_block_forest(drawable)", _notebook_code())


# ==================================================================
# The sitting has a length distribution, not a length
# ==================================================================
class SittingSpreadTests(unittest.TestCase):
    """The design quoted one measured number, 44.4 minutes, against a
    45 minute budget. Several blocks draw fresh material every time
    (their seed keys in config are empty on purpose), so no two
    sittings take the same number of minutes and one run is a sample
    of one. scripts/measure_battery.py can now run the sitting more
    than once and report the spread."""

    def test_the_seed_keys_really_are_empty(self) -> None:
        """The reason the sitting varies. If these were pinned the
        spread would be a bug rather than the design."""
        from finger_rehab.config import Config
        cfg = Config.load()
        empty = 0
        for key in ("reaction.foreperiod_seed", "chords.seed",
                    "syllables.seed", "buzz_hunt.seed"):
            val = cfg.get(key, "sentinel")
            if val == "sentinel":
                continue
            if val in (None, "", 0):
                empty += 1
        self.assertGreater(empty, 0,
                           "no per-block seed is left empty, so the "
                           "sitting should be repeatable and this "
                           "class has nothing to guard")

    def test_one_sitting_reports_the_minutes_it_took(self) -> None:
        import argparse
        import measure_battery as mb
        args = argparse.Namespace(code="P01", dominant="right", fps=240.0,
                                  cap_min=20.0, keep=False, seed=1,
                                  repeats=1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = mb.one_sitting(args, 1, quiet=True)
        self.assertIsNotNone(got)
        self.assertEqual(got["blocks"], 11)
        self.assertGreater(got["total_min"], 20.0)
        self.assertLess(got["total_min"], got["budget_min"] + 5.0)
        self.assertEqual(len(got["by_mode_min"]), 10)
        # Quiet means quiet: the per-block lines belong to the first
        # sitting only, or a --repeats 30 run is 330 lines of noise.
        self.assertEqual(buf.getvalue().strip(), "")

    def test_two_sittings_on_different_seeds_differ(self) -> None:
        """The claim the whole change rests on."""
        import argparse
        import measure_battery as mb
        args = argparse.Namespace(code="P01", dominant="right", fps=240.0,
                                  cap_min=20.0, keep=False, seed=1,
                                  repeats=2)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            a = mb.one_sitting(args, 1, quiet=True)
            b = mb.one_sitting(args, 101, quiet=True)
        self.assertNotAlmostEqual(a["total_min"], b["total_min"],
                                  places=2)

    def test_the_perfect_reader_leaves_the_syllable_timing_alone(self):
        """The cohort simulator's erring reader must not reach this
        script: a wrong press parks a word for a later return, which
        makes the block longer, and the budget number would move for a
        reason that has nothing to do with the battery."""
        import measure_battery as mb
        self.assertEqual(mb.Participant.SYLLABLE_ERROR_RATE, 0.0)
        who = mb.Participant(mb.HandModel(), random.Random(1))
        self.assertEqual(who.syllable_error_rate(), 0.0)

    def test_the_script_says_one_run_is_a_sample_of_one(self) -> None:
        src = (ROOT / "scripts"
               / "measure_battery.py").read_text(encoding="utf-8")
        self.assertIn("ONE RUN IS A SAMPLE OF ONE", src)
        self.assertIn("--repeats", src)

    def test_the_design_document_carries_the_spread(self) -> None:
        doc = (ROOT / "docs" / "research"
               / "healthy_baseline_study.txt").read_text(encoding="utf-8")
        self.assertIn("One sitting is one draw", doc)
        self.assertIn("43.11 to", doc)
        # And the old single number is still there as the record of
        # what was measured on the day it was measured.
        self.assertIn("median 44.4", doc)
