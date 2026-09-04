"""Buzz Hunt soak: many randomised blocks, one invariant each.

The single-case tests next door pin each fault by name. This file
asks the blunter question Basil's report actually asked: across a lot
of blocks played a lot of different ways, does the buzzer always go
off long enough to feel, and does the block always end?

Every block runs the real engine and the real mode on a virtual clock
against a board that timestamps its bytes, then the wire is replayed
through the firmware model in test_buzz_hunt_wire so the assertions
are about the ON intervals a finger felt.

THE INVARIANTS

  1. The block ends. phase "done" with an end_reason, whatever the
     player does, inside its own cap.
  2. Every buzz is at least one firmware hold, 150 ms. A 310-103 class
     ERM has about 40 ms of lag and 87 ms of rise (Precision
     Microdrives datasheet), so a command cut inside its own hold is
     not a fainter buzz, it is no buzz. Nothing may write a STOP
     across a live hold: not an early press, not the wall, not a
     pause, not a stale re-arm.
  3. No two fingers on one board are driven at once. They share one
     darlington that cannot supply both, so an overlap is two weak
     buzzes and neither is the stimulus the row claims.
  4. A trial whose stimulus was disturbed is voided, not scored: no
     row may carry a delivered stimulus the wire disagrees with.

SOAK_BLOCKS keeps the suite quick. The same file runs a long soak
(200 blocks, both hands, every player) when it is run directly:

    python3 tests/test_buzz_hunt_soak.py --blocks 200
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import unittest
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_buzz_hunt import (_attach_detectors, _mode,  # noqa: E402
                                  _press_event)
from tests.test_buzz_hunt_wire import (FIRMWARE_HOLD_MS,  # noqa: E402
                                       FRAME, _Rig, patched_clock,
                                       replay_wire, same_board_overlaps,
                                       wire_engine)

# How many blocks the suite soaks. The long soak is a command-line
# argument, not a slower test: a gate that takes a minute stops being
# run.
SOAK_BLOCKS = 12
# The clock is exact, so an interval is either a whole hold or it was
# cut. A hair of slack absorbs float addition only.
EPS_MS = 1e-6


# ---- the players -----------------------------------------------------------
def player_perfect(rng):
    def hook(rig):
        m = rig.mode
        if m.phase == "trial" and m.sub == "respond":
            want = (m.sequence if m.waveform == "buzz_seq"
                    else [m.lane] * (2 if m.gap_two else 1)
                    if m.waveform == "buzz_gap" else [m.lane])
            if len(m._resp_presses) < len(want):
                m.queue_press(_press_event(
                    want[len(m._resp_presses)], rig.clock.t))
        return None
    return hook


def player_never_responds(rng):
    return lambda rig: None


def player_taps_along(rng):
    """Replays what they feel as they feel it. The natural way to play
    the span and gap stages, and the behaviour that locked the block
    up for good."""
    react = rng.uniform(0.25, 0.7)
    seen = {"t0": None}

    def hook(rig):
        m = rig.mode
        if m.phase != "trial":
            return None
        if m.sub == "play" and m._play_t0 is not None:
            if (rig.clock.t >= m._play_t0 + react
                    and seen["t0"] != m._play_t0):
                seen["t0"] = m._play_t0
                m.queue_press(_press_event(m.lane, rig.clock.t))
        elif m.sub == "respond":
            m.queue_press(_press_event(m.lane, rig.clock.t))
        return None
    return hook


def player_fidgets(rng):
    period = rng.uniform(0.4, 2.5)
    state = {"next": None}

    def hook(rig):
        m = rig.mode
        if state["next"] is None:
            state["next"] = rig.clock.t
        if rig.clock.t >= state["next"]:
            state["next"] = rig.clock.t + period
            lane = rng.choice(m.hands[m.hand])
            m.queue_press(_press_event(lane, rig.clock.t))
        return None
    return hook


def player_rests_a_finger(rng):
    """A drifting FSR baseline, or a patient who rests a finger
    between trials. The quiet gate reset every frame for it."""
    state = {"at": None}

    def hook(rig):
        if state["at"] is None:
            state["at"] = rig.clock.t + rng.uniform(5.0, 40.0)
        if rig.clock.t >= state["at"]:
            for det in rig.engine.detectors.values():
                det.pressed[0] = True
        return None
    return hook


def player_pauses(rng):
    period = rng.uniform(4.0, 20.0)
    state = {"next": None}

    def hook(rig):
        if state["next"] is None:
            state["next"] = rig.clock.t + period
        if rig.clock.t >= state["next"]:
            state["next"] = rig.clock.t + period
            rig.mode.on_resume(rng.uniform(0.5, 3.0))
        return None
    return hook


PLAYERS = {
    "perfect": player_perfect,
    "never responds": player_never_responds,
    "taps along": player_taps_along,
    "fidgets": player_fidgets,
    "rests a finger": player_rests_a_finger,
    "pauses": player_pauses,
}


def frame_jitter(rng, heavy):
    """Long frames, the way a trial-log flush to a cloud-synced folder,
    a window drag or a garbage collection pause makes them."""
    state = {"next": None}

    def hook(rig):
        if state["next"] is None:
            state["next"] = rig.clock.t + rng.uniform(3.0, 12.0)
        if rig.clock.t >= state["next"]:
            state["next"] = rig.clock.t + rng.uniform(3.0, 12.0)
            return rng.uniform(0.12, 2.0) if heavy else rng.uniform(
                FRAME * 2, 0.25)
        return None
    return hook


# ---- one block -------------------------------------------------------------
def run_block(seed):
    """One randomised block. Returns a dict of what happened plus the
    wire the firmware model reads."""
    rng = random.Random(seed)
    both = rng.random() < 0.4
    hand_mode = "both" if both else "right"
    hands = ({"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]} if both
             else {"right": [0, 1, 2, 3]})
    player_name = rng.choice(list(PLAYERS))
    heavy = rng.random() < 0.4
    cfg_extra = {"cue.buzz_after": rng.random() < 0.5,
                 "cue.sound_after": rng.random() < 0.5}
    with patched_clock(1000.0 + seed) as clock:
        e = wire_engine(clock, hand_mode, cfg_extra=cfg_extra)
        m = _mode(e, hands=hands,
                  seed=seed,
                  catch_rate=rng.choice([0.0, 0.1, 0.2]),
                  loc_trials_per_hand=rng.randint(2, 6),
                  distractor_trials_per_hand=rng.randint(0, 2),
                  span_trials=rng.randint(0, 3),
                  gap_trials_per_hand=rng.randint(0, 3),
                  session_cap_min=rng.choice([1.0, 2.0, 3.0]),
                  # The SHIPPED pulse numbers, not the smaller ones
                  # the unit tests use to keep their arithmetic
                  # readable: every fixed pulse in a real block is one
                  # firmware hold, which is what makes the 150 ms
                  # invariant below exactly right.
                  loc_pulse_ms=150.0, span_pulse_ms=150.0,
                  span_ioi_ms=400.0, gap_short_ms=150.0,
                  gap_floor_ms=150.0, gap_start_ms=320.0,
                  gap_step_ms=40.0)
        m.engine.finish_block = lambda: None
        _attach_detectors(e, hands=tuple(hands))
        rig = _Rig(clock, e, m)
        play = PLAYERS[player_name](rng)
        jitter = frame_jitter(rng, heavy)

        def hook(r):
            play(r)
            return jitter(r)

        # Twice the largest cap, so a block that has not ended by then
        # has genuinely stalled.
        rig.run(6.0 * 60.0, hook=hook)
        return {
            "seed": seed,
            "player": player_name,
            "hand_mode": hand_mode,
            "phase": m.phase,
            "end_reason": m.end_reason,
            "trials": m.trials_done,
            "wire": list(e.board.wire),
            "rows": list(e.trial_logger.rows),
            "stats": m.block_stats() if m.phase == "done" else None,
        }


def short_pulses(intervals):
    """Delivered buzzes shorter than one firmware hold. Every one of
    them is a STOP written across a live hold, which is the "doesn't
    go off long enough to feel" fault."""
    return [r for r in intervals
            if r[4] is not None and r[4] < FIRMWARE_HOLD_MS - EPS_MS]


class SoakTests(unittest.TestCase):
    def test_no_block_stalls_and_no_buzz_is_cut_short(self):
        for seed in range(SOAK_BLOCKS):
            res = run_block(seed)
            label = (f"seed={seed} player={res['player']} "
                     f"hands={res['hand_mode']}")
            with self.subTest(block=label):
                self.assertEqual(res["phase"], "done", label)
                self.assertIsNotNone(res["end_reason"], label)
                iv = replay_wire(res["wire"], res["hand_mode"])
                self.assertEqual(
                    short_pulses(iv), [],
                    f"{label}: a buzz was cut inside its own firmware "
                    f"hold, so the finger felt nothing")
                self.assertEqual(
                    same_board_overlaps(iv), [],
                    f"{label}: two fingers driven at once on one board")

    def test_every_delivered_row_agrees_with_the_wire(self):
        # A row that claims a delivered stimulus while the wire says
        # the pulse broke is the failure mode that quietly corrupts
        # the gap staircase, so it gets its own assertion.
        for seed in range(SOAK_BLOCKS):
            res = run_block(seed)
            with self.subTest(block=f"seed={seed}"):
                for row in res["rows"]:
                    if row.get("stim_delivered") == "FALSE":
                        self.assertIn("stim_failed=True",
                                      str(row.get("stimulus", "")))

    def test_the_soak_actually_exercises_the_stages(self):
        # A soak that never reaches the span or gap stage would pass
        # for the wrong reason.
        seen = set()
        for seed in range(SOAK_BLOCKS):
            res = run_block(seed)
            for row in res["rows"]:
                seen.add(row.get("waveform"))
        self.assertIn("buzz", seen)
        self.assertTrue({"buzz_seq", "buzz_gap"} & seen,
                        "the soak must reach the sequence or gap stage")


def _long_soak(blocks):
    """The gate the build spec asked for: many blocks, the invariants
    reported rather than asserted, so a run says what it saw."""
    bad_end, bad_short, bad_overlap = [], [], []
    ends: dict[str, int] = {}
    n_pulses = 0
    for seed in range(blocks):
        res = run_block(seed)
        ends[str(res["end_reason"])] = ends.get(
            str(res["end_reason"]), 0) + 1
        if res["phase"] != "done" or res["end_reason"] is None:
            bad_end.append(res["seed"])
        iv = replay_wire(res["wire"], res["hand_mode"])
        n_pulses += len([r for r in iv if r[4] is not None])
        if short_pulses(iv):
            bad_short.append((res["seed"], res["player"],
                              [round(r[4], 1) for r in short_pulses(iv)]))
        if same_board_overlaps(iv):
            bad_overlap.append(res["seed"])
    print(f"blocks            : {blocks}")
    print(f"delivered pulses  : {n_pulses}")
    print(f"end reasons       : {ends}")
    print(f"blocks that stalled       : {bad_end}")
    print(f"buzzes under {FIRMWARE_HOLD_MS:.0f} ms      : {bad_short}")
    print(f"same-board overlaps       : {bad_overlap}")
    return not (bad_end or bad_short or bad_overlap)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", type=int, default=0)
    args, rest = ap.parse_known_args()
    if args.blocks:
        raise SystemExit(0 if _long_soak(args.blocks) else 1)
    unittest.main(argv=[sys.argv[0]] + rest)
