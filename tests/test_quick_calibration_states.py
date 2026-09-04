"""What the quick calibration rest steps say when the device is quiet.

The rest steps carry one state each: a headline of at most four words,
a short line under it, a countdown ring and a picture of the hand. The
picture is the only thing on the step that names a finger, so it has
to agree with the headline. When no samples are arriving the headline
is NO SIGNAL, and the last readings before the device went quiet are
not news about the hand: a finger glowing amber under NO SIGNAL asks
the player to lift something the screen cannot see.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_quick_calibration import _engine, EMPTY  # noqa: E402


def _screen(tmp_path):
    eng = _engine(tmp_path)
    eng.maybe_start_quick_calibration(lambda: None)
    return eng, eng.screen_obj


def test_a_loaded_lane_is_named_and_lit(tmp_path):
    _eng, sc = _screen(tmp_path)
    t = 0.0
    for _ in range(120):
        sc.on_sample(t, tuple(EMPTY))
        t += 0.005
    down = list(EMPTY)
    down[2] += 40
    for _ in range(120):
        sc.on_sample(t, tuple(down))
        t += 0.005
    sc.update(0.01)
    assert sc._blockers() == [("right", 2)]
    assert sc._rest_words()[0] == "LIFT YOUR RING FINGER"


def test_no_signal_lights_no_finger(tmp_path):
    import pygame
    _eng, sc = _screen(tmp_path)
    t = 0.0
    for _ in range(120):
        sc.on_sample(t, tuple(EMPTY))
        t += 0.005
    down = list(EMPTY)
    down[2] += 40
    for _ in range(120):
        sc.on_sample(t, tuple(down))
        t += 0.005
    sc.update(0.01)
    assert sc._blockers()                      # a lane really is loaded
    sc._last_sample_at = 0.0                   # and then the board stops
    assert sc._stale()
    assert sc._rest_words()[0] == "NO SIGNAL"
    lit: list = []
    real = sc._draw_hand_map

    def spy(surf, rect, hand, active, hot, on_pads):
        lit.append(set(hot or ()))
        return real(surf, rect, hand, active, hot, on_pads)

    sc._draw_hand_map = spy
    sc.draw(pygame.Surface((1280, 800)))
    assert lit and all(not h for h in lit), lit
