"""Tests for Patterns mode, the SRTT sequence-learning block. The
guarantees pinned here are the ones the measurement depends on: the
trained sequence is a valid second-order conditional cycle and is
identical for a participant across sessions, probes share no
second-order structure with the trained material, the session layout
interleaves trained and probe takes as designed, EVERY trial reaches
the CSV with pattern_trial TRUE or FALSE (that column IS the
measurement), timing never changes within a participant, and the
safety rails (fatigue rests, session cap) end a block rather than trap
a patient in it.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _press(lane: int, t: float = 0.0):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="right")


def _build_mode(**overrides):
    """A PatternMode wired to a MagicMock engine, driven with explicit
    `now` values instead of sleeping, following the reaction-mode test
    harness."""
    from finger_rehab.game.modes.pattern import PatternMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
    kwargs = dict(
        engine=engine,
        lanes=[0, 1, 2, 3],
        p_seed=1234,
        block_seed=99,
        soc_cycles_per_block=5,
        warmup_trials=20,
        random_block_trials=60,
        probe_pool_size=4,
        rsi_s=0.5,
        timeout_s=2.0,
        rest_min_s=10.0,
        long_rest_s=30.0,
        fatigue_rest_s=45.0,
        fatigue_timeout_run=5,
        session_cap_min=30.0,
        short_session=False,
        score_cfg=ScoreConfig(),
        demo_trials=None,
    )
    kwargs.update(overrides)
    return engine, PatternMode(**kwargs)


def _seg_index(mode, kind: str, nth: int = 0) -> int:
    hits = [i for i, s in enumerate(mode.segments) if s.kind == kind]
    return hits[nth]


class SequenceGeneratorTests(unittest.TestCase):
    """The material is the manipulation. A sequence that breaks the
    second-order conditional constraints lets the patient learn finger
    frequencies instead of the sequence (Reed and Johnson 1994), and a
    sequence that changes between sessions destroys every cross-session
    comparison."""

    def test_soc_satisfies_the_reed_johnson_constraints(self) -> None:
        import random
        from finger_rehab.game.modes.pattern import generate_soc
        for seed in range(25):
            seq = generate_soc(random.Random(seed))
            self.assertEqual(len(seq), 12)
            # Each finger exactly 3 times, so per-finger comparisons
            # inside a take rest on equal counts.
            for finger in range(4):
                self.assertEqual(seq.count(finger), 3)
            pairs = [(seq[i], seq[(i + 1) % 12]) for i in range(12)]
            # No back-to-back repeats, and all 12 possible transitions
            # exactly once, including across the loop boundary.
            self.assertTrue(all(a != b for a, b in pairs))
            self.assertEqual(len(set(pairs)), 12)

    def test_trained_sequence_is_stable_for_a_participant(self) -> None:
        from finger_rehab.game.modes.pattern import (build_sequences,
                                              participant_seed)
        # The seed comes from the name, trimmed and case-folded, so the
        # common typing slips do not silently fork the material.
        self.assertEqual(participant_seed("Basil"),
                         participant_seed("  basil "))
        s = participant_seed("Basil")
        t1, p1 = build_sequences(s)
        t2, p2 = build_sequences(s)
        self.assertEqual(t1, t2)
        self.assertEqual(p1, p2)

    def test_different_participants_get_different_material(self) -> None:
        from finger_rehab.game.modes.pattern import (build_sequences,
                                              participant_seed)
        t_a, _ = build_sequences(participant_seed("alice"))
        t_b, _ = build_sequences(participant_seed("bob"))
        self.assertNotEqual(t_a, t_b)

    def test_probes_share_no_second_order_structure(self) -> None:
        from finger_rehab.game.modes.pattern import (_canonical_rotation,
                                              build_sequences,
                                              shared_triplets)
        for seed in range(10):
            trained, pool = build_sequences(seed)
            # A session needs two distinct probes at minimum.
            self.assertGreaterEqual(len(pool), 2)
            canons = {_canonical_rotation(trained)}
            for probe in pool:
                # Zero shared triplets: knowing the trained sequence
                # tells you nothing two-back about the probe, so probe
                # RT cannot benefit from trained knowledge.
                self.assertEqual(shared_triplets(probe, trained), 0)
                canon = _canonical_rotation(probe)
                # No probe is a rotation of the trained sequence or of
                # another probe: rotations are the same material.
                self.assertNotIn(canon, canons)
                canons.add(canon)


class Cycle8Tests(unittest.TestCase):
    """K8: the bimanual 24-item cycle over eight lanes, the probe
    builder that reuses its own transitions, and the fresh-cycle and
    minimal-overlap fallbacks build_sequences(n_lanes=8) falls back to
    when a seed's graph will not give a clean re-ordering. Untested
    before this, despite being the material bilateral play depends on."""

    def test_generate_cycle8_satisfies_the_k8_constraints(self) -> None:
        import random
        from finger_rehab.game.modes.pattern import generate_cycle8
        for seed in range(25):
            cyc = generate_cycle8(random.Random(seed))
            self.assertEqual(len(cyc), 24)
            # Every lane exactly 3 times, so a per-finger comparison
            # inside a take rests on equal counts across all 8 lanes.
            for lane in range(8):
                self.assertEqual(cyc.count(lane), 3)
            pairs = [(cyc[i], cyc[(i + 1) % 24]) for i in range(24)]
            # No back-to-back repeats, and no ordered transition used
            # twice, wrap included, so every first-order transition
            # inside the cycle is equally frequent.
            self.assertTrue(all(a != b for a, b in pairs))
            self.assertEqual(len(set(pairs)), 24)

    def test_reorder_cycle_matches_first_order_and_zero_triplets(
            self) -> None:
        import random
        from finger_rehab.game.modes.pattern import (_triplet_map, generate_cycle8,
                                              reorder_cycle,
                                              shared_triplets)
        hits = 0
        for seed in range(60):
            rng = random.Random(seed)
            trained = generate_cycle8(rng)
            forbid = _triplet_map(trained)
            cand = reorder_cycle(trained, rng, forbid)
            if cand is None:
                continue
            hits += 1
            # Same 24 transitions in a new order: identical location
            # and first-order frequencies, only the two-back structure
            # (the triplet map) may differ, and here it must be zero.
            self.assertEqual(sorted(cand), sorted(trained))
            self.assertEqual(
                sorted((cand[i], cand[(i + 1) % 24]) for i in range(24)),
                sorted((trained[i], trained[(i + 1) % 24])
                      for i in range(24)))
            self.assertEqual(shared_triplets(cand, trained), 0)
        # A re-ordering exists for the large majority of seeds; the
        # test would be vacuous if the search never once succeeded.
        self.assertGreater(hits, 30)

    def test_build_sequences8_first_choice_reuses_trained_transitions(
            self) -> None:
        from finger_rehab.game.modes.pattern import build_sequences, shared_triplets
        trained, pool = build_sequences(seed=7, n_lanes=8)
        self.assertEqual(len(trained), 24)
        self.assertGreaterEqual(len(pool), 2)
        for probe in pool:
            self.assertEqual(len(probe), 24)
            self.assertEqual(shared_triplets(probe, trained), 0)
            # First choice is a re-ordering of the trained cycle's own
            # transitions, so probe material stays location- and
            # first-order-matched unless the fallback had to fire.
            self.assertEqual(sorted(probe), sorted(trained))

    def test_build_sequences8_falls_back_to_fresh_zero_overlap_cycles(
            self) -> None:
        # Force every re-ordering attempt to fail so the second stage,
        # fresh cycles sharing zero triplets with the trained one, is
        # what actually builds the pool.
        from finger_rehab.game.modes import pattern as pattern_mod
        with patch.object(pattern_mod, "reorder_cycle", return_value=None):
            trained, pool = pattern_mod.build_sequences(seed=7, n_lanes=8)
        self.assertGreaterEqual(len(pool), 2)
        for probe in pool:
            self.assertEqual(pattern_mod.shared_triplets(probe, trained), 0)
            # Fresh cycles satisfy K8 on their own; they are not
            # required to reuse the trained transition set.
            for lane in range(8):
                self.assertEqual(probe.count(lane), 3)

    def test_build_sequences8_falls_back_to_minimal_overlap(self) -> None:
        # Force both the re-ordering stage and the zero-overlap fresh
        # cycle stage to fail, so only the last-resort minimal-overlap
        # fallback (shared triplets <= _PROBE_FALLBACK_MAX_SHARED) can
        # fill the pool. A frozen block start is worse than this.
        from finger_rehab.game.modes import pattern as pattern_mod
        real_shared = pattern_mod.shared_triplets
        with patch.object(pattern_mod, "reorder_cycle", return_value=None), \
             patch.object(pattern_mod, "shared_triplets",
                          side_effect=lambda a, b: max(1, real_shared(a, b))):
            trained, pool = pattern_mod.build_sequences(seed=7, n_lanes=8)
        self.assertGreaterEqual(len(pool), 2)
        for probe in pool:
            self.assertLessEqual(real_shared(probe, trained),
                                 pattern_mod._PROBE_FALLBACK_MAX_SHARED)

    def test_build_sequences8_raises_when_no_probe_survives(self) -> None:
        # Every candidate reported as sharing more than the fallback
        # allows: no probe can ever qualify, so the pool must fail
        # loudly rather than hand back too few probes to alternate.
        from finger_rehab.game.modes import pattern as pattern_mod
        with patch.object(pattern_mod, "reorder_cycle", return_value=None), \
             patch.object(pattern_mod, "shared_triplets", return_value=99):
            with self.assertRaises(RuntimeError):
                pattern_mod.build_sequences(seed=7, n_lanes=8)


class LayoutTests(unittest.TestCase):
    """The session structure is the experiment: probes at fixed spots
    with trained takes either side, every take starting the cycle at
    position 0, counts balanced per finger."""

    def test_standard_layout_shape(self) -> None:
        _, mode = _build_mode()
        kinds = [s.kind for s in mode.segments]
        self.assertEqual(kinds, ["warmup", "random",
                                 "seq", "seq", "seq", "probe",
                                 "seq", "seq", "seq", "probe", "seq"])
        # Probes at positions 5 and 9 of the ten takes, matching the
        # cross-session comparability requirement.
        labels = [s.label for s in mode.segments if s.kind == "probe"]
        self.assertEqual(labels, ["5", "9"])
        # 20 warm-up + 10 takes of 60 = 620 trials.
        self.assertEqual(sum(len(s.fingers) for s in mode.segments), 620)
        # The one long rest follows take 6, never a probe: a rest
        # boosts the take after it, and B7 is the only trained take
        # the probe subtraction never reads. Both probes keep the
        # plain floor on both sides (symmetric rests).
        rests = [s.long_rest_after for s in mode.segments]
        self.assertEqual(sum(rests), 1)
        self.assertTrue(mode.segments[6].long_rest_after)
        self.assertEqual(mode.segments[6].kind, "seq")
        self.assertEqual(mode.segments[6].label, "6")
        for seg in mode.segments:
            if seg.kind == "probe":
                self.assertFalse(seg.long_rest_after)

    def test_takes_start_the_cycle_at_position_zero(self) -> None:
        _, mode = _build_mode()
        for seg in mode.segments:
            if seg.kind == "seq":
                self.assertEqual(seg.fingers[:12], mode.trained)
                self.assertEqual(seg.fingers, mode.trained * 5)

    def test_probe_takes_use_untrained_material(self) -> None:
        from finger_rehab.game.modes.pattern import shared_triplets
        _, mode = _build_mode()
        probe_socs = [s.fingers[:12] for s in mode.segments
                      if s.kind == "probe"]
        self.assertEqual(len(probe_socs), 2)
        # The two probes of one session use different pool members.
        self.assertNotEqual(probe_socs[0], probe_socs[1])
        for soc in probe_socs:
            self.assertIn(soc, mode.probes)
            self.assertEqual(shared_triplets(soc, mode.trained), 0)

    def test_short_session_keeps_both_probes_flanked(self) -> None:
        _, mode = _build_mode(short_session=True)
        kinds = [s.kind for s in mode.segments]
        self.assertEqual(kinds, ["warmup", "random", "seq", "seq", "seq",
                                 "probe", "seq", "probe", "seq"])
        # The flanker subtraction IS the learning score, so every probe
        # needs a trained take on each side.
        for i, k in enumerate(kinds):
            if k == "probe":
                self.assertEqual(kinds[i - 1], "seq")
                self.assertEqual(kinds[i + 1], "seq")

    def test_random_material_is_finger_balanced(self) -> None:
        # A random baseline that starves a finger makes its per-finger
        # comparison meaningless, same argument as everywhere else in
        # the suite.
        _, mode = _build_mode()
        for seg in mode.segments:
            if seg.kind in ("warmup", "random"):
                per = len(seg.fingers) // 4
                for finger in range(4):
                    self.assertEqual(seg.fingers.count(finger), per)
                pairs = zip(seg.fingers, seg.fingers[1:])
                self.assertTrue(all(a != b for a, b in pairs))

    def test_lopsided_warmup_does_not_warn_but_lopsided_random_does(
            self) -> None:
        # Audit finding #14: the shipped warmup (20 trials) is not a
        # multiple of 4 lanes, so with the warning unconditional every
        # default bimanual block cried wolf about a segment that is
        # excluded from analysis anyway, training the researcher to
        # ignore the same warning firing about B1, where it matters.
        import logging
        log = logging.getLogger("finger_rehab.game.modes.pattern")
        with self.assertNoLogs(log, level="WARNING"):
            _build_mode(warmup_trials=21, random_block_trials=64)
        with self.assertLogs(log, level="WARNING") as cm:
            _build_mode(warmup_trials=20, random_block_trials=61)
        self.assertIn("random block", cm.output[0])
        self.assertNotIn("warmup block", cm.output[0])


class BimanualLayoutTests(unittest.TestCase):
    """The 8-lane session layout bilateral play depends on: the K8
    cycle instead of the 12-item SOC, the halved cycle count that
    keeps take length in the standard envelope, and the same probe
    positions and hygiene the unilateral layout guarantees."""

    def test_both_hands_use_the_k8_cycle(self) -> None:
        _, mode = _build_mode(lanes=list(range(8)))
        self.assertEqual(mode.n_fingers, 8)
        self.assertEqual(mode.cycle_len, 24)
        self.assertEqual(len(mode.trained), 24)
        for lane in range(8):
            self.assertEqual(mode.trained.count(lane), 3)

    def test_soc_cycles_per_block_halves_for_bimanual_takes(self) -> None:
        # 5 loops of 12 unilaterally; bimanual halves the loop count so
        # a take stays near the same length (3 loops of 24 = 72, not
        # 5 loops of 24 = 120).
        _, mode = _build_mode(lanes=list(range(8)), soc_cycles_per_block=5)
        for seg in mode.segments:
            if seg.kind in ("seq", "probe"):
                self.assertEqual(len(seg.fingers), 24 * 3)

    def test_standard_layout_shape_is_unchanged_bimanual(self) -> None:
        _, mode = _build_mode(lanes=list(range(8)))
        kinds = [s.kind for s in mode.segments]
        self.assertEqual(kinds, ["warmup", "random",
                                 "seq", "seq", "seq", "probe",
                                 "seq", "seq", "seq", "probe", "seq"])
        labels = [s.label for s in mode.segments if s.kind == "probe"]
        self.assertEqual(labels, ["5", "9"])

    def test_takes_start_the_cycle_at_position_zero_bimanual(self) -> None:
        _, mode = _build_mode(lanes=list(range(8)))
        for seg in mode.segments:
            if seg.kind == "seq":
                self.assertEqual(seg.fingers[:24], mode.trained)

    def test_probe_takes_use_untrained_bimanual_material(self) -> None:
        from finger_rehab.game.modes.pattern import shared_triplets
        _, mode = _build_mode(lanes=list(range(8)))
        probe_socs = [s.fingers[:24] for s in mode.segments
                      if s.kind == "probe"]
        self.assertEqual(len(probe_socs), 2)
        for soc in probe_socs:
            self.assertIn(soc, mode.probes)
            self.assertEqual(shared_triplets(soc, mode.trained), 0)

    def test_random_block_balances_lanes_and_hands_at_the_default(
            self) -> None:
        # random_block_trials=64 is the shipped default specifically
        # because it is a clean multiple of 8: every lane gets exactly
        # 8 trials, so the two hands (lanes 0-3 and 4-7) come out
        # exactly equal rather than within-one.
        _, mode = _build_mode(lanes=list(range(8)), random_block_trials=64)
        random_seg = next(s for s in mode.segments if s.kind == "random")
        for lane in range(8):
            self.assertEqual(random_seg.fingers.count(lane), 8)
        right = sum(1 for f in random_seg.fingers if f < 4)
        left = sum(1 for f in random_seg.fingers if f >= 4)
        self.assertEqual(right, left)

    def test_random_block_off_multiple_of_8_warns(self) -> None:
        # random_block_trials=60 does not divide evenly across 8 lanes
        # (4 lanes get 8, 4 get 7): the mode must say so rather than
        # silently letting the "balances the hands too" claim slip.
        with self.assertLogs("finger_rehab.game.modes.pattern",
                             level="WARNING") as cm:
            _build_mode(lanes=list(range(8)), random_block_trials=60)
        self.assertTrue(any("does not divide evenly" in m
                            for m in cm.output))

    def test_block_stats_scores_a_bimanual_probe(self) -> None:
        # Same probe-minus-flankers arithmetic as the unilateral case,
        # exercised on an 8-lane build so the K8 material path is
        # covered end to end, not just the generator in isolation.
        _, mode = _build_mode(lanes=list(range(8)))
        probe_i = _seg_index(mode, "probe")
        flankers = (probe_i - 1, probe_i + 1)
        # Past the block-start exclusion (a full 24-trial cycle here),
        # with one shared RT per take so the mean is unchanged.
        n_rows = mode.cycle_len + 5
        for i, rt in ((flankers[0], 320.0), (flankers[1], 360.0),
                      (probe_i, 440.0)):
            for _ in range(n_rows):
                mode._trials.append((i, True, rt))
            mode.segments[i].n_done += n_rows
            mode.segments[i].n_correct += n_rows
        stats = mode.block_stats()
        self.assertEqual(stats["cycle_len"], 24)
        self.assertEqual(len(stats["trained_soc"].split(",")), 24)
        probe = [p for p in stats["probe_scores"]
                 if p["block"] == mode.segments[probe_i].label][0]
        # 440 - mean(320, 360) = 100.
        self.assertAlmostEqual(probe["learning_score_ms"], 100.0, places=1)
        self.assertAlmostEqual(
            stats["session_learning_score_ms"], 100.0, places=1)


class TrialFlowTests(unittest.TestCase):
    """Every trial must reach engine.log_trial with the right
    pattern_trial flag: that column is the measurement, and a single
    unlabelled trial is a trial the analysis cannot use."""

    def test_seq_trial_logs_pattern_trial_true(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=10.0)
        target = mode.active.lane
        mode._handle_press(_press(lane=target, t=10.3), now=10.3)
        engine.log_trial.assert_called_once()
        kwargs = engine.log_trial.call_args.kwargs
        self.assertIs(kwargs["pattern_trial"], True)
        self.assertTrue(kwargs["stimulus"].startswith("seq;b=2;soc=trained"))
        outcome = engine.log_trial.call_args[0][1]
        self.assertAlmostEqual(outcome.rt_ms, 300.0, places=3)

    def test_probe_and_random_trials_log_pattern_trial_false(self) -> None:
        for kind in ("warmup", "random", "probe"):
            engine, mode = _build_mode()
            mode._seg_idx = _seg_index(mode, kind)
            mode._trial_in_seg = 0
            mode._fire(now=10.0)
            mode._handle_press(
                _press(lane=mode.active.lane, t=10.3), now=10.3)
            kwargs = engine.log_trial.call_args.kwargs
            self.assertIs(kwargs["pattern_trial"], False,
                          f"{kind} trial must be FALSE, never empty")
            self.assertTrue(kwargs["stimulus"].startswith(f"{kind};b="))

    def test_stimulus_records_cycle_position(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 13          # second cycle, position 1
        mode._fire(now=10.0)
        mode._handle_press(_press(lane=mode.active.lane, t=10.3), now=10.3)
        self.assertIn(";pos=1", engine.log_trial.call_args.kwargs["stimulus"])

    def test_wrong_then_correct_press_follows_classic_miss(self) -> None:
        # The cue stays until the correct press; the fumble downgrades
        # the trial to Miss so RT aggregates (correct trials only) stay
        # clean, exactly the Classic convention downstream tools parse.
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=10.0)
        target = mode.active.lane
        wrong = (target + 1) % 4
        mode._handle_press(_press(lane=wrong, t=10.2), now=10.2)
        engine.apply_wrong_press_penalty.assert_called_once()
        self.assertIsNotNone(mode.active)     # trial still open
        mode._handle_press(_press(lane=target, t=10.6), now=10.6)
        trial = engine.log_trial.call_args[0][0]
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertEqual(len(trial.incorrect_presses), 1)
        self.assertEqual(trial.incorrect_presses[0][0], wrong)

    def test_timeout_logs_a_miss_with_no_rt(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=10.0)
        mode._close(None, now=12.5)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertIsNone(outcome.rt_ms)

    def test_next_stimulus_follows_the_fixed_rsi(self) -> None:
        # The response-to-stimulus interval is the game's rhythm and
        # must never move within a participant: a timing change
        # confounds the RT contrast that is the outcome.
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=10.0)
        mode._handle_press(_press(lane=mode.active.lane, t=10.3), now=10.3)
        self.assertAlmostEqual(mode._next_stim_due, 10.3 + mode.rsi)

    def test_press_between_trials_is_ignored_not_penalised(self) -> None:
        # An RSI press is the patient anticipating the next item, which
        # is sequence knowledge being expressed. Classic's idle-press
        # penalty would punish the thing the mode measures.
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._handle_press(_press(lane=0, t=10.0), now=10.0)
        engine.apply_idle_press_penalty.assert_not_called()
        engine.apply_wrong_press_penalty.assert_not_called()
        engine.log_trial.assert_not_called()

    def test_rsi_presses_are_counted_per_take_not_lost(self) -> None:
        # Audit finding #12: an RSI press writes no trial row (there is
        # no trial to attach it to, see the test above) but must not
        # vanish entirely -- it is the one countable trace of
        # anticipatory pressing, an early marker of explicit sequence
        # knowledge, and a keyboard-only session has no raw.csv sample
        # stream to recover it from otherwise.
        _, mode = _build_mode()
        seq_i = _seg_index(mode, "seq")
        mode._seg_idx = seq_i
        mode._trial_in_seg = 0
        # Two anticipatory presses before the cue fires.
        mode._handle_press(_press(lane=0, t=10.0), now=10.0)
        mode._handle_press(_press(lane=1, t=10.05), now=10.05)
        self.assertEqual(mode._rsi_presses[seq_i], 2)
        # One ordinary trial in the same take, so it shows up in
        # block_stats' per_take list (gated on seg.n_done > 0).
        mode._fire(now=10.1)
        mode._handle_press(_press(lane=mode.active.lane, t=10.4),
                           now=10.4)
        take = next(t for t in mode.block_stats()["per_take"]
                   if t["block"] == mode.segments[seq_i].label
                   and t["kind"] == "seq")
        self.assertEqual(take["n_rsi_presses"], 2)
        # A take with no RSI presses reports zero, not a missing key.
        other_seq_i = _seg_index(mode, "seq", nth=1)
        mode._seg_idx = other_seq_i
        mode._trial_in_seg = 0
        mode._fire(now=20.0)
        mode._handle_press(_press(lane=mode.active.lane, t=20.3),
                           now=20.3)
        other_take = next(t for t in mode.block_stats()["per_take"]
                          if t["block"] == mode.segments[other_seq_i].label
                          and t["kind"] == "seq")
        self.assertEqual(other_take["n_rsi_presses"], 0)

    def test_pause_shifts_inflight_deadlines(self) -> None:
        _, mode = _build_mode()
        mode._t0 = 100.0
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=110.0)
        mode.on_resume(5.0)
        self.assertAlmostEqual(mode.active.stim_t_perf, 115.0)
        # The session-cap clock must not count the pause either.
        self.assertAlmostEqual(mode._t0, 105.0)


class RestFlowTests(unittest.TestCase):
    """Rests are self-paced past a floor. Without the floor a keen
    patient skips recovery; without the self-pacing a tired one is
    rushed. Placement is measurement-critical: a rest speeds up the
    take after it, so the one long rest must sit where the scoring
    never looks (after take 6), and probes must see the same floor on
    both sides."""

    def test_rest_gates_on_the_floor_then_any_press_advances(self) -> None:
        _, mode = _build_mode()
        seq_i = _seg_index(mode, "seq")
        mode._seg_idx = seq_i
        mode._after_segment(now=100.0)
        self.assertEqual(mode.phase, "rest")
        # Before the floor a press does nothing.
        mode._handle_press(_press(lane=0, t=105.0), now=105.0)
        self.assertEqual(mode.phase, "rest")
        # After it, any finger moves to the next take.
        mode._handle_press(_press(lane=0, t=116.0), now=116.0)
        self.assertEqual(mode.phase, "play")
        self.assertEqual(mode._seg_idx, seq_i + 1)

    def test_long_rest_follows_take_six_not_the_probe(self) -> None:
        # The rest boost lands on the take AFTER a rest, so the long
        # rest sits where the boosted take (B7) is never read by the
        # probe subtraction. A probe take gets the plain floor.
        _, mode = _build_mode()
        take6 = next(i for i, s in enumerate(mode.segments)
                     if s.label == "6")
        mode._seg_idx = take6
        mode._after_segment(now=100.0)
        self.assertAlmostEqual(mode._rest_min_until, 100.0 + mode.long_rest)

    def test_probe_rests_are_the_plain_floor_on_both_sides(self) -> None:
        _, mode = _build_mode()
        probe_i = _seg_index(mode, "probe")
        # After the probe itself.
        mode._seg_idx = probe_i
        mode._after_segment(now=100.0)
        self.assertAlmostEqual(mode._rest_min_until, 100.0 + mode.rest_min)
        # After the trained take right before the probe.
        mode.phase = "play"
        mode._seg_idx = probe_i - 1
        mode._after_segment(now=200.0)
        self.assertAlmostEqual(mode._rest_min_until, 200.0 + mode.rest_min)

    def test_short_session_has_no_long_rest(self) -> None:
        # In the 8-take layout B6 flanks BOTH probes, so there is no
        # take an asymmetric rest can boost without the scoring
        # reading it; every break uses the floor.
        _, mode = _build_mode(short_session=True)
        self.assertFalse(any(s.long_rest_after for s in mode.segments))

    def test_final_take_ends_the_block(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = len(mode.segments) - 1
        mode._after_segment(now=100.0)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "completed")


class FatigueAndCapTests(unittest.TestCase):
    """The stop rules are what make a 620-trial session safe to hand a
    stroke patient: silence gets a rest, twice gets a graceful end, and
    the wall clock has a ceiling. Probe slowing must never trip them."""

    def _run_timeouts(self, mode, n: int, t0: float = 100.0) -> float:
        t = t0
        for _ in range(n):
            mode._fire(now=t)
            t += mode.timeout + 0.1
            mode._close(None, now=t)
            if mode.phase != "play":
                break
        return t

    def test_five_silent_timeouts_force_one_rest(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        t_end = self._run_timeouts(mode, 5)
        self.assertEqual(mode.phase, "rest")
        self.assertEqual(mode._rest_kind, "forced")
        self.assertEqual(mode._fatigue_triggers, 1)
        # The forced rest has its own duration: its job is recovery,
        # which the 10 s between-take floor is too thin for.
        self.assertAlmostEqual(mode._rest_min_until,
                               t_end + mode.fatigue_rest)
        self.assertGreater(mode.fatigue_rest, mode.rest_min)
        engine.finish_block.assert_not_called()

    def test_second_fatigue_run_ends_the_session_gracefully(self) -> None:
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fatigue_triggers = 1
        self._run_timeouts(mode, 5)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "fatigue")

    def test_probe_timeouts_never_count_as_fatigue(self) -> None:
        # Slowing down on a probe is the expected sign of learning, so
        # it must not read as exhaustion.
        engine, mode = _build_mode()
        mode._seg_idx = _seg_index(mode, "probe")
        mode._trial_in_seg = 0
        self._run_timeouts(mode, 6)
        self.assertEqual(mode.phase, "play")
        self.assertEqual(mode._fatigue_triggers, 0)
        engine.finish_block.assert_not_called()

    def test_session_cap_ends_at_the_next_trial_close(self) -> None:
        engine, mode = _build_mode(session_cap_min=1.0)
        mode._t0 = 0.0
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        mode._fire(now=100.0)
        mode._handle_press(_press(lane=mode.active.lane, t=100.3), now=100.3)
        # The trial itself still logs; the block then ends.
        engine.log_trial.assert_called_once()
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "time_cap")


class TestModeDemoTests(unittest.TestCase):
    """Test Mode has to show the whole pipeline in under a minute AND
    still write both pattern_trial values, or a supervisor demo
    produces a CSV that looks nothing like a real session's."""

    def test_demo_is_a_two_take_miniature(self) -> None:
        _, mode = _build_mode(demo_trials=6)
        kinds = [s.kind for s in mode.segments]
        self.assertEqual(kinds, ["seq", "probe"])
        self.assertEqual(sum(len(s.fingers) for s in mode.segments), 6)
        self.assertLessEqual(mode.rest_min, 2.0)
        self.assertLessEqual(mode.fatigue_rest, 2.0)
        # Demo takes are shorter than a cycle, so the block-start RT
        # exclusion is off or the demo CSV would carry no RT stats.
        self.assertEqual(mode.start_trim, 0)

    def test_demo_material_still_follows_the_design(self) -> None:
        _, mode = _build_mode(demo_trials=6)
        seq_seg, probe_seg = mode.segments
        # Even a demo plays the participant's real material: trained
        # riff first, then a probe from the pool.
        self.assertEqual(seq_seg.fingers, mode.trained[:4])
        self.assertEqual(probe_seg.fingers,
                         mode.probes[mode.probe_offset][:2])


class BlockStatsTests(unittest.TestCase):
    """The block summary carries the learning score, the material used
    and the exclusion counts, so a session is readable without opening
    trials.csv and the analysis can rebuild every decision."""

    def test_learning_score_is_probe_minus_flanker_mean(self) -> None:
        _, mode = _build_mode()
        probe_i = _seg_index(mode, "probe")
        flankers = (probe_i - 1, probe_i + 1)
        # Enough rows that the block-start exclusion (first cycle of
        # every take) still leaves RTs; every row in a take shares one
        # value so the take mean is unchanged by the trim.
        n_rows = mode.cycle_len + 5
        for i, rt in ((flankers[0], 300.0), (flankers[1], 340.0),
                      (probe_i, 420.0)):
            for _ in range(n_rows):
                mode._trials.append((i, True, rt))
            mode.segments[i].n_done += n_rows
            mode.segments[i].n_correct += n_rows
        stats = mode.block_stats()
        probe = [p for p in stats["probe_scores"]
                 if p["block"] == mode.segments[probe_i].label][0]
        # 420 - mean(300, 340) = 100.
        self.assertAlmostEqual(probe["learning_score_ms"], 100.0, places=1)
        self.assertEqual(probe["n_flankers"], 2)
        self.assertAlmostEqual(
            stats["session_learning_score_ms"], 100.0, places=1)

    def test_anticipations_leave_rt_stats_but_keep_accuracy(self) -> None:
        # Sub-100 ms presses cannot be responses to the stimulus, so
        # they stay in the accuracy count but not the RT mean. The
        # block-start exclusion has its own tests below; disabled here
        # so this one stays about the anticipation cut.
        _, mode = _build_mode()
        mode.start_trim = 0
        seq_i = _seg_index(mode, "seq")
        for rt in (50.0, 300.0, 300.0, 300.0):
            mode._trials.append((seq_i, True, rt))
        mode.segments[seq_i].n_done = 4
        mode.segments[seq_i].n_correct = 4
        st = mode._segment_rt_stats(seq_i)
        self.assertEqual(st["n_anticipation"], 1)
        self.assertEqual(st["n_rt_used"], 3)
        self.assertAlmostEqual(st["mean_rt_ms"], 300.0, places=1)
        self.assertAlmostEqual(st["accuracy"], 1.0, places=3)

    def test_first_cycle_of_a_take_leaves_rt_aggregates(self) -> None:
        # The first presses after a rest carry a recovery transient
        # that is not learning (Das 2025; Gupta and Rickard 2022), so
        # the first cycle of every take leaves RT stats. Accuracy
        # keeps every trial.
        _, mode = _build_mode()
        self.assertEqual(mode.start_trim, mode.cycle_len)
        seq_i = _seg_index(mode, "seq")
        # First cycle artificially fast (the post-rest burst), the
        # rest of the take steady at 400 ms.
        for _ in range(mode.cycle_len):
            mode._trials.append((seq_i, True, 200.0))
        for _ in range(10):
            mode._trials.append((seq_i, True, 400.0))
        n = mode.cycle_len + 10
        mode.segments[seq_i].n_done = n
        mode.segments[seq_i].n_correct = n
        st = mode._segment_rt_stats(seq_i)
        self.assertEqual(st["n_start_excluded"], mode.cycle_len)
        self.assertEqual(st["n_rt_used"], 10)
        # The burst never reaches the mean.
        self.assertAlmostEqual(st["mean_rt_ms"], 400.0, places=1)
        self.assertAlmostEqual(st["accuracy"], 1.0, places=3)

    def test_start_exclusion_counts_positions_not_rt_rows(self) -> None:
        # Position within the take counts every closed trial, correct
        # or not: a miss inside the first cycle consumes one of its
        # slots rather than pushing the exclusion deeper into the take.
        _, mode = _build_mode()
        seq_i = _seg_index(mode, "seq")
        for _ in range(mode.cycle_len):
            mode._trials.append((seq_i, False, None))
        for _ in range(4):
            mode._trials.append((seq_i, True, 350.0))
        st = mode._segment_rt_stats(seq_i)
        self.assertEqual(st["n_start_excluded"], 0)
        self.assertEqual(st["n_rt_used"], 4)
        self.assertAlmostEqual(st["mean_rt_ms"], 350.0, places=1)

    def test_stats_record_the_material_and_seeds(self) -> None:
        _, mode = _build_mode()
        stats = mode.block_stats()
        self.assertEqual(stats["participant_seed"], 1234)
        self.assertEqual(stats["block_seed"], 99)
        self.assertEqual(len(stats["trained_soc"].split(",")), 12)
        self.assertGreaterEqual(len(stats["probe_pool"]), 2)
        self.assertEqual(stats["rsi_ms"], 500)
        self.assertEqual(stats["timeout_ms"], 2000)
        # The rest protocol and RT hygiene that shaped the numbers:
        # the notebook reads start_trim to apply the same exclusion.
        self.assertEqual(stats["rest_min_s"], 10.0)
        self.assertEqual(stats["long_rest_s"], 30.0)
        self.assertEqual(stats["fatigue_rest_s"], 45.0)
        self.assertEqual(stats["start_trim"], mode.cycle_len)

    def test_three_star_streak_rolls_and_records(self) -> None:
        # Reward-flavoured, accuracy-only feedback (Abe 2011; OPTIMAL
        # theory): consecutive 3-star takes are counted, the best run
        # lands in the block summary, and speed never enters it.
        _, mode = _build_mode()
        take_idxs = [i for i, s in enumerate(mode.segments)
                     if s.kind != "warmup"]

        def finish(i, acc_num, acc_den=20):
            seg = mode.segments[i]
            seg.n_done = acc_den
            seg.n_correct = acc_num
            mode._seg_idx = i
            mode.phase = "play"
            mode._after_segment(now=100.0 + i)

        finish(take_idxs[0], 20)          # 100% -> ***
        finish(take_idxs[1], 20)          # ***
        self.assertEqual(mode.star_streak, 2)
        finish(take_idxs[2], 15)          # 75% -> * breaks the run
        self.assertEqual(mode.star_streak, 0)
        finish(take_idxs[3], 20)          # ***
        self.assertEqual(mode.star_streak, 1)
        self.assertEqual(mode.best_star_streak, 2)
        self.assertEqual(mode.block_stats()["three_star_streak_best"], 2)

    def test_final_take_still_counts_toward_the_streak(self) -> None:
        # The last take ends the block without a rest card; its stars
        # must still roll into the streak the results screen recaps.
        _, mode = _build_mode()
        last = len(mode.segments) - 1
        seg = mode.segments[last]
        seg.n_done = 20
        seg.n_correct = 20
        mode._seg_idx = last
        mode._after_segment(now=100.0)
        self.assertEqual(mode.best_star_streak, 1)
        self.assertEqual(mode.end_reason, "completed")


class KeyboardFallbackTests(unittest.TestCase):
    """JKL; must keep working with an Arduino connected, same contract
    as every other mode: a busted auto-detect must never leave the
    therapist with no input."""

    def test_keydown_queues_a_press(self) -> None:
        import pygame
        engine, mode = _build_mode()
        engine.cfg.get = MagicMock(return_value={"j": 0, "semicolon": 3})
        e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j)
        mode.handle_event(e)
        self.assertEqual(len(mode._presses), 1)
        self.assertEqual(mode._presses[0].lane, 0)

    def test_keyboard_session_shows_the_controls_hint(self) -> None:
        # Audit finding #110: GameplayScreen (which pattern uses) drew
        # no keyboard legend at all, unconditionally, on the stale
        # premise that the patient is always on the Arduino. A
        # keyboard-fallback pattern session must get the same corner
        # Controls note syllables already had, and a real sensor
        # session must still get none of it.
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            from finger_rehab.ui.widgets import keyboard_controls_lines
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                cfg.data["session"]["participant"] = "Basil"
                eng = GameEngine(cfg, KeyboardOnlySource())
                eng.session.participant = "Basil"
                eng._screens = {"gameplay": MagicMock(lanes=[]),
                                "results": MagicMock()}
                eng.begin_pattern_block()
                lines = keyboard_controls_lines(eng, eng.mode)
                self.assertEqual(lines, ["Right hand: J K L ;"])
        finally:
            pygame.quit()
        # A real-sensor session (provides_samples True) gets nothing.
        engine, mode = _build_mode()
        engine.source = MagicMock(provides_samples=True)
        self.assertEqual(keyboard_controls_lines(engine, mode), [])


class ScoreCapTests(unittest.TestCase):
    """Audit finding #11: the default ScoreConfig gives its top tier
    (Perfect, 10 points) to RTs at or under 100 ms, exactly the
    anticipation region the mode's own RT stats exclude as
    non-stimulus-driven. Rewarding that response class more than an
    honest one biases the whole session toward guessing. Engine-level
    because the cap is applied where the mode is built
    (GameEngine.begin_pattern_block), not in PatternMode itself."""

    def test_pattern_block_caps_perfect_points_to_good(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                cfg.data["session"]["participant"] = "Basil"
                eng = GameEngine(cfg, KeyboardOnlySource())
                eng.session.participant = "Basil"
                eng._screens = {"gameplay": MagicMock(lanes=[]),
                                "results": MagicMock()}
                # The suite-wide default rewards a sub-100 ms guess
                # more than any other mode's honest response.
                self.assertGreater(eng.score_cfg.perfect_points,
                                   eng.score_cfg.good_points)
                eng.begin_pattern_block()
                self.assertEqual(eng.mode.score_cfg.perfect_points,
                                 eng.mode.score_cfg.good_points)
                # The tier label is untouched -- only the points are
                # levelled (the docstring's own distinction).
                from finger_rehab.game.scoring import classify
                fast = classify(50.0, eng.mode.score_cfg)
                self.assertEqual(fast.label, "Perfect")
                self.assertEqual(fast.points, eng.mode.score_cfg.good_points)
        finally:
            pygame.quit()


class ResultsScreenPatientFacingTests(unittest.TestCase):
    """Two docstring promises the shipped Results screen used to break
    (audit findings #9 and #10): 'RT numbers are never shown' (Boyd and
    Winstein -- explicit sequence knowledge impairs the implicit
    learning this mode measures) and nothing patient-facing names the
    concept of a repeating pattern."""

    def _draw_pattern_results(self, block_summary_pattern):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.ui.screens import ResultsScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.hits, e.misses, e.score = 500, 20, 1200
        e.current_block, e.hand_mode = "pattern", "right"
        e.best_streak, e.per_lane_stats = 5, {}
        e.hit_streak = 5
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"pattern": block_summary_pattern}})()
        e.stop_all_motors = lambda *a, **k: None
        # A 50 ms anticipation dragging the pool, exactly the finding
        # #9 failure scenario: BEST RT would read a sub-100 ms guess.
        e.overall_mean_rt = lambda: 55.0
        e.overall_best_rt = lambda: 50.0
        r = ResultsScreen(e)
        r._shown_t = 1.0
        cards = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: cards.append((lbl, val)))
        charts = []
        r._draw_per_lane_chart = (
            lambda surf, rect, title, *a, **k: charts.append(title))
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        self._charts = charts
        return cards

    def test_no_rt_cards_on_a_pattern_results_screen(self) -> None:
        cards = self._draw_pattern_results({
            "per_take": [
                {"block": "2", "kind": "seq", "n": 60, "accuracy": 0.97},
            ],
        })
        labels = [lbl for lbl, _ in cards]
        self.assertNotIn("AVG RT", labels)
        self.assertNotIn("BEST RT", labels)
        # The BEST RT value the mean/best functions would have supplied
        # (55/50 ms, an anticipation) must not appear under any label.
        self.assertNotIn("50 ms", [v for _, v in cards])
        self.assertNotIn("55 ms", [v for _, v in cards])
        # The per-finger MEAN RT chart is an RT number too: pattern
        # results draw the what-this-trains panel instead of any
        # per-lane timing chart.
        self.assertEqual(self._charts, [])

    def test_pattern_results_recap_the_star_run(self) -> None:
        cards = self._draw_pattern_results({
            "three_star_streak_best": 4,
            "per_take": [
                {"block": "2", "kind": "seq", "n": 60, "accuracy": 0.97},
            ],
        })
        self.assertIn(("BEST 3-STAR RUN", "4 takes"), cards)

    def test_pattern_results_show_accuracy_not_speed(self) -> None:
        cards = self._draw_pattern_results({
            "per_take": [
                {"block": "2", "kind": "seq", "n": 60, "accuracy": 0.90},
                {"block": "3", "kind": "seq", "n": 60, "accuracy": 0.80},
            ],
        })
        labels = [lbl for lbl, _ in cards]
        self.assertIn("TAKES", labels)
        self.assertIn("ACCURACY", labels)
        self.assertIn("STARS EARNED", labels)

    def test_mode_select_card_and_results_pill_never_say_pattern(
            self) -> None:
        # audit finding #10: config/default.yaml calls never showing
        # the patient the word "pattern" non-negotiable, but the mode
        # card, title-screen overlay and results pill all used to say
        # "Patterns"/"PATTERN".
        from finger_rehab.ui.screens import ModeSelectScreen, TitleScreen
        mode_titles = dict((k, t) for k, t, _ in ModeSelectScreen.MODES)
        self.assertEqual(mode_titles["pattern"], "Muscle Memory")
        overlay_text = "\n".join(TitleScreen.INFO_STEPS)
        self.assertNotIn("Patterns", overlay_text)
        self.assertIn("Muscle Memory", overlay_text)


class EngineIntegrationTests(unittest.TestCase):
    """begin_pattern_block through to the CSV and metadata on disk: the
    path a real session takes, where a broken column value or a missing
    summary would show up."""

    def test_block_writes_labelled_rows_and_summary(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                # Test Mode gives the two-take miniature so the test
                # exercises the same demo path a supervisor sees.
                cfg.data["game"]["test_mode_enabled"] = True
                cfg.data["game"]["test_mode_trials"] = 6
                cfg.data["session"]["participant"] = "Basil"
                eng = GameEngine(cfg, KeyboardOnlySource())
                eng.session.participant = "Basil"
                gp = MagicMock()
                gp.lanes = []
                eng._screens = {"gameplay": gp, "results": MagicMock()}
                eng.begin_pattern_block()
                self.assertEqual(eng.current_block, "pattern")
                mode = eng.mode
                # One trained trial (clean 300 ms press) and one probe
                # trial (timeout), so both labels land in the CSV.
                mode._seg_idx = 0
                mode._begin_segment(now=100.0)
                mode._fire(now=102.0)
                target = mode.active.lane
                mode._handle_press(_press(lane=target, t=102.3), now=102.3)
                mode._seg_idx = 1
                mode._begin_segment(now=120.0)
                mode._fire(now=122.0)
                mode._close(None, now=124.5)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                with (root / "trials.csv").open() as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 2)
                seq_row, probe_row = rows
                self.assertEqual(seq_row["pattern_trial"], "TRUE")
                self.assertTrue(
                    seq_row["stimulus"].startswith("seq;b=1;soc=trained"))
                self.assertAlmostEqual(
                    float(seq_row["time_difference_ms"]), 300.0, delta=1.0)
                self.assertEqual(probe_row["pattern_trial"], "FALSE")
                self.assertTrue(
                    probe_row["stimulus"].startswith("probe;b=2;soc=p"))
                self.assertEqual(probe_row["early_late"], "Miss")
                meta = json.loads((root / "metadata.json").read_text())
                stats = meta["block_summary"]["pattern"]
                self.assertTrue(stats["demo"])
                self.assertEqual(
                    len(stats["trained_soc"].split(",")), 12)
                self.assertEqual(stats["n_trials"], 2)
        finally:
            pygame.quit()

    def test_trained_sequence_survives_an_engine_rebuild(self) -> None:
        # The stability non-negotiable at the engine level: two blocks
        # built from scratch for the same participant name use the same
        # trained sequence, with no state file involved.
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            with tempfile.TemporaryDirectory() as td:
                sequences = []
                for _ in range(2):
                    cfg = Config.load()
                    cfg.data["ui"]["resolution"] = [640, 480]
                    cfg.data["audio"]["enabled"] = False
                    cfg.data["session"]["data_dir"] = td
                    cfg.data["report"] = {"enabled": False}
                    cfg.data["game"]["test_mode_enabled"] = True
                    eng = GameEngine(cfg, KeyboardOnlySource())
                    eng.session.participant = "Basil"
                    eng._screens = {"gameplay": MagicMock(lanes=[]),
                                    "results": MagicMock()}
                    eng.begin_pattern_block()
                    sequences.append(list(eng.mode.trained))
                    eng._abandon_if_in_block()
                self.assertEqual(sequences[0], sequences[1])
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
