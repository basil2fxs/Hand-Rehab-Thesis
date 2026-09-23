"""Per-hand, per-device calibration: the opening menu and what a run writes.

The point of the menu is that a therapist can do one job without losing
the other. The sensor thresholds and the buzzer channel map are measured
by different steps and stored in different places, so a run that only
measured one of them must leave the other exactly as it was.

That is the part worth pinning down. Getting it wrong is silent: a
buzzers-only visit that also wrote the profile would replace a real
measurement with the zeros of a profile nobody took, and the next
session would run every trial on unreachable thresholds and record a
patient with four working fingers as having none.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import finger_rehab.ui.calibration_screen as cs
from finger_rehab.hardware.calibration_profile import CalibrationProfile


# A profile that passes usable(): each finger travels well clear of the
# noise, and no pad is so preloaded that its trigger is unreachable.
EMPTY = [243.0, 244.0, 245.0, 246.0]
REST = [2.0, 4.0, 8.0, 30.0]
PRESS = [90.0, 95.0, 88.0, 92.0]


class FakeCfg:
    """Enough of Config to drive the screen, with the writes recorded.

    resolve_path is rooted at a tmp dir so the profile the screen saves
    is a real file this test can read back, which is the only way to
    tell "left alone" apart from "rewritten with the same values".
    """

    def __init__(self, root: Path, data: dict | None = None) -> None:
        self.root = root
        self.data = data if data is not None else {}
        self.saved: dict = {}
        self.save_calls = 0

    def get(self, key, default=None):
        node = self.data
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def resolve_path(self, value):
        return self.root / value

    def calibration_path(self, name):
        """Config.calibration_path. The whole calibration store moves
        when session.calibration_dir is set, so reads and writes stay
        together; a double with only resolve_path hands the screen a
        path object it never built."""
        return self.resolve_path(Path("config") / "calibration" / name)

    def save_user_overrides(self, overrides):
        self.saved.update(overrides)
        self.save_calls += 1
        for key, value in overrides.items():
            section, _, leaf = key.partition(".")
            self.data.setdefault(section, {})[leaf] = value
        return self.root / "user_settings.yaml"


def make_screen(tmp_path: Path, hand: str = "right",
                cfg_data: dict | None = None, detectors: int = 1):
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.ui.theme import THEMES
    from finger_rehab.ui.widgets import Layout

    sent: list[str] = []

    class Src:
        port = "/dev/mock"

        def send_command(self, c):
            sent.append(c)
            return True

    data = {"bilateral": {"hand": hand}}
    if cfg_data:
        data.update(cfg_data)

    e = GameEngine.__new__(GameEngine)
    e.cfg = FakeCfg(tmp_path, data)
    e.theme = list(THEMES.values())[0]
    e.layout = Layout(1280, 800, 1.0)
    e.source = Src()
    e.detectors = {h: None for h in ("right", "left")[:detectors]}
    e.session = type("S", (), {"participant": "T1"})()
    screen = cs.CalibrationScreen(e)
    return screen, e.cfg, sent


def measured_profile(hand: str = "right") -> CalibrationProfile:
    return CalibrationProfile(
        hand=hand,
        empty=list(EMPTY),
        empty_noise=[1.0] * 4,
        resting=[EMPTY[i] + REST[i] for i in range(4)],
        press=[EMPTY[i] + PRESS[i] for i in range(4)],
        press_all=[EMPTY[i] + PRESS[i] * 0.8 for i in range(4)],
    )


def fill_measurements(screen) -> None:
    """Put a usable set of sensor numbers on the screen's live profile,
    as though the four measuring steps had just been walked through."""
    p = measured_profile(screen.hand)
    screen.profile.empty = list(p.empty)
    screen.profile.empty_noise = list(p.empty_noise)
    screen.profile.resting = list(p.resting)
    screen.profile.press = list(p.press)
    screen.profile.press_all = list(p.press_all)


class TestSaveIsPerJob:
    """A run writes what it measured and nothing else."""

    def test_buzzers_only_leaves_the_saved_profile_byte_for_byte(
            self, tmp_path: Path):
        """The failure this guards against wipes a real calibration.

        A buzzers-only run has never touched a sensor, so its live
        profile is all zeros. Saving that over the hand's file would
        replace measured thresholds with unreachable ones and every
        later trial on that hand would score a miss.
        """
        path = tmp_path / "config/calibration/current_right.json"
        measured_profile("right").save(path)
        before = path.read_bytes()

        screen, cfg, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        for _ in range(4):
            screen._record_felt(0)
        screen._save()

        assert path.read_bytes() == before, "buzzers-only rewrote the profile"
        assert screen._saved is True

    def test_buzzers_only_writes_the_channel_map(self, tmp_path: Path):
        screen, cfg, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        # Channel 1 was felt on the ring finger, so cueing the ring
        # finger has to send channel 1.
        screen.buzz_channel = 1
        screen._record_felt(2)
        screen.buzz_channel = 2
        screen._record_felt(0)
        screen.buzz_channel = 3
        screen._record_felt(1)
        screen.buzz_channel = 4
        screen._record_felt(3)
        screen._save()

        assert cfg.saved["motor.channel_map"] == [2, 3, 1, 4]
        assert cfg.data["motor"]["channel_map"] == [2, 3, 1, 4]

    def test_sensors_only_does_not_touch_the_channel_map(
            self, tmp_path: Path):
        """The mirror-image failure: a sensors-only run that also wrote
        the map would reset a discovered wiring back to straight-through,
        so cueing one finger would buzz another and the patient's correct
        press would be recorded as their error."""
        discovered = [3, 4, 1, 2]
        screen, cfg, _ = make_screen(
            tmp_path, cfg_data={"motor": {"channel_map": list(discovered)}})
        screen._pick_job(cs.JOB_SENSORS)
        screen._begin()
        fill_measurements(screen)
        screen._save()

        assert cfg.data["motor"]["channel_map"] == discovered
        assert "motor.channel_map" not in cfg.saved

    def test_sensors_only_writes_the_profile(self, tmp_path: Path):
        screen, cfg, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_SENSORS)
        screen._begin()
        fill_measurements(screen)
        screen._save()

        path = tmp_path / "config/calibration/current_right.json"
        assert path.exists()
        saved = json.loads(path.read_text())
        assert saved["hand"] == "right"
        assert saved["press"] == [EMPTY[i] + PRESS[i] for i in range(4)]

    def test_both_writes_both(self, tmp_path: Path):
        screen, cfg, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BOTH)
        screen._begin()
        fill_measurements(screen)
        for _ in range(4):
            screen._record_felt(0)
        screen._save()

        assert (tmp_path / "config/calibration/current_right.json").exists()
        assert "motor.channel_map" in cfg.saved

    def test_each_hand_keeps_its_own_file(self, tmp_path: Path):
        """A profile describes one hand's pads. Calibrating the left must
        not land on the right hand's saved thresholds."""
        screen, cfg, _ = make_screen(tmp_path, detectors=2)
        screen._pick_job(cs.JOB_SENSORS)
        screen._pick_hand("right")
        screen._begin()
        fill_measurements(screen)
        screen._save()

        screen._pick_hand("left")
        screen._begin()
        fill_measurements(screen)
        screen._save()

        right = tmp_path / "config/calibration/current_right.json"
        left = tmp_path / "config/calibration/current_left.json"
        assert right.exists() and left.exists()
        assert json.loads(right.read_text())["hand"] == "right"
        assert json.loads(left.read_text())["hand"] == "left"

    def test_a_dated_copy_is_kept_only_when_sensors_were_measured(
            self, tmp_path: Path):
        history = tmp_path / "config/calibration/history"
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        for _ in range(4):
            screen._record_felt(0)
        screen._save()
        assert not history.exists() or not list(history.glob("*.json"))

        screen._pick_job(cs.JOB_SENSORS)
        screen._begin()
        fill_measurements(screen)
        screen._save()
        assert list(history.glob("*.json"))


class TestRunPlan:
    """Only the chosen steps run, and the counter says so."""

    def test_plan_matches_the_job(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_SENSORS)
        assert screen._plan() == [cs.STEP_EMPTY, cs.STEP_RESTING,
                                  cs.STEP_PRESS, cs.STEP_ALL]
        screen._pick_job(cs.JOB_BUZZERS)
        assert screen._plan() == [cs.STEP_BUZZ]
        screen._pick_job(cs.JOB_BOTH)
        assert screen._plan() == [cs.STEP_EMPTY, cs.STEP_RESTING,
                                  cs.STEP_PRESS, cs.STEP_ALL, cs.STEP_BUZZ]

    def test_begin_lands_on_the_first_step_of_the_job(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        assert screen.step == cs.STEP_BUZZ

        screen._pick_job(cs.JOB_SENSORS)
        screen._begin()
        assert screen.step == cs.STEP_EMPTY

    def test_sensors_only_ends_at_review_without_the_buzz_step(
            self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_SENSORS)
        assert screen._next_step(cs.STEP_ALL) == cs.STEP_REVIEW

    def test_step_counter_never_promises_a_step_it_will_not_ask_for(
            self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        assert screen._step_label(cs.STEP_BUZZ) == "Step 1 of 1"
        screen._pick_job(cs.JOB_BOTH)
        assert screen._step_label(cs.STEP_BUZZ) == "Step 5 of 5"

    def test_buzzers_only_review_shows_the_kept_thresholds(
            self, tmp_path: Path):
        """A buzzers-only run works from the saved profile so the review
        shows the numbers the device will keep running on, rather than a
        table of zeros that reads as a broken measurement."""
        measured_profile("right").save(
            tmp_path / "config/calibration/current_right.json")
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        assert screen._has_sensor_data() is True
        assert screen.profile.press == [EMPTY[i] + PRESS[i] for i in range(4)]

    def test_buzzers_only_says_so_when_no_sensor_profile_exists(
            self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen._begin()
        assert screen._has_sensor_data() is False
        assert "sensors when you can" in screen._keep_note()

    def test_the_menu_says_what_will_be_left_alone(self, tmp_path: Path):
        measured_profile("right").save(
            tmp_path / "config/calibration/current_right.json")
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_SENSORS)
        assert "buzzer channel map stays" in screen._keep_note()
        screen._pick_job(cs.JOB_BUZZERS)
        assert "stay exactly as they are" in screen._keep_note()

    def test_the_effective_map_is_the_saved_one_when_not_measured(
            self, tmp_path: Path):
        screen, _, _ = make_screen(
            tmp_path, cfg_data={"motor": {"channel_map": [4, 3, 2, 1]}})
        screen._pick_job(cs.JOB_SENSORS)
        assert screen.effective_channel_map() == [4, 3, 2, 1]
        screen._pick_job(cs.JOB_BUZZERS)
        screen._record_felt(0)
        assert screen.effective_channel_map()[0] == 1


class TestHandChoice:
    def test_switch_is_offered_only_when_a_second_hand_exists(
            self, tmp_path: Path):
        one, _, _ = make_screen(tmp_path, detectors=1)
        assert one._both_hands_possible() is False
        two, _, _ = make_screen(tmp_path, detectors=2)
        assert two._both_hands_possible() is True

    def test_bilateral_config_counts_as_a_second_hand(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path, hand="both", detectors=1)
        assert screen._both_hands_possible() is True

    def test_both_is_never_a_hand_the_pads_are_calibrated_for(
            self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path, hand="both")
        assert screen.hand in ("left", "right")

    def test_changing_hand_drops_the_other_hand_measurements(
            self, tmp_path: Path):
        """Samples already taken came off the other hand's pads, so
        carrying them over would save one hand's travel as the other's."""
        screen, _, _ = make_screen(tmp_path, detectors=2)
        screen._begin()
        fill_measurements(screen)
        screen._felt = {1: 0}
        screen._pick_hand("left")
        assert screen.profile.press == [0.0] * 4
        assert screen._felt == {}

    def test_changing_job_drops_measurements_too(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._begin()
        fill_measurements(screen)
        screen._pick_job(cs.JOB_BUZZERS)
        assert screen.profile.press == [0.0] * 4

    def test_reset_returns_to_the_menu_with_both_as_the_job(
            self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path)
        screen._pick_job(cs.JOB_BUZZERS)
        screen.step = cs.STEP_REVIEW
        screen.reset()
        assert screen.step == cs.STEP_INTRO
        assert screen.job == cs.JOB_BOTH


class TestMenuHitBoxes:
    """A click has to register where the control was drawn.

    The menu rows are drawn from _intro_geometry and the buttons are
    built from the same call, so this checks the two have not drifted
    and that no two controls overlap.
    """

    def _intro_buttons(self, screen):
        return [b for b in screen._buttons if b.label != "Back"]

    def test_every_menu_button_sits_on_a_geometry_row(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path, detectors=2)
        g = screen._intro_geometry()
        rows = {g["hand_buttons"], g["job_buttons"], g["start"]}
        for b in self._intro_buttons(screen):
            assert b.rect.y in rows, f"{b.label} is drawn off every row"

    def test_menu_buttons_do_not_overlap(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path, detectors=2)
        buttons = self._intro_buttons(screen)
        for i, a in enumerate(buttons):
            for b in buttons[i + 1:]:
                assert not a.rect.colliderect(b.rect), (
                    f"{a.label} overlaps {b.label}, so one click could "
                    f"fire the wrong action")

    def test_menu_buttons_stay_on_screen(self, tmp_path: Path):
        screen, _, _ = make_screen(tmp_path, detectors=2)
        surface = screen.layout.width, screen.layout.height
        for b in screen._buttons:
            assert b.rect.left >= 0 and b.rect.right <= surface[0]
            assert b.rect.top >= 0 and b.rect.bottom <= surface[1]

    def test_clicking_a_hand_button_picks_that_hand(self, tmp_path: Path):
        import pygame
        screen, _, _ = make_screen(tmp_path, detectors=2)
        left = next(b for b in screen._buttons if b.label == "Left hand")
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": left.rect.center}))
        assert screen.hand == "left"

    def test_clicking_a_job_button_picks_that_job(self, tmp_path: Path):
        import pygame
        screen, _, _ = make_screen(tmp_path)
        btn = next(b for b in screen._buttons if b.label == "Buzzers only")
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": btn.rect.center}))
        assert screen.job == cs.JOB_BUZZERS

    def test_clicking_start_leaves_the_menu(self, tmp_path: Path):
        import pygame
        screen, _, _ = make_screen(tmp_path)
        btn = next(b for b in screen._buttons
                   if b.label == "Start calibration")
        for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            screen.handle_event(pygame.event.Event(
                kind, {"button": 1, "pos": btn.rect.center}))
        assert screen.step != cs.STEP_INTRO

    def test_the_hand_row_is_dropped_when_there_is_only_one_hand(
            self, tmp_path: Path):
        """With one board there is nothing to switch to, so the row is
        not drawn and the job row moves up into its place. The buttons
        have to move with it."""
        screen, _, _ = make_screen(tmp_path, detectors=1)
        g = screen._intro_geometry()
        assert "hand_buttons" not in g
        assert not any(b.label.endswith("hand") for b in screen._buttons)
        for b in self._intro_buttons(screen):
            assert b.rect.y in {g["job_buttons"], g["start"]}

    def test_every_step_keeps_a_way_out(self, tmp_path: Path):
        for step in (cs.STEP_INTRO, cs.STEP_EMPTY, cs.STEP_RESTING,
                     cs.STEP_PRESS, cs.STEP_ALL, cs.STEP_BUZZ,
                     cs.STEP_REVIEW):
            screen, _, _ = make_screen(tmp_path)
            screen.step = step
            screen._rebuild_buttons()
            assert any(b.label == "Back" for b in screen._buttons)


class TestScreenRenders:
    """The screen draws at every step without raising, on the real
    surface size the app uses."""

    @pytest.mark.parametrize("job", [cs.JOB_SENSORS, cs.JOB_BUZZERS,
                                     cs.JOB_BOTH])
    def test_draws_at_every_step(self, tmp_path: Path, job):
        import pygame
        screen, _, _ = make_screen(tmp_path, detectors=2)
        surf = pygame.Surface((1280, 800))
        screen._pick_job(job)
        for step in [cs.STEP_INTRO] + screen._plan() + [cs.STEP_REVIEW]:
            screen.step = step
            screen._rebuild_buttons()
            screen.draw(surf)

    def test_review_draws_with_measurements(self, tmp_path: Path):
        import pygame
        screen, _, _ = make_screen(tmp_path)
        surf = pygame.Surface((1280, 800))
        screen._begin()
        fill_measurements(screen)
        screen.step = cs.STEP_REVIEW
        screen._rebuild_buttons()
        screen.draw(surf)
