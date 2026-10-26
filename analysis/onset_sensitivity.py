"""Does the press check depend on the onset rule? Rerun press_check.py with
the Teasdale velocity threshold at other shares of its peak (18 percent is
the rule the thesis uses) and report how far each player's median lag and
push-start learning score move.

    python3 onset_sensitivity.py --out DIR "E1=/path/to/session" ... [--fracs 0.10 0.30]
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import finger_rehab.analytics.signal as sig  # noqa: E402
import press_check  # noqa: E402
from sequence_task import SEGMENTS  # noqa: E402

BASE = 0.18


def run(frac: float, out: Path, sessions: list[str]) -> dict:
    orig = sig.teasdale_onset
    sig.teasdale_onset = functools.partial(orig, slope_frac=frac)
    try:
        press_check.main(["--out", str(out)] + sessions)
    finally:
        sig.teasdale_onset = orig
    d = json.load(open(out / "press_check.json"))
    row = {}
    for k, q in d.items():
        segs = {s["segment"]: s for s in q["segments"]}
        row[k] = {"lag_ms": q["lag_ms"][1], "found": q["onset_share"],
                  "score_ms": segs[SEGMENTS[-1]]["rt_onset_ms"] - segs[SEGMENTS[-2]]["rt_onset_ms"]}
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessions", nargs="+", help="KEY=path to a sequence-task session")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--fracs", type=float, nargs="+", default=[0.10, 0.30])
    args = ap.parse_args(argv)
    base = run(BASE, args.out / f"frac_{BASE}", args.sessions)
    print(f"velocity threshold {BASE:.2f} of peak: " + ", ".join(
        f"{k} lag {v['lag_ms']:.0f} ms, score {v['score_ms']:.0f} ms" for k, v in base.items()))
    summary = {str(BASE): base}
    for frac in args.fracs:
        row = run(frac, args.out / f"frac_{frac}", args.sessions)
        summary[str(frac)] = row
        print(f"velocity threshold {frac:.2f} of peak: lags move "
              + ", ".join(f"{row[k]['lag_ms'] - base[k]['lag_ms']:+.0f}" for k in base)
              + " ms; scores move "
              + ", ".join(f"{row[k]['score_ms'] - base[k]['score_ms']:+.0f}" for k in base) + " ms")
    (args.out / "onset_sensitivity.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
