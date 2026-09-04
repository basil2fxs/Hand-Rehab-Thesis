"""Simulate the healthy baseline cohort through the real engine.

Participant codes (24 by default, --n for more) play the study
battery ONCE, in one long sitting, the way the research assistant
runs it: log in with the intake fields, start the battery, take every
NEXT UP step, end the session. The engine, the modes, the loggers and
the battery runner are the shipped ones (scripts/measure_battery.py
supplies the model hand on a fake 200 Hz sensor stream and the
simulated clock); only the person is synthetic.

The design is ONE PASS: eleven blocks, every mode played once, no
repeated block anywhere in the sitting. There is therefore no
between-block change to inject and none to recover: a cohort built
here cannot be used to compute ICC, SEM, MDC95 or any pre-versus-post
contrast, because the data those need was never collected. What the
cohort is for is the normative table, the paired dominant versus
non-dominant comparison, the known-effect checks and the feasibility
numbers.

The one change a single pass can still show is WITHIN a block: trials
late in a block against trials early in the same block. Each code
carries latent skill plus a per-person within-block drift:

  reaction   a per-person base RT, the dominant hand 25 ms faster,
             45 ms trial-to-trial noise, and a small within-block
             warm-up that fades over the first trials
  mirror     the dominant hand's press leads the other by 15 ms
  rhythm     a per-person negative asynchrony with a per-person SD
  echo       a per-person span ceiling
  buzz hunt  a per-person localisation accuracy, errors landing on
             the neighbouring finger
  chords     a per-person press spread across the chord, tightening
             a little across the block
  pattern    trained-sequence presses speed up with exposure, which
             is the mode's own known effect and is measured inside
             the one block
  force      the hold noise is drawn PER BLOCK with no per-person
             part, so force error is the metric with no recoverable
             person behind it

The within-block drift is deliberately small and it decays, because
that is what a warm-up looks like: a participant settling into a task
over its first trials, not a person getting better at it. A slope
recovered from it is much weaker evidence than a repeated block would
have been, and any analysis over this cohort has to say so.

The truth behind every code is written to <out>/truth.json and the
measured minutes to <out>/durations.csv, so an analysis run over
<out>/sessions can be checked against what was injected.

    python3 scripts/simulate_cohort.py --out /tmp/cohort
    python3 scripts/simulate_cohort.py --out /tmp/cohort --n 4
    python3 scripts/simulate_cohort.py --out /tmp/cohort --n 28 --first 25
                                   (add four codes to a tree of 24)

Never points at the real sessions/ tree: --out is required and
must not be inside the repository.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import time as _time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import measure_battery as mb  # noqa: E402


DOMINANT_ADVANTAGE_S = 0.025
MIRROR_LEAD_S = 0.015
# How much tighter the presses inside a chord land by the end of the
# block than at its start, as a fraction of the starting spread.
CHORD_WITHIN_BLOCK_FACTOR = 0.85
# The within-block warm-up, as the mean of the per-person draw: how
# much faster the model is once it has settled than on its first
# trial of a block. Small on purpose. It decays with a time constant
# of WARMUP_TRIALS trials, so most of it is gone within the first
# handful and what an analysis recovers from it is a warm-up curve,
# not a learning curve.
WITHIN_BLOCK_WARMUP_S = 0.020
WARMUP_TRIALS = 8.0


def make_truth(n: int, seed: int) -> dict[str, dict]:
    """The latent skill behind each code, drawn once."""
    rng = random.Random(seed)
    truth: dict[str, dict] = {}
    for i in range(1, n + 1):
        code = f"P{i:02d}"
        # About one in ten adults is left-handed.
        dominant = "left" if rng.random() < 0.12 else "right"
        lq = (rng.randint(60, 100) if dominant == "right"
              else -rng.randint(60, 100))
        truth[code] = {
            "dominant": dominant,
            "edinburgh_lq": lq,
            "age": rng.randint(19, 34),
            "sex": rng.choice(["female", "male", "female", "male", ""]),
            "hand_length_mm": rng.randint(165, 205),
            "hand_breadth_mm": rng.randint(72, 95),
            "rt_s": max(0.22, rng.gauss(0.30, 0.035)),
            "rt_sd_s": 0.045,
            "span_cap": rng.choice([4, 5, 5, 6, 6, 6, 7, 7, 8]),
            "asyn_s": rng.gauss(-0.030, 0.012),
            "asyn_sd_s": rng.uniform(0.015, 0.035),
            "loc_acc": rng.uniform(0.86, 1.0),
            "learn_per_cycle_s": rng.uniform(0.004, 0.008),
            "chord_spread_s": rng.uniform(0.010, 0.022),
            # The per-person within-block warm-up. Clamped at zero:
            # nobody warms up backwards on purpose, and the
            # measurement noise supplies the people who look as
            # though they did.
            "warmup_s": max(0.0, rng.gauss(WITHIN_BLOCK_WARMUP_S, 0.008)),
        }
    return truth


class CohortParticipant(mb.Participant):
    """The model participant with a person behind it.

    One pass means every block is this person's only go at that mode,
    so the only change there is to inject is the one INSIDE a block.
    `trials_this_block` counts cued trials since the block opened and
    drives the warm-up, and it resets in begin_block so a warm-up
    cannot leak from one block into the next.
    """

    def __init__(self, hand: mb.HandModel, rng: random.Random,
                 truth: dict, seq_presses: int) -> None:
        super().__init__(hand, rng)
        self.truth = truth
        self.seq_presses = seq_presses      # pattern exposure so far
        self.hand_mode = "right"
        self.trials_this_block = 0

    def begin_block(self) -> None:
        super().begin_block()
        self.trials_this_block = 0

    def warmup_gain_s(self) -> float:
        """How much of the per-person warm-up has been taken up by the
        trial about to be answered. Exponential: most of it inside the
        first WARMUP_TRIALS trials, none of it on the first trial."""
        import math
        n = float(self.trials_this_block)
        return float(self.truth["warmup_s"]) * (
            1.0 - math.exp(-n / WARMUP_TRIALS))

    def block_progress(self) -> float:
        """Roughly how far into the block this trial sits, 0 to 1, for
        the drifts that are a fraction rather than a time. Capped
        because a block's trial count is not known up front."""
        return min(1.0, float(self.trials_this_block) / 40.0)

    # ---- hands and reaction times -------------------------------------
    def lane_hand(self, lane: int) -> str:
        if self.hand_mode == "both":
            return "right" if int(lane) < 4 else "left"
        return self.hand_mode

    def rt_for(self, lane: int) -> float:
        base = float(self.truth["rt_s"])
        if self.lane_hand(lane) != self.truth["dominant"]:
            base += DOMINANT_ADVANTAGE_S
        base -= self.warmup_gain_s()
        return max(0.15, self.rng.gauss(base, float(self.truth["rt_sd_s"])))

    def act(self, eng, now: float) -> None:
        self.hand_mode = str(eng.hand_mode)
        super().act(eng, now)

    # ---- cued presses ----------------------------------------------------
    def _reaction(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None or getattr(m, "_phase", "") != "stim":
            return
        key = ("reaction", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        # rt_for reads the warm-up, so the count moves AFTER the draw:
        # the first trial of a block gets none of it.
        self.schedule(act.stim_t_perf + self.rt_for(act.lane), act.lane)
        self.trials_this_block += 1

    def _mirror(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None:
            return
        key = ("mirror", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        # One shared reaction, then the dominant hand lands first. The
        # lead is the mode's known effect and it does not move inside
        # the block: what the mean gap reads is the asymmetry, not a
        # change in it.
        t = act.stim_t_perf + self.rt_for(act.finger) + 0.05
        self.trials_this_block += 1
        right, left = act.finger, act.finger + 4
        gap = MIRROR_LEAD_S
        jitter = 0.010
        lead = gap / 2.0
        if self.truth["dominant"] == "right":
            self.schedule(t - lead, right)
            self.schedule(t + lead + self.rng.gauss(0.0, jitter), left)
        else:
            self.schedule(t + lead + self.rng.gauss(0.0, jitter), right)
            self.schedule(t - lead, left)

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
        # The presses inside a chord land closer together as the block
        # goes on: the same warm-up story as reaction, in the units
        # chords is scored in.
        spread = float(self.truth["chord_spread_s"]) * (
            1.0 - (1.0 - CHORD_WITHIN_BLOCK_FACTOR) * self.block_progress())
        t = act.stim_t_perf + self._rt() + 0.15
        self.trials_this_block += 1
        for lane in act.targets:
            self.schedule(t + self.rng.gauss(0.0, spread), int(lane), 0.45)

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
        rt = self.rt_for(act.lane) + 0.05
        self.trials_this_block += 1
        seg = m.segments[m._seg_idx]
        if seg.kind == "seq":
            # Trained material: faster with every cycle seen, capped.
            # The block is the only go at pattern in the sitting, so
            # this exposure effect is measured entirely inside it,
            # trained takes against the random take and against the
            # probe takes.
            cycles = self.seq_presses / 12.0
            rt -= min(0.06, cycles * float(self.truth["learn_per_cycle_s"]))
            self.seq_presses += 1
        self.schedule(act.stim_t_perf + max(0.15, rt), act.lane)

    def _echo(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None or getattr(m, "phase", "") != "respond":
            return
        key = ("echo", m.trial_counter)
        if key in self.answered:
            return
        self.answered.add(key)
        t = now + 0.4
        seq = list(m.sequence)
        if len(seq) > int(self.truth["span_cap"]):
            # Past the span: one wrong press ends the trial. The cap
            # is a fixed property of the person, so the span the block
            # reports is a normative number and nothing else.
            wrong = next(l for l in m.lanes if l != seq[0])
            self.schedule(t, int(wrong))
            return
        for lane in seq:
            self.schedule(t, int(lane))
            t += 0.55

    def _rhythm(self, m, now, eng) -> None:
        if not getattr(m, "_countdown_done", False):
            return
        sd = float(self.truth["asyn_sd_s"])
        for s in m.upcoming(0.6):
            key = ("rhythm", s.index)
            if key in self.answered or s.hit_at is not None:
                continue
            self.answered.add(key)
            until = float(s.note.t) - float(m.song_time)
            asyn = self.rng.gauss(float(self.truth["asyn_s"]), sd)
            self.schedule(now + until + asyn, int(s.note.lane), 0.10)

    def _buzz_hunt(self, m, now, eng) -> None:
        if (getattr(m, "phase", "") != "trial"
                or getattr(m, "sub", "") != "respond"):
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
            seq = list(m.sequence)
            if len(seq) > int(self.truth["span_cap"]):
                wrong = next(l for l in m.hands[m.hand] if l != seq[0])
                self.schedule(t, int(wrong))
                return
            for lane in seq:
                self.schedule(t, int(lane))
                t += 0.45
            return
        lane = int(m.lane)
        if self.rng.random() > float(self.truth["loc_acc"]):
            fingers = list(m.hands[m.hand])
            i = fingers.index(lane) if lane in fingers else 0
            j = i + 1 if i + 1 < len(fingers) else i - 1
            lane = int(fingers[j])
        rt = self.rt_for(lane)
        self.trials_this_block += 1
        self.schedule(max(now, t0) + rt + 0.15, lane)


def build_engine(code: str, truth: dict, data_dir: Path,
                 rig: mb.FakeRig):
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
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    eng = GameEngine(cfg, rig)
    eng._screens = eng._build_screens()
    eng.begin_session(
        code, str(truth["age"]),
        sex=str(truth["sex"]),
        dominant_hand=str(truth["dominant"]),
        edinburgh_lq=str(truth["edinburgh_lq"]),
        visit="1",
        hand_length_mm=str(truth["hand_length_mm"]),
        hand_breadth_mm=str(truth["hand_breadth_mm"]))
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    for hand in ("right", "left"):
        prof = CalibrationProfile(hand=hand, participant=code,
                                  resting=[mb.RESTING] * 4,
                                  press=[mb.RESTING + 60.0] * 4)
        prof.set_max_press([mb.MAX_PRESS] * 4)
        prof.participant = code
        prof.session_token = str(getattr(eng, "_session_token", ""))
        eng.apply_calibration(prof)
    eng._uncal_ack = {"left", "right"}
    return eng


def play_session(code: str, truth: dict, data_dir: Path,
                 clock: mb.SimClock, fps: float, cap_s: float,
                 seed: int) -> tuple[list, float]:
    """One sitting: login, battery, every NEXT UP and every rest, end
    session. Returns (rows per block, total simulated minutes)."""
    rig = mb.FakeRig()
    hand = mb.HandModel(rng=random.Random(seed))
    noise_rng = random.Random(seed + 7)
    who = CohortParticipant(hand, random.Random(seed + 1), truth, 0)
    eng = build_engine(code, truth, data_dir, rig)
    rows = []
    waits_s = 0.0
    rests_s = 0.0
    try:
        ok, reason = eng.battery_available()
        if not ok:
            raise SystemExit(f"{code}: battery unavailable: {reason}")
        if not eng.start_battery():
            raise SystemExit(f"{code}: battery did not start")
        while eng.block_is_running():
            mode = str(eng.current_block)
            hand_mode = str(eng.hand_mode)
            step = dict(eng._protocol_current or {})
            # Force noise is redrawn for every block with no person
            # part, so there is no latent steadiness behind the force
            # error a block reports. It is the one metric in the
            # cohort with nothing to recover, which is what makes it
            # useful as a negative control.
            hand.noise_sd = noise_rng.uniform(0.8, 1.9)
            secs = mb.run_block(eng, rig, hand, who, clock, fps, cap_s)
            summary = eng.session.block_summary or {}
            rows.append({
                "code": code,
                "position": step.get("position", 0), "mode": mode,
                "hand": hand_mode,
                "phase": str(step.get("phase") or ""),
                "minutes": secs / 60.0,
                "status": summary.get("status", "?"),
                "trials": summary.get("trials", ""),
            })
            nxt = eng.pending_protocol_step()
            if nxt is None:
                break
            wait_s = mb.wait_before(nxt)
            if float(nxt.get("rest_s") or 0.0) > 0:
                rests_s += wait_s
            else:
                waits_s += wait_s
            waits_s += mb.TRANSITION_S
            clock.t += mb.TRANSITION_S + wait_s
            eng.continue_protocol()
        progress = eng.battery_progress() or {}
        if not progress.get("finished"):
            print(f"  {code}: battery did not finish", file=sys.stderr)
        eng.end_session()
    finally:
        try:
            eng._close_loggers()
        except Exception:
            pass
    blocks_s = sum(r["minutes"] for r in rows) * 60.0
    total_min = ((mb.LOGIN_S + mb.QUICK_CAL_S + blocks_s + waits_s
                  + rests_s) / 60.0)
    return rows, total_min


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True,
                    help="folder for sessions/, truth.json, durations.csv")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--first", type=int, default=1,
                    help="first code number to play (codes below it "
                         "are assumed to be on disk already)")
    ap.add_argument("--fps", type=float, default=120.0)
    ap.add_argument("--cap-min", type=float, default=20.0)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    out = Path(args.out).resolve()
    if REPO in out.parents or out == REPO:
        raise SystemExit("--out must be outside the repository")
    root = out / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    truth = make_truth(args.n, args.seed)
    todo = {c: t for c, t in truth.items()
            if int(c[1:]) >= args.first}
    (out / "truth.json").write_text(json.dumps({
        "design": ("one sitting per person, one pass, every mode "
                   "played once; no repeated block, so no test-retest "
                   "quantity is computable from this cohort"),
        "dominant_advantage_s": DOMINANT_ADVANTAGE_S,
        "mirror_lead_s": MIRROR_LEAD_S,
        "within_block_warmup_s": WITHIN_BLOCK_WARMUP_S,
        "warmup_trials": WARMUP_TRIALS,
        "chord_within_block_factor": CHORD_WITHIN_BLOCK_FACTOR,
        "participants": truth},
        indent=2), encoding="utf-8")

    real_perf = _time.perf_counter
    clock = mb.SimClock(real_perf())
    _time.perf_counter = lambda: clock.t
    wall0 = _time.time()
    block_rows: list[dict] = []
    session_rows: list[dict] = []
    try:
        for i, (code, t) in enumerate(truth.items()):
            if code not in todo:
                continue
            rows, total_min = play_session(
                code, t, root, clock, args.fps, args.cap_min * 60.0,
                args.seed * 100 + i)
            block_rows.extend(rows)
            completed = sum(1 for r in rows if r["status"] == "completed")
            session_rows.append({"code": code, "dominant": t["dominant"],
                                 "blocks": len(rows),
                                 "completed": completed,
                                 "minutes": round(total_min, 2)})
            print(f"{code} {t['dominant']:5s} {total_min:6.2f} min  "
                  f"{completed}/{len(rows)} completed", flush=True)
    finally:
        _time.perf_counter = real_perf
    for name, rows in (("durations.csv", session_rows),
                       ("blocks.csv", block_rows)):
        path = out / name
        append = args.first > 1 and path.is_file()
        with path.open("a" if append else "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if not append:
                w.writeheader()
            w.writerows(rows)
    mins = sorted(r["minutes"] for r in session_rows)
    mid = mins[len(mins) // 2]
    # The shipped target, read off the preset rather than typed here,
    # so a config change cannot leave this line quoting a dead number.
    from finger_rehab.config import Config
    budget = float((Config.load().get("protocol.presets.study_battery")
                    or {}).get("budget_min") or 45.0)
    print()
    print(f"  {len(mins)} sessions: min {mins[0]:.1f}, median {mid:.1f}, "
          f"max {mins[-1]:.1f} min against a {budget:.0f} min target; "
          f"{sum(1 for m in mins if m > budget)} over")
    print(f"  wall time {(_time.time() - wall0) / 60.0:.1f} min; "
          f"sessions at {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
