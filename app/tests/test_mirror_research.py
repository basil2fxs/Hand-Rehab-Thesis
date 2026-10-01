"""Mirror after the deep research of 1 October 2026.

Each board's samples keep their own stamps and none are dropped; a
hand's detector is fed only its own board's samples; the raw file
names the board; a press under 100 ms is not a response; a late press
after the window closed is not charged; a one-sided pair and a gated
pair say so in the row; a pair cut short by a dropped board never
reaches the pace controller; the block records the window and the
one-sided count beside the gap; and the notebook reads the median gap
as a rig check, the lead two-sided outside Holm, and no mirror
therapy.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_mirror_mode import _Spy, _build, _press  # noqa: E402
from tests.test_multi_serial import _make_multi  # noqa: E402

APP = Path(__file__).resolve().parents[1]


def _drain(multi) -> list:
    out = []
    while True:
        s = multi.get_sample(timeout=0)
        if s is None:
            return out
        out.append(s)


def _queue(multi, hand: str, t: float, values) -> None:
    item = (t, tuple(values))
    if hand == "right":
        multi._last_right = item
        multi._q_right.append(item)
    else:
        multi._last_left = item
        multi._q_left.append(item)


class MergerTests(unittest.TestCase):

    def _multi(self):
        multi, _fakes = _make_multi(["/dev/cu.RIGHT", "/dev/cu.LEFT"])
        multi._reset_pairing()
        return multi

    def test_every_sample_goes_on_in_time_order_with_its_own_stamp(self):
        multi = self._multi()
        t0 = time.perf_counter() - 1.0
        for dt in (0.000, 0.001, 0.002):          # one packet of three
            _queue(multi, "right", t0 + dt, (10, 20, 30, 40))
        _queue(multi, "left", t0 + 0.0015, (50, 60, 70, 80))
        multi._emit_paired_if_ready()
        got = _drain(multi)
        self.assertEqual(len(got), 4, "a sample of the packet was dropped")
        stamps = [s.t_perf for s in got]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual([s.t_hands for s in got],
                         [(t0, None), (t0 + 0.001, None),
                          (None, t0 + 0.0015), (t0 + 0.002, None)])
        self.assertEqual(got[2].values, (10, 20, 30, 40, 50, 60, 70, 80))

    def test_a_fresh_sample_waits_for_an_earlier_one_from_the_other_board(self):
        multi = self._multi()
        t = time.perf_counter()
        _queue(multi, "right", t, (10, 20, 30, 40))
        multi._emit_paired_if_ready()
        self.assertEqual(_drain(multi), [])
        _queue(multi, "left", t - 0.004, (50, 60, 70, 80))
        multi._emit_paired_if_ready()
        got = _drain(multi)
        self.assertEqual(got[0].t_hands, (None, t - 0.004))

    def test_a_silent_board_reads_as_zeros(self):
        multi = self._multi()
        t0 = time.perf_counter() - 2.0
        _queue(multi, "left", t0, (50, 60, 70, 80))
        multi._emit_paired_if_ready()
        _drain(multi)
        _queue(multi, "right", t0 + 0.2, (10, 20, 30, 40))
        multi._emit_paired_if_ready()
        got = _drain(multi)
        self.assertEqual(got[-1].values, (10, 20, 30, 40, 0, 0, 0, 0))


class EngineFeedTests(unittest.TestCase):

    def _ns(self):
        from finger_rehab.game.engine import GameEngine
        cfg = MagicMock()
        cfg.get = MagicMock(side_effect=lambda k, d=None:
                            4 if k == "fsr.num_sensors_per_hand" else d)
        ns = SimpleNamespace(cfg=cfg, hand_mode="both", _hands_down=set(),
                             detectors={"right": MagicMock(),
                                        "left": MagicMock()})
        return GameEngine, ns

    def test_only_the_board_that_sent_is_fed_on_its_own_stamp(self):
        GameEngine, ns = self._ns()
        vals = (1, 2, 3, 4, 5, 6, 7, 8)
        GameEngine._feed_detectors(ns, 10.0, vals, (10.0, None))
        ns.detectors["right"].feed.assert_called_once_with(10.0, (1, 2, 3, 4))
        ns.detectors["left"].feed.assert_not_called()
        GameEngine._feed_detectors(ns, 10.003, vals, (None, 10.003))
        ns.detectors["left"].feed.assert_called_once_with(10.003,
                                                          (5, 6, 7, 8))

    def test_one_board_still_feeds_both_slots_as_before(self):
        GameEngine, ns = self._ns()
        GameEngine._feed_detectors(ns, 5.0, (1, 2, 3, 4, 5, 6, 7, 8))
        ns.detectors["right"].feed.assert_called_once()
        ns.detectors["left"].feed.assert_called_once()

    def test_the_raw_row_names_the_board(self):
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.source import Sample
        samples = [Sample(t_perf=1.0, values=(0,) * 8, t_hands=(1.0, None)),
                   Sample(t_perf=1.002, values=(0,) * 8,
                          t_hands=(None, 1.002)),
                   Sample(t_perf=1.004, values=(0,) * 4)]
        src = MagicMock()
        src.get_sample = MagicMock(side_effect=samples + [None])
        ns = SimpleNamespace(_check_source_connection=lambda: None,
                             current_block="(none)", source=src,
                             _feed_detectors=MagicMock(),
                             raw_logger=MagicMock(), _screens={},
                             hand_mode="both", screen_obj=None,
                             detectors={}, cfg=MagicMock())
        GameEngine._pump_source(ns)
        details = [c.kwargs.get("detail")
                   for c in ns.raw_logger.queue_sample.call_args_list]
        self.assertEqual(details, ["board=right", "board=left", ""])


class ModeRuleTests(unittest.TestCase):

    def _mode(self, **kw):
        spy = _Spy()
        spy.raw_logger = MagicMock()
        mode = _build(spy, pattern=[0], **kw)
        return spy, mode

    def _events(self, spy):
        return [c.args[0] for c in spy.raw_logger.queue_event.call_args_list]

    def test_a_press_under_100_ms_is_not_a_response(self):
        spy, mode = self._mode()
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.05), now=0.05)
        self.assertIsNone(mode.active.right_press_t)
        self.assertEqual(mode._anticipations, 1)
        self.assertIn("anticipation_press", self._events(spy))
        spy.apply_wrong_press_penalty.assert_not_called()
        mode._handle_press(_press(0, 0.25), now=0.25)
        mode._handle_press(_press(4, 0.27), now=0.27)
        outcome = spy.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")
        self.assertAlmostEqual(outcome.rt_ms, 270.0, places=2)

    def test_a_one_sided_pair_says_so_and_the_late_hand_is_not_charged(self):
        spy, mode = self._mode()
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.25), now=0.25)
        mode._finish(2.0)
        self.assertEqual(spy.log_trial.call_args.kwargs["error_type"],
                         "one_sided")
        mode._handle_press(_press(4, 2.1), now=2.1)
        self.assertEqual(mode._late_presses, 1)
        self.assertIn("late_press", self._events(spy))
        spy.apply_idle_press_penalty.assert_not_called()
        mode._handle_press(_press(1, 2.2), now=2.2)
        spy.apply_idle_press_penalty.assert_called_once()
        self.assertEqual(mode.block_stats()["n_one_sided"], 1)

    def test_a_gated_pair_is_async_and_names_the_hand_behind(self):
        spy, mode = self._mode()
        gp = MagicMock()
        spy._screens = {"gameplay": gp}
        spy.feedback_style = "encouraging"
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.20), now=0.20)
        mode._handle_press(_press(4, 0.70), now=0.70)
        self.assertEqual(spy.log_trial.call_args[0][1].label, "Miss")
        self.assertEqual(spy.log_trial.call_args.kwargs["error_type"], "async")
        self.assertEqual(mode.block_stats()["n_gated"], 1)
        text = gp.set_message.call_args[0][0]
        self.assertTrue(text.startswith("Left hand"), text)

    def test_a_dropped_board_never_reaches_the_pace(self):
        spy, mode = self._mode()
        spy.source = SimpleNamespace(provides_samples=True, is_connected=True)
        spy._hands_down = {"left"}
        mode.adapter.record = MagicMock()
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.25), now=0.25)
        mode._finish(2.0)
        self.assertEqual(spy.log_trial.call_args.kwargs["error_type"],
                         "device_drop")
        mode.adapter.record.assert_not_called()
        self.assertEqual(mode.block_stats()["device_drops"], 1)
        self.assertEqual(mode.block_stats()["n_one_sided"], 0)

    def test_the_block_records_the_window_beside_the_gap(self):
        spy, mode = self._mode(repeat_count=3)
        t = 0.0
        for _i in range(3):
            mode._fire(now=t)
            mode._handle_press(_press(0, t + 0.25), now=t + 0.25)
            mode._handle_press(_press(4, t + 0.27), now=t + 0.27)
            t += 2.0
        st = mode.block_stats()
        self.assertEqual(len(st["bpm_trace"]), 3)
        self.assertEqual(len(st["window_trace_ms"]), 3)
        self.assertEqual(st["window_max_ms"], max(st["window_trace_ms"]))
        self.assertEqual(st["cues_per_finger"], [3, 0, 0, 0])
        self.assertEqual(st["hits_per_finger"], [3, 0, 0, 0])
        self.assertEqual(st["max_async_ms"], 350.0)
        states = [c for c in spy.raw_logger.queue_event.call_args_list
                  if c.args[0] == "mirror_state"]
        self.assertEqual(len(states), 3)
        self.assertIn("window_ms=", states[0].kwargs["detail"])

    def test_the_summary_carries_the_median_and_the_block_stats(self):
        from tests.test_block_summary import _bare_engine_for_summary
        eng = _bare_engine_for_summary()
        eng.current_block = "mirror"
        eng.hand_mode = "both"
        eng._mirror_gaps_ms = [20.0, 30.0, 400.0]
        eng._mirror_right_rts_ms = [250.0, 260.0, 270.0]
        eng._mirror_left_rts_ms = [270.0, 290.0, 670.0]
        eng.mode = SimpleNamespace(seed=3, block_stats=lambda: {
            "window_min_ms": 900, "n_one_sided": 2})
        s = eng._build_block_summary("completed")
        self.assertEqual(s["mirror"]["median_gap_ms"], 30.0)
        self.assertEqual(s["mirror"]["mean_gap_ms"], 150.0)
        self.assertEqual(s["mirror"]["n_one_sided"], 2)
        self.assertEqual(s["mirror"]["window_min_ms"], 900)


class WordingTests(unittest.TestCase):

    def test_the_card_says_what_the_game_asks(self):
        from finger_rehab.ui.feedback_bank import offending
        from finger_rehab.ui.screens import GameplayScreen
        line = " ".join(GameplayScreen.GET_READY_LINES["mirror"])
        self.assertEqual(line, "Press the lit finger on both hands at the "
                               "same moment. A pair counts when both land "
                               "together.")
        self.assertEqual(offending(line), [])

    def test_the_late_hand_lines_name_the_hand_and_the_next_action(self):
        from finger_rehab.ui.feedback_bank import MODE_LINES, offending
        lines = MODE_LINES["mirror"]["late_hand"]
        self.assertEqual(len(lines), 3)
        for raw in lines:
            text = raw.format(target="Right")
            self.assertTrue(text.startswith("Right hand"), text)
            self.assertEqual(offending(text), [])

    def test_the_mode_no_longer_claims_mirror_therapy(self):
        text = (APP / "finger_rehab" / "game" / "modes" / "mirror.py") \
            .read_text(encoding="utf-8")
        self.assertIn("It is NOT mirror\ntherapy.", text)
        self.assertIn("comparison condition in mirror-therapy trials", text)
        self.assertIn("Coupar et al. 2010", text)
        review = APP / "docs" / "research" / "deep" / "mirror.md"
        self.assertTrue(review.exists())
        index = (APP / "docs" / "research" / "deep" / "README.md") \
            .read_text(encoding="utf-8")
        self.assertIn("(mirror.md)", index)


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_gap_summaries(self):
        got = self.ra.mirror_gap_summary([-20.0, 10.0, 30.0, -40.0, 200.0])
        self.assertEqual(got["n"], 5)
        self.assertEqual(got["median_abs_ms"], 30.0)
        self.assertAlmostEqual(got["share_within"], 0.8)
        self.assertEqual(got["signed_median_ms"], 10.0)
        self.assertEqual(got["mean_abs_ms"], 60.0)
        import numpy as np
        self.assertTrue(np.isnan(self.ra.mirror_signed_ci([5.0, 7.0])[1]))

    def test_the_cohort_rows_carry_the_median_and_each_hands_latency(self):
        import pandas as pd
        rows = pd.DataFrame({
            "mirror_right_rt_ms": [250.0, 260.0, 90.0, 300.0, None],
            "mirror_left_rt_ms": [270.0, 250.0, 280.0, 330.0, 400.0],
            "had_incorrect_press": ["FALSE"] * 5})
        out = self.ra._cohort_mirror({"bs": {"mirror": {}}, "rows": rows})
        got = {(h, m): v for h, m, v, _n in out}
        self.assertEqual(got[("both", "median_abs_gap_ms")], 20.0)
        self.assertEqual(got[("both", "signed_median_ms")], -20.0)
        self.assertEqual(got[("right", "rt_median_ms")], 260.0)
        self.assertEqual(got[("left", "rt_median_ms")], 270.0)

    def test_a_one_sided_pair_is_recovered_from_raw(self):
        import pandas as pd
        with tempfile.TemporaryDirectory() as td:
            raw = pd.DataFrame({
                "t_perf": [10.0, 10.25, 10.6, 12.0, 12.3],
                "event": ["stim", "press", "press", "stim", "press"],
                "lane": [0, 0, 4, 1, 1],
                "detail": ["trial_id=3", "", "", "trial_id=4", ""]})
            raw.to_csv(Path(td) / "raw.csv", index=False)
            pad = Path(td) / "raw.csv"
            pad.write_text(pad.read_text() + "\n" * 200)
            rows = pd.DataFrame({"folder": [td], "trial": [3], "lane": [1],
                                 "right_rt": [250.0], "left_rt": [None]})
            got = self.ra.mirror_recover_one_sided(rows)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0], -350.0, places=3)

    def test_the_onset_is_re_timed_from_each_hands_own_board(self):
        import pandas as pd
        t0 = 10.0
        recs = [{"t_perf": t0, "event": "stim", "lane": 0,
                 "detail": "trial_id=3"}]
        for k in range(220):
            tr = t0 - 0.3 + 0.005 * k
            tl = tr + 0.002
            r = 550 if tr >= t0 + 0.2525 else 50
            left = 650 if tl >= t0 + 0.2725 else 60
            recs.append({"t_perf": tr, "event": "", "detail": "board=right",
                         "fsr1": r, "fsr5": 0})
            recs.append({"t_perf": tl, "event": "", "detail": "board=left",
                         "fsr1": 0, "fsr5": left})
        with tempfile.TemporaryDirectory() as td:
            pd.DataFrame(recs).to_csv(Path(td) / "raw.csv", index=False)
            rows = pd.DataFrame({"folder": [td], "trial": [3], "lane": [1],
                                 "right_rt": [255.0], "left_rt": [277.0]})
            got = self.ra.mirror_retimed_gaps(rows)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0], -22.0, places=1)

    def test_m1_is_a_rig_check_and_m2_sits_outside_holm(self):
        ra = self.ra
        self.assertIn("M1", ra.COHORT_PRESPECIFIED)
        self.assertNotIn("M2", ra.COHORT_PRESPECIFIED)
        self.assertEqual(ra.MIRROR_RIG_GAP_MS, 60.0)
        spec = {s["id"]: s for s in ra.MODE_LIT["mirror"]}
        self.assertIn("rig check", spec["M1"]["claim"])
        self.assertIn("two-sided", spec["M2"]["claim"])
        limits = " ".join(ra.MODE_CLAIM_LIMITS["mirror"])
        self.assertIn("not mirror therapy", limits)
        self.assertIn("own stamps", limits)


if __name__ == "__main__":
    unittest.main()
