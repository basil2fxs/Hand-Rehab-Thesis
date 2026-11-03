"""The detector's code defaults are the device's settings, and the press
count follows the raw force.

Calibration() is what every simulation builds when it does not read the
config, so a default that differs from config/default.yaml makes the
simulation a different detector from the one the device runs. The
baseline rate did: 0.02 in the code against 0.0005 shipped, and the ramp
simulations of 28 October 2026 found slow pushes uncounted that the
device counts (3 November 2026). The force constant was the same kind of
fault, and the same kind of test now holds it.

From 3 November 2026 a press is counted on the second raw sample in a row
at or above the trigger, one sample after the raw force crosses it,
where the smoothed value had come one or two samples later, more on a
slow press.
"""
from __future__ import annotations

import sys
from dataclasses import fields
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

APP = Path(__file__).resolve().parents[1]
FS = 200.0
REST = 255
ON = 21                      # 30 percent of a 70-count light press


def _shipped_fsr() -> dict:
    return yaml.safe_load((APP / "config" / "default.yaml").read_text(encoding="utf-8"))["fsr"]


def test_every_rule_default_matches_the_shipped_config():
    fsr = _shipped_fsr()
    rules = ("baseline_alpha", "value_alpha", "debounce_ms", "release_frac",
             "rest_release_s", "hold_max_s", "baseline_down_alpha", "baseline_hold",
             "baseline_hold_s", "count_on", "count_samples")
    defaults = {f.name: f.default for f in fields(Calibration)}
    for key in rules:
        assert key in fsr, f"fsr.{key} is not in default.yaml"
        assert defaults[key] == fsr[key], (key, defaults[key], fsr[key])


def _feed(values: list[int], **rules) -> list[int]:
    """Sample indices at which lane 0 was counted."""
    cal = Calibration(on_delta=[ON] * 4, off_delta=[ON - 10] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4, **rules)
    det = FSRDetector(cal)
    det.baseline = [float(REST)] * 4
    out: list[int] = []
    det.on_press = lambda e: out.append(int(round(e.t_perf * FS)))
    for k, v in enumerate(values):
        det.feed(k / FS, (v, REST, REST, REST))
    return out


def test_a_press_is_counted_one_sample_after_the_raw_crossing():
    # a push rising 8 counts a sample, about a 45 ms rise to the light press
    vals = [REST] * 20 + [REST + 8 * k for k in range(1, 10)] + [REST + 72] * 40
    first_over = 22                       # REST + 24, the first sample over REST + 21
    assert _feed(vals) == [first_over + 1]
    # the old rule waited for the smoothed value, a sample later here
    assert _feed(vals, count_on="smoothed") == [first_over + 2]


def test_one_noisy_sample_cannot_count_a_press():
    spike = [REST] * 20 + [REST + 70] + [REST] * 40
    assert _feed(spike) == []
    # the smoothed value took 35 percent of it, over the 21-count trigger
    assert len(_feed(spike, count_on="smoothed")) == 1


def _ramp(rise_s: float, **rules) -> float | None:
    """ms from the raw crossing to the count on a linear rise to 70 counts,
    None if it was never counted. The crossing is read against the
    detector's own live threshold, as analysis/count_lag.py reads it."""
    cal = Calibration(on_delta=[ON] * 4, off_delta=[ON - 10] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4, **rules)
    det = FSRDetector(cal)
    det.baseline = [float(REST)] * 4
    got: list[int] = []
    det.on_press = lambda e: got.append(int(round(e.t_perf * FS)))
    cross = None
    for k in range(int((2.0 + rise_s + 1.0) * FS)):
        t = k / FS
        v = int(round(REST if t < 2.0 else REST + 70 * min(1.0, (t - 2.0) / rise_s)))
        det.feed(t, (v, REST, REST, REST))
        if cross is None and v >= det.baseline[0] + ON:
            cross = k
        if got:
            break
    return None if not got else (got[0] - cross) * 1000.0 / FS


def test_at_the_shipped_settings_every_slow_push_to_3_s_is_counted():
    for rise in (0.4, 1.0, 2.0, 3.0):
        assert _ramp(rise) == 5.0, rise
        lag = _ramp(rise, count_on="smoothed")
        assert lag is not None and lag < 100.0, (rise, lag)


def test_the_slow_push_limit_belonged_to_the_old_code_default():
    # the 0.25 s baseline of the old default took the push in before the trigger
    assert _ramp(1.0, baseline_alpha=0.02, count_on="smoothed") is None
