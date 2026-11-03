"""The screen's delay read off a slow-motion clip (scripts/clip_delay.py).

The tool times each LED flash and the tile's next change to a fraction of
a frame, from where the brightness crosses halfway. Pinned here on
brightness series with a known delay, each frame the mean light over its
whole exposure as a camera records it, and, when ffmpeg is installed, on
a clip coded with x264 as a phone stores it.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import clip_delay  # noqa: E402

FPS = 240.0


def _frames(delay_ms: float, rng, pulses: int = 12) -> tuple[np.ndarray, np.ndarray]:
    """LED lit 20 ms at each command, tile white from delay_ms after it for
    300 ms, both as the mean light over each frame, 0 to 255, with noise."""
    n = int((pulses + 1.5) * FPS)
    sub = 16
    tt = (np.arange(n * sub) + 0.5) / (FPS * sub)
    led, tile = np.zeros_like(tt), np.zeros_like(tt)
    for k in range(pulses):
        c = 0.5 + k + rng.uniform(0.0, 1.0 / FPS)
        led[(tt >= c) & (tt < c + 0.020)] = 1.0
        tile[(tt >= c + delay_ms / 1000.0) & (tt < c + 0.300 + delay_ms / 1000.0)] = 1.0
    noise = lambda: rng.normal(0.0, 3.0, n)  # noqa: E731
    return (30.0 + 200.0 * led.reshape(n, sub).mean(axis=1) + noise(),
            30.0 + 200.0 * tile.reshape(n, sub).mean(axis=1) + noise())


class ClipDelayTests(unittest.TestCase):

    def test_a_planted_delay_is_read_to_a_fraction_of_a_frame(self):
        for planted in (8.0, 10.0, 23.0, 40.0, 75.0):
            led, tile = _frames(planted, np.random.default_rng(int(planted)))
            got = clip_delay.delays_ms(led, tile, FPS)
            self.assertEqual(len(got), 12, planted)
            # a whole frame is 4.2 ms; the halfway crossing reads well inside it
            self.assertLess(abs(float(np.median(got)) - planted), 0.5, planted)

    def test_a_flash_with_no_tile_change_gives_nothing(self):
        led, _ = _frames(20.0, np.random.default_rng(1))
        flat = np.full_like(led, 30.0)
        self.assertEqual(clip_delay.delays_ms(led, flat, FPS), [])

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs ffmpeg")
    def test_the_command_line_reads_a_coded_clip(self):
        led, tile = _frames(23.0, np.random.default_rng(7))
        h, w = 64, 96
        frames = np.full((len(led), h, w), 30.0)
        frames[:, 8:16, 8:16] = led[:, None, None]
        frames[:, 16:48, 48:80] = tile[:, None, None]
        raw = np.clip(frames, 0, 255).astype(np.uint8).tobytes()
        with tempfile.TemporaryDirectory() as d:
            clip, out = Path(d) / "clip.mp4", Path(d) / "out.json"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray",
                            "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                            "-crf", "12", "-pix_fmt", "yuv420p", str(clip)], input=raw, check=True)
            rc = clip_delay.main([str(clip), "--led", "8,8,8,8", "--tile", "48,16,32,32",
                                  "--fps", str(FPS), "--json", str(out)])
            self.assertEqual(rc, 0)
            res = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(res["pulses"], 12)
        self.assertLess(abs(res["median_ms"] - 23.0), 1.0)


if __name__ == "__main__":
    unittest.main()
