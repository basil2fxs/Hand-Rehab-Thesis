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

from finger_rehab.data.logger import TRIAL_COLUMNS, RAW_COLUMNS


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
        from finger_rehab.game.engine import CueSettings
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


def _notebook_names(source, names):
    """Compile the named top-level defs AND assignments out of the
    notebook source (functions plus the constants they close over as
    globals). Unlike _notebook_functions, this also picks up plain
    `NAME = ...` statements, which chord_difficulty needs for
    CHORD_ENSLAVABILITY et al."""
    tree = ast.parse(source)
    wanted = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            wanted[node.name] = node
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in names:
                    wanted[t.id] = node
    missing = [n for n in names if n not in wanted]
    assert not missing, f"notebook no longer defines {missing}"
    import numpy
    ns = {"np": numpy}
    mod = ast.Module(body=[wanted[n] for n in names], type_ignores=[])
    exec(compile(mod, "<notebook>", "exec"), ns)
    return [ns[n] for n in names]


class TestChordsNotebookContract:
    """Regression for the chords-chapter NameError: chord_difficulty,
    chord_frame and sec_chords used five constants the setup cell
    never defined, so any selection with a chords block crashed and
    Jupyter's Run All never reached the chapters after it."""

    CONSTANT_NAMES = ["CHORD_LETTERS", "CHORD_ENSLAVABILITY",
                       "CHORD_ADJACENT", "CHORD_SIZE_PENALTY",
                       "HEALTHY_ER_BAND"]

    @pytest.mark.parametrize("name", CONSTANT_NAMES)
    def test_constant_is_defined_in_the_setup_cell(self, name, source):
        (const,) = _notebook_names(source, [name])
        assert const is not None

    def test_chord_difficulty_matches_the_game_for_every_chord(
            self, source):
        from itertools import combinations
        from finger_rehab.game.modes.chords import chord_difficulty as game_d

        names = ["chord_difficulty"] + self.CONSTANT_NAMES[:4]
        nb_d = _notebook_names(source, names)[0]

        for size in (2, 3, 4):
            for fingers in combinations(range(4), size):
                assert nb_d(fingers) == game_d(fingers), (
                    f"notebook D disagrees with the game for {fingers}")

    def test_healthy_er_band_matches_the_printed_legend(self, source):
        # The cross-talk panel's own legend text says "healthy 8-15%
        # (light force)"; the constant must match what it prints.
        (band,) = _notebook_names(source, ["HEALTHY_ER_BAND"])
        assert band == (0.08, 0.15)
        assert 'healthy 8-15%' in source


class TestReactionFrameContract:
    """Regression for the choice-mode wrong-finger misclassification:
    reaction.py writes error_type='wrong_finger' on BOTH the simple
    sub-mode's never-scorable retry (early_late=='Wrong') and the
    choice sub-mode's scorable wrong-choice Miss (early_late=='Miss'),
    but reaction_frame used to treat every wrong_finger row as a never-
    scorable event, undercounting choice-mode scorable trials and
    misses."""

    def _reaction_frame(self, source):
        import numpy
        import pandas
        names = ["reaction_frame", "mode_rows", "stimulus_parts",
                 "REACTION_NEVER_SCORABLE"]
        tree = ast.parse(source)
        wanted = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                wanted[node.name] = node
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in names:
                        wanted[t.id] = node
        missing = [n for n in names if n not in wanted]
        assert not missing, f"notebook no longer defines {missing}"
        ns = {"np": numpy, "pd": pandas}
        mod = ast.Module(body=[wanted[n] for n in names], type_ignores=[])
        exec(compile(mod, "<notebook>", "exec"), ns)
        return ns["reaction_frame"]

    def _rows(self, **overrides):
        import pandas as pd
        row = {
            "mode": "reaction", "stimulus": "choice;fp=2.314",
            "error_type": "", "early_late": "Good",
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_choice_wrong_finger_miss_is_scorable_not_an_event(
            self, source):
        reaction_frame = self._reaction_frame(source)
        rows = self._rows(error_type="wrong_finger", early_late="Miss")
        out = reaction_frame(rows)
        assert bool(out.iloc[0]["is_event"]) is False, (
            "a choice-mode wrong-choice Miss (a real scorable trial, "
            "engine.py's own convention) was classified as an event "
            "row that never became a scorable trial")

    def test_simple_wrong_finger_retry_is_still_an_event(self, source):
        reaction_frame = self._reaction_frame(source)
        rows = self._rows(error_type="wrong_finger", early_late="Wrong")
        out = reaction_frame(rows)
        assert bool(out.iloc[0]["is_event"]) is True, (
            "the simple sub-mode's free wrong-finger retry (no scorable "
            "slot consumed) must still be excluded from the scored count"
        )

    def test_ordinary_hit_is_scored(self, source):
        reaction_frame = self._reaction_frame(source)
        out = reaction_frame(self._rows())
        assert bool(out.iloc[0]["is_event"]) is False


class TestReactionModeChapter:
    """Drives sec_reaction_mode itself (not just the isolated helpers)
    over a synthetic choice-mode block: 6 correct hits and 3 wrong-
    choice Misses is 67% accuracy, under the brief's 80% guessing
    line. Regression for findings #1 (wrong-choice rows undercounted
    as never-scorable events) and #5 (nothing checked choice accuracy
    against the guessing threshold)."""

    NAMES = ["sec_reaction_mode", "_reaction_mode_group", "reaction_frame",
             "mode_rows", "stimulus_parts", "REACTION_NEVER_SCORABLE",
             "reaction_floor_note", "_reaction_accuracy_warning",
             "_reaction_exgaussian_fit", "_reaction_time_on_task",
             "_nothing", "_show", "_nbins", "ANTICIPATION_MS",
             "LAPSE_MS", "stored_mode_stats", "_meta_items"]

    def _load(self, source):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy
        import pandas

        tree = ast.parse(source)
        wanted = {}
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in self.NAMES:
                wanted[node.name] = node
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in self.NAMES:
                        wanted[t.id] = node
        missing = [n for n in self.NAMES if n not in wanted]
        assert not missing, f"notebook no longer defines {missing}"
        # _save writes PNGs into the real repo figures/ dir and clears
        # it first; the chapter's own maths is what this test checks,
        # so figure persistence is stubbed out rather than pointed at
        # a scratch dir, keeping the working tree untouched.
        ns = {"np": numpy, "pd": pandas, "plt": plt,
              "_save": lambda fig, name: None}
        mod = ast.Module(body=[wanted[n] for n in self.NAMES],
                          type_ignores=[])
        exec(compile(mod, "<notebook>", "exec"), ns)
        return ns["sec_reaction_mode"]

    def _choice_trials(self):
        import pandas as pd
        rows = []
        for i in range(6):
            rows.append(dict(
                mode="reaction", stimulus=f"choice;fp={2.0 + i / 10:.3f}",
                error_type="", early_late="Good",
                time_difference_ms=250.0 + i * 5, session="s1",
                game="g1", trial=i + 1))
        for i in range(3):
            rows.append(dict(
                mode="reaction", stimulus=f"choice;fp={3.0 + i / 10:.3f}",
                error_type="wrong_finger", early_late="Miss",
                time_difference_ms="", session="s1",
                game="g1", trial=7 + i))
        return pd.DataFrame(rows)

    def test_choice_accuracy_below_80pct_is_flagged(self, source, capsys):
        sec_reaction_mode = self._load(source)
        result = sec_reaction_mode(self._choice_trials())
        out = capsys.readouterr().out
        import matplotlib.pyplot as plt
        plt.close("all")
        # 9 scorable trials (6 hits + 3 wrong-choice Misses), not 6
        # scorable plus "3 event rows that never became scorable
        # trials": a choice wrong-finger row IS a scorable trial.
        assert "9 scorable trials" in out, out
        assert "0 event rows" in out, out
        assert "choice accuracy 67%" in out, out
        assert "WARNING: under 80%" in out, out
        assert result["accuracy"] == pytest.approx(6 / 9, abs=1e-3)

    def test_clean_choice_block_accuracy_is_not_flagged(self, source,
                                                         capsys):
        sec_reaction_mode = self._load(source)
        rows = self._choice_trials()
        rows = rows[rows["error_type"] != "wrong_finger"]
        sec_reaction_mode(rows)
        out = capsys.readouterr().out
        import matplotlib.pyplot as plt
        plt.close("all")
        assert "WARNING" not in out


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
        ('waveform="corridor"', "finger_rehab/game/modes/force_pilot.py",
         '== "corridor"'),
        ('waveform="hold"', "finger_rehab/game/modes/lighthouse.py",
         '"hold"'),
        ('waveform="reproduce"', "finger_rehab/game/modes/lighthouse.py",
         '"reproduce"'),
        ('"loc"', "finger_rehab/game/modes/buzz_hunt.py", '"loc"'),
        ('"distractor"', "finger_rehab/game/modes/buzz_hunt.py",
         '"distractor"'),
        ('"span"', "finger_rehab/game/modes/buzz_hunt.py", '"span"'),
        ('"gap"', "finger_rehab/game/modes/buzz_hunt.py", '"gap"'),
        ('"buzz_hunt_reversal"', "finger_rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_reversal"'),
        ("level_ms=", "finger_rehab/game/modes/buzz_hunt.py", '"level_ms"'),
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
        from finger_rehab.data.logger import (pack_waveform_params,
                                       parse_waveform_params)
        from finger_rehab.game.modes.force_pilot import (draw_run_params,
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
