# Reaction mode: deep research audit

30 September 2026. Scope: the study battery's Reaction step, `app/finger_rehab/game/modes/reaction.py` (mode key `reaction`), its config, screen, logging and the notebook analysis. The hub card titled "Reaction" opens the lab SRT (`srt.py`) and is out of scope here, apart from the naming problem in Section 1.7.

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the stated assumptions; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository. Line numbers refer to commit cdacb9b; `screens.py` was being edited in the working tree during this review (cosmetic chip changes), so its functions are named as well.

---

## 1. What the mode does now

### 1.1 The trial loop under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Block start | GET READY card, a number counting down, no instruction text | 3.0 s | `screens.py` `_draw_countdown_card` (line 3650); `default.yaml` `game.start_countdown_s` |
| Arm | Every finger below its press threshold for the rest gate; any press restarts it | 0.3 s | `reaction.py` `_update_arm` 399-428; `default.yaml` 858 |
| Catch decision | Each attempt is a catch trial with probability 0.10, drawn per attempt; a catch trial shows nothing, ends silently at 8.0 s and adds 1 point | 0.10, 8.0 s | `_begin_trial` 451-466, `_catch_survived` 656-673; `default.yaml` 830-831 |
| Foreperiod | 1.5 s plus an exponential with mean 2.5 s, redrawn above 9.0 s | see below | `_draw_foreperiod` 493-525; `default.yaml` 811-814 |
| Stimulus | Target tile lights in its finger colour on grey idle tiles; buzzer under the target finger for 250 ms; a lane tone (C4 261.63 Hz, E4 329.63, G4 392.00, C5 523.25, index to little, 0.12 s); every tenth stimulus of a block 35 percent louder | all three channels on | `engine.on_stim_multi` (engine.py 8624); `audio/engine.py` 103-105; `default.yaml` 388, 398, 451, 493, 1836-1837; `engine._is_loud_trial` 812-821 |
| Clock start | The update tick that fires the stimulus, up to one frame before the flip | | docstring 94-98; `_fire` 527-538 |
| Response | First press decides. Under 100 ms: anticipation event, no scorable slot. Cued finger: hit; other fingers on the same sample are logged as `co_press` and the cued finger wins the tie. Other finger: scorable Miss, 0 points. No press by 2.0 s: Miss; a press after the window is kept as `late_ms` | 100 ms cut, 2.0 s window | `_press_on_stim` 675-763, `_prefer_cued` 581-597, `_close_scorable` 765-838; `default.yaml` 839, 2009 |
| Foreperiod press | Logged `false_start` (or `catch_false_start`), trial aborted with nothing on screen, rest 1.5 s + 0.5 s, no scorable slot used | | `_false_start` 619-637, `_catch_false_start` 639-654 |
| Feedback | RT number, small and grey, top right, 1.2 s; the lane flashes green for any hit and grey for a Miss; SESSION BEST chip at the foot of the screen, kept per pass | | `_show_rt_feedback` 841-864, `_best_key` 872-884; engine `_outcome_colour`; `screens.py` `_draw_reaction_layer` (3831, chip at 3889) |
| Rest | Feedback time plus gap | 1.2 s + 0.5 s | `_enter_rest` 886-894; `default.yaml` 864-866 |
| Block end | Scorable target reached or attempt cap | 20 scorable (battery), cap 35 | `default.yaml` 2008, 801 (default 25 at 800) |
| Cue order | One bag of 20 per block, five cues per finger, no finger twice running | copies = 5 | `reaction.py` 227-244; `scheduling.py` `BalancedScheduler` |

Foreperiod distribution (arithmetic from the code values): 5.0 percent of draws are redrawn; mean 3.61 s, median 3.11 s, 10th percentile 1.75 s, 90th percentile 6.33 s; 2.6 percent of real foreperiods exceed 8.0 s, the length of a catch trial.

Channel timing. Study MacBook, `app/config/latency_profile.yaml`, measured 24 September 2026: short sound 77 ms from dispatch, motor motion 74 ms from the STIM command. The display lag is not measured (config estimate 20 ms, `default.yaml` 1768). The sitting runs on the lab PC (healthy_baseline_study.txt line 9), which has no measured profile yet (`docs/study_day/before_the_day.md` Sections 3 and 4). Press timing floor (`docs/research/new_modes/modes-review.md`, "Device facts"): presses stamped 10 to 11 ms late on a bursting board (SD about 6 ms, maximum about 21 ms), detector 7 to 11 ms after the raw crossing, stimulus stamp 0 to 16.7 ms before the flip.

Place in the sitting: order A steps 1 and 9, order B steps 5 and 11 (`default.yaml` 1956-1990). Order A plays Reaction straight after the quick calibration. Measured block length 2.16 to 2.44 minutes (design doc Section 2.3, M).

### 1.2 Scoring and the screen

- Points (`scoring.py` `classify`; `default.yaml` 714-724): at or under 100 ms 10 points (unreachable here, since under 100 ms is an anticipation), at or under 200 ms 6, at or under 500 ms 3, over 500 ms 1, Miss 0; multiplied by a streak bonus of up to 1.5 (engine `_streak_multiplier` 8079-8086, `_score_for` 8088-8094). A survived catch adds 1.
- The stage is frozen while a trial is open: no score pulse, no popups, no timing bar (`screens.py` `_reaction_stage`, `_held`).
- No instruction reaches the participant. `mode_title("reaction")` falls back to "Reaction" and the NEXT UP card's description lookup finds no `reaction` key in `ModeSelectScreen.MODES`, so the card shows the title only (`screens.py` 471, 1530, 6696, by code reading). The GET READY card has no text beyond its heading. The run sheet has the RA say "Press lightly, like typing" and "Don't coach during a game" (`docs/study_day/run_sheet.md`). Nothing tells the participant that some trials never light up.

### 1.3 Logging and block_stats

Every attempt writes a row: scorable trials through `engine.log_trial`, events (false start, anticipation, catch outcome, simple-mode wrong finger, device drop) through `engine.log_reaction_event`. The `stimulus` column carries the sub-mode, the scheduled foreperiod and flags (`choice;fp=2.314`, `;gate_skipped`, `;late_ms=`, `;co_press=`); `cue_flags` and `loud_trial` are on every row. `block_stats` (1043-1122) gives median, mean, SD, p10 (the second-fastest RT at n = 20, arithmetic from `int(0.1 * (n - 1))`), maximum, accuracy, least-squares slope per trial, Spearman rho of RT against scheduled foreperiod, and the event counts. `lapse_like_rate` counts RTs at or over 500 ms, timeouts and wrong choices over scorable trials (932-948).

### 1.4 Registered checks and the notebook

- R1 (design doc Section 1.1; notebook `sec_cohort_validity`, cell 2 line 24007): cohort median of each person's Spearman rho within plus or minus 0.2 and mean false-start rate under 10 percent of attempts.
- R3 (`_r3_row`, line 23296; `COHORT_R3_MARGIN_MS` 23250): the 90 percent interval of pass 2 minus pass 1 median RT inside plus or minus 20 ms, by two one-sided tests.
- W1 (line 24488 onward): per-person slope of RT on log trial index, the median with a bootstrap interval, reported and not tested.
- T1 (`COHORT_RELIABILITY_METRICS`, line 29225): ICC(2,1) of median RT, predicted good to excellent (0.75 and up), reported and not tested.
- Per-selection rows (`MODE_LIT["reaction"]`, line 25121): R-lapse (under 10 percent of scored trials at or over 500 ms or timed out) and R-hick (not available).
- `sec_reaction_mode` / `_reaction_mode_group` (11146, 11207): pooled RT histogram, a method-of-moments ex-Gaussian fit when the selection holds 40 or more RTs, the foreperiod diagnostic, which prints for rho at or above 0.2 that RT growing with the wait "reads as slowing across the longer waits" (about line 11330), time on task, per-session median and p10 (the p10 there uses pandas' interpolated quantile at lines 11358 and 11388, and the returned `p10_ms` at 11460, while `reaction_p10` at 10967 promises one definition everywhere; `sec_reaction_checks` does the same at 26116).
- Cohort metrics (`_cohort_reaction`, 20372): median, SD, p10, lapse_like_rate, accuracy, rho, false_start_rate.
- Internal consistency: permutation split-half over 1000 splits (`split_half`, 21527).

### 1.5 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| An exponential foreperiod keeps the hazard flat, so RT should not track the wait; near-zero rho is the healthy result | reaction.py 8-17, 1006-1012; design doc R1 | Niemi and Naatanen 1981; Naatanen 1971 | Partly: flat is one finding, rising RT is another (Q1); catch trials make the hazard fall (arithmetic) |
| Four equiprobable fingers is a 2-bit choice | reaction.py 23-24, 227-233; design doc Section 1.1 cue-order note | Hick 1952; Hyman 1953 | Not supported with the no-repeat rule and a buzzer on the responding finger (Q6) |
| Choice RT runs roughly double simple RT | default.yaml 784-787 | none | Deary young adults: 1.6 times (Q6) |
| Under 100 ms is not a plausible visual RT | reaction.py 39-41 | Luce 1986; Basner and Dinges 2011; Whelan 2008 | True for the PVT; on this rig the logged scale sits about 35 to 55 ms above the physiological one (Q4) |
| Catch trials are the standard second anticipation control from the PVT tradition | reaction.py 47-50 | Dinges and Powell 1985 | Not supported: the PVT has no catch trials (Q3) |
| At or over 500 ms is a lapse | reaction.py 52-53; notebook R-lapse | Basner and Dinges 2011 | The PVT convention for visual simple RT; poor fit for a four-choice task (Q5) |
| A 20 or 25 trial block lands near the validated 3 minute PVT-B | reaction.py 54-57; design doc Section 1.1 | Basner, Mollicone and Dinges 2011 | Same duration only: PVT-B samples about 62 RTs at 1 to 4 s ISIs with a 355 ms lapse (Q2, Q5) |
| Median is the headline because RT is skewed | reaction.py 57-58 | Ratcliff 1993; Whelan 2008 | Supported, with small-n bias caveats (Q13) |
| No transfer beyond the task | reaction.py 69-72 | Owen et al. 2010 | Verified: 11,430 people, no transfer even to closely related tasks [FT] |
| Labs differ by over 100 ms on hardware | reaction.py 73-77; notebook floor note | Woods 2015; Plant and Turner 2009 | Supported (Woods cites Neath 2011 for up to 100 ms) [FT] |
| Quantisation averages out in block medians | reaction.py 78-81 | Ulrich and Giray 1989 | Consistent with arithmetic (Q10) |
| R3: no practice effect, margin 20 ms, "a little over one 60 Hz frame" | design doc Section 1.1; notebook 23245-23250 | Basner et al. 2017 (2018); Lakens 2017; Woods 2015 "visual choice RT" | Margin rationale mixes trial grain with block resolution; the Woods task is two-choice (Q10) |
| T1 good to excellent | design doc Section 1.1 | PVT tradition; Basner, Mollicone and Dinges 2011 | "Good" is the realistic centre (Q9) |
| Left-handers' simple RT differs little between hands | design doc Section 2.1 | Nisiyama and Ribeiro-do-Valle 2014 | That study tested right-handers only (Q12) |
| Ex-Gaussian at n of 40 or more | notebook 11067 | Hohle 1965 | Imprecise at this n and pooled across people (Q13) |
| Cue mix changes what the number means | reaction.py 28-37; default.yaml 376-382 | none | Supported, with numbers in Q7 |

Also cited in the design doc and notebook for this mode: Peters 1980 and Hubel et al. 2013 (R2, now dropped), Koo and Li 2016, Bonett 2002, McGraw and Wong 1996, Weir 2005, Bland and Altman 1986, Heathcote, Brown and Mewhort 2000, Kantak and Winstein 2012, and in design_check.md Collie 2003, Falleti 2006, Zeinalzadeh 2021, Woods 2015 (SRT and CRT retest papers).

### 1.6 Pilot blocks on disk (rig check only)

Six usable choice blocks by the development team (sessions dated 31 August to 23 September 2026), all with buzz, tone and tile on: 68 valid RTs, block medians 282 to 501 ms, fastest valid RT 235 ms, 7 wrong-finger rows (4 of 7 to an adjacent finger, 5 of 7 under 280 ms), 2 foreperiod false starts, block rho from -0.27 to +0.43 on 6 to 17 trials, and one block (median 501 ms) with 7 of 13 RTs at or over 500 ms (pilot). Error share 9.3 percent (arithmetic, pilot).

### 1.7 Naming

The README's game table labels `docs/images/reaction.png` "Reaction" and describes Reaction as the lab's sequence task; that screenshot is the SRT screen (its instruction line is `srt.py` line 867), and `reaction_setup.png` is the SRT setup screen. No screenshot of the battery step exists. trials.csv keeps the two apart (`reaction` against `srt`), but a thesis reader will not.

---

## 2. Research questions and findings

### Q1. Does the exponential foreperiod keep expectancy flat, and what RT against foreperiod should a healthy hand show? (R1)

- Flat. With an exponential (non-aging) foreperiod distribution the RT against foreperiod function lies down and becomes approximately flat (Los, Kruijne and Meeter 2014 [FT, section on the foreperiod-distribution effect, Figure 1B], citing Naatanen 1971, Trillenberg et al. 2000 and Vangkilde et al. 2013). The same authors add that under their theory the flat average is a coincidence of several influences, not a pure effect. Uneven or non-aging distributions can shrink the usual variable-foreperiod effect or remove it altogether (Bausenhart and Ulrich 2026 [FT, section on expectancy and hazard]).
- Rising. In a two-choice task with a non-aging distribution (400 and 1,400 ms foreperiods in a 2 to 1 ratio, with catch trials), RT was 439 and 463 ms at 400 ms against 484 and 492 ms at 1,400 ms (repetition and alternation cells), partial eta squared 0.70, errors about 1.5 percent (Han and Proctor 2022, Experiment 1, Table 1 [FT]). Capizzi et al. 2015 found the same rising direction in simple RT [META; reported in Han and Proctor]. Han and Proctor conclude that under a non-aging distribution the variable-foreperiod function takes the direction of the fixed-foreperiod function, which rises with foreperiod beyond a few hundred milliseconds and keeps rising slowly towards 20 s (Los 2014 [FT]; Bausenhart and Ulrich 2026 [FT]).
- Rising, from a different model. With a truncated exponential go-time distribution (0.4 to 1.4 s, 9.09 percent catch trials; 24 people, about 3,500 RTs each) RT was strongly modulated by go time, and the reciprocal of the blurred probability density, not the hazard, fitted RT (Grabenhorst et al. 2019, Results and Figures 3 to 4 [FT]). The reciprocal of a falling density rises, so this model predicts RT rising with foreperiod.
- History. RT depends on the previous trial's foreperiod, for long sets (1,200 to 3,600 ms) as well as short (Bausenhart and Ulrich 2026 [FT], citing Steinborn et al. 2008); in Han and Proctor the sequential effect was 24 ms at the short foreperiod and 8 ms at the long [FT]. Preparation follows the foreperiods experienced before, not the current hazard (Los et al. 2017 [ABS]).
- This implementation (arithmetic from the code values). Without catch trials the truncated exponential's go hazard rises from 0.42 per s at 1.5 s to 0.73 per s at 7 s and 1.12 per s at 7.9 s. With 10 percent catch trials that end at 8 s, the go hazard falls from 0.38 per s at 1.5 s to 0.23 per s at 7.9 s, then jumps above 1.3 per s after 8 s, when every trial still open must be a real one. So the combined design is not flat: the longer the wait, the more likely it is a catch trial, which is the condition under which a rising RT against foreperiod is expected.
- One person's rho from 20 trials has a null SD of about 0.24 (notebook comment; arithmetic 1/sqrt(17)).

Where sources disagree: Los 2014 and the classic studies it cites report a flat function; Han and Proctor 2022, Capizzi 2015 and Grabenhorst 2019 report or predict a rising one. All agree that a falling RT with foreperiod is the signature of timing an aging hazard.

Bearing on the mode. R1's two-sided rule can fail with a correctly working foreperiod. Simulation (10 people, 20 trials each, within-person SD about 70 ms, between-person SD 45 ms, 1,500 runs per cell): true slope 0 passes 98 percent; +5 ms per s passes 76 to 78 percent; +10 ms per s passes 22 percent; a one-sided rule (median rho above -0.2) passes 99 to 100 percent in all three (simulation). The notebook's reading of rho at or above 0.2 as slowing across the longer waits has no support in these sources.

### Q2. Is 1.5 to 9 s (mean 3.6 s) a good foreperiod range for choice RT?

- Wider foreperiod ranges slow RT even at the same foreperiod, and fixed-foreperiod RT rises with foreperiod because time estimation gets less precise (Klemmer 1956 [META], reported in Bausenhart and Ulrich 2026 [FT]).
- PVT-B shortened the ISI from 2 to 10 s to 1 to 4 s and sampled 62.3 stimuli in 3 minutes against 93.6 in the 10 minute PVT; in the authors' mixed model of both versions (random, uniformly drawn ISIs), RT fell as the ISI grew from 1 to 6 s and levelled off from 7 s, and RT rose with time on task (Basner, Mollicone and Dinges 2011, Results [FT]).
- Reference tasks use short waits: Deary et al. 2011 ISI 1 to 3 s [FT, Method]; Woods SRT SOA 1.0 to 1.8 s [FT, Methods].
- Block time (arithmetic): about 6.0 s per scorable trial (1.7 s rest, 0.3 s gate, 3.61 s mean foreperiod, about 0.35 s RT) and 2.2 catch trials of about 10 s each per block. A distribution of 1.0 s plus an exponential with mean 1.5 s truncated at 5 s has a mean of 2.2 s (arithmetic) and would fit about 25 trials in the time of 20.

Bearing: the long, wide foreperiod slows and spreads RT relative to 1 to 3 s tasks and costs trials per minute. Changing it changes the task, so it belongs after collection.

### Q3. Catch trials: rate, schedule, length and what they do

- The PVT has no catch trials. Its false starts are responses without a stimulus or RTs under 100 ms, and it shows "FS" for 1 s (Basner and Dinges 2011, Table 3 [FT]). The docstring's attribution of catch trials to the PVT tradition is therefore wrong.
- Catch trials come from the foreperiod literature, where target probability (the catch-trial share) is one of the factors shown to change preparation and RT (Buckolz and Rodgers 1980; Drazin 1961; Naatanen 1972 [all META], grouped this way in Bausenhart and Ulrich 2026, section "Foreperiod paradigms" [FT]); raising the catch proportion shifts the response criterion, with effects additive to foreperiod (Seibold et al. 2011 [ABS]). Grabenhorst et al. 2019 used 9.09 percent [FT, Figure 2 legend]; Girard et al. 2011 used 10 percent [FT, Method]; Han and Proctor 2022 ran each catch trial 1 s longer than the longest foreperiod [FT, Method].
- Schedule (arithmetic): drawn per attempt, a 20-trial block has no catch trial 12 percent of the time and 2.2 on average. The Buzz Hunt code review fixed the same per-trial draw because a fifth of its blocks had no false-alarm measure (`docs/code_review_2026-09-27.md`).
- Length: 8.0 s against a 9.0 s maximum foreperiod, so any trial still open after 8 s is a real one (2.6 percent of real trials, arithmetic).
- Expected false-alarm levels without catch trials: false alarms averaged 3.2 percent of responses (median 1.71 percent) and 5.7 percent of people exceeded 10 percent (Woods et al. 2015 SRT, Results [FT], 1.0 to 1.8 s SOAs). In four trained observers anticipations were about 0.002 percent (Diederich and Colonius 2004, Method [FT]).

### Q4. What is an anticipation on this rig?

- PVT: under 100 ms for visual stimuli; the footnote to Table 3 says the threshold would have to be lower for auditory stimuli (Basner and Dinges 2011 [FT]).
- Other cut-offs: Woods SRT 110 to 1000 ms window [FT, Methods]; Woods two-choice CRT 250 to 1250 ms window [FT, Data analysis]; Nisiyama and Ribeiro-do-Valle 2014 under 150 ms [FT, Methods]; valid RTs should not start before 100 to 200 ms, and a 200 ms lower cut-off was one of the methods tested (Berger and Kiefer 2021, Introduction and Table 1 [FT]).
- Fast guesses in choice tasks sit near chance accuracy (Yellott 1971 [META], reported in Heitz 2014 [FT]).
- The logged RT includes 0 to 16.7 ms to the flip, an unmeasured panel lag, 7 to 11 ms of detector delay and 10 to 11 ms of stamping delay (modes-review.md). Summed, the rig adds about 35 to 55 ms on the visual route (arithmetic, taking a mean of 8 ms to the flip, 10 to 25 ms of panel lag including the macOS frame, 7 to 11 ms detector and 10 to 11 ms stamping), so a logged 100 ms is roughly 45 to 65 ms of physiological latency (arithmetic).
- Pilot: fastest valid RT 235 ms; 5 of the 7 wrong-finger presses at 247 to 273 ms (pilot).

Bearing: the 100 ms logged cut is permissive for a four-choice task here. A 150 ms logged cut (about 95 to 115 ms physiological, arithmetic) is closer to the choice-RT literature, and a conditional accuracy function (accuracy by RT bin) shows directly whether fast presses are informed.

### Q5. Is 500 ms a lapse in a four-choice task?

- PVT lapses are RTs at or over 500 ms or, in the older definition, at or over twice the mean RT, for visual stimuli; auditory thresholds would be lower (Basner and Dinges 2011, Introduction and Table 3 [FT]). PVT-B uses 355 ms, set after the fact on its data (Basner, Mollicone and Dinges 2011, Discussion [FT]).
- Four-choice RT in young adults: mean 388.0 ms, within-person SD 69.4 ms (Deary et al. 2011, Table 1 [FT]); two-choice feature-conjunction CRT 472 ms in 18 to 24 year olds (Woods et al. 2015 CRT age paper, Table 2 [FT]).
- Arithmetic (normal approximation, within-person SD 69 ms): a person with a mean of 388 ms passes 500 ms on 5.2 percent of trials, at 420 ms on 12.3 percent, at 450 ms on 23.4 percent. The rig adds tens of milliseconds on top (Q4). The pilot block with a 501 ms median had 7 of 13 RTs past the cut (pilot).

Bearing: the notebook's R-lapse (under 10 percent over 500 ms) will fail for slower healthy people with no lapse of attention. The older PVT form, at or over twice the person's own median, or reciprocal speed (1/RT), measures the construct better in a choice task.

### Q6. Is it a 2-bit choice, and what does a buzzer on the responding finger do?

- Hick 1952 and Hyman 1953: choice RT rises with stimulus information, and Hyman showed sequential dependencies count towards that information (Proctor and Schneider 2018, sections on Hick's and Hyman's experiments and "Sequential effects" [FT]; primaries [META]).
- Stimulus-response compatibility changes the slope. With vibration applied to the finger that must respond, Leonard 1959 found no RT difference between two, four and eight choices, a flat function; ten Hoopen et al. 1982 qualify the finding; Brainard et al. 1962 found similar (Proctor and Schneider 2018, section "S-R compatibility" [FT]; primaries [META]). Practice also flattens it: Hale 1968's eight-choice minus two-choice difference fell from close to 500 ms to a little over 300 ms over five sessions, Wifall et al. 2016 still found 149 ms after about 4,000 trials, and Teichner and Krebs 1974 concluded from many studies that with enough practice RT might become independent of set size (section "Practice" [FT]).
- Sequential structure. At a set size of four, repetition probabilities of 0.08 and 0.44 both carry 1.87 bits (Kornblum 1969, reported in Proctor and Schneider [FT]). With no immediate repeats a cue carries at most log2(3) = 1.58 bits (arithmetic). An observer who also tracks the five-per-finger counts faces 1.34 bits per cue on average, and 2.3 cues per block are fully determined, always including the last (arithmetic, simulation of the shipped scheduler over 2,000 blocks). Repetitions are usually faster, but at response-stimulus intervals near 7.5 s the differences between equal-information conditions were very small (Hyman and Umilta 1969, reported in Proctor and Schneider [FT]); here the interval is about 3.5 to 11 s (arithmetic).
- Choice against simple. Deary et al. 2011 young adults: 388.0 against 243.1 ms, a difference of 144.9 ms and a ratio of 1.6 (arithmetic from Table 1 [FT]).

Bearing: with the buzzer on the target finger, the measure is closer to an ideomotor-compatible choice than to Hick's 2-bit choice, and the Hick framing in the docstring, design doc and notebook should go. The config comment "roughly double the RT" is not supported.

### Q7. What does the light, tone and buzz cue do to RT?

- Redundant signals. Trimodal stimuli gave faster responses than bimodal, and bimodal faster than unimodal. Enhancement reached 9.4 percent of the fastest unimodal RT for bimodal and 13.1 percent for trimodal stimuli, was largest when the onset asynchrony matched the difference in unimodal RTs, and grew as stimuli got weaker (Diederich and Colonius 2004, Tables 2, 4 and 5 [FT]; four trained observers, 10,600 responses each). Unimodal simple RT there: 90 dB tone 132 ms, light 163 ms, strongest toe vibration 177 ms; 70 dB tone 150 ms and 80 dB 137 ms [FT, Table 2]. The race-model inequality (Miller 1982 [META]) was violated, so the gains exceed statistical facilitation [FT].
- Visual plus tactile. Simple RT to simultaneous visual and tactile stimuli was faster than to either alone, beyond what probability summation allows (Forster et al. 2002 [ABS]).
- Choice tasks. Absolute multisensory gains were larger in choice than in simple RT with audio, visual and haptic signals (Hecht, Reiner and Karni 2008 [ABS]). With spatially aligned visual and tactile stimuli at the index finger, the multisensory gain was the same in a simple and a side-choice task, and the race model was violated from the 10th to the 70th or 80th percentile (Girard et al. 2011, Results [FT]).
- An accessory tone that needed no response cut visual RT from 314 to 275 ms (Giray and Ulrich 1993 [META], reported in Bausenhart and Ulrich 2026, Box 1 [FT]).
- Touch. Vibrotactile simple RT in young adults was about 200 ms at the head and 230 ms at the foot, and a coin motor was 46 ms slower than a C-2 tactor (Bao et al. 2019, Results and Discussion [FT]). Tactile mislocalisations fall on neighbouring fingers more often than distant ones (Schweizer et al. 2000 [ABS]).
- On the rig. The tile appears first (estimated 20 ms; pygame-based Expyriment showed a 29.02 ms visual onset lag on macOS, Bridges et al. 2020, Table 2 [FT]), then the buzz at 74 ms and the tone at 77 ms (measured). The tone arrives about 50 to 57 ms after the tile (arithmetic), while the unimodal auditory advantage in Diederich and Colonius is 31 ms (arithmetic, 163 minus 132). The tone's pitch names the finger only through a learned mapping (code), whereas the buzz is on the finger itself.

Bearing: the logged RT is a race or coactivation across three channels, one of them (touch on the responding finger) highly compatible and one (pitch) arbitrary. It is not comparable with visual-only norms, and it moves if any channel's latency moves: another computer, another audio output, another motor.

### Q8. Healthy four-choice values and device latency

- Deary et al. 2011 [FT, Method, Table 1]: 18 to 25 years (n = 50): simple RT 243.1 ms (SD 17.6), four-choice 388.0 ms (SD 45.0), within-person SD 69.4 ms, errors 3.0 percent (Table 1 labels errors as a percentage; the text reports the whole-sample figure, 2.4, as a mean number of errors). Index and middle fingers of both hands on keyboard keys under spatially matched squares, 8 practice and 40 test trials, ISI 1 to 3 s, 60 Hz screen. The same people on the numbers box: 459.4 ms (SD 42.5). The authors decline to publish norms because hardware differs between studies.
- Woods et al. 2015 CRT age paper, Table 1 [FT]: large CRT studies from 475 to 801 ms across different tasks, with age slopes of 2.0 to 3.4 ms per year.
- Der and Deary 2006 [ABS]: 7,130 adults; choice RT slows across the adult span, simple RT little until about 50.
- Hardware: Woods measured 11.0 ms of display delay and 6.8 ms of mouse delay, 17.8 ms in all, and cites up to 100 ms between labs (Woods et al. 2015 SRT factors paper, Methods and Introduction [FT]). Pygame-based Expyriment: RT lag 33.83 ms on macOS; audio onset lag 42.81 ms on macOS and 106.83 ms on Windows 10 (Bridges et al. 2020, Table 2 [FT]).

### Q9. How many trials, and what ICC to expect? (T1)

- Mean-RT reliability over three weeks with 240 trials per condition, ICC(2,1): 0.63 to 0.77 (flanker congruent 0.74 and 0.69, Stroop congruent 0.77 and 0.72, SNARC 0.69 and 0.74, Navon 0.63 to 0.70), SEMs 20 to 42 ms (Hedge, Powell and Sumner 2018, Tables 1 and 2 [FT]).
- Two-choice CRT, 46 young adults, 140 trials, weekly: Pearson r 0.72, 0.74 and 0.77 between sessions; the reported three-session ICC of 0.89 matches the average-measures form (3r/(1+2r) with mean r 0.743 gives 0.90, arithmetic). SRT, 48 young adults, 100 trials: pairwise r 0.59, 0.80 and 0.53, reported ICC 0.84 (the same form gives 0.84 from mean r 0.64, arithmetic). Earlier CRT test-retest values quoted there: 0.79, 0.65, 0.69, 0.85 and 0.58 (Woods et al. 2015 CRT and SRT retest papers, Results [FT]).
- Four-choice, 40 trials: Cronbach's alpha 0.97; back-to-back retest (n = 20) r = 0.83 for the mean, 0.64 for simple RT (Deary et al. 2011, Results [FT]). Halving to 20 trials by Spearman-Brown gives 0.71 (arithmetic, trial noise only).
- Aggregated scores carry trial noise that shrinks only as the number of trials grows (a sigma squared over L term); in Hedge's data both effect sizes and test-retest reliability rose as trials per condition went from 20 to 400, and a hierarchical model estimates the trial-free quantity (Rouder and Haaf 2019, author's version 2 of July 2018, sections on portability and the model [FT]).
- Simulation (10 people, 20 trials a pass, person shift SD 10 ms): ICC(2,1) median 0.87 (5th percentile 0.64) with within-person SD 70 ms and between-person SD 45 ms; 0.75 (0.37) with between-person SD 30 ms; 0.91 (0.75) and 0.82 (0.52) with within-person SD 52 ms (simulation).
- The PVT's ICCs above 0.8 quoted for lapses (Basner and Dinges 2011, Introduction [FT]) are for a 10 minute simple-RT test and a different metric.

Bearing: "good" (0.75 to 0.9) is the realistic centre for a 20-trial within-session median; "excellent" is unlikely; a homogeneous student sample can land in "moderate", and at n = 10 the interval will span two or three bands.

### Q10. Practice between the passes, and the R3 margin

- Back-to-back four-choice retest: 420.0 to 427.3 ms, 7.3 ms slower (arithmetic), errors 1.6 and 1.8 percent (Deary et al. 2011, Table 5 [FT]).
- Two-choice CRT over three weekly sessions: 494, 475 and 463 ms (Table 2), described in the text as a 33 ms decrease, largest for the harder stimuli (Woods et al. 2015 CRT retest paper [FT]). This is a two-button task, not four-choice.
- SRT: under 3 ms change across three weekly sessions (Woods et al. 2015 SRT retest paper [FT]). PVT-B over 16 administrations: mean and median RT and lapses did not change; the fastest 10 percent and the minimum RT increased; false starts fell (Basner et al. 2018 [ABS]).
- Computerised batteries at brief intervals (four times in a day; 10 minutes apart): practice effects mostly between the first and second administration (Collie et al. 2003 [ABS]; Falleti et al. 2006 [ABS]).
- An equivalence margin should be a smallest effect size of interest fixed before the data: objectively from a theoretical prediction or a just noticeable difference, otherwise from related studies or resources; a bare benchmark is the weakest justification (Lakens, Scheel and Isager 2018, author's accepted version, section "Justifying the Smallest Effect Size of Interest" [FT]; Lakens 2017 [META]).
- Arithmetic on the margin. Frame quantisation adds a uniform 0 to 16.7 ms error per trial (SD 4.8 ms), which contributes about 1.3 ms to the standard error of a 20-trial median (arithmetic), so "a little over one 60 Hz frame" describes single trials, not block medians; reaction.py's own docstring (78-81) makes the same point about averaging. Sampling alone gives the difference of two 20-trial medians an SD of 17 ms (within-person SD 52 ms) to 22 ms (70 ms) (simulation). At n = 10 R3 passes 55 to 80 percent of the time with a true shift of zero, and 29 to 43 percent with a true shift of -10 ms (simulation). The design_check.md figure of about 80 percent assumes the smaller spread.

Bearing: R3 carries little information either way at this n; the shift and its interval are the useful output.

### Q11. Warm-up and time on task in a 2.3 minute block (W1)

- RT rose with time on task over a 10 minute PVT (Basner, Mollicone and Dinges 2011, Results [FT]); a 2 minute PVT was less sensitive to sleepiness than 5 and 10 minute versions (Loh et al. 2004 [ABS]). Little decrement is expected over 2.3 minutes in rested students.
- Reference tasks give practice first: Deary 8 trials, Woods 20 [FT]. Practice gains concentrate early (Collie 2003; Falleti 2006 [ABS]). Practice trials give an acclimation period (Heitz 2014 [FT]).

Bearing: with no practice trials and no instruction, the first trials of pass 1 (the first game of the sitting in order A) include working out the task, so W1 will carry task learning as well as warm-up.

### Q12. Handedness

- 32 right-handed young adults (laterality quotient 0.77): no difference between the hands in simple or choice RT (Nisiyama and Ribeiro-do-Valle 2014, Methods and Results [FT]). The study did not test left-handers.
- Handedness did not predict SRT (r = -0.02) in 1,469 adults, 10.8 percent left-handed (Woods et al. 2015 SRT factors paper, Results [FT]).

Bearing: a small or absent handedness effect is the expected answer; the design doc's use of Nisiyama for left-handers needs rewording.

### Q13. Distribution analysis at 20 trials

- Sample medians overestimate population medians in small skewed samples, by up to about 50 ms; medians should not be compared across unequal trial counts (Miller 1988 [ABS]). For an ex-Gaussian with mu 300, sigma 20 and tau 300, the bias is 15.1 ms at n = 10 and 0.7 ms at n = 100; a percentile bootstrap corrects it, and the median is median-unbiased (Rousselet and Wilcox 2020 [FT]).
- Outlier-resistant location measures (medians and similar) are far less affected by outliers than moments; fitting distributions is not worth routine use unless shape is the question (Ratcliff 1993 [ABS]).
- Median-absolute-deviation exclusion inflated Type I errors to between 10 and 25 percent; no exclusion gave the largest absolute bias; 2 SD, 10 percent quantile and transform methods the smallest (Berger and Kiefer 2021, Table 4 and Discussion [FT]).
- Ex-Gaussian by maximum likelihood at N = 20: tau 95 percent interval 60.4 to 461.1 ms for a true 250, sigma 0 to 210.3 for a true 100; at N = 100, tau 165.7 to 317.0 (Lacouture and Cousineau 2008, Table 1 [FT]).
- Reciprocal outcomes (mean 1/RT, slowest 10 percent 1/RT) had the highest effect sizes for sleep loss; mean and median RT the lowest (Basner and Dinges 2011, Results and Table 2 [FT]). That criterion is sensitivity to sleep loss, not reliability.

Bearing: the notebook's method-of-moments ex-Gaussian, gated at 40 RTs pooled over whatever the selection holds, mixes people into tau and is too imprecise per person; p10 at 20 trials is the second-fastest trial; per-finger medians rest on five trials each.

### Q14. Feedback, score and instructions

- Verbal instructions are the most common speed-accuracy manipulation and give large effects; payoff matrices with a criterion time shift the trade-off even without instructions (Fitts 1966, reported in Heitz 2014, SAT methodology [FT]).
- An instruction to try harder speeded choice RT, raised errors at short foreperiods and reduced skew (Steinborn et al. 2017 [ABS]). Reward raised sustained-attention performance and effort (Massar et al. 2016 [ABS]).
- PVT convention: RT shown for 1 s after each response, "FS" after a false start, no points (Basner and Dinges 2011, Table 3 [FT]).
- Code: criterion times at 200 and 500 ms with a streak multiplier form a speed-weighted payoff; an answer right half the time at under 200 ms earns about what a careful one does (arithmetic, 0.5 x 6 = 3 points). No instruction line, no false-start message, and no warning that some trials never light up (Section 1.2).
- Combined speed and accuracy: the balanced integration score (z of accuracy minus z of mean correct RT, standardised across all cells) weights the two equally and is relatively insensitive to speed-accuracy shifts, unlike inverse efficiency, rate-correct and LISAS scores (Liesefeld and Janczyk 2019 [FT, sections on the measures and Figure 3]).

### Q15. Error pattern and the co-press rule

- Errors: 3.0 percent in Deary's young adults [FT]; hit rates 92.1 to 96.6 percent across stimulus types in Woods' two-choice task [FT].
- Pilot: 9.3 percent errors, 4 of 7 to an adjacent finger, 5 of 7 under 280 ms (pilot). Tactile mislocalisation favours neighbours (Schweizer et al. 2000 [ABS]).
- Code: presses that land on the same sample as the cued finger make a hit, tagged `co_press`. On a bursting board samples arrive in packets about every 20 ms and are stamped on arrival (modes-review.md), so presses up to about 20 ms apart can share a stamp (arithmetic). The notebook never reads the tag.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Sub-mode | choice, four fingers, one hand (`default.yaml` 788, 2007) | Fine as a battery measure; not a Hick 2-bit measure (Q6) | Keep, reword the claims |
| Cue channels | tile + buzz on the target + lane tone (388, 398, 451) | Multisensory, touch on the responding finger (Q7) | Keep for the study; state it with every number; channel study after collection |
| Loud trials | every 10th stimulus 35 percent louder (1836-1837) | Louder tones speed RT (Diederich and Colonius Table 2 [FT]) | Change: exempt Reaction, or at least analyse |
| Foreperiod distribution | exponential, 1.5 s floor, mean extra 2.5 s, truncated at 9.0 s (811-814) | Flat or rising RT with foreperiod; hazard falls with the catch trials (Q1) | Keep; change R1 and the wording |
| Foreperiod range | mean 3.61 s, 90th percentile 6.33 s (arithmetic) | Long waits add time uncertainty and cost trials (Q2) | Keep for this study; shorter distribution after collection |
| Catch rate | 0.10 (830) | 9 to 10 percent in comparable studies (Q3) | Keep |
| Catch schedule | Bernoulli per attempt (`_begin_trial` 451) | 12 percent of blocks with none (arithmetic) | Change: fixed count per block |
| Catch length | 8.0 s (831) | Should outlast the longest foreperiod (Han and Proctor Method [FT]) | Change: at least `fp_max_s` |
| Anticipation cut | 100 ms logged (839) | 100 to 250 ms in the literature; logged scale about 35 to 55 ms above physiological (Q4) | Add a 150 ms sensitivity row; consider 150 ms |
| Lapse cut | 500 ms (842) | PVT visual simple-RT convention (Q5) | Keep for continuity; add a person-relative lapse |
| Response window | 2.0 s fixed (2009) | Healthy four-choice RTs sit far below it (Deary [FT]) | Keep |
| Trials per block | 20 scorable, cap 35 (2008, 801) | Retest r 0.83 at 40 trials; about 0.71 at 20 (arithmetic) (Q9) | Keep (time); state the precision |
| Practice trials | none | 8 (Deary), 20 (Woods) [FT] | Add, both passes |
| Instructions | none on screen; RA says "press lightly" | Instructions set speed-accuracy (Heitz [FT]) | Add |
| Rest gate | 0.3 s (858) | No literature value; protects false-start data | Keep |
| Inter-trial rest | 1.2 + 0.5 s (864-866) | PVT shows RT 1 s inside the ISI [FT] | Keep |
| No-repeat rule | on (`BalancedScheduler`) | At most 1.58 bits per cue; repetition effects small at long intervals (Q6) | Keep for this study; allow repeats after collection |
| Bag of 20 | 5 per finger | Balanced counts; last cue determined (arithmetic) | Keep |
| Scoring tiers | 6/3/1 points at 200/500 ms, streak multiplier | Acts as a speed payoff (Heitz [FT]) | Change for the battery or keep and state it |
| RT feedback | corner number 1.2 s | PVT convention [FT] | Keep |
| Session best chip | on, per pass | Goal cue; not in the PVT | Keep; note in the thesis |
| False-start feedback | none | PVT shows "FS" [FT] | Optional neutral line |
| Co-press rule | cued finger wins a same-sample tie | Needed against enslaving bias; opens a multi-finger loophole | Keep; count and report co-presses |
| Headline | median of valid RTs | Supported; small-n bias (Q13) | Keep |
| p10 | second-fastest of 20 | Unstable; fastest 10 percent drifts with repetition (Basner 2018 [ABS]) | Keep as descriptive; one definition |
| Ex-Gaussian | method of moments, pooled, n of 40 or more | Imprecise and mixes people (Q13) | Change |
| Rho against foreperiod | per person, 20 trials | Null SD 0.24 (arithmetic) | Keep as descriptive; add a pooled slope |
| R1 | two-sided, 0.2 | Rising function expected under this design (Q1) | Change to one-sided |
| R3 | 90 percent CI inside 20 ms | Weak at n = 10; margin rationale misplaced (Q10) | Report as an estimate; re-justify the margin |
| W1 | slope on log trial | Carries task learning without practice (Q11) | Keep; add practice |
| T1 | predicted 0.75 and up | Centre about 0.75 to 0.87 (simulation) | Keep "good"; drop "excellent" |
| Latency provenance | MacBook profile; lab PC unmeasured | Channel lags set the race (Q7, Q8) | Measure the lab PC before collection |
| Board clock | not applied to Reaction | 10 to 11 ms stamping delay (modes-review) | Add a sensitivity row |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

1. **R1: change how a positive rho is read, and make the rule one-sided.**
   SAFE-NOW part: in `analysis/session_analysis.ipynb` cell 2, `_reaction_mode_group` (the rho message block near line 11330), replace the "RT GROWS ... reads as slowing" text with: a positive rho is expected with a non-aging foreperiod and catch trials (Han and Proctor 2022; Grabenhorst et al. 2019; the falling hazard, arithmetic), only a negative rho signals timing. Add a pooled slope of RT on foreperiod in ms per s with a participant random intercept (the REML model in `finger_rehab/analytics/mixed_model.py`), with the previous trial's foreperiod as a second term, printed beside R1 in `sec_cohort_validity` (line 24007 onward). Reword `reaction.py` lines 8-17 and the `_spearman_rho` docstring (1006-1012): the hazard falls over the wait once catch trials are included.
   DESIGN-CHANGE part: R1 passes when the cohort median rho is above -0.2 and false starts are under 10 percent. Change `sec_cohort_validity` R1 `ok`, `sec_reaction_checks` R1 `ok` (line 26028 area), `MODE_LIT["reaction"]` R1 reference (25122), and design doc Section 1.1 R1; log the change and its date in the design document.

2. **Tell the participant what to do.** SAFE-NOW (UX, no measure changes; log it in the design document because it changes what participants are told).
   Add one line for the battery Reaction step: "Rest your fingers on the pads. When a finger lights up and buzzes, press that finger as fast as you can. Sometimes nothing comes: keep still." Two routes: a battery-only description table read by the NEXT UP card (`screens.py` `ResultsScreen._draw_next_up`, the `desc` lookup at 6696) that does not add a hub card to `ModeSelectScreen.MODES`, and the same line on the GET READY card when `current_block == "reaction"` (`GameplayScreen._draw_countdown_card`), which sits outside every measured epoch. The NEXT UP card never shows before the first block of order A, so the GET READY route (or the run sheet) is the one that reaches everybody. Also add it to `docs/study_day/run_sheet.md` under "Seat and log in", said once before LOG IN, because order A starts Reaction straight after calibration.

3. **Correct the claims that the evidence contradicts.** SAFE-NOW (text only).
   - `reaction.py` 23-26 and 227-233, design doc Section 1.1 cue-order note, notebook `MODE_LIT["reaction"]` R-hick and `sec_reaction_mode`'s "cost of a 2-bit selection (Hick 1952)" line: with the buzzer on the responding finger and no repeats, the task is not a 2-bit Hick choice (at most 1.58 bits per cue, arithmetic; Leonard 1959 via Proctor and Schneider 2018).
   - `default.yaml` 784-787: "roughly double the RT" to "about 1.6 times simple RT for a visual spatial task (Deary et al. 2011); likely less with the buzz on the finger".
   - `reaction.py` 47-50 and `default.yaml` 826-829: catch trials come from the foreperiod literature (Drazin 1961; Buckolz and Rodgers 1980; Seibold et al. 2011), not the PVT, which has none.
   - `reaction.py` 54-57 and design doc Section 1.1: same duration as PVT-B, but PVT-B samples about 62 RTs at 1 to 4 s ISIs with a 355 ms lapse cut.
   - Design doc Section 1.1 R3 basis and `design_check.md` Section 3: Woods et al. 2015 is a two-button (two-choice) CRT; "four-choice RT does fall" should read "two-choice CRT fell by about 19 ms from week 1 to week 2 (494 to 475 ms)".
   - Design doc Section 2.1: Nisiyama and Ribeiro-do-Valle 2014 tested right-handers only; cite Woods et al. 2015 (handedness r = -0.02 with SRT) instead, or drop the left-hander claim.
   - Design doc Section 1 preamble ("This design does not test them: nothing in it is measured twice"): stale since the two-pass design.
   - README game table and `docs/images/reaction.png`: label the screenshot "Reaction (lab SRT)" and add a screenshot of the battery step (`app/scripts/make_screenshots.py` can take it).

4. **Report R3 as an estimate, and re-justify its margin.** SAFE-NOW for the reporting; DESIGN-CHANGE for the decision rule.
   In `_r3_row` (line 23296), print the pass 2 minus pass 1 shift with its 90 percent interval as the primary result, and beside it the chance of passing at zero true shift for the observed spread of differences (55 to 80 percent at n = 10, simulation). Replace the "one 60 Hz frame" reason in the `COHORT_R3_MARGIN_MS` comment (23245-23249) and design doc Section 1.1 with a smallest-effect rationale fixed before data (Lakens, Scheel and Isager 2018): the rig's resolution for a block median is about 1 to 2 ms (arithmetic), so it cannot justify 20 ms; a related-studies justification can, for example the practice sizes in the literature (+7 ms back to back, Deary 2011; -19 ms at one week, Woods 2015 two-choice). If the verdict stays, state that at n = 10 a fail is expected about half the time even with no practice.

5. **Add a person-relative lapse and response speed.** SAFE-NOW (new rows; `lapse_like_rate` unchanged). DESIGN-CHANGE only if the primary metric is redefined.
   In `ReactionMode.block_stats` (1043-1122) add `n_lapse_2x_median` (RTs at or over twice the block median, the older PVT form in Basner and Dinges 2011) and `mean_speed_per_s` (mean of 1000/RT). In `_cohort_reaction` (20372) emit them. Reword R-lapse in `MODE_LIT["reaction"]` (25122 onward): 500 ms is a visual simple-RT convention, and for this task the row is descriptive.

6. **Fix the catch-trial schedule and length.** DESIGN-CHANGE (task parameter, before any participant; log it).
   In `ReactionMode.__init__` (160-285) draw a fixed number of catch positions per block from `self.rng` (for example two among the first 22 attempts, new key `reaction.catch_trials_per_block`), and use it in `_begin_trial` (451) in place of `self.rng.random() < self.catch_rate`. Set `catch_wait_s` to at least `fp_max_s` plus 0.5 s (`default.yaml` 831: 8.0 to 9.5). This mirrors the Buzz Hunt fix in the 27 September code review and removes the 8 s give-away.

7. **Add practice trials to both passes.** DESIGN-CHANGE (adds about 25 s per block, arithmetic).
   New key `reaction.practice_trials` (default 0; battery override 4 plus 1 catch). In `ReactionMode`, the first N attempts run the full trial loop but are tagged `;practice` in `_stimulus_tag` and kept out of `completed`, the tallies and `_valid_rts`; `reaction_frame` treats them as events. Deary (8) and Woods (20) both give practice first [FT]. If time forbids, the SAFE-NOW fallback is a sensitivity median without each block's first four scorable trials.

8. **Measure the lab PC before collection and never pool RT across machines.** SAFE-NOW (procedure and checks).
   Run `scripts/audio_latency.py --write` on the lab PC, and `scripts/latency_check.py` with a phone at 240 fps for the tile. Extend `scripts/check_sitting.py` so a Reaction block on an unmeasured profile reads CHECK, as Rhythm does. In the notebook, split cohort Reaction rows by `platform` or the latency values in `config_snapshot` and print a warning if they differ. Evidence: pygame audio lag 42.81 ms on macOS and 106.83 ms on Windows 10 (Bridges et al. 2020 [FT]); the channel lags decide which cue wins the race (Q7).

9. **Anticipation cut: sensitivity first, then decide.** SAFE-NOW (analysis); DESIGN-CHANGE if `anticipation_cut_ms` moves to 150.
   Add a conditional accuracy function to `sec_reaction_checks` (accuracy in 50 ms RT bins, including the 100 to 150 ms bin and the logged `anticipation` rows' `pressed_lane`), and a median with a 150 ms cut beside the registered one.

10. **Exempt Reaction from loud trials.** DESIGN-CHANGE.
    In `engine.on_stim_multi` (8624 onward) extend the syllables exemption for `is_loud` to `current_block == "reaction"`. The alternative, a battery override of `audio.loud_trial.fraction: 0`, changes every mode. SAFE-NOW fallback: report RT on `loud_trial` rows against the rest and a median without them. In Diederich and Colonius, a 10 dB louder tone gave 5 to 13 ms faster simple RT [FT, Table 2].

11. **Replace the ex-Gaussian and unify p10.** SAFE-NOW.
    In `_reaction_mode_group` drop the pooled method-of-moments fit (11271-11292) or restrict it to per-person fits with a bootstrap interval, labelled imprecise below 100 RTs (Lacouture and Cousineau 2008 [FT]); if shape is wanted, fit quantiles averaged across people (Vincentised). Use `reaction_p10` at lines 11358, 11388, 11460 and 26116.

12. **Speed-accuracy and error structure.** SAFE-NOW.
    Add to `sec_reaction_checks`: errors by finger distance (1, 2, 3), wrong-press RT against correct RT, the co-press share per person with a median excluding co-press trials, and the balanced integration score (Liesefeld and Janczyk 2019 [FT]) as an exploratory row.

13. **Scoring tiers in the battery.** DESIGN-CHANGE (low priority).
    Give Reaction a flat point per correct press (a `ScoreConfig` with equal tiers passed by `begin_reaction_block`, engine 4386) and no streak multiplier, keeping the RT readout, which is the PVT convention. The 200 and 500 ms tiers act as a speed payoff (Heitz 2014 [FT]).

14. **T1 wording.** DESIGN-CHANGE (text of a reported prediction).
    Design doc Section 1.1 and `COHORT_RELIABILITY_METRICS` (29225): "good (0.75 to 0.9)", with the benchmarks 0.71 (Deary retest halved to 20 trials, arithmetic), 0.72 to 0.77 (Woods weekly, single session) and 0.63 to 0.77 (Hedge, three weeks).

15. **After collection.** AFTER-COLLECTION.
    A cue-channel preset (tile only, buzz only, tone only, all three) with a race-model test (Miller 1982; Diederich and Colonius 2004); a simple-RT block for the choice-simple contrast; a shorter foreperiod distribution (for example 1.0 s + exponential mean 1.5 s, maximum 5 s; mean 2.2 s, arithmetic); repeats allowed at the chance rate with balanced counts; stimulus stamps on the flip (the modes-review's after-collection list).

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Positive-rho message rewritten; pooled RT on foreperiod slope (ms per s) with participant random intercept and previous-foreperiod term | `_reaction_mode_group`; `sec_cohort_validity` R1 | Han and Proctor 2022 [FT]; Los et al. 2014 [FT]; Grabenhorst et al. 2019 [FT]; REML as in analysis_methods.md |
| R1 one-sided (after approval) | `sec_cohort_validity`, `sec_reaction_checks`, `MODE_LIT` | Q1 |
| R3 shift and interval as the primary output, with the pass chance at zero shift | `_r3_row` | Lakens et al. 2018 [FT] |
| Conditional accuracy function; 150 ms sensitivity median | `sec_reaction_checks` | Woods CRT window [FT]; Berger and Kiefer 2021 [FT]; Yellott via Heitz 2014 [FT] |
| Person-relative lapse (2 x median) and mean 1/RT | `_cohort_reaction`, `block_stats` | Basner and Dinges 2011 [FT] |
| Per-person ex-Gaussian removed or bootstrapped; group shape by averaged quantiles | `_reaction_exgaussian_fit`, `_reaction_mode_group` | Lacouture and Cousineau 2008 [FT]; Ratcliff 1993 [ABS] |
| One p10 definition | lines 11358, 11388, 11460, 26116 | internal consistency |
| Per-finger RT only from a mixed model over the cohort (finger fixed, participant random); no per-person finger medians from five trials | `per_finger_table` callers | Miller 1988 [ABS]; Rousselet and Wilcox 2020 [FT] |
| Errors by finger distance; error RT against correct RT; co-press share and a median without co-presses | `sec_reaction_checks` | Schweizer et al. 2000 [ABS]; Liesefeld and Janczyk 2019 [FT] |
| Loud-trial sensitivity | `_reaction_mode_group` | Diederich and Colonius 2004 Table 2 [FT] |
| Board-clock sensitivity row (median RT with each press re-timed on its sample) | reuse `press_timing` as the chords and rhythm chapters do | modes-review.md device facts |
| Catch false alarms as pooled counts, not per-person rates (about two catch trials a block) | `_cohort_reaction` | arithmetic (Q3) |
| R3 and T1 described by order (A against B) | `_r3_row`, `sec_cohort_reliability` | order A puts pass 1 first in the sitting (code) |
| Machine or latency split before pooling | cohort loaders | Bridges et al. 2020 [FT] |
| First-four-trials-out sensitivity median (if no practice trials) | `_reaction_mode_group` | Collie 2003; Falleti 2006 [ABS] |

Keep as they are: the median headline, the permutation split-half with its interval (Parsons et al. 2019, cited in analysis_methods.md), no SEM or MDC from a split-half, ICC(2,1) with the exact interval, and the within-session wording.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Four-choice RT, 18 to 25 years | 388.0 ms (SD 45.0), within-person SD 69.4 ms, 3.0 percent errors | Deary et al. 2011 Table 1 [FT] | visual only, two fingers per hand, keyboard, 1 to 3 s ISI, 8 practice + 40 trials |
| Simple RT, same people | 243.1 ms (SD 17.6) | Deary et al. 2011 Table 1 [FT] | index finger, visual |
| Four-choice RT, numbers box | 459.4 ms (SD 42.5) | Deary et al. 2011 Table 1 [FT] | the same people were 71.4 ms slower on another device with number stimuli (arithmetic), which the authors put down to the stimulus coding |
| Simple RT, 18 to 24 years, 1,469-person study | 217.9 ms; 200 ms after 17.8 ms hardware correction | Woods et al. 2015 SRT factors, Table 2 [FT] | calibrated gaming mouse |
| Two-choice CRT, 18 to 24 years | 472 ms (SD 58.8) | Woods et al. 2015 CRT age, Table 2 [FT] | feature-conjunction task, adaptive SOA |
| Vibrotactile simple RT, young adults | about 200 ms (head) to 230 ms (foot); coin motor 46 ms slower than a C-2 tactor | Bao et al. 2019 [FT] | thumb trigger, not a finger-under-buzz choice |
| Multisensory gain | up to 9.4 percent (bimodal) and 13.1 percent (trimodal) of the fastest unimodal RT | Diederich and Colonius 2004 [FT] | four trained observers, simple RT |
| Accessory tone gain | 314 to 275 ms | Giray and Ulrich 1993, via Bausenhart and Ulrich 2026 [FT] | visual focused-attention task |
| PVT definitions | false start: no stimulus or under 100 ms; lapse: 500 ms or more, or twice the mean | Basner and Dinges 2011 Table 3 [FT] | visual simple RT; auditory thresholds lower |

How to use them: report the device's numbers as the device's own, measured to an audio-tactile-visual cue with a 1.5 to 9 s exponential foreperiod, a force-threshold press and roughly 35 to 55 ms of rig delay on the visual route (arithmetic from the repository's timing facts). The published values are an order-of-magnitude frame, never a norm to test against; Deary and colleagues themselves decline to publish norms because hardware differs.

### 6.2 Reliability and practice expectations

- Within-session ICC(2,1) of the 20-trial median: most likely "good" (0.75 to 0.9); the interval at n = 10 will span two or three bands (Q9, simulation; Bonett 2002 [META] as the design already says).
- Benchmarks: 0.71 for a 20-trial four-choice mean back to back (Deary retest halved, arithmetic); 0.72 to 0.77 single-session at one week (Woods two-choice, 140 trials [FT]); 0.63 to 0.77 at three weeks (Hedge et al. 2018, 240 trials [FT]).
- Pass 2 minus pass 1: anything from about +7 ms (back to back, Deary [FT]) to about -19 ms (one week, Woods two-choice [FT]) is consistent with the literature; practice at brief intervals concentrates in the first repeat (Collie; Falleti [ABS]).
- Internal consistency will be high (alpha 0.97 at 40 trials, Deary [FT]) and says nothing about day-to-day stability.

### 6.3 Claims to avoid

- A Hick slope, "2-bit choice" or information rate from this task.
- Any comparison of absolute RTs with published norms, visual-only tasks, or the PVT.
- "Vigilance" or "lapses of attention" from RTs over 500 ms in a four-choice task.
- A positive RT against foreperiod slope as evidence of fatigue or slowing.
- "No practice effect" from an R3 pass at n = 10, or "practice" from a fail, without the interval.
- The within-session ICC as test-retest reliability between days.
- Per-finger differences from five trials per finger per person.
- Any claim that the three cue channels add up to a single-modality RT; the channel mix, the channel latencies and the computer are part of the number.
- Transfer beyond the task (Owen et al. 2010 [FT]).

---

## 7. Sources

Retrieved and checked on 30 September 2026 through Europe PMC, PubMed E-utilities, Crossref, OpenAlex and publisher or repository pages.

1. Bao T, Su L, Kinnaird C, Kabeto M, Shull PB, Sienko KH. 2019. Vibrotactile display design: Quantifying the importance of age and various factors on reaction times. PLoS One 14(8):e0219737. DOI 10.1371/journal.pone.0219737. PMID 31398207. PMC6688825. [FT: Results Parts I to IV, Table 2, Discussion]
2. Basner M, Dinges DF. 2011. Maximizing sensitivity of the psychomotor vigilance test (PVT) to sleep loss. Sleep 34(5):581-591. DOI 10.1093/sleep/34.5.581. PMID 21532951. PMC3079937. [FT: Introduction, Table 2, Table 3 and footnotes, Methods]
3. Basner M, Mollicone D, Dinges DF. 2011. Validity and sensitivity of a brief psychomotor vigilance test (PVT-B) to total and partial sleep deprivation. Acta Astronautica 69(11-12):949-959. DOI 10.1016/j.actaastro.2011.07.015. PMID 22025811. PMC3197786. [FT: Introduction, Methods, Results, Discussion]
4. Basner M, Hermosillo E, Nasrini J, McGuire S, Saxena S, Moore TM, Gur RC, Dinges DF. 2018. Repeated administration effects on psychomotor vigilance test performance. Sleep 41(1):zsx187. DOI 10.1093/sleep/zsx187. PMID 29126328. [ABS]
5. Bausenhart KM, Ulrich R. 2026. What is prepared in temporal preparation? A review and a historical appreciation. Frontiers in Psychology 17:1768431. DOI 10.3389/fpsyg.2026.1768431. PMID 42325310. PMC13275726. [FT: Box 1, sections on foreperiod paradigms, expectancy and hazard, sequential effects, CNV]
6. Berger A, Kiefer M. 2021. Comparison of different response time outlier exclusion methods: a simulation study. Frontiers in Psychology 12:675558. DOI 10.3389/fpsyg.2021.675558. PMID 34194371. PMC8238084. [FT: Introduction, Table 1, Table 4, Discussion]
7. Bonett DG. 2002. Sample size requirements for estimating intraclass correlations with desired precision. Statistics in Medicine 21(9):1331-1335. DOI 10.1002/sim.1108. PMID 12111881. [META]
8. Bridges D, Pitiot A, MacAskill MR, Peirce JW. 2020. The timing mega-study: comparing a range of experiment generators, both lab-based and online. PeerJ 8:e9414. DOI 10.7717/peerj.9414. PMID 33005482. PMC7512138. [FT: Table 2 and Results for lab-based packages]
9. Buckolz E, Rodgers R. 1980. The influence of catch trial frequency on simple reaction time. Acta Psychologica 44(2):191-200. DOI 10.1016/0001-6918(80)90067-0. [META]
10. Capizzi M, Correa A, Wojtowicz A, Rafal RD. 2015. Foreperiod priming in temporal preparation: Testing current models of sequential effects. Cognition 134:39-49. DOI 10.1016/j.cognition.2014.09.002. [META; findings as reported in Han and Proctor 2022]
11. Collie A, Maruff P, Darby DG, McStephen M. 2003. The effects of practice on the cognitive test performance of neurologically normal individuals assessed at brief test-retest intervals. Journal of the International Neuropsychological Society 9(3):419-428. DOI 10.1017/S1355617703930074. PMID 12666766. [ABS]
12. Deary IJ, Liewald D, Nissan J. 2011. A free, easy-to-use, computer-based simple and four-choice reaction time programme: the Deary-Liewald reaction time task. Behavior Research Methods 43(1):258-268. DOI 10.3758/s13428-010-0024-1. PMID 21287123. [FT: Method, Results, Table 1, Table 5, Discussion]
13. Der G, Deary IJ. 2006. Age and sex differences in reaction time in adulthood: results from the United Kingdom Health and Lifestyle Survey. Psychology and Aging 21(1):62-73. DOI 10.1037/0882-7974.21.1.62. PMID 16594792. [ABS]
14. Diederich A, Colonius H. 2004. Bimodal and trimodal multisensory enhancement: effects of stimulus onset and intensity on reaction time. Perception and Psychophysics 66(8):1388-1404. DOI 10.3758/BF03195006. PMID 15813202. [FT: Method, Tables 2 to 5, Discussion, race-model section]
15. Dinges DF, Powell JW. 1985. Microcomputer analyses of performance on a portable, simple visual RT task during sustained operations. Behavior Research Methods, Instruments, and Computers 17(6):652-655. DOI 10.3758/BF03200977. [META]
16. Drazin DH. 1961. Effects of foreperiod, foreperiod variability, and probability of stimulus occurrence on simple reaction time. Journal of Experimental Psychology 62(1):43-50. DOI 10.1037/h0046860. [META]
17. Falleti MG, Maruff P, Collie A, Darby DG. 2006. Practice effects associated with the repeated assessment of cognitive function using the CogState battery at 10-minute, one week and one month test-retest intervals. Journal of Clinical and Experimental Neuropsychology 28(7):1095-1112. DOI 10.1080/13803390500205718. PMID 16840238. [ABS]
18. Forster B, Cavina-Pratesi C, Aglioti SM, Berlucchi G. 2002. Redundant target effect and intersensory facilitation from visual-tactile interactions in simple reaction time. Experimental Brain Research 143(4):480-487. DOI 10.1007/s00221-002-1017-9. PMID 11914794. [ABS]
19. Giray M, Ulrich R. 1993. Motor coactivation revealed by response force in divided and focused attention. Journal of Experimental Psychology: Human Perception and Performance 19(6):1278-1291. DOI 10.1037/0096-1523.19.6.1278. [META; figure as reported in Bausenhart and Ulrich 2026]
20. Girard S, Collignon O, Lepore F. 2011. Multisensory gain within and across hemispaces in simple and choice reaction time paradigms. Experimental Brain Research 214(1):1-8. DOI 10.1007/s00221-010-2515-9. PMID 21161190. [FT: author's submitted version in the UCLouvain DIAL repository; Method, Results]
21. Grabenhorst M, Michalareas G, Maloney LT, Poeppel D. 2019. The anticipation of events in time. Nature Communications 10:5802. DOI 10.1038/s41467-019-13849-0. PMID 31862912. PMC6925136. [FT: Results, Figures 2 to 4, Methods on distributions and catch trials, Discussion]
22. Han T, Proctor RW. 2022. Revisiting variable-foreperiod effects: evaluating the repetition priming account. Attention, Perception, and Psychophysics 84(4):1193-1207. DOI 10.3758/s13414-022-02476-5. PMID 35391659. PMC8989257. [FT: Introduction, Experiment 1 Method and Results, Table 1, General Discussion]
23. Hecht D, Reiner M, Karni A. 2008. Multisensory enhancement: gains in choice and in simple response times. Experimental Brain Research 189(2):133-143. DOI 10.1007/s00221-008-1410-0. PMID 18478210. [ABS]
24. Hedge C, Powell G, Sumner P. 2018. The reliability paradox: Why robust cognitive tasks do not produce reliable individual differences. Behavior Research Methods 50(3):1166-1186. DOI 10.3758/s13428-017-0935-1. PMID 28726177. PMC5990556. [FT: Method, Tables 1 and 2, section on trial numbers]
25. Heitz RP. 2014. The speed-accuracy tradeoff: history, physiology, methodology, and behavior. Frontiers in Neuroscience 8:150. DOI 10.3389/fnins.2014.00150. PMID 24966810. PMC4052662. [FT: sections on models and SAT methodology (instructions, payoffs, deadlines)]
26. Hick WE. 1952. On the rate of gain of information. Quarterly Journal of Experimental Psychology 4(1):11-26. DOI 10.1080/17470215208416600. [META; content as reported in Proctor and Schneider 2018]
27. Hyman R. 1953. Stimulus information as a determinant of reaction time. Journal of Experimental Psychology 45(3):188-196. DOI 10.1037/h0056940. [META; content as reported in Proctor and Schneider 2018]
28. Klemmer ET. 1956. Time uncertainty in simple reaction time. Journal of Experimental Psychology 51(3):179-184. DOI 10.1037/h0042317. [META; content as reported in Bausenhart and Ulrich 2026]
29. Koo TK, Li MY. 2016. A guideline of selecting and reporting intraclass correlation coefficients for reliability research. Journal of Chiropractic Medicine 15(2):155-163. DOI 10.1016/j.jcm.2016.02.012. PMID 27330520. PMC4913118. [META]
30. Kornblum S. 1969. Sequential determinants of information processing in serial and discrete choice reaction time. Psychological Review 76(2):113-131. DOI 10.1037/h0027245. [META; content as reported in Proctor and Schneider 2018]
31. Lacouture Y, Cousineau D. 2008. How to use MATLAB to fit the ex-Gaussian and other probability functions to a distribution of response times. Tutorials in Quantitative Methods for Psychology 4(1):35-45. DOI 10.20982/tqmp.04.1.p035. [FT: Monte Carlo study, Table 1]
32. Lakens D. 2017. Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. Social Psychological and Personality Science 8(4):355-362. DOI 10.1177/1948550617697177. [META]
33. Lakens D, Scheel AM, Isager PM. 2018. Equivalence testing for psychological research: a tutorial. Advances in Methods and Practices in Psychological Science 1(2):259-269. DOI 10.1177/2515245918770963. [FT: author's accepted version on OSF (osf.io/v3zkt); sections on objective and subjective justification of the smallest effect size of interest]
34. Leonard JA. 1959. Tactual choice reactions: I. Quarterly Journal of Experimental Psychology 11(2):76-83. DOI 10.1080/17470215908416294. [META; content as reported in Proctor and Schneider 2018]
35. Liesefeld HR, Janczyk M. 2019. Combining speed and accuracy to control for speed-accuracy trade-offs(?). Behavior Research Methods 51(1):40-60. DOI 10.3758/s13428-018-1076-x. PMID 30022459. [FT: Introduction, definitions of IES, RCS, LISAS and BIS, Figure 3]
36. Loh S, Lamond N, Dorrian J, Roach G, Dawson D. 2004. The validity of psychomotor vigilance tasks of less than 10-minute duration. Behavior Research Methods, Instruments, and Computers 36(2):339-346. DOI 10.3758/BF03195580. PMID 15354700. [ABS]
37. Los SA, Kruijne W, Meeter M. 2014. Outlines of a multiple trace theory of temporal preparation. Frontiers in Psychology 5:1058. DOI 10.3389/fpsyg.2014.01058. PMID 25285088. PMC4168672. [FT: sections on the foreperiod-distribution effect, the hazard function and MTP, Figures 1 and 3]
38. Los SA, Kruijne W, Meeter M. 2017. Hazard versus history: temporal preparation is driven by past experience. Journal of Experimental Psychology: Human Perception and Performance 43(1):78-88. DOI 10.1037/xhp0000279. PMID 27808547. [ABS]
39. Massar SAA, Lim J, Sasmita K, Chee MWL. 2016. Rewards boost sustained attention through higher effort: a value-based decision making approach. Biological Psychology 120:21-27. DOI 10.1016/j.biopsycho.2016.07.019. PMID 27498294. [ABS]
40. McGraw KO, Wong SP. 1996. Forming inferences about some intraclass correlation coefficients. Psychological Methods 1(1):30-46. DOI 10.1037/1082-989X.1.1.30. [META]
41. Miller J. 1982. Divided attention: evidence for coactivation with redundant signals. Cognitive Psychology 14(2):247-279. DOI 10.1016/0010-0285(82)90010-X. PMID 7083803. [META]
42. Miller J. 1988. A warning about median reaction time. Journal of Experimental Psychology: Human Perception and Performance 14(3):539-543. DOI 10.1037/0096-1523.14.3.539. PMID 2971778. [ABS]
43. Naatanen R. 1971. Non-aging fore-periods and simple reaction time. Acta Psychologica 35(4):316-327. DOI 10.1016/0001-6918(71)90040-0. [META; findings as reported in Los et al. 2014 and Bausenhart and Ulrich 2026]
44. Naatanen R. 1972. Time uncertainty and occurrence uncertainty of the stimulus in a simple reaction time task. Acta Psychologica 36(6):492-503. DOI 10.1016/0001-6918(72)90029-7. [META]
45. Niemi P, Naatanen R. 1981. Foreperiod and simple reaction time. Psychological Bulletin 89(1):133-162. DOI 10.1037/0033-2909.89.1.133. [META]
46. Nisiyama M, Ribeiro-do-Valle LE. 2014. Relative performance of the two hands in simple and choice reaction time tasks. Brazilian Journal of Medical and Biological Research 47(1):80-89. DOI 10.1590/1414-431X20132932. PMID 24345871. PMC3932976. [FT: Abstract, Methods (participants, anticipation criterion), Results]
47. Owen AM, Hampshire A, Grahn JA, Stenton R, Dajani S, Burns AS, Howard RJ, Ballard CG. 2010. Putting brain training to the test. Nature 465(7299):775-778. DOI 10.1038/nature09042. PMID 20407435. PMC2884087. [FT: Abstract, Results]
48. Plant RR, Turner G. 2009. Millisecond precision psychological research in a world of commodity computers: new hardware, new problems? Behavior Research Methods 41(3):598-614. DOI 10.3758/BRM.41.3.598. PMID 19587169. [ABS]
49. Proctor RW, Schneider DW. 2018. Hick's law for choice reaction time: a review. Quarterly Journal of Experimental Psychology 71(6):1281-1299. DOI 10.1080/17470218.2017.1322622. PMID 28434379. [FT: author copy; sections on Hick's experiments, S-R compatibility, Practice, Sequential effects]
50. Ratcliff R. 1993. Methods for dealing with reaction time outliers. Psychological Bulletin 114(3):510-532. DOI 10.1037/0033-2909.114.3.510. PMID 8272468. [ABS]
51. Rouder JN, Haaf JM. 2019. A psychometrics of individual differences in experimental tasks. Psychonomic Bulletin and Review 26(2):452-467. DOI 10.3758/s13423-018-1558-y. PMID 30911907. [FT: author's version 2 of July 2018 on PsyArXiv (DOI 10.31234/osf.io/f3h2k); sections on portability, Figure 1, and the hierarchical model]
52. Rousselet GA, Wilcox RR. 2020. Reaction times and other skewed distributions: problems with the mean and the median. Meta-Psychology 4:MP.2019.1630. DOI 10.15626/MP.2019.1630. [FT: Introduction, bias and bias-correction sections]
53. Schweizer R, Maier M, Braun C, Birbaumer N. 2000. Distribution of mislocalizations of tactile stimuli on the fingers of the human hand. Somatosensory and Motor Research 17(4):309-316. DOI 10.1080/08990220020002006. PMID 11125874. [ABS]
54. Seibold VC, Bausenhart KM, Rolke B, Ulrich R. 2011. Does temporal preparation increase the rate of sensory information accumulation? Acta Psychologica 137(1):56-64. DOI 10.1016/j.actpsy.2011.02.006. PMID 21440239. [ABS]
55. Steinborn MB, Langner R, Huestegge L. 2017. Mobilizing cognition for speeded action: try-harder instructions promote motivated readiness in the constant-foreperiod paradigm. Psychological Research 81(6):1135-1151. DOI 10.1007/s00426-016-0810-1. PMID 27650820. [ABS]
56. Teichner WH, Krebs MJ. 1974. Laws of visual choice reaction time. Psychological Review 81(1):75-98. DOI 10.1037/h0035867. [META; content as reported in Proctor and Schneider 2018]
57. ten Hoopen G, Akerboom S, Raaymakers E. 1982. Vibrotactual choice reaction time, tactile receptor systems and ideomotor compatibility. Acta Psychologica 50(2):143-157. DOI 10.1016/0001-6918(82)90004-X. PMID 7102358. [META]
58. Ulrich R, Giray M. 1989. Time resolution of clocks: effects on reaction time measurement. Good news for bad clocks. British Journal of Mathematical and Statistical Psychology 42(1):1-12. DOI 10.1111/j.2044-8317.1989.tb01111.x. [META]
59. Weir JP. 2005. Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. Journal of Strength and Conditioning Research 19(1):231-240. DOI 10.1519/15184.1. PMID 15705040. [META]
60. Whelan R. 2008. Effective analysis of reaction time data. The Psychological Record 58(3):475-482. DOI 10.1007/BF03395630. [META]
61. Woods DL, Wyma JM, Yund EW, Herron TJ, Reed B. 2015. Factors influencing the latency of simple reaction time. Frontiers in Human Neuroscience 9:131. DOI 10.3389/fnhum.2015.00131. PMID 25859198. PMC4374455. [FT: Introduction, Table 1, Methods (timing calibration, response window), Table 2, Results on false alarms and handedness]
62. Woods DL, Wyma JM, Yund EW, Herron TJ, Reed B. 2015. Age-related slowing of response selection and production in a visual choice reaction time task. Frontiers in Human Neuroscience 9:193. DOI 10.3389/fnhum.2015.00193. PMID 25954175. PMC4407573. [FT: Table 1, Table 2, Methods (task, hardware, response window)]
63. Woods DL, Wyma JM, Yund EW, Herron TJ. 2015. The effects of repeated testing, simulated malingering, and traumatic brain injury on visual choice reaction time. Frontiers in Human Neuroscience 9:595. DOI 10.3389/fnhum.2015.00595. PMID 26635569. PMC4656817. [FT: Methods, Table 2, test-retest and learning sections, Figure 6 legend]
64. Woods DL, Wyma JM, Yund EW, Herron TJ. 2015. The effects of repeated testing, simulated malingering, and traumatic brain injury on high-precision measures of simple visual reaction time. Frontiers in Human Neuroscience 9:540. DOI 10.3389/fnhum.2015.00540. PMID 26617505. PMC4637414. [FT: Methods, test-retest reliability and learning sections]

Counts: 64 sources; 26 FT, 15 ABS, 23 META. Of the 41 sources whose own text supplied a number or finding (FT plus ABS), 26 are FT. Every META source whose content is used above was read through a named FT secondary source; the other META entries are method references the design already uses (Koo and Li, McGraw and Wong, Weir, Bonett, Lakens 2017) or the primary papers behind the code's own citations.

Not re-read here and left as the design already cites them: Peters 1980, Hubel et al. 2013 (R2, dropped), Heathcote, Brown and Mewhort 2000, Kantak and Winstein 2012, Zeinalzadeh et al. 2021, Bland and Altman 1986, Luce 1986, Dean et al. 2012, Hohle 1965, Palmer 2024 (config comment on cue channels).

### Simulation assumptions (for Sections 2 and 4)

Ten people, 20 valid trials per pass, RT = person location + ex-Gaussian noise (sigma 35 ms, tau 60 ms, within-person SD about 70 ms, matching Deary's young within-person SD 69.4; or sigma 30, tau 42, SD about 52 ms, the median of the pilot blocks' SDs), between-person SD 45 ms (Deary young) or 30 ms, a person-level pass-to-pass shift with SD 10 ms, foreperiods drawn from the shipped truncated exponential, 1,500 to 2,000 runs per cell; ICC(2,1) by the McGraw and Wong absolute-agreement single-measure formula; R3 by the 90 percent t interval; R1 by the cohort median of per-person Spearman rho. The cue-predictability figures came from 2,000 blocks of a scratch copy of `scheduling.BalancedScheduler` with copies = 5.
