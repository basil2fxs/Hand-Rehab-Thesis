"""Regression tests for the analysis, which now lives only in the notebook.

Nothing under tests/ covered the analysis before this file, which is how a
boolean column that read back as all-NaN survived: every check built on
those columns treats missing as "nothing to report", so a block where every
cue failed to reach the device came out looking clean.

The code used to sit in analysis/rehab_analysis.py. It is inside
analysis/session_analysis.ipynb now, so these tests pull it back out of the
.ipynb, exec it once into one namespace and hand that namespace to each
test as the `ra` fixture. Everything below it is unchanged behaviour.
"""
from __future__ import annotations

import ast
import csv
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import matplotlib
matplotlib.use("Agg")

import pandas as pd
import pytest


NOTEBOOK = (Path(__file__).resolve().parents[1]
            / "analysis" / "session_analysis.ipynb")

MODULE_NAME = "session_analysis_notebook"

# Jupyter carries a __future__ statement in one cell forward to every cell
# after it, so cell 1's `from __future__ import annotations` is in force for
# the whole notebook. Compile with that flag and nothing else, rather than
# inheriting whatever happens to be at the top of this file.
FUTURE_FLAGS = annotations.compiler_flag

# Called by the tests below. Checked after the exec so a cell that stops
# defining one of them fails here, loudly, instead of the tests quietly
# covering less than they claim to.
REQUIRED = ("as_bool", "prepare", "build_catalogue", "check", "sec_quality",
            "individuation", "calibration_signature", "sec_compare",
            "sec_rhythm", "sec_phase", "sec_objective_one", "sec_raw",
            "sec_sampling_note")


# --------------------------------------------------- pulling the code out

def _code_cells(path=None):
    """(cell index, source lines) for every code cell in the notebook.

    Cell magics are blanked rather than dropped so a line number in a
    traceback still points at the line you see in Jupyter.
    """
    nb = json.loads(Path(path or NOTEBOOK).read_text())
    cells = []
    for index, cell in enumerate(nb["cells"]):
        if cell["cell_type"] != "code":
            continue
        lines = ["\n" if line.lstrip().startswith(("%", "!")) else line
                 for line in cell["source"]]
        cells.append((index, lines))
    return cells


def _is_definition(node) -> bool:
    """True for an import, a def, a class or a CONSTANT assignment.

    A try/except wrapping only imports counts too. The notebook guards its
    top-level imports that way so a missing package produces a readable
    message instead of a bare ModuleNotFoundError out of the first cell.
    Without this the imports are not top level any more, the extractor
    drops them, and every test here dies on a NameError for pd.
    """
    if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef,
                         ast.AsyncFunctionDef, ast.ClassDef)):
        return True
    if isinstance(node, ast.Try):
        body = list(node.body)
        return bool(body) and all(
            isinstance(n, (ast.Import, ast.ImportFrom)) for n in body)
    if not isinstance(node, (ast.Assign, ast.AnnAssign)):
        return False
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names = []
    for target in targets:
        parts = (target.elts if isinstance(target, (ast.Tuple, ast.List))
                 else [target])
        for part in parts:
            if not isinstance(part, ast.Name):
                return False
            names.append(part.id)
    return bool(names) and all(n.lstrip("_").isupper() for n in names)


def _definitions(index, lines) -> str:
    """The cell with its driver statements blanked out.

    Every code cell is definitions followed by the call that produces that
    section's output, and those calls read sessions/, draw figures and
    write CSVs. Tests want the definitions, so the rest goes, and the
    display and widget calls that need a live front end go with it. Lines
    are blanked, never deleted, to keep the numbering.
    """
    try:
        tree = ast.parse("".join(lines))
    except SyntaxError as exc:
        raise RuntimeError(
            f"{NOTEBOOK.name} cell {index} does not parse: {exc}") from exc

    keep, drop = set(), []
    for node in tree.body:
        starts = [node.lineno]
        starts += [d.lineno for d in getattr(node, "decorator_list", [])]
        span = range(min(starts), node.end_lineno + 1)
        if _is_definition(node):
            keep.update(span)
        else:
            drop.append(span)

    out = list(lines)
    for span in drop:
        for n in span:
            if n not in keep:      # a line shared with a definition stays
                out[n - 1] = "\n"
    return "".join(out)


@pytest.fixture(scope="module")
def ra(tmp_path_factory):
    """The notebook's analysis code, exec'd once into one namespace.

    Into a real module, registered under a name, because @dataclass reads
    the globals of the module its class claims to come from.
    """
    cells = _code_cells()
    if not cells:
        raise RuntimeError(f"no code cells in {NOTEBOOK}")

    module = ModuleType(MODULE_NAME)
    module.__file__ = str(NOTEBOOK)
    sys.modules[MODULE_NAME] = module
    ns = module.__dict__
    try:
        for index, lines in cells:
            source = _definitions(index, lines)
            code = compile(source, f"{NOTEBOOK.name} cell {index}", "exec",
                           flags=FUTURE_FLAGS, dont_inherit=True)
            try:
                exec(code, ns)
            except Exception as exc:
                raise RuntimeError(
                    f"{NOTEBOOK.name} cell {index} would not run: "
                    f"{type(exc).__name__}: {exc}. The tests below cover that "
                    f"cell, so this is a failure, not a cell to skip."
                ) from exc

        missing = [name for name in REQUIRED if name not in ns]
        if missing:
            raise RuntimeError(
                f"{NOTEBOOK.name} no longer defines {', '.join(missing)}. "
                f"Either the notebook dropped them or the extraction above "
                f"threw them away, and either way the tests below are not "
                f"testing what they say they are.")

        # Sections save PNGs under the working directory. Send those to a
        # temporary folder so a test run leaves the repo alone.
        ns["FIGDIR"] = tmp_path_factory.mktemp("figures")
        yield SimpleNamespace(**{k: v for k, v in ns.items()
                                 if not k.startswith("__")})
    finally:
        sys.modules.pop(MODULE_NAME, None)


# ------------------------------------------------------------- fake saves

FINGER_COLS = ["iso_ts", "block_t_s", "participant", "age", "hand", "block",
               "trial", "lane", "time_difference_ms", "early_late", "points",
               "feedback", "error_type", "keys_pressed", "correct_keys",
               "num_presses", "had_incorrect_press", "first_incorrect_ms",
               "first_incorrect_lane", "bpm_at_trial", "streak_at_trial",
               "in_recovery", "song_time_s", "peak_force_n", "impulse_n",
               "phase", "loud_trial", "timeout_ms", "force_window_sum",
               "force_window_peaks", "stim_delivered", "cue_mode"]

EMPTY = [12.0, 15.0, 10.0, 18.0]
PRELOAD = [20.0, 25.0, 18.0, 40.0]


def _calibration(gaps, created_at="2026-08-05T09:00:00"):
    resting = [EMPTY[i] + PRELOAD[i] for i in range(4)]
    return {
        "created_at": created_at,
        "device_port": "/dev/cu.usbserial-test",
        "hand": "right",
        "empty": list(EMPTY),
        "resting": resting,
        "press": [resting[i] + gaps[i] for i in range(4)],
        "press_all": [resting[i] + gaps[i] * 0.88 for i in range(4)],
        "preload": list(PRELOAD),
        "gap": list(gaps),
        "on_delta": [round(g * 0.35, 1) for g in gaps],
        "off_delta": [round(g * 0.20, 1) for g in gaps],
        "multi_finger_deficit": 0.12,
    }


def _write_session(root, name, gaps, *, cal=True, delivered="TRUE",
                   wrong_on=(), clock="090000", day="2026-08-05",
                   n_trials=32, effort=1.40, spill=0.12, created_at=None):
    """One game folder. Behaviour is fixed, so two calls differing only in
    `gaps` describe the same hand on two differently sensitive devices."""
    folder = Path(root) / day / f"{name}_{clock}_classic"
    folder.mkdir(parents=True, exist_ok=True)

    rows = []
    for t in range(1, n_trials + 1):
        lane0 = (t - 1) % 4
        peaks = {i: (effort if i == lane0 else spill) * gaps[i]
                 for i in range(4)}
        rows.append({
            **{c: "" for c in FINGER_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 1.2,
            "participant": name, "age": 30, "hand": "right",
            "block": "classic", "trial": t, "lane": lane0 + 1,
            "time_difference_ms": 400.0 + lane0, "early_late": "Good",
            "points": 3, "feedback": "Good",
            "keys_pressed": lane0 + 1, "correct_keys": lane0 + 1,
            "num_presses": 1,
            "had_incorrect_press": "TRUE" if t in wrong_on else "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "peak_force_n": round(peaks[lane0], 3),
            "impulse_n": round(peaks[lane0] * 0.19, 3),
            "loud_trial": "FALSE", "timeout_ms": 1000,
            "force_window_sum": round(sum(peaks.values()), 3),
            "force_window_peaks": ";".join(
                f"{i + 1}:{v:.3f}" for i, v in sorted(peaks.items())),
            "stim_delivered": delivered, "cue_mode": "both"})

    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
        w.writeheader()
        w.writerows(rows)

    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "classic", "status": "completed",
                          "trials": n_trials, "hit_rate": 1.0,
                          "avg_rt_ms": 400.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": (_calibration(gaps, created_at or "2026-08-05T09:00:00")
                        if cal else {}),
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


REACTION_COLS = ["iso_ts", "block_t_s", "participant", "age", "hand",
                  "block", "trial", "lane", "time_difference_ms",
                  "early_late", "points", "feedback", "error_type",
                  "keys_pressed", "correct_keys", "num_presses",
                  "had_incorrect_press", "first_incorrect_ms",
                  "first_incorrect_lane", "bpm_at_trial", "streak_at_trial",
                  "in_recovery", "song_time_s", "peak_force_n", "impulse_n",
                  "phase", "loud_trial", "timeout_ms", "force_window_sum",
                  "force_window_peaks", "stim_delivered", "cue_flags",
                  "stimulus", "pattern_trial", "cue_target_shown"]


def _write_reaction_session(root, name, *, right_rt_ms, left_rt_ms,
                            clock="090000", day="2026-08-05"):
    """A both-hands reaction block: `right_rt_ms` cues lanes 1-4, then
    `left_rt_ms` cues lanes 5-8, one trial per RT given. Mirrors what
    engine.log_trial now writes for reaction with the per-trial hand
    fix: hand follows the cued lane, not the block-level "both"."""
    folder = Path(root) / day / f"{name}_{clock}_reaction"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    trial_id = 0
    for lane0, rt in enumerate(right_rt_ms):
        trial_id += 1
        rows.append({
            **{c: "" for c in REACTION_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": trial_id * 3.0,
            "participant": name, "age": 30, "hand": "right",
            "block": "reaction", "trial": trial_id, "lane": lane0 + 1,
            "time_difference_ms": rt, "early_late": "Good", "points": 3,
            "feedback": "Good", "keys_pressed": lane0 + 1,
            "correct_keys": lane0 + 1, "num_presses": 1,
            "had_incorrect_press": "FALSE",
            "streak_at_trial": trial_id, "in_recovery": "FALSE",
            "timeout_ms": 2000, "stim_delivered": "TRUE",
            "stimulus": f"choice;fp={1.5 + 0.1 * trial_id:.3f}"})
    for lane0, rt in enumerate(left_rt_ms):
        trial_id += 1
        rows.append({
            **{c: "" for c in REACTION_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": trial_id * 3.0,
            "participant": name, "age": 30, "hand": "left",
            "block": "reaction", "trial": trial_id, "lane": lane0 + 5,
            "time_difference_ms": rt, "early_late": "Good", "points": 3,
            "feedback": "Good", "keys_pressed": lane0 + 5,
            "correct_keys": lane0 + 5, "num_presses": 1,
            "had_incorrect_press": "FALSE",
            "streak_at_trial": trial_id, "in_recovery": "FALSE",
            "timeout_ms": 2000, "stim_delivered": "TRUE",
            "stimulus": f"choice;fp={1.5 + 0.1 * trial_id:.3f}"})

    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)

    all_rt = list(right_rt_ms) + list(left_rt_ms)
    meta = {
        "participant": name, "hand": "both",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(both)",
        "block_summary": {
            "block": "reaction", "status": "completed",
            "trials": len(all_rt), "hit_rate": 1.0,
            "avg_rt_ms": sum(all_rt) / len(all_rt), "duration_s": 60.0,
            "paused_total_s": 0.0, "force_unit": "sensor counts",
            "reaction": {
                "sub_mode": "choice", "level": 1,
                "median_rt_ms": sorted(all_rt)[len(all_rt) // 2],
                "p10_rt_ms": min(all_rt),
                "spearman_rho_rt_vs_fp": 0.05,
                "accuracy": 0.875,
            },
        },
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _write_pattern_session(root, name, *, day, rsi_ms=500, timeout_ms=2000,
                           cue_flags="BS/--", clock="090000",
                           seq_rt_ms=300.0, probe_rt_ms=420.0,
                           mixed_cue_on_probe=None):
    """One pattern-mode game: a trained take followed by a probe take,
    the two-row minimum the mode's own stimulus packing needs to mark
    both pattern_trial values. rsi_ms/timeout_ms land in
    block_summary.pattern the way pattern.py's block_stats() writes
    them; cue_flags lands on the trial rows the way every mode writes
    it. mixed_cue_on_probe overrides just the probe row's cue_flags,
    for the single-game internal-mismatch case."""
    folder = Path(root) / day / f"{name}_{clock}_pattern"
    folder.mkdir(parents=True, exist_ok=True)
    rows = [
        {**{c: "" for c in REACTION_COLS},
         "iso_ts": f"{day}T09:00:00", "block_t_s": 1.0,
         "participant": name, "age": 30, "hand": "right",
         "block": "pattern", "trial": 1, "lane": 1,
         "time_difference_ms": seq_rt_ms, "early_late": "Good",
         "points": 3, "feedback": "Good", "keys_pressed": 1,
         "correct_keys": 1, "num_presses": 1,
         "had_incorrect_press": "FALSE", "streak_at_trial": 1,
         "in_recovery": "FALSE", "timeout_ms": timeout_ms,
         "stim_delivered": "TRUE", "cue_flags": cue_flags,
         "stimulus": "seq;b=1;soc=trained;pos=0",
         "pattern_trial": "TRUE"},
        {**{c: "" for c in REACTION_COLS},
         "iso_ts": f"{day}T09:00:00", "block_t_s": 2.0,
         "participant": name, "age": 30, "hand": "right",
         "block": "pattern", "trial": 2, "lane": 2,
         "time_difference_ms": probe_rt_ms, "early_late": "Good",
         "points": 3, "feedback": "Good", "keys_pressed": 2,
         "correct_keys": 2, "num_presses": 1,
         "had_incorrect_press": "FALSE", "streak_at_trial": 2,
         "in_recovery": "FALSE", "timeout_ms": timeout_ms,
         "stim_delivered": "TRUE",
         "cue_flags": mixed_cue_on_probe or cue_flags,
         "stimulus": "probe;b=2;soc=p0;pos=0",
         "pattern_trial": "FALSE"},
    ]
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)

    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {
            "block": "pattern", "status": "completed", "trials": 2,
            "hit_rate": 1.0, "avg_rt_ms": (seq_rt_ms + probe_rt_ms) / 2,
            "duration_s": 60.0, "paused_total_s": 0.0,
            "force_unit": "sensor counts",
            "pattern": {
                "rsi_ms": rsi_ms, "timeout_ms": timeout_ms,
                "session_learning_score_ms": probe_rt_ms - seq_rt_ms,
                "end_reason": "completed", "short_session": False,
            },
        },
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


# ---------------------------------------------------------- self-contained

class TestNotebookStandsAlone:
    """The whole point of moving the code in. A stray import of the old
    module would run against a file that is not there any more."""

    def test_no_code_cell_imports_the_old_module(self):
        banned = {"rehab_analysis", "parts"}
        offences = []
        for index, lines in _code_cells():
            for node in ast.walk(ast.parse("".join(lines))):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] in banned:
                            offences.append(f"cell {index}: {alias.name}")
                elif isinstance(node, ast.ImportFrom):
                    root = (node.module or "").split(".")[0]
                    if node.level or root in banned:
                        offences.append(f"cell {index}: "
                                        f"{'.' * node.level}{node.module}")
        assert not offences, f"notebook still imports: {'; '.join(offences)}"
        assert not (NOTEBOOK.parent / "rehab_analysis.py").exists()
        assert not (NOTEBOOK.parent / "parts").exists()


# ------------------------------------------------------------ boolean columns

class TestAsBool:
    """read_csv already turns TRUE/FALSE into real booleans, so mapping
    the strings a second time wiped every value."""

    def test_real_booleans_pass_through(self, ra):
        s = pd.Series([True, False, True])
        assert ra.as_bool(s).tolist() == [True, False, True]

    def test_uppercase_text_parses(self, ra):
        s = pd.Series(["TRUE", "FALSE", "TRUE"], dtype=object)
        assert ra.as_bool(s).tolist() == [True, False, True]

    def test_mixed_text_and_blank(self, ra):
        out = ra.as_bool(pd.Series(["TRUE", "", None, "FALSE"], dtype=object))
        assert out.iloc[0] is True
        assert out.iloc[3] is False
        assert pd.isna(out.iloc[1]) and pd.isna(out.iloc[2])

    def test_nothing_becomes_all_nan(self, ra):
        for values in ([True, False], ["TRUE", "FALSE"], ["true", "false"]):
            out = ra.as_bool(pd.Series(values, dtype=object))
            assert out.notna().all(), values


class TestBooleanColumnsSurviveLoading:

    def test_undelivered_cues_are_not_lost(self, ra, tmp_path):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE", wrong_on=(3, 7, 11))
        trials = ra.prepare("all", root=tmp_path)["trials"]

        assert trials["stim_delivered"].notna().all()
        assert (trials["stim_delivered"] == False).sum() == 32
        assert int((trials["had_incorrect_press"] == True).sum()) == 3

    def test_cue_failure_count_is_never_negative(self, ra, tmp_path, capsys):
        """Concatenating games leaves the column as object dtype, where
        `~` is integer bitwise negation."""
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE", clock="090000")
        _write_session(tmp_path, "P2", [49.0, 60.0, 75.0, 49.0],
                       delivered="TRUE", clock="100000")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_quality(ctx["trials"], ctx["folders"], ctx["metas"])

        line = [l for l in capsys.readouterr().out.splitlines()
                if "cue commands not delivered" in l][0]
        assert "32 of 64" in line, line
        assert "-" not in line.split(":")[1]


# ------------------------------------------------------- the calibration fix

class TestCalibrationRemovesSensorSkew:
    """The same hand on two devices whose pinky pads differ. Raw counts
    must disagree and the normalised figure must not."""

    @staticmethod
    def _two_devices(ra, tmp_path):
        _write_session(tmp_path, "HOT", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "EVEN", [49.0, 60.0, 75.0, 49.0],
                       clock="100000")
        return (ra.prepare("HOT", root=tmp_path),
                ra.prepare("EVEN", root=tmp_path))

    def test_raw_counts_disagree_between_devices(self, ra, tmp_path):
        hot, even = self._two_devices(ra, tmp_path)
        h = hot["trials"]
        e = even["trials"]
        raw_h = h.loc[h["finger"] == "Pinky", "peak_force_n"].mean()
        raw_e = e.loc[e["finger"] == "Pinky", "peak_force_n"].mean()
        assert raw_h / raw_e == pytest.approx(115.0 / 49.0, rel=1e-6)

    def test_normalised_force_agrees_between_devices(self, ra, tmp_path):
        hot, even = self._two_devices(ra, tmp_path)
        h = hot["trials"]
        e = even["trials"]
        cal_h = h.loc[h["finger"] == "Pinky", "peak_force_cal"].mean()
        cal_e = e.loc[e["finger"] == "Pinky", "peak_force_cal"].mean()
        assert cal_h == pytest.approx(cal_e, rel=1e-9)
        assert cal_h == pytest.approx(1.40, rel=1e-6)

    def test_normalised_force_is_flat_across_fingers(self, ra, tmp_path):
        hot, _ = self._two_devices(ra, tmp_path)
        per = hot["trials"].groupby("finger")["peak_force_cal"].mean()
        assert per.max() - per.min() == pytest.approx(0.0, abs=1e-9)
        # The raw column over the same trials is anything but flat.
        raw = hot["trials"].groupby("finger")["peak_force_n"].mean()
        assert raw.max() / raw.min() == pytest.approx(115.0 / 49.0, rel=1e-6)

    def test_individuation_matches_between_devices(self, ra, tmp_path):
        hot, even = self._two_devices(ra, tmp_path)
        ind_h = ra.individuation(hot["trials"], hot["calset"])
        ind_e = ra.individuation(even["trials"], even["calset"])
        assert ind_h["corrected"].all() and ind_e["corrected"].all()
        assert (ind_h["individuation_cal"].mean()
                == pytest.approx(ind_e["individuation_cal"].mean(), rel=1e-9))
        # The uncorrected index is the one the hardware moves.
        assert (ind_h["individuation"].mean()
                != pytest.approx(ind_e["individuation"].mean(), rel=1e-4))

    def test_no_calibration_leaves_columns_blank_not_wrong(self, ra, tmp_path):
        _write_session(tmp_path, "OLD", [49.0, 60.0, 75.0, 115.0], cal=False)
        ctx = ra.prepare("all", root=tmp_path)
        trials = ctx["trials"]
        assert ctx["calset"].status == "none"
        assert trials["peak_force_cal"].isna().all()
        assert not trials["force_calibrated"].any()
        assert trials["peak_force_n"].notna().all()


class TestCalibrationGrouping:

    def test_same_timestamp_different_numbers_stay_apart(self, ra, tmp_path):
        """created_at alone is not an identity. Two profiles saved in the
        same second must not collapse into one printed table."""
        _write_session(tmp_path, "HOT", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "EVEN", [49.0, 60.0, 75.0, 49.0],
                       clock="100000")
        cs = ra.prepare("all", root=tmp_path)["calset"]
        assert len(cs.stamps) == 2
        assert cs.status == "multiple"

    def test_identical_calibrations_still_group(self, ra, tmp_path):
        _write_session(tmp_path, "A", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "B", [49.0, 60.0, 75.0, 115.0],
                       clock="100000")
        cs = ra.prepare("all", root=tmp_path)["calset"]
        assert len(cs.stamps) == 1
        assert cs.status == "single"

    def test_signature_ignores_formatting_only_changes(self, ra):
        a = _calibration([49.0, 60.0, 75.0, 115.0])
        b = _calibration([49, 60, 75, 115])
        assert ra.calibration_signature(a) == ra.calibration_signature(b)


class TestGameLabels:

    def test_two_games_in_one_minute_keep_separate_labels(self, ra, tmp_path):
        """Sections group on game_label, so a collision merges two games
        and sec_compare then reports there is nothing to compare."""
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "P2", [49.0, 60.0, 75.0, 49.0],
                       clock="090000")
        trials = ra.prepare("all", root=tmp_path)["trials"]
        assert trials["game"].nunique() == 2
        assert trials["game_label"].nunique() == 2

    def test_distinct_times_keep_the_plain_label(self, ra, tmp_path):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="101500")
        labels = set(ra.prepare("all", root=tmp_path)["trials"]["game_label"])
        assert labels == {"09:00 classic", "10:15 classic"}


# -------------------------------------------------------------- empty states

class TestSectionsAlwaysSaySomething:
    """A section that prints nothing reads as a section that failed."""

    @pytest.mark.parametrize("section", [
        "sec_compare", "sec_rhythm", "sec_phase", "sec_objective_one",
    ])
    def test_trial_sections_explain_themselves(self, ra, tmp_path, capsys,
                                               section):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE")
        ctx = ra.prepare("all", root=tmp_path)
        getattr(ra, section)(ctx["trials"])
        assert capsys.readouterr().out.strip(), f"{section} printed nothing"

    @pytest.mark.parametrize("section", ["sec_raw", "sec_sampling_note"])
    def test_raw_sections_explain_themselves(self, ra, tmp_path, capsys,
                                             section):
        folder = _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0])
        (folder / "raw.csv").write_text(
            "iso_ts,t_perf,sample_idx,fsr1,fsr2,fsr3,fsr4,hand,event,lane,"
            "detail\n"
            + "".join(f"2026-08-05T09:00:0{i % 10},{100.0 + i},{i},0,0,0,0,"
                      f"right,stim,1,trial_id={i}\n" for i in range(60)))
        getattr(ra, section)([folder])
        assert capsys.readouterr().out.strip(), f"{section} printed nothing"


class TestReactionModeByHand:
    """A both-hands reaction block cues one board per trial (lanes 1-4
    right, 5-8 left). Before the engine fix each row still said
    hand="both" and this section never split anything by hand; now
    trials.csv carries the real per-trial side (via load_games's
    lane-derived "side" column) and the section reads it."""

    def test_bilateral_block_prints_a_per_hand_split(self, ra, tmp_path,
                                                      capsys):
        _write_reaction_session(
            tmp_path, "P1",
            right_rt_ms=[280.0, 300.0, 260.0, 310.0],
            left_rt_ms=[420.0, 440.0, 400.0, 460.0])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_mode(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "median and p10 by hand" in out, (
            "sec_reaction_mode did not print a per-hand split for a "
            "bilateral block")
        assert "right" in out and "left" in out

    def test_unilateral_block_skips_the_hand_split(self, ra, tmp_path,
                                                    capsys):
        # Only right-hand lanes fire, so "side" has one unique value
        # and the split is meaningless noise to print.
        _write_reaction_session(tmp_path, "P1",
                                right_rt_ms=[280.0, 300.0, 260.0, 310.0],
                                left_rt_ms=[])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_mode(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "median and p10 by hand" not in out

    def test_block_summary_accuracy_reaches_the_stored_table(
            self, ra, tmp_path, capsys):
        _write_reaction_session(
            tmp_path, "P1",
            right_rt_ms=[280.0, 300.0, 260.0, 310.0],
            left_rt_ms=[420.0, 440.0, 400.0, 460.0])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_mode(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "stored_accuracy" in out
        assert "0.875" in out


class TestCheckAndCatalogue:

    def test_catalogue_and_check_agree(self, ra, tmp_path, capsys):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0])
        cat = ra.build_catalogue(tmp_path)
        assert len(cat) == 1
        assert ra.check(tmp_path, verbose=False) is True
        capsys.readouterr()

    def test_check_reports_an_empty_folder(self, ra, tmp_path, capsys):
        assert ra.check(tmp_path, verbose=False) is False
        assert "no recordings" in capsys.readouterr().out


class TestPatternConsistencyCheck:
    """pattern.py's own docstring says rsi_ms, timeout_ms and cue_flags
    must stay fixed for a participant across sessions, and that
    cue_flags on every row is how the analysis is meant to verify it
    did. sec_pattern_srtt used to group purely on (game, take) and pool
    RTs across whatever sessions got selected, with nothing reading
    those three fields at all: a therapist changing the RSI between
    two sessions would blend a slower rhythm's RTs into a faster one's
    curve with no warning. These pin the check in its place."""

    def test_matching_sessions_pool_into_one_curve(self, ra, tmp_path,
                                                    capsys):
        _write_pattern_session(tmp_path, "P1", day="2026-08-01",
                               rsi_ms=500, timeout_ms=2000)
        _write_pattern_session(tmp_path, "P1", day="2026-08-02",
                               rsi_ms=500, timeout_ms=2000,
                               clock="091000")
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "SPLIT" not in out
        assert "WARNING" not in out
        # Both sessions' takes survive, pooled as one group.
        assert takes["session"].nunique() == 2

    def test_different_rsi_splits_instead_of_pooling(self, ra, tmp_path,
                                                      capsys):
        f1 = _write_pattern_session(tmp_path, "P1", day="2026-08-01",
                                    rsi_ms=500)
        f2 = _write_pattern_session(tmp_path, "P1", day="2026-08-02",
                                    rsi_ms=900, clock="091000")
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "SPLIT" in out
        assert "rsi=500" in out and "rsi=900" in out
        g1, g2 = f1.parent.name + "/" + f1.name, f2.parent.name + "/" + f2.name
        assert g1 in out and g2 in out
        # Nothing is silently dropped: both sessions still come back.
        assert takes["session"].nunique() == 2

    def test_different_timeout_splits_instead_of_pooling(self, ra, tmp_path,
                                                          capsys):
        _write_pattern_session(tmp_path, "P1", day="2026-08-01",
                               timeout_ms=2000)
        _write_pattern_session(tmp_path, "P1", day="2026-08-02",
                               timeout_ms=3000, clock="091000")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "SPLIT" in out
        assert "timeout=2000" in out and "timeout=3000" in out

    def test_different_cue_flags_splits_instead_of_pooling(self, ra,
                                                            tmp_path, capsys):
        _write_pattern_session(tmp_path, "P1", day="2026-08-01",
                               cue_flags="BS/--")
        _write_pattern_session(tmp_path, "P1", day="2026-08-02",
                               cue_flags="B-/--", clock="091000")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "SPLIT" in out
        assert "cue=BS/--" in out and "cue=B-/--" in out

    def test_mixed_cue_flags_within_one_game_warns(self, ra, tmp_path,
                                                    capsys):
        # A single block should carry one cue_flags value; two on one
        # game's rows means the CSV and the mode's settings drifted
        # apart, which is a different failure to the cross-session one
        # and gets its own message rather than silently picking one.
        _write_pattern_session(tmp_path, "P1", day="2026-08-01",
                               cue_flags="BS/--",
                               mixed_cue_on_probe="B-/--")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "WARNING" in out and "not constant WITHIN" in out

    def test_single_session_never_splits(self, ra, tmp_path, capsys):
        # One session cannot disagree with itself; the split machinery
        # must not fire just because there is only one group.
        _write_pattern_session(tmp_path, "P1", day="2026-08-01")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "SPLIT" not in out and "WARNING" not in out
