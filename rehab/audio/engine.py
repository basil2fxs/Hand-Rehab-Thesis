"""Audio engine wrapping pygame.mixer. Music playback + per-lane stim sounds
+ click track when no music file is provided."""
from __future__ import annotations

import logging
import math
import time
from pathlib import Path


log = logging.getLogger(__name__)


try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]


class AudioEngine:
    def __init__(self, master_volume: float = 0.8,
                 sample_rate: int = 44100) -> None:
        self.master_volume = master_volume
        self.sample_rate = sample_rate
        self._stim: list = []
        self._click = None
        # `_hit` is the soft confirmation chime that fires on a correct
        # press. Different tone from the metronome click so the patient
        # can hear "yes that landed" without it clashing with the music.
        self._hit = None
        self._song_path: str | None = None
        self._song_start_perf: float | None = None
        self._metronome_period: float | None = None
        self._next_metronome_t: float | None = None
        self._initialised = False

    def init(self) -> bool:
        if pygame is None:
            log.warning("pygame not available; audio disabled")
            return False
        self._stim = []
        self._click = None
        self._hit = None
        try:
            # pygame.init() (called earlier in engine.run) implicitly
            # initialises the mixer with platform defaults BEFORE we
            # reach this point. pygame.mixer.pre_init only affects the
            # NEXT mixer.init() call and a no-args mixer.init() no-ops
            # when the mixer is already up - so without this teardown
            # the 512-byte buffer is silently ignored and audio runs at
            # the default ~4096-byte latency, which is audible in rhythm
            # mode as a lag between visual note arrival and the hit chime.
            try:
                if pygame.mixer.get_init() is not None:
                    pygame.mixer.quit()
            except Exception:
                pass
            pygame.mixer.pre_init(self.sample_rate, -16, 2, 512)
            pygame.mixer.init()
            pygame.mixer.set_num_channels(16)
            # Per-lane tones kept around in case classic mode wants them
            # later, but on_stim doesn't play them anymore.
            freqs = [261.63, 329.63, 392.00, 523.25]   # C, E, G, C
            for f in freqs:
                self._stim.append(self._tone(f, 0.12))
            # High click for the metronome (when no music file is selected).
            self._click = self._tone(2000, 0.03, attack_s=0.001)
            # Softer, warmer confirmation chime. Two-note chord (C5 + E5,
            # a major third) with a slow attack and long release so it
            # blooms instead of beeping. Sits behind rhythm-mode music
            # rather than fighting it.
            self._hit = self._chord([523.25, 659.25], 0.18,
                                     attack_s=0.012, release_s=0.10)
            self._initialised = True
            return True
        except Exception as e:
            log.error("Audio init failed: %s", e)
            return False

    def shutdown(self) -> None:
        if pygame is None or not self._initialised:
            self._initialised = False
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
            pygame.mixer.quit()
        except Exception as e:
            log.debug("audio shutdown noise: %s", e)
        self._song_path = None
        self._song_start_perf = None
        self._metronome_period = None
        self._next_metronome_t = None
        self._initialised = False

    def play_song(self, path: str | Path, loops: int = 0,
                  start_s: float = 0.0) -> bool:
        """Play a song from `start_s` seconds in. start_s > 0 is used by the
        pause-resume path; behaviour depends on the audio format (OGG and
        WAV typically support seeking; MP3 is hit and miss with pygame)."""
        if not self._initialised or pygame is None:
            return False
        p = Path(path)
        if not p.exists():
            log.warning("Song not found: %s", p)
            return False
        try:
            pygame.mixer.music.load(str(p))
            pygame.mixer.music.set_volume(self.master_volume)
            pygame.mixer.music.play(loops=loops, start=max(0.0, start_s))
            self._song_path = str(p)
            # Adjust the song-start anchor so song_time() returns roughly
            # `start_s` seconds right away, keeping the visuals in sync with
            # what the user hears.
            self._song_start_perf = time.perf_counter() - max(0.0, start_s)
            # Disarm metronome if it was running.
            self._metronome_period = None
            self._next_metronome_t = None
            return True
        except Exception as e:
            log.warning("Could not play %s: %s", p, e)
            return False

    def start_metronome(self, bpm: float) -> None:
        if not self._initialised:
            return
        if pygame is not None:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._song_path = None
        self._metronome_period = 60.0 / max(bpm, 1.0)
        self._song_start_perf = time.perf_counter()
        self._next_metronome_t = self._metronome_period

    def stop(self) -> None:
        # Kill BOTH the music stream AND any in-flight channel sounds (click
        # track, per-lane stim tones). Before this fix, stop() only stopped
        # mixer.music, so click ticks queued just before the game ended kept
        # playing for a beat or two after results screen appeared.
        if pygame is not None and self._initialised:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            try:
                pygame.mixer.stop()
            except Exception:
                pass
        self._song_path = None
        self._song_start_perf = None
        self._metronome_period = None
        self._next_metronome_t = None

    @property
    def is_playing(self) -> bool:
        return self._song_start_perf is not None

    def song_time(self) -> float:
        if self._song_start_perf is None:
            return 0.0
        return time.perf_counter() - self._song_start_perf

    def tick(self) -> None:
        if not self._initialised or pygame is None:
            return
        if self._metronome_period is None or self._next_metronome_t is None:
            return
        t = self.song_time()
        # After a long stall (alt-tab, IO), don't burst dozens of catch-up clicks.
        if t - self._next_metronome_t > 5.0:
            self._next_metronome_t = t + self._metronome_period
            return
        while t >= self._next_metronome_t:
            self._play_click()
            self._next_metronome_t += self._metronome_period

    def play_stim(self, lane: int) -> None:
        # Kept for backwards compatibility but no longer called by the
        # engine. The per-lane tones were clashing with the rhythm music.
        if not self._initialised or not self._stim:
            return
        snd = self._stim[lane % len(self._stim)]
        if snd is not None:
            snd.set_volume(self.master_volume)
            snd.play()

    def play_hit(self) -> None:
        """Confirmation chime that fires when the patient lands a correct
        press. Drops volume even further when music is playing under it
        so the chime stays as a subtle 'yes that landed' cue instead of
        a beep that fights the song."""
        if not self._initialised or self._hit is None:
            return
        try:
            music_playing = (self._song_path is not None
                              and self._metronome_period is None)
            vol = self.master_volume * (0.25 if music_playing else 0.45)
            self._hit.set_volume(vol)
            self._hit.play()
        except Exception:
            pass

    def _play_click(self) -> None:
        if self._click is not None:
            self._click.set_volume(self.master_volume * 0.6)
            self._click.play()

    def _tone(self, freq: float, duration_s: float,
              attack_s: float = 0.005, release_s: float = 0.02):
        if pygame is None or np is None:
            return None
        sr = self.sample_rate
        n = max(1, int(duration_s * sr))
        t = np.linspace(0, duration_s, n, endpoint=False)
        wave = 0.6 * np.sin(2 * math.pi * freq * t).astype(np.float32)
        env = np.ones_like(wave)
        a = max(1, int(attack_s * sr))
        r = max(1, int(release_s * sr))
        env[:a] = np.linspace(0, 1, a)
        env[-r:] = np.linspace(1, 0, r)
        wave *= env
        stereo = np.stack([wave, wave], axis=1)
        pcm = (stereo * 32767).astype("int16")
        try:
            return pygame.sndarray.make_sound(pcm)
        except Exception:
            return None

    def _chord(self, freqs: list[float], duration_s: float,
                attack_s: float = 0.010, release_s: float = 0.08):
        """Sum several sine tones into a chord. Each note is half the
        amplitude of `_tone` so the sum stays below clipping. Gives a
        warmer "ding" than a single sine, which reads as confirmation
        without being as harsh as a beep."""
        if pygame is None or np is None:
            return None
        sr = self.sample_rate
        n = max(1, int(duration_s * sr))
        t = np.linspace(0, duration_s, n, endpoint=False)
        wave = np.zeros(n, dtype=np.float32)
        amp_per_note = 0.45 / max(1, len(freqs))
        for f in freqs:
            wave += amp_per_note * np.sin(2 * math.pi * f * t).astype(np.float32)
        env = np.ones_like(wave)
        a = max(1, int(attack_s * sr))
        r = max(1, int(release_s * sr))
        env[:a] = np.linspace(0, 1, a)
        env[-r:] = np.linspace(1, 0, r)
        wave *= env
        stereo = np.stack([wave, wave], axis=1)
        pcm = (stereo * 32767).astype("int16")
        try:
            return pygame.sndarray.make_sound(pcm)
        except Exception:
            return None
