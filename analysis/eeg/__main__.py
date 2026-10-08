"""Run the EEG analysis on a lab sessions folder.

    cd analysis
    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

Writes into <sessions>/../results/<date>_<participant>/: figures/,
tables/, summary.json, the MNE reports and the results page. The
recordings, the results and the cache never leave that folder, which
git ignores.
"""
from __future__ import annotations

import argparse
import json
import pickle
import warnings
from pathlib import Path

import numpy as np

import mne

from . import analyses as A
from . import figures as F
from . import pipeline as P


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def compute(sessions: Path):
    blocks = P.pair(sessions)
    # The sites assume the right hand answers: C3 is its motor cortex
    # and the touch response is read over the left hemisphere.
    for b in blocks:
        hand = json.loads((b.folder / "metadata.json").read_text()).get("hand")
        if hand not in (None, "right"):
            raise SystemExit(f"{b.name} was played with the {hand} hand; the EEG analysis reads "
                             "C3 and the left hemisphere as the answering side, so mirror the "
                             "site lists in analyses.py before running it on this block.")
    cleaned, results = {}, {}
    for b in blocks:
        c = P.clean(b.raw)
        cleaned[b.mode] = c
        if b.mode == "srt":
            results["srt"] = A.srt(b, c)
        elif b.mode == "buzz_hunt":
            results["buzz_hunt"] = A.buzz(b, c)
    return blocks, cleaned, results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessions", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--reuse", action="store_true",
                    help="reuse the cached computation and redraw only")
    ap.add_argument("--no-reports", action="store_true",
                    help="skip the MNE reports, the slow part of a redraw")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    mne.set_log_level("ERROR")
    sessions = args.sessions.resolve()
    first = sorted(sessions.glob("*/*/metadata.json"))
    meta = json.loads(first[-1].read_text()) if first else {}
    who = meta.get("participant", "participant")
    day = sessions.glob("20*")
    date = next((p.name for p in sorted(day)), "session")
    out = (args.out or sessions.parent / "results" / f"{date}_{who}").resolve()
    (out / "figures").mkdir(parents=True, exist_ok=True)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    # The cache holds the recordings themselves (over a gigabyte), so it
    # lives in the system's temporary folder, never beside the results.
    import hashlib
    import tempfile
    key = hashlib.sha1(str(sessions).encode()).hexdigest()[:12]
    cache = Path(tempfile.gettempdir()) / f"finger_rehab_eeg_{key}.pkl"
    if args.reuse and cache.is_file():
        blocks, cleaned, results = pickle.loads(cache.read_bytes())
    else:
        blocks, cleaned, results = compute(sessions)
        cache.write_bytes(pickle.dumps((blocks, cleaned, results)))
    figs = out / "figures"
    names = {"markers": F.markers(blocks, figs)}
    names["quality"] = F.quality(cleaned, figs)
    if "srt" in results:
        r = results["srt"]
        names.update(srt_behaviour=F.srt_behaviour(r, figs), srt_joint=F.srt_joint(r, figs),
                     srt_conditions=F.srt_conditions(r, figs), srt_topos=F.srt_topos(r, figs),
                     srt_curve=F.srt_learning_curve(r, figs), srt_ern=F.srt_ern(r, figs),
                     srt_lock=F.srt_lock(r, figs), srt_tfr=F.srt_tfr(r, figs),
                     srt_power=F.srt_block_power(r, figs), srt_rerp=F.srt_rerp(r, figs))
        r.behaviour.to_csv(out / "tables" / "srt_behaviour.csv", index=False)
        r.stim_measures.to_csv(out / "tables" / "srt_stimulus_erp_measures.csv", index=False)
        r.resp_measures.to_csv(out / "tables" / "srt_response_erp_measures.csv", index=False)
        r.per_block.to_csv(out / "tables" / "srt_erp_by_block.csv", index=False)
        r.block_power.to_csv(out / "tables" / "srt_band_power_by_block.csv", index=False)
    if "buzz_hunt" in results:
        r = results["buzz_hunt"]
        names.update(buzz_behaviour=F.buzz_behaviour(r, figs), buzz_erp=F.buzz_erp(r, figs),
                     buzz_tfr=F.buzz_tfr(r, figs), buzz_press=F.buzz_press(r, figs))
        r.measures.to_csv(out / "tables" / "buzz_erp_measures.csv", index=False)
    for b in blocks:
        b.alignment.pairs.to_csv(out / "tables" / f"markers_{b.mode}.csv", index=False)
    from . import content as C
    from . import dashboard as Dash
    from . import findings as FD
    from . import summary as S
    summ = S.build(blocks, cleaned, results, sessions)
    S.write(summ, out / "summary.json")
    limits = C.limitations(summ, FD.build(summ)["notes"])
    html_text = Dash.page(summ, names, figs, Dash.explorer(results), C.METHODS,
                          C.REFERENCES, limits, C.FILES)
    (out / "EEG_results.html").write_text(html_text, encoding="utf-8")
    print("page", round((out / "EEG_results.html").stat().st_size / 1e6, 1), "MB")
    from . import deliver
    if not args.no_reports:
        print("reports", deliver.mne_reports(blocks, cleaned, results, out))
    print("summary", deliver.summary_doc(summ, figs, out, C.METHODS_SHORT,
                                         [x.replace("<b>", "").replace("</b>", "") for x in limits],
                                         C.REFERENCES))
    print("zip", deliver.zip_folder(out, out.name))
    print(json.dumps(_jsonable(names), indent=1))
    print("results in", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
