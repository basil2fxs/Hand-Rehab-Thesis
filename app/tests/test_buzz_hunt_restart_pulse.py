"""Two ways a Buzz Hunt buzz was still being cut inside its own hold.

The soak next door found both by playing many randomised blocks; this
file pins them as the smallest reproductions, because a soak that only
fails on some seeds is not a regression test.

Both are the same injury from different directions. The firmware holds
every STIM for 150 ms and turns the motor off on its own timer
(arduino/firmware_on_device/lib/Config/Config.cpp, read only). A
310-103 class ERM needs about 40 ms of lag and 87 ms of rise before it
is at amplitude (Precision Microdrives datasheet), so a command cut
part way through its hold is not a fainter buzz, it is a buzz the
finger never felt. In Buzz Hunt the buzz IS the stimulus, so that is
the whole trial.

  1. A global STOP held back for a previous trial's confirmation buzz
     (stop_all_motors with allow_after_cue, parked in _motor_stop_at)
     fired in the middle of the next stimulus. The two cue paths in
     engine.py already clear that parked stop when they fire; the
     stimulus path did not.
  2. A playback restarted by an early press fired its first pulse
     while the board was still inside the hold of the pulse the
     abandoned playback left running. _send_stim has to write a STOP
     before it can drive another finger on the same board (one
     darlington, one motor at a time), so the abandoned buzz was cut.
"""
from __future__ import annotations

import os
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
                                       replay_wire, wire_engine)

EPS_MS = 1e-6


def _short(intervals):
    return [r for r in intervals
            if r[4] is not None and r[4] < FIRMWARE_HOLD_MS - EPS_MS]


class HeldBackStopTests(unittest.TestCase):
    """A parked global STOP must not reach across into a new pulse."""

    def test_a_parked_stop_does_not_cut_the_next_stimulus(self) -> None:
        with patched_clock() as clock:
            e = wire_engine(clock)
            # What stop_all_motors(allow_after_cue=True) leaves behind
            # when finish_block runs while a confirmation buzz is still
            # playing: a STOP owed a fraction of a second from now.
            e._after_cue_until = clock.t + 0.05
            e.stop_all_motors(allow_after_cue=True)
            self.assertIsNotNone(e._motor_stop_at)
            e.pulse_motor(0, FIRMWARE_HOLD_MS)
            rig = _Rig(clock, e)
            for _ in range(30):
                rig.step()
            intervals = replay_wire(e.board.wire)
            self.assertEqual(_short(intervals), [])
            self.assertEqual(len(intervals), 1)


class RestartedPlaybackTests(unittest.TestCase):
    """An early press restarts the trial with fresh material. The new
    plan's first pulse must wait out the hold the abandoned one left
    running on the same board."""

    def _span_mode(self, e):
        m = _mode(e, hands={"right": [0, 1, 2, 3]}, seed=7,
                  loc_trials_per_hand=0, distractor_trials_per_hand=0,
                  gap_trials_per_hand=0, span_trials=6,
                  catch_rate=0.0, span_pulse_ms=FIRMWARE_HOLD_MS,
                  span_ioi_ms=400.0)
        m.engine.finish_block = lambda: None
        return m

    def test_a_restart_never_clips_the_pulse_it_interrupted(self) -> None:
        with patched_clock() as clock:
            e = wire_engine(clock)
            m = self._span_mode(e)
            _attach_detectors(e, hands=("right",))
            rig = _Rig(clock, e, m)
            seen = {"t0": None}
            restarts = {"n": 0}

            def hook(r):
                # Hands that have been still since the last trial, so
                # the quiet gate is already satisfied and the restart
                # comes back round in a frame or two rather than after
                # a fresh REST_GATE_S. That is the ordinary case for a
                # patient sitting quietly, and it is what puts the new
                # plan's first pulse inside the old one's hold.
                if (m.phase == "trial" and m.sub == "wait"
                        and m._quiet_since is not None):
                    m._quiet_since = min(m._quiet_since, clock.t - 30.0)
                # A press a third of the way into every playback: the
                # natural way to play a span stage, replaying what you
                # feel as you feel it.
                if (m.phase == "trial" and m.sub == "play"
                        and m._play_t0 is not None
                        and clock.t >= m._play_t0 + 0.05
                        and seen["t0"] != m._play_t0):
                    seen["t0"] = m._play_t0
                    restarts["n"] += 1
                    m.queue_press(_press_event(m.lane, clock.t))
                return None

            rig.run(240.0, hook=hook)
            self.assertGreater(restarts["n"], 50)
            intervals = replay_wire(e.board.wire)
            self.assertGreater(len(intervals), 50)
            self.assertEqual(
                [(r[1], round(r[4], 1)) for r in _short(intervals)], [])


if __name__ == "__main__":
    unittest.main()
