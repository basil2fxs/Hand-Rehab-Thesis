"""The study battery: the fixed block order from the healthy baseline
design, run through the real engine's protocol runner.

  1. game/battery.py: the plan for a code (cell, order, hands), the
     override snapshot and its restore.
  2. The engine end to end, real blocks in a temp sessions tree: even
     and odd codes get their orders, every block's metadata carries
     the battery id and position, the short-form keys reach the mode
     objects, the config is put back at the end, the strip and NEXT
     UP read the same state, and an abandon or a skip behaves.
  3. What a keyboard rig can and cannot run.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


ORDER_A = ["reaction", "reaction", "mirror", "rhythm", "echo",
           "force_pilot", "lighthouse", "chords", "buzz_hunt", "pattern"]
ORDER_B = ["force_pilot", "lighthouse", "chords", "buzz_hunt",
           "reaction", "reaction", "mirror", "rhythm", "echo", "pattern"]


class _Rig:
    """A two-board rig that never delivers a sample: every mode is
    playable, nothing ever ticks. Enough for a block to open, write
    its metadata and close through the real finish path."""
    provides_samples = True
    is_connected = True
    name = "fake-two-board"
    hand_modes_available = {"right", "left", "both"}

    def __init__(self) -> None:
        self.commands: list[str] = []

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def get_sample(self, timeout: float = 0.0):
        return None

    def send_command(self, cmd: str) -> bool:
        self.commands.append(cmd)
        return True


# ---------------------------------------------------------------------
# 1. the plan
# ---------------------------------------------------------------------
class PlanTests(unittest.TestCase):
    def _cfg(self):
        from finger_rehab.config import Config
        return Config.load()

    def test_the_four_cells_give_the_design_orders(self) -> None:
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        cases = {
            # code: (order, first hand for a right-dominant person)
            "P01": (ORDER_A, "right"), "P02": (ORDER_B, "right"),
            "P03": (ORDER_A, "left"), "P04": (ORDER_B, "left"),
            "P05": (ORDER_A, "right"), "P12": (ORDER_B, "left"),
        }
        for code, (order, first) in cases.items():
            plan = build_plan(cfg, code, "right")
            self.assertEqual([s.mode for s in plan.steps], order, code)
            self.assertEqual(plan.id, "healthy_baseline_v1")
            self.assertEqual(len(plan.steps), 10)
            hand1 = next(s for s in plan.steps
                         if s.hand_requested == "hand1")
            hand2 = next(s for s in plan.steps
                         if s.hand_requested == "hand2")
            self.assertEqual(hand1.hand, first, code)
            self.assertNotEqual(hand1.hand, hand2.hand)
            self.assertEqual(plan.steps[-1].mode, "pattern")
            self.assertEqual(plan.steps[-1].hand, "right")
            for s in plan.steps:
                if s.hand_requested == "both":
                    self.assertEqual(s.hand, "both")
            self.assertEqual([s.position for s in plan.steps],
                             list(range(1, 11)))

    def test_hands_follow_the_dominant_hand(self) -> None:
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        plan = build_plan(cfg, "P03", "left")   # non-dominant first
        hand1 = next(s for s in plan.steps if s.hand_requested == "hand1")
        self.assertEqual(hand1.hand, "right")
        self.assertEqual(plan.steps[-1].hand, "left")
        self.assertEqual(plan.cell["hand_first"], "non_dominant")
        self.assertEqual(plan.cell["mode_order"], "A")

    def test_the_stretch_sits_at_the_set_boundary(self) -> None:
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        a = build_plan(cfg, "P01", "right")
        b = build_plan(cfg, "P02", "right")
        self.assertEqual([s.mode for s in a.steps if s.stretch_before_s],
                         ["force_pilot"])
        self.assertEqual([s.mode for s in b.steps if s.stretch_before_s],
                         ["reaction"])
        self.assertEqual(a.stretch_s, 60.0)
        self.assertEqual(a.budget_min, 50.0)

    def test_rhythm_carries_its_pinned_track(self) -> None:
        from finger_rehab.game.battery import build_plan, find_track
        cfg = self._cfg()
        plan = build_plan(cfg, "P01", "right")
        rhythm = next(s for s in plan.steps if s.mode == "rhythm")
        self.assertEqual(rhythm.track, "Easy_Lemon.mp3")
        self.assertEqual(rhythm.difficulty, "medium")
        self.assertIsNotNone(find_track(cfg, "Easy_Lemon.mp3"))
        self.assertIsNone(find_track(cfg, "no_such_track.mp3"))

    def test_a_missing_dominant_hand_is_refused_plainly(self) -> None:
        from finger_rehab.game.battery import build_plan, BatteryError
        with self.assertRaises(BatteryError) as ctx:
            build_plan(self._cfg(), "P01", "")
        self.assertIn("dominant hand", str(ctx.exception))

    def test_a_name_gets_a_fixed_cell_too(self) -> None:
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        one = build_plan(cfg, "Mara", "right")
        two = build_plan(cfg, "mara ", "right")
        self.assertEqual([s.mode for s in one.steps],
                         [s.mode for s in two.steps])
        self.assertEqual(one.cell["source"], "hash")


class OverrideTests(unittest.TestCase):
    def test_overrides_change_counts_and_ladders_only(self) -> None:
        """Every key the preset touches is a trial count, a rest, a
        level or a ladder threshold. No scoring, window or detection
        key may ever appear here: short forms change how many, never
        what a hit is."""
        from finger_rehab.config import Config
        from finger_rehab.game.battery import _flatten, load_preset
        cfg = Config.load()
        keys = set(_flatten(load_preset(cfg)["overrides"]))
        allowed = {
            "reaction.sub_mode", "reaction.block_trials",
            "reaction.response_windows_s",
            "force_pilot.runs_per_finger", "force_pilot.rest_s",
            "force_pilot.level", "force_pilot.promote_frac",
            "force_pilot.demote_frac",
            "lighthouse.holds_per_finger", "lighthouse.echoes_per_finger",
            "lighthouse.echo_delays_s", "lighthouse.rest_s",
            "lighthouse.level", "lighthouse.promote_lit_mae_pct",
            "lighthouse.promote_delta_pct", "lighthouse.demote_delta_pct",
            "chords.subblocks", "chords.trials_per_subblock",
            "chords.sync_windows_ms",
            "buzz_hunt.loc_trials_per_hand",
            "buzz_hunt.distractor_trials_per_hand",
            "buzz_hunt.span_trials", "buzz_hunt.gap_trials_per_hand",
            "buzz_hunt.catch_rate",
            "pattern.short_session", "pattern.soc_cycles_per_block",
            "pattern.random_block_trials",
            "rhythm.difficulty",
        }
        self.assertEqual(keys, allowed)
        for key in keys:
            self.assertFalse(key.startswith("scoring"), key)

    def test_apply_and_restore_round_trip(self) -> None:
        from finger_rehab.game.battery import (apply_overrides,
                                               restore_overrides)
        data = {"reaction": {"block_trials": 25,
                             "response_windows_s": [2.0, 1.5, 1.2],
                             "lapse_ms": 500},
                "scoring": {"perfect_ms": 100}}
        snap = apply_overrides(data, {
            "reaction": {"block_trials": 10, "response_windows_s": [2.0],
                         "brand_new": True},
            "lighthouse": {"level": 3}})
        self.assertEqual(data["reaction"]["block_trials"], 10)
        self.assertEqual(data["reaction"]["response_windows_s"], [2.0])
        self.assertEqual(data["reaction"]["lapse_ms"], 500)
        self.assertTrue(data["reaction"]["brand_new"])
        self.assertEqual(data["lighthouse"], {"level": 3})
        restore_overrides(data, snap)
        self.assertEqual(data["reaction"], {
            "block_trials": 25, "response_windows_s": [2.0, 1.5, 1.2],
            "lapse_ms": 500})
        self.assertEqual(data["lighthouse"], {})
        self.assertEqual(data["scoring"], {"perfect_ms": 100})


# ---------------------------------------------------------------------
# 2. the engine, end to end
# ---------------------------------------------------------------------
class _BatteryHarness(unittest.TestCase):
    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self) -> None:
        import pygame
        eng = getattr(self, "eng", None)
        if eng is not None:
            try:
                eng._close_loggers()
            except Exception:
                pass
        self._td.cleanup()
        pygame.quit()

    def _engine(self, source=None):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(self.root)
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        eng = GameEngine(cfg, source or KeyboardOnlySource())
        eng._screens = eng._build_screens()
        self.eng = eng
        return eng

    def _login(self, eng, code: str, dominant: str) -> None:
        eng.begin_session(code, "25", dominant_hand=dominant, visit="1")
        # A fake rig has no calibration behind it; the guard would
        # put a question up. The clinician has answered it here.
        eng._uncal_ack = {"left", "right"}

    def _stub_rhythm(self) -> None:
        """Pin the beatmap: extracting Easy_Lemon with librosa is
        seconds of work the order test does not need."""
        import finger_rehab.audio.beatmap as bm
        real = bm.extract_beatmap

        def fake(path, difficulty="medium", lane_pattern=None,
                 num_lanes=4):
            b = bm.procedural_beatmap(120.0, 8, difficulty=difficulty,
                                      num_lanes=num_lanes)
            b.song = str(path)
            return b
        bm.extract_beatmap = fake
        self.addCleanup(lambda: setattr(bm, "extract_beatmap", real))

    def _run_battery(self, eng) -> list[tuple[str, str, Path]]:
        """Start the battery and finish every block the moment it
        opens, taking each NEXT UP step, the way the RA does.
        Returns (mode, hand, folder) per completed block."""
        played: list[tuple[str, str, Path]] = []
        self.assertTrue(eng.start_battery())
        for _ in range(20):
            if not eng.block_is_running():
                break
            played.append((str(eng.current_block), str(eng.hand_mode),
                           Path(eng.session_paths.root)))
            eng.finish_block()
            if eng.pending_protocol_step() is None:
                break
            self.assertIs(eng.screen_obj, eng._screens["results"])
            self.assertTrue(eng.continue_protocol())
        return played


class BatteryOrderTests(_BatteryHarness):
    def test_odd_code_runs_order_a_dominant_first(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        played = self._run_battery(eng)
        self.assertEqual([m for m, _h, _f in played], ORDER_A)
        self.assertEqual([h for _m, h, _f in played],
                         ["right", "left", "both", "both", "both",
                          "both", "both", "both", "both", "right"])

    def test_even_code_runs_order_b_non_dominant_first(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P04", "right")
        played = self._run_battery(eng)
        self.assertEqual([m for m, _h, _f in played], ORDER_B)
        self.assertEqual([h for _m, h, _f in played],
                         ["both", "both", "both", "both",
                          "left", "right", "both", "both", "both", "right"])

    def test_left_dominant_flips_the_hands(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P02", "left")     # B, dominant first
        played = self._run_battery(eng)
        self.assertEqual([m for m, _h, _f in played], ORDER_B)
        self.assertEqual([h for _m, h, _f in played][4:6], ["left", "right"])
        self.assertEqual(played[-1][1], "left")

    def test_every_block_carries_the_battery_stamp(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P03", "right")
        played = self._run_battery(eng)
        self.assertEqual(len(played), 10)
        for pos, (mode, hand, folder) in enumerate(played, start=1):
            meta = json.loads((folder / "metadata.json").read_text(
                encoding="utf-8"))
            bat = meta["battery"]
            self.assertEqual(bat["id"], "healthy_baseline_v1", mode)
            self.assertEqual(bat["position"], pos, mode)
            self.assertEqual(bat["of"], 10)
            self.assertEqual(bat["step"], f"{mode}_{hand}")
            self.assertEqual(bat["cell"]["mode_order"], "A")
            self.assertEqual(bat["cell"]["hand_first"], "non_dominant")
            self.assertEqual(meta["participant"], "P03")
            self.assertEqual(meta["visit"], "1")
            self.assertEqual(meta["dominant_hand"], "right")
            self.assertEqual(meta["block_summary"]["block"], mode)
            self.assertEqual(meta["block_summary"]["status"], "completed")
            self.assertTrue(folder.name.startswith("P03_"))
            # The snapshot in the block's own metadata shows the
            # short forms it ran under.
            snap = meta["config_snapshot"]
            self.assertEqual(snap["reaction"]["response_windows_s"], [2.0])
            self.assertEqual(snap["force_pilot"]["runs_per_finger"], 1)
        # And the trial CSV phase column names the battery.
        self.assertEqual(eng._current_phase, "")
        progress = eng.battery_progress()
        self.assertTrue(progress["finished"])
        self.assertEqual(progress["done"], 10)
        self.assertEqual([r["status"] for r in progress["log"]],
                         ["completed"] * 10)
        self.assertEqual([r["battery_pos"] for r in eng.session_games_log()],
                         list(range(1, 11)))

    @staticmethod
    def _config_text(eng) -> str:
        """The config as text, minus the two keys any game start
        writes (the picked mode and hand) so the comparison is about
        the battery's overrides and nothing else."""
        data = json.loads(json.dumps(eng.cfg.data, default=str))
        data.get("game", {}).pop("mode", None)
        data.get("bilateral", {}).pop("hand", None)
        return json.dumps(data, sort_keys=True)

    def test_config_is_put_back_after_the_battery(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        before = self._config_text(eng)
        self._login(eng, "P01", "right")
        self.assertTrue(eng.start_battery())
        self.assertEqual(eng.cfg.get("reaction.response_windows_s"), [2.0])
        self.assertEqual(eng.cfg.get("chords.subblocks"), 3)
        self._run_battery_from_running(eng)
        self.assertEqual(eng.cfg.get("reaction.response_windows_s"),
                         [2.0, 1.5, 1.2])
        self.assertEqual(eng.cfg.get("chords.subblocks"), 5)
        self.assertEqual(eng.cfg.get("buzz_hunt.gap_trials_per_hand"), 20)
        # A free game after the battery is a standard block again and
        # carries no stamp.
        eng.begin_game("reaction", "right")
        self.assertEqual(eng.mode.max_level, 3)
        self.assertEqual(eng.session.battery, {})
        eng.finish_block()
        # Nothing but the picked mode and hand differs from boot.
        eng.end_session()
        self.assertEqual(before, self._config_text(eng))

    def _run_battery_from_running(self, eng) -> None:
        for _ in range(20):
            if not eng.block_is_running():
                break
            eng.finish_block()
            if eng.pending_protocol_step() is None:
                break
            eng.continue_protocol()


class ShortFormTests(_BatteryHarness):
    """The short-form keys reach the mode objects, and only counts
    and ladders move."""

    def _step_to(self, eng, mode: str):
        for _ in range(20):
            if str(eng.current_block) == mode and eng.block_is_running():
                return eng.mode
            if eng.block_is_running():
                eng.finish_block()
            if eng.pending_protocol_step() is None:
                break
            eng.continue_protocol()
        self.fail(f"battery never reached {mode}")

    def test_reaction_window_is_frozen_at_one_rung(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        m = self._step_to(eng, "reaction")
        self.assertEqual(m.max_level, 1)
        self.assertEqual(m.response_window, 2.0)
        self.assertEqual(m.total_trials, 25)
        # Scoring is untouched.
        self.assertEqual(eng.score_cfg.perfect_ms, 100)

    def test_force_pilot_and_lighthouse_ladders_are_frozen(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        fp = self._step_to(eng, "force_pilot")
        self.assertEqual(fp.total_runs, 8)      # one run per finger, both
        self.assertGreater(fp.promote_frac, 1.0)
        self.assertEqual(fp.demote_frac, 0.0)
        self.assertEqual(fp.rest_s, 5.0)
        lh = self._step_to(eng, "lighthouse")
        # One hold and one echo per finger over eight fingers.
        self.assertEqual(lh._kind_bag.count("hold"), 8)
        self.assertEqual(lh._kind_bag.count("echo"), 8)
        self.assertEqual(lh.total_trials, 16)
        self.assertEqual(lh.echo_delays_s, [2.0, 10.0])
        self.assertEqual(lh.level, 3)
        self.assertLess(lh.promote_delta_pct, 0)
        self.assertGreater(lh.demote_delta_pct, 100)

    def test_chords_buzz_hunt_and_pattern_counts(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P02", "right")
        eng.start_battery()
        ch = self._step_to(eng, "chords")
        self.assertEqual(ch.subblocks, 3)
        self.assertEqual(ch.trials_per_subblock, 20)
        self.assertEqual(ch.max_level, 0)          # one window: no ladder
        self.assertEqual(ch.windows_ms, [150.0])
        bh = self._step_to(eng, "buzz_hunt")
        plan = list(bh._stage_plan)
        self.assertEqual(plan.count("loc"), 32)    # 16 per hand, both
        self.assertEqual(plan.count("span"), 8)
        self.assertEqual(plan.count("dis"), 0)
        self.assertEqual(plan.count("gap"), 0)
        pat = self._step_to(eng, "pattern")
        self.assertTrue(pat.short_session)
        # The short layout: warm-up, random, three trained, probe,
        # trained, probe, trained; 36-press takes over the 12-item
        # sequence and a 32-trial random take.
        kinds = [s.kind for s in pat.segments]
        self.assertEqual(kinds, ["warmup", "random", "seq", "seq", "seq",
                                 "probe", "seq", "probe", "seq"])
        self.assertEqual([len(s.fingers) for s in pat.segments
                          if s.kind == "seq"], [36] * 5)
        self.assertEqual([len(s.fingers) for s in pat.segments
                          if s.kind == "random"], [32])
        self.assertEqual(eng.hand_mode, "right")


class BatteryFlowTests(_BatteryHarness):
    def test_abandon_offers_the_same_step_again(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        self.assertEqual(eng.current_block, "reaction")
        first_folder = Path(eng.session_paths.root)
        eng._abandon_if_in_block()
        eng.show_mode_select()
        pending = eng.pending_protocol_step()
        self.assertEqual((pending["mode"], pending["hand"], pending["position"]),
                         ("reaction", "right", 1))
        meta = json.loads((first_folder / "metadata.json").read_text(
            encoding="utf-8"))
        self.assertEqual(meta["battery"]["position"], 1)
        self.assertEqual(meta["block_summary"]["status"], "abandoned")
        progress = eng.battery_progress()
        self.assertEqual(progress["done"], 0)
        self.assertEqual(progress["log"][-1]["status"], "abandoned")
        # Continue, and the redo carries position 1 too.
        eng.continue_protocol()
        self.assertEqual(eng.session.battery["position"], 1)
        eng.finish_block()
        self.assertEqual(eng.pending_protocol_step()["position"], 2)

    def test_skip_moves_past_a_step(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        self.assertEqual(eng.pending_protocol_step()["position"], 2)
        self.assertTrue(eng.skip_protocol_step())
        self.assertEqual(eng.pending_protocol_step()["position"], 3)
        log = eng.battery_progress()["log"]
        self.assertEqual([r["status"] for r in log],
                         ["completed", "skipped"])
        self.assertIn("researcher", log[-1]["reason"])

    def test_a_free_pick_mid_battery_is_not_a_battery_block(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        # The hub is open; the RA plays echo on its own.
        eng.begin_game("echo", "right")
        self.assertEqual(eng.session.battery, {})
        eng.finish_block()
        pending = eng.pending_protocol_step()
        self.assertEqual((pending["mode"], pending["position"]),
                         ("reaction", 2))

    def test_end_session_cancels_the_battery_and_restores(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        eng.end_session()
        self.assertIsNone(eng.battery_progress())
        self.assertEqual(eng.cfg.get("reaction.response_windows_s"),
                         [2.0, 1.5, 1.2])
        self.assertIsNone(eng.pending_protocol_step())

    def test_hub_and_results_read_the_battery(self) -> None:
        import pygame
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        hub = eng._screens["mode_select"]
        ok, label, reason = hub._battery_state()
        self.assertTrue(ok, reason)
        self.assertIn("Study battery", label)
        # B starts it from the hub.
        eng.show_mode_select()
        hub.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_b, "mod": 0, "unicode": "b",
                             "scancode": 0}))
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng.current_block, "reaction")
        eng.finish_block()
        results = eng._screens["results"]
        self.assertIs(eng.screen_obj, results)
        key, hand = results._next_up_plan()
        self.assertEqual((key, hand), ("reaction", "left"))
        heading, pill, stretch = results._battery_card_lines(
            eng.pending_protocol_step())
        self.assertIn("step 2 of 10", heading)
        self.assertEqual(stretch, "")
        results.draw(pygame.Surface((1280, 800)))
        # N takes the step.
        results.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_n, "mod": 0, "unicode": "n",
                             "scancode": 0}))
        self.assertEqual((eng.current_block, eng.hand_mode),
                         ("reaction", "left"))
        eng.finish_block()
        _ok, label, _reason = hub._battery_state()
        self.assertIn("2/10", label)
        hub.draw(pygame.Surface((1280, 800)))

    def test_the_stretch_step_says_so_on_the_card(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        for _ in range(5):
            eng.finish_block()
            if eng.pending_protocol_step()["mode"] == "force_pilot":
                break
            eng.continue_protocol()
        results = eng._screens["results"]
        heading, _pill, stretch = results._battery_card_lines(
            eng.pending_protocol_step())
        self.assertIn("step 6 of 10", heading)
        self.assertIn("Stretch", stretch)

    def test_without_a_dominant_hand_the_hub_says_why(self) -> None:
        eng = self._engine(_Rig())
        eng.begin_session("Mara", "40")
        ok, reason = eng.battery_available()
        self.assertFalse(ok)
        self.assertIn("dominant hand", reason)
        self.assertFalse(eng.start_battery())
        self.assertEqual(eng._screens["mode_select"]._battery_state()[0],
                         False)

    def test_legacy_protocol_still_chains_without_results(self) -> None:
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.cfg.data["protocol"]["blocks"] = [
            {"mode": "reaction", "phase": "pretest"},
            {"mode": "reaction", "phase": "aftertest", "hand": "left"},
        ]
        self.assertTrue(eng.start_protocol())
        self.assertEqual(eng._current_phase, "pretest")
        self.assertEqual(eng.hand_mode, "right")
        self.assertEqual(eng.session.battery, {})
        eng.finish_block()
        # Straight into the next block, no results in between, and
        # the named hand took effect.
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng._current_phase, "aftertest")
        self.assertEqual(eng.hand_mode, "left")
        eng.finish_block()
        self.assertIs(eng.screen_obj, eng._screens["results"])
        self.assertEqual(eng._current_phase, "")


# ---------------------------------------------------------------------
# 3. a keyboard rig
# ---------------------------------------------------------------------
class KeyboardRigTests(_BatteryHarness):
    def test_hardware_steps_are_skipped_and_said(self) -> None:
        self._stub_rhythm()
        eng = self._engine()          # KeyboardOnlySource
        self._login(eng, "P01", "right")
        played = self._run_battery(eng)
        # Chords plays on the keys; the three sensor modes do not.
        self.assertEqual([m for m, _h, _f in played],
                         ["reaction", "reaction", "mirror", "rhythm",
                          "echo", "chords", "pattern"])
        log = eng.battery_progress()["log"]
        skipped = [(r["mode"], r["reason"]) for r in log
                   if r["status"] == "skipped"]
        self.assertEqual(skipped, [
            ("force_pilot", "needs sensor hardware"),
            ("lighthouse", "needs sensor hardware"),
            ("buzz_hunt", "needs sensor hardware")])
        self.assertTrue(eng.battery_progress()["finished"])
        # Position numbering is the design's, skips included.
        meta = json.loads((played[-1][2] / "metadata.json").read_text(
            encoding="utf-8"))
        self.assertEqual(meta["battery"]["position"], 10)


if __name__ == "__main__":
    unittest.main()
