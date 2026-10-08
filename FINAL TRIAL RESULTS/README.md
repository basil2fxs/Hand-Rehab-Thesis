<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">What to run for the thesis, and where each result goes.<br>The data stays off GitHub: only this README is shared.</p>

| Run | How many | Thesis | Folder |
| --- | --- | --- | --- |
| Student sittings, 15 to 60 min | 5 to 20; 10 or more at 45 or 60 | 4.1, 4.4 to 4.7 | `1 Healthy study` |
| Sensor bench, no people | moved to future work | 4.3 | `2 Sensor comparison` |
| Left-hand device, uncalibrated pads | a few, if it is ready | 4.3 | `2 Sensor comparison` |
| EEG session | 1 | 4.8 | `3 EEG lab` |
| Syllables, readers with dyslexia | a couple | 3.5 | `4 Syllables case` |
| Tables and figures for Chapter 4 | | 4.1 to 4.8 | `5 Thesis results` |

Each folder holds a `sessions/` copied in after each day. Codes only, never names.

## Student sittings

1. Lab PC: install `FingerRehab-Setup-Windows.exe` from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) (EEG off), then once, board plugged in: Settings, Setup, Audio delay. Print the [study-day kit](../app/docs/study_day/README.md).
2. Each student, with you or your teammate: consent and intake, then log in with the next code (P01 upward) and the longest SESSION their slot allows. Follow the [run sheet](../app/docs/study_day/run_sheet.md).
3. After each day: copy `%LOCALAPPDATA%\Programs\Finger Rehab\sessions` into `1 Healthy study/sessions`, add each code's intake answers to `intake_sheet.csv` there (columns in `app/docs/study_day/intake_sheet_template.csv`), then check it: `python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>`.

Leave out bench tests and demos; the first two participants are the pilot and stay in. Under 8 at 45 or 60, results are described but not tested.

## Sensor bench

Moved to future work on 3 October 2026: nothing to run for this collection. The procedure, for later: `python3 app/scripts/pad_bench.py --characterise --label calibrated`, then `--label uncalibrated` on the left-hand device, with 100, 250, 500 and 1000 g each on a coin centred on the pad. Its files go in `2 Sensor comparison/bench/`.

## Left-hand device

A few sittings at most, kept out of the study. Log in with a code from U01 upward, SESSION Free play, then Left hand for each game. Never a SESSION length: every length plays the right hand, so the sitting would be saved as right-hand study data. Copy the U folders into `2 Sensor comparison/sessions`. They are described, not compared, since hand and sensor set change together.

## EEG session

Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README; run the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) before the recording. Afterwards copy the lab folder's whole `sessions/`, `eeg/` and its `.bdf` included, into `3 EEG lab/sessions`, then from `analysis/` (MNE installed, see [its README](../analysis/README.md)):

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

Results land in `3 EEG lab/results/`.

## Syllables

Readers with dyslexia, codes D01 upward, each a case of their own and reported apart from the healthy study. Copy each code's dated folders into `4 Syllables case/sessions`.

Before the first session:

- Consent from the reader; for a child, a parent's consent and the child's own agreement.
- Note the reader's age, how and when dyslexia was identified, first language, and any hearing or vision problem.
- One published reading measure: the Castles and Coltheart test for a child, the Adult Reading History Questionnaire for an adult. Repeat it after the last session if there is time.
- The listening check, once: two adult listeners of Australian English each run `python3 app/scripts/syllables_recording_kit.py listen --listener L1 --device "the headphones" --level "the volume"` (then L2). `listen --report` names any probe set fewer than 90 percent of answers got right; re-render or drop it before the probe is used.

The sessions: log in with the code, the reader's real age and SESSION Free play, then the Syllables card. A D code opens every sitting with the probe, the READING CHECK card: the same sets in the same order, no hints, no feedback.

- Baseline: 3 to 5 sessions on separate days with the probe alone. After its last set the HEAR AND PICK card waits; Esc twice there keeps every answer.
- Training: then the whole sitting (the probe, then Start on that card). 6 to 9 year olds play 20 words, older readers 30; about 12 to 20 minutes with the probe.
- With three readers, start their training at different times.

One session alone is a case description: it shows the game ran and how the reader played, and nothing about change.

Each session:

- A quiet room, the same closed headphones at the same level every time, checked with the reader before starting.
- Sit beside the reader. Encourage between sections in neutral words, never name or point to an answer, press R only when asked, and note any interruption.
- Before the first block, say: "If a finger buzzes, that is a hint; try first if you can."
- Stop if the reader asks, is upset, or misses three words in a row and is frustrated: end after the word in play (Esc twice).
- Afterwards: it is a practice game, not a test or a treatment, and no number describes reading ability.

The analysis: set `SESSIONS_DIR` in `analysis/session_analysis.ipynb` to `4 Syllables case/sessions` and Run All. The chapters SYLLABLES: THE CASE SITTING and SYLLABLES: THE PROBE are the case.

## Results

Open `analysis/session_analysis.ipynb`, set `SESSIONS_DIR` to a folder's `sessions`, and Run All; every length pools. Copy the tables and figures the thesis uses out of `cohort_results/` into `5 Thesis results`, one folder per section (`4.1` to `4.8`), plus the Syllables case.
