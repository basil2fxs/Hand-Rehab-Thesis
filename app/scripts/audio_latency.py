"""Measure this computer's sound and buzz delays and save them for the
game: rhythm.audio_offset_ms, rhythm.metronome_offset_ms,
latency.tone_ms and latency.buzzer_ms.

The same measurement runs from the app itself: Settings, Setup, Audio delay,
which is the way on a new computer (nothing to install). This script is
its command-line front end. How it measures is set out in
finger_rehab/audio/latency_measure.py.

    python3 app/scripts/audio_latency.py            measure and print
    python3 app/scripts/audio_latency.py --write    and save for the game
    python3 app/scripts/audio_latency.py --tap      time the microphone
                                                    by fingernail taps on
                                                    the index pad instead
                                                    (any OS; you tap)

--write saves config/latency_profile.yaml (per machine, never
committed), which the game lays over default.yaml at every start and
records in every block's config snapshot, so the analysis can see the
numbers were measured. Keep the room quiet and the volume where a
participant would have it; allow microphone access if macOS asks.
Re-run it on any other computer, or after changing the audio output.
A CSV of every take lands in config/calibration/.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from finger_rehab.audio.latency_measure import (  # noqa: E402,F401
    BOARD_DELAY_MS, CHUNK, MAX_LAG_S, SR, Board, Recorder, _envelope, _lag,
    _mic_onsets, averaged_onset_ms, coreaudio_input_ms, measure,
    write_profile, write_takes,
)

TRACK = APP / "assets" / "music" / "Easy_Lemon.mp3"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--takes", type=int, default=5)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--volume", type=float, default=0.4)
    ap.add_argument("--pulses", type=int, default=10,
                    help="per motor")
    ap.add_argument("--port", default=None, help="the hand board's port")
    ap.add_argument("--tap", action="store_true",
                    help="time the microphone by fingernail taps")
    ap.add_argument("--tap-seconds", type=float, default=20.0)
    ap.add_argument("--write", action="store_true",
                    help="save the result for the game")
    args = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.mixer.pre_init(SR, -16, 2, CHUNK)
    pygame.init()
    pygame.mixer.init()
    res = measure(TRACK, args.port, say=print, takes=args.takes,
                  seconds=args.seconds, volume=args.volume,
                  pulses=args.pulses, tap=args.tap,
                  tap_seconds=args.tap_seconds, find_board=True)
    pygame.quit()
    if res["mic_ms"] is None:
        print(res["problem"])
        return 1
    mic_ms, values = res["mic_ms"], res["values"]
    detail = res["detail"]
    print("\nresult (play call or STIM command to the sound leaving the "
          "device):")
    if "audio_offset_ms" in values:
        print(f"  rhythm.audio_offset_ms      {values['audio_offset_ms']:4d} "
              f"(song to microphone {detail['song_to_mic_median_ms']:.0f}, "
              f"less {mic_ms:.0f})")
    if "tone_ms" in values:
        print(f"  latency.tone_ms             {values['tone_ms']:4d} "
              f"(click to microphone "
              f"{detail['click_to_mic_median_ms']:.0f}, less {mic_ms:.0f})")
        print(f"  rhythm.metronome_offset_ms  {values['tone_ms']:4d} "
              f"(the same short-sound path)")
    if "buzzer_ms" in values:
        onsets = res["motors"]
        print(f"  latency.buzzer_ms           {values['buzzer_ms']:4d} "
              f"(motor onsets to microphone "
              + ", ".join(f"{k}: {v:.0f}" for k, v in onsets.items())
              + f", median less {mic_ms:.0f})")
    out = write_takes(res["rows"])
    if out is not None:
        print(f"\ntakes -> {out}")
    if args.write:
        if res["problem"]:
            print(res["problem"])
            return 1
        print(f"saved -> {write_profile(values, detail)}")
    else:
        print("Nothing saved; run with --write to save it for the game.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
