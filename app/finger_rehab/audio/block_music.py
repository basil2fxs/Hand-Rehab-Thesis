"""Background music inside a block: Force Pilot only.

The rule everywhere else in the app is no music under a block, because
gameplay audio is a recorded condition. Force Pilot is the one
exception, at Basil's request: its runs are long silent holds, and a
quiet track keeps a block from dragging. The exception is kept narrow
on purpose:

  - BLOCK_MODES is a closed set with one entry. Rhythm owns the music
    stream for its song, and every other mode stays silent.
  - The track starts only once the menu playlist has finished its
    fade, so the two never overlap, and it never starts while a game
    song or the metronome holds the stream.
  - The mode never reads the stream. Scoring, the trial rows and the
    raw log are the same with the track on or off; a test pins that.
  - config/eeg_lab.yaml turns it off, so a lab block is recorded in
    silence.

Same shape as audio/menu_music.py: update() once per frame from the
engine's loop, config read live, a swappable clock for tests.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path


log = logging.getLogger(__name__)


class BlockMusicPlayer:
    # The only modes allowed a background track. One entry, on purpose.
    BLOCK_MODES = ("force_pilot",)
    # Rise over the opening second so the track does not land on the
    # GET READY card at full level.
    FADE_IN_S = 1.0
    # Cooldown after a refused or failed start, so a broken decoder
    # cannot be retried every frame.
    RETRY_S = 2.0

    def __init__(self, audio, cfg) -> None:
        self.audio = audio
        self.cfg = cfg
        self.state = "idle"        # idle | playing
        self._playlist: list[Path] = []
        self._index = 0
        self._started_at = 0.0
        self._retry_after = 0.0
        self._clock = time.perf_counter
        self._tracks = self._resolve_tracks()
        self._reshuffle()

    # ---- config reads (live) -------------------------------------------
    def enabled(self, mode: str) -> bool:
        if mode not in self.BLOCK_MODES:
            return False
        return bool(self.cfg.get(f"{mode}.music_enabled", False))

    def volume(self, mode: str) -> float:
        try:
            v = float(self.cfg.get(f"{mode}.music_volume", 0.2))
        except (TypeError, ValueError):
            v = 0.2
        return max(0.0, min(1.0, v))

    def _resolve_tracks(self) -> list[Path]:
        """The licensed menu tracks that exist on disk: the block track
        draws on the same playlist so no new licence enters the app."""
        names = self.cfg.get("audio.menu_music_tracks", []) or []
        music_dir = self.cfg.get("audio.music_dir", "assets/music")
        out: list[Path] = []
        for name in names:
            try:
                p = self.cfg.resolve_path(str(Path(music_dir) / str(name)))
            except Exception:
                continue
            if Path(p).exists():
                out.append(Path(p))
        return out

    def _reshuffle(self) -> None:
        self._playlist = list(self._tracks)
        random.shuffle(self._playlist)
        self._index = 0

    # ---- the one entry point -------------------------------------------
    def update(self, block_mode: str | None, paused: bool = False,
               menu_state: str = "idle") -> None:
        """Advance one frame. `block_mode` is the running block's mode
        key, or None between blocks; `menu_state` is the menu player's
        state so the block track waits for its fade."""
        if self.audio is None:
            self.state = "idle"
            return
        now = self._clock()
        want = (block_mode is not None
                and self.enabled(block_mode)
                and not paused
                and bool(self._tracks)
                and menu_state == "idle"
                and not self.audio.game_stream_active())
        if not want:
            if self.state == "playing":
                self.audio.block_music_stop()
                self.state = "idle"
            return
        if self.state == "idle":
            if now >= self._retry_after:
                self._start_next(now, block_mode)
            return
        if not self.audio.block_music_busy():
            # Track ran out (or something else took the stream).
            self._start_next(now, block_mode)
            return
        frac = min(1.0, max(0.0, (now - self._started_at) / self.FADE_IN_S))
        self.audio.block_music_set_volume(self.volume(block_mode) * frac)

    @property
    def is_playing(self) -> bool:
        return self.state == "playing"

    def _start_next(self, now: float, mode: str) -> None:
        if self._index >= len(self._playlist):
            self._reshuffle()
        track = self._playlist[self._index]
        self._index += 1
        self._started_at = now
        if self.audio.block_music_play(track, 0.0):
            self._retry_after = 0.0
            self.state = "playing"
        else:
            self._retry_after = now + self.RETRY_S
            self.state = "idle"

    def stop_now(self) -> None:
        if self.audio is not None:
            self.audio.block_music_stop()
        self.state = "idle"
