"""The SRT against the lab's own script.

The Reaction card runs the lab's serial reaction time task, Welber
Marinovic's PsychoPy script (archive/Webler EEG past program/
SRT_Sequence_learning_Final_v2.py), replicated trial for trial. These
tests read the script itself, so a constant that drifts from it fails
here, then drive whole sessions on a simulated 60 Hz flip clock and
check the frames: the 1000 ms first wait, the 100 ms flash, the
interval plus the one frame the script's loop adds, the anticipation
window, the deadline and miss pause, the practice word, the recall,
the three CSVs and the EEG bytes. The setups file, the setup screen
and the EEG lab's Play all swap are covered at the end.
"""
from __future__ import annotations

import ast
import csv
import json
import os
import random
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from finger_rehab.game import srt_setup as ss  # noqa: E402
from finger_rehab.ui.widgets import LaneStrip  # noqa: E402

APP = Path(__file__).resolve().parents[1]
SCRIPT = (APP.parent / "archive" / "Webler EEG past program"
          / "SRT_Sequence_learning_Final_v2.py")
FRAME = 1 / 60


def _script_constants() -> dict:
    """Every module-level NAME = literal in the lab's script."""
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return out


def _engine(root: Path, source=None, screens: bool = True, **srt):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = str(root)
    cfg.data["session"]["prefs_file"] = str(root / "prefs.json")
    cfg.data["session"]["participant"] = "P09"
    cfg.data["session"]["age"] = "30"
    cfg.data["report"] = {"enabled": False}
    cfg.data["srt"]["setups_file"] = str(root / "srt_setups.json")
    cfg.data["srt"]["seed"] = 11
    cfg.data["srt"].update(srt)
    eng = GameEngine(cfg, source or KeyboardOnlySource())
    if screens:
        eng._screens = eng._build_screens()
    else:
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock(),
                        "mode_select": MagicMock()}
    return eng


def _use(root: Path, group="constant", isi=500, seq=ss.LAB_SEQUENCE):
    store = ss.SetupStore(root / "srt_setups.json")
    assert not store.set_current(ss.SRTSetup("test", group, isi, seq))


class Sim:
    """A 60 Hz frame loop around the mode: each frame the update runs
    1 ms after the last flip, then the frame flips, then the markers
    armed for it go out, as in GameEngine.run."""

    KEYS = (pygame.K_j, pygame.K_k, pygame.K_l, pygame.K_SEMICOLON)

    def __init__(self, eng):
        self.eng = eng
        self.mode = eng.mode
        self.t = 1000.0
        self.mode._clock = lambda: self.t
        eng.frame_period_s = FRAME
        eng.last_flip_t = self.t
        self.sent: list[tuple[int, float]] = []
        eng._eeg_send = (lambda code, lane=None, t_event=None:
                         self.sent.append((code, t_event)))
        self.flash_flips: dict[tuple, list[float]] = {}
        self.fb_flips: list[tuple[str, float]] = []

    def key(self, k, at: float | None = None):
        keep = self.t
        if at is not None:
            self.t = at
        self.mode.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": k, "mod": 0, "unicode": "",
                             "scancode": 0}))
        self.t = keep

    def frame(self):
        self.t = self.eng.last_flip_t + 0.001
        self.mode.update(FRAME)
        flip = self.eng.last_flip_t + FRAME
        if self.mode.flash_square is not None and self.mode.trial:
            key = (self.mode.step_i, self.mode.trial.index)
            self.flash_flips.setdefault(key, []).append(flip)
        if self.mode.feedback_now:
            self.fb_flips.append((self.mode.feedback_now[0], flip))
        self.eng.last_flip_t = flip
        self.eng._flush_eeg_stim(flip)

    def run(self, respond, max_frames=400000):
        """respond(sim, trial) -> None or (rt_s, square) for the press
        to make on that trial."""
        planned: dict[tuple, tuple] = {}
        n = 0
        while not self.mode.done and n < max_frames:
            n += 1
            step = self.mode.step
            if step is not None and step.kind == "message" and n % 6 == 0:
                self.key(pygame.K_SPACE)
            elif step is not None and step.kind == "recall":
                if n % 12 == 0:
                    if len(self.mode.recalled) < len(self.mode.seq):
                        sq = self.mode.seq[len(self.mode.recalled)]
                        self.key(self.KEYS[sq - 1])
                    else:
                        self.key(pygame.K_RETURN)
            elif step is not None and step.kind == "block":
                tr = self.mode.trial
                if tr is not None:
                    k = (self.mode.step_i, tr.index)
                    if k not in planned:
                        planned[k] = respond(self, tr)
                    plan = planned[k]
                    if plan is not None and not isinstance(plan, str):
                        rt, sq = plan
                        at = tr.flash_due + rt
                        if self.t + FRAME > at >= self.t - FRAME and (
                                rt < 0 or tr.onset is not None):
                            self.key(self.KEYS[sq - 1],
                                     at=min(at, self.t))
                            planned[k] = "done"
            self.frame()
        return n


def _fast_cfg():
    """A short protocol with the lab's timing: 8 random trials either
    side, 2 learning blocks of 2 passes."""
    return {"random_trials": 8, "learning_blocks": 2, "learning_reps": 2}


class TheScriptsConstantsAreTheDefaults(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise unittest.SkipTest("the lab's script is not in this tree")
        cls.c = _script_constants()
        from finger_rehab.config import Config
        cls.cfg = Config.load()

    def test_timing(self):
        g = self.cfg.get
        self.assertEqual(g("srt.flash_ms"), self.c["FLASH_MS"])
        self.assertEqual(g("srt.deadline_ms"), self.c["DEADLINE_MS"])
        self.assertEqual(g("srt.anticipation_ms"), self.c["ANTICIPATION_MS"])
        self.assertEqual(g("srt.miss_pause_ms"), self.c["MISS_PAUSE_MS"])
        self.assertEqual(g("srt.feedback_ms"), self.c["FEEDBACK_MS"])
        self.assertEqual(g("srt.random_isi_ms"), self.c["CONSTANT_ISI_MS"])
        self.assertEqual(ss.DEFAULT_SETUP.isi_ms, self.c["CONSTANT_ISI_MS"])

    def test_counts(self):
        g = self.cfg.get
        self.assertEqual(g("srt.random_trials"), self.c["RANDOM_TRIALS"])
        self.assertEqual(g("srt.learning_blocks"), self.c["LEARNING_BLOCKS"])
        self.assertEqual(g("srt.learning_reps"), self.c["LEARNING_REPS"])

    def test_sequence_and_letters(self):
        self.assertEqual(tuple(ss.LETTERS), tuple(self.c["LANES"]))
        seq = tuple(self.c["LANES"].index(k) + 1
                    for k in self.c["FIXED_SEQUENCE"])
        self.assertEqual(ss.LAB_SEQUENCE, seq)
        self.assertEqual(ss.cyclical_pattern(500, 10),
                         list(self.c["CYCLICAL_ISI"]))

    def test_marker(self):
        # The squares' size and place are the app's now (AppLook below);
        # the byte that marks a flash is still the script's.
        self.assertEqual(self.cfg.get("srt.stim_code"),
                         self.c["MARKER_FLASH_ONSET"])

    def test_the_tones_are_the_labs_files(self):
        src = SCRIPT.parent / "sounds"
        for name in self.cfg.get("srt.tone_files"):
            ours = APP / self.cfg.get("srt.tone_dir") / name
            self.assertEqual(ours.read_bytes(), (src / name).read_bytes(),
                             name)


class SetupRules(unittest.TestCase):

    def test_random_chunks_average_the_interval(self):
        rng = random.Random(3)
        for isi in (200, 300, 500, 750):
            for n in (4, 7, 10, 13, 16):
                chunk = ss.random_chunk(isi, n, rng)
                self.assertEqual(len(chunk), n)
                self.assertAlmostEqual(sum(chunk) / n, isi, delta=1.0)
        chunk = ss.random_chunk(500, 10, rng)
        self.assertEqual(Counter(chunk), {250: 3, 500: 4, 750: 3})

    def test_isi_lists(self):
        rng = random.Random(1)
        self.assertEqual(ss.isi_list("constant", 400, 5, 10, rng),
                         [400] * 5)
        cyc = ss.isi_list("cyclical", 500, 100, 10, rng)
        self.assertEqual(cyc[:10], ss.cyclical_pattern(500, 10))
        self.assertEqual(cyc[90:], cyc[:10])
        rnd = ss.isi_list("random", 500, 100, 10, rng)
        for j in range(10):
            self.assertEqual(Counter(rnd[10 * j:10 * j + 10]),
                             {250: 3, 500: 4, 750: 3})
        self.assertNotEqual(rnd[:10], rnd[10:20])

    def test_cyclical_for_other_lengths(self):
        self.assertEqual(ss.cyclical_pattern(300, 8),
                         [150, 300, 450, 150, 300, 450, 300, 300])
        self.assertEqual(ss.cyclical_pattern(500, 12),
                         [250, 500, 750] * 4)

    def test_random_blocks(self):
        for seed in range(20):
            got = ss.random_targets(48, random.Random(seed))
            self.assertEqual(Counter(got), {1: 12, 2: 12, 3: 12, 4: 12})
            self.assertTrue(all(a != b for a, b in zip(got, got[1:])))
        self.assertEqual(ss.random_targets(48, random.Random(5)),
                         ss.random_targets(48, random.Random(5)))
        odd = ss.random_targets(10, random.Random(2))
        self.assertEqual(sorted(Counter(odd).values()), [2, 2, 3, 3])

    def test_sequence_checks(self):
        self.assertEqual(ss.sequence_problem(ss.LAB_SEQUENCE), "")
        self.assertIn("missing 4", ss.sequence_problem((1, 2, 3, 1, 2, 3)))
        self.assertIn("items 2 and 3",
                      ss.sequence_problem((1, 2, 2, 3, 4, 3)))
        self.assertIn("last and the first",
                      ss.sequence_problem((1, 2, 3, 4, 2, 1)))
        self.assertIn("4 to 16", ss.sequence_problem((1, 2, 3)))
        self.assertIn("4 to 16", ss.sequence_problem((1, 2, 3, 4) * 5))
        self.assertIn("1 to 4", ss.sequence_problem((1, 2, 5, 4)))

    def test_parsing(self):
        for text in ("1321432413", "1-3-2-1-4-3-2-4-1-3",
                     "v n b v m n b m v n", "VNBVMNBMVN", "1, 3 2,1 4 3 2 4 1 3"):
            seq, why = ss.parse_sequence(text)
            self.assertEqual(seq, ss.LAB_SEQUENCE, (text, why))
        self.assertIsNone(ss.parse_sequence("")[0])
        self.assertIn("'x'", ss.parse_sequence("12x4")[1])
        self.assertIsNone(ss.parse_sequence("1234 1234 1234 1234 1")[0])

    def test_the_lab_setup_is_about_a_quarter_hour(self):
        mins = ss.estimate_minutes(ss.DEFAULT_SETUP, ss.protocol_counts(None))
        self.assertTrue(14.0 <= mins <= 17.0, mins)


class RecallScoring(unittest.TestCase):
    """The script scores recall position by position from position 1,
    so a right order started mid-cycle scores near zero. The triplet
    share and the longest run do not care where the recall started."""

    def test_a_perfect_recall(self):
        sc = ss.recall_scores(ss.LAB_SEQUENCE, ss.LAB_SEQUENCE)
        self.assertEqual(sc, {"positional": 10, "triplet": 1.0,
                              "longest_run": 10})

    def test_the_right_order_started_mid_cycle(self):
        shifted = ss.LAB_SEQUENCE[3:] + ss.LAB_SEQUENCE[:3]
        sc = ss.recall_scores(shifted, ss.LAB_SEQUENCE)
        self.assertLessEqual(sc["positional"], 3)
        self.assertEqual(sc["triplet"], 1.0)
        self.assertEqual(sc["longest_run"], 10)

    def test_a_guess(self):
        sc = ss.recall_scores((1, 2, 3, 4, 1, 2, 3, 4, 1, 2),
                              ss.LAB_SEQUENCE)
        self.assertLess(sc["triplet"], 0.5)
        self.assertLessEqual(sc["longest_run"], 3)

    def test_the_notebook_scores_the_same(self):
        from tests.test_analysis_logic_gaps import _load_notebook
        nb = _load_notebook("srt_recall")
        rng = random.Random(9)
        for _ in range(200):
            rec = [rng.randint(1, 4) for _ in range(10)]
            self.assertEqual(nb.srt_recall_scores(rec, ss.LAB_SEQUENCE),
                             ss.recall_scores(rec, ss.LAB_SEQUENCE))


class TheSetupsFile(unittest.TestCase):

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.path = Path(self.td.name) / "cfg" / "srt_setups.json"

    def tearDown(self):
        self.td.cleanup()

    def test_starts_on_the_lab_setup_and_lists_the_three_groups(self):
        store = ss.SetupStore(self.path)
        self.assertEqual(store.current, ss.DEFAULT_SETUP)
        self.assertEqual([s.group for s in store.all()],
                         ["constant", "cyclical", "random"])
        self.assertFalse(self.path.exists())

    def test_everything_survives_a_reload(self):
        store = ss.SetupStore(self.path)
        self.assertEqual(store.save_as(
            "Cyclical 300", ss.SRTSetup("x", "cyclical", 300,
                                        (1, 2, 3, 4, 3, 2))), "")
        again = ss.SetupStore(self.path)
        self.assertEqual(again.current.name, "Cyclical 300")
        self.assertEqual(again.current.isi_ms, 300)
        self.assertEqual(again.current.sequence, (1, 2, 3, 4, 3, 2))
        self.assertEqual([s.name for s in again.saved], ["Cyclical 300"])

    def test_same_name_replaces_and_delete_removes(self):
        store = ss.SetupStore(self.path)
        store.save_as("A", ss.SRTSetup("A", "random", 400))
        store.save_as("a", ss.SRTSetup("a", "random", 600))
        self.assertEqual(len(store.saved), 1)
        self.assertEqual(store.saved[0].isi_ms, 600)
        self.assertEqual(store.delete("a"), "")
        self.assertEqual(ss.SetupStore(self.path).saved, [])

    def test_the_lab_setups_stay(self):
        store = ss.SetupStore(self.path)
        self.assertTrue(store.delete("Lab constant 500"))
        self.assertTrue(store.save_as("lab random 500",
                                      ss.SRTSetup("x", "random", 300)))
        self.assertEqual(len(store.all()), 3)

    def test_bad_setups_are_refused(self):
        store = ss.SetupStore(self.path)
        self.assertIn("Interval", store.set_current(
            ss.SRTSetup("x", "constant", 50)))
        self.assertTrue(store.set_current(
            ss.SRTSetup("x", "constant", 500, (1, 1, 2, 3, 4))))
        self.assertTrue(store.set_current(ss.SRTSetup("x", "wavy", 500)))
        self.assertEqual(store.current, ss.DEFAULT_SETUP)

    def test_a_broken_file_opens_on_the_lab_setup(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json")
        self.assertEqual(ss.SetupStore(self.path).current, ss.DEFAULT_SETUP)
        self.path.write_text(json.dumps({"current": {
            "name": "x", "group": "constant", "isi_ms": 500,
            "sequence": [1, 2, 2, 3]}, "saved": [{"nope": 1}]}))
        store = ss.SetupStore(self.path)
        self.assertEqual(store.current, ss.DEFAULT_SETUP)
        self.assertEqual(store.saved, [])


class AWholeSessionFrameByFrame(unittest.TestCase):
    """The lab protocol shortened to 8 + 2 x 2 passes + 8, played on a
    60 Hz flip clock by a participant who answers every trial 300 to
    450 ms after the flash, one in twenty with the wrong finger."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.td = tempfile.TemporaryDirectory()
        root = Path(cls.td.name)
        _use(root, "cyclical", 500)
        eng = _engine(root, **_fast_cfg())
        eng.set_hand_mode("right")
        eng.begin_srt_block()
        cls.eng = eng
        cls.sim = Sim(eng)
        rng = random.Random(4)

        def respond(sim, tr):
            sq = tr.square if rng.random() > 0.05 else tr.square % 4 + 1
            return (0.30 + rng.random() * 0.15, sq)
        cls.frames = cls.sim.run(respond)
        cls.root = Path(eng.last_session_root)
        cls.files = {p.name: p for p in cls.root.iterdir()}
        perf = [p for n, p in cls.files.items() if n.startswith("SRT_P09_")]
        cls.rows = list(csv.DictReader(perf[0].open(encoding="utf-8")))
        cls.meta = json.loads((cls.root / "metadata.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()
        pygame.quit()

    def test_it_ends_on_results_with_every_trial(self):
        self.assertTrue(self.sim.mode.done)
        self.assertIs(self.eng.screen_obj, self.eng._screens["results"])
        self.assertEqual(len(self.rows), 8 + 2 * 20 + 8)
        blocks = Counter((r["phase"], r["block"]) for r in self.rows)
        self.assertEqual(blocks, {("practice", "1"): 8,
                                  ("learning", "1"): 20,
                                  ("learning", "2"): 20,
                                  ("posttest", "1"): 8})

    def test_the_files_carry_the_scripts_names_and_columns(self):
        names = sorted(self.files)
        self.assertTrue(any(n.startswith("SRT_P09_cyclical_") for n in names))
        self.assertTrue(any(n.startswith("SRT_SEQUENCE_P09_") for n in names))
        self.assertTrue(any(n.startswith("SRT_RECALL_P09_cyclical_")
                            for n in names))
        from finger_rehab.game.modes.srt import PERF_COLUMNS
        self.assertEqual(list(self.rows[0])[:len(PERF_COLUMNS)],
                         PERF_COLUMNS)
        if SCRIPT.is_file():
            text = SCRIPT.read_text(encoding="utf-8")
            for col in PERF_COLUMNS:
                self.assertIn(f"'{col}':", text, col)
        seq = [p for n, p in self.files.items() if "SEQUENCE" in n][0]
        seq_rows = list(csv.reader(seq.open(encoding="utf-8")))
        self.assertEqual(seq_rows[0], ["participant", "seq_position",
                                       "finger", "cyclical_isi_after_ms"])
        self.assertEqual([r[2] for r in seq_rows[1:]],
                         list("vnbvmnbmvn"))
        rec = [p for n, p in self.files.items() if "RECALL" in n][0]
        rec_rows = list(csv.DictReader(rec.open(encoding="utf-8")))
        self.assertEqual(len(rec_rows), 10)
        self.assertTrue(all(r["correct"] == "1" for r in rec_rows))

    def test_rows_use_the_scripts_words(self):
        r = self.rows[0]
        self.assertEqual(r["target_lane"], "vbnm"[int(
            self.sim.mode.steps[2].targets[0]) - 1])
        self.assertIn(r["response_key"], "vbnm")
        self.assertEqual(r["isi_before_ms"], "")
        self.assertEqual(r["monitor_hz"], "60")
        self.assertEqual(Counter(x["accuracy"] for x in self.rows).keys()
                         - {"correct", "incorrect"}, set())
        pos = [int(x["seq_position"]) for x in self.rows
               if x["phase"] == "learning" and x["block"] == "1"]
        self.assertEqual(pos, list(range(1, 11)) * 2)

    def test_each_flash_is_six_frames(self):
        lens = Counter(len(v) for v in self.sim.flash_flips.values())
        self.assertEqual(lens, {6: len(self.rows)})

    def test_the_first_trial_waits_a_second(self):
        for r in self.rows:
            if r["trial"] == "1":
                self.assertAlmostEqual(float(r["rsi_ms"]), 1000.0, delta=0.5)

    def test_the_interval_runs_one_frame_past_its_nominal_length(self):
        # The script draws the interval's frames after the frame that
        # ends a trial, so the flash lands one frame after the interval.
        for r in self.rows:
            if r["phase"] == "learning" and r["isi_before_ms"]:
                self.assertAlmostEqual(
                    float(r["rsi_ms"]) - float(r["isi_before_ms"]),
                    FRAME * 1000, delta=0.5)

    def test_practice_adds_its_word_for_twelve_frames(self):
        prac = [r for r in self.rows if r["phase"] == "practice"]
        for r in prac[1:]:
            self.assertAlmostEqual(
                float(r["rsi_ms"]) - float(r["isi_before_ms"]),
                200 + FRAME * 1000, delta=0.5)
        words = Counter(w for w, _t in self.sim.fb_flips)
        self.assertEqual(sum(words.values()), 12 * 8)
        self.assertLessEqual(set(words), {"Correct", "Incorrect"})

    def test_the_cyclical_intervals_follow_the_position(self):
        blk = [r for r in self.rows if r["phase"] == "learning"
               and r["block"] == "2"]
        got = [int(r["isi_before_ms"]) for r in blk[1:]]
        pattern = ss.cyclical_pattern(500, 10)
        self.assertEqual(got, [pattern[i % 10] for i in range(19)])
        rand = {r["isi_before_ms"] for r in self.rows
                if r["phase"] != "learning" and r["isi_before_ms"]}
        self.assertEqual(rand, {"500"})

    def test_one_byte_30_per_flash_on_its_flip(self):
        thirty = [t for c, t in self.sim.sent if c == 30]
        self.assertEqual(len(thirty), len(self.rows))
        onsets = sorted(v[0] for v in self.sim.flash_flips.values())
        self.assertEqual(len(onsets), len(thirty))
        for a, b in zip(sorted(thirty), onsets):
            self.assertLess(abs(a - b), 0.002)
        self.assertEqual({c for c, _t in self.sim.sent} - {30}, {233})

    def test_the_summary(self):
        sr = self.meta["block_summary"]["srt"]
        self.assertEqual(sr["group"], "cyclical")
        self.assertEqual(sr["n_trials"], len(self.rows))
        self.assertEqual(sr["recall"]["n_correct"], 10)
        self.assertEqual(sr["recall"]["triplet"], 1.0)
        self.assertEqual(sr["recall"]["longest_run"], 10)
        self.assertEqual(len(sr["learning"]), 2)
        for key in ("sequence_effect_ms", "sequence_effect_matched_ms",
                    "sequence_effect_prop", "learning_speedup_ms",
                    "accuracy_cost", "accuracy"):
            self.assertIn(key, sr)
        self.assertIsNotNone(sr["sequence_effect_matched_ms"])
        rows = list(csv.DictReader((self.root / "trials.csv").open()))
        self.assertEqual(len(rows), len(self.rows))
        self.assertEqual({r["block"] for r in rows}, {"srt"})
        self.assertTrue(rows[0]["stimulus"].startswith("srt;practice;b=1;"))


class OneTrialAtATime(unittest.TestCase):
    """The script's trial rules, one situation each."""

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        _use(root)
        self.eng = _engine(root, **_fast_cfg())
        self.eng.set_hand_mode("right")
        self.eng.begin_srt_block()
        self.sim = Sim(self.eng)
        self.mode = self.eng.mode
        # Straight to the practice block.
        self.sim.key(pygame.K_SPACE)
        self.sim.frame()
        self.sim.key(pygame.K_SPACE)
        self.sim.frame()
        self.assertEqual(self.mode.step.kind, "block")

    def tearDown(self):
        self.eng._abandon_if_in_block()
        self.td.cleanup()
        pygame.quit()

    def _to_flash(self):
        tr = self.mode.trial
        while tr.onset is None:
            self.sim.frame()
        return tr

    def test_a_press_just_before_the_flash_is_an_anticipation(self):
        tr = self.mode.trial
        while self.sim.eng.last_flip_t + FRAME < tr.flash_due - 0.06:
            self.sim.frame()
        self.sim.key(Sim.KEYS[tr.square - 1], at=tr.flash_due - 0.05)
        while self.mode.perf_rows == []:
            self.sim.frame()
        row = self.mode.perf_rows[0]
        self.assertEqual(row["accuracy"], "anticipatory_correct")
        self.assertAlmostEqual(row["rt_ms"], -50.0, delta=1.0)

    def test_a_press_well_before_the_flash_is_thrown_away(self):
        tr = self.mode.trial
        while self.sim.eng.last_flip_t + FRAME < tr.flash_due - 0.3:
            self.sim.frame()
        self.sim.key(Sim.KEYS[tr.square - 1], at=tr.flash_due - 0.2)
        self._to_flash()
        self.assertEqual(self.mode.perf_rows, [])
        self.sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 0.35)
        self.sim.frame()
        self.assertEqual(self.mode.perf_rows[0]["accuracy"], "correct")
        self.assertAlmostEqual(self.mode.perf_rows[0]["rt_ms"], 350.0,
                               delta=0.5)

    def test_wrong_finger_and_only_the_first_press(self):
        tr = self._to_flash()
        wrong = tr.square % 4 + 1
        self.sim.key(Sim.KEYS[wrong - 1], at=tr.onset + 0.3)
        self.sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 0.31)
        self.sim.frame()
        self.assertEqual(len(self.mode.perf_rows), 1)
        row = self.mode.perf_rows[0]
        self.assertEqual(row["accuracy"], "incorrect")
        self.assertEqual(row["response_key"], "vbnm"[wrong - 1])

    def test_no_press_is_a_miss_after_two_point_six_seconds(self):
        tr = self._to_flash()
        onset = tr.onset
        while not self.mode.perf_rows:
            self.sim.frame()
        row = self.mode.perf_rows[0]
        self.assertEqual(row["accuracy"], "miss")
        self.assertEqual(row["response_key"], "none")
        self.assertEqual(row["rt_ms"], "")
        end = self.eng.last_flip_t
        self.assertAlmostEqual(end - onset, 2.6, delta=FRAME / 2)
        nxt = self.mode.trial
        # Miss pause 200, practice word 200, interval 500, one frame.
        self.assertAlmostEqual(nxt.flash_due - end, 0.9 + FRAME, delta=1e-6)
        seen = []
        while nxt.onset is None:
            self.sim.frame()
            if self.mode.feedback_now:
                seen.append(self.eng.last_flip_t)
        self.assertEqual(len(seen), 12)
        self.assertAlmostEqual(seen[0] - end, 0.2 + FRAME, delta=1e-6)

    def test_a_press_after_the_deadline_is_too_late(self):
        tr = self._to_flash()
        self.sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 2.7)
        while not self.mode.perf_rows:
            self.sim.frame()
        self.assertEqual(self.mode.perf_rows[0]["accuracy"], "miss")

    def test_pad_presses_carry_their_own_time(self):
        from finger_rehab.hardware.fsr_detector import PressEvent
        tr = self._to_flash()
        self.mode.queue_press(PressEvent(lane=tr.square - 1,
                                         t_perf=tr.onset + 0.2718,
                                         value=900, baseline=100.0))
        self.sim.frame()
        row = self.mode.perf_rows[0]
        self.assertEqual(row["input"], "pad")
        self.assertAlmostEqual(row["rt_ms"], 271.8, places=1)

    def test_a_pause_does_not_eat_the_interval(self):
        tr = self.mode.trial
        due = tr.flash_due
        self.mode.on_resume(5.0)
        self.assertAlmostEqual(self.mode.trial.flash_due, due + 5.0)


class TheLabsRtRules(unittest.TestCase):
    """RT measures leave out each block's first trial and anything over
    1000 ms, as the lab's own SRT papers did; the trials still count
    for accuracy."""

    def test_first_trials_and_slow_ones_are_left_out(self):
        from finger_rehab.game.modes.srt import SRTMode
        m = SRTMode.__new__(SRTMode)
        m.perf_rows = []
        for trial, rt, acc, isi in ((1, 300.0, "correct", ""),
                                    (2, 400.0, "correct", 500),
                                    (3, 1200.0, "correct", 250),
                                    (4, 350.0, "incorrect", 750),
                                    (5, 450.0, "correct", 750)):
            m.perf_rows.append({"phase": "learning", "block": 1,
                                "trial": trial, "rt_ms": rt,
                                "accuracy": acc, "isi_before_ms": isi})
        self.assertEqual(m._rts("learning", 1), [400.0, 450.0])
        self.assertEqual(m._rts("learning", 1, isi=500), [400.0])


class RecallAndMessages(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        _use(root)
        self.eng = _engine(root, **_fast_cfg())
        self.eng.set_hand_mode("right")
        self.eng.begin_srt_block()
        self.sim = Sim(self.eng)
        self.mode = self.eng.mode

    def tearDown(self):
        if self.eng.session_paths is not None:
            self.eng._abandon_if_in_block()
        self.td.cleanup()
        pygame.quit()

    def test_messages_wait_for_space_and_drop_presses(self):
        for _ in range(30):
            self.sim.key(pygame.K_j)
            self.sim.frame()
        self.assertEqual(self.mode.step.key, "welcome")
        self.sim.key(pygame.K_RETURN)
        self.sim.frame()
        self.assertEqual(self.mode.step.key, "welcome")
        self.sim.key(pygame.K_SPACE)
        self.sim.frame()
        self.assertEqual(self.mode.step.key, "practice")
        self.assertEqual(len(self.mode._presses), 0)

    def test_the_message_words_are_the_scripts(self):
        text = self.mode.message_text(self.mode.steps[0])
        self.assertTrue(text.startswith("Welcome to the experiment."))
        self.assertIn("(J, K, L, or ;)", text)
        self.assertNotIn("V, B", text)
        blocks = [s for s in self.mode.steps if s.key == "block"]
        self.assertEqual(self.mode.message_text(blocks[1]),
                         "Block 2 of 2\n\nPress SPACE when ready.")

    def test_recall_entry(self):
        m = self.mode
        sim = self.sim
        m.step_i = next(i for i, s in enumerate(m.steps)
                        if s.kind == "recall")

        def later(dt):
            sim.eng.last_flip_t += dt
            sim.t = sim.eng.last_flip_t + 0.001

        def press(k, after=0.2):
            later(after)
            sim.key(k)
            sim.frame()
        press(Sim.KEYS[0], after=0.0)
        self.assertEqual(m.recalled, [1])
        self.assertEqual(m.select_square, 1)
        # Inside the 150 ms yellow flash: dropped, as the script drops it.
        press(Sim.KEYS[2], after=0.05)
        self.assertEqual(m.recalled, [1])
        press(Sim.KEYS[2])
        self.assertEqual(m.recalled, [1, 3])
        later(0.2)
        sim.key(pygame.K_BACKSPACE)
        self.assertEqual(m.recalled, [1])
        sim.key(pygame.K_RETURN)
        self.assertFalse(m.recall_done)
        for sq in ss.LAB_SEQUENCE[1:]:
            press(Sim.KEYS[sq - 1])
        self.assertIn("Items entered: 10 / 10", m.recall_progress())
        later(0.2)
        sim.key(pygame.K_SPACE)
        self.assertTrue(m.recall_done)

    def test_an_abandoned_session_keeps_what_it_has(self):
        self.eng._abandon_if_in_block()
        root = Path(self.eng.last_session_root)
        names = [p.name for p in root.iterdir()]
        self.assertTrue(any(n.startswith("SRT_P09_constant_")
                            for n in names))
        self.assertFalse(any("RECALL" in n for n in names))


class HandsLabelsAndMarkers(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        _use(Path(self.td.name))

    def tearDown(self):
        self.td.cleanup()
        pygame.quit()

    def _mode(self, hand, **srt):
        eng = _engine(Path(self.td.name), **srt)
        eng.set_hand_mode(hand)
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        return eng, eng.mode

    def test_the_left_hand_is_mirrored(self):
        _eng, m = self._mode("left")
        self.assertEqual([m.lane_to_square(i) for i in range(4)],
                         [4, 3, 2, 1])
        self.assertEqual(m.square_to_lane(1), 3)

    def test_both_hands_play_the_labs_two_hand_layout(self):
        # The session's hands decide (28 September 2026): both hands at
        # login is the lab's two-hand layout, with nothing to ask.
        _eng, m = self._mode("both")
        self.assertTrue(m.two_hands)
        self.assertEqual([m.lane_to_square(i) for i in range(8)],
                         [3, 4, None, None, 2, 1, None, None])

    def test_labels(self):
        eng, m = self._mode("right")
        self.assertEqual(m.labels(), ["J", "K", "L", ";"])
        eng.source = MagicMock(provides_samples=True)
        self.assertEqual(m.labels(), ["Index", "Middle", "Ring", "Little"])
        eng.hand_mode = "left"
        self.assertEqual(m.labels(), ["Little", "Ring", "Middle", "Index"])
        self.assertIn("finger", m.instruction())

    def test_only_the_apps_own_keys_answer(self):
        # The keys every game uses, J K L ; and F D S A, and not the
        # lab script's V B N M as well (Basil, 29 September 2026).
        keys = {"right": ((pygame.K_j, pygame.K_k, pygame.K_l,
                           pygame.K_SEMICOLON), ["J", "K", "L", ";"]),
                "left": ((pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f),
                         ["A", "S", "D", "F"]),
                "both": ((pygame.K_d, pygame.K_f, pygame.K_j, pygame.K_k),
                         ["D", "F", "J", "K"])}
        for hand, (ks, names) in keys.items():
            with self.subTest(hand=hand):
                _eng, m = self._mode(hand)
                for i, k in enumerate(ks):
                    self.assertEqual(m.lane_to_square(m._key_lane(k)),
                                     i + 1)
                for k in (pygame.K_v, pygame.K_b, pygame.K_n, pygame.K_m):
                    self.assertIsNone(m._key_lane(k))
                self.assertEqual(m.labels(), names)
                self.assertNotIn("V, B", m.recall_text())

    def test_response_bytes_only_when_asked(self):
        eng, m = self._mode("right", response_markers=True)
        sim = Sim(eng)
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        tr = m.trial
        while tr.onset is None:
            sim.frame()
        sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 0.3)
        sim.frame()
        codes = [c for c, _t in sim.sent]
        self.assertIn(100 + tr.square - 1, codes)

    def test_the_block_bytes(self):
        from finger_rehab.hardware import eeg_trigger as et
        self.assertEqual(et.MODE_IDS["srt"], 13)
        self.assertEqual(et.block_code("srt", "start"), 213)
        self.assertEqual(et.block_code("srt", "end"), 233)
        self.assertNotIn(13, et.RETIRED_MODE_IDS.values())


class TwoHands(unittest.TestCase):
    """The lab's own studies ran the task on two hands: V and B under
    the left middle and index fingers, N and M under the right index
    and middle. Both hands picked at login asks for that; a saved setup
    no longer does (28 September 2026)."""

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()
        pygame.quit()

    def _save(self, hands):
        store = ss.SetupStore(self.root / "srt_setups.json")
        assert not store.set_current(
            ss.SRTSetup("saved", "constant", 500, ss.LAB_SEQUENCE, hands))

    def _start(self, hand="both"):
        eng = _engine(self.root)
        eng.set_hand_mode(hand)
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        return eng, eng.mode

    def test_the_block_runs_on_both_hands_with_the_labs_fingers(self):
        eng, m = self._start()
        self.assertEqual(eng.hand_mode, "both")
        self.assertTrue(m.two_hands)
        self.assertEqual([m.square_to_lane(q) for q in (1, 2, 3, 4)],
                         [5, 4, 0, 1])
        self.assertEqual([m.lane_to_square(ln) for ln in range(8)],
                         [3, 4, None, None, 2, 1, None, None])
        eng.source = MagicMock(provides_samples=True)
        self.assertEqual(m.labels(),
                         ["L middle", "L index", "R index", "R middle"])

    def test_the_two_hand_keys_answer(self):
        _eng, m = self._start()
        for key, square in ((pygame.K_d, 1), (pygame.K_f, 2),
                            (pygame.K_j, 3), (pygame.K_k, 4)):
            self.assertEqual(m.lane_to_square(m._key_lane(key)), square)

    def test_rows_say_which_hand_answered(self):
        eng, m = self._start()
        sim = Sim(eng)
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        tr = m.trial
        while tr.onset is None:
            sim.frame()
        key = {1: pygame.K_d, 2: pygame.K_f, 3: pygame.K_j,
               4: pygame.K_k}[tr.square]
        sim.key(key, at=tr.onset + 0.3)
        sim.frame()
        row = m.perf_rows[0]
        self.assertEqual(row["accuracy"], "correct")
        self.assertEqual(row["hand"], "both")
        self.assertIn(row["response_finger"], ("L1", "L2", "R1", "R2"))

    def test_a_saved_two_hand_setup_no_longer_changes_the_hand(self):
        self._save("two")
        eng, m = self._start("right")
        self.assertEqual(eng.hand_mode, "right")
        self.assertFalse(m.two_hands)
        self.assertEqual(m.setup.hands, "one")

    def test_both_hands_play_two_hands_whatever_the_file_says(self):
        self._save("one")
        eng, m = self._start("both")
        self.assertTrue(m.two_hands)
        self.assertEqual(m.setup.hands, "two")
        # A file from before the field existed still loads, as one hand.
        self.assertEqual(ss.SRTSetup.from_dict(
            {"name": "old", "group": "random", "isi_ms": 500}).hands, "one")

    def test_play_all_runs_the_srt_on_the_steps_hand(self):
        self._save("two")
        eng = _engine(self.root)
        eng._battery = {"id": "eeg_lab_srt_v2", "preset": "study_battery",
                        "cell": {}, "of": 11, "log": []}
        eng._protocol_current = {"mode": "srt", "hand": "right",
                                 "position": 1, "phase": "pass1"}
        eng.set_hand_mode("right")
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        self.assertEqual(eng.hand_mode, "right")
        self.assertFalse(eng.mode.two_hands)
        self.assertEqual(eng.session.battery.get("position"), 1)


class AppLook(unittest.TestCase):
    """The lab's task drawn in the app's own look (28 September 2026):
    the lane games' finger cards on the theme's page, the target card
    lit for the flash and nothing else changing. Each of these fails on
    the screen that drew the script's black window."""

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        _use(Path(self.td.name))

    def tearDown(self):
        self.td.cleanup()
        pygame.quit()

    def _run(self, hand="right", **srt):
        eng = _engine(Path(self.td.name), **{**_fast_cfg(), **srt})
        eng.set_hand_mode(hand)
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        return eng, eng._screens["srt"], Sim(eng)

    def _to_flash(self, sim):
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        while sim.mode.flash_square is None:
            sim.frame()

    def test_the_cards_are_the_lane_games_cards(self):
        for hand in ("right", "left"):
            eng, sc, _sim = self._run(hand)
            gp = eng._screens["gameplay"]
            gp.rebuild_lanes()
            by_square = {eng.mode.lane_to_square(ls.lane): ls.rect
                         for ls in gp.lanes}
            self.assertEqual(sc.lane_rects(eng.mode),
                             [by_square[s] for s in (1, 2, 3, 4)], hand)
            names = [LaneStrip.FINGER_LABELS[ls.finger]
                     for ls in sc.lanes(eng.mode)]
            want = ["Index", "Middle", "Ring", "Pinky"]
            self.assertEqual(names, want if hand == "right"
                             else list(reversed(want)))

    def test_only_the_target_card_lights_and_nothing_else_moves(self):
        eng, sc, sim = self._run()
        self._to_flash(sim)
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        lit = [i + 1 for i, ls in enumerate(sc.lanes(eng.mode)) if ls.active]
        self.assertEqual(lit, [eng.mode.flash_square])
        for ls in sc.lanes(eng.mode):
            self.assertFalse(ls.show_halos)
            self.assertFalse(ls.show_timing_bar)
            self.assertFalse(ls.is_pressed)
        while eng.mode.flash_square is not None:
            sim.frame()
        sc.draw(surf)
        self.assertEqual([ls for ls in sc.lanes(eng.mode) if ls.active], [])

    def test_waiting_cards_are_grey_and_only_the_cue_has_colour(self):
        # Basil, 28 September 2026: every finger a neutral grey, and a
        # finger's colour only on the card a cue lights.
        eng, sc, sim = self._run()
        self._to_flash(sim)
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        lanes = sc.lanes(eng.mode)
        grey = lanes[0].neutral_colours()[0]
        for ls in lanes:
            self.assertTrue(ls.neutral_idle)
            px = tuple(surf.get_at((ls.rect.centerx,
                                    ls.rect.y + ls.rect.h // 3)))[:3]
            want = (eng.theme.lane_active[ls.finger] if ls.active
                    else grey)
            self.assertEqual(px, want, ls.finger)
        while eng.mode.flash_square is not None:
            sim.frame()
        sc.draw(surf)
        for ls in lanes:
            px = tuple(surf.get_at((ls.rect.centerx,
                                    ls.rect.y + ls.rect.h // 3)))[:3]
            self.assertEqual(px, grey)

    def test_the_page_is_the_theme_not_the_scripts_black(self):
        eng, sc, sim = self._run()
        self._to_flash(sim)
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        self.assertEqual(tuple(surf.get_at((4, 4)))[:3], eng.theme.background)

    def test_a_click_on_a_recall_card_enters_it(self):
        eng, sc, _sim = self._run()
        m = eng.mode
        m.step_i = next(i for i, s in enumerate(m.steps)
                        if s.kind == "recall")
        rect = sc.lane_rects(m, recall=True)[2]
        sc.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rect.center}))
        self.assertEqual(m.recalled, [3])
        # A click off the cards enters nothing.
        m._select = None
        sc.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": (5, 5)}))
        self.assertEqual(m.recalled, [3])

    def test_the_words_name_cards_not_squares(self):
        eng, _sc, _sim = self._run()
        m = eng.mode
        texts = [m.message_text(s) for s in m.steps if s.kind == "message"]
        texts.append(m.instruction())
        for text in texts:
            for word in ("square", "RED", "grey", "red "):
                self.assertNotIn(word, text)
        self.assertIn("lights up", m.instruction())


class EveryHand(unittest.TestCase):
    """The app look on every hand the task can run on: the right hand,
    the left hand (mirrored, little finger leftmost), and both hands,
    the lab's two-hand layout (left middle, left index, right index,
    right middle). The hands are the session's: a two-hand setup saved
    in the file changes nothing. For each: the cards on screen are the
    fingers that answer, a pad press on the lit card's finger scores
    correct, and a click on a recall card enters that card."""

    CASES = {
        # name: (hand at login, saved setup hands, (hand, finger) left
        # to right)
        "right": ("right", "one", [("right", 0), ("right", 1),
                                   ("right", 2), ("right", 3)]),
        "left": ("left", "one", [("left", 3), ("left", 2),
                                 ("left", 1), ("left", 0)]),
        "both hands": ("both", "one", [("left", 1), ("left", 0),
                                       ("right", 0), ("right", 1)]),
        "right, two-hand setup saved": ("right", "two", [
            ("right", 0), ("right", 1), ("right", 2), ("right", 3)]),
    }

    def setUp(self):
        pygame.init()

    def tearDown(self):
        pygame.quit()

    def _run(self, hand, hands):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        store = ss.SetupStore(root / "srt_setups.json")
        assert not store.set_current(ss.SRTSetup(
            "test", "constant", 500, ss.LAB_SEQUENCE, hands))
        eng = _engine(root, **_fast_cfg())
        eng.set_hand_mode(hand)
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        return eng, eng._screens["srt"], Sim(eng)

    def test_the_cards_are_the_fingers_that_answer(self):
        for name, (hand, hands, want) in self.CASES.items():
            with self.subTest(name):
                eng, sc, _sim = self._run(hand, hands)
                m = eng.mode
                got = [(ls.hand, ls.finger) for ls in sc.lanes(m)]
                self.assertEqual(got, want)
                # Each card is the finger its square answers to.
                for square, ls in enumerate(sc.lanes(m), start=1):
                    lane = m.square_to_lane(square)
                    self.assertEqual(m.lane_to_square(lane), square)
                    self.assertEqual(lane % 4, ls.finger)
                    self.assertEqual("left" if (lane >= 4 or (
                        not m.two_hands and eng.hand_mode == "left"))
                        else "right", ls.hand)

    def test_a_pad_press_on_the_lit_finger_is_correct(self):
        from finger_rehab.hardware.fsr_detector import PressEvent
        for name, (hand, hands, _want) in self.CASES.items():
            with self.subTest(name):
                eng, sc, sim = self._run(hand, hands)
                m = eng.mode
                sim.key(pygame.K_SPACE)
                sim.frame()
                sim.key(pygame.K_SPACE)
                sim.frame()
                tr = m.trial
                while tr.onset is None:
                    sim.frame()
                surf = pygame.Surface((1280, 800))
                sc.draw(surf)
                lit = [i + 1 for i, ls in enumerate(sc.lanes(m))
                       if ls.active]
                self.assertEqual(lit, [tr.square])
                lane = m.square_to_lane(tr.square)
                m.queue_press(PressEvent(
                    lane=lane, t_perf=tr.onset + 0.3, value=0,
                    baseline=0.0,
                    hand="left" if lane >= 4 else eng.hand_mode))
                sim.frame()
                self.assertEqual(m.perf_rows[0]["accuracy"], "correct")

    def test_a_recall_click_enters_the_card_clicked(self):
        for name, (hand, hands, _want) in self.CASES.items():
            with self.subTest(name):
                eng, sc, _sim = self._run(hand, hands)
                m = eng.mode
                m.step_i = next(i for i, s in enumerate(m.steps)
                                if s.kind == "recall")
                for square in (1, 4, 2):
                    rect = sc.lane_rects(m, recall=True)[square - 1]
                    m._select = None
                    sc.handle_event(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN,
                        {"button": 1, "pos": rect.center}))
                self.assertEqual(m.recalled, [1, 4, 2])

    def test_the_practice_word_is_drawn_in_the_pages_colours(self):
        eng, sc, sim = self._run("right", "one")
        m = eng.mode
        seen = []
        real_font = sc.layout.font

        class _SpyFont:
            def __init__(self, font):
                self._font = font

            def render(self, text, aa, colour, *args, **kwargs):
                seen.append((str(text), tuple(colour)[:3]))
                return self._font.render(text, aa, colour, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._font, name)
        sc.layout.font = lambda pt, bold=False: _SpyFont(real_font(pt, bold))
        self.addCleanup(setattr, sc.layout, "font", real_font)
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        tr = m.trial
        while tr.onset is None:
            sim.frame()
        sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 0.3)
        for _ in range(60):
            sim.frame()
            if m.feedback_now:
                break
        self.assertEqual(m.feedback_now[0], "Correct")
        sc.draw(pygame.Surface((1280, 800)))
        colours = [c for text, c in seen if text == "Correct"]
        self.assertEqual(colours, [eng.theme.success])


class TheCardAndTheSetupScreen(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        self.root = Path(self.td.name)
        self.eng = _engine(self.root)
        self.eng.show_title()
        self.eng.begin_session("P09", "30", dominant_hand="right")
        self.eng.choose_session_hand("right")

    def tearDown(self):
        if self.eng.session_paths is not None:
            self.eng._abandon_if_in_block()
        self.td.cleanup()
        pygame.quit()

    def test_the_reaction_card_opens_the_setup(self):
        from finger_rehab.ui.screens import ModeSelectScreen, mode_title
        keys = [k for k, _t, _d in ModeSelectScreen.MODES]
        self.assertEqual(keys[0], "srt")
        self.assertEqual(mode_title("srt"), "Reaction")
        hub = self.eng._screens["mode_select"]
        self.eng.screen_obj = hub
        hub._pick("srt")
        self.assertIs(self.eng.screen_obj, self.eng._screens["srt_setup"])
        self.assertFalse(self.eng.block_is_running())

    def test_the_group_is_kept_and_start_runs_it(self):
        self.eng.show_srt_setup()
        sc = self.eng.screen_obj
        sc.group_seg.set("random")
        sc.handle_event(pygame.event.Event(pygame.MOUSEMOTION,
                                           {"pos": (0, 0), "rel": (0, 0),
                                            "buttons": (0, 0, 0)}))
        sc.music_seg.set("3")
        store = ss.SetupStore(self.root / "srt_setups.json")
        self.assertEqual(store.current.group, "random")
        self.assertEqual(store.current.name, "Lab random 500")
        sc._start()
        self.assertTrue(self.eng.block_is_running())
        self.assertEqual(self.eng.current_block, "srt")
        self.assertEqual(self.eng.mode.setup.group, "random")
        self.assertEqual(self.eng.mode.setup.isi_ms, 500)
        self.assertEqual(self.eng.mode.musical_experience, 3)
        self.assertIs(self.eng.screen_obj, self.eng._screens["srt"])

    def _drawn(self, sc) -> list[str]:
        """Every string the setup screen renders through its layout."""
        seen: list[str] = []
        real_font = sc.layout.font

        class _SpyFont:
            def __init__(self, font):
                self._font = font

            def render(self, text, *args, **kwargs):
                seen.append(str(text))
                return self._font.render(text, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._font, name)
        sc.layout.font = lambda pt, bold=False: _SpyFont(real_font(pt, bold))
        try:
            sc.draw(pygame.Surface((1280, 800)))
        finally:
            sc.layout.font = real_font
        return seen

    def test_one_view_with_only_what_changes_per_person(self):
        # One menu (Basil, 28 September 2026): the timing group, musical
        # experience and START. No More options, no hand question: the
        # hands are the session's and the screen only says which.
        self.eng.show_srt_setup()
        sc = self.eng.screen_obj
        blob = " | ".join(self._drawn(sc))
        for word in ("Timing group", "Musical experience", "START",
                     "Right hand, as picked at login"):
            self.assertIn(word, blob)
        for word in ("More options", "Learning interval", "Saved setups",
                     "Sequence", "Save these settings", "One hand",
                     "Two hands"):
            self.assertNotIn(word, blob)
        self.assertFalse(hasattr(sc, "hands_seg"))

    def test_the_hands_line_is_the_sessions(self):
        self.eng.set_hand_mode("both")
        self.eng.show_srt_setup()
        sc = self.eng.screen_obj
        self.assertEqual(sc.hands, "two")
        self.assertIn("Both hands, as picked at login",
                      " | ".join(self._drawn(sc)))

    def test_the_sequence_is_never_drawn(self):
        self.eng.show_srt_setup()
        blob = " | ".join(self._drawn(self.eng.screen_obj))
        self.assertNotIn(ss.sequence_text(ss.LAB_SEQUENCE), blob)
        self.assertNotIn(ss.sequence_text(ss.LAB_SEQUENCE, letters=True),
                         blob)

    def test_a_custom_setup_in_the_file_is_said_and_run(self):
        store = ss.SetupStore(self.root / "srt_setups.json")
        assert not store.set_current(
            ss.SRTSetup("mine", "constant", 400, ss.LAB_SEQUENCE))
        self.eng.show_srt_setup()
        sc = self.eng.screen_obj
        blob = " | ".join(self._drawn(sc))
        self.assertIn("Custom setup from srt_setups.json", blob)
        self.assertIn("400", blob)
        sc._start()
        self.assertEqual(self.eng.mode.setup.isi_ms, 400)

    def test_the_labs_own_run_says_nothing_extra(self):
        self.eng.show_srt_setup()
        self.assertNotIn("Custom setup",
                         " | ".join(self._drawn(self.eng.screen_obj)))

    def test_enter_starts_the_task(self):
        self.eng.show_srt_setup()
        sc = self.eng.screen_obj
        sc.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0,
                             "unicode": "\r", "scancode": 0}))
        self.assertTrue(self.eng.block_is_running())
        self.assertEqual(self.eng.current_block, "srt")

    def test_musical_experience_belongs_to_the_login(self):
        self.eng._srt_musical_experience = 4
        self.eng._clear_session_carry()
        self.assertIsNone(getattr(self.eng, "_srt_musical_experience", None))


class TheLabSession(unittest.TestCase):

    def _plan(self, code, lab):
        from finger_rehab.config import Config
        from finger_rehab.game.battery import build_plan
        cfg = (Config.load(APP / "config" / "eeg_lab.yaml") if lab
               else Config.load())
        return build_plan(cfg, code, "right")

    def test_the_study_battery_keeps_its_reaction(self):
        for code in ("P001", "P002"):
            modes = [s.mode for s in self._plan(code, False).steps]
            self.assertEqual(modes.count("reaction"), 2)
            self.assertNotIn("srt", modes)

    def test_the_lab_plays_the_srt_once(self):
        for code in ("P001", "P002"):
            with self.subTest(code=code):
                plan = self._plan(code, True)
                study = self._plan(code, False)
                modes = [s.mode for s in plan.steps]
                self.assertEqual(modes.count("srt"), 1)
                self.assertNotIn("reaction", modes)
                # The second Reaction block and Muscle Memory are out.
                self.assertEqual(len(plan.steps), len(study.steps) - 2)
                self.assertEqual([s.position for s in plan.steps],
                                 list(range(1, len(plan.steps) + 1)))
                srt = next(s for s in plan.steps if s.mode == "srt")
                self.assertEqual(srt.phase, "pass1")
                self.assertEqual(plan.id, "eeg_lab_srt_v3")
                # The rest between the passes survives the drop.
                rests = [s for s in plan.steps if s.rest_before_s > 0]
                self.assertEqual(len(rests), 1)
                self.assertEqual(rests[0].phase, "pass2")

    def test_the_lab_leaves_out_muscle_memory(self):
        # The SRT's recall question comes first in both orders and
        # tells the player a sequence was there (Basil, 29 September
        # 2026); the home sitting keeps its Muscle Memory block.
        for code in ("P001", "P002"):
            with self.subTest(code=code):
                modes = [s.mode for s in self._plan(code, True).steps]
                self.assertNotIn("pattern", modes)
                self.assertIn("pattern",
                              [s.mode for s in self._plan(code, False).steps])

    def test_leave_out_moves_a_rest_forward(self):
        from finger_rehab.game.battery import BatteryStep, leave_out
        steps = [BatteryStep("srt", "right", "right", "pass1"),
                 BatteryStep("pattern", "right", "right", "pass2",
                             rest_before_s=180, rest_min_s=60),
                 BatteryStep("chords", "right", "right", "pass2",
                             stretch_before_s=30),
                 BatteryStep("pattern", "right", "right", "pass2")]
        out = leave_out(steps, {"pattern"})
        self.assertEqual([s.mode for s in out], ["srt", "chords"])
        # The rest wins over the stretch the next block had.
        self.assertEqual((out[1].rest_before_s, out[1].rest_min_s,
                          out[1].stretch_before_s), (180, 60, 0.0))
        self.assertEqual([s.position for s in out], [1, 2])

    def test_two_left_out_in_a_row_keep_the_rest(self):
        # A rest, then a stretch, both on left-out steps: the enforced
        # rest must survive, not the stretch that came after it.
        from finger_rehab.game.battery import BatteryStep, leave_out
        steps = [BatteryStep("srt", "right", "right", "pass1"),
                 BatteryStep("pattern", "right", "right", "pass2",
                             rest_before_s=180, rest_min_s=60),
                 BatteryStep("pattern", "right", "right", "pass2",
                             stretch_before_s=30),
                 BatteryStep("chords", "right", "right", "pass2")]
        out = leave_out(steps, {"pattern"})
        self.assertEqual([s.mode for s in out], ["srt", "chords"])
        self.assertEqual((out[1].rest_before_s, out[1].rest_min_s),
                         (180, 60))

    def test_swap_once_moves_a_rest_forward(self):
        from finger_rehab.game.battery import BatteryStep, swap_once
        steps = [BatteryStep("reaction", "right", "right", "pass1"),
                 BatteryStep("chords", "right", "right", "pass1"),
                 BatteryStep("reaction", "right", "right", "pass2",
                             rest_before_s=180, rest_min_s=60),
                 BatteryStep("force_pilot", "right", "right", "pass2")]
        out = swap_once(steps, {"reaction": "srt"})
        self.assertEqual([s.mode for s in out],
                         ["srt", "chords", "force_pilot"])
        self.assertEqual((out[2].rest_before_s, out[2].rest_min_s),
                         (180, 60))


class TestModeRunsShort(unittest.TestCase):

    def test_demo_structure(self):
        pygame.init()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _use(root)
            eng = _engine(root)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.set_hand_mode("right")
            eng.begin_srt_block()
            m = eng.mode
            blocks = [(s.phase, len(s.targets)) for s in m.steps
                      if s.kind == "block"]
            n = eng.cfg.get("game.test_mode_trials")
            self.assertEqual(blocks, [("practice", n), ("learning", 10),
                                      ("learning", 10), ("posttest", n)])
            eng._abandon_if_in_block()
        pygame.quit()


if __name__ == "__main__":
    unittest.main()
