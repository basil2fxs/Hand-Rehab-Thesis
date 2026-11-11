<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">Where the thesis's data and results are kept, and how to reproduce each result.<br>None of the data is on GitHub: git ignores everything here except this README and the .gitignore beside it.</p>

| Folder | What it holds |
| --- | --- |
| `1 Healthy study` | The student sittings: `raw/` as copied off the lab computer, with names, and `sessions/` with the names replaced by codes. Also the one-page sitting sheet the students followed, and its source |
| `3 EEG lab` | The EEG sittings' session folders with their `.bdf` recordings, and `results/` from the EEG analysis |
| `5 Thesis results` | `run_all.sh` and everything it writes |
| `2 Sensor comparison`, `4 Syllables case` | Empty: the pad bench and the Syllables case moved to future work |
| `6 Self tests` | Empty: the author's own between-day checks were planned but not run |

Data collection finished on 22 October 2026: the laboratory's sequence task played four times (twice with EEG, and one of those also played Buzz Hunt), one 30-minute sitting and one Force Pilot block. The thesis calls the six people Person 1 to 6, with the EEG sittings first. In the data itself they have the software's own codes (`P01` and up).

## Rerunning the thesis results

`5 Thesis results/run_all.sh` reruns the analysis of the final data. It's kept in this ignored folder because its paths include the session folder names, which include people's names. It can be run from any folder:

    bash "FINAL TRIAL RESULTS/5 Thesis results/run_all.sh"
    bash "FINAL TRIAL RESULTS/5 Thesis results/run_all.sh" --eeg

From `analysis/` it runs `sequence_task.py`, `press_check.py`, `count_lag.py` and `hold_replay.py` on the four sequence-task blocks (labelled `E1` and `E2` for the EEG sittings, `L1` and `L2` for the others), and `onset_accuracy.py` on simulated pushes, each writing into its own folder or text file here. `--eeg` adds the two-recording EEG statistics (`python3 -m eeg.group`, which needs MNE). Finally, `review_report.py` puts it all into `review/Results_for_review.pdf`. It reads each EEG sitting's own results, so on a fresh copy run `python3 -m eeg` on each EEG sessions folder first. For new data, copy the script and change its folder lines to point at the new sessions. [The analysis README](../analysis/README.md) explains what each script measures.

## Student sittings

Each student ran their own sitting on the EEG lab's computer from the one-page sheet, `1 Healthy study/Sitting sheet.pdf`: PsychoPy, Coder, `run_in_psychopy.py` from the `Finger Rehab study` folder on the desktop, then a login with their own name and the session length they had time for. Using their own name means an interrupted sitting can be resumed.

After the last sitting:

1. Copy the lab computer's `Finger Rehab study/sessions` into `1 Healthy study/raw`. These folders have people's names in them, so don't copy them off this computer.
2. Replace every name with a code, P01 upwards in the order of each person's first sitting. Test logins (Test Mode blocks, names starting with test or demo) are left out, and `--exclude NAME` leaves out any other. The key is printed once, so save it somewhere that isn't shared. The output folder must not exist yet.

       python3 app/scripts/deidentify_sessions.py "FINAL TRIAL RESULTS/1 Healthy study/raw" "FINAL TRIAL RESULTS/1 Healthy study/sessions"

3. Check each coded sitting:

       python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>

4. Open `analysis/session_analysis.ipynb`, set `SESSIONS_DIR` to `1 Healthy study/sessions` and Run All. Sittings of every length are pooled, and the tables and figures are saved in its `cohort_results/`. Keep a copy in `5 Thesis results`. With fewer than 8 people, each check is described rather than tested.

## EEG sittings

Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README; run the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) before recording. Afterwards copy the lab folder's whole `sessions/` folder, including `eeg/` and its `.bdf`, into `3 EEG lab/sessions`. Then run this from `analysis/` (it needs MNE, see [its README](../analysis/README.md)):

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

The results are saved in `3 EEG lab/results/`, with a folder for each sitting.

## Future work

The sensor bench (`app/scripts/pad_bench.py --characterise`, 100 to 1000 g on each pad of both sets), sittings on the left-hand device and Syllables with readers with dyslexia were moved to future work on 3 October 2026, so no data was collected for them. The calibrated set doesn't need a load check, because each pad keeps the manufacturer's calibration on its matched board (thesis Section 2.12).
