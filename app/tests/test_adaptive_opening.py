"""The adaptive controller's opening climb.

From the 30 BPM start the pressure rule climbed at most 15 BPM a trial,
behind a streak gate, so a fast hand took 53 trials to reach the 65 to 80
percent band, longer than the study's 40-trial block: Person 5's block
climbed for its first 30 trials. Until the block's first miss each hit now
raises the pace by fast_start_gain, and the cap is 240 BPM, where a 250 ms
hand had sat above the band at 180 (3 November 2026). The check reads the
hit rate over the block itself: a trailing window can hold the climb's
own misses and look settled while the pace is still too easy.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine  # noqa: E402


def test_each_hit_before_the_first_miss_raises_the_pace_by_the_gain():
    eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
    eng.bpm = 30.0
    seen = []
    for i in range(6):
        eng.record(i % 4, hit=True, rt_ms=400.0)
        seen.append(eng.next_bpm())
    # the first call waits for min_trials, then 20 percent a hit
    assert seen[0] == 30.0
    for a, b in zip(seen[1:], seen[2:]):
        assert abs(b / a - 1.2) < 1e-9


def test_the_first_miss_hands_the_pace_to_the_pressure_rule():
    eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
    eng.bpm = 60.0
    for i in range(3):
        eng.record(i, hit=True, rt_ms=400.0)
        eng.next_bpm()
    eng.record(3, hit=False, rt_ms=None)
    eng.next_bpm()
    assert eng.missed_once and "pressure" in eng.last_decision


def _block_rate(mean_rt: float, seed: int, n: int = 40) -> float:
    """Hit rate over a block of n trials from the 30 BPM start, for a hand
    pressing at mean_rt (SD 40 ms), as analysis/adaptive_band.py drives it."""
    rng = random.Random(seed)
    eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2, bpm_min=10.0))
    eng.bpm = 30.0
    hits = 0
    for i in range(n):
        window_ms = eng.current_timeout_s * 1000.0
        rt = min(mean_rt + 80.0, max(mean_rt - 60.0, rng.gauss(mean_rt, 40.0)))
        hit = rt <= window_ms
        eng.record(i % 4, hit=hit, rt_ms=(rt if hit else None),
                   quality=((1.0 if rt <= 350.0 else 0.75) if hit else 0.0))
        eng.next_bpm()
        hits += hit
    return hits / n


def test_a_40_trial_block_lands_in_the_band_for_hands_of_250_to_800_ms():
    # the study's controller gave 0.84 to 0.96 here for hands of 250 to 350 ms
    for rt in (250, 280, 300, 350, 400, 500, 800):
        rates = [_block_rate(rt, seed) for seed in range(5)]
        mean = sum(rates) / len(rates)
        assert 0.65 <= mean <= 0.80, (rt, rates)
