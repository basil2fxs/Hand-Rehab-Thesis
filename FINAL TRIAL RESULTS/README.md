<h1 align="center">FINAL TRIAL RESULTS</h1>
<p align="center">Everything to collect for the thesis, in order, and where each result lands.<br>The data stays on this laptop and its backups. Only these READMEs are on GitHub.</p>

## What to collect

Participants are students. Each comes once and plays the one device on the right hand, with the calibrated pads.

| What | How many | Time | Thesis |
| --- | --- | --- | --- |
| One sitting each, the longest the slot allows: 60, 45, 30 or 15 min | 10 finished at 45 or 60, 8 at the least; any 15s and 30s on top | the length, plus about 15 min off the rig | 4.1, 4.4 to 4.7 |
| The EEG lab sitting | 1 at the least; 3 to 5 for a learning curve | 55 min, plus the cap | 4.8 |
| Sensor bench, no participants | each pad set once: calibrated now, uncalibrated at the end of semester if time allows | about 20 min a set | 4.3 |

The software fixes the games. The 45 plays Reaction 20 trials, Rhythm 107 notes, Force Pilot 12 runs and Chords 40 trials, each twice, plus Echo, Buzz Hunt, Muscle Memory and Adaptive once; the 60 plays those four twice as well. The results come from the 45s and 60s together, so hour-long slots come first: the 15 and 30 play shortened games and are read on their own. With 20 people instead of 10, a reliability interval is about a third narrower ([design check](../app/docs/research/design_check.md)). The Syllables case is separate, below.

## Before the day

- [ ] Print the [study-day kit](../app/docs/study_day/README.md): the run sheet, and per person an information sheet, a consent form and an intake sheet.
- [ ] Book 12 hour-long slots (75 minutes for anyone sitting the 60) and a spare, and shorter slots only for students who cannot give an hour. The first two people are the pilot and count ([before the day](../app/docs/study_day/before_the_day.md)).
- [ ] On the study laptop, start the game with `Local_Runner.command`: newest code, data into `sessions/`.
- [ ] Quick pad check, board plugged in, game closed: `python3 app/scripts/pad_bench.py --masses 31.1 62.2 155.5` (2, 4 and 10 fifty-cent coins).

## Each participant

1. Consent and the intake sheet (10 min).
2. Log in: the code (P01 upward) in NAME, age, main hand, SESSION the longest length the slot allows, LOG IN.
3. Play all runs everything. Follow the [run sheet](../app/docs/study_day/run_sheet.md).
4. Before they leave: `python3 app/scripts/check_sitting.py` says READY.

## After each day

1. `python3 app/scripts/check_sitting.py --all`
2. Type each code's Edinburgh LQ into `sessions/intake_sheet.csv`.
3. Copy `sessions/<date>/` to one more place. Consent forms stay on paper, apart from the intake sheets.

## The sensor bench

1. Once per pad set, board plugged in, game closed: `python3 app/scripts/pad_bench.py --characterise --label calibrated`. It walks every pad from empty up to 1 kg and back down, then holds 500 g on the index pad for ten minutes (about 20 minutes in all).
2. Masses of 100, 250, 500 and 1000 g, each weighed on a kitchen scale with the coin it stands on; the coin sits centred on the pad.
3. The uncalibrated set the same way with `--label uncalibrated`, on the left-hand device it is being built into, once that device reads (end of semester if time allows).

## The Syllables case

1. A separate day. Log in with code **D01**, the real age (the game picks its word level and speed from it), main hand, SESSION **Free play**.
2. Right hand, then the **Syllables** card. One block is 40 words in rounds of 10, about 9 minutes. A second block after a 5 minute break, if they are happy to.
3. The notebook: pick the D01 save, Run All. Report it as one described case: accuracy against chance (25 percent), which wrong options caught the reader, and the word level reached. It is a game, not a dyslexia test.

## The EEG lab

1. Copy [`EEG_Lab`](../EEG_Lab) to the lab PC and follow its README.
2. First visit only, before anyone is recorded: the marker check in [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt) ("Validate once"). One Reaction block; the gaps between stimulus bytes in ActiView's Status channel must match `raw.csv` to one sample plus 1 ms. That is the result Section 4.8 needs.
3. Per person: cap on, log in with the code, start ActiView under the name the menu shows, **Play all**.
4. Take the lab folder's `sessions/` home after each visit.

## When collection is done

1. Copy each dataset into its folder:

   | Folder | What goes in |
   | --- | --- |
   | [`1 Healthy study`](1%20Healthy%20study) | the collection days' `sessions/`, with `intake_sheet.csv` |
   | [`2 Sensor comparison`](2%20Sensor%20comparison) | the `pad_bench.py` CSVs |
   | [`3 EEG lab`](3%20EEG%20lab) | the lab's `sessions/`, `eeg/` included |
   | [`4 Syllables case`](4%20Syllables%20case) | D01's folders |
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
