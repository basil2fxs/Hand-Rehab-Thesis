"""Adaptive difficulty engine (Thread 1).

Motivated by Guadagnoli & Lee's (2004) challenge-point framework, which
argues an optimal (nominal) difficulty exists for learning but does not
itself name a success-rate number. The 65-80% target band here is a
design choice, informed by success-rate-controlled rehab games in the
literature (e.g. Wilson et al. 2019; the FINGER robot line), not a
number reported by Guadagnoli & Lee. Two control inputs:

  - Lane weights: weak fingers get picked more often (per-lane hit-rate EMA).
  - BPM: speed up when overall hit rate is too high, slow down when too low.

Math-only module so it can be unit-tested without pygame or hardware.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Iterable


log = logging.getLogger(__name__)


@dataclass
class LaneState:
    lane: int
    hit_ema: float = 0.5      # 0..1, binary hit/miss EMA
    quality_ema: float = 0.5  # 0..1, weighted by press quality
    rt_ema_ms: float = 500.0
    n_trials: int = 0

    def update(self, hit: bool, rt_ms: float | None,
               quality: float = 1.0,
               alpha_hit: float = 0.25, alpha_rt: float = 0.2) -> None:
        """Record one trial outcome.

        `quality` is 0..1 where 1.0 = ideal speed press (Great), 0.0 = miss.

        On the FIRST trial both `hit_ema` and `quality_ema` seed to the
        observed values directly (no averaging with the 0.5 prior). A
        stale prior would have masked real early performance: a patient
        landing perfect Greats from trial one would see their EMA stall
        at 0.625 instead of 1.0, putting them below the target band and
        triggering an immediate slow-down despite flawless play.
        """
        q = max(0.0, min(1.0, quality))
        h = 1.0 if hit else 0.0
        if self.n_trials == 0:
            self.hit_ema = h
            self.quality_ema = q
        else:
            self.hit_ema = alpha_hit * h + (1 - alpha_hit) * self.hit_ema
            self.quality_ema = alpha_hit * q + (1 - alpha_hit) * self.quality_ema
        self.n_trials += 1
        # Only update RT EMA on hits with a real RT. Misses give us nothing useful.
        if hit and rt_ms is not None and rt_ms > 0:
            self.rt_ema_ms = alpha_rt * rt_ms + (1 - alpha_rt) * self.rt_ema_ms


@dataclass
class AdaptiveConfig:
    """Tunable parameters for the adaptive-difficulty engine.

    All fields are session-level constants; the engine reads them at
    construction and never mutates them. Defaults hold a 65-80 percent
    hit-rate band, a design choice built on Guadagnoli & Lee's (2004)
    challenge-point framework (which motivates having a target band at
    all, not this specific number) plus success-rate-controlled rehab
    games in the literature (Wilson et al. 2019 and similar).
    """
    # Target hit-rate band. Below `target_low` the engine slows down;
    # above `target_high` it speeds up. Inside the band it holds steady.
    target_low: float = 0.65
    target_high: float = 0.80
    # BPM bounds and step size for the speed-up / slow-down decisions.
    # `bpm_min` 10 prevents the cadence collapsing during long recovery
    # spirals. `bpm_max` 180 (333 ms between stimuli, press window
    # about 300 ms) is set by the band, not by taste: the controller's
    # one job for a high performer is to shrink the window until their
    # hit rate falls back into 65-80 percent, and a hand with a fast
    # 280 ms press needs the window down near 300 ms before that
    # happens. The old cap of 140 (window 386 ms) parked such a hand
    # at 100 percent hits forever, measurably outside the band.
    bpm_min: float = 10.0
    bpm_max: float = 180.0
    bpm_step: float = 10.0
    # Weakness bias on lane selection. Lane weights scale as
    # weakness_bias ** (1 - hit_ema), so a weak lane (hit_ema = 0)
    # is picked 2.5x more often than a strong one (hit_ema = 1).
    weakness_bias: float = 2.5
    # Minimum trials per lane before its EMA influences BPM decisions.
    # Stops single-trial noise driving an early speed-up / slow-down.
    min_trials: int = 2
    # EMA smoothing coefficients. Higher = more reactive to recent
    # trials; lower = more inertia. Tuned so a 4-trial run of one
    # outcome roughly halves the gap between current EMA and target.
    alpha_hit: float = 0.25
    alpha_rt: float = 0.2
    # Timeout window = (60/bpm) * timeout_factor. At 60 BPM the cadence
    # is 1.0s so the press window is 0.9s; at 30 BPM the cadence is 2.0s
    # so the patient gets 1.8s to land the press.
    timeout_factor: float = 0.90


@dataclass
class AdaptiveEngine:
    num_lanes: int = 4
    cfg: AdaptiveConfig = field(default_factory=AdaptiveConfig)
    state: list[LaneState] = field(default_factory=list)
    bpm: float = 80.0
    # Recovery mode kicks in after a run of consecutive misses. The engine
    # forces BPM down a big step and biases the next lane pick toward the
    # patient's strongest finger so they get an easy win and break the
    # failure spiral. Cleared the moment they land a hit.
    in_recovery: bool = False
    # Live streak counters maintained by record(). The next_bpm() decision
    # function reads these so a hot run can push the pace faster than the
    # quality EMA alone (which is slow to settle).
    current_streak: int = 0
    current_miss_streak: int = 0
    # Smallest share of a block any one finger is guaranteed. Set from
    # adaptive.min_finger_share. 0 restores the old unfloored weighting.
    min_finger_share: float = 0.15
    # True when num_lanes covers two hands (bilateral), so the scheduler
    # keeps the hands equal as well as the fingers.
    hands_split: bool = False
    # How many times next_bpm() has actually applied a decision (i.e.
    # past the min_trials data-gate). Used to soften the negative rate
    # limit for the first few decisions -- see next_bpm().
    bpm_decisions: int = 0

    def __post_init__(self) -> None:
        if self.num_lanes < 1:
            raise ValueError(
                f"AdaptiveEngine needs num_lanes >= 1, got {self.num_lanes}"
            )
        if not self.state:
            self.state = [LaneState(lane=i) for i in range(self.num_lanes)]

    def enter_recovery(self) -> None:
        # Big BPM drop on entry so the next trial is well within the
        # patient's capability. Capped at bpm_min so we don't go silly slow.
        if self.in_recovery:
            return
        self.in_recovery = True
        drop = self.cfg.bpm_step * 2.5
        self.bpm = max(self.cfg.bpm_min, self.bpm - drop)

    def exit_recovery(self) -> None:
        self.in_recovery = False

    def record(self, lane: int, hit: bool, rt_ms: float | None,
                quality: float | None = None) -> None:
        if 0 <= lane < self.num_lanes:
            # When the caller doesn't pass a specific quality (e.g. legacy
            # call sites that only know hit/miss), derive it: hits = 1.0,
            # misses = 0.0. Newer callers pass a more granular value.
            q = (1.0 if hit else 0.0) if quality is None else quality
            self.state[lane].update(hit, rt_ms,
                                    quality=q,
                                    alpha_hit=self.cfg.alpha_hit,
                                    alpha_rt=self.cfg.alpha_rt)
        else:
            log.debug("record: lane %d out of [0, %d), ignored",
                      lane, self.num_lanes)
        # Update live streaks. A press counts as a "hit" toward the
        # streak only when both the lane was right AND the timing
        # wasn't dreadful. We use the same hit flag the caller passed,
        # which mirrors how the engine's _update_streak treats it.
        if hit:
            self.current_streak += 1
            self.current_miss_streak = 0
        else:
            self.current_miss_streak += 1
            self.current_streak = 0

    @property
    def session_hit_rate(self) -> float:
        """Average hit-rate across lanes the patient has actually played.
        Unplayed lanes are EXCLUDED so they don't pull the rate toward
        the default 0.5 prior, which used to mask early performance."""
        played = [s for s in self.state if s.n_trials > 0]
        if not played:
            return 0.5
        return sum(s.hit_ema for s in played) / len(played)

    @property
    def session_quality_rate(self) -> float:
        """Quality-weighted hit rate. Like `session_hit_rate` but each
        trial counts as its press-quality (Great=1.0, Good=0.75, Late=
        0.25, Miss=0.0) so an all-Lates session reads as low quality
        despite being 100% hits. Only played lanes are averaged."""
        played = [s for s in self.state if s.n_trials > 0]
        if not played:
            return 0.5
        return sum(s.quality_ema for s in played) / len(played)

    @property
    def session_rt_ms(self) -> float:
        """Average reaction time across lanes that have actually been
        played. Lanes that haven't fired keep their default (500 ms) and
        would skew the average if we included them, so we filter."""
        played = [s for s in self.state if s.n_trials > 0]
        if not played:
            return 0.0
        return sum(s.rt_ema_ms for s in played) / len(played)

    @property
    def rt_utilisation(self) -> float:
        """Fraction of the current press window the patient is using on
        average. 0.0 means instant presses, 1.0 means they're using the
        full window. >0.85 means they're cutting it fine and the engine
        should slow down even when they're still landing the press."""
        rt = self.session_rt_ms
        if rt <= 0.0:
            return 0.0
        window_ms = self.current_timeout_s * 1000.0
        return rt / max(1.0, window_ms)

    def next_bpm(self) -> float:
        """Continuous-pressure challenge-point adaptation.

        The algorithm boils every trial down to a single scalar called
        `combined` that says how the pace should move:

            +1.5 ... -7+   roughly. Positive = speed up, negative = slow.

        It's built from two independent pressure signals:

            quality_pressure -- success vs the 65-80 percent target band.
                +1.5 max when the patient is acing every trial,
                 0    while they sit in the target band,
                -N    when success drops below target_low (unbounded so a
                      total collapse triggers a hard slow-down).

            rt_pressure -- reaction time vs the press window.
                +1.0 max when the patient barely uses any of the window,
                 0    while RT sits in the comfortable 0.55-0.80 band,
                -N    when RT eats > 0.80 of the window. The patient is
                      racing the clock and a faster pace would push them
                      off the cliff.

        Combination rule: the WORST signal wins. If either pressure says
        slow down, slow down. We don't speed up just because quality is
        great if the patient is also burning the window on every press.

        Streak gate on positive signal: a single fluke press cannot
        speed the pace up. Need streak >= 2 for a soft probe nudge and
        >= 3 for the full positive amplitude.

        Asymmetry: negative signal multiplied by 1.5 so we slow down
        harder than we speed up. Better to keep the patient in their
        zone than chase a brief good run.

        Rate limit: per-trial delta is clamped so a single sample can't
        yank BPM around. Repeated calls compound smoothly toward the
        natural equilibrium.

        The 65-80 percent target band is a stable equilibrium: in band
        + comfortable RT yields combined = 0 and BPM holds. Performance
        creeping up either signal pushes BPM up; creeping down on
        either signal pushes BPM down. No discrete state machine, no
        gotchas, just a smooth controller.
        """
        # Don't react before we have enough data to be confident.
        if sum(s.n_trials for s in self.state) < self.cfg.min_trials:
            return self.bpm
        self.bpm_decisions += 1
        hr = self.session_hit_rate
        qr = self.session_quality_rate
        util = self.rt_utilisation
        streak = self.current_streak

        # ---- Quality pressure ----
        # Primary signal is HIT RATE (the target band is 65-80%).
        # Quality (Great vs Good vs Late) refines it: in band but
        # mostly Lates -> nudge down; above band but only Goods -> tone
        # down the speed-up so we don't push a barely-coping patient.
        if hr > self.cfg.target_high:
            quality_pressure = min(1.5, (hr - self.cfg.target_high) / 0.10)
            # Above the band BUT quality is low (lots of Lates). The
            # patient is technically hitting but their timing is bad;
            # tone the speed-up right down.
            if qr < 0.5:
                quality_pressure *= 0.3
        elif hr < self.cfg.target_low:
            # Below the band. Slow down. Uncapped on the negative side
            # so a total collapse triggers a fast retreat.
            quality_pressure = (hr - self.cfg.target_low) / 0.10
        else:
            # Hit rate sits in the 65-80% target band. Use quality as a
            # fine-grain decision: if quality is awful (lots of Lates
            # masquerading as hits) nudge down; if quality is great
            # nudge up to probe their real limit.
            if qr < 0.4:
                quality_pressure = -0.5
            elif qr > 0.85:
                quality_pressure = 0.3
            else:
                quality_pressure = 0.0

        # ---- RT pressure ----
        if util <= 0.0:
            rt_pressure = 0.0          # no real RT data yet (all misses)
        elif util > 0.80:
            # Each 10% past 0.80 of utilisation subtracts 0.5 from the
            # signal. util=1.0 -> -1.0, util=1.2 -> -2.0.
            rt_pressure = (0.80 - util) * 5.0
        elif util < 0.55:
            # Spare time -> push harder. Capped so it can't fully
            # dominate quality on its own.
            rt_pressure = min(1.0, (0.55 - util) * 2.0)
        else:
            rt_pressure = 0.0          # comfortable band, neutral

        # ---- Combine: worst signal dominates ----
        if quality_pressure < 0 or rt_pressure < 0:
            # Either side asking for a slow-down. Take the worst.
            combined = min(quality_pressure, rt_pressure)
            if rt_pressure < 0 <= quality_pressure \
                    and hr > self.cfg.target_high and qr >= 0.5:
                # Band-keeping override. The utilisation guard exists
                # to stop a coping-but-fragile patient being pushed
                # over the cliff, but ABOVE the band the cliff edge is
                # the destination: the controller's job is to shrink
                # the window until the hit rate falls back to 65-80
                # percent, and utilisation rising through 0.80 is what
                # that approach looks like. Letting the guard veto
                # here parked a 96-percent player at util 0.80 for
                # entire sessions (measured: 300 of 300 trials above
                # the band, BPM oscillating just under the stall
                # point). Blend instead of veto: the guard tempers the
                # climb as it strengthens and only wins outright once
                # it outweighs the whole quality signal, by which
                # point the misses it predicted have arrived and hr
                # itself has dropped back toward the band. The qr
                # gate keeps the override honest: a 100 percent hit
                # rate made of Lates (qr under 0.5) is a patient at
                # their limit, and there the guard keeps its veto.
                combined = max(0.0, quality_pressure + rt_pressure)
        else:
            # Both non-negative. Use whichever is more confidently
            # asking for a speed-up.
            combined = max(quality_pressure, rt_pressure)

        # ---- Streak gate on speed-up ----
        # Don't speed up off a single fluke press. The patient needs to
        # demonstrate they can hold the pace before we crank it.
        if combined > 0:
            if streak < 2:
                combined = 0.0
            elif streak < 3:
                # Probe-strength nudge so a patient who's clearly fine
                # gets pushed to find their real limit, not just sit
                # where they are.
                combined *= 0.3
            else:
                # Streak amplification: each consecutive hit beyond 3
                # adds 0.25x scale, capped at +1.5x (around streak 9).
                streak_mult = 1.0 + min(1.5, (streak - 3) * 0.25)
                combined *= streak_mult

        # ---- Asymmetric slow-down ----
        # Slow-downs hit ~1.5x harder than speed-ups so a struggling
        # patient gets caught quickly while a strong patient gets
        # pushed gradually.
        if combined < 0:
            combined *= 1.5

        # ---- Apply with rate limit ----
        # Per-trial cap so a single outlier can't fling BPM around.
        # Repeated calls compound smoothly toward equilibrium.
        step = self.cfg.bpm_step
        delta = combined * step * 0.4
        # Cold-start softening: the full -2*step clamp is sized to be
        # a meaningful per-trial move for a session already under way,
        # but at session start it can equal (or exceed) the whole gap
        # from a comfortable start_bpm down to bpm_min -- two opening
        # misses (min_trials=2) then decide the block's entire pace in
        # one call, before the controller has any real read on the
        # patient. The first few decisions get a softer floor instead;
        # this decays back to the normal clamp so a genuinely
        # struggling patient still reaches bpm_min quickly, just not
        # in a single step off two trials.
        neg_clamp = step * 2.0
        if self.bpm_decisions <= 3:
            neg_clamp = step * (0.5 + 0.5 * self.bpm_decisions)
        delta = max(-neg_clamp, min(step * 1.5, delta))
        self.bpm = max(self.cfg.bpm_min,
                        min(self.cfg.bpm_max, self.bpm + delta))
        return self.bpm

    @property
    def current_timeout_s(self) -> float:
        """How long the patient has to press at the current BPM. Slower
        pace gives more time per press."""
        cadence_s = 60.0 / max(1.0, self.bpm)
        return cadence_s * self.cfg.timeout_factor

    def pace_label(self) -> str:
        """Short human label for the current BPM.

        Currently unused: the gameplay HUD deliberately dropped BPM
        (and everything else therapist-only) from the patient-facing
        screen to cut on-screen noise -- see GameplayScreen.draw's
        "Stripped-down HUD" comment. Kept here as a ready-made string
        for a therapist-facing view (Results screen, notebook) or a
        future pace-change chip, should one get added; nothing calls
        it today.
        """
        b = self.bpm
        if b < 45:
            return "very slow"
        if b < 65:
            return "slow"
        if b < 90:
            return "steady"
        if b < 110:
            return "brisk"
        return "fast"

    def lane_weights(self) -> list[float]:
        # Recovery override: pile most of the weight on the patient's
        # strongest finger so they get an easy hit to break the miss streak.
        if self.in_recovery:
            return self._recovery_weights()
        # Normal mode: weakness^bias + small base so even strong lanes get
        # picked sometimes. Weak fingers get more practice over time.
        weights = []
        for s in self.state:
            weakness = max(0.05, 1.0 - s.hit_ema)
            weights.append(weakness ** self.cfg.weakness_bias + 0.1)
        total = sum(weights) or 1.0
        return [w / total for w in weights]

    def _recovery_weights(self) -> list[float]:
        # Pick the lane with the highest hit_ema (their strongest finger).
        # 70% weight on it; remaining 30% split evenly over the others so
        # there's still some variety.
        strongest = max(range(self.num_lanes),
                         key=lambda i: self.state[i].hit_ema)
        rest_share = 0.30 / max(1, self.num_lanes - 1)
        return [
            0.70 if i == strongest else rest_share
            for i in range(self.num_lanes)
        ]

    def pick_lane(self, rng: random.Random | None = None) -> int:
        r = rng or random.Random()
        weights = self.lane_weights()
        u = r.random()
        c = 0.0
        for i, w in enumerate(weights):
            c += w
            if u <= c:
                return i
        return self.num_lanes - 1

    def generate_sequence(self, length: int,
                          rng: random.Random | None = None,
                          avoid_repeats: bool = True) -> list[int]:
        """Next `length` lanes, weighted toward whichever finger is
        struggling but with a floor under every finger.

        Weighting alone can starve a strong finger. Simulated over 60 trials
        with one weak finger it left the strongest with about 5% of the
        trials, three of sixty, which is far too few to say anything about
        that finger afterwards. The floor guarantees a usable share without
        flattening the weighting: the weak finger is still cued most.

        The weights themselves are untouched. lane_weights() has to keep
        summing to 1.0 for pick_lane's cumulative scan, and recovery mode's
        shape is pinned by tests, so the floor is applied here at the point
        of choosing rather than by clamping the distribution.

        In bilateral mode the hands are balanced too. The engine sees a flat
        list of 8 lanes and has no idea two hands are involved, so without
        this an affected hand can quietly collect most of the trials and the
        left-versus-right comparison stops meaning anything.
        """
        r = rng or random.Random()
        # Hand the caller's rng to the schedulers the first time they are
        # built, so a block replayed with the same seed comes out the same.
        self._rng = r
        floor = self._floor_scheduler()
        if floor is None:
            out: list[int] = []
            last = -1
            for _ in range(length):
                for _ in range(8):
                    pick = self.pick_lane(r)
                    if not avoid_repeats or pick != last or self.num_lanes < 2:
                        break
                out.append(pick)
                last = pick
            return out

        weights = self.lane_weights()
        if self.hands_split and self.num_lanes >= 2:
            return self._paired_sequence(length, weights, r)
        return [floor.next(weights) for _ in range(length)]

    def _floor_scheduler(self):
        """Lazily built so it persists across the repeated short
        regenerations adaptive mode does (block_size is 4), which is what
        lets the floor be tracked over a whole block rather than reset every
        four trials."""
        if self.min_finger_share <= 0:
            return None
        if getattr(self, "_floor", None) is None:
            from ..game.scheduling import FloorWeightedScheduler
            per_hand = (self.num_lanes // 2 if self.hands_split
                        else self.num_lanes)
            # The rng is passed in so a replayed block reproduces exactly.
            self._floor = FloorWeightedScheduler(
                per_hand, min_share=self.min_finger_share, rng=self._rng)
            if self.hands_split:
                from ..game.scheduling import BalancedScheduler
                self._floor_other = FloorWeightedScheduler(
                    per_hand, min_share=self.min_finger_share, rng=self._rng)
                self._hand_order = BalancedScheduler(
                    [0, 1], rng=self._rng, avoid_repeats=False)
        return self._floor

    def _paired_sequence(self, length: int, weights, r) -> list[int]:
        n = self.num_lanes // 2
        out = []
        for _ in range(length):
            side = self._hand_order.next()
            sched = self._floor if side == 0 else self._floor_other
            # Each hand is weighted by its own lanes' weights.
            w = weights[side * n:(side + 1) * n]
            out.append(side * n + sched.next(w))
        return out

    def summary(self) -> dict:
        return {
            "bpm": self.bpm,
            "session_hit_rate": self.session_hit_rate,
            "lane_weights": self.lane_weights(),
            "lanes": [
                {"lane": s.lane, "n_trials": s.n_trials,
                 "hit_ema": s.hit_ema, "rt_ema_ms": s.rt_ema_ms}
                for s in self.state
            ],
        }


def warm_start_from_history(history: Iterable[dict],
                            cfg: AdaptiveConfig | None = None,
                            num_lanes: int = 4) -> AdaptiveEngine:
    """Seed an AdaptiveEngine from past trial dicts. Tolerant of legacy CSVs
    where booleans round-trip as strings and bad rows might be present."""
    eng = AdaptiveEngine(num_lanes=num_lanes, cfg=cfg or AdaptiveConfig())
    skipped = 0
    for rec in history:
        try:
            lane = int(rec["lane"])
        except (KeyError, TypeError, ValueError):
            skipped += 1
            continue
        hit_raw = rec.get("hit")
        if isinstance(hit_raw, str):
            hit = hit_raw.strip().lower() in ("1", "true", "yes", "y", "hit")
        else:
            hit = bool(hit_raw)
        rt_raw = rec.get("rt_ms")
        try:
            rt_ms = float(rt_raw) if rt_raw not in (None, "", "None") else None
        except (TypeError, ValueError):
            rt_ms = None
        eng.record(lane, hit, rt_ms)
    if skipped:
        log.info("warm_start: skipped %d malformed rows", skipped)
    return eng
