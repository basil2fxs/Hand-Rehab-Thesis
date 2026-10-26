# analysis

[`session_analysis.ipynb`](session_analysis.ipynb) turns recorded sessions into results: a chapter per game, the cohort tables and figures, a report, and the reference list.

1. `pip install -r ../app/requirements.txt`
2. Open the notebook in VS Code or Jupyter and run the Setup cell.
3. Pick a save from the dropdown, then Run All.

<p align="center"><img src="../app/docs/images/analysis_norms.png" width="48%" alt="A normal-range figure from the cohort chapter"> <img src="../app/docs/images/analysis_reliability.png" width="48%" alt="A reliability figure from the cohort chapter"><br><sub>Two of the cohort chapter's figures, from a simulated cohort.</sub></p>

It finds `sessions/` beside it or up to four levels above; set `SESSIONS_DIR` in the Setup cell for a copy kept elsewhere. Figures land in the session folder they describe, per-person summaries in `sessions/individual_patient_results/<person>/`, cohort output in `sessions/cohort_results/`.

The export cell also writes `shared/matlab/finger_rehab.mat` for MATLAB and `shared/rayan_format/`, on which Rayan's R scripts run unchanged. Methods and their sources: [`app/docs/research/analysis_methods.md`](../app/docs/research/analysis_methods.md).

## EEG recordings

[`eeg/`](eeg) analyses a lab session's BioSemi recordings with MNE-Python: it pairs each `.bdf` with its game block by the marker bytes, cleans the data (average reference, 0.1-40 Hz, ICA for the eyes), and measures the ERPs, the error signal and the brain rhythms for the SRT and Buzz Hunt. `pip install mne python-picard`, then from this folder:

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

The output goes beside the sessions, in `results/`, where git never sees it.

Two recordings or more are read together with `python3 -m eeg.group SESSIONS_1 SESSIONS_2 --out DIR`: each person's own difference between conditions is averaged, the trial labels are shuffled within each person only, and Holm's correction runs across the N2 and P3.

## The laboratory's sequence task

`sequence_task.py` scores the laboratory's serial reaction time task across players the way the laboratory does (correct presses under 1000 ms, each block's first trial dropped), reads the learning score again without reversals, without presses made before the flash and against the faster of the two random blocks, fits a mixed model of reaction time on block in which each player has their own speed and their own learning effect (a random intercept and a random post-test slope per player, so the learning score's interval carries the spread between players), sets the two random blocks against each other as a repeated measure, scores the presses made too early to be reactions by the finger they chose, reads the error rates, and scores recall against simulated guessing. `press_check.py` sets every counted press against the start of its push on the board's force stream, block by block. `review_report.py` draws all of it, with the EEG, on a few pages for the people checking the results. Each takes its session folders on the command line, so no folder name is written into the code:

    python3 sequence_task.py --out DIR LABEL=BLOCK_FOLDER [LABEL=BLOCK_FOLDER ...]
    python3 press_check.py --out DIR LABEL=BLOCK_FOLDER [LABEL=BLOCK_FOLDER ...]

## The detector and its fixes

`stuck_pad_replay.py` replays a logged force stream through the press detector under the rules that ran and under the rest and hold rules added on 24 October 2026, and reports which counted presses change; `stuck_pad_figure.py` draws one player's pad through the blocks where it rested above its release margin. `onset_sensitivity.py` reruns the press check with the onset rule's velocity threshold at 10 and 30 percent of the peak instead of 18, to show how far the lags and the push-start scores move. `detector_lag_vs_rise.py` feeds the detector linear ramps at 200 Hz, rises of 10 to 400 ms at three peaks with the trigger at 30 percent of the gap, and reports how long after the raw crossing each press is counted; `--out` draws it. `adaptive_band.py` plays the adaptive controller with a headless hand of a given reaction time under the two pace ceilings.

    python3 analysis/detector_lag_vs_rise.py --out lag.png
