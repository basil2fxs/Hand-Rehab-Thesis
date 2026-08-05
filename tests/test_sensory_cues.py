"""The four sensory-cue switches, and the screen reveal beside them.

Two moments matter to the patient. BEFORE the press something has to
say which finger to move; AFTER a correct press something can confirm
it landed. Each moment has a buzzer channel and a sound channel:

    cue.buzz_before   motor on the target finger, when the stim fires
    cue.sound_before  cue tone, when the stim fires
    cue.sound_after   confirmation chime, correct press only
    cue.buzz_after    motor on the pressed finger, correct press only

All sixteen combinations have to work, in classic, adaptive, rhythm
and mirror. cue.show_target is not one of the four: it decides whether
the gameplay screen highlights the finger, and turning it off with
buzz_before on is the condition that isolates the tactile channel.

What these tests pin down:
  - each switch alone does its own channel and nothing else
  - all four on, and all four off
  - the after-press pair never fires on a timeout or a wrong finger
  - every mode routes through the same two entry points
  - mirror confirms on BOTH pressed fingers
  - the per-trial cue_flags code separates all sixteen states
  - an override file from the old build migrates onto the new keys
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


ALL_ON = dict(buzz_before=True, sound_before=True,
              sound_after=True, buzz_after=True)
ALL_OFF = dict(buzz_before=False, sound_before=False,
               sound_after=False, buzz_after=False)


def _only(name: str) -> dict:
    """Every switch off except `name`."""
    d = dict(ALL_OFF)
    d[name] = True
    return d


class _Audio:
    """Records which sounds the engine asked for. Only the four methods
    the cue paths touch; everything else on the real audio engine is
    irrelevant here."""

    def __init__(self) -> None:
        self.stim: list[int] = []
        self.hits = 0
        self.misses = 0

    def play_stim(self, lane):
        self.stim.append(lane)

    def play_hit(self, combo=0):
        self.hits += 1

    def play_miss(self):
        self.misses += 1

    def set_trial_gain(self, g):
        pass


class _Lane:
    """Stand-in for a LaneStrip: only what on_stim_multi touches."""

    def __init__(self, lane):
        self.lane = lane
        self.active = False
        self.timing_armed = False

    def arm_timing(self, *_):
        self.timing_armed = True

    def clear_timing(self):
        self.timing_armed = False


def _engine(show_target=True, cue_ms=250, **cues):
    """A GameEngine built through __new__ with just the state the cue
    paths read. Real construction needs pygame, a serial source and a
    display, none of which say anything about cue routing."""
    from rehab.game.engine import GameEngine
    e = GameEngine.__new__(GameEngine)
    settings = dict(ALL_ON)
    settings.update(cues)
    values = {f"cue.{k}": v for k, v in settings.items()}
    values["cue.show_target"] = show_target
    values.update({
        "motor.cue_ms": cue_ms,
        "motor.pulse_interval_ms": 120,
        "game.timeout_s": 1.0,
        "fsr.num_sensors_per_hand": 4,
        "scoring.wrong_press_penalty": 0,
    })
    e.cfg = MagicMock()
    e.cfg.get = MagicMock(side_effect=lambda k, d=None: values.get(k, d))
    sent: list[str] = []
    src = MagicMock()
    src.send_command = lambda c: (sent.append(c) or True)
    e.source = src
    e._sent = sent
    gp = MagicMock()
    gp.lanes = [_Lane(i) for i in range(8)]
    e._screens = {"gameplay": gp}
    e._lanes = gp.lanes
    e.hand_mode = "right"
    e.audio = _Audio()
    e.raw_logger = None
    e.mode = None
    e.detectors = {}
    # Trial-close bookkeeping log_trial / log_rhythm_hit walk through.
    e.score = 0
    e.hits = 0
    e.misses = 0
    e.hit_streak = 0
    e.miss_streak = 0
    e._streak_fired = set()
    e._streak_thresholds = ()
    e._block_rt_sum = 0.0
    e._block_rt_count = 0
    e._block_bpm_min = None
    e._block_bpm_max = None
    e._block_wrong_press_trials = 0
    e._block_rhythm_spurious_presses = 0
    e._block_idle_presses = 0
    e._block_peak_streak = 0
    e._last_gained = 0
    e.current_block = "classic"
    e.trial_logger = None
    e.session_paths = None
    e.session = MagicMock()
    e.session.participant = "T"
    e.session.age = ""
    e.theme = MagicMock()
    e._per_lane_rts = {}
    e._per_lane_misses = {}
    e._per_lane_wrong = {}
    e._trial_context = MagicMock(return_value={})
    e._ensure_metric_state()
    return e


def _stims(e) -> list[str]:
    return [c for c in e._sent if c.startswith("STIM")]


def _trial(lane: int, incorrect=()):
    from rehab.game.modes.classic import PendingTrial
    return PendingTrial(trial_id=1, lane=lane, stim_t_perf=0.0,
                         keys_pressed=[lane],
                         incorrect_presses=list(incorrect))


def _result(label: str, rt_ms: float | None = 200.0):
    from rehab.game.scoring import TrialResult
    return TrialResult(label=label, points=0, rt_ms=rt_ms)


def _note(lane: int, index: int = 0):
    from rehab.audio.beatmap import Note
    sched = MagicMock()
    sched.note = Note(t=1.0, lane=lane)
    sched.index = index
    return sched


class OneSwitchAtATimeTests(unittest.TestCase):
    """Each switch on its own drives its own channel and leaves the
    other three silent. Together these four cover the single-toggle
    half of the sixteen combinations."""

    def test_buzz_before_alone(self) -> None:
        e = _engine(**_only("buzz_before"))
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertIn("STIM:3", _stims(e))
        self.assertEqual(e.audio.stim, [], "cue tone played with sound off")
        e._sent.clear()
        e.log_trial(_trial(2), _result("Great"), now=0.0)
        self.assertEqual(_stims(e), [], "buzzed after a press with it off")
        self.assertEqual(e.audio.hits, 0)

    def test_sound_before_alone(self) -> None:
        e = _engine(**_only("sound_before"))
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertEqual(e.audio.stim, [2])
        self.assertEqual(_stims(e), [], "motor buzzed with the buzzer off")
        e.log_trial(_trial(2), _result("Great"), now=0.0)
        self.assertEqual(e.audio.hits, 0)
        self.assertEqual(_stims(e), [])

    def test_sound_after_alone(self) -> None:
        e = _engine(**_only("sound_after"))
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.stim, [])
        e.log_trial(_trial(1), _result("Great"), now=0.0)
        self.assertEqual(e.audio.hits, 1)
        self.assertEqual(_stims(e), [], "buzzed after a press with it off")

    def test_buzz_after_alone(self) -> None:
        e = _engine(**_only("buzz_after"))
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertEqual(_stims(e), [], "buzzed the cue with it off")
        e.log_trial(_trial(1), _result("Great"), now=0.0)
        self.assertIn("STIM:2", _stims(e))
        self.assertEqual(e.audio.hits, 0, "chimed with the sound off")


class AllOnAllOffTests(unittest.TestCase):
    def test_all_four_on(self) -> None:
        e = _engine(**ALL_ON)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertIn("STIM:1", _stims(e))
        self.assertEqual(e.audio.stim, [0])
        e._sent.clear()
        e.log_trial(_trial(0), _result("Great"), now=0.0)
        self.assertIn("STIM:1", _stims(e))
        self.assertEqual(e.audio.hits, 1)

    def test_all_four_off_leaves_only_the_screen(self) -> None:
        e = _engine(**ALL_OFF)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.stim, [])
        # The screen is not one of the four, so it still names the
        # finger and the timing bar still runs.
        self.assertTrue(e._lanes[0].active)
        self.assertTrue(e._lanes[0].timing_armed)
        e.log_trial(_trial(0), _result("Great"), now=0.0)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.hits, 0)
        self.assertEqual(e.audio.misses, 0)

    def test_all_off_records_a_delivered_flag_of_nothing(self) -> None:
        # With no buzzer cue there is no serial write to succeed or
        # fail, so the trial row must not claim a delivery either way.
        e = _engine(**ALL_OFF)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertIsNone(e._last_stim_delivered)


class AfterPressOnlyOnACorrectPressTests(unittest.TestCase):
    """The two after-press channels confirm a CORRECT press. A timeout
    or a fumbled trial has to stay silent, otherwise the confirmation
    stops meaning anything."""

    def test_timeout_gets_no_after_cue(self) -> None:
        e = _engine(**ALL_ON)
        e.log_trial(_trial(0), _result("Miss", rt_ms=None), now=0.0)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.hits, 0)

    def test_wrong_finger_gets_no_after_cue(self) -> None:
        # Classic downgrades a trial with any wrong-finger press to a
        # Miss before logging it, so the cue never sees it as correct.
        # Driving the mode rather than hand-building the outcome is the
        # point: it checks the downgrade and the cue gate agree.
        from rehab.game.modes.classic import ClassicMode
        from rehab.game.scoring import ScoreConfig
        from rehab.hardware.fsr_detector import PressEvent
        e = _engine(**ALL_ON)
        mode = ClassicMode(engine=e, pattern=[0], repeat_count=1,
                            trigger_interval_s=0.5, timeout_s=1.0,
                            early_window_s=0.1, score_cfg=ScoreConfig())
        mode._fire(now=0.0)
        e._sent.clear()
        e.audio.hits = 0
        mode._handle_press(
            PressEvent(lane=2, t_perf=0.10, value=0, baseline=0.0,
                        hand="right"), now=0.10)
        mode._handle_press(
            PressEvent(lane=0, t_perf=0.20, value=0, baseline=0.0,
                        hand="right"), now=0.20)
        self.assertEqual(_stims(e), [],
                          "buzzed a confirmation on a fumbled trial")
        self.assertEqual(e.audio.hits, 0)

    def test_streak_break_thunk_follows_sound_after(self) -> None:
        # The low thunk on a streak-breaking miss is still something
        # the patient hears after touching a sensor, so the post-press
        # sound switch owns it too.
        for flag, expected in ((True, 1), (False, 0)):
            with self.subTest(sound_after=flag):
                e = _engine(sound_after=flag)
                e.hit_streak = 4
                e.log_trial(_trial(0), _result("Miss", rt_ms=None), now=0.0)
                self.assertEqual(e.audio.misses, expected)

    def test_rhythm_no_press_miss_gets_nothing(self) -> None:
        e = _engine(**ALL_ON)
        e.current_block = "rhythm"
        e.log_rhythm_hit(_note(1), 0.0, "Miss", 0, now=0.0,
                          was_pressed=False)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.hits, 0)

    def test_rhythm_wrong_lane_press_gets_no_confirmation(self) -> None:
        e = _engine(**ALL_ON)
        e.current_block = "rhythm"
        e.log_rhythm_unmatched(lane=2, now=0.0)
        self.assertEqual(_stims(e), [],
                          "buzzed a confirmation for a note that was not there")


class EveryModeHonoursTheSwitchesTests(unittest.TestCase):
    """classic, adaptive and mirror close a trial through log_trial;
    rhythm closes one through log_rhythm_hit. Both entry points have to
    read the same switches, or a block run in one mode would not be
    comparable with the same block run in another."""

    def test_cadence_modes_share_one_close_path(self) -> None:
        for block in ("classic", "adaptive", "mirror"):
            with self.subTest(block=block):
                e = _engine(**ALL_ON)
                e.current_block = block
                e.log_trial(_trial(1), _result("Great"), now=0.0)
                self.assertIn("STIM:2", _stims(e))
                self.assertEqual(e.audio.hits, 1)
                off = _engine(**ALL_OFF)
                off.current_block = block
                off.log_trial(_trial(1), _result("Great"), now=0.0)
                self.assertEqual(_stims(off), [])
                self.assertEqual(off.audio.hits, 0)

    def test_rhythm_hit_honours_both_after_switches(self) -> None:
        e = _engine(**ALL_ON)
        e.current_block = "rhythm"
        e.log_rhythm_hit(_note(2), 20.0, "Great", 6, now=0.0)
        self.assertIn("STIM:3", _stims(e))
        self.assertEqual(e.audio.hits, 1)

    def test_rhythm_hit_stays_silent_with_the_switches_off(self) -> None:
        e = _engine(**ALL_OFF)
        e.current_block = "rhythm"
        e.log_rhythm_hit(_note(2), 20.0, "Great", 6, now=0.0)
        self.assertEqual(_stims(e), [])
        self.assertEqual(e.audio.hits, 0)

    def test_rhythm_gets_the_pre_press_cue_too(self) -> None:
        # Rhythm used to be the one mode with no cue tone, which left
        # a switch that did nothing there. Now the beatmap's notes go
        # through on_stim like any other stimulus.
        e = _engine(**ALL_ON)
        e.current_block = "rhythm"
        e.on_stim(lane=3, trial_id=1, t_perf=0.0)
        self.assertEqual(e.audio.stim, [3])
        self.assertIn("STIM:4", _stims(e))

    def test_mirror_cues_both_hands_before_the_press(self) -> None:
        e = _engine(**ALL_ON)
        e.on_stim_multi([1, 5], trial_id=1, t_perf=0.0)
        self.assertIn("STIM:2", _stims(e))
        self.assertIn("STIM:6", _stims(e))
        # One tone for the pair, not two stacked on the same beat.
        self.assertEqual(e.audio.stim, [1])

    def test_mirror_confirms_on_both_pressed_fingers(self) -> None:
        e = _engine(**ALL_ON)
        e.log_trial(_trial(1), _result("Great"), now=0.0,
                     cue_lanes=[1, 5])
        self.assertIn("STIM:2", _stims(e))
        self.assertIn("STIM:6", _stims(e))

    def test_mirror_mode_passes_both_lanes(self) -> None:
        # The engine can only buzz both hands if the mode tells it
        # which two lanes were pressed, so pin that hand-off.
        from rehab.game.modes.mirror import MirrorMode
        from rehab.game.scoring import ScoreConfig
        from rehab.hardware.fsr_detector import PressEvent
        spy = MagicMock()
        spy.cfg = MagicMock()
        spy.cfg.get = MagicMock(return_value=0)
        spy.hand_mode = "both"
        mode = MirrorMode(engine=spy, pattern=[2], repeat_count=1,
                           trigger_interval_s=0.5, timeout_s=1.0,
                           early_window_s=0.1, score_cfg=ScoreConfig())
        mode._fire(now=0.0)
        mode._handle_press(
            PressEvent(lane=2, t_perf=0.10, value=0, baseline=0.0,
                        hand="both"), now=0.10)
        mode._handle_press(
            PressEvent(lane=6, t_perf=0.18, value=0, baseline=0.0,
                        hand="both"), now=0.18)
        spy.log_trial.assert_called_once()
        self.assertEqual(spy.log_trial.call_args.kwargs["cue_lanes"],
                          [2, 6])


class ScreenRevealTests(unittest.TestCase):
    """cue.show_target is separate from the four. With it off and the
    buzzer on, the finger has to be found by touch, which is the
    tactile-only condition the old vibration mode provided."""

    def test_on_by_default(self) -> None:
        e = _engine()
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[2].active)

    def test_off_hides_the_finger_but_still_buzzes(self) -> None:
        e = _engine(show_target=False, **_only("buzz_before"))
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertFalse(e._lanes[2].active,
                          "the screen gave the finger away")
        self.assertIn("STIM:3", _stims(e))

    def test_timing_bar_runs_even_when_the_tile_is_neutral(self) -> None:
        # How long is left is not a cue to which finger, so the patient
        # keeps it in every condition.
        e = _engine(show_target=False)
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[1].timing_armed)

    def test_nothing_at_all_is_allowed(self) -> None:
        # Screen off and buzzer off leaves nothing saying WHICH finger.
        # The software must still run the trial rather than refusing it.
        e = _engine(show_target=False, **ALL_OFF)
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertFalse(e._lanes[1].active)
        self.assertEqual(_stims(e), [])
        self.assertTrue(e._lanes[1].timing_armed)


class CueBuzzOverlapTests(unittest.TestCase):
    """A fast press lands while the cue buzz is still running. The
    confirmation has to read as a separate signal, not as the cue
    quietly carrying on."""

    def test_pending_cue_pulses_are_dropped_before_confirming(self) -> None:
        e = _engine(cue_ms=450, **ALL_ON)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertGreater(len(e._motor_queue), 0)
        queued_before = list(e._motor_queue)
        e.log_trial(_trial(0), _result("Great"), now=0.0)
        for lane, due in queued_before:
            self.assertNotIn((lane, due), e._motor_queue,
                              "a leftover cue pulse ran into the "
                              "confirmation buzz")

    def test_finish_block_lets_the_last_confirmation_finish(self) -> None:
        # finish_block runs in the same frame as the final trial's
        # result. An unconditional STOP there would make the last trial
        # the only one with no confirmation.
        e = _engine(cue_ms=450, **ALL_ON)
        e.log_trial(_trial(0), _result("Great"), now=0.0)
        e._sent.clear()
        e.stop_all_motors(allow_after_cue=True)
        self.assertNotIn("STOP", e._sent)
        self.assertIsNotNone(e._motor_stop_at)

    def test_pause_stops_the_motors_immediately(self) -> None:
        e = _engine(cue_ms=450, **ALL_ON)
        e.log_trial(_trial(0), _result("Great"), now=0.0)
        e._sent.clear()
        e.stop_all_motors()
        self.assertIn("STOP", e._sent)
        self.assertEqual(e._motor_queue, [])


class CueFlagsColumnTests(unittest.TestCase):
    """One column has to carry the whole four-way state so an analysis
    can split blocks by condition without the config snapshot."""

    def test_columns_registered(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("cue_flags", TRIAL_COLUMNS)
        self.assertIn("cue_target_shown", TRIAL_COLUMNS)
        self.assertNotIn("cue_mode", TRIAL_COLUMNS)

    def test_all_sixteen_states_are_distinct(self) -> None:
        from rehab.game.engine import CueSettings
        codes = set()
        for i in range(16):
            codes.add(CueSettings(
                buzz_before=bool(i & 1), sound_before=bool(i & 2),
                sound_after=bool(i & 4), buzz_after=bool(i & 8),
                show_target=True).code)
        self.assertEqual(len(codes), 16)

    def test_code_reads_as_before_slash_after(self) -> None:
        from rehab.game.engine import CueSettings
        self.assertEqual(CueSettings(True, True, True, True, True).code,
                          "BS/BS")
        self.assertEqual(CueSettings(False, False, False, False, True).code,
                          "--/--")
        self.assertEqual(CueSettings(True, False, False, False, True).code,
                          "B-/--")
        self.assertEqual(CueSettings(False, False, True, False, True).code,
                          "--/-S")

    def test_the_stim_stamps_the_trial(self) -> None:
        e = _engine(show_target=False, **_only("buzz_before"))
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertEqual(e._last_cue_code, "B-/--")
        self.assertFalse(e._last_target_shown)


class NoConfigAtAllTests(unittest.TestCase):
    def test_an_engine_without_a_config_actuates_nothing(self) -> None:
        # Only reachable from a __new__-built engine in a test that
        # never set a config up. Not knowing what the therapist chose
        # is a reason to drive nothing, not a reason to buzz.
        from rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        cues = e.cue_settings()
        self.assertFalse(cues.buzz_before)
        self.assertFalse(cues.sound_before)
        self.assertFalse(cues.sound_after)
        self.assertFalse(cues.buzz_after)
        self.assertTrue(cues.show_target)


class SensoryCuesMenuTests(unittest.TestCase):
    """The Settings menu is the only way a therapist reaches these, so
    its rows have to name the keys the engine actually reads."""

    def test_the_menu_covers_every_switch(self) -> None:
        from rehab.ui.screens import DiagnosticsScreen
        keys = [k for k, _l, _h in DiagnosticsScreen.CUE_ROWS if k is not None]
        self.assertEqual(sorted(keys), [
            "cue.buzz_after", "cue.buzz_before", "cue.show_target",
            "cue.sound_after", "cue.sound_before",
        ])

    def test_every_switch_explains_itself(self) -> None:
        from rehab.ui.screens import DiagnosticsScreen
        for key, label, help_text in DiagnosticsScreen.CUE_ROWS:
            if key is None:
                continue
            with self.subTest(key=key):
                self.assertTrue(label.strip())
                self.assertGreater(len(help_text), 30, key)

    def test_a_row_click_flips_that_row_and_stays_open(self) -> None:
        # Four switches are normally set as a group, so closing after
        # each one would mean four trips through the menu.
        import pygame
        from rehab.ui.widgets import ToggleMenu
        state = {"a": False, "b": True}
        flips: list[tuple[str, bool]] = []

        def toggle(k, v):
            state[k] = v
            flips.append((k, v))

        menu = ToggleMenu(pygame.Rect(0, 0, 200, 30),
                           [("a", "A", ""), ("b", "B", "")],
                           get_value=lambda k: state[k],
                           on_toggle=toggle,
                           theme=MagicMock(), layout=MagicMock())
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                   pos=(10, 15))
        self.assertTrue(menu.handle_event(down))
        self.assertTrue(menu.is_open)
        row = menu._row_rect(0)
        self.assertTrue(menu.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=row.center)))
        self.assertEqual(flips, [("a", True)])
        self.assertTrue(menu.is_open, "the menu closed after one switch")

    def test_a_click_off_the_menu_closes_it(self) -> None:
        import pygame
        from rehab.ui.widgets import ToggleMenu
        menu = ToggleMenu(pygame.Rect(0, 0, 200, 30),
                           [("a", "A", "")],
                           get_value=lambda k: False,
                           on_toggle=lambda k, v: None,
                           theme=MagicMock(), layout=MagicMock())
        menu.is_open = True
        menu.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(900, 700)))
        self.assertFalse(menu.is_open)


class ShippedDefaultsTests(unittest.TestCase):
    """Read default.yaml directly. Config.load() merges the local
    user_settings.yaml on top, and this is about what the software
    ships with, not what one machine is set to."""

    def _shipped(self) -> dict:
        import yaml
        from rehab.config import DEFAULT_CONFIG
        with open(DEFAULT_CONFIG) as f:
            return yaml.safe_load(f)

    def test_the_before_press_cues_ship_on(self) -> None:
        """Buzzer, sound and screen before the press."""
        cue = self._shipped()["cue"]
        for key in ("buzz_before", "sound_before", "show_target"):
            with self.subTest(key=key):
                self.assertIs(cue[key], True)

    def test_the_after_press_cues_ship_off(self) -> None:
        """A confirmation on every correct press gets wearing over a
        block, and the reaction-time comparison only cares about what
        the patient got BEFORE they moved. Available, not default."""
        cue = self._shipped()["cue"]
        for key in ("buzz_after", "sound_after"):
            with self.subTest(key=key):
                self.assertIs(cue[key], False)

    def test_the_old_block_is_gone(self) -> None:
        self.assertNotIn("game_cue", self._shipped())


class LegacySettingsMigrationTests(unittest.TestCase):
    """A user_settings.yaml written by the old build still says
    game_cue.mode and motor.enabled. Reading those once and translating
    them is the difference between an existing rig behaving the same
    after an update and quietly changing on the patient."""

    def _migrate(self, overrides: dict) -> dict:
        from rehab.config import apply_cue_migration
        merged = {"cue": {"buzz_before": True, "sound_before": True,
                           "sound_after": True, "buzz_after": True,
                           "show_target": True}}
        apply_cue_migration(merged, overrides)
        return merged["cue"]

    def test_visual_mode_turns_the_buzzer_cue_off(self) -> None:
        cue = self._migrate({"game_cue": {"mode": "visual"}})
        self.assertFalse(cue["buzz_before"])
        self.assertTrue(cue["show_target"])

    def test_vibration_mode_hides_the_target(self) -> None:
        cue = self._migrate({"game_cue": {"mode": "vibration"}})
        self.assertTrue(cue["buzz_before"])
        self.assertFalse(cue["show_target"])

    def test_both_mode_leaves_everything_on(self) -> None:
        cue = self._migrate({"game_cue": {"mode": "both"}})
        self.assertTrue(cue["buzz_before"])
        self.assertTrue(cue["show_target"])

    def test_motor_disabled_turns_the_buzzer_cue_off(self) -> None:
        cue = self._migrate({"motor": {"enabled": False}})
        self.assertFalse(cue["buzz_before"])

    def test_silenced_stim_tone_carries_over(self) -> None:
        cue = self._migrate({"audio": {"stim_tone_enabled": False}})
        self.assertFalse(cue["sound_before"])

    def test_an_explicit_new_key_wins(self) -> None:
        # Once the Sensory Cues menu has written the new keys, the
        # legacy ones must stop overriding them.
        cue = self._migrate({"game_cue": {"mode": "visual"},
                              "cue": {"buzz_before": True}})
        self.assertTrue(cue["buzz_before"])

    def test_a_file_with_none_of_it_is_left_alone(self) -> None:
        from rehab.config import apply_cue_migration
        merged = {"cue": {"buzz_before": True}}
        derived = apply_cue_migration(merged, {"serial": {"left_port": None}})
        self.assertEqual(derived, [])
        self.assertEqual(merged["cue"], {"buzz_before": True})

    def test_a_nonsense_mode_falls_back_to_everything_on(self) -> None:
        cue = self._migrate({"game_cue": {"mode": "nonsense"}})
        self.assertTrue(cue["buzz_before"])
        self.assertTrue(cue["show_target"])


if __name__ == "__main__":
    unittest.main()
