"""Read the screen's delay off a slow-motion phone clip.

scripts/latency_check.py --display fills a screen tile white on the frame
it sends each STIM to the board and black with the STOP, so in a phone
clip at 240 fps that frames the Nano's RX LED and the tile, the LED lights
when the command arrives and the tile changes when the screen shows it.
Counting those frames by hand is slow and reads to a whole frame (4.2 ms).
This reads the brightness of the two patches in every frame, finds each
LED flash and the tile's next change, and times both to a fraction of a
frame from where the brightness crosses halfway, since a camera frame
that straddles a change catches it part bright.

    python3 scripts/clip_delay.py CLIP.mp4 --led X,Y,W,H --tile X,Y,W,H
    python3 scripts/clip_delay.py CLIP.mp4 --led ... --tile ... --fps 240 --json out.json

X,Y,W,H is a patch in the clip's pixels, from the top left. --fps is read
from the clip when it is left out; phones often store a slow-motion clip
at 30 fps, so give the capture rate when the clip plays slowed. The delay
printed is the tile change after the LED flash, the display's delay plus
the gap from the flip to the command, which latency_check.py prints and
which is under 1 ms. analysis/timing_tools_sim.py checks this on
synthetic clips with a known delay.

Needs ffmpeg on the PATH.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np


def _rect(text: str) -> tuple[int, int, int, int]:
    x, y, w, h = (int(v) for v in text.split(","))
    if w < 1 or h < 1:
        raise argparse.ArgumentTypeError("a patch needs a width and a height")
    return x, y, w, h


def clip_fps(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=avg_frame_rate", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    num, _, den = out.partition("/")
    return float(num) / float(den or 1)


def patch_brightness(path: Path, rect: tuple[int, int, int, int]) -> np.ndarray:
    """Mean grey level of one patch in every frame, 0 to 255."""
    x, y, w, h = rect
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-vf", f"crop={w}:{h}:{x}:{y},format=gray,scale=1:1:flags=area",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.uint8).astype(float)


def rising_edges(b: np.ndarray) -> list[float]:
    """Frame positions, to a fraction of a frame, where the brightness
    rises through halfway between its dark and bright levels."""
    # an LED lit for 20 ms a second is bright in about one frame in fifty,
    # so the bright level is read near the top of the range, not at a decile
    lo, hi = np.percentile(b, 5), np.percentile(b, 99.5)
    if hi - lo < 10:
        return []
    mid = (lo + hi) / 2.0
    out = []
    for k in range(1, len(b)):
        if b[k - 1] < mid <= b[k]:
            out.append(k - 1 + (mid - b[k - 1]) / (b[k] - b[k - 1]))
    return out


def delays_ms(led: np.ndarray, tile: np.ndarray, fps: float,
              max_ms: float = 250.0) -> list[float]:
    """For each LED flash, the tile's next rise within max_ms, in ms."""
    tiles = rising_edges(tile)
    out = []
    for f in rising_edges(led):
        nxt = [t for t in tiles if f <= t <= f + max_ms * fps / 1000.0]
        if nxt:
            out.append((nxt[0] - f) * 1000.0 / fps)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clip", type=Path)
    ap.add_argument("--led", type=_rect, required=True, help="the RX LED's patch, X,Y,W,H")
    ap.add_argument("--tile", type=_rect, required=True, help="the screen tile's patch, X,Y,W,H")
    ap.add_argument("--fps", type=float, help="the capture rate, if the clip plays slowed")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    if not shutil.which("ffmpeg"):
        print("ffmpeg is not on the PATH", file=sys.stderr)
        return 1
    fps = args.fps or clip_fps(args.clip)
    d = delays_ms(patch_brightness(args.clip, args.led), patch_brightness(args.clip, args.tile), fps)
    if not d:
        print("no LED flash was followed by a tile change; check the two patches", file=sys.stderr)
        return 1
    res = {"pulses": len(d), "median_ms": float(np.median(d)),
           "iqr_ms": [float(np.percentile(d, 25)), float(np.percentile(d, 75))],
           "min_ms": float(min(d)), "max_ms": float(max(d)), "fps": fps}
    print(f"{len(d)} pulses at {fps:.0f} fps: tile {res['median_ms']:.1f} ms after the LED "
          f"(interquartile {res['iqr_ms'][0]:.1f} to {res['iqr_ms'][1]:.1f}, "
          f"{res['min_ms']:.1f} to {res['max_ms']:.1f})")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
