<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">What to run for the thesis, and where each result goes.<br>The data stays off GitHub: only these READMEs are shared.</p>

| Run | How many | Thesis | Folder |
| --- | --- | --- | --- |
| Student sittings, 15 to 60 min | 5 to 20; 10 or more at 45 or 60 | 4.1, 4.4 to 4.7 | [`1 Healthy study`](1%20Healthy%20study) |
| Sensor bench, no people | each pad set once | 4.3 | [`2 Sensor comparison`](2%20Sensor%20comparison) |
| EEG session | 1 | 4.8 | [`3 EEG lab`](3%20EEG%20lab) |
| Syllables, readers with dyslexia | a couple | 3.5 | [`4 Syllables case`](4%20Syllables%20case) |

## Student sittings

1. Lab PC: install `FingerRehab-Setup-Windows.exe` from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) (EEG off), then once, board plugged in: Settings, Setup, Audio delay. Print the [study-day kit](../app/docs/study_day/README.md).
2. Each student, with you or your teammate: consent and intake, then log in with the next code (P01 upward) and the longest SESSION their slot allows. The session then plays its games in order; follow the [run sheet](../app/docs/study_day/run_sheet.md).
3. After each day: copy `%LOCALAPPDATA%\Programs\Finger Rehab\sessions` into `1 Healthy study/sessions`, add each code's intake sheet answers to `intake_sheet.csv` (the columns in `app/docs/study_day/intake_sheet_template.csv`: Edinburgh LQ, music years and the Muscle Memory check), then check it: `python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>`.

Under 8 at 45 or 60, results are described but not tested.

## Sensor bench

`python3 app/scripts/pad_bench.py --characterise --label calibrated`, then `--label uncalibrated` on the left-hand device once it reads. Masses of 100, 250, 500 and 1000 g, each on a coin centred on the pad; about 20 minutes a set.

## EEG session

Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README. Run the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) before the recording.

## Syllables

Your own sessions: code D01 upward, the reader's real age, SESSION Free play, then the Syllables card. Each reader is one described case.

## Results

Open `analysis/session_analysis.ipynb`, set `SESSIONS_DIR` to a folder's `sessions`, and Run All (`COHORT_FAMILY = "short"` for the 15s and 30s). Copy what the thesis uses into [`5 Thesis results`](5%20Thesis%20results).
