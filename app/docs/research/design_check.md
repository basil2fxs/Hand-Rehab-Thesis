# Design check: will the collection give the thesis what it needs?

28 September 2026, before any participant. Each thesis aim against what the current setup collects, the gaps, and better options where there are any. The evidence: 12 simulated people through the real engine and the full notebook, simulated statistics at each sample size, and the sources at the end (each checked against the paper or its publisher's page).

## The answer

Every aim is covered but one. The sensor comparison (V4, SQ3, thesis Section 4.3) has its bench half and no way yet to collect its paired half. One pre-registered check, R3, needs a second look before the first participant.

| Aim | What it needs | What the setup gives | Verdict |
| --- | --- | --- | --- |
| V1 Normal ranges (4.4) | pass 1 from everyone | every block finished in all 12 simulated sittings | Covered, as descriptive ranges |
| V2 Known effects (4.5) | pass 1 | every pre-specified check computes; 13 dropped by design, each with its reason | Covered; R3 needs a look (Section 4) |
| V3 Reliability (4.6) | pass 1 against pass 2 | T1 to T5 compute; Rhythm's second go is an exploratory row | Covered, with wide intervals |
| V4 Sensors (4.3) | bench, and paired game measures on both sensor sets | `pad_bench.py` for the bench; nothing collects the paired part, records which set a block used, or analyses it | **Not covered** |
| V5 Feasibility (4.1) | minutes, blocks, rests | the feasibility chapter | Covered |
| V6 EEG markers (4.8) | the marker log against the amplifier record | the notebook audits the game's side; the amplifier side is checked by hand ([eeg_lab_setup.txt](../eeg_lab_setup.txt), "Validate once") | Covered by one lab visit |
| Handedness (4.7) | left-handers | pooled numbers and a rerun without them | Descriptive: about 1 in 10 people |
| Syllables case | one reader with dyslexia | a hub game, read by the per-session chapters and kept out of n | Covered, as a description |

The dry run: 12 simulated people through the 45 minute sitting finished 12 of 12 blocks each (42.4 to 44.4 minutes), and the notebook's ten cohort chapters wrote 54 files: validity, reliability, second goes, handedness, sensitivity, feasibility and the rest. The simulated verdicts describe a model hand and are never quoted.

## 1. How many people

The collection day sets n. What n buys, from 4,000 simulated studies per cell (two passes, the exact F interval) and the t distribution:

| n | ICC 95% interval, lower end, true ICC 0.75 | the same, true ICC 0.9 | smallest effect a check detects (dz, 80% power) |
| --- | --- | --- | --- |
| 8 | 0.17 | 0.59 | 1.16 |
| 10 | 0.28 | 0.65 | 1.00 |
| 12 | 0.33 | 0.69 | 0.89 |
| 15 | 0.41 | 0.73 | 0.78 |
| 20 | 0.46 | 0.77 | 0.66 |
| 30 | 0.53 | 0.80 | 0.53 |

The guidance asks for more than one day gives. Bonett's formula needs 24 people to hold an ICC of 0.8 to plus or minus 0.15 [1]. Koo and Li suggest at least 30, and say to read the class off the interval, not the point estimate [2]. Hopkins suggests about 50 people and three or more trials [3]. Planning on the average width also leaves a real chance of a wider interval [4]. At n = 10 a true ICC of 0.8 reads 0.38 to 0.95, across three of Koo and Li's bands, which is why the thesis compares each T row with its predicted class rather than testing it.

**Better:** book 12 so that 10 finish. A second day of 8 to 10 more makes every interval about a third narrower. Say plainly in the method that n was set by the collection day.

## 2. Same session against another day

The two passes are twenty minutes apart, one seat, one calibration: within-session repeatability, an upper bound on day-to-day reliability [5]. The size of the gap depends on the task. For force tracking it can be large: trial-to-trial ICCs of 0.87 to 0.95 fell to 0.33 to 0.76 between days in one study [6], and less in another (0.92 to 0.98 within a day, 0.87 to 0.98 between days) [7]. For reaction time the drop was small (0.78 to 0.94 within, 0.70 to 0.94 between) [8]. For serial reaction time learning, a within-session consistency of 0.66 compares with about 0.3 between sessions [9].

**Better, optional:** 8 of the participants come back 2 to 7 days later for 15 minutes: Reaction, Force Pilot and Chords again, at full length. That gives a between-day ICC for T1 to T5, the answer SQ2 most wants, and Force Pilot is where it matters most. It costs a second visit, a sitting of the three core games, and the notebook pairing a code across two days, which it now flags.

## 3. Practice, and check R3

Most of the practice gain on a repeated computer test comes on the first repeat [10, 11]. Simple reaction time barely moves across repeats [12, 13]. Four-choice reaction time does move: 33 ms across three weekly sessions in one study [14]. So pass 2 minus pass 1 will mostly show practice, which the thesis already reads as practice.

R3 predicts no practice effect on Reaction (95% interval of pass 2 minus pass 1 inside 20 ms either way), citing a simple reaction time test [12]. Two things before the first participant:

1. The Reaction block is four-choice, the task where a second go shows practice [14]. R3 may well fail, and that is an honest result if it stays as written.
2. A 95% interval inside the margin is an equivalence test at 2.5% each side. The usual form reads the 90% interval, 5% each side [15]. At n = 10 and a true shift of 0, the chance R3 passes is 0.80 with a 90% interval against 0.61 with a 95% one, when two blocks of one person differ by 20 ms (SD); at 25 ms it is 0.52 against 0.30.

Both are decisions to make and date before any data, like the changes of 24 and 28 September.

## 4. The sensor comparison: the gap

The thesis promises agreement between calibrated and uncalibrated sensors on six game measures, each against a margin fixed in advance, and its main question names both sensor types. The collection plan never schedules the paired part.

What the maker says: the calibrated and standard 10 N pads list the same resolution, linearity, hysteresis (under 4%), repeatability, drift (2% at 1 min, 4% at 10 min at half load) and response time (under 1 ms) [16]. Calibration linearises the output and holds full scale to within 2%, and a standard pad suits uses where 10% accuracy is enough [17]. So calibration buys a shared newton scale, about USD 54.50 a pad more, and nothing for drift, hysteresis or timing. That backs the thesis prediction: timing and percent-of-maximum measures agree, newtons do not. (The two pages disagree on the standard pad's linearity: under 2% on one, a 10% class on the other.)

| Option | How | Cost | What it can claim |
| --- | --- | --- | --- |
| **A. A sensor pass (recommended)** | 10 of the healthy people: after the 45 minute sitting on set A, swap to set B, quick calibration, then Reaction, Rhythm, Force Pilot and Chords once more | about 15 minutes each; the software needs a sensor-set field, the sitting and a notebook chapter, about half a day | Paired: set B against the same person's pass 2 on set A, with pass 1 against pass 2 as the yardstick. The swap passes if it adds no more disagreement than repeating the block. |
| B. Between people | half the participants on each set | no extra time; a sensor-set field and a split in the notebook | Unpaired, about 5 a side: only large differences show. Section 3.7 would need rewriting. |
| C. Bench only | `pad_bench.py` on both sets, no people | 20 minutes | Where calibration matters in newtons, and nothing about the game measures. SQ3 would shrink to the bench. |

The bench half costs nothing and belongs in every option: counts per newton, linearity, hysteresis, noise and drift for both sets.

What the paired half can show at n = 10: each limit of agreement is known only to about plus or minus 1.1 SD of the differences [18]; Bland recommends about 100 people [18], and a formal agreement claim can need hundreds [19]. The equivalence test at 20 ms passes 97% of the time if one person's two blocks differ by 15 ms (SD), 80% at 20 ms, 52% at 25 ms and 28% at 30 ms. Pass 1 against pass 2 shows that spread first. Where it is wider than a margin, the row reads "not shown equivalent", which is not "different". Report the limits beside every row.

## 5. Normal ranges

Reference intervals need about 120 people [20]. A veterinary guideline that mirrors the clinical one says that below 20 no interval should be set, and that 10 to 20 values are shown one by one with the median [21]. The thesis already does this: every value, the median with its interval, the IQR and the range, no percentiles. Call them descriptive ranges for this sample.

## 6. The sittings

The 45 minute sitting holds: counterbalanced orders, the rest as the retest interval, pass 2 in pass 1's order, and every table filling in the dry run. The 60 minute sitting suits anyone who can stay 75 minutes: the 45 is inside it block for block, so they pool, and it adds P2 and a second go at every game. The 15 and 30 are for short slots. They measure with shortened games, so they are read on their own and need 8 in their own family.

## 7. The EEG lab

One lab visit covers V6: the "Validate once" check on the first Reaction block. Three to five recorded people give a descriptive SRT learning curve. Nothing in the software reads the amplifier's BDF file yet, so the Status channel comparison is done in EEGLAB or MNE by hand, as the lab note describes. A short script would make it repeatable if the lab work grows.

## 8. The Syllables case

One session with no baseline is a case description, outside the single-case reporting guideline [22] and short of the design standards [23]. It can show that the game works with the readers it was built for: finished, logged, the error pattern and the timing. It cannot claim the game helped anyone read. The notebook keeps the code out of the healthy n.

## What to change, in order

1. Decide the sensor comparison (Section 4). Option A keeps the thesis as written.
2. Decide R3: keep it, move it to the 90% interval, or re-base its prediction (Section 3).
3. Book 12 per collection day, and a second day if the rooms allow.
4. Optional: the between-day retest for 8 people (Section 2).
5. Optional: a script for the EEG Status channel check (Section 7).

## Sources

1. Bonett DG. Sample size requirements for estimating intraclass correlations with desired precision. Statistics in Medicine. 2002;21(9):1331-1335. doi:10.1002/sim.1108
2. Koo TK, Li MY. A guideline of selecting and reporting intraclass correlation coefficients for reliability research. Journal of Chiropractic Medicine. 2016;15(2):155-163. doi:10.1016/j.jcm.2016.02.012
3. Hopkins WG. Measures of reliability in sports medicine and science. Sports Medicine. 2000;30(1):1-15. doi:10.2165/00007256-200030010-00001
4. Zou GY. Sample size formulas for estimating intraclass correlation coefficients with precision and assurance. Statistics in Medicine. 2012;31(29):3972-3981. doi:10.1002/sim.5466
5. Weir JP. Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. Journal of Strength and Conditioning Research. 2005;19(1):231-240.
6. Nagasawa Y, Demura S, Nakada M. Reliability of a computerized target-pursuit system for measuring coordinated exertion of force. Perceptual and Motor Skills. 2003;96(3 Pt 2):1071-1085. doi:10.2466/pms.2003.96.3c.1071
7. Gilliam JR, Song A, Sahu PK, Silfies SP. Test-retest reliability and construct validity of trunk extensor muscle force modulation accuracy. PLoS ONE. 2023;18(8):e0289531. doi:10.1371/journal.pone.0289531
8. Zeinalzadeh A, et al. Intra- and inter-session reliability of methods for measuring reaction time in participants with and without patellofemoral pain syndrome. Archives of Bone and Joint Surgery. 2021;9(1):102-109. doi:10.22038/abjs.2020.46213.2270
9. Oliveira CM, Hayiou-Thomas ME, Henderson LM. The reliability of the serial reaction time task: meta-analysis of test-retest correlations. Royal Society Open Science. 2023;10(7):221542. doi:10.1098/rsos.221542
10. Collie A, Maruff P, Darby DG, McStephen M. The effects of practice on the cognitive test performance of neurologically normal individuals assessed at brief test-retest intervals. Journal of the International Neuropsychological Society. 2003;9(3):419-428. doi:10.1017/S1355617703930074
11. Falleti MG, Maruff P, Collie A, Darby DG. Practice effects associated with the repeated assessment of cognitive function using the CogState battery at 10-minute, one week and one month test-retest intervals. Journal of Clinical and Experimental Neuropsychology. 2006;28(7):1095-1112. doi:10.1080/13803390500205718
12. Basner M, Hermosillo E, Nasrini J, et al. Repeated administration effects on psychomotor vigilance test performance. Sleep. 2018;41(1):zsx187. doi:10.1093/sleep/zsx187
13. Woods DL, Wyma JM, Yund EW, Herron TJ. The effects of repeated testing, simulated malingering, and traumatic brain injury on high-precision measures of simple visual reaction time. Frontiers in Human Neuroscience. 2015;9:540. doi:10.3389/fnhum.2015.00540
14. Woods DL, Wyma JM, Yund EW, Herron TJ. The effects of repeated testing, simulated malingering, and traumatic brain injury on visual choice reaction time. Frontiers in Human Neuroscience. 2015;9:595. doi:10.3389/fnhum.2015.00595
15. Lakens D. Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. Social Psychological and Personality Science. 2017;8(4):355-362. doi:10.1177/1948550617697177
16. SingleTact. CS8-10N calibrated and S8-10N standard 10 N sensors, product specifications. https://www.singletact.com (accessed 28 September 2026)
17. SingleTact. Calibration. https://www.singletact.com/calibration (accessed 28 September 2026)
18. Bland JM. Sample size for a study of agreement between two methods of measurement. University of York, 2004. https://www-users.york.ac.uk/~mb55/meas/sizemeth.htm
19. Lu MJ, Zhong WH, Liu YX, Miao HZ, Li YC, Ji MH. Sample size for assessing agreement between two methods of measurement by Bland-Altman method. International Journal of Biostatistics. 2016;12(2):20150039. doi:10.1515/ijb-2015-0039
20. CLSI. EP28-A3c: Defining, establishing, and verifying reference intervals in the clinical laboratory. 3rd ed. Wayne, PA: CLSI; 2010.
21. Friedrichs KR, Harr KE, Freeman KP, et al. ASVCP reference interval guidelines. Veterinary Clinical Pathology. 2012;41(4):441-453. doi:10.1111/vcp.12006
22. Tate RL, Perdices M, Rosenkoetter U, et al. The Single-Case Reporting Guideline In BEhavioural Interventions (SCRIBE) 2016 statement. Aphasiology. 2016;30(7):862-876. doi:10.1080/02687038.2016.1178022
23. Kratochwill TR, Hitchcock J, Horner RH, et al. Single-case designs technical documentation. What Works Clearinghouse; 2010.
