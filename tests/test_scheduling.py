"""Target scheduling: equal finger counts, equal hand counts, and a floor
under the adaptive weighting.

These are the guarantees the analysis depends on. A cross-finger reaction-time
comparison is only meaningful if the fingers were cued a comparable number of
times, so the balance properties are asserted at every trial rather than just
at the end of a block, and over many seeds rather than one.
"""
from __future__ import annotations

import random

import pytest

from rehab.game.scheduling import (
    BalancedScheduler, PairedBalancedScheduler, FloorWeightedScheduler,
)


LANES4 = [0, 1, 2, 3]


class TestBalancedScheduler:
    def test_counts_never_drift_more_than_one(self):
        """Checked after EVERY trial, not just at the end. A block stopped
        early must still be balanced."""
        for seed in range(100):
            s = BalancedScheduler(LANES4, random.Random(seed))
            for _ in range(83):
                s.next()
                assert s.spread() <= 1

    def test_full_rounds_are_exactly_equal(self):
        s = BalancedScheduler(LANES4, random.Random(0))
        s.sequence(60)
        assert set(s.counts.values()) == {15}

    def test_no_consecutive_repeats(self):
        """A finger cued twice running lets the patient keep it hovering, so
        the reaction time measures anticipation rather than response."""
        for seed in range(100):
            s = BalancedScheduler(LANES4, random.Random(seed))
            seq = s.sequence(80)
            assert all(a != b for a, b in zip(seq, seq[1:])), f"seed {seed}"

    def test_order_is_not_fixed(self):
        """Balanced must not mean predictable: a patient who learns the order
        stops reacting and starts anticipating."""
        seqs = {tuple(BalancedScheduler(LANES4, random.Random(s)).sequence(12))
                for s in range(30)}
        assert len(seqs) > 5

    def test_beats_plain_random_on_balance(self):
        """The behaviour this replaces. Plain random choice routinely lands a
        spread of 5 or more over 40 trials, which is enough to make a
        per-finger comparison meaningless."""
        worst_random = 0
        for seed in range(100):
            r = random.Random(seed)
            c = [0] * 4
            for _ in range(40):
                c[r.randrange(4)] += 1
            worst_random = max(worst_random, max(c) - min(c))
        worst_balanced = 0
        for seed in range(100):
            s = BalancedScheduler(LANES4, random.Random(seed))
            s.sequence(40)
            worst_balanced = max(worst_balanced, s.spread())
        assert worst_random >= 5
        assert worst_balanced <= 1

    def test_single_lane_degrades_gracefully(self):
        s = BalancedScheduler([2], random.Random(0))
        assert s.sequence(5) == [2] * 5

    def test_two_lanes_alternate_without_repeats(self):
        s = BalancedScheduler([0, 1], random.Random(0))
        seq = s.sequence(40)
        assert all(a != b for a, b in zip(seq, seq[1:]))
        assert s.counts == {0: 20, 1: 20}

    def test_eight_lanes_balanced(self):
        s = BalancedScheduler(list(range(8)), random.Random(0))
        s.sequence(80)
        assert set(s.counts.values()) == {10}

    def test_non_contiguous_lane_ids(self):
        s = BalancedScheduler([4, 5, 6, 7], random.Random(0))
        s.sequence(40)
        assert s.counts == {4: 10, 5: 10, 6: 10, 7: 10}

    def test_empty_lane_list_rejected(self):
        with pytest.raises(ValueError):
            BalancedScheduler([], random.Random(0))


class TestPairedBalancedScheduler:
    HANDS = {"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]}

    def test_hands_stay_equal(self):
        """Comparing an affected hand to an unaffected one only means
        something if both were cued the same number of times."""
        for seed in range(60):
            p = PairedBalancedScheduler(self.HANDS, random.Random(seed))
            for _ in range(96):
                p.next()
                assert p.hand_spread() <= 1

    def test_fingers_within_each_hand_stay_equal(self):
        """Balancing hands alone is not enough: 50/50 between hands is
        satisfied by a left hand that only ever cues its index finger."""
        for seed in range(60):
            p = PairedBalancedScheduler(self.HANDS, random.Random(seed))
            for _ in range(96):
                p.next()
                assert p.finger_spread() <= 1

    def test_full_block_is_exactly_even(self):
        p = PairedBalancedScheduler(self.HANDS, random.Random(3))
        for _ in range(80):
            p.next()
        assert p.hand_counts == {"right": 40, "left": 40}
        assert set(p.counts().values()) == {10}

    def test_next_returns_hand_with_lane(self):
        p = PairedBalancedScheduler(self.HANDS, random.Random(0))
        for _ in range(40):
            hand, lane = p.next()
            assert lane in self.HANDS[hand], "lane must belong to its hand"

    def test_single_hand_still_works(self):
        p = PairedBalancedScheduler({"right": [0, 1, 2, 3]}, random.Random(0))
        for _ in range(40):
            p.next()
        assert p.hand_counts == {"right": 40}
        assert set(p.counts().values()) == {10}

    def test_empty_hands_rejected(self):
        with pytest.raises(ValueError):
            PairedBalancedScheduler({"right": [], "left": []})


class TestFloorWeightedScheduler:
    # Pinky struggling, index strong: the shape adaptive mode produces.
    WEAK_PINKY = [0.05, 0.10, 0.15, 0.70]

    def test_unfloored_weighting_starves_the_strong_finger(self):
        """Why the floor exists. Straight weighted choice can leave a finger
        with a handful of trials, too few to say anything about."""
        r = random.Random(7)
        c = [0] * 4
        for _ in range(60):
            u, acc = r.random(), 0.0
            for i, w in enumerate(self.WEAK_PINKY):
                acc += w
                if u <= acc:
                    c[i] += 1
                    break
        assert min(c) / 60 < 0.10

    def test_floor_is_honoured_within_one_trial(self):
        """The floor forces a pick once a lane is a whole trial behind its
        owed rate, so the shortfall is bounded by one trial rather than by
        luck."""
        for seed in range(200):
            f = FloorWeightedScheduler(4, min_share=0.15,
                                       rng=random.Random(seed))
            for _ in range(60):
                f.next(self.WEAK_PINKY)
            owed = 0.15 * 60
            assert min(f.counts) >= owed - 1

    def test_adaptivity_survives_the_floor(self):
        """The weak finger must still get the most practice, otherwise the
        floor has quietly turned adaptive mode into classic."""
        f = FloorWeightedScheduler(4, min_share=0.15, rng=random.Random(7))
        for _ in range(60):
            f.next(self.WEAK_PINKY)
        assert f.counts[3] == max(f.counts)
        assert f.counts[3] > f.counts[0] * 1.5

    def test_most_picks_are_still_weight_driven(self):
        f = FloorWeightedScheduler(4, min_share=0.15, rng=random.Random(7))
        for _ in range(60):
            f.next(self.WEAK_PINKY)
        assert f.forced < 15, "the floor should nudge, not take over"

    def test_min_share_capped_so_floors_cannot_exceed_the_block(self):
        f = FloorWeightedScheduler(4, min_share=0.90)
        assert f.min_share == pytest.approx(0.25)

    def test_max_floor_gives_near_exact_balance(self):
        f = FloorWeightedScheduler(4, min_share=0.25, rng=random.Random(0))
        for _ in range(60):
            f.next(self.WEAK_PINKY)
        assert max(f.counts) - min(f.counts) <= 2

    def test_zero_floor_leaves_weighting_untouched(self):
        f = FloorWeightedScheduler(4, min_share=0.0, rng=random.Random(7))
        for _ in range(60):
            f.next(self.WEAK_PINKY)
        assert f.forced == 0

    def test_no_consecutive_repeats_under_weighting(self):
        for seed in range(50):
            f = FloorWeightedScheduler(4, min_share=0.15,
                                       rng=random.Random(seed))
            seq = [f.next(self.WEAK_PINKY) for _ in range(60)]
            assert all(a != b for a, b in zip(seq, seq[1:])), f"seed {seed}"

    def test_survives_degenerate_weights(self):
        for bad in (None, [], [0, 0, 0, 0], [1, 2], [-1, -1, -1, -1],
                    [float("nan")] * 4):
            f = FloorWeightedScheduler(4, min_share=0.15,
                                       rng=random.Random(0))
            try:
                picks = [f.next(bad) for _ in range(20)]
            except (TypeError, ValueError):
                pytest.fail(f"weights {bad!r} raised")
            assert all(0 <= p < 4 for p in picks), f"weights {bad!r}"

    def test_all_weight_on_one_lane_still_respects_the_floor(self):
        f = FloorWeightedScheduler(4, min_share=0.15, rng=random.Random(0))
        for _ in range(80):
            f.next([1.0, 0.0, 0.0, 0.0])
        assert min(f.counts) >= 0.15 * 80 - 1

    def test_rejects_zero_lanes(self):
        with pytest.raises(ValueError):
            FloorWeightedScheduler(0)
