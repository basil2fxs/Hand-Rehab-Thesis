"""The study battery: the fixed block order from the healthy baseline
design, run through the real engine's protocol runner.

The design is ONE PASS in one sitting, eleven blocks, every mode
played once. Nothing here may pin a second pass, a pre/post pair or a
test-retest quantity back into the battery.

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
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


# ONE PASS in one sitting: eleven blocks, ten modes, every mode
# played once and reaction twice because the two hands are two
# different tasks. Order A is the plan file's measured block table;
# order B plays the same eleven with the force and vibration work
# first. Data Collection Plan.md of 4 September 2026, and the
# amendment at the top of docs/research/healthy_baseline_study.txt.
ORDER_A = ["reaction", "reaction", "mirror", "rhythm", "echo",
           "force_pilot", "chords", "buzz_hunt", "pattern",
           "adaptive", "syllables"]
ORDER_B = ["force_pilot", "chords", "buzz_hunt", "adaptive",
           "syllables", "reaction", "reaction", "mirror", "rhythm",
           "echo", "pattern"]
N_STEPS = 11
# With one pass there is nothing left for the phase word to separate,
# so every step carries the same one. A test that finds pre, mid or
# post here means the two-visit design has crept back in.
PHASE = "battery"
PHASES = [PHASE] * N_STEPS
BUDGET_MIN = 45.0
HARD_STOP_MIN = 50.0
BATTERY_ID = "healthy_one_pass_v1"


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
            self.assertEqual(plan.id, BATTERY_ID)
            self.assertEqual(len(plan.steps), N_STEPS)
            self.assertEqual([s.phase for s in plan.steps], PHASES, code)
            hand1 = next(s for s in plan.steps
                         if s.hand_requested == "hand1")
            hand2 = next(s for s in plan.steps
                         if s.hand_requested == "hand2")
            self.assertEqual(hand1.hand, first, code)
            self.assertNotEqual(hand1.hand, hand2.hand)
            for s in plan.steps:
                if s.hand_requested == "both":
                    self.assertEqual(s.hand, "both")
            self.assertEqual([s.position for s in plan.steps],
                             list(range(1, N_STEPS + 1)))
            # All ten modes, and no mode played twice except reaction,
            # whose two goes are the two hands.
            modes = [s.mode for s in plan.steps]
            self.assertEqual(len(set(modes)), 10, code)
            twice = [m for m in set(modes) if modes.count(m) > 1]
            self.assertEqual(twice, ["reaction"], code)
            self.assertEqual({s.hand for s in plan.steps
                              if s.mode == "reaction"},
                             {"left", "right"}, code)

    def test_both_orders_play_the_same_eleven_blocks(self) -> None:
        """Counterbalancing moves a mode's position in the sitting and
        nothing else: the same eleven blocks on the same hands, so no
        cell gets more or less of anything than another."""
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        a = build_plan(cfg, "P01", "right")
        b = build_plan(cfg, "P02", "right")
        self.assertEqual(sorted(s.mode for s in a.steps),
                         sorted(s.mode for s in b.steps))
        self.assertEqual(sorted((s.mode, s.hand) for s in a.steps),
                         sorted((s.mode, s.hand) for s in b.steps))
        self.assertNotEqual([s.mode for s in a.steps],
                            [s.mode for s in b.steps])

    def test_hands_follow_the_dominant_hand(self) -> None:
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        plan = build_plan(cfg, "P03", "left")   # non-dominant first
        hand1 = next(s for s in plan.steps if s.hand_requested == "hand1")
        self.assertEqual(hand1.hand, "right")
        # A step asking for the dominant hand gets it whichever way
        # the counterbalanced pair went.
        pattern = next(s for s in plan.steps if s.mode == "pattern")
        self.assertEqual(pattern.hand, "left")
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
                         ["chords"])
        self.assertEqual(a.stretch_s, 60.0)
        self.assertEqual(a.budget_min, BUDGET_MIN)
        self.assertEqual(a.hard_stop_min, HARD_STOP_MIN)
        # About a third of the way in by measured minutes: before the
        # sixth block in A, before the second in B (which is straight
        # off Force Pilot's seven minutes of sustained holding).
        self.assertEqual([s.position for s in a.steps
                          if s.stretch_before_s], [6])
        self.assertEqual([s.position for s in b.steps
                          if s.stretch_before_s], [2])

    def test_one_rest_sits_halfway_through_the_sitting(self) -> None:
        """One pass, one rest, about halfway by measured minutes in
        both orders. The rest holds the button for its floor and
        counts down to its full length."""
        from finger_rehab.game.battery import build_plan
        cfg = self._cfg()
        for code, position, mode in (("P01", 7, "chords"),
                                     ("P02", 6, "reaction")):
            plan = build_plan(cfg, code, "right")
            rests = [s for s in plan.steps if s.rest_before_s]
            self.assertEqual([s.position for s in rests], [position], code)
            self.assertEqual([s.mode for s in rests], [mode], code)
            for s in rests:
                self.assertEqual(s.rest_before_s, 180.0)
                self.assertEqual(s.rest_min_s, 60.0)
                # A rest and a stretch on one card would be two
                # countdowns; the rest wins.
                self.assertEqual(s.stretch_before_s, 0.0)
            self.assertEqual(plan.rest_s, 180.0)
            self.assertEqual(plan.rest_min_s, 60.0)

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
        self.assertIn("main hand", str(ctx.exception))

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
            "force_pilot.passes",
            "chords.subblocks", "chords.trials_per_subblock",
            "chords.sync_windows_ms",
            "buzz_hunt.loc_trials_per_hand",
            "buzz_hunt.distractor_trials_per_hand",
            "buzz_hunt.span_trials", "buzz_hunt.gap_trials_per_hand",
            "buzz_hunt.catch_rate",
            "pattern.short_session", "pattern.soc_cycles_per_block",
            "pattern.random_block_trials",
            "rhythm.difficulty",
            "echo.games", "echo.max_len",
            "syllables.rung", "syllables.words_per_block",
            "syllables.round_size", "syllables.break_s",
            "game.total_trials",
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
            "chords": {"subblocks": 3}})
        self.assertEqual(data["reaction"]["block_trials"], 10)
        self.assertEqual(data["reaction"]["response_windows_s"], [2.0])
        self.assertEqual(data["reaction"]["lapse_ms"], 500)
        self.assertTrue(data["reaction"]["brand_new"])
        self.assertEqual(data["chords"], {"subblocks": 3})
        restore_overrides(data, snap)
        self.assertEqual(data["reaction"], {
            "block_trials": 25, "response_windows_s": [2.0, 1.5, 1.2],
            "lapse_ms": 500})
        self.assertEqual(data["chords"], {})
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
        for _ in range(N_STEPS * 2):
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
                         ["right", "left", "both", "both", "both", "both",
                          "both", "both", "right", "right", "both"])

    def test_even_code_runs_order_b_non_dominant_first(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P04", "right")
        played = self._run_battery(eng)
        self.assertEqual([m for m, _h, _f in played], ORDER_B)
        self.assertEqual([h for _m, h, _f in played],
                         ["both", "both", "both", "right", "both", "left",
                          "right", "both", "both", "both", "right"])

    def test_left_dominant_flips_the_hands(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P02", "left")     # B, dominant first
        played = self._run_battery(eng)
        self.assertEqual([m for m, _h, _f in played], ORDER_B)
        # The two reaction blocks, dominant hand first.
        self.assertEqual([h for _m, h, _f in played][5:7], ["left", "right"])
        # And pattern, which asks for the dominant hand by name.
        self.assertEqual(played[-1][1], "left")

    def test_every_block_carries_the_battery_stamp(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P03", "right")
        played = self._run_battery(eng)
        self.assertEqual(len(played), N_STEPS)
        for pos, (mode, hand, folder) in enumerate(played, start=1):
            meta = json.loads((folder / "metadata.json").read_text(
                encoding="utf-8"))
            bat = meta["battery"]
            self.assertEqual(bat["id"], BATTERY_ID, mode)
            self.assertEqual(bat["position"], pos, mode)
            self.assertEqual(bat["of"], N_STEPS)
            self.assertEqual(bat["phase"], PHASES[pos - 1], mode)
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
            self.assertEqual(snap["force_pilot"]["passes"], 1)
            self.assertEqual(snap["syllables"]["words_per_block"], 12)
        # And the trial CSV phase column names the battery.
        self.assertEqual(eng._current_phase, "")
        progress = eng.battery_progress()
        self.assertTrue(progress["finished"])
        self.assertEqual(progress["done"], N_STEPS)
        self.assertEqual(progress["budget_min"], BUDGET_MIN)
        self.assertEqual(progress["hard_stop_min"], HARD_STOP_MIN)
        self.assertEqual([r["status"] for r in progress["log"]],
                         ["completed"] * N_STEPS)
        self.assertEqual([r["battery_pos"] for r in eng.session_games_log()],
                         list(range(1, N_STEPS + 1)))
        self.assertEqual([r["phase"] for r in eng.session_games_log()],
                         PHASES)

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
        self.assertEqual(eng.cfg.get("syllables.words_per_block"), 40)
        self.assertEqual(eng.cfg.get("syllables.rung"), 1)
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
        for _ in range(N_STEPS * 2):
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
        for _ in range(N_STEPS * 2):
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
        self.assertEqual(m.total_trials, 20)
        # Scoring is untouched.
        self.assertEqual(eng.score_cfg.perfect_ms, 100)

    def test_force_pilot_flies_the_whole_wave_ladder(self) -> None:
        # Nothing to freeze any more: the ladder is fixed by design,
        # so the battery runs it once, both hands, 24 runs.
        self._stub_rhythm()
        eng = self._engine(_Rig())
        self._login(eng, "P01", "right")
        eng.start_battery()
        fp = self._step_to(eng, "force_pilot")
        self.assertEqual(fp.passes, 1)
        self.assertEqual([w.lvl for w in fp.levels], list(range(1, 13)))
        self.assertEqual(fp.total_runs, 24)     # 12 levels x two hands

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
        self.assertEqual(plan.count("loc"), 24)    # 12 per hand, both
        self.assertEqual(plan.count("span"), 4)
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
        self.assertEqual(label, "PLAY ALL  (A)")
        # A starts it from the hub.
        eng.show_mode_select()
        hub.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_a, "mod": 0, "unicode": "a",
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
        self.assertEqual(heading, "PLAY ALL  step 2 of 11")
        self.assertEqual(pill, "Play all step 2, hand 2")
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
        self.assertEqual(label, "PLAY ALL 2/11  (A)")
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
        self.assertIn("step 6 of 11", heading)
        self.assertIn("Stretch", stretch)

    def test_without_a_main_hand_the_hub_says_why(self) -> None:
        eng = self._engine(_Rig())
        eng.begin_session("Mara", "40")
        ok, reason = eng.battery_available()
        self.assertFalse(ok)
        self.assertEqual(reason,
                         "Play all needs a main hand: pick one at login")
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
# 2b. the two scheduled rests, and the session-so-far row
# ---------------------------------------------------------------------
class RestStepTests(_BatteryHarness):
    """A rest is not a stretch. The stretch about a third of the way
    in is a suggestion and never locks anything; the one rest is what
    separates the halves of the sitting, so the card holds the button
    for the floor and the length actually taken is logged. A shortened
    rest changes what the block after it means, which is why the
    length taken goes into the record and not just the length
    offered."""

    def _advance_to(self, eng, position: int) -> dict:
        for _ in range(N_STEPS * 2):
            if eng.block_is_running():
                eng.finish_block()
            step = eng.pending_protocol_step()
            if step is None:
                break
            if int(step["position"]) == position:
                return step
            eng.continue_protocol()
        self.fail(f"battery never waited at step {position}")

    def _at_rest(self, eng):
        self._stub_rhythm()
        self._login(eng, "P01", "right")
        eng.start_battery()
        step = self._advance_to(eng, 7)
        self.assertEqual(step["mode"], "chords")
        self.assertEqual(step["rest_s"], 180.0)
        self.assertEqual(step["rest_min_s"], 60.0)
        return step, eng._screens["results"]

    def test_the_rest_card_counts_down_and_holds_the_button(self) -> None:
        eng = self._engine(_Rig())
        step, results = self._at_rest(eng)
        heading = ""
        for elapsed, line, held in ((0.0, "Rest: 3:00 left", True),
                                    (30.0, "Rest: 2:30 left", True),
                                    (90.0, "Rest: 1:30 left", False),
                                    (200.0, "Rest done", False)):
            eng._step_card_t = time.perf_counter() - elapsed
            heading, _pill, wait = results._battery_card_lines(step)
            self.assertEqual(wait, line)
            self.assertEqual(results._rest_lock(step)[0], held)
        self.assertIn("step 7 of 11", heading)

    def test_n_is_refused_until_the_floor_then_starts_early(self) -> None:
        import pygame
        eng = self._engine(_Rig())
        step, results = self._at_rest(eng)
        press = pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_n, "mod": 0, "unicode": "n",
                             "scancode": 0})
        eng._step_card_t = time.perf_counter() - 5.0
        results.draw(pygame.Surface((1280, 800)))
        self.assertEqual(results.next_btn.label, "Rest: 2:55")
        results.handle_event(press)
        self.assertFalse(eng.block_is_running())
        self.assertEqual(eng.pending_protocol_step()["position"], 7)
        # Past the floor the button comes back and says the rest can
        # be cut short.
        eng._step_card_t = time.perf_counter() - 70.0
        results.draw(pygame.Surface((1280, 800)))
        self.assertTrue(results.next_btn.label.startswith("Start now"))
        results.handle_event(press)
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng.current_block, "chords")

    def test_the_rest_actually_taken_is_logged(self) -> None:
        eng = self._engine(_Rig())
        step, _results = self._at_rest(eng)
        eng._step_card_t = time.perf_counter() - 95.0
        eng.continue_protocol()
        folder = Path(eng.session_paths.root)
        eng.finish_block()
        entry = next(r for r in eng.battery_progress()["log"]
                     if r["position"] == 7)
        self.assertEqual(entry["rest_s"], 180.0)
        self.assertGreaterEqual(entry["rest_taken_s"], 95.0)
        self.assertLess(entry["rest_taken_s"], 120.0)
        meta = json.loads((folder / "metadata.json").read_text(
            encoding="utf-8"))
        self.assertGreaterEqual(meta["battery"]["rest_before_s"], 95.0)
        # A step with no rest carries no rest key at all, rather than
        # a zero that reads like a rest of no length.
        first = next(r for r in eng.battery_progress()["log"]
                     if r["position"] == 1)
        self.assertEqual(first["rest_taken_s"], 0.0)


class ProgressRowTests(unittest.TestCase):
    """game/battery.progress_rows: this session's first go against its
    latest, per mode and hand. Pure over the engine's session log, so
    no screen and no sessions tree.

    One pass plays each mode and hand ONCE, so inside the battery
    every row here is a single go with nothing to compare against.
    The two-go rows below are what happens when the RA replays a mode
    freely from the hub after the battery, which is the only way a
    second go at the same task now happens in a sitting. Phase words
    say which: `battery` for the battery block, `free` for the replay.
    """

    @staticmethod
    def _reaction(ms: float) -> dict:
        return {"block": "reaction", "status": "completed",
                "reaction": {"median_rt_ms": ms}}

    @staticmethod
    def _force(frac: float) -> dict:
        return {"block": "force_pilot", "status": "completed",
                "force_pilot": {"overall": {"time_in_corridor": frac}}}

    def _rows(self, log):
        from finger_rehab.game.battery import progress_rows
        return {(r["mode"], r["hand"]): r for r in progress_rows(log)}

    def test_first_against_latest_in_the_modes_own_words(self) -> None:
        rows = self._rows([
            {"mode": "reaction", "hand": "right", "status": "completed",
             "phase": "battery", "summary": self._reaction(312.0)},
            {"mode": "force_pilot", "hand": "both", "status": "completed",
             "phase": "battery", "summary": self._force(0.82)},
            # An abandoned block is not a result to be measured against.
            {"mode": "reaction", "hand": "right", "status": "abandoned",
             "phase": "free", "summary": self._reaction(999.0)},
            {"mode": "reaction", "hand": "left", "status": "completed",
             "phase": "battery", "summary": self._reaction(331.0)},
            {"mode": "reaction", "hand": "right", "status": "completed",
             "phase": "free", "summary": self._reaction(290.0)},
            {"mode": "force_pilot", "hand": "both", "status": "completed",
             "phase": "free", "summary": self._force(0.89)},
        ])
        rx = rows[("reaction", "right")]
        self.assertEqual((rx["n"], rx["first"], rx["latest"]),
                         (2, 312.0, 290.0))
        self.assertTrue(rx["better"])
        self.assertEqual(rx["text"], "22 ms faster than your first go")
        self.assertEqual(rx["short"], "22 ms faster")
        fp = rows[("force_pilot", "both")]
        self.assertEqual(fp["text"], "7% steadier than your first go")
        self.assertEqual(fp["short"], "7% steadier")
        # The two hands never mix, and a mode played once says so by
        # having nothing to say.
        left = rows[("reaction", "left")]
        self.assertEqual((left["n"], left["text"], left["better"]),
                         (1, "", None))

    def test_a_change_too_small_to_print_is_about_the_same(self) -> None:
        rows = self._rows([
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": self._reaction(300.0)},
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": self._reaction(300.2)},
        ])
        rx = rows[("reaction", "right")]
        self.assertEqual(rx["text"], "about the same as your first go")
        self.assertEqual(rx["short"], "about the same")
        self.assertIsNone(rx["better"])

    def test_every_mode_with_a_chip_has_a_unit_to_print(self) -> None:
        """The wording lives in data/history, the unit in battery. If a
        mode gains a chip and no unit, the panel would print a bare
        number, so the two tables are pinned together."""
        from finger_rehab.data import history
        from finger_rehab.game.battery import PROGRESS_UNITS, value_text
        self.assertEqual(set(PROGRESS_UNITS), set(history._RULES))
        self.assertEqual(value_text("reaction", 290.4), "290 ms")
        self.assertEqual(value_text("force_pilot", 0.894), "89%")
        self.assertEqual(value_text("echo", 7), "7")
        self.assertEqual(value_text("adaptive", 160.0), "160 BPM")
        self.assertEqual(value_text("reaction", None), "")

    def test_a_second_go_that_came_in_under_is_said_plainly(self) -> None:
        rows = self._rows([
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": self._reaction(290.0)},
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": self._reaction(312.0)},
        ])
        rx = rows[("reaction", "right")]
        self.assertFalse(rx["better"])
        # The direction, not a verdict on the round.
        self.assertEqual(rx["short"], "22 ms behind")


class ProgressStripTests(_BatteryHarness):
    """The row the participant reads on the results screen."""

    def _screen(self, log):
        eng = self._engine(_Rig())
        eng._session_log = log
        results = eng._screens["results"]
        results.on_show()
        return eng, results

    def test_the_row_leads_with_the_mode_just_played(self) -> None:
        import pygame
        log = [
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": ProgressRowTests._reaction(312.0)},
            {"mode": "force_pilot", "hand": "both", "status": "completed",
             "summary": ProgressRowTests._force(0.82)},
            {"mode": "force_pilot", "hand": "both", "status": "completed",
             "summary": ProgressRowTests._force(0.89)},
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": ProgressRowTests._reaction(290.0)},
        ]
        eng, results = self._screen(log)
        eng.current_block = "reaction"
        eng.hand_mode = "right"
        here = results._progress_row_for("reaction", "right")
        self.assertEqual(here["text"], "22 ms faster than your first go")
        self.assertEqual(results._progress_colour(here["better"]),
                         results.theme.success)
        other = results._progress_row_for("force_pilot", "both")
        self.assertEqual(other["short"], "7% steadier")
        self.assertEqual(results._progress_label("reaction", "right"),
                         "Reaction R")
        self.assertEqual(results._progress_label("force_pilot", "both"),
                         "Force Pilot")
        # And it draws, at the shipped size and at the smallest one.
        results.draw(pygame.Surface((1280, 800)))
        results.draw(pygame.Surface((1024, 700)))

    def test_no_second_go_means_no_row(self) -> None:
        import pygame
        eng, results = self._screen([
            {"mode": "reaction", "hand": "right", "status": "completed",
             "summary": ProgressRowTests._reaction(312.0)}])
        eng.current_block = "reaction"
        eng.hand_mode = "right"
        row = results._progress_row_for("reaction", "right")
        self.assertEqual(row["n"], 1)
        self.assertEqual(row["text"], "")
        results.draw(pygame.Surface((1280, 800)))

    def test_play_all_done_turns_the_card_into_todays_table(self) -> None:
        import pygame
        log = [
            {"mode": "reaction", "hand": "right", "status": "completed",
             "battery_pos": 1,
             "summary": ProgressRowTests._reaction(312.0)},
            {"mode": "reaction", "hand": "right", "status": "completed",
             "battery_pos": 11,
             "summary": ProgressRowTests._reaction(290.0)},
        ]
        eng, results = self._screen(log)
        eng.current_block = "reaction"
        eng.hand_mode = "right"
        # No battery: the card is the ordinary NEXT UP suggestion.
        self.assertFalse(results._battery_done())
        eng._battery = {"id": "x", "cell": {}, "of": 2, "done": True,
                        "log": [], "budget_min": BUDGET_MIN,
                        "hard_stop_min": HARD_STOP_MIN,
                        "started_perf": 0.0}
        self.assertTrue(results._battery_done())
        results.draw(pygame.Surface((1280, 800)))
        # A free game after PLAY ALL is an ordinary game again.
        eng._session_log = log + [
            {"mode": "echo", "hand": "both", "status": "completed",
             "battery_pos": 0, "summary": None}]
        self.assertFalse(results._battery_done())

    def test_an_empty_session_still_draws(self) -> None:
        import pygame
        eng, results = self._screen([])
        eng.current_block = "reaction"
        self.assertEqual(results._progress(), [])
        results.draw(pygame.Surface((1280, 800)))


# ---------------------------------------------------------------------
# 3. a keyboard rig
# ---------------------------------------------------------------------
class KeyboardRigTests(_BatteryHarness):
    def test_hardware_steps_are_skipped_and_said(self) -> None:
        self._stub_rhythm()
        eng = self._engine()          # KeyboardOnlySource
        self._login(eng, "P01", "right")
        played = self._run_battery(eng)
        # Chords plays on the keys; the two sensor modes do not, so
        # a keyboard rig gets nine of the eleven blocks.
        self.assertEqual([m for m, _h, _f in played],
                         [m for m in ORDER_A
                          if m not in ("force_pilot", "buzz_hunt")])
        log = eng.battery_progress()["log"]
        skipped = [(r["mode"], r["reason"]) for r in log
                   if r["status"] == "skipped"]
        self.assertEqual(skipped, [
            ("force_pilot", "needs sensor hardware"),
            ("buzz_hunt", "needs sensor hardware")])
        self.assertTrue(eng.battery_progress()["finished"])
        # Position numbering is the design's, skips included.
        meta = json.loads((played[-1][2] / "metadata.json").read_text(
            encoding="utf-8"))
        self.assertEqual(meta["battery"]["position"], N_STEPS)
        self.assertEqual(meta["battery"]["phase"], PHASE)


class HandoverProseTests(unittest.TestCase):
    """battery.py's docstring and the preset's comment are the two
    pieces of prose a handover reader opens first. A bad edit once
    left both half-replaced: a cross-reference doubled onto itself and
    a sentence that started mid-word. Neither changes behaviour, which
    is exactly why nothing caught it.
    """

    def _texts(self):
        from finger_rehab.game import battery
        yaml_text = (Path(__file__).resolve().parents[1]
                     / "config" / "default.yaml").read_text(
                         encoding="utf-8")
        start = yaml_text.index("  # The study_battery preset")
        end = yaml_text.index("  presets:", start)
        comment = yaml_text[start:end].replace("#", " ")
        return {"battery.py docstring": battery.__doc__,
                "default.yaml preset comment": comment}

    def test_the_cross_reference_is_one_sentence(self) -> None:
        for where, text in self._texts().items():
            flat = " ".join(text.split())
            with self.subTest(where=where):
                self.assertIn("Section 1 of that document", flat)
                self.assertIn("Sections 2 to 5 are written for", flat)
                # The half-replaced form, and the doubled clause it
                # ran into.
                self.assertNotIn("Sections 2, 4", flat)
                self.assertEqual(flat.count("Sections 2 to 5"), 1)

    def test_the_docstring_sentence_is_whole(self) -> None:
        from finger_rehab.game import battery
        flat = " ".join((battery.__doc__ or "").split())
        self.assertIn("Nothing in this module knows about passes or "
                      "phases", flat)
        self.assertNotIn("this one-pass design. module knows", flat)


if __name__ == "__main__":
    unittest.main()
