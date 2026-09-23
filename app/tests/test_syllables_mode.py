"""Tests for Syllables, the children's syllable-matching mode.

The guarantees pinned here are the ones the measurement and the
child's experience depend on.

The task: a word is heard and modelled, then one option set per
syllable in order, four tiles over four fingers, and only a press on
the target lane after the lockout scores. One trials.csv row per SET,
carrying the whole set (every option, its lane and its foil kind) and
every press that landed, so the notebook can rebuild the screen the
child answered.

No hints: the model's tactile pulse is a four-finger roll and never a
single lane, the option-set spawn goes through the engine's cue path
with silent_stim set so nothing is heard, felt or highlighted, and the
target lane is drawn by the deficit rule with a random tie-break.

The learning rules: a 3-down-1-up staircase moves the foil rung on
first-press correctness, the band gate keeps the brief's 8-of-10 /
under-5-of-10 rule on word outcomes and freezes while the source is
down, a missed word comes back after 2 words and then 4 and then
retires, and two Misses in a row bias one draw to the child's best
syllable count.

The kindness rules: a wrong press greys one tile and does nothing
else, the set stays answerable, nothing is ever taken away, and the
corrective display for a missed set arrives at the exit line rather
than on top of the wrong press.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _press(lane: int, t: float = 0.0, hand: str = "right"):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                      hand=hand)


def _build_mode(hand_mode: str = "right", **overrides):
    """A SyllablesMode wired to a MagicMock engine, driven with
    explicit `now` values through _tick. Speech is off (no assets and
    no `say` in a test), the peak helper reports no force data
    (keyboard reality) unless a test installs its own, and the timing
    knobs are shrunk so a scenario runs in a handful of ticks."""
    from finger_rehab.game.modes.syllables import SyllablesMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = hand_mode
    engine.source.provides_samples = False
    engine.detectors = {}
    engine._peak_force_for_lane = lambda lane: None
    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "game.keyboard_map": {"j": 0, "k": 1, "l": 2, "semicolon": 3},
        "game.keyboard_map_left": {"f": 4, "d": 5, "s": 6, "a": 7},
        "game.keyboard_map_both": {"j": 0, "k": 1, "l": 2, "semicolon": 3,
                                   "f": 4, "d": 5, "s": 6, "a": 7},
    }.get(k, d))
    kwargs = dict(
        engine=engine,
        lanes=[0, 1, 2, 3],
        band="A",
        ioi_ms=500,
        words_total=40,
        round_size=10,
        break_s=30.0,
        warmup_taps=0,
        attend_s=0.5,
        tap_debounce_ms=150,
        inter_trial_gap_ms=0,
        session_cap_min=20.0,
        score_cfg=ScoreConfig(),
        seed=7,
        speech={"backend": "off"},
        demo_trials=None,
    )
    kwargs.update(overrides)
    return engine, SyllablesMode(**kwargs)


def _run_to_choose(mode, t: float = 0.0, step: float = 0.05) -> float:
    """Tick from cold through attend and model until a set is on
    screen. Returns the time at which it spawned."""
    guard = 0
    while not (mode.phase == "choose" and mode.option_set is not None):
        mode._tick(t)
        t += step
        guard += 1
        if guard > 2000:
            raise AssertionError(f"never reached a set, at {mode.phase}")
    return t


def _wait_for_next_set(mode, t: float, step: float = 0.05) -> float:
    """Tick until the next set is on screen (or the word ends)."""
    guard = 0
    start_word = mode.word.word if mode.word else None
    start_pos = mode.pos
    while True:
        mode._tick(t)
        t += step
        guard += 1
        if (mode.phase == "choose" and mode.option_set is not None
                and (mode.pos != start_pos
                     or (mode.word and mode.word.word != start_word))):
            return t
        if guard > 2000:
            raise AssertionError(f"no next set, at {mode.phase}")


def _answer_set(mode, t: float, lane=None, delay: float = 0.3) -> float:
    """Press `lane` (the target by default) `delay` after the spawn,
    then tick past the set's close."""
    lane = mode.option_set.target_lane if lane is None else lane
    t_press = mode._spawn_t + delay
    mode.queue_press(_press(lane, t_press,
                            hand=mode._hand_of_lane(lane)))
    mode._tick(t_press)
    t = max(t, t_press) + 0.05
    for _ in range(20):
        mode._tick(t)
        t += 0.05
        if mode.option_set is None:
            break
    return t


def _play_word(mode, t: float, policy: str = "right") -> float:
    """Play one whole word under a policy: right (every set answered
    correctly), wrong_then_right, or miss (never press)."""
    t = _run_to_choose(mode, t) if mode.option_set is None else t
    word = mode.word.word
    guard = 0
    while mode.word and mode.word.word == word and mode.phase in (
            "choose", "complete"):
        if mode.phase == "choose" and mode.option_set is not None:
            oset = mode.option_set
            if policy == "right":
                t = _answer_set(mode, t)
            elif policy == "wrong_then_right":
                wrong = [o.lane for o in oset.options
                         if o.lane != oset.target_lane][0]
                mode.queue_press(_press(wrong, mode._spawn_t + 0.3))
                mode._tick(mode._spawn_t + 0.3)
                t = _answer_set(mode, t, delay=0.6)
            else:
                # Sit on the hands and let the set leave the screen,
                # then wait out the corrective glow.
                t = max(t, mode._spawn_t + mode.fall_s + 0.01)
                mode._tick(t)
                t += mode.MISS_GLOW_S + 0.05
                mode._tick(t)
        mode._tick(t)
        t += 0.05
        guard += 1
        if guard > 400:
            raise AssertionError("word never closed")
    return t


def _stimuli(engine) -> list[str]:
    return [c.kwargs["stimulus"] for c in engine.log_trial.call_args_list]


def _parse_stimulus(cell: str) -> dict:
    """The parser the notebook uses, written out here so the mode and
    the analysis can be checked against ONE definition of the row (the
    notebook request file carries the same code)."""
    parts = cell.split(";")
    out: dict = {"word": parts[0]}
    for p in parts[1:]:
        key, _, val = p.partition("=")
        if key == "opts":
            opts = []
            for entry in filter(None, val.split(",")):
                lane, text, kind = entry.split(":")
                opts.append((int(lane), text, kind))
            out["opts"] = opts
        elif key == "presses":
            presses = []
            for entry in filter(None, val.split(",")):
                lane, t_ms, peak, kind = entry.split(":")
                presses.append((int(lane), float(t_ms),
                                float(peak) if peak else None, kind))
            out["presses"] = presses
        elif key in ("pos", "nsyll", "rung", "respeak", "ret", "tlane",
                     "streak", "ease", "sup"):
            out[key] = int(val)
        elif key in ("fall", "rt"):
            out[key] = float(val) if val else None
        else:
            out[key] = val
    return out


def _raw_events(engine, name: str) -> list[str]:
    return [c.args[0] if c.args else c.kwargs.get("event")
            for c in engine.raw_logger.queue_event.call_args_list
            if (c.args and c.args[0] == name)]


def _raw_details(engine, name: str) -> list[str]:
    return [c.kwargs.get("detail", "")
            for c in engine.raw_logger.queue_event.call_args_list
            if c.args and c.args[0] == name]


# ---------------------------------------------------------------------------


class FlowTests(unittest.TestCase):
    """One word from cold: the phases in order, one row per set, and a
    stimulus string that round-trips."""

    def test_phase_order_and_one_row_per_set(self) -> None:
        engine, mode = _build_mode()
        seen: list[str] = []
        t = 0.0
        for _ in range(400):
            mode._tick(t)
            if not seen or seen[-1] != mode.phase:
                seen.append(mode.phase)
            t += 0.05
            if mode.phase == "choose" and mode.option_set is not None:
                t = _answer_set(mode, t)
            if seen.count("complete"):
                break
        # The gap is zero-length in the harness, so the first frame
        # is already ATTEND.
        self.assertEqual(seen[:4],
                         ["attend", "model", "choose", "complete"])
        n = mode.n_syll
        self.assertEqual(engine.log_trial.call_count, n)
        self.assertEqual(len(mode._sets), n)

    def test_the_stimulus_carries_the_whole_set(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        oset = mode.option_set
        word = mode.word
        _answer_set(mode, t)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["word"], word.word)
        self.assertEqual(row["pos"], 0)
        self.assertEqual(row["nsyll"], word.n_syll)
        self.assertEqual(row["syl"], word.syllables[0])
        self.assertEqual(row["band"], "A")
        self.assertEqual(row["rung"], 1)
        self.assertEqual(row["hand"], "R")
        self.assertEqual(row["fall"], mode.fall_s * 1000.0)
        self.assertEqual(row["respeak"], 1)
        self.assertEqual(row["ret"], 0)
        self.assertEqual(row["tlane"], oset.target_lane + 1)
        self.assertEqual(len(row["opts"]), 4)
        self.assertEqual({t for _, t, _ in row["opts"]},
                         {o.text for o in oset.options})
        self.assertEqual(row["first"], "ok")
        self.assertEqual(row["err"], "ok")
        self.assertAlmostEqual(row["rt"], 300.0, places=0)
        self.assertEqual(row["presses"][0][0], oset.target_lane + 1)
        self.assertEqual(row["presses"][0][3], "correct")
        self.assertEqual(row["sup"], 1)

    def test_the_row_is_keyed_on_the_target_lane(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        target = mode.option_set.target_lane
        _answer_set(mode, t)
        call = engine.log_trial.call_args_list[0]
        self.assertEqual(call.kwargs["correct_lanes"], [target])
        self.assertEqual(call.args[0].lane, target)
        self.assertEqual(call.kwargs["hand"], "right")

    def test_word_completes_and_the_strip_fills_in_order(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        word = mode.word
        filled_seen = []
        for k in range(word.n_syll):
            self.assertEqual(mode.pos, k)
            t = _answer_set(mode, t)
            filled_seen.append(list(mode.filled))
            if k < word.n_syll - 1:
                t = _run_to_choose(mode, t)
        self.assertEqual(mode.filled, list(word.syllables))
        self.assertEqual(filled_seen[0][0], word.syllables[0])
        self.assertIsNone(filled_seen[0][-1] if word.n_syll > 1 else "x")

    def test_block_ends_politely_at_a_word_boundary(self) -> None:
        engine, mode = _build_mode(words_total=2)
        t = 0.0
        for _ in range(600):
            mode._tick(t)
            t += 0.05
            if mode.phase == "choose" and mode.option_set is not None:
                t = _answer_set(mode, t)
            if mode.phase == "done":
                break
        self.assertEqual(mode.phase, "done")
        self.assertEqual(mode.end_reason, "completed")
        self.assertEqual(mode.words_done, 2)
        engine.finish_block.assert_called()


class ModelAndHintTests(unittest.TestCase):
    """The model tells the child the word, never the finger."""

    def test_the_model_rolls_all_four_fingers_never_one(self) -> None:
        engine, mode = _build_mode()
        t = 0.0
        while mode.phase != "choose":
            mode._tick(t)
            t += 0.05
        calls = [c.args[0] for c in engine.on_stim_multi.call_args_list]
        # One roll per syllable, then the silent spawn call.
        self.assertGreaterEqual(len(calls), mode.n_syll)
        for lanes in calls[:mode.n_syll]:
            self.assertEqual(sorted(lanes), sorted(mode.active_lanes()))
        engine.on_stim.assert_not_called()

    def test_the_spawn_marker_is_silent(self) -> None:
        # The spawn goes through the cue path for the force window,
        # the timeout and the EEG byte, with silent_stim set so the
        # engine fires no tone, no highlight and no buzzer. A cue on
        # the target lane there would hand the child the answer.
        engine, mode = _build_mode()
        seen: list[bool] = []

        def watch(lanes, trial_id, t_perf, **kw):
            seen.append(bool(getattr(mode, "silent_stim", False)))

        engine.on_stim_multi.side_effect = watch
        _run_to_choose(mode)
        self.assertTrue(seen[-1], "spawn call was not silent")
        self.assertFalse(any(seen[:mode.n_syll]),
                         "the model roll must not be silent")
        self.assertFalse(mode.silent_stim, "the flag stuck on")
        spawn_call = engine.on_stim_multi.call_args_list[-1]
        self.assertEqual(spawn_call.kwargs.get("buzz"), False)
        self.assertEqual(sorted(spawn_call.args[0]),
                         sorted(mode.active_lanes()))

    def test_no_stim_fires_between_sets(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        before = engine.on_stim_multi.call_count
        t = _answer_set(mode, t)
        # Exactly one more call, the next set's spawn.
        t = _run_to_choose(mode, t)
        self.assertEqual(engine.on_stim_multi.call_count, before + 1)

    def test_eeg_code_is_the_choice_band_only_while_choosing(self) -> None:
        from finger_rehab.hardware import eeg_trigger
        engine, mode = _build_mode()
        self.assertIsNone(mode.eeg_stim_code())
        _run_to_choose(mode)
        self.assertEqual(mode.eeg_stim_code(),
                         eeg_trigger.CODES["stim_choice_set"])
        mode.ret = 1
        self.assertEqual(mode.eeg_stim_code(),
                         eeg_trigger.CODES["stim_choice_set_return"])

    def test_the_four_tiles_are_drawn_identically(self) -> None:
        # The only thing that says which finger answers a tile is
        # where the tile is. Same size, same fill, same fade.
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.syllables_screen import SyllablesScreen
            engine, mode = _build_mode()
            _run_to_choose(mode)
            screen = SyllablesScreen.__new__(SyllablesScreen)
            screen.engine = engine
            layout = MagicMock()
            layout.width = 1280
            layout.height = 800
            screen.layout = layout
            items = SyllablesScreen.tile_layout(screen, mode,
                                                mode._spawn_t + 0.4)
            self.assertEqual(len(items), 4)
            sizes = {i["rect"].size for i in items}
            states = {i["state"] for i in items}
            ys = {i["rect"].centery for i in items}
            alphas = {i["alpha"] for i in items}
            self.assertEqual(len(sizes), 1, sizes)
            self.assertEqual(states, {"falling"})
            self.assertEqual(len(ys), 1, "tiles fall together")
            self.assertEqual(len(alphas), 1, "tiles fade together")
            xs = sorted(i["rect"].centerx for i in items)
            self.assertEqual(len(set(xs)), 4, "one lane each")
        finally:
            pygame.quit()


class InputRuleTests(unittest.TestCase):

    def test_lockout_rejects_a_press_that_beat_the_tiles(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        target = mode.option_set.target_lane
        early = mode._spawn_t + 0.1
        mode.queue_press(_press(target, early))
        mode._tick(early)
        self.assertIsNotNone(mode.option_set, "the set closed on an "
                                              "anticipation")
        self.assertEqual(mode._set_presses[-1].kind, "anticip")
        self.assertIsNone(mode._first_kind)
        # The same press after the lockout scores.
        t = _answer_set(mode, t, delay=0.3)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["first"], "ok")
        self.assertEqual([p[3] for p in row["presses"]],
                         ["anticip", "correct"])

    def test_a_wrong_press_greys_one_tile_and_nothing_else(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        oset = mode.option_set
        wrong = [o.lane for o in oset.options
                 if o.lane != oset.target_lane][0]
        tp = mode._spawn_t + 0.3
        mode.queue_press(_press(wrong, tp))
        mode._tick(tp)
        self.assertIsNotNone(mode.option_set, "a wrong press ended the set")
        self.assertEqual(mode._dead_lanes, {wrong})
        self.assertEqual(mode._first_kind, "wrong")
        self.assertEqual(engine.log_trial.call_count, 0)
        # The set is still answerable.
        t = _answer_set(mode, t, delay=0.6)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["first"], "wrong")
        self.assertEqual(row["err"], "wrong_first")
        self.assertEqual(engine.log_trial.call_args_list[0].args[1].label,
                         "Good")

    def test_a_second_press_on_a_dead_lane_is_ignored(self) -> None:
        engine, mode = _build_mode()
        _run_to_choose(mode)
        oset = mode.option_set
        wrong = [o.lane for o in oset.options
                 if o.lane != oset.target_lane][0]
        for k, dt in enumerate((0.3, 0.6)):
            tp = mode._spawn_t + dt
            mode.queue_press(_press(wrong, tp))
            mode._tick(tp)
        kinds = [p.kind for p in mode._set_presses]
        self.assertEqual(kinds, ["wrong", "wrong_repeat"])
        self.assertEqual(mode._dead_lanes, {wrong})

    def test_off_hand_presses_are_logged_and_never_scored(self) -> None:
        engine, mode = _build_mode(
            "both", lanes=[0, 1, 2, 3],
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        t = _run_to_choose(mode)
        resting = [l for l in range(8) if l not in mode.active_lanes()]
        tp = mode._spawn_t + 0.3
        mode.queue_press(_press(resting[0], tp))
        mode._tick(tp)
        self.assertEqual(mode._set_presses[-1].kind, "off_hand")
        self.assertIsNone(mode._first_kind)
        self.assertIsNotNone(mode.option_set)
        t = _answer_set(mode, t, delay=0.6)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["first"], "ok", "an off-hand press counted")
        self.assertIn("off_hand", [p[3] for p in row["presses"]])

    def test_debounce_holds_a_bouncy_finger_to_one_press(self) -> None:
        engine, mode = _build_mode()
        _run_to_choose(mode)
        oset = mode.option_set
        wrong = [o.lane for o in oset.options
                 if o.lane != oset.target_lane][0]
        for dt in (0.3, 0.35):
            tp = mode._spawn_t + dt
            mode.queue_press(_press(wrong, tp))
            mode._tick(tp)
        self.assertEqual(len(mode._set_presses), 1)

    def test_keyboard_equals_the_sensors_on_both_hands(self) -> None:
        import pygame
        pygame.init()
        try:
            for hand, keys in (("right", {"j": 0, "k": 1, "l": 2,
                                          "semicolon": 3}),
                               ("left", {"f": 4, "d": 5, "s": 6,
                                         "a": 7})):
                engine, mode = _build_mode(hand)
                if hand == "left":
                    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: {
                        "game.keyboard_map_left": keys}.get(k, d))
                    mode.hands = {"left": [4, 5, 6, 7]}
                    mode.hand_names = ["left"]
                    mode.lanes = [4, 5, 6, 7]
                for name, lane in keys.items():
                    code = pygame.key.key_code(
                        ";" if name == "semicolon" else name)
                    mode.handle_event(pygame.event.Event(
                        pygame.KEYDOWN, {"key": code}))
                queued = [ev.lane for ev in mode._presses]
                self.assertEqual(sorted(queued), sorted(keys.values()),
                                 hand)
                details = [c.kwargs.get("detail") for c
                           in engine.raw_logger.queue_event.call_args_list
                           if c.args and c.args[0] == "press"]
                self.assertTrue(all(d == "keyboard" for d in details))
        finally:
            pygame.quit()


class MissAndReturnTests(unittest.TestCase):

    def test_a_missed_set_stops_the_word_and_parks_it(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        word = mode.word
        t = mode._spawn_t + mode.fall_s + 0.01
        mode._tick(t)
        # The corrective glow is armed at the exit line, not on the
        # wrong press, and the row is already scored.
        self.assertIsNotNone(mode._glow_t)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["err"], "miss")
        self.assertEqual(row["first"], "none")
        self.assertIsNone(row["rt"])
        self.assertEqual(engine.log_trial.call_args_list[0].args[1].label,
                         "Miss")
        self.assertEqual(
            engine.log_trial.call_args_list[0].kwargs["error_type"], "miss")
        self.assertIsNone(
            engine.log_trial.call_args_list[0].kwargs["response_t_perf"])
        # The word stops: no further sets this attempt.
        for _ in range(40):
            t += 0.05
            mode._tick(t)
        self.assertEqual(engine.log_trial.call_count, 1, "the word ran on")
        self.assertEqual(len(mode._records), 1)
        self.assertEqual(mode._records[0].error, "miss")
        parked = _raw_details(engine, "word_parked")
        self.assertTrue(any(word.word in d for d in parked), parked)

    def test_a_missed_word_returns_after_two_words_then_four(self) -> None:
        engine, mode = _build_mode(seed=3)
        t = _run_to_choose(mode)
        first = mode.word.word
        hand = mode.word_hand
        t = _play_word(mode, t, "miss")
        order: list[tuple[str, int]] = []
        for _ in range(9):
            t = _run_to_choose(mode, t)
            order.append((mode.word.word, mode.ret))
            t = _play_word(mode, t, "right")
        # First return after exactly two other words, second after
        # four more.
        rets = [i for i, (w, r) in enumerate(order) if w == first]
        self.assertEqual(order[2], (first, 1),
                         f"return not after two words: {order}")
        self.assertEqual(rets[0], 2, order)
        # A returned word keeps the hand it was first played on.
        self.assertEqual(mode._records[-1].hand, hand)

    def test_a_third_miss_retires_the_word(self) -> None:
        engine, mode = _build_mode(seed=3, return_after=[0, 0])
        t = _run_to_choose(mode)
        first = mode.word.word
        for expected_ret in (0, 1, 2):
            self.assertEqual(mode.word.word, first)
            self.assertEqual(mode.ret, expected_ret)
            t = _play_word(mode, t, "miss")
            t = _run_to_choose(mode, t)
        self.assertNotEqual(mode.word.word, first)
        self.assertIn(first, mode._retired)
        details = _raw_details(engine, "word_retired")
        self.assertTrue(any(first in d for d in details), details)

    def test_returns_are_capped_so_the_block_still_ends(self) -> None:
        engine, mode = _build_mode(seed=3, words_total=12,
                                   return_after=[0, 0])
        t = 0.0
        for _ in range(4000):
            mode._tick(t)
            t += 0.05
            if mode.phase == "choose" and mode.option_set is not None:
                # Never press: every set falls off the bottom.
                t = max(t, mode._spawn_t + mode.fall_s + 0.01)
                mode._tick(t)
                t += mode.MISS_GLOW_S + 0.05
                mode._tick(t)
            if mode.phase == "done":
                break
        self.assertEqual(mode.phase, "done")
        stats = mode.block_stats()
        self.assertLessEqual(stats["words_returned"], mode.MAX_RETURNS)
        self.assertEqual(stats["words_attempted"], 12)

    def test_a_completed_return_leaves_the_queue(self) -> None:
        engine, mode = _build_mode(seed=3, return_after=[0, 0])
        t = _run_to_choose(mode)
        first = mode.word.word
        t = _play_word(mode, t, "miss")
        t = _run_to_choose(mode, t)
        self.assertEqual((mode.word.word, mode.ret), (first, 1))
        t = _play_word(mode, t, "right")
        t = _run_to_choose(mode, t)
        self.assertNotEqual(mode.word.word, first)
        self.assertEqual(mode._parked, [])


class StaircaseTests(unittest.TestCase):

    def test_three_right_raises_the_rung_and_one_wrong_lowers_it(
            self) -> None:
        engine, mode = _build_mode(rung=4)
        t = 0.0
        rungs = []
        for _ in range(3):
            t = _run_to_choose(mode, t)
            t = _answer_set(mode, t)
            rungs.append(mode.rung)
        self.assertEqual(rungs, [4, 4, 5], "3-down-1-up did not step up")
        # One wrong first press drops it straight back.
        t = _run_to_choose(mode, t)
        oset = mode.option_set
        wrong = [o.lane for o in oset.options
                 if o.lane != oset.target_lane][0]
        mode.queue_press(_press(wrong, mode._spawn_t + 0.3))
        mode._tick(mode._spawn_t + 0.3)
        t = _answer_set(mode, t, delay=0.6)
        self.assertEqual(mode.rung, 4)
        changes = _raw_details(engine, "rung_change")
        self.assertTrue(any("old=4;new=5" in d for d in changes), changes)
        self.assertTrue(any("old=5;new=4" in d for d in changes), changes)
        self.assertTrue(any("reason=wrong_first" in d for d in changes),
                        changes)

    def test_a_missed_set_lowers_the_rung(self) -> None:
        engine, mode = _build_mode(rung=5)
        t = _run_to_choose(mode)
        t = mode._spawn_t + mode.fall_s + 0.01
        mode._tick(t)
        self.assertEqual(mode.rung, 4)

    def test_the_rung_stays_inside_its_bounds(self) -> None:
        engine, mode = _build_mode(rung=8, rung_max=8)
        t = 0.0
        for _ in range(6):
            t = _run_to_choose(mode, t)
            t = _answer_set(mode, t)
        self.assertEqual(mode.rung, 8)
        engine2, mode2 = _build_mode(rung=1, rung_min=1)
        t = 0.0
        for _ in range(3):
            t = _run_to_choose(mode2, t)
            t = mode2._spawn_t + mode2.fall_s + 0.01
            mode2._tick(t)
            t += mode2.MISS_GLOW_S + 0.2
            mode2._tick(t)
        self.assertEqual(mode2.rung, 1)

    def test_fall_time_and_respeak_follow_the_rung(self) -> None:
        engine, mode = _build_mode(rung=1)
        self.assertEqual(mode.fall_s, 4.0)
        self.assertIn(1, mode.respeak_rungs)
        mode.rung = 7
        self.assertEqual(mode.fall_s, 2.5)
        self.assertNotIn(7, mode.respeak_rungs)
        # Whatever the config asks for, the fall never goes under the
        # floor the mode's timing argument rests on.
        engine2, mode2 = _build_mode(fall_s=[0.5] * 8)
        self.assertGreaterEqual(mode2.fall_s, mode2.MIN_FALL_S)

    def test_the_row_carries_the_rung_it_ran_at(self) -> None:
        engine, mode = _build_mode(rung=6)
        t = _run_to_choose(mode)
        _answer_set(mode, t)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["rung"], 6)
        self.assertEqual(row["respeak"], 0)
        self.assertEqual(row["fall"], 3000.0)

    def test_a_dead_source_freezes_the_staircase(self) -> None:
        engine, mode = _build_mode()
        engine.source.provides_samples = True
        engine.source.is_connected = False
        t = 0.0
        for _ in range(4):
            t = _run_to_choose(mode, t)
            t = _answer_set(mode, t)
        self.assertEqual(mode.rung, 1, "the rung moved on a dead link")


class BandTests(unittest.TestCase):

    def _feed(self, mode, outcomes) -> None:
        for ok in outcomes:
            mode._recent.append(ok)
            mode._since_band_change += 1
        mode._maybe_move_band()

    def test_eight_of_ten_promotes_and_shows_one_card(self) -> None:
        engine, mode = _build_mode()
        self._feed(mode, [True] * 8 + [False] * 2)
        self.assertEqual(mode.band, "B")
        self.assertEqual(mode.band_celebrate, "B")
        self.assertEqual(mode._band_trace, ["A", "B"])
        detail = _raw_details(engine, "syllables_band")
        self.assertTrue(any("shown=1" in d for d in detail), detail)

    def test_under_five_of_ten_demotes_silently(self) -> None:
        engine, mode = _build_mode(band="B")
        self._feed(mode, [True] * 4 + [False] * 6)
        self.assertEqual(mode.band, "A")
        self.assertIsNone(mode.band_celebrate)
        detail = _raw_details(engine, "syllables_band")
        self.assertTrue(detail)
        self.assertFalse(any("shown=1" in d for d in detail), detail)

    def test_the_gate_needs_a_full_window(self) -> None:
        engine, mode = _build_mode()
        self._feed(mode, [True] * 9)
        self.assertEqual(mode.band, "A")

    def test_only_first_attempts_feed_the_gate(self) -> None:
        # A returned word is a second look at material the child has
        # already met, so counting it would flatter the gate.
        engine, mode = _build_mode()
        mode.word = mode._draw_word()
        mode.filled = [None] * mode.n_syll
        mode.ret = 1
        mode._finish_word(0.0, completed=True)
        self.assertEqual(len(mode._recent), 0)


class HandTests(unittest.TestCase):

    def test_both_hands_alternate_per_word(self) -> None:
        engine, mode = _build_mode(
            "both", lanes=[0, 1, 2, 3],
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        hands = []
        t = 0.0
        for _ in range(4):
            t = _run_to_choose(mode, t)
            hands.append(mode.word_hand)
            # Every tile of the word sits on the playing hand.
            for o in mode.option_set.options:
                self.assertEqual(mode._hand_of_lane(o.lane),
                                 mode.word_hand)
            t = _play_word(mode, t, "right")
        self.assertEqual(len(set(hands)), 2, hands)
        self.assertNotEqual(hands[0], hands[1])
        self.assertEqual(hands[0], hands[2])

    def test_one_hand_plays_every_word(self) -> None:
        engine, mode = _build_mode("left", lanes=[4, 5, 6, 7])
        t = 0.0
        for _ in range(3):
            t = _run_to_choose(mode, t)
            self.assertEqual(mode.word_hand, "left")
            self.assertEqual(sorted(mode.active_lanes()), [4, 5, 6, 7])
            t = _play_word(mode, t, "right")
        self.assertTrue(all(r.hand == "left" for r in mode._records))

    def test_the_left_hand_reads_left_to_right(self) -> None:
        # Lane lists run index outward, which is right to left on the
        # left hand, so the desk order reverses: the leftmost lane on
        # screen is the little finger.
        engine, mode = _build_mode("left", lanes=[4, 5, 6, 7])
        self.assertEqual(mode.active_lanes(), [7, 6, 5, 4])

    def test_alternate_hands_off_keeps_one_hand(self) -> None:
        engine, mode = _build_mode(
            "both", alternate_hands=False, lanes=[0, 1, 2, 3],
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        t = 0.0
        hands = []
        for _ in range(3):
            t = _run_to_choose(mode, t)
            hands.append(mode.word_hand)
            t = _play_word(mode, t, "right")
        self.assertEqual(len(set(hands)), 1, hands)

    def test_the_row_names_the_word_hand(self) -> None:
        engine, mode = _build_mode(
            "both", lanes=[0, 1, 2, 3],
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        t = _run_to_choose(mode)
        hand = mode.word_hand
        _answer_set(mode, t)
        call = engine.log_trial.call_args_list[0]
        self.assertEqual(call.kwargs["hand"], hand)
        row = _parse_stimulus(_stimuli(engine)[0])
        self.assertEqual(row["hand"], "L" if hand == "left" else "R")


class RewardTests(unittest.TestCase):

    def test_stars_light_at_three_five_and_eight_words(self) -> None:
        engine, mode = _build_mode()
        t = 0.0
        stars = []
        for _ in range(8):
            t = _run_to_choose(mode, t)
            t = _play_word(mode, t, "right")
            stars.append(mode.round_stars)
        self.assertEqual(stars[2], 1)
        self.assertEqual(stars[4], 2)
        self.assertEqual(stars[7], 3)
        self.assertEqual(mode._max_streak, 8)

    def test_a_wrong_first_press_makes_the_word_good_and_ends_a_streak(
            self) -> None:
        engine, mode = _build_mode()
        t = 0.0
        for _ in range(3):
            t = _run_to_choose(mode, t)
            t = _play_word(mode, t, "right")
        self.assertEqual(mode._streak, 3)
        t = _run_to_choose(mode, t)
        t = _play_word(mode, t, "wrong_then_right")
        self.assertEqual(mode._records[-1].error, "wrong_first")
        self.assertTrue(mode._records[-1].completed)
        self.assertFalse(mode._records[-1].correct)
        self.assertEqual(mode._streak, 0)
        # Nothing is taken away: the stars stay lit for the round.
        self.assertEqual(mode.round_stars, 1)

    def test_one_sticker_per_finished_round(self) -> None:
        engine, mode = _build_mode(round_size=2, break_s=0.0)
        t = 0.0
        for _ in range(4):
            t = _run_to_choose(mode, t)
            t = _play_word(mode, t, "right")
        self.assertEqual(mode.stickers, 2)
        self.assertEqual(len(_raw_details(engine, "syllables_sticker")), 2)

    def test_a_missed_word_still_counts_toward_the_round(self) -> None:
        engine, mode = _build_mode(round_size=2, break_s=0.0)
        t = _run_to_choose(mode)
        t = _play_word(mode, t, "miss")
        t = _run_to_choose(mode, t)
        t = _play_word(mode, t, "right")
        self.assertEqual(mode.words_done, 2)
        self.assertEqual(mode.stickers, 1)

    def test_the_ease_in_draw_follows_two_missed_words(self) -> None:
        engine, mode = _build_mode(seed=3)
        t = 0.0
        for _ in range(2):
            t = _run_to_choose(mode, t)
            t = _play_word(mode, t, "miss")
        t = _run_to_choose(mode, t)
        self.assertTrue(mode._ease_word or mode.ret > 0,
                        "no ease-in draw after two missed words")
        if mode._ease_word:
            _answer_set(mode, t)
            self.assertIn("ease=1", _stimuli(engine)[-1])


class SpeechTests(unittest.TestCase):

    def test_backend_off_says_nothing(self) -> None:
        engine, mode = _build_mode(speech={"backend": "off"})
        _run_to_choose(mode)
        self.assertEqual(_raw_details(engine, "speech"), [])
        self.assertIsNone(mode._say_proc)

    def test_a_missing_file_is_logged_once_and_never_raises(self) -> None:
        engine, mode = _build_mode(
            speech={"backend": "file", "dir": "assets/no_such_dir"})
        with self.assertLogs("finger_rehab.game.modes.syllables",
                             level="INFO") as logs:
            t = _run_to_choose(mode)
            _answer_set(mode, t)
        self.assertTrue(any("No speech file" in m for m in logs.output))
        # One line per stem, not one per play.
        first = mode.word.word
        n_first = sum(1 for m in logs.output if f"'{first}'" in m)
        self.assertLessEqual(n_first, 1)

    def test_backend_say_spawns_nothing_off_a_mac(self) -> None:
        import finger_rehab.game.modes.syllables as syl
        engine, mode = _build_mode(speech={"backend": "say"})
        real = syl.sys.platform
        try:
            syl.sys.platform = "win32"
            _run_to_choose(mode)
            self.assertIsNone(mode._say_proc)
        finally:
            syl.sys.platform = real

    def test_a_rendered_file_plays_through_the_audio_engine(self) -> None:
        import tempfile
        engine, mode = _build_mode()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mode.speech_backend = "file"
            mode._speech_root = lambda: root
            (root / "banana.ogg").write_bytes(b"")
            mode.word = [w for w in
                         __import__("finger_rehab.game.modes."
                                    "syllables_words", fromlist=["x"]
                                    ).all_words()
                         if w.word == "banana"][0]
            mode._speak_word()
        engine.audio.play_speech.assert_called_once()
        args = engine.audio.play_speech.call_args
        self.assertTrue(args.args[0].endswith("banana.ogg"))
        self.assertEqual(_raw_details(engine, "speech"),
                         ["file=banana.ogg"])


class PauseTests(unittest.TestCase):

    def test_a_pause_mid_word_restarts_it_from_attend(self) -> None:
        engine, mode = _build_mode()
        t = _run_to_choose(mode)
        word = mode.word.word
        real = time.perf_counter
        try:
            time.perf_counter = lambda: t + 5.0
            mode.on_resume(5.0)
        finally:
            time.perf_counter = real
        self.assertEqual(mode.phase, "attend")
        self.assertEqual(mode.word.word, word, "the word changed")
        self.assertEqual(mode.pos, 0)
        self.assertIsNone(mode.option_set)
        details = _raw_details(engine, "trial_restart")
        self.assertTrue(details)
        self.assertIn("phase=choose", details[0])

    def test_a_pause_between_words_changes_nothing(self) -> None:
        engine, mode = _build_mode(inter_trial_gap_ms=800)
        mode._tick(0.0)
        self.assertEqual(mode.phase, "gap")
        mode.on_resume(3.0)
        self.assertEqual(mode.phase, "gap")
        self.assertEqual(_raw_details(engine, "trial_restart"), [])


class WarmupTests(unittest.TestCase):

    def test_the_warm_up_probe_logs_its_asynchronies(self) -> None:
        engine, mode = _build_mode(warmup_taps=3)
        self.assertEqual(mode.phase, "warmup")
        t = 0.0
        mode._tick(t)
        beats = list(mode._warmup_beats)
        for b in beats[mode.COUNT_IN_BEATS:]:
            mode.queue_press(_press(0, b + 0.02))
            mode._tick(b + 0.02)
        self.assertEqual(mode._warmup_done, 3)
        details = _raw_details(engine, "warmup_tap")
        self.assertEqual(len(details), 3)
        self.assertTrue(all("asyn_ms=" in d for d in details))

    def test_the_warm_up_is_capped_however_the_config_asks(self) -> None:
        engine, mode = _build_mode(warmup_taps=50)
        self.assertEqual(mode.warmup_total, mode.WARMUP_TAPS_MAX)


class BlockStatsTests(unittest.TestCase):

    def test_the_summary_carries_what_the_analysis_needs(self) -> None:
        engine, mode = _build_mode(round_size=2, break_s=0.0)
        t = 0.0
        for policy in ("right", "wrong_then_right", "miss", "right"):
            t = _run_to_choose(mode, t)
            t = _play_word(mode, t, policy)
        stats = mode.block_stats()
        for key in ("rung_start", "rung_final", "rung_trace", "n_sets",
                    "first_press_accuracy", "accuracy_by_rung",
                    "accuracy_by_pos", "accuracy_by_nsyll",
                    "confusion_by_kind", "mean_rt_correct_ms",
                    "n_anticipations", "n_off_hand", "words_attempted",
                    "words_completed", "words_returned",
                    "returns_completed", "words_retired", "per_hand",
                    "band_trace", "max_streak", "stickers", "n_ease_in",
                    "demo", "end_reason", "supervised", "chance_level",
                    "warmup_taps", "accuracy"):
            self.assertIn(key, stats)
        self.assertEqual(stats["chance_level"], 0.25)
        self.assertGreater(stats["n_sets"], 0)
        self.assertEqual(stats["words_attempted"], 4)
        self.assertEqual(stats["words_completed"], 3)
        self.assertTrue(0.0 <= stats["first_press_accuracy"] <= 1.0)
        self.assertIn("F1", stats["confusion_by_kind"])

    def test_confusion_counts_the_foil_kind_that_captured_the_press(
            self) -> None:
        engine, mode = _build_mode(rung=1)
        t = _run_to_choose(mode)
        oset = mode.option_set
        wrong = [o for o in oset.options if o.lane != oset.target_lane][0]
        mode.queue_press(_press(wrong.lane, mode._spawn_t + 0.3))
        mode._tick(mode._spawn_t + 0.3)
        _answer_set(mode, t, delay=0.6)
        self.assertEqual(mode._sets[0].wrong_kind, wrong.kind)
        self.assertEqual(mode.block_stats()["confusion_by_kind"],
                         {wrong.kind: 1})


class TimingTests(unittest.TestCase):
    """How long a block actually takes, measured rather than guessed."""

    def _minutes(self, words: int, latency: float) -> float:
        engine, mode = _build_mode(words_total=words, round_size=10,
                                   break_s=30.0, inter_trial_gap_ms=800)
        t = 0.0
        start = t
        guard = 0
        while mode.phase != "done" and guard < 200000:
            guard += 1
            mode._tick(t)
            if mode.phase == "choose" and mode.option_set is not None:
                if t >= mode._spawn_t + latency:
                    mode.queue_press(_press(mode.option_set.target_lane, t))
                    mode._tick(t)
            if mode.phase == "break" and mode._phase_until:
                t = mode._phase_until
                continue
            t += 1.0 / 60.0
        return (t - start) / 60.0

    def test_a_compliant_child_finishes_inside_the_rest_skip_cap(
            self) -> None:
        # tests/test_rest_skip.py caps a syllables block at 10.5
        # minutes with a compliant patient at 1.2 s per answer. The
        # numbers for 32 and 40 words are printed so the words per
        # block stays Basil's call rather than drifting.
        m40 = self._minutes(40, 1.2)
        m32 = self._minutes(32, 1.2)
        print(f"\nsyllables block length at 1.2 s per set: "
              f"40 words {m40:.1f} min, 32 words {m32:.1f} min")
        self.assertLess(m40, 10.5,
                        f"40 words runs {m40:.1f} min, over the "
                        "10.5 min cap in tests/test_rest_skip.py")
        self.assertGreater(m32, 0.5)


if __name__ == "__main__":
    unittest.main()
