"""Measure the study battery's clock cost headless.

The healthy baseline design budgets 50 minutes per visit (docs/
research/healthy_baseline_study.txt, Section 2.3) from arithmetic
over the config. This script plays the whole battery through the
real engine, real modes and real loggers with a simulated
participant, on a simulated clock, and reports what the blocks
actually cost in seconds. No display, no audio, no hardware.

The participant is a model hand on a fake sensor stream: every mode
is driven the way the boards drive it, through 200 Hz samples into
the engine's own detectors, so a press is a real press event and a
force hold is a real force reading. The model reacts about 350 ms
after a cue, holds within a percent or so of a force target and
replays what it is shown, which is a healthy adult on a good day;
the reaction and rest floors of every mode are what set the time.

    python3 scripts/measure_battery.py                 P01, right-handed
    python3 scripts/measure_battery.py --code P04 --dominant left
    python3 scripts/measure_battery.py --fps 60        coarser frames

The sessions it writes go to a temp folder that is deleted at the
end (pass --keep to look at them). Nothing touches the real
sessions/ tree or config/user_settings.yaml.
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import tempfile
import time as _time
from dataclasses import dataclass, field
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


RESTING = 100.0          # counts on the pad with the finger resting
MAX_PRESS = 400.0        # counts above resting at a maximal press
PRESS_COUNTS = 260.0     # a firm tap, well over the on threshold
SAMPLE_HZ = 200.0

# Fixed allowances the design counts outside the blocks (Section
# 2.3): login, seating and hand placement; the quick calibration for
# both hands; and the NEXT UP moment between blocks.
LOGIN_S = 3 * 60.0
QUICK_CAL_S = 2 * 60.0
TRANSITION_S = 10.0


class SimClock:
    def __init__(self, t0: float) -> None:
        self.t = t0


@dataclass
class HandModel:
    """What the eight fingers are doing right now, as the sample
    stream will report it. Presses are (release time) per lane;
    force targets are percent of max per lane."""
    press_until: dict[int, float] = field(default_factory=dict)
    force_pct: dict[int, float] = field(default_factory=dict)
    noise_sd: float = 0.6
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def press(self, lane: int, now: float, hold_s: float = 0.12) -> None:
        self.press_until[lane] = max(self.press_until.get(lane, 0.0),
                                     now + hold_s)

    def sample(self, now: float) -> tuple[int, ...]:
        vals = []
        for lane in range(8):
            v = RESTING
            pct = self.force_pct.get(lane)
            if pct is not None and pct > 0:
                v = RESTING + MAX_PRESS * pct / 100.0
                v += self.rng.gauss(0.0, self.noise_sd * MAX_PRESS / 100.0)
            if self.press_until.get(lane, 0.0) > now:
                v = max(v, RESTING + PRESS_COUNTS)
            vals.append(int(round(max(0.0, v))))
        return tuple(vals)


class FakeRig:
    """A two-board rig fed by the HandModel."""
    provides_samples = True
    is_connected = True
    name = "SimulatedTwoBoardRig"
    hand_modes_available = {"right", "left", "both"}
    hands: list = []

    def __init__(self) -> None:
        from collections import deque
        self._q: deque = deque()
        self.commands: list[str] = []

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def push(self, t_perf: float, values: tuple[int, ...],
             hand_mode: str) -> None:
        """The model's lanes are the engine's lanes for the hand mode
        in play: 0..3 for one hand (whichever it is), 0..7 with the
        left hand on 4..7 for both. A one-hand session's board sees
        the first four values."""
        from finger_rehab.hardware.source import Sample
        vals = values if hand_mode == "both" else values[0:4]
        self._q.append(Sample(t_perf=t_perf, values=tuple(vals)))

    def get_sample(self, timeout: float = 0.0):
        if self._q:
            return self._q.popleft()
        return None

    def send_command(self, cmd: str) -> bool:
        self.commands.append(cmd)
        return True


class Participant:
    """Per-mode responders. Each reads the live mode object and moves
    the HandModel; nothing here calls into a mode, so the modes see
    exactly what the boards would send."""

    RT_S = 0.35

    def __init__(self, hand: HandModel, rng: random.Random) -> None:
        self.hand = hand
        self.rng = rng
        self.answered: set = set()
        self.pending: list[tuple[float, int, float]] = []   # (t, lane, hold)
        self._probe_phase_t0: float | None = None

    def _rt(self) -> float:
        return max(0.18, self.rng.gauss(self.RT_S, 0.06))

    def schedule(self, t: float, lane: int, hold: float = 0.12) -> None:
        self.pending.append((t, lane, hold))

    def flush(self, now: float) -> None:
        keep = []
        for t, lane, hold in self.pending:
            if t <= now:
                self.hand.press(lane, now, hold)
            else:
                keep.append((t, lane, hold))
        self.pending = keep

    def act(self, eng, now: float) -> None:
        mode = getattr(eng, "mode", None)
        if mode is None:
            return
        name = str(eng.current_block)
        handler = getattr(self, f"_{name}", None)
        if handler is not None:
            handler(mode, now, eng)
        self.flush(now)

    # ---- cued presses ----------------------------------------------------
    def _reaction(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None or getattr(m, "_phase", "") != "stim":
            return
        key = ("reaction", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        self.schedule(act.stim_t_perf + self._rt(), act.lane)

    def _mirror(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None:
            return
        key = ("mirror", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        t = act.stim_t_perf + self._rt() + 0.05
        self.schedule(t, act.finger)
        self.schedule(t + self.rng.gauss(0.0, 0.02), act.finger + 4)

    # Rests in pattern and chords are self-paced past their floor: the
    # screen says "press any finger when ready". The model takes a
    # second and a half to be ready.
    READY_S = 1.5

    def _self_paced_rest(self, m, now, until_attr: str, lane: int) -> bool:
        if getattr(m, "phase", "") != "rest":
            return False
        until = getattr(m, until_attr, None)
        if until is None:
            return True
        key = ("rest", id(m), round(until, 3))
        if now >= until + self.READY_S and key not in self.answered:
            self.answered.add(key)
            self.hand.press(lane, now, 0.12)
        return True

    def _pattern(self, m, now, eng) -> None:
        if self._self_paced_rest(m, now, "_rest_min_until",
                                 int(m.lanes[0])):
            return
        act = getattr(m, "active", None)
        if act is None or getattr(m, "phase", "") != "play":
            return
        key = ("pattern", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        self.schedule(act.stim_t_perf + self._rt() + 0.05, act.lane)

    def _chords(self, m, now, eng) -> None:
        if self._self_paced_rest(m, now, "_rest_until", int(m.lanes[0])):
            return
        act = getattr(m, "active", None)
        if act is None or getattr(m, "phase", "") != "stim":
            return
        key = ("chords", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        t = act.stim_t_perf + self._rt() + 0.15
        for lane in act.targets:
            self.schedule(t + self.rng.gauss(0.0, 0.015), int(lane), 0.45)

    def _echo(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None or getattr(m, "phase", "") != "respond":
            return
        key = ("echo", m.trial_counter)
        if key in self.answered:
            return
        self.answered.add(key)
        t = now + 0.4
        for lane in m.sequence:
            self.schedule(t, int(lane))
            t += 0.55

    def _rhythm(self, m, now, eng) -> None:
        if not getattr(m, "_countdown_done", False):
            return
        for s in m.upcoming(0.03):
            key = ("rhythm", s.index)
            if key in self.answered or s.hit_at is not None:
                continue
            self.answered.add(key)
            self.hand.press(int(s.note.lane), now, 0.10)

    # ---- force modes -------------------------------------------------------
    def _probe(self, m, now) -> bool:
        """Maximal presses on cue during a max-press probe. True
        while the probe owns the hand."""
        if getattr(m, "phase", "") != "probe":
            self._probe_phase_t0 = None
            return False
        if self._probe_phase_t0 is None:
            self._probe_phase_t0 = now
        lane = m.hands[m.probe_hand][m.probe_finger]
        cycle = (now - self._probe_phase_t0) % 3.0
        self.hand.force_pct = {lane: 100.0 if cycle < 1.5 else 0.0}
        return True

    def _force_pilot(self, m, now, eng) -> None:
        if self._probe(m, now):
            return
        if getattr(m, "phase", "") == "run":
            target = float(getattr(m, "target_now", 0.0) or 0.0)
            self.hand.force_pct = {int(m.lane): target}
        else:
            self.hand.force_pct = {}

    def _lighthouse(self, m, now, eng) -> None:
        if self._probe(m, now):
            return
        if getattr(m, "phase", "") != "trial":
            self.hand.force_pct = {}
            return
        target = float(getattr(m, "target_pct", 0.0) or 0.0)
        if m.kind == "hold":
            self.hand.force_pct = {int(m.lane): target}
            return
        # An echo studies the force on set_lane and reproduces it on
        # lane (the mirror finger when the trial is cross-hand).
        sub = getattr(m, "sub", "")
        study_lane = int(getattr(m, "set_lane", m.lane))
        repro_lane = int(m.lane)
        if sub in ("enter", "study"):
            self.hand.force_pct = {study_lane: target}
        elif sub == "delay":
            self.hand.force_pct = {}
        elif sub == "reproduce":
            self.hand.force_pct = {repro_lane: target + 1.5}
        else:
            self.hand.force_pct = {}

    def _buzz_hunt(self, m, now, eng) -> None:
        if getattr(m, "phase", "") != "trial" or getattr(m, "sub", "") != "respond":
            return
        key = ("buzz_hunt", m.trial_counter)
        if key in self.answered:
            return
        self.answered.add(key)
        if not m._pulse_plan:
            return                      # catch trial: stay silent
        t0 = float(getattr(m, "_respond_t0", now) or now)
        if m.waveform == "buzz_seq":
            t = max(now, t0) + 0.5
            for lane in m.sequence:
                self.schedule(t, int(lane))
                t += 0.45
        else:
            self.schedule(max(now, t0) + self._rt() + 0.15, int(m.lane))


def build_engine(code: str, dominant: str, data_dir: Path, rig: FakeRig):
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["session"]["data_dir"] = str(data_dir)
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    cfg.data["eeg"] = {"enabled": False}
    # The quick calibration is counted as a fixed allowance below;
    # the profiles are installed directly.
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    eng = GameEngine(cfg, rig)
    eng._screens = eng._build_screens()
    eng.begin_session(code, "25", dominant_hand=dominant, visit="1")
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    for hand in ("right", "left"):
        prof = CalibrationProfile(hand=hand, participant=code,
                                  resting=[RESTING] * 4,
                                  press=[RESTING + 60.0] * 4)
        prof.set_max_press([MAX_PRESS] * 4)
        prof.participant = code
        prof.session_token = str(getattr(eng, "_session_token", ""))
        eng.apply_calibration(prof)
    eng._uncal_ack = {"left", "right"}
    return eng


def run_block(eng, rig: FakeRig, hand: HandModel, who: Participant,
              clock: SimClock, fps: float, cap_s: float) -> float:
    """Frames until the live block ends. Returns simulated seconds."""
    t_start = clock.t
    dt = 1.0 / fps
    sample_dt = 1.0 / SAMPLE_HZ
    next_sample = clock.t
    hand.press_until.clear()
    hand.force_pct = {}
    who.pending.clear()
    # Trial ids restart at 1 in every block, so the answered set must
    # too, or the second reaction block times out every trial.
    who.answered.clear()
    while eng.block_is_running():
        clock.t += dt
        now = clock.t
        while next_sample <= now:
            rig.push(next_sample, hand.sample(next_sample), eng.hand_mode)
            next_sample += sample_dt
        eng._pump_source()
        eng._drain_motor_queue()
        if eng.screen_obj is not None:
            eng.screen_obj.update(dt)
        eng.markers.tick()
        who.act(eng, now)
        if now - t_start > cap_s:
            # A block the model cannot finish is abandoned and its
            # step skipped, so the run reports the rest of the
            # battery instead of retrying the same block for ever.
            print(f"    block {eng.current_block} passed the {cap_s:.0f} s "
                  "cap; abandoning and skipping the step", file=sys.stderr)
            eng._abandon_if_in_block()
            eng.show_mode_select()
            eng.skip_protocol_step()
            break
    return clock.t - t_start


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--code", default="P01")
    ap.add_argument("--dominant", default="right",
                    choices=("left", "right"))
    ap.add_argument("--fps", type=float, default=120.0)
    ap.add_argument("--cap-min", type=float, default=20.0,
                    help="abandon any single block past this many minutes")
    ap.add_argument("--keep", action="store_true",
                    help="keep the temp sessions folder")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="battery_timing_"))
    rig = FakeRig()
    hand = HandModel(rng=random.Random(args.seed))
    who = Participant(hand, random.Random(args.seed + 1))
    real_perf = _time.perf_counter
    clock = SimClock(real_perf())
    _time.perf_counter = lambda: clock.t
    wall0 = _time.time()
    try:
        eng = build_engine(args.code, args.dominant, tmp, rig)
        ok, reason = eng.battery_available()
        if not ok:
            print(f"battery unavailable: {reason}")
            return 2
        if not eng.start_battery():
            print("battery did not start")
            return 2
        cell = eng._battery["cell"]
        print(f"Battery {eng._battery['id']} for {args.code}, dominant "
              f"{args.dominant}: order {cell['mode_order']}, hand 1 = "
              f"{cell['hand_first'].replace('_', '-')}", flush=True)
        rows = []
        transitions_s = 0.0
        while True:
            if not eng.block_is_running():
                break
            mode = str(eng.current_block)
            hand_mode = str(eng.hand_mode)
            step = dict(eng._protocol_current or {})
            secs = run_block(eng, rig, hand, who, clock, args.fps,
                             args.cap_min * 60.0)
            summary = eng.session.block_summary or {}
            rows.append((step.get("position", 0), mode, hand_mode, secs,
                         summary.get("status", "?"),
                         summary.get("trials", "")))
            print(f"  {step.get('position', 0):2d} {mode:12s} {hand_mode:6s}"
                  f" {secs / 60.0:6.2f} min  {summary.get('status', '?')}"
                  f"  trials={summary.get('trials', '')}", flush=True)
            nxt = eng.pending_protocol_step()
            if nxt is None:
                break
            gap = TRANSITION_S + float(nxt.get("stretch_s") or 0.0)
            transitions_s += gap
            clock.t += gap
            eng.continue_protocol()
        blocks_s = sum(r[3] for r in rows)
        total_s = LOGIN_S + QUICK_CAL_S + blocks_s + transitions_s
        budget = float((eng._battery or {}).get("budget_min", 50.0))
        print()
        print(f"  blocks       {blocks_s / 60.0:6.2f} min over {len(rows)} blocks")
        print(f"  transitions  {transitions_s / 60.0:6.2f} min "
              f"({TRANSITION_S:.0f} s NEXT UP each, plus the stretch)")
        print(f"  login + cal  {(LOGIN_S + QUICK_CAL_S) / 60.0:6.2f} min "
              "(fixed allowances from the design)")
        print(f"  TOTAL        {total_s / 60.0:6.2f} min against a "
              f"{budget:.0f} min budget "
              f"({'inside' if total_s <= budget * 60 else 'OVER'})")
        print(f"  wall time    {(_time.time() - wall0) / 60.0:.1f} min")
        if args.keep:
            print(f"  sessions kept at {tmp}")
        return 0
    finally:
        _time.perf_counter = real_perf
        try:
            eng = locals().get("eng")
            if eng is not None:
                eng._close_loggers()
        except Exception:
            pass
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
