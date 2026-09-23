"""Target schedulers: who gets cued next, and how often.

Two problems have to be solved at once, and they pull against each other.

The RESEARCH problem. Every cross-finger comparison in the analysis assumes
each finger got a fair number of attempts. Ten trials on the index against two
on the pinky makes the pinky's reaction time an average of two numbers, which
is noise, and the difference between fingers then says more about how often
they were asked than about the hand. The same goes for the two hands in
bilateral mode: comparing an affected hand to an unaffected one only means
something if both were cued the same number of times.

The THERAPY problem. Adaptive mode deliberately gives a weak finger more
practice. That is the point of the mode, and flattening it to a uniform split
would remove the reason it exists.

So there are two schedulers here:

    BalancedScheduler       exact equal counts, unpredictable order.
                            Used where there is no therapeutic reason to
                            favour any finger: classic, rhythm, bilateral.

    FloorWeightedScheduler  keeps the adaptive weighting, but no lane is
                            allowed to fall below a guaranteed share. Weak
                            fingers still get extra practice; every finger
                            still ends up with enough trials to analyse.

Both avoid consecutive repeats where they can, because a finger cued twice in
a row lets the patient keep their finger hovering and gives a reaction time
that measures anticipation rather than response.
"""
from __future__ import annotations

import random


class BalancedScheduler:
    """Equal counts per lane, in an order the patient cannot predict.

    Works as a shuffle bag: fill a bag with one of every lane, shuffle it,
    deal it out, refill. After every complete bag each lane has been cued
    exactly the same number of times, so the counts can never drift apart by
    more than one no matter where a block is cut short.

    A plain random choice does not give this. Over 40 trials on 4 lanes it
    routinely lands 15/12/7/6, which is enough imbalance to make a per-finger
    reaction-time comparison meaningless.

    KNOWN PROPERTY WITH TWO LANES. Banning consecutive repeats over a pool of
    two forces strict alternation, so the patient can predict every cue. That
    only arises when a therapist deliberately restricts a block to two
    fingers, which is a therapy drill rather than a measurement block, and
    alternation is reasonable there. Do not read reaction times from a
    two-finger block as if the cue were unpredictable.
    """

    def __init__(self, lanes, rng: random.Random | None = None,
                 avoid_repeats: bool = True) -> None:
        self.lanes = list(lanes)
        if not self.lanes:
            raise ValueError("BalancedScheduler needs at least one lane")
        self.rng = rng or random.Random()
        self.avoid_repeats = avoid_repeats
        self._bag: list[int] = []
        self._last: int | None = None
        self.counts: dict[int, int] = {ln: 0 for ln in self.lanes}

    # How many reshuffles to attempt before giving up and accepting a repeat
    # across a bag boundary. With n lanes the chance of needing another go is
    # 1/n, so even at n = 2 the odds of exhausting this are under one in a
    # million.
    _MAX_RESHUFFLES = 20

    def _refill(self) -> None:
        self._bag = list(self.lanes)
        self.rng.shuffle(self._bag)
        if not (self.avoid_repeats and len(self._bag) > 1
                and self._last is not None):
            return
        # A bag starting with the lane that just played would cue the same
        # finger twice running.
        #
        # Reshuffle rather than swapping the first two entries. The swap
        # looks equivalent and is not: it sends the just-played lane to
        # position 1 every single time the collision happens, which measured
        # at 50% of boundaries against the 33% an unbiased order gives. That
        # puts a detectable rhythm in the cue order, and a patient who picks
        # up on it starts anticipating rather than reacting, which is the
        # thing the shuffling exists to prevent.
        for _ in range(self._MAX_RESHUFFLES):
            if self._bag[0] != self._last:
                return
            self.rng.shuffle(self._bag)

    def next(self) -> int:
        if not self._bag:
            self._refill()
        lane = self._bag.pop(0)
        self._last = lane
        self.counts[lane] += 1
        return lane

    def sequence(self, n: int) -> list[int]:
        return [self.next() for _ in range(n)]

    def spread(self) -> int:
        """Largest gap between any two lanes' counts. Stays at 0 or 1."""
        if not self.counts:
            return 0
        return max(self.counts.values()) - min(self.counts.values())


class PairedBalancedScheduler:
    """Bilateral scheduling where the two hands stay equal.

    Balances on two axes at once. Each hand is cued the same number of times,
    and within each hand each finger is cued the same number of times. Without
    the second axis a scheduler can hand out 50/50 between hands while still
    giving the left index ten trials and the left pinky two.

    `lanes_by_hand` maps a hand name to its lane numbers, e.g.
    {"right": [0,1,2,3], "left": [4,5,6,7]}.
    """

    def __init__(self, lanes_by_hand: dict, rng: random.Random | None = None,
                 avoid_repeats: bool = True) -> None:
        self.rng = rng or random.Random()
        self.hands = [h for h, v in lanes_by_hand.items() if v]
        if not self.hands:
            raise ValueError("PairedBalancedScheduler needs at least one hand")
        self._per_hand = {
            h: BalancedScheduler(lanes_by_hand[h], self.rng,
                                 avoid_repeats=avoid_repeats)
            for h in self.hands
        }
        # Which hand goes next is itself balanced, so the hands cannot drift.
        self._hand_order = BalancedScheduler(
            list(range(len(self.hands))), self.rng, avoid_repeats=False)
        self.hand_counts = {h: 0 for h in self.hands}

    def next(self) -> tuple[str, int]:
        hand = self.hands[self._hand_order.next()]
        self.hand_counts[hand] += 1
        return hand, self._per_hand[hand].next()

    def next_lane(self) -> int:
        return self.next()[1]

    def counts(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for s in self._per_hand.values():
            out.update(s.counts)
        return out

    def hand_spread(self) -> int:
        if not self.hand_counts:
            return 0
        return max(self.hand_counts.values()) - min(self.hand_counts.values())

    def finger_spread(self) -> int:
        c = self.counts()
        return (max(c.values()) - min(c.values())) if c else 0


class FloorWeightedScheduler:
    """Weighted picking with a guaranteed minimum share per lane.

    Adaptive mode weights toward whichever finger is struggling. Left alone
    that can starve a strong finger down to a handful of trials, which is not
    enough to say anything about it afterwards. This keeps the weighting but
    puts a floor under every lane.

    The floor is enforced by tracking how far each lane has fallen behind the
    rate it is owed. A lane owed `min_share` of trials should have about
    `min_share * n` by trial n; when one slips a whole trial behind, it is
    cued next regardless of what the weights say. That bounds the shortfall at
    under one trial at all times, rather than hoping the weights average out.

    min_share is capped so the floors cannot demand more than the whole block:
    with four lanes the highest usable floor is 0.25, which would be exact
    balance and leave the weights nothing to do.
    """

    def __init__(self, num_lanes: int, min_share: float = 0.15,
                 rng: random.Random | None = None,
                 avoid_repeats: bool = True) -> None:
        if num_lanes < 1:
            raise ValueError("FloorWeightedScheduler needs at least one lane")
        self.num_lanes = num_lanes
        # Never let the floors sum past 1.0, or every trial would be forced
        # and the weighting would be dead code.
        self.min_share = max(0.0, min(float(min_share), 1.0 / num_lanes))
        self.rng = rng or random.Random()
        self.avoid_repeats = avoid_repeats
        self.counts = [0] * num_lanes
        self.n = 0
        self._last: int | None = None
        self.forced = 0          # how many picks the floor had to force

    def _deficit(self, i: int) -> float:
        """How many trials lane i is short of its guaranteed rate."""
        return self.min_share * (self.n + 1) - self.counts[i]

    def next(self, weights=None) -> int:
        # A lane a full trial behind its floor gets cued now. Taking the
        # worst one first means the floors are honoured in the order they
        # were breached.
        deficits = [self._deficit(i) for i in range(self.num_lanes)]
        worst = max(range(self.num_lanes), key=lambda i: deficits[i])
        if self.min_share > 0 and deficits[worst] >= 1.0:
            pick = worst
            self.forced += 1
        else:
            pick = self._weighted(weights)
        self._last = pick
        self.counts[pick] += 1
        self.n += 1
        return pick

    def _weighted(self, weights) -> int:
        if not weights or len(weights) != self.num_lanes:
            weights = [1.0] * self.num_lanes
        w = [max(0.0, float(x)) for x in weights]
        # Suppress a repeat by zeroing the last lane, but only when there are
        # at least three lanes and some other lane could actually be picked.
        #
        # With exactly two lanes, zeroing the last one leaves a single
        # candidate, so the weights are discarded and the mode emits a fixed
        # alternation. In adaptive and mirror the weighting IS the mode: a
        # therapist who narrows a drill to two fingers still wants the
        # weaker one cued more often. Allowing the occasional repeat keeps
        # the weighting alive and keeps the order from being fully
        # predictable, which matters more here than the hovering the
        # no-repeat rule guards against.
        if (self.avoid_repeats and self._last is not None
                and self.num_lanes > 2
                and sum(x for i, x in enumerate(w) if i != self._last) > 0):
            w[self._last] = 0.0
        total = sum(w)
        if total <= 0:
            return self.rng.randrange(self.num_lanes)
        u = self.rng.random() * total
        c = 0.0
        for i, x in enumerate(w):
            c += x
            if u <= c:
                return i
        return self.num_lanes - 1

    def shares(self) -> list[float]:
        if self.n == 0:
            return [0.0] * self.num_lanes
        return [c / self.n for c in self.counts]

    def min_observed_share(self) -> float:
        return min(self.shares()) if self.n else 0.0
