"""Copy a sessions folder with every name replaced by a study code.

The self-run sittings of October 2026 log in under the player's name,
so that a sitting interrupted by a closed window or a dropped board
resumes under the same identity. The analysis keeps study codes only
(the notebook drops a named block as not anonymised), so the sittings
are copied here first. Each person with at least one sitting block
becomes P01, P02 and so on, in the order of their first sitting block.
The name is replaced in the folder name, in every participant column of
trials.csv and summary.csv (flattened nested ones included), and in
every metadata field called participant; report.html and charts/ are not copied, since they repeat
the name and nothing reads them. The copy is then searched, and any
field still equal to a name stops the run.

Test logins are left out: Test Mode blocks, names starting with test or
demo, and any name given to --exclude. So is anyone who played hub
games only, since no analysis reads them. The name-to-code key is
printed, never written into the copy.

    python3 app/scripts/deidentify_sessions.py RAW OUT
    python3 app/scripts/deidentify_sessions.py RAW OUT --exclude Basil --first 11

RAW is the sessions folder copied off the study computer, OUT a folder
that must not exist yet.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GAME_RE = re.compile(r"^(?P<who>.+)_(?P<clock>\d{6})_(?P<mode>[a-z_]+)$")
TEST_RE = re.compile(r"^(test|demo)", re.IGNORECASE)
SKIP = {"report.html", "charts", ".DS_Store"}
CSV_FILES = ("trials.csv", "summary.csv")
ID_KEY = "participant"


def _key(name) -> str:
    return " ".join(str(name or "").split()).casefold()


def _is_demo(meta: dict) -> bool:
    for sub in (meta.get("block_summary") or {}).values():
        if isinstance(sub, dict) and sub.get("demo"):
            return True
    snap = meta.get("config_snapshot") or {}
    return bool((snap.get("game") or {}).get("test_mode_enabled"))


def blocks(raw: Path) -> list[dict]:
    """Every block folder under RAW with its identity and timing."""
    out = []
    for day in sorted(p for p in raw.iterdir() if p.is_dir() and DAY_RE.match(p.name)):
        for folder in sorted(p for p in day.iterdir() if p.is_dir()):
            m = GAME_RE.match(folder.name)
            meta_path = folder / "metadata.json"
            if not m or not meta_path.is_file():
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            who = str(meta.get(ID_KEY) or m.group("who"))
            out.append({"folder": folder, "day": day.name, "clock": m.group("clock"),
                        "mode": m.group("mode"), "who": who, "key": _key(who),
                        "sitting": bool((meta.get("battery") or {}).get("phase")),
                        "demo": _is_demo(meta),
                        "started": str(meta.get("started_at") or f"{day.name}T{m.group('clock')}")})
    return out


def plan(rows: list[dict], exclude=(), first: int = 1) -> dict[str, str]:
    """identity key -> code, P01 upwards by each person's first sitting
    block. Test logins, excluded names and hub-only players get none."""
    skip = {_key(n) for n in exclude}
    firsts: dict[str, str] = {}
    for r in rows:
        if r["demo"] or not r["sitting"] or not r["key"]:
            continue
        if r["key"] in skip or TEST_RE.match(r["key"]):
            continue
        firsts[r["key"]] = min(firsts.get(r["key"], r["started"]), r["started"])
    order = sorted(firsts, key=lambda k: (firsts[k], k))
    return {k: f"P{first + i:02d}" for i, k in enumerate(order)}


def _swap_json(obj, names: set[str], code: str):
    """Every value under a key called participant that is the person's
    name becomes the code, at any depth."""
    if isinstance(obj, dict):
        return {k: (code if k == ID_KEY and isinstance(v, str) and _key(v) in names
                    else _swap_json(v, names, code)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_swap_json(v, names, code) for v in obj]
    return obj


def _swap_csv(src: Path, dst: Path, names: set[str], code: str) -> None:
    with src.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    # summary.csv flattens nested fields, so a reference basis arrives as
    # chords.reference_basis.right.participant beside the participant column.
    cols = [i for i, h in enumerate(rows[0]) if h == ID_KEY or h.endswith("." + ID_KEY)] if rows else []
    for row in rows[1:]:
        for col in cols:
            if col < len(row) and _key(row[col]) in names:
                row[col] = code
    with dst.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def copy_block(row: dict, out: Path, code: str) -> Path:
    names = {row["key"]}
    dst = out / row["day"] / f"{code}_{row['clock']}_{row['mode']}"
    dst.mkdir(parents=True)
    for item in sorted(row["folder"].iterdir()):
        if item.name in SKIP:
            continue
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=shutil.ignore_patterns(*SKIP))
        elif item.name == "metadata.json":
            meta = json.loads(item.read_text(encoding="utf-8"))
            target.write_text(json.dumps(_swap_json(meta, names, code), indent=2),
                              encoding="utf-8")
        elif item.name in CSV_FILES:
            _swap_csv(item, target, names, code)
        else:
            shutil.copyfile(item, target)
    return dst


def leftovers(out: Path, names: set[str]) -> list[str]:
    """Paths, CSV cells and JSON values in the copy still equal to a name."""
    found = []

    def walk(obj, where):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{where}.{k}")
        elif isinstance(obj, list):
            for v in obj:
                walk(v, where)
        elif isinstance(obj, str) and _key(obj) in names:
            found.append(where)
    for p in sorted(out.rglob("*")):
        rel = str(p.relative_to(out))
        m = GAME_RE.match(p.name)
        if p.is_dir() and m and _key(m.group("who")) in names:
            found.append(rel)
        elif p.suffix == ".json":
            walk(json.loads(p.read_text(encoding="utf-8")), rel)
        elif p.suffix in (".csv", ".tsv"):
            delim = "\t" if p.suffix == ".tsv" else ","
            with p.open(newline="", encoding="utf-8") as fh:
                for i, row in enumerate(csv.reader(fh, delimiter=delim)):
                    if any(_key(c) in names for c in row):
                        found.append(f"{rel}:{i + 1}")
                        break
    return found


def run(raw: Path, out: Path, exclude=(), first: int = 1) -> dict[str, str]:
    """Copy RAW to OUT under codes; returns name -> code as typed."""
    if out.exists():
        raise SystemExit(f"{out} already exists; give a new folder")
    rows = blocks(raw)
    codes = plan(rows, exclude, first)
    out.mkdir(parents=True)
    shown: dict[str, str] = {}
    for r in rows:
        code = codes.get(r["key"])
        if code is None or r["demo"]:
            continue
        copy_block(r, out, code)
        shown.setdefault(r["who"], code)
    bad = leftovers(out, set(codes))
    if bad:
        shutil.rmtree(out)
        raise SystemExit("a name is still in the copy, nothing kept:\n  " + "\n  ".join(bad[:20]))
    return shown


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("raw", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--exclude", nargs="*", default=[], help="names to leave out, as typed")
    ap.add_argument("--first", type=int, default=1, help="number of the first code (default 1)")
    args = ap.parse_args(argv)
    shown = run(args.raw.resolve(), args.out.resolve(), args.exclude, args.first)
    if not shown:
        print("no sitting found to copy")
        return 1
    print(f"copied {len(set(shown.values()))} participants to {args.out}")
    print("key, keep it off the shared folders:")
    for name, code in sorted(shown.items(), key=lambda kv: kv[1]):
        print(f"  {code}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
