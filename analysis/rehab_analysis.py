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

A note on force, because it is the easiest number here to misread. Each
sensor pad reads a different number of counts for the same real force,
so raw counts cannot be compared between fingers. Force therefore comes
in three columns:

    peak_force_n    raw counts as recorded
    peak_force_N    newtons, absolute, for the Demouche comparison
    peak_force_cal  counts divided by that finger's OWN calibration press

peak_force_cal is NOT a strength ranking. The calibration press is the
patient's own light press, not a known physical force, so a weak finger
recorded a small reference press and dividing by it cancels the real
weakness along with the pad difference. Four identical pads with a true
four to one weakness gradient across the hand all come out near 1.0.
Read peak_force_cal as effort against that finger's own reference, which
is the right measure for consistency within a finger and for change over
time. For "which finger is stronger", read the newton column and accept
that the pad differences are not corrected there. Separating pad
sensitivity from finger strength needs a known physical reference on
each pad, a weight or a load cell, which this device does not have.

Sessions recorded before the in-app calibration existed get the raw and
newton columns only, and are said to be uncorrected rather than quietly
pooled with the rest.
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

# What the TRUE/FALSE columns can arrive as. read_csv turns a column of
# plain TRUE/FALSE into real booleans on its own, so the text forms only
# survive when the column also holds blanks and comes through as object.
_TRUE_TEXT = {"true", "t", "yes", "y", "1", "1.0"}
_FALSE_TEXT = {"false", "f", "no", "n", "0", "0.0"}


def as_bool(series: pd.Series) -> pd.Series:
    """A TRUE/FALSE column as real booleans, NaN where unreadable.

    read_csv has already parsed most of these to bool, so mapping the
    literal strings a second time turns every value into NaN. That is
    silent: the checks built on these columns all test `== True`,
    `!= False` or `.dropna()`, so an all-NaN column reads as "nothing to
    report" rather than as an error, and a block where every cue failed
    to reach the device comes out looking clean.
    """
    if pd.api.types.is_bool_dtype(series):
        return series

    def one(v):
        if isinstance(v, (bool, np.bool_)):
            return bool(v)
        if v is None or v is pd.NA:
            return np.nan
        if isinstance(v, float) and np.isnan(v):
            return np.nan
        text = str(v).strip().lower()
        if text in _TRUE_TEXT:
            return True
        if text in _FALSE_TEXT:
            return False
        return np.nan

    return series.map(one)


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


CATALOGUE_COLS = ["day", "time", "who", "mode", "hand", "trials",
                  "hit_rate", "mean_rt", "status", "folder", "session"]


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
    # Columns even when there is nothing on disk. An empty frame with no
    # columns turns every later cat["session"] into KeyError('session'),
    # which cascades through the whole notebook and looks like a broken
    # install rather than an empty sessions folder.
    cat = pd.DataFrame(rows, columns=CATALOGUE_COLS[:-1])
    if cat.empty:
        cat["session"] = pd.Series(dtype="object")
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


def game_key(folder) -> str:
    """A name that identifies exactly one game folder.

    The folder name on its own is not enough. sessions/<day>/<game> can
    hold the same block name on two different days, and every per-game
    lookup here is keyed on that name: the metadata, the calibration,
    the force factors. A collision quietly applies one game's
    calibration profile to another game's trials, which is the same
    class of error as normalising the left hand with the right hand's
    gaps. The day folder disambiguates, and two folders inside one day
    cannot share a name.
    """
    folder = Path(folder)
    parent = folder.parent.name
    return f"{parent}/{folder.name}" if parent else folder.name


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
                df[c] = as_bool(df[c])
        meta = read_meta(folder)
        bs = meta.get("block_summary", {}) or {}
        row = cat[cat["folder"] == str(folder)]
        df["game"] = game_key(folder)
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
    return _unique_game_labels(pd.concat(frames, ignore_index=True))


def _unique_game_labels(trials: pd.DataFrame) -> pd.DataFrame:
    """Make game_label name exactly one game.

    The label is clock time plus mode, which two games can share: two
    people recorded in the same minute, or the same mode started twice
    on two boards. Sections group on this label, so a collision silently
    merges two games into one row and sec_compare then reports there is
    nothing to compare when there is.
    """
    if trials.empty or "game_label" not in trials.columns:
        return trials
    for extra in ("participant", "game"):
        pairs = trials[["game", "game_label"]].drop_duplicates()
        clashing = pairs["game_label"].duplicated(keep=False)
        if not clashing.any():
            break
        mask = trials["game_label"].isin(set(pairs.loc[clashing, "game_label"]))
        if extra == "game":
            trials.loc[mask, "game_label"] = trials.loc[mask, "game"]
        else:
            trials.loc[mask, "game_label"] = (
                trials.loc[mask, "game_label"] + "  "
                + trials.loc[mask, extra].astype(str))
    return trials


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
    return {game_key(f): read_meta(Path(f)) for f in folders}


# ------------------------------------------------------------- calibration
# Each pad reads a different number of counts for the same real force,
# because of where it sits under the finger. On this device one light
# press gives about 49 counts on the index and 115 on the pinky. Raw
# counts are therefore not comparable between fingers, and every
# cross-finger force number built from them is reporting the hardware as
# much as the patient.
#
# The in-app calibration records what a press was worth on each pad on
# the day. Dividing by that finger's own gap removes the pad, but it
# also removes the finger: the gap is the patient's own light press, so
# a weak finger has a small divisor and the ratio hides the weakness.
# See NORM_MEANING below. The ratio answers "how hard did this finger
# push compared with itself", not "which finger is stronger".
#
# Calibration is per hand. A bilateral block sits on eight pads and each
# hand has its own profile, saved as config/calibration/current_<hand>.json
# and stamped into the session metadata with a "hand" field. Lanes are
# normalised with their own hand's profile, and a lane whose hand was
# never calibrated stays uncorrected rather than borrowing the other
# hand's numbers.

# Per-finger lists a calibration carries, all index order
# index/middle/ring/pinky, matching FINGERS.
CAL_LISTS = ("empty", "resting", "press", "press_all",
             "preload", "gap", "on_delta", "off_delta")

# Name for the calibrated measure. Deliberately not called a force: it
# is a ratio against a reference the patient produced. The old label
# "force (x calibration press)" read as a force comparable between
# fingers, which is exactly the wrong reading.
NORM_UNIT = "x own reference press"
NORM_LABEL = "relative effort (x that finger's own reference press)"

# One sentence for every table and axis where the ratio turns up. The
# reader should never meet the number without meeting this.
NORM_SHORT = ("effort against that finger's own reference press, "
              "not a strength ranking")

# The hands a lane can belong to.
HANDS = ("right", "left")


def print_norm_short(indent="   "):
    """The short version, wrapped to the width everything else here
    prints at. Every table carrying the ratio gets this."""
    for line in (f"{NORM_LABEL}.",
                 "Effort against that finger's own reference press: good",
                 "for consistency within a finger and for change over",
                 "time, NOT a between-finger strength ranking. For which",
                 "finger is stronger, read the newton column and its",
                 "caveat."):
        print(indent + line)


def normalisation_note(indent="") -> str:
    """The full statement of what the calibrated ratio can and cannot
    answer, printed once wherever force is the subject.

    Written out rather than summarised because the failure it guards
    against is silent: peak_force_cal looks like a corrected force and
    reads like one, and a reader who ranks fingers on it gets a number
    that has had the ranking divided out of it.
    """
    lines = [
        "WHAT THE CALIBRATED COLUMN MEANS",
        f"  {NORM_LABEL}.",
        "  Each finger's force divided by the light press THAT finger gave",
        "  at calibration. 1.0 means the same effort as that reference.",
        "",
        "  It CAN answer: was this finger consistent, did its effort change",
        "  across the block, did it change between sessions.",
        "",
        "  It CANNOT answer: which finger is stronger. The reference press",
        "  is the patient's own light press, not a known physical force, so",
        "  a weak finger recorded a small reference and dividing by it",
        "  cancels the weakness along with the pad difference. Four",
        "  identical pads with a real four to one weakness gradient across",
        "  the hand all come out near 1.0 on this measure.",
        "",
        "  For a between-finger strength comparison, read the newton",
        "  figures. Those are absolute, but they are NOT corrected for pad",
        "  sensitivity, so part of any difference between fingers there is",
        "  the hardware.",
        "",
        "  This device cannot separate pad sensitivity from finger strength.",
        "  Doing that needs a known physical reference on each pad, a weight",
        "  or a load cell, and there is none here. Report the limitation",
        "  rather than picking whichever number looks cleaner.",
    ]
    return "\n".join(indent + ln if ln else ln for ln in lines)

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


def lane_side(lane, hand_mode="right"):
    """Which hand a 0-based lane belongs to, or None when it makes no
    sense.

    A bilateral block puts the right hand on lanes 0 to 3 and the left on
    4 to 7. A one-handed block only ever uses 0 to 3, and those belong to
    whichever hand was played, so the lane number alone does not say
    which hand a reading came from.
    """
    mode = str(hand_mode or "right").strip().lower()
    if mode in ("left", "right"):
        return mode
    try:
        i = int(lane)
    except (TypeError, ValueError):
        return None
    if isinstance(lane, float) and np.isnan(lane):
        return None
    return "left" if i >= len(FINGERS) else "right"


def normalise_hand(hand) -> str | None:
    h = str(hand or "").strip().lower()
    return h if h in HANDS else None


def read_calibrations(meta) -> dict:
    """Every calibration a session recorded, keyed by hand.

    Calibration is measured one hand at a time, so a bilateral block can
    carry two profiles, one, or none. Three shapes turn up and all three
    have to be read, because a session written by an older build has to
    keep working:

        {"hand": "right", "gap": [...], ...}      one profile
        {"right": {...}, "left": {...}}            one per hand
        [{...}, {...}]                             a list of profiles

    A profile with no hand field at all is taken as the right hand,
    which is what the app defaults to, and that assumption is reported
    by sec_calibration rather than buried here.
    """
    raw = (meta or {}).get("calibration")
    out = {}

    def take(cal, fallback=None):
        if not isinstance(cal, dict) or not cal:
            return
        hand = normalise_hand(cal.get("hand")) or normalise_hand(fallback)
        if hand is None:
            hand = "right"
            cal = {**cal, "hand": hand, "hand_assumed": True}
        out.setdefault(hand, cal)

    if isinstance(raw, dict):
        by_hand = {k: v for k, v in raw.items()
                   if normalise_hand(k) and isinstance(v, dict)}
        if by_hand:
            for key, cal in by_hand.items():
                take(cal, key)
        else:
            take(raw)
    elif isinstance(raw, (list, tuple)):
        for cal in raw:
            take(cal)
    return out


def read_calibration(meta, hand=None) -> dict:
    """One hand's calibration, empty dict when that hand has none.

    Kept for callers that only ever look at one hand. With no hand asked
    for it returns the single profile when there is exactly one, and an
    empty dict when the session carries two, so nothing can pick up the
    wrong hand's numbers by accident.
    """
    cals = read_calibrations(meta)
    if hand is not None:
        return cals.get(normalise_hand(hand) or "", {})
    return list(cals.values())[0] if len(cals) == 1 else {}


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


def calibration_signature(cal) -> tuple:
    """What a calibration actually measured, for telling two of them
    apart.

    created_at is not enough on its own. Two profiles saved inside the
    same second, or one metadata.json copied into another session, share
    a timestamp while holding different numbers, and grouping on the
    timestamp then prints one table of the first game's figures over the
    lot.
    """
    out = []
    for key in CAL_LISTS:
        seq = cal.get(key)
        if not isinstance(seq, (list, tuple)):
            out.append((key, None))
            continue
        vals = []
        for v in seq:
            try:
                vals.append(round(float(v), 3))
            except (TypeError, ValueError):
                vals.append(None)
        out.append((key, tuple(vals)))
    return tuple(out)


@dataclass
class CalibrationSet:
    """Every calibration behind one selection, kept apart rather than
    collapsed.

    A selection can span games recorded under different calibrations, or
    under none at all, so there is no single set of numbers to hand back.
    Callers ask per game and per hand and get None when that game has
    nothing usable for that hand and finger.

    Per hand matters. Lanes 4 to 7 are the left hand, and normalising
    them with the right hand's gaps mixes two sets of pads into one
    number that looks corrected. A hand with no profile stays
    uncorrected instead.
    """

    # game -> {hand -> calibration}
    per_game: dict = field(default_factory=dict)
    # game -> {hand -> [gap|None] x4}
    gaps: dict = field(default_factory=dict)
    # game -> {hand -> [str]}
    problems: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)        # game -> logged unit
    played: dict = field(default_factory=dict)       # game -> {hand}
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

    def cals(self, game) -> dict:
        """{hand: calibration} for one game, empty when it has none."""
        return self.per_game.get(str(game)) or {}

    def hands(self, game) -> set:
        """Hands of one game that have at least one usable finger gap."""
        out = set()
        for hand, seq in (self.gaps.get(str(game)) or {}).items():
            if any(g is not None for g in seq):
                out.add(hand)
        return out

    def missing_hands(self, game, needed) -> list:
        """Hands this game has trials on but no usable calibration for."""
        have = self.hands(game)
        return sorted(h for h in needed if h and h not in have)

    @property
    def all_cals(self) -> list:
        """(game, hand, calibration) for every profile in the selection."""
        return [(g, h, c)
                for g in sorted(self.per_game)
                for h, c in sorted((self.per_game[g] or {}).items())
                if c]

    @property
    def stamps(self) -> dict:
        """Label -> the (game, hand) pairs recorded under it, oldest key
        first.

        Grouped by what each calibration measured as well as by when it
        was taken, so two different profiles sharing a timestamp stay in
        two blocks instead of one block showing the first one's numbers.
        The hand is part of the grouping too: a left and a right profile
        saved in the same second are two different measurements of two
        different sets of pads.
        """
        groups = {}
        for game, hand, cal in self.all_cals:
            key = (cal.get("created_at") or "unknown", hand,
                   calibration_signature(cal))
            groups.setdefault(key, []).append((game, hand))

        out, seen = {}, {}
        for (created, hand, _sig), pairs in sorted(groups.items(),
                                                   key=lambda kv: str(kv[0])):
            base = f"{created}  ({hand} hand)"
            seen[base] = seen.get(base, 0) + 1
            label = (base if seen[base] == 1
                     else f"{base}  (distinct calibration {seen[base]})")
            out[label] = pairs
        return out

    @property
    def status(self) -> str:
        """none, single, partial or multiple.

        Counted per hand. One bilateral game with a left and a right
        profile is one calibration of each hand, not two calibrations of
        the selection, so it must not raise the "these games span more
        than one calibration" warning.
        """
        n_cal = len(self.calibrated_games)
        if n_cal == 0:
            return "none"
        per_hand = {}
        for _game, hand, cal in self.all_cals:
            per_hand.setdefault(hand, set()).add(calibration_signature(cal))
        if any(len(sigs) > 1 for sigs in per_hand.values()):
            return "multiple"
        if n_cal < len(self.per_game):
            return "partial"
        if any(self.missing_hands(g, self.played.get(g, set()))
               for g in self.per_game):
            return "partial"
        return "single"

    @property
    def usable(self) -> bool:
        """Whether any finger of any hand of any game can be normalised."""
        return any(g is not None
                   for by_hand in self.gaps.values()
                   for seq in by_hand.values()
                   for g in seq)

    def gap(self, game, finger, hand=None):
        """Counts between resting and a light press, for one finger of
        one hand of one game. None when that pad has no usable
        calibration.

        `hand` is required whenever the game could have both. With no
        hand given it falls back to the game's only profile, and returns
        None when the game carries two, so a lane can never pick up the
        other hand's numbers by omission.
        """
        by_hand = self.gaps.get(str(game)) or {}
        if not by_hand:
            return None
        hand = normalise_hand(hand)
        if hand is None:
            if len(by_hand) != 1:
                return None
            seq = list(by_hand.values())[0]
        else:
            seq = by_hand.get(hand)
        if not seq:
            return None
        i = _finger_index(finger)
        if i is None or i >= len(seq):
            return None
        return seq[i]

    def lane_gap(self, game, lane, hand_mode="right"):
        """Gap for a 0-based lane, taken from the hand that lane sits on."""
        return self.gap(game, lane % len(FINGERS),
                        lane_side(lane, hand_mode))

    def factor(self, game, finger, hand=None):
        """Multiply raw counts above baseline by this to get force as a
        fraction of that finger's own reference press."""
        g = self.gap(game, finger, hand)
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


def played_hands(meta) -> set:
    """The hands a block was played with, from its metadata."""
    mode = str((meta or {}).get("hand") or "").strip().lower()
    if mode == "both":
        return set(HANDS)
    h = normalise_hand(mode)
    return {h} if h else set()


def hand_profiles_on_disk(root=None) -> dict:
    """The per-hand profiles sitting in config/calibration right now.

    Only used to say which hands have ever been calibrated on this
    machine, so the caveat text can name the file that is missing. These
    are NOT applied to any session: current_left.json is whatever was
    measured last, not what a past block ran under, and using it would
    put a corrected-looking number on data it never covered.
    """
    base = Path(root) if root else Path(SESSIONS_DIR).parent
    out = {}
    for hand in HANDS:
        p = base / "config" / "calibration" / f"current_{hand}.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            out[hand] = {"path": str(p),
                         "created_at": data.get("created_at", "unknown")}
    return out


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
        cals = read_calibrations(meta)
        cs.per_game[name] = cals
        cs.gaps[name] = {h: calibration_gaps(c) for h, c in cals.items()}
        cs.problems[name] = {h: calibration_problems(c)
                             for h, c in cals.items()}
        # Which hands the block actually played, so sec_calibration can
        # say a hand was used but never calibrated rather than only
        # listing what was measured.
        cs.played[name] = played_hands(meta)

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


def parse_peaks_normalised(cell, game=None, calset=None,
                           hand_mode="right") -> dict:
    """parse_peaks with every lane divided by that lane's own reference
    press, taken from the profile for the hand that lane sits on.

    Lanes with no usable gap are left out, so a caller can spot a partial
    result by comparing the length against parse_peaks. `hand_mode` is
    the block's hand setting: without it, lanes 4 to 7 would be divided
    by the right hand's gaps, which is eight pads normalised by four.
    """
    raw = parse_peaks(cell)
    if calset is None or not raw:
        return {}
    out = {}
    for lane0, val in raw.items():
        g = calset.lane_gap(game, lane0, hand_mode)
        if g:
            out[lane0] = calset.counts(game, val) / g
    return out


def add_force_columns(trials, calset=None) -> pd.DataFrame:
    """Copy of `trials` carrying the calibrated and the newton force
    columns next to the raw counts.

    peak_force_cal, impulse_cal and force_window_sum_cal are counts above
    baseline divided by the light press THAT finger of THAT hand gave at
    calibration, so 1.0 means the same effort as its own reference. They
    are not a between-finger strength comparison: see normalisation_note.

    peak_force_N and impulse_Ns stay absolute, because Demouche's healthy
    fingertip forces are in newtons and a ratio cannot be checked against
    them. They are not corrected for pad sensitivity either.

    Each row is normalised with the profile for the hand its lane sits
    on. A row on a hand with no profile comes back blank in the
    calibrated columns with force_calibrated False, rather than borrowing
    the other hand's gaps.

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
        hand_mode = r.get("hand_mode", "right")
        side = r.get("side") or lane_side(_lane0(r), hand_mode)
        g = (calset.gap(game, r.get("finger"), side)
             if calset is not None else None)
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
        norm = parse_peaks_normalised(cell, game, calset, hand_mode)
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


def _lane0(row):
    """A trial row's 0-based lane, or None when it has none."""
    lane = row.get("lane")
    try:
        if pd.isna(lane):
            return None
        return int(lane) - 1
    except (TypeError, ValueError):
        return None


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

    Two indices come out, on two different bases, and they are not
    interchangeable.

    `individuation` is on absolute readings. That is the basis the
    enslavement figures in the literature use (13 percent unimpaired,
    25.1 percent after stroke), so it is the one that can be put next to
    them. It carries the per-pad sensitivity bias: a finger on an
    over-reading pad inflates the denominator on every trial and drags
    the index down for every other finger.

    `individuation_cal` divides each lane by its own reference press
    first. That removes the pad, but it also weights each finger's spill
    by the inverse of that finger's own press strength, so a weak finger
    with a small reference contributes more spill per newton than a
    strong one. The per-finger ranking it produces is not the ranking on
    absolute force, and the number is NOT comparable with the published
    enslavement figures. It answers a different question: how the force
    spread relative to what each finger can produce.

    `comparable` marks the trials where both indices exist, so a raw
    against corrected comparison can be made over the same trials. That
    matters because correctability is not random: a lane is dropped
    when its finger has no usable gap, which is exactly the lanes most
    likely to be carrying spill, so comparing the corrected mean over
    its own subset against the raw mean over all trials moves the
    corrected figure up for reasons that have nothing to do with the
    calibration.
    """
    cols = ["row_id", "trial", "finger", "game", "game_label", "hand",
            "on_target", "spillover", "individuation", "on_target_cal",
            "spillover_cal", "individuation_cal", "corrected", "comparable",
            "why_not"]
    rows = []
    if trials.empty or "force_window_peaks" not in trials.columns:
        return pd.DataFrame(columns=cols)
    for idx, r in trials.iterrows():
        cell = r.get("force_window_peaks")
        peaks = parse_peaks(cell)
        lane0 = _lane0(r)
        if not peaks or lane0 is None:
            continue
        tgt = lane0
        hand_mode = r.get("hand_mode", "right")
        side = r.get("side") or lane_side(tgt, hand_mode)
        on_target = peaks.get(tgt, 0.0)
        spill = sum(v for k, v in peaks.items() if k != tgt)
        total = on_target + spill
        if total <= 0:
            continue
        # The trials row this came from. Joining on (game, trial) is not
        # safe: two folders can carry the same block name, and trial
        # numbers restart at 1 in every block.
        row = {"row_id": idx,
               "trial": r["trial"], "finger": r["finger"],
               "game": r.get("game"), "game_label": r["game_label"],
               "hand": side,
               "on_target": on_target, "spillover": spill,
               "individuation": on_target / total,
               "on_target_cal": np.nan, "spillover_cal": np.nan,
               "individuation_cal": np.nan, "corrected": False,
               "comparable": False, "why_not": ""}
        # Every lane in the trial needs a gap, including the target lane
        # even when it registered nothing: an on-target zero is a real
        # zero and has to stay in. Normalising some lanes and leaving
        # others raw would be worse still, because the mixture is
        # invisible in the result.
        norm = parse_peaks_normalised(cell, r.get("game"), calset, hand_mode)
        tgt_gap = (calset.gap(r.get("game"), tgt % len(FINGERS), side)
                   if calset is not None else None)
        if calset is None or not calset.usable:
            row["why_not"] = "no calibration for these games"
        elif not tgt_gap:
            row["why_not"] = (f"no usable {side}-hand gap for the target "
                              f"finger")
        elif len(norm) != len(peaks):
            missing = sorted(FINGERS[k % len(FINGERS)]
                             for k in peaks if k not in norm)
            row["why_not"] = ("no usable gap on a lane that registered: "
                              + ", ".join(missing))
        if not row["why_not"]:
            on_c = norm.get(tgt, 0.0)
            spill_c = sum(v for k, v in norm.items() if k != tgt)
            total_c = on_c + spill_c
            if total_c > 0:
                row.update({"on_target_cal": on_c, "spillover_cal": spill_c,
                            "individuation_cal": on_c / total_c,
                            "corrected": True, "comparable": True})
            else:
                row["why_not"] = "nothing registered once normalised"
        rows.append(row)
    return pd.DataFrame(rows, columns=cols)


# -------------------------------------------------- what counts as a
# reaction time
#
# time_difference_ms is two different measurements under one name. In
# classic, adaptive and mirror it is the delay from the cue to the press,
# a reaction time, and it cannot be negative. In rhythm it is a SIGNED
# offset from the beat: the note is known in advance, so pressing early
# is normal and the column is negative about half the time.
#
# Pooling the two produces numbers that are not wrong so much as
# meaningless. A rhythm block's mean of -95 ms mixed with a classic
# block's 158 ms gave a left-right "asymmetry" of -8.027 on the shipped
# data, and a coefficient of variation of -0.475, which cannot exist.
# Every reaction-time aggregate goes through here instead.

CUED_MODES = ("classic", "adaptive", "mirror")


def is_cued(trials) -> pd.Series:
    """True on trials whose time_difference_ms is a reaction time."""
    if trials.empty or "mode" not in trials.columns:
        return pd.Series(False, index=trials.index, dtype=bool)
    return trials["mode"].isin(CUED_MODES)


def reaction_times(trials, per=None):
    """Reaction times only: cued modes, misses removed, blanks removed.

    Returns the values as a Series when `per` is None, otherwise the
    rows, so callers that need to group keep their other columns.
    """
    if trials is None or trials.empty:
        empty = trials if trials is not None else pd.DataFrame()
        return empty if per == "rows" else pd.Series(dtype="float64")
    rows = trials[is_cued(trials)]
    if "time_difference_ms" not in rows.columns:
        return rows.iloc[0:0] if per == "rows" else pd.Series(dtype="float64")
    rows = rows[rows["time_difference_ms"].notna()]
    if "early_late" in rows.columns:
        rows = rows[rows["early_late"] != "Miss"]
    if per == "rows":
        return rows
    return rows["time_difference_ms"].astype(float)


def rt_stats(trials) -> dict:
    """n, mean and CV over reaction times only. CV is None rather than
    negative: a negative CV means beat offsets got in, not a fast
    participant."""
    v = reaction_times(trials)
    if v.empty:
        return {"n": 0, "mean_rt": np.nan, "rt_cv": np.nan}
    mean = float(v.mean())
    cv = float(v.std() / mean) if mean > 0 and len(v) > 1 else np.nan
    return {"n": int(len(v)), "mean_rt": round(mean, 1),
            "rt_cv": round(cv, 3) if pd.notna(cv) else np.nan}


def rhythm_rows(trials):
    """Rhythm trials with a usable beat offset."""
    if trials.empty or "mode" not in trials.columns:
        return trials.iloc[0:0] if not trials.empty else trials
    rhy = trials[(trials["mode"] == "rhythm")
                 & trials["time_difference_ms"].notna()]
    if "early_late" in rhy.columns:
        rhy = rhy[rhy["early_late"] != "Miss"]
    return rhy


# --------------------------------------------------- trial exclusions
# Two kinds of trial cannot be analysed. A trial where the cue command
# never reached the device was never presented, so the participant had
# nothing to react to. A press under 100 ms is faster than a cued
# reaction and is anticipation, not a response.
#
# The headline table and the exported CSV used to be built from every
# recorded trial, including these, while the exclusions section printed
# how many there were. On the shipped default that meant a hit rate and
# a mean reaction time computed from 48 trials the same notebook said
# could not be analysed.

ANTICIPATION_MS = 100.0


def exclusion_flags(trials) -> pd.DataFrame:
    """Copy of `trials` with why each trial can or cannot be analysed."""
    df = trials.copy()
    if df.empty:
        for c in ("no_cue", "anticipation", "excluded"):
            df[c] = pd.Series(dtype="bool")
        df["exclusion_reason"] = pd.Series(dtype="object")
        return df
    rt = df["time_difference_ms"] if "time_difference_ms" in df.columns \
        else pd.Series(np.nan, index=df.index)
    mode = df["mode"] if "mode" in df.columns \
        else pd.Series("", index=df.index)
    df["no_cue"] = (df.get("stim_delivered") == False)
    df["anticipation"] = (rt.notna() & (rt < ANTICIPATION_MS)
                          & (mode != "rhythm"))
    df["excluded"] = df["no_cue"] | df["anticipation"]
    df["exclusion_reason"] = np.where(
        df["no_cue"], "cue never delivered",
        np.where(df["anticipation"],
                 f"faster than {ANTICIPATION_MS:.0f} ms", ""))
    return df


def analysable(trials):
    """(kept trials, flagged trials, counts). The kept frame is what any
    headline number should be built from."""
    flagged = exclusion_flags(trials)
    if flagged.empty:
        counts = {"recorded": 0, "no_cue": 0, "anticipation": 0,
                  "analysed": 0}
        return flagged, flagged, counts
    counts = {"recorded": int(len(flagged)),
              "no_cue": int(flagged["no_cue"].sum()),
              "anticipation": int(flagged["anticipation"].sum()),
              "analysed": int((~flagged["excluded"]).sum())}
    return flagged[~flagged["excluded"]].copy(), flagged, counts


# ---------------------------------------------------------------- sections

def _order(df, col="finger"):
    return [f for f in FINGERS if f in df[col].unique()]


def _nothing(*lines):
    """Say why a section has nothing to show. Every section prints
    something: a section that returns in silence reads as one that
    crashed, and the reader cannot tell an empty result from a broken
    cell."""
    for ln in lines:
        print(ln)


def sec_overview(trials, folders, metas):
    print("=" * 62)
    print("OVERVIEW")
    print("=" * 62)
    if not folders:
        _nothing("Nothing is selected, so there is no game to summarise.",
                 "Record a block, then run the cells above again.")
        return 0.0
    rows = []
    for f in folders:
        m = metas.get(game_key(f), {})
        bs = m.get("block_summary", {}) or {}
        sub = (trials[trials["folder"] == str(f)]
               if "folder" in trials.columns else trials.iloc[0:0])
        rows.append({
            "game": (sub["game_label"].iloc[0] if len(sub)
                     else game_key(f)),
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
    if trials.empty:
        _nothing("No trials are loaded, so there is nothing to check.",
                 "Pick a save from the dropdown and run the load cell.")
        return
    if "stim_delivered" in trials.columns:
        sd = trials["stim_delivered"].dropna()
        if len(sd):
            # Compare against False rather than inverting. Concatenating
            # games leaves this column as object dtype, where `~` is
            # integer bitwise negation and turns the count negative.
            failed = int((sd == False).sum())
            print(f"cue commands not delivered : {failed} of {len(sd)}")
            if failed:
                print("   ^ no cue on those trials. Not ordinary misses.")
    n_force = trials["peak_force_n"].notna().sum()
    print(f"trials with force data     : {n_force} of {len(trials)}")
    if n_force == 0:
        # Blaming keyboard mode is a guess. A serial device that was
        # connected but never crossed a trigger leaves the same empty
        # column, and that is a hardware fault worth chasing rather than
        # a choice of input worth ignoring.
        sources = {str(metas.get(game_key(f), {}).get("source_name", "?"))
                   for f in folders}
        if all(s == "?" or s.lower().startswith("keyboard") for s in sources):
            print("   ^ keyboard mode, so force and individuation are empty.")
        else:
            print(f"   ^ input was {', '.join(sorted(sources))}, which is not")
            print("     keyboard mode. The sensors were connected and never")
            print("     registered a press, so check the wiring and the press")
            print("     thresholds before reading any force number below.")
    for f in folders:
        bs = metas.get(game_key(f), {}).get("block_summary", {}) or {}
        if bs.get("pauses"):
            print(f"{game_key(f)}: paused {bs['pauses']}x "
                  f"for {bs.get('paused_total_s', 0):.0f}s")
        drift = bs.get("drift_units_per_min") or {}
        vals = [(abs(v), k) for k, v in drift.items() if v is not None]
        if vals:
            worst = max(vals)
            flag = "   <- large, check the sensor" if worst[0] > 10 else ""
            print(f"{game_key(f)}: worst drift {worst[1]} "
                  f"{worst[0]:.2f}/min{flag}")


def sec_compare(trials):
    if trials.empty:
        print("No trials are loaded, so there is nothing to compare.")
        return None
    games = trials["game_label"].nunique()
    if games < 2:
        print("Only one game in this selection, so there is nothing\n"
              "to compare against. Pick a session or a participant\n"
              "from the dropdown to compare games.")
        return None
    print("\n" + "=" * 62)
    print("COMPARING GAMES")
    print("=" * 62)
    rows = []
    for g, sub in trials.groupby("game_label", sort=False):
        # Reaction time only from cued modes. A rhythm block's column is
        # a signed offset from the beat, so putting it in a mean_rt
        # cell would print a negative reaction time next to real ones.
        s = rt_stats(sub)
        mode = sub["mode"].iloc[0]
        rows.append({"game": g, "mode": mode, "trials": len(sub),
                     "hit_rate": round((sub["early_late"] != "Miss").mean(), 3),
                     "rt_trials": s["n"],
                     "mean_rt": s["mean_rt"], "rt_cv": s["rt_cv"]})
    comp = pd.DataFrame(rows)
    _show(comp)
    if (comp["mode"] == "rhythm").any():
        print("mean_rt and rt_cv are blank for rhythm blocks. Their")
        print("time_difference_ms is a signed offset from the beat, not a")
        print("reaction time, so it cannot go in the same column. The")
        print("rhythm section below reports those offsets on their own.")
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
    rt = reaction_times(trials, per="rows")
    if rt.empty:
        print("\nNo cued-mode reaction times here. This section covers")
        print("classic, adaptive and mirror blocks with a press logged")
        print("against the cue. Rhythm blocks are left out on purpose:")
        print("their timing column is an offset from the beat, not a")
        print("reaction time.")
        return rt
    print("\n" + "=" * 62)
    print("REACTION TIME")
    print("=" * 62)
    v = rt["time_difference_ms"]
    # CV through rt_stats so it can never come out negative. A negative
    # CV is impossible and only ever meant beat offsets had got in.
    s = rt_stats(rt)
    cv = f"{s['rt_cv']:.3f}" if pd.notna(s["rt_cv"]) else "not computable"
    print(f"n {len(v)}   mean {v.mean():.1f} ms   median {v.median():.1f} ms   "
          f"sd {v.std():.1f}   CV {cv}")
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
    # Blank rather than negative where the mean is not positive.
    per["CV"] = (per["sd"] / per["mean"]).where(per["mean"] > 0).round(3)
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
    """Hit rate against the challenge-point band.

    The band belongs to the adaptive controller, so when the selection
    holds adaptive blocks this narrows to them. That used to happen
    silently, and the printed hit rate then disagreed with the one the
    summary exported over every cued block. Both scopes are printed now,
    and the returned dict names which one the band was checked against
    so the summary can label them apart.
    """
    print("\n" + "=" * 62)
    print("ACCURACY AND THE CHALLENGE POINT")
    print("=" * 62)
    if trials.empty:
        _nothing("No trials are loaded, so there is no hit rate to show.")
        return None
    cued = trials[is_cued(trials)]
    adaptive = trials[trials["mode"] == "adaptive"] if "mode" in trials \
        else trials.iloc[0:0]
    if cued.empty:
        _nothing("No classic, adaptive or mirror trials in this selection,",
                 "so there is no hit rate against the band to show. Rhythm",
                 "blocks are scored on beat timing instead, in the rhythm",
                 "section below.")
        return None
    target = adaptive if not adaptive.empty else cued
    scope = "adaptive blocks only" if not adaptive.empty \
        else "all cued blocks (classic, adaptive, mirror)"
    hit = (target["early_late"] != "Miss")
    hit_all = (cued["early_late"] != "Miss")
    print(f"SCOPE of this section: {scope}")
    print(f"   hit rate, {scope}")
    print(f"      {hit.mean():.1%}  ({hit.sum()} of {len(hit)} trials)")
    print("   hit rate, all cued blocks (what the summary exports)")
    print(f"      {hit_all.mean():.1%}  ({hit_all.sum()} of {len(hit_all)} "
          f"trials)")
    if not adaptive.empty and len(hit) != len(hit_all):
        print("The band belongs to the adaptive controller, so it is")
        print("checked against the adaptive figure. The all-cued figure is")
        print("the one the summary exports. Two scopes, not a disagreement.")
    print(f"inside the {BAND_LO:.0%} to {BAND_HI:.0%} band ({scope}): "
          f"{'yes' if BAND_LO <= hit.mean() <= BAND_HI else 'no'}")

    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    roll = hit.rolling(12, min_periods=3).mean()
    ax[0].axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15,
                  label="target 65 to 80%")
    ax[0].axhline(WILSON, color="#ca8a04", ls=":", lw=2, label="Wilson 85%")
    ax[0].plot(range(len(roll)), roll, lw=2, color="#2563eb")
    ax[0].set_ylim(0, 1.02); ax[0].set_xlabel("trial")
    ax[0].set_ylabel("hit rate (rolling 12)")
    ax[0].set_title(f"Did difficulty stay in the band ({scope})")
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

    return {"scope": scope,
            "hit_rate_scoped": round(float(hit.mean()), 3),
            "hit_rate_all_cued": round(float(hit_all.mean()), 3),
            "trials_scoped": int(len(hit)),
            "trials_all_cued": int(len(hit_all))}


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
    pinky. The newton column is that same reading times a datasheet
    constant, so it carries the same pad bias, and it exists so the
    numbers can be put next to Demouche's healthy fingertip forces.

    The calibrated column divides out the pad, but it divides out the
    finger with it, so it answers consistency and change over time
    rather than which finger is stronger. This is the section that
    states that in full, once, because it is where force is the subject.
    """
    trials = ensure_force_columns(trials, calset)
    force = trials[trials["peak_force_n"].notna()] if not trials.empty \
        else trials
    if force.empty:
        print("\n" + "=" * 62)
        print(f"FORCE   (logged unit: {unit})")
        print("=" * 62)
        _nothing("No force data in this selection. The force columns are",
                 "only filled when the sensors are streaming, so they are",
                 "empty for keyboard blocks and for blocks where nothing",
                 "crossed a press threshold.")
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
        print(normalisation_note())
        if n_missing:
            print(f"\n{n_missing} of {len(force)} force trials had no usable")
            print("calibration for their finger on their hand, and are blank")
            print("in the calibrated columns rather than borrowing another")
            print("hand's or another finger's reference.")
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
               NORM_LABEL, "Effort against each finger's own reference")
        ax[0].axhline(1.0, color="#16a34a", ls="--", lw=1.5,
                      label="own reference press")
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
        print("peak_force_cal  effort against that finger's own reference")
        print("              press, not a strength ranking")
    print("peak_force_N  newtons, absolute, for the Demouche comparison")

    # The between-finger question, answered on the only basis that can
    # answer it at all. Absolute newtons keep the real differences in
    # them, which the ratio above does not, at the price of keeping the
    # pad differences too. Printing it separately and saying so is more
    # use than printing nothing and letting the ratio be read as a
    # ranking.
    print("\nBETWEEN-FINGER STRENGTH, absolute newtons")
    strength = (force.groupby("finger")["peak_force_N"]
                     .agg(n="count", mean="mean", sd="std", max="max")
                     .reindex(order).round(2))
    _show(strength)
    print("Pad differences are NOT corrected here. Each pad reads a")
    print("different number of counts for the same real force, so part of")
    print("any difference down this column is where the sensor sits, not")
    print("the finger. It is still the right column for the question,")
    print("because the calibrated ratio has the strength divided out of")
    print("it. Treat a ranking from this table as provisional and say so")
    print("in the write-up.")

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
        # The newton column is the datasheet constant applied to raw
        # counts, so it carries the whole per-pad bias the calibrated
        # column exists to remove. An over-reading pad reads as a finger
        # stronger than any healthy participant Demouche measured.
        print("   The newton figures are the datasheet constant applied to")
        print("   raw counts. They are NOT corrected for where each pad")
        print("   sits, so this comparison inherits the same per-sensor")
        print("   skew as the raw counts and cannot rank one finger")
        print("   against another.")
        if corrected:
            worst = None
            for finger in order:
                g = calset_gap_summary(force, finger)
                if g is not None and (worst is None or g > worst[1]):
                    worst = (finger, g)
            if worst and worst[1] >= 2.0:
                print(f"   Here the {worst[0]} pad reads {worst[1]:.1f}x the "
                      f"counts of the")
                print("   least sensitive pad for the same share of a")
                print("   reference press, so a newton difference of that")
                print("   size between fingers could be the pads alone.")
    return force


def calset_gap_summary(force, finger):
    """How many raw counts this finger logged per unit of its own
    calibration press, relative to the least sensitive finger present.

    Used only to say out loud how far apart the pads sit in the selection
    being reported, so the newton caveat carries a number rather than a
    warning nobody sizes.
    """
    sub = force[force["finger"] == finger]
    if sub.empty:
        return None
    ratios = []
    for f in force["finger"].dropna().unique():
        other = force[force["finger"] == f]
        raw = other["peak_force_n"].mean()
        cal = other["peak_force_cal"].mean()
        if pd.notna(raw) and pd.notna(cal) and cal:
            ratios.append(raw / cal)
    mine = sub["peak_force_n"].mean() / sub["peak_force_cal"].mean() \
        if sub["peak_force_cal"].notna().any() \
        and sub["peak_force_cal"].mean() else None
    if not ratios or mine is None or not min(ratios):
        return None
    return mine / min(ratios)


def individuation_summary(ind) -> dict:
    """The individuation figures every caller should quote, on both
    bases and over a matched set of trials.

    Two things go wrong without this. First, the corrected index is not
    on the same basis as the published enslavement figures, so quoting it
    next to them compares two different measurements. Second, the
    corrected subset is not a random sample of trials: it drops trials
    where a lane had no usable gap, and a lane with a tiny gap is a lane
    on a pad that reads little, which is where spill hides. Comparing
    the corrected mean over its own subset against the raw mean over
    every trial therefore moves the number for reasons that are nothing
    to do with the calibration.
    """
    out = {"n_all": 0, "n_matched": 0, "raw_all": np.nan,
           "raw_matched": np.nan, "cal_matched": np.nan,
           "n_dropped": 0, "why": {}}
    if ind is None or ind.empty:
        return out
    matched = ind[ind["comparable"] == True]
    out["n_all"] = int(len(ind))
    out["n_matched"] = int(len(matched))
    out["n_dropped"] = int(len(ind) - len(matched))
    out["raw_all"] = round(float(ind["individuation"].mean()), 3)
    if not matched.empty:
        out["raw_matched"] = round(float(matched["individuation"].mean()), 3)
        out["cal_matched"] = round(
            float(matched["individuation_cal"].mean()), 3)
    dropped = ind[ind["comparable"] != True]
    if not dropped.empty:
        out["why"] = dropped["why_not"].value_counts().to_dict()
    return out


def sec_individuation(trials, calset=None):
    """Finger isolation, on both bases, with the limits of each stated.

    The index is target force over total force.

    On absolute readings it is the same basis as the enslavement figures
    in the literature, so it is the one that can be quoted against them.
    It is biased by the pads: an over-reading pad inflates the
    denominator on every trial and drags the index down for every other
    finger.

    Dividing each lane by its own reference press removes the pad, but
    it weights each finger's spill by the inverse of that finger's own
    press strength. A weak finger with a small reference then contributes
    more spill per newton than a strong one, which changes the ranking
    between fingers and moves the number away from the published
    figures. That version answers "how did the force spread relative to
    what each finger can produce", and it is not comparable with 13 and
    25.1 percent.
    """
    ind = individuation(trials, calset)
    print("\n" + "=" * 62)
    print("FINGER INDIVIDUATION")
    print("=" * 62)
    if ind.empty:
        _nothing("No individuation data. This needs the force sensors and a",
                 "force_window_peaks column with more than one lane reading,",
                 "so it is empty for keyboard blocks.")
        return ind
    s = individuation_summary(ind)
    corrected = bool(ind["corrected"].any())

    print(f"{s['n_all']} trials with usable force spread")
    print("\nABSOLUTE BASIS (target force over total force, as recorded)")
    print(f"   mean index over all {s['n_all']} trials : {s['raw_all']:.3f}")
    spill = 1 - s["raw_all"]
    print(f"   enslavement, force on the other fingers: {spill:.3f}")
    print(f"   published: unimpaired {ENSLAVEMENT_REF['unimpaired']}, "
          f"stroke {ENSLAVEMENT_REF['stroke']} (Li via Lew)")
    print("   Those published figures are computed on ABSOLUTE force, so")
    print("   this is the line to put next to them. It carries the")
    print("   per-pad sensitivity bias: an over-reading pad inflates the")
    print("   total and pushes the index down.")

    if corrected:
        print(f"\nOWN-REFERENCE BASIS (each lane divided by its own "
              f"reference press)")
        print(f"   matched trials                : {s['n_matched']} of "
              f"{s['n_all']}")
        print(f"   absolute basis, same trials   : {s['raw_matched']:.3f}")
        print(f"   own-reference basis           : {s['cal_matched']:.3f}")
        print("   Both lines cover the SAME trials, so the difference")
        print("   between them is the correction and nothing else.")
        print("   This basis is NOT comparable with the published")
        print("   enslavement figures. It weights each finger's spill by")
        print("   the inverse of that finger's own press strength, so a")
        print("   weak finger's spill counts for more, and the ranking")
        print("   between fingers is not the ranking on absolute force.")
        if s["n_dropped"]:
            print(f"\n   {s['n_dropped']} trial(s) could not be corrected:")
            for why, n in s["why"].items():
                print(f"      {n}x  {why or 'unknown'}")
            print("   Those trials are excluded from BOTH matched lines, not")
            print("   just the corrected one. Dropping them from the")
            print("   corrected figure alone would raise it, because a lane")
            print("   with no usable gap is a lane on a pad that barely")
            print("   moves, which is where spill hides.")
    else:
        # Two different situations end up here and they need different
        # answers. Either nothing was calibrated, or a calibration was
        # measured and every trial still touched a lane whose gap is
        # unusable. Calling the second one "no calibration" hides the
        # only thing the user can act on, which is that one named pad is
        # the problem and recalibrating it brings the whole basis back.
        why = {w: n for w, n in (s["why"] or {}).items() if w}
        no_cal = all("no calibration" in w for w in why) if why else True
        if no_cal:
            print("\nNo usable calibration for these games, so there is no")
            print("own-reference version. Differences between fingers")
            print("above are a mix of the hand and the hardware.")
        else:
            print("\nA calibration was recorded, but NOT ONE trial could be")
            print("fully corrected, so there is no own-reference version:")
            for w, n in why.items():
                print(f"      {n}x  {w}")
            print("   Every trial touched a lane with no usable gap, so")
            print("   correcting any of them would mix normalised lanes")
            print("   with dropped ones. Recalibrate the pad named above")
            print("   and this basis comes back. Differences between")
            print("   fingers are a mix of the hand and the hardware")
            print("   until then.")

    col = "individuation_cal" if corrected else "individuation"
    shown = ind[ind["comparable"] == True] if corrected else ind
    order = _order(shown)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    label = ("individuation, own-reference basis" if corrected
             else "individuation, absolute basis (not corrected)")
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

    cols = ["individuation_cal", "individuation"] if corrected \
        else ["individuation"]
    _show(shown.groupby("finger")[cols]
               .agg(["count", "mean", "std"]).reindex(order).round(3))
    print("individuation      absolute basis. Comparable with the")
    print("                   published enslavement figures.")
    if corrected:
        print("individuation_cal  own-reference basis. NOT comparable with")
        print("                   them, and its per-finger ranking is not")
        print("                   the ranking on absolute force.")
    ind.attrs["summary"] = s
    return ind


def sec_rhythm(trials):
    rhy = rhythm_rows(trials)
    if rhy.empty:
        print("No rhythm blocks in this selection, so there is no\n"
              "timing offset to report. This section only applies to\n"
              "games played in rhythm mode.")
        return rhy
    print("\n" + "=" * 62)
    print("RHYTHM")
    print("=" * 62)
    off = rhy["time_difference_ms"]
    print("These are SIGNED offsets from the beat, not reaction times. The")
    print("note is known in advance, so early is normal and the sign")
    print("matters. They are kept out of every reaction-time figure.")
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

    Two ways this used to print a wrong number.

    The reaction-time line pooled every trial with a time_difference_ms,
    including rhythm beat offsets and misses. On the shipped data that
    gave "left -95 | right 158 -> asymmetry -8.027", where the -95 ms is
    a rhythm block's mean offset from the beat. Only cued-mode reaction
    times go in now.

    The one-hand caveat was suppressed whenever the SELECTION held both a
    left-calibrated and a right-calibrated game, which is exactly the
    case where each individual game still only covers one hand. The check
    is per game now.
    """
    trials = ensure_force_columns(trials, calset)
    print("\n" + "=" * 62)
    print("BOTH HANDS")
    print("=" * 62)
    if trials.empty:
        _nothing("No trials are loaded, so there is no left against right",
                 "to show.")
        return None
    bil = trials[trials["hand_mode"] == "both"] if "hand_mode" in trials \
        else trials.iloc[0:0]
    if bil.empty:
        modes = sorted({str(h) for h in trials.get("hand_mode", [])
                        if str(h)})
        _nothing("Nothing to show: this section needs a block played with "
                 "both",
                 f"hands, and this selection is {', '.join(modes) or 'one'}"
                 f"-handed.",
                 "Play a bilateral or mirror block, or pick one from the",
                 "dropdown, to get a left against right comparison.")
        return None
    L, R = bil[bil["side"] == "left"], bil[bil["side"] == "right"]

    def asym(l, r):
        if pd.isna(l) or pd.isna(r) or (l + r) == 0:
            return float("nan")
        return (l - r) / ((l + r) / 2)

    # Reaction times only: cued modes, misses out. A rhythm block's
    # signed beat offset in this line is what produced the -8.027.
    lrt, rrt = reaction_times(L), reaction_times(R)
    n_other = len(bil) - len(reaction_times(bil))
    if len(lrt) and len(rrt):
        lr, rr = lrt.mean(), rrt.mean()
        print(f"reaction time  left {lr:.0f} | right {rr:.0f} ms  "
              f"-> asymmetry {asym(lr, rr):+.3f}")
        print(f"   from {len(lrt)} left and {len(rrt)} right cued trials "
              f"with a press")
    else:
        print("reaction time  not available: this selection has no cued")
        print("   trials with a press on both hands. Rhythm beat offsets")
        print("   and missed trials are excluded on purpose, because an")
        print("   offset from a known beat is not a reaction time.")
    if n_other:
        print(f"   {n_other} of {len(bil)} bilateral trials are rhythm "
              f"offsets or")
        print("   misses and are left out of the line above.")

    corrected = bool(bil["force_calibrated"].any())
    lf, rf = L["peak_force_n"].mean(), R["peak_force_n"].mean()
    if pd.notna(lf) and pd.notna(rf):
        print(f"peak force     left {lf:.0f} | right {rf:.0f} {unit}  "
              f"-> asymmetry {asym(lf, rf):+.3f}   NOT comparable")
    if corrected:
        lc, rc = L["peak_force_cal"].mean(), R["peak_force_cal"].mean()
        # Per game, not per selection. A left-calibrated game and a
        # right-calibrated game in one selection do not add up to a game
        # with both hands calibrated.
        gaps_missing = {}
        for game, sub in bil.groupby("game"):
            needed = {s for s in sub["side"].dropna().unique()}
            miss = (calset.missing_hands(game, needed) if calset
                    else sorted(needed))
            if miss:
                gaps_missing[game] = miss
        both_hands_ok = not gaps_missing
        if pd.notna(lc) and pd.notna(rc):
            print(f"own reference  left {lc:.2f} | right {rc:.2f} "
                  f"{NORM_UNIT}  -> asymmetry {asym(lc, rc):+.3f}")
            print_norm_short()
            if both_hands_ok:
                print("   Both hands of every game here were calibrated")
                print("   separately, so this asymmetry is not carrying one")
                print("   hand's pads. It still compares effort against each")
                print("   hand's own reference, so a hand that was weak at")
                print("   calibration is weak in the reference too.")
            else:
                print("   Do NOT report this as a patient asymmetry.")
        if gaps_missing:
            print("   CAVEAT: these games have trials on a hand with no")
            print("   usable calibration, so those rows are left")
            print("   uncorrected rather than normalised with the other")
            print("   hand's pads:")
            for game, miss in gaps_missing.items():
                print(f"      {game}: no profile for the "
                      f"{', '.join(miss)} hand")
            wanted = sorted({h for miss in gaps_missing.values()
                             for h in miss})
            on_disk = hand_profiles_on_disk()
            for hand in wanted:
                if hand in on_disk:
                    print(f"   config/calibration/current_{hand}.json "
                          f"exists, taken {on_disk[hand]['created_at']},")
                    print("      but it is not what these blocks ran under "
                          "so it is not applied.")
                else:
                    print(f"   config/calibration/current_{hand}.json does "
                          f"not exist.")
            print("   Run Calibrate once per hand before the next session.")
    elif pd.notna(lf) and pd.notna(rf):
        print("   no calibration, so the force asymmetry above is a mix of")
        print("   the two hands and the eight pads and should not be")
        print("   reported as a patient asymmetry.")
    order = _order(bil)
    rt_rows = reaction_times(bil, per="rows")
    fig, ax = plt.subplots(figsize=(8, 3.4))
    x = np.arange(len(order)); w = .38
    for i, side in enumerate(("right", "left")):
        ax.bar(x + (i - .5) * w,
               [rt_rows[(rt_rows["side"] == side) & (rt_rows["finger"] == f)]
                ["time_difference_ms"].mean() if not rt_rows.empty else np.nan
                for f in order],
               w, label=side, color=HAND_COLOUR[side])
    ax.set_xticks(x); ax.set_xticklabels(order)
    ax.set_ylabel("mean reaction time (ms)")
    ax.set_title("Reaction time, both hands (cued trials only)")
    ax.legend(frameon=False)
    _save(fig, "bilateral"); plt.show()
    return {"n_left": int(len(L)), "n_right": int(len(R)),
            "rt_left": round(float(lrt.mean()), 1) if len(lrt) else np.nan,
            "rt_right": round(float(rrt.mean()), 1) if len(rrt) else np.nan}


def sec_raw(folders, unit="sensor counts", calset=None):
    """A look at the sample stream behind one game.

    The average press shape at the end puts all four fingers on one axis,
    so it is a cross-finger force comparison and gets the same
    correction as the rest.
    """
    print("\n" + "=" * 62)
    print("RAW STREAM")
    print("=" * 62)
    raw, game, folder = None, None, None
    for f in folders:
        candidate = load_raw(f)
        if candidate is not None and len(candidate) > 50:
            raw, game, folder = candidate, game_key(f), Path(f)
            break
    if raw is None:
        # Silence here read as a section that crashed. Say which games
        # were looked at and why none of them had a stream.
        missing = [game_key(f) for f in folders
                   if not (Path(f) / "raw.csv").exists()]
        _nothing(f"None of the {len(folders)} selected game(s) carry a "
                 f"usable raw.csv,",
                 "so there is no sample stream, no press duration and no",
                 "press shape to show here.")
        if missing:
            print(f"no raw.csv at all: {', '.join(missing)}")
        thin = [game_key(f) for f in folders
                if (Path(f) / "raw.csv").exists()
                and game_key(f) not in missing]
        if thin:
            print(f"raw.csv present but under 50 rows: {', '.join(thin)}")
        print("The 200 Hz stream is only written when the force sensors are")
        print("streaming, so keyboard blocks and very short blocks have none.")
        return None
    hand_mode = read_meta(folder).get("hand", "right") if folder else "right"
    samples = raw[raw["event"].isna() | (raw["event"] == "")]
    events = raw[raw["event"].notna() & (raw["event"] != "")]
    if len(samples) > 1:
        dur = samples["t_perf"].max() - samples["t_perf"].min()
        print(f"{len(samples)} samples over {dur:.1f} s "
              f"({len(samples)/max(dur,1e-9):.0f} Hz), {len(events)} events")
    else:
        # A raw.csv holding only event rows still passes the length check
        # above, so without this the section prints its heading and
        # nothing else and reads as a section that failed.
        print(f"{game} logged {len(events)} events but no sensor samples,")
        print("so there is no press shape or press duration to show here.")
        print("The sample stream is only written when the force sensors")
        print("are streaming, so this is empty for keyboard sessions.")
        return None
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
            # Lanes 0 to 3, so the right hand in a bilateral block and
            # whichever hand was played in a one-handed one.
            gaps = ([calset.lane_gap(game, i, hand_mode) for i in range(4)]
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
                print("reference press, so the pads are out of the four")
                print("heights.")
                print_norm_short("")
                print("A taller trace here means more effort against that")
                print("finger's own reference, not a stronger finger.")
            else:
                print("Press shapes are in raw counts. The four traces sit")
                print("on four differently sensitive pads, so their heights")
                print("cannot be compared with each other. Shape and timing")
                print("still can.")
    return raw


# ---------------------------------------------------------------- entry

def prepare(pick="latest", root=None) -> dict:
    """Everything the sections need, built once.

    Returns a dict with cat, sel, folders, metas, sessions, trials, unit
    and calset. A notebook cell can unpack it and then call any sec_
    function on its own, in any order, with no hidden state between
    cells. `trials` already carries the calibrated and newton force
    columns.

    The selection is stamped into the context. Every later cell checks
    that stamp against the dropdown before using anything, so changing
    the pick and re-running only some cells cannot blend two selections
    into one headline table. See check_selection.
    """
    cat = build_catalogue(root)
    if cat.empty:
        ctx = {"cat": cat, "sel": cat, "folders": [], "metas": {},
               "sessions": {}, "trials": pd.DataFrame(),
               "unit": "sensor counts", "calset": CalibrationSet(),
               "root": root, "pick": pick}
        ctx["selection"] = selection_key(pick, cat)
        ctx["results"] = {}
        return ctx
    sel = resolve(pick, cat)
    folders = [Path(p) for p in sel["folder"]]
    metas = load_metas(folders)
    sessions = {game_key(p): s
                for p, s in zip(sel["folder"], sel["session"])}
    trials = load_games(folders, cat)
    unit = force_unit(metas)
    calset = calibration_factors(metas, unit)
    trials = add_force_columns(trials, calset)
    return {"cat": cat, "sel": sel, "folders": folders, "metas": metas,
            "sessions": sessions, "trials": trials, "unit": unit,
            "calset": calset, "root": root, "pick": pick,
            "selection": selection_key(pick, sel), "results": {}}


# ------------------------------------------------- stale-selection guard
# The notebook keeps its selection in a global that the dropdown writes
# to. Change the dropdown, re-run some cells and not others, and the
# headline table ends up built from `trials` for one save and `rt` or
# `force` for another. Nothing warns, the numbers look plausible, and
# they belong to no single session.
#
# So prepare() stamps what it loaded into the context, every cell checks
# that stamp against the dropdown before touching anything, and results
# are filed under the stamp they were computed on. A stale run raises
# instead of printing a mixed answer.


class StaleSelection(RuntimeError):
    """The cell was run against a selection the context was not built
    from. Raised rather than warned: a warning scrolls past and the
    wrong number still gets written to the CSV."""


def selection_key(pick, sel) -> str:
    """Short text naming exactly what was loaded.

    Built from the resolved folders rather than from `pick` alone,
    because two different picks can name the same games and the same
    pick can name different games after a rescan.
    """
    if sel is None or getattr(sel, "empty", True):
        return f"{pick!r} -> nothing"
    folders = sorted(str(f) for f in sel["folder"])
    return f"{pick!r} -> {len(folders)} game(s): " + "; ".join(folders)


def describe_pick(pick, cat) -> str:
    """What `pick` would load right now, for the error message."""
    try:
        return selection_key(pick, resolve(pick, cat))
    except (KeyError, TypeError) as e:
        return f"{pick!r} -> cannot be resolved ({e})"


def check_selection(ctx, pick):
    """Stop the cell unless ctx was built from the current dropdown value.

    Call this at the top of every cell that reads anything prepare()
    built. It costs a catalogue lookup and it is the only thing standing
    between a changed dropdown and a headline table made of two
    different sessions.
    """
    if not isinstance(ctx, dict) or "selection" not in ctx:
        raise StaleSelection(
            "the context has not been built yet. Run the 'Load the "
            "selection' cell, then the cells above this one, before "
            "running this cell.")
    now = describe_pick(pick, ctx.get("cat"))
    if now != ctx["selection"]:
        raise StaleSelection(
            "this cell is about to mix two selections.\n"
            f"   loaded : {ctx['selection']}\n"
            f"   dropdown now : {now}\n"
            "   Re-run the cells above, starting at 'Load the selection', "
            "then run this one again.")
    return True


def keep(ctx, name, value):
    """File a section's result under the selection it was computed on."""
    ctx.setdefault("results", {})[name] = (ctx.get("selection"), value)
    return value


def need(ctx, *names):
    """The stored results, or a clear refusal.

    The summary cell reads what the section cells produced. Without this,
    running the summary after re-running prepare() but not the sections
    quietly reuses the previous selection's tables.
    """
    out, missing, stale = {}, [], []
    stored = ctx.get("results", {})
    for name in names:
        if name not in stored:
            missing.append(name)
            continue
        key, value = stored[name]
        if key != ctx.get("selection"):
            stale.append(name)
            continue
        out[name] = value
    if missing or stale:
        lines = ["the sections this cell needs have not been run for the "
                 "current selection."]
        if missing:
            lines.append(f"   never run here : {', '.join(missing)}")
        if stale:
            lines.append(f"   run on an older selection : {', '.join(stale)}")
        lines.append("   Run every cell from 'Load the selection' down to "
                     "this one, in order.")
        raise StaleSelection("\n".join(lines))
    return out


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

    sec_calibration(metas, sessions, calset)
    on_task = sec_overview(trials, folders, metas)
    sec_quality(trials, folders, metas)
    comp = sec_compare(trials)
    rt = sec_reaction_time(trials)
    acc = sec_accuracy(trials)
    force = sec_force(trials, unit, calset)
    ind = sec_individuation(trials, calset)
    rhy = sec_rhythm(trials)
    sec_bilateral(trials, unit, calset)
    sec_raw(folders, unit, calset)
    ons = sec_onset(folders, trials, unit, calset)

    # Analyses that came out of reading the past Curtin theses.
    sec_objective_one(trials, calset=calset)
    flagged = sec_exclusions(trials)
    sec_phase(trials)
    sec_threshold_audit(metas=metas, calset=calset)
    sec_cue_modality(trials, calset)
    sec_dose(trials, on_task / 60 if on_task else 0)
    sec_sampling_note(folders)
    sec_participant_progress(root, cat)

    summary = sec_summary(trials, unit, calset, on_task,
                          folders=folders, onset=ons, accuracy=acc)

    if export:
        write_exports(summary, trials, calset)

    return {"trials": trials, "rt": rt, "force": force, "individuation": ind,
            "rhythm": rhy, "comparison": comp, "summary": summary,
            "onset": ons, "accuracy": acc, "flagged": flagged,
            "catalogue": cat, "selected": sel}


def build_summary(trials, unit="sensor counts", calset=None, on_task=0.0,
                  folders=None, onset=None, accuracy=None) -> dict:
    """The headline numbers, built once so the notebook and report()
    cannot drift apart.

    Built from the trials that CAN be analysed. A trial whose cue command
    never reached the device was never presented, and a press under
    100 ms is anticipation rather than a response. The old summary
    counted both, so on the shipped default it published a hit rate and a
    mean reaction time computed from 48 trials the exclusions section
    said could not be analysed. Every count that went into the figures is
    in the table, so the basis is visible rather than assumed.
    """
    kept, flagged, counts = analysable(trials)
    calset = calset if calset is not None else CalibrationSet()
    s = {
        "games": len(folders) if folders is not None else np.nan,
        "summary_basis": "analysable trials only",
        "trials_recorded": counts["recorded"],
        "trials_no_cue": counts["no_cue"],
        "trials_anticipation": counts["anticipation"],
        "trials_analysed": counts["analysed"],
        "time_on_task_min": round(on_task / 60, 1) if on_task else 0.0,
        "calibration": calset.status,
    }
    if counts["analysed"] == 0:
        s["warning"] = ("no analysable trials, every figure below is blank "
                        "on purpose")
        return s

    rts = rt_stats(kept)
    s["rt_trials"] = rts["n"]
    s["rt_mean_ms"] = rts["mean_rt"]
    s["rt_cv"] = rts["rt_cv"]
    s["rt_basis"] = "cued modes, misses and rhythm beat offsets excluded"

    cued = kept[is_cued(kept)]
    if not cued.empty:
        s["hit_rate_all_cued"] = round(
            float((cued["early_late"] != "Miss").mean()), 3)
        s["hit_rate_scope"] = "classic, adaptive and mirror blocks"
    if accuracy:
        # The accuracy section narrows to adaptive blocks when it can.
        # Both scopes go in the table, named, rather than one number that
        # disagrees with the printed one.
        s["hit_rate_section_scope"] = accuracy.get("scope")
        s["hit_rate_section"] = accuracy.get("hit_rate_scoped")
        s["hit_rate_section_basis"] = "all recorded trials, as printed above"

    force = ensure_force_columns(kept, calset)
    force = force[force["peak_force_n"].notna()]
    if not force.empty:
        s["force_unit"] = unit
        s["peak_force_mean_raw"] = round(
            float(force["peak_force_n"].mean()), 1)
        s["peak_force_mean_N"] = round(float(force["peak_force_N"].mean()), 2)
        s["peak_force_N_meaning"] = ("absolute, pad sensitivity NOT "
                                     "corrected, use for strength")
        if force["peak_force_cal"].notna().any():
            s["peak_force_mean_cal"] = round(
                float(force["peak_force_cal"].mean()), 3)
            s["peak_force_cal_meaning"] = NORM_SHORT

    ind = individuation(kept, calset)
    isum = individuation_summary(ind)
    if isum["n_all"]:
        s["individuation_absolute"] = isum["raw_all"]
        s["individuation_absolute_n"] = isum["n_all"]
        s["individuation_absolute_meaning"] = (
            "target over total on absolute force, the basis the published "
            "enslavement figures use")
        if isum["n_matched"]:
            s["individuation_own_reference"] = isum["cal_matched"]
            s["individuation_absolute_matched"] = isum["raw_matched"]
            s["individuation_matched_n"] = isum["n_matched"]
            s["individuation_own_reference_meaning"] = (
                "each lane over its own reference press, NOT comparable "
                "with the published enslavement figures")
            s["individuation_matched_note"] = (
                "the two matched figures cover the same trials, so the "
                "difference is the correction alone")

    rhy = rhythm_rows(kept)
    if not rhy.empty:
        s["beat_accuracy_ms"] = round(
            float(rhy["time_difference_ms"].abs().mean()), 1)
        s["beat_bias_ms"] = round(float(rhy["time_difference_ms"].mean()), 1)
        s["beat_note"] = "signed offset from the beat, not a reaction time"

    if onset is not None and not onset.empty:
        v = onset["onset_rt_ms"]
        s["onset_rt_mean_ms"] = round(float(v.mean()), 1)
        s["onset_rt_cv"] = (round(float(v.std() / v.mean()), 3)
                            if len(v) > 1 and v.mean() > 0 else np.nan)
        s["onset_rfd_mean_raw"] = round(float(onset["peak_dforce"].mean()), 1)
        if onset["peak_dforce_cal"].notna().any():
            s["onset_rfd_mean_cal"] = round(
                float(onset["peak_dforce_cal"].mean()), 3)
        s["onset_basis"] = ("raw sample stream, trial exclusions do not "
                            "apply to it")
    return s


def sec_summary(trials, unit="sensor counts", calset=None, on_task=0.0,
                folders=None, onset=None, accuracy=None) -> dict:
    """Print the headline numbers and say plainly what they were built
    from."""
    s = build_summary(trials, unit, calset, on_task, folders, onset, accuracy)
    print("\n" + "=" * 62)
    print("SUMMARY")
    print("=" * 62)
    excluded = s["trials_no_cue"] + s["trials_anticipation"]
    if excluded:
        print(f"BUILT FROM {s['trials_analysed']} OF "
              f"{s['trials_recorded']} RECORDED TRIALS.")
        print(f"   {s['trials_no_cue']} had no cue delivered, so nothing was "
              f"presented.")
        print(f"   {s['trials_anticipation']} were faster than "
              f"{ANTICIPATION_MS:.0f} ms, so they are anticipation.")
        print("   Those are excluded here. Sections above print over every")
        print("   recorded trial unless they say otherwise, so a figure")
        print("   there can differ from the one below.")
        if s["trials_analysed"] == 0:
            print("   NOTHING IS ANALYSABLE IN THIS SELECTION. There is no")
            print("   hit rate and no reaction time to report from it.")
        print()
    else:
        print(f"Built from all {s['trials_recorded']} recorded trials: none "
              f"were flagged.\n")
    _show(pd.DataFrame([s]).T.rename(columns={0: "value"}))
    return s


IND_EXPORT = "individuation_per_trial.csv"


def write_exports(summary, trials, calset=None, ind=None):
    """Write the CSVs, with the exclusion flags on every trial row.

    selected_trials.csv keeps every recorded trial so nothing disappears,
    but each row now carries whether it could be analysed and why not, so
    anyone recomputing from the CSV lands on the same figures as the
    summary rather than on the ones that include flagged trials.

    Only the files actually written this run are described. A selection
    with no individuation leaves any earlier individuation_per_trial.csv
    untouched, and that stale file gets called out rather than listed as
    though it went with the summary.
    """
    pd.DataFrame([summary]).T.rename(columns={0: "value"}).to_csv(
        "session_summary.csv")
    flags = exclusion_flags(trials)
    flags.to_csv("selected_trials.csv", index=False)
    written = ["session_summary.csv", "selected_trials.csv"]
    if ind is None:
        ind = individuation(trials, calset)
    if ind is not None and not ind.empty:
        # Carry the same flag onto the per-trial individuation rows, so
        # the file the summary was built from can be reconstructed from
        # either CSV without guessing which trials went in.
        out = ind.copy()
        if not flags.empty and "row_id" in out.columns:
            excluded = flags["excluded"]
            out["excluded"] = [bool(excluded.get(i, False))
                               for i in out["row_id"]]
        out.to_csv(IND_EXPORT, index=False)
        written.append(IND_EXPORT)
    print("\nwritten: " + ", ".join(written))
    if IND_EXPORT in written:
        print(f"selected_trials.csv and {IND_EXPORT} both carry an")
        print("excluded column, and selected_trials.csv also carries")
        print("exclusion_reason.")
    else:
        print("selected_trials.csv carries an excluded column and an")
        print("exclusion_reason column.")
    print("The summary is built from the rows where excluded is False, so")
    print("filter on it to reproduce the headline numbers.")
    # A selection with no individuation writes no individuation file, but
    # one from an earlier run is still sitting next to the notebook under
    # the same name. Saying nothing points the reader at a file of
    # another session's trials as though it matched the summary above it,
    # and an older one does not even carry the excluded column.
    if IND_EXPORT not in written and Path(IND_EXPORT).exists():
        print(f"\nWARNING: {IND_EXPORT} on disk is left over from an")
        print("earlier run. This selection has no individuation data, so")
        print("that file was NOT rewritten and its rows belong to a")
        print("different selection. Delete it, or re-run the export on the")
        print("selection it came from, before reading anything off it.")
    print("figures are in figures/ ready for the report")
    return written


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
        chosen = dd.value
        dd.unobserve(_changed, names="value")
        dd.options = menu_options(fresh)
        dd.value = chosen if chosen in [v for _, v in dd.options] else None
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
        hand_mode = read_meta(Path(folder)).get("hand", "right")
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
            game = game_key(folder)
            # Lanes 4 to 7 are the left hand, so they need the left
            # hand's profile. Dividing them by the right hand's gaps
            # produced a corrected-looking number off the wrong pads.
            side = lane_side(lane, hand_mode)
            gap = (calset.lane_gap(game, lane, hand_mode)
                   if calset is not None else None)
            rows.append({"game": game,
                         "finger": FINGERS[lane % 4], "lane": lane,
                         "hand": side,
                         "onset_rt_ms": rt, "peak_dforce": vmax,
                         "peak_dforce_cal": vmax / gap if gap else np.nan})
    return pd.DataFrame(
        rows, columns=["game", "finger", "lane", "hand", "onset_rt_ms",
                       "peak_dforce", "peak_dforce_cal"])


def sec_onset(folders, trials, unit="sensor counts", calset=None):
    """Onset-based reaction time and rate of force development, and how
    they compare with the threshold-crossing figure the game records."""
    ons = onset_table(folders, unit, calset=calset)
    if ons.empty:
        print("No movement onset could be measured. This needs the raw\n"
              "sample stream (raw.csv) with force rising after a cue, so\n"
              "it is empty for keyboard sessions and for blocks where no\n"
              "press crossed the detection floor.")
        return ons
    corrected = bool(ons["peak_dforce_cal"].notna().any())
    print("\n" + "=" * 62)
    print("MOVEMENT ONSET AND RATE OF FORCE DEVELOPMENT")
    print("=" * 62)
    v = ons["onset_rt_ms"]
    print(f"\nonset reaction time : n {len(v)}   mean {v.mean():.1f} ms   "
          f"median {v.median():.1f} ms   sd {v.std():.1f} ms")
    cv = v.std() / v.mean() if len(v) > 1 and v.mean() > 0 else np.nan
    if pd.notna(cv):
        print(f"response stability  : CV {cv:.3f}  "
              f"(sd over mean, lower is steadier)")
    else:
        print("response stability  : CV not computable from this sample")
    d = ons["peak_dforce"]
    print(f"rate of force dev.  : mean {d.mean():.0f} {unit} per second "
          f"(raw, not comparable between fingers)")
    if corrected:
        print(f"rate, own reference : mean "
              f"{ons['peak_dforce_cal'].mean():.2f} {NORM_UNIT} per second")
        print_norm_short()
    else:
        print("no calibration available, so the per-finger rates below are")
        print("not corrected for the pads and should not be ranked.")

    # Threshold-crossing RT from the game, for comparison. Cued modes
    # only: a rhythm beat offset is not a reaction time and would drag
    # the comparison below in either direction.
    thr = reaction_times(trials)

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
        # One entry per hand: the two hands have their own pads and
        # their own thresholds, and averaging or overwriting one with
        # the other prints a trigger no finger ever ran under.
        cals = read_calibrations(meta)
        found = False
        for hand, cal in sorted(cals.items()):
            on = cal.get("on_delta")
            if not on:
                continue
            found = True
            source = f"calibration, {hand} hand"
            stamp = cal.get("created_at") or "unknown"
            key = (source, stamp, tuple(on))
            out.setdefault(key, {"source": source, "stamp": stamp,
                                 "on_delta": list(on), "hand": hand,
                                 "games": []})["games"].append(name)
        if found:
            continue
        snap = ((meta.get("config_snapshot") or {}).get("fsr") or {})
        on = snap.get("on_delta")
        source, stamp = "config snapshot", "no calibration"
        if not on:
            source, stamp, on = "unrecorded", "unknown", None
        key = (source, stamp, tuple(on) if on else None)
        out.setdefault(key, {"source": source, "stamp": stamp,
                             "on_delta": list(on) if on else None,
                             "hand": "?", "games": []})["games"].append(name)
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
                 "on_delta": list(cfg_on_delta), "hand": "?", "games": []}]
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
                     "stamp": "as the config reads today", "hand": "?",
                     "games": []}]
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


def sec_calibration(metas, sessions=None, calset=None):
    """What a press meant on the day, taken from the calibration each
    game recorded rather than from whatever the config says now.

    One block per distinct calibration per hand. Nothing is collapsed: a
    selection can span several, and printing the first one as though it
    covered the lot reports the OLDEST calibration and asserts the newer
    games ran under it. A left profile does not stand in for the right
    hand either, because they are eight different pads.

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

    cs = calset if calset is not None else calibration_factors(metas)
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

    # A hand that was played but never calibrated. This is the case the
    # per-hand split exists for: the bilateral force numbers used to be
    # normalised entirely with whichever hand happened to be measured.
    gaps_missing = {g: cs.missing_hands(g, cs.played.get(g, set()))
                    for g in cs.per_game if cs.per_game[g]}
    gaps_missing = {g: m for g, m in gaps_missing.items() if m}
    if gaps_missing:
        print("HANDS PLAYED WITH NO USABLE CALIBRATION:")
        for game, miss in gaps_missing.items():
            print(f"   {game}: no profile for the {', '.join(miss)} hand")
        print("Those lanes are left uncorrected. They are NOT normalised")
        print("with the other hand's gaps, because the two hands sit on")
        print("eight different pads and borrowing four of them produces a")
        print("corrected-looking number off the wrong sensors.")
        on_disk = hand_profiles_on_disk()
        for hand in HANDS:
            if hand in on_disk:
                print(f"   config/calibration/current_{hand}.json exists, "
                      f"taken {on_disk[hand]['created_at']}. It is NOT")
                print("      applied here: it is whatever was measured last,")
                print("      not what these blocks ran under.")
            else:
                print(f"   config/calibration/current_{hand}.json does not "
                      f"exist.")
        print("Run Calibrate once per hand before the next bilateral "
              "session.\n")

    if cs.status == "multiple":
        print("WARNING: one or both hands were calibrated more than once")
        print("across these games. A press did not mean the same thing in")
        print("each, so a force change across them is not necessarily a")
        print("change in the patient. Normalising by each game's own")
        print("calibration makes the pads comparable within a finger, but a")
        print("like-for-like comparison over time still has to stay inside")
        print("one calibration.\n")

    tables = {}
    for stamp, pairs in cs.stamps.items():
        first_game, hand = pairs[0]
        games = [g for g, _ in pairs]
        cal = cs.per_game[first_game][hand]
        print("-" * 62)
        print(f"calibration taken {stamp} on "
              f"{cal.get('device_port') or 'an unrecorded port'}")
        if cal.get("hand_assumed"):
            print("   this profile carries no hand field, so it is taken as")
            print("   the right hand, which is what the app defaults to")
        label = f"{len(games)} game(s)"
        if sessions:
            label += (f" across "
                      f"{len({sessions.get(g, g) for g in games})} session(s)")
        print(f"used by {label}: {', '.join(games)}")
        problems = cs.problems[first_game][hand]
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
    print("What these gaps can and cannot be used for:")
    print(normalisation_note("   "))
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
    cued = trials[is_cued(trials)] if not trials.empty else trials
    n_cued = len(cued)
    if "stim_delivered" in cued.columns:
        cued = cued[cued["stim_delivered"] != False]
    if cued.empty:
        if n_cued:
            print(f"All {n_cued} cued trials in this selection recorded the")
            print("cue as never delivered, so there is no trial the")
            print("participant can be scored on. Objective 1 needs blocks")
            print("where the cue actually reached the device.")
        else:
            print("No cued-mode trials in this selection, so there is no")
            print("per-finger hit rate to check against the band. Objective")
            print("1 applies to classic, adaptive and mirror blocks.")
        return None
    # A partial window is not a window. The objective is worded as a hit
    # rate over a 32-trial block, so a finger with 8 trials has not been
    # measured against it yet, and printing an 8-trial rolling mean under
    # a "32-trial window" heading claims a measurement that was not made.
    min_n = max(5, window // 4)
    print("\n" + "=" * 62)
    print(f"OBJECTIVE 1: PER-FINGER HIT RATE, ROLLING WINDOW UP TO "
          f"{window} TRIALS")
    print("=" * 62)
    print(f"The objective is worded over a full {window}-trial block. A "
          f"finger needs")
    print(f"{window} trials of its own for one full window. Fingers with "
          f"fewer are")
    print(f"shown over a partial window of at least {min_n} trials, drawn "
          f"dashed,")
    print("and in_band_share is left blank for them rather than computed")
    print("from a window the objective does not describe.")
    order = [f for f in FINGERS if f in cued["finger"].unique()]
    fig, axes = plt.subplots(1, len(order), figsize=(3.4 * len(order), 3.2),
                             sharey=True)
    if len(order) == 1:
        axes = [axes]
    rows = []
    for ax, f in zip(axes, order):
        g = cued[cued["finger"] == f].sort_values("trial")
        hit = (g["early_late"] != "Miss").astype(float)
        roll = hit.rolling(window, min_periods=min_n).mean()
        full = hit.rolling(window).mean().dropna()
        n_full = int(len(full))
        inband = full.between(BAND_LO, BAND_HI)
        first = None
        for k, (idx, val) in enumerate(full.items()):
            if BAND_LO <= val <= BAND_HI:
                first = k
                break
        rows.append({"finger": f, "trials": len(g),
                     "hit_rate": round(hit.mean(), 3),
                     "full_windows": n_full,
                     "in_band_share": (round(inband.mean(), 3)
                                       if n_full else np.nan),
                     "windows_to_settle": first})
        ax.axhspan(BAND_LO, BAND_HI, color="#16a34a", alpha=.15)
        ax.axhline(WILSON, color="#ca8a04", ls=":", lw=1.5)
        drawn = roll.reset_index(drop=True)
        n_partial = max(0, min(len(drawn), window - 1))
        ax.plot(range(len(drawn)), drawn, lw=2, ls="--", alpha=.55,
                color=FINGER_COLOUR[f])
        if n_full:
            ax.plot(range(n_partial, len(drawn)), drawn.iloc[n_partial:],
                    lw=2, color=FINGER_COLOUR[f])
        if first is not None:
            ax.axvline(n_partial + first, color="#0f172a", ls="--", lw=1,
                       label="first full window in band")
            ax.legend(frameon=False, fontsize=7)
        title = f if n_full else f"{f} (no full window)"
        ax.set_ylim(0, 1.02); ax.set_title(title); ax.set_xlabel("trial")
    axes[0].set_ylabel(f"hit rate (rolling, up to {window})")
    fig.suptitle(f"Objective 1 per finger, band 65 to 80 percent, "
                 f"solid = full {window}-trial window",
                 fontsize=11, fontweight="bold", x=0.02, ha="left")
    _save(fig, "objective_one"); plt.show()
    tbl = pd.DataFrame(rows)
    short = tbl[tbl["full_windows"] == 0]["finger"].tolist()
    if short:
        print(f"\nNOT ENOUGH DATA for a full {window}-trial window on: "
              f"{', '.join(short)}.")
        print("Their hit_rate is over every trial they have, which is fewer")
        print(f"than the {window} the objective asks for, so it is not yet a")
        print("test of the objective.")

    # How hard each finger's own trigger was, as a share of the press
    # that finger produced at calibration. Comparable between fingers,
    # unlike the trigger in counts.
    if calset is not None and calset.usable:
        shares = []
        for f in tbl["finger"]:
            vals = []
            # Per hand, so a left-hand trigger is compared against the
            # left hand's own reference press and not the right's.
            for game, hand, cal in calset.all_cals:
                gap = calset.gap(game, f, hand)
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
        print("reference press the trigger sits. Fingers differ here only")
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
    print("\n" + "=" * 62)
    print("TRIAL EXCLUSIONS")
    print("=" * 62)
    if trials.empty:
        _nothing("No trials are loaded, so there is nothing to flag.")
        return None
    kept, df, counts = analysable(trials)
    print(f"recorded trials            : {counts['recorded']}")
    print(f"cue never delivered        : {counts['no_cue']}")
    print(f"faster than {ANTICIPATION_MS:.0f} ms         : "
          f"{counts['anticipation']}   (anticipation, not a reaction)")
    print(f"analysed                   : {counts['analysed']}")

    def headline(d):
        c = d[is_cued(d)]
        s = rt_stats(d)
        return {"hit_rate": round(float((c["early_late"] != "Miss").mean()), 3)
                             if len(c) else np.nan,
                "mean_rt": s["mean_rt"], "rt_cv": s["rt_cv"]}
    before, after = headline(df), headline(kept)
    cmp_tbl = pd.DataFrame([{"": "with everything", **before},
                            {"": "after exclusions", **after}])
    _show(cmp_tbl)
    print("The summary at the end of the notebook uses the second row.")
    print("Sections above print over every recorded trial unless they say")
    print("otherwise, so a figure there can differ from the summary.")
    if counts["analysed"] == 0:
        print("\nNOTHING IN THIS SELECTION CAN BE ANALYSED. Every trial is")
        print("flagged, so there is no hit rate and no reaction time to")
        print("report from it. Fix the cue path and record again.")
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
        print("No protocol phase recorded, so there is no pretest to\n"
              "aftertest change to show. Phase is only set when a block\n"
              "is run as part of a protocol.")
        return None
    ph = trials[trials["phase"].notna() & (trials["phase"] != "")]
    if ph.empty or ph["phase"].nunique() < 2:
        print("Only one protocol phase is present in this selection.\n"
              "A pretest to aftertest comparison needs at least two.")
        return None
    print("\n" + "=" * 62)
    print("PRETEST TO AFTERTEST")
    print("=" * 62)
    rows = []
    for (who, phase), g in ph.groupby(["participant", "phase"]):
        s = rt_stats(g)
        rows.append({"participant": who, "phase": phase, "trials": len(g),
                     "rt_trials": s["n"],
                     "mean_rt": s["mean_rt"], "rt_cv": s["rt_cv"],
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
    print("Not enough raw samples to estimate the sampling rate.\n"
          "This needs at least 50 rows in raw.csv, so it is empty for\n"
          "keyboard sessions and very short blocks.")
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
        # Cued modes only, so a rhythm block under the same cue setting
        # cannot drag the mean toward zero with its beat offsets.
        v = reaction_times(g)
        s = rt_stats(g)
        rows.append({
            "cue": mode, "trials": len(g),
            "hit_rate": round((g["early_late"] != "Miss").mean(), 3),
            "rt_trials": s["n"],
            "mean_rt": s["mean_rt"],
            "median_rt": round(float(v.median()), 1) if len(v) else np.nan,
            "rt_cv": s["rt_cv"],
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
    print("mean_rt is over cued modes only. rt_trials says how many trials")
    print("are behind it, and it is blank for a cue setting that only ever")
    print("ran in rhythm mode.")
    if tbl["mean_force_cal"].notna().any():
        print(f"mean_force_cal is in {NORM_UNIT}: relative {NORM_SHORT}.")
        print("It compares cues within a finger, not fingers with each")
        print("other.")
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


def _progress_game(folder, mode) -> pd.DataFrame:
    """One game's trials, with the columns the progress table needs.

    Read here rather than from `trials` because this section covers
    everyone on disk, not just the current selection.
    """
    folder = Path(folder)
    try:
        df = pd.read_csv(folder / "trials.csv")
    except OSError:
        return pd.DataFrame()
    if df.empty:
        return df
    for c in ("time_difference_ms", "peak_force_n", "lane"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "stim_delivered" in df.columns:
        df["stim_delivered"] = as_bool(df["stim_delivered"])
    meta = read_meta(folder)
    hand_mode = meta.get("hand", "right")
    df["mode"] = mode
    df["game"] = game_key(folder)
    df["hand_mode"] = hand_mode
    df["side"] = [lane_side((int(l) - 1) if pd.notna(l) else None, hand_mode)
                  for l in df.get("lane", pd.Series(dtype=float))]
    return df


def sec_participant_progress(root=None, cat=None):
    """Every session a participant has done, in order, so progress
    across the whole programme is visible rather than one block at a
    time.

    A session is one person on one day. Counting games as sessions turned
    two blocks in one sitting into a two-session training trend, which is
    the opposite of what this table is for.

    Reaction time is from cued modes only. Pooling rhythm beat offsets
    into it produced a negative coefficient of variation, which cannot
    exist, and a first-to-latest change that was really the difference
    between a rhythm block and a classic one.

    Force is the number most exposed to the calibration problem, because
    a trend over sessions can cross a recalibration. Each game is
    normalised against its own calibration and its own hand.
    """
    cat = build_catalogue(root) if cat is None else cat
    print("\n" + "=" * 62)
    print("PROGRESS PER PARTICIPANT")
    print("=" * 62)
    if cat.empty:
        _nothing("Nothing is recorded yet, so there is no progress to show.")
        return None
    people = [p for p in cat["who"].unique() if str(p) not in ("NA", "")]
    if not people:
        _nothing("Every recording on disk is under the placeholder name NA,",
                 "so there is no participant to follow across sessions.",
                 "Enter a participant name on the session screen.")
        return None

    rows = []
    for who in people:
        mine = cat[cat["who"] == who]
        # One row per DAY, not per game. Two blocks in one sitting are
        # one session, and reading them as two points on a training
        # curve invents a trend.
        for n, (day, day_games) in enumerate(
                sorted(mine.groupby("day")), start=1):
            frames = [_progress_game(g["folder"], g["mode"])
                      for _, g in day_games.iterrows()]
            frames = [f for f in frames if not f.empty]
            if not frames:
                continue
            df = pd.concat(frames, ignore_index=True)
            kept, _, counts = analysable(df)
            hit_rows = kept[is_cued(kept)]
            s = rt_stats(kept)
            force = kept.get("peak_force_n", pd.Series(dtype=float))
            cal_force = []
            for game, sub in kept.groupby("game", sort=False):
                folder = next((Path(g["folder"])
                               for _, g in day_games.iterrows()
                               if game_key(g["folder"]) == game), None)
                if folder is None:
                    continue
                cs = calibration_factors({game: read_meta(folder)})
                hand_mode = sub["hand_mode"].iloc[0]
                for v, l in zip(sub.get("peak_force_n", []),
                                sub.get("lane", [])):
                    gap = (cs.lane_gap(game, int(l) - 1, hand_mode)
                           if pd.notna(l) else None)
                    cal_force.append(cs.counts(game, v) / gap
                                     if (pd.notna(v) and gap) else np.nan)
            cal_force = pd.Series(cal_force, dtype="float64")
            rows.append({
                "who": who, "session": n, "day": day,
                "games": len(day_games),
                "modes": ", ".join(dict.fromkeys(day_games["mode"])),
                "trials": counts["recorded"],
                "analysed": counts["analysed"],
                "hit_rate": (round(float((hit_rows["early_late"] != "Miss")
                                         .mean()), 3)
                             if len(hit_rows) else np.nan),
                "rt_trials": s["n"],
                "mean_rt": s["mean_rt"],
                "rt_cv": s["rt_cv"],
                "mean_force_raw": (round(float(force.mean()), 1)
                                   if len(force) and force.notna().any()
                                   else np.nan),
                "mean_force_cal": (round(float(cal_force.mean()), 3)
                                   if cal_force.notna().any() else np.nan),
            })
    prog = pd.DataFrame(rows)
    if prog.empty:
        _nothing("No participant has a readable trials.csv, so there is no",
                 "progress table to build.")
        return None
    _show(prog)
    print("session  one person on one day. Two blocks in one sitting are")
    print("         one session, not two.")
    print("trials   recorded. analysed leaves out trials with no cue")
    print("         delivered and presses under "
          f"{ANTICIPATION_MS:.0f} ms.")
    print("mean_rt  cued modes only, misses out. Rhythm blocks contribute")
    print("         no reaction time: their timing column is a signed")
    print("         offset from the beat. rt_trials says how many trials")
    print("         are behind it, and it is blank when there are none.")

    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    for who, g in prog.groupby("who"):
        g = g.sort_values("session")
        ax[0].plot(g["session"], g["mean_rt"], "o-", lw=2, label=who)
        ax[1].plot(g["session"], g["hit_rate"], "o-", lw=2, label=who)
        ax[2].plot(g["session"], g["rt_cv"], "o-", lw=2, label=who)
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
        g = g.sort_values("session")
        if len(g) < 2:
            print(f"   {who}: only one session so far, so there is no "
                  f"change to report")
            continue
        parts = []
        # Each measure only when both ends of it exist. A blank at
        # either end used to come out as nan formatted into a change,
        # which reads as a measured result.
        def change(col, fmt, name):
            v = g[col].dropna()
            if len(v) < 2:
                return None
            return f"{name} {fmt.format(v.iloc[-1] - v.iloc[0])}"
        for col, fmt, name in (("mean_rt", "{:+.0f} ms", "reaction time"),
                               ("hit_rate", "{:+.3f}", "hit rate"),
                               ("rt_cv", "{:+.3f}", "consistency"),
                               ("mean_force_cal", "{:+.3f}",
                                f"effort ({NORM_UNIT})")):
            got = change(col, fmt, name)
            if got:
                parts.append(got)
        if not parts:
            print(f"   {who}: {len(g)} sessions, but no measure has a value "
                  f"at both ends")
            continue
        print(f"   {who}: " + ", ".join(parts) + f" over {len(g)} sessions")
        blank = [c for c in ("mean_rt", "hit_rate", "rt_cv",
                             "mean_force_cal")
                 if len(g[c].dropna()) < 2]
        if blank:
            print(f"      no change reported for: {', '.join(blank)} "
                  f"(missing at one end)")
    if prog["mean_force_cal"].notna().any():
        print(f"\nmean_force_cal is {NORM_LABEL}. Each game is against its")
        print("own calibration and its own hand, so a recalibration between")
        print("sessions does not move it.")
        print_norm_short()
        print("   A rise down this column is more effort against the same")
        print("   reference, not a stronger finger in newtons.")
    if prog["mean_force_raw"].notna().any():
        print("mean_force_raw is raw counts and cannot be read down the")
        print("column: it mixes the fingers that came up with the pads they")
        print("sat on, and a recalibration between sessions moves it on its")
        print("own.")
    return prog
