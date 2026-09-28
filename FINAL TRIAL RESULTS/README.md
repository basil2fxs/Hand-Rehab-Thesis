<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">Everything to collect for the thesis, in order, and where each result lands.<br>The data stays on this laptop and its backups. Only these READMEs are on GitHub.</p>

## What to collect

Participants are students, 5 to 20 of them. Each comes once and plays the one device on the right hand, with the calibrated pads, on the lab PC with you or your teammate supervising.

| What | How many | Time | Thesis |
| --- | --- | --- | --- |
| One sitting each, the longest the slot allows: 60, 45, 30 or 15 min | 5 to 20; aim for 10 or more at 45 or 60 | the length, plus about 15 min off the rig | 4.1, 4.4 to 4.7 |
| The EEG session | 1 | 55 min, plus the cap | 4.8 |
| Sensor bench, no participants | each pad set once: calibrated now, uncalibrated at the end of semester if time allows | about 20 min a set | 4.3 |

The software fixes the games. The 45 plays Reaction 20 trials, Rhythm 107 notes, Force Pilot 12 runs and Chords 40 trials, each twice, plus Echo, Buzz Hunt, Muscle Memory and Adaptive once; the 60 plays those four twice as well. The results come from the 45s and 60s together, so hour-long slots come first: the 15 and 30 play shortened games and are read on their own. Under 8 at 45 or 60, the notebook describes each person but tests no check. At 8 a check passes only when nearly everyone shows the effect, and 10 or more leaves room for one or two going the other way; with 20 instead of 10, a reliability interval is about a third narrower ([design check](../app/docs/research/design_check.md)). The Syllables cases are separate, below.

## Before the day

- [ ] Print the [study-day kit](../app/docs/study_day/README.md): the run sheet, and per person an information sheet, a consent form and an intake sheet.
- [ ] Book as many hour-long slots as the lab allows (75 minutes for anyone sitting the 60), and shorter slots only for students who cannot give an hour. The first two people are the pilot and count ([before the day](../app/docs/study_day/before_the_day.md)).
- [ ] On the lab PC, install `FingerRehab-Setup-Windows.exe` from the [latest release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest). EEG is off in it. It saves to `%LOCALAPPDATA%\Programs\Finger Rehab\sessions`.
- [ ] Quick pad check on your laptop before the device goes to the lab, board plugged in, game closed: `python3 app/scripts/pad_bench.py --masses 31.1 62.2 155.5` (2, 4 and 10 fifty-cent coins).

## Each participant

1. Consent and the intake sheet (10 min).
2. Log in: the code (P01 upward) in NAME, age, main hand, SESSION the longest length the slot allows, LOG IN.
3. Play all runs everything. Follow the [run sheet](../app/docs/study_day/run_sheet.md).
4. Before they leave: the strip shows every step done (12/12 on the 45).

## After each day

1. Copy the lab PC's `%LOCALAPPDATA%\Programs\Finger Rehab\sessions` to a USB stick, then into [`1 Healthy study`](1%20Healthy%20study) as `sessions/` on your laptop.
2. The READY check, from the project folder: `python3 app/scripts/check_sitting.py --all --data "FINAL TRIAL RESULTS/1 Healthy study/sessions" --day <date>`.
3. Type each code's Edinburgh LQ into `sessions/intake_sheet.csv`.
4. Copy the day's folder to one more place. Consent forms stay on paper, apart from the intake sheets.

## The sensor bench

1. Once per pad set, board plugged in, game closed: `python3 app/scripts/pad_bench.py --characterise --label calibrated`. It walks every pad from empty up to 1 kg and back down, then holds 500 g on the index pad for ten minutes (about 20 minutes in all).
2. Masses of 100, 250, 500 and 1000 g, each weighed on a kitchen scale with the coin it stands on; the coin sits centred on the pad.
3. The uncalibrated set the same way with `--label uncalibrated`, on the left-hand device it is being built into, once that device reads (end of semester if time allows).

## The Syllables cases

1. Your own sessions, a couple of readers, around the lab's bookings (it is the same device). Log in with code **D01**, then D02 and so on, the real age (the game picks its word level and speed from it), main hand, SESSION **Free play**.
2. Right hand, then the **Syllables** card. One block is 40 words in rounds of 10, about 9 minutes. A second block after a 5 minute break, if they are happy to.
3. The notebook: pick each reader's save, Run All. Report each as a described case: accuracy against chance (25 percent), which wrong options caught the reader, and the word level reached. It is a game, not a dyslexia test.

## The EEG session

One session, one person.

1. Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README.
2. Before the recording: the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) ("Validate once"). One Reaction block; the gaps between stimulus bytes in ActiView's Status channel must match `raw.csv` to one sample plus 1 ms. That is the result Section 4.8 needs.
3. Cap on, log in with the code, start ActiView under the name the menu shows, **Play all**.
4. Take the lab folder's `sessions/` home.

## When collection is done

1. Copy each dataset into its folder:

   | Folder | What goes in |
   | --- | --- |
   | [`1 Healthy study`](1%20Healthy%20study) | the collection days' `sessions/`, with `intake_sheet.csv` |
   | [`2 Sensor comparison`](2%20Sensor%20comparison) | the `pad_bench.py` CSVs |
   | [`3 EEG lab`](3%20EEG%20lab) | the lab's `sessions/`, `eeg/` included |
   | [`4 Syllables case`](4%20Syllables%20case) | the D codes' folders |
   | [`5 Thesis results`](5%20Thesis%20results) | the tables and figures that go in the thesis |

2. Open `analysis/session_analysis.ipynb`. In the Setup cell, set `SESSIONS_DIR` to a dataset's `sessions` folder, then Run All. The cohort chapter reads the 45s and 60s and writes to `sessions/cohort_results/` beside it; for the 15s and 30s, set `COHORT_FAMILY = "short"` and run it again.
3. Copy what the thesis uses into `5 Thesis results/<section>/`, mostly from `cohort_results/`:

   | Thesis | Files |
   | --- | --- |
   | 4.1 Participants and feasibility | `cohort_participants.csv`, `cohort_feasibility.csv` |
   | 4.3 Sensor comparison | the `pad_bench.py` CSVs |
   | 4.4 Normal ranges | `cohort_describe.csv`, `figures/cohort_norm_*.png` |
   | 4.5 Validity checks | `cohort_validity.csv`, `cohort_within_block_*.csv` |
   | 4.6 Reliability | `cohort_reliability.csv`, `cohort_second_goes.csv`, the ICC and Bland-Altman figures |
   | 4.7 Handedness | `cohort_handedness_*.csv`, `cohort_sensitivity.csv` |
   | 4.8 EEG lab | the EEG markers and SRT chapters run on `3 EEG lab`, and the Status channel check |

The design behind every number: [healthy_baseline_study.txt](../app/docs/research/healthy_baseline_study.txt) and [trial_mode.md](../app/docs/research/trial_mode.md).
