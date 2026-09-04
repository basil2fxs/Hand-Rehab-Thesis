"""Simulate the healthy baseline cohort through the real engine.

Participant codes (24 by default, --n for more) play the study
battery ONCE, in one long sitting, the way the research assistant
runs it: log in with the intake fields, start the battery, take every
NEXT UP step, end the session. The engine, the modes, the loggers and
the battery runner are the shipped ones (scripts/measure_battery.py
supplies the model hand on a fake 200 Hz sensor stream and the
simulated clock); only the person is synthetic.

The design is one visit with every mode played early (phase pre) and
again late (phase post), so the thing to inject is not a
between-visit practice effect but a WITHIN-session one. Each code
carries latent skill plus a per-person rate of change from its first
go to its last:

  reaction   a per-person base RT, the dominant hand 25 ms faster,
             45 ms trial-to-trial noise, and only 0 to 5 ms of
             pre-to-post gain: this is the stability anchor, and the
             analysis expects it NOT to move
  mirror     the dominant hand's press leads the other by 15 ms, and
             the lead and its jitter shrink by post
  rhythm     a per-person negative asynchrony; its SD tightens by
             post, the mean stays negative
  echo       a per-person span ceiling, the same in both passes (the
             span is expected to be flat)
  buzz hunt  a per-person localisation accuracy, errors landing on
             the neighbouring finger, and 40 ms off the localisation
             RT by post
  chords     a per-person press spread across the chord, 15 percent
             tighter by post
  pattern    trained-sequence presses speed up with exposure, and the
             exposure carries from the pre block into the post block
  force      the hold noise is drawn PER BLOCK with no per-person
             part, so force error is the metric that should come out
             unreliable within a session; on top of that the post
             blocks are 30 percent quieter, so the pre-post change is
             real while the reliability is not

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
# How much quieter a post force block is than a pre one. The absolute
# noise is redrawn per block, so this is a shift in the middle of a
# noisy distribution: the pre-post change is recoverable, the
# block-to-block reliability is not.
FORCE_POST_FACTOR = 0.70
# How much tighter the presses inside a chord land by the post pass.
CHORD_POST_FACTOR = 0.85
# Everything the post pass is supposed to move, as the mean of the
# per-person draw. The analysis has to recover these signs.
POST_GAINS_S = {
    "reaction": 0.0025,     # the anchor: small on purpose
    "mirror": 0.012,
    "rhythm_sd": 0.003,
    "buzz": 0.040,
}


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
            # Per-person rates of change from the pre pass to the post
            # pass. Clamped at zero: nobody gets worse on purpose, the
            # measurement noise supplies the people who look worse.
            "post_rt_gain_s": max(0.0, rng.gauss(
                POST_GAINS_S["reaction"], 0.0015)),
            "post_mirror_gain_s": max(0.0, rng.gauss(
                POST_GAINS_S["mirror"], 0.004)),
            "post_asyn_sd_gain_s": max(0.0, rng.gauss(
                POST_GAINS_S["rhythm_sd"], 0.001)),
            "post_buzz_gain_s": max(0.0, rng.gauss(
                POST_GAINS_S["buzz"], 0.012)),
        }
    return truth


class CohortParticipant(mb.Participant):
    """The model participant with a person behind it, and a phase.

    `phase` is the battery's own phase word for the block in play
    (pre, mid, post), taken from the engine before every block, so the
    injected within-session change lands on exactly the blocks the
    analysis pairs.
    """

    def __init__(self, hand: mb.HandModel, rng: random.Random,
                 truth: dict, seq_presses: int) -> None:
        super().__init__(hand, rng)
        self.truth = truth
        self.phase = "pre"
        self.seq_presses = seq_presses      # pattern exposure so far
        self.hand_mode = "right"

    @property
    def late(self) -> bool:
        return self.phase == "post"

    # ---- hands and reaction times -------------------------------------
    def lane_hand(self, lane: int) -> str:
        if self.hand_mode == "both":
            return "right" if int(lane) < 4 else "left"
        return self.hand_mode

    def rt_for(self, lane: int) -> float:
        base = float(self.truth["rt_s"])
        if self.lane_hand(lane) != self.truth["dominant"]:
            base += DOMINANT_ADVANTAGE_S
        if self.late:
            base -= float(self.truth["post_rt_gain_s"])
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
        self.schedule(act.stim_t_perf + self.rt_for(act.lane), act.lane)

    def _mirror(self, m, now, eng) -> None:
        act = getattr(m, "active", None)
        if act is None:
            return
        key = ("mirror", act.trial_id)
        if key in self.answered:
            return
        self.answered.add(key)
        # One shared reaction, then the dominant hand lands first. By
        # the post pass the lead and its jitter have both shrunk,
        # which is what the mean gap reads.
        t = act.stim_t_perf + self.rt_for(act.finger) + 0.05
        right, left = act.finger, act.finger + 4
        gap = MIRROR_LEAD_S
        jitter = 0.010
        if self.late:
            gap = max(0.002, gap - float(self.truth["post_mirror_gain_s"]))
            jitter *= 0.6
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
        spread = float(self.truth["chord_spread_s"])
        if self.late:
            spread *= CHORD_POST_FACTOR
        t = act.stim_t_perf + self._rt() + 0.15
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
        seg = m.segments[m._seg_idx]
        if seg.kind == "seq":
            # Trained material: faster with every cycle seen, capped,
            # and the exposure count carries from the pre block into
            # the post block of the same sitting.
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
            # does not move between passes, so echo span is the metric
            # expected to sit still.
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
        if self.late:
            sd = max(0.005, sd - float(self.truth["post_asyn_sd_gain_s"]))
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
        if self.late:
            rt = max(0.15, rt - float(self.truth["post_buzz_gain_s"]))
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
            who.phase = str(step.get("phase") or "")
            # Force noise is redrawn for every block with no person
            # part, so the within-session reliability of force error
            # is poor by construction; the post blocks are quieter, so
            # the pre-post change is still there to be found.
            noise = noise_rng.uniform(0.8, 1.9)
            hand.noise_sd = (noise * FORCE_POST_FACTOR if who.late
                             else noise)
            secs = mb.run_block(eng, rig, hand, who, clock, fps, cap_s)
            summary = eng.session.block_summary or {}
            rows.append({
                "code": code,
                "position": step.get("position", 0), "mode": mode,
                "hand": hand_mode, "phase": who.phase,
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
        "design": "one long session, phases pre / mid / post",
        "dominant_advantage_s": DOMINANT_ADVANTAGE_S,
        "mirror_lead_s": MIRROR_LEAD_S,
        "post_gains_s": POST_GAINS_S,
        "force_post_factor": FORCE_POST_FACTOR,
        "chord_post_factor": CHORD_POST_FACTOR,
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
    budget = 85.0
    print()
    print(f"  {len(mins)} sessions: min {mins[0]:.1f}, median {mid:.1f}, "
          f"max {mins[-1]:.1f} min against a {budget:.0f} min target; "
          f"{sum(1 for m in mins if m > budget)} over")
    print(f"  wall time {(_time.time() - wall0) / 60.0:.1f} min; "
          f"sessions at {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
