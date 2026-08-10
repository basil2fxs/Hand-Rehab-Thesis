"""The notebook and the game have to agree about the CSV.

They are two separate programs sharing a file format, and nothing links
them at import time, so a column renamed on the game side goes unnoticed
until someone opens the notebook weeks later and finds a section quietly
reporting nothing. That happened once already: cue_mode became cue_flags
and the cue comparison went silent rather than failing.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from rehab.data.logger import TRIAL_COLUMNS, RAW_COLUMNS


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "analysis" / "session_analysis.ipynb"


def _notebook_source() -> str:
    nb = json.loads(NOTEBOOK.read_text())
    out = []
    for cell in nb["cells"]:
        if cell["cell_type"] != "code":
            continue
        for line in cell["source"]:
            out.append("" if line.lstrip().startswith(("%", "!")) else line)
        out.append("\n")
    return "".join(out)


@pytest.fixture(scope="module")
def source() -> str:
    return _notebook_source()


class TestColumnsTheNotebookNeeds:
    # Columns the notebook cannot do its job without. Each is read by a
    # named section, so losing one silently disables that section.
    REQUIRED = [
        ("time_difference_ms", "reaction time and rhythm offsets"),
        ("lane", "everything per finger"),
        ("early_late", "hit and miss split"),
        ("block", "which mode a trial came from"),
        ("participant", "grouping by person"),
        ("peak_force_n", "force"),
        ("impulse_n", "force over the press"),
        ("force_window_sum", "miss force"),
        ("force_window_peaks", "individuation"),
        ("cue_flags", "the cue comparison"),
        ("cue_target_shown", "the tactile-only condition"),
        ("stim_delivered", "excluding trials whose cue never arrived"),
        ("timeout_ms", "the response window"),
        ("phase", "pretest against aftertest"),
        ("hand", "left against right"),
        ("mirror_right_rt_ms", "mirror mode's right-hand press latency"),
        ("mirror_left_rt_ms", "mirror mode's left-hand press latency"),
        ("stimulus", "the packed per-trial detail of the newer modes"),
        ("pattern_trial", "trained against probe trials in pattern mode"),
        ("waveform", "which trajectory a continuous-force trial ran"),
        ("waveform_params", "the numbers that rebuild that trajectory"),
        ("waveform_seed", "regenerating pseudorandom sections exactly"),
        ("segment_times", "cutting raw traces into scored windows"),
    ]

    @pytest.mark.parametrize("column,why", REQUIRED)
    def test_the_game_still_writes_it(self, column, why):
        assert column in TRIAL_COLUMNS, (
            f"the game stopped writing {column!r}, which the notebook "
            f"uses for {why}")

    @pytest.mark.parametrize("column,why", REQUIRED)
    def test_the_notebook_still_reads_it(self, column, why, source):
        assert f'"{column}"' in source or f"'{column}'" in source, (
            f"the notebook stopped reading {column!r} ({why}), so that "
            f"section is now silent on real data")


class TestRawStreamColumns:
    @pytest.mark.parametrize("column", ["t_perf", "fsr1", "fsr4", "event",
                                        "lane", "hand"])
    def test_raw_columns_the_onset_section_needs(self, column):
        assert column in RAW_COLUMNS


class TestNotebookStaysSelfContained:
    def test_it_imports_no_local_module(self, source):
        """The point of the rebuild was that the .ipynb travels alone."""
        for bad in ("import rehab_analysis", "from rehab_analysis",
                    "from parts", "import parts"):
            assert bad not in source, f"notebook imports {bad!r}"

    def test_every_code_cell_parses(self):
        nb = json.loads(NOTEBOOK.read_text())
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] != "code":
                continue
            src = "\n".join(
                "" if l.lstrip().startswith(("%", "!")) else l
                for l in "".join(cell["source"]).splitlines())
            try:
                ast.parse(src)
            except SyntaxError as e:
                pytest.fail(f"cell {i} does not parse: {e}")

    def test_every_code_cell_is_folded(self):
        """Opening it should show headings and results, not code."""
        nb = json.loads(NOTEBOOK.read_text())
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] != "code":
                continue
            meta = cell.get("metadata", {})
            assert meta.get("jupyter", {}).get("source_hidden"), (
                f"code cell {i} is not folded")


class TestCueFlagsRoundTrip:
    """The notebook has to understand the code the game writes."""

    def test_the_game_and_the_notebook_agree_on_the_format(self, source):
        from rehab.game.engine import CueSettings
        code = CueSettings(buzz_before=True, sound_before=True,
                           sound_after=False, buzz_after=False,
                           show_target=True).code
        assert code == "BS/--"
        # The notebook splits on the slash and looks for B and S.
        assert "cue_flags" in source
        assert 'split("/")' in source or "split('/')" in source


def _notebook_functions(source, names):
    """Compile just the named top-level defs out of the notebook
    source. The copies can then be exercised directly, without
    running any of the notebook's IO or widget code around them."""
    tree = ast.parse(source)
    wanted = {node.name: node for node in tree.body
              if isinstance(node, ast.FunctionDef)
              and node.name in names}
    missing = [n for n in names if n not in wanted]
    assert not missing, f"notebook no longer defines {missing}"
    import numpy
    ns = {"np": numpy}
    mod = ast.Module(body=[wanted[n] for n in names], type_ignores=[])
    exec(compile(mod, "<notebook>", "exec"), ns)
    return [ns[n] for n in names]


class TestContinuousModeContract:
    """The three continuous-force chapters rebuild trials offline.

    The notebook carries copies of the game's pure trajectory
    builders and keys on the game's packed tokens. Either side can
    change without the other noticing, so the shared names are pinned
    here, and the corridor rebuild is exercised end to end through
    the packed CSV cell, exactly the round trip a real trial takes.
    """

    # (literal, game file that writes it, notebook section that
    # reads it). A rename on either side must fail here, not go
    # quiet in a chapter.
    TOKENS = [
        ('waveform="corridor"', "rehab/game/modes/force_pilot.py",
         '== "corridor"'),
        ('waveform="hold"', "rehab/game/modes/lighthouse.py",
         '"hold"'),
        ('waveform="reproduce"', "rehab/game/modes/lighthouse.py",
         '"reproduce"'),
        ('"loc"', "rehab/game/modes/buzz_hunt.py", '"loc"'),
        ('"distractor"', "rehab/game/modes/buzz_hunt.py",
         '"distractor"'),
        ('"span"', "rehab/game/modes/buzz_hunt.py", '"span"'),
        ('"gap"', "rehab/game/modes/buzz_hunt.py", '"gap"'),
        ('"buzz_hunt_reversal"', "rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_reversal"'),
        ("level_ms=", "rehab/game/modes/buzz_hunt.py", '"level_ms"'),
    ]

    @pytest.mark.parametrize("game_literal,game_file,nb_literal",
                             TOKENS)
    def test_both_sides_still_use_the_token(self, game_literal,
                                            game_file, nb_literal,
                                            source):
        game_src = (ROOT / game_file).read_text()
        assert game_literal in game_src, (
            f"{game_file} stopped writing {game_literal!r}")
        assert nb_literal in source, (
            f"the notebook stopped reading {nb_literal!r}, so that "
            f"part of its chapter is now silent")

    def test_the_notebook_rebuilds_the_corridor_the_game_flew(
            self, source):
        from rehab.data.logger import (pack_waveform_params,
                                       parse_waveform_params)
        from rehab.game.modes.force_pilot import (draw_run_params,
                                                  sections_from_params,
                                                  target_pct)
        fp_sections, fp_target = _notebook_functions(
            source, ["fp_sections_from_params", "fp_target_pct"])
        p = draw_run_params(
            seed=7, level=2, freq_ceiling_hz=0.45,
            corridor_hw_pct=6.0, gain=1.0, span_pct=40.0,
            base_pct=8.0, plateau_pct=28.0,
            ramp_rates_pct_s=[5.0, 10.0], sine_amp_pct=9.0,
            sine_s=6.0, sos_amps_pct=[6.0, 3.5, 2.5], sos_s=8.0,
            hold_in_s=3.0, hold_top_s=3.0, pre_assess_s=1.0,
            max_press_counts=420.0)
        # Through the CSV cell, exactly as a logged trial travels.
        rebuilt = fp_sections(
            parse_waveform_params(pack_waveform_params(p)))
        game = sections_from_params(p)
        assert [s["name"] for s in rebuilt] == [s.name for s in game]
        dur = game[-1].end_s
        worst = max(
            abs(target_pct(game, i / 20.0)
                - fp_target(rebuilt, i / 20.0))
            for i in range(int(dur * 20) + 1))
        # The packed cell rounds to 6 significant digits, which
        # bounds the rebuild error far under a hundredth of a
        # percent of max.
        assert worst < 0.01, (
            f"corridor rebuild drifted by {worst:.4f}% of max")
