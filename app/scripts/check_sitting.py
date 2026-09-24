"""Check one participant's sitting before they leave the room.

Reads the session folders the game wrote and says, in a few lines,
whether the sitting is complete and usable for the study: all twelve
Play all steps finished once, in their passes, on the right hand, with
the files every analysis reads, full counts (no Test Mode blocks), the
rest between the passes taken, no board drops or failed buzzes, and
the intake filled in. Anything that needs a look is printed as CHECK
with what to do; the last line says READY or how many items to check.

    python3 app/scripts/check_sitting.py            newest code today
    python3 app/scripts/check_sitting.py P07        one code
    python3 app/scripts/check_sitting.py --all      every code today
    python3 app/scripts/check_sitting.py --data /path/to/sessions

The sessions folder is the one Local_Runner.command writes to (the
project's top-level sessions/), unless --data names another. Nothing
is written or moved.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GAME_RE = re.compile(r"^(?P<who>.+)_(?P<clock>\d{6})_(?P<mode>[a-z_]+)$")
CODE_RE = re.compile(r"^[A-Za-z]{1,3}\d{2,4}$")

# The shipped plan (protocol.presets.study_battery, healthy_one_hand_v2):
# twelve steps, nine in pass 1 and three in pass 2. The exact counts a
# full block of these modes plays; the rest vary with the player and
# only need to be above zero.
N_STEPS = 12
PASS2_FROM = 10
EXACT_TRIALS = {"reaction": 20, "chords": 40, "pattern": 296}
FORCE_PILOT_RUNS = 12
REST_PLANNED_S = 180.0
INTAKE_FIELDS = ("age", "sex", "dominant_hand", "hand_length_mm",
                 "hand_breadth_mm")


def _read_meta(folder: Path) -> dict | None:
    try:
        return json.loads((folder / "metadata.json").read_text(
            encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _when(text) -> datetime | None:
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%S")
    except (TypeError, ValueError):
        return None


def games(sessions: Path, day: str | None) -> list[dict]:
    """Every game folder of one day (the newest day when None)."""
    days = sorted(d for d in sessions.iterdir()
                  if d.is_dir() and DAY_RE.match(d.name))
    if day is not None:
        days = [d for d in days if d.name == day]
    if not days:
        return []
    out = []
    for g in sorted(days[-1].iterdir()):
        m = GAME_RE.match(g.name)
        if not g.is_dir() or not m:
            continue
        out.append({"folder": g, "who": m.group("who").upper(),
                    "clock": m.group("clock"), "mode": m.group("mode"),
                    "meta": _read_meta(g)})
    return out


def check_code(code: str, rows: list[dict]) -> list[tuple[bool, str]]:
    """(ok, line) per check for one code's games of the day."""
    out: list[tuple[bool, str]] = []
    mine = [r for r in rows if r["who"] == code]
    battery = [r for r in mine if r["meta"]
               and (r["meta"].get("battery") or {}).get("id")]
    free = [r for r in mine if r not in battery]
    if not battery:
        out.append((False, f"no Play all block for {code}: was the "
                           f"sitting started with PLAY ALL?"))
        return out
    by_pos: dict[int, list[dict]] = {}
    for r in battery:
        pos = int((r["meta"].get("battery") or {}).get("position") or 0)
        by_pos.setdefault(pos, []).append(r)

    def status(r):
        return str((r["meta"].get("block_summary") or {}).get("status", ""))

    done = {p: [r for r in rs if status(r) == "completed"]
            for p, rs in by_pos.items()}
    missing = [p for p in range(1, N_STEPS + 1) if not done.get(p)]
    twice = [p for p, rs in done.items() if len(rs) > 1]
    retried = [p for p, rs in by_pos.items()
               if any(status(r) == "abandoned" for r in rs) and done.get(p)]
    if missing:
        names = ", ".join(
            f"{p} ({by_pos[p][0]['mode']}, ended early)" if p in by_pos
            else str(p) for p in missing)
        out.append((False, f"steps not finished: {names}. Press PLAY ALL "
                           f"to play them, or write down why they were "
                           f"skipped"))
    else:
        out.append((True, f"all {N_STEPS} steps finished"))
    if twice:
        out.append((False, f"step(s) finished twice: {twice}. The "
                           f"notebook averages them; note why"))
    if retried:
        out.append((True, f"step(s) ended early and replayed: {retried} "
                          f"(fine, the early one stays on record)"))

    first = sorted((r for rs in done.values() for r in rs),
                   key=lambda r: int(r["meta"]["battery"]["position"]))
    wrong_phase = [int(r["meta"]["battery"]["position"]) for r in first
                   if (r["meta"]["battery"].get("phase") or "")
                   != ("pass2" if int(r["meta"]["battery"]["position"])
                       >= PASS2_FROM else "pass1")]
    out.append((not wrong_phase,
                "passes stamped: steps 1 to 9 pass 1, 10 to 12 pass 2"
                if not wrong_phase else
                f"pass stamp wrong on step(s) {wrong_phase}"))
    hands = {str(r["meta"].get("hand")) for r in first}
    out.append((hands == {"right"},
                "every block on the right hand" if hands == {"right"}
                else f"hands recorded: {sorted(hands)}; the study plays "
                     f"the right hand only"))
    lacking = [f"{r['folder'].name}: " + ", ".join(
        n for n in ("trials.csv", "raw.csv", "metadata.json")
        if not (r["folder"] / n).is_file()
        or (r["folder"] / n).stat().st_size == 0)
        for r in first
        if any(not (r["folder"] / n).is_file()
               or (r["folder"] / n).stat().st_size == 0
               for n in ("trials.csv", "raw.csv", "metadata.json"))]
    out.append((not lacking, "trials.csv, raw.csv and metadata.json in "
                             "every block" if not lacking else
                "missing or empty: " + "; ".join(lacking)))

    short = []
    for r in first:
        m, mode = r["meta"], r["mode"]
        bs = m.get("block_summary") or {}
        snap = (m.get("config_snapshot") or {}).get("game") or {}
        if snap.get("test_mode_enabled"):
            short.append(f"{mode} (Test Mode on)")
            continue
        if mode == "force_pilot":
            runs = int(((bs.get("force_pilot") or {}).get("runs")) or 0)
            if runs != FORCE_PILOT_RUNS:
                short.append(f"force_pilot ({runs} of {FORCE_PILOT_RUNS} "
                             f"runs)")
            continue
        n = int(bs.get("trials") or 0)
        want = EXACT_TRIALS.get(mode)
        if (want and n != want) or n <= 0:
            short.append(f"{mode} ({n} trials"
                         + (f" of {want})" if want else ")"))
    out.append((not short, "full counts in every block" if not short
                else "short blocks: " + ", ".join(short)
                + ". Replay from the hub if the participant has time"))

    rest = next((r["meta"]["battery"].get("rest_before_s") for r in first
                 if int(r["meta"]["battery"]["position"]) == PASS2_FROM),
                None)
    if rest is None:
        out.append((False, "no rest recorded before pass 2"))
    else:
        rest = float(rest)
        ok = rest >= REST_PLANNED_S - 5
        out.append((ok,
                    f"rest before pass 2: {rest / 60:.1f} min"
                    + ("" if ok else " (cut short: write it on the intake "
                                     "sheet)")))

    drops = sum(int(((r["meta"].get("block_summary") or {})
                     .get("connection") or {}).get("drops") or 0)
                for r in first)
    fails = sum(int((r["meta"].get("block_summary") or {})
                    .get("stim_cue_failures") or 0) for r in first)
    out.append((drops == 0, "no board drops" if drops == 0 else
                f"{drops} board drop(s): the affected trials are voided; "
                f"note the blocks"))
    out.append((fails == 0, "every buzz delivered" if fails == 0 else
                f"{fails} buzz(es) not delivered: check the board's cable"))

    meta0 = first[0]["meta"] if first else {}
    gaps = [f for f in INTAKE_FIELDS if not str(meta0.get(f) or "").strip()]
    out.append((not gaps, "intake filled in at login" if not gaps else
                "not entered at login: " + ", ".join(gaps)
                + " (write them on the intake sheet)"))
    dom = {str(r["meta"].get("dominant_hand")) for r in first}
    if len(dom) > 1:
        out.append((False, f"main hand differs between blocks: {sorted(dom)}"))
    cal = (meta0.get("calibration") or {})
    out.append((bool(cal.get("created_at")),
                f"calibration applied (taken {cal.get('created_at')})"
                if cal.get("created_at") else
                "no calibration recorded: force numbers will not be "
                "comparable"))

    starts = [_when(r["meta"].get("started_at")) for r in first]
    ends = [_when(r["meta"].get("finished_at")) for r in first]
    starts = [s for s in starts if s]
    ends = [e for e in ends if e]
    if starts and ends:
        mins = (max(ends) - min(starts)).total_seconds() / 60.0
        out.append((mins <= 50.0, f"first block to last: {mins:.0f} min"
                    + ("" if mins <= 50.0 else " (past the 50 min stop)")))
    if free:
        out.append((True, f"{len(free)} free-play block(s) as well; they "
                          f"stay out of the analysis"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("code", nargs="?", default=None)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--day", default=None, help="YYYY-MM-DD, newest if "
                                                "not given")
    ap.add_argument("--data", type=Path, default=REPO / "sessions")
    args = ap.parse_args()
    if not args.data.is_dir():
        print(f"No sessions folder at {args.data}.")
        return 2
    rows = games(args.data, args.day)
    if not rows:
        print(f"No game folders for {args.day or 'the newest day'} under "
              f"{args.data}.")
        return 2
    codes = sorted({r["who"] for r in rows if CODE_RE.match(r["who"])})
    if args.code:
        codes = [args.code.upper()]
    elif not args.all:
        newest = max((r for r in rows if r["who"] in codes),
                     key=lambda r: r["clock"], default=None)
        codes = [newest["who"]] if newest else []
    if not codes:
        print("No study code (P01, P02, ...) in that day's games.")
        return 2
    to_check = 0
    for code in codes:
        print(f"\n{code}  ({rows[0]['folder'].parent.name})")
        for ok, line in check_code(code, rows):
            print(f"  {'OK   ' if ok else 'CHECK'} {line}")
            to_check += 0 if ok else 1
    print("\n" + ("READY: every check passed." if to_check == 0 else
                  f"{to_check} item(s) to check above."))
    return 0 if to_check == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
