"""Analysis helpers for the hand rehabilitation device.

The notebook is a thin wrapper over this. Keeping the work in a module
means the notebook stays readable and these functions can be run from a
plain script or tested without opening Jupyter.

Typical use:

    from rehab_analysis import catalogue, report

    catalogue()          # print everything on disk with an id per game
    report(3)            # full analysis of game 3
    report("latest")     # the most recent game
    report("Basil")      # every game that person played

`report` accepts the same things `pick` does everywhere else: an id, a
list of ids, a participant, a date, a mode, a session label, "latest",
or "all".

For a notebook that runs one section per cell, start with

    ctx = prepare("latest")

and pass `ctx["trials"]`, `ctx["calset"]` and the rest into the sec_
functions by hand. Every section takes explicit arguments and holds no
state between calls, so cells can be run in any order.

A note on force. Each sensor pad reads a different number of counts for
the same real force, so raw counts cannot be compared between fingers.
Every force number here therefore comes in three forms: raw counts as
recorded, newtons for the absolute comparison against Demouche's healthy
data, and force as a fraction of that finger's own calibration press,
which is the only one comparable across fingers. Sessions recorded
before the in-app calibration existed get the first two and are said to
be uncorrected rather than quietly pooled with the rest.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


# ---------------------------------------------------------------- config

SESSIONS_DIR = Path("../sessions")
FIGDIR = Path("figures")

FINGERS = ["Index", "Middle", "Ring", "Pinky"]
FINGER_COLOUR = {"Index": "#ea580c", "Middle": "#0ea5e9",
                 "Ring": "#0f172a", "Pinky": "#ca8a04"}
HAND_COLOUR = {"right": "#2563eb", "left": "#a855f7"}
MODE_COLOUR = {"classic": "#2563eb", "adaptive": "#16a34a",
               "rhythm": "#a855f7", "mirror": "#ea580c", "unknown": "#94a3b8"}

# From the progress report: the adaptive controller aims to hold a
# per-finger hit rate in this band (Guadagnoli and Lee). Wilson and
# colleagues put the optimum nearer 85 percent, so both get drawn.
BAND_LO, BAND_HI, WILSON = 0.65, 0.80, 0.85

NUMERIC = ["block_t_s", "trial", "lane", "time_difference_ms", "points",
           "num_presses", "first_incorrect_ms", "first_incorrect_lane",
           "bpm_at_trial", "streak_at_trial", "song_time_s", "peak_force_n",
           "impulse_n", "timeout_ms", "force_window_sum"]
BOOLISH = ["had_incorrect_press", "in_recovery", "loud_trial", "stim_delivered"]


def use_style():
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 160,
        "axes.grid": True, "grid.color": "#e2e8f0", "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "figure.autolayout": True,
    })


def _save(fig, name):
    FIGDIR.mkdir(exist_ok=True)
    fig.savefig(FIGDIR / f"{name}.png", bbox_inches="tight")


def _nbins(series, want=28):
    """matplotlib throws if every value is identical, which happens with
    small or very consistent samples."""
    s = pd.Series(series).dropna()
    if len(s) < 2 or float(s.max()) == float(s.min()):
        return 1
    return min(want, max(5, int(len(s) ** 0.5) * 2))


def _show(obj):
    """display() in a notebook, print() anywhere else."""
    try:
        from IPython.display import display as _d
        _d(obj)
    except Exception:
        print(obj)


# ---------------------------------------------------------------- loading

def read_meta(folder: Path) -> dict:
    p = Path(folder) / "metadata.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def build_catalogue(root: Path | str = None) -> pd.DataFrame:
    """One row per game folder. A game is one block of one mode; a
    session is one person on one day."""
    root = Path(root or SESSIONS_DIR)
    if not root.exists():
        raise FileNotFoundError(
            f"{root.resolve()} does not exist. Set SESSIONS_DIR.")
    rows = []
    for trials_csv in sorted(root.rglob("trials.csv")):
        folder = trials_csv.parent
        meta = read_meta(folder)
        bs = meta.get("block_summary", {}) or {}
        day = (folder.parent.name
               if re.fullmatch(r"\d{4}-\d{2}-\d{2}", folder.parent.name)
               else meta.get("started_at", "")[:10])
        m = re.match(r"^(.*)_(\d{6})(?:_(.*))?$", folder.name)
        clock = m.group(2) if m else ""
        clock = f"{clock[:2]}:{clock[2:4]}" if len(clock) == 6 else ""
        try:
            n = sum(1 for _ in open(trials_csv)) - 1
        except OSError:
            n = 0
        rows.append({
            "day": day, "time": clock,
            "who": meta.get("participant",
                            m.group(1) if m else folder.name),
            "mode": bs.get("block",
                           m.group(3) if m and m.group(3) else "unknown"),
            "hand": meta.get("hand", "?"),
            "trials": int(bs.get("trials", n) or n),
            "hit_rate": bs.get("hit_rate"), "mean_rt": bs.get("avg_rt_ms"),
            "status": bs.get("status", "?"), "folder": str(folder),
        })
    cat = pd.DataFrame(rows)
    if cat.empty:
        return cat
    cat = cat.sort_values(["day", "time", "who"]).reset_index(drop=True)
    cat["session"] = cat["day"] + "  " + cat["who"]
    return cat


def catalogue(root=None) -> pd.DataFrame:
    """Print everything on disk with an id per game, and return it."""
    cat = build_catalogue(root)
    if cat.empty:
        print("Nothing recorded yet. Play a block and come back.")
        return cat
    print(f"{len(cat)} game(s) across {cat['session'].nunique()} session(s)\n")
    show = cat[["day", "time", "who", "mode", "hand",
                "trials", "hit_rate", "status"]].copy()
    show.index.name = "id"
    _show(show)
    print("\nSESSIONS  (one person, one day)")
    for s, g in cat.groupby("session"):
        modes = ", ".join(f"{m} x{c}" if c > 1 else m
                          for m, c in g["mode"].value_counts().items())
        print(f'   "{s}"   {len(g)} game(s), {g["trials"].sum()} trials   {modes}')
    print("\nreport(id) for one game, report(\"session label\") for a whole "
          "session,\nreport(\"latest\"), report(\"all\"), or report(\"name\").")
    return cat


def resolve(pick, cat: pd.DataFrame) -> pd.DataFrame:
    """Turn a pick into catalogue rows. Accepts an id, a list of ids, a
    name, a date, a mode, a session label, 'latest' or 'all'."""
    if cat.empty:
        return cat
    if isinstance(pick, str) and pick.lower() == "all":
        return cat
    if isinstance(pick, str) and pick.lower() == "latest":
        return cat.tail(1)
    items = pick if isinstance(pick, (list, tuple, set)) else [pick]
    ids = [i for i in items if isinstance(i, (int, np.integer))
           and not isinstance(i, bool)]
    if ids:
        bad = [i for i in ids if i not in cat.index]
        if bad:
            raise KeyError(f"no game with id {bad}. "
                           f"Valid ids are 0 to {cat.index.max()}.")
        return cat.loc[ids]
    sel = cat
    for term in items:
        t = str(term).strip()
        hit = (sel["session"].eq(t) | sel["day"].eq(t) | sel["who"].eq(t)
               | sel["mode"].eq(t) | sel["hand"].eq(t)
               | sel["folder"].str.contains(re.escape(t), case=False))
        if not hit.any():
            raise KeyError(
                f"nothing matches {t!r}. Try a day, a name, a mode, a "
                f"session label, or an id from catalogue().")
        sel = sel[hit]
    return sel


def load_games(folders, cat: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for folder in folders:
        folder = Path(folder)
        df = pd.read_csv(folder / "trials.csv")
        for c in NUMERIC:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        for c in BOOLISH:
            if c in df.columns:
                df[c] = df[c].map({"TRUE": True, "FALSE": False})
        meta = read_meta(folder)
        bs = meta.get("block_summary", {}) or {}
        row = cat[cat["folder"] == str(folder)]
        df["game"] = folder.name
        df["game_label"] = (f"{row['time'].iloc[0]} {row['mode'].iloc[0]}"
                            if len(row) else folder.name)
        df["session"] = row["session"].iloc[0] if len(row) else folder.name
        df["mode"] = bs.get("block", "unknown")
        df["hand_mode"] = meta.get("hand", "right")
        df["participant"] = meta.get("participant", "NA")
        df["folder"] = str(folder)
        lane0 = df["lane"] - 1
        df["finger"] = [FINGERS[int(l) % 4] if pd.notna(l) else None
                        for l in lane0]
        df["side"] = ["left" if (pd.notna(l) and l >= 4) else "right"
                      for l in lane0]
        if df["hand_mode"].iloc[0] == "left":
            df["side"] = "left"
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def load_raw(folder: Path):
    p = Path(folder) / "raw.csv"
    if not p.exists() or p.stat().st_size < 200:
        return None
    df = pd.read_csv(p)
    for c in ["t_perf"] + [f"fsr{i}" for i in range(1, 9)]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def force_unit(metas) -> str:
    for m in _meta_list(metas):
        u = (m.get("block_summary", {}) or {}).get("force_unit")
        if u:
            return u
    return "sensor counts"


def load_metas(folders) -> dict:
    """Read every metadata.json for a selection, keyed by game folder
    name. Same shape report() builds internally, so a notebook cell can
    get one without running the whole report."""
    return {Path(f).name: read_meta(Path(f)) for f in folders}


# ------------------------------------------------------------- calibration
# Each pad reads a different number of counts for the same real force,
# because of where it sits under the finger. On this device one light
# press gives about 49 counts on the index and 115 on the pinky. Raw
# counts are therefore not comparable between fingers, and every
# cross-finger force number built from them is reporting the hardware as
# much as the patient.
#
# The in-app calibration records what a press was worth on each pad on
# the day. Dividing by that finger's own gap removes the pad and leaves
# the person.

# Per-finger lists a calibration carries, all index order
# index/middle/ring/pinky, matching FINGERS.
CAL_LISTS = ("empty", "resting", "press", "press_all",
             "preload", "gap", "on_delta", "off_delta")

# Name for the calibrated measure. Used for column names and axis labels
# so a reader never has to guess whether a force number is comparable.
NORM_UNIT = "x calibration press"
NORM_LABEL = "force (x calibration press)"

# Counts between resting and pressing below which the calibration press
# was too weak to divide by: sensor noise would come out as a large
# normalised force. Same floor the app refuses to save a profile under.
MIN_USABLE_GAP = 20.0

# Columns add_force_columns writes.
FORCE_COLS = ("peak_force_cal", "impulse_cal", "force_window_sum_cal",
              "peak_force_N", "impulse_Ns", "force_calibrated")


def _meta_list(metas):
    """metas turns up as a dict keyed by game name, a list, or None."""
    return [m for _, m in _meta_items(metas)]


def _meta_items(metas):
    """(game name, metadata) pairs. An unreadable metadata.json comes
    through as an empty dict so the game is still counted and still
    reported as having no calibration, rather than vanishing."""
    if metas is None:
        return []
    pairs = (metas.items() if hasattr(metas, "items")
             else enumerate(metas))
    return [(str(k), v if isinstance(v, dict) else {}) for k, v in pairs]


def _finger_index(finger):
    """Accepts 'Index', 0, or a 0-based lane number. None when it makes
    no sense, which happens on keyboard rows with no lane."""
    if isinstance(finger, str):
        for i, f in enumerate(FINGERS):
            if f.lower() == finger.strip().lower():
                return i
        return None
    if finger is None or (isinstance(finger, float) and np.isnan(finger)):
        return None
    try:
        return int(finger) % len(FINGERS)
    except (TypeError, ValueError):
        return None


def read_calibration(meta) -> dict:
    """The calibration a session recorded. Empty dict for anything
    recorded before the in-app calibration existed, which is a normal
    state and not an error."""
    cal = (meta or {}).get("calibration") or {}
    return cal if isinstance(cal, dict) else {}


def calibration_problems(cal) -> list:
    """Everything wrong with one calibration, empty when it is sound.

    A truncated list is the case worth catching: a calibration holding
    two of four fingers is not a calibration, and silently reading the
    missing entries as zero prints a full table that was never measured.
    """
    if not cal:
        return ["no calibration recorded"]
    problems = []
    for key in ("resting", "press", "gap"):
        seq = cal.get(key)
        if not isinstance(seq, (list, tuple)):
            problems.append(f"{key}: missing")
        elif len(seq) < len(FINGERS):
            problems.append(
                f"{key}: {len(seq)} of {len(FINGERS)} fingers recorded")
    gaps = cal.get("gap")
    if isinstance(gaps, (list, tuple)):
        for i, finger in enumerate(FINGERS):
            if i >= len(gaps):
                continue
            try:
                g = float(gaps[i])
            except (TypeError, ValueError):
                problems.append(f"{finger}: gap is not a number")
                continue
            if g <= 0:
                problems.append(
                    f"{finger}: gap is {g:.0f} counts, so that pad never "
                    f"moved between resting and pressing")
            elif g < MIN_USABLE_GAP:
                problems.append(
                    f"{finger}: gap is only {g:.0f} counts, under the "
                    f"{MIN_USABLE_GAP:.0f} a usable press needs")
    return problems


def calibration_gaps(cal) -> list:
    """Per-finger resting-to-press gap in counts, None where the entry is
    missing, unreadable or too small to divide by."""
    out = [None] * len(FINGERS)
    seq = (cal or {}).get("gap")
    if not isinstance(seq, (list, tuple)):
        return out
    for i in range(len(FINGERS)):
        if i >= len(seq):
            continue
        try:
            g = float(seq[i])
        except (TypeError, ValueError):
            continue
        if g >= MIN_USABLE_GAP:
            out[i] = g
    return out


@dataclass
class CalibrationSet:
    """Every calibration behind one selection, kept apart rather than
    collapsed.

    A selection can span games recorded under different calibrations, or
    under none at all, so there is no single set of numbers to hand back.
    Callers ask per game and get None when that game has nothing usable
    for that finger.
    """

    per_game: dict = field(default_factory=dict)     # game -> calibration
    gaps: dict = field(default_factory=dict)         # game -> [gap|None] x4
    problems: dict = field(default_factory=dict)     # game -> [str]
    units: dict = field(default_factory=dict)        # game -> logged unit
    # Per game, how many raw sensor counts one logged unit is, and how
    # many newtons. Both are 1.0 and N_PER_COUNT for the ordinary case
    # where force was logged in counts.
    counts_per_unit: dict = field(default_factory=dict)
    newtons_per_unit: dict = field(default_factory=dict)
    unit: str = "sensor counts"
    n_per_unit: float = 1.0                          # newtons per unit

    @property
    def mixed_units(self) -> bool:
        """True when the selection pools games logged in different force
        units, which no single axis label can describe honestly."""
        return len(set(self.units.values())) > 1

    def counts(self, game, value):
        """A logged force value back in raw sensor counts, which is the
        unit the calibration gaps are in."""
        try:
            return float(value) * self.counts_per_unit.get(str(game), 1.0)
        except (TypeError, ValueError):
            return float("nan")

    @property
    def calibrated_games(self) -> list:
        return sorted(k for k, v in self.per_game.items() if v)

    @property
    def uncalibrated_games(self) -> list:
        return sorted(k for k, v in self.per_game.items() if not v)

    @property
    def stamps(self) -> dict:
        """created_at -> the games recorded under it, oldest key first."""
        out = {}
        for name in sorted(self.per_game):
            cal = self.per_game[name]
            if cal:
                out.setdefault(cal.get("created_at") or "unknown",
                               []).append(name)
        return dict(sorted(out.items()))

    @property
    def status(self) -> str:
        """none, single, partial (some games missing one) or multiple
        (the selection spans more than one calibration)."""
        n_cal = len(self.calibrated_games)
        if n_cal == 0:
            return "none"
        if len(self.stamps) > 1:
            return "multiple"
        if n_cal < len(self.per_game):
            return "partial"
        return "single"

    @property
    def usable(self) -> bool:
        """Whether any finger of any game can be normalised at all."""
        return any(g is not None for seq in self.gaps.values() for g in seq)

    def gap(self, game, finger):
        """Counts between resting and a light press, for one finger of
        one game. None when that pad has no usable calibration."""
        seq = self.gaps.get(str(game))
        if not seq:
            return None
        i = _finger_index(finger)
        if i is None or i >= len(seq):
            return None
        return seq[i]

    def factor(self, game, finger):
        """Multiply raw counts above baseline by this to get force as a
        fraction of that finger's own calibration press."""
        g = self.gap(game, finger)
        return None if not g else 1.0 / g

    def newtons(self, value, game=None):
        """A logged force value in newtons, whichever unit it was logged
        in. Absolute, so it can be checked against Demouche."""
        try:
            per = self.newtons_per_unit.get(str(game), self.n_per_unit)
            return float(value) * per
        except (TypeError, ValueError):
            return float("nan")


def _is_newtons(unit) -> bool:
    return str(unit).strip().upper() in ("N", "NEWTON", "NEWTONS")


def calibration_factors(metas, unit=None) -> CalibrationSet:
    """Per-finger normalisation factors for a selection.

    Handles the three cases that actually turn up: nothing calibrated,
    some games calibrated and some not, and several games under different
    calibrations. Nothing is collapsed to a single set of numbers,
    because collapsing is exactly what lets the oldest calibration stand
    in for the whole report.
    """
    items = _meta_items(metas)
    unit = unit or force_unit(metas)
    cs = CalibrationSet(unit=unit,
                        n_per_unit=1.0 if _is_newtons(unit) else N_PER_COUNT)
    for name, meta in items:
        cal = read_calibration(meta)
        cs.per_game[name] = cal
        cs.gaps[name] = calibration_gaps(cal)
        cs.problems[name] = calibration_problems(cal)

        game_unit = ((meta.get("block_summary", {}) or {}).get("force_unit")
                     or unit)
        cs.units[name] = game_unit
        # The app only logs newtons when a counts-to-newtons constant is
        # configured, and it snapshots that config with the session, so
        # the constant is there to undo when it is needed.
        snap = ((meta.get("config_snapshot") or {}).get("fsr") or {})
        try:
            const = float(snap.get("force_calibration_n_per_count") or 0)
        except (TypeError, ValueError):
            const = 0.0
        const = const or None
        if _is_newtons(game_unit):
            per_n = const or N_PER_COUNT
            cs.counts_per_unit[name] = 1.0 / per_n
            cs.newtons_per_unit[name] = 1.0
        else:
            cs.counts_per_unit[name] = 1.0
            cs.newtons_per_unit[name] = const or N_PER_COUNT
    return cs


def parse_peaks_normalised(cell, game=None, calset=None) -> dict:
    """parse_peaks with every lane divided by that lane's own calibration
    press. Lanes with no usable gap are left out, so a caller can spot a
    partial result by comparing the length against parse_peaks."""
    raw = parse_peaks(cell)
    if calset is None or not raw:
        return {}
    out = {}
    for lane0, val in raw.items():
        g = calset.gap(game, lane0 % len(FINGERS))
        if g:
            out[lane0] = calset.counts(game, val) / g
    return out


def add_force_columns(trials, calset=None) -> pd.DataFrame:
    """Copy of `trials` carrying the calibrated and the newton force
    columns next to the raw counts.

    peak_force_cal, impulse_cal and force_window_sum_cal are counts above
    baseline divided by that finger's own calibration press, so 1.0 means
    as strong as the press that finger gave at calibration. Those are the
    only force numbers comparable between fingers.

    peak_force_N and impulse_Ns stay absolute, because Demouche's healthy
    fingertip forces are in newtons and a ratio cannot be checked against
    them.

    Safe to call twice. With no calibration the calibrated columns come
    back all NaN and force_calibrated is False everywhere, which is what
    the sections check before claiming a correction was applied.
    """
    df = trials.copy()
    if df.empty:
        for c in FORCE_COLS:
            if c not in df.columns:
                df[c] = pd.Series(dtype="bool" if c == "force_calibrated"
                                  else "float64")
        return df

    peak_cal, imp_cal, win_cal, flag = [], [], [], []
    peak_n, imp_n = [], []
    for _, r in df.iterrows():
        game = r.get("game")
        g = calset.gap(game, r.get("finger")) if calset is not None else None
        pk, im = r.get("peak_force_n"), r.get("impulse_n")
        if calset is None:
            peak_n.append(float(pk) * N_PER_COUNT if pd.notna(pk) else np.nan)
            imp_n.append(float(im) * N_PER_COUNT if pd.notna(im) else np.nan)
        else:
            peak_n.append(calset.newtons(pk, game) if pd.notna(pk) else np.nan)
            imp_n.append(calset.newtons(im, game) if pd.notna(im) else np.nan)
        peak_cal.append(calset.counts(game, pk) / g
                        if g and pd.notna(pk) else np.nan)
        imp_cal.append(calset.counts(game, im) / g
                       if g and pd.notna(im) else np.nan)
        cell = r.get("force_window_peaks")
        norm = parse_peaks_normalised(cell, game, calset)
        # Only sum when every lane that registered has a gap to divide
        # by. A partial sum mixes normalised lanes with dropped ones and
        # is not comparable with anything.
        raw_n = len(parse_peaks(cell))
        win_cal.append(sum(norm.values())
                       if raw_n and len(norm) == raw_n else np.nan)
        flag.append(bool(g))

    df["peak_force_cal"] = peak_cal
    df["impulse_cal"] = imp_cal
    df["force_window_sum_cal"] = win_cal
    df["force_calibrated"] = flag
    df["peak_force_N"] = peak_n
    df["impulse_Ns"] = imp_n
    return df


def ensure_force_columns(trials, calset=None) -> pd.DataFrame:
    """Add the force columns unless they are already there. Lets every
    section be called on its own with just trials and a calset, without
    recomputing when report() has already done it."""
    if all(c in trials.columns for c in FORCE_COLS):
        return trials
    return add_force_columns(trials, calset)


def multi_finger_deficit(cal) -> dict:
    """Recompute the calibration's multi-finger deficit and say what can
    and cannot be read off it.

    Three problems with the saved number, all of which have to be
    surfaced rather than fixed silently:

    The guard on the saved value is any(press_all), so one sensor reading
    non-zero passes it while the other three read zero. A dead sensor
    then fabricates a large deficit that looks like a clinical finding.

    It can come out negative, meaning more force appeared with all four
    pressing than with each alone. That is not a deficit, it is either
    noise or an uneven effort, and printing it as a percentage lost is
    wrong.

    It is computed from submaximal presses that nobody asked the
    participant to match for effort, whereas the multi-finger deficit in
    the literature is defined on maximal voluntary force. So it is not
    the published measure and must not be compared against published
    values.

    Returns a dict: value (clamped, None when not measurable), signed
    (the raw figure including negatives), dead (finger names with no
    reading), notes (plain-language caveats), measurable (bool).
    """
    out = {"value": None, "signed": None, "dead": [], "notes": [],
           "measurable": False}
    if not cal:
        out["notes"].append("no calibration recorded")
        return out
    gaps = [None] * len(FINGERS)
    raw_gaps = cal.get("gap") or []
    for i in range(len(FINGERS)):
        if i < len(raw_gaps):
            try:
                gaps[i] = float(raw_gaps[i])
            except (TypeError, ValueError):
                gaps[i] = None
    press_all = cal.get("press_all") or []
    resting = cal.get("resting") or []
    if len(press_all) < len(FINGERS) or len(resting) < len(FINGERS):
        out["notes"].append(
            "the all-fingers step was skipped or only partly recorded, so "
            "there is no multi-finger measurement here")
        return out

    together = []
    for i in range(len(FINGERS)):
        try:
            together.append(max(0.0, float(press_all[i]) - float(resting[i])))
        except (TypeError, ValueError):
            together.append(0.0)
    if not any(together):
        # Nothing at all read during the all-fingers step, which means it
        # was skipped rather than that all four sensors died.
        out["notes"].append(
            "the all-fingers step was skipped, so there is no multi-finger "
            "measurement here")
        return out

    # A pad that read nothing while all four pressed, but that did move
    # for its own single press, is a dead sensor rather than a finger
    # producing no force. Either way its zero cannot be counted as lost
    # force, so the deficit is not measurable.
    for i, finger in enumerate(FINGERS):
        if together[i] <= 0 and (gaps[i] or 0) > 0:
            out["dead"].append(finger)
    empty = cal.get("empty") or []
    for i, finger in enumerate(FINGERS):
        if i < len(empty):
            try:
                if float(empty[i]) <= 1 and finger not in out["dead"]:
                    out["dead"].append(finger)
                    out["notes"].append(
                        f"{finger}: reads zero with nothing touching it, "
                        f"which is an I2C fault, not a weak finger")
            except (TypeError, ValueError):
                pass

    singles = sum(g for g in gaps if g)
    if singles <= 0:
        out["notes"].append("no usable single-finger presses to compare "
                            "against")
        return out
    signed = (singles - sum(together)) / singles
    out["signed"] = round(signed, 4)

    if out["dead"]:
        out["notes"].append(
            "sensors reading nothing during the all-fingers press: "
            + ", ".join(out["dead"])
            + ". Their zeros would be counted as lost force, so this "
              "figure is not usable until that is fixed")
        return out
    if signed < 0:
        out["notes"].append(
            f"came out at {signed * 100:+.0f} percent, meaning more force "
            f"appeared with all four fingers than with each alone. That is "
            f"not a deficit, it is an uneven effort between the two steps")
        return out

    out["value"] = round(signed, 4)
    out["measurable"] = True
    out["notes"].append(
        "measured from light submaximal presses, not from maximal "
        "voluntary force, which is how the stroke literature defines the "
        "multi-finger deficit. Treat it as a device-specific number and "
        "do not compare it against published values")
    return out


def parse_peaks(cell) -> dict:
    """force_window_peaks looks like '1:50.000;4:200.000', lanes 1-indexed."""
    out = {}
    if not isinstance(cell, str) or not cell.strip():
        return out
    for part in cell.split(";"):
        if ":" in part:
            lane, val = part.split(":", 1)
            try:
                out[int(lane) - 1] = float(val)
            except ValueError:
                pass
    return out


def individuation(trials: pd.DataFrame, calset=None) -> pd.DataFrame:
    """Target-finger force over total force across all fingers, per trial.
    1.0 means only the intended finger pressed; lower means the force
    spread onto its neighbours.

    The raw index is biased by the sensors, not just by the hand. A
    finger sitting on an over-reading pad inflates the denominator on
    every trial, which drags the index down for every other finger and
    reads as spill that never happened. `individuation_cal` divides each
    lane by its own calibration press first and is the version to report
    whenever the `corrected` column is True.
    """
    rows = []
    if "force_window_peaks" not in trials.columns:
        return pd.DataFrame(rows)
    for _, r in trials.iterrows():
        cell = r.get("force_window_peaks")
        peaks = parse_peaks(cell)
        if not peaks or pd.isna(r.get("lane")):
            continue
        tgt = int(r["lane"]) - 1
        on_target = peaks.get(tgt, 0.0)
        spill = sum(v for k, v in peaks.items() if k != tgt)
        total = on_target + spill
        if total <= 0:
            continue
        row = {"trial": r["trial"], "finger": r["finger"],
               "game": r.get("game"), "game_label": r["game_label"],
               "on_target": on_target, "spillover": spill,
               "individuation": on_target / total,
               "on_target_cal": np.nan, "spillover_cal": np.nan,
               "individuation_cal": np.nan, "corrected": False}
        # Every lane in the trial needs a gap, including the target lane
        # even when it registered nothing: an on-target zero is a real
        # zero and has to stay in, or the corrected mean quietly drops
        # the worst trials and looks better than the raw one for reasons
        # that have nothing to do with the calibration. Normalising some
        # lanes and leaving others raw would be worse still, because the
        # mixture is invisible in the result.
        norm = parse_peaks_normalised(cell, r.get("game"), calset)
        tgt_gap = (calset.gap(r.get("game"), tgt % len(FINGERS))
                   if calset is not None else None)
        if tgt_gap and len(norm) == len(peaks):
            on_c = norm.get(tgt, 0.0)
            spill_c = sum(v for k, v in norm.items() if k != tgt)
            total_c = on_c + spill_c
            if total_c > 0:
                row.update({"on_target_cal": on_c, "spillover_cal": spill_c,
                            "individuation_cal": on_c / total_c,
                            "corrected": True})
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- sections

def _order(df, col="finger"):
    return [f for f in FINGERS if f in df[col].unique()]


def sec_overview(trials, folders, metas):
    print("=" * 62)
    print("OVERVIEW")
    print("=" * 62)
    rows = []
    for f in folders:
        m = metas.get(Path(f).name, {})
        bs = m.get("block_summary", {}) or {}
        sub = trials[trials["folder"] == str(f)]
        rows.append({
            "game": sub["game_label"].iloc[0] if len(sub) else Path(f).name,
            "mode": bs.get("block", "?"), "hand": m.get("hand", "?"),
            "trials": bs.get("trials", len(sub)), "hit_rate": bs.get("hit_rate"),
            "mean_rt_ms": bs.get("avg_rt_ms"), "score": bs.get("final_score"),
            "duration_s": bs.get("duration_s"),
            "paused_s": bs.get("paused_total_s", 0),
            "input": m.get("source_name", "?")})
    ov = pd.DataFrame(rows)
    _show(ov)
    on_task = (ov["duration_s"].fillna(0).sum() - ov["paused_s"].fillna(0).sum())
    print(f"\ngames        : {len(ov)}")
    print(f"total trials : {ov['trials'].sum():.0f}")
    print(f"time on task : {on_task/60:.1f} min (pauses removed)")
    if on_task > 0:
        print(f"presses/min  : {ov['trials'].sum()/(on_task/60):.1f}")
    return on_task


def sec_quality(trials, folders, metas):
    print("\n" + "=" * 62)
    print("DATA QUALITY")
    print("=" * 62)
    if "stim_delivered" in trials.columns:
        sd = trials["stim_delivered"].dropna()
        if len(sd):
            failed = int((~sd).sum())
            print(f"cue commands not delivered : {failed} of {len(sd)}")
            if failed:
                print("   ^ no cue on those trials. Not ordinary misses.")
    n_force = trials["peak_force_n"].notna().sum()
    print(f"trials with force data     : {n_force} of {len(trials)}")
    if n_force == 0:
        print("   ^ keyboard mode, so force and individuation are empty.")
    for f in folders:
        bs = metas.get(Path(f).name, {}).get("block_summary", {}) or {}
        if bs.get("pauses"):
            print(f"{Path(f).name}: paused {bs['pauses']}x "
                  f"for {bs.get('paused_total_s', 0):.0f}s")
        drift = bs.get("drift_units_per_min") or {}
        vals = [(abs(v), k) for k, v in drift.items() if v is not None]
        if vals:
            worst = max(vals)
            flag = "   <- large, check the sensor" if worst[0] > 10 else ""
            print(f"{Path(f).name}: worst drift {worst[1]} "
                  f"{worst[0]:.2f}/min{flag}")


def sec_compare(trials):
    games = trials["game_label"].nunique()
    if games < 2:
        return None
    print("\n" + "=" * 62)
    print("COMPARING GAMES")
    print("=" * 62)
    rows = []
    for g, sub in trials.groupby("game_label", sort=False):
        v = sub.loc[sub["early_late"] != "Miss", "time_difference_ms"].dropna()
        rows.append({"game": g, "mode": sub["mode"].iloc[0], "trials": len(sub),
                     "hit_rate": round((sub["early_late"] != "Miss").mean(), 3),
                     "mean_rt": round(v.mean(), 1) if len(v) else np.nan,
                     "rt_cv": (round(v.std() / v.mean(), 3)
                               if len(v) and v.mean() else np.nan)})
    comp = pd.DataFrame(rows)
    _show(comp)
    cols = [MODE_COLOUR.get(m, "#94a3b8") for m in comp["mode"]]
    x = np.arange(len(comp))
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    ax[0].bar(x, comp["hit_rate"], color=cols, width=.6)
    ax[0].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
    ax[0].set_ylim(0, 1.02); ax[0].set_ylabel("hit rate")
    ax[0].set_title("Accuracy per game")
    ax[1].bar(x, comp["mean_rt"], color=cols, width=.6)
    ax[1].set_ylabel("mean reaction time (ms)"); ax[1].set_title("Speed per game")
    ax[2].bar(x, comp["rt_cv"], color=cols, width=.6)
    ax[2].set_ylabel("reaction time CV")
    ax[2].set_title("Consistency (lower is steadier)")
    for a in ax:
        a.set_xticks(x)
        a.set_xticklabels(comp["game"], rotation=35, ha="right", fontsize=8)
    _save(fig, "game_comparison"); plt.show()
    return comp


def sec_reaction_time(trials):
    cued = trials[trials["mode"].isin(["classic", "adaptive", "mirror"])]
    rt = cued[cued["time_difference_ms"].notna()
              & (cued["early_late"] != "Miss")]
    if rt.empty:
        print("\nNo cued-mode reaction times here.")
        return rt
    print("\n" + "=" * 62)
    print("REACTION TIME")
    print("=" * 62)
    v = rt["time_difference_ms"]
    print(f"n {len(v)}   mean {v.mean():.1f} ms   median {v.median():.1f} ms   "
          f"sd {v.std():.1f}   CV {v.std()/v.mean():.3f}")
    print(f"fastest {v.min():.0f} ms   10th/90th "
          f"{v.quantile(.1):.0f}/{v.quantile(.9):.0f} ms")

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    ax[0].hist(v, bins=_nbins(v), color="#2563eb", alpha=.85)
    ax[0].axvline(v.mean(), color="#dc2626", lw=2, label=f"mean {v.mean():.0f}")
    ax[0].axvline(v.median(), color="#16a34a", lw=2, ls="--",
                  label=f"median {v.median():.0f}")
    ax[0].set_xlabel("reaction time (ms)"); ax[0].set_ylabel("trials")
    ax[0].set_title("Distribution"); ax[0].legend(frameon=False)
    order = _order(rt)
    bp = ax[1].boxplot([rt[rt["finger"] == f]["time_difference_ms"]
                        for f in order], labels=order,
                       patch_artist=True, widths=.6)
    for p, f in zip(bp["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax[1].set_ylabel("reaction time (ms)"); ax[1].set_title("By finger")
    _save(fig, "reaction_time"); plt.show()

    per = (rt.groupby("finger")["time_difference_ms"]
             .agg(n="count", mean="mean", median="median", sd="std")
             .reindex(order).round(1))
    per["CV"] = (per["sd"] / per["mean"]).round(3)
    _show(per)

    if len(rt) > 8:
        fig, ax = plt.subplots(figsize=(9, 3.4))
        for g, sub in rt.groupby("game_label", sort=False):
            sub = sub.sort_values("trial")
            c = MODE_COLOUR.get(sub["mode"].iloc[0], "#2563eb")
            ax.plot(sub["trial"], sub["time_difference_ms"], "o", ms=3.5,
                    alpha=.3, color=c)
            ax.plot(sub["trial"],
                    sub["time_difference_ms"].rolling(5, min_periods=1).mean(),
                    lw=2, color=c)
        x = rt["trial"].astype(float).values
        y = rt["time_difference_ms"].astype(float).values
        slope, inter = np.polyfit(x, y, 1)
        xs = np.linspace(x.min(), x.max(), 40)
        ax.plot(xs, slope * xs + inter, "--", lw=2, color="#dc2626",
                label=f"trend {slope:+.2f} ms per trial")
        ax.set_xlabel("trial"); ax.set_ylabel("reaction time (ms)")
        ax.set_title("Across the block"); ax.legend(frameon=False, fontsize=8)
        _save(fig, "rt_learning"); plt.show()
        print(f"slope {slope:+.2f} ms per trial, so the participant "
              f"{'got faster' if slope < 0 else 'got slower'}.")
    return rt


def sec_accuracy(trials):
    cued = trials[trials["mode"].isin(["classic", "adaptive", "mirror"])]
    adaptive = trials[trials["mode"] == "adaptive"]
    target = adaptive if not adaptive.empty else cued
    if target.empty:
        return
    print("\n" + "=" * 62)
    print("ACCURACY AND THE CHALLENGE POINT")
    print("=" * 62)
    hit = (target["early_late"] != "Miss")
    print(f"hit rate {hit.mean():.1%}  ({hit.sum()} of {len(hit)})")
    print(f"inside the {BAND_LO:.0%} to {BAND_HI:.0%} band: "
          f"{'yes' if BAND_LO <= hit.mean() <= BAND_HI else 'no'}")

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    roll = hit.rolling(12, min_periods=3).mean()
    ax[0].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15,
                  label="target 65 to 80%")
    ax[0].axhline(WILSON, color="#ca8a04", ls=":", lw=2, label="Wilson 85%")
    ax[0].plot(range(len(roll)), roll, lw=2, color="#2563eb")
    ax[0].set_ylim(0, 1.02); ax[0].set_xlabel("trial")
    ax[0].set_ylabel("hit rate (rolling 12)")
    ax[0].set_title("Did difficulty stay in the band")
    ax[0].legend(frameon=False, fontsize=8)
    order = _order(target)
    ax[1].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
    ax[1].bar(order, [(target[target["finger"] == f]["early_late"] != "Miss").mean()
                      for f in order],
              color=[FINGER_COLOUR[f] for f in order], width=.6)
    ax[1].set_ylim(0, 1.02); ax[1].set_ylabel("hit rate")
    ax[1].set_title("Per finger")
    _save(fig, "challenge_point"); plt.show()
    print(f"share of the block inside the band: "
          f"{roll.dropna().between(BAND_LO, BAND_HI).mean():.1%}")

    if not adaptive.empty and adaptive["bpm_at_trial"].notna().any():
        fig, ax = plt.subplots(figsize=(9, 3.2))
        for g, sub in adaptive.groupby("game_label", sort=False):
            sub = sub.sort_values("trial")
            ax.plot(sub["trial"], sub["bpm_at_trial"], lw=2)
            rec = sub[sub.get("in_recovery") == True]
            if not rec.empty:
                ax.scatter(rec["trial"], rec["bpm_at_trial"], s=40,
                           color="#dc2626", zorder=5, label="recovery mode")
        ax.set_xlabel("trial"); ax.set_ylabel("BPM")
        ax.set_title("Difficulty the controller chose")
        h, l = ax.get_legend_handles_labels()
        if l:
            ax.legend(dict(zip(l, h)).values(), dict(zip(l, h)).keys(),
                      frameon=False, fontsize=8)
        _save(fig, "adaptive_bpm"); plt.show()

    # A miss and a wrong-finger press are different failures.
    if not cued.empty:
        order = _order(cued)
        miss = [(cued[cued["finger"] == f]["early_late"] == "Miss").sum()
                for f in order]
        wrong = [(cued[cued["finger"] == f]["had_incorrect_press"] == True).sum()
                 for f in order]
        fig, ax = plt.subplots(figsize=(8, 3.2))
        x = np.arange(len(order)); w = .38
        ax.bar(x - w/2, miss, w, label="missed, no press in time", color="#dc2626")
        ax.bar(x + w/2, wrong, w, label="wrong finger pressed", color="#ea580c")
        ax.set_xticks(x); ax.set_xticklabels(order); ax.set_ylabel("trials")
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set_title("Two kinds of error"); ax.legend(frameon=False)
        _save(fig, "errors"); plt.show()


def _boxes(ax, data, order, ylabel, title):
    bp = ax.boxplot(data, labels=order, patch_artist=True, widths=.6)
    for p, f in zip(bp["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax.set_ylabel(ylabel); ax.set_title(title)
    return bp


def sec_force(trials, unit="sensor counts", calset=None):
    """Peak force and impulse per finger, in three units.

    Raw counts are kept because they are what the device recorded, but
    they are NOT comparable between fingers: on this device the same
    light press reads about 49 counts on the index pad and 115 on the
    pinky. The calibrated column removes that. The newton column is
    absolute and exists so the numbers can be put next to Demouche's
    healthy fingertip forces, which are published in newtons.
    """
    trials = ensure_force_columns(trials, calset)
    force = trials[trials["peak_force_n"].notna()]
    if force.empty:
        print("\nNo force data (keyboard mode or sensors not connected).")
        return force
    corrected = bool(force["force_calibrated"].any())
    print("\n" + "=" * 62)
    print(f"FORCE   (logged unit: {unit})")
    print("=" * 62)
    if calset is not None and calset.mixed_units:
        print("WARNING: these games did not all log force in the same unit.")
        print("Read the per-game tables rather than the pooled figures.\n")
    if corrected:
        n_missing = int((~force["force_calibrated"]).sum())
        print(f"Comparable measure: {NORM_LABEL}. 1.0 is as strong as the")
        print("press that finger gave at calibration. Raw counts below are")
        print("kept for the record and are NOT comparable between fingers,")
        print("because each pad reads a different number of counts for the")
        print("same real force.")
        if n_missing:
            print(f"{n_missing} of {len(force)} force trials had no usable")
            print("calibration for their finger and are blank in the")
            print("calibrated columns.")
    else:
        print("NOT CORRECTED for per-sensor sensitivity: no calibration is")
        print("available for these games. Differences between fingers below")
        print("mix the patient with the pad and cannot be separated. The")
        print("newton figures rest on the SingleTact datasheet alone.")
    print()

    order = _order(force)
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    if corrected:
        _boxes(ax[0], [force[force["finger"] == f]["peak_force_cal"].dropna()
                       for f in order], order,
               NORM_LABEL, "Peak force, calibrated (comparable)")
        ax[0].axhline(1.0, color="#16a34a", ls="--", lw=1.5,
                      label="calibration press")
        ax[0].legend(frameon=False, fontsize=8)
    else:
        _boxes(ax[0], [force[force["finger"] == f]["peak_force_n"]
                       for f in order], order,
               f"peak force ({unit})", "Peak force, raw (not comparable)")
    _boxes(ax[1], [force[force["finger"] == f]["peak_force_n"]
                   for f in order], order,
           f"peak force ({unit})", "Peak force, raw counts")
    ycol = "peak_force_cal" if corrected else "peak_force_n"
    g = force.sort_values("trial")
    ax[2].plot(g["trial"], g[ycol], "o", ms=3.5, alpha=.35, color="#16a34a")
    ax[2].plot(g["trial"], g[ycol].rolling(5, min_periods=1).mean(),
               lw=2, color="#16a34a")
    ax[2].set_xlabel("trial")
    ax[2].set_ylabel(NORM_LABEL if corrected else f"peak force ({unit})")
    ax[2].set_title("Across the block (fatigue check)")
    _save(fig, "force"); plt.show()

    if force["impulse_n"].notna().any():
        icol = "impulse_cal" if corrected else "impulse_n"
        ilabel = (f"impulse ({NORM_UNIT} x s)" if corrected
                  else f"impulse ({unit} x s)")
        fig, ax = plt.subplots(figsize=(7, 3.4))
        _boxes(ax, [force[force["finger"] == f][icol].dropna()
                    for f in order], order, ilabel,
               "Effort held over the press")
        _save(fig, "impulse"); plt.show()

    cols = ["peak_force_n", "peak_force_N"]
    if corrected:
        cols.insert(0, "peak_force_cal")
    tbl = (force.groupby("finger")[cols]
                .agg(["count", "mean", "std", "max"])
                .reindex(order).round(3))
    _show(tbl)
    print("peak_force_n  raw counts above baseline, not comparable "
          "between fingers")
    if corrected:
        print(f"peak_force_cal  {NORM_LABEL}, comparable between fingers")
    print("peak_force_N  newtons, absolute, for the Demouche comparison")

    # Absolute force against the only healthy data in this lineage.
    per_finger_n = force.groupby("finger")["peak_force_N"].mean()
    idx = per_finger_n.get("Index")
    pky = per_finger_n.get("Pinky")
    if pd.notna(idx) or pd.notna(pky):
        print(f"\nhealthy means (Demouche 2025): index "
              f"{DEMOUCHE_2025['index_mean']} N, "
              f"little {DEMOUCHE_2025['little_mean']} N")
        if pd.notna(idx):
            print(f"   this selection, index : {idx:.2f} N")
        if pd.notna(pky):
            print(f"   this selection, pinky : {pky:.2f} N")
        print("   These are game presses against a trigger, not maximal")
        print("   voluntary force, so a lower number here is expected and")
        print("   is not by itself evidence of weakness.")
    return force


def sec_individuation(trials, calset=None):
    """Finger isolation, corrected for the sensors where possible.

    The index is target force over total force. Raw, it is biased by the
    pads: an over-reading pad inflates the denominator on every trial and
    drags the index down for every OTHER finger, so a hardware quirk
    reads as spill the patient never produced. Dividing each lane by its
    own calibration press first removes that.
    """
    ind = individuation(trials, calset)
    if ind.empty:
        print("\nNo individuation data (needs the force sensors).")
        return ind
    corrected = bool(ind["corrected"].any())
    col = "individuation_cal" if corrected else "individuation"
    shown = ind[ind[col].notna()]
    print("\n" + "=" * 62)
    print("FINGER INDIVIDUATION")
    print("=" * 62)
    if corrected:
        print("Showing the CALIBRATED index: each lane divided by its own")
        print("calibration press before the ratio, so differences between")
        print("the sensor pads do not show up as finger spill.")
        n_raw = int((~ind["corrected"]).sum())
        if n_raw:
            print(f"{n_raw} of {len(ind)} trials had at least one lane with")
            print("no usable calibration and are left out of the corrected")
            print("figures rather than half corrected.")
    else:
        print("Showing the RAW index. It is NOT corrected for per-sensor")
        print("sensitivity, because no calibration is available for these")
        print("games. A finger on an over-reading pad inflates the total and")
        print("pushes every other finger's index down, so treat differences")
        print("between fingers here as a mix of the hand and the hardware.")
    print(f"\n{len(shown)} trials with usable force spread")
    print(f"mean index {shown[col].mean():.3f}  "
          f"(1.0 = only the target finger pressed)")
    if corrected:
        # The same trials both ways, otherwise the two means differ
        # partly because they cover different trials.
        print(f"uncorrected, over the same trials: "
              f"{shown['individuation'].mean():.3f}")
    spill = 1 - shown[col].mean()
    print(f"enslavement (force on the other fingers): {spill:.3f}   "
          f"unimpaired {ENSLAVEMENT_REF['unimpaired']}, "
          f"stroke {ENSLAVEMENT_REF['stroke']} (Li via Lew)")

    order = _order(shown)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    label = ("individuation index (calibrated)" if corrected
             else "individuation index (raw, not corrected)")
    _boxes(ax[0], [shown[shown["finger"] == f][col] for f in order], order,
           label, "How isolated was each finger")
    ax[0].axhline(1.0, color="#16a34a", ls="--", lw=1.5,
                  label="perfect isolation")
    ax[0].set_ylim(0, 1.05)
    ax[0].legend(frameon=False, fontsize=8)
    g = shown.sort_values("trial")
    ax[1].plot(g["trial"], g[col], "o", ms=3.5, alpha=.35, color="#7c3aed")
    ax[1].plot(g["trial"], g[col].rolling(5, min_periods=1).mean(),
               lw=2, color="#7c3aed")
    ax[1].set_ylim(0, 1.05); ax[1].set_xlabel("trial")
    ax[1].set_ylabel(label); ax[1].set_title("Across the block")
    _save(fig, "individuation"); plt.show()

    cols = [col] if not corrected else ["individuation_cal", "individuation"]
    _show(shown.groupby("finger")[cols]
               .agg(["count", "mean", "std"]).reindex(order).round(3))
    return ind


def sec_rhythm(trials):
    rhy = trials[(trials["mode"] == "rhythm")
                 & trials["time_difference_ms"].notna()
                 & (trials["early_late"] != "Miss")]
    if rhy.empty:
        return rhy
    print("\n" + "=" * 62)
    print("RHYTHM")
    print("=" * 62)
    off = rhy["time_difference_ms"]
    print(f"notes {len(off)}   accuracy {off.abs().mean():.1f} ms   "
          f"bias {off.mean():+.1f} ms "
          f"({'ahead of' if off.mean() < 0 else 'behind'} the beat)   "
          f"sd {off.std():.1f} ms")
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    ax[0].hist(off, bins=_nbins(off), color="#0ea5e9", alpha=.85)
    ax[0].axvline(0, color="#16a34a", lw=2, label="on the beat")
    ax[0].axvline(off.mean(), color="#dc2626", lw=2, ls="--",
                  label=f"bias {off.mean():+.0f}")
    ax[0].set_xlabel("offset (ms), negative is early")
    ax[0].set_ylabel("notes"); ax[0].set_title("Timing around the beat")
    ax[0].legend(frameon=False, fontsize=8)
    if rhy["song_time_s"].notna().any():
        g = rhy.sort_values("song_time_s")
        ax[1].plot(g["song_time_s"], g["time_difference_ms"], "o", ms=3.5,
                   alpha=.4, color="#0ea5e9")
        ax[1].plot(g["song_time_s"],
                   g["time_difference_ms"].rolling(7, min_periods=1).mean(),
                   lw=2, color="#0ea5e9")
        ax[1].axhline(0, color="#16a34a", lw=1.5)
        ax[1].set_xlabel("position in the song (s)"); ax[1].set_ylabel("offset (ms)")
        ax[1].set_title("Did timing hold up")
    o = off.values
    if len(o) > 3:
        r = np.corrcoef(o[1:], o[:-1])[0, 1]
        ax[2].scatter(o[:-1], o[1:], s=18, alpha=.5, color="#7c3aed")
        ax[2].axhline(0, color="#94a3b8", lw=1)
        ax[2].axvline(0, color="#94a3b8", lw=1)
        ax[2].set_xlabel("offset on note n"); ax[2].set_ylabel("offset on note n+1")
        ax[2].set_title(f"Tempo tracking, r = {r:.2f}")
    _save(fig, "rhythm"); plt.show()
    if len(o) > 3:
        reading = ("tracking the tempo" if r > 0.2
                   else "landing near beats without really tracking"
                   if abs(r) <= 0.2 else "over-correcting after each note")
        print(f"lag-1 correlation {r:.3f}, which reads as {reading}.")
    return rhy


def sec_bilateral(trials, unit="sensor counts", calset=None):
    """Left against right.

    Force asymmetry is the number most exposed to the sensor problem:
    the two hands sit on eight different pads, so a raw left-right force
    difference is partly just which pads each hand happens to be on.
    """
    trials = ensure_force_columns(trials, calset)
    bil = trials[trials["hand_mode"] == "both"]
    if bil.empty:
        return
    print("\n" + "=" * 62)
    print("BOTH HANDS")
    print("=" * 62)
    L, R = bil[bil["side"] == "left"], bil[bil["side"] == "right"]

    def asym(l, r):
        if pd.isna(l) or pd.isna(r) or (l + r) == 0:
            return float("nan")
        return (l - r) / ((l + r) / 2)

    lr, rr = L["time_difference_ms"].mean(), R["time_difference_ms"].mean()
    print(f"reaction time  left {lr:.0f} | right {rr:.0f}  "
          f"-> asymmetry {asym(lr, rr):+.3f}")
    corrected = bool(bil["force_calibrated"].any())
    lf, rf = L["peak_force_n"].mean(), R["peak_force_n"].mean()
    if pd.notna(lf) and pd.notna(rf):
        print(f"peak force     left {lf:.0f} | right {rf:.0f} {unit}  "
              f"-> asymmetry {asym(lf, rf):+.3f}   NOT comparable")
    if corrected:
        lc, rc = L["peak_force_cal"].mean(), R["peak_force_cal"].mean()
        if pd.notna(lc) and pd.notna(rc):
            print(f"calibrated     left {lc:.2f} | right {rc:.2f} "
                  f"{NORM_UNIT}  -> asymmetry {asym(lc, rc):+.3f}")
            print("   ^ this is the asymmetry to report")
        # The calibration screen measures one hand at a time and stores
        # one set of four gaps per session, so the second hand is being
        # normalised against the first hand's pads unless both were
        # calibrated separately.
        hands = {(c.get("hand") or "?")
                 for c in calset.per_game.values() if c} if calset else set()
        if len(hands) < 2:
            print(f"   caveat: the calibration recorded covers the "
                  f"{', '.join(sorted(hands)) or 'one'} hand only, so the")
            print("   other hand is normalised against pads it was not")
            print("   measured on. Calibrate each hand to close this.")
    elif pd.notna(lf) and pd.notna(rf):
        print("   no calibration, so the force asymmetry above is a mix of")
        print("   the two hands and the eight pads and should not be")
        print("   reported as a patient asymmetry.")
    order = _order(bil)
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = np.arange(len(order)); w = .38
    for i, side in enumerate(("right", "left")):
        ax.bar(x + (i - .5) * w,
               [bil[(bil["side"] == side) & (bil["finger"] == f)]
                ["time_difference_ms"].mean() for f in order],
               w, label=side, color=HAND_COLOUR[side])
    ax.set_xticks(x); ax.set_xticklabels(order)
    ax.set_ylabel("mean reaction time (ms)")
    ax.set_title("Reaction time, both hands"); ax.legend(frameon=False)
    _save(fig, "bilateral"); plt.show()


def sec_raw(folders, unit="sensor counts", calset=None):
    """A look at the sample stream behind one game.

    The average press shape at the end puts all four fingers on one axis,
    so it is a cross-finger force comparison and gets the same
    correction as the rest.
    """
    raw, game = None, None
    for f in folders:
        raw = load_raw(f)
        if raw is not None and len(raw) > 50:
            game = Path(f).name
            break
    if raw is None:
        return
    print("\n" + "=" * 62)
    print("RAW STREAM")
    print("=" * 62)
    samples = raw[raw["event"].isna() | (raw["event"] == "")]
    events = raw[raw["event"].notna() & (raw["event"] != "")]
    if len(samples) > 1:
        dur = samples["t_perf"].max() - samples["t_perf"].min()
        print(f"{len(samples)} samples over {dur:.1f} s "
              f"({len(samples)/max(dur,1e-9):.0f} Hz), {len(events)} events")
    presses = events[events["event"] == "press"]
    releases = events[events["event"] == "release"]
    durs = []
    for _, p in presses.iterrows():
        after = releases[(releases["lane"] == p["lane"])
                         & (releases["t_perf"] > p["t_perf"])]
        if len(after):
            durs.append((after["t_perf"].iloc[0] - p["t_perf"]) * 1000)
    if durs:
        durs = pd.Series(durs)
        print(f"press duration: mean {durs.mean():.0f} ms, "
              f"median {durs.median():.0f} ms")
        fig, ax = plt.subplots(figsize=(7, 3.0))
        ax.hist(durs, bins=_nbins(durs, 24), color="#0f172a", alpha=.8)
        ax.set_xlabel("press duration (ms)"); ax.set_ylabel("presses")
        ax.set_title("How long each press was held")
        _save(fig, "press_duration"); plt.show()

    stims = raw[raw["event"] == "stim"]
    if len(stims) and len(samples) > 50:
        BEFORE, AFTER = 0.25, 1.25
        stacked = {i: [] for i in range(4)}
        for _, s in stims.iterrows():
            lane = s.get("lane")
            if pd.isna(lane) or int(lane) > 3:
                continue
            lane = int(lane); t0 = s["t_perf"]; col = f"fsr{lane+1}"
            w = samples[(samples["t_perf"] >= t0 - BEFORE)
                        & (samples["t_perf"] <= t0 + AFTER)]
            if len(w) > 20 and col in w.columns:
                base = w[w["t_perf"] < t0][col].median()
                if pd.notna(base):
                    stacked[lane].append((w["t_perf"].values - t0,
                                          w[col].values - base))
        if any(stacked.values()):
            gaps = ([calset.gap(game, i) for i in range(4)]
                    if calset is not None else [None] * 4)
            # Only correct when every lane that has traces has a gap,
            # so the plot never mixes normalised and raw curves.
            corrected = all(gaps[l] for l, tr in stacked.items() if tr)
            fig, ax = plt.subplots(figsize=(9, 3.6))
            grid = np.linspace(-BEFORE, AFTER, 150)
            for lane, traces in stacked.items():
                if not traces:
                    continue
                mean = np.mean([np.interp(grid, t, v) for t, v in traces], axis=0)
                if corrected:
                    mean = mean / gaps[lane]
                ax.plot(grid * 1000, mean, lw=2,
                        color=FINGER_COLOUR[FINGERS[lane]],
                        label=f"{FINGERS[lane]} (n={len(traces)})")
            ax.axvline(0, color="#dc2626", lw=1.5, ls="--", label="cue")
            ax.set_xlabel("time from cue (ms)")
            ax.set_ylabel(NORM_LABEL if corrected
                          else f"force above baseline ({unit})")
            ax.set_title("Average shape of a press"
                         + ("" if corrected else ", raw counts"))
            ax.legend(frameon=False, fontsize=8)
            _save(fig, "force_waveform"); plt.show()
            if corrected:
                print("Press shapes are divided by each finger's own")
                print("calibration press, so the four traces are on one")
                print("scale and their heights can be compared.")
            else:
                print("Press shapes are in raw counts. The four traces sit")
                print("on four differently sensitive pads, so their heights")
                print("cannot be compared with each other. Shape and timing")
                print("still can.")


# ---------------------------------------------------------------- entry

def prepare(pick="latest", root=None) -> dict:
    """Everything the sections need, built once.

    Returns a dict with cat, sel, folders, metas, sessions, trials, unit
    and calset. A notebook cell can unpack it and then call any sec_
    function on its own, in any order, with no hidden state between
    cells. `trials` already carries the calibrated and newton force
    columns.
    """
    cat = build_catalogue(root)
    if cat.empty:
        return {"cat": cat, "sel": cat, "folders": [], "metas": {},
                "sessions": {}, "trials": pd.DataFrame(),
                "unit": "sensor counts", "calset": CalibrationSet()}
    sel = resolve(pick, cat)
    folders = [Path(p) for p in sel["folder"]]
    metas = load_metas(folders)
    sessions = {Path(p).name: s for p, s in zip(sel["folder"], sel["session"])}
    trials = load_games(folders, cat)
    unit = force_unit(metas)
    calset = calibration_factors(metas, unit)
    trials = add_force_columns(trials, calset)
    return {"cat": cat, "sel": sel, "folders": folders, "metas": metas,
            "sessions": sessions, "trials": trials, "unit": unit,
            "calset": calset}


def report(pick="latest", root=None, export=True):
    """Run the whole analysis on whatever `pick` selects.

    pick accepts an id from catalogue(), a list of ids, a participant
    name, a date, a mode, a session label, "latest" or "all".
    """
    use_style()
    ctx = prepare(pick, root)
    cat, sel = ctx["cat"], ctx["sel"]
    if cat.empty:
        print("Nothing recorded yet. Play a block and come back.")
        return {}
    folders, metas, trials = ctx["folders"], ctx["metas"], ctx["trials"]
    sessions, unit, calset = ctx["sessions"], ctx["unit"], ctx["calset"]

    print("=" * 62)
    print(f"REPORT  ({pick!r})")
    print("=" * 62)
    print(f"{len(folders)} game(s), {len(trials)} trials, "
          f"{sel['session'].nunique()} session(s)")
    for _, r in sel.iterrows():
        print(f"   {r['day']} {r['time']}  {r['who']:10} {r['mode']:9} "
              f"{r['trials']:4} trials")

    sec_calibration(metas, sessions)
    on_task = sec_overview(trials, folders, metas)
    sec_quality(trials, folders, metas)
    comp = sec_compare(trials)
    rt = sec_reaction_time(trials)
    sec_accuracy(trials)
    force = sec_force(trials, unit, calset)
    ind = sec_individuation(trials, calset)
    rhy = sec_rhythm(trials)
    sec_bilateral(trials, unit, calset)
    sec_raw(folders, unit, calset)
    ons = sec_onset(folders, trials, unit, calset)

    # Analyses that came out of reading the past Curtin theses.
    sec_objective_one(trials, calset=calset)
    sec_exclusions(trials)
    sec_phase(trials)
    sec_threshold_audit(metas=metas, calset=calset)
    sec_cue_modality(trials, calset)
    sec_dose(trials, on_task / 60 if on_task else 0)
    sec_sampling_note(folders)
    sec_participant_progress(root, cat)

    summary = {"games": len(folders), "trials": int(len(trials)),
               "time_on_task_min": round(on_task / 60, 1)}
    if not rt.empty:
        summary["rt_mean_ms"] = round(rt["time_difference_ms"].mean(), 1)
        summary["rt_cv"] = round(rt["time_difference_ms"].std()
                                 / rt["time_difference_ms"].mean(), 3)
    cued = trials[trials["mode"].isin(["classic", "adaptive", "mirror"])]
    if not cued.empty:
        summary["hit_rate"] = round((cued["early_late"] != "Miss").mean(), 3)
    summary["calibration"] = calset.status
    if not force.empty:
        summary["peak_force_mean_raw"] = round(force["peak_force_n"].mean(), 1)
        summary["force_unit"] = unit
        summary["peak_force_mean_N"] = round(force["peak_force_N"].mean(), 2)
        if force["peak_force_cal"].notna().any():
            summary["peak_force_mean_cal"] = round(
                force["peak_force_cal"].mean(), 3)
            summary["force_measure"] = NORM_LABEL
    if not ind.empty:
        if ind["individuation_cal"].notna().any():
            summary["individuation_mean"] = round(
                ind["individuation_cal"].mean(), 3)
            summary["individuation_basis"] = "calibrated"
        else:
            summary["individuation_mean"] = round(
                ind["individuation"].mean(), 3)
            summary["individuation_basis"] = "raw, not corrected"
    if not rhy.empty:
        summary["beat_accuracy_ms"] = round(rhy["time_difference_ms"]
                                            .abs().mean(), 1)
    if ons is not None and not ons.empty:
        summary["onset_rt_mean_ms"] = round(ons["onset_rt_ms"].mean(), 1)
        summary["onset_rt_cv"] = round(ons["onset_rt_ms"].std()
                                       / ons["onset_rt_ms"].mean(), 3)
        summary["rfd_mean_raw"] = round(ons["peak_dforce"].mean(), 1)
        if ons["peak_dforce_cal"].notna().any():
            summary["rfd_mean_cal"] = round(ons["peak_dforce_cal"].mean(), 3)

    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    _show(pd.DataFrame([summary]).T.rename(columns={0: "value"}))

    if export:
        pd.DataFrame([summary]).T.rename(columns={0: "value"}).to_csv(
            "session_summary.csv")
        trials.to_csv("selected_trials.csv", index=False)
        if not ind.empty:
            ind.to_csv("individuation_per_trial.csv", index=False)
        print("\nwritten: session_summary.csv, selected_trials.csv")
        print("figures are in figures/ ready for the report")

    return {"trials": trials, "rt": rt, "force": force, "individuation": ind,
            "rhythm": rhy, "comparison": comp, "summary": summary,
            "onset": ons, "catalogue": cat, "selected": sel}


# ---------------------------------------------------------------- picker

def _friendly_day(day: str) -> str:
    """'today', 'yesterday', or the date itself."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(day)
    except (ValueError, TypeError):
        return day or "unknown date"
    today = date.today()
    if d == today:
        return "today"
    if d == today - timedelta(days=1):
        return "yesterday"
    if (today - d).days < 7:
        return d.strftime("%A")          # Monday, Tuesday, ...
    return d.strftime("%d %b")           # 28 Jul


def menu_options(cat: pd.DataFrame):
    """Dropdown entries, newest first. Returns [(label, pick), ...].

    Three groupings, which is every scope the analysis is actually read
    at: one game, one session, or one person across every day they
    played. Headings come back with a pick of None.

    "Most recent game" and "everything together" are deliberately absent.
    The first row of the first group is the most recent game, so an extra
    entry for it was the same analysis under two names, and pooling
    different people into one set of figures is not a result anyone can
    read.
    """
    if cat.empty:
        return []
    newest = cat.iloc[::-1]              # catalogue is oldest first
    opts = [("---  one game, newest first  ---", None)]
    for idx, r in newest.iterrows():
        hit = f"{r['hit_rate']:.0%}" if pd.notna(r["hit_rate"]) else "  ?"
        opts.append((f"   {_friendly_day(r['day'])} {r['time']}   "
                     f"{r['who']}   {r['mode']}   "
                     f"{int(r['trials'])} trials, {hit} hit", int(idx)))

    sessions = list(dict.fromkeys(newest["session"]))
    if sessions:
        opts.append(("---  one session, a person on one day  ---", None))
        for s in sessions:
            g = cat[cat["session"] == s]
            day = _friendly_day(g["day"].iloc[0])
            modes = ", ".join(dict.fromkeys(g["mode"]))
            n = len(g)
            opts.append((f"   {day}   {g['who'].iloc[0]}   "
                         f"{n} game{'s' if n != 1 else ''} ({modes})", s))

    people = list(dict.fromkeys(newest["who"]))
    if people:
        opts.append(("---  one person, every day  ---", None))
        for p in people:
            n = int((cat["who"] == p).sum())
            opts.append((f"   {p}   all {n} game{'s' if n != 1 else ''}", p))
    return opts


def picker(root=None, auto=True):
    """Dropdown of every save, newest first. Choosing one runs it.

    One click and the report appears. `auto=False` puts a Run button in
    instead, if you would rather choose first and run second. Falls back
    to printing the list when ipywidgets is not installed.
    """
    cat = build_catalogue(root)
    if cat.empty:
        print("Nothing recorded yet. Play a block and come back.")
        return
    try:
        import ipywidgets as W
        from IPython.display import display as _d, clear_output
    except ImportError:
        print("ipywidgets is not installed, so here is the list instead.")
        print("Run one with report(<id>) or report(\"latest\").\n")
        for label, val in menu_options(cat):
            if val is not None:
                print(f"  {str(val):22} {label.strip()}")
        return

    state = {"cat": cat, "busy": False}

    dd = W.Dropdown(options=menu_options(cat), value=None,
                    description="Session:",
                    layout=W.Layout(width="660px"),
                    style={"description_width": "70px"})
    rescan = W.Button(description="Rescan", icon="refresh",
                      tooltip="Look for new recordings",
                      layout=W.Layout(width="110px"))
    note = W.HTML()
    out = W.Output()

    def _run(pick):
        if state["busy"]:
            return
        state["busy"] = True
        note.value = "<span style='color:#2563eb'>working...</span>"
        with out:
            clear_output(wait=True)
            try:
                report(pick, root=root)
            except Exception as e:
                print(f"{type(e).__name__}: {e}")
        note.value = ("<span style='color:#64748b'>pick another to "
                      "switch, or Rescan for new recordings</span>")
        state["busy"] = False

    def _changed(change):
        pick = change["new"]
        if pick is None:
            note.value = ("<span style='color:#b45309'>that row is a "
                          "heading, choose a save under it</span>")
            return
        if auto:
            _run(pick)

    dd.observe(_changed, names="value")

    def _rescan(_):
        fresh = build_catalogue(root)
        state["cat"] = fresh
        keep = dd.value
        dd.unobserve(_changed, names="value")
        dd.options = menu_options(fresh)
        dd.value = keep if keep in [v for _, v in dd.options] else None
        dd.observe(_changed, names="value")
        note.value = (f"<span style='color:#16a34a'>found {len(fresh)} "
                      f"game(s). Pick one.</span>")

    rescan.on_click(_rescan)

    widgets = [W.HBox([dd, rescan])]
    if not auto:
        run = W.Button(description="Run analysis", button_style="success",
                       icon="play", layout=W.Layout(width="150px"))
        run.on_click(lambda _: (_run(dd.value) if dd.value is not None
                                else None))
        widgets = [W.HBox([dd, run, rescan])]
    widgets += [note, out]
    _d(W.VBox(widgets))

    note.value = ("<span style='color:#64748b'>choose a save above and it "
                  "runs straight away</span>")
    return dd


# ------------------------------------------------- movement onset (Teasdale)
# Nakayama's 2025 software thesis estimated reaction time with a
# Teasdale-style movement-onset detector run over the raw force traces,
# rather than taking the moment a fixed threshold was crossed. The two
# are not the same thing: a threshold crossing happens some way into the
# press, so it overstates reaction time, and by an amount that depends on
# how hard the person pressed. Onset detection finds where force first
# departs from its own pre-stimulus baseline, which is the closer
# estimate of when the finger actually started moving.
#
# Following his notation: baseline mean and sd are taken from the window
# before the cue, the force derivative (DForce) is checked against both
# an absolute floor and a fraction of its own peak (Vmax), and the
# candidate onset has to be backed by a real rise in force over about
# 50 ms so a single noisy sample cannot trigger it.
#
# Reproducing his measure here means results from this device can be
# compared with his directly instead of only by eye.

ONSET = {
    "baseline_s": 0.25,     # pre-cue window for mean and sd
    "search_min_s": 0.05,   # ignore the first 50 ms, too fast to be real
    "search_max_s": 1.20,   # give up after this
    "sigma_k": 3.0,         # force must clear mean + k*sd
    "slope_frac": 0.15,     # DForce must clear this fraction of Vmax
    "step_ms": 50,          # and force must actually rise over this long
    "step_min": 3.0,        # by at least this many counts
    "smooth_n": 5,          # moving-average window on the raw samples
}


def _smooth(y, n):
    if n <= 1 or len(y) < n:
        return np.asarray(y, dtype=float)
    k = np.ones(n) / n
    return np.convolve(np.asarray(y, dtype=float), k, mode="same")


def onset_from_trace(t, force, t_stim, cfg=None):
    """Teasdale-style movement onset. Returns (rt_ms, peak_dforce) or
    (None, None) if nothing convincing happened in the window.

    t and force are arrays for one finger around one cue, t in seconds.
    """
    c = {**ONSET, **(cfg or {})}
    t = np.asarray(t, dtype=float)
    f = _smooth(force, c["smooth_n"])
    pre = f[(t >= t_stim - c["baseline_s"]) & (t < t_stim)]
    if len(pre) < 5:
        return None, None
    mu, sd = float(np.mean(pre)), float(np.std(pre))
    win = (t >= t_stim + c["search_min_s"]) & (t <= t_stim + c["search_max_s"])
    if win.sum() < 8:
        return None, None
    tw, fw = t[win], f[win]
    dt = np.median(np.diff(tw)) or 0.005
    dforce = np.gradient(fw, dt)
    vmax = float(np.max(dforce)) if len(dforce) else 0.0
    if vmax <= 0:
        return None, None
    step = max(1, int(round((c["step_ms"] / 1000.0) / dt)))
    level = mu + c["sigma_k"] * max(sd, 0.5)
    slope_gate = c["slope_frac"] * vmax
    for i in range(len(tw) - step):
        if fw[i] < level:
            continue
        if dforce[i] < slope_gate:
            continue
        if (fw[i + step] - fw[i]) < c["step_min"]:
            continue
        return (tw[i] - t_stim) * 1000.0, vmax
    return None, None


def onset_table(folders, unit="sensor counts", cfg=None,
                calset=None) -> pd.DataFrame:
    """Run the onset detector over every cue in the raw streams.

    peak_dforce is counts per second, so it carries the same per-sensor
    bias as any other force number. peak_dforce_cal divides by that
    finger's own calibration press, which is the column to compare
    between fingers.
    """
    rows = []
    for folder in folders:
        raw = load_raw(folder)
        if raw is None:
            continue
        samples = raw[raw["event"].isna() | (raw["event"] == "")]
        stims = raw[raw["event"] == "stim"]
        if not len(stims) or len(samples) < 50:
            continue
        for _, s in stims.iterrows():
            lane = s.get("lane")
            if pd.isna(lane) or int(lane) > 7:
                continue
            lane = int(lane)
            col = f"fsr{lane + 1}"
            if col not in samples.columns:
                continue
            t0 = s["t_perf"]
            w = samples[(samples["t_perf"] >= t0 - ONSET["baseline_s"] - .05)
                        & (samples["t_perf"] <= t0 + ONSET["search_max_s"] + .05)]
            if len(w) < 20:
                continue
            rt, vmax = onset_from_trace(w["t_perf"].values, w[col].values,
                                        t0, cfg)
            if rt is None:
                continue
            game = Path(folder).name
            gap = calset.gap(game, lane % 4) if calset is not None else None
            rows.append({"game": game,
                         "finger": FINGERS[lane % 4], "lane": lane,
                         "onset_rt_ms": rt, "peak_dforce": vmax,
                         "peak_dforce_cal": vmax / gap if gap else np.nan})
    return pd.DataFrame(rows)


def sec_onset(folders, trials, unit="sensor counts", calset=None):
    """Onset-based reaction time and rate of force development, and how
    they compare with the threshold-crossing figure the game records."""
    ons = onset_table(folders, unit, calset=calset)
    if ons.empty:
        return ons
    corrected = bool(ons["peak_dforce_cal"].notna().any())
    print("\n" + "=" * 62)
    print("MOVEMENT ONSET AND RATE OF FORCE DEVELOPMENT")
    print("=" * 62)
    v = ons["onset_rt_ms"]
    print(f"\nonset reaction time : n {len(v)}   mean {v.mean():.1f} ms   "
          f"median {v.median():.1f} ms   sd {v.std():.1f} ms")
    print(f"response stability  : CV {v.std()/v.mean():.3f}  "
          f"(sd over mean, lower is steadier)")
    d = ons["peak_dforce"]
    print(f"rate of force dev.  : mean {d.mean():.0f} {unit} per second "
          f"(raw, not comparable between fingers)")
    if corrected:
        print(f"rate, calibrated    : mean "
              f"{ons['peak_dforce_cal'].mean():.2f} {NORM_UNIT} per second "
              f"(comparable)")
    else:
        print("no calibration available, so the per-finger rates below are")
        print("not corrected for the pads and should not be ranked.")

    # Threshold-crossing RT from the game, for comparison.
    cued = trials[trials["mode"].isin(["classic", "adaptive", "mirror"])]
    thr = cued.loc[cued["early_late"] != "Miss", "time_difference_ms"].dropna()

    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    ax[0].hist(v, bins=_nbins(v), color="#0ea5e9", alpha=.85, label="onset")
    if len(thr):
        ax[0].hist(thr, bins=_nbins(thr), color="#94a3b8", alpha=.5,
                   label="threshold crossing")
        ax[0].legend(frameon=False, fontsize=8)
    ax[0].set_xlabel("reaction time (ms)"); ax[0].set_ylabel("trials")
    ax[0].set_title("Onset vs threshold crossing")

    order = [f for f in FINGERS if f in ons["finger"].unique()]
    bp = ax[1].boxplot([ons[ons["finger"] == f]["onset_rt_ms"] for f in order],
                       labels=order, patch_artist=True, widths=.6)
    for p, f in zip(bp["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax[1].set_ylabel("onset reaction time (ms)")
    ax[1].set_title("Onset by finger")

    dcol = "peak_dforce_cal" if corrected else "peak_dforce"
    dlabel = (f"peak dForce ({NORM_UNIT} per s)" if corrected
              else f"peak dForce ({unit} per s, raw)")
    _boxes(ax[2], [ons[ons["finger"] == f][dcol].dropna() for f in order],
           order, dlabel, "How fast force was built")
    _save(fig, "onset_rfd"); plt.show()

    cols = ["onset_rt_ms", "peak_dforce"]
    if corrected:
        cols.append("peak_dforce_cal")
    _show(ons.groupby("finger")[cols]
             .agg(["count", "mean", "std"]).reindex(order).round(2))

    if len(thr):
        gap = thr.mean() - v.mean()
        print(f"\nthreshold crossing sits {gap:+.0f} ms after onset on average.")
    return ons


# ---------------------------------------------------------------- health

def check(root=None, verbose=True) -> bool:
    """Confirm the notebook can actually run before anything else.

    Checks the packages, that the sessions folder exists, and that there
    is something in it. Prints what to do about anything missing rather
    than failing halfway through an analysis.
    """
    ok = True
    print("CHECKING SETUP")
    print("-" * 52)

    for mod, why, install in (
        ("pandas", "reading the CSVs", "pandas"),
        ("numpy", "the maths", "numpy"),
        ("matplotlib", "the plots", "matplotlib"),
        ("ipywidgets", "the dropdown picker", "ipywidgets"),
    ):
        try:
            __import__(mod)
            if verbose:
                print(f"   ok    {mod:12} {why}")
        except ImportError:
            ok = False
            print(f"   MISSING {mod:12} {why}")
            print(f"           fix: pip install {install}")

    folder = Path(root or SESSIONS_DIR)
    if not folder.exists():
        ok = False
        print(f"\n   MISSING sessions folder at {folder.resolve()}")
        print("           The notebook expects to sit in analysis/ next to")
        print("           it. If it lives somewhere else, set SESSIONS_DIR:")
        print("             import rehab_analysis as ra")
        print("             ra.SESSIONS_DIR = Path('/full/path/to/sessions')")
    else:
        cat = build_catalogue(folder)
        if cat.empty:
            print(f"\n   sessions folder found at {folder.resolve()}")
            print("   but there are no recordings in it yet.")
            print("   Play a block in the game, then run this again.")
            ok = False
        else:
            print(f"\n   ok    {len(cat)} game(s) found in {folder.resolve()}")
            newest = cat.iloc[-1]
            print(f"         newest: {newest['day']} {newest['time']} "
                  f"{newest['who']} {newest['mode']}")

    print("-" * 52)
    print("   ready to go" if ok else "   fix the above, then run check() again")
    return ok


# ------------------------------------------------- thesis-facing analyses
# Everything below came out of reading the past Curtin theses in this
# project's lineage (Lim 2023, Palmer and Lew 2024, Nakayama, Lee,
# Demouche and Dixon 2025) and checking what each of them measured that
# this notebook did not.

# SingleTact conversion. The manufacturer equation is
#     Load(N) = (counts - baseline) / 512 * sensor rating
# so on a 45 N part one count is about 0.0879 N.
SENSOR_RATING_N = 45.0
COUNTS_FULL_SCALE = 512.0
N_PER_COUNT = SENSOR_RATING_N / COUNTS_FULL_SCALE

# Healthy peak fingertip force measured by Demouche on the 2025 button
# device, 7 participants. Different button geometry so not a direct
# read-across, but the only same-lineage human data available.
DEMOUCHE_2025 = {"index_mean": 3.11, "index_max": 6.56,
                 "little_mean": 2.66, "little_max": 5.60}

# Li et al. via Lew: enslavement, the share of force appearing on the
# fingers that were not asked to move.
ENSLAVEMENT_REF = {"unimpaired": 0.13, "stroke": 0.251}

# Lang's clinical figure for repetitions per therapy session, the number
# Basil's dose argument is built on.
LANG_REPS_PER_SESSION = 32


def counts_to_newtons(counts) -> float:
    return float(counts) * N_PER_COUNT


def threshold_sets(metas) -> list:
    """Every distinct press-threshold set behind a selection, with the
    games that ran under each.

    Taking the first entry of metas and printing it as the report's
    thresholds is wrong twice over: metas is insertion ordered, so the
    first entry is the OLDEST game, and a selection can easily span more
    than one calibration. Returns a list of dicts instead, so nothing has
    to be collapsed.
    """
    out = {}
    for name, meta in _meta_items(metas):
        cal = read_calibration(meta)
        on = cal.get("on_delta")
        source, stamp = "calibration", cal.get("created_at") or "unknown"
        if not on:
            snap = ((meta.get("config_snapshot") or {}).get("fsr") or {})
            on = snap.get("on_delta")
            source, stamp = "config snapshot", "no calibration"
        if not on:
            source, stamp, on = "unrecorded", "unknown", None
        key = (source, stamp, tuple(on) if on else None)
        out.setdefault(key, {"source": source, "stamp": stamp,
                             "on_delta": list(on) if on else None,
                             "games": []})["games"].append(name)
    return [v for _, v in sorted(out.items(), key=lambda kv: str(kv[0]))]


def sec_threshold_audit(cfg_on_delta=None, metas=None, calset=None):
    """Put the press thresholds into newtons and check them against the
    only healthy force data in this project's lineage.

    Demouche measured healthy peak fingertip force on the 2025 button
    device. If a trigger sits above what a healthy little finger can
    produce, a weak finger cannot reach it either, and the game will
    score a genuine attempt as a miss. That reads as a patient deficit
    when it is really a threshold problem, so it is worth checking
    before any participant session.

    One table per distinct threshold set. Nothing is averaged and no set
    stands in for another, because a game only ever ran under its own.
    """
    print("\n" + "=" * 62)
    print("PRESS THRESHOLDS IN NEWTONS")
    print("=" * 62)
    print(f"SingleTact {SENSOR_RATING_N:.0f} N part, "
          f"{N_PER_COUNT:.4f} N per count")

    sets = []
    if cfg_on_delta is not None:
        sets = [{"source": "supplied", "stamp": "supplied by the caller",
                 "on_delta": list(cfg_on_delta), "games": []}]
    elif metas:
        found = threshold_sets(metas)
        sets = [s for s in found if s["on_delta"]]
        for s in (s for s in found if not s["on_delta"]):
            print(f"\n{len(s['games'])} game(s) recorded no thresholds at "
                  f"all: {', '.join(s['games'])}")
    if not sets:
        try:
            import sys as _s
            _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from rehab.config import Config
            sets = [{"source": "current config", "on_delta":
                     list(Config.load().get("fsr.on_delta")),
                     "stamp": "as the config reads today", "games": []}]
            print("\nNo thresholds in the session metadata, so these are the")
            print("CURRENT config values. They are not necessarily what this")
            print("data ran under.")
        except Exception:
            print("Could not read fsr.on_delta from the config.")
            return None

    tables = []
    for s in sets:
        # One row per finger whatever the list holds, so a short or
        # partly unreadable list leaves a blank in the right place
        # instead of shifting the fingers along.
        rows = []
        for i, finger in enumerate(FINGERS):
            d = np.nan
            if i < len(s["on_delta"]):
                try:
                    d = float(s["on_delta"][i])
                except (TypeError, ValueError):
                    d = np.nan
            rows.append({"finger": finger, "on_delta_counts": d,
                         "trigger_N": (round(counts_to_newtons(d), 2)
                                       if pd.notna(d) else np.nan)})
        if all(pd.isna(r["on_delta_counts"]) for r in rows):
            continue
        tbl = pd.DataFrame(rows)
        tbl.attrs["label"] = f"{s['source']}, {s['stamp']}"
        tbl.attrs["games"] = s["games"]
        tables.append(tbl)
        print(f"\nfrom the {s['source']} ({s['stamp']})")
        if s["games"]:
            print(f"   {len(s['games'])} game(s): {', '.join(s['games'])}")
        _show(tbl)

    if not tables:
        return None

    fig, ax = plt.subplots(figsize=(9, 3.6))
    width = 0.8 / len(tables)
    for i, tbl in enumerate(tables):
        x = np.arange(len(tbl)) + (i - (len(tables) - 1) / 2) * width
        ax.bar(x, tbl["trigger_N"], width,
               color=[FINGER_COLOUR[f] for f in tbl["finger"]],
               edgecolor="white",
               label=tbl.attrs["label"] if len(tables) > 1 else None)
    ax.set_xticks(np.arange(len(tables[0])))
    ax.set_xticklabels(tables[0]["finger"])
    ax.axhline(DEMOUCHE_2025["little_mean"], color="#dc2626", ls="--", lw=2,
               label=f"healthy little finger mean "
                     f"{DEMOUCHE_2025['little_mean']} N")
    ax.axhline(DEMOUCHE_2025["little_max"], color="#dc2626", ls=":", lw=2,
               label=f"healthy little finger max "
                     f"{DEMOUCHE_2025['little_max']} N")
    ax.set_ylabel("force needed to register a press (N)")
    ax.set_title("Trigger thresholds against healthy force (Demouche 2025)")
    ax.legend(frameon=False, fontsize=8)
    _save(fig, "threshold_audit"); plt.show()

    for tbl in tables:
        pinky = tbl[tbl["finger"] == "Pinky"]
        if pinky.empty:
            continue
        little = float(pinky.iloc[0]["trigger_N"])
        if little > DEMOUCHE_2025["little_max"]:
            print(f"\n   WARNING ({tbl.attrs['label']}): the pinky trigger")
            print(f"   is {little:.2f} N, above the highest little-finger")
            print(f"   force Demouche recorded in healthy participants "
                  f"({DEMOUCHE_2025['little_max']} N).")
            print("   A weak little finger may be physically unable to reach")
            print("   it, and every attempt would be logged as a miss. Run")
            print("   the Calibrate step from the title screen with the")
            print("   participant's own hand before the next session, and")
            print("   look at why that pad carries so much load at rest.")
    return tables[0] if len(tables) == 1 else tables


def _calibration_table(cal):
    """One per-finger table for one calibration. Missing entries come
    back as NaN, never as zero: a truncated calibration printed as a
    full table of zeros looks like a measurement that was never taken.
    """
    rows = []
    for i, finger in enumerate(FINGERS):
        def at(key):
            seq = cal.get(key)
            if not isinstance(seq, (list, tuple)) or i >= len(seq):
                return np.nan
            try:
                return float(seq[i])
            except (TypeError, ValueError):
                return np.nan
        on, gap = at("on_delta"), at("gap")
        rows.append({
            "finger": finger,
            "rest_load_counts": at("preload"),
            "press_gap_counts": gap,
            "trigger_counts": on,
            "trigger_N": (round(counts_to_newtons(on), 2)
                          if pd.notna(on) else np.nan),
            "pct_of_gap": (round(100 * on / gap, 0)
                           if pd.notna(on) and pd.notna(gap) and gap else
                           np.nan),
        })
    return pd.DataFrame(rows)


def sec_calibration(metas, sessions=None):
    """What a press meant on the day, taken from the calibration each
    game recorded rather than from whatever the config says now.

    One block per distinct calibration. Nothing is collapsed: a
    selection can span several, and printing the first one as though it
    covered the lot reports the OLDEST calibration and asserts the newer
    games ran under it.

    `sessions` maps game folder name to session label, so the counts
    below can say games and sessions separately. A game is one block of
    one mode; a session is one person on one day. Without it only games
    are counted, because game folders are all this function can see.

    A game recorded before the in-app calibration existed carries
    nothing here. Its force numbers are still valid in counts, but they
    cannot be compared across fingers, and the counts-to-newtons
    conversion rests on the datasheet figure alone.
    """
    print("\n" + "=" * 62)
    print("CALIBRATION THIS DATA WAS RECORDED UNDER")
    print("=" * 62)

    cs = calibration_factors(metas)
    n_games = len(cs.per_game)
    if sessions:
        n_sessions = len({sessions.get(g, g) for g in cs.per_game})
        scope = f"{n_games} game(s) across {n_sessions} session(s)"
    else:
        scope = f"{n_games} game(s)"
    print(f"{scope}   (a game is one block, a session is one person on "
          f"one day)\n")

    if cs.status == "none":
        print("None of these games recorded a calibration.")
        print("Force stays in raw counts, which are NOT comparable between")
        print("fingers, and the newton conversion comes from the SingleTact")
        print("datasheet rather than from this device.")
        return None

    if cs.uncalibrated_games:
        missing = cs.uncalibrated_games
        line = f"{len(missing)} of {n_games} game(s) have no calibration"
        if sessions:
            miss_sessions = sorted({sessions.get(g, g) for g in missing})
            line += f", covering {len(miss_sessions)} session(s)"
        print(line + ":")
        for g in missing:
            print(f"   {g}" + (f"   ({sessions.get(g, '?')})"
                               if sessions else ""))
        print("Their force values cannot be normalised, so they are left")
        print("out of the calibrated columns rather than pooled with the")
        print("rest.\n")

    if cs.status == "multiple":
        print(f"WARNING: these games span {len(cs.stamps)} different")
        print("calibrations. A press did not mean the same thing in each,")
        print("so a force change across them is not necessarily a change in")
        print("the patient. Normalising by each game's own calibration makes")
        print("the fingers comparable, but a like-for-like comparison over")
        print("time still has to stay inside one calibration.\n")

    tables = {}
    for stamp, games in cs.stamps.items():
        cal = cs.per_game[games[0]]
        print("-" * 62)
        print(f"calibration taken {stamp} on "
              f"{cal.get('device_port') or 'an unrecorded port'}, "
              f"{cal.get('hand', '?')} hand")
        label = f"{len(games)} game(s)"
        if sessions:
            label += (f" across "
                      f"{len({sessions.get(g, g) for g in games})} session(s)")
        print(f"used by {label}: {', '.join(games)}")
        problems = cs.problems[games[0]]
        if problems:
            print("\n   INCOMPLETE CALIBRATION, do not read the blanks as")
            print("   measurements of zero:")
            for p in problems:
                print(f"      {p}")
        tbl = _calibration_table(cal)
        print()
        _show(tbl)
        tables[stamp] = tbl

        mfd = multi_finger_deficit(cal)
        print("\nMulti-finger force deficit")
        if mfd["measurable"]:
            print(f"   {mfd['value'] * 100:.0f} percent of the single-finger "
                  f"force went missing when all four pressed together.")
        elif mfd["signed"] is not None:
            print(f"   not usable. Raw figure {mfd['signed'] * 100:+.0f} "
                  f"percent.")
        else:
            print("   not measured.")
        for note in mfd["notes"]:
            print(f"   caveat: {note}")
    print("-" * 62)
    return tables[list(tables)[0]] if len(tables) == 1 else tables


def sec_objective_one(trials, window=32, calset=None):
    """Objective 1 as the progress report words it: a per-finger hit rate
    between 65 and 80 percent over a 32-trial block.

    The session-level rolling figure elsewhere can sit inside the band
    while individual fingers sit well outside it, so this checks each
    finger against its own trials, which is what the objective claims.

    A finger's hit rate depends on how hard its own trigger is to reach,
    and the triggers are set per pad. `calset` adds each finger's trigger
    as a share of its own calibration press, which is what separates a
    finger that is genuinely weak from a finger sitting behind a harder
    threshold than the others.
    """
    cued = trials[trials["mode"].isin(["classic", "adaptive", "mirror"])]
    if "stim_delivered" in cued.columns:
        cued = cued[cued["stim_delivered"] != False]
    if cued.empty:
        return None
    print("\n" + "=" * 62)
    print(f"OBJECTIVE 1: PER-FINGER HIT RATE OVER {window}-TRIAL WINDOWS")
    print("=" * 62)
    order = [f for f in FINGERS if f in cued["finger"].unique()]
    fig, axes = plt.subplots(1, len(order), figsize=(3.4 * len(order), 3.2),
                             sharey=True)
    if len(order) == 1:
        axes = [axes]
    rows = []
    for ax, f in zip(axes, order):
        g = cued[cued["finger"] == f].sort_values("trial")
        hit = (g["early_late"] != "Miss").astype(float)
        roll = hit.rolling(window, min_periods=max(5, window // 4)).mean()
        inband = roll.dropna().between(BAND_LO, BAND_HI)
        first = None
        for k, (idx, val) in enumerate(roll.dropna().items()):
            if BAND_LO <= val <= BAND_HI:
                first = k
                break
        rows.append({"finger": f, "trials": len(g),
                     "hit_rate": round(hit.mean(), 3),
                     "in_band_share": (round(inband.mean(), 3)
                                       if len(inband) else np.nan),
                     "windows_to_settle": first})
        ax.axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
        ax.axhline(WILSON, color="#ca8a04", ls=":", lw=1.5)
        ax.plot(range(len(roll)), roll, lw=2, color=FINGER_COLOUR[f])
        if first is not None:
            ax.axvline(first, color="#0f172a", ls="--", lw=1,
                       label="first in band")
            ax.legend(frameon=False, fontsize=7)
        ax.set_ylim(0, 1.02); ax.set_title(f); ax.set_xlabel("window")
    axes[0].set_ylabel(f"hit rate (rolling {window})")
    fig.suptitle("Objective 1 per finger, band 65 to 80 percent",
                 fontsize=11, fontweight="bold", x=0.02, ha="left")
    _save(fig, "objective_one"); plt.show()
    tbl = pd.DataFrame(rows)

    # How hard each finger's own trigger was, as a share of the press
    # that finger produced at calibration. Comparable between fingers,
    # unlike the trigger in counts.
    if calset is not None and calset.usable:
        shares = []
        for f in tbl["finger"]:
            vals = []
            for game, cal in calset.per_game.items():
                gap = calset.gap(game, f)
                on = (cal or {}).get("on_delta") or []
                i = _finger_index(f)
                if gap and i is not None and i < len(on):
                    try:
                        vals.append(float(on[i]) / gap)
                    except (TypeError, ValueError):
                        pass
            shares.append(round(float(np.mean(vals)), 2) if vals else np.nan)
        tbl["trigger_share_of_press"] = shares
    _show(tbl)
    if "trigger_share_of_press" in tbl.columns:
        print("trigger_share_of_press: how far into that finger's own")
        print("calibration press the trigger sits. Fingers differ here only")
        print("because of the pads, so a finger with a higher share and a")
        print("lower hit rate is behind a harder threshold, not necessarily")
        print("weaker.")
    met = tbl["hit_rate"].between(BAND_LO, BAND_HI)
    print(f"\nfingers whose overall hit rate met the band: "
          f"{int(met.sum())} of {len(tbl)}")
    if not met.all():
        miss = ", ".join(tbl.loc[~met, "finger"])
        print(f"outside the band: {miss}")
    return tbl


def sec_exclusions(trials):
    """Flag trials that should not count, and show how much the headline
    numbers move once they are removed.

    Nakayama's search window let very fast presses count as genuine
    reactions, which matters most in exactly the predictable condition
    where anticipation is the confound. Anything under about 100 ms is
    faster than a real cued reaction and is almost certainly a guess.
    """
    if trials.empty:
        return None
    print("\n" + "=" * 62)
    print("TRIAL EXCLUSIONS")
    print("=" * 62)
    df = trials.copy()
    rt = df["time_difference_ms"]
    df["_no_cue"] = (df.get("stim_delivered") == False)
    df["_anticipation"] = rt.notna() & (rt < 100) & (df["mode"] != "rhythm")
    df["_excluded"] = df["_no_cue"] | df["_anticipation"]
    n = len(df)
    print(f"recorded trials            : {n}")
    print(f"cue never delivered        : {int(df['_no_cue'].sum())}")
    print(f"faster than 100 ms         : {int(df['_anticipation'].sum())}"
          "   (anticipation, not a reaction)")
    print(f"analysed                   : {int((~df['_excluded']).sum())}")

    keep = df[~df["_excluded"]]
    def headline(d):
        c = d[d["mode"].isin(["classic", "adaptive", "mirror"])]
        v = c.loc[c["early_late"] != "Miss", "time_difference_ms"].dropna()
        return {"hit_rate": round((c["early_late"] != "Miss").mean(), 3)
                             if len(c) else np.nan,
                "mean_rt": round(v.mean(), 1) if len(v) else np.nan}
    before, after = headline(df), headline(keep)
    cmp_tbl = pd.DataFrame([{"": "with everything", **before},
                            {"": "after exclusions", **after}])
    _show(cmp_tbl)
    return df


def sec_phase(trials):
    """Pretest, main and aftertest comparison.

    Nakayama and Lee's headline claim is that the gain is specific to the
    trained sequence rather than general warm-up, and it rests entirely
    on comparing the aftertest against the last trained block. The phase
    column already exists in the CSV, so this is free once a protocol
    has actually been run.
    """
    if "phase" not in trials.columns:
        return None
    ph = trials[trials["phase"].notna() & (trials["phase"] != "")]
    if ph.empty or ph["phase"].nunique() < 2:
        return None
    print("\n" + "=" * 62)
    print("PRETEST TO AFTERTEST")
    print("=" * 62)
    rows = []
    for (who, phase), g in ph.groupby(["participant", "phase"]):
        v = g.loc[g["early_late"] != "Miss", "time_difference_ms"].dropna()
        rows.append({"participant": who, "phase": phase, "trials": len(g),
                     "mean_rt": round(v.mean(), 1) if len(v) else np.nan,
                     "rt_cv": (round(v.std()/v.mean(), 3)
                               if len(v) and v.mean() else np.nan),
                     "hit_rate": round((g["early_late"] != "Miss").mean(), 3)})
    tbl = pd.DataFrame(rows)
    _show(tbl)

    fig, ax = plt.subplots(figsize=(8, 3.4))
    order = [p for p in ("pretest", "main", "aftertest")
             if p in tbl["phase"].unique()]
    for who, g in tbl.groupby("participant"):
        g = g.set_index("phase").reindex(order)
        ax.plot(order, g["mean_rt"], "o-", lw=2, label=who)
    ax.set_ylabel("mean reaction time (ms)")
    ax.set_title("Reaction time by protocol phase")
    ax.legend(frameon=False, fontsize=8)
    _save(fig, "phase"); plt.show()

    if {"pretest", "aftertest"} <= set(tbl["phase"]):
        pre = tbl[tbl["phase"] == "pretest"]["mean_rt"].mean()
        post = tbl[tbl["phase"] == "aftertest"]["mean_rt"].mean()
        print(f"\npretest {pre:.0f} ms, aftertest {post:.0f} ms, "
              f"change {post - pre:+.0f} ms")
    return tbl


def sec_dose(trials, on_task_min=0.0):
    """Repetitions against the clinical benchmark.

    Lang's figure of about 32 repetitions in a typical therapy session is
    the number the whole dose argument rests on, so it is worth plotting
    rather than only citing.

    `on_task_min` is what sec_overview returns, divided by 60. Passing 0
    skips the per-minute lines rather than guessing at them.
    """
    reps = len(trials)
    print("\n" + "=" * 62)
    print("DOSE")
    print("=" * 62)
    print(f"repetitions this selection : {reps}")
    print(f"typical clinical session   : {LANG_REPS_PER_SESSION} (Lang)")
    if reps:
        print(f"ratio                      : {reps/LANG_REPS_PER_SESSION:.1f}x")
    if on_task_min > 0:
        print(f"rate                       : {reps/on_task_min:.1f} per minute")
        print(f"projected over 30 min      : "
              f"{reps/on_task_min*30:.0f} repetitions")
    fig, ax = plt.subplots(figsize=(7, 2.6))
    ax.barh(["this selection", "typical clinical session"],
            [reps, LANG_REPS_PER_SESSION],
            color=["#16a34a", "#94a3b8"], height=.55)
    ax.set_xlabel("repetitions")
    ax.set_title("Repetitions against the clinical benchmark")
    _save(fig, "dose"); plt.show()


def sec_sampling_note(folders):
    """How many logged samples actually carry new sensor data.

    The SingleTact interface board updates its output register at about
    50 to 120 Hz whatever rate it is polled at, so a 200 Hz log contains
    repeated frames. That sets the real resolution of any onset time or
    rate-of-force figure, and it belongs in the limitations section.
    """
    for folder in folders:
        raw = load_raw(folder)
        if raw is None:
            continue
        s = raw[raw["event"].isna() | (raw["event"] == "")]
        if len(s) < 50:
            continue
        cols = [c for c in ("fsr1", "fsr2", "fsr3", "fsr4") if c in s.columns]
        if not cols:
            continue
        same = (s[cols].diff().abs().sum(axis=1) == 0)
        dup = float(same.mean())
        dur = s["t_perf"].max() - s["t_perf"].min()
        logged = len(s) / max(dur, 1e-9)
        print("\n" + "=" * 62)
        print("SAMPLING")
        print("=" * 62)
        print(f"logged rate            : {logged:.0f} Hz")
        print(f"frames identical to the one before : {dup:.0%}")
        print(f"effective new-data rate: {logged * (1 - dup):.0f} Hz")
        return {"logged_hz": logged, "duplicate_fraction": dup,
                "effective_hz": logged * (1 - dup)}
    return None


def sec_cue_modality(trials, calset=None):
    """Compare visual only, vibration only and both.

    Palmer (2024) found reaction time differed between an LED-only cue
    and all cues together, and the 2023 device existed to test exactly
    that. Vibration-only is the condition worth reporting: the screen
    does not say which finger, so it has to be found by touch, which
    isolates the tactile channel. Expect it to be slower and less
    accurate, and that difference is the result.
    """
    if "cue_mode" not in trials.columns:
        return None
    trials = ensure_force_columns(trials, calset)
    cm = trials[trials["cue_mode"].notna() & (trials["cue_mode"] != "")]
    if cm.empty or cm["cue_mode"].nunique() < 2:
        if not cm.empty:
            only = cm["cue_mode"].iloc[0]
            print("\n" + "=" * 62)
            print("CUE MODALITY")
            print("=" * 62)
            print(f"Every trial here used the '{only}' cue, so there is")
            print("nothing to compare. Run blocks under at least two")
            print("settings (Settings screen, CUE pill) to get the")
            print("comparison Palmer's result rests on.")
        return None

    print("\n" + "=" * 62)
    print("CUE MODALITY: VISUAL vs VIBRATION vs BOTH")
    print("=" * 62)
    rows = []
    for mode, g in cm.groupby("cue_mode"):
        v = g.loc[g["early_late"] != "Miss", "time_difference_ms"].dropna()
        rows.append({
            "cue": mode, "trials": len(g),
            "hit_rate": round((g["early_late"] != "Miss").mean(), 3),
            "mean_rt": round(v.mean(), 1) if len(v) else np.nan,
            "median_rt": round(v.median(), 1) if len(v) else np.nan,
            "rt_cv": (round(v.std() / v.mean(), 3)
                      if len(v) and v.mean() else np.nan),
            "wrong_finger": int((g["had_incorrect_press"] == True).sum()),
            "mean_force_raw": (round(g["peak_force_n"].mean(), 1)
                               if g["peak_force_n"].notna().any() else np.nan),
            # Each cue condition pools all four fingers, so a raw mean
            # force is weighted by which pads happened to come up. The
            # calibrated mean is not.
            "mean_force_cal": (round(g["peak_force_cal"].mean(), 3)
                               if g["peak_force_cal"].notna().any()
                               else np.nan),
        })
    tbl = pd.DataFrame(rows).sort_values("cue").reset_index(drop=True)
    _show(tbl)
    if tbl["mean_force_cal"].notna().any():
        print(f"mean_force_cal is in {NORM_UNIT} and is the force column to "
              f"compare between cues.")
    elif tbl["mean_force_raw"].notna().any():
        print("mean_force_raw is raw counts pooled over four differently")
        print("sensitive pads, so a difference between cues here can come")
        print("from which fingers were cued rather than from the cue.")

    colours = {"both": "#2563eb", "visual": "#ca8a04",
               "vibration": "#a855f7"}
    cols = [colours.get(c, "#94a3b8") for c in tbl["cue"]]
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    x = np.arange(len(tbl))
    ax[0].bar(x, tbl["mean_rt"], color=cols, width=.6)
    ax[0].set_ylabel("mean reaction time (ms)")
    ax[0].set_title("Speed by cue")
    ax[1].bar(x, tbl["hit_rate"], color=cols, width=.6)
    ax[1].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
    ax[1].set_ylim(0, 1.02); ax[1].set_ylabel("hit rate")
    ax[1].set_title("Accuracy by cue")
    ax[2].bar(x, tbl["wrong_finger"], color=cols, width=.6)
    ax[2].set_ylabel("trials with a wrong finger")
    ax[2].set_title("Wrong-finger errors by cue")
    for a in ax:
        a.set_xticks(x); a.set_xticklabels(tbl["cue"])
    _save(fig, "cue_modality"); plt.show()

    # Per-finger RT by cue, since a tactile-only cue may hurt the weaker
    # fingers more than the strong ones.
    order = [f for f in FINGERS if f in cm["finger"].unique()]
    if len(order) > 1:
        fig, ax = plt.subplots(figsize=(9, 3.4))
        w = 0.8 / max(1, len(tbl))
        for i, mode in enumerate(tbl["cue"]):
            vals = [cm[(cm["cue_mode"] == mode) & (cm["finger"] == f)]
                    ["time_difference_ms"].mean() for f in order]
            ax.bar(np.arange(len(order)) + (i - (len(tbl)-1)/2) * w, vals, w,
                   label=mode, color=colours.get(mode, "#94a3b8"))
        ax.set_xticks(np.arange(len(order))); ax.set_xticklabels(order)
        ax.set_ylabel("mean reaction time (ms)")
        ax.set_title("Reaction time per finger, by cue")
        ax.legend(frameon=False, fontsize=8)
        _save(fig, "cue_modality_per_finger"); plt.show()

    if {"visual", "vibration"} <= set(tbl["cue"]):
        vis = tbl[tbl["cue"] == "visual"].iloc[0]
        vib = tbl[tbl["cue"] == "vibration"].iloc[0]
        d_rt = vib["mean_rt"] - vis["mean_rt"]
        d_hit = vib["hit_rate"] - vis["hit_rate"]
        print(f"\nvibration minus visual: {d_rt:+.0f} ms, "
              f"hit rate {d_hit:+.3f}")
    return tbl


def sec_participant_progress(root=None, cat=None):
    """Every session a participant has done, in order, so progress
    across the whole programme is visible rather than one block at a
    time.

    This is the view that answers whether the training is working. A
    single block says how someone did that day; the trend across blocks
    is the outcome measure.

    Force here is the number most exposed to the calibration problem,
    because a trend over sessions can cross a recalibration. Each game's
    force is normalised by its own calibration, so mean_force_cal is
    comparable down the column and mean_force_raw is not.
    """
    cat = build_catalogue(root) if cat is None else cat
    if cat.empty:
        return None
    people = [p for p in cat["who"].unique() if str(p) not in ("NA", "")]
    if not people:
        return None

    print("\n" + "=" * 62)
    print("PROGRESS PER PARTICIPANT")
    print("=" * 62)

    rows = []
    for who in people:
        games = cat[cat["who"] == who]
        for n, (_, g) in enumerate(games.iterrows(), start=1):
            try:
                df = pd.read_csv(Path(g["folder"]) / "trials.csv")
            except OSError:
                continue
            rt = pd.to_numeric(df.get("time_difference_ms"), errors="coerce")
            outcome = df.get("early_late")
            hit = (outcome != "Miss") if outcome is not None else pd.Series(dtype=bool)
            good = rt[(outcome != "Miss")].dropna() if outcome is not None else rt.dropna()
            force = pd.to_numeric(df.get("peak_force_n"), errors="coerce")
            # Each game against its own calibration, so a recalibration
            # partway through a programme does not read as a force change.
            folder = Path(g["folder"])
            cs = calibration_factors({folder.name: read_meta(folder)})
            lanes = pd.to_numeric(df.get("lane"), errors="coerce")
            cal_force = [
                (cs.counts(folder.name, v) / cs.gap(folder.name, int(l) - 1))
                if (pd.notna(v) and pd.notna(l)
                    and cs.gap(folder.name, int(l) - 1)) else np.nan
                for v, l in zip(force, lanes)]
            cal_force = pd.Series(cal_force, dtype="float64")
            rows.append({
                "who": who, "n": n, "day": g["day"], "mode": g["mode"],
                "trials": len(df),
                "hit_rate": round(hit.mean(), 3) if len(hit) else np.nan,
                "mean_rt": round(good.mean(), 1) if len(good) else np.nan,
                "rt_cv": (round(good.std() / good.mean(), 3)
                          if len(good) and good.mean() else np.nan),
                "mean_force_raw": (round(force.mean(), 1)
                                   if force.notna().any() else np.nan),
                "mean_force_cal": (round(cal_force.mean(), 3)
                                   if cal_force.notna().any() else np.nan),
            })
    prog = pd.DataFrame(rows)
    if prog.empty:
        return None
    _show(prog)

    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    for who, g in prog.groupby("who"):
        g = g.sort_values("n")
        ax[0].plot(g["n"], g["mean_rt"], "o-", lw=2, label=who)
        ax[1].plot(g["n"], g["hit_rate"], "o-", lw=2, label=who)
        ax[2].plot(g["n"], g["rt_cv"], "o-", lw=2, label=who)
    ax[0].set_ylabel("mean reaction time (ms)"); ax[0].set_title("Speed")
    ax[1].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
    ax[1].set_ylim(0, 1.02); ax[1].set_ylabel("hit rate")
    ax[1].set_title("Accuracy")
    ax[2].set_ylabel("reaction time CV")
    ax[2].set_title("Consistency (lower is steadier)")
    for a in ax:
        a.set_xlabel("session number")
        a.xaxis.set_major_locator(MaxNLocator(integer=True))
        if len(people) > 1:
            a.legend(frameon=False, fontsize=8)
    _save(fig, "participant_progress"); plt.show()

    print("\nchange from first to latest session:")
    for who, g in prog.groupby("who"):
        g = g.sort_values("n")
        if len(g) < 2:
            print(f"   {who}: only one session so far")
            continue
        d_rt = g["mean_rt"].iloc[-1] - g["mean_rt"].iloc[0]
        d_hit = g["hit_rate"].iloc[-1] - g["hit_rate"].iloc[0]
        d_cv = g["rt_cv"].iloc[-1] - g["rt_cv"].iloc[0]
        line = (f"   {who}: reaction time {d_rt:+.0f} ms, "
                f"hit rate {d_hit:+.3f}, consistency {d_cv:+.3f}")
        fc = g["mean_force_cal"].dropna()
        if len(fc) > 1:
            line += f", force {fc.iloc[-1] - fc.iloc[0]:+.3f} {NORM_UNIT}"
        print(line + f" over {len(g)} sessions")
    if prog["mean_force_cal"].notna().any():
        print(f"\nmean_force_cal is {NORM_LABEL}, each game against its own")
        print("calibration, so it can be read down the column.")
    if prog["mean_force_raw"].notna().any():
        print("mean_force_raw is raw counts and cannot: it mixes the")
        print("fingers that came up with the pads they sat on, and a")
        print("recalibration between sessions moves it on its own.")
    return prog
