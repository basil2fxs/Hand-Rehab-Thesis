"""Tests for bilateral hand support (Thread 3)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class BilateralDetectorTests(unittest.TestCase):
    def test_press_event_carries_hand_label(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4), hand="left")
        captured = []
        det.on_press = lambda ev: captured.append(ev)
        # First feed idle samples to establish baseline near 50.
        t0 = 100.0
        for i in range(40):
            det.feed(t0 + i * 0.005, (50, 50, 50, 50))
        # Then press lane 0 well above the threshold for at least 30 ms.
        for i in range(40):
            det.feed(t0 + 0.2 + i * 0.005, (600, 50, 50, 50))
        self.assertTrue(any(ev.hand == "left" and ev.lane == 0
                            for ev in captured),
                         f"no left-hand press captured. events={captured}")

    def test_per_hand_routing_via_engine_split(self) -> None:
        # Simulates engine._feed_detectors for the both-hand case.
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        right = FSRDetector(Calibration(num_sensors=4), hand="right")
        left = FSRDetector(Calibration(num_sensors=4), hand="left")
        events = []
        right.on_press = lambda ev: events.append(("right", ev.lane))
        left.on_press = lambda ev: events.append(("left", ev.lane))
        t0 = 50.0
        # Settle baselines on idle first.
        for i in range(40):
            right.feed(t0 + i * 0.005, (50, 50, 50, 50))
            left.feed(t0 + i * 0.005, (50, 50, 50, 50))
        # Now press lane 1 on the LEFT hand for long enough to trip the detector.
        for i in range(40):
            right.feed(t0 + 0.2 + i * 0.005, (50, 50, 50, 50))
            left.feed(t0 + 0.2 + i * 0.005, (50, 600, 50, 50))
        self.assertTrue(any(e == ("left", 1) for e in events),
                         f"left lane 1 press not detected. events={events}")
        self.assertFalse(any(side == "right" for side, _ in events))


class BilateralCSVSchemaTests(unittest.TestCase):
    def test_raw_csv_columns_include_hand_and_fsr5_to_8(self) -> None:
        from rehab.data.logger import RAW_COLUMNS
        self.assertIn("hand", RAW_COLUMNS)
        for col in ("fsr5", "fsr6", "fsr7", "fsr8"):
            self.assertIn(col, RAW_COLUMNS)

    def test_trial_csv_columns_include_hand(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("hand", TRIAL_COLUMNS)


class BilateralEightLaneTests(unittest.TestCase):
    """Bilateral mode should run as an 8-finger game: right hand uses lanes
    0-3, left hand uses lanes 4-7, and the modes generate sequences in 0-7."""

    def test_adaptive_engine_accepts_eight_lanes(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine(num_lanes=8)
        # Should be able to record events on any of the 8 lanes.
        for lane in range(8):
            eng.record(lane, hit=True, rt_ms=300.0)
        self.assertEqual(sum(s.n_trials for s in eng.state), 8)

    def test_adaptive_sequence_uses_eight_lanes(self) -> None:
        import random
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine(num_lanes=8)
        seq = eng.generate_sequence(200, rng=random.Random(0))
        # All 8 lanes should appear at least once over a long sequence.
        self.assertEqual(set(seq), set(range(8)))

    def test_procedural_beatmap_uses_eight_lanes_when_bilateral(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=32, difficulty="hard",
                                 num_lanes=8)
        used = {n.lane for n in bm.notes}
        # The default bilateral pattern alternates right and left, so all
        # 8 lanes should be reachable.
        self.assertTrue(used.issubset(set(range(8))))
        self.assertGreater(len(used), 4,
                            "bilateral beatmap should touch lanes on both hands")

    def test_unilateral_beatmap_stays_under_four_lanes(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=16, difficulty="hard")
        used = {n.lane for n in bm.notes}
        self.assertTrue(used.issubset({0, 1, 2, 3}))


class BilateralKeyboardMapTests(unittest.TestCase):
    """Config exposes a separate 8-key keymap that modes consult when the
    user picked both hands."""

    def test_bilateral_keymap_covers_eight_lanes(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        km = cfg.get("game.keyboard_map_bilateral", {})
        self.assertEqual(len(km), 8,
                          f"expected 8 keys in keyboard_map_bilateral, got {km}")
        # Every key maps to a unique lane in 0..7.
        lanes = sorted(km.values())
        self.assertEqual(lanes, list(range(8)))


class UnilateralKeymapNaturalTests(unittest.TestCase):
    """Unilateral keymaps must put the patient's index finger on lane 0 and
    little finger on lane 3, regardless of which hand they're using. Right
    hand uses J K L ;, left hand uses F D S A."""

    def test_right_hand_keymap_is_jkl_semicolon(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        km = cfg.get("game.keyboard_map", {})
        # j = index = lane 0; ; = little = lane 3.
        self.assertEqual(km.get("j"), 0)
        self.assertEqual(km.get("k"), 1)
        self.assertEqual(km.get("l"), 2)
        self.assertEqual(km.get("semicolon"), 3)
        # Four keys, all lanes covered.
        self.assertEqual(sorted(km.values()), [0, 1, 2, 3])

    def test_left_hand_keymap_is_fdsa(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        km = cfg.get("game.keyboard_map_left", {})
        # f = index = lane 0; a = little = lane 3.
        self.assertEqual(km.get("f"), 0)
        self.assertEqual(km.get("d"), 1)
        self.assertEqual(km.get("s"), 2)
        self.assertEqual(km.get("a"), 3)
        self.assertEqual(sorted(km.values()), [0, 1, 2, 3])

    def test_keymap_for_hand_picks_correct_config_key(self) -> None:
        from rehab.game.modes._keys import keymap_for_hand
        self.assertEqual(keymap_for_hand("right"),
                          "game.keyboard_map")
        self.assertEqual(keymap_for_hand("left"),
                          "game.keyboard_map_left")
        self.assertEqual(keymap_for_hand("both"),
                          "game.keyboard_map_bilateral")
        # Anything unexpected falls through to the right-hand map so the
        # game stays usable even if the config is weird.
        self.assertEqual(keymap_for_hand("nonsense"),
                          "game.keyboard_map")


class KeyResolverTests(unittest.TestCase):
    """pygame names letters lowercase (K_a) and special chars uppercase
    (K_SEMICOLON). The mode keymaps need to work for both."""

    def test_lowercase_letter_resolves(self) -> None:
        import pygame
        from rehab.game.modes._keys import resolve_key
        pygame.init()
        try:
            self.assertEqual(resolve_key("j"), pygame.K_j)
            self.assertEqual(resolve_key("a"), pygame.K_a)
        finally:
            pygame.quit()

    def test_semicolon_resolves(self) -> None:
        import pygame
        from rehab.game.modes._keys import resolve_key
        pygame.init()
        try:
            # The bug: old code used K_semicolon (lowercase) which doesn't
            # exist in pygame. resolve_key now falls back to K_SEMICOLON.
            self.assertEqual(resolve_key("semicolon"), pygame.K_SEMICOLON)
        finally:
            pygame.quit()

    def test_unknown_key_returns_none(self) -> None:
        from rehab.game.modes._keys import resolve_key
        self.assertIsNone(resolve_key("not_a_real_key"))
        self.assertIsNone(resolve_key(""))


class BilateralLaneLayoutTests(unittest.TestCase):
    """In both-hand mode the screen mirrors the patient: left hand on the
    LEFT side, right hand on the RIGHT side, with each hand's little finger
    on the outer edge (matches a/s/d/f and j/k/l/; on a keyboard)."""

    def _make_engine(self):
        # Build a minimal engine without invoking pygame. We just need
        # hand_mode, theme, layout, and a stub config.
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["bilateral"]["hand"] = "both"
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        return eng

    def test_gameplay_lanes_indexed_by_lane_number(self) -> None:
        # `self.lanes[i].lane == i` must hold so the FSR pump and falling
        # notes can keep looking up lanes by id.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine()
            sc = GameplayScreen(eng)
            self.assertEqual(len(sc.lanes), 8)
            for i, ls in enumerate(sc.lanes):
                self.assertEqual(ls.lane, i,
                    f"self.lanes[{i}].lane should be {i}, got {ls.lane}")
        finally:
            pygame.quit()

    def test_gameplay_left_hand_lanes_are_left_of_centre(self) -> None:
        # Lanes 4..7 (left hand) should sit on the LEFT half of the screen.
        # Lanes 0..3 (right hand) on the RIGHT half.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine()
            sc = GameplayScreen(eng)
            mid = eng.layout.width / 2.0
            for lane in (4, 5, 6, 7):
                ls = sc.lanes[lane]
                self.assertLess(ls.rect.centerx, mid,
                    f"left-hand lane {lane} should be left of screen midline")
            for lane in (0, 1, 2, 3):
                ls = sc.lanes[lane]
                self.assertGreater(ls.rect.centerx, mid,
                    f"right-hand lane {lane} should be right of screen midline")
        finally:
            pygame.quit()

    def test_gameplay_left_little_is_leftmost_and_left_index_nearest_centre(self) -> None:
        # Within the left-hand block, lane 7 (little) should be furthest
        # left and lane 4 (index) closest to the centre. Mirrors a s d f.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine()
            sc = GameplayScreen(eng)
            xs = [sc.lanes[lane].rect.centerx for lane in (7, 6, 5, 4)]
            # Reading the lanes in order little -> ring -> middle -> index
            # the x-coordinates should be strictly increasing.
            self.assertEqual(xs, sorted(xs))
        finally:
            pygame.quit()

    def test_gameplay_right_index_nearest_centre_right_little_outer(self) -> None:
        # Within the right-hand block, lane 0 (index) closest to centre,
        # lane 3 (little) on the outer right edge. Mirrors j k l ;.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine()
            sc = GameplayScreen(eng)
            xs = [sc.lanes[lane].rect.centerx for lane in (0, 1, 2, 3)]
            self.assertEqual(xs, sorted(xs))
        finally:
            pygame.quit()

    def test_rhythm_lanes_have_same_left_right_layout(self) -> None:
        # Same invariants for the rhythm screen so falling notes land on
        # the correct side too.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import RhythmScreen
            eng = self._make_engine()
            sc = RhythmScreen(eng)
            mid = eng.layout.width / 2.0
            self.assertEqual(len(sc.lanes), 8)
            for lane in (4, 5, 6, 7):
                self.assertLess(sc.lanes[lane].rect.centerx, mid)
            for lane in (0, 1, 2, 3):
                self.assertGreater(sc.lanes[lane].rect.centerx, mid)
            # And lane id matches index for the falling-note lookup.
            for i, ls in enumerate(sc.lanes):
                self.assertEqual(ls.lane, i)
        finally:
            pygame.quit()


class UnilateralLeftLayoutMirrorTests(unittest.TestCase):
    """Left-hand unilateral must mirror the keyboard too: lane 3 (little, on
    key `a`) leftmost on screen, lane 0 (index, on key `f`) closest to centre."""

    def _make_engine(self, hand: str):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["bilateral"]["hand"] = hand
        cfg.data["ui"]["resolution"] = [1280, 800]
        return GameEngine(cfg, KeyboardOnlySource())

    def test_left_unilateral_lane_3_is_leftmost(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine("left")
            sc = GameplayScreen(eng)
            # Reading lanes in physical key order a s d f -> lanes 3 2 1 0,
            # x-coords should increase strictly.
            xs = [sc.lanes[lane].rect.centerx for lane in (3, 2, 1, 0)]
            self.assertEqual(xs, sorted(xs))
        finally:
            pygame.quit()

    def test_right_unilateral_lane_0_is_leftmost(self) -> None:
        # For right-hand unilateral the keys are j k l ; -> lanes 0 1 2 3
        # so the natural visual order has lane 0 leftmost.
        import pygame
        pygame.init()
        try:
            from rehab.ui.screens import GameplayScreen
            eng = self._make_engine("right")
            sc = GameplayScreen(eng)
            xs = [sc.lanes[lane].rect.centerx for lane in (0, 1, 2, 3)]
            self.assertEqual(xs, sorted(xs))
        finally:
            pygame.quit()


class GamePaceDefaultsTests(unittest.TestCase):
    """Classic mode defaults should give the patient enough time to react,
    and the adaptive engine should be able to drop to ~20 BPM (3 s gap)
    for severely impaired patients."""

    def test_classic_default_trigger_interval_is_slow_enough(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        # 0.6 s was too fast for a rehab session. Anything under 1.0 s is
        # uncomfortable for the patient.
        self.assertGreaterEqual(cfg.get("game.trigger_interval_s"), 1.0)

    def test_adaptive_can_drop_to_super_slow(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        # 20 BPM = 3 s per stim. Lower than that gets unwieldy.
        self.assertLessEqual(cfg.get("adaptive.bpm_min"), 20)


class LaneColourReservationTests(unittest.TestCase):
    """Themes must not use green or red as default lane fills since those
    colours are reserved for hit/miss flash feedback."""

    HIT_GREEN = (34, 197, 94)
    MISS_RED = (239, 68, 68)

    def _too_close(self, c, target, tol=40) -> bool:
        return all(abs(c[i] - target[i]) <= tol for i in range(3))

    def test_clinical_lane_palettes_avoid_green_and_red(self) -> None:
        from rehab.ui.theme import CLINICAL
        for c in CLINICAL.lane_idle + CLINICAL.lane_active:
            self.assertFalse(self._too_close(c, self.HIT_GREEN),
                              f"{c} too close to hit green")
            self.assertFalse(self._too_close(c, self.MISS_RED),
                              f"{c} too close to miss red")

    def test_dark_lane_palettes_avoid_green_and_red(self) -> None:
        from rehab.ui.theme import DARK
        for c in DARK.lane_idle + DARK.lane_active:
            self.assertFalse(self._too_close(c, self.HIT_GREEN),
                              f"{c} too close to hit green")
            self.assertFalse(self._too_close(c, self.MISS_RED),
                              f"{c} too close to miss red")

    def test_left_hand_badge_is_not_red(self) -> None:
        # The left-hand border + badge mustn't be red either or a default
        # left-hand tile would look "missed".
        from rehab.ui.widgets import LaneStrip
        c = LaneStrip.HAND_BADGE["left"]
        self.assertFalse(self._too_close(c, self.MISS_RED),
                          f"left badge {c} too close to miss red")


if __name__ == "__main__":
    unittest.main()
