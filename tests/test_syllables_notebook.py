"""The Syllables chapter of the notebook, on a block the REAL mode wrote.

The mode changed from tapping the beats inside a word to picking the
written syllable out of four falling options, so one trials.csv row is
now one option SET and the stimulus carries a different set of keys.
What this pins is that the notebook's parser reads back exactly what
SyllablesMode._pack_stimulus wrote, that the chance line and the
staircase target are actually drawn, that a session from the old
tapping design still renders through the legacy chapter, and above all
that the two designs are never pooled: they are different tasks and no
measure survives the change.

The session folder is written by the REAL GameEngine and SyllablesMode
through the real TrialLogger, then handed to the REAL notebook
functions, the same path tests/test_echo_notebook_span.py walks.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_ra():
    """Every notebook cell's definitions in one module namespace."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_syllables"
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in _code_cells():
            code = compile(_definitions(index, lines),
                           f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())

    class _Live:
        def __init__(self, d):
            self.__dict__ = d

    return _Live(ns)


def _run_choice_block(root: Path, words: int = 3) -> Path:
    """One real syllables block, every set answered on the target lane
    after the lockout. The driver is tests/test_syllables_eeg.py's,
    with the session left on disk for the notebook to read."""
    import pygame
    pygame.init()
    try:
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.fsr_detector import PressEvent
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = str(root)
        cfg.data["report"] = {"enabled": False}
        cfg.data["syllables"]["speech"] = {"backend": "off"}
        cfg.data["syllables"]["words_per_block"] = words
        cfg.data["syllables"]["warmup_taps"] = 0
        cfg.data["syllables"]["break_s"] = 0
        cfg.data["syllables"]["seed"] = 21
        eng = GameEngine(cfg, KeyboardOnlySource())
        gp = MagicMock()
        gp.lanes = []
        # Real screens are not built here (the block is driven by
        # hand); the engine only needs somewhere to point.
        eng._screens = {name: MagicMock() for name in
                        ("results", "syllables", "mode_select",
                         "title", "login", "calibration")}
        eng._screens["gameplay"] = gp
        eng.show_results = lambda: None
        eng.begin_session("SylNb", "9", dominant_hand="right", visit="")
        eng.begin_syllables_block()
        mode = eng.mode
        folder = Path(eng.session_paths.root)
        answered: set = set()
        vt = 1000.0
        for _ in range(60000):
            if mode.phase == "done":
                break
            vt += 1.0 / 120.0
            mode._tick(vt)
            if (mode.phase == "choose" and mode.option_set is not None
                    and mode._set_close_t is None):
                key = (mode.word.word, mode.pos, mode.ret,
                       mode.trial_counter)
                if vt >= mode._spawn_t + 0.4 and key not in answered:
                    answered.add(key)
                    mode.queue_press(PressEvent(
                        lane=mode.option_set.target_lane, t_perf=vt,
                        value=0, baseline=0.0, hand=mode.word_hand))
        eng.finish_block()
        eng.end_session()
        return folder
    finally:
        pygame.quit()


def _legacy_frame(ra):
    """A one-row trials frame in the OLD tapping shape: taps= and lvl=,
    no opts=, which is what every session before the rework carries."""
    import pandas as pd
    return pd.DataFrame([{
        "mode": "syllables", "session": "old", "game": "old_game",
        "hand_mode": "right", "trial": 1, "block": 1,
        "stimulus": ("butter;lvl=2;band=A;nsyll=2;stress=0;map=off0;"
                     "paced=0;taps=1:120.0:,2:410.0:;err=ok;streak=1"),
        "time_difference_ms": 120.0, "early_late": "", "error_type": "",
    }])


class SyllablesChoiceChapterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        cls.folder = _run_choice_block(Path(cls._td.name))
        cls.ra = _load_ra()
        cat = cls.ra.build_catalogue(root=cls._td.name)
        folders = [Path(p) for p in cat["folder"]]
        cls.trials = cls.ra.load_games(folders, cat)
        cls.metas = cls.ra.load_metas(folders)
        cls.sets = cls.ra.syllable_set_frame(cls.trials)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()
        import matplotlib.pyplot as plt
        plt.close("all")

    def test_the_parser_reads_back_what_the_mode_wrote(self) -> None:
        from tests.test_syllables_mode import _parse_stimulus
        rows = self.trials[self.trials["mode"] == "syllables"]
        self.assertTrue(len(rows))
        self.assertEqual(len(self.sets), len(rows))
        for (_i, raw), (_j, got) in zip(rows.iterrows(),
                                        self.sets.iterrows()):
            kv = _parse_stimulus(raw["stimulus"])
            self.assertEqual(got["word"], raw["stimulus"].split(";")[0])
            self.assertEqual(int(got["pos"]), int(kv["pos"]))
            self.assertEqual(int(got["nsyll"]), int(kv["nsyll"]))
            self.assertEqual(int(got["tlane"]), int(kv["tlane"]))
            self.assertEqual(got["first"], kv["first"])
            self.assertEqual(got["err"], kv["err"])
            self.assertEqual(got["syl"], kv["syl"])
            # _parse_stimulus already unpacks opts into tuples; the
            # notebook's parser must agree lane for lane.
            self.assertEqual(got["opts"], kv["opts"])
            self.assertEqual(got["n_options"], len(kv["opts"]))
            kinds = [k for _l, _t, k in got["opts"]]
            self.assertEqual(kinds.count("target"), 1)

    def test_every_set_was_answered_on_the_target(self) -> None:
        self.assertTrue(self.sets["first_ok"].all())
        self.assertEqual(set(self.sets["err"]), {"ok"})
        words = self.ra.syllable_word_frame(self.sets)
        self.assertTrue(words["completed"].all())
        self.assertEqual(set(words["outcome"]), {"Great"})

    def test_the_chance_line_and_the_target_are_drawn(self) -> None:
        drawn = []
        real = self.ra.plt.Axes.axhline

        def spy(self_ax, y=0, *a, **kw):
            drawn.append(round(float(y), 3))
            return real(self_ax, y, *a, **kw)

        self.ra.plt.Axes.axhline = spy
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                out = self.ra.sec_syllables(self.trials, self.metas)
        finally:
            self.ra.plt.Axes.axhline = real
        self.assertIn(0.25, drawn)      # chance with four options
        self.assertIn(0.8, drawn)       # the staircase target
        text = buf.getvalue()
        self.assertIn("chance 25 percent with 4 options", text)
        self.assertIn("WHAT THIS CHAPTER CANNOT SAY", text)
        self.assertIn("sets", out)
        self.assertIn("words", out)

    def test_a_legacy_tapping_session_still_renders(self) -> None:
        import pandas as pd
        legacy = _legacy_frame(self.ra)
        choice, tapping = self.ra.syllable_rows(legacy)
        self.assertTrue(choice.empty)
        self.assertEqual(len(tapping), 1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ra.sec_syllables(legacy, {})
        text = buf.getvalue()
        self.assertIn("SYLLABLE BEATS (legacy tapping design)", text)
        # The choice parser reads nothing out of a legacy row.
        self.assertTrue(self.ra.syllable_set_frame(legacy).empty)

    def test_a_windowless_legacy_row_does_not_kill_the_chapter(self):
        """A selection holding windowed and pre-window tapping rows
        makes the off column a float, so a windowless row arrives as
        NaN. int(nan) used to take the whole chapter down."""
        import pandas as pd
        ra = self.ra
        windowed = _legacy_frame(ra)
        plain = _legacy_frame(ra)
        plain.loc[0, "stimulus"] = plain.loc[0, "stimulus"].replace(
            "map=off0;", "")
        mixed = pd.concat([windowed, plain], ignore_index=True)
        sy = ra.syllable_frame_legacy(mixed)
        self.assertEqual(len(sy), 2)
        self.assertTrue(sy["off"].isna().any())
        lanes = [ra.syllable_expected_lanes(r) for _i, r in sy.iterrows()]
        self.assertEqual(lanes, [[1, 2], None])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ra.sec_syllables(mixed, {})
        self.assertIn("SYLLABLE BEATS (legacy tapping design)",
                      buf.getvalue())

    def test_the_two_designs_are_never_pooled(self) -> None:
        import pandas as pd
        mixed = pd.concat([self.trials, _legacy_frame(self.ra)],
                          ignore_index=True)
        choice, tapping = self.ra.syllable_rows(mixed)
        self.assertEqual(len(tapping), 1)
        self.assertEqual(len(choice), len(self.sets))
        # The choice charts count only the choice rows.
        self.assertEqual(len(self.ra.syllable_set_frame(mixed)),
                         len(self.sets))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = self.ra.sec_syllables(mixed, self.metas)
        text = buf.getvalue()
        self.assertIn("1 row(s) from the tapping design", text)
        self.assertIn("nothing in", text)
        self.assertIn("legacy", out)
        self.assertEqual(len(out["sets"]), len(self.sets))


if __name__ == "__main__":
    unittest.main()
