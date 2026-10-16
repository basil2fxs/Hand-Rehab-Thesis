<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">What to run for the thesis, and where each result goes.<br>The data stays off GitHub: only this README is shared.</p>

| Run | How many | Thesis | Folder |
| --- | --- | --- | --- |
| Student sittings, 15 to 60 min, run by the students | about 10 | 4.1, 4.3 to 4.6 | `1 Healthy study` |
| EEG session | 1 | 4.7 | `3 EEG lab` |
| Tables and figures for Chapter 4 | | 4.1 to 4.6 | `5 Thesis results` |
| The author's own checks: 15-minute sittings on five days, one slow-press block | by 22 October | 4.8, limitations 2 and 6 | `6 Self tests` |
| Sensor bench, left-hand device | moved to future work | | `2 Sensor comparison` |
| Syllables with readers with dyslexia | moved to future work | | `4 Syllables case` |

## Student sittings

Each student runs their own sitting on the EEG lab's computer from the one-page sheet, `1 Healthy study/Sitting sheet.pdf`: PsychoPy, Coder, `run_in_psychopy.py` from the `Finger Rehab study` folder on the desktop, then a login with their own name and the session length they have time for. The name lets an interrupted sitting resume.

After the last sitting:

1. Copy the lab computer's `Finger Rehab study/sessions` into `1 Healthy study/raw`. These folders carry names, so they stay on this machine.
2. Replace every name with a code, P01 upwards in the order of each person's first sitting. Add `--exclude NAME` for a test login. The key prints once; keep it out of every shared folder.

       python3 app/scripts/deidentify_sessions.py "FINAL TRIAL RESULTS/1 Healthy study/raw" "FINAL TRIAL RESULTS/1 Healthy study/sessions"

   A volunteer who sits a second time on another day (same name, any length) keeps one code. The thesis build's `results.py` uses each person's first day for the study and the second day for reliability between days.

3. Check each coded sitting:

       python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>

4. Open `analysis/session_analysis.ipynb`, set `SESSIONS_DIR` to `1 Healthy study/sessions` and Run All. Every length pools, and the tables and figures land in its `cohort_results/`; keep a copy in `5 Thesis results` for the handover.

A check with fewer than 8 participants is described, not tested.

## The author's own checks

Two checks the study cannot make, both played by the author under the login `testbasil`, which the deidentify step leaves out because it starts with `test`. Test Mode stays off, since the analysis skips Test Mode blocks.

- Between days: the 15-minute sitting on five different days. The spread of the five core measures from day to day sits beside the study's within-session error.
- Slow presses: two Free play Reaction blocks, about 40 presses, each built at a different speed from a quick tap to about half a second. Their detector lag against rise time sits beside the simulated one of Section 3.3.2.

Copy the lab computer's sessions folder, then, from the thesis build folder:

    python3 self_tests.py "<copied sessions>" --login testbasil

It writes `6 Self tests/self_tests.json`, the author's numbers only, which `results.py` and the paper's `paper_results.py` read when they fill Chapter 4.

## EEG session

Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README; run the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) before the recording. Afterwards copy the lab folder's whole `sessions/`, `eeg/` and its `.bdf` included, into `3 EEG lab/sessions`, then from `analysis/` (MNE installed, see [its README](../analysis/README.md)):

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

Results land in `3 EEG lab/results/`.

## Future work

The sensor bench (`app/scripts/pad_bench.py --characterise`, 100 to 1000 g on each pad of the calibrated and the uncalibrated set), sittings on the left-hand device and Syllables with readers with dyslexia were moved to future work on 3 October 2026. Nothing for them is collected in this study. The calibrated set needs no load check for it: each pad holds the maker's calibration on its matched board (thesis Section 2.12).
