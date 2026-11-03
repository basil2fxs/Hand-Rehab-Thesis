"""Spoken instructions, in the computer's own voice.

The one participant who played alone rated the on-screen instructions 2
of 5, and a patient after a stroke may read slowly or not see the card
well, so each game's instruction can also be said aloud when its GET
READY card opens (instructions.spoken in config/default.yaml, off for
the healthy study so its sittings stay as they ran).

The voice is the operating system's own, rendered to a file and played
through the game's mixer: macOS `say -o`, Windows' System.Speech, or
espeak-ng elsewhere. Nothing is shipped, so no voice licence travels
with the app, and `say` is never run without -o, which can leave macOS's
sound server stuck. A text is rendered once and kept in the temporary
folder. Every failure is quiet: the card still shows the words.
"""
from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

log = logging.getLogger(__name__)

# The card's own lines where the card has them (ui/screens.py
# GameplayScreen.GET_READY_LINES and RhythmScreen.GET_READY_LINES), and a
# line each for the games whose card shows only GET READY.
EXTRA_LINES = {
    "force_pilot": ("Press gently to fly the ship along the line,",
                    "and keep it inside the band."),
    "buzz_hunt": ("Feel for the buzz,",
                  "then press the finger that buzzed."),
    "syllables": ("Listen to each part of the word,",
                  "then press the finger under the part you heard."),
    "classic": ("Press the finger that lights up.",),
}

WORDS_PER_S = 2.5          # a slow, clear reading pace


def lines_for(mode: str) -> str | None:
    """The instruction for a game, as one sentence or two, or None."""
    try:
        from ..ui.screens import GameplayScreen, RhythmScreen
        table = dict(GameplayScreen.GET_READY_LINES)
        table["rhythm"] = RhythmScreen.GET_READY_LINES
    except Exception as e:                       # no pygame, no UI
        log.debug("instruction lines unavailable: %s", e)
        table = {}
    table.update({k: v for k, v in EXTRA_LINES.items() if k not in table})
    lines = table.get(mode)
    return " ".join(lines) if lines else None


def seconds_for(text: str) -> float:
    """About how long the text takes to say."""
    return len(text.split()) / WORDS_PER_S


def render_command(text: str, out: Path, platform: str | None = None) -> list[str] | None:
    """The command that writes `text` as a WAV file at `out`, or None when
    this computer has no voice the game knows how to use."""
    platform = platform or sys.platform
    if platform == "darwin":
        return ["say", "-o", str(out), "--file-format=WAVE", "--data-format=LEI16@22050", text]
    if platform.startswith("win"):
        quoted = text.replace("'", "''")
        script = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  f"$s.SetOutputToWaveFile('{out}'); $s.Speak('{quoted}'); $s.Dispose()")
        return ["powershell", "-NoProfile", "-NonInteractive", "-Command", script]
    for exe in ("espeak-ng", "espeak"):
        if shutil.which(exe):
            return [exe, "-w", str(out), text]
    return None


def render(text: str, folder: Path | None = None) -> Path | None:
    """The WAV file for `text`, rendering it the first time."""
    folder = folder or Path(tempfile.gettempdir()) / "finger_rehab_speech"
    out = folder / (hashlib.sha1(text.encode("utf-8")).hexdigest()[:16] + ".wav")
    if out.exists() and out.stat().st_size > 1000:
        return out
    cmd = render_command(text, out)
    if cmd is None:
        return None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as e:
        log.info("could not voice the instruction: %s", e)
        return None
    return out if out.exists() and out.stat().st_size > 1000 else None


class Speaker:
    """Says one instruction at a time, off the game loop's thread."""

    def __init__(self) -> None:
        self._sound = None
        self.last_text: str | None = None

    def speak(self, text: str) -> None:
        self.last_text = text
        threading.Thread(target=self._run, args=(text,), daemon=True).start()

    def _run(self, text: str) -> None:
        path = render(text)
        if path is None:
            return
        try:
            import pygame
            if not pygame.mixer.get_init():
                return
            self.stop()
            self._sound = pygame.mixer.Sound(str(path))
            self._sound.play()
        except Exception as e:
            log.info("could not play the instruction: %s", e)

    def stop(self) -> None:
        if self._sound is not None:
            try:
                self._sound.stop()
            except Exception:
                pass
            self._sound = None
