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
