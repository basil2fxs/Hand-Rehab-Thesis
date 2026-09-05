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
import re
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


class TestCanonicalSignalCopies:
    """The setup cell carries verbatim copies of teasdale_onset and
    lookback_baseline from finger_rehab/analytics/signal.py, because
    the notebook travels alone and cannot import them. Verbatim is
    checked as AST equality, so an edit that reaches one copy and
    misses the other fails here before the two detectors can quietly
    hand out different onsets for the same press."""

    NAMES = ["teasdale_onset", "lookback_baseline"]

    def _package_defs(self):
        import inspect
        import finger_rehab.analytics.signal as sig
        src = inspect.getsource(sig)
        return {node.name: node for node in ast.parse(src).body
                if isinstance(node, ast.FunctionDef)
                and node.name in self.NAMES}

    @pytest.mark.parametrize("name", NAMES)
    def test_notebook_copy_is_verbatim(self, name, source):
        pkg = self._package_defs()
        assert name in pkg, f"signal.py no longer defines {name}"
        nb = {node.name: node for node in ast.parse(source).body
              if isinstance(node, ast.FunctionDef) and node.name == name}
        assert name in nb, f"the notebook no longer defines {name}"
        assert ast.dump(nb[name]) == ast.dump(pkg[name]), (
            f"{name} differs between the notebook and signal.py. Edit "
            f"signal.py and re-copy the function into the setup cell, "
            f"never one side alone.")


_LIVE = {}


def _live_notebook():
    """Every notebook cell's definitions exec'd into one module
    namespace, so a chapter function can be called for real. Built
    once per test session: the setup cell is large."""
    import sys
    import tempfile
    from types import ModuleType
    if "ns" in _LIVE:
        return _LIVE["ns"]
    import matplotlib
    matplotlib.use("Agg")
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_contract"
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

    _LIVE["ns"] = _Live(ns)
    return _LIVE["ns"]


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
        ('"loc"', "finger_rehab/game/modes/buzz_hunt.py", '"loc"'),
        ('"distractor"', "finger_rehab/game/modes/buzz_hunt.py",
         '"distractor"'),
        ('"span"', "finger_rehab/game/modes/buzz_hunt.py", '"span"'),
        ('"gap"', "finger_rehab/game/modes/buzz_hunt.py", '"gap"'),
        ('"buzz_hunt_reversal"', "finger_rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_reversal"'),
        ("level_ms=", "finger_rehab/game/modes/buzz_hunt.py", '"level_ms"'),
        # The reliability build's raw events. The notebook counts them
        # per block as frame health, so a rename on either side has to
        # fail here rather than turn a column silently to zero.
        ('"buzz_hunt_gate_forced"', "finger_rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_gate_forced"'),
        ('"buzz_hunt_trial_forced"', "finger_rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_trial_forced"'),
        ('"buzz_hunt_stim_fail"', "finger_rehab/game/modes/buzz_hunt.py",
         '"buzz_hunt_stim_fail"'),
        ('"stim_lost"', "finger_rehab/game/modes/buzz_hunt.py",
         '"stim_lost"'),
        ('"pulse_broken"', "finger_rehab/game/engine.py",
         '"pulse_broken"'),
        ("wall_forced=", "finger_rehab/game/modes/buzz_hunt.py",
         '"wall_forced"'),
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



# --------------------------------------------------------------- report
# The notebook exports one HTML holding everything it printed and drew.
# That only stays true while every section goes through keep(), which is
# what files the section's text and figures. A section added later that
# skips keep() would silently vanish from the report, so the shape is
# pinned here rather than trusted.

def _cells():
    nb = json.loads(NOTEBOOK.read_text())
    return [("".join(c.get("source", [])), c.get("cell_type"))
            for c in nb["cells"]]


def test_every_section_call_goes_through_keep():
    offenders = []
    for src, kind in _cells():
        if kind != "code" or "def sec_" in src:
            continue  # the Setup cell defines sections, never calls them
        if re.search(r"\bsec_\w+\s*\(", src) and "keep(" not in src:
            offenders.append(src.strip().splitlines()[0][:70])
    assert offenders == [], (
        "these cells run a section without keep(), so the report would "
        "not contain them: " + "; ".join(offenders))


def test_keep_files_the_section_for_the_report():
    setup = _cells()[2][0]
    assert "_capture_section(name)" in setup
    for name in ("_wrap_sections", "_capture_reset", "write_report",
                 "PATIENT_RESULTS"):
        assert name in setup, f"{name} missing from Setup"


def test_patient_results_path_is_not_relative():
    # A relative "sessions" path resolves against the notebook's own
    # directory, which creates a second empty sessions tree beside the
    # notebook and shadows the real recordings on the next run.
    assert 'PATIENT_RESULTS = Path(SESSIONS_DIR)' in _cells()[2][0]


def test_the_export_cell_is_last():
    code = [src for src, kind in _cells() if kind == "code"]
    assert "write_report(ctx)" in code[-1], (
        "the export cell must be the last code cell so it captures "
        "every section above it")


# --------------------------------------------------------------- cohort
# The cohort chapter (docs/research/healthy_baseline_study.txt, Section
# 4) reads the whole sessions tree and writes its own report. Its
# contract with the rest of the notebook is pinned here; the numbers
# it produces are pinned in tests/test_cohort_notebook.py on a cohort
# the real engine wrote.

class TestBuzzHuntFloorsAndCensoring:
    """The gap floor is a host limit, not a perceptual one, and the
    notebook has to know the same number the mode does."""

    def test_the_gap_floor_matches_the_mode(self, source) -> None:
        from finger_rehab.game.modes.buzz_hunt import GAP_FLOOR_MS
        (floor,) = _notebook_names(source, ["BH_GAP_FLOOR_MS"])
        assert floor == GAP_FLOOR_MS == 150.0

    def test_the_config_ships_the_same_floor(self) -> None:
        from finger_rehab.config import Config
        from finger_rehab.game.modes.buzz_hunt import GAP_FLOOR_MS
        assert float(Config.load().get("buzz_hunt.gap_floor_ms")) \
            == GAP_FLOOR_MS

    def test_a_censored_threshold_never_prints_a_number(self) -> None:
        ra = _live_notebook()
        text = ra.bh_gap_threshold_text(
            {"final_ms": 150.0, "estimate_ms": 150.0, "floor_ms": 150.0,
             "censored": True})
        assert "censored" in text
        assert "at or below 150 ms" in text
        # An uncensored one is a plain number.
        clear = ra.bh_gap_threshold_text(
            {"final_ms": 320.0, "estimate_ms": 316.7, "floor_ms": 150.0,
             "censored": False})
        assert clear == "317 ms"
        assert ra.bh_gap_threshold_text(None) is None

    def test_stim_lost_survives_the_block_loader(self) -> None:
        """A block that ended because the board went away must still
        render, and must be named as not comparable."""
        import contextlib
        import io
        import pandas as pd
        ra = _live_notebook()
        metas = {"g1": {"block_summary": {
            "block": "buzz_hunt",
            "buzz_hunt": {
                "end_reason": "stim_lost",
                "reliability": {"forced_starts": 3, "stim_failures": 4,
                                "stim_lost": True},
                "gap": {"threshold": {"right": {
                    "final_ms": 150.0, "estimate_ms": 150.0,
                    "floor_ms": 150.0, "censored": True}}},
                "loc": {"accuracy": 0.9}}}}}
        stored = ra.stored_mode_stats(metas, "buzz_hunt")
        assert stored["g1"]["end_reason"] == "stim_lost"
        assert stored["g1"]["reliability"]["stim_lost"] is True
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = ra.sec_tactile([], pd.DataFrame(), metas)
        # No trials, so the chapter says so rather than half-drawing.
        assert out is None
        assert "No Buzz Hunt trials" in buf.getvalue()


SEQUENCE_FILE = {
    "schema": 1, "name": "Riff A", "file_name": "riffA.yaml",
    "schedule_id": "abc123def456", "hands": "one", "n_lanes": 4,
    "explicit": False, "show_sequence": False, "cycle_len": 4,
    "total_trials": 24, "estimated_minutes": 1.2, "warnings": [],
    "blocks": [
        {"name": "riff_1", "kind": "seq", "label": "1", "trials": 12,
         "repeats": 3, "sequence": [2, 4, 1, 3],
         "gaps_ms": [400, 400, 800, 1200], "rest_after_s": 10.0},
        {"name": "fresh", "kind": "probe", "label": "2", "trials": 12,
         "repeats": 3, "sequence": [1, 4, 2, 3],
         "gaps_ms": [400, 400, 800, 1200], "rest_after_s": 10.0}],
}


def _pattern_trials(game, n=14):
    """Two takes of one pattern game: a trained take then a probe."""
    import pandas as pd
    rows = []
    trial = 0
    for take, kind, soc, base in (("1", "seq", "file:riff_1", 420.0),
                                  ("2", "probe", "file:fresh", 520.0),
                                  ("3", "seq", "file:riff_1", 430.0)):
        for i in range(n):
            trial += 1
            rows.append({
                "mode": "pattern", "game": game, "session": game,
                "hand_mode": "right", "side": "right", "trial": trial,
                "stimulus": f"{kind};b={take};soc={soc};pos={i % 4}",
                "time_difference_ms": base + (i % 5) * 4.0,
                "early_late": "", "error_type": "",
                "pattern_trial": kind == "seq",
            })
    return pd.DataFrame(rows)


def _pattern_meta(**summary):
    base = {"rsi_ms": 500, "timeout_ms": 2000, "start_trim": 0,
            "material": "generated", "schedule_id": "builtin",
            "explicit": False, "sequence_file": None,
            "sequence_file_error": None, "demo": False}
    base.update(summary)
    return {"block_summary": {"block": "pattern", "pattern": base}}


class TestPatternSequenceFileChapter:
    """A loaded sequence file replaces the material AND the per-press
    gaps, so two games under different files are two different tasks.
    The chapter has to split on the schedule, print what each group
    actually ran, and keep explicit practice out of the implicit
    learning score."""

    def test_a_file_game_gets_its_own_consistency_group(self) -> None:
        import pandas as pd
        ra = _live_notebook()
        trials = pd.concat([_pattern_trials("g_builtin"),
                            _pattern_trials("g_file")],
                           ignore_index=True)
        metas = {
            "g_builtin": _pattern_meta(),
            "g_file": _pattern_meta(material="file",
                                    schedule_id="abc123def456",
                                    sequence_file=SEQUENCE_FILE),
        }
        groups, sigs = ra.pattern_consistency_groups(trials, metas)
        assert len(groups) == 2, groups
        assert sigs["g_file"]["schedule_id"] == "abc123def456"
        assert sigs["g_builtin"]["schedule_id"] == "builtin"
        # Same rsi, same timeout, same cue flags: only the file split
        # them.
        for key in ("rsi_ms", "timeout_ms", "cue_flags"):
            assert sigs["g_file"][key] == sigs["g_builtin"][key]

    def test_the_split_and_the_schedule_readout_print(self) -> None:
        import contextlib
        import io
        import pandas as pd
        ra = _live_notebook()
        trials = pd.concat([_pattern_trials("g_builtin"),
                            _pattern_trials("g_file")],
                           ignore_index=True)
        metas = {
            "g_builtin": _pattern_meta(),
            "g_file": _pattern_meta(material="file",
                                    schedule_id="abc123def456",
                                    sequence_file=SEQUENCE_FILE),
        }
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ra.sec_pattern_srtt(trials, metas)
        import matplotlib.pyplot as plt
        plt.close("all")
        out = buf.getvalue()
        assert "SPLIT:" in out
        assert "schedule=abc123def456" in out
        assert "Schedule read from metadata" in out
        assert "riff_1" in out
        assert "400-1200 (4 per cycle)" in out

    def test_a_fallback_says_why_it_fell_back(self) -> None:
        import contextlib
        import io
        ra = _live_notebook()
        stored = {"g_bad": _pattern_meta(
            material="builtin_fallback",
            sequence_file_error="lane 9 is not on a four-lane board",
        )["block_summary"]["pattern"]}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ra._pattern_schedule_readout(stored)
        out = buf.getvalue()
        assert "FELL BACK: g_bad" in out
        assert "lane 9 is not on a four-lane board" in out

    def test_explicit_practice_never_enters_the_learning_score(self):
        ra = _live_notebook()
        for explicit in (False, True):
            block = {"game": "g1", "folder": Path("."),
                     "meta": _pattern_meta(), "rows": _pattern_trials("g1"),
                     "hand": "right", "calset": None, "extra": {},
                     "bs": _pattern_meta(
                         material="file", schedule_id="abc123def456",
                         explicit=explicit,
                         sequence_file=dict(SEQUENCE_FILE,
                                            explicit=explicit),
                     )["block_summary"]}
            out = ra._cohort_pattern(block)
            metrics = {m for _h, m, _v, _n in out}
            assert block["extra"]["pattern_schedule_id"] == "abc123def456"
            assert block["extra"]["pattern_explicit"] is explicit
            if explicit:
                assert "learning_score_ms" not in metrics
            else:
                assert "learning_score_ms" in metrics, metrics

    def test_the_mode_still_writes_every_key_the_chapter_reads(self):
        """The chapter reads these off block_summary.pattern. If
        pattern.py stops writing one, the split or the read-out goes
        quiet instead of failing, so the source is pinned here."""
        src = (ROOT / "finger_rehab/game/modes/pattern.py").read_text()
        for key in ('"material"', '"schedule_id"', '"explicit"',
                    '"sequence_file"', '"sequence_file_error"',
                    '"battery_overrides_ignored"'):
            assert key in src, f"pattern.py no longer writes {key}"
        for key in ('"n_items"', '"gap_ms_mean"', '"gap_ms_min"',
                    '"gap_ms_max"', '"rest_after_s"'):
            assert key in src, f"pattern.py no longer writes {key} " \
                               f"on a per_take row"
        source = _notebook_source()
        for key in ("schedule_id", "sequence_file", "explicit",
                    "material", "sequence_file_error"):
            assert f'"{key}"' in source or f"'{key}'" in source, (
                f"the notebook stopped reading {key}")

    def test_the_long_table_names_the_excluded_explicit_blocks(self):
        import contextlib
        import io
        import pandas as pd
        ra = _live_notebook()
        sel = pd.DataFrame([{
            "folder": "/nowhere/2026-09-04/P01_100000_pattern",
            "participant": "P01", "visit": "1", "day": "2026-09-04",
            "mode": "pattern", "dominant_hand": "right",
            "phase": "pre", "battery_position": 1,
        }])
        game = ra.game_key(sel["folder"].iloc[0])
        trials = _pattern_trials(game)
        metas = {game: _pattern_meta(material="file",
                                     schedule_id="abc123def456",
                                     explicit=True,
                                     sequence_file=SEQUENCE_FILE)}
        metas[game]["battery"] = {"phase": "pre", "position": 1}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            long, frames = ra.cohort_long_table(sel, trials, metas)
        out = buf.getvalue()
        assert "EXCLUDED from the Muscle Memory learning score" in out
        assert "1 block(s) run as EXPLICIT practice" in out
        assert "learning_score_ms" not in set(long["metric"])
        assert frames["pattern_schedule_id"][0][2] == "abc123def456"


class TestCohortChapterContract:
    SECTIONS = ["sec_cohort_selection", "sec_cohort_describe",
                "sec_cohort_hands", "sec_cohort_within_block",
                "sec_cohort_consistency", "sec_cohort_feasibility",
                "sec_cohort_validity", "sec_cohort_export"]
    HELPERS = ["write_cohort_report", "icc_ci", "cohort_long_table",
               "cohort_catalogue", "cohort_paired", "cohort_values",
               "cohort_battery_rows", "median_order_ci",
               "is_study_code", "cohort_hand_role", "split_half",
               "tost_paired", "wilson_ci", "log_linear_slope",
               "exp_fit", "fine_series", "rolling_median",
               "cohort_within_block_curves", "cohort_series_table",
               "_binned_curve", "_slope_ci", "_dropped_row",
               "_within_block_row", "_bh_fixed_level_series",
               "_fp_level_residual"]
    # Every mode is played once in the one pass. The split below is not
    # how often a mode is played any more, it is whether the design
    # makes a directional claim on it: adaptive and syllables are
    # described and never claimed on, because the staircase moves the
    # task under the hand.
    CLAIMED_MODES = {"reaction", "mirror", "rhythm", "echo", "force_pilot",
                     "chords", "buzz_hunt", "pattern"}
    ONCE_MODES = {"adaptive", "syllables"}

    def test_setup_defines_every_cohort_name(self, source):
        tree = ast.parse(source)
        defined = {node.name for node in tree.body
                   if isinstance(node, ast.FunctionDef)}
        missing = [n for n in self.SECTIONS + self.HELPERS
                   if n not in defined]
        assert missing == [], f"the setup cell no longer defines {missing}"

    def test_long_table_columns_match_the_design(self, source):
        (cols,) = _notebook_names(source, ["COHORT_LONG_COLS"])
        # phase is the pairing key of the single-session design and
        # position is where in the sitting the block ran; visit stays
        # so a tree from the old two-visit design still loads.
        assert cols == ["participant", "phase", "position", "visit", "day",
                        "hand", "hand_role", "mode", "metric", "value",
                        "n_trials", "block_folder", "config_hash"]
        assert "phase" in cols and "position" in cols

    def test_the_phases_are_the_ones_the_shipped_preset_writes(
            self, source):
        """The one pass writes a single phase word on every step, and
        the notebook has to carry the same one: a battery block is told
        from a free pick by having a phase at all."""
        from finger_rehab.config import Config
        one, phases = _notebook_names(
            source, ["COHORT_PHASE", "COHORT_PHASES"])
        preset = Config.load().get("protocol.presets.study_battery") or {}
        shipped = {str(step.get("phase") or "").strip().lower()
                   for order in (preset.get("orders") or {}).values()
                   for step in order}
        assert set(phases) == shipped
        assert len(shipped) == 1, (
            "the shipped preset writes more than one phase word, so the "
            "battery repeats a block and this is no longer one pass")
        assert one in shipped

    def test_no_paired_phase_machinery_survives(self, source):
        """The one pass repeats nothing, so a pre-against-post pairing
        key, a retest interval and an MDC file would all be machinery
        for data that is never collected."""
        for gone in ("COHORT_PAIR_PHASES", "COHORT_INTERVAL_DAYS",
                     "COHORT_ANCHOR_BAND_MS", "COHORT_NEEDS_POST",
                     '"progress_mdc.yaml"', "sec_cohort_within_session",
                     "sec_cohort_learning", "_equivalence_check",
                     "_change_check", "_cohort_post_rest"):
            assert gone not in source, f"{gone} outlived the one pass"

    def test_the_dropped_checks_are_named_with_their_reason(self, source):
        """R3, P2 and E2 are in Section 1 of the design and cannot be
        run here. They print as DROPPED with the reason, so a reader
        who meets them there finds out what happened to them.

        Two reasons, not one. R3 and P2 need the same block played
        twice and the design plays it once. E2 needs echo under its
        ladder rule and the battery plays the Simon rule, so it came
        out for a reason that has nothing to do with the one pass and
        carries its own criterion line.
        """
        (dropped,) = _notebook_names(source, ["COHORT_DROPPED_CHECKS"])
        assert set(dropped) == {"R3", "P2", "E2"}
        for cid, (mode, _check, reason, criterion) in dropped.items():
            assert mode in ("reaction", "pattern", "echo"), cid
            assert criterion.startswith("DROPPED:"), cid
            if cid == "E2":
                assert "ladder" in reason and "simon" in reason, cid
            else:
                assert "twice" in reason, cid

    def test_every_mode_says_how_its_within_block_trend_reads(
            self, source):
        """A mode missing from the table would have its trend read as
        improvement by default, and for four of them a later trial is a
        harder trial."""
        reading, modes = _notebook_names(
            source, ["COHORT_WITHIN_BLOCK_READING", "COHORT_MODES"])
        assert set(reading) == set(modes)
        assert reading["reaction"][0] == "anchor"
        harder = {m for m, (kind, _why) in reading.items()
                  if kind == "harder"}
        assert harder == {"echo", "force_pilot", "buzz_hunt", "adaptive"}
        for mode, (_kind, why) in reading.items():
            assert why, f"{mode} says nothing about why"

    def test_the_fine_series_covers_every_shipped_mode(self, source):
        """Every mode on the hub has a watched series, or the curve
        chapter silently skips it."""
        from finger_rehab.ui.screens import ModeSelectScreen
        (better,) = _notebook_names(source, ["FINE_SERIES_BETTER"])
        modes = {str(m[0]) for m in ModeSelectScreen.MODES} - {"classic"}
        assert modes <= set(better), modes - set(better)
        assert set(better.values()) <= {"lower", "higher"}

    def test_registry_covers_every_mode_the_sitting_plays(self, source):
        floor, registry, modes = _notebook_names(
            source, ["COHORT_BH_FLOOR_MS", "COHORT_METRICS", "COHORT_MODES"])
        every = self.CLAIMED_MODES | self.ONCE_MODES
        assert {mode for mode, _m in registry} == every
        assert set(modes) == every
        # Every mode has exactly one headline metric for the figures.
        for mode in every:
            heads = [m for (md, m), s in registry.items()
                     if md == mode and s.get("headline")]
            assert len(heads) == 1, f"{mode} headline metrics: {heads}"
        assert floor == 40.0

    def test_the_described_modes_carry_their_caveat(self, source):
        """Adaptive and syllables are described and never claimed on:
        their staircases move the task under the hand, so the number is
        the ladder as much as the finger. Every one of their rows has
        to be marked descriptive and has to carry the reason, or it
        walks into a table that makes a claim about it."""
        _floor, registry = _notebook_names(
            source, ["COHORT_BH_FLOOR_MS", "COHORT_METRICS"])
        for mode in self.ONCE_MODES:
            rows = {m: s for (md, m), s in registry.items() if md == mode}
            assert rows, f"{mode} has no registry rows"
            for metric, spec in rows.items():
                assert spec.get("descriptive"), f"{mode}.{metric}"
                assert spec.get("caveat"), f"{mode}.{metric} has no reason"
        for (mode, metric), spec in registry.items():
            if mode in self.CLAIMED_MODES:
                assert not spec.get("descriptive"), f"{mode}.{metric}"
        # "played once" is true of every mode now, so it cannot be a
        # reason for anything.
        for (mode, metric), spec in registry.items():
            assert "played once" not in str(spec.get("caveat", "")), (
                f"{mode}.{metric} still explains itself by being played "
                f"once, which is now true of all ten modes")

    def test_the_builders_cover_every_mode_in_the_registry(self, source):
        """A registry row with no builder emits nothing, so the metric
        would print as missing data rather than as a coding gap."""
        tree = ast.parse(source)
        builders = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "COHORT_BUILDERS"
                    for t in node.targets):
                builders = {k.value for k in node.value.keys}
        assert builders is not None, "COHORT_BUILDERS is gone"
        _floor, registry = _notebook_names(
            source, ["COHORT_BH_FLOOR_MS", "COHORT_METRICS"])
        assert builders == {mode for mode, _m in registry}

    def test_the_within_block_chapter_carries_its_own_limitation(
            self, source):
        """The result and the caveat go in the same breath or the
        caveat is not there at all."""
        chapter = _section_source(source, "sec_cohort_within_block")
        low = chapter.lower()
        for phrase in ("warm-up", "fatigue", "noise floor",
                       "kantak and winstein", "heathcote"):
            assert phrase in low, f"the chapter never says {phrase!r}"

    def test_the_consistency_chapter_refuses_to_derive_an_mdc(
            self, source):
        chapter = _section_source(source, "sec_cohort_consistency")
        low = chapter.lower()
        assert "internal consistency" in low
        assert "not test-retest" in low
        assert "too tight" in low

    def test_the_design_minimum_is_the_collection_day(self, source):
        """Section 2.1: the sample is set by the day, not by a power
        calculation. Ten students for a ten-hour day, and the eight-hour
        day is the floor nothing inferential prints below."""
        n_design, min_n, pct = _notebook_names(
            source, ["COHORT_N_DESIGN", "COHORT_MIN_N",
                     "COHORT_PERCENTILE_MIN_N"])
        assert n_design == 10
        assert min_n == 8
        assert pct == 20

    def test_icc_ci_matches_the_shrout_fleiss_example(self, source):
        """Shrout and Fleiss 1979, Table 2, six targets by four raters:
        ICC(2,1) 0.29 with 0.019 to 0.761, ICC(3,1) 0.71 with 0.342 to
        0.946, the values the R psych package and pingouin print for
        the same data (McGraw and Wong 1996 intervals)."""
        (icc_ci,) = _notebook_functions(source, ["icc_ci"])
        import numpy as np
        sf = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8],
                       [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]], float)
        out = icc_ci(sf)
        assert out["n"] == 6 and out["k"] == 4
        assert out["icc21"] == pytest.approx(0.29, abs=0.005)
        assert out["lo21"] == pytest.approx(0.019, abs=0.001)
        assert out["hi21"] == pytest.approx(0.761, abs=0.001)
        assert out["icc31"] == pytest.approx(0.715, abs=0.001)
        assert out["lo31"] == pytest.approx(0.342, abs=0.001)
        assert out["hi31"] == pytest.approx(0.946, abs=0.001)
        # Degenerate input refuses with NaNs rather than raising.
        flat = icc_ci(np.ones((6, 2)))
        assert flat["icc21"] != flat["icc21"]

    def test_cohort_cells_run_every_section_through_keep(self):
        code = [src for src, kind in _cells() if kind == "code"]
        cohort_cells = [c for c in code if "sec_cohort_" in c
                        and "def sec_cohort_" not in c]
        called = set()
        for cell in cohort_cells:
            assert "keep(" in cell, cell
            called |= set(re.findall(r"\b(sec_cohort_\w+)\s*\(", cell))
        assert called == set(self.SECTIONS)
        # The within-block result feeds the validity table's W rows,
        # so the two cannot be run out of order.
        assert any("sec_cohort_validity(cohort, within)" in c
                   for c in cohort_cells), (
            "the validity cell no longer takes the within-block result, "
            "so W1 to W6 would print as not testable")
        # The cohort report cell sits before the per-session export
        # cell, which must stay last.
        report_cells = [i for i, c in enumerate(code)
                        if "write_cohort_report(ctx, cohort)" in c
                        and "def write_cohort_report" not in c]
        assert len(report_cells) == 1
        assert 0 < report_cells[0] < len(code) - 1

    def test_the_two_reports_stay_apart(self):
        setup = _cells()[2][0]
        assert 'COHORT_RESULTS = Path(SESSIONS_DIR)' in setup
        assert 'if not s["name"].startswith("cohort_")]' in setup
        assert 'if s["name"].startswith("cohort_")]' in setup
        # Figures are filed by absolute path so the per-session report
        # written after the cohort cells still finds its own.
        assert '"figures": [str(FIGDIR / n)' in setup
        assert "_img_tag(Path(fig))" in setup


# ------------------------------------------- per-mode literature checks
# Every one of the ten live modes has to carry, in the notebook: the
# checks the design pre-specifies for it, a section that prints them
# with the reference and the source beside the number, a per-finger
# cut, a both-hands cut where the mode uses both hands, and a paragraph
# saying what its numbers cannot claim. A mode that loses any of those
# leaves the thesis with a number and nothing to read it against.

class TestPerModeLiteratureChecks:
    MODES = ("reaction", "pattern", "chords", "syllables", "adaptive",
             "rhythm", "mirror", "force_pilot", "buzz_hunt", "echo")
    # The section that decides each mode's checks. Some are the mode's
    # only chapter (mirror, adaptive), the rest sit beside one.
    SECTION = {
        "reaction": "sec_reaction_checks",
        "pattern": "sec_pattern_checks",
        "chords": "sec_chords_checks",
        "syllables": "sec_syllables_checks",
        "adaptive": "sec_adaptive",
        "rhythm": "sec_rhythm_checks",
        "mirror": "sec_mirror",
        "force_pilot": "sec_force_pilot_checks",
        "buzz_hunt": "sec_buzz_hunt_checks",
        "echo": "sec_echo_checks",
    }
    # The ids docs/research/healthy_baseline_study.txt Section 1 names.
    # E2 is Hebb there, so it is Hebb here.
    DESIGN_IDS = {
        "reaction": {"R1", "R2"},
        "pattern": {"P1", "P3"},
        "chords": {"C1", "C2", "C3", "C4", "C5"},
        "rhythm": {"Rh1", "Rh2", "Rh3"},
        "mirror": {"M1", "M2"},
        "force_pilot": {"F1", "F2", "F3", "F4"},
        "buzz_hunt": {"B1", "B2", "B3", "B4", "B5"},
        "echo": {"E1", "E2", "E3"},
    }

    def test_every_mode_has_a_check_registry(self, source):
        (lit,) = _notebook_names(source, ["MODE_LIT"])
        assert set(lit) == set(self.MODES), set(lit) ^ set(self.MODES)

    @pytest.mark.parametrize("mode", MODES)
    def test_every_check_names_a_reference_and_a_source(self, mode, source):
        (lit,) = _notebook_names(source, ["MODE_LIT"])
        for spec in lit[mode]:
            for field in ("id", "claim", "reference", "source"):
                assert spec.get(field), f"{mode} {spec.get('id')}: {field}"
            # A source has to be citable: a name and a year, or the
            # project file the rule comes from.
            src = spec["source"]
            assert re.search(r"(19|20)\d\d", src) or ".py" in src \
                or "design Section" in src, f"{mode} {spec['id']}: {src}"

    @pytest.mark.parametrize("mode", sorted(DESIGN_IDS))
    def test_the_design_ids_all_have_a_row(self, mode, source):
        (lit,) = _notebook_names(source, ["MODE_LIT"])
        have = {spec["id"] for spec in lit[mode]}
        missing = self.DESIGN_IDS[mode] - have
        assert missing == set(), f"{mode} is missing {sorted(missing)}"

    def test_echo_e2_is_hebb_the_way_the_design_numbers_it(self, source):
        (lit,) = _notebook_names(source, ["MODE_LIT"])
        by_id = {spec["id"]: spec for spec in lit["echo"]}
        assert "Hebb" in by_id["E2"]["claim"] or \
            "repeated" in by_id["E2"]["claim"]
        assert "E2p" in by_id, "the prefix-miss check lost its own id"
        assert "E2b" not in by_id

    @pytest.mark.parametrize("mode", MODES)
    def test_each_mode_has_a_section_and_it_runs_through_keep(self, mode,
                                                              source):
        name = self.SECTION[mode]
        tree = ast.parse(source)
        defined = {n.name for n in tree.body
                   if isinstance(n, ast.FunctionDef)}
        assert name in defined, f"{name} is not defined"
        called = [src for src, kind in _cells()
                  if kind == "code" and f"{name}(" in src
                  and f"def {name}(" not in src]
        assert called, f"{name} is never called from a cell"
        for cell in called:
            assert "keep(" in cell, f"{name} runs outside keep()"

    @pytest.mark.parametrize("mode", MODES)
    def test_each_mode_prints_its_claim_limits(self, mode, source):
        """print_claim_limits is the one heading a reader looks for, so
        every mode has to call it (syllables also keeps its older
        WHAT THIS CHAPTER CANNOT SAY block, which is the same thing)."""
        body = _section_source(source, self.SECTION[mode])
        assert "print_claim_limits(" in body, self.SECTION[mode]

    @pytest.mark.parametrize("mode", MODES)
    def test_each_mode_cuts_by_finger(self, mode, source):
        body = _section_source(source, self.SECTION[mode])
        assert ("per_finger_table(" in body or "FINGERS[" in body
                or 'groupby(["hand", "finger"])' in body
                or '"finger"' in body), self.SECTION[mode]

    BOTH_HANDS = ("reaction", "chords", "syllables", "rhythm", "mirror",
                  "force_pilot", "buzz_hunt", "echo")

    @pytest.mark.parametrize("mode", BOTH_HANDS)
    def test_the_bimanual_modes_split_by_hand(self, mode, source):
        body = _section_source(source, self.SECTION[mode])
        assert ("per_hand_pair(" in body or '"side"' in body
                or 'groupby("hand")' in body
                or 'groupby("h")' in body
                or 'groupby(["side"' in body
                # mirror carries both hands as two columns of one
                # trial, so its split is right_rt against left_rt.
                or ('"right_rt"' in body and '"left_rt"' in body)), \
            self.SECTION[mode]

    def test_every_source_named_in_a_check_is_in_the_reference_list(
            self, source):
        """A verdict that cites a paper the reference list has never
        heard of is the citation an examiner checks first."""
        lit, refs = _notebook_names(source, ["MODE_LIT", "REFERENCES"])
        listed = " ".join(entry for _group, entries in refs
                          for entry in entries)
        missing = []
        for mode, specs in lit.items():
            for spec in specs:
                for surname in re.findall(r"\b([A-Z][a-z]{3,})(?= \d{4}| et al| and |,)",
                                          spec["source"]):
                    if surname in ("Section", "Journal", "Proceedings",
                                   "Psychological", "Perceptual",
                                   "Experimental", "Quarterly", "Nature",
                                   "Scientific", "Canadian", "American",
                                   "Behavioral", "Applied", "Clinical",
                                   "Biological", "Cognitive", "Motor",
                                   "Somatosensory", "World", "Brain",
                                   "Memory", "Reading", "Research",
                                   "Neuropsychologia", "Communications",
                                   "Bulletin", "Cybernetics", "Physiology",
                                   "Neuroscience", "Skills", "Sleep",
                                   "Aging", "Psychonomic", "Review",
                                   "Behaviour", "Speech", "Language",
                                   "Hearing", "Biomechanics", "Report",
                                   "Reports", "Acoustical", "America",
                                   "Conference", "Mechanisms", "Learning",
                                   "Disease", "Neurological", "Sciences",
                                   "Psychophysics", "Perception",
                                   "Physical", "Therapy", "Chiropractic",
                                   "Medicine", "Strength", "Conditioning",
                                   "Society", "Open", "Science",
                                   "Neurophysiology", "Frontiers",
                                   "Education", "Computers", "Technology",
                                   "Human", "Oxford", "University",
                                   "Press"):
                        continue
                    if surname not in listed:
                        missing.append((mode, spec["id"], surname))
        assert missing == [], f"cited but not in REFERENCES: {missing}"


def _section_source(source, name):
    """The source text of one top-level function, for the coverage
    assertions above."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(source, node) or ""
    raise AssertionError(f"{name} is not defined in the notebook")


def test_every_name_the_notebook_cites_is_in_the_reference_list():
    """A citation in the prose with no entry in REFERENCES is the one
    an examiner checks first. The scan is over the whole notebook, not
    just the per-mode checks, because the statistical toolkit the
    cohort chapter runs on was cited in prose and listed nowhere.
    """
    source = _notebook_source()
    (refs,) = _notebook_names(source, ["REFERENCES"])
    listed = " ".join(entry for _group, entries in refs
                      for entry in entries)
    # "Surname 1999", "Surname et al 2019", "Surname and Other 2004".
    pattern = (r"\b([A-Z][a-zA-Z-]{3,})"
               r"(?:,? (?:et al\.?|and [A-Z][a-zA-Z]+))? \(?((?:19|20)\d\d)\)?")
    # Words that start a sentence in front of a year and are not names.
    not_names = {
        "Section", "Setup", "Every", "Sessions", "September", "August",
        "January", "The", "This", "That", "Read", "Run", "Cell",
        "Basil", "Curtin", "Notebook", "Force", "Buzz", "Echo",
        "Rhythm", "Chords", "Reaction", "Pattern", "Mirror", "Adaptive",
        "Syllables", "Note", "NOTE", "What", "Where", "When", "Since",
        "With", "From", "Both", "Only", "Their", "There", "These",
        "Those", "Which", "While", "After", "Before", "Under", "Above",
        "Below", "Table", "Figure", "Design", "Study", "Amendment",
        "Anything", "Everything",
    }
    missing = sorted({name for name, _year in re.findall(pattern, source)
                      if name not in listed and name not in not_names})
    assert missing == [], (
        f"cited in the notebook but absent from REFERENCES: {missing}")
