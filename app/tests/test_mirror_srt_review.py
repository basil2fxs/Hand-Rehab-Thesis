"""Mirror and SRT faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Mirror: the notebook's gap counted wrong-finger trials as clean pairs
while the engine banks the gap on clean pairs only, so the chapter,
the within-block series and the internal-consistency series disagreed
with block_summary.mirror; and every block drew its finger order from
the same seed, with no seed recorded anywhere.

SRT: a pause between the flash and the answer logged an ordinary trial
with a moved onset; a silent trial the board was away for counted as
a miss; and every block began with a GET READY byte for a card the
task never shows.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from tests.test_mirror_mode import _Spy, _press  # noqa: E402
from tests.test_srt_mode import Sim, _engine, _fast_cfg, _use  # noqa: E402


def setUpModule() -> None:
    pygame.init()


def tearDownModule() -> None:
    pygame.quit()


# ---- mirror ----------------------------------------------------------------


def _mirror_order(seed: int, repeats: int = 8) -> tuple[list[int], int]:
    from finger_rehab.game.modes.mirror import MirrorMode
    from finger_rehab.game.scoring import ScoreConfig
    m = MirrorMode(engine=_Spy(), pattern=[0, 1, 2, 3],
                   repeat_count=repeats, trigger_interval_s=0.5,
                   timeout_s=1.0, early_window_s=0.1,
                   score_cfg=ScoreConfig(), seed=seed)
    order = []
    while m.completed < m.total_trials:
        m._fire(now=0.0)
        f = m.active.finger
        order.append(f)
        m._handle_press(_press(f, 0.25), now=0.25)
        m._handle_press(_press(f + 4, 0.26), now=0.26)
    return order, m.seed


def _play_mirror_block(participant: str, seed=None):
    """A whole mirror block through a real engine on the keyboard
    source, every trial a clean pair. Returns (finger order, the seed
    raw.csv recorded, the seed in the block summary)."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.fsr_detector import PressEvent
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    tmp = tempfile.mkdtemp()
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    cfg.data.setdefault("session", {})["data_dir"] = tmp
    cfg.data["session"]["participant"] = participant
    cfg.data["report"] = {"enabled": False}
    cfg.data.setdefault("mirror", {})["seed"] = seed
    eng = GameEngine(cfg, KeyboardOnlySource(cfg))
    eng.screen = pygame.display.set_mode((eng.layout.width,
                                          eng.layout.height))
    eng._screens = eng._build_screens()
    eng.hand_mode = "both"
    eng._build_detectors()
    for key in ("gameplay", "rhythm"):
        sc = eng._screens.get(key)
        if sc and hasattr(sc, "rebuild_lanes"):
            sc.rebuild_lanes()
    eng.begin_mirror_block()
    m = eng.mode
    order = []
    while m.completed < m.total_trials:
        m._fire(now=0.0)
        f = m.active.finger
        order.append(f)
        m._handle_press(PressEvent(lane=f, t_perf=0.25, value=0,
                                   baseline=0.0, hand="both"), now=0.25)
        m._handle_press(PressEvent(lane=f + 4, t_perf=0.26, value=0,
                                   baseline=0.0, hand="both"), now=0.26)
    eng.finish_block()
    root = Path(eng.last_session_root)
    meta = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    raw_seed = None
    with (root / "raw.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("event") == "mirror_config":
                raw_seed = int(r["detail"].split("seed=")[1].split()[0])
    return order, raw_seed, meta["block_summary"]["mirror"].get("seed")


class MirrorSeedTests(unittest.TestCase):

    def test_the_finger_order_follows_the_seed(self):
        a, seed_a = _mirror_order(1)
        b, _seed_b = _mirror_order(2)
        a_again, _s = _mirror_order(1)
        self.assertEqual(seed_a, 1)
        self.assertEqual(a, a_again)
        self.assertNotEqual(a, b)

    def test_the_engine_draws_records_and_honours_a_seed(self):
        order_a, raw_a, meta_a = _play_mirror_block("P01")
        order_b, raw_b, meta_b = _play_mirror_block("P02")
        self.assertIsInstance(raw_a, int)
        self.assertEqual(raw_a, meta_a)
        self.assertNotEqual(raw_a, raw_b)
        self.assertNotEqual(order_a, order_b)
        order_c, raw_c, meta_c = _play_mirror_block("P03", seed=7)
        order_d, _raw_d, _meta_d = _play_mirror_block("P04", seed=7)
        self.assertEqual((raw_c, meta_c), (7, 7))
        self.assertEqual(order_c, order_d)


# ---- srt -------------------------------------------------------------------


class _SrtBlock:
    """The test suite's 60 Hz Sim around a real SRT block, run to the
    practice block's first flash."""

    def __init__(self, spy_bytes: bool = False):
        self.td = tempfile.TemporaryDirectory()
        root = Path(self.td.name)
        _use(root)
        self.eng = _engine(root, **_fast_cfg())
        self.sent_before = []
        if spy_bytes:
            self.eng._eeg_send = (lambda code, lane=None, t_event=None:
                                  self.sent_before.append(code))
        self.eng.set_hand_mode("right")
        self.eng.begin_srt_block()
        self.sim = Sim(self.eng)
        self.mode = self.eng.mode

    def to_flash(self):
        self.sim.key(pygame.K_SPACE)
        self.sim.frame()
        self.sim.key(pygame.K_SPACE)
        self.sim.frame()
        tr = self.mode.trial
        while tr.onset is None:
            self.sim.frame()
        return tr

    def close(self):
        self.eng._abandon_if_in_block()
        self.td.cleanup()


class SrtPauseTests(unittest.TestCase):

    def test_a_pause_inside_a_trial_flags_the_row(self):
        blk = _SrtBlock()
        try:
            sim, mode = blk.sim, blk.mode
            tr = blk.to_flash()
            flash = tr.onset
            for _ in range(30):
                sim.frame()
            mode.on_resume(3.0)
            sim.eng.last_flip_t += 3.0
            sim.t = sim.eng.last_flip_t + 0.001
            sim.key(Sim.KEYS[tr.square - 1], at=tr.onset + 0.300)
            while not mode.perf_rows:
                sim.frame()
            row = mode.perf_rows[0]
            t0 = blk.eng._block_t0
            self.assertEqual(row["accuracy"], "correct")
            self.assertEqual(row["flag"], "paused")
            self.assertAlmostEqual(row["onset_s"], round(flash - t0, 4),
                                   places=4)
            self.assertEqual(mode._rts("practice"), [])
            st = mode.block_stats()
            self.assertEqual(st["n_paused"], 1)
            self.assertEqual(st["n_voided"], 0)
            self.assertEqual(st["practice"]["n"], 1)
        finally:
            blk.close()


class SrtDropTests(unittest.TestCase):

    def test_a_silent_trial_the_board_was_away_for_is_the_rigs(self):
        blk = _SrtBlock()
        try:
            sim, mode, eng = blk.sim, blk.mode, blk.eng
            logged = []
            orig = eng.log_srt_trial
            eng.log_srt_trial = (lambda row, hit, void=False:
                                 (logged.append((row, hit, void)),
                                  orig(row, hit, void)))
            tr = blk.to_flash()
            eng._block_drops = [{"hand": "right",
                                 "t_down": tr.onset + 0.1, "t_up": None}]
            misses = eng.misses
            while not mode.perf_rows:
                sim.frame()
            row = mode.perf_rows[0]
            self.assertEqual(row["accuracy"], "miss")
            self.assertEqual(row["flag"], "device_drop")
            self.assertEqual(eng.misses, misses)
            self.assertEqual(eng._block_drop_voided, 1)
            csv_row, hit, void = logged[-1]
            self.assertTrue(void)
            self.assertFalse(hit)
            self.assertEqual(csv_row["error_type"], "device_drop")
            self.assertEqual(mode._phase_stats("practice")["n"], 0)
            st = mode.block_stats()
            self.assertEqual(st["n_voided"], 1)
            self.assertEqual(st["n_trials"], 0)
        finally:
            blk.close()

    def test_a_plain_silent_trial_is_still_a_miss(self):
        blk = _SrtBlock()
        try:
            sim, mode, eng = blk.sim, blk.mode, blk.eng
            blk.to_flash()
            misses = eng.misses
            while not mode.perf_rows:
                sim.frame()
            self.assertEqual(mode.perf_rows[0]["flag"], "")
            self.assertEqual(eng.misses, misses + 1)
            self.assertEqual(mode._phase_stats("practice")["n_miss"], 1)
        finally:
            blk.close()


class SrtBlockByteTests(unittest.TestCase):

    def test_no_get_ready_byte_for_a_block_with_no_card(self):
        blk = _SrtBlock(spy_bytes=True)
        try:
            self.assertEqual(blk.sent_before, [213])
        finally:
            blk.close()


# ---- notebook --------------------------------------------------------------


def _mirror_frame():
    import pandas as pd
    rows = []

    def row(i, label, err, fumble, r, left):
        both = r is not None and left is not None
        rows.append(dict(mode="mirror", trial=i, lane=1, finger="index",
                         early_late=label, error_type=err,
                         had_incorrect_press="TRUE" if fumble else "FALSE",
                         mirror_right_rt_ms=r, mirror_left_rt_ms=left,
                         time_difference_ms=(max(r, left) if both
                                             else (r or left)),
                         bpm_at_trial=24.0))

    row(1, "Great", "", False, 200.0, 210.0)
    row(2, "Great", "", False, 200.0, 220.0)
    row(3, "Great", "", False, 200.0, 230.0)
    # A wrong finger first, then both correct: 350 ms of recovery.
    row(4, "Miss", "wrong_finger", True, 200.0, 550.0)
    # An async pair, both inside the window, 400 ms apart.
    row(5, "Miss", "async", False, 100.0, 500.0)
    # One hand only.
    row(6, "Miss", "timeout", False, 150.0, None)
    return pd.DataFrame(rows)


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_mirror_gap_is_the_engines_clean_pair_rule(self):
        import matplotlib.pyplot as plt
        frame = _mirror_frame()
        with contextlib.redirect_stdout(io.StringIO()):
            out = self.ra.sec_mirror(frame, {})
        plt.close("all")
        self.assertEqual(out["n_clean_pairs"], 4)
        self.assertEqual(out["n_fumbled"], 1)
        self.assertEqual(out["n_one_sided"], 1)
        self.assertAlmostEqual(out["mean_gap_ms"], 115.0)
        gaps, _better = self.ra.fine_series("mirror", frame)
        self.assertEqual(sorted(gaps), [10.0, 20.0, 30.0, 400.0])
        st = {"seed": 7, "mean_gap_ms": 115.0, "n_clean_pairs": 4,
              "right_hand_mean_rt_ms": 175.0,
              "left_hand_mean_rt_ms": 290.0}
        block = {"bs": {"mirror": st, "hit_rate": 0.5, "trials": 6},
                 "rows": frame, "hand": "both"}
        emitted = {(h, m): n for h, m, _v, n in self.ra._cohort_mirror(block)}
        self.assertEqual(emitted[("right", "rt_ms")], 4)
        self.assertEqual(emitted[("left", "rt_ms")], 4)

    def test_the_srt_rt_mask_leaves_paused_trials_out(self):
        import pandas as pd
        g = pd.DataFrame([
            {"phase": "practice", "accuracy": "correct", "trial": 2,
             "rt_ms": 300.0, "flag": "", "block": 0, "isi_before_ms": 500},
            {"phase": "practice", "accuracy": "correct", "trial": 3,
             "rt_ms": 300.0, "flag": "paused", "block": 0,
             "isi_before_ms": 500},
        ])
        m = self.ra._srt_rt_mask(g, "practice")
        self.assertEqual(m.tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()
