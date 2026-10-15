<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">What to run for the thesis, and where each result goes.<br>The data stays off GitHub: only this README is shared.</p>

| Run | How many | Thesis | Folder |
| --- | --- | --- | --- |
| Student sittings, 15 to 60 min, run by the students | about 10 | 4.1, 4.3 to 4.6 | `1 Healthy study` |
| EEG session | 1 | 4.7 | `3 EEG lab` |
| Tables and figures for Chapter 4 | | 4.1 to 4.6 | `5 Thesis results` |
| Sensor bench, left-hand device | moved to future work | | `2 Sensor comparison` |
| Syllables with readers with dyslexia | moved to future work | | `4 Syllables case` |

## Student sittings

Each student runs their own sitting on the EEG lab's computer from the one-page sheet, `1 Healthy study/Sitting sheet.pdf`: PsychoPy, Coder, `run_in_psychopy.py` from the `Finger Rehab study` folder on the desktop, then a login with their own name and the session length they have time for. The name lets an interrupted sitting resume.

After the last sitting:

1. Copy the lab computer's `Finger Rehab study/sessions` into `1 Healthy study/raw`. These folders carry names, so they stay on this machine.
2. Replace every name with a code, P01 upwards in the order of each person's first sitting. Add `--exclude NAME` for a test login. The key prints once; keep it out of every shared folder.

       python3 app/scripts/deidentify_sessions.py "FINAL TRIAL RESULTS/1 Healthy study/raw" "FINAL TRIAL RESULTS/1 Healthy study/sessions"

3. Check each coded sitting:

       python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>

4. Open `analysis/session_analysis.ipynb`, set `SESSIONS_DIR` to `1 Healthy study/sessions` and Run All. Every length pools, and the tables and figures land in its `cohort_results/`; keep a copy in `5 Thesis results` for the handover.

A check with fewer than 8 participants is described, not tested.

## EEG session

Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README; run the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) before the recording. Afterwards copy the lab folder's whole `sessions/`, `eeg/` and its `.bdf` included, into `3 EEG lab/sessions`, then from `analysis/` (MNE installed, see [its README](../analysis/README.md)):

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

Results land in `3 EEG lab/results/`.

## Future work

The sensor bench (`app/scripts/pad_bench.py --characterise`, 100 to 1000 g on each pad of the calibrated and the uncalibrated set), sittings on the left-hand device and Syllables with readers with dyslexia were moved to future work on 3 October 2026. Nothing for them is collected in this study.
