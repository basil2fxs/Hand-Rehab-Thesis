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
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _press(lane: int, t: float = 0.0):
    from rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="right")


def _build_mode(**overrides):
    """A PatternMode wired to a MagicMock engine, driven with explicit
    `now` values instead of sleeping, following the reaction-mode test
    harness."""
    from rehab.game.modes.pattern import PatternMode
    from rehab.game.scoring import ScoreConfig
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
        rest_min_s=15.0,
        long_rest_s=60.0,
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
        from rehab.game.modes.pattern import generate_soc
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
        from rehab.game.modes.pattern import (build_sequences,
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
        from rehab.game.modes.pattern import (build_sequences,
                                              participant_seed)
        t_a, _ = build_sequences(participant_seed("alice"))
        t_b, _ = build_sequences(participant_seed("bob"))
        self.assertNotEqual(t_a, t_b)

    def test_probes_share_no_second_order_structure(self) -> None:
        from rehab.game.modes.pattern import (_canonical_rotation,
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
        # The mandatory long rest follows the first probe only.
        rests = [s.long_rest_after for s in mode.segments]
        self.assertEqual(sum(rests), 1)
        self.assertTrue(mode.segments[5].long_rest_after)

    def test_takes_start_the_cycle_at_position_zero(self) -> None:
        _, mode = _build_mode()
        for seg in mode.segments:
            if seg.kind == "seq":
                self.assertEqual(seg.fingers[:12], mode.trained)
                self.assertEqual(seg.fingers, mode.trained * 5)

    def test_probe_takes_use_untrained_material(self) -> None:
        from rehab.game.modes.pattern import shared_triplets
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
    rushed. The long rest after the first probe is part of the design."""

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

    def test_long_rest_follows_the_first_probe(self) -> None:
        _, mode = _build_mode()
        probe_i = _seg_index(mode, "probe")
        mode._seg_idx = probe_i
        mode._after_segment(now=100.0)
        self.assertAlmostEqual(mode._rest_min_until, 100.0 + mode.long_rest)

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
        self._run_timeouts(mode, 5)
        self.assertEqual(mode.phase, "rest")
        self.assertEqual(mode._rest_kind, "forced")
        self.assertEqual(mode._fatigue_triggers, 1)
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
        for i, rt in ((flankers[0], 300.0), (flankers[1], 340.0),
                      (probe_i, 420.0)):
            for _ in range(5):
                mode._trials.append((i, True, rt))
            mode.segments[i].n_done += 5
            mode.segments[i].n_correct += 5
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
        # they stay in the accuracy count but not the RT mean.
        _, mode = _build_mode()
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

    def test_stats_record_the_material_and_seeds(self) -> None:
        _, mode = _build_mode()
        stats = mode.block_stats()
        self.assertEqual(stats["participant_seed"], 1234)
        self.assertEqual(stats["block_seed"], 99)
        self.assertEqual(len(stats["trained_soc"].split(",")), 12)
        self.assertGreaterEqual(len(stats["probe_pool"]), 2)
        self.assertEqual(stats["rsi_ms"], 500)
        self.assertEqual(stats["timeout_ms"], 2000)


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


class EngineIntegrationTests(unittest.TestCase):
    """begin_pattern_block through to the CSV and metadata on disk: the
    path a real session takes, where a broken column value or a missing
    summary would show up."""

    def test_block_writes_labelled_rows_and_summary(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
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
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
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
