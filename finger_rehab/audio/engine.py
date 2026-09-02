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
                 sample_rate: int = 44100,
                 cue_volume: float = 1.0,
                 feedback_volume: float = 1.0) -> None:
        # master scales the whole game. cue is the pre-press click track,
        # feedback is the post-press hit / miss chime. Final volume of a
        # sound is master x category x trial_gain x a fixed per-sound
        # factor (see _cue_vol / _feedback_vol).
        self.master_volume = master_volume
        self.cue_volume = cue_volume
        self.feedback_volume = feedback_volume
        # Transient per-trial loudness multiplier. The game engine raises
        # this above 1.0 on the small fraction of "loud" trials and resets
        # it to 1.0 when the trial ends, so the cue + feedback are slightly
        # louder on those trials. Programmatic, not a manual setting.
        self.trial_gain = 1.0
        self.sample_rate = sample_rate
        self._stim: list = []
        self._click = None
        # `_hit` is the soft confirmation chime that fires on a correct
        # press. Different tone from the metronome click so the patient
        # can hear "yes that landed" without it clashing with the music.
        self._hit = None
        # Pre-rendered chime scale used in rhythm mode. Each entry is
        # the same chord transposed up by N semitones. play_hit picks
        # which one based on the caller's combo so a streak rises in
        # pitch like Beat Saber / Guitar Hero.
        self._hit_scale: list = []
        # Low "thunk" sound used as a combo-break / miss cue.
        self._miss_thunk = None
        self._song_path: str | None = None
        self._song_start_perf: float | None = None
        self._metronome_period: float | None = None
        self._next_metronome_t: float | None = None
        # Whether the mixer.music stream currently belongs to the MENU
        # playlist rather than to a game. There is only one music
        # stream, so this flag is how the two users stay out of each
        # other's way: the menu player refuses to start while a game
        # owns the stream (see menu_play), and every game-side entry
        # point (play_song, start_metronome, stop) takes the stream
        # back by clearing the flag.
        self._menu_active = False
        # Same idea for the Force Pilot background track; see the
        # block_music_* methods at the end.
        self._block_music_active = False
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
            # Per-lane cue tones (C E G C). on_stim_multi plays the
            # lowest target lane's tone on every stim while
            # cue.sound_before is on.
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
            # Combo-pitched chime scale. Each step transposes the base
            # C5 + E5 chord up by 2 semitones (whole-tone steps so the
            # ladder sounds bright + uplifting rather than chromatic).
            # 6 levels covers streaks 0..50+ with each tier feeling
            # noticeably higher than the last.
            self._hit_scale = []
            for step in range(6):
                ratio = 2 ** (step * 2 / 12.0)
                self._hit_scale.append(self._chord(
                    [523.25 * ratio, 659.25 * ratio], 0.18,
                    attack_s=0.012, release_s=0.10,
                ))
            # Combo-break thunk: low chord with no upper note, snappy
            # attack, short release. Used on miss to give the patient
            # a soft "ah, missed that one" cue without being harsh.
            self._miss_thunk = self._chord(
                [98.00, 130.81], 0.20,
                attack_s=0.005, release_s=0.14,
            )
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
        self._menu_active = False
        self._block_music_active = False
        self._initialised = False

    @staticmethod
    def _clamp01(v: float) -> float:
        # pygame set_volume expects 0..1. trial_gain can push a level
        # above 1.0, so clamp before handing it over.
        return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

    def _cue_vol(self, local: float = 1.0) -> float:
        """Effective volume for a pre-press cue (metronome click, stim
        tone): master x cue x trial_gain x local, clamped to 0..1."""
        return self._clamp01(self.master_volume * self.cue_volume
                              * self.trial_gain * local)

    def _feedback_vol(self, local: float = 1.0) -> float:
        """Effective volume for a post-press feedback sound (hit chime,
        miss thunk): master x feedback x trial_gain x local, clamped."""
        return self._clamp01(self.master_volume * self.feedback_volume
                             * self.trial_gain * local)

    def set_trial_gain(self, gain: float) -> None:
        """Set the transient per-trial loudness multiplier (1.0 = normal).
        Called by the game engine: raised on a loud trial, reset to 1.0
        when the trial ends."""
        self.trial_gain = max(0.0, float(gain))

    def set_volumes(self, master: float | None = None,
                    cue: float | None = None,
                    feedback: float | None = None) -> None:
        """Update one or more base levels (0..1) live from the Settings
        screen. Re-applies the music stream volume so a song already
        playing follows the change; discrete cue / feedback sounds read
        the current levels at play time so they need no refresh."""
        if master is not None:
            self.master_volume = self._clamp01(master)
        if cue is not None:
            self.cue_volume = self._clamp01(cue)
        if feedback is not None:
            self.feedback_volume = self._clamp01(feedback)
        if (self._initialised and pygame is not None
                and self._song_path is not None):
            try:
                pygame.mixer.music.set_volume(self._clamp01(self.master_volume))
            except Exception:
                pass

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
            # Music rides the whole-game master level. The cue / feedback
            # sliders shape the discrete click + chime sounds, not the
            # backing track.
            pygame.mixer.music.set_volume(self._clamp01(self.master_volume))
            pygame.mixer.music.play(loops=loops, start=max(0.0, start_s))
            # The game owns the one music stream from here; any menu
            # or block track that was on it has just been replaced.
            self._menu_active = False
            self._block_music_active = False
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

    def start_metronome(self, bpm: float,
                        first_click_in_s: float | None = None) -> None:
        """Start the click track. `first_click_in_s` schedules the
        first click that many seconds from now instead of one full
        period out. A restart (rhythm resume) needs it: this method
        resets the click phase, so without it the clicks after a pause
        land up to half a period away from the beats the game scores,
        and the patient spends the rest of the block hearing one grid
        while being marked against another."""
        if not self._initialised:
            return
        if pygame is not None:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        self._song_path = None
        self._menu_active = False
        self._block_music_active = False
        self._metronome_period = 60.0 / max(bpm, 1.0)
        self._song_start_perf = time.perf_counter()
        if first_click_in_s is not None and first_click_in_s > 0:
            self._next_metronome_t = float(first_click_in_s)
        else:
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
        self._menu_active = False
        self._block_music_active = False

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
        # The pre-press cue tone. Called from on_stim_multi on every
        # stim in every mode while cue.sound_before is on, once per
        # stim (the lowest target lane in a multi-lane cue).
        if not self._initialised or not self._stim:
            return
        snd = self._stim[lane % len(self._stim)]
        if snd is not None:
            snd.set_volume(self._cue_vol())
            snd.play()

    def play_hit(self, combo: int = 0) -> None:
        """Confirmation chime that fires when the patient lands a correct
        press. Drops volume when music is playing under it so the chime
        stays as a subtle 'yes that landed' cue rather than a beep that
        fights the song. `combo` lifts the pitch up the pre-rendered
        scale at thresholds 3 / 6 / 10 / 15 / 25 so a long streak rises
        in pitch the way a rhythm game should."""
        if not self._initialised:
            return
        try:
            music_playing = (self._song_path is not None
                              and self._metronome_period is None)
            vol = self._feedback_vol(0.30 if music_playing else 0.50)
            # Pick which chime step matches the combo.
            sample = self._hit
            if self._hit_scale:
                # Thresholds: 0+, 3+, 6+, 10+, 15+, 25+.
                if combo >= 25:
                    sample = self._hit_scale[5]
                elif combo >= 15:
                    sample = self._hit_scale[4]
                elif combo >= 10:
                    sample = self._hit_scale[3]
                elif combo >= 6:
                    sample = self._hit_scale[2]
                elif combo >= 3:
                    sample = self._hit_scale[1]
                else:
                    sample = self._hit_scale[0]
            if sample is not None:
                sample.set_volume(vol)
                sample.play()
        except Exception:
            pass

    def play_miss(self) -> None:
        """Low combo-break thunk. Played after a miss that breaks a
        streak so the patient has a clear aural cue something went
        wrong, without it being harsh or punishing."""
        if not self._initialised or self._miss_thunk is None:
            return
        try:
            music_playing = (self._song_path is not None
                              and self._metronome_period is None)
            vol = self._feedback_vol(0.25 if music_playing else 0.45)
            self._miss_thunk.set_volume(vol)
            self._miss_thunk.play()
        except Exception:
            pass

    # ---- menu music -------------------------------------------------------
    # The menu playlist and the game share the ONE mixer.music stream,
    # so these four methods are written so the menu side can never win
    # a fight over it: menu_play refuses while a game song or the
    # metronome is live, and the game-side entry points above reclaim
    # the stream by clearing _menu_active. The player that drives them
    # (audio/menu_music.py) decides WHEN menu music should run; this
    # layer only guarantees it cannot run over gameplay audio.

    def game_stream_active(self) -> bool:
        """Whether gameplay owns the music stream right now (a rhythm
        song is loaded or the metronome is clicking)."""
        return (self._song_path is not None
                or self._metronome_period is not None)

    def menu_play(self, path: str | Path, volume: float = 1.0) -> bool:
        """Start one menu track at `volume` (0..1, scaled by master).
        Returns False without touching the mixer when the engine is
        not initialised, the file is missing, or gameplay owns the
        stream."""
        if not self._initialised or pygame is None:
            return False
        if self.game_stream_active():
            return False
        p = Path(path)
        if not p.exists():
            log.warning("Menu track not found: %s", p)
            return False
        try:
            pygame.mixer.music.load(str(p))
            pygame.mixer.music.set_volume(
                self._clamp01(self.master_volume * volume))
            pygame.mixer.music.play()
            self._menu_active = True
            return True
        except Exception as e:
            log.warning("Could not play menu track %s: %s", p, e)
            self._menu_active = False
            return False

    def menu_stop(self) -> None:
        """Stop the menu track. Touches the mixer only while the menu
        still owns the stream, so a game song that took over is never
        stopped from here."""
        was_ours = self._menu_active
        self._menu_active = False
        if not was_ours or pygame is None or not self._initialised:
            return
        if self.game_stream_active():
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def menu_set_volume(self, volume: float) -> None:
        """Live level for the playing menu track (0..1 on top of
        master). No-op unless the menu owns the stream."""
        if (not self._menu_active or pygame is None
                or not self._initialised or self.game_stream_active()):
            return
        try:
            pygame.mixer.music.set_volume(
                self._clamp01(self.master_volume * volume))
        except Exception:
            pass

    def menu_busy(self) -> bool:
        """Whether the menu track is still sounding. False the moment
        a game takes the stream or the track runs out."""
        if (not self._menu_active or pygame is None
                or not self._initialised or self.game_stream_active()):
            return False
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    # ---- block background music --------------------------------------
    # The Force Pilot background track (audio/block_music.py) is the
    # one piece of music allowed under a block, and it rides the same
    # single stream. It is kept apart from the menu flag so the menu
    # player's fade-out can never stop it and it can never be mistaken
    # for a menu track. It yields to the game exactly as the menu does:
    # play_song / start_metronome / stop all clear the flag, and it
    # refuses to start while a rhythm song or the metronome is live.

    def block_music_play(self, path: str | Path, volume: float = 1.0
                         ) -> bool:
        if not self._initialised or pygame is None:
            return False
        if self.game_stream_active():
            return False
        p = Path(path)
        if not p.exists():
            log.warning("Block track not found: %s", p)
            return False
        try:
            pygame.mixer.music.load(str(p))
            pygame.mixer.music.set_volume(
                self._clamp01(self.master_volume * volume))
            pygame.mixer.music.play()
            self._menu_active = False
            self._block_music_active = True
            return True
        except Exception as e:
            log.warning("Could not play block track %s: %s", p, e)
            self._block_music_active = False
            return False

    def block_music_stop(self) -> None:
        was_ours = getattr(self, "_block_music_active", False)
        self._block_music_active = False
        if not was_ours or pygame is None or not self._initialised:
            return
        if self.game_stream_active():
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def block_music_set_volume(self, volume: float) -> None:
        """Live level for the block track (0..1 on top of master).
        No-op unless the block track owns the stream."""
        if (not getattr(self, "_block_music_active", False)
                or pygame is None or not self._initialised
                or self.game_stream_active()):
            return
        try:
            pygame.mixer.music.set_volume(
                self._clamp01(self.master_volume * volume))
        except Exception:
            pass

    def block_music_busy(self) -> bool:
        if (not getattr(self, "_block_music_active", False)
                or pygame is None or not self._initialised
                or self.game_stream_active()):
            return False
        try:
            return bool(pygame.mixer.music.get_busy())
        except Exception:
            return False

    def _play_click(self) -> None:
        if self._click is not None:
            self._click.set_volume(self._cue_vol(0.6))
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
