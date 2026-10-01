# Chords mode: deep research audit

1 October 2026. Scope: the study battery's Chords step, `app/finger_rehab/game/modes/chords.py` (mode key `chords`), the force path its enslaving ratio rests on (the engine's force window, `hardware/fsr_detector.py`, `hardware/calibration_profile.py`, and the pad facts in `game/force_stream.py` and `docs/research/force_units.txt`), the config, the screen text and the notebook analysis (`analysis/session_analysis.ipynb`, cell 2). Cross-hand chords, C4 and C5 are out of scope: the one-board rig cannot produce them.

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the assumptions at the end of Section 7; "(pilot)" is the development team's own Chords blocks under `sessions/` (five blocks with sensor streams, 31 August to 24 September 2026, played under the older deal and the 250 to 100 ms window ladder), which describe the rig and one to four developers, not participants; "(code)" and "(design doc)" are values read in the repository. Code line numbers refer to HEAD a8bcb2c (`chords.py`, `calibration_profile.py` and `fsr_detector.py` are unchanged in the working tree). `engine.py`, the design doc and the notebook changed on the same day for other modes, so their references also name the function or section; notebook line numbers are lines of cell 2's source as read on 1 October.

---

## 1. What the mode does now

### 1.1 The block under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Block shape | Two sub-blocks of 20 with a 30 s rest between them (skippable past the floor); the same counts in pass 1 and pass 2 | 40 trials, right hand | battery override `default.yaml` 2022-2028; `chords.rest_between_s` 1099 |
| Deal | Per 20: 4 singles (one per finger, rotating), 10 pairs, 5 triples, 1 quad. A weighted shuffle bag over sizes (no size other than pairs twice running, never opening on a single); within a size a deficit draw among the chords whose fingers have been used least; the chord just dealt is barred from the next draw | seed null, fresh every block | `DEFAULT_SIZE_MIX` 512, `WeightedClassBag` 530-588, `MixedChordDeck` 591-671; `default.yaml` 1065, 1117 |
| Per-type counts | Per 40-trial block each pair type is dealt 3.3 times on average (0 to 8), each triple type 2.5 (0 to 7), the quad twice, each single twice; about 1 percent of blocks miss a given pair type and 3.4 percent a given triple type | | simulation of the shipped deck, 2,000 blocks |
| Quiet gate | No finger past its press threshold for 500 ms before the chord fires. It reads press state only, with no force band; skippable, and the trial then carries `settle_skipped` | 500 ms | `_update_settle` 1380-1450; `default.yaml` 1086 |
| Inter-trial wait | Uniform draw before the gate starts counting | 1.5 to 2.5 s | `_arm_next` 2040-2047; `default.yaml` 1090-1091 |
| Stimulus | All target tiles light under a PRESS TOGETHER bracket; one tone, the pitch of the lowest target lane; up to three target motors buzz together for 250 ms, the quad as an arpeggio (150 ms pulses 190 ms apart, index to little, the last starting 570 ms after the stimulus); every tenth stimulus 35 percent louder | | `_fire` 1495-1535; `engine.on_stim_multi` (tone `play_stim(min(targets))`); `default.yaml` 493, 509, 514, 519, 1845; arithmetic for the arpeggio |
| Press onset | The detector's crossing of each finger's own trigger: 30 percent of that finger's light-press gap from the quick calibration (with noise and preload floors), on an EMA of the raw signal (alpha 0.35), 100 ms debounce | | `calibration_profile.py` 50, `on_delta` 235-254; `fsr_detector.py` `feed` 299-443; `default.yaml` 227, 316 |
| Completion | The chord completes when every target is down together; a target that lifts first loses its onset | | `_drop_lifted_onsets` 1208-1223; `_handle_press` 1538-1581 |
| Hold | All targets stay down 200 ms from the last onset; a ring fills on the tiles | 200 ms | `_update_hold` 1584-1602; `default.yaml` 1081 |
| Wrong press | A quiet finger crossing its trigger | Miss row, class `leak_fail`, no ER | `_handle_press` 1575-1581; `_finish` 1730-1743 |
| Timeout | | 3.0 s | `default.yaml` 1055 |
| Synchrony window | Last onset minus first onset within W counts as together | W = 150 ms, one rung | override 2028; `_finish` 1632 |
| Ladder and fatigue guard | The staircase has one rung. The fatigue guard can only count a trigger after sub-block 2, and the block then ends anyway | inert | `_staircase` 1978-2001; `_close_subblock` 2049-2088 (code trace) |
| Place in the sitting | Order A steps 5 and 12, order B steps 2 and 10. Chords follows Force Pilot every time, and pass 1's Force Pilot opens with two or three maximal presses per finger (the max-press probe); pass 2 reuses the stored maximum | | `default.yaml` 1966-1997; `force_pilot.py` FLOW (149-151), `force_stream.needs_max_press_probe` |
| Duration | | 2.63 to 2.73 min a block (M) | design doc Section 2.3 |

### 1.2 Scoring, the screen and the instructions

- Class precedence: partial, then leak_fail (a wrong press, or one quiet finger at or over 0.25 of the mean target press), then over_force (any finger of the hand at or over 2.5 times its light-press gap), then late_chord (span over W), then no_hold, then hit (`_finish` 1727-1743; constants 724-735).
- Points: completion 6 (scaled by the targets that landed), together 2 x (1 - span/W) on a full chord with the hold met, quiet 2 x (1 - ER/0.5) unless the trial is a measured leak fail (1758-1807). A hit takes its speed-tier label and never reads below Good; any other landed chord reads Late with its class in `error_type`.
- After a chord: no words; the tiles flash; after a clean chord the quiet fingers wear a brief tick (1836-1853).
- Instructions: the NEXT UP card's description is "Press keys together" (`ModeSelectScreen.MODES`, `screens.py` 1533); the GET READY card has lines for Echo only (`GameplayScreen.GET_READY_LINES`, 3738); the run sheet gives lines for Reaction, Rhythm and Echo and, for the whole sitting, "Press lightly, like typing" (`docs/study_day/run_sheet.md`). Nothing tells the participant to keep the other fingers still or resting on their pads, that the fingers must land within 150 ms, or that firm presses are classed apart.

### 1.3 The force path under ER

- Pads: SingleTact CS8-10N, 512 counts per 10 N, so one count is 0.0195 N and a newton is 51.2 counts; resting noise about 1.1 counts SD (config comment, fsr block), 1.2 to 1.5 counts with at most 1.5 counts of drift in 60 s (`force_stream.py` docstring); hysteresis under 4 percent of full scale by the datasheet (`force_units.txt`).
- Baseline: the detector's EMA of the smoothed value, alpha 0.0005 per sample (time constant about 10 s at 200 Hz), updated only while the finger is not pressed and primed from the calibration's resting level at block start (`fsr_detector.py` 312-316; `default.yaml` 226; `engine._prime_baselines`).
- Force window: opens at the stimulus and closes when the trial is logged; each lane's peak is the largest raw sample minus the baseline EMA over the window, clamped at zero (`engine._track_force_peaks`, `_open_force_window`, `_close_force_window`), converted to newtons by the engine and back to counts by the mode (`_window_peaks` 1135-1160). For a landed chord the window runs to the end of the hold, the completion time plus 200 ms: 0.68 to 2.9 s in the pilot, about 1 s typically (pilot). It is 3.2 s only on a timeout.
- ER: the mean over quiet fingers of peak/gap divided by the mean over targets of peak/gap, where gap is the calibration's light press minus resting, uncapped (`CalibrationProfile.gap` 205-209); computed only on a complete response with no wrong press, and never for the quad (`_finish` 1645-1725, record 1899-1900).
- Reconstruction: re-running the detector over each pilot block's raw samples (the calibration's resting level as the primed baseline, the block's own on and off deltas) reproduced every logged `force_window_peaks` value, with a median absolute difference of 0.00 to 0.03 counts per pad in all five blocks (pilot). Section 1.7 rests on it.

### 1.4 Logging and block_stats

Each trial writes a CSV row (the chord in `stimulus` as lane numbers, the targets in `correct_keys`, the per-pad peaks in `force_window_peaks`, keyed on the lowest target lane) and a record in the block summary: kind, size, D, W, class, span, first-onset RT, completion time, ER, per-finger normalised presses and leaks, hold, over_force, light, wrong, settle time, `settle_skipped`, sub-block (`_finish` 1873-1934). `block_stats` (2237-2566) adds the per-chord table by (hand, chord, W), the size table (hit rate and median RT, completion, span and ER per size), the singles per finger and the one-finger matrix, chord-conditioned start and end matrices from the first and last sub-blocks, the outcome classes, and the calibration basis of each hand's normaliser.

### 1.5 Registered checks and the notebook

- C1: cohort median of each person's median ER under 0.15, on the point and its bootstrap interval (`_mean_check`; the C1 row, line 24741); read as a feasibility check since 30 September (design doc Sections 1.3 and 4.6).
- C2: Spearman rho of D against per-chord hit rate (negative) and against per-chord median ER (positive) over the cohort-pooled per-chord table, each half decided on its own at p < 0.05 two-sided with the predicted sign; the quad stays out of the ER half (`chord_c2_halves` 12327).
- C3: the ring column of the cohort-mean chord-conditioned matrix is the largest (`_chords_c3_row` 24317).
- C6: per person, the least-squares slope of median first-press RT on size over one, two and three fingers (each size needs three trials); cohort median above zero by one-sided Wilcoxon, in the Holm family (`chord_cost_per_finger` 21200; the C6 row, 24824). With three equally spaced sizes the least-squares slope equals half of (median RT of triples minus median RT of singles), so the 20 pairs of a block carry no weight in it (arithmetic).
- W4: sub-block 2 against sub-block 1, median ER down and clean hit rate up, each half on its own 95 percent interval, both needed (`_chords_w4_row` 24362).
- T4 median_er predicted moderate (0.5 to 0.75); T5 median_span_ms predicted good (0.75 to 0.9) (design doc Section 4.5c; notebook 30369-30370).
- Sensitivity rows added on 30 September (`docs/research/new_modes/modes-review.md`): ER with each pad's rest peak taken off (`chord_rest_peaks` 12115, over 3.2 s windows, `CHORD_REST_WIN_S` 12108), the share of chords whose leak is under 1.5 times that floor, and spans on the board's clock (`chord_spans_on_grid` 21033).
- Cohort metrics (`_cohort_chords` 21092): median_er, median_span_ms, median_span_ms_grid, clean_hit_rate, over_force_rate, median_er_nc, er_at_floor_share, chord_cost_ms, single_rt_ms, single_er.
- `MODE_LIT["chords"]` (25949) carries C1 to C5 and an EEG row, and no C6; `MODE_CLAIM_LIMITS["chords"]` (26544).
- `sec_individuation` (5342) and `sec_crosstalk` (13265) read every single-target trial (multi-finger chord rows are left out; Chords' single-finger trials enter) and print `ENSLAVEMENT_REF` (269) as the published comparison. The force chapter's `true_press_force` (7291) already zeroes each press on the 250 ms before its cue (`lookback_baseline`, 4639); no chords function uses it.

### 1.6 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this audit |
|---|---|---|---|
| Healthy hands leak roughly 5 to 15 percent of the instructed force at light effort; 8 to 10 percent at about 25 percent MVC | `chords.py` 9-11; design doc C1; notebook `HEALTHY_ER_BAND` (118, "light force"), `MODE_LIT` C1 ("Journal of Motor Behavior") | Abolins et al. 2020 | Figure right, context wrong. It is the non-instructed pair's share of the TOTAL force while a finger pair holds 25 percent of the pair's MVC: 8 to 10 percent at 4 s, 12 to 17 percent by 19 s. The journal is J Neurophysiol 124(6) [FT]. 25 percent MVC is well above the study's presses (Q1) |
| A resting finger's own noise gives an ER near 0.05; a quiet finger reaches about 2 counts over a chord's 3.2 s window | `chords.py` 11-15; design doc C1; `MODE_CLAIM_LIMITS` | modes-review.md (pilot) | The ER figure holds (pilot median 0.045), the window does not (about 1 s for a landed chord), and most of the peaks come before the press (Section 1.7) |
| Enslaving is strongest between neighbouring fingers | `chords.py` 6-8, 29-31 | Zatsiorsky, Li and Latash 2000 | Supported [ABS]; also Kim et al. 2008, Mirakhorlo et al. 2017, van den Noort et al. 2016 [FT] |
| Ring the least independent, then middle and little, index the most (weights 1, 2, 3, 2) | `chords.py` 31-34, 402-405 | Hager-Ross and Schieber 2000; Chiang et al. 2004 | Supported for movement (1 minus the stationarity index runs 1 : 1.8 : 2.8 : 1.7 for I, M, R, L, arithmetic from Table 2 [FT]) and for force received at MVC (Wilhelm et al. 2014 Table 1, arithmetic [FT]). Chiang and Slobounov's "most enslaved" ring is the ring as the instructed finger (Q4) |
| Per-finger force and timing degrade as chord size grows | `chords.py` 36-38, 408-409 | Li, Latash and Zatsiorsky 1998 | Force deficit, yes [ABS]; timing comes from Verwey 2023 [FT] and Seibel 1962 [META] |
| Skilled pianists land chord tones within about 30 ms | `chords.py` 106-107; `default.yaml` 1070-1071 | Goebl 2001 | Not as stated: about 30 ms is the melody lead at hammer impact; at the finger-key level it falls to near zero [ABS] |
| Perceptual simultaneity is 20 to 50 ms | `chords.py` 107-108 | Rasch 1979/1988 | Not verified: no DOI or index record found; not load-bearing |
| Enslaving drifts up about 50 percent over a 15 s hold | `chords.py` 95-97; `default.yaml` 1078-1080 | Abolins et al. 2020 | Supported: the index rose 49 percent on average between 4 and 19 s [FT]. At 200 ms against 500 ms the drift is negligible either way (Q13) |
| Fatigue inflates enslaving and the force deficit; four-finger MVC fell about 43 percent | `chords.py` 142-146, 201-205 | Danion et al. 2000, 2001 | The 43 percent holds [ABS]. Enslaving was unchanged at the fatigued site in 2000 [ABS] and fell under fatigue in 2001 (22.1 to 20.7 percent, p = 0.07; the fatigued index less enslaved, 12.5 to 9.7 percent) [FT] |
| Stroke raises the leak and lowers individuation | `chords.py` 15-17 | Lang and Schieber 2003, 2004 | Supported [ABS]; Li et al. 2003 [ABS] |
| Individuation recovers partly apart from strength | `chords.py` 17-19 | Xu et al. 2017 | Supported [FT] |
| Accuracy practice raised enslaving; feedback on independence lowered it | `chords.py` 20-23 | Chiang, Slobounov and Ray 2004 | Supported [ABS] |
| Modest post-stroke gains from game training with multi-finger combinations | `chords.py` 23-25 | Thielbar et al. 2014 | Supported: a key-combination mode; FMH up 1.9 points (12 percent, p = 0.026) by the one-month follow-up; individuation index p = 0.05 in 4 people [FT] |
| RT rises with keys pressed at once: 510, 632 and 762 ms | `chords.py` 177-181; design doc C6; notebook C6 row | Verwey 2023; Seibel 1962 | Numbers right [FT]. They are the mean of the key times in a test phase after 240 practice trials per chord, pooled over a one-hand and a two-hand group, for chords whose keys landed within 50 ms. C6 reads the first press (Q7) |
| Enslaving is not additive; the leak from two or three instructed fingers is often smaller | `chords.py` 186-189 | Zatsiorsky et al. 2000 | Supported for force at MVC [ABS]; movement data disagree for ring and little (van den Noort et al. 2016 [FT]) |
| A chord-conditioned cell upper-bounds the single-finger cell under the additive model | `_chord_matrix` docstring 2204-2207; `sec_chords` printed text | Zatsiorsky et al. 2000 | Contradicted by the module's own docstring (186-189) and `modes-review.md`: non-additive, so no bound |
| Press onset at about 40 percent of the light press | `chords.py` 253-254 | code | Stale: `PRESS_FRACTION` is 0.30 (`calibration_profile.py` 50) |
| Challenge-point staircase in the style of FINGER's success-rate control | `chords.py` 152-160 | Taheri et al. 2014; Rowe et al. 2017 | Consistent [FT for Taheri: gains fall by a step per hit and rise by a multiple of it per miss]; frozen in the battery |
| 300 repetitions a session as the stroke feasibility benchmark | `chords.py` 162-170 | Birkenmeier, Prager and Lang 2010 | Supported: 322 repetitions per session on average [FT] |
| Healthy light-force enslaving sits around 0.08 to 0.15; healthy hands leak under about 10 percent (Xu's healthy slope 0.087) | notebook `sec_chords` printed text | Abolins et al. 2020; Xu et al. 2017 | Xu's controls were 64 years old, and 0.087 is the RMS deviation of all uninstructed fingers per newton at 20 to 80 percent MVF [FT]; for Abolins see the first row |
| Published enslavement: unimpaired 0.13, stroke 0.251 | notebook `ENSLAVEMENT_REF` 269 | Li et al., via an unpublished 2024 thesis | Not verifiable: the Li et al. 2003 abstract carries no such figures [ABS]; not for quotation |
| Worse by the end of the session is the within-session fatigue picture | notebook `sec_chords` | Danion 2000 | Not supported (the fatigue row above); in the battery the start and end matrices are 20 trials apart |
| Chords (C1 to C3) are strong for a healthy cohort: known effect, expected good reliability | design doc Section 1.12 | | Not supported for C1 to C3 at the study's forces (Section 1.7; Q1 to Q4) |

### 1.7 Pilot blocks on disk, and a measurement finding

Five Chords blocks carry sensor streams: `Test_174458` (31 August; 20 chords and 8 single-finger probes), `test_220623` (2 September; 16 chords), `P669_192951` (23 September; 30 trials, the last 13 with no response), `P670_234126` (23 September; 5) and `P671_010224` (24 September; 6). Two of them name `KeyboardOnlySource` in their metadata, but they carry raw sensor samples and the reconstruction reproduces their logged peaks. `P666` and the two `ff` blocks have no usable force data. All ran the older deal and the 250 to 100 ms ladder, and the players were the development team (pilot throughout this subsection).

- Presses. Landed-chord target peaks had block medians of 84 to 120 counts (1.6 to 2.3 N) and normalised presses of 0.97 to 1.74 times the calibration gap; 6 of 31 target presses in one block reached 2.5 times the gap (over_force), none in the other blocks. Calibration gaps ran 50 to 139 counts across fingers and blocks.
- Timing. For two- and three-finger chords (n = 40), span median 82 ms (IQR 22.5 to 131); 57 percent at or under 100 ms, 78 percent at or under 150 ms, 85 percent at or under 250 ms. Quad spans had a median of 188 ms (n = 13). First-press RT medians by size were 496 ms (one finger, n = 7), 491 ms (two, n = 23), 535 ms (three, n = 14) and 589 ms (four, n = 13); completion medians 496, 554, 767 and 823 ms. The lowest-lane target (the finger whose tone plays) was among the first presses in 42 percent of chords against 44 percent by chance.
- ER. Median 0.045 over 40 two- and three-finger chords (IQR 0.027 to 0.096).
- Rest floor on the engine's own method. In the one block with long rests (P669), the peak of raw minus baseline over 1.0 s windows with no press had a median of 1.1 to 1.4 counts per pad (90th percentile 2.4 to 3.7; 125 windows), and over 3.2 s windows 1.4 to 1.8. The notebook's look-back form gives 2 counts at both lengths because its look-back median is a whole count.
- Where the ER numerator comes from. Of the 67 positive quiet-finger peaks in landed chords and singles, 55 (82 percent) came before the first target finger crossed its trigger, a median 0.31 s before it. The quiet fingers' raw-minus-baseline level in the 200 ms before the stimulus had a median of +1.8 counts, and the engine's quiet-finger peak a median of 5.4 counts; measured instead from the level in the 200 ms before the stimulus, the peak's median was 2.4 counts.
- What the quiet fingers do during the chord. Mean level over the 200 ms hold minus the 250 ms look-back, per quiet finger: median -2.0 counts over all 80 instances; +0.8 in singles (n = 21; 33 percent above +2 counts); -3.1 in pairs (n = 46; 57 percent below -2); -4.4 in triples (n = 13; 85 percent below -2); -7.1 for a quiet finger enclosed by two pressing neighbours (n = 5). Aligned to the first target onset, quiet fingers next to a pressing finger fell to a median of about -4 counts from 0.25 s after it (non-neighbours about -1 to -3), with no positive transient on average. The fall did not scale with the summed target force (Spearman rho 0.06, n = 59).

What follows. On this rig at light presses, a quiet finger on average unloads while its neighbours press, rather than being pulled down. The registered ER, a positive peak over the whole window against a slow baseline, is mostly built from level differences in the second before the press. Three explanations fit the unloading, and the pilot cannot separate them: a postural shift of the resting hand, active lifting or bracing of the quiet fingers (the wrong-press rule rewards it), and cross-talk through the frame. The last is less likely because the fall does not grow with force, but `scripts/pad_bench.py` has not yet been run on the study pads. These data come from one to four developers under an older deal, so they set a direction for the analysis, not a finding about people.

---

## 2. Research questions and findings

### Q1. How large is healthy enslaving at the forces the study uses? (C1)

- Adjacent finger pairs, 25 percent of the pair's MVC, seven young adults on Nano-17 sensors zeroed at rest: the non-instructed pair's share of total force (E) was about 8 to 10 percent at 4 s and 12 to 17 percent by 19 s; the non-instructed fingers started at 2.7 to 2.8 percent MVC (Abolins et al. 2020, Methods and Results, "Changes in enslaving" [FT]). As a per-finger ratio of quiet to pressing force, E of 0.08 to 0.10 is 0.087 to 0.111 (arithmetic, E/(1 - E)).
- Index and ring pressing with the middle finger enclosed, 20 percent MVC of total force, 14 young adults on load cells read by an Arduino: master 15.6 and non-instructed 4.1 percent MVC at 5 s, E 0.208 rising to 0.233 over 12 s (0.183 to 0.256 over 60 s) (Abolins, Bernans and Latash 2026, Results [FT]); a per-finger ratio of 0.26 (arithmetic). Feedback showed total force, which may have raised the non-instructed share.
- One finger at low absolute force: index held at 4, 6 and 8 N (static phase), ten non-musicians aged 22 to 30, rest level zeroed: middle 6.5, 9.5 and 9.2 percent of the index force (SD about 5), ring 3.6 to 4.5, little 2.4 to 3.2 (Mirakhorlo, Maas and Veeger 2017, Table 3 [FT]).
- Peak-on-peak slopes at 25, 50 and 75 percent MVF: 0.028 N per N per finger pair in nine healthy professional musicians (Sadnicka et al. 2024, Results [FT]). Older controls (mean 64 years) at 20 to 80 percent MVF: 0.087 (SD 0.046) N of RMS deviation over all uninstructed fingers per N (Xu et al. 2017, Results [FT]).
- At MVC the non-instructed fingers can reach 67.5 percent of their own maximum (Zatsiorsky et al. 2000 [ABS]); in index MVC, middle 13, ring 4 and little 5 percent of their own MVC (Danion et al. 2001, Results [FT]).
- Force dependence. Enslaving grows with instructed force (Slobounov et al. 2002, Brain Res [ABS]; Xu et al. 2017, near linear [FT]; Sadnicka et al. 2024, near linear [FT]); across 4 to 8 N the ratio moved little (Mirakhorlo 2017 Table 3, force-level effect p = 0.043 [FT]). The low end is disputed: one finger's distal flexor could not be driven focally above 2.5 percent MVC (Kilbreath and Gandevia 1994, EMG [ABS]); motor units of other fingers' compartments recruited below 10 percent MVC mostly for adjacent digits, more on the ulnar side (van Duinen and Gandevia 2011, Figure 4 and text [FT]); in movement, each finger had a range of 13 to 61 percent of its travel before other fingers moved, while force enslaving is described as starting with the instructed force, with no independent range (van den Noort et al. 2016, Results and Discussion [FT]); slave-finger activation lagged more at lower force levels (Slobounov 2002 [ABS]).
- The study's presses: 1.6 to 2.3 N (pilot medians) against young men's single-finger flexion MVC of 40, 30, 26 and 17 N for index to little (Park and Xu 2017, Results [FT]) are about 4 to 14 percent MVC (arithmetic); women's lower MVC puts them higher. If enslaving scaled down in proportion, a quiet neighbour would carry about 0.03 to 0.10 of the press, 2 to 12 counts (arithmetic from the ratios above).

Where sources disagree: force enslaving is described as proportional from zero (van den Noort's reading of earlier force work; Xu; Sadnicka), while EMG and movement studies show a low-force range with little or no spill (Kilbreath; van den Noort's kinematics).

Bearing: the only published healthy values are at 10 to 100 percent MVC and several times the device's forces; none is a light-force norm. At the study's presses the expected leak is a few counts, the size of the pad's floor and of the pre-stimulus offsets (Section 1.7). C1 passes on noise and is a feasibility check, as the design already says.

### Q2. What does the device's ER read at those forces? (C1, T4)

- Pilot (Section 1.7): 82 percent of the positive quiet-finger peaks precede the press; during the hold quiet fingers sit 2 to 4 counts below their pre-stimulus level; the engine's ER (median 0.045) is mostly pre-press level differences against a baseline with a 10 s time constant.
- Negative forces in non-instructed fingers are not new: non-instructed digits produced both flexion and extension forces (Reilly and Hammond 2000 [ABS]); non-neighbours showed negative enslaving in a moving-finger task (little in the middle-finger task -0.08 to -0.16 N/rad; Kim et al. 2008, Table 1 [FT]); single-finger tasks can involve negative commands to other fingers (Reschechtko et al. 2014 [META], reported in Abolins et al. 2026, Discussion [FT]).
- Method in the literature: forces zeroed at rest at the start of each trial (Abolins 2020, Procedure [FT]; Xu 2017, baseline at the go cue [FT]; Sadnicka 2024, resting baseline at trial start [FT]; Mirakhorlo 2017, resting position set to zero [FT]), fingers told never to lift off (Abolins 2020 [FT]), steady-state means (Abolins; Mirakhorlo) or regression slopes over trials (Xu; Sadnicka; Park and Xu). The notebook's own force chapter already zeroes presses on the 250 ms before the cue (`lookback_baseline`, `true_press_force`; analysis_methods.md Section 3).
- A hand supported on a palm rest or strapped at the wrist is the norm in those set-ups (Xu 2017, wrists strapped; Park and Xu 2017, palm on a wooden cylinder; Wilhelm et al. 2014, palm on foam [FT]); the run sheet asks only for a flat forearm.

Bearing: the registered ER is not a measure of enslaving at the study's forces. A press-locked measure zeroed at the stimulus, signed, on the hold (Recommendation 1) is closer to the literature and shows what the quiet fingers actually do. Between-person differences in ER will carry pad placement, resting behaviour and the per-finger gaps, which stay fixed within a sitting.

### Q3. Adjacency, enclosed quiet fingers and the difficulty rank D (C2)

- Neighbours carry the most leak: in force at MVC (Zatsiorsky 2000 [ABS]; Danion 2001 [FT]), at 4 to 8 N (Mirakhorlo 2017 [FT]), with a moving finger (Kim 2008, Results 3.3 [FT]) and in submaximal force (Slobounov 2002 [ABS]).
- Enclosed quiet finger: the index-ring pair with the middle enclosed gave E of about 0.21 at 20 percent MVC (Abolins 2026 [FT]) against 0.08 to 0.10 for adjacent pairs at 25 percent (Abolins 2020 [FT]); different studies, sensors and feedback.
- Chord timing and errors: the Chord Complexity Index (CCI, the count of neighbours moving differently) slowed chords of equal size in naive right-hand players: three adjacent fingers 728 ms against a gap in the middle 903 ms in block 1 (671 against 782 ms in block 8); adjacent pairs 673 against alternating pairs 785 ms in block 1, not significant by block 8; index or little alone 509 against middle or ring alone 553 ms in block 1, gone by block 8 (Verwey 2023, Table 1 [FT]). After 680 practice trials per chord (Seibel's 31 right-hand chords), RT = 4.67 x CCI + 13.6 x fingers + 264.4 ms and errors (percent) = 1.60 x CCI + 2.77 x fingers - 3.90 (Verwey 2023, Appendix C [FT]; Seibel 1962 [META]).
- D against CCI over the 11 chords: Spearman rho 0.75 (0.78 without the quad) (arithmetic). The two orderings agree that IR and MP are hardest among pairs and that IRP and IMP are harder than IMR and MRP.
- Power of C2's hit half: with 2 to 4 trials per chord type per person, pooled over the cohort, the half passes in 22 percent (n = 10) or 38 percent (n = 20) of simulated cohorts when the true hit rate falls 0.11 across the D range, and in 64 and 89 percent when it falls 0.22 (simulation).
- Pilot: rho(D, median ER) +0.23 over 9 chord types, rho(D, hit rate) -0.39 over 11 (pilot; the ER medians rest on 1 to 10 trials a type).

Bearing: D is well founded as a ladder and matches Verwey's CCI; the hit half of C2 tests a timing effect with modest power. The ER half would test adjacency only if leak were measurable, and on the pilot the enclosed fingers unload most (Section 1.7), so its direction on this rig is uncertain.

### Q4. Which finger is the most enslaved, and in which sense? (C3)

- Movement, right hand, ten adults: individuation index 0.982 for the index finger, 0.937 middle, 0.907 ring, 0.943 little; stationarity index (how still a finger stays while others move, the column sense) 0.967, 0.941, 0.908, 0.943; the ring had the lowest individuation index in nine of ten right hands (Hager-Ross and Schieber 2000, Tables 1 and 2, Results [FT]). The ring also moved most when others moved in van den Noort et al. 2016 (Results [FT]).
- Force at MVC, 22 right-handed men: summing the off-diagonal forces each finger produced when the others were instructed gives index 3.2, middle 4.0, ring 5.4 and little 4.0 N (arithmetic from Table 1; Table 2 is printed in the opposite orientation and gives the same order) (Wilhelm et al. 2014 [FT]).
- The instructed-finger sense (the row): the ring as the task finger produced the most enslaving in flexion ramps (EN_I, EN_M below EN_L below EN_R; Park and Xu 2017, Results [FT]); non-instructed force rose from thumb to index, middle, ring and little as the instructed digit (Reilly and Hammond 2000 [ABS]). Chiang 2004 and Slobounov 2002 call the ring the "most enslaved" finger in this instructed sense [ABS].
- One instructed finger only: the neighbour of the pressing finger carries the most (Kim 2008 [FT]; Mirakhorlo 2017, middle for an index press [FT]).
- Normalisation: each quiet finger's leak is divided by its own calibration gap. Under zero enslaving, the column with the smallest gap wins; in the seven pilot calibration profiles the ring had the smallest gap in three, and the index had the largest mean of 1/gap (arithmetic).

Bearing: C3's direction is supported in the movement literature and for force at MVC; the design's cited "Chiang: ring most enslaved" is the other sense. At the study's forces the column means will be decided mostly by noise, the look-back offset and 1/gap. Keep C3, but decide it (or print it beside) on the press-locked measure and the counts basis, and show the singles matrix, where positive leak was commoner on the pilot.

### Q5. Which published index does ER correspond to?

- Hager-Ross and Schieber (movement): individuation index 1 minus the mean relative-motion slope of the non-instructed digits; stationarity index the same by column [FT].
- Zatsiorsky, Danion and colleagues (force at MVC): non-instructed force as a percentage of that finger's own MVC (Danion 2001, Methods [FT]); neural-network connection matrices (Wilhelm 2014, Methods [FT]); ramp-based matrices, forces regressed on total force (Park and Xu 2017; Wu et al. 2013, Methods [FT]).
- Abolins (steady state): E = non-instructed force over total force, 500 ms means [FT].
- Xu 2017: minus the log of the slope, through the origin and fitted with outlier-resistant regression, of the RMS deviation of all uninstructed fingers on instructed force across four force levels [FT]. Sadnicka 2024: the same slope per finger pair, peak on peak, baseline taken at trial start [FT].
- The device's ER: mean normalised quiet peak over mean normalised target peak, from stimulus to close, against a slow EMA baseline, positive part only, at one light force, in chords. Its shape is closest to Sadnicka's per-pair peak ratio (and to 1 minus the individuation index), but it differs in normalisation (a light-press gap, not newtons or MVC), baseline (slow EMA, not a trial-start zero), window (it includes the second before the press), sign (clamped), force range (one level, so a ratio rather than a slope) and task (chord-conditioned).

Bearing: quote ER as the device's own index; name its differences whenever a literature value appears beside it.

### Q6. How synchronous are healthy chords, and is W = 150 ms right?

- Verwey 2023 [FT, Task and Data analyses, Errors]: a chord counted as timed correctly only when its first and last key fell within 50 ms, with a "timing error" message after each miss. Error rates (timing and wrong keys together) for the right-hand group in block 1 were 0.5, 10.1 and 34.4 percent for one, two and three keys, and 0.7, 4.0 and 8.5 percent in block 8; 32 students, PS/2 keys, visual cue.
- Ghavampour et al. 2025 [FT, preprint version: Methods, Results]: after five days of practice, the mean absolute spread between the fastest and slowest finger in four-finger isometric chords (flexion and extension) was 78 ms (SEM 21) for trained and 121 ms (SEM 32) for untrained chords; on day 1 some chords succeeded in only 61 percent of trials with 10 s allowed.
- Waters-Metenier et al. 2014 [FT, configuration task, Results]: attempted de novo, difficult configurations were built by adjusting the fingers one after another; after four days they were produced as a unit.
- Pianists: about 30 ms of melody lead at hammer impact, near zero at the finger-key level (Goebl 2001 [ABS]).
- Pilot: two- and three-finger spans median 82 ms, 78 percent at or under 150 ms (Section 1.7). Onsets come in steps of about 20 ms on a bursting board, and each finger's onset is its own threshold crossing (30 percent of its gap), so spans also carry per-finger threshold differences (code).

Bearing: W = 150 ms is three times Verwey's criterion and close to the untrained spread after days of practice in a harder task, so it separates chords from sequential presses without demanding practised synchrony. The clean-hit rate is mostly a synchrony rate with force and hold rules on top (Q8). Keep W.

### Q7. The chord cost: how big, and on which RT? (C6)

- Verwey 2023 [FT, Data analyses; Results]: chord RT is the mean of the key times, for chords within 50 ms. Test phase: 510, 632 and 762 ms for one, two and three keys (both groups, practised and novel chords); block 8: 466, 571 and 652 ms; right-hand group, CCI-2 chords, block 1: 484, 664 and 754 ms. The number-of-fingers effect shrank with practice but stayed.
- Seibel 1962 after 680 trials per chord: 13.6 ms per finger (Verwey Appendix C [FT]).
- Pilot first press: 496, 491 and 535 ms for one, two and three fingers, about 20 ms per finger (arithmetic); completion 496, 554 and 767 ms, about 136 ms per finger (arithmetic). The singles were cold probes of an older design.
- Power (simulation; 8 singles and 10 triples per person; within-person RT SD 150 ms): at a true 15 ms per finger C6 passes in 19 percent of cohorts at n = 10 and 34 percent at n = 20 (alpha 0.05), at 30 ms in 51 and 81 percent, at 60 ms in 95 and 100 percent; at Holm's first threshold (0.05/8) the 30 ms figures fall to 16 and 46 percent.
- Cue: singles get one motor and the finger's own tone, chords two or three motors and the lowest lane's tone; identifying more filled positions takes longer (Verwey Discussion [FT]). Direction comparable, size not (`modes-review.md`).

Bearing: C6 as registered reads a quantity Verwey did not measure. When fingers need not wait for each other, the first press can stay early while the chord takes longer to complete; the pilot shows exactly that. The mean onset time is Verwey's measure and the one to register; the first press stays as a sensitivity row.

### Q8. Instructions, speed and what the clean-hit rate measures

- Two paradigms. Individuation tasks tell the participant to keep the other fingers still (Xu 2017 [FT]; Waters-Metenier 2014, passive fingers within resting range [FT]; Kamara et al. preprint, uninstructed fingers within 5 percent MVF [FT]; Lang and Schieber 2004 [ABS]). Enslaving tasks tell them to ignore the other fingers and never lift one off its sensor (Abolins 2020 [FT]; Park and Xu 2017 [FT]; Wu 2013 [FT]).
- Speed: externally paced 3 Hz movements were less individuated than self-paced ones at about 2 Hz (Hager-Ross and Schieber 2000, Figure 5 and text [FT]). In the configuration task, faster execution came with better synchrony, not a trade-off (Waters-Metenier 2014 [FT]).
- Vision of the hand raised individuation and stationarity slightly (Johansson et al. 2021, Results [FT]).
- Device: no on-screen instruction beyond "Press keys together"; the wrong-press rule and the quiet points reward stillness; nothing forbids lifting (code). The clean-hit rate combines timing (W), force (over 2.5 times the gap), leak and hold, in that order of precedence (code).

Bearing: add one line that sets the individuation instruction and keeps the fingers on the pads (Recommendation 3). Report a timing-only clean rate beside the registered one (Recommendation 7).

### Q9. Force level and over-force

- Enslaving scales with instructed force (Q1), so at the floor ER falls as presses get firmer: a player who presses harder gets a lower ER with no change in individuation (arithmetic from the definition).
- Over-force has no literature value; it is a design threshold relative to the light calibration press. The calibration's target band for a pad with 1.1 counts of noise and 10 counts of preload runs 22 to 88 counts (0.43 to 1.72 N) (arithmetic from `target_gap_band`), so a player who calibrates near the bottom and plays at a typing force passes 2.5 times the gap. On the pilot 6 of 31 target presses in one block did (pilot).
- Over-force outranks late and no-hold in the class order (code), so firm presses cost clean hits whatever the timing.

Bearing: report press level with ER, and ER against press level per person; keep over_force as a recorded class, and report a clean rate that ignores it.

### Q10. Reliability of enslaving, individuation and chord timing (T4, T5)

- MVC-based total enslaving, 11 right-handed men retested after two months: ICC 0.918 for the right (dominant) hand (SEM 0.031, minimum difference 0.087) and 0.548 for the left (SEM 0.066, minimum difference 0.184); mean changes -0.005 and -0.028 (Wilhelm et al. 2014, Table 4 [FT]).
- Force individuation index retested, by finger in flexion: thumb 0.73, index 0.68, middle 0.48, ring 0.72, little 0.80 (Knill et al. 2025 [ABS]).
- Split-half reliability of the individuation index in controls r = 0.97 (Xu et al. 2017 [FT]); of the within-person pattern of 20 enslaving cells r = 0.945 in healthy musicians (Sadnicka et al. 2024 [FT]). Both describe consistency within one session, not test-retest.
- A control group retested four days apart without training showed no significant change in individuation (right-hand flexion 2.51 to 2.63) or synchronisation (-39 ms) (Kamara et al. preprint, control experiment [FT]).
- No test-retest study of within-hand chord onset spread was found.
- Simulation for this design (pilot within-person spread of a block median; pass shift SD 0.005 for ER and a -10 ms practice shift with SD 10 ms for span): T4's ICC(2,1) has a median of 0.19, 0.49 or 0.79 at n = 10 when the between-person SD of median ER is 0.005, 0.01 or 0.02 (5th percentiles -0.39, -0.04, 0.48); T5's median is 0.57, 0.78 or 0.88 when the between-person SD of median span is 25, 40 or 60 ms (5th percentiles 0.12, 0.45, 0.68) (simulation). The pilot cannot say which spread applies.

Bearing: T4's "moderate" is one plausible outcome among several; a good ICC would mostly show that pad placement, resting behaviour and a shared calibration are stable within a sitting. T5's "good" is plausible if students differ by 40 ms or more in median span; the absolute-agreement form also pays for the practice shift.

### Q11. Learning within a session, and pass 2 against pass 1 (W4)

- Chord timing improves with practice: RT fell across Verwey's eight blocks of 180 trials, with the largest block 1 to 2 drop for two- and three-key chords, and errors fell from 15.0 to 4.4 percent in the right-hand group (Verwey 2023 [FT]). Configurations became faster and more synchronous within and across days (Waters-Metenier 2014; Ghavampour 2025; Kamara preprint [FT]).
- Enslaving moves with practice in either direction: the enslaving index rose from 0.81 to 0.95 in young adults after about an hour of two-finger force practice (Wu et al. 2013, Results [FT]); it rose with accuracy-only practice over 12 sessions and fell only with feedback on independence (Chiang 2004 [ABS]); individuation improved over three days of chord training (Kamara preprint: 2.36 to 2.65 in flexion [FT]); within a single hold, enslaving drifts up (Abolins 2020 [FT]). Controls' individuation index stayed level over a year (Xu 2017 [FT]).
- Force Pilot's maximal presses sit just before pass 1's Chords block and not pass 2's (code).

Bearing: pass 2 should show shorter spans and faster RTs; the direction of any ER change over 20 trials has no support, so W4's ER half is a guess and its hit-rate half carries the prediction. The pass 2 minus pass 1 shift in T4 and T5 mixes practice with the absence of maximal presses beforehand.

### Q12. Handedness, sex and musical training

- No dominant against non-dominant difference in individuation (Hager-Ross and Schieber 2000, hand effect F = 0.6, p > 0.80, only the thumb differed [FT]; Reilly and Hammond 2000, 2004, 2006 [ABS]; Johansson et al. 2021 [FT]) or in total enslaving (Wilhelm et al. 2014: 19.7 against 21.0 percent, p = 0.229 [FT]). About 2 percent more enslaving in the non-dominant hand was found only with the little finger left out (Li et al. 2000 [META], reported in Wilhelm 2014 Discussion [FT]). The non-dominant hand's index retested less well (ICC 0.55 against 0.92; Wilhelm [FT]).
- Sex: enslaving at MVC was smaller in women and larger in people with higher peak force (Shinohara et al. 2003 [ABS]); women moved their fingers marginally more independently (Johansson 2021 [FT]).
- Musical training: musicians showed less enslaving (Slobounov et al. 2002, Clin Neurophysiol 113(12) [ABS]); pianists' middle and ring fingers reach the individuation of non-musicians' thumb and index (Xu, Mawase and Schieber 2024, Section 7.1 [FT]); studies exclude or separate musicians (Mirakhorlo 2017 [FT]; Kamara preprint [FT]).

Bearing: left-handers on the right hand should not differ in ER or span; the right-handers-only rerun (design doc Section 4.9) stays a sensitivity check. Sex and musical training are the between-person factors with published effects; musical training is not collected.

### Q13. Holds, drift and fatigue

- Holds in the literature: 0.5 s (Xu 2017 [FT]; Waters-Metenier 2014 [FT]), 0.6 s (Ghavampour 2025 [FT]), 2 to 3 s (Sadnicka 2024 [FT]), 12 to 60 s in drift studies (Abolins 2020, 2026 [FT]).
- Drift: about 49 percent over 15 s (Abolins 2020 [FT]), or a few percent of that over 0.2 to 0.5 s if linear (arithmetic).
- Fatigue: 60 s of maximal four-finger effort cut four-finger MVC by 43 percent, left enslaving unchanged at the fatigued site and raised it at the other site (Danion 2000 [ABS]); a fatigued index was enslaved less (Danion 2001 [FT]). The battery's 40 light presses with a 30 s rest are far from either protocol.

Bearing: 200 ms is fine for the timing measures; a longer hold would give a steadier leak mean at no drift cost (after collection). The fatigue guard and the start-to-end "fatigue read" have no role in the battery; their rationale should drop the claim that fatigue inflates enslaving.

### Q14. What the healthy study can say about rehabilitation

- Stroke reduces individuation, most in the middle, ring and little fingers (Lang and Schieber 2003 [ABS]), with less selective muscle activation (Lang and Schieber 2004 [ABS]) and higher enslaving (Li et al. 2003 [ABS]); individuation recovers partly apart from strength (Xu 2017, 54 patients [FT]) and is the last function to return (Xu 2024, Section 8 [FT]).
- Training evidence is small: key-combination play with an actuated glove, 7 people a group (Thielbar 2014 [FT]); 322 repetitions a session are feasible (Birkenmeier 2010 [FT]).

Bearing: nothing in a healthy sitting at light forces shows sensitivity to impaired individuation; a stroke hand's leak may clear the floor that a healthy hand's does not, which is a question for later work.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Chord set | 11 chords plus 4 singles, every one-to-four finger combination (`CHORD_TIERS` 437-442, 505) | Complete set; D matches Verwey's CCI (rho 0.75) (Q3) | Keep |
| Difficulty rank D | weights I 1, M 2, R 3, P 2; adjacency; 1.5 per finger above two (405-426) | Weights track the stationarity index (Q4); size effect on timing supported (Verwey, Seibel), not on leak | Keep as an analysis rank; add CCI as a sensitivity |
| Size mix | 4/10/5/1 per 20 (512) | Per-type counts 0 to 8 a block (simulation) | Keep |
| Deal randomisation | fresh seed each block (1117) | The battery already fixes Echo's material so everyone meets the same items (design doc, 1 October 2026); chord-mix noise is small (simulation, Section 7) | Change (optional): fixed battery seed |
| Quiet gate | 500 ms, press state only (1380-1450) | 500 ms steady-rest gate with a force band in Waters-Metenier [FT]; pilot pre-stimulus offsets median 1.8 counts | Keep; zero each trial in the analysis; force band after collection |
| Stimulus channels | tiles, up to 3 motors together, lowest-lane tone, loud every tenth | Tone finger does not lead (pilot 42 against 44 percent) | Keep; check press order in the analysis |
| Quad cue | arpeggio, last pulse at 570 ms (code) | Different cue; pilot quad spans median 188 ms | Keep; exclude from span and clean-rate sensitivity rows |
| Onset criterion | 30 percent of each finger's gap, EMA 0.35, 100 ms debounce | Standard threshold practice; spans carry per-finger threshold differences | Keep; state it |
| Synchrony window | W = 150 ms, one rung | Three times Verwey's 50 ms; near Ghavampour's untrained spread (Q6) | Keep |
| Timeout | 3.0 s | Landed chords complete in about 0.5 to 0.9 s (pilot) | Keep |
| Hold | 200 ms | Literature holds 0.5 to 3 s; drift negligible at 0.5 s (Q13) | Keep; 500 ms after collection |
| ER definition | positive peak over stimulus to close, slow EMA baseline, normalised by gap (1645-1725) | 82 percent of peaks before the press; quiet fingers unload (pilot); literature zeroes per trial and uses steady means or slopes (Q2, Q5) | Keep as registered; add press-locked measures now; re-register after approval |
| Normaliser | calibration light-press gap per finger | Literature uses newtons or percent MVC; gap mixes press habits into ER (Q4, Q9) | Keep; add a counts (newton) basis |
| Leak-fail ratio | 0.25 of mean press (728) | 2 to 8 times healthy per-finger ratios at moderate force (Q1) | Keep |
| Over-force | 2.5 times the gap on any finger, above late in precedence (732, 1736) | No literature value; pilot 6 of 31 in one block | Keep; add a timing-only clean rate |
| Quiet points | full at ER 0, zero at 0.5 (724) | Healthy ER sits at the floor | Keep |
| Instructions | "Press keys together" only | Individuation tasks instruct stillness; enslaving tasks forbid lifting (Q8) | Add one line |
| Feedback | tile flash, quiet-finger tick, hold ring | Independence feedback lowers enslaving over sessions (Chiang [ABS]) | Keep |
| Staircase and fatigue guard | frozen; inert | Fatigue does not inflate enslaving (Q13) | Keep; correct the rationale |
| Start and end matrices | first and last sub-block | 20 trials apart; not a fatigue read | Keep as description |
| Short form | 2 x 20, both passes | Per-chord cells cohort-pooled | Keep |
| Position after Force Pilot | always; pass 1 after maximal presses | A pass-order confound for T4 and T5 shifts (Q11) | Keep; state it |
| C1 | cohort median ER under 0.15 | Passes on noise (Q1, Q2) | Keep as a feasibility check; reword |
| C2 | hit and ER halves against D | Hit half: a timing effect, modest power; ER half: not measurable here (Q3) | Change: ER half exploratory |
| C3 | ring column largest | Direction supported at MVC and in movement; at these forces decided by noise and 1/gap (Q4) | Change: exploratory, or decide on the press-locked measure |
| C6 | first-press slope | Verwey measured mean key time; pilot first press about 20 ms per finger (Q7) | Change: mean onset |
| W4 | ER down and hit rate up | ER direction unsupported at this scale (Q11) | Change: hit-rate half decides |
| T4 | predicted moderate | 0.19 to 0.79 depending on an unknown spread (simulation) | Keep reported; reword |
| T5 | predicted good | 0.57 to 0.88 (simulation) | Keep; note the practice shift |
| Pad cross-talk | not measured | Needed to read quiet-finger changes as the hand's | Add: bench before collection |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

No SAFE-NOW item changes the task. Items 3 and 8 touch the game code (one screen line; new record fields). The only task changes proposed are in item 14, after collection.

1. **Measure the quiet fingers locked to the press, zeroed at the stimulus, with their sign.** SAFE-NOW (new analysis rows only; no registered measure changes).
   In notebook cell 2 add `chord_quiet_levels(folder, rows)` beside `chord_rest_peaks` (12115). For each landed within-hand chord and single, from `raw.csv`: the stimulus time (first `stim` event per `trial_id`, as `chord_spans_on_grid` 21033 does), the first and last target press times, and the close (last onset plus 0.2 s for a hit). Zero each lane on `lookback_baseline` over the 250 ms before the stimulus (4639; `DRIFT_LOOKBACK_SAMPLES` 4901). Per quiet lane, take the signed mean over the hold and the peak from 50 ms before the first onset to the close; per target lane, the hold mean. From these: `er_hold` (mean of the positive quiet hold levels over the mean target hold level, on the counts basis and on the gap basis), `quiet_hold_median_counts`, and the shares of quiet fingers below -2 and above +2 counts. Carry them into `chord_frame` (12169), emit them from `_cohort_chords` (21092) under an exploratory label, draw a quiet-finger trace aligned to the first onset (neighbours and non-neighbours) in `sec_chords` (12395), and print C1, C2's ER half and C3 on this basis in `sec_chords_checks` (27253). Set `CHORD_REST_WIN_S` (12108) to the landed-chord window (about 1 s) or compute the floor per trial length. Evidence: Section 1.7 (pilot); per-trial zeroing and steady-state or slope measures in Xu 2017, Sadnicka 2024, Abolins 2020, Mirakhorlo 2017 [FT].

2. **Say plainly what ER measures at the study's forces.** SAFE-NOW (text only).
   - `chords.py` 9-15 and CROSS-TALK SCORE (119-133): Abolins' 8 to 10 percent is the non-instructed pair's share of total force at 25 percent of the pair's MVC (J Neurophysiol 124(6):1625-1636); the device's presses are about 4 to 14 percent of single-finger MVC; at those forces the quiet fingers unloaded on the pilot and ER's peaks mostly preceded the press.
   - Design doc Section 1.3 C1 and Section 1.12: drop "strong for a healthy cohort" for C1 to C3; the chord window is about 1 s, not 3.2 s.
   - Notebook: `MODE_LIT["chords"]` C1 (25949; journal, figure, force level), `HEALTHY_ER_BAND` comment (118), `MODE_CLAIM_LIMITS["chords"]` (26544; window, pre-press peaks, unloading), and the `sec_chords` anchor text (Xu's controls were 64 years old; 0.087 is an RMS deviation over all uninstructed fingers per newton at 20 to 80 percent MVF).

3. **One instruction line for Chords.** SAFE-NOW (UX; log it in the design doc because it changes what participants are told).
   Add `"chords": ("Press the lit fingers together and hold until the ring fills.", "Keep the other fingers resting still on their pads.")` to `GameplayScreen.GET_READY_LINES` (`screens.py` 3738), and a Chords line in the run sheet's first-time list ("The first time Reaction, Rhythm and Echo come up"): "Press the lit fingers together and hold till the ring fills. Keep the others resting on their pads, as light as in the calibration." Evidence: individuation tasks instruct stillness and enslaving tasks forbid lifting (Q8 [FT]); none is given now (code).

4. **Run the pad bench for cross-talk before collection.** SAFE-NOW (procedure).
   Run `scripts/pad_bench.py --characterise` on the study pad set and keep its cross-talk matrix beside the Chords results. If loading one pad moves its neighbours by amounts comparable to the pilot's quiet-finger changes (2 to 4 counts at 80 to 100 counts of press), the quiet-finger measures cannot be read as the hand's. Evidence: Section 1.7 (the unloading did not scale with force, rho 0.06, which points away from cross-talk but does not exclude it).

5. **Read C6 on the mean onset time.** DESIGN-CHANGE (the registered metric), with SAFE-NOW logging and a sensitivity row now.
   SAFE-NOW: in `ChordsMode._finish` add `mean_onset_ms` (mean of the target onsets minus the stimulus) to the trial record (1873-1934), and `median_mean_onset_ms` to `by_size` in `block_stats` (2310-2336); in the notebook give `chord_cost_per_finger` (21200) a basis argument (first, mean, last onset), emit `chord_cost_mean_onset_ms` in `_cohort_chords`, and leave wrong-press trials out of the size table's RTs. DESIGN-CHANGE: C6 decided on the mean onset (design doc Section 1.3 and Table 1; the C6 row, 24824), the first press kept as the sensitivity row. Evidence: Verwey's RT is the mean key time within a 50 ms criterion [FT]; pilot first press about 20 ms per finger against 136 ms for completion (pilot); C6 power falls to 19 to 51 percent at 15 to 30 ms per finger at n = 10 (simulation).

6. **Move C2's ER half, C3 and W4's ER half to the exploratory heading, or decide them on the press-locked measure.** DESIGN-CHANGE (pre-registered rows; log with date).
   Design doc Sections 1.3, 4.4 (two-part checks) and 4.6 (Tables 1 and 2); notebook: decide C2 on its hit-rate half and print the ER half as exploratory (the C2 row near 24741; `chord_c2_halves`), move C3 (`_chords_c3_row` 24317) under the exploratory heading with the counts-basis and press-locked versions and the singles matrix, and decide W4 (`_chords_w4_row` 24362) on the clean hit rate with the ER half reported. Evidence: Q2 to Q4, Q11; Section 1.7.

7. **Report a timing-only clean rate, and set the quad aside in sensitivity rows.** SAFE-NOW (analysis).
   In `_cohort_chords` add `timing_clean_rate` (two- and three-finger chords fully landed, no wrong press, span within the trial's W) from `chord_block_records` (12283), and `median_span_ms_no_quad`; print both beside the registered clean rate and span in `sec_chords`. Evidence: over-force outranks timing (code; pilot 6 of 31 in one block); the quad's cue runs to 570 ms (code) and its pilot spans had a median of 188 ms against 82 ms.

8. **Log the pre-stimulus level and the hold-end level per lane.** SAFE-NOW (new record fields; no measure changes).
   In `ChordsMode._fire` (1495-1535) read each lane's detector `val_ema` into the pending trial; in `_finish` read it again and store `pre_levels` and `hold_end_deltas` (counts) in the record, with the first-pressing finger. The notebook then has a signed quiet-finger change without reprocessing `raw.csv`. Evidence: Section 1.7.

9. **Report T4 and T5 against their real range.** DESIGN-CHANGE (text of reported predictions).
   Design doc Section 4.5c and `COHORT_RELIABILITY_METRICS` (30369-30370): T4 "moderate is one outcome among several (median ICC 0.19 to 0.79 in simulation, depending on how much students differ); a high value would mostly show that pad placement and one calibration are stable within a sitting"; T5 "moderate to good (0.57 to 0.88 in simulation), with a practice shift". Anchors: 0.92 and 0.55 for MVC-based enslaving at two months (Wilhelm [FT]); 0.48 to 0.80 for a force individuation index (Knill [ABS]).

10. **The same chord material for everyone.** DESIGN-CHANGE (battery setting; low priority).
    Add `seed: <integer>` and a per-pass rule (as Echo's `seed_follows_game_count`) to `protocol.presets.study_battery.overrides.chords` (`default.yaml` 2022-2028), so every participant meets the same 40 chords in each pass. Evidence: chord types differ by up to 175 ms in naive RT (Verwey Table 1 [FT]); per-type counts vary 0 to 8 a block; the precision gain is small (SD of the pass difference in median RT 49.0 to 46.6 ms, simulation).

11. **Add musical training to the intake.** DESIGN-CHANGE (intake form; `modes-review.md` leaves it open).
    One line on the intake sheet (years of piano, guitar or other keyboard or string instrument) and a column in `sessions/intake_sheet.csv`, used as a descriptive split for ER and span. Evidence: musicians show less enslaving (Slobounov 2002 [ABS]; Xu 2024 [FT]); studies exclude or separate them (Mirakhorlo 2017; Kamara preprint [FT]).

12. **Correct the smaller claims.** SAFE-NOW (text only).
    `chords.py` 106-108 and `default.yaml` 1070-1071 (Goebl: near zero at the finger-key level; Rasch unverified); 36-38 and 408-409 (Li 1998 is force deficit, not timing); 142-146 and 201-205 (Danion: fatigue did not inflate enslaving); 253-254 (0.30 of the gap, not 0.40); `_chord_matrix` docstring 2204-2207 and the `sec_chords` text (no upper bound under non-additivity); design doc C3 (Chiang's "most enslaved" ring is the instructed finger); `sec_chords` fatigue sentence (Danion 2000 does not show it); `ENSLAVEMENT_REF` (269; unverified, do not quote).

13. **Print sex and handedness splits.** SAFE-NOW (analysis).
    A descriptive sex split for ER and span in the cohort tables, and a note in the handedness chapter that the non-dominant hand's enslaving index retested worse (Wilhelm [FT]). Evidence: Q12.

14. **After collection: a proper individuation and chord-skill preset.** AFTER-COLLECTION (changes the task).
    Single-finger isometric holds at 20 to 40 percent MVC with the palm supported and every finger resting on its pad, zeroed at trial start, the slope through the origin per finger pair (Xu 2017; Sadnicka 2024; Park and Xu 2017 [FT]); a 500 ms hold; a force-band quiet gate; a chord block with Verwey's 50 ms timing feedback; both hands when the second board exists.

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Press-locked quiet-finger levels zeroed at the stimulus (hold mean signed, peak after the first onset), `er_hold` on counts and gap bases, unloading and leaking shares | new `chord_quiet_levels`; `chord_frame`; `_cohort_chords`; `sec_chords`; `sec_chords_checks` | Xu 2017; Sadnicka 2024; Abolins 2020; Mirakhorlo 2017 [FT]; the notebook's own look-back zero |
| Rest floor on the engine's method and the landed-chord window length | `CHORD_REST_WIN_S`, `chord_rest_peaks` | pilot |
| Quiet-finger trace aligned to the first onset, neighbours against non-neighbours | `sec_chords` | Mirakhorlo 2017 (enslaving onset timing) [FT] |
| Per-person enslaving slope: quiet hold level on target hold level across trials, through the origin, outlier-resistant, per finger pair, exploratory | `sec_chords_checks` | Xu 2017; Sadnicka 2024 [FT] |
| C6 on mean and last onset beside the first press; wrong presses out | `chord_cost_per_finger`; `_cohort_chords`; C6 row | Verwey 2023 [FT] |
| Timing-only clean rate; span and clean rate without the quad | `_cohort_chords` | Verwey 2023 [FT] |
| C2 with CCI in place of D; each person weighted once per chord type | `chord_c2_halves` and its callers | Verwey 2023 [FT] |
| C3 on the counts basis, on the press-locked measure and on the singles matrix | `_chords_c3_row` | Hager-Ross and Schieber 2000; Wilhelm 2014 [FT] |
| W4 decided on the clean hit rate, the ER half reported | `_chords_w4_row` | Q11 sources |
| Press order: does the tone's finger lead? | `sec_chords` | code (tone on the lowest lane) |
| ER against press level per person, printed beside ER | `sec_chords` | Q9 |
| T4 and T5 with the pass shift and its interval, split by order (A against B) and noting the shared calibration | `sec_cohort_reliability` | Weir 2005 [META]; code (pass 1 follows maximal presses) |
| Sex split; musical training when collected | cohort tables | Shinohara 2003 [ABS]; Johansson 2021 [FT]; Slobounov 2002 [ABS] |
| `MODE_LIT["chords"]`: add C6 (Verwey 2023; Seibel 1962), fix C1's citation and force level | 25949 | Verwey 2023; Abolins 2020 [FT] |
| `MODE_CLAIM_LIMITS["chords"]`: window length, pre-press peaks, unloading, the counts basis | 26544 | pilot |

Keep as they are: the board-clock span row (`median_span_ms_grid`), per-chord cells pooled over the cohort and never per person, the singles kept apart from every chord number, and the exact-interval ICC.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Enslaving, adjacent finger pairs, 25 percent of pair MVC | share of total force 8 to 10 percent, 12 to 17 percent after 15 s | Abolins et al. 2020 [FT] | seven people; share of total force, not a per-finger ratio; forces several times the device's |
| Enslaving with the middle finger enclosed (index and ring pressing), 20 percent MVC | non-instructed 4.1 against instructed 15.6 percent MVC; share 0.21 | Abolins et al. 2026 [FT] | feedback on total force |
| One finger at 4 to 8 N | middle 6.5 to 9.5, ring 3.6 to 4.5, little 2.4 to 3.2 percent of index force | Mirakhorlo et al. 2017 Table 3 [FT] | ten non-musicians, index only, rest zeroed |
| Peak-on-peak slope, healthy musicians | 0.028 N per N per finger pair | Sadnicka et al. 2024 [FT] | nine professional musicians aged about 41 |
| Individuation slope, older controls | 0.087 (SD 0.046), RMS over all uninstructed fingers | Xu et al. 2017 [FT] | mean age 64; 20 to 80 percent MVF |
| Movement individuation, right hand | index 0.982, middle 0.937, ring 0.907, little 0.943 | Hager-Ross and Schieber 2000 Table 1 [FT] | cyclic movement, not force |
| Single-finger flexion MVC, young men | 40, 30, 26, 17 N (index to little) | Park and Xu 2017 [FT] | nine men |
| Chord RT, one to three keys, mean key time | 510, 632, 762 ms | Verwey 2023 [FT] | after 240 practice trials per chord; visual cue; 50 ms criterion; one- and two-hand groups pooled |
| Naive chord errors, right hand, 50 ms criterion | 0.5, 10.1, 34.4 percent (one to three keys) | Verwey 2023 [FT] | timing and wrong keys together |
| Chord cost after long practice | 13.6 ms per finger, 4.67 ms per CCI unit | Seibel 1962 [META], via Verwey 2023 Appendix C [FT] | 680 trials per chord, five fingers |
| Residual finger spread after five days | 78 ms trained, 121 ms untrained | Ghavampour et al. 2025 [FT] | four-finger flexion and extension chords |
| Pianists' chord asynchrony | about 30 ms melody lead at the hammer; near zero at the finger-key level | Goebl 2001 [ABS] | experts |

How to use them: report ER, span, RT and the chord cost as the device's own, measured with light presses of about 1.6 to 2.3 N on preloaded pads, a slow-EMA baseline, per-finger light-press normalisation and an audio-tactile-visual cue. The published values frame the order of magnitude; none is a norm to test against.

### 6.2 Reliability and practice expectations

- T4 (median ER): anything from poor to good is plausible at n = 10 (median ICC 0.19 to 0.79 in simulation); a high value would mostly reflect stable pads, resting behaviour and one shared calibration. Published anchors: 0.92 (dominant) and 0.55 (non-dominant) for MVC-based enslaving over two months (Wilhelm 2014 [FT]); 0.48 to 0.80 by finger for a force individuation index (Knill 2025 [ABS]).
- T5 (median span): moderate to good (0.57 to 0.88 in simulation) if students differ by 25 to 60 ms in median span; no published test-retest for chord spread.
- Pass 2 minus pass 1: shorter spans and faster RTs expected (Verwey; Waters-Metenier; Ghavampour; Kamara [FT]); no supported direction for ER (Wu 2013 [FT] against Kamara [FT]; Chiang [ABS]); the shift also carries pass 1's preceding maximal presses.
- Split-half values (0.945 to 0.97 in the literature) say the trials of one session agree; they are not test-retest.

### 6.3 Claims to avoid

- "Healthy enslaving was measured" or "ER sits in the healthy band" as a finding: at the study's forces ER passes on noise and pre-press level differences, and quiet fingers unloaded on the pilot.
- A comparison of ER with published enslaving percentages as a norm, or Xu's 0.087 as a healthy young value.
- "The ring finger is the most enslaved" from C3, or "D predicts leak" from C2's ER half, unless the press-locked measure supports it.
- A chord cost equal to Verwey's 126 ms per finger from the first press.
- Within-session ICC as test-retest reliability of individuation.
- Fatigue from the start and end matrices, or "fatigue inflates enslaving".
- A handedness effect from left-handers' non-dominant hand.
- Anything from the quad's span or RT beside the other sizes (its buzz is an arpeggio).
- Training, rehabilitation or stroke-sensitivity claims from a healthy light-force sitting.

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, PubMed E-utilities, the NCBI ID converter, Crossref, OpenAlex, PMC and bioRxiv.

1. Abolins V, Stremoukhov A, Walter C, Latash ML. 2020. On the origin of finger enslaving: control with referent coordinates and effects of visual feedback. Journal of Neurophysiology 124(6):1625-1636. DOI 10.1152/jn.00322.2020. PMID 32997555. PMC7814910. [FT: Methods (subjects, procedure, enslaving index), Results (force drifts, changes in enslaving), Discussion]
2. Abolins V, Bernans E, Latash ML. 2026. Force production with a subset of fingers: two aspects of unintentional finger involvement. Experimental Brain Research 244(10):194. DOI 10.1007/s00221-026-07393-9. PMID 42700255. PMC13546314. [FT: Methods, Results (general performance, force drifts), Discussion including limitations]
3. Abolins V, Latash ML. 2021. The nature of finger enslaving: new results and their implications. Motor Control 25(4):680-703. DOI 10.1123/mc.2021-0044. PMID 34530403. [ABS]
4. Aoki T, Furuya S, Kinoshita H. 2005. Finger-tapping ability in male and female pianists and nonmusician controls. Motor Control 9(1):23-39. DOI 10.1123/mcj.9.1.23. [META; cited in Xu et al. 2024 for pianists' individuation]
5. Birkenmeier RL, Prager EM, Lang CE. 2010. Translating animal doses of task-specific training to people with chronic stroke in 1-hour therapy sessions: a proof-of-concept study. Neurorehabilitation and Neural Repair 24(7):620-635. DOI 10.1177/1545968310361957. PMID 20424192. PMC3235711. [FT: Abstract, Results (repetitions per session)]
6. Chiang H, Slobounov SM, Ray W. 2004. Practice-related modulations of force enslaving and cortical activity as revealed by EEG. Clinical Neurophysiology 115(5):1033-1043. DOI 10.1016/j.clinph.2003.12.019. PMID 15066527. [ABS]
7. Danion F, Latash ML, Li ZM, Zatsiorsky VM. 2000. The effect of fatigue on multifinger co-ordination in force production tasks in humans. Journal of Physiology 523(Pt 2):523-532. DOI 10.1111/j.1469-7793.2000.00523.x. PMID 10699094. [ABS]
8. Danion F, Latash ML, Li ZM, Zatsiorsky VM. 2001. The effect of a fatiguing exercise by the index finger on single- and multi-finger force production tasks. Experimental Brain Research 138(3):322-329. DOI 10.1007/s002210100698. PMID 11460770. PMC2830622. [FT: Methods (enslaving index), Results (enslaving)]
9. Ghavampour A, Emanuele M, Sayyid SR, Orban de Xivry JJ, Michaels JA, Pruszynski JA, Diedrichsen J. 2025. A paradigm to study the learning of muscle activity patterns outside of the natural repertoire. Journal of Neurophysiology 134(1):347-360. DOI 10.1152/jn.00088.2025. PMID 40549582. [FT: bioRxiv version, DOI 10.1101/2025.02.13.638098; Methods (apparatus, task), Results (success rate, residual asynchrony)]
10. Goebl W. 2001. Melody lead in piano performance: expressive device or artifact? Journal of the Acoustical Society of America 110(1):563-572. DOI 10.1121/1.1376133. PMID 11508980. [ABS]
11. Häger-Ross C, Schieber MH. 2000. Quantifying the independence of human finger movements: comparisons of digits, hands, and movement frequencies. Journal of Neuroscience 20(22):8542-8550. DOI 10.1523/JNEUROSCI.20-22-08542.2000. PMID 11069962. PMC6773164. [FT: Methods (individuation and stationarity indexes), Tables 1 to 3, dominance and frequency sections]
12. Johansson AM, Grip H, Rönnqvist L, Selling J, Boraxbekk CJ, Strong A, Häger CK. 2021. Influence of visual feedback, hand dominance and sex on individuated finger movements. Experimental Brain Research 239(6):1911-1928. DOI 10.1007/s00221-021-06100-0. PMID 33871660. PMC8277644. [FT: Abstract, Results summary, Discussion on dominance and sex]
13. Kamara G, Rajchert O, Solomonow-Avnon D, Mawase F. 2023. Generalization indicates asymmetric and interactive control networks for multi-finger dexterous movements. Cell Reports 42(3):112214. DOI 10.1016/j.celrep.2023.112214. PMID 36924500. [FT: bioRxiv version, DOI 10.1101/2022.06.07.495015; Methods (participants, task), Results (synchronisation, individuation index, control experiment)]
14. Kilbreath SL, Gandevia SC. 1994. Limited independent flexion of the thumb and fingers in human subjects. Journal of Physiology 479(Pt 3):487-497. DOI 10.1113/jphysiol.1994.sp020312. PMID 7837104. PMC1155766. [ABS]
15. Kim SW, Shim JK, Zatsiorsky VM, Latash ML. 2008. Finger inter-dependence: linking the kinetic and kinematic variables. Human Movement Science 27(3):408-422. DOI 10.1016/j.humov.2007.08.005. PMID 18255182. PMC2481561. [FT: Methods, Results 3.3 and 3.4, Table 1]
16. Knill AS, Shi S, Easthope CA, Branscheidt M, Lambercy O. 2025. Development and evaluation of a device to assess finger individuation in neurorehabilitation. IEEE International Conference on Rehabilitation Robotics 2025:450-455. DOI 10.1109/ICORR66766.2025.11063048. PMID 40644104. [ABS]
17. Lang CE, Schieber MH. 2003. Differential impairment of individuated finger movements in humans after damage to the motor cortex or the corticospinal tract. Journal of Neurophysiology 90(2):1160-1170. DOI 10.1152/jn.00130.2003. PMID 12660350. [ABS]
18. Lang CE, Schieber MH. 2004. Reduced muscle selectivity during individuated finger movements in humans after damage to the motor cortex or corticospinal tract. Journal of Neurophysiology 91(4):1722-1733. DOI 10.1152/jn.00805.2003. PMID 14668295. [ABS]
19. Lang CE, Schieber MH. 2004. Human finger independence: limitations due to passive mechanical coupling versus active neuromuscular control. Journal of Neurophysiology 92(5):2802-2810. DOI 10.1152/jn.00480.2004. PMID 15212429. [ABS]
20. Li S, Danion F, Latash ML, Li ZM, Zatsiorsky VM. 2000. Characteristics of finger force production during one- and two-hand tasks. Human Movement Science 19(6):897-923. DOI 10.1016/S0167-9457(01)00023-9. [META; content as reported in Wilhelm et al. 2014]
21. Li S, Latash ML, Yue GH, Siemionow V, Sahgal V. 2003. The effects of stroke and age on finger interaction in multi-finger force production tasks. Clinical Neurophysiology 114(9):1646-1655. DOI 10.1016/S1388-2457(03)00164-0. PMID 12948793. [ABS]
22. Li ZM, Latash ML, Zatsiorsky VM. 1998. Force sharing among fingers as a model of the redundancy problem. Experimental Brain Research 119(3):276-286. DOI 10.1007/s002210050343. PMID 9551828. [ABS]
23. Mirakhorlo M, Maas H, Veeger DHEJ. 2017. Timing and extent of finger force enslaving during a dynamic force task cannot be explained by EMG activity patterns. PLoS One 12(8):e0183145. DOI 10.1371/journal.pone.0183145. PMID 28817708. PMC5560573. [FT: Methods, Results, Table 3]
24. Park J, Xu D. 2017. Multi-finger interaction and synergies in finger flexion and extension force production. Frontiers in Human Neuroscience 11:318. DOI 10.3389/fnhum.2017.00318. PMID 28674489. PMC5474495. [FT: Methods (enslaving matrix), Results (MVC and enslaving), Figure 3 legend]
25. Rasch RA. 1979. Synchronization in performed ensemble music. Acustica 43(2):121-131. [META not found: no DOI or index record located; cited by the code, not verified]
26. Reilly KT, Hammond GR. 2000. Independence of force production by digits of the human hand. Neuroscience Letters 290(1):53-56. DOI 10.1016/S0304-3940(00)01328-8. PMID 10925173. [ABS]
27. Reilly KT, Hammond GR. 2004. Human handedness: is there a difference in the independence of the digits on the preferred and non-preferred hands? Experimental Brain Research 156(2):255-262. DOI 10.1007/s00221-003-1783-z. PMID 14712333. [ABS]
28. Reilly KT, Hammond GR. 2006. Intrinsic hand muscles and digit independence on the preferred and non-preferred hands of humans. Experimental Brain Research 173(4):564-571. DOI 10.1007/s00221-006-0397-7. PMID 16505998. [ABS]
29. Reschechtko S, Zatsiorsky VM, Latash ML. 2014. Stability of multi-finger action in different state spaces. Journal of Neurophysiology 112(12):3209-3218. DOI 10.1152/jn.00395.2014. [META; content as reported in Abolins et al. 2026]
30. Rowe JB, Chan V, Ingemanson ML, Cramer SC, Wolbrecht ET, Reinkensmeyer DJ. 2017. Robotic assistance for training finger movement using a Hebbian model: a randomized controlled trial. Neurorehabilitation and Neural Repair 31(8):769-780. DOI 10.1177/1545968317721975. [META]
31. Sadnicka A, Wiestler T, Butler K, Altenmuller E, Edwards MJ, Ejaz N, Diedrichsen J. 2024. Boundaries of task-specificity: bimanual finger dexterity is reduced in musician's dystonia. Scientific Reports 14(1):15972. DOI 10.1038/s41598-024-65888-3. PMID 38987302. PMC11237050. [FT: Results (reliability, enslaving), Methods (participants, task, quantifying enslaving)]
32. Seibel R. 1962. Performance on a five-finger chord keyboard. Journal of Applied Psychology 46(3):165-169. DOI 10.1037/h0047948. [META; content as re-analysed in Verwey 2023, Appendix C]
33. Shinohara M, Li S, Kang N, Zatsiorsky VM, Latash ML. 2003. Effects of age and gender on finger coordination in MVC and submaximal force-matching tasks. Journal of Applied Physiology 94(1):259-270. DOI 10.1152/japplphysiol.00643.2002. PMID 12391031. [ABS]
34. Slobounov S, Johnston J, Chiang H, Ray W. 2002. The role of sub-maximal force production in the enslaving phenomenon. Brain Research 954(2):212-219. DOI 10.1016/S0006-8993(02)03288-2. PMID 12414104. [ABS]
35. Slobounov S, Johnston J, Chiang H, Ray WJ. 2002. Motor-related cortical potentials accompanying enslaving effect in single versus combination of fingers force production tasks. Clinical Neurophysiology 113(9):1444-1453. DOI 10.1016/S1388-2457(02)00195-5. PMID 12169327. [ABS]
36. Slobounov S, Chiang H, Johnston J, Ray W. 2002. Modulated cortical control of individual fingers in experienced musicians: an EEG study. Clinical Neurophysiology 113(12):2013-2024. DOI 10.1016/S1388-2457(02)00298-5. PMID 12464342. [ABS]
37. Taheri H, Rowe JB, Gardner D, Chan V, Gray K, Bower C, Reinkensmeyer DJ, Wolbrecht ET. 2014. Design and preliminary evaluation of the FINGER rehabilitation robot: controlling challenge and quantifying finger individuation during musical computer game play. Journal of NeuroEngineering and Rehabilitation 11:10. DOI 10.1186/1743-0003-11-10. PMID 24495432. PMC3928667. [FT: success-rate algorithm, experimental protocol]
38. Thielbar KO, Lord TJ, Fischer HC, Lazzaro EC, Barth KC, Stoykov ME, Triandafilou KM, Kamper DG. 2014. Training finger individuation with a mechatronic-virtual reality system leads to improved fine motor control post-stroke. Journal of NeuroEngineering and Rehabilitation 11:171. DOI 10.1186/1743-0003-11-171. PMID 25542201. PMC4292811. [FT: Abstract, Methods (AVK system, key combination mode), Results]
39. van den Noort JC, van Beek N, van der Kraan T, Veeger DH, Stegeman DF, Veltink PH, Maas H. 2016. Variable and asymmetric range of enslaving: fingers can act independently over small range of flexion. PLoS One 11(12):e0168636. DOI 10.1371/journal.pone.0168636. PMID 27992598. PMC5167409. [FT: Methods, Results (enslaving, range of independent movement), Discussion]
40. van Duinen H, Gandevia SC. 2011. Constraints for control of the human hand. Journal of Physiology 589(Pt 23):5583-5593. DOI 10.1113/jphysiol.2011.217810. PMID 21986205. PMC3249034. [FT: section on central limits and linkages, Figures 4 and 5 legends]
41. Verwey WB. 2023. Chord skill: learning optimized hand postures and bimanual coordination. Experimental Brain Research 241(6):1643-1659. DOI 10.1007/s00221-023-06629-2. PMID 37179513. PMC10224868. [FT: Methods (task, data analyses), Results (practice and test phases, errors), Table 1, Discussion, Appendix C]
42. Waters-Metenier S, Husain M, Wiestler T, Diedrichsen J. 2014. Bihemispheric transcranial direct current stimulation enhances effector-independent representations of motor synergy and sequence learning. Journal of Neuroscience 34(3):1037-1050. DOI 10.1523/JNEUROSCI.2282-13.2014. PMID 24431461. PMC3891947. [FT: Methods (configuration and individuation tasks), Results (synergy learning)]
43. Weir JP. 2005. Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. Journal of Strength and Conditioning Research 19(1):231-240. DOI 10.1519/15184.1. PMID 15705040. [META]
44. Wilhelm LA, Martin JR, Latash ML, Zatsiorsky VM. 2014. Finger enslaving in the dominant and non-dominant hand. Human Movement Science 33:185-193. DOI 10.1016/j.humov.2013.10.001. PMID 24360253. PMC3976954. [FT: Methods, Results, Tables 1, 2 and 4, Discussion]
45. Wu YH, Pazin N, Zatsiorsky VM, Latash ML. 2013. Improving finger coordination in young and elderly persons. Experimental Brain Research 226(2):273-283. DOI 10.1007/s00221-013-3433-4. PMID 23411675. PMC3615093. [FT: Methods (enslaving matrix), Results (enslaving), Discussion]
46. Xu J, Ejaz N, Hertler B, Branscheidt M, Widmer M, Faria AV, Harran MD, Cortes JC, Kim N, Celnik PA, Kitago T, Luft AR, Krakauer JW, Diedrichsen J. 2017. Separable systems for recovery of finger strength and control after stroke. Journal of Neurophysiology 118(2):1151-1163. DOI 10.1152/jn.00123.2017. PMID 28566461. PMC5547267. [FT: Methods (assessment, individuation index, reliability), Results (reliability, controls, recovery)]
47. Xu J, Mawase F, Schieber MH. 2024. Evolution, biomechanics, and neurobiology converge to explain selective finger motor control. Physiological Reviews 104(3):983-1020. DOI 10.1152/physrev.00030.2023. PMID 38385888. PMC11380997. [FT: Sections 3.2, 3.3, 7.1 to 7.4 and 8]
48. Zatsiorsky VM, Li ZM, Latash ML. 2000. Enslaving effects in multi-finger force production. Experimental Brain Research 131(2):187-195. DOI 10.1007/s002219900261. PMID 10766271. [ABS]
49. Zondervan DK, Friedman N, Chang E, Zhao X, Augsburger R, Reinkensmeyer DJ, Cramer SC. 2016. Home-based hand rehabilitation after chronic stroke: randomized, controlled single-blind trial comparing the MusicGlove with a conventional exercise program. Journal of Rehabilitation Research and Development 53(4):457-472. DOI 10.1682/JRRD.2015.04.0057. [META]

Counts: 49 sources; 22 FT, 19 ABS, 8 META. Of the 41 sources whose own text supplied a number or finding (FT plus ABS), 22 are FT. Every META source whose content is used above was read through a named FT source, or is a record the code or design already cites (Rasch could not be located at all).

Not re-read here and left as the design or code already cites them: Kelso 1984, Haken, Kelso and Bunz 1985, Mechsner et al. 2001, Swinnen 2002, Murase et al. 2004, Kantak, Jax and Wittenberg 2017, Cincotta and Ziemann 2008 and Li et al. 2001 (all for cross-hand chords, not played on one board); Eswari, Balasubramanian and Varadhan 2025 (C5, dropped); Koo and Li 2016, McGraw and Wong 1996 and Bonett 2002 (ICC methods; listed in `docs/research/deep/reaction.md`).

### Simulation and pilot-analysis assumptions (for Sections 1, 2 and 4)

- Pilot reconstruction: the detector re-run sample by sample over `raw.csv` in file order with value alpha 0.35, baseline alpha 0.0005, the block's calibration `on_delta`, `off_delta` and resting level (primed baseline), the 150-count absolute floor and 100 ms debounce; the force window from the first `stim` event of each trial to block start plus `block_t_s`. Rest windows: no press from 1 s before to 0.3 s after, no stimulus from 1.5 s before, no pad pressed, every pad within 15 counts, non-overlapping. Look-back zero: the mean of the 250 ms before the stimulus. Pre-stimulus offset: the mean of raw minus baseline EMA over the 200 ms before the stimulus, and the peak measured from it. Hold: from completion (`complete_ms`) to the logged close.
- Deal: 2,000 blocks of 40 from the shipped `MixedChordDeck` with the default size mix. Chord-mix noise: RT Normal(650, 150) ms plus 112 ms for IR, MP, IRP and IMP (Verwey Table 1, block 1, CCI 6 against CCI 2 pairs), 4,000 draws of a block median, random against one fixed deal.
- T4 and T5: ten or twenty people; person median ER Normal(0.05, SD 0.005, 0.01 or 0.02) truncated at zero, within-person SD of a block median 0.0095 (bootstrap of 30 values from the 40 pilot chord ERs), pass shift Normal(0, 0.005); person median span Normal(100 ms, SD 25, 40 or 60), within-person SD 19 ms (bootstrap of 30 pilot spans), pass shift Normal(-10, 10) ms; ICC(2,1) absolute agreement single measure (McGraw and Wong form); 3,000 runs a cell.
- C6: per person 8 singles and 10 triples; RT = person base Normal(500, 60) + 2 x slope for triples + gamma-shaped noise with SD 150 ms; person slope Normal(true slope, 30); per-person slope (median triples minus median singles)/2; one-sided Wilcoxon at 0.05 or 0.05/8; 4,000 runs.
- C2 hit half: per person hit probability 0.65 + Normal(0, 0.10) - k x (D - mean D); per block 20/6 trials per pair type, 10/4 per triple type, 2 quads; Spearman over 11 chord types pooled over the cohort, pass at p < 0.05 with a negative rho; 3,000 runs.
