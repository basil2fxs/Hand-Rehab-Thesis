"""A press's outcome flash never outlives the next cue.

Adaptive fires cues on a beat counted from the previous cue, not from
the press, so at a quick pace the next cue came as little as 27 ms
after a correct press while that press's 0.4 s green flash was still
up: the green sat beside the new cue, and on the same finger it hid
the cue under the flash colour (the tile draws a flash over its cue
colour). Classic schedules the same way and did it with slower
presses. Every cue now ends every outcome flash on the tiles.

The lab build had a second route to the same thing: the feedback ring
parked for 800 ms re-flashed the tile in the outcome colour when it
appeared, so a correct press went green twice, the second time after
the next cue, and hit and miss differed in colour at the very moment
the feedback ERP is measured on. The ring now appears on its own, and
one still waiting when the next cue fires is dropped with its byte.

Rhythm keeps its own 0.6 s flash: its cues are falling notes, not the
tiles, and a new note never lights a tile.
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

GREEN = (22, 163, 74)


def _flashing(ls, now):
    return now < ls.flash_until


def test_a_new_cue_ends_every_flash_still_showing(tmp_path):
    eng = _engine(tmp_path)
    gp = eng._screens["gameplay"]
    now = time.perf_counter()
    gp.flash_lane(1, GREEN, 0.4, now)
    gp.flash_lane(2, GREEN, 0.4, now)
    eng.on_stim_multi([3], 1, now + 0.03)
    t = now + 0.05
    for ls in gp.lanes:
        assert not _flashing(ls, t), f"lane {ls.lane} still flashing"
        assert ls.glow_until <= t
    assert [ls.lane for ls in gp.lanes if ls.active] == [3]


def test_the_cue_tile_is_never_hidden_under_the_last_flash(tmp_path):
    eng = _engine(tmp_path)
    gp = eng._screens["gameplay"]
    now = time.perf_counter()
    gp.flash_lane(2, GREEN, 0.4, now)
    eng.on_stim_multi([2], 1, now + 0.03)
    tile = next(ls for ls in gp.lanes if ls.lane == 2)
    assert tile.active and not _flashing(tile, now + 0.05)


def test_rhythm_keeps_its_hit_flash_through_the_next_beat(tmp_path):
    eng = _engine(tmp_path)
    rs = eng._screens["rhythm"]
    now = time.perf_counter()
    rs.flash_lane(1, GREEN, 0.6, now)
    eng.on_stim_multi([2], 1, now + 0.05)
    tile = next(ls for ls in rs.lanes if ls.lane == 1)
    assert _flashing(tile, now + 0.1)


def test_the_delayed_ring_does_not_flash_the_tile_again(tmp_path):
    eng = _engine(tmp_path)
    eng.feedback_delay_ms = 800
    gp = eng._screens["gameplay"]
    now = time.perf_counter()
    gp.flash_lane(1, GREEN, 0.4, now)          # the press itself
    tile = next(ls for ls in gp.lanes if ls.lane == 1)
    first = tile.flash_until
    eng._park_feedback("gameplay", 1, {"popup_glyph": "full"}, GREEN,
                       "Great", marker=False)
    eng._drain_feedback(force=True)
    assert tile.flash_until == first, "the ring re-flashed the tile"
    assert any(getattr(p, "glyph", None) == "full" for p in gp._popups)


def test_the_delayed_rhythm_ring_bursts_no_second_time(tmp_path):
    eng = _engine(tmp_path)
    eng.feedback_delay_ms = 800
    rs = eng._screens["rhythm"]
    now = time.perf_counter()
    rs.flash_lane(1, GREEN, 0.6, now)
    tile = next(ls for ls in rs.lanes if ls.lane == 1)
    first, bursts = tile.flash_until, len(rs._bursts)
    eng._park_feedback("rhythm", 1, {"popup_glyph": "full"}, GREEN,
                       "Great", marker=False)
    eng._drain_feedback(force=True)
    assert tile.flash_until == first
    assert len(rs._bursts) == bursts
    assert any(getattr(p, "glyph", None) == "full" for p in rs._popups)


def test_a_ring_still_waiting_at_the_next_cue_is_dropped(tmp_path):
    eng = _engine(tmp_path)
    eng.feedback_delay_ms = 800
    sent = []
    eng._eeg_send = lambda code, **k: sent.append(code)
    eng._eeg_feedback_markers = True
    now = time.perf_counter()
    eng._park_feedback("gameplay", 1, {"popup_glyph": "full"}, GREEN,
                       "Great")
    eng._park_feedback("rhythm", 2, {"popup_glyph": "full"}, GREEN,
                       "Great")
    eng.on_stim_multi([3], 2, now + 0.1)
    left = [e[1] for e in eng._pending_feedback]
    assert left == ["rhythm"], left
    eng._drain_feedback(force=True)
    # The dropped ring sends no byte; the rhythm one, forced out
    # early, sends none either.
    assert sent == []
    gp = eng._screens["gameplay"]
    assert not any(getattr(p, "glyph", None) for p in gp._popups)
