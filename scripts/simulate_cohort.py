"""Simulate the healthy baseline cohort through the real engine.

Participant codes (24 by default, --n for more) play the study
battery twice, seven days apart, the way the research assistant
runs it: log in with the
intake fields, start the battery, take every NEXT UP step, end the
session. The engine, the modes, the loggers and the battery runner
are the shipped ones (scripts/measure_battery.py supplies the model
hand on a fake 200 Hz sensor stream and the simulated clock); only
the person is synthetic.

Each code carries latent skill so the cohort chapter of the notebook
has something to find:

  reaction   a per-person base RT (stable across visits), the
             dominant hand 25 ms faster, visit 2 10 ms faster than
             visit 1, 45 ms trial-to-trial noise
  mirror     the dominant hand's press leads the other by 15 ms
  rhythm     a per-person negative asynchrony and jitter
  echo       a per-person span ceiling (the ladder fails past it)
  buzz hunt  a per-person localisation accuracy; errors land on
             the neighbouring finger
  pattern    trained-sequence presses speed up with exposure and
             the exposure carries into visit 2 (retention)
  force      the hold noise is drawn PER VISIT with no per-person
             part, so force error is the metric that should come
             out unreliable

The truth behind every code is written to <out>/truth.json and the
measured minutes per visit to <out>/durations.csv, so an analysis
run over <out>/sessions can be checked against what was injected.

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
import datetime as _dt
import json
import os
import random
import shutil
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
PRACTICE_S = 0.010
MIRROR_LEAD_S = 0.015
RETEST_DAYS = 7


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
            # Force noise per visit, no person part: see the module doc.
            "force_noise_sd": [rng.uniform(0.4, 2.2), rng.uniform(0.4, 2.2)],
        }
    return truth


class CohortParticipant(mb.Participant):
    """The model participant with a person behind it."""

    def __init__(self, hand: mb.HandModel, rng: random.Random,
                 truth: dict, visit: int, seq_presses: int) -> None:
        super().__init__(hand, rng)
        self.truth = truth
        self.visit = visit
        self.seq_presses = seq_presses      # pattern exposure so far
        self.hand_mode = "right"

    # ---- hands and reaction times -------------------------------------
    def lane_hand(self, lane: int) -> str:
        if self.hand_mode == "both":
            return "right" if int(lane) < 4 else "left"
        return self.hand_mode

    def rt_for(self, lane: int) -> float:
        base = float(self.truth["rt_s"])
        if self.lane_hand(lane) != self.truth["dominant"]:
            base += DOMINANT_ADVANTAGE_S
        if self.visit >= 2:
            base -= PRACTICE_S
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
        # One shared reaction, then the dominant hand lands first.
        t = act.stim_t_perf + self.rt_for(act.finger) + 0.05
        right, left = act.finger, act.finger + 4
        lead = MIRROR_LEAD_S / 2.0
        if self.truth["dominant"] == "right":
            self.schedule(t - lead, right)
            self.schedule(t + lead + self.rng.gauss(0.0, 0.01), left)
        else:
            self.schedule(t + lead + self.rng.gauss(0.0, 0.01), right)
            self.schedule(t - lead, left)

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
            # and the exposure count carries across visits.
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
            # Past the span: one wrong press ends the trial.
            wrong = next(l for l in m.lanes if l != seq[0])
            self.schedule(t, int(wrong))
            return
        for lane in seq:
            self.schedule(t, int(lane))
            t += 0.55

    def _rhythm(self, m, now, eng) -> None:
        if not getattr(m, "_countdown_done", False):
            return
        for s in m.upcoming(0.6):
            key = ("rhythm", s.index)
            if key in self.answered or s.hit_at is not None:
                continue
            self.answered.add(key)
            until = float(s.note.t) - float(m.song_time)
            asyn = self.rng.gauss(float(self.truth["asyn_s"]),
                                  float(self.truth["asyn_sd_s"]))
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
        self.schedule(max(now, t0) + self.rt_for(lane) + 0.15, lane)


def build_engine(code: str, truth: dict, visit: int, data_dir: Path,
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
        visit=str(visit),
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


def play_visit(code: str, truth: dict, visit: int, data_dir: Path,
               clock: mb.SimClock, fps: float, cap_s: float,
               seq_presses: int, seed: int) -> tuple[list, float, int]:
    """One visit: login, battery, every NEXT UP, end session.
    Returns (rows per block, total simulated minutes, pattern exposure)."""
    rig = mb.FakeRig()
    hand = mb.HandModel(rng=random.Random(seed))
    hand.noise_sd = float(truth["force_noise_sd"][visit - 1])
    who = CohortParticipant(hand, random.Random(seed + 1), truth, visit,
                            seq_presses)
    eng = build_engine(code, truth, visit, data_dir, rig)
    rows = []
    transitions_s = 0.0
    try:
        ok, reason = eng.battery_available()
        if not ok:
            raise SystemExit(f"{code} visit {visit}: battery unavailable: "
                             f"{reason}")
        if not eng.start_battery():
            raise SystemExit(f"{code} visit {visit}: battery did not start")
        while eng.block_is_running():
            mode = str(eng.current_block)
            hand_mode = str(eng.hand_mode)
            step = dict(eng._protocol_current or {})
            secs = mb.run_block(eng, rig, hand, who, clock, fps, cap_s)
            summary = eng.session.block_summary or {}
            rows.append({
                "code": code, "visit": visit,
                "position": step.get("position", 0), "mode": mode,
                "hand": hand_mode, "minutes": secs / 60.0,
                "status": summary.get("status", "?"),
                "trials": summary.get("trials", ""),
            })
            nxt = eng.pending_protocol_step()
            if nxt is None:
                break
            gap = mb.TRANSITION_S + float(nxt.get("stretch_s") or 0.0)
            transitions_s += gap
            clock.t += gap
            eng.continue_protocol()
        progress = eng.battery_progress() or {}
        if not progress.get("finished"):
            print(f"  {code} visit {visit}: battery did not finish",
                  file=sys.stderr)
        eng.end_session()
    finally:
        try:
            eng._close_loggers()
        except Exception:
            pass
    blocks_s = sum(r["minutes"] for r in rows) * 60.0
    total_min = (mb.LOGIN_S + mb.QUICK_CAL_S + blocks_s + transitions_s) / 60.0
    return rows, total_min, who.seq_presses


def move_day(root: Path, old_day: str, new_day: str,
             codes: set[str]) -> None:
    """Move the given codes' game folders from one day folder to
    another and fix the index rows that point at them, so visit 1
    sits a week before visit 2 the way it would on disk. Other
    codes' folders stay where they are (a later run can add codes
    to a tree that already holds two visits of the first ones)."""
    src, dst = root / old_day, root / new_day
    if not src.is_dir():
        return
    dst.mkdir(exist_ok=True)
    for p in list(src.iterdir()):
        if p.is_dir() and p.name.split("_")[0] in codes:
            shutil.move(str(p), str(dst / p.name))
    if not any(src.iterdir()):
        src.rmdir()
    index = root / "sessions_index.csv"
    if index.is_file():
        out = []
        for line in index.read_text(encoding="utf-8").splitlines(True):
            cells = line.split(",")
            if len(cells) > 2 and cells[2] in codes:
                line = (line.replace(f"{old_day}/", f"{new_day}/")
                        .replace(f"{old_day},", f"{new_day},", 1))
            out.append(line)
        index.write_text("".join(out), encoding="utf-8")


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
        "dominant_advantage_s": DOMINANT_ADVANTAGE_S,
        "practice_s": PRACTICE_S, "mirror_lead_s": MIRROR_LEAD_S,
        "retest_days": RETEST_DAYS, "participants": truth},
        indent=2), encoding="utf-8")

    real_perf = _time.perf_counter
    clock = mb.SimClock(real_perf())
    _time.perf_counter = lambda: clock.t
    wall0 = _time.time()
    today = _time.strftime("%Y-%m-%d")
    day1 = (_dt.date.today() - _dt.timedelta(days=RETEST_DAYS)).isoformat()
    exposure: dict[str, int] = {c: 0 for c in truth}
    block_rows: list[dict] = []
    visit_rows: list[dict] = []
    try:
        for visit in (1, 2):
            for i, (code, t) in enumerate(truth.items()):
                if code not in todo:
                    continue
                if visit == 2:
                    from finger_rehab.data.intake import suggest_visit
                    suggested = suggest_visit(root, code)
                    if suggested != 2:
                        print(f"  {code}: login would suggest visit "
                              f"{suggested}, not 2", file=sys.stderr)
                rows, total_min, exposure[code] = play_visit(
                    code, t, visit, root, clock, args.fps,
                    args.cap_min * 60.0, exposure[code],
                    args.seed * 100 + i * 2 + visit)
                block_rows.extend(rows)
                completed = sum(1 for r in rows if r["status"] == "completed")
                visit_rows.append({"code": code, "visit": visit,
                                   "dominant": t["dominant"],
                                   "blocks": len(rows),
                                   "completed": completed,
                                   "minutes": round(total_min, 2)})
                print(f"{code} visit {visit} {t['dominant']:5s} "
                      f"{total_min:6.2f} min  {completed}/10 completed",
                      flush=True)
            if visit == 1:
                move_day(root, today, day1, set(todo))
    finally:
        _time.perf_counter = real_perf
    for name, rows in (("durations.csv", visit_rows),
                       ("blocks.csv", block_rows)):
        path = out / name
        append = args.first > 1 and path.is_file()
        with path.open("a" if append else "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if not append:
                w.writeheader()
            w.writerows(rows)
    mins = sorted(r["minutes"] for r in visit_rows)
    mid = mins[len(mins) // 2]
    print()
    print(f"  {len(mins)} visits: min {mins[0]:.1f}, median {mid:.1f}, "
          f"max {mins[-1]:.1f} min against a 50 min budget; "
          f"{sum(1 for m in mins if m > 50)} over")
    print(f"  wall time {(_time.time() - wall0) / 60.0:.1f} min; "
          f"sessions at {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
