"""Layout faults the rendered screens showed, held by tests.

scripts/make_screenshots.py renders every screen headless, and reading
those pictures turned up two faults: Echo's "Watch the echo..." chip
ran 11 px into the tallest tile and over the chevron bobbing above a
lit one, and Mirror's eight narrow tiles printed "Middle" smaller than
the names beside it. The script also had no Rhythm or Force Pilot
picture, so the README's two were copies nothing could rebuild.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

# The chevron over a lit tile starts 24 px above it and bobs 4 px
# either way, so its top can reach 28 px above the tile.
CHEVRON_REACH = 28


def setUpModule() -> None:
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    pygame.quit()


class MessageChipTests(unittest.TestCase):

    def _screen(self):
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        import finger_rehab.ui.screens as screens
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["audio"]["enabled"] = False
        cfg.data.setdefault("eeg", {})["enabled"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = {"gameplay": MagicMock(), "results": MagicMock()}
        eng.begin_adaptive_block()
        gp = screens.GameplayScreen(eng)
        gp._countdown_until = 0.0
        eng._screens["gameplay"] = gp
        return eng, gp, screens

    def test_the_chip_sits_between_the_score_and_a_lit_tallest_tile(self):
        eng, gp, screens = self._screen()
        tallest = min(gp.lanes, key=lambda ls: ls.rect.top)
        for ls in gp.lanes:
            ls.active = ls is tallest
        text = "Watch the echo..."
        gp.set_message(text, 5.0)
        gp._message_born = time.perf_counter() - 1.0   # past the pop-in
        chips, words = [], []
        real_chip, real_text = screens._chip, screens.draw_text

        def chip(surf, layout, centre, label, fg, **kw):
            chips.append((centre, label, kw))
            return real_chip(surf, layout, centre, label, fg, **kw)

        def draw_text(surf, label, pos, *a, **kw):
            words.append((label, pos, kw.get("pt")))
            return real_text(surf, label, pos, *a, **kw)

        with patch.object(screens, "_chip", chip), \
                patch.object(screens, "draw_text", draw_text):
            gp.draw(pygame.Surface((1280, 800)))
        (_, cy), _, kw = next(c for c in chips if c[1] == text)
        h = gp.layout.font(kw["font_pt"]).size(text)[1] + 2 * kw["pad_y"]
        score = str(eng.score)
        _, (_, sy), spt = next(w for w in words if w[0] == score)
        score_bottom = sy + gp.layout.font(spt).size(score)[1] / 2
        self.assertGreaterEqual(cy - h / 2, score_bottom)
        self.assertLessEqual(cy + h / 2, tallest.rect.top - CHEVRON_REACH)

    def test_reactions_bigger_chip_clears_the_tile_row(self):
        """Reaction draws no chevron, so its chip only has to clear
        the tallest tile itself."""
        _, gp, screens = self._screen()
        top = min(ls.rect.top for ls in gp.lanes)
        pt, cy, _, pad_y = screens.GameplayScreen._msg_chip_place("reaction")
        h = gp.layout.font(pt).size("Ready")[1] + 2 * pad_y
        self.assertLessEqual(cy + h / 2, top)


class TileLabelTests(unittest.TestCase):

    def test_a_row_prints_every_name_at_one_size(self):
        from finger_rehab.ui import theme as th
        from finger_rehab.ui.widgets import LaneStrip, Layout
        layout = Layout(1280, 800)
        t = next(iter(th.THEMES.values()))
        # 120 px is a Mirror tile, eight across; 265 px a one-hand tile.
        for width in (120, 150, 265):
            sizes = {LaneStrip(f, pygame.Rect(0, 0, width, 400), t, layout,
                               finger=f).label_pt() for f in range(4)}
            self.assertEqual(len(sizes), 1, (width, sizes))
            pt = sizes.pop()
            for name in LaneStrip.FINGER_LABELS:
                self.assertLessEqual(layout.font(pt).size(name)[0],
                                     width - 20, (width, name))
        wide = LaneStrip(0, pygame.Rect(0, 0, 265, 400), t, layout)
        self.assertEqual(wide.label_pt(), 32)


class ScreenshotScriptTests(unittest.TestCase):

    def test_every_readme_screen_is_rendered_by_the_script(self):
        """Every game screen a README shows comes out of the script, so
        a UI change can always be re-shot. The two analysis figures are
        the notebook's, from a simulated cohort."""
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import make_screenshots
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        text = "".join(p.read_text(encoding="utf-8") for p in (
            ROOT.parent / "README.md",
            ROOT / "finger_rehab" / "ui" / "README.md"))
        shown = set(re.findall(r"docs/images/([a-z_]+)\.png", text))
        shown -= {"analysis_norms", "analysis_reliability"}
        self.assertEqual(shown - set(make_screenshots.NAMES), set())
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ, SDL_VIDEODRIVER="dummy",
                       SDL_AUDIODRIVER="dummy")
            run = subprocess.run(
                [sys.executable, "scripts/make_screenshots.py", "--out", td],
                cwd=ROOT, env=env, capture_output=True, text=True,
                timeout=300)
            self.assertEqual(run.returncode, 0, run.stderr[-2000:])
            made = {p.stem for p in Path(td).glob("*.png")}
        self.assertEqual(set(make_screenshots.NAMES) - made, set())


if __name__ == "__main__":
    unittest.main()
