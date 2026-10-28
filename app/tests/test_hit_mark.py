"""A hit marks its tile with a tick, so the outcome reads without colour.

In the shipping style the only feedback a press gets is its tile's flash:
green on a hit (gold for a Perfect) and grey on a miss or a press before
the cue. With the confirming chime off for the healthy study, a player who
cannot tell the green from the grey had nothing else to go on. Every hit's
flash now carries a tick; a miss stays a plain grey flash. The laboratory's
neutral style keeps its tile flash unmarked, since there the feedback is the
delayed ring and only the ring's fill may differ between outcomes.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_quick_calibration import _engine  # noqa: E402


def _tile(screen, lane):
    return next(ls for ls in screen.lanes if ls.lane == lane)


def _trial(trial_id, lane, pressed):
    from finger_rehab.game.modes.classic import PendingTrial
    return PendingTrial(trial_id=trial_id, lane=lane, stim_t_perf=0.0,
                        keys_pressed=[lane] if pressed else [],
                        incorrect_presses=[])


def _in_block(eng):
    """The counters a block's start sets, as test_adaptive sets them."""
    eng._ensure_metric_state()
    eng._block_t0 = time.perf_counter()
    eng._block_rt_sum, eng._block_rt_count = 0.0, 0
    eng._block_bpm_min = eng._block_bpm_max = None
    eng._block_wrong_press_trials = eng._block_rhythm_spurious_presses = 0
    eng._block_idle_presses = eng._block_peak_streak = 0
    return eng


def _result(label, rt_ms):
    from finger_rehab.game.scoring import TrialResult
    return TrialResult(label=label, points=6 if rt_ms else 0, rt_ms=rt_ms)


def test_a_hit_flashes_with_a_tick_and_a_miss_without(tmp_path):
    eng = _in_block(_engine(tmp_path))
    gp = eng._screens["gameplay"]
    eng.log_trial(_trial(1, 1, True), _result("Great", 200.0), now=time.perf_counter())
    eng.log_trial(_trial(2, 2, False), _result("Miss", None), now=time.perf_counter())
    assert _tile(gp, 1).flash_mark == "tick"
    assert _tile(gp, 2).flash_mark is None
    assert tuple(_tile(gp, 2).flash_colour) == tuple(eng.theme.muted)


def test_a_rhythm_note_pressed_is_ticked_and_one_let_pass_is_not(tmp_path):
    from unittest.mock import MagicMock
    from finger_rehab.audio.beatmap import Note
    eng = _engine(tmp_path)
    eng.current_block = "rhythm"
    eng._ensure_metric_state()
    rs = eng._screens["rhythm"]

    def note(lane, index):
        sched = MagicMock()
        sched.note = Note(t=1.0, lane=lane)
        sched.index = index
        return sched
    eng.log_rhythm_hit(note(1, 3), 20.0, "Great", 6, now=0.0, was_pressed=True)
    eng.log_rhythm_hit(note(2, 4), 0.0, "Miss", 0, now=0.0, was_pressed=False)
    assert _tile(rs, 1).flash_mark == "tick"
    assert _tile(rs, 2).flash_mark is None


def test_the_lab_style_keeps_its_tile_flash_unmarked(tmp_path):
    eng = _engine(tmp_path)
    eng.feedback_style = "neutral"
    eng.feedback_delay_ms = 800
    _in_block(eng)
    gp = eng._screens["gameplay"]
    eng.log_trial(_trial(1, 1, True), _result("Great", 200.0), now=time.perf_counter())
    assert _tile(gp, 1).flash_mark is None


def test_the_tick_is_drawn_on_green_and_on_gold(tmp_path):
    import pygame
    eng = _engine(tmp_path)
    gp = eng._screens["gameplay"]
    tile = _tile(gp, 1)
    now = time.perf_counter()
    for colour in (eng.theme.lane_hit, eng._GOLD):
        plain, ticked = pygame.Surface((1280, 800)), pygame.Surface((1280, 800))
        tile.flash(colour, 0.4, now)
        tile.draw(plain, now + 0.01)
        tile.flash(colour, 0.4, now, mark="tick")
        tile.draw(ticked, now + 0.01)
        r = tile.rect
        changed = sum(plain.get_at((x, y)) != ticked.get_at((x, y))
                      for x in range(r.left, r.right, 2) for y in range(r.top, r.bottom, 2))
        assert changed > 50, f"no tick drawn on {colour}"
        tile.end_flash()
