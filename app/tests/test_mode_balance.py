"""Every mode gives the fingers a fair share, and bilateral gives the hands
a fair share too.

These assert the property the analysis depends on, at the level the game
actually runs it. A cross-finger comparison is only meaningful when the
fingers were cued a comparable number of times, and a left-versus-right
comparison only when both hands were.

What each mode did before this was wired in:

    classic    [1,0,2,1,3,0] repeated: index and middle 16 trials each,
               ring and pinky 8. Fixed order, no randomisation. In bilateral
               it named only lanes 1 to 4, so the left hand was never cued.
    rhythm     bilateral pattern repeated the middle and ring within its
               cycle, giving them twice the notes of index and pinky.
    adaptive   weighting with no floor left the strongest finger on about
               5% of trials, and nothing balanced the two hands.
    mirror     weighting with no floor on the finger choice.
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import random

import pytest


N = 4


def _engine(hand_mode: str, balance: bool = True):
    from finger_rehab.game.engine import GameEngine

    class Cfg:
        def get(self, key, default=None):
            if key == "fsr.num_sensors_per_hand":
                return N
            if key == "game.balance_targets":
                return balance
            return default

    e = GameEngine.__new__(GameEngine)
    e.cfg = Cfg()
    e.hand_mode = hand_mode
    return e


class TestClassicSequence:
    def test_unilateral_fingers_are_equal(self):
        seq = _engine("right").build_balanced_sequence(48)
        c = Counter(seq)
        assert len(seq) == 48
        assert set(c) == {0, 1, 2, 3}
        assert max(c.values()) - min(c.values()) <= 1

    def test_bilateral_cues_the_left_hand_at_all(self):
        """The old fixed pattern named only lanes 1 to 4, so across a whole
        48-trial bilateral block the left hand received zero cues while its
        four lanes stayed live and could only lose points."""
        seq = _engine("both").build_balanced_sequence(48)
        left = [x for x in seq if x >= N]
        assert left, "left hand was never cued"

    def test_bilateral_hands_are_equal(self):
        seq = _engine("both").build_balanced_sequence(80)
        right = sum(1 for x in seq if x < N)
        left = sum(1 for x in seq if x >= N)
        assert abs(right - left) <= 1

    def test_bilateral_all_eight_lanes_equal(self):
        seq = _engine("both").build_balanced_sequence(80)
        c = Counter(seq)
        assert set(c) == set(range(8))
        assert max(c.values()) - min(c.values()) <= 1

    def test_order_is_not_a_repeating_loop(self):
        """A fixed short order lets the patient learn it, so the reaction
        time starts measuring anticipation instead of response."""
        seqs = {tuple(_engine("right").build_balanced_sequence(24))
                for _ in range(20)}
        assert len(seqs) > 5

    def test_no_finger_cued_twice_running(self):
        seq = _engine("right").build_balanced_sequence(60)
        assert all(a != b for a, b in zip(seq, seq[1:]))

    def test_odd_trial_count_stays_within_one(self):
        seq = _engine("right").build_balanced_sequence(37)
        c = Counter(seq)
        assert len(seq) == 37
        assert max(c.values()) - min(c.values()) <= 1

    def test_switch_returns_empty_so_caller_keeps_old_behaviour(self):
        assert _engine("right", balance=False).build_balanced_sequence(48) == []

    def test_zero_and_negative_lengths(self):
        e = _engine("right")
        assert e.build_balanced_sequence(0) == []
        assert e.build_balanced_sequence(-5) == []

    def test_classic_mode_uses_the_sequence_it_is_given(self):
        from finger_rehab.game.modes.classic import ClassicMode
        from finger_rehab.game.scoring import ScoreConfig
        m = ClassicMode.__new__(ClassicMode)
        ClassicMode.__init__(
            m, engine=None, pattern=[0, 1], repeat_count=2,
            trigger_interval_s=1.0, timeout_s=1.0, early_window_s=0.1,
            score_cfg=ScoreConfig(), sequence=[3, 2, 1, 0])
        assert m.sequence == [3, 2, 1, 0]

    def test_classic_falls_back_to_the_pattern_without_a_sequence(self):
        from finger_rehab.game.modes.classic import ClassicMode
        from finger_rehab.game.scoring import ScoreConfig
        m = ClassicMode.__new__(ClassicMode)
        ClassicMode.__init__(
            m, engine=None, pattern=[0, 1], repeat_count=3,
            trigger_interval_s=1.0, timeout_s=1.0, early_window_s=0.1,
            score_cfg=ScoreConfig(), sequence=None)
        assert m.sequence == [0, 1, 0, 1, 0, 1]


class TestRhythmPattern:
    def test_unilateral_pattern_is_balanced(self):
        from finger_rehab.audio.beatmap import _default_pattern
        c = Counter(_default_pattern(4))
        assert max(c.values()) == min(c.values())

    def test_bilateral_pattern_is_balanced(self):
        """Was [0,4,1,5,2,6,3,7,1,5,2,6]: middle and ring appeared twice per
        cycle, index and pinky once, so the inner fingers got twice the
        notes on every track."""
        from finger_rehab.audio.beatmap import _default_pattern
        pat = _default_pattern(8)
        c = Counter(pat)
        assert set(c) == set(range(8))
        assert max(c.values()) == min(c.values())

    def test_bilateral_alternates_hands(self):
        from finger_rehab.audio.beatmap import _default_pattern
        pat = _default_pattern(8)
        sides = [0 if x < 4 else 1 for x in pat]
        assert all(a != b for a, b in zip(sides, sides[1:]))

    def test_notes_across_a_song_are_balanced(self):
        from finger_rehab.audio.beatmap import _assign_lanes
        for n in (4, 8):
            notes = _assign_lanes([i * 0.5 for i in range(240)], num_lanes=n)
            c = Counter(x.lane for x in notes)
            assert set(c) == set(range(n))
            assert max(c.values()) - min(c.values()) <= 1, f"{n} lanes"


class TestAdaptiveFloor:
    def _sim(self, min_share, n_lanes=4, hands=False, trials=60, seed=5):
        from finger_rehab.analytics.adaptive import AdaptiveEngine, AdaptiveConfig
        a = AdaptiveEngine(num_lanes=n_lanes,
                           cfg=AdaptiveConfig(weakness_bias=2.5),
                           min_finger_share=min_share, hands_split=hands)
        for i, s in enumerate(a.state):
            s.hit_ema = 0.3 if i % 4 == 3 else 0.9      # pinky struggling
        r = random.Random(seed)
        out = []
        for _ in range(trials // 4):
            out += a.generate_sequence(4, r)
        return Counter(out)

    def test_floor_lifts_the_starved_finger(self):
        floored = self._sim(0.15)
        assert min(floored.values()) / sum(floored.values()) >= 0.12

    def test_weak_finger_still_gets_the_most_practice(self):
        """The floor must not flatten the mode into classic. Adaptive
        exists to give a struggling finger extra work."""
        c = self._sim(0.15)
        assert c[3] == max(c.values())

    def test_zero_share_restores_the_old_weighting(self):
        from finger_rehab.analytics.adaptive import AdaptiveEngine, AdaptiveConfig
        a = AdaptiveEngine(num_lanes=4, cfg=AdaptiveConfig(),
                           min_finger_share=0.0)
        assert a._floor_scheduler() is None

    def test_bilateral_hands_are_equal(self):
        c = self._sim(0.15, n_lanes=8, hands=True, trials=80)
        right = sum(v for k, v in c.items() if k < 4)
        left = sum(v for k, v in c.items() if k >= 4)
        assert abs(right - left) <= 1

    def test_bilateral_covers_every_lane(self):
        c = self._sim(0.15, n_lanes=8, hands=True, trials=80)
        assert set(c) == set(range(8))

    def test_lane_weights_still_sum_to_one(self):
        """pick_lane does a cumulative scan with a silent fall-through to
        the last lane, so a weight vector that does not sum to 1 quietly
        dumps the remainder on the pinky."""
        from finger_rehab.analytics.adaptive import AdaptiveEngine, AdaptiveConfig
        for recovery in (False, True):
            a = AdaptiveEngine(num_lanes=4, cfg=AdaptiveConfig(),
                               min_finger_share=0.15)
            a.in_recovery = recovery
            assert sum(a.lane_weights()) == pytest.approx(1.0)

    def test_sequence_length_is_respected(self):
        from finger_rehab.analytics.adaptive import AdaptiveEngine, AdaptiveConfig
        a = AdaptiveEngine(num_lanes=4, cfg=AdaptiveConfig(),
                           min_finger_share=0.15)
        assert len(a.generate_sequence(9, random.Random(0))) == 9

    def test_lanes_stay_in_range(self):
        for n, hands in ((4, False), (8, True)):
            c = self._sim(0.15, n_lanes=n, hands=hands, trials=80)
            assert all(0 <= k < n for k in c)


class TestMirrorFloor:
    def _mode(self, min_share=0.15):
        from finger_rehab.game.modes.mirror import MirrorMode
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.analytics.adaptive import AdaptiveConfig
        m = MirrorMode.__new__(MirrorMode)
        MirrorMode.__init__(
            m, engine=None, pattern=[0, 1, 2, 3], repeat_count=8,
            trigger_interval_s=1.0, timeout_s=1.0, early_window_s=0.1,
            score_cfg=ScoreConfig(), adaptive_cfg=AdaptiveConfig(),
            start_bpm=24.0, seed=3, min_finger_share=min_share)
        for i, s in enumerate(m.adapter.state):
            s.hit_ema = 0.3 if i == 3 else 0.9
        return m

    def test_fingers_get_a_fair_share(self):
        m = self._mode()
        c = Counter(m._pick_finger() for _ in range(60))
        assert min(c.values()) / 60 >= 0.12

    def test_weak_finger_still_leads(self):
        m = self._mode()
        c = Counter(m._pick_finger() for _ in range(60))
        assert c[3] == max(c.values())

    def test_only_eligible_fingers_are_picked(self):
        from finger_rehab.game.modes.mirror import MirrorMode
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.analytics.adaptive import AdaptiveConfig
        m = MirrorMode.__new__(MirrorMode)
        MirrorMode.__init__(
            m, engine=None, pattern=[0, 2], repeat_count=8,
            trigger_interval_s=1.0, timeout_s=1.0, early_window_s=0.1,
            score_cfg=ScoreConfig(), adaptive_cfg=AdaptiveConfig(),
            start_bpm=24.0, seed=1, min_finger_share=0.15)
        picks = {m._pick_finger() for _ in range(80)}
        assert picks <= {0, 2}

    def test_single_eligible_finger_does_not_crash(self):
        from finger_rehab.game.modes.mirror import MirrorMode
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.analytics.adaptive import AdaptiveConfig
        m = MirrorMode.__new__(MirrorMode)
        MirrorMode.__init__(
            m, engine=None, pattern=[2], repeat_count=4,
            trigger_interval_s=1.0, timeout_s=1.0, early_window_s=0.1,
            score_cfg=ScoreConfig(), adaptive_cfg=AdaptiveConfig(),
            start_bpm=24.0, seed=1, min_finger_share=0.15)
        assert {m._pick_finger() for _ in range(20)} == {2}


class TestPatternRespect:
    """A narrowed game.pattern is a deliberate drill and must be honoured.
    The built-in fallback is not a choice and must not be, because it names
    only lanes 1 to 4 and honouring it in bilateral mode would leave the
    left hand permanently uncued."""

    def _engine(self, hand_mode="right", pattern=None):
        from finger_rehab.game.engine import GameEngine

        class Cfg:
            def __init__(self):
                self.data = {"game": {}} if pattern is None else \
                    {"game": {"pattern": pattern}}

            def get(self, key, default=None):
                if key == "fsr.num_sensors_per_hand":
                    return N
                if key == "game.balance_targets":
                    return True
                if key == "game.pattern":
                    return pattern or default
                return default

        e = GameEngine.__new__(GameEngine)
        e.cfg = Cfg()
        e.hand_mode = hand_mode
        return e

    def test_fallback_pattern_is_not_treated_as_a_choice(self):
        e = self._engine()
        assert e._pattern_is_configured() is False

    def test_explicit_pattern_is_treated_as_a_choice(self):
        e = self._engine(pattern="1,2")
        assert e._pattern_is_configured() is True

    def test_default_bilateral_still_cues_both_hands(self):
        """The regression this guards: honouring the fallback pattern
        restricted bilateral to lanes 0 to 3, so the left hand was never
        cued, which is the original bug."""
        e = self._engine("both")
        pat = e._parse_pattern("2,1,3,2,4,1", 8)
        seq = e.build_balanced_sequence(
            48, lanes=pat if e._pattern_is_configured() else None)
        assert any(x >= N for x in seq), "left hand never cued"
        c = Counter(seq)
        assert set(c) == set(range(8))

    def test_explicit_narrow_pattern_excludes_the_others(self):
        e = self._engine("right", pattern="1,2")
        pat = e._parse_pattern("1,2", 4)
        seq = e.build_balanced_sequence(
            32, lanes=pat if e._pattern_is_configured() else None)
        assert set(seq) == {0, 1}
        c = Counter(seq)
        assert max(c.values()) - min(c.values()) <= 1

    def test_explicit_pattern_spanning_both_hands_balances_hands(self):
        e = self._engine("both", pattern="1,2,5,6")
        pat = e._parse_pattern("1,2,5,6", 8)
        seq = e.build_balanced_sequence(
            48, lanes=pat if e._pattern_is_configured() else None)
        assert set(seq) == {0, 1, 4, 5}
        right = sum(1 for x in seq if x < N)
        left = sum(1 for x in seq if x >= N)
        assert abs(right - left) <= 1
