"""Hand support, proven through the real engine.

Basil's decision (7 Aug 2026): selecting Both hands puts all EIGHT
fingers in the game, in every mode. These tests drive every mode
through the real GameEngine under each hand selection (left-only,
right-only, both) with fake boards standing in for the hardware, and
pin four things per run:

  - the lanes cued belong to the selected hands, and with Both
    selected the cues reach both hands with the paired balance the
    schedulers promise;
  - stim commands reach the correct BOARD: left lanes to the left
    board's handle, right lanes to the right, through the real
    MultiSerialSource router;
  - a left-only session works end to end on a single LEFT board: the
    samples feed the left detector, the left calibration profile's
    thresholds decide the presses, the screen mirrors the finger
    order, and the a s d f keyboard fallback covers the lanes;
  - the block ends clean: metadata written, loggers closed.

Also pinned here: the single 3-second GET READY prep every mode runs
between pressing start and the game beginning, and the properties of
the 24-item bimanual pattern material.

The driver replaces time.perf_counter with a hand-stepped clock, the
same trick the mirror-mode tests use, so a whole session's worth of
foreperiods and rests runs in milliseconds of real time.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time as _time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def setUpModule() -> None:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    import pygame
    pygame.quit()


# ---- fakes -----------------------------------------------------------------
class FakeBoard:
    """One Arduino's command handle. Records what the router sent it,
    which is the whole point: the assertions read these lists."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def send_command(self, cmd: str) -> bool:
        self.commands.append(cmd)
        return True

    def get_sample(self, timeout: float = 0.0):
        return None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return True

    def stim(self, lane: int) -> None:
        self.send_command(f"STIM:{lane + 1}")


def make_source(hand_mode: str):
    """A real MultiSerialSource whose per-board SerialSources are
    swapped for FakeBoards, so the ROUTING under test is the shipped
    send_command, not a reimplementation. Returns (source, boards)."""
    from rehab.hardware.multi_serial import MultiSerialSource
    if hand_mode == "both":
        src = MultiSerialSource(ports=["fakeR", "fakeL"],
                                hand_assignment=["right", "left"])
    else:
        src = MultiSerialSource(ports=["fake"],
                                hand_assignment=[hand_mode])
    boards: dict[str, FakeBoard] = {}
    for h in src.hands:
        fake = FakeBoard()
        h.source = fake
        boards[h.hand] = fake
    return src, boards


class FakeClock:
    def __init__(self, t: float) -> None:
        self.t = t


class patched_clock:
    """Swap time.perf_counter for a stepped clock. Restores on exit so
    an assertion failure cannot leak a frozen clock into other tests."""

    def __enter__(self) -> FakeClock:
        self._orig = _time.perf_counter
        self.clock = FakeClock(self._orig())
        _time.perf_counter = lambda: self.clock.t
        return self.clock

    def __exit__(self, *exc) -> None:
        _time.perf_counter = self._orig


def _press(lane: int, t: float, hand: str = "right"):
    from rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=600, baseline=50.0,
                      hand=hand)


def make_engine(hand_mode: str, data_dir: str):
    """A real GameEngine on a fake board rig, screens built, reports
    off (chart generation is minutes of matplotlib the assertions
    never read), stim cues on their shipped defaults."""
    from rehab.config import Config
    from rehab.game.engine import GameEngine
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("bilateral", {})["hand"] = hand_mode
    cfg.data.setdefault("session", {})["data_dir"] = data_dir
    cfg.data["session"]["participant"] = "HandProof"
    cfg.data.setdefault("report", {})["enabled"] = False
    cfg.data.setdefault("audio", {})["enabled"] = False
    source, boards = make_source(hand_mode)
    eng = GameEngine(cfg, source)
    eng._screens = eng._build_screens()
    eng.show_results = lambda: None
    eng._fake_boards = boards

    stims: list[list[int]] = []
    orig = eng.on_stim_multi

    def recording(lanes, trial_id, t_perf):
        stims.append([int(l) for l in lanes])
        return orig(lanes, trial_id, t_perf)

    eng.on_stim_multi = recording
    eng._stim_record = stims
    return eng


def drive(eng, clock, responder=None, step_s: float = 0.05,
          max_steps: int = 6000, stop=None) -> None:
    """Step the fake clock and the mode together, letting `responder`
    press keys the way a patient would, until `stop` says the run
    proved what it needed to (or the step budget runs out, which the
    caller's assertions then report)."""
    for _ in range(max_steps):
        if eng.mode is None:
            return
        clock.t += step_s
        eng.mode.update(step_s)
        if responder is not None:
            responder(clock)
        if stop is not None and stop():
            return


def hands_of(lanes: list[int]) -> set[str]:
    return {"left" if l >= 4 else "right" for l in lanes}


# ---- stim routing: the boards addressed ------------------------------------
class StimRoutingTests(unittest.TestCase):
    """Left lanes must reach the left board's handle and right lanes
    the right board's, through the real MultiSerialSource router."""

    def test_bilateral_lanes_split_across_the_two_boards(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            for lane in range(8):
                self.assertTrue(eng._send_stim(lane), f"lane {lane}")
            right = eng._fake_boards["right"].commands
            left = eng._fake_boards["left"].commands
            # Global lanes 0..3 are the right board's STIM:1..4; global
            # 4..7 are the LEFT board's local STIM:1..4.
            self.assertEqual([c for c in right if c.startswith("STIM")],
                             ["STIM:1", "STIM:2", "STIM:3", "STIM:4"])
            self.assertEqual([c for c in left if c.startswith("STIM")],
                             ["STIM:1", "STIM:2", "STIM:3", "STIM:4"])

    def test_left_only_board_receives_the_session_stims(self) -> None:
        # A left-only session runs ONE board assigned to the left
        # hand; the engine cues lanes 0..3 and every stim must land on
        # that board.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("left", td)
            for lane in range(4):
                self.assertTrue(eng._send_stim(lane))
            left = eng._fake_boards["left"].commands
            self.assertEqual([c for c in left if c.startswith("STIM")],
                             ["STIM:1", "STIM:2", "STIM:3", "STIM:4"])

    def test_hand_prefixed_stop_reaches_one_board_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.source.send_command("LEFT:STOP")
            self.assertIn("STOP", eng._fake_boards["left"].commands)
            self.assertNotIn("STOP", eng._fake_boards["right"].commands)

    def test_same_board_chord_stims_one_board_cross_board_both(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            # A chord within the LEFT hand: only the left board buzzes
            # (as an arpeggio; the first pulse is immediate).
            eng.on_stim_multi([4, 6], 1, _time.perf_counter())
            right = [c for c in eng._fake_boards["right"].commands
                     if c.startswith("STIM")]
            left = [c for c in eng._fake_boards["left"].commands
                    if c.startswith("STIM")]
            self.assertEqual(right, [])
            self.assertTrue(left, "left board never buzzed for its chord")
            # Mirror's cross-board pair: both boards get their pulse.
            eng.on_stim_multi([0, 4], 2, _time.perf_counter())
            self.assertTrue([c for c in eng._fake_boards["right"].commands
                             if c.startswith("STIM")])


# ---- left calibration profile ----------------------------------------------
class LeftCalibrationProfileTests(unittest.TestCase):
    """The left hand's own measured thresholds decide left presses.
    A press that clears the shipped default but not the left profile
    must NOT register once the profile is applied."""

    def _engine_with_left_profile(self, td: str, gap: float):
        from rehab.hardware.calibration_profile import CalibrationProfile
        eng = make_engine("left", td)
        prof = CalibrationProfile(
            hand="left",
            empty=[10.0] * 4, empty_noise=[2.0] * 4,
            resting=[50.0] * 4,
            press=[50.0 + gap] * 4,
            press_all=[50.0 + gap] * 4,
        )
        eng.calibration_profiles["left"] = prof
        eng.apply_calibration(prof)
        return eng, prof

    def _feed(self, eng, values_fn, seconds: float = 0.4) -> list:
        events = []
        eng.detectors["left"].on_press = lambda ev: events.append(ev)
        t = _time.perf_counter()
        n = int(seconds / 0.005)
        for i in range(n):
            eng._feed_detectors(t + i * 0.005, values_fn(i))
        return events

    def test_profile_thresholds_land_on_the_left_detector(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, prof = self._engine_with_left_profile(td, gap=400.0)
            det = eng.detectors["left"]
            self.assertEqual(list(det.cal.on_delta), prof.on_delta())

    def test_press_below_the_left_profile_is_rejected(self) -> None:
        # gap 400 -> on_delta 240 per finger (0.6 of the gap). A rise
        # of 120 counts would clear the shipped default of 45 but sits
        # under the profile, so the profile is what must decide.
        with tempfile.TemporaryDirectory() as td:
            eng, _ = self._engine_with_left_profile(td, gap=400.0)
            self._feed(eng, lambda i: (50, 50, 50, 50))
            events = self._feed(
                eng, lambda i: (170, 50, 50, 50) if i > 20
                else (50, 50, 50, 50))
            self.assertEqual(events, [],
                             "a press under the left profile's threshold "
                             "was accepted")

    def test_press_above_the_left_profile_fires_with_hand_left(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, _ = self._engine_with_left_profile(td, gap=400.0)
            self._feed(eng, lambda i: (50, 50, 50, 50))
            events = self._feed(
                eng, lambda i: (700, 50, 50, 50) if i > 20
                else (50, 50, 50, 50))
            self.assertTrue(events, "no press for a clear crossing")
            self.assertEqual(events[0].hand, "left")
            self.assertEqual(events[0].lane, 0)

    def test_left_only_four_value_samples_reach_the_left_detector(self) -> None:
        # The regression this file exists to hold: a single LEFT board
        # sends 4-value samples, and they must feed the LEFT detector,
        # not be assumed to be right-hand data.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("left", td)
            events = []
            eng.detectors["left"].on_press = lambda ev: events.append(ev)
            t = _time.perf_counter()
            for i in range(80):
                vals = (50, 600, 50, 50) if i > 40 else (50, 50, 50, 50)
                eng._feed_detectors(t + i * 0.005, vals)
            self.assertTrue(any(ev.lane == 1 for ev in events),
                            f"left lane 1 press lost: {events}")


# ---- on-screen mirroring ---------------------------------------------------
class ScreenMirrorTests(unittest.TestCase):
    """The strip mirrors the LEFT hand so the on-screen order matches
    the patient's fingers: little finger on the outer left edge."""

    def test_left_mode_gameplay_strip_is_mirrored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("left", td)
            gp = eng._screens["gameplay"]
            xs = {ls.lane: ls.rect.x for ls in gp.lanes}
            # Left-to-right on screen: little(3), ring(2), middle(1),
            # index(0), matching a s d f under the left hand.
            self.assertLess(xs[3], xs[2])
            self.assertLess(xs[2], xs[1])
            self.assertLess(xs[1], xs[0])
            for ls in gp.lanes:
                self.assertEqual(ls.hand, "left")
                self.assertEqual(ls.finger, ls.lane)

    def test_bilateral_strip_left_block_sits_left_and_mirrored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            gp = eng._screens["gameplay"]
            xs = {ls.lane: ls.rect.x for ls in gp.lanes}
            # Left hand block (lanes 4..7, mirrored so 7 is outermost)
            # sits wholly left of the right hand block (lanes 0..3).
            self.assertLess(xs[7], xs[6])
            self.assertLess(xs[6], xs[5])
            self.assertLess(xs[5], xs[4])
            self.assertLess(max(xs[l] for l in (4, 5, 6, 7)),
                            min(xs[l] for l in (0, 1, 2, 3)))
            self.assertLess(xs[0], xs[1])
            for ls in gp.lanes:
                self.assertEqual(ls.hand,
                                 "left" if ls.lane >= 4 else "right")
                self.assertEqual(ls.finger, ls.lane % 4)

    def _keyboard_engine(self, hand_mode: str, data_dir: str):
        # The corner note is for the child whose input IS the
        # keyboard, so these tests need the keyboard source, not the
        # fake board rig make_engine builds.
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data.setdefault("bilateral", {})["hand"] = hand_mode
        cfg.data.setdefault("session", {})["data_dir"] = data_dir
        cfg.data["session"]["participant"] = "HandProof"
        cfg.data.setdefault("report", {})["enabled"] = False
        cfg.data.setdefault("audio", {})["enabled"] = False
        cfg.data.setdefault("game", {})["test_mode_enabled"] = True
        cfg.data.setdefault("syllables", {})["speak_words"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = eng._build_screens()
        eng.show_results = lambda: None
        return eng

    def test_syllables_keyboard_note_mirrors_the_left_hand(self) -> None:
        # The finger row under the blocks is gone by design (it pulled
        # a child's eyes off the blocks); what remains is a small
        # corner note with keyboard hints, in keyboard reading order,
        # so the left hand's keys still read a s d f.
        with tempfile.TemporaryDirectory() as td:
            eng = self._keyboard_engine("left", td)
            eng.begin_syllables_block()
            sc = eng._screens["syllables"]
            lines = sc.controls_lines(eng.mode)
            self.assertEqual(lines, ["Left hand: A S D F"])
            eng.finish_block()

    def test_syllables_keyboard_note_shows_both_hands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = self._keyboard_engine("both", td)
            eng.begin_syllables_block()
            sc = eng._screens["syllables"]
            lines = sc.controls_lines(eng.mode)
            self.assertEqual(lines, ["Left hand: A S D F",
                                     "Right hand: J K L ;"])
            eng.finish_block()

    def test_syllables_note_hides_when_real_sensors_play(self) -> None:
        # Fingers on the pads need no key legend; the note would only
        # pull the child's eyes off the blocks.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.cfg.data["syllables"]["speak_words"] = False
            eng.begin_syllables_block()
            sc = eng._screens["syllables"]
            self.assertEqual(sc.controls_lines(eng.mode), [])
            eng.finish_block()

    def test_syllables_screen_keeps_no_finger_row(self) -> None:
        # Basil's order, 7 Aug 2026: no finger or letter labels under
        # the blocks. The tiles must not quietly come back.
        from rehab.ui.syllables_screen import SyllablesScreen
        self.assertFalse(hasattr(SyllablesScreen, "_draw_finger_row"))
        self.assertFalse(hasattr(SyllablesScreen, "_finger_tiles"))

    def test_syllables_model_names_the_buzzing_hand(self) -> None:
        # In bilateral play the model's buzz hops between hands on
        # purpose; the mode must expose which hand carries the current
        # buzz so the screen can name the hop as it happens.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.cfg.data["syllables"]["speak_words"] = False
            eng.begin_syllables_block()
            mode = eng.mode
            self.assertIsNone(mode.model_hand)
            t = _time.perf_counter()
            mode._tick(t)
            seen = set()
            guard = 0
            while mode.phase != "respond" and guard < 500:
                t += 0.05
                mode._tick(t)
                if mode.phase == "model" and mode.model_hand:
                    self.assertIn(mode.model_hand, ("left", "right"))
                    seen.add(mode.model_hand)
                guard += 1
            self.assertTrue(seen, "model never exposed a buzzing hand")
            # Outside the model the tag is cleared: nothing on screen
            # should name a hand while the child is tapping.
            self.assertIsNone(mode.model_hand)
            eng.finish_block()


# ---- keyboard fallback -----------------------------------------------------
class KeyboardFallbackTests(unittest.TestCase):
    """a s d f is the left hand's fallback (f = index = lane 0), and
    the bilateral map covers all eight lanes."""

    def _key_event(self, name: str):
        import pygame
        from rehab.game.modes._keys import resolve_key
        return pygame.event.Event(pygame.KEYDOWN, key=resolve_key(name))

    def test_left_map_is_asdf_with_index_on_f(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        km = cfg.get("game.keyboard_map_left", {})
        self.assertEqual(km, {"f": 0, "d": 1, "s": 2, "a": 3})

    def test_left_mode_keys_queue_left_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("left", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.begin_reaction_block()
            mode = eng.mode
            for name, lane in (("f", 0), ("d", 1), ("s", 2), ("a", 3)):
                mode.handle_event(self._key_event(name))
                ev = mode._presses[-1]
                self.assertEqual(ev.lane, lane, f"key {name}")
            eng.finish_block()

    def test_bilateral_keys_cover_both_hands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.begin_reaction_block()
            mode = eng.mode
            for name, lane in (("j", 0), ("semicolon", 3),
                               ("f", 4), ("a", 7)):
                mode.handle_event(self._key_event(name))
                ev = mode._presses[-1]
                self.assertEqual(ev.lane, lane, f"key {name}")
            eng.finish_block()


# ---- the mode x hand matrix ------------------------------------------------
class ModeHandMatrixTests(unittest.TestCase):
    """Every mode under every hand selection: lanes cued belong to the
    selection, Both plays both hands with balance, the right boards
    are addressed, and the block ends clean."""

    def _expected_lanes(self, hand_mode: str) -> set[int]:
        return set(range(8)) if hand_mode == "both" else set(range(4))

    def _assert_boards_match_lanes(self, eng, hand_mode: str) -> None:
        # Cues default to buzz_before on, so every cued lane sent a
        # STIM somewhere; the split across boards must follow the
        # lanes that were cued.
        cued = [l for lanes in eng._stim_record for l in lanes]
        if not cued:
            return
        right_stims = [c for c in eng._fake_boards.get(
            "right", FakeBoard()).commands if c.startswith("STIM")]
        left_stims = [c for c in eng._fake_boards.get(
            "left", FakeBoard()).commands if c.startswith("STIM")]
        if hand_mode == "both":
            if any(l >= 4 for l in cued):
                self.assertTrue(left_stims,
                                "left lanes cued, left board silent")
            if any(l < 4 for l in cued):
                self.assertTrue(right_stims,
                                "right lanes cued, right board silent")
        else:
            only = eng._fake_boards[hand_mode]
            other = [b for h, b in eng._fake_boards.items()
                     if h != hand_mode]
            self.assertTrue(
                [c for c in only.commands if c.startswith("STIM")],
                f"{hand_mode} board got no stims")
            for b in other:
                self.assertEqual(
                    [c for c in b.commands if c.startswith("STIM")], [])

    def _assert_block_end_clean(self, eng) -> None:
        if eng.trial_logger is not None:
            eng.finish_block()
        self.assertIsNone(eng.trial_logger)
        self.assertIsNone(eng.raw_logger)
        self.assertIsNotNone(eng.last_session_root)
        meta = Path(eng.last_session_root) / "metadata.json"
        self.assertTrue(meta.exists(), f"no metadata at {meta}")

    def _cadence_responder(self, eng, hand_mode: str):
        """Press whatever was cued, one step after the stim, with the
        press event shaped the way the detector path shapes it."""
        seen = {"n": 0}

        def respond(clock) -> None:
            record = eng._stim_record
            while seen["n"] < len(record):
                lanes = record[seen["n"]]
                seen["n"] += 1
                for lane in lanes:
                    hand = ("left" if hand_mode == "both" and lane >= 4
                            else hand_mode if hand_mode != "both"
                            else "right")
                    if eng.mode is not None:
                        eng.mode.queue_press(
                            _press(lane, clock.t, hand=hand))
        return respond

    def _run_cadence(self, eng, clock, want_stims: int) -> None:
        drive(eng, clock,
              responder=self._cadence_responder(eng, eng.hand_mode),
              stop=lambda: (len(eng._stim_record) >= want_stims
                            or eng.trial_logger is None))

    def _matrix_engine(self, hand_mode: str, td: str, trials: int):
        eng = make_engine(hand_mode, td)
        eng.cfg.data["game"]["test_mode_enabled"] = True
        eng.cfg.data["game"]["test_mode_trials"] = trials
        return eng

    def test_reaction_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 8)
                eng.begin_reaction_block()
                self._run_cadence(eng, clock, want_stims=8)
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(cued, "no stims fired")
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    self.assertEqual(hands_of(cued), {"left", "right"})
                    n_left = sum(1 for l in cued if l >= 4)
                    # PairedBalancedScheduler: the hands never drift
                    # apart by more than one cue.
                    self.assertLessEqual(
                        abs(n_left - (len(cued) - n_left)), 1, cued)
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_classic_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 8)
                eng.begin_classic_block()
                self._run_cadence(eng, clock, want_stims=8)
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(cued)
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    self.assertEqual(hands_of(cued), {"left", "right"})
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_adaptive_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 8)
                eng.begin_adaptive_block()
                self._run_cadence(eng, clock, want_stims=8)
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(cued)
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    # The adapter alternates hands off a shuffle bag,
                    # so both hands play and never drift far apart.
                    self.assertEqual(hands_of(cued), {"left", "right"})
                    n_left = sum(1 for l in cued if l >= 4)
                    self.assertLessEqual(
                        abs(n_left - (len(cued) - n_left)), 1, cued)
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_pattern_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                # 30 demo trials = 20 trained + 10 probe: enough of
                # the 24-item bimanual cycle to see both hands.
                eng = self._matrix_engine(hand_mode, td, 30)
                eng.begin_pattern_block()
                if hand_mode == "both":
                    self.assertEqual(eng.mode.n_fingers, 8)
                    self.assertEqual(eng.mode.cycle_len, 24)
                else:
                    self.assertEqual(eng.mode.n_fingers, 4)
                    self.assertEqual(eng.mode.cycle_len, 12)
                self._run_cadence(eng, clock, want_stims=26)
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(cued)
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    self.assertEqual(hands_of(cued), {"left", "right"})
                    # One full trained cycle gives each hand exactly
                    # half its trials.
                    first_cycle = cued[:24]
                    n_left = sum(1 for l in first_cycle if l >= 4)
                    if len(first_cycle) == 24:
                        self.assertEqual(n_left, 12, first_cycle)
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_chords_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 10)
                eng.begin_chords_block()
                self._run_cadence(eng, clock, want_stims=10)
                records = eng.mode._records if eng.mode else []
                self.assertTrue(records, "no chord trials completed")
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                for lanes in eng._stim_record:
                    # Every chord sits within ONE hand: cross-talk is
                    # a within-hand quantity.
                    self.assertLessEqual(len(hands_of(lanes)), 1, lanes)
                if hand_mode == "both":
                    by_hand = {"left": 0, "right": 0}
                    for r in records:
                        by_hand[r["hand"]] += 1
                    self.assertTrue(by_hand["left"] > 0
                                    and by_hand["right"] > 0, by_hand)
                    # Probe bag and chord bag each keep the hands
                    # within one of each other.
                    self.assertLessEqual(
                        abs(by_hand["left"] - by_hand["right"]), 2,
                        by_hand)
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_syllables_matrix(self) -> None:
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 6)
                eng.cfg.data["syllables"]["speak_words"] = False
                eng.cfg.data["syllables"]["level"] = 2
                eng.begin_syllables_block()
                mode = eng.mode

                def respond(clock, mode=mode, hand_mode=hand_mode):
                    # Tap back the word during respond, alternating
                    # hands in bilateral play: either hand's finger
                    # must satisfy its position.
                    if mode.phase != "respond" or mode.active is None:
                        return
                    if len(mode.taps) >= mode.n_expected:
                        return
                    pos = len(mode.taps)
                    hands = list(mode.hands.items())
                    hand, lanes = hands[pos % len(hands)]
                    mode.queue_press(
                        _press(lanes[pos], clock.t, hand=hand))

                drive(eng, clock, responder=respond, step_s=0.05,
                      stop=lambda: (len(mode._records) >= 4
                                    or eng.trial_logger is None))
                self.assertGreaterEqual(len(mode._records), 4,
                                        "too few words completed")
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    # The model's buzzes divide between the hands.
                    self.assertEqual(hands_of(cued), {"left", "right"})
                    # Mixed-hand tapping is never wrong: position is
                    # what is checked, not the hand.
                    self.assertTrue(
                        any(r.correct for r in mode._records),
                        [r.error for r in mode._records])
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_rhythm_matrix(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        for hand_mode in ("left", "right", "both"):
            with self.subTest(hand=hand_mode), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = self._matrix_engine(hand_mode, td, 16)
                bm = procedural_beatmap(
                    bpm=120, beats=16, difficulty="hard",
                    num_lanes=eng.total_lanes)
                eng.begin_rhythm_block(bm)
                self._run_cadence(eng, clock, want_stims=12)
                cued = [l for lanes in eng._stim_record for l in lanes]
                self.assertTrue(cued, "no notes fired")
                self.assertTrue(
                    set(cued) <= self._expected_lanes(hand_mode), cued)
                if hand_mode == "both":
                    self.assertEqual(hands_of(cued), {"left", "right"})
                self._assert_boards_match_lanes(eng, hand_mode)
                self._assert_block_end_clean(eng)

    def test_mirror_forces_both_and_pairs_the_hands(self) -> None:
        # Mirror stays bilateral-only: starting it from a unilateral
        # config must flip the session to both hands.
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = self._matrix_engine("right", td, 6)
            eng.begin_mirror_block()
            self.assertEqual(eng.hand_mode, "both")
            self._run_cadence(eng, clock, want_stims=6)
            self.assertTrue(eng._stim_record)
            for lanes in eng._stim_record:
                # Every stim is the same finger on both hands.
                self.assertEqual(len(lanes), 2, lanes)
                self.assertEqual(lanes[0] % 4, lanes[1] % 4, lanes)
                self.assertEqual(hands_of(lanes), {"left", "right"})
            self._assert_block_end_clean(eng)


# ---- calibration survives detector rebuilds --------------------------------
class CalibrationSurvivesRebuildTests(unittest.TestCase):
    """The setup screen's hand pick and mirror's force-both both call
    _build_detectors, and a rebuilt detector comes back on config
    defaults. The measured per-hand thresholds must be reapplied by the
    rebuild itself, not by whichever caller remembers to; before the
    7 Aug fix every block started through the setup screen ran on
    defaults while the metadata still recorded the calibration."""

    def _profile(self, hand: str, gap: float):
        from rehab.hardware.calibration_profile import CalibrationProfile
        return CalibrationProfile(
            hand=hand,
            empty=[10.0] * 4, empty_noise=[2.0] * 4,
            resting=[50.0] * 4,
            press=[50.0 + gap] * 4,
            press_all=[50.0 + gap] * 4,
        )

    def test_setup_screen_hand_pick_keeps_both_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            right = self._profile("right", 300.0)
            left = self._profile("left", 500.0)
            eng.apply_calibration(right)
            eng.apply_calibration(left)
            eng.cfg.data["game"]["mode"] = "reaction"
            eng._screens["setup"]._pick("both")
            self.assertEqual(list(eng.detectors["right"].cal.on_delta),
                             right.on_delta())
            self.assertEqual(list(eng.detectors["left"].cal.on_delta),
                             left.on_delta())
            eng.finish_block()

    def test_mirror_force_both_keeps_both_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("right", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            right = self._profile("right", 300.0)
            eng.apply_calibration(right)
            eng.calibration_profiles["left"] = self._profile("left", 500.0)
            eng.begin_mirror_block()
            self.assertEqual(list(eng.detectors["right"].cal.on_delta),
                             right.on_delta())
            self.assertEqual(list(eng.detectors["left"].cal.on_delta),
                             self._profile("left", 500.0).on_delta())
            eng.finish_block()

    def test_stored_left_profile_stays_off_the_right_detector(self) -> None:
        # A unilateral RIGHT rebuild drops the left detector. The left
        # hand's stored profile must then be skipped, not fall through
        # apply_calibration's every-detector fallback onto the right
        # hand's differently-placed sensors.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("right", td)
            right = self._profile("right", 300.0)
            eng.apply_calibration(right)
            eng.calibration_profiles["left"] = self._profile("left", 500.0)
            eng._build_detectors()
            self.assertEqual(list(eng.detectors["right"].cal.on_delta),
                             right.on_delta())


# ---- the single 3-second prep ----------------------------------------------
class PrepCountdownTests(unittest.TestCase):
    """One prep, three seconds, every mode: from pressing start the
    player gets a single GET READY countdown and then the game
    begins."""

    def test_shipped_default_is_three_seconds(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        self.assertEqual(float(cfg.get("game.start_countdown_s")), 3.0)

    def test_every_gameplay_mode_gets_the_same_three_seconds(self) -> None:
        cases = {
            "classic": lambda e: e.begin_classic_block(),
            "reaction": lambda e: e.begin_reaction_block(),
            "adaptive": lambda e: e.begin_adaptive_block(),
            "pattern": lambda e: e.begin_pattern_block(),
            "chords": lambda e: e.begin_chords_block(),
        }
        for name, begin in cases.items():
            with self.subTest(mode=name), \
                    tempfile.TemporaryDirectory() as td, \
                    patched_clock() as clock:
                eng = make_engine("right", td)
                begin(eng)
                gp = eng._screens["gameplay"]
                self.assertAlmostEqual(
                    gp._countdown_until - clock.t, 3.0, places=3,
                    msg=f"{name} did not get the single 3 s prep")
                eng.finish_block()

    def test_syllables_screen_gets_the_same_prep(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = make_engine("right", td)
            eng.cfg.data["syllables"]["speak_words"] = False
            eng.begin_syllables_block()
            sc = eng._screens["syllables"]
            self.assertAlmostEqual(sc._countdown_until - clock.t, 3.0,
                                   places=3)
            eng.finish_block()

    def test_rhythm_reads_the_same_config_key(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("right", td)
            bm = procedural_beatmap(bpm=120, beats=8, num_lanes=4)
            eng.begin_rhythm_block(bm)
            self.assertEqual(eng.mode._countdown_s, 3.0)
            eng.finish_block()

    def test_countdown_holds_the_mode_and_runs_chords_prep(self) -> None:
        # The gameplay screen must hold the mode back through the
        # countdown while letting the chords baseline-quiet clock
        # accumulate, so the first chord fires the moment play starts
        # instead of stacking a second wait.
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = make_engine("right", td)
            eng.begin_chords_block()
            gp = eng._screens["gameplay"]
            for _ in range(40):        # 2 s of countdown
                clock.t += 0.05
                gp.update(0.05)
            self.assertEqual(eng._stim_record, [],
                             "a stim fired during GET READY")
            self.assertIsNotNone(eng.mode._quiet_since,
                                 "the quiet clock did not run in prep")
            # Countdown over: the settled hand fires without waiting
            # another baseline-quiet period.
            clock.t = gp._countdown_until + 0.05
            gp.update(0.05)
            self.assertTrue(eng._stim_record,
                            "first chord did not fire at prep end")
            eng.finish_block()

    def test_test_mode_still_trims_the_prep(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = make_engine("right", td)
            eng.cfg.data["game"]["test_mode_enabled"] = True
            eng.begin_classic_block()
            gp = eng._screens["gameplay"]
            self.assertLessEqual(gp._countdown_until - clock.t, 1.5 + 1e-6)
            eng.finish_block()


# ---- bimanual pattern material ---------------------------------------------
class Pattern8SequenceTests(unittest.TestCase):
    """The 24-item bimanual cycle must satisfy the properties the
    measurement depends on, and must not disturb the unilateral
    material existing participants already trained on."""

    def _props(self, seq: list[int]) -> None:
        self.assertEqual(len(seq), 24)
        for lane in range(8):
            self.assertEqual(seq.count(lane), 3,
                             f"lane {lane} unbalanced in {seq}")
        pairs = [(seq[i], seq[(i + 1) % 24]) for i in range(24)]
        for a, b in pairs:
            self.assertNotEqual(a, b, f"immediate repeat in {seq}")
        self.assertEqual(len(set(pairs)), 24,
                         f"a transition repeats in {seq}")

    def test_trained_cycle_properties_across_seeds(self) -> None:
        from rehab.game.modes.pattern import build_sequences
        for seed in (1, 7, 1234, 99991):
            trained, pool = build_sequences(seed, n_lanes=8)
            with self.subTest(seed=seed):
                self._props(trained)
                for p in pool:
                    self._props(p)

    def test_each_hand_gets_exactly_half_of_every_cycle(self) -> None:
        from rehab.game.modes.pattern import build_sequences
        for seed in (1, 7, 1234):
            trained, _ = build_sequences(seed, n_lanes=8)
            self.assertEqual(sum(1 for l in trained if l >= 4), 12)

    def test_probes_share_no_second_order_structure(self) -> None:
        from rehab.game.modes.pattern import build_sequences, shared_triplets
        for seed in (1, 7, 1234):
            trained, pool = build_sequences(seed, n_lanes=8)
            self.assertGreaterEqual(len(pool), 2)
            for p in pool:
                self.assertLessEqual(shared_triplets(p, trained), 2,
                                     "probe leaks trained structure")

    def test_material_is_stable_for_a_participant(self) -> None:
        from rehab.game.modes.pattern import build_sequences
        a = build_sequences(4242, n_lanes=8)
        b = build_sequences(4242, n_lanes=8)
        self.assertEqual(a, b)

    def test_unilateral_material_is_untouched_by_the_bimanual_path(self) -> None:
        # A participant's 12-item SOC must be byte-identical to what
        # the generator always produced, or their cross-session curves
        # break the day the app updates.
        import random
        from rehab.game.modes.pattern import build_sequences, generate_soc
        for seed in (1, 7, 1234):
            trained, _ = build_sequences(seed, n_lanes=4)
            legacy = generate_soc(random.Random(seed))
            self.assertEqual(trained, legacy)

    def test_bimanual_take_length_stays_in_the_envelope(self) -> None:
        # 3 cycles x 24 = 72 trials per take, inside the 50 to 100
        # trial envelope the research brief works to.
        with tempfile.TemporaryDirectory() as td:
            eng = make_engine("both", td)
            eng.begin_pattern_block()
            seq_segs = [s for s in eng.mode.segments if s.kind == "seq"]
            self.assertTrue(seq_segs)
            for s in seq_segs:
                self.assertEqual(len(s.fingers), 72)
            eng.finish_block()


if __name__ == "__main__":
    unittest.main()
