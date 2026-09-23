"""The study-day workflow on a real rig, one participant, Play all
from login to the last block. The study rig is one board (the
right-hand device); the two-board cases stay covered because the app
still supports that rig.

Found by reading the path end to end after a run on the real board
(23 September 2026). Each class is one way a sitting could produce
wrong data or lose a step without anyone noticing:

  1. A one-hand block on a two-board rig buzzed the right board for the
     left hand, and took the resting hand's presses as its own.
  2. Play all on one board skipped every two-hand step and ran the
     other hand's steps on the board that was there. A one-hand plan
     now runs on the one board, renamed to the plan's hand; a plan
     that needs a second board says which.
  3. A step whose board had dropped started anyway; a board gone for
     good skipped every later two-hand step.
  4. A step that never opened its block (a question dismissed, a
     calibration abandoned) was used up.
  5. An abandoned calibration left the last person's saved profile in
     use for the rest of the battery.
  6. A free pick mid-battery wrote "battery" in its phase column, the S
     key dropped a step with no question, and the hub walked round the
     scheduled rest.
  7. A relaunch mid-sitting started the battery again at step 1.
  8. A lone board replugged on a new port name came back as the wrong
     hand, with its old label stuck as down.
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_study_battery import BATTERY_ID, _BatteryHarness, _Rig  # noqa: E402


class _OneBoard(_Rig):
    """One board, labelled the way plug order or the login named it."""
    name = "fake-one-board"

    def __init__(self, hand: str = "right") -> None:
        super().__init__()
        self.hands[0].hand = hand


class _TwoBoards(_Rig):
    def __init__(self) -> None:
        super().__init__()
        self.hands = [SimpleNamespace(hand="right", port="/dev/fake0"),
                      SimpleNamespace(hand="left", port="/dev/fake1")]


def _key(k: int, ch: str):
    import pygame
    return pygame.event.Event(pygame.KEYDOWN, {"key": k, "mod": 0,
                                               "unicode": ch,
                                               "scancode": 0})


# ---------------------------------------------------------------------
# 1. one-hand blocks on two boards
# ---------------------------------------------------------------------
class OneHandBlocksOnTwoBoards(_BatteryHarness):

    def test_a_left_hand_buzz_goes_to_the_left_board(self) -> None:
        rig = _TwoBoards()
        eng = self._engine(rig)
        eng.set_hand_mode("left")
        rig.commands.clear()
        self.assertTrue(eng._send_stim(2))
        self.assertEqual(rig.commands[-1], "LEFT:STIM:3")
        eng._scoped_stop("left")
        self.assertEqual(rig.commands[-1], "LEFT:STOP")
        eng.set_hand_mode("right")
        eng._send_stim(0)
        self.assertEqual(rig.commands[-1], "RIGHT:STIM:1")

    def test_bilateral_and_one_board_commands_are_unchanged(self) -> None:
        rig = _TwoBoards()
        eng = self._engine(rig)
        eng.set_hand_mode("both")
        eng._send_stim(5)
        # Global lane, split by the board router.
        self.assertEqual(rig.commands[-1], "STIM:6")
        one = _OneBoard("left")
        eng2 = self._engine(one)
        eng2.set_hand_mode("left")
        eng2._send_stim(1)
        self.assertEqual(one.commands[-1], "STIM:2")

    def test_the_resting_hand_is_not_the_playing_hand(self) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        eng = self._engine(_TwoBoards())
        eng.set_hand_mode("both")       # both detectors built
        eng.set_hand_mode("right")
        seen = []
        eng.mode = SimpleNamespace(queue_press=seen.append)
        eng._on_press(PressEvent(lane=2, t_perf=1.0, value=500,
                                 baseline=300.0, hand="left"))
        self.assertEqual(seen, [])
        eng._on_press(PressEvent(lane=2, t_perf=1.1, value=500,
                                 baseline=300.0, hand="right"))
        self.assertEqual([e.lane for e in seen], [2])
        eng.set_hand_mode("both")
        eng._on_press(PressEvent(lane=2, t_perf=1.2, value=500,
                                 baseline=300.0, hand="left"))
        self.assertEqual(seen[-1].lane, 6)


# ---------------------------------------------------------------------
# 2. one board
# ---------------------------------------------------------------------
class PlayAllAndTheBoards(_BatteryHarness):

    def test_the_one_board_plan_runs_on_one_board(self) -> None:
        for rig in (_OneBoard("right"), _OneBoard("left"), _TwoBoards()):
            eng = self._engine(rig)
            self._login(eng, "P02", "right")
            self.assertEqual(eng.battery_available(), (True, ""),
                             rig.hands)

    def test_a_two_hand_plan_on_one_board_says_which_is_missing(
            self) -> None:
        eng = self._engine(_OneBoard("right"))
        pre = eng.cfg.data["protocol"]["presets"]["study_battery"]
        pre["orders"] = {k: [{"mode": "reaction", "hand": "right",
                              "phase": "pass1"},
                             {"mode": "mirror", "hand": "both",
                              "phase": "pass1"}]
                         for k in ("A", "B")}
        self._login(eng, "P02", "right")
        ok, why = eng.battery_available()
        self.assertFalse(ok)
        self.assertIn("left board", why)
        self.assertFalse(eng.start_battery())
        self.assertIsNone(eng.battery_progress())
        hub = eng._screens["mode_select"]
        self.assertEqual(hub._battery_state(),
                         (False, "Play all", why))


# ---------------------------------------------------------------------
# 3. a board down between blocks
# ---------------------------------------------------------------------
class AStepWaitsForItsBoard(_BatteryHarness):

    def test_the_step_waits_and_is_not_used_up(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_OneBoard("right"))
        self._login(eng, "P01", "right")
        self.assertTrue(eng.start_battery())
        self.assertEqual(eng.current_block, "reaction")
        eng.finish_block()
        pending = eng.pending_protocol_step()
        self.assertEqual((pending["mode"], pending["position"]),
                         ("rhythm", 2))
        eng._hands_down = {"right"}
        self.assertFalse(eng.continue_protocol())
        self.assertFalse(eng.block_is_running())
        self.assertEqual(eng.pending_protocol_step()["position"], 2)
        self.assertIn("Right board not connected", eng.battery_wait_line())
        self.assertEqual([r["status"] for r in
                          eng.battery_progress()["log"]], ["completed"])
        # The card says so rather than offering a start.
        import pygame
        results = eng._screens["results"]
        results.draw(pygame.Surface((1280, 800)))
        self.assertEqual(results.next_btn.label, "Waiting for the board")
        # Board back: the same step runs.
        eng._hands_down = set()
        self.assertEqual(eng.battery_wait_line(), "")
        self.assertTrue(eng.continue_protocol())
        self.assertEqual((eng.current_block, eng.hand_mode),
                         ("rhythm", "right"))
        self.assertEqual(eng.session.battery["position"], 2)

    def test_a_board_gone_from_the_rig_waits_too(self) -> None:
        # A rebuild that comes back with no board used to read as a
        # rig that could not run the step, and skipped it.
        self._stub_rhythm()
        rig = _OneBoard("right")
        eng = self._engine(rig)
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        rig.hands = []
        self.assertFalse(eng.continue_protocol())
        pending = eng.pending_protocol_step()
        self.assertEqual((pending["mode"], pending["position"]),
                         ("rhythm", 2))
        self.assertNotIn("skipped", [r["status"] for r in
                                     eng.battery_progress()["log"]])


# ---------------------------------------------------------------------
# 4. a launched step that never opened
# ---------------------------------------------------------------------
class ALaunchThatNeverOpenedIsHandedBack(_BatteryHarness):

    def test_dismissing_the_uncalibrated_question_keeps_the_step(self):
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        eng.cfg.data.setdefault("quick_cal", {})["enabled"] = False
        eng._uncal_ack = set()
        eng.calibration_profiles = {}
        eng._usable_saved_profile = lambda hand: None
        eng.show_mode_select()
        self.assertTrue(eng.start_battery())
        self.assertIsNotNone(eng._exit_confirm)     # the question
        self.assertFalse(eng.block_is_running())
        eng._handle_escape()                        # dismissed
        self.assertIsNone(eng._exit_confirm)
        pending = eng.pending_protocol_step()
        self.assertEqual((pending["mode"], pending["position"]),
                         ("reaction", 1))
        # Play anyway on the second go, and it is position 1.
        eng.continue_protocol()
        eng._exit_confirm.danger_btn.on_click()
        self.assertTrue(eng.block_is_running())
        self.assertEqual(eng.session.battery["position"], 1)

    def test_a_different_game_opened_instead_hands_the_step_back(self):
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        # Launched, then something else opens before it (a pick from
        # the hand picker after a refusal).
        eng._protocol_launch_idx = eng._protocol_index
        eng._protocol_index += 1
        eng._protocol_current = eng._protocol_steps[
            eng._protocol_launch_idx]
        eng.begin_game("echo", "right")
        self.assertEqual(eng.session.battery, {})
        eng.finish_block()
        self.assertEqual(eng.pending_protocol_step()["position"], 2)


# ---------------------------------------------------------------------
# 5. calibration
# ---------------------------------------------------------------------
class AnAbandonedCalibrationIsOfferedAgain(_BatteryHarness):

    def test_the_next_step_offers_it_again(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        offers: list[list[str]] = []

        def offer(cb, hands=None):
            offers.append(list(hands or []))
            eng._pending_cal_cb = cb
            return True

        eng.maybe_start_quick_calibration = offer
        eng._uncal_ack = set()
        self.assertTrue(eng.start_battery())
        self.assertEqual(offers, [["right"]])
        # Abandoned: the callback never runs. Continuing offers the
        # hand again instead of playing on whatever profile was
        # lying about.
        eng.show_mode_select()
        eng.start_battery()
        self.assertEqual(offers[-1], ["right"])
        self.assertFalse(eng.block_is_running())
        # Finished this time: the step starts. (The stubbed flow
        # measures nothing, so the uncalibrated question is kept out
        # of the way.)
        eng._warn_uncalibrated = lambda hand, start: False
        eng._pending_cal_cb()
        self.assertEqual((eng.current_block, eng.hand_mode),
                         ("reaction", "right"))
        # Once finished, later steps do not ask again.
        n = len(offers)
        eng.finish_block()
        eng.continue_protocol()
        self.assertEqual(eng.current_block, "rhythm")
        self.assertEqual(len(offers), n)


# ---------------------------------------------------------------------
# 6. labels and the hub
# ---------------------------------------------------------------------
class FreePicksSkipsAndRests(_BatteryHarness):

    def test_a_free_pick_mid_battery_has_no_phase(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        eng.start_battery()
        self.assertEqual(eng._current_phase, "pass1")
        eng.finish_block()
        eng.begin_game("echo", "right")
        self.assertEqual(eng._current_phase, "")
        eng.finish_block()
        eng.continue_protocol()
        self.assertEqual(eng._current_phase, "pass1")

    def test_s_asks_before_skipping(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        eng.start_battery()
        eng.finish_block()
        eng.show_mode_select()
        hub = eng._screens["mode_select"]
        import pygame
        hub.handle_event(_key(pygame.K_s, "s"))
        self.assertIsNotNone(eng._exit_confirm)
        self.assertEqual(eng.pending_protocol_step()["position"], 2)
        eng._handle_escape()                    # kept
        self.assertEqual(eng.pending_protocol_step()["position"], 2)
        hub.handle_event(_key(pygame.K_s, "s"))
        eng._exit_confirm.danger_btn.on_click()           # skipped on purpose
        self.assertEqual(eng.pending_protocol_step()["position"], 3)
        self.assertEqual(eng.battery_progress()["log"][-1]["reason"],
                         "skipped by researcher")

    def test_the_hub_keeps_the_rest_floor(self) -> None:
        self._stub_rhythm()
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        eng.start_battery()
        # Put the pending step behind a rest that started just now.
        eng.finish_block()
        step = eng._protocol_steps[eng._protocol_index]
        step["rest_s"], step["rest_min_s"] = 180.0, 60.0
        eng._step_card_t = time.perf_counter()
        held, left = eng.battery_rest_hold()
        self.assertTrue(held)
        self.assertGreater(left, 170)
        hub = eng._screens["mode_select"]
        eng.show_mode_select()
        hub._battery()
        self.assertFalse(eng.block_is_running())
        self.assertTrue(hub._battery_live_line().startswith("Rest: "))
        eng._step_card_t = time.perf_counter() - 61
        hub._battery()
        self.assertTrue(eng.block_is_running())


# ---------------------------------------------------------------------
# 7. a relaunch mid-sitting
# ---------------------------------------------------------------------
class ARelaunchPicksUpWhereTheSittingWas(_BatteryHarness):

    def _done_block(self, name: str, position: int, step: str,
                    status: str = "completed", code: str = "P01") -> Path:
        day = self.root / time.strftime("%Y-%m-%d") / name
        day.mkdir(parents=True)
        (day / "metadata.json").write_text(json.dumps({
            "participant": code,
            "battery": {"id": BATTERY_ID, "position": position,
                        "step": step},
            "block_summary": {"status": status},
        }), encoding="utf-8")
        return day

    def test_steps_done_earlier_today_are_not_played_again(self) -> None:
        self._stub_rhythm()
        first = self._done_block("P01_090000_reaction", 1, "reaction_right")
        self._done_block("P01_090100_rhythm", 2, "rhythm_right",
                         status="abandoned")
        self._done_block("P09_090200_rhythm", 2, "rhythm_right",
                         code="P09")
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        self.assertTrue(eng.start_battery())
        # Position 1 is done; the abandoned and the other code's
        # blocks are not this sitting's.
        self.assertEqual((eng.current_block, eng.hand_mode),
                         ("rhythm", "right"))
        self.assertEqual(eng.session.battery["position"], 2)
        progress = eng.battery_progress()
        self.assertEqual(progress["done"], 1)
        self.assertEqual(progress["log"][0]["reason"], "earlier today")
        self.assertEqual(progress["log"][0]["folder"], str(first))


# ---------------------------------------------------------------------
# 8. a lone board back on a new port
# ---------------------------------------------------------------------
class ALoneBoardKeepsItsHand(_BatteryHarness):

    def test_a_label_the_rig_no_longer_has_is_not_down(self) -> None:
        eng = self._engine(_OneBoard("right"))
        eng._hands_down = {"left"}
        eng._hand_was_connected = {"left": False}
        eng.source.hands_connected = {"right": True}
        eng._check_per_hand_connection()
        self.assertEqual(eng._hands_down, set())

    def test_the_rebuild_puts_the_session_hand_back(self) -> None:
        eng = self._engine(_OneBoard("left"))
        eng._session_hand = "left"
        fresh = _OneBoard("right")         # plug order named it right

        def rebuild():
            eng.source = fresh
            return "ok"

        eng.reconnect_source = rebuild
        eng._calibrate_joined_hands = lambda hands: self.fail(
            "the same hand came back; nothing to calibrate")
        eng._apply_autoconnect()
        self.assertEqual(fresh.hands[0].hand, "left")


class TheCalibrationScreenNeverStrandsASession(_BatteryHarness):

    def test_a_used_continue_lands_on_the_hub(self) -> None:
        eng = self._engine(_TwoBoards())
        self._login(eng, "P01", "right")
        quick = eng._screens["quick_cal"]
        quick.begin(["right"], lambda: None)
        quick._go_on()
        quick._go_on()                     # the stale button
        self.assertIs(eng.screen_obj, eng._screens["mode_select"])


class TheHandScreenIsLaidOutLikeTheHands(_BatteryHarness):

    def test_left_sits_left_and_right_sits_right(self) -> None:
        for rig, want in ((_OneBoard("right"), ["left", "right"]),
                          (_TwoBoards(), ["left", "both", "right"])):
            eng = self._engine(rig)
            sc = eng._screens["hand_choice"]
            sc.enter()
            self.assertEqual(sc.options, want)
            xs = [b.rect.x for b in sc.buttons]
            self.assertEqual(xs, sorted(xs))


if __name__ == "__main__":
    unittest.main()
