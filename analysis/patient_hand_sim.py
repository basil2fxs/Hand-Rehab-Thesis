"""The press detector, as shipped, on presses a patient's hand might make.

No patient has played the device, so this feeds the game's own detector
(app/finger_rehab/hardware/fsr_detector.py at the config's settings) the
kinds of force a weak, slow or shaking hand would put on a pad, with the
pads' measured noise (1.2 to 1.5 counts SD):

  weak and slow: smooth pushes to a light press of 20 counts, the smallest
  gap calibration accepts (and 40 and 70), rising over 0.1 to 3 s and held
  1 s, the trigger set as calibration sets it: 30 percent of the gap, never
  under its 12-count floor (calibration_profile.press_floor_counts). Each
  must be counted once.

  tremor at rest: ten minutes of a resting finger with a 4 to 6 Hz tremor
  of 1 to 16 counts peak (19.5 mN a count), the frequency of parkinsonian
  rest tremor, against the same triggers. Nothing should be counted.

  tremor on a press: the 20-count push with a 5 Hz tremor riding on it,
  which must still be counted once and released once.

    cd analysis
    python3 patient_hand_sim.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
from finger_rehab.hardware.calibration_profile import CalibrationProfile, MIN_DELTA_COUNTS  # noqa: E402
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS = 200.0
REST = 265


def shipped(on: int, off: int | None = None) -> Calibration:
    """The config's detector, with one finger's trigger at `on` counts and its
    release margin `off`, by default as a healthy calibration sets it
    (trigger less ten, at least 3)."""
    f = yaml.safe_load((APP / "config" / "default.yaml").read_text(encoding="utf-8"))["fsr"]
    keys = ("baseline_alpha", "value_alpha", "debounce_ms", "release_frac", "rest_release_s",
            "hold_max_s", "baseline_down_alpha", "baseline_hold", "baseline_hold_s",
            "count_on", "count_samples")
    off = max(3, on - 10) if off is None else off
    return Calibration(on_delta=[on] * 4, off_delta=[off] * 4,
                       abs_on_min=[0] * 4, abs_off_max=[4095] * 4, **{k: f[k] for k in keys})


def run(trace: np.ndarray, on: int, off: int | None = None) -> tuple[int, int]:
    det = FSRDetector(shipped(on, off))
    det.baseline = [float(REST)] * 4
    presses, releases = [], []
    det.on_press = lambda e: presses.append(e.t_perf)
    det.on_release = lambda e: releases.append(e.t_perf)
    for k, v in enumerate(trace):
        det.feed(k / FS, (int(round(v)), REST, REST, REST))
    return len(presses), len(releases)


def push(gap: float, rise_s: float, rng, sd: float, tremor: float = 0.0) -> np.ndarray:
    """Rest 2 s, a smooth rise to the gap, a 1 s hold, a smooth fall, rest 2 s."""
    seg = [np.zeros(int(2 * FS))]
    u = np.arange(int(rise_s * FS)) / (rise_s * FS)
    seg.append(gap * 0.5 * (1 - np.cos(np.pi * u)))
    seg.append(np.full(int(1.0 * FS), gap))
    seg.append(gap * 0.5 * (1 + np.cos(np.pi * np.arange(int(0.2 * FS)) / (0.2 * FS))))
    seg.append(np.zeros(int(2 * FS)))
    x = np.concatenate(seg)
    t = np.arange(len(x)) / FS
    x = x + tremor * np.sin(2 * np.pi * 5.0 * t) + rng.normal(0.0, sd, len(x))
    return REST + x


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    rng = np.random.default_rng(2026)
    res: dict = {"pushes": {}, "rest_tremor": {}, "press_tremor": {}}
    for gap in (20, 40, 70):
        on = max(MIN_DELTA_COUNTS, int(round(0.3 * gap)))
        ok, n = 0, 0
        for rise in (0.1, 0.2, 0.4, 0.8, 1.5, 2.0, 3.0):
            for sd in (1.2, 1.5):
                for _ in range(10):
                    p, r = run(push(gap, rise, rng, sd), on)
                    n += 1
                    ok += int(p == 1 and r == 1)
        res["pushes"][gap] = {"trigger": on, "counted_once": ok, "of": n}
        print(f"push to {gap} counts (trigger {on}), rises 0.1 to 3 s: {ok} of {n} counted and released once")
    for on in (12, 21):
        row = {}
        for amp in (1, 2, 4, 6, 8, 10, 12, 16):
            t = np.arange(int(600 * FS)) / FS
            f = rng.uniform(4.0, 6.0)
            trace = REST + amp * np.sin(2 * np.pi * f * t) + rng.normal(0.0, 1.5, len(t))
            row[amp] = run(trace, on)[0]
        res["rest_tremor"][on] = row
        quiet = max([a for a, c in row.items() if c == 0], default=0)
        print(f"trigger {on} counts: false counts in 10 min of rest tremor by peak amplitude {row}; "
              f"none up to {quiet} counts")
    for amp in (1, 2, 4, 6, 8):
        ok, n = 0, 0
        for rise in (0.2, 0.8, 2.0):
            for _ in range(10):
                p, r = run(push(20, rise, rng, 1.5, tremor=amp), MIN_DELTA_COUNTS)
                n += 1
                ok += int(p == 1 and r == 1)
        res["press_tremor"][amp] = {"counted_once": ok, "of": n}
        print(f"20-count push with a 5 Hz tremor of {amp} counts: {ok} of {n} counted and released once")
    # the tremor floor of 3 November 2026: calibration reads the resting
    # finger's spread and keeps the trigger above it
    res["tremor_floor"] = {}
    for amp in (10, 12, 16):
        t = np.arange(int(30 * FS)) / FS
        rest = amp * np.sin(2 * np.pi * 5.0 * t) + rng.normal(0.0, 1.5, len(t))
        spread = float(np.std(rest))
        gap = 4.0 * amp
        prof = CalibrationProfile(empty=[255.0] * 4, empty_noise=[1.2] * 4, resting=[float(REST)] * 4,
                                  resting_noise=[spread] * 4, press=[REST + gap] * 4)
        on, off = prof.on_delta()[0], prof.off_delta()[0]
        t10 = np.arange(int(600 * FS)) / FS
        f = rng.uniform(4.0, 6.0)
        false = run(REST + amp * np.sin(2 * np.pi * f * t10) + rng.normal(0.0, 1.5, len(t10)), on, off)[0]
        ok, n = 0, 0
        for rise in (0.2, 0.8, 2.0):
            for _ in range(10):
                p, r = run(push(gap, rise, rng, 1.5, tremor=amp), on, off)
                n += 1
                ok += int(p == 1 and r == 1)
        res["tremor_floor"][amp] = {"trigger": on, "release": off, "false_10min": false,
                                    "counted_once": ok, "of": n}
        print(f"tremor {amp} counts, trigger raised to {on}, release {off}: {false} false counts in 10 min; "
              f"a {gap:.0f}-count push with it {ok} of {n} counted and released once")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
