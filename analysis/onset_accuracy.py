"""How close the press check's onset rule comes to a push's true start.

Smooth pushes (a half-cosine rise from rest to a peak) with the pads'
measured noise added, 1.2 and 1.5 counts SD, go through the game's
press detector to get the counted sample, then through press_onset as
press_check.py calls it; the error is the found onset minus the true
start of the push. Quick pushes (rises of 100 to 200 ms) come out within
about 7 ms early to 15 ms late; slower pushes are read later, so a lag
measured from the onset reads short on a slow push, and a lag that falls
as pushes steepen is, if anything, understated by the press check.

Run from the repository root:
    python3 analysis/onset_accuracy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
from finger_rehab.analytics.signal import press_onset  # noqa: E402
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS, REST = 200.0, 255
PEAKS = (70, 150)
RISES = (100, 150, 200, 300, 400)
NOISE_SD = (1.2, 1.5)
PHASES = np.linspace(0.0, 1.0 / FS, 10, endpoint=False)


def onset_error_ms(rise_ms: float, peak: int, sd: float, phase: float, rng) -> float | None:
    """Found onset minus true start in ms; None if the push was never
    counted, nan if it was counted but no onset was found."""
    on = max(1, int(round(0.3 * peak)))
    det = FSRDetector(Calibration(on_delta=[on] * 4, off_delta=[max(1, on - 10)] * 4,
                                  abs_on_min=[0] * 4, abs_off_max=[4095] * 4))
    det.baseline = [float(REST)] * 4
    hits: list[float] = []
    det.on_press = lambda e: hits.append(e.t_perf)
    t0, rise = 2.0 + phase, rise_ms / 1000.0
    n = int((t0 + rise + 0.8) * FS)
    t = np.arange(n) / FS
    u = np.clip((t - t0) / rise, 0.0, 1.0)
    raw = np.round(REST + peak * 0.5 * (1.0 - np.cos(np.pi * u)) + rng.normal(0.0, sd, n))
    for k in range(n):
        det.feed(t[k], (int(raw[k]), REST, REST, REST))
    if not hits:
        return None
    k = int(round(hits[0] * FS))
    o = press_onset(raw - REST, k, FS)
    return float("nan") if o is None else (t[o] - t0) * 1000.0


def main() -> int:
    rng = np.random.default_rng(7)
    print("peak  rise ms  found  median error ms  range ms")
    for peak in PEAKS:
        for rise in RISES:
            errs = [onset_error_ms(rise, peak, sd, ph, rng) for sd in NOISE_SD for ph in PHASES]
            errs = [e for e in errs if e is not None]
            found = [e for e in errs if np.isfinite(e)]
            med = np.median(found) if found else float("nan")
            lo, hi = (min(found), max(found)) if found else (float("nan"), float("nan"))
            print(f"{peak:4d}  {rise:7d}  {len(found):2d}/{len(errs):2d}  {med:+15.1f}  {lo:+.1f} to {hi:+.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
