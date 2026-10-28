"""A slow push and the baseline that follows it.

The baseline follows the smoothed signal while the finger is up, and a
push still rising towards the trigger counts as up, so a slow push is
taken into the resting level before it reaches the trigger. In
simulation a linear rise to the light press over 0.8 s or more is never
counted (28 October 2026). Calibration.baseline_hold holds the baseline
once the push sits that many counts above it, for up to baseline_hold_s.
Replayed over the study's sequence-task streams, a hold small enough to
count every slow ramp also counted extra presses, so it ships off and the
pilot tunes it on patients' pushes. These tests pin both: the limit with
the hold off, and what the hold does when it is on.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS = 200.0
REST = 255
GAP = 70                      # a light press, 70 counts above rest
ON = int(round(0.3 * GAP))    # the study's trigger, 30 percent of the gap


def _count_lag(rise_s: float, **rules) -> float | None:
    """ms from the raw crossing of the trigger to the count, None if the
    push was never counted."""
    cal = Calibration(on_delta=[ON] * 4, off_delta=[ON - 10] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4, **rules)
    det = FSRDetector(cal)
    counted: list[float] = []
    det.on_press = lambda e: counted.append(e.t_perf)
    t0, raw_cross = 2.0, None
    for k in range(int((t0 + rise_s + 1.0) * FS)):
        t = k / FS
        v = REST if t < t0 else REST + GAP * min(1.0, (t - t0) / rise_s)
        v = int(round(v))
        if raw_cross is None and v >= REST + ON:
            raw_cross = t
        det.feed(t, (v, REST, REST, REST))
    return None if not counted else (counted[0] - raw_cross) * 1000.0


def test_off_by_default_so_the_study_detector_is_unchanged():
    assert Calibration().baseline_hold == 0.0


def test_with_the_hold_off_a_slow_push_is_never_counted():
    assert _count_lag(0.4) is not None
    assert _count_lag(1.0) is None
    assert _count_lag(2.0) is None


def test_a_held_baseline_counts_a_slow_push():
    lag = _count_lag(1.0, baseline_hold=10.0)
    assert lag is not None and lag < 100.0   # 85 ms here
    assert _count_lag(1.5, baseline_hold=10.0) is not None


def test_a_held_baseline_moves_a_quick_press_by_at_most_one_sample():
    for rise in (0.1, 0.2):
        off, on = _count_lag(rise), _count_lag(rise, baseline_hold=10.0)
        assert off is not None and on is not None
        assert 0.0 <= off - on <= 1000.0 / FS + 1e-9, (rise, off, on)


def test_the_hold_lets_go_after_baseline_hold_s():
    """A finger that settles 15 counts heavier, short of the trigger, is
    tracked again once the hold runs out, and is never counted."""
    cal = Calibration(on_delta=[ON] * 4, off_delta=[ON - 10] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4,
                      baseline_hold=10.0, baseline_hold_s=0.5)
    det = FSRDetector(cal)
    counted: list[float] = []
    det.on_press = lambda e: counted.append(e.t_perf)
    for k in range(int(6.0 * FS)):
        t = k / FS
        det.feed(t, (REST if t < 1.0 else REST + 15, REST, REST, REST))
    assert not counted
    assert det.baseline_value(0) > REST + 14.0


def test_the_engine_reads_the_hold_from_config():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from finger_rehab.config import Config
    cfg = Config.load()
    assert float(cfg.get("fsr.baseline_hold", -1)) == 0.0
    assert float(cfg.get("fsr.baseline_hold_s", -1)) == 3.0
