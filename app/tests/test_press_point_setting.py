"""Settings, Setup, Press point (Basil, 8 October 2026): the share of
the resting-to-light-press gap that counts as a press, which is also
where the EEG response byte goes out. 30 percent by default, moved in
5 percent steps, used at once and saved until it is changed again."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.hardware import calibration_profile as cp  # noqa: E402


@pytest.fixture(autouse=True)
def _default_point():
    cp.set_press_fraction(cp.PRESS_FRACTION)
    yield
    cp.set_press_fraction(cp.PRESS_FRACTION)


def _profile():
    p = cp.CalibrationProfile()
    p.empty = [500.0] * 4
    p.empty_noise = [1.0] * 4
    p.resting = [505.0] * 4
    p.press = [605.0] * 4
    return p


def test_the_default_is_thirty_percent():
    assert cp.press_fraction() == 0.30


def test_the_point_stays_in_range_and_in_whole_percent():
    assert cp.set_press_fraction(0.05) == 0.10
    assert cp.set_press_fraction(0.9) == 0.60
    assert cp.set_press_fraction(0.2499) == 0.25
    assert cp.set_press_fraction("junk") == cp.PRESS_FRACTION


def test_thresholds_follow_the_point():
    p = _profile()
    at30 = p.on_delta()
    cp.set_press_fraction(0.20)
    at20 = p.on_delta()
    assert all(a < b for a, b in zip(at20, at30))
    # the release point stays under the press point
    assert all(off < on for off, on in zip(p.off_delta(), at20))


@pytest.fixture
def settings():
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import DiagnosticsScreen
    cfg = Config.load()
    cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
    eng = GameEngine(cfg, KeyboardOnlySource())
    screen = DiagnosticsScreen(eng)
    eng._screens["diagnostics"] = screen
    eng.screen_obj = screen
    yield screen, eng
    pygame.quit()


def _button(screen, label):
    return next(b for b, t in zip(screen._panel_buttons, screen._panel_tabs)
                if b.label == label and t == "setup")


def test_the_steps_sit_on_the_setup_card(settings):
    screen, _eng = settings
    card = screen._firmware_rect()
    for label in ("-", "+"):
        assert card.contains(_button(screen, label).rect)


def test_a_step_is_used_at_once_and_saved(settings, monkeypatch):
    screen, eng = settings
    saved, applied = {}, []
    monkeypatch.setattr(eng.cfg, "save_user_overrides", saved.update)
    monkeypatch.setattr(eng, "reapply_calibrations", lambda: applied.append(1))
    _button(screen, "-").on_click()
    _button(screen, "-").on_click()
    assert cp.press_fraction() == 0.20
    assert eng.cfg.get("fsr.press_fraction") == 0.20
    assert saved == {"fsr.press_fraction": 0.20}
    assert len(applied) == 2
    assert "20%" in screen._port_status


def test_a_saved_point_is_used_at_launch():
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data.setdefault("fsr", {})["press_fraction"] = 0.25
    GameEngine(cfg, KeyboardOnlySource())
    assert cp.press_fraction() == 0.25
    pygame.quit()
