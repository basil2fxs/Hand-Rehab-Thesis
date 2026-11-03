"""A resting tremor raises the press trigger above it.

Calibration set each trigger from the empty pad's noise and the resting
load, never from how much the resting finger moves. On the shipped
detector a 12-count trigger, the calibration's floor, stayed silent
through ten minutes of a 4 to 6 Hz tremor of 8 counts peak and counted
189 presses at 10 (analysis/patient_hand_sim.py, 3 November 2026). The
resting capture now keeps each pad's SD with the hand on it, and the
trigger floor sits at 2.5 times the tremor's peak.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.hardware.calibration_profile import (  # noqa: E402
    CalibrationProfile, MIN_DELTA_COUNTS, press_floor_counts)
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS = 200.0
REST = 265.0


def _profile(spread: float, gap: float = 60.0) -> CalibrationProfile:
    return CalibrationProfile(empty=[255.0] * 4, empty_noise=[1.2] * 4,
                              resting=[REST] * 4, resting_noise=[spread] * 4,
                              press=[REST + gap] * 4)


def test_a_healthy_resting_finger_leaves_the_floor_where_it_was():
    for spread in (0.0, 1.5, 3.0):
        assert press_floor_counts(10.0, 1.2, spread) == press_floor_counts(10.0, 1.2)
    assert _profile(1.5).on_delta() == _profile(0.0).on_delta()


def test_a_tremor_lifts_the_trigger_clear_of_its_peak():
    for peak in (10.0, 12.0, 16.0):
        spread = math.sqrt(peak ** 2 / 2 + 1.5 ** 2)     # a sine plus the pad's noise
        prof = _profile(spread, gap=4 * peak)
        on, off = prof.on_delta()[0], prof.off_delta()[0]
        assert on >= 2.5 * peak and on > MIN_DELTA_COUNTS, (peak, on)
        # the release stays above the resting level, so a finger that
        # stops shaking still lets go
        assert off > 0, (peak, on, off)


def test_the_lifted_trigger_counts_nothing_through_the_tremor():
    rng = np.random.default_rng(3)
    peak = 12.0
    spread = math.sqrt(peak ** 2 / 2 + 1.5 ** 2)
    on = _profile(spread, gap=4 * peak).on_delta()[0]
    det = FSRDetector(Calibration(on_delta=[on] * 4, off_delta=[on - 10] * 4,
                                  abs_on_min=[0] * 4, abs_off_max=[4095] * 4))
    det.baseline = [REST] * 4
    counted = []
    det.on_press = lambda e: counted.append(e.t_perf)
    t = np.arange(int(120 * FS)) / FS
    trace = REST + peak * np.sin(2 * np.pi * 5.0 * t) + rng.normal(0.0, 1.5, len(t))
    for k, v in enumerate(trace):
        det.feed(t[k], (int(round(v)), int(REST), int(REST), int(REST)))
    assert counted == []


def test_old_profiles_load_without_the_field(tmp_path):
    import json
    p = tmp_path / "old.json"
    data = {"empty": [255.0] * 4, "empty_noise": [1.2] * 4, "resting": [REST] * 4,
            "press": [REST + 40.0] * 4}
    p.write_text(json.dumps(data), encoding="utf-8")
    prof = CalibrationProfile.load(p)
    assert prof is not None and prof.resting_noise == [0.0] * 4
    assert prof.on_delta() == _profile(0.0, gap=40.0).on_delta()


def test_a_slow_press_with_the_tremor_on_it_counts_once():
    # the release sits below the trigger by the tremor's swing, so the
    # tremor riding on a slow press cannot release it and count it again
    rng = np.random.default_rng(4)
    peak, gap = 12.0, 48.0
    spread = math.sqrt(peak ** 2 / 2 + 1.5 ** 2)
    prof = _profile(spread, gap=gap)
    on, off = prof.on_delta()[0], prof.off_delta()[0]
    assert on - off > 2 * 0.9 * peak
    for _ in range(5):
        det = FSRDetector(Calibration(on_delta=[on] * 4, off_delta=[off] * 4,
                                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4))
        det.baseline = [REST] * 4
        presses, releases = [], []
        det.on_press = lambda e: presses.append(e.t_perf)
        det.on_release = lambda e: releases.append(e.t_perf)
        u = np.arange(int(2.0 * FS)) / (2.0 * FS)
        x = np.concatenate([np.zeros(int(2 * FS)), gap * 0.5 * (1 - np.cos(np.pi * u)),
                            np.full(int(FS), gap), np.zeros(int(2 * FS))])
        t = np.arange(len(x)) / FS
        x = REST + x + peak * np.sin(2 * np.pi * 5.0 * t) + rng.normal(0.0, 1.5, len(x))
        for k, v in enumerate(x):
            det.feed(t[k], (int(round(v)), int(REST), int(REST), int(REST)))
        assert len(presses) == 1 and len(releases) == 1


def test_a_healthy_spread_leaves_the_release_where_it_was():
    assert _profile(1.5).off_delta() == _profile(0.0).off_delta()
