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
"""
from __future__ import annotations

import json
import re
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
    for m in metas:
        u = (m.get("block_summary", {}) or {}).get("force_unit")
        if u:
            return u
    return "sensor counts"


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


def individuation(trials: pd.DataFrame) -> pd.DataFrame:
    """Target-finger force over total force across all fingers, per trial.
    1.0 means only the intended finger pressed; lower means the force
    spread onto its neighbours."""
    rows = []
    if "force_window_peaks" not in trials.columns:
        return pd.DataFrame(rows)
    for _, r in trials.iterrows():
        peaks = parse_peaks(r.get("force_window_peaks"))
        if not peaks or pd.isna(r.get("lane")):
            continue
        tgt = int(r["lane"]) - 1
        on_target = peaks.get(tgt, 0.0)
        spill = sum(v for k, v in peaks.items() if k != tgt)
        total = on_target + spill
        if total <= 0:
            continue
        rows.append({"trial": r["trial"], "finger": r["finger"],
                     "game_label": r["game_label"], "on_target": on_target,
                     "spillover": spill, "individuation": on_target / total})
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


def sec_force(trials, unit):
    force = trials[trials["peak_force_n"].notna()]
    if force.empty:
        print("\nNo force data (keyboard mode or sensors not connected).")
        return force
    print("\n" + "=" * 62)
    print(f"FORCE   (unit: {unit})")
    print("=" * 62)
    order = _order(force)
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    bp = ax[0].boxplot([force[force["finger"] == f]["peak_force_n"]
                        for f in order], labels=order,
                       patch_artist=True, widths=.6)
    for p, f in zip(bp["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax[0].set_ylabel(f"peak force ({unit})"); ax[0].set_title("Peak force")
    if force["impulse_n"].notna().any():
        bp2 = ax[1].boxplot([force[force["finger"] == f]["impulse_n"].dropna()
                             for f in order], labels=order,
                            patch_artist=True, widths=.6)
        for p, f in zip(bp2["boxes"], order):
            p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
        for m in bp2["medians"]:
            m.set_color("white"); m.set_linewidth(2)
        ax[1].set_ylabel(f"impulse ({unit} x s)")
        ax[1].set_title("Effort held over the press")
    g = force.sort_values("trial")
    ax[2].plot(g["trial"], g["peak_force_n"], "o", ms=3.5, alpha=.35,
               color="#16a34a")
    ax[2].plot(g["trial"], g["peak_force_n"].rolling(5, min_periods=1).mean(),
               lw=2, color="#16a34a")
    ax[2].set_xlabel("trial"); ax[2].set_ylabel(f"peak force ({unit})")
    ax[2].set_title("Across the block (fatigue check)")
    _save(fig, "force"); plt.show()
    _show(force.groupby("finger")["peak_force_n"]
               .agg(n="count", mean="mean", sd="std", min="min", max="max")
               .reindex(order).round(1))
    return force


def sec_individuation(trials):
    ind = individuation(trials)
    if ind.empty:
        print("\nNo individuation data (needs the force sensors).")
        return ind
    print("\n" + "=" * 62)
    print("FINGER INDIVIDUATION")
    print("=" * 62)
    print(f"{len(ind)} trials with usable force spread")
    print(f"mean index {ind['individuation'].mean():.3f}  "
          f"(1.0 = only the target finger pressed)")
    order = _order(ind)
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.6))
    bp = ax[0].boxplot([ind[ind["finger"] == f]["individuation"] for f in order],
                       labels=order, patch_artist=True, widths=.6)
    for p, f in zip(bp["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax[0].axhline(1.0, color="#16a34a", ls="--", lw=1.5,
                  label="perfect isolation")
    ax[0].set_ylim(0, 1.05); ax[0].set_ylabel("individuation index")
    ax[0].set_title("How isolated was each finger")
    ax[0].legend(frameon=False, fontsize=8)
    g = ind.sort_values("trial")
    ax[1].plot(g["trial"], g["individuation"], "o", ms=3.5, alpha=.35,
               color="#7c3aed")
    ax[1].plot(g["trial"], g["individuation"].rolling(5, min_periods=1).mean(),
               lw=2, color="#7c3aed")
    ax[1].set_ylim(0, 1.05); ax[1].set_xlabel("trial")
    ax[1].set_ylabel("individuation index"); ax[1].set_title("Across the block")
    _save(fig, "individuation"); plt.show()
    _show(ind.groupby("finger")["individuation"]
             .agg(n="count", mean="mean", sd="std").reindex(order).round(3))
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


def sec_bilateral(trials, unit):
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
    lf, rf = L["peak_force_n"].mean(), R["peak_force_n"].mean()
    if pd.notna(lf) and pd.notna(rf):
        print(f"peak force     left {lf:.0f} | right {rf:.0f}  "
              f"-> asymmetry {asym(lf, rf):+.3f}")
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


def sec_raw(folders, unit):
    raw = None
    for f in folders:
        raw = load_raw(f)
        if raw is not None and len(raw) > 50:
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
            fig, ax = plt.subplots(figsize=(9, 3.6))
            grid = np.linspace(-BEFORE, AFTER, 150)
            for lane, traces in stacked.items():
                if not traces:
                    continue
                mean = np.mean([np.interp(grid, t, v) for t, v in traces], axis=0)
                ax.plot(grid * 1000, mean, lw=2,
                        color=FINGER_COLOUR[FINGERS[lane]],
                        label=f"{FINGERS[lane]} (n={len(traces)})")
            ax.axvline(0, color="#dc2626", lw=1.5, ls="--", label="cue")
            ax.set_xlabel("time from cue (ms)")
            ax.set_ylabel(f"force above baseline ({unit})")
            ax.set_title("Average shape of a press")
            ax.legend(frameon=False, fontsize=8)
            _save(fig, "force_waveform"); plt.show()
    

# ---------------------------------------------------------------- entry

def report(pick="latest", root=None, export=True):
    """Run the whole analysis on whatever `pick` selects.

    pick accepts an id from catalogue(), a list of ids, a participant
    name, a date, a mode, a session label, "latest" or "all".
    """
    use_style()
    cat = build_catalogue(root)
    if cat.empty:
        print("Nothing recorded yet. Play a block and come back.")
        return {}
    sel = resolve(pick, cat)
    folders = [Path(p) for p in sel["folder"]]
    metas = {f.name: read_meta(f) for f in folders}
    trials = load_games(folders, cat)
    unit = force_unit(list(metas.values()))

    print("=" * 62)
    print(f"REPORT  ({pick!r})")
    print("=" * 62)
    print(f"{len(folders)} game(s), {len(trials)} trials, "
          f"{sel['session'].nunique()} session(s)")
    for _, r in sel.iterrows():
        print(f"   {r['day']} {r['time']}  {r['who']:10} {r['mode']:9} "
              f"{r['trials']:4} trials")

    sec_calibration(metas)
    on_task = sec_overview(trials, folders, metas)
    sec_quality(trials, folders, metas)
    comp = sec_compare(trials)
    rt = sec_reaction_time(trials)
    sec_accuracy(trials)
    force = sec_force(trials, unit)
    ind = sec_individuation(trials)
    rhy = sec_rhythm(trials)
    sec_bilateral(trials, unit)
    sec_raw(folders, unit)
    ons = sec_onset(folders, trials, unit)

    # Analyses that came out of reading the past Curtin theses.
    sec_objective_one(trials)
    sec_exclusions(trials)
    sec_phase(trials)
    sec_threshold_audit(metas=metas)
    sec_cue_modality(trials)
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
    if not force.empty:
        summary["peak_force_mean"] = round(force["peak_force_n"].mean(), 1)
        summary["force_unit"] = unit
    if not ind.empty:
        summary["individuation_mean"] = round(ind["individuation"].mean(), 3)
    if not rhy.empty:
        summary["beat_accuracy_ms"] = round(rhy["time_difference_ms"]
                                            .abs().mean(), 1)
    if ons is not None and not ons.empty:
        summary["onset_rt_mean_ms"] = round(ons["onset_rt_ms"].mean(), 1)
        summary["onset_rt_cv"] = round(ons["onset_rt_ms"].std()
                                       / ons["onset_rt_ms"].mean(), 3)
        summary["rfd_mean"] = round(ons["peak_dforce"].mean(), 1)

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
    """Dropdown entries, newest first. Returns [(label, pick), ...]."""
    if cat.empty:
        return []
    newest = cat.iloc[::-1]              # catalogue is oldest first
    opts = [(f"Most recent game", "latest")]

    opts.append(("---  single games, newest first  ---", None))
    for idx, r in newest.iterrows():
        hit = f"{r['hit_rate']:.0%}" if pd.notna(r["hit_rate"]) else "  ?"
        opts.append((f"   {_friendly_day(r['day'])} {r['time']}   "
                     f"{r['who']}   {r['mode']}   "
                     f"{int(r['trials'])} trials, {hit} hit", int(idx)))

    sessions = list(dict.fromkeys(newest["session"]))
    if sessions:
        opts.append(("---  whole sessions  ---", None))
        for s in sessions:
            g = cat[cat["session"] == s]
            day = _friendly_day(g["day"].iloc[0])
            modes = ", ".join(dict.fromkeys(g["mode"]))
            n = len(g)
            opts.append((f"   {day}   {g['who'].iloc[0]}   "
                         f"{n} game{'s' if n != 1 else ''} ({modes})", s))

    people = list(dict.fromkeys(newest["who"]))
    if len(people) > 1:
        opts.append(("---  one person, every day  ---", None))
        for p in people:
            n = int((cat["who"] == p).sum())
            opts.append((f"   {p}   all {n} game{'s' if n != 1 else ''}", p))

    opts.append(("---  everything  ---", None))
    opts.append(("   All games together", "all"))
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


def onset_table(folders, unit="sensor counts", cfg=None) -> pd.DataFrame:
    """Run the onset detector over every cue in the raw streams."""
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
            rows.append({"game": Path(folder).name,
                         "finger": FINGERS[lane % 4], "lane": lane,
                         "onset_rt_ms": rt, "peak_dforce": vmax})
    return pd.DataFrame(rows)


def sec_onset(folders, trials, unit):
    """Onset-based reaction time and rate of force development, and how
    they compare with the threshold-crossing figure the game records."""
    ons = onset_table(folders, unit)
    if ons.empty:
        return ons
    print("\n" + "=" * 62)
    print("MOVEMENT ONSET AND RATE OF FORCE DEVELOPMENT")
    print("=" * 62)
    v = ons["onset_rt_ms"]
    print(f"\nonset reaction time : n {len(v)}   mean {v.mean():.1f} ms   "
          f"median {v.median():.1f} ms   sd {v.std():.1f} ms")
    print(f"response stability  : CV {v.std()/v.mean():.3f}  "
          f"(sd over mean, lower is steadier)")
    d = ons["peak_dforce"]
    print(f"rate of force dev.  : mean {d.mean():.0f} {unit} per second")

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

    bp2 = ax[2].boxplot([ons[ons["finger"] == f]["peak_dforce"] for f in order],
                        labels=order, patch_artist=True, widths=.6)
    for p, f in zip(bp2["boxes"], order):
        p.set_facecolor(FINGER_COLOUR[f]); p.set_alpha(.65)
    for m in bp2["medians"]:
        m.set_color("white"); m.set_linewidth(2)
    ax[2].set_ylabel(f"peak dForce ({unit} per s)")
    ax[2].set_title("How fast force was built")
    _save(fig, "onset_rfd"); plt.show()

    _show(ons.groupby("finger")[["onset_rt_ms", "peak_dforce"]]
             .agg(["count", "mean", "std"]).round(1))

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


def sec_threshold_audit(cfg_on_delta=None, metas=None):
    """Put the configured press thresholds into newtons and check them
    against the only healthy force data in this project's lineage.

    Demouche measured healthy peak fingertip force on the 2025 button
    device. If a trigger sits above what a healthy little finger can
    produce, a weak finger cannot reach it either, and the game will
    score a genuine attempt as a miss. That reads as a patient deficit
    when it is really a threshold problem, so it is worth checking
    before any participant session.
    """
    if cfg_on_delta is None and metas:
        # A session's own calibration beats the current config: the
        # config may have been recalibrated since this data was recorded.
        for m in metas.values() if hasattr(metas, "values") else []:
            cal = (m or {}).get("calibration") or {}
            if cal.get("on_delta"):
                cfg_on_delta = list(cal["on_delta"])
                print("Thresholds below are the ones this session actually "
                      "ran under, from its own calibration.")
                break
    if cfg_on_delta is None:
        try:
            import sys as _s
            _s.path.insert(0, str(Path(__file__).resolve().parents[1]))
            from rehab.config import Config
            cfg_on_delta = list(Config.load().get("fsr.on_delta"))
        except Exception:
            print("Could not read fsr.on_delta from the config.")
            return None
    print("\n" + "=" * 62)
    print("PRESS THRESHOLDS IN NEWTONS")
    print("=" * 62)
    print(f"SingleTact {SENSOR_RATING_N:.0f} N part, "
          f"{N_PER_COUNT:.4f} N per count\n")
    rows = []
    for i, d in enumerate(cfg_on_delta[:4]):
        n = counts_to_newtons(d)
        rows.append({"finger": FINGERS[i], "on_delta_counts": d,
                     "trigger_N": round(n, 2)})
    tbl = pd.DataFrame(rows)
    _show(tbl)

    little = tbl.iloc[3]["trigger_N"] if len(tbl) > 3 else None
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar(tbl["finger"], tbl["trigger_N"],
           color=[FINGER_COLOUR[f] for f in tbl["finger"]], width=.6)
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

    if little is not None and little > DEMOUCHE_2025["little_max"]:
        print(f"\n   WARNING: the pinky trigger is {little:.2f} N, which is")
        print(f"   above the highest little-finger force Demouche recorded")
        print(f"   in healthy participants ({DEMOUCHE_2025['little_max']} N).")
        print("   A weak little finger may be physically unable to reach it,")
        print("   and every attempt would be logged as a miss. Run the")
        print("   Calibrate step from the title screen with the")
        print("   participant's own hand before the next session, and look")
        print("   at why that pad carries so much load at rest.")
    return tbl


def sec_calibration(metas):
    """What a press meant on the day, taken from the calibration each
    session recorded rather than from whatever the config says now.

    A session run before the in-app calibration existed carries nothing
    here. Its force numbers are still valid in counts, but the
    counts-to-newtons conversion rests on the datasheet figure alone
    rather than on a measurement of this device, so treat any absolute
    force claim from those sessions as weaker evidence.
    """
    print("\n" + "=" * 62)
    print("CALIBRATION THIS DATA WAS RECORDED UNDER")
    print("=" * 62)

    have = {name: m.get("calibration") or {}
            for name, m in metas.items()}
    withcal = {k: v for k, v in have.items() if v}
    if not withcal:
        print("None of these sessions recorded a calibration.")
        print("Force is in raw counts and the newton conversion comes")
        print("from the SingleTact datasheet, not from this device.")
        return None

    if len(withcal) < len(have):
        missing = [k for k, v in have.items() if not v]
        print(f"{len(missing)} of {len(have)} session(s) have no "
              f"calibration recorded:")
        for m in missing:
            print(f"   {m}")
        print("Do not pool their absolute force values with the rest.\n")

    # Flag sessions that ran under DIFFERENT calibrations. Pooling force
    # across two calibrations compares two different definitions of a
    # press, which would show up as a spurious change over time.
    stamps = {v.get("created_at") for v in withcal.values()}
    if len(stamps) > 1:
        print(f"WARNING: these sessions span {len(stamps)} different")
        print("calibrations. A press did not mean the same thing in each,")
        print("so a force change across them is not necessarily a change")
        print("in the patient. Compare within one calibration:")
        for name, v in sorted(withcal.items()):
            print(f"   {v.get('created_at', 'unknown')}   {name}")
        print()

    ref = list(withcal.values())[0]
    rows = []
    for i, finger in enumerate(FINGERS[:4]):
        def at(key, default=0):
            seq = ref.get(key) or []
            return seq[i] if i < len(seq) else default
        on = at("on_delta")
        rows.append({
            "finger": finger,
            "rest_load_counts": at("preload"),
            "press_gap_counts": at("gap"),
            "trigger_counts": on,
            "trigger_N": round(counts_to_newtons(on), 2),
            "pct_of_gap": (round(100 * on / at("gap"), 0)
                           if at("gap") else None),
        })
    tbl = pd.DataFrame(rows)
    print(f"Taken {ref.get('created_at', 'unknown')} "
          f"on {ref.get('device_port') or 'an unrecorded port'}\n")
    _show(tbl)

    deficit = ref.get("multi_finger_deficit")
    if deficit is not None:
        print(f"\nMulti-finger force deficit: {deficit * 100:.0f}%")
        print("Force lost per finger when all four press together against")
        print("each finger pressing alone. Healthy hands lose some; a")
        print("larger loss is the multi-finger deficit reported after")
        print("stroke, and it is measured here at calibration rather than")
        print("inferred from gameplay.")
    return tbl


def sec_objective_one(trials, window=32):
    """Objective 1 as the progress report words it: a per-finger hit rate
    between 65 and 80 percent over a 32-trial block.

    The session-level rolling figure elsewhere can sit inside the band
    while individual fingers sit well outside it, so this checks each
    finger against its own trials, which is what the objective claims.
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
    _show(tbl)
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


def sec_dose(trials, on_task_min):
    """Repetitions against the clinical benchmark.

    Lang's figure of about 32 repetitions in a typical therapy session is
    the number the whole dose argument rests on, so it is worth plotting
    rather than only citing.
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


def sec_cue_modality(trials):
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
            "mean_force": (round(g["peak_force_n"].mean(), 1)
                           if g["peak_force_n"].notna().any() else np.nan),
        })
    tbl = pd.DataFrame(rows).sort_values("cue").reset_index(drop=True)
    _show(tbl)

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
            rows.append({
                "who": who, "n": n, "day": g["day"], "mode": g["mode"],
                "trials": len(df),
                "hit_rate": round(hit.mean(), 3) if len(hit) else np.nan,
                "mean_rt": round(good.mean(), 1) if len(good) else np.nan,
                "rt_cv": (round(good.std() / good.mean(), 3)
                          if len(good) and good.mean() else np.nan),
                "mean_force": (round(force.mean(), 1)
                               if force.notna().any() else np.nan),
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
        print(f"   {who}: reaction time {d_rt:+.0f} ms, "
              f"hit rate {d_hit:+.3f}, consistency {d_cv:+.3f} "
              f"over {len(g)} sessions")
    return prog
