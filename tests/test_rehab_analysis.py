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

from rehab.data.logger import TRIAL_COLUMNS as BUZZ_HUNT_COLS


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


def _write_chords_session(root, name, *, day, clock="090000",
                          per_chord, outcome_classes, per_hand=None,
                          over_force_trials=0, median_settle_ms=None,
                          sub_trials=None, cross=None):
    """One chords game folder with a shaped block_summary.chords (the
    fields block_stats() actually writes, per_chord now carrying
    w_ms per audit finding #21): enough trials.csv rows to pass
    chord_frame's emptiness check, real analysis reads block_summary.
    `per_chord` is [{"hand","chord","w_ms","d","n","hit_rate",
    "median_span_ms","median_er"}, ...]; `sub_trials` (optional) is
    the per-trial "trials" list block_stats() stores, for the C6
    within-session trajectory."""
    folder = Path(root) / day / f"{name}_{clock}_chords"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    trial_id = 0
    hands_seen = sorted({row["hand"] for row in per_chord})
    for hand in hands_seen:
        board = 0 if hand == "right" else 1
        lanes = [board * 4, board * 4 + 1]
        for _ in range(2):
            trial_id += 1
            rows.append({
                **{c: "" for c in REACTION_COLS},
                "iso_ts": f"{day}T09:00:00", "block_t_s": trial_id * 3.0,
                "participant": name, "age": 30, "hand": hand,
                "block": "chords", "trial": trial_id, "lane": lanes[0] + 1,
                "stimulus": "+".join(str(l + 1) for l in lanes),
                "correct_keys": ",".join(str(l + 1) for l in lanes),
                "early_late": "Good", "points": 10, "feedback": "Chord!",
                "keys_pressed": "+".join(str(l + 1) for l in lanes),
                "num_presses": 2, "had_incorrect_press": "FALSE",
                "streak_at_trial": trial_id, "in_recovery": "FALSE",
                "timeout_ms": 3000, "stim_delivered": "TRUE",
                "force_window_peaks": ""})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)

    chords_summary = {
        "hand": "both" if len(hands_seen) > 1 else hands_seen[0],
        "hands": hands_seen,
        "outcome_classes": outcome_classes,
        "over_force_trials": over_force_trials,
        "median_settle_ms": median_settle_ms,
        "per_chord": per_chord,
        "per_hand": per_hand or {},
        "trials": sub_trials or [],
    }
    if cross is not None:
        # The bimanual section block_stats() writes for bilateral
        # sessions (mirror vs non-mirror, lead-lag, per-hand ER,
        # bilateral deficit).
        chords_summary["cross"] = cross
    meta = {
        "participant": name, "hand": chords_summary["hand"],
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(both)",
        "block_summary": {
            "block": "chords", "status": "completed",
            "trials": trial_id, "hit_rate": 1.0, "avg_rt_ms": 300.0,
            "duration_s": 60.0, "paused_total_s": 0.0,
            "force_unit": "sensor counts",
            "chords": chords_summary,
        },
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _write_syllables_session(root, name, *, day, words, gaps=None,
                             clock="090000", hand="right", level=4,
                             nsyll=2, syllables_extra=None, paced=False,
                             asyn=None, row=False, errs=None):
    """One syllables game folder with words packed into the stimulus
    cell the way syllables.py._pack_stimulus writes them.

    `words` is a list of (word, stress_idx, [(lane1, t_ms, peak), ...])
    tuples, lane1 1-indexed exactly as the mode packs it. `gaps` is the
    right hand's 4-finger calibration gap list, or None for no
    calibration recorded (peak_force_cal stays unusable). `level` and
    `nsyll` go straight into the packed stimulus (lvl=/nsyll=), so a
    caller can build a level 1/2/5/6 block instead of the level-4
    default. `syllables_extra` merges extra keys into
    block_summary.syllables (band_trace, warmup_asyn_mean_ms/sd),
    mirroring what SyllablesMode.block_stats() actually returns.
    `paced`/`asyn` pack paced=1 and an asyn= list (one per word, same
    length every word) so the beat-synchronisation branch runs. `row`
    packs map=row the way _pack_stimulus marks a spanning read-across
    row trial; `errs` is an optional per-word error-code list (default
    every word err=ok)."""
    folder = Path(root) / day / f"{name}_{clock}_syllables"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for trial_id, (word, stress_idx, taps) in enumerate(words, start=1):
        taps_s = ",".join(
            f"{lane1}:{t_ms:.1f}:" + (f"{peak:.1f}" if peak is not None
                                      else "")
            for lane1, t_ms, peak in taps)
        err = (errs[trial_id - 1] if errs else "ok")
        parts = [
            word, f"lvl={level}", "band=C", f"nsyll={nsyll}",
            f"stress={stress_idx}",
        ]
        if row:
            parts.append("map=row")
        parts += [
            f"paced={1 if paced else 0}", "ioi=500", "replay=0",
            f"err={err}", f"taps={taps_s}",
        ]
        if paced and asyn:
            parts.append("asyn=" + ",".join(f"{a:.1f}" for a in asyn))
        stimulus = ";".join(parts)
        rows.append({
            **{c: "" for c in REACTION_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": trial_id * 3.0,
            "participant": name, "age": 30, "hand": hand,
            "block": "syllables", "trial": trial_id, "lane": taps[0][0],
            "stimulus": stimulus,
            "early_late": "Great", "points": 6, "feedback": "Great",
            "keys_pressed": ",".join(str(t[0]) for t in taps),
            "correct_keys": ",".join(str(t[0]) for t in taps),
            "num_presses": len(taps), "had_incorrect_press": "FALSE",
            "streak_at_trial": trial_id, "in_recovery": "FALSE",
            "timeout_ms": 6000, "stim_delivered": "TRUE",
        })
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)

    syllables_summary = {
        "level": level, "accuracy": 1.0, "asyn_sd_ms": None,
        "band_final": "C", "band_trace": ["A", "B", "C"],
    }
    if syllables_extra:
        syllables_summary.update(syllables_extra)
    meta = {
        "participant": name, "hand": hand,
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "syllables", "status": "completed",
                          "trials": len(rows), "hit_rate": 1.0,
                          "avg_rt_ms": 400.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts",
                          "syllables": syllables_summary},
        "calibration": (_calibration(gaps) if gaps is not None else {}),
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


def _write_pattern_flanked_probe_session(root, name, *, day,
                                         before_rts, probe_rts, after_rts,
                                         clock="090000"):
    """One pattern game: a flanker take BEFORE the probe, the probe
    itself, and a flanker take AFTER, each with its own list of RTs
    (one trial per RT). Lets a test give the two flankers different
    trial counts and means, which is exactly the case where the
    trial-count-weighted pool and the mean-of-take-means disagree
    (audit finding #15)."""
    folder = Path(root) / day / f"{name}_{clock}_pattern"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    trial = 0

    def add_take(take_label, kind, soc, rts, pattern_trial):
        nonlocal trial
        for rt in rts:
            trial += 1
            rows.append({
                **{c: "" for c in REACTION_COLS},
                "iso_ts": f"{day}T09:00:00", "block_t_s": float(trial),
                "participant": name, "age": 30, "hand": "right",
                "block": "pattern", "trial": trial, "lane": 1,
                "time_difference_ms": rt, "early_late": "Good",
                "points": 3, "feedback": "Good", "keys_pressed": 1,
                "correct_keys": 1, "num_presses": 1,
                "had_incorrect_press": "FALSE", "streak_at_trial": 1,
                "in_recovery": "FALSE", "timeout_ms": 2000,
                "stim_delivered": "TRUE", "cue_flags": "BS/--",
                "stimulus": f"{kind};b={take_label};soc={soc};pos=0",
                "pattern_trial": "TRUE" if pattern_trial else "FALSE",
            })

    add_take("4", "seq", "trained", before_rts, True)
    add_take("5", "probe", "p0", probe_rts, False)
    add_take("6", "seq", "trained", after_rts, True)

    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)

    fl_mean = (sum(before_rts) / len(before_rts)
              + sum(after_rts) / len(after_rts)) / 2
    mode_style_score = sum(probe_rts) / len(probe_rts) - fl_mean
    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {
            "block": "pattern", "status": "completed", "trials": trial,
            "hit_rate": 1.0, "avg_rt_ms": sum(probe_rts) / len(probe_rts),
            "duration_s": 60.0, "paused_total_s": 0.0,
            "force_unit": "sensor counts",
            "pattern": {
                "rsi_ms": 500, "timeout_ms": 2000,
                "session_learning_score_ms": round(mode_style_score, 1),
                "end_reason": "completed", "short_session": False,
                "demo": False,
            },
        },
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder, mode_style_score


class TestPatternLearningScoreMatchesModeConvention:
    """block_stats() (pattern.py) scores a probe as the mean of its two
    FLANKING TAKE MEANS (a block-mean average), the classic SRTT
    convention; pattern_learning_scores() used to pool both flankers'
    raw trial RTs into one series first, which is trial-count-weighted
    instead. The two agree only when both flankers have the same
    number of trials -- exactly the case every other test in this file
    happens to use, which is how this survived. A short/truncated
    flanker (attrition, an abandoned take) makes them diverge (audit
    finding #15)."""

    def test_score_matches_mode_style_with_uneven_flanker_counts(
            self, ra, tmp_path):
        # Flanker BEFORE the probe has only 2 trials (as if the take
        # got cut short), flanker AFTER has 8: a trial-count-weighted
        # pool skews hard toward the AFTER take's mean, but the mode's
        # own block-mean convention weighs both takes equally.
        folder, mode_style_score = _write_pattern_flanked_probe_session(
            tmp_path, "P1", day="2026-08-01",
            before_rts=[300.0, 320.0],
            probe_rts=[500.0, 520.0, 480.0, 510.0],
            after_rts=[200.0, 210.0, 205.0, 195.0,
                      200.0, 210.0, 205.0, 195.0])
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.pattern_take_table(ctx["trials"])
        scores = ra.pattern_learning_scores(takes)
        assert len(scores) == 1
        nb_score = scores["learning_score_ms"].iloc[0]
        assert nb_score == pytest.approx(mode_style_score, abs=0.1), (
            f"notebook score {nb_score} does not match the mode's own "
            f"block-mean convention {mode_style_score}; "
            "pattern_learning_scores has drifted back to pooling "
            "flanker trials by count instead of averaging take means")

    def test_matches_mode_convention_even_with_equal_flanker_counts(
            self, ra, tmp_path):
        # Sanity check: with equal-sized flankers pooled and
        # mean-of-means agree, so this alone would not have caught the
        # bug -- the uneven-count test above is the one that matters.
        folder, mode_style_score = _write_pattern_flanked_probe_session(
            tmp_path, "P2", day="2026-08-01",
            before_rts=[300.0, 320.0, 310.0, 305.0],
            probe_rts=[500.0, 520.0],
            after_rts=[200.0, 210.0, 205.0, 195.0])
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.pattern_take_table(ctx["trials"])
        scores = ra.pattern_learning_scores(takes)
        nb_score = scores["learning_score_ms"].iloc[0]
        assert nb_score == pytest.approx(mode_style_score, abs=0.1)


class TestPatternStartTrimAlignment:
    """pattern.py drops the first cycle of every take from RT
    aggregates (block-start transient after a rest, not learning) and
    stores that as start_trim in block_summary.pattern. The notebook
    must apply exactly the stored trim, so recomputed take means keep
    matching the stored ones (the finding #15 alignment rule), and
    must leave sessions saved before the trim existed un-trimmed,
    because their stored means are un-trimmed too."""

    def test_stored_start_trim_is_applied(self, ra, tmp_path):
        folder, _ = _write_pattern_flanked_probe_session(
            tmp_path, "P1", day="2026-08-01",
            before_rts=[200.0, 300.0, 300.0],
            probe_rts=[900.0, 500.0, 500.0],
            after_rts=[200.0, 300.0, 300.0])
        meta = json.loads((folder / "metadata.json").read_text())
        meta["block_summary"]["pattern"]["start_trim"] = 1
        (folder / "metadata.json").write_text(json.dumps(meta))
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        by_take = {r["take"]: r for _, r in takes.iterrows()}
        # First trial of every take excluded, so the burst values
        # (200 / 900) never reach a take mean.
        assert by_take["4"]["rt_ms"] == pytest.approx(300.0)
        assert by_take["5"]["rt_ms"] == pytest.approx(500.0)
        assert int(by_take["4"]["n_start_excluded"]) == 1
        assert int(by_take["5"]["n_start_excluded"]) == 1

    def test_sessions_without_start_trim_stay_untrimmed(self, ra,
                                                        tmp_path):
        # Saved before the trim existed: stored take means are
        # un-trimmed, so the recompute must be too.
        _write_pattern_flanked_probe_session(
            tmp_path, "P1", day="2026-08-01",
            before_rts=[200.0, 300.0, 300.0],
            probe_rts=[500.0, 500.0],
            after_rts=[300.0, 300.0])
        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        by_take = {r["take"]: r for _, r in takes.iterrows()}
        assert by_take["4"]["rt_ms"] == pytest.approx(800.0 / 3, abs=0.1)
        assert int(by_take["4"]["n_start_excluded"]) == 0


class TestPatternDemoBlocksExcluded:
    """Test Mode's pattern demo block (block_summary.pattern.demo=True)
    is a supervisor-facing miniature built to write both pattern_trial
    values, not a measurement. sec_pattern_srtt used to pool it in
    alongside real sessions with nothing reading the flag at all
    (audit finding #16)."""

    def test_demo_game_excluded_from_curve_and_scores(self, ra, tmp_path,
                                                       capsys):
        real_folder = _write_pattern_session(tmp_path, "P1",
                                             day="2026-08-01")
        demo_folder = Path(tmp_path) / "2026-08-01" / "P1_091500_pattern"
        demo_folder.mkdir(parents=True, exist_ok=True)
        # Copy the real session's row shape but mark the block a demo.
        import shutil
        shutil.copy(real_folder / "trials.csv",
                    demo_folder / "trials.csv")
        meta = json.loads((real_folder / "metadata.json").read_text())
        meta["block_summary"]["pattern"]["demo"] = True
        (demo_folder / "metadata.json").write_text(json.dumps(meta))

        ctx = ra.prepare("all", root=tmp_path)
        takes = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "EXCLUDED" in out and "demo" in out.lower()
        demo_game = demo_folder.parent.name + "/" + demo_folder.name
        assert demo_game not in takes["game"].unique()
        real_game = real_folder.parent.name + "/" + real_folder.name
        assert real_game in takes["game"].unique()

    def test_selection_of_only_demo_games_reports_nothing(self, ra,
                                                           tmp_path,
                                                           capsys):
        real_folder = _write_pattern_session(tmp_path, "P1",
                                             day="2026-08-01")
        meta = json.loads((real_folder / "metadata.json").read_text())
        meta["block_summary"]["pattern"]["demo"] = True
        (real_folder / "metadata.json").write_text(json.dumps(meta))

        ctx = ra.prepare("all", root=tmp_path)
        result = ra.sec_pattern_srtt(ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "EXCLUDED" in out
        assert result is None


class TestChordsMode:
    """Chords chapter fixes from the 2026-08-08 audit: #21 (per-chord
    hit rate pooled across synchrony windows can mistake a window
    artefact for the enslaving pattern), #20 (missing data-quality,
    across-session learning-curve and within-session subsections)."""

    def _run(self, ra, tmp_path, capsys, **kwargs):
        _write_chords_session(tmp_path, "P1", day="2026-08-01", **kwargs)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_chords(ctx["trials"], ctx["metas"], calset=None)
        return capsys.readouterr().out

    def test_per_chord_table_splits_the_rank_test_by_window(
            self, ra, tmp_path, capsys):
        # A skilled player climbing the ladder meets the easy chord
        # (RP, D=2) at the wide W=250 window and the hard chord (IR,
        # D=6) first at the tight W=100 window. Pooled, IR's low hit
        # rate at the hardest window would read as agreement with D;
        # per window, both windows are near-ceiling and there is not
        # enough spread to call a rank result either way.
        out = self._run(
            ra, tmp_path, capsys,
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0, "d": 2.0,
                 "n": 10, "hit_rate": 0.95, "median_span_ms": 40.0,
                 "median_er": 0.1},
                {"hand": "right", "chord": "IR", "w_ms": 100.0, "d": 6.0,
                 "n": 10, "hit_rate": 0.90, "median_span_ms": 60.0,
                 "median_er": 0.15},
            ],
            outcome_classes={"hit": 18, "late_chord": 2},
        )
        assert "W=250ms" in out
        assert "W=100ms" in out
        # Pooling both chords into one rank test would have been the
        # old behaviour; the new per-window groups have too few chords
        # each to compute a rank at all, which is the honest answer.
        assert "predicted-vs-actual ordering cannot be tested" in out

    def test_data_quality_section_prints_outcome_classes(
            self, ra, tmp_path, capsys):
        out = self._run(
            ra, tmp_path, capsys,
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0, "d": 2.0,
                 "n": 4, "hit_rate": 0.5, "median_span_ms": 40.0,
                 "median_er": 0.1},
            ],
            outcome_classes={"hit": 2, "leak_fail": 1, "over_force": 1},
            over_force_trials=1, median_settle_ms=540.0,
        )
        assert "data quality" in out
        assert "leak_fail" in out
        assert "over-force trials" in out
        assert "540" in out

    def test_single_session_reports_no_learning_curve_yet(
            self, ra, tmp_path, capsys):
        out = self._run(
            ra, tmp_path, capsys,
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0, "d": 2.0,
                 "n": 4, "hit_rate": 0.5, "median_span_ms": 40.0,
                 "median_er": 0.1},
            ],
            outcome_classes={"hit": 2},
            per_hand={"right": {"median_er": 0.1}},
        )
        assert "Only one session with chords" in out

    def test_two_sessions_report_data_but_too_few_for_a_trend(
            self, ra, tmp_path, capsys):
        # A linear slope from two points is meaningless; the section
        # should say so rather than fit one anyway.
        _write_chords_session(
            tmp_path, "P1", day="2026-08-01",
            per_chord=[{"hand": "right", "chord": "RP", "w_ms": 250.0,
                       "d": 2.0, "n": 4, "hit_rate": 0.5,
                       "median_span_ms": 40.0, "median_er": 0.30}],
            outcome_classes={"hit": 2},
            per_hand={"right": {"median_er": 0.30}})
        _write_chords_session(
            tmp_path, "P1", day="2026-08-05",
            per_chord=[{"hand": "right", "chord": "RP", "w_ms": 250.0,
                       "d": 2.0, "n": 4, "hit_rate": 0.9,
                       "median_span_ms": 40.0, "median_er": 0.12}],
            outcome_classes={"hit": 4},
            per_hand={"right": {"median_er": 0.12}})
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_chords(ctx["trials"], ctx["metas"], calset=None)
        out = capsys.readouterr().out
        assert "fewer than 3 sessions" in out

    def test_three_sessions_print_a_falling_er_trend(
            self, ra, tmp_path, capsys):
        for day, er in (("2026-08-01", 0.30), ("2026-08-03", 0.20),
                        ("2026-08-05", 0.12)):
            _write_chords_session(
                tmp_path, "P1", day=day,
                per_chord=[{"hand": "right", "chord": "RP", "w_ms": 250.0,
                           "d": 2.0, "n": 4, "hit_rate": 0.5,
                           "median_span_ms": 40.0, "median_er": er}],
                outcome_classes={"hit": 2},
                per_hand={"right": {"median_er": er}})
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_chords(ctx["trials"], ctx["metas"], calset=None)
        out = capsys.readouterr().out
        assert "ER trend" in out
        assert "-0." in out          # improving (falling) ER

    def test_within_session_subblock_trajectory_reads_the_trials_list(
            self, ra, tmp_path, capsys):
        sub_trials = [
            {"trial": i, "kind": "chord", "hand": "right", "chord": "RP",
             "d": 2.0, "w_ms": 250.0,
             "class": "hit" if i % 2 else "late_chord",
             "span_ms": 40.0, "rt_ms": 300.0, "er": 0.1 + 0.01 * i,
             "subblock": 1 + i // 4}
            for i in range(1, 9)
        ]
        out = self._run(
            ra, tmp_path, capsys,
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0, "d": 2.0,
                 "n": 8, "hit_rate": 0.5, "median_span_ms": 40.0,
                 "median_er": 0.12},
            ],
            outcome_classes={"hit": 4, "late_chord": 4},
            sub_trials=sub_trials,
        )
        # No exception and the "no sub-block data" fallback message did
        # not fire, i.e. the subblock field on the stored trials list
        # was actually read.
        assert "No sub-block breakdown" not in out


class TestChordsBimanualSubsection:
    """The cross-hand upgrade's notebook half: the chapter reads the
    block summary's cross section, keeps it scope-pure (no pooling
    with the within-hand numbers), and says honestly when a selection
    has none."""

    CROSS = {
        "n_chords": 20, "level_final": 3, "level_highest": 4,
        "w_final_ms": 250.0, "tier_final": 4,
        "hit_rate_mirror": 0.9, "hit_rate_nonmirror": 0.6,
        "median_span_mirror_ms": 60.0,
        "median_span_nonmirror_ms": 110.0,
        "median_lag_ms": 35.0,
        "lead_hand_counts": {"right": 14, "left": 6},
        "median_lag_by_lead_ms": {"right": 30.0, "left": 55.0},
        "median_er_left": 0.18, "median_er_right": 0.09,
        "bilateral_deficit": {"right": {"I": 0.85, "M": 0.9},
                              "left": {"I": 0.8}},
    }

    def _run(self, ra, tmp_path, capsys, cross):
        _write_chords_session(
            tmp_path, "P1", day="2026-08-01",
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0,
                 "d": 2.0, "n": 10, "hit_rate": 0.8,
                 "median_span_ms": 40.0, "median_er": 0.1},
                {"hand": "left", "chord": "RP", "w_ms": 250.0,
                 "d": 2.0, "n": 10, "hit_rate": 0.7,
                 "median_span_ms": 50.0, "median_er": 0.12},
            ],
            outcome_classes={"hit": 30, "late_chord": 10},
            cross=cross)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_chords(ctx["trials"], ctx["metas"], calset=None)
        return capsys.readouterr().out

    def test_cross_section_prints_the_bimanual_numbers(
            self, ra, tmp_path, capsys):
        out = self._run(ra, tmp_path, capsys, self.CROSS)
        assert "cross-hand (bimanual) chords" in out
        assert "20 cross-hand chords" in out
        assert "symmetry advantage" in out
        assert "median between-hand lag 35 ms" in out
        assert "right led 14x" in out
        assert "bilateral deficit ratio" in out
        assert "per-hand ER on cross chords: left 0.180, right 0.090" \
            in out
        # Scope purity: the within-hand ER medians must not have
        # swallowed the cross numbers (0.18 or 0.09 as a pooled ER).
        assert "Never pooled with within-hand ER" in out

    def test_selection_without_cross_says_so(self, ra, tmp_path,
                                             capsys):
        out = self._run(ra, tmp_path, capsys, None)
        assert "cross-hand (bimanual) chords" in out
        assert "none in this selection" in out

    def test_cross_subblocks_stay_out_of_the_trajectory(
            self, ra, tmp_path, capsys):
        # Sub-blocks 1-2 within at hit rate 1.0, sub-block 3 cross at
        # 0.0: if the trajectory pooled scopes the cross sub-block
        # would appear as a fatigue dip. It must be excluded.
        sub_trials = (
            [{"trial": i, "kind": "chord", "scope": "within",
              "hand": "right", "chord": "RP", "d": 2.0, "w_ms": 250.0,
              "class": "hit", "span_ms": 40.0, "rt_ms": 300.0,
              "er": 0.1, "subblock": 1 + (i - 1) // 4}
             for i in range(1, 9)]
            + [{"trial": 8 + i, "kind": "chord", "scope": "cross",
                "hand": "both", "chord": "I|M", "d": 9.0,
                "w_ms": 250.0, "class": "late_chord", "span_ms": 400.0,
                "rt_ms": 500.0, "er": None, "subblock": 3}
               for i in range(1, 5)])
        _write_chords_session(
            tmp_path, "P1", day="2026-08-01",
            per_chord=[
                {"hand": "right", "chord": "RP", "w_ms": 250.0,
                 "d": 2.0, "n": 8, "hit_rate": 1.0,
                 "median_span_ms": 40.0, "median_er": 0.1},
            ],
            outcome_classes={"hit": 8, "late_chord": 4},
            sub_trials=sub_trials, cross=self.CROSS)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_chords(ctx["trials"], ctx["metas"], calset=None)
        out = capsys.readouterr().out
        assert "No sub-block breakdown" not in out
        # The chapter object's within-hand span histogram and the
        # trajectory ran on within trials only; the cross rows still
        # got their own subsection.
        assert "cross-hand (bimanual) chords" in out


class TestSyllablesStressRatio:
    """Fix for #28/#99 (2026-08-08 audit): the stress ratio used to be
    peaks[stress] / median(ALL peaks including the stressed one). For a
    2-syllable word that median is always the louder tap, so a
    correctly accented word could never clear any criterion above 1.0.
    The fix mirrors rehab/game/modes/syllables.py's _score_stress: the
    reference is the median of the OTHER taps only, on each finger's
    own calibrated light-press gap."""

    def _ratios(self, ra, tmp_path, capsys, words, gaps=None):
        _write_syllables_session(tmp_path, "P1", day="2026-08-01",
                                 words=words, gaps=gaps)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        return capsys.readouterr().out

    def test_strong_accent_on_a_two_syllable_word_clears_the_criterion(
            self, ra, tmp_path, capsys):
        # galah, stress on the second syllable: a soft first tap (0.5x
        # the calibration gap) and a hard second tap (3.0x). Every pad
        # shares the same gap here, isolating the self-referential
        # median bug from the cross-finger normalisation fix below.
        gaps = [49.0, 49.0, 49.0, 49.0]
        out = self._ratios(
            ra, tmp_path, capsys,
            words=[("galah", 1,
                    [(1, 400.0, 0.5 * gaps[0]), (2, 800.0, 3.0 * gaps[1])])],
            gaps=gaps)
        assert "stressed-tap ratio median 6.00" in out
        # The old formula pinned this at 1.0 ("no accent was produced")
        # for every 2-syllable word no matter how hard the child
        # accented; it must not print that reading here.
        assert "median 1.00" not in out

    def test_cross_finger_pad_gain_is_normalised_before_the_ratio(
            self, ra, tmp_path, capsys):
        # Same raw ADC counts (115) on both taps, but the stressed tap
        # is on a much more sensitive pad (gap 49) than the unstressed
        # tap (gap 115). Un-normalised, equal raw counts read as ratio
        # 1.0 ("no accent"); normalised by each finger's own gap the
        # stressed tap is 115/49 = 2.347x its own reference, a real
        # accent the raw-counts comparison could never show.
        gaps = [49.0, 115.0, 75.0, 115.0]
        out = self._ratios(
            ra, tmp_path, capsys,
            words=[("galah", 0,
                    [(1, 400.0, 115.0), (2, 800.0, 115.0)])],
            gaps=gaps)
        assert "stressed-tap ratio median 2.35" in out

    def test_no_calibration_skips_the_ratio_instead_of_using_raw_counts(
            self, ra, tmp_path, capsys):
        out = self._ratios(
            ra, tmp_path, capsys,
            words=[("galah", 1,
                    [(1, 400.0, 15.0), (2, 800.0, 90.0)])],
            gaps=None)
        assert "1 words dropped: no calibration" in out
        assert "stressed-tap ratio median" not in out


class TestSyllablesSegmentationUnitFilter:
    """Fix for #37 (2026-08-08 audit): nsyll= is the packed UNIT
    count -- syllables at levels 1-4, but onset-rime pairs at level 5
    and graphemes at level 6 -- so grouping the whole frame by nsyll
    plotted a level-6 word's 2-4 phoneme graphemes as though they were
    2-4 "syllables" against the Liberman syllable-tapping anchor. The
    segmentation-by-count chart must be restricted to levels 1-4."""

    def test_level_six_words_are_excluded_and_flagged(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", clock="091000", level=6,
            nsyll=3,
            words=[("sun", 0, [(1, 400.0, None), (2, 800.0, None),
                               (3, 1200.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "1 level 5/6 word(s) excluded" in out

    def test_no_exclusion_note_when_every_word_is_level_one_to_four(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=2, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "excluded from the syllable" not in out


class TestSyllablesWarmupProbe:
    """Fix for #31 (2026-08-08 audit): the warm-up (10 free taps to the
    metronome before the first word) is logged every session, but the
    chapter only ever built asynchrony from paced word trials, so an
    L1/L2 session -- every word free-paced -- printed "no asynchrony
    to draw yet" although block_summary.syllables.warmup_asyn_mean_ms/
    sd carried a synchronisation reading the whole time."""

    def test_level_one_session_still_prints_a_synchronisation_reading(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])],
            syllables_extra={"warmup_taps": 10,
                             "warmup_asyn_mean_ms": -12.3,
                             "warmup_asyn_sd_ms": 18.4})
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        # The old code's only message for an all-free-paced selection.
        assert "no asynchrony to draw yet" in out   # still true of paced
        assert "warm-up synchronisation probe" in out
        assert "18.4" in out

    def test_no_stored_warmup_stats_says_so_plainly(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "No stored warm-up asynchrony yet" in out


class TestSyllablesLatencyCaveat:
    """Fix for #39 (2026-08-08 audit): output-latency measurement is
    genuinely not implemented anywhere (mixer init only forces a
    buffer size, it does not measure the OS output chain), so the
    fix is the caveat the audit's own fix sketch asks for: tell the
    reader the mean asynchrony carries an unknown constant positive
    bias they cannot correct for, without pretending it was fixed."""

    def test_beat_sync_mean_line_carries_the_latency_caveat(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=3, nsyll=2,
            paced=True, asyn=[-20.0, -20.0],
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "CAVEAT: the mean is not corrected for unmeasured audio" in out
        assert "unknown constant positive bias" in out


class TestSyllablesClaimLimits:
    """Fix for #32 (2026-08-08 audit): the chapter never printed the
    mode docstring's mandated statement that the curves are
    within-task learning, not evidence of reading transfer, and never
    surfaced band_trace outside the raw stored-stats table."""

    def test_claim_limit_paragraph_always_prints(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "CLAIM LIMITS" in out
        assert "not evidence that" in out
        assert "reading has improved" in out
        assert "not a diagnostic instrument" in out

    def test_band_trace_is_printed_per_session(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])],
            syllables_extra={"band_trace": ["A", "B"]})
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "band trace per session" in out
        assert "A->B" in out


class TestSyllablesReadAcrossRow:
    """Read-across row regime (2026-08 upgrade): words of 5-8 units
    span both hands with one lane per position and map=row in the
    stimulus. The chapter must (a) hold row trials out of the
    Liberman-anchored chart even at levels 2-4, because Liberman
    tested 1-3 syllable dowel tapping; (b) report the regimes apart,
    because the row adds a spatial-mapping demand; and (c) locate
    each row trial's first wrong position relative to the hand
    transition, the one new motor event the row introduces."""

    # A clean 5-unit row trial: expected 1-indexed row for n=5 is
    # 7,6,5 (left ring/middle/index) then 1,2 (right index/middle).
    ROW5_OK = [(7, 400.0, None), (6, 800.0, None), (5, 1200.0, None),
               (1, 1600.0, None), (2, 2000.0, None)]
    # Same word with the transition fumbled: position 3 (the first
    # right-hand unit) tapped on the wrong finger.
    ROW5_HOP = [(7, 400.0, None), (6, 800.0, None), (5, 1200.0, None),
                (2, 1600.0, None), (1, 2000.0, None)]

    def test_row_words_are_held_out_of_the_liberman_chart(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=2, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", clock="091500", level=2,
            nsyll=5, row=True, hand="both",
            words=[("hippopotamus", 2, self.ROW5_OK)])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "read-across row word(s) also held out" in out
        assert "READ-ACROSS ROW" in out
        assert "either-hand (1-4 units)" in out
        assert "row (5-8 units)" in out

    def test_row_regime_is_inferred_from_nsyll_without_the_flag(
            self, ra, tmp_path, capsys):
        # Rows logged before map=row existed still carry nsyll >= 5,
        # so the regime split must not depend on the flag alone.
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=6, nsyll=5,
            row=False, hand="both",
            words=[("stamp", 0, self.ROW5_OK)])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "READ-ACROSS ROW" in out

    def test_transition_errors_are_located_and_named(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=2, nsyll=5,
            row=True, hand="both", errs=["wrong_order"],
            words=[("hippopotamus", 2, self.ROW5_HOP)])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "first wrong position: at the hand transition 1" in out
        assert "motor artefact" in out

    def test_clean_row_trials_report_no_mismatches(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=2, nsyll=5,
            row=True, hand="both",
            words=[("hippopotamus", 2, self.ROW5_OK)])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "no positional mismatches on row trials" in out
        assert "row taps by hand: left 3, right 2" in out

    def test_claim_limits_name_the_row_as_scaffolding(
            self, ra, tmp_path, capsys):
        _write_syllables_session(
            tmp_path, "P1", day="2026-08-01", level=1, nsyll=2,
            words=[("cat", 0, [(1, 400.0, None), (2, 800.0, None)])])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_syllables(ctx["trials"], ctx["metas"], ctx["calset"])
        out = capsys.readouterr().out
        assert "scaffolding and engagement" in out


# ---------------------------------------------------------------------
# Audit findings #44/#46/#47/#48 (adaptive fix stage, notebook side)
# ---------------------------------------------------------------------

def _write_adaptive_session(root, name, trial_specs, *, clock="090000",
                            day="2026-08-05"):
    """One adaptive game folder built from explicit (lane0, early_late,
    timeout_ms, bpm_at_trial) tuples, so a test controls exactly which
    finger missed and exactly what window/pace each row claims -- the
    two things findings #46/#47/#48 are about."""
    folder = Path(root) / day / f"{name}_{clock}_adaptive"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, (lane0, early_late, timeout_ms, bpm) in enumerate(trial_specs, 1):
        rt = (timeout_ms * 0.3) if early_late != "Miss" else ""
        rows.append({
            **{c: "" for c in FINGER_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 1.5,
            "participant": name, "age": 30, "hand": "right",
            "block": "adaptive", "trial": t, "lane": lane0 + 1,
            "time_difference_ms": rt, "early_late": early_late,
            "points": 0 if early_late == "Miss" else 3,
            "feedback": early_late, "keys_pressed": lane0 + 1,
            "correct_keys": lane0 + 1, "num_presses": 1,
            "had_incorrect_press": "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "bpm_at_trial": bpm, "timeout_ms": timeout_ms,
            "stim_delivered": "TRUE", "cue_mode": "both"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
        w.writeheader()
        w.writerows(rows)
    n = len(trial_specs)
    hits = sum(1 for _, el, _, _ in trial_specs if el != "Miss")
    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "adaptive", "status": "completed",
                          "trials": n, "hit_rate": hits / n,
                          "avg_rt_ms": 300.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestCensoringCaveat:
    """Finding #46: adaptive's response window varies with the cadence
    (timeout_ms per trial), so pooling its RTs with no note is not the
    same measurement as a fixed-window mode's RTs. censoring_caveat
    must fire when a pool holds adaptive trials under different
    windows, and stay quiet when the window never moved."""

    def test_fires_when_adaptive_rows_span_different_windows(
            self, ra, tmp_path):
        _write_adaptive_session(tmp_path, "P1", [
            (0, "Good", 386, 140.0),
            (1, "Good", 1800, 30.0),
            (2, "Good", 386, 140.0),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        caveat = ra.censoring_caveat(ctx["trials"])
        assert caveat is not None
        assert "386" in caveat
        assert "1800" in caveat

    def test_quiet_when_the_window_never_moved(self, ra, tmp_path):
        _write_adaptive_session(tmp_path, "P1", [
            (0, "Good", 1000, 60.0),
            (1, "Good", 1000, 60.0),
            (2, "Good", 1000, 60.0),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        assert ra.censoring_caveat(ctx["trials"]) is None

    def test_reaction_time_headline_prints_the_caveat(
            self, ra, tmp_path, capsys):
        _write_adaptive_session(tmp_path, "P1", [
            (0, "Good", 386, 140.0),
            (1, "Good", 1800, 30.0),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_time(ctx["trials"])
        out = capsys.readouterr().out
        assert "CAVEAT" in out
        assert "survivorship" in out


class TestChallengePointLaneMean:
    """Findings #47/#48: the controller regulates the unweighted mean
    of PER-LANE hit rates, not the trial-share hit rate -- weakness-
    biased sampling pulls the two apart. sec_accuracy must compute and
    report both, name which one the band verdict is checked against,
    and the return dict must carry the per-lane figure too."""

    def test_lanemean_and_trialshare_diverge_under_weakness_bias(
            self, ra, tmp_path, capsys):
        # 3 strong lanes (9/10 hits, oversampled less) and one weak
        # lane sampled far more often (weakness_bias), all misses.
        specs = []
        for _ in range(9):
            specs.append((0, "Good", 1000, 60.0))
        specs.append((0, "Miss", 1000, 60.0))
        for lane0 in (1, 2, 3):
            for _ in range(9):
                specs.append((lane0, "Good", 1000, 60.0))
            specs.append((lane0, "Miss", 1000, 60.0))
        # Now add a heavily-oversampled weak lane pulling the
        # trial-share figure down harder than the per-lane mean.
        for _ in range(60):
            specs.append((0, "Miss", 1000, 60.0))
        _write_adaptive_session(tmp_path, "P1", specs)
        ctx = ra.prepare("all", root=tmp_path)
        result = ra.sec_accuracy(ctx["trials"])
        assert result is not None
        assert "hit_rate_lanemean_scoped" in result
        assert result["hit_rate_lanemean_scoped"] is not None
        # The oversampled weak lane must pull the trial-share figure
        # below the unweighted per-lane mean.
        assert result["hit_rate_scoped"] < result["hit_rate_lanemean_scoped"]
        out = capsys.readouterr().out
        assert "per-lane mean" in out
        assert "trial-share" in out

    def test_per_finger_panel_no_longer_implies_per_finger_regulation(
            self):
        # The notebook source itself, not the exec'd function (which
        # has no real file for inspect.getsource to read back): the
        # per-finger bar panel must not draw the band as if the
        # controller held each finger inside it individually.
        src = NOTEBOOK.read_text()
        start = src.index('"def sec_accuracy(trials):')
        end = src.index('def sec_')  # next section after the caveat below
        end = src.index('"def sec_', start + 10)
        section = src[start:end]
        assert 'ax[1].axhspan(BAND_LO, BAND_HI' not in section


# ---------------------------------------------------------------------
# Audit finding #58 (fix:rhythm stage): fixed-cadence vs RAS comparison
# ---------------------------------------------------------------------

def _write_cadence_ras_session(root, name, *, mode, rows, day="2026-08-05",
                               clock="090000",
                               rhythm_spurious_presses=0):
    """One classic or rhythm game folder built from explicit
    (lane0, early_late, time_difference_ms, had_incorrect_press) tuples,
    for cadence_ras_rows (findings #58) which needs both no-press Miss
    rows (rhythm writes a literal 0.0 into time_difference_ms for
    these) and, for rhythm, a block_summary rhythm_spurious_presses
    count (rhythm's had_incorrect_press is hard-coded FALSE on every
    row, so wrong-finger activity has to come from there instead)."""
    folder = Path(root) / day / f"{name}_{clock}_{mode}"
    folder.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for t, (lane0, early_late, rt_ms, incorrect) in enumerate(rows, 1):
        out_rows.append({
            **{c: "" for c in FINGER_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 1.0,
            "participant": name, "age": 30, "hand": "right",
            "block": mode, "trial": t, "lane": lane0 + 1,
            "time_difference_ms": rt_ms, "early_late": early_late,
            "points": 0 if early_late == "Miss" else 3,
            "feedback": early_late,
            "keys_pressed": ("" if early_late == "Miss" and mode == "rhythm"
                              else lane0 + 1),
            "correct_keys": lane0 + 1,
            "num_presses": 0 if (early_late == "Miss" and mode == "rhythm")
                           else 1,
            "had_incorrect_press": "TRUE" if incorrect else "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "timeout_ms": 300, "stim_delivered": "TRUE", "cue_mode": "both"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
        w.writeheader()
        w.writerows(out_rows)
    n = len(rows)
    hits = sum(1 for _, el, _, _ in rows if el != "Miss")
    bs = {"block": mode, "status": "completed", "trials": n,
          "hit_rate": hits / n if n else 0.0, "avg_rt_ms": 300.0,
          "duration_s": 60.0, "paused_total_s": 0.0,
          "force_unit": "sensor counts"}
    if mode == "rhythm":
        bs["rhythm_spurious_presses"] = rhythm_spurious_presses
    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": bs,
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestCadenceRasNoPressMissTimingSpread:
    """Finding #58a: a rhythm no-press Miss writes a literal 0.0 into
    time_difference_ms (classic writes an empty cell for the same
    outcome), and cadence_ras_rows used to fold Misses straight into
    the timing spread with no filter, so every missed note read as a
    perfectly-on-beat press and pulled timing_sd_ms / timing_iqr_ms
    toward zero purely from how many notes were missed."""

    def test_miss_rows_are_excluded_from_timing_spread(self, ra, tmp_path):
        # Two real hits with a genuine spread, plus a pile of no-press
        # Misses (0.0 in time_difference_ms). Including the Misses
        # would crush the spread toward zero.
        rows = [(0, "Good", 40.0, False), (1, "Good", -60.0, False)]
        rows += [(2, "Miss", 0.0, False) for _ in range(20)]
        _write_cadence_ras_session(tmp_path, "P1", mode="rhythm", rows=rows)
        ctx = ra.prepare("all", root=tmp_path)
        tbl = ra.cadence_ras_rows(ctx["trials"], ctx["metas"])
        ras = tbl[tbl["condition"] == "RAS (rhythm)"].iloc[0]
        # Spread of just [40.0, -60.0]: sd = 70.71, not crushed by 20
        # zeros mixed in.
        assert ras["timing_sd_ms"] > 50.0, (
            f"timing_sd_ms={ras['timing_sd_ms']} was pulled toward zero "
            f"by no-press Miss rows' fabricated 0.0 offset")

    def test_classic_misses_have_no_offset_to_exclude(self, ra, tmp_path):
        # Classic writes an empty cell for a Miss, so trials.dropna()
        # already excludes them; the fix must not touch classic's row.
        rows = [(0, "Good", 400.0, False), (1, "Good", 420.0, False),
                (2, "Miss", "", False)]
        _write_cadence_ras_session(tmp_path, "P1", mode="classic", rows=rows)
        ctx = ra.prepare("all", root=tmp_path)
        tbl = ra.cadence_ras_rows(ctx["trials"], ctx["metas"])
        classic = tbl[tbl["condition"] == "fixed cadence (classic)"].iloc[0]
        assert classic["trials"] == 3
        assert classic["misses"] == 1


class TestCadenceRasWrongFingerFromSpuriousPresses:
    """Finding #58b: had_incorrect_press is hard-coded FALSE on every
    rhythm trial row (rhythm's wrong presses are unmatched spurious
    presses, not a wrong press inside a scored trial), so the RAS
    wrong_finger count used to always read 0 no matter how many
    spurious presses the block summary recorded. cadence_ras_rows must
    read rhythm_spurious_presses from the block summary for the RAS
    row instead."""

    def test_ras_wrong_finger_reads_spurious_press_count(self, ra, tmp_path):
        rows = [(0, "Good", 40.0, False), (1, "Good", -30.0, False)]
        _write_cadence_ras_session(tmp_path, "P1", mode="rhythm", rows=rows,
                                   rhythm_spurious_presses=5)
        ctx = ra.prepare("all", root=tmp_path)
        tbl = ra.cadence_ras_rows(ctx["trials"], ctx["metas"])
        ras = tbl[tbl["condition"] == "RAS (rhythm)"].iloc[0]
        assert ras["wrong_finger"] == 5

    def test_classic_wrong_finger_still_reads_had_incorrect_press(
            self, ra, tmp_path):
        rows = [(0, "Good", 400.0, False), (1, "Late", 900.0, True)]
        _write_cadence_ras_session(tmp_path, "P1", mode="classic", rows=rows)
        ctx = ra.prepare("all", root=tmp_path)
        tbl = ra.cadence_ras_rows(ctx["trials"], ctx["metas"])
        classic = tbl[tbl["condition"] == "fixed cadence (classic)"].iloc[0]
        assert classic["wrong_finger"] == 1


# ------------------------------------------------------------ mirror mode
# Findings #66, #70, #71, #73 (mirror fix stage).

MIRROR_COLS = FINGER_COLS + [
    "mirror_right_rt_ms", "mirror_left_rt_ms", "cue_target_shown"]


def _write_mirror_session(root, name, trial_specs, *, clock="090000",
                          day="2026-08-05"):
    """One bilateral mirror game folder. trial_specs is a list of
    (finger0, right_rt_ms, left_rt_ms, had_incorrect) tuples; finger0
    is the within-hand finger index (0..3), the row's lane is always
    the right-hand copy (finger0 + 1) the way PendingMirrorTrial.lane()
    logs it. time_difference_ms is the later of the two RTs, matching
    MirrorMode._finish's scoring rule; a Miss (either RT missing) or a
    wrong-finger-then-correct trial (had_incorrect) still carries both
    per-hand RTs when both sides eventually pressed, the same way the
    engine logs it (audit finding #65's fix)."""
    folder = Path(root) / day / f"{name}_{clock}_mirror"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, (finger0, right_rt, left_rt, had_incorrect) in enumerate(
            trial_specs, 1):
        both_in = right_rt is not None and left_rt is not None
        rt = max(right_rt, left_rt) if both_in else ""
        label = "Miss" if (had_incorrect or not both_in) else "Great"
        rows.append({
            **{c: "" for c in MIRROR_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 1.5,
            "participant": name, "age": 30, "hand": "both",
            "block": "mirror", "trial": t, "lane": finger0 + 1,
            "time_difference_ms": rt, "early_late": label,
            "points": 0 if label == "Miss" else 6,
            "feedback": label, "keys_pressed": finger0 + 1,
            "correct_keys": f"{finger0 + 1},{finger0 + 5}",
            "num_presses": 2 if both_in else 1,
            "had_incorrect_press": "TRUE" if had_incorrect else "FALSE",
            "mirror_right_rt_ms": "" if right_rt is None else right_rt,
            "mirror_left_rt_ms": "" if left_rt is None else left_rt,
            "cue_target_shown": "TRUE",
            "stim_delivered": "FALSE", "cue_mode": "both"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=MIRROR_COLS)
        w.writeheader()
        w.writerows(rows)
    n = len(trial_specs)
    hits = sum(1 for _, r, l, inc in trial_specs
               if r is not None and l is not None and not inc)
    meta = {
        "participant": name, "hand": "both",
        "started_at": f"{day}T09:00:00",
        # Keyboard fallback: no Arduino, buzz_before still on by
        # default, so stim_delivered is FALSE on every row even though
        # cue_target_shown is TRUE (audit finding #70).
        "source_name": "KeyboardOnlySource",
        "block_summary": {"block": "mirror", "status": "completed",
                          "trials": n, "hit_rate": hits / n if n else 0.0,
                          "avg_rt_ms": 300.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestMirrorSideBasedSplitsExcludeMirror:
    """Finding #66: mirror always logs the right-hand copy of the
    finger as its lane (PendingMirrorTrial.lane()), so `side` derived
    from lane is always "right" for a mirror row -- pooling mirror
    into any left/right split silently reports its later-press RT
    (systematically slower than a unimanual RT) as right-hand data.
    sec_bilateral's headline reaction-time line and per-finger chart
    must exclude mirror rows; the dedicated mirror asynchrony readout
    further down is the correct per-hand view."""

    def test_mirror_rt_does_not_contaminate_the_right_hand_mean(
            self, ra, tmp_path, capsys):
        # A real (non-mirror) bilateral block would need reaction
        # rows; here we isolate the bug by writing ONLY a mirror
        # session and confirming the headline line reports "not
        # available" (no cued non-mirror trials) rather than folding
        # mirror's later-press RT into a right-hand mean.
        _write_mirror_session(tmp_path, "P1", [
            (0, 850.0, 900.0, False),
            (1, 800.0, 950.0, False),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_bilateral(ctx["trials"])
        out = capsys.readouterr().out
        assert "reaction time  not available" in out
        assert "bilateral trials are mirror" in out
        # The dedicated mirror asynchrony section still reports it.
        assert "mirror asynchrony" in out
        assert "right hand mean 825" in out


class TestMirrorAsynchronyGapExcludesFumbles:
    """Finding #73: a wrong-finger-then-correct trial downgrades to
    Miss but both hands still eventually pressed, so the naive
    both_in filter folded the ERROR-RECOVERY time into the mean
    |left - right| coordination gap. Must be filtered on
    had_incorrect_press."""

    def test_fumbled_trial_excluded_from_the_gap(self, ra, tmp_path,
                                                  capsys):
        _write_mirror_session(tmp_path, "P1", [
            (0, 104.2, 109.2, False),        # clean, 5ms gap
            (1, 104.2, 303.7, True),         # fumbled, 199.5ms "gap"
        ])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_bilateral(ctx["trials"])
        out = capsys.readouterr().out
        assert "mean |left - right| gap 5 ms over 1 clean trial" in out
        assert "1 wrong-finger-then-correct trial(s) excluded" in out


class TestMirrorKeyboardNoCueExclusion:
    """Finding #70: a keyboard-only mirror block has buzz_before on by
    default with no Arduino, so stim_delivered is FALSE on every row
    even though the visual cue WAS shown (cue_target_shown TRUE) and
    the patient plainly had something to react to. The no_cue
    exclusion must not drop a trial where another channel delivered
    the cue."""

    def test_keyboard_block_with_visual_cue_is_not_all_excluded(
            self, ra, tmp_path):
        _write_mirror_session(tmp_path, "P1", [
            (0, 150.0, 160.0, False),
            (1, 140.0, 170.0, False),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        kept, flagged, counts = ra.analysable(ctx["trials"])
        assert counts["no_cue"] == 0
        assert counts["analysed"] == 2

    def test_genuine_no_cue_trial_still_excluded(self, ra, tmp_path):
        folder = _write_mirror_session(tmp_path, "P1", [(0, 150.0, 160.0, False)])
        # Flip cue_target_shown off for the one row: neither channel
        # delivered anything.
        rows = list(csv.DictReader(open(folder / "trials.csv")))
        rows[0]["cue_target_shown"] = "FALSE"
        with open(folder / "trials.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=MIRROR_COLS)
            w.writeheader()
            w.writerows(rows)
        ctx = ra.prepare("all", root=tmp_path)
        kept, flagged, counts = ra.analysable(ctx["trials"])
        assert counts["no_cue"] == 1
        assert counts["analysed"] == 0


class TestMirrorPooledReactionTimeCaveat:
    """Finding #71: mirror's time_difference_ms is the LATER of two
    simultaneous presses, systematically slower than a single-hand
    reaction time, but sec_reaction_time pools it into the same
    headline mean/median/CV as classic/adaptive with no note. A
    selection's mode mix (more mirror this session than last) then
    moves the headline even with no change in patient speed. A
    caveat must fire when the pool holds any mirror rows."""

    def test_caveat_fires_when_pool_holds_mirror_rows(
            self, ra, tmp_path, capsys):
        _write_adaptive_session(tmp_path, "P1", [
            (0, "Good", 400, 60.0),
            (1, "Good", 400, 60.0),
        ])
        _write_mirror_session(tmp_path, "P1", [
            (0, 850.0, 900.0, False),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_time(ctx["trials"])
        out = capsys.readouterr().out
        assert "CAVEAT" in out
        assert "1 of" in out and "mirror" in out
        assert "LATER" in out

    def test_no_caveat_when_pool_has_no_mirror_rows(
            self, ra, tmp_path, capsys):
        _write_adaptive_session(tmp_path, "P1", [
            (0, "Good", 400, 60.0),
            (1, "Good", 400, 60.0),
        ])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_reaction_time(ctx["trials"])
        out = capsys.readouterr().out
        assert "mirror" not in out.lower()


# --------------------------------------------------------------- buzz_hunt
# Audit findings #90, #91, #95, #96, #97 (fix:buzz_hunt stage).

def _bh_pack(lanes):
    return "-".join(str(int(x)) for x in lanes)


def _write_buzz_hunt_span_session(root, name, span_specs, *, day="2026-08-05",
                                  clock="090000", hand="right"):
    """One buzz_hunt game folder with only span-stage rows.

    span_specs: list of (length, hebb, played_lanes, pressed_lanes)
    tuples, matching the stimulus cell BuzzHuntMode._close_span writes
    ("span;len=..;hebb=..;played=..;pressed=..;stim_failed=..").
    """
    folder = Path(root) / day / f"{name}_{clock}_buzz_hunt"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, (length, hebb, played, pressed) in enumerate(span_specs, 1):
        correct = played == pressed
        rows.append({
            **{c: "" for c in BUZZ_HUNT_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 2.0,
            "participant": name, "age": 30, "hand": hand,
            "block": "buzz_hunt", "trial": t, "lane": played[0] + 1,
            "early_late": "Great" if correct else "Miss",
            "points": 4 if correct else 0, "feedback": "Great" if correct
            else "Miss", "keys_pressed": _bh_pack([p + 1 for p in pressed]),
            "correct_keys": _bh_pack([p + 1 for p in played]),
            "num_presses": len(pressed), "had_incorrect_press": "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "cue_target_shown": "FALSE",
            "stimulus": (f"span;len={length};hebb={1 if hebb else 0};"
                        f"played={_bh_pack(played)};"
                        f"pressed={_bh_pack(pressed)};"
                        f"stim_failed=False"),
            "waveform": "buzz_seq", "stim_delivered": "TRUE"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BUZZ_HUNT_COLS)
        w.writeheader()
        w.writerows(rows)
    meta = {
        "participant": name, "hand": hand,
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "buzz_hunt", "status": "completed",
                          "trials": len(span_specs), "hit_rate": None,
                          "avg_rt_ms": None, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _write_buzz_hunt_gap_session(root, name, gap_specs, *, day="2026-08-05",
                                 clock="090000", hand="right"):
    """One buzz_hunt game folder with only gap-stage rows.

    gap_specs: list of (two, taps, gap_ms) tuples, matching the
    stimulus cell BuzzHuntMode._close_gap writes.
    """
    folder = Path(root) / day / f"{name}_{clock}_buzz_hunt"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, (two, taps, gap_ms) in enumerate(gap_specs, 1):
        answered_two = taps >= 2
        responded = taps > 0
        correct = responded and answered_two == two
        rows.append({
            **{c: "" for c in BUZZ_HUNT_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 2.0,
            "participant": name, "age": 30, "hand": hand,
            "block": "buzz_hunt", "trial": t, "lane": 1,
            "early_late": "Great" if correct else "Miss",
            "points": 3 if correct else 0, "feedback": "Great" if correct
            else "Miss", "keys_pressed": "1" if taps else "",
            "correct_keys": "1", "num_presses": taps,
            "had_incorrect_press": "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "cue_target_shown": "FALSE",
            "stimulus": (f"gap;hand={hand};finger=index;"
                        f"two={1 if two else 0};gap_ms={gap_ms:.0f};"
                        f"taps={taps};stair_ms={gap_ms:.0f};"
                        f"reversal=False;stim_failed=False"),
            "waveform": "buzz_gap", "stim_delivered": "TRUE"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BUZZ_HUNT_COLS)
        w.writeheader()
        w.writerows(rows)
    meta = {
        "participant": name, "hand": hand,
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "buzz_hunt", "status": "completed",
                          "trials": len(gap_specs), "hit_rate": None,
                          "avg_rt_ms": None, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _write_buzz_hunt_distractor_session(root, name, records, *,
                                        day="2026-08-05", clock="090000"):
    """One bilateral buzz_hunt game folder with distractor-stage rows.

    records: list of (target_lane0, decoy_lane0, pressed_lane0) global
    0-based lanes, matching BuzzHuntMode._close_buzz's distractor
    stimulus cell.
    """
    folder = Path(root) / day / f"{name}_{clock}_buzz_hunt"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, (target, decoy, pressed) in enumerate(records, 1):
        lured = pressed == decoy
        correct = pressed == target
        hand = "left" if target >= 4 else "right"
        rows.append({
            **{c: "" for c in BUZZ_HUNT_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 2.0,
            "participant": name, "age": 30, "hand": "both",
            "block": "buzz_hunt", "trial": t, "lane": target + 1,
            "early_late": "Great" if correct else "Miss",
            "points": 4 if correct else 0, "feedback": "Great" if correct
            else "Miss", "keys_pressed": str(pressed + 1),
            "correct_keys": str(target + 1), "num_presses": 1,
            "had_incorrect_press": "FALSE" if correct else "TRUE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "cue_target_shown": "FALSE",
            "stimulus": (f"distractor;hand={hand};finger=index;"
                        f"dur_ms=300;stair_ms=300;reversal=False;"
                        f"lured={lured};stim_failed=False"),
            "waveform": "buzz", "stim_delivered": "TRUE"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BUZZ_HUNT_COLS)
        w.writeheader()
        w.writerows(rows)
    meta = {
        "participant": name, "hand": "both",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(both)",
        "block_summary": {"block": "buzz_hunt", "status": "completed",
                          "trials": len(records), "hit_rate": None,
                          "avg_rt_ms": None, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _write_buzz_hunt_reversal_session(root, name, reversals, *,
                                      day="2026-08-05", clock="090000",
                                      hand="right"):
    """One buzz_hunt game folder whose raw.csv carries only the given
    duration-staircase reversal events (level_ms per reversal, in
    order), plus one trivial loc trial row so the folder is
    discovered. Matches buzz_hunt_reversal's detail cell."""
    folder = Path(root) / day / f"{name}_{clock}_buzz_hunt"
    folder.mkdir(parents=True, exist_ok=True)
    rows = [{
        **{c: "" for c in BUZZ_HUNT_COLS},
        "iso_ts": f"{day}T09:00:00", "block_t_s": 2.0,
        "participant": name, "age": 30, "hand": hand,
        "block": "buzz_hunt", "trial": 1, "lane": 1,
        "early_late": "Great", "points": 3, "feedback": "Great",
        "keys_pressed": "1", "correct_keys": "1", "num_presses": 1,
        "had_incorrect_press": "FALSE", "streak_at_trial": 1,
        "in_recovery": "FALSE", "cue_target_shown": "FALSE",
        "stimulus": "loc;hand=right;finger=index;dur_ms=300;"
                    "stair_ms=300;reversal=False;lured=False;"
                    "stim_failed=False",
        "waveform": "buzz", "stim_delivered": "TRUE"}]
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BUZZ_HUNT_COLS)
        w.writeheader()
        w.writerows(rows)

    raw_cols = ["iso_ts", "t_perf", "sample_idx", "fsr1", "fsr2", "fsr3",
               "fsr4", "fsr5", "fsr6", "fsr7", "fsr8", "hand", "event",
               "lane", "detail"]
    raw_rows = []
    for n, level_ms in enumerate(reversals, 1):
        raw_rows.append({
            **{c: "" for c in raw_cols},
            "iso_ts": f"{day}T09:00:00", "t_perf": n * 3.0,
            "hand": hand, "event": "buzz_hunt_reversal", "lane": 0,
            "detail": (f"stair=duration;hand={hand};"
                      f"level_ms={level_ms:.0f};n={n}")})
    with open(folder / "raw.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=raw_cols)
        w.writeheader()
        w.writerows(raw_rows)

    meta = {
        "participant": name, "hand": hand,
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "buzz_hunt", "status": "completed",
                          "trials": 1, "hit_rate": None,
                          "avg_rt_ms": None, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestBuzzHuntHebbSlopeByLength:
    """Finding #90: hebb_sequence draws a DIFFERENT hidden sequence
    per span LENGTH, so pooling hebb-flagged trials of different
    lengths into one slope fits a line over item accuracies that were
    never repeats of each other."""

    def test_different_lengths_are_not_pooled_into_one_repeated_count(
            self, ra, tmp_path, capsys):
        specs = [
            (4, True, [0, 2, 0, 1], [0, 2, 0, 1]),   # repeat 1, correct
            (4, False, [1, 3, 1, 2], [1, 3, 1, 2]),
            (4, True, [0, 2, 0, 1], [0, 1, 0, 1]),   # repeat 2, one wrong
            (7, True, [0, 3, 2, 0, 3, 0, 3], [0, 3, 2, 0, 3, 0, 3]),
        ]
        _write_buzz_hunt_span_session(tmp_path, "P1", specs)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_tactile(ctx["folders"], ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        # The length-4 sequence really did repeat twice.
        assert "length 4: repeated 2 time(s)" in out
        # The length-7 sequence occurred once: unusable, not pooled
        # into a 3-point slope with the length-4 trials.
        assert "length 7: repeated 1 time(s)" in out
        assert "unusable" in out
        assert "repeated 3 time(s)" not in out

    def test_prints_nothing_pooled_when_no_span_trials(
            self, ra, tmp_path, capsys):
        _write_buzz_hunt_gap_session(tmp_path, "P1", [(True, 2, 200.0)])
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_tactile(ctx["folders"], ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "Hebb repetition learning" not in out


class TestBuzzHuntGapNoResponseExclusion:
    """Finding #91: a no-response gap trial says nothing about the
    percept (the mode's own staircase holds still on silence), so it
    must not count as a false 'two' or feed the psychometric fit's
    hit column."""

    def test_no_responses_do_not_inflate_the_false_two_rate(
            self, ra, tmp_path, capsys):
        specs = [(False, 1, 150.0) for _ in range(8)]  # correct
        specs += [(False, 0, 150.0), (False, 0, 150.0)]  # no response
        _write_buzz_hunt_gap_session(tmp_path, "P1", specs)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_tactile(ctx["folders"], ctx["trials"], ctx["metas"])
        out = capsys.readouterr().out
        assert "false 'two' on responded one-buzz trials 0%" in out
        assert "2 no-response" in out


class TestBuzzHuntGapFitFloorFromMeasuredBias:
    """Finding #97: the gap psychometric fit's guess floor must come
    from the participant's own measured false-two rate on one-buzz
    trials, not a fixed 0.1 constant."""

    def test_gamma_floor_is_not_the_fixed_constant(self):
        src = NOTEBOOK.read_text()
        start = src.index('"def sec_tactile(folders')
        section = src[start:start + 20000]
        assert "gamma=0.1" not in section
        assert "gamma = fa if np.isfinite(fa)" in section


class TestBuzzHuntConfusionExcludesDistractor:
    """Finding #95: the localisation confusion matrix (the Weber 2023
    misreferral analogue) must not include distractor-stage presses,
    a designed decoy-lure error and a different mechanism."""

    def test_distractor_lure_does_not_enter_the_loc_matrix(
            self, ra, tmp_path):
        # One clean localisation trial (lane 0 -> 0) and one distractor
        # trial lured onto the decoy (target 5, decoy 2, pressed 2).
        _write_buzz_hunt_distractor_session(
            tmp_path, "P1", [(5, 2, 2)])
        ctx = ra.prepare("all", root=tmp_path)
        rows = ra.bh_frame(ctx["trials"])
        m, lanes = ra.bh_confusion(rows)
        assert m is None or m.sum() == 0, (
            "a distractor-only selection must not populate the "
            "localisation confusion matrix")


class TestBuzzHuntReversalPlotGroupedByGame:
    """Finding #96: a reversal index restarts at 1 in every session,
    so the headline reversal plot and threshold estimate must be
    grouped by (game, hand), not hand alone, or two sessions' reversal
    sequences zigzag together and their thresholds blend."""

    def test_two_sessions_produce_two_separate_threshold_estimates(
            self, ra, tmp_path, capsys):
        _write_buzz_hunt_reversal_session(
            tmp_path, "P1", [300.0, 300.0, 280.0, 280.0, 260.0, 260.0],
            clock="090000")
        _write_buzz_hunt_reversal_session(
            tmp_path, "P1", [150.0, 150.0, 140.0, 140.0, 130.0, 130.0],
            clock="100000")
        ctx = ra.prepare("all", root=tmp_path)
        result = ra.sec_tactile(ctx["folders"], ctx["trials"], ctx["metas"])
        capsys.readouterr()
        thresholds = result["thresholds"]
        assert len(thresholds) == 2, (
            "each session's reversals must produce its own threshold "
            "estimate, not one blended figure")
        ests = sorted(t["threshold_ms"] for t in thresholds)
        # Each session's own tail-of-reversals mean, not a figure
        # that blends the two very different sessions together.
        assert ests[0] < 200.0 < ests[1]


def _write_buzz_hunt_segment_session(root, name, *, day="2026-08-05",
                                     clock="090000", trial=1,
                                     respond_start, respond_end,
                                     raw_start, raw_end,
                                     waveform="buzz"):
    """One buzz_hunt game folder with a single trial whose packed
    "respond" segment and raw segment_start/segment_end markers can be
    set independently, for the segment cut check (audit finding #102):
    a folder-filtering bug that let one game's markers be checked
    against every selected game's rows, and buzz_hunt's own
    documented one-frame respond-start offset."""
    from rehab.data.logger import pack_segments
    folder = Path(root) / day / f"{name}_{clock}_buzz_hunt"
    folder.mkdir(parents=True, exist_ok=True)
    seg_cell = pack_segments([("stim", respond_start - 0.3, respond_start),
                              ("respond", respond_start, respond_end)])
    rows = [{
        **{c: "" for c in BUZZ_HUNT_COLS},
        "iso_ts": f"{day}T09:00:00", "block_t_s": 2.0,
        "participant": name, "age": 30, "hand": "right",
        "block": "buzz_hunt", "trial": trial, "lane": 1,
        "early_late": "Great", "points": 3, "feedback": "Great",
        "keys_pressed": "1", "correct_keys": "1", "num_presses": 1,
        "had_incorrect_press": "FALSE", "streak_at_trial": 1,
        "in_recovery": "FALSE", "cue_target_shown": "FALSE",
        "stimulus": "loc;hand=right;finger=index;dur_ms=300;"
                    "stair_ms=300;reversal=False;lured=False;"
                    "stim_failed=False",
        "waveform": waveform, "stim_delivered": "TRUE",
        "segment_times": seg_cell}]
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=BUZZ_HUNT_COLS)
        w.writeheader()
        w.writerows(rows)

    raw_cols = ["iso_ts", "t_perf", "sample_idx", "fsr1", "fsr2", "fsr3",
               "fsr4", "fsr5", "fsr6", "fsr7", "fsr8", "hand", "event",
               "lane", "detail"]
    raw_rows = [
        {**{c: "" for c in raw_cols}, "iso_ts": f"{day}T09:00:00",
         "t_perf": raw_start, "hand": "right", "event": "segment_start",
         "lane": 0, "detail": f"trial_id={trial};segment=respond"},
        {**{c: "" for c in raw_cols}, "iso_ts": f"{day}T09:00:00",
         "t_perf": raw_end, "hand": "right", "event": "segment_end",
         "lane": 0, "detail": f"trial_id={trial};segment=respond"},
    ]
    # Pad past load_raw's 200-byte minimum-size guard.
    raw_rows += [{**{c: "" for c in raw_cols}} for _ in range(10)]
    with open(folder / "raw.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=raw_cols)
        w.writeheader()
        w.writerows(raw_rows)

    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "buzz_hunt", "status": "completed",
                          "trials": 1, "hit_rate": None,
                          "avg_rt_ms": None, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestBuzzHuntSegmentCutCheckPerFolder:
    """Finding #102: the segment cut check compared every selected
    game's rows against every folder's markers, so trial-id
    collisions across games reported mostly false mismatches, and
    buzz_hunt's documented one-display-frame respond-start offset
    against the raw marker needs its own wider tolerance rather than
    being flagged as a real cut error."""

    def test_two_games_sharing_trial_1_do_not_cross_contaminate(
            self, ra, tmp_path, capsys):
        _write_buzz_hunt_segment_session(
            tmp_path, "P1", clock="090000", trial=1,
            respond_start=100.0, respond_end=100.5,
            raw_start=100.0, raw_end=100.5)
        _write_buzz_hunt_segment_session(
            tmp_path, "P1", clock="100000", trial=1,
            respond_start=200.0, respond_end=200.7,
            raw_start=200.0, raw_end=200.7)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_continuous(ctx["folders"], ctx["trials"])
        out = capsys.readouterr().out
        assert "0 mismatched" in out
        assert "investigate before" not in out

    def test_one_frame_respond_offset_is_not_flagged(self, ra, tmp_path,
                                                      capsys):
        _write_buzz_hunt_segment_session(
            tmp_path, "P1", respond_start=100.0, respond_end=100.5,
            raw_start=100.017, raw_end=100.517)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_continuous(ctx["folders"], ctx["trials"])
        out = capsys.readouterr().out
        assert "0 mismatched" in out

    def test_a_genuinely_wrong_cut_is_still_caught(self, ra, tmp_path,
                                                    capsys):
        _write_buzz_hunt_segment_session(
            tmp_path, "P1", respond_start=100.0, respond_end=100.5,
            raw_start=100.3, raw_end=100.8)
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_continuous(ctx["folders"], ctx["trials"])
        out = capsys.readouterr().out
        assert "1 mismatched" in out


# ------------------------------------------------------- notebook-wide
# Findings #100, #101, #105, #106, #108 (fix:notebook stage). Unlike the
# per-mode findings above, each of these is a bug in a section that pools
# every selected mode together, not in one mode's own chapter.

class TestBilateralExcludesAnticipationTrials:
    """Finding #100: sec_bilateral ran its reaction-time and force lines
    on raw `trials`, so a sub-100 ms anticipation press (not a plausible
    reaction) rode straight into the left/right mean. On the shipped
    data that gave a left reaction time of 53.4 ms built entirely from
    eight anticipations. Restricted to analysable(trials) now."""

    def test_left_mean_excludes_the_anticipation_press(self, ra, tmp_path):
        _write_reaction_session(tmp_path, "P1",
                                right_rt_ms=[300.0],
                                left_rt_ms=[45.0, 315.0])
        ctx = ra.prepare("all", root=tmp_path)
        out = ra.sec_bilateral(ctx["trials"])
        assert out["rt_left"] == pytest.approx(315.0), (
            f"rt_left={out['rt_left']} still carries the 45 ms "
            "anticipation press (audit finding #100)")


def _write_dose_session(root, name, *, day="2026-08-05", clock="090000"):
    """One reaction game folder with three real movement trials, one
    CatchOk (a correctly WITHHELD press -- the correct response there is
    not pressing) and one row whose cue never reached the device, for
    sec_dose's repetition count (audit finding #100)."""
    folder = Path(root) / day / f"{name}_{clock}_reaction"
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for t, rt in enumerate([300.0, 310.0, 320.0], 1):
        rows.append({
            **{c: "" for c in REACTION_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 3.0,
            "participant": name, "age": 30, "hand": "right",
            "block": "reaction", "trial": t, "lane": 1,
            "time_difference_ms": rt, "early_late": "Good", "points": 3,
            "feedback": "Good", "keys_pressed": 1, "correct_keys": 1,
            "num_presses": 1, "had_incorrect_press": "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "timeout_ms": 2000, "stim_delivered": "TRUE",
            "cue_target_shown": "TRUE", "stimulus": "choice;fp=1.500"})
    rows.append({  # a correctly-withheld catch trial: no press at all
        **{c: "" for c in REACTION_COLS},
        "iso_ts": f"{day}T09:00:00", "block_t_s": 12.0,
        "participant": name, "age": 30, "hand": "right",
        "block": "reaction", "trial": 4, "lane": "",
        "time_difference_ms": "", "early_late": "CatchOk", "points": 1,
        "feedback": "CatchOk", "keys_pressed": "", "correct_keys": "",
        "num_presses": 0, "had_incorrect_press": "FALSE",
        "streak_at_trial": 4, "in_recovery": "FALSE",
        "timeout_ms": 2000, "stim_delivered": "TRUE",
        "cue_target_shown": "TRUE", "stimulus": "choice;catch"})
    rows.append({  # cue never reached the device: nothing was presented
        **{c: "" for c in REACTION_COLS},
        "iso_ts": f"{day}T09:00:00", "block_t_s": 15.0,
        "participant": name, "age": 30, "hand": "right",
        "block": "reaction", "trial": 5, "lane": 1,
        "time_difference_ms": "", "early_late": "Miss", "points": 0,
        "feedback": "Miss", "keys_pressed": "", "correct_keys": 1,
        "num_presses": 0, "had_incorrect_press": "FALSE",
        "streak_at_trial": 0, "in_recovery": "FALSE",
        "timeout_ms": 2000, "stim_delivered": "FALSE",
        "cue_target_shown": "FALSE", "stimulus": "choice;fp=1.700"})
    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REACTION_COLS)
        w.writeheader()
        w.writerows(rows)
    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "reaction", "status": "completed",
                          "trials": 5, "hit_rate": 0.6,
                          "avg_rt_ms": 310.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": {},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class TestDoseCountsAnalysableMovementTrialsOnly:
    """Finding #100: sec_dose used to count reps = len(trials), so a
    trial whose cue never reached the device (nothing was presented)
    and a CatchOk trial (the correct response is NOT pressing) both
    counted as a repetition against Lang's clinical benchmark."""

    def test_reps_excludes_catch_and_no_cue_rows(self, ra, tmp_path,
                                                  capsys):
        _write_dose_session(tmp_path, "P1")
        ctx = ra.prepare("all", root=tmp_path)
        out = ra.sec_dose(ctx["trials"])
        assert out["reps"] == 3, (
            f"reps={out['reps']}, should be 3 real movement trials, "
            "not 5 (audit finding #100)")
        printed = capsys.readouterr().out
        assert "analysable movement trials" in printed


class TestCrosstalkAndIndividuationExcludeErrorTrials:
    """Finding #101: crosstalk_cells and individuation had no outcome
    filter, so a Miss or a wrong-finger-first trial's force spread
    pooled straight into "force on the quiet fingers", reading a
    deliberate wrong press as finger enslavement."""

    def _write(self, root):
        def peaks_cell(vals):
            return ";".join(f"{i + 1}:{v:.3f}" for i, v in enumerate(vals))
        folder = Path(root) / "2026-08-05" / "P1_090000_classic"
        folder.mkdir(parents=True, exist_ok=True)
        rows = [
            {  # clean hit: small, plausible leak onto the neighbours
                **{c: "" for c in FINGER_COLS},
                "iso_ts": "2026-08-05T09:00:00", "block_t_s": 1.2,
                "participant": "P1", "age": 30, "hand": "right",
                "block": "classic", "trial": 1, "lane": 1,
                "time_difference_ms": 400.0, "early_late": "Good",
                "points": 3, "feedback": "Good",
                "keys_pressed": 1, "correct_keys": 1, "num_presses": 1,
                "had_incorrect_press": "FALSE", "streak_at_trial": 1,
                "in_recovery": "FALSE",
                "peak_force_n": 100.0, "impulse_n": 19.0,
                "force_window_sum": 130.0,
                "force_window_peaks": peaks_cell([100.0, 20.0, 5.0, 5.0]),
                "stim_delivered": "TRUE", "cue_mode": "both"},
            {  # Miss, with a big spurious spike on a neighbour: a
               # response error, not spill from the intended press
                **{c: "" for c in FINGER_COLS},
                "iso_ts": "2026-08-05T09:00:00", "block_t_s": 2.4,
                "participant": "P1", "age": 30, "hand": "right",
                "block": "classic", "trial": 2, "lane": 1,
                "time_difference_ms": "", "early_late": "Miss",
                "points": 0, "feedback": "Miss",
                "keys_pressed": "", "correct_keys": 1, "num_presses": 0,
                "had_incorrect_press": "FALSE", "streak_at_trial": 0,
                "in_recovery": "FALSE",
                "peak_force_n": "", "impulse_n": "",
                "force_window_sum": 98.0,
                "force_window_peaks": peaks_cell([2.0, 90.0, 3.0, 3.0]),
                "stim_delivered": "TRUE", "cue_mode": "both"},
            {  # wrong finger pressed first, then corrected
                **{c: "" for c in FINGER_COLS},
                "iso_ts": "2026-08-05T09:00:00", "block_t_s": 3.6,
                "participant": "P1", "age": 30, "hand": "right",
                "block": "classic", "trial": 3, "lane": 1,
                "time_difference_ms": 600.0, "early_late": "Good",
                "points": 1, "feedback": "Good",
                "keys_pressed": "2,1", "correct_keys": 1, "num_presses": 2,
                "had_incorrect_press": "TRUE", "streak_at_trial": 0,
                "in_recovery": "FALSE",
                "peak_force_n": 95.0, "impulse_n": 18.0,
                "force_window_sum": 175.0,
                "force_window_peaks": peaks_cell([95.0, 80.0, 0.0, 0.0]),
                "stim_delivered": "TRUE", "cue_mode": "both"},
        ]
        with open(folder / "trials.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
            w.writeheader()
            w.writerows(rows)
        meta = {
            "participant": "P1", "hand": "right",
            "started_at": "2026-08-05T09:00:00",
            "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
            "block_summary": {"block": "classic", "status": "completed",
                              "trials": 3, "hit_rate": 0.667,
                              "avg_rt_ms": 500.0, "duration_s": 60.0,
                              "paused_total_s": 0.0,
                              "force_unit": "sensor counts"},
            "calibration": {},
        }
        (folder / "metadata.json").write_text(json.dumps(meta))
        return folder

    def test_crosstalk_cells_only_uses_the_clean_hit(self, ra, tmp_path):
        self._write(tmp_path)
        ctx = ra.prepare("all", root=tmp_path)
        cells, n_multi = ra.crosstalk_cells(ctx["trials"])
        assert set(cells["row_id"]) == {0}, (
            "the Miss and the wrong-finger trial must not contribute "
            "cells (audit finding #101)")
        assert cells["leak_frac"].mean() == pytest.approx(0.1), (
            f"mean leak_frac={cells['leak_frac'].mean()}, should be the "
            "clean trial's 0.1, not inflated by the two error trials")

    def test_individuation_only_uses_the_clean_hit(self, ra, tmp_path):
        self._write(tmp_path)
        ctx = ra.prepare("all", root=tmp_path)
        ind = ra.individuation(ctx["trials"])
        assert len(ind) == 1
        assert ind.iloc[0]["trial"] == 1
        assert ind.iloc[0]["individuation"] == pytest.approx(
            100.0 / 130.0)


class TestCueModalityPerFingerChartCuedOnly:
    """Finding #105: the per-finger reaction-time chart averaged raw
    time_difference_ms over every mode sharing a cue_mode/finger pair,
    including rhythm's signed beat offsets, while the table above it
    already restricts mean_rt to cued modes via reaction_times(). Must
    build the chart the same way."""

    def test_chart_bar_is_the_cued_only_mean_not_the_pooled_mean(
            self, ra, tmp_path):
        import matplotlib.pyplot as plt
        # Index finger: a classic 400 ms RT and a rhythm -300 ms signed
        # beat offset share the "both" cue setting. Pooled, that
        # averages to 50 ms; cued-only, it is the classic 400 ms alone.
        _write_cadence_ras_session(
            tmp_path, "P1", mode="classic",
            rows=[(0, "Good", 400.0, False), (1, "Good", 410.0, False)])
        _write_cadence_ras_session(
            tmp_path, "P1", mode="rhythm",
            rows=[(0, "Good", -300.0, False)])
        # A second cue setting so sec_cue_modality has something to
        # compare (it needs at least two distinct cue_mode values).
        visual_folder = _write_cadence_ras_session(
            tmp_path, "P1", mode="classic", clock="100000",
            rows=[(2, "Good", 420.0, False)])
        rows = list(csv.DictReader(open(visual_folder / "trials.csv")))
        for r in rows:
            r["cue_mode"] = "visual"
        with open(visual_folder / "trials.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
            w.writeheader()
            w.writerows(rows)

        ctx = ra.prepare("all", root=tmp_path)
        plt.close("all")
        ra.sec_cue_modality(ctx["trials"])
        per_finger_fig = plt.figure(plt.get_fignums()[-1])
        heights = [p.get_height() for p in per_finger_fig.axes[0].patches]
        plt.close("all")
        assert heights[0] == pytest.approx(400.0), (
            f"per-finger chart bar for Index/'both' is {heights[0]}, not "
            "the cued-only mean 400.0 -- rhythm's signed offset is still "
            "pooled in (audit finding #105)")


class TestCuedModesIncludesReaction:
    """Finding #106: reaction is the PVT-style press-after-randomised-
    wait task and its time_difference_ms is a genuine cue-to-press
    latency by the same reasoning as classic and adaptive, but it was
    left out of CUED_MODES, so a selection with reaction blocks logged
    real RTs in its own chapter while sec_bilateral reported nothing."""

    def test_reaction_mode_bilateral_rt_is_reported(self, ra, tmp_path):
        _write_reaction_session(tmp_path, "P1",
                                right_rt_ms=[300.0, 320.0],
                                left_rt_ms=[310.0, 330.0])
        ctx = ra.prepare("all", root=tmp_path)
        out = ra.sec_bilateral(ctx["trials"])
        assert out is not None
        assert out["rt_left"] == pytest.approx(320.0)
        assert out["rt_right"] == pytest.approx(310.0)

    def test_caveat_names_the_actual_excluded_mode_not_rhythm(
            self, ra, tmp_path, capsys):
        # A bilateral buzz_hunt selection -- not in CUED_MODES, and
        # not rhythm -- used to print "are rhythm offsets or misses"
        # regardless of which mode was actually excluded (audit
        # finding #106's mislabelling).
        folder = Path(tmp_path) / "2026-08-05" / "P1_090000_buzz_hunt"
        folder.mkdir(parents=True, exist_ok=True)
        cols = REACTION_COLS
        rows = [
            {**{c: "" for c in cols}, "iso_ts": "2026-08-05T09:00:00",
             "block_t_s": 1.0, "participant": "P1", "age": 30,
             "hand": "right", "block": "buzz_hunt", "trial": 1, "lane": 1,
             "early_late": "Great", "points": 3, "feedback": "Great",
             "had_incorrect_press": "FALSE", "stim_delivered": "TRUE",
             "stimulus": "loc;hand=right"},
            {**{c: "" for c in cols}, "iso_ts": "2026-08-05T09:00:00",
             "block_t_s": 2.0, "participant": "P1", "age": 30,
             "hand": "left", "block": "buzz_hunt", "trial": 2, "lane": 5,
             "early_late": "Great", "points": 3, "feedback": "Great",
             "had_incorrect_press": "FALSE", "stim_delivered": "TRUE",
             "stimulus": "loc;hand=left"},
        ]
        with open(folder / "trials.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        meta = {
            "participant": "P1", "hand": "both",
            "started_at": "2026-08-05T09:00:00",
            "source_name": "MultiSerial(both)",
            "block_summary": {"block": "buzz_hunt", "status": "completed",
                              "trials": 2, "hit_rate": 1.0,
                              "avg_rt_ms": None, "duration_s": 60.0,
                              "paused_total_s": 0.0,
                              "force_unit": "sensor counts"},
            "calibration": {},
        }
        (folder / "metadata.json").write_text(json.dumps(meta))
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_bilateral(ctx["trials"])
        out = capsys.readouterr().out
        assert "buzz_hunt" in out
        assert "rhythm" not in out, (
            "the caveat still hard-codes \"rhythm\" instead of naming "
            "the mode that was actually excluded (audit finding #106)")


class TestSamplingNoteChecksAllEightChannels:
    """Finding #108: sec_sampling_note checked fsr1-4 only, so on a
    bilateral block a frame where only the LEFT hand changed still
    counted as a duplicate, and its effective-rate figure could
    disagree with sample_rate_rows (which already used all eight) for
    the identical raw log."""

    def test_left_hand_only_changes_are_not_duplicates(self, ra, tmp_path):
        folder = _write_mirror_session(tmp_path, "P1", [
            (0, 150.0, 160.0, False)])
        raw_cols = ["iso_ts", "t_perf", "sample_idx", "fsr1", "fsr2",
                   "fsr3", "fsr4", "fsr5", "fsr6", "fsr7", "fsr8",
                   "hand", "event", "lane", "detail"]
        rows = []
        for i in range(60):
            # Right hand (fsr1-4) is frozen; left hand (fsr5-8) ramps.
            # A right-only check reads every one of these as a
            # duplicate frame; the real answer is 0 percent.
            rows.append({**{c: "" for c in raw_cols},
                        "iso_ts": "2026-08-05T09:00:00",
                        "t_perf": i * 0.005, "hand": "both",
                        "fsr1": 10, "fsr2": 10, "fsr3": 10, "fsr4": 10,
                        "fsr5": 10 + i, "fsr6": 10, "fsr7": 10,
                        "fsr8": 10})
        with open(folder / "raw.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=raw_cols)
            w.writeheader()
            w.writerows(rows)
        ctx = ra.prepare("all", root=tmp_path)
        note = ra.sec_sampling_note(ctx["folders"])
        assert note is not None
        # Every frame differs on fsr5 (the left hand's own ramp), so
        # only the diff-boundary's first row can read as "identical to
        # the one before" -- checking fsr1-4 only would have read all
        # 60 as duplicates instead, since the right hand never moves.
        assert note["duplicate_fraction"] < 0.05, (
            f"duplicate_fraction={note['duplicate_fraction']}, should be "
            "near 0 -- the left hand's own ramp was visible on "
            "fsr1-4-only and got missed (audit finding #108)")
