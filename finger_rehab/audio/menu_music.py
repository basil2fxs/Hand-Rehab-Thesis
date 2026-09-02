"""Menu music: a shuffled playlist that plays between games.

The player runs on the menu screens only (login, game select, the
hand-picker setup and results) and is silent everywhere else. That
rule is not a style choice: gameplay audio is part of the experiment
(the cue click, the confirmation chime and rhythm's own songs are all
recorded conditions), so a background track under a block would be an
uncontrolled stimulus. The screen list is therefore a closed set, and
the update() gate also checks block_is_running so a block that starts
UNDER a menu screen key (there is no such path today, but the gate is
cheap) still silences it.

Timing model: update() is called once per frame by the engine's main
loop, and also directly by tests. All fading is done by hand with
mixer volume ramps rather than pygame's own fadeout(), because
music.fadeout blocks the caller until the fade finishes, which would
freeze a frame for most of a second at block start.

The volume and on/off switch are read live from the config every
update, so the Settings screen only has to write cfg and save; there
is no wiring between the two and no state to fall out of sync. The
per-participant mute is the one input that is not config: the engine
passes it into update() from data/prefs.py, so a person who muted
the menus at their last visit gets silence from the first frame.
"""
from __future__ import annotations

import logging
import random
import time
from pathlib import Path


log = logging.getLogger(__name__)


# Amplitude factor that makes a track HALF AS LOUD as the game music.
# Loudness halves per 10 dB (the sone scale: Stevens 1956, J Acoust
# Soc Am 28:807, and ISO 532), and 10 dB down is an amplitude of
# 10 ** (-10 / 20) = 0.316. An amplitude of 0.5 is only 6 dB down and
# reads as roughly two thirds as loud, which is what the menus used to
# ship at. The rhythm song plays at master_volume, so this factor on
# top of master IS "half the game music", and it follows master when
# the Settings slider moves.
HALF_LOUDNESS = 0.316


def menu_music_level(cfg) -> float:
    """The menu playlist level as a fraction of master_volume: the
    number in audio.menu_music_volume when one is set (the Settings
    MUSIC slider writes one), else half the game music's loudness."""
    raw = cfg.get("audio.menu_music_volume", None)
    if raw is None or raw == "":
        return HALF_LOUDNESS
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return HALF_LOUDNESS
    return max(0.0, min(1.0, v))


class MenuMusicPlayer:
    # The closed set of screens the playlist runs on. The quick
    # calibration, the manual calibration, Settings and the rhythm
    # song picker are deliberately absent: calibration is a measuring
    # step, and the rhythm picker previews tracks on the same stream
    # this player would be using.
    MENU_SCREENS = ("title", "mode_select", "setup", "results")

    # Seconds for the hand-rolled ramps. FADE_OUT_S must stay well
    # under the 1.5 s minimum GET READY countdown so the music is gone
    # before any trial can fire.
    FADE_IN_S = 0.8
    FADE_OUT_S = 0.9
    # Results-screen duck: the last trial's confirmation chime is
    # often still sounding when the results screen lands (finish_block
    # lets it through on purpose), so the first track starts held at
    # DUCK_FACTOR for DUCK_S and then rises, instead of opening at
    # full level over the top of it.
    DUCK_S = 1.5
    DUCK_FACTOR = 0.25
    # Cooldown after a refused or failed start. Without it a host with
    # a broken decoder would retry a full file load on every frame of
    # every menu.
    RETRY_S = 2.0

    def __init__(self, audio, cfg) -> None:
        self.audio = audio
        self.cfg = cfg
        # "idle" (nothing on), "playing" (track up, gain ramping or
        # steady) or "fading" (ramping to zero, then stop).
        self.state = "idle"
        self._playlist: list[Path] = []
        self._index = 0
        self._last_track: Path | None = None
        self._started_at = 0.0
        self._ducked = False
        self._fade_started = 0.0
        self._fade_from = 1.0
        self._gain = 0.0
        self._retry_after = 0.0
        # Swappable clock so tests can step through fades without
        # sleeping through them.
        self._clock = time.perf_counter
        self._tracks = self._resolve_tracks()
        self._reshuffle()

    # ---- config reads (live, every update) ----------------------------
    def enabled(self) -> bool:
        return bool(self.cfg.get("audio.menu_music_enabled", True))

    def volume(self) -> float:
        return menu_music_level(self.cfg)

    def _resolve_tracks(self) -> list[Path]:
        """The playlist files that actually exist on disk. Names come
        from config so the rhythm library can grow without the menus
        picking up tracks chosen for gameplay pacing."""
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
            else:
                log.warning("menu music track missing: %s", name)
        return out

    def _reshuffle(self) -> None:
        self._playlist = list(self._tracks)
        random.shuffle(self._playlist)
        # Avoid a back-to-back repeat across the cycle boundary.
        if (len(self._playlist) > 1 and self._last_track is not None
                and self._playlist[0] == self._last_track):
            self._playlist.append(self._playlist.pop(0))
        self._index = 0

    # ---- the one entry point ------------------------------------------
    def update(self, screen_key: str | None, block_running: bool,
               muted: bool = False) -> None:
        """Advance the state machine one frame. `screen_key` is the
        engine's current screen; `block_running` is
        engine.block_is_running(); `muted` is the logged-in person's
        own mute (data/prefs.py), which fades the track out like a
        block start does and keeps it off until it clears. Safe to
        call from anywhere at any rate."""
        if self.audio is None:
            self.state = "idle"
            return
        now = self._clock()
        want = (self.enabled()
                and not muted
                and not block_running
                and screen_key in self.MENU_SCREENS
                and bool(self._tracks))
        if not want:
            if self.state == "playing":
                self._begin_fade(now)
            if self.state == "fading":
                self._advance_fade(now)
            return
        if self.state == "fading":
            # Wanted again mid-fade (quick bounce back to a menu):
            # finish the fade first so a restart is always from clean
            # silence, never a half-level jump.
            self._advance_fade(now)
            return
        if self.state == "idle":
            if now >= self._retry_after:
                self._start_next(now, duck=(screen_key == "results"))
            return
        # state == "playing"
        if not self.audio.menu_busy():
            # Track ran out (or something else claimed the stream);
            # move along the playlist.
            self._start_next(now, duck=False)
            return
        self._apply_gain(now)

    @property
    def is_playing(self) -> bool:
        return self.state == "playing"

    # ---- internals -----------------------------------------------------
    def _start_next(self, now: float, duck: bool) -> None:
        if not self._tracks:
            self.state = "idle"
            return
        if self._index >= len(self._playlist):
            self._reshuffle()
        track = self._playlist[self._index]
        self._index += 1
        self._started_at = now
        self._ducked = duck
        self._gain = 0.0
        start_gain = self.DUCK_FACTOR if duck else 0.0
        if self.audio.menu_play(track, self.volume() * start_gain):
            self._last_track = track
            self._retry_after = 0.0
            self.state = "playing"
        else:
            # Refused (game owns the stream, file vanished, audio
            # down). Stay idle and try again after the cooldown; the
            # want-gate above already keeps that retry off gameplay.
            self._retry_after = now + self.RETRY_S
            self.state = "idle"

    def _entry_gain(self, now: float) -> float:
        """Gain 0..1 for a track's opening seconds: the duck hold,
        then a linear rise over FADE_IN_S."""
        t = now - self._started_at
        if self._ducked:
            if t < self.DUCK_S:
                return self.DUCK_FACTOR
            t -= self.DUCK_S
            base = self.DUCK_FACTOR
        else:
            base = 0.0
        if t >= self.FADE_IN_S:
            return 1.0
        frac = max(0.0, t / self.FADE_IN_S)
        return base + (1.0 - base) * frac

    def _apply_gain(self, now: float) -> None:
        self._gain = self._entry_gain(now)
        self.audio.menu_set_volume(self.volume() * self._gain)

    def _begin_fade(self, now: float) -> None:
        self._fade_started = now
        self._fade_from = self._gain if self._gain > 0.0 else 1.0
        self.state = "fading"

    def _advance_fade(self, now: float) -> None:
        if not self.audio.menu_busy():
            # Stream already gone (track ended, game took it over):
            # nothing left to ramp.
            self.audio.menu_stop()
            self.state = "idle"
            return
        t = now - self._fade_started
        if t >= self.FADE_OUT_S:
            self.audio.menu_stop()
            self.state = "idle"
            return
        frac = 1.0 - (t / self.FADE_OUT_S)
        self.audio.menu_set_volume(self.volume() * self._fade_from * frac)

    def stop_now(self) -> None:
        """Hard stop, no fade. Used when the switch in Settings turns
        the playlist off."""
        if self.audio is not None:
            self.audio.menu_stop()
        self.state = "idle"
