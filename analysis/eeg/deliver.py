"""MNE's own reports, one per game, beside the results page."""
from __future__ import annotations

from pathlib import Path

import numpy as np

import mne

from . import pipeline as P
from .analyses import SRT_LABELS


def mne_reports(blocks, cleaned, results, out: Path) -> list[str]:
    names = []
    for b in blocks:
        c = cleaned[b.mode]
        rep = mne.Report(title=f"{b.mode.upper()}: {b.bdf.name}", verbose="ERROR")
        rep.add_events(b.eeg_events, title="Markers on the Status channel",
                       sfreq=b.raw.info["sfreq"])
        rep.add_raw(c.raw, title="Cleaned recording (0.1-40 Hz, average reference, ICA)",
                    psd=True, butterfly=False)
        rep.add_ica(c.ica, title="ICA: eye components removed", inst=c.raw_ica_fit,
                    picks=c.ica.exclude, n_jobs=1)
        if b.mode == "srt" and "srt" in results:
            r = results["srt"]
            t = r.trials
            ep = P.make_epochs(c.raw, t.flash_sample, np.full(len(t), 30), t,
                               -0.2, 0.6, (-0.2, 0.0))
            rep.add_epochs(ep, title="Flash epochs (all trials)", psd=False)
            evs = [r.stim[k] for k in ["all_correct", *SRT_LABELS] if k in r.stim]
            titles = ["All correct flashes"] + [SRT_LABELS[k] for k in SRT_LABELS if k in r.stim]
            rep.add_evokeds(evs, titles=[f"Flash: {x}" for x in titles], n_time_points=7)
            evs = [r.resp[k] for k in ("correct", "error", "anticipation") if k in r.resp]
            rep.add_evokeds(evs, titles=[f"Press (force onset): {k}" for k in ("correct", "error", "anticipation") if k in r.resp],
                            n_time_points=7)
        if b.mode == "buzz_hunt" and "buzz_hunt" in results:
            r = results["buzz_hunt"]
            evs = [r.erp[k] for k in ("localisation", "gap", "span") if k in r.erp]
            rep.add_evokeds(evs, titles=[f"Buzz: {k}" for k in ("localisation", "gap", "span") if k in r.erp],
                            n_time_points=7)
        name = f"mne_report_{b.mode}.html"
        rep.save(out / name, open_browser=False, overwrite=True, verbose="ERROR")
        # MNE's template writes its time ranges with an en dash; the
        # files are sent on, so the ranges read "-0.2 to 0.6 s" instead.
        text = (out / name).read_text(encoding="utf-8")
        (out / name).write_text(text.replace(" \u2013 ", " to ").replace("\u2014", "-"),
                                encoding="utf-8")
        names.append(name)
    return names
