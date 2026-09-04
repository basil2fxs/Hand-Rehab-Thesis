"""Buzz Hunt at the wire: what the finger actually feels.

The rest of the Buzz Hunt suite checks the state machine. This file
checks the bytes. Every command the mode and the engine write is
timestamped on a virtual clock and replayed through a model of the
shipped sketch (arduino/firmware_on_device/lib/Motor/Motor.cpp, read
only), so the assertions are about delivered ON intervals rather than
about intentions:

  STIM:n  turns motor n-1 on and sets its own auto-off 150 ms later
          (STIM_ON_MS in lib/Config/Config.cpp). Other lanes are not
          touched, which is why the host stops the board first: the
          four motors on a board share one darlington driver that
          cannot supply two at once.
  STOP    drops every lane on that board and clears its timers.
  LEFT:/RIGHT: picks one board; anything unprefixed is broadcast to
          both (finger_rehab/hardware/multi_serial.py).

What is pinned here:

  - the fixed localisation pulse is exactly one firmware hold, 150 ms,
    at 144, 120, 60 and 30 frames per second and under frame jitter
  - a stretched pulse (the gap stage's one-long-buzz, echo's playback
    items) is ONE continuous buzz when frames are steady
  - a stretched pulse broken by a long frame reports itself undelivered
    instead of restarting the motor: the patient must never feel two
    buzzes where the row says one, which in the gap stage is the wrong
    answer and moves the staircase on it
  - the after-press confirmation buzz never merges with the stimulus
    and stretches it into a function of reaction time
  - the delivered silent gap at the bottom of the staircase still
    clears the motor's spin-down
  - two fingers on one board are never driven at once
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from contextlib import contextmanager
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_buzz_hunt import (_attach_detectors, _engine,  # noqa: E402
                                  _mode, _only_stage, _press_event)

# The firmware's own hold, lib/Config/Config.cpp STIM_ON_MS.
FIRMWARE_HOLD_MS = 150.0
# Precision Microdrives 310-103 class: typical stop time after current
# off. A "silence" shorter than this is not silence.
MOTOR_STOP_MS = 115.0
FRAME = 1.0 / 60.0
FRAME_MS = FRAME * 1000.0


# ---- the virtual clock -----------------------------------------------------
class _Clock:
    def __init__(self, t0: float = 1000.0) -> None:
        self.t = float(t0)

    def perf_counter(self) -> float:
        return self.t


@contextmanager
def patched_clock(t0: float = 1000.0):
    """Drive engine.py, buzz_hunt.py and rest_skip.py off one virtual
    clock. They all reach time.perf_counter through the module, so one
    patch covers the lot and a twenty minute block runs in a moment
    with every interval exact rather than sampled."""
    clock = _Clock(t0)
    real = time.perf_counter
    time.perf_counter = clock.perf_counter
    try:
        yield clock
    finally:
        time.perf_counter = real


# ---- the board -------------------------------------------------------------
class _WireBoard:
    """Records every command with the virtual time it was written."""

    provides_samples = True

    def __init__(self, clock: _Clock) -> None:
        self.clock = clock
        self.wire: list[tuple[float, str]] = []
        self.refused: list[tuple[float, str]] = []
        self.down_from: float | None = None

    def send_command(self, cmd: str) -> bool:
        if self.down_from is not None and self.clock.t >= self.down_from:
            # A dead port delivers nothing, so the byte must not reach
            # the wire the firmware model replays.
            self.refused.append((self.clock.t, cmd))
            return False
        self.wire.append((self.clock.t, cmd))
        return True


def replay_wire(wire, hand_mode="right", n_per_hand=4):
    """Turn a recorded byte stream into the ON intervals a finger
    feels: [(hand, finger, t_on, t_off, ms, why)] with why one of
    "auto" (the firmware's own timer), "stop" (a STOP byte) or "open"
    (still running when the stream ended)."""
    boards = ["right", "left"] if hand_mode == "both" else [hand_mode]
    on: dict[tuple[str, int], float] = {}
    off_at: dict[tuple[str, int], float] = {}
    out: list[tuple] = []

    def expire(upto):
        for key in list(off_at):
            if off_at[key] <= upto:
                t_on = on.pop(key)
                out.append((key[0], key[1], t_on, off_at[key],
                            (off_at[key] - t_on) * 1000.0, "auto"))
                del off_at[key]

    for t, cmd in wire:
        expire(t)
        scoped = cmd.startswith("LEFT:") or cmd.startswith("RIGHT:")
        if scoped:
            head, rest = cmd.split(":", 1)
            targets = [head.lower()]
        else:
            rest, targets = cmd, list(boards)
        if rest.startswith("STIM:"):
            ch = int(rest.split(":", 1)[1])
            if len(boards) == 2 and not scoped:
                # multi_serial splits 1..n to the right board and
                # n+1..2n to the left.
                if 1 <= ch <= n_per_hand:
                    hand, local = "right", ch
                else:
                    hand, local = "left", ch - n_per_hand
            else:
                hand, local = targets[0], ch
            key = (hand, local - 1)
            on.setdefault(key, t)
            off_at[key] = t + FIRMWARE_HOLD_MS / 1000.0
        elif rest == "STOP":
            for hand in targets:
                for f in range(n_per_hand):
                    key = (hand, f)
                    if key in on:
                        out.append((hand, f, on[key], t,
                                    (t - on[key]) * 1000.0, "stop"))
                        del on[key]
                        off_at.pop(key, None)
    if wire:
        expire(wire[-1][0] + 10.0)
    for key, t_on in list(on.items()):
        out.append((key[0], key[1], t_on, None, None, "open"))
    out.sort(key=lambda r: r[2])
    return out


def same_board_overlaps(intervals):
    """Pairs of intervals on ONE board that overlap in time. The
    firmware would allow it; the shared driver cannot supply it, so
    both buzzes come out weak and neither is the stimulus that was
    asked for."""
    bad = []
    by_board: dict[str, list] = {}
    for hand, f, t_on, t_off, _ms, _why in intervals:
        by_board.setdefault(hand, []).append(
            (t_on, t_off if t_off is not None else t_on + 0.15, f))
    for hand, rows in by_board.items():
        rows.sort()
        for a, b in zip(rows, rows[1:]):
            if a[2] != b[2] and b[0] < a[1] - 1e-9:
                bad.append((hand, a, b))
    return bad


# ---- the rig ---------------------------------------------------------------
def wire_engine(clock, hand_mode="right", cfg_extra=None):
    e = _engine(hand_mode, cfg_extra=cfg_extra)
    board = _WireBoard(clock)
    e.source = board
    e.board = board
    return e


class _Rig:
    """One engine frame: drain the motor queue, then tick the mode,
    the same order the main loop uses."""

    def __init__(self, clock, engine, mode=None, dt=FRAME):
        self.clock = clock
        self.engine = engine
        self.mode = mode
        self.dt = dt

    def step(self, dt=None):
        self.clock.t += self.dt if dt is None else dt
        self.engine._drain_motor_queue()
        if self.mode is not None:
            self.mode._tick(self.clock.t)

    def run(self, seconds, hook=None):
        end = self.clock.t + seconds
        while self.clock.t < end:
            dt = None
            if hook is not None:
                dt = hook(self)
            self.step(dt)
            if self.mode is not None and self.mode.phase == "done":
                break


class FixedPulseTests(unittest.TestCase):
    """The 150 ms localisation and span pulse is the whole paradigm:
    the pulse never changes and the response window is what moves. If
    the delivered pulse wobbles with the frame rate, the paradigm is
    not what the write-up says it is."""

    def _one_pulse(self, request_ms, fps, jitter=None):
        with patched_clock() as clock:
            e = wire_engine(clock)
            e.pulse_motor(0, float(request_ms))
            rig = _Rig(clock, e, dt=1.0 / fps)
            if jitter is None:
                rig.run(2.0)
            else:
                rig.run(2.0, hook=lambda r: next(jitter))
            return replay_wire(e.board.wire)

    def test_the_fixed_pulse_is_exactly_one_firmware_hold(self):
        for fps in (144, 120, 60, 30):
            with self.subTest(fps=fps):
                iv = self._one_pulse(150.0, fps)
                lengths = [round(r[4], 1) for r in iv]
                self.assertEqual(lengths, [FIRMWARE_HOLD_MS],
                                 "the firmware's own auto-off always "
                                 "wins over the host stop")

    def test_the_fixed_pulse_survives_frame_jitter(self):
        import itertools
        jitter = itertools.cycle([FRAME, FRAME * 2.5, FRAME * 0.5,
                                  FRAME * 4.0])
        iv = self._one_pulse(150.0, 60, jitter=jitter)
        self.assertEqual([round(r[4], 1) for r in iv], [FIRMWARE_HOLD_MS])

    def test_a_clean_stretched_pulse_is_one_continuous_buzz(self):
        iv = self._one_pulse(620.0, 60)
        self.assertEqual(len(iv), 1, "one request, one buzz")
        self.assertGreaterEqual(iv[0][4], 620.0 - FRAME_MS)
        self.assertLessEqual(iv[0][4], 620.0 + FRAME_MS)


class BrokenPulseTests(unittest.TestCase):
    """A pulse longer than the firmware hold is built out of re-arms
    that must each land INSIDE the previous hold. One frame longer
    than motor.pulse_interval_ms skips a re-arm, the motor spins down
    mid-buzz, and sending the stale re-arms afterwards restarts it:
    the finger feels TWO buzzes where the row says one. In the gap
    stage that is the wrong answer and the staircase steps on it."""

    def _broken(self, request_ms, freeze_at_ms, freeze_s):
        with patched_clock() as clock:
            e = wire_engine(clock)
            e.pulse_motor(0, float(request_ms))
            t0 = clock.t
            fired = {"done": False}

            def hook(rig):
                if (not fired["done"]
                        and (rig.clock.t - t0) * 1000.0 >= freeze_at_ms):
                    fired["done"] = True
                    return freeze_s
                return None

            _Rig(clock, e).run(3.0, hook=hook)
            return e, replay_wire(e.board.wire)

    def test_a_broken_stretched_pulse_reports_undelivered(self):
        e, iv = self._broken(620.0, 250.0, 0.20)
        self.assertEqual(len(iv), 1,
                         "one truncated buzz, never two")
        self.assertIs(e._last_stim_delivered, False)
        broken = [ev for ev in e.raw_logger.events
                  if ev["event"] == "pulse_broken"]
        self.assertTrue(broken, "raw.csv must carry the break")

    def test_no_stim_reaches_the_wire_after_the_break(self):
        e, _iv = self._broken(940.0, 300.0, 0.25)
        wire = e.board.wire
        stims = [t for t, c in wire if "STIM" in c]
        self.assertTrue(stims)
        # The motor is silent from the moment the first hold that was
        # not re-armed in time lapses. Nothing may re-arm it after
        # that: a buzz with a hole in it is a different stimulus, and
        # in the gap stage it is the wrong answer.
        holds_end = []
        for i, t in enumerate(stims):
            nxt = stims[i + 1] if i + 1 < len(stims) else None
            if nxt is None or nxt > t + FIRMWARE_HOLD_MS / 1000.0:
                holds_end.append(t + FIRMWARE_HOLD_MS / 1000.0)
        silent_from = holds_end[0]
        self.assertEqual(
            [t for t in stims if t >= silent_from - 1e-9], [],
            "a buzz with a hole in it must not be restarted")

    def test_the_broken_pulse_used_to_split_in_two(self):
        # The shape of the fault, pinned so a future change to the
        # re-arm queue cannot bring it back: with the drain sending
        # stale re-arms the finger felt two buzzes for one request.
        e, iv = self._broken(620.0, 200.0, 0.30)
        self.assertEqual(len(iv), 1)
        self.assertIs(e._last_stim_delivered, False)

    def test_a_clean_stretched_pulse_is_not_reported_broken(self):
        with patched_clock() as clock:
            e = wire_engine(clock)
            e.pulse_motor(0, 620.0)
            _Rig(clock, e).run(2.0)
            self.assertIsNot(e._last_stim_delivered, False)
            self.assertEqual(
                [ev for ev in e.raw_logger.events
                 if ev["event"] == "pulse_broken"], [])


class GapStageWireTests(unittest.TestCase):
    def _gap_mode(self, e, **over):
        kw = dict(catch_rate=0.0)
        kw.update(over)
        m = _mode(e, **kw)
        m.engine.finish_block = lambda: None
        return _only_stage(m, "gap", 4)

    def _to_trial(self, rig):
        """Frames until the FIRST trial's quiet gate, so the test can
        pin the material before _prepare_trial draws the next one."""
        m, guard = rig.mode, rig.clock.t + 30.0
        while m.phase != "trial" and rig.clock.t < guard:
            rig.step()
        assert m.phase == "trial", m.phase
        return m

    def _to_play(self, rig):
        m, guard = rig.mode, rig.clock.t + 30.0
        while m.sub != "play" and rig.clock.t < guard:
            rig.step()
        assert m.sub == "play", m.sub
        return m

    def _pin_gap(self, m, two, gap_ms=None):
        from finger_rehab.game.modes.buzz_hunt import pulses_from_params
        m.gap_two = bool(two)
        m.params["two"] = 1 if two else 0
        if gap_ms is not None:
            m.params["gap_ms"] = float(gap_ms)
        m._pulse_plan = pulses_from_params(m.waveform, m.params)

    def test_a_one_buzz_gap_trial_broken_mid_pulse_is_voided(self):
        # The stage asks "one buzz or two?". A frame overrun used to
        # split the one-buzz stimulus in two, the patient answered
        # two, and the row still said two=0 with the staircase
        # stepping on it. The break now voids the trial, which is what
        # the mode already does for a dropped STIM.
        with patched_clock() as clock:
            e = wire_engine(clock)
            m = self._gap_mode(e, gap_start_ms=320.0)
            _attach_detectors(e)
            rig = _Rig(clock, e, m)
            self._to_trial(rig)
            self._pin_gap(m, two=False)
            before = m._gap_stair[m.hand].level
            self._to_play(rig)
            rig.step()                        # the long buzz starts
            self.assertEqual(m._pulse_idx, 1)
            rig.step(0.30)                    # one long frame inside it
            rig.run(0.5)
            self.assertIs(m._stim_delivered, False)
            iv = [r for r in replay_wire(e.board.wire) if r[4] is not None]
            self.assertEqual(len(iv), 1,
                             "the finger must feel one buzz, not two")
            # Answer, and check the trial never reached the numbers.
            m.queue_press(_press_event(m.lane, clock.t))
            rig.run(m.response_window_s + 1.0)
            self.assertEqual(m._gap_records, [])
            self.assertEqual(m._gap_stair[m.hand].level, before)
            row = e.trial_logger.rows[-1]
            self.assertIn("stim_failed=True", row["stimulus"])

    def test_the_delivered_gap_never_falls_under_the_spin_down(self):
        # The delivered silence is the request minus up to one display
        # frame: the first short ends on the firmware's own timer
        # while the second starts at the next frame at or after its
        # planned onset. At the old 120 ms floor that left under 2 ms
        # of real silence against a 115 ms spin-down, so the bottom of
        # the staircase was a level nobody could answer.
        from finger_rehab.game.modes.buzz_hunt import GAP_FLOOR_MS
        with patched_clock() as clock:
            e = wire_engine(clock)
            m = self._gap_mode(e, gap_start_ms=GAP_FLOOR_MS)
            _attach_detectors(e)
            rig = _Rig(clock, e, m)
            self._to_trial(rig)
            self._pin_gap(m, two=True, gap_ms=GAP_FLOOR_MS)
            self._to_play(rig)
            rig.run(3.0)
            iv = [r for r in replay_wire(e.board.wire)
                  if r[4] is not None]
            self.assertGreaterEqual(len(iv), 2,
                                    "two shorts must reach the finger")
            silence_ms = (iv[1][2] - iv[0][3]) * 1000.0
            self.assertGreaterEqual(
                silence_ms, MOTOR_STOP_MS,
                "a gap shorter than the spin-down is not silent")
            self.assertGreaterEqual(
                silence_ms, MOTOR_STOP_MS + FRAME_MS,
                "the floor must clear the spin-down by a frame, or a "
                "good performer walks the staircase down to a level "
                "nobody can answer")

    def test_the_gap_floor_is_reported_as_censored(self):
        with patched_clock() as clock:
            e = wire_engine(clock)
            m = self._gap_mode(e)
            m._gap_stair["right"].level = m.gap_floor_ms
            stats = m.block_stats()["gap"]["threshold"]["right"]
            self.assertTrue(stats["censored"])
            self.assertEqual(stats["floor_ms"], round(m.gap_floor_ms, 1))


class AfterPressCueTests(unittest.TestCase):
    """cue.buzz_after buzzes the finger the patient just pressed. In
    every other mode that is a confirmation the patient can tell from
    the cue. Here the buzz IS the stimulus, on the same finger, and
    log_trial's after-press path throws away the stimulus pulse's own
    scoped stop, so the two merged into one buzz running from onset to
    150 ms past the press. Measured with the switch on: a 50 ms
    reaction delivered 183 ms and a 120 ms reaction 267 ms, against a
    row that still said 150. Stimulus length became a function of
    reaction time in the mode whose whole design is a fixed pulse."""

    def _loc_trial(self, press_rt_s):
        with patched_clock() as clock:
            e = wire_engine(clock, cfg_extra={"cue.buzz_after": True})
            m = _mode(e, catch_rate=0.0)
            m.engine.finish_block = lambda: None
            m = _only_stage(m, "loc", 2)
            _attach_detectors(e)
            rig = _Rig(clock, e, m)
            guard = clock.t + 30.0
            while m.sub != "play" and clock.t < guard:
                rig.step()
            rig.step()
            target = m.lane
            fire_at = clock.t + press_rt_s
            while clock.t < fire_at:
                rig.step()
            m.queue_press(_press_event(target, clock.t))
            rig.run(1.5)
            return e, replay_wire(e.board.wire)

    def test_the_after_press_cue_never_lengthens_the_stimulus(self):
        for rt in (0.05, 0.08, 0.12, 0.2):
            with self.subTest(reaction_ms=int(rt * 1000)):
                e, iv = self._loc_trial(rt)
                lengths = [round(r[4], 1) for r in iv if r[4] is not None]
                self.assertEqual(
                    lengths, [FIRMWARE_HOLD_MS],
                    "the stimulus must stay one firmware hold whatever "
                    "the reaction time")
                self.assertEqual(
                    [ev for ev in e.raw_logger.events
                     if ev["event"] == "press_motor"], [],
                    "no confirmation buzz on the stimulus finger")


class BoardSharingTests(unittest.TestCase):
    def test_two_fingers_on_one_board_are_never_driven_at_once(self):
        with patched_clock() as clock:
            e = wire_engine(clock)
            m = _mode(e, catch_rate=0.1, session_cap_min=3.0)
            m.engine.finish_block = lambda: None
            _attach_detectors(e)
            rig = _Rig(clock, e, m)

            def answer(r):
                if r.mode.sub == "respond" and not r.mode._resp_presses:
                    r.mode.queue_press(
                        _press_event(r.mode.lane, r.clock.t))
                return None

            rig.run(600.0, hook=answer)
            self.assertEqual(m.phase, "done")
            self.assertEqual(same_board_overlaps(
                replay_wire(e.board.wire)), [])


if __name__ == "__main__":
    unittest.main()
