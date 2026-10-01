# Adaptive mode: deep research audit

1 October 2026. Scope: the study battery's Adaptive step, `app/finger_rehab/game/modes/adaptive.py` (mode key `adaptive`) and its controller `app/finger_rehab/analytics/adaptive.py`, with their config, screen, logging and the notebook analysis. Mirror reuses the same controller and is out of scope.

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source, or in the repository's Reaction review, `docs/research/deep/reaction.md`, which read it in full). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result from a headless replica of the shipped controller (verbatim copies of `analytics/adaptive.py` and `game/scheduling.py`) driven by simulated hands, assumptions at the end of Section 7; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository. Line numbers are those of the working tree on 1 October 2026 (HEAD 37dce13 plus uncommitted edits); `engine.py`, `screens.py`, `default.yaml` and the run sheet were being edited on the same day, so function names are given with each line number.

---

## 1. What the mode does now

### 1.1 The trial loop under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Block start | GET READY card with a number counting down. No instruction line for Adaptive (Echo, Chords and Muscle Memory now have one) | 3.0 s | `screens.py` `GameplayScreen.GET_READY_LINES` (3743); `default.yaml` `game.start_countdown_s` |
| Material | Fresh seed per block unless `adaptive.seed` is set; seed, trial count and start pace written to raw.csv as `adaptive_config` | random | `engine.py` `begin_adaptive_block` (5194) |
| Start pace | 30 BPM: a cue every 2.0 s, press window 1.8 s | 30 BPM | `default.yaml` 673 |
| Cue | The cued finger's tile lights in its colour on grey idle tiles and its timing bar runs for the window; the buzzer under that finger runs 250 ms (repeated 150 ms firmware pulses); the finger's lane tone plays (C4, E4, G4, C5, 0.12 s); every tenth cue is 35 percent louder. No separate metronome click plays: the 2 kHz click is only used by Rhythm's metronome | all channels on | `engine.py` `on_stim_multi` (8672, tone at 8923); `audio/engine.py` 103 and `play_stim` (317); `default.yaml` 493, 1849-1851; `screens.py` `NEUTRAL_IDLE_BLOCKS` (3138) |
| Finger order | Four-cue sequences drawn from the current weights, regenerated every four trials and at every recovery entry or exit; a floor of 0.15 of the block per finger; no finger twice running | `block_size` 4, `min_finger_share` 0.15 | mode `_fire` 158-184, `_finish` 321-331; analytics `generate_sequence` 502-544; `scheduling.py` `FloorWeightedScheduler` (240, no-repeat at 310); `default.yaml` 664, 693 |
| Weights | weight = max(0.05, 1 minus the finger's hit EMA) to the power 2.5, plus 0.1, normalised; in recovery 0.70 on the finger with the best hit EMA and 0.10 on each other | `weakness_bias` 2.5 | analytics `lane_weights` 465-477, `_recovery_weights` 479-489 |
| Timing | The next cue fires once the trial is closed and 60/BPM s have passed since the last cue; the window is 0.9 of the cadence, checked every frame | `timeout_factor` 0.90 | mode `update` 131-156; analytics `current_timeout_s` 436-441; `default.yaml` 696 |
| Response | The first press on the cued finger closes the trial; RT is timed from the update tick that fired the cue. Any wrong-finger press before it makes the trial a Miss and costs 3 points per press; a press with no trial open is an idle press (1 point off, raw event, not scored); no correct press inside the window is a timeout Miss | | mode `_handle_press` 186-215, `_finish` 268-319; `default.yaml` 734, 744 |
| Controller update | After every trial `record()` then `next_bpm()`; then the engine counts misses in a row: the third enters recovery (pace down 25 BPM, strongest-finger weights) and any hit leaves it | threshold 3 | mode 311-331; `engine.py` `_update_streak` (8504), `_recovery_threshold` (283); analytics `enter_recovery` 159-166 |
| Block end | 40 trials | 40 | battery override `game.total_trials` (`default.yaml` 2079) |
| Hardware loss | A press-less close while a board is down is logged `device_drop` and kept out of the controller and the streak | | mode 278-288; `engine.py` `log_trial` |

Window and gap at a given pace (arithmetic): 60 BPM 900 ms window, 100 ms from window close to the next cue; 90 BPM 600 and 67 ms; 120 BPM 450 and 50 ms; 150 BPM 360 and 40 ms; 180 BPM 300 and 33 ms.

Place in the sitting (config on 1 October 2026, changed that day): order A step 7 of 12, after Buzz Hunt and before Muscle Memory; order B step 4, after Buzz Hunt. That is about 23 and 15 minutes after LOG IN (arithmetic from the measured block minutes in design doc Section 2.3). Every participant plays the right hand, which is the dominant hand only for right-handers. The 30 and 60 minute sittings play Adaptive again in pass 2 (60 minute: step 15 of 16 in order A, 14 in order B). Measured block length: 30 to 43 s on the pilot blocks (pilot), 0.46 min in the design doc's simulated sittings (design doc), median 26 s in this simulation.

### 1.2 The pace controller (`next_bpm`, analytics 239-434)

- What it reads. hr: the mean, over fingers already cued, of each finger's hit EMA (alpha 0.25; the first trial on a finger seeds it). qr: the same for press quality (Perfect and Great 1.0, Good 0.75, Late 0.25, Miss 0; a press under 100 ms gets quality 0 but still counts as a hit). util: the mean of the fingers' RT EMAs (alpha 0.2, hits only, starting from 500 ms) divided by the window (analytics 27-60 and 196-237; mode 224-250).
- Gate: no decision until two trials in total. `min_trials` is a total across fingers; the comment at analytics 98-99 says per finger.
- Quality pressure: above 0.80, min(1.5, (hr minus 0.80)/0.10), cut to 0.3 of that if qr is under 0.5; below 0.65, (hr minus 0.65)/0.10, uncapped; inside the band, minus 0.5 if qr is under 0.4, plus 0.3 if qr is over 0.85, else 0 (303-324).
- RT pressure: util over 0.80 gives (0.80 minus util) times 5; under 0.55 gives min(1, (0.55 minus util) times 2) (327-338).
- Combination: the more negative signal wins, except that at hr of 0.65 or more with qr of 0.5 or more the RT guard only tempers the pace, and above the band a probe of at least 0.15 keeps the pace creeping up (341-387; `ABOVE_BAND_PROBE` 149, 0.6 BPM a trial).
- Streak gate: a speed-up needs two hits in a row (times 0.3) or three (full), growing by 0.25 per further hit to 2.5 times (392-404). Slow-downs are multiplied by 1.5 (410-411).
- Step: 4 BPM per unit of pressure (`bpm_step` 10 times 0.4), clamped to plus 15 and minus 20 BPM a trial (minus 10, 15 and 20 for the first three decisions); bounds 10 and 180 BPM (416-433).
- Recovery: minus 25 BPM on the third miss in a row, on top of that trial's own slow-down step (159-166; engine 8504).

Opening climb (arithmetic from the code): with an unbroken run of hits the pace goes 30, 30, 31.8, 37.8, 45.3, 54.3, 64.8, 76.8, 90.3, 105.3 over the first ten trials and can then rise by up to 15 BPM a trial. The 31 August and 2 September pilot blocks show these values exactly up to their first miss (pilot).

Estimate noise (simulation of the estimator alone, 2,000 runs): for a hand whose true hit probability is 0.725, the mean of four per-finger EMAs has an SD of 0.085 and lies outside 0.65 to 0.80 on 39 percent of trials. Its information lags by about 12 trials (arithmetic: the mean age of an EMA with alpha 0.25 is 3 updates of that finger, and a finger is cued about every 4 trials).

### 1.3 Scoring, screen and instructions

- Points (`scoring.py` `classify`; `default.yaml` 698-744): Perfect (100 ms or under) 10, Great (200 ms or under) 6, Good (500 ms or under) 3, Late 1, Miss 0, multiplied by max(1, BPM/60) and by a streak multiplier of up to 1.5 (`engine.py` `_pace_multiplier` 8095, `_streak_multiplier` 8120). Perfect is only reachable by a press under 100 ms.
- Screen: the cued tile and its timing bar; outcome wording from `ui/feedback_bank.py` (`feedback_style: encouraging`, `default.yaml` 1877); streak banners at 10, 20, 30, 50, 75 and 100 in a row (Adaptive is not in `_QUIET_STREAK_MODES`, engine 8502); results screen shows top pace, final pace and score (`screens.py` 6982).
- Instructions: the hub and NEXT UP card say "The pace follows you" (`screens.py` 1531). There is no GET READY line, and the run sheet gives a line to say for every other battery game and none for Adaptive (`docs/study_day/run_sheet.md`, first-time lines). Nothing tells the participant that the bar is the deadline, that the pace rises while they keep up, or that a wrong finger loses the trial even when corrected.

### 1.4 Logging and block summary

- trials.csv: `bpm_at_trial` and `in_recovery` snapshotted at the cue, `timeout_ms` (the window), `streak_at_trial`, `first_incorrect_ms`, `first_incorrect_lane`, `keys_pressed`, `cue_flags`, `loud_trial`, `block_t_s` (engine `_trial_context` 9468).
- raw.csv: `adaptive_config` (seed, trial count, start pace), every press with lane and time, `idle_press` events with lane, time and trial id (mode 198-203).
- Block summary (engine `_build_block_summary` 5871, adaptive context near 6128): `bpm_min` and `bpm_max` over cue-time paces, and `bpm_final`, which is the controller's live value after the last trial (the pace a 41st trial would have had). The notebook's `bpm_final` is the last row's cue-time pace, a different number under the same name.
- `AdaptiveMode` has no `block_stats`. Nothing records the controller's own estimates (hr, qr, util, the pressure applied) or per-finger cue counts in the summary.

### 1.5 Registered checks and the notebook

- A5 and A6 (design Sections 1.5 and 4.6; notebook `_mean_check` calls at 26118-26125): cohort median `bpm_rise` above 0, and cohort median `hit_rate` above 0.65. A row passes when the median and the lower end of its percentile-bootstrap interval clear the reference ("direction only" otherwise); the order-statistic interval is printed beside it. No p value; outside the Holm family. A5 is listed as a feasibility check (design 4.6); A6 is not.
- `_cohort_adaptive` (22161): hit_rate, bpm_max_reached, bpm_final, bpm_rise, share_at_bpm_cap, plus `adaptive_controller_rows` (22121): time_in_band (share of trials 12 to 40 whose trailing 12-trial hit rate lies in 0.65 to 0.80), recovery_entries, first_band_entry (first trial in the band after the pace has climbed 20 BPM), window_at_peak_ms.
- `sec_adaptive` (28568): A1 (the whole-block hit rate inside the band, printed with a yes or no), A2 (against 0.85), A3 (pace, cap and the controller record), A4 (per-finger hit rates), two figures.
- `sec_accuracy` (3789) and `band_side` (177): "below the band (too hard)" and "above the band (too easy)"; the band share there uses a rolling window that starts at 3 trials.
- Registry rows are descriptive (20750-20773); the within-block reading is "harder" (30652); the second-go table reads bpm_max_reached and window_at_peak_ms for the 30 and 60 minute sittings (31778-31779); `censoring_caveat` (1362) warns that adaptive RTs are censored by a moving window.
- `MODE_LIT["adaptive"]` (26984) and `MODE_CLAIM_LIMITS["adaptive"]` (27581).

### 1.6 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| The 65 to 80 band is a design choice; the framework names no success rate | analytics docstring 1-10, `AdaptiveConfig` 66-74; design 1.5; `MODE_LIT` A1 | Guadagnoli and Lee 2004 | Supported: no source sets a band (Q1). Rehabilitation systems run between 50 and 80 percent, and one direct motor test puts the optimum near 68 percent (Q2) |
| About 85 percent for a class of learning algorithms | same; notebook `WILSON` line | Wilson et al. 2019 | Supported, and narrower than it reads: binary classification, gradient descent, Gaussian noise (82 percent Laplacian, 75 percent Cauchy), multi-choice tasks not derived [FT] (Q2) |
| "The FINGER robot line held success rate through robot assistance" | analytics docstring 7-8 | (Taheri et al. 2014 implied) | Supported: a weighted up-down rule on the robot's gains; targets 50, 75 and 99 percent reached 47.7, 73.8 and 97.6 percent in stroke [FT] (Q3) |
| "aim for the 65-80% band around the 70% target" | `default.yaml` 689 | none | The band's centre is 72.5 percent; the long-run equilibrium is about 75 percent (simulation, Q3) |
| The 180 BPM cap is "set by the band": a 280 ms press needs a 300 ms window | `default.yaml` 675-686; `AdaptiveConfig` 81-87 | headless 280 ms player | A 280 ms mean press is faster than healthy four-finger references (343 to 388 ms, Q4); simulated healthy blocks touch the cap 0.2 percent of the time |
| Pilot blocks peaked at 90 to 144 BPM and entered the band at trials 21 to 33 in four of five | `default.yaml` 683-686; design 1.5; `MODE_LIT` A3; claim limits | pilot review | Peaks confirmed; the notebook's own `adaptive_controller_rows` gives entries at trials 22, 22, 22 and 34 and none in the fifth (pilot) |
| A healthy 40-trial block tests how the controller holds the band as well as how fast a hand goes | design 1.5; claim limits | none | Partly: about 14 trials of climb, then 20 to 25 near the limit; time in band cannot exceed about 0.47 with a 12-trial window (Q3, Q6) |
| Three misses drop the pace by 25 BPM; "read the peak" | `MODE_CLAIM_LIMITS`; modes-review | code | Drop confirmed, plus that trial's own slow-down. The peak overshoots the pace the hand holds at 72.5 percent by about 10 BPM (simulation, Q6) |
| "A deadline threshold cannot be recovered from 40 trials" | modes-review, Adaptive | none | A two-parameter fit per block fails; a location-only fit with a cohort slope and a small lapse rate does as well as the peak without its overshoot (simulation, Q6) |
| A5 cannot fail for a healthy hand | design 4.6 | none | Confirmed (simulation, Q6) |
| A6: the controller's steps do not push a healthy hand into failure | design 1.5 | none | Cannot fail by construction (arithmetic and simulation, Q6) |
| The controller regulates the unweighted mean of per-finger EMAs, not the trial share | notebook `sec_accuracy` | code | Correct (code); see the estimate noise in Section 1.2 |
| "Above the band the task is too easy and there is nothing to learn from" | `band_side` docstring (177) | implicit Guadagnoli and Lee | Not supported: no source sets the band, and Wilson's optimum, drawn on the same figure, lies above it (Q1, Q2) |
| A press under 100 ms "cannot be a response to the stimulus" | mode 233-245 | Basner and Dinges 2011 | Consistent with Reaction, but here such a press still counts as a hit, and a wrong press under 100 ms still counts as a wrong finger (Q5) |
| Adaptive "deliberately gives a struggling finger more practice" | `default.yaml` 576-579; `generate_sequence` docstring | none | In a 40-trial healthy block the bias barely moves allocation (simulation; pilot counts 7 to 14 per finger, Q7) |
| `cue_volume`: "the metronome click in classic / adaptive" | `default.yaml` 1799-1801 | none | No click plays in Adaptive; the lane tone is the go signal (code, Q9) |
| Start at 30 because 60 opened above a comfortable pace for stroke patients | `default.yaml` 665-672 | none | Not checked for stroke; for a healthy block 60 would save one or two climb trials (simulation, Q3) |

### 1.7 Pilot blocks on disk (rig check only)

Five complete 40-trial blocks (6 August twice, 31 August, 2 and 3 September 2026; the August ones under `bpm_max` 140) and three incomplete ones (pilot):

- Peaks 90, 111, 125, 144 and 121 BPM; block hit rates 0.925, 0.725, 0.900, 0.775 and 0.725; recovery entries 0, 2, 0, 2 and 1; time in band 0.00 to 0.28; trials 21 to 40 hit rate 0.55 to 0.95, pooled 0.72 over 100 trials; block durations 30.3 to 42.9 s.
- Hit rate by window: 1.3 to 2.1 s 0.96 (n 28); 0.8 to 1.3 s 0.83 (35); 600 to 800 ms 0.86 (63); 500 to 600 ms 0.70 (27); 450 to 500 ms 0.78 (36); 400 to 450 ms 0.50 (6); under 400 ms 0.40 (5). Median RT of hits at 450 to 600 ms windows 345 to 353 ms.
- 25 wrong-finger presses, 19 on a finger next to the cued one. Four were the previous trial's finger within 150 ms of a new cue (13.8, 23.4, 23.5 and 106.5 ms after it), all at the top of a climb and each followed by a recovery entry within four trials; a fifth came at 174 ms. Two hits came under 100 ms (53 and 65 ms).
- Cues per finger 7 to 14 a block; pooled hit rates index 0.82, middle 0.87, ring 0.73, little 0.82.
- One abandoned block (25 September, 11 trials) fell from 30 to the 10 BPM floor by trial 4, a 5.4 s window, after early wrong presses.

---

## 2. Research questions and findings

### Q1. What does the challenge-point framework predict, and does any source set a success band?

- The framework relates practice conditions to skill level and task difficulty and proposes that learning depends on the information arising from performance, optimised along functions of difficulty against skill; it states testable hypotheses (Guadagnoli and Lee 2004 [ABS]). The abstract gives no number.
- Learning against functional difficulty is an inverted U while performance falls steadily; the optimum is better thought of as a zone where performance has started to drop; the point of best performance comes before the point of best learning; and "There is no simple percentage" of how often learners should succeed (Hodges and Lohse 2022, author's preprint, sections on the framework, Figure 2 and motivation [FT]).
- A 2025 scoping review included 100 papers that applied the framework; 46 percent were reviews, chapters or conceptual papers. Studies that tried to measure the optimal challenge point used NASA-TLX and salivary amylase (Akizuki and Ohashi 2015) or individual performance curves (Wadden et al. 2019); the stated limitations include a lack of practical application research (Thomas et al. 2025, Results and "Limitations of the CPF" [FT]). No success rate appears as the challenge point in the review.
- Tests disagree. In a balance task the second-hardest of four levels gave the best retention (Akizuki and Ohashi 2015 [ABS]). In 36 young adults learning mirror star tracing at three difficulties, difficulty changed performance but not acquisition, retention or transfer, and the authors call the evidence for the framework mixed (Bootsma et al. 2018, author's manuscript, Abstract, Introduction and Discussion [FT]). In Parkinson's disease the predictions were broadly supported, but high-demand practice helped, against the framework (Onla-or and Winstein 2008 [ABS]).

Bearing: the docstring's position (a design choice, no number from the framework) is right. Nothing in this literature calls a success rate above 80 percent "nothing to learn from", so `band_side`'s wording goes beyond the evidence.

### Q2. Which success rates have evidence behind them?

- 85 percent: for binary classification learnt by stochastic gradient descent with Gaussian noise, the optimal training error is 15.87 percent; Laplacian noise gives 82 percent accuracy and Cauchy 75 percent; multi-category tasks are left for future work; and the authors note that staircases are commonly set to 80 to 85 percent and that a test in people was still to be done (Wilson et al. 2019, Results equation 6 and Discussion [FT]).
- 68 percent: extending the same argument to a signed, continuous motor error with a two-sided hit criterion gives an optimal error of 31.73 percent, a 68.27 percent success rate. In a Pong task (N = 194, paddle size adjusted to hold 15, 30, 50 or 65 percent error over 70 training trials) the 30 percent group improved most: more than the 15 percent group (t(89) = 3.11, p = 0.003, d = 0.65), not reliably more than the 65 percent group (d = 0.33, p = 0.12) or the 50 percent group (d = 0.20, p = 0.32); the participants' sextile at 31.7 percent error had the highest learning index. There was no retention test; it is an online, single-session preprint (Al-Fawakhiri, Kayani and McDougle 2023, bioRxiv full text, theory section and Results [FT]).
- Error thresholds that steer practice structure rather than difficulty: groups that moved from blocked to more varied practice once they reached 67 or 56 percent accuracy outperformed the random-practice and control groups at retention in a soccer kick (71 novices; Taghizadeh et al. 2026, Abstract and Methods [FT]).
- An easier success criterion alone did not improve learning (80 participants, mini-shuffleboard; Parma et al. 2023 [ABS]).
- Operating points of rehabilitation systems: a hold zone of 50 to 70 percent hits, difficulty up 10 percent above 70 and down 5 percent below 50, every 10 trials (Cameirao et al. 2010, Personalized Training Module [FT]); a 70 percent target, level up at 70 percent or more and down at 20 percent or less, session to session (Metzger et al. 2014, Methods [FT]); targets of 50, 75 and 99 percent (Taheri et al. 2014 [FT]); an assumption, without a source, that full success bores and success under half frustrates (Zimmerli et al. 2012, Discussion [FT]).
- Staircase targets: a one-up two-down rule settles where p squared is 0.5, so 70.7 percent, and one-up three-down at 79.4 percent (arithmetic from the rule; Levitt 1971 [ABS]). With unequal step sizes a staircase can be aimed at any point (Kaernbach 1991 [ABS]); in forced-choice tasks the equal-step rules miss their presumed targets, and specific down to up step ratios of 0.2845, 0.5488, 0.7393 and 0.8415 give 77.85, 80.35, 83.15 and 85.84 percent (Garcia-Perez 1998 [ABS]).

Where sources disagree: Wilson puts the optimum at 85 percent for binary decisions; Al-Fawakhiri puts it near 68 percent for continuous motor error and found 50 percent error no worse at p 0.32; Hodges and Lohse say no single percentage exists. Bearing: 65 to 80 sits inside the range rehabilitation systems use and contains the one direct motor estimate, but the Adaptive task is neither binary nor continuous: a miss is a timeout or a wrong finger in a four-choice deadline task. The thesis can call the band consistent with these values, not derived from them.

### Q3. How are adaptive controllers in rehabilitation built and evaluated, and how should this one converge in 40 trials?

- Update rules in the literature: a proportional rule (difficulty changed by a learning rate times performance minus the reference) took 29.4 (SD 8.2) trials from the easiest setting before difficulty stopped rising, then stayed within 33.3 (SD 27.9) percent of the challenge point; the authors warn that a high learning rate follows noise and oscillates and a low one lags (Choi et al. 2011, Methods and Results [FT]). Block-wise asymmetric steps with a dead zone (Cameirao et al. 2010 [FT]). A weighted up-down rule: gains fall by rho after each hit and rise by alpha times rho after each miss, converging on alpha/(alpha+1); success was read over the last 25 notes; healthy players reached 72.2 (SD 19.5), 79.3 (SD 4) and 99 (SD 1.1) percent against targets of 50, 75 and 99, because the robot cannot make the game harder than unassisted; effort fell as success rose (Taheri et al. 2014, "Success rate algorithm" and Results [FT]). Deadline tracking at 97.5, 82.0 and 66.0 percent with 30 ms steps per block takes many trials to converge, because accuracy has to be computed over sets of trials (Heitz 2014 on Rinkenauer et al. 2004, section on deadline tracking [FT]).
- This controller updates every trial with a high gain and a slow, noisy estimate (Section 1.2). In control terms the loop has a delayed sensor: the pace moves every trial while the hit estimate reflects trials up to about 12 back, and the climb arrives at the hand's limit at up to 15 BPM a trial.
- Simulation (400 simulated healthy hands, mean RT 350 ms, between-person SD 40 ms): the pace reaches 5 BPM below the hand's 72.5 percent pace at trial 14 (IQR 12 to 18); the peak comes at a median trial 31 and exceeds the 72.5 percent pace by 10.5 BPM (IQR 5.1 to 16.2); the first band entry after the climb is at trial 22.4 (SD 5.7); recovery is entered 0.81 times a block; 7.7 misses a block (3.0 wrong finger, 4.7 timeouts), against 3 to 11 on the pilot blocks.
- Long blocks (simulation, 60 hands, trials 101 to 400): the hit rate settles at 0.756 (SD 0.012), inside the band; the pace settles 4.7 BPM below the 72.5 percent pace (the recovery drops pull it down); the trailing 12-trial rate lies in the band 40 percent of the time.
- Start pace: starting at 60 rather than 30 BPM moves the first band entry from trial 22.4 to 20.9 and leaves the peak and its reliability unchanged (simulation).

Bearing: the band holds in the long run, so the design works as a training controller. Inside 40 trials, though, a block is about 14 trials of climb plus 20 to 25 trials near the limit, in line with Choi's 30 trials to converge.

### Q4. How fast can a healthy hand go on four-finger cued presses, and what do the 180 BPM cap and the 0.90 window mean?

- Serial four-finger choice, right hand, keyboard keys under four marks, about 200 ms from press to next cue, no immediate repeats: 373 (SD 65) ms with 96.5 (SD 4.1) percent correct in the first run and 343 (SD 59) ms with 93.5 (SD 8.1) percent in the second, 10 to 15 minutes or 2 or more days later; run-to-run r 0.63 (95 percent CI 0.43 to 0.77) in 53 right-handed university participant-pool adults (whole sample aged 21.2, SD 2.4) (Stark-Inbar et al. 2017, Methods (participants, SRT task) and Results [FT, PMC page]). Of the published references found, this sample is closest to the study's student cohort.
- Discrete four-choice RT, 18 to 25 years: 388.0 ms (SD 45.0), errors 3.0 percent, visual cue, keyboard (Deary et al. 2011 [ABS]; values read in full in the Reaction review).
- A vibration on the finger that must respond flattens the cost of more choices (Leonard 1959 [META]; reported in Proctor and Schneider 2018, read in full in the Reaction review). Temporal predictability shortens RT: constant foreperiods give faster RTs than variable ones and isochronous streams help targets on the beat (Bausenhart and Ulrich 2026, sections on paradigms and time uncertainty [FT]; Sanabria et al. 2011 [ABS]). So a healthy hand may beat the keyboard references here.
- Motor speed is not the limit at 3 presses a second: in fast tapping the index finger is quickest, then middle, little and ring (Aoki et al. 2003 [ABS]); the cap's 333 ms cadence is a choice limit, not a tapping one.
- Simulation: the pace at which a fixed-pace run gives 72.5 percent hits is 146, 131, 117, 106 and 97 BPM for mean RTs of 300, 350, 400, 450 and 500 ms (windows 371, 413, 460, 508 and 557 ms). In the simulated cohort it runs from 117 to 145 BPM (10th to 90th percentile; windows 464 to 374 ms), and 0.2 percent of 40-trial blocks touch 180 BPM.
- Rig timing (repository `docs/research/new_modes/modes-review.md`, device facts): the buzz moves 74 ms after the command, the tone sounds at 77 ms, presses are stamped 10 to 11 ms late and detected 7 to 11 ms after the raw crossing, and the cue is stamped 0 to 16.7 ms before the screen flip. At a 400 ms window about 300 ms remain after the buzz starts (arithmetic).
- At the cap the 250 ms buzz plus the motor's 115 ms spin-down (`default.yaml` latency notes) lasts 365 ms against a 333 ms cadence, so consecutive fingers' motors overlap for about 32 ms; this starts above about 164 BPM (arithmetic).

At the band the task becomes a forced-paced serial choice task, a format studied since Alluisi, Muller and Fitts 1957 [META], with the deadline and the time to the next cue tied together by the 0.90 factor.

Bearing: the cap never binds for a healthy hand and costs nothing; the reason given for it in the config (a 280 ms player) describes no healthy four-finger hand. The 0.90 factor leaves 33 to 60 ms between window close and the next cue at the paces healthy hands reach (arithmetic), too short to absorb a late press (Q5).

### Q5. What happens to a late press?

- Code: a press between 0.9 and 1.0 of the cadence is an idle press (a point off, not scored). A press after the next cue lands in the next trial; since no finger is cued twice running, a late press on the previous trial's finger is always a wrong finger there, so one slow response costs two trials (mode `_handle_press` 186-215).
- The next response is also delayed: the shorter the interval between two choice stimuli, the slower and more error-prone the second response, which the response-selection bottleneck explains (Fischer and Plessow 2015, Introduction and Figure 1 [FT]; Pashler 1994 [META]). A slow response therefore pushes the next one late, and three misses in a row trigger recovery.
- Pilot: the four previous-finger presses within 150 ms of a new cue (Section 1.7) each started or extended a run of misses that ended in recovery (pilot).
- Code inconsistency: `ANTICIPATION_MS` (mode 245) says a press under 100 ms cannot be a response, but a correct-finger press under 100 ms still counts as a hit (quality 0) and a wrong-finger press under 100 ms still counts as a wrong finger. Reaction treats any press under 100 ms as not a response.
- Simulation, crediting a previous-finger press in the first 150 ms of a new trial to the previous trial: recovery entries fall from 0.81 to 0.47 a block; the final pace moves from 5.3 BPM below to 1.5 BPM above the hand's 72.5 percent pace; the block-to-block ICC of the last-10 pace rises from 0.41 to 0.51 and of the peak from 0.52 to 0.59; the long-run pace moves from 4.7 below to 0.6 above the 72.5 percent pace. At a fixed 140 BPM the default simulated hand hits 0.644 of trials with the carry-over and 0.730 without it.

Bearing: much of the "crash" after the climb is a scoring artefact of the trial boundary, not the hand failing twice. The fix changes scoring, so it is a design change.

### Q6. What can A5 and A6 decide at n = 10, and what summaries describe a closed-loop block better?

- A5 (median `bpm_rise` above 0): passed in 2,000 of 2,000 simulated cohorts of 10; the smallest single-person rise was 25 BPM. Two hits from 30 BPM already raise the pace (code).
- A6 (median block hit rate above 0.65): passed in 2,000 of 2,000 cohorts; the lowest simulated person scored 0.70. Arithmetic: with 15 climb trials near 100 percent, a block stays at 0.69 even if every later trial runs at 50 percent. Pilot block rates 0.725 to 0.925.
- Time in band: a trailing 12-trial rate can only be 8/12 or 9/12 inside 0.65 to 0.80, so a controller holding a hand exactly at p scores at most 0.432, 0.471, 0.469, 0.452 and 0.369 for p of 0.65, 0.70, 0.725, 0.75 and 0.80 (arithmetic, binomial). Simulation 0.36 (SD 0.17); pilot 0.00 to 0.28.
- Block-to-block reliability of each summary with no change in the hand (simulation, two independent blocks for each of 400 hands): peak ICC(2,1) 0.52 (Spearman with the true 72.5 percent pace 0.70; bias plus 9.9 BPM); median pace over trials 21 to 40 ICC 0.40 (Spearman 0.64; bias minus 3.0); last-10 mean 0.41; final pace 0.33 (bias minus 5.3); block hit rate 0.08; trials 21 to 40 hit rate 0.00; time in band 0.06; recovery entries 0.00; first band entry 0.12; window at the peak 0.36.
- A staircase-style estimate from reversals is not available: after dropping the first two, a median of 0 usable reversals remain in 40 trials (simulation). Short fixed-step staircases (up to 20 reversals) are biased and imprecise (Garcia-Perez 1998 [ABS]; Leek 2001 [ABS]).
- Fitting the hand's pace at 72.5 percent: a two-parameter logistic of hit on window, per block, fails (ICC 0.05; no fit in 30 of 400 blocks). A location-only fit with a slope of 3 per 100 ms gives ICC 0.57, r 0.61 with the true pace and a bias of minus 1.5 BPM (simulation). Estimating the common slope from a cohort of 10 with a 2 percent lapse rate gives ICC 0.57 (IQR across cohorts 0.32 to 0.73), r 0.79 and a bias of plus 0.7 BPM, against ICC 0.62 (0.40 to 0.74) and r 0.77 for the peak in the same cohorts, whose bias in the full simulated cohort is plus 10 BPM (simulation). Without a lapse term the pooled slope collapses to 0.41 per 100 ms and the estimate fails (ICC 0.20). Method sources: lapse rates in psychometric fits (Wichmann and Hill 2001 [META]), mixed models for psychometric data (Moscatelli et al. 2012 [ABS]), location estimation (Watson and Pelli 1983; King-Smith et al. 1994 [META]); with 60 to 120 trials Bayesian placement keeps threshold bias under 1 percent (Chopin et al. 2026, Results [FT]).
- Post-climb hit rate (trials 21 to 40): 0.73 (SD 0.09) per person; the cohort mean of 10 falls between 0.67 and 0.79 in 95 percent of cohorts, and its bootstrap interval lies wholly inside 0.65 to 0.80 in 59 percent (simulation). Pilot pooled 0.72.

Bearing: A5 and A6 confirm only that the game ran. The two numbers a 40-trial block can carry are the peak (with its overshoot) and a steady-state pace (median of trials 21 to 40, or the location fit); the rest describe the controller, not the person.

### Q7. The weakness bias and the floor

- Allocating more trials to the task performed worse beat random scheduling at delayed retention (48 adults; Choi et al. 2008 [ABS]). Random and variable practice favour retention despite poorer practice performance (Maier et al. 2019, sections on variable practice [FT]).
- Healthy finger differences: ring slowest in fast tapping (Aoki et al. 2003 [ABS]); after stroke, grips with fingers 2 to 5 were sequentially worse in MusicGlove (Friedman et al. 2014, Results [FT]); pilot hit rates ring 0.73 against 0.82 to 0.87 for the others (pilot).
- Simulation, 40-trial blocks, 300 hands: with equal fingers the mean cues per finger are 10.2, 9.9, 9.9 and 10.0; with the ring finger 60 ms slower, 10.0, 9.8, 10.4 and 9.8, and the ring finger gets the most cues in 30 percent of blocks against 21 percent with equal fingers; any finger gets between 5 and 16 cues. The ring finger's hit rate drops to 0.73 against 0.82 to 0.84.
- The floor of 0.15 asks for 6 cues in 40 and keeps each finger within one cue of it, so 5 is possible (arithmetic; simulation minimum 5). After three misses, recovery puts 70 percent of the weight on the strongest finger, which works against the bias (code).
- Unequal cue rates make the favoured finger more expected, and expected stimuli are answered faster (Hyman 1953 [META]; as reported in Proctor and Schneider 2018, read in full in the Reaction review); the no-repeat rule already caps each cue at log2 3 = 1.58 bits (arithmetic).

Bearing: in a healthy 40-trial block the bias is close to inert, and a finger's hit rate rests on 5 to 16 trials taken at different paces (binomial SE about 0.13 at 10 trials and p 0.8, arithmetic). No weakness-bias effect or per-finger claim can come from this block.

### Q8. Reliability: what can one block, and a second go, support?

- One block gives no test-retest estimate, and a split-half is not meaningful because the climb makes the block non-stationary.
- Second go (30 and 60 minute sittings), simulation with no real change: peak ICC 0.39, 0.52 and 0.67 when the true 72.5 percent pace varies between people with an SD of 8, 11 and 18 BPM (0.78 in a slower cohort, mean RT 450 ms); the peak's within-person SEM is 9.7 BPM, the SD of a block-to-block change 13.8 BPM and the MDC95 27 BPM; final pace ICC 0.19 to 0.58.
- Benchmarks: baseline RT from 252 trials of four-finger serial choice repeated at r 0.63 (Stark-Inbar et al. 2017 [FT]). None of the rehabilitation controller papers read here (Cameirao et al. 2010, Choi et al. 2011, Metzger et al. 2014, Taheri et al. 2014) reports the test-retest reliability of the level a player reaches.
- Practice: RT fell 30 ms between runs in Stark-Inbar et al. [FT]. A 30 ms faster hand gains about 7 to 9 BPM of 72.5 percent pace (simulation: about 0.25 to 0.3 BPM per ms). At n = 10 the 95 percent interval of a cohort's mean change is about plus or minus 9 BPM (arithmetic from the SD of change).

Bearing: "moderate" is the realistic expectation for the peak, and a practice effect the size the literature suggests sits at the resolution limit of a second block at n = 10.

### Q9. The cue and the timing

- Cues arrive on an isochronous grid, so the time is predictable and only the finger is not. Constant foreperiods give faster RTs than variable ones (Mattes and Ulrich 1997 [META], reported in Bausenhart and Ulrich 2026 [FT]); very short foreperiods speed RT at a cost in errors (Han and Proctor 2023 [META], reported there). Adaptive RTs are therefore not comparable with Reaction's (random foreperiods of 1.5 to 9 s and catch trials).
- The interval from a response to the next cue shrinks as the pace rises, and people set a lower decision threshold when that interval is short: fitted thresholds 0.0558, 0.0606 and 0.0734 at response-stimulus intervals of 0.5, 1 and 2 s in a two-choice task (Simen et al. 2009, Experiment 1, Table 1 [FT, PMC page]); adapting to a new interval can take 20 trials (Heitz 2014, section on RSI [FT]). In Adaptive the interval changes every trial, so the person's speed-accuracy setting is never settled.
- Deadlines with feedback are the standard way to induce a speed-accuracy trade-off, practice trials give an acclimation period, and deadlines that are too fast encourage guessing (Heitz 2014, section on deadlines [FT]). The timing bar is that feedback.
- The cue is trimodal, with the buzz on the responding finger (code); the Reaction review sets out what such a mix does to RT (Diederich and Colonius 2004 [META]; read in full there).
- A press timed to the beat before the finger is known is right one time in three (arithmetic, no repeats); under the code it counts as a Perfect hit at 10 points times the multipliers.
- The config comment calling the cue a metronome click is out of date (code).

### Q10. Learning, fatigue and the block's place in the sitting

- A block lasts 24 to 34 s (10th to 90th percentile, simulation), too short for fatigue to matter.
- There are no practice trials. MusicGlove opened with a 1 min 10 s tutorial song (Friedman et al. 2014, Methods [FT]); FINGER players practised a song at 75 percent success first (Taheri et al. 2014, Experimental protocol [FT]).
- Early wrong presses at 30 BPM drive the pace down: in simulation 8.5 percent of healthy blocks dip below the 30 BPM start and 3.3 percent below 20 BPM, and 1.8 percent run past 45 s (longest 98 s, at 6 s a trial near the floor). The abandoned 25 September pilot block went to 10 BPM by trial 4 (pilot).
- Order: in order A the participant arrives after five games of presses to cues (Reaction, Rhythm, Echo, Chords, Buzz Hunt) and Force Pilot; in order B after Force Pilot, Chords and Buzz Hunt, with no lit single-finger choice task yet. Four-finger choice RT was 30 ms faster on a second run (Stark-Inbar et al. 2017 [FT]), so prior cued pressing can raise the pace and order and pace are confounded.
- Within the block, practice and difficulty both rise (design 4.5b already reads Adaptive as "harder").

### Q11. Scoring, feedback and instructions

- Verbal instructions set the speed-accuracy trade-off, but loosely; payoffs and deadlines set it more precisely (Heitz 2014, SAT methodology [FT]). The Adaptive payoff rewards pace (times BPM/60), streaks and sub-200 ms presses, and charges 3 points per wrong press (code), with no instruction to weigh them.
- The pace reached mixes speed with accuracy: a simulated hand that answers fast with many wrong fingers stays slow (simulation, the three simulated blocks that never passed 80 BPM came from fast but error-prone hands).
- Feedback after good trials, aimed at the task, is the bank's rule set (`ui/feedback_bank.py` docstring); its banned-word list (`BANNED`) bars "wrong", "miss", "late", "early" and "slow" from anything shown to a participant, which constrains any instruction line.
- Engagement: a game version of a sequence task improved retention over a plain version (40 players; Lohse et al. 2016 [ABS]); choosing one's own difficulty raised motivation, but engagement and motivation did not predict learning (60 players; Leiker et al. 2016 [ABS]); matched skill and demand produced flow (Keller and Bless 2008 [ABS]).

### Q12. Clinical relevance, as far as it bears on the healthy study

- MusicGlove asked for 1,420 movements in a 45 minute session; percent of notes hit related to Box and Block scores; its Dexterity test is a fixed ramp whose notes come closer together as the song goes on, the same for everyone (Friedman et al. 2014, Methods and Results [FT]).
- The MusicGlove and FINGER lines both went on to randomised trials (Zondervan et al. 2016; Rowe et al. 2017 [META]); their outcomes were not read here and nothing in this report rests on them.
- Increasing difficulty in steps worked when the increases were adaptive and not when fixed (37 transfer studies; Wickens et al. 2013 [ABS]); personalised difficulty is listed as a principle of neurorehabilitation, and the effect of shaping on its own has not been studied (Maier et al. 2019, "Increasing Difficulty" [FT]).
- More repetitions alone did not help: 85 people at least 6 months after stroke given 3,200, 6,400, 9,600 or an individualised maximum of task-specific repetitions over 8 weeks showed no dose-response; the 3,200 reference was chosen as about 100 repetitions a session, the amount earlier studies observed in usual therapy (Lang et al. 2016, Abstract and Methods [FT, PMC author manuscript]).
- Performance during practice is not learning; delayed retention is the better indicator (Kantak and Winstein 2012 [ABS]).

Bearing: a healthy sitting can show that the controller climbs, settles near a pace that depends on the hand, and how repeatable that pace is. It cannot show that the band, the bias or the dose helps anybody.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Target band | 0.65 to 0.80 (analytics 77-78; `default.yaml` 689-690) | No source sets a band; rehabilitation systems run at 50 to 80 percent; one motor estimate is 68 percent (Q1, Q2) | Keep; reword claims |
| Controller estimate | mean of per-finger hit EMAs, alpha 0.25 | SD 0.085 at p 0.725, about 12 trials of lag (Section 1.2) | Keep; log it per trial |
| Start pace | 30 BPM (673) | Climb about 14 trials; 60 saves 1 to 2 (Q3) | Keep |
| Floor | 10 BPM (674) | Early wrong presses sink 8.5 percent of healthy blocks below the start (Q10) | Change for the battery: 30 |
| Cap | 180 BPM (687) | Never reached by healthy hands (Q4) | Keep; fix the comment |
| Step rule | 4 BPM per unit, streak gain to 2.5, plus 15 and minus 20 clamps, slow-downs times 1.5 | Overshoot of about 10 BPM (Q3) | Keep; report the overshoot |
| Recovery | minus 25 BPM after 3 misses, strongest-finger weights | Mostly triggered by carry-over (Q5) | Keep; fix the carry-over |
| `min_trials` | 2 in total (comment says per finger) | Code | Keep; fix the comment |
| Window factor | 0.90 of the cadence (696) | No source; 33 to 60 ms gap at healthy paces (Q4) | Keep |
| Late press scoring | a press after the next cue is a wrong finger there | Splits one slow response into two misses (Q5) | Change |
| Sub-100 ms presses | correct counts as a hit, wrong as a wrong finger | Not a response by the mode's own rule (Q5) | Change with the late-press rule; count now |
| Weakness bias and floor | 2.5; 0.15; regenerate every 4 | Near inert in 40 healthy trials (Q7) | Keep; describe only |
| No-repeat rule | on | 1.58 bits a cue at most (Q7) | Keep |
| Cue | tile, buzz 250 ms, lane tone 0.12 s; no click | Trimodal; motors overlap above 164 BPM (Q4, Q9) | Keep; fix the cue_volume comment |
| Loud trials | every 10th cue 35 percent louder | Small effect on RT | Keep |
| Scoring | tiers times pace times streak; minus 3 per wrong press | A speed payoff (Q11) | Keep; not analysed |
| Instructions | "The pace follows you" only | Instructions and deadlines set SAT (Q11) | Add a GET READY line and a run-sheet line |
| Practice trials | none | Tutorials in MusicGlove and FINGER (Q10) | Keep; the floor change covers the damage |
| Block length | 40 trials (2079) | 60 and 80 trials improve the steady-pace estimate (Q6, Section 4) | Keep; optional change |
| Position | order A step 7, order B step 4 | Order confounds practice (Q10) | Keep; analyse by order |
| A5 | median rise above 0 | Cannot fail (Q6) | Keep as a feasibility check |
| A6 | median hit rate above 0.65 | Cannot fail by arithmetic (Q6) | Re-label as a feasibility check |
| Time in band | trailing 12-trial share, trials 12 to 40 | Ceiling about 0.47; ICC 0.06 (Q6) | Keep with its ceiling |
| Peak pace | `bpm_max_reached` | Overshoot plus 10 BPM; ICC about 0.5 (Q6) | Keep with the caveat |
| Steady pace | not computed | ICC 0.40 to 0.57, bias 3 BPM or less (Q6) | Add |
| Post-climb hit rate | not computed | 0.73 (SD 0.09) (Q6) | Add |
| A1 in `sec_adaptive` | whole-block rate in the band | Above the band by design during the climb | Change to trials 21 to 40 |
| `band_side` wording | "too easy", "nothing to learn from" | Not supported (Q1, Q2) | Change |
| Second-go rows | peak and window at the peak | Expected noise SEM about 10 BPM (Q8) | Keep; print the noise |
| Block summary | no `block_stats`; `bpm_final` is the next pace | Logging gap; name clash | Add; rename |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

1. **Read the block for what it measures, and re-label A6.** SAFE-NOW for the analysis and text; DESIGN-CHANGE for the A6 wording (the criterion does not change).
   In `analysis/session_analysis.ipynb` cell 2, `adaptive_controller_rows` (22121): add `steady_pace_bpm` (median `bpm_at_trial` over trials 21 to 40), `post_climb_hit_rate` (trials 21 to 40) and `time_in_band_ceiling` (the binomial maximum for the 12-trial window, 0.47); emit them in `_cohort_adaptive` (22161) and print them in `sec_adaptive` (28568) beside the peak, with the peak's overshoot stated (about 10 BPM above the steady pace in simulation). Add `steady_pace_bpm` to `COHORT_SECOND_GO_METRICS` (31764). In `MODE_CLAIM_LIMITS["adaptive"]` (27581) replace "Read the peak." with "The peak overshoots the pace the hand holds by about 10 BPM in simulation; read it beside the steady pace." In design doc Sections 1.5 and 4.6, list A6 with A5, Rh2, B4 and C1 as a feasibility check: with about 15 climb trials of near-certain hits the block rate cannot fall below 0.65 unless the later 25 trials run under 44 percent (arithmetic). Log the date.

2. **Score a late press against the trial it belongs to.** DESIGN-CHANGE (scoring; no participant yet; log it). SAFE-NOW part first.
   SAFE-NOW: in the notebook, count per block the wrong presses on the previous row's finger with `first_incorrect_ms` under 150 and the hits under 100 ms, print them in `sec_adaptive` beside the recovery entries, and add a sensitivity hit rate that does not count those trials as misses.
   DESIGN-CHANGE: in `AdaptiveMode._handle_press` (mode 186), when a press arrives within a new key `adaptive.carry_ms` (150) of the current cue on the previous trial's finger, log it as a raw `late_press` event against the previous trial and do not add it to `incorrect_presses`; in `_handle_press`, treat any other press under `ANTICIPATION_MS` after the cue, on any finger, as not a response to it (log it and keep the trial open), as Reaction does; tag the row's `stimulus` with `carry_ms=`. Simulation: recovery entries fall from 0.81 to 0.47 a block, the final pace bias moves from minus 5.3 to plus 1.5 BPM, and the last-10 pace ICC rises from 0.41 to 0.51. Evidence for the delay that causes it: Fischer and Plessow 2015 [FT]; the mode's own 100 ms rule (Basner and Dinges 2011, as cited in the code).

3. **Tell the participant what the game asks.** SAFE-NOW (UX; changes what participants are told, so log it in the design document).
   Add `GameplayScreen.GET_READY_LINES["adaptive"]` in `screens.py` (3743), for example: "Press the finger that lights up," / "before its bar runs out." / "Keep up and it speeds up; it eases off when you need it." / "Only the lit finger counts." Check it with `feedback_bank.offending()` (no "miss", "wrong", "late", "slow"); a test like `tests/test_chords_research.py` line 233 can pin it. Add the same line to the first-time lines in `docs/study_day/run_sheet.md`, which now cover every other battery game. Evidence: instructions and deadlines set the speed-accuracy trade-off (Heitz 2014 [FT]); the pace mixes speed with accuracy (Q11).

4. **Stop a healthy block from sinking below its start pace.** DESIGN-CHANGE (battery setting).
   In `default.yaml` `protocol.presets.study_battery.overrides` add `adaptive: {bpm_min: 30}` (the Trial Mode presets inherit it through `overrides_from`, merged in `game/battery.py` `resolved_overrides`). A block then cannot fall below 30 BPM after early wrong presses; normal blocks are unchanged. Simulation: 8.5 percent of healthy blocks dip below 30 BPM and 3.3 percent below 20, with blocks up to 98 s; one pilot block reached the 10 BPM floor by trial 4. SAFE-NOW fallback: flag a block whose minimum pace fell below its start in `scripts/check_sitting.py` and in `sec_adaptive`.

5. **Correct the text the evidence contradicts.** SAFE-NOW (text only).
   - `analytics/adaptive.py` docstring 1-10 and `AdaptiveConfig` 66-74: keep "design choice" and add the operating points of rehabilitation systems (50 to 70 percent, Cameirao et al. 2010; 70 percent, Metzger et al. 2014; 75 percent, Taheri et al. 2014), the motor estimate of 68 percent (Al-Fawakhiri et al. 2023, preprint) and Hodges and Lohse's (2022) view that no single percentage exists; say that Wilson's 85 percent is for binary classification.
   - `AdaptiveConfig` 98-99: `min_trials` counts trials across all fingers. 102-103: a 4-trial run closes about a third of the gap, not half (arithmetic: each finger gets about 1.3 of the 4 updates, 0.75 to that power is 0.68).
   - `default.yaml` 675-687 and `AdaptiveConfig` 81-87: a 280 ms mean press is faster than healthy four-finger RTs (343 to 388 ms, Stark-Inbar et al. 2017; Deary et al. 2011); the cap is a guard that healthy hands do not reach. 689: the band's centre is 72.5 percent. 1799-1801: Adaptive plays the lane tone, not a click.
   - Design doc 1.5, `MODE_LIT["adaptive"]` A3 (26984), `default.yaml` 683-686 and the claim limits: first band entries were at trials 22 to 34 by the notebook's own function (pilot). Design doc 1.5: the block plays the right hand for everyone, at step 7 (order A) or 4 (order B), not late on the dominant hand.
   - `band_side` (177): above the band means the controller had not yet slowed the pace, expected during the climb; drop "nothing to learn from" and "failing more than they learn from".
   - `sec_adaptive` A4 note (28665): a low finger rate is mostly noise or a slower finger on 5 to 16 trials; in 40 trials the bias barely changes allocation (simulation).
   - `MODE_LIT["adaptive"]` A2: draw the 68.27 percent line beside 85 percent, labelled as a preprint estimate for continuous motor error.

6. **Log what the controller did.** SAFE-NOW (logging only).
   Add `AdaptiveMode.block_stats()` returning the peak, the steady pace, recovery entries, late presses under 150 ms, sub-100 ms hits, cues and hits per finger, idle presses and the seed, and call it from `engine.py` `_build_block_summary` (5871) the way echo and srt are called. Queue one raw event per trial (`adaptive_state`: hr, qr, util, combined pressure, the BPM change and recovery state) from `_finish` after `next_bpm()`. Rename the summary's `bpm_final` to `bpm_next` or document that it is the pace after the last update.

7. **Read the pace by order and against Reaction.** SAFE-NOW (exploratory rows).
   In `sec_adaptive` and the cohort chapter, print peak and steady pace by order (A against B), and a Spearman correlation between steady pace and pass 1 Reaction median RT. Expected rho about minus 0.4 to minus 0.5; at n = 10 it is negative in 93 percent of cohorts and beyond the two-sided 5 percent value in 36 percent (simulation), so it is a description, not a test.

8. **Print the expected noise beside every second-go change.** SAFE-NOW.
   In `_cohort_second_goes` (31787), for the Adaptive rows print the change a block-to-block repeat gives with no real change (peak SD about 14 BPM, MDC95 about 27 BPM, simulation) and the practice effect the literature suggests (about 7 to 9 BPM from a 30 ms faster RT; Stark-Inbar et al. 2017 [FT] with the simulation's slope). No individual change claims.

9. **Estimate the hand's pace at 72.5 percent directly.** SAFE-NOW (exploratory, analysis only).
   Add a cohort-level fit in `sec_adaptive`: hit against window with a person intercept, one common slope and a 2 percent lapse rate, maximum likelihood with `scipy.optimize.minimize` (the notebook has scipy, not statsmodels); report each person's window and pace at 72.5 percent. Simulation: ICC 0.57, r 0.79 with the true pace, bias plus 0.7 BPM at n = 10. Method: Wichmann and Hill 2001 (lapse); Moscatelli et al. 2012 (mixed models); Watson and Pelli 1983 (location estimation).

10. **Lengthen the block only if the minutes allow.** DESIGN-CHANGE (battery setting; low priority).
    `protocol.presets.study_battery.overrides.game.total_trials` from 40 to 60 adds about 10 s and lifts the fixed-slope estimate from ICC 0.57 and r 0.61 to 0.63 and 0.68; 80 trials add about 20 s for 0.65 and 0.82 (simulation). The peak grows more biased with length (plus 13 and plus 16 BPM). The sitting has about a minute of headroom (design 2.3).

11. **After collection.** AFTER-COLLECTION.
    A measurement preset separate from the training game: a fixed cadence with the window as a deadline set by a Bayesian adaptive procedure (QUEST or ZEST; Watson and Pelli 1983; King-Smith et al. 1994; 60 to 120 trials, Chopin et al. 2026 [FT]) or a fixed ramp the same for everyone (MusicGlove's Dexterity test, Friedman et al. 2014 [FT]); practice trials first; the late-press guard; cue-channel conditions; and, if the weakness bias is to be studied, blocks long enough for it to act, with per-finger reliability measured.

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Steady pace (median BPM, trials 21 to 40) beside the peak, with the peak's overshoot stated | `adaptive_controller_rows`, `_cohort_adaptive`, `sec_adaptive`, `COHORT_SECOND_GO_METRICS` | Cameirao et al. 2010 used the mean of the last 30 trials [FT]; simulation |
| Post-climb hit rate with its interval, pooled and per person | same | Taheri et al. 2014 read success over the last 25 notes [FT] |
| Binomial ceiling printed with time in band (0.43 to 0.47) | `adaptive_controller_rows`, `sec_adaptive` | arithmetic |
| A1 computed on trials 21 to 40, not the whole block | `sec_adaptive` (28600) | Q6 |
| `band_side` wording | 177-196 | Q1, Q2 |
| Late presses under 150 ms on the previous finger, sub-100 ms hits, and a sensitivity hit rate without them | `sec_adaptive`, `_cohort_adaptive` | Fischer and Plessow 2015 [FT]; pilot |
| Pace at 72.5 percent from a person-intercept, common-slope logistic with a 2 percent lapse | new helper beside `adaptive_controller_rows` | Wichmann and Hill 2001 [META]; Moscatelli et al. 2012 [ABS]; simulation |
| Peak and steady pace by order (A, B) | `sec_adaptive`, cohort chapter | Q10 |
| Spearman of steady pace against pass 1 Reaction median RT (exploratory) | cohort chapter | simulation |
| Expected no-change noise beside each second-go change (SEM about 10 BPM, MDC95 about 27) | `_cohort_second_goes` | simulation; Bonett 2002 [META] for ICC width at n = 10 |
| Per-finger rows: cues and hits per finger, no per-person finger claims | `sec_adaptive` A4 | Q7 |
| Flag blocks whose minimum pace fell below the start pace | `sec_adaptive`; `scripts/check_sitting.py` | Q10 |
| Keep RTs out of any pooled RT table (censored by a moving window) | `censoring_caveat` (1362), already in place | code |
| One meaning for `bpm_final` | `_cohort_adaptive` and the block summary | code |
| `sec_accuracy` band share with the same 12-trial definition | 3789 onward | consistency |

Keep as they are: A5 and A6 as registered (with A6 re-labelled), the descriptive status of every Adaptive row, Adaptive's absence from the reliability and within-block tables in the 45 minute sitting, and the second-go table for the 30 and 60.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Four-finger serial choice RT, young adults | 373 (SD 65) ms, 96.5 (SD 4.1) percent correct; 343 (SD 59) ms on the second run; run-to-run r 0.63 | Stark-Inbar et al. 2017 [FT] | visual cue, keyboard, self-paced with about 200 ms to the next cue; 53 right-handed students aged about 21 |
| Four-choice discrete RT, 18 to 25 years | 388.0 ms (SD 45.0), 3.0 percent errors | Deary et al. 2011 (values read in full in the Reaction review) | visual, two fingers per hand, 1 to 3 s gaps |
| Optimal training accuracy, theory | 85 percent for binary classification; 68.27 percent for continuous signed motor error | Wilson et al. 2019 [FT]; Al-Fawakhiri et al. 2023 preprint [FT] | neither models a four-choice deadline task |
| Rehabilitation controllers' operating points | hold zone 50 to 70 percent; target 70 percent (achieved 64, SD 21); target 75 percent (achieved 73.8, SD 7.1, after stroke; 79.3, SD 4, healthy) | Cameirao et al. 2010; Metzger et al. 2014; Taheri et al. 2014 [all FT] | different tasks, robots and timescales |
| Convergence of an adaptive difficulty rule from the easiest level | 29.4 (SD 8.2) trials | Choi et al. 2011 [FT] | five people after stroke, functional tasks |
| Training dose in a hand rehabilitation game | 1,420 movements in a 45 minute session | Friedman et al. 2014 [FT] | MusicGlove, stroke |
| Expected pace for healthy hands on this controller | 72.5 percent pace 117 to 145 BPM (window 464 to 374 ms); peak 125 to 157 BPM; block 24 to 34 s (10th to 90th percentiles) | simulation | a model of a hand, not a norm; check against the cohort |
| Pilot | peaks 90 to 144 BPM; trials 21 to 40 hit rate pooled 0.72 | pilot | development team, mixed software versions |

How to use them: report the cohort's peak and steady pace as this device's numbers, measured with a trimodal cue on an isochronous grid, a force-threshold press and the rig delays in Q4; compare them with the published RTs only as an order-of-magnitude check (the simulated 72.5 percent windows of about 375 to 465 ms sit above the published mean RTs of 343 to 388 ms, as they must).

### 6.2 Reliability and change expectations

- One 40-trial block: no reliability estimate of any kind.
- Second go: peak ICC about 0.4 to 0.67 with no real change, depending on how much people differ (simulation); the steady pace slightly lower; hit rate, time in band, recovery entries and first band entry near 0.
- Within-person SEM of the peak about 10 BPM, MDC95 about 27 BPM (simulation); a cohort mean change at n = 10 carries an interval of about plus or minus 9 BPM (arithmetic).
- Practice between goes: of the order of 7 to 9 BPM if RT falls 30 ms as in Stark-Inbar et al. 2017 (simulation slope), the same size as the noise.

### 6.3 Claims to avoid

- That 65 to 80 percent is the optimal challenge, or that any source sets it.
- That above the band "there is nothing to learn", or that a healthy hit rate inside the band shows optimal training.
- Any learning or therapeutic claim from a 40-trial healthy block, including for the weakness bias (performance is not learning, Kantak and Winstein 2012).
- That A5 or A6 shows anything about the hand; both confirm the game ran.
- The peak as the hand's limit without the overshoot caveat, or the final pace as its steady state (the final pace depends on where a crash lands).
- Time in band as a percentage of good control without its ceiling of about 0.47.
- Per-finger hit rates, or a finger "struggling", from 5 to 16 trials at changing paces.
- Comparisons of Adaptive RTs with Reaction RTs or published norms (isochronous timing, censoring by the window, different SAT).
- That a second-go change in pace is a person's improvement, unless it exceeds about 27 BPM, or a cohort's, without its interval.
- Engagement or flow from the score or the streaks; nothing in the sitting measures them.

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, PubMed E-utilities, Crossref, OpenAlex and publisher, preprint or repository pages.

1. Al-Fawakhiri N, Kayani S, McDougle SD. 2023. Evidence of an optimal error rate for motor skill learning. bioRxiv preprint. DOI 10.1101/2023.07.19.549705. [FT: bioRxiv full text; theory section, Results, Methods]
2. Alluisi EA, Muller PF, Fitts PM. 1957. An information analysis of verbal and motor responses in a forced-paced serial task. Journal of Experimental Psychology 53(3):153-158. DOI 10.1037/h0046294. PMID 13416475. [META]
3. Akizuki K, Ohashi Y. 2015. Measurement of functional task difficulty during motor learning: what level of difficulty corresponds to the optimal challenge point? Human Movement Science 43:107-117. DOI 10.1016/j.humov.2015.07.007. PMID 26253223. [ABS]
4. Aoki T, Francis PR, Kinoshita H. 2003. Differences in the abilities of individual fingers during the performance of fast, repetitive tapping movements. Experimental Brain Research 152(2):270-280. DOI 10.1007/s00221-003-1552-z. PMID 12898096. [ABS]
5. Bausenhart KM, Ulrich R. 2026. What is prepared in temporal preparation? A review and a historical appreciation. Frontiers in Psychology 17:1768431. DOI 10.3389/fpsyg.2026.1768431. PMID 42325310. PMC13275726. [FT: sections on temporal orienting and rhythms, time uncertainty and hazard, response selection, response force]
6. Bonett DG. 2002. Sample size requirements for estimating intraclass correlations with desired precision. Statistics in Medicine 21(9):1331-1335. DOI 10.1002/sim.1108. PMID 12111881. [META]
7. Bootsma JM, Hortobagyi T, Rothwell JC, Caljouw SR. 2018. The role of task difficulty in learning a visuomotor skill. Medicine and Science in Sports and Exercise 50(9):1842-1849. DOI 10.1249/MSS.0000000000001635. PMID 29634641. [FT: author's accepted manuscript in the UCL repository; Abstract, Introduction, Methods, Discussion]
8. Cameirao MS, Bermudez i Badia S, Duarte Oller E, Verschure PFMJ. 2010. Neurorehabilitation using the virtual reality based Rehabilitation Gaming System: methodology, design, psychometrics, usability and validation. Journal of NeuroEngineering and Rehabilitation 7:48. DOI 10.1186/1743-0003-7-48. PMID 20860808. PMC2949710. [FT: Personalized Training Module, analysis of the adaptive version, Results]
9. Chopin A, Szinte M, Arleo A, Sheynikhovich D. 2026. Comparison of methods for quick estimation of psychometric thresholds. Frontiers in Neuroscience 20:1760278. DOI 10.3389/fnins.2026.1760278. PMID 42559195. PMC13439673. [FT: Introduction, Results for monotonic profiles, Figure 1]
10. Choi Y, Qi F, Gordon J, Schweighofer N. 2008. Performance-based adaptive schedules enhance motor learning. Journal of Motor Behavior 40(4):273-280. DOI 10.3200/JMBR.40.4.273-280. PMID 18628104. [ABS]
11. Choi Y, Gordon J, Park H, Schweighofer N. 2011. Feasibility of the adaptive and automatic presentation of tasks (ADAPT) system for rehabilitation of upper extremity function post-stroke. Journal of NeuroEngineering and Rehabilitation 8:42. DOI 10.1186/1743-0003-8-42. PMID 21813010. PMC3169456. [FT: adaptive scheduler equations, training procedure, Results, Discussion]
12. Deary IJ, Liewald D, Nissan J. 2011. A free, easy-to-use, computer-based simple and four-choice reaction time programme: the Deary-Liewald reaction time task. Behavior Research Methods 43(1):258-268. DOI 10.3758/s13428-010-0024-1. PMID 21287123. [ABS; Table 1 values as read in full in docs/research/deep/reaction.md]
13. Diederich A, Colonius H. 2004. Bimodal and trimodal multisensory enhancement: effects of stimulus onset and intensity on reaction time. Perception and Psychophysics 66(8):1388-1404. DOI 10.3758/BF03195006. PMID 15813202. [META; read in full in docs/research/deep/reaction.md]
14. Fischer R, Plessow F. 2015. Efficient multitasking: parallel versus serial processing of multiple tasks. Frontiers in Psychology 6:1366. DOI 10.3389/fpsyg.2015.01366. PMID 26441742. PMC4561751. [FT: Introduction, Figure 1, sections on the PRP paradigm and bottleneck models]
15. Friedman N, Chan V, Reinkensmeyer AN, Beroukhim A, Zambrano GJ, Bachman M, Reinkensmeyer DJ. 2014. Retraining and assessing hand movement after stroke using the MusicGlove: comparison with conventional hand therapy and isometric grip training. Journal of NeuroEngineering and Rehabilitation 11:76. DOI 10.1186/1743-0003-11-76. PMID 24885076. PMC4022276. [FT: Methods (interventions, Speed and Dexterity tests), Results, Discussion]
16. Garcia-Perez MA. 1998. Forced-choice staircases with fixed step sizes: asymptotic and small-sample properties. Vision Research 38(12):1861-1881. DOI 10.1016/S0042-6989(97)00340-4. PMID 9797963. [ABS]
17. Guadagnoli MA, Lee TD. 2004. Challenge point: a framework for conceptualizing the effects of various practice conditions in motor learning. Journal of Motor Behavior 36(2):212-224. DOI 10.3200/JMBR.36.2.212-224. PMID 15130871. [ABS; framework content as reported in Hodges and Lohse 2022, Thomas et al. 2025 and Maier et al. 2019]
18. Han T, Proctor RW. 2023. Effects of a neutral warning signal under increased temporal uncertainty. Memory and Cognition 51(6):1346-1357. DOI 10.3758/s13421-023-01404-8. PMID 36811693. [META; finding as reported in Bausenhart and Ulrich 2026]
19. Heitz RP. 2014. The speed-accuracy tradeoff: history, physiology, methodology, and behavior. Frontiers in Neuroscience 8:150. DOI 10.3389/fnins.2014.00150. PMID 24966810. PMC4052662. [FT: SAT methodology sections on instructions, payoffs, deadlines, deadline tracking and RSI; Table 2]
20. Hodges NJ, Lohse KR. 2022. An extended challenge-based framework for practice design in sports coaching. Journal of Sports Sciences 40(7):754-768. DOI 10.1080/02640414.2021.2015917. PMID 35019816. [FT: author's preprint of December 2021; sections on the challenge point framework, Figure 2, motivation, practice-to-maintain]
21. Hyman R. 1953. Stimulus information as a determinant of reaction time. Journal of Experimental Psychology 45(3):188-196. DOI 10.1037/h0056940. PMID 13052851. [META; content as reported in Proctor and Schneider 2018, read in full in docs/research/deep/reaction.md]
22. Kaernbach C. 1991. Simple adaptive testing with the weighted up-down method. Perception and Psychophysics 49(3):227-229. DOI 10.3758/BF03214307. PMID 2011460. [ABS]
23. Kantak SS, Winstein CJ. 2012. Learning-performance distinction and memory processes for motor skills: a focused review and perspective. Behavioural Brain Research 228(1):219-231. DOI 10.1016/j.bbr.2011.11.028. PMID 22142953. [ABS]
24. Keller J, Bless H. 2008. Flow and regulatory compatibility: an experimental approach to the flow model of intrinsic motivation. Personality and Social Psychology Bulletin 34(2):196-209. DOI 10.1177/0146167207310026. PMID 18212330. [ABS]
25. King-Smith PE, Grigsby SS, Vingrys AJ, Benes SC, Supowit A. 1994. Efficient and unbiased modifications of the QUEST threshold method: theory, simulations, experimental evaluation and practical implementation. Vision Research 34(7):885-912. DOI 10.1016/0042-6989(94)90039-6. PMID 8160402. [META]
26. Lang CE, Strube MJ, Bland MD, Waddell KJ, Cherry-Allen KM, Nudo RJ, Dromerick AW, Birkenmeier RL. 2016. Dose response of task-specific upper limb training in people at least 6 months poststroke: a phase II, single-blind, randomized, controlled trial. Annals of Neurology 80(3):342-354. DOI 10.1002/ana.24734. PMID 27447365. PMC5016233. [FT: PMC author manuscript; Abstract, Methods on the dose groups]
27. Leek MR. 2001. Adaptive procedures in psychophysical research. Perception and Psychophysics 63(8):1279-1292. DOI 10.3758/BF03194543. PMID 11800457. [ABS]
28. Leiker AM, Bruzi AT, Miller MW, Nelson M, Wegman R, Lohse KR. 2016. The effects of autonomous difficulty selection on engagement, motivation, and learning in a motion-controlled video game task. Human Movement Science 49:326-335. DOI 10.1016/j.humov.2016.08.005. PMID 27551820. [ABS]
29. Leonard JA. 1959. Tactual choice reactions: I. Quarterly Journal of Experimental Psychology 11(2):76-83. DOI 10.1080/17470215908416294. [META; finding as reported in Proctor and Schneider 2018, read in full in docs/research/deep/reaction.md]
30. Levitt H. 1971. Transformed up-down methods in psychoacoustics. Journal of the Acoustical Society of America 49(2B):467-477. DOI 10.1121/1.1912375. PMID 5541744. [ABS; the 70.7 and 79.4 percent targets are arithmetic from the rules]
31. Lohse KR, Boyd LA, Hodges NJ. 2016. Engaging environments enhance motor skill learning in a computer gaming task. Journal of Motor Behavior 48(2):172-182. DOI 10.1080/00222895.2015.1068158. PMID 26296097. [ABS]
32. Maier M, Ballester BR, Verschure PFMJ. 2019. Principles of neurorehabilitation after stroke based on motor learning and brain plasticity mechanisms. Frontiers in Systems Neuroscience 13:74. DOI 10.3389/fnsys.2019.00074. PMID 31920570. PMC6928101. [FT: Introduction, sections on variable practice, increasing difficulty, massed practice and dosage, Discussion]
33. Mattes S, Ulrich R. 1997. Response force is sensitive to the temporal uncertainty of response stimuli. Perception and Psychophysics 59(7):1089-1097. DOI 10.3758/BF03205523. PMID 9360481. [META; finding as reported in Bausenhart and Ulrich 2026]
34. Metzger JC, Lambercy O, Califfi A, Dinacci D, Petrillo C, Rossi P, Conti FM, Gassert R. 2014. Assessment-driven selection and adaptation of exercise difficulty in robot-assisted therapy: a pilot study with a hand rehabilitation robot. Journal of NeuroEngineering and Rehabilitation 11:154. DOI 10.1186/1743-0003-11-154. PMID 25399249. PMC4273449. [FT: Abstract, initial selection and automatic adaptation of difficulty levels, Results, Discussion]
35. Moscatelli A, Mezzetti M, Lacquaniti F. 2012. Modeling psychophysical data at the population-level: the generalized linear mixed model. Journal of Vision 12(11):26. DOI 10.1167/12.11.26. PMID 23104819. [ABS]
36. Onla-or S, Winstein CJ. 2008. Determining the optimal challenge point for motor skill learning in adults with moderately severe Parkinson's disease. Neurorehabilitation and Neural Repair 22(4):385-395. DOI 10.1177/1545968307313508. PMID 18326891. [ABS]
37. Parma JO, Bacelar MFB, Cabral DAR, Lohse KR, Hodges NJ, Miller MW. 2023. That looks easy! Evidence against the benefits of an easier criterion of success for enhancing motor learning. Psychology of Sport and Exercise 66:102394. DOI 10.1016/j.psychsport.2023.102394. PMID 37665856. [ABS]
38. Pashler H. 1994. Dual-task interference in simple tasks: data and theory. Psychological Bulletin 116(2):220-244. DOI 10.1037/0033-2909.116.2.220. PMID 7972591. [META; content as reported in Fischer and Plessow 2015]
39. Proctor RW, Schneider DW. 2018. Hick's law for choice reaction time: a review. Quarterly Journal of Experimental Psychology 71(6):1281-1299. DOI 10.1080/17470218.2017.1322622. PMID 28434379. [META; read in full in docs/research/deep/reaction.md]
40. Rinkenauer G, Osman A, Ulrich R, Muller-Gethmann H, Mattes S. 2004. On the locus of speed-accuracy trade-off in reaction time: inferences from the lateralized readiness potential. Journal of Experimental Psychology: General 133(2):261-282. DOI 10.1037/0096-3445.133.2.261. PMID 15149253. [META; deadline tracking as reported in Heitz 2014]
41. Rowe JB, Chan V, Ingemanson ML, Cramer SC, Wolbrecht ET, Reinkensmeyer DJ. 2017. Robotic assistance for training finger movement using a Hebbian model: a randomized controlled trial. Neurorehabilitation and Neural Repair 31(8):769-780. DOI 10.1177/1545968317721975. PMID 28803535. PMC5894506. [META]
42. Sanabria D, Capizzi M, Correa A. 2011. Rhythms that speed you up. Journal of Experimental Psychology: Human Perception and Performance 37(1):236-244. DOI 10.1037/a0019956. PMID 20718571. [ABS]
43. Simen P, Contreras D, Buck C, Hu P, Holmes P, Cohen JD. 2009. Reward rate optimization in two-alternative decision making: empirical tests of theoretical predictions. Journal of Experimental Psychology: Human Perception and Performance 35(6):1865-1897. DOI 10.1037/a0016926. PMID 19968441. PMC2791916. [FT: PMC page; Abstract, Experiment 1 method and Table 1]
44. Stark-Inbar A, Raza M, Taylor JA, Ivry RB. 2017. Individual differences in implicit motor learning: task specificity in sensorimotor adaptation and sequence learning. Journal of Neurophysiology 117(1):412-428. DOI 10.1152/jn.01141.2015. PMID 27832611. PMC5253399. [FT: PMC page; Methods (SRT task, runs), Results (run effect, reliability of baseline RT)]
45. Taghizadeh H, Fazeli D, Nazemzadegan G. 2026. Effects of adaptive error-threshold practice on soccer instep kick learning. Scientific Reports 16:26922. DOI 10.1038/s41598-026-57684-y. PMID 42288584. PMC13518949. [FT: Abstract, Introduction, Methods]
46. Taheri H, Rowe JB, Gardner D, Chan V, Gray K, Bower C, Reinkensmeyer DJ, Wolbrecht ET. 2014. Design and preliminary evaluation of the FINGER rehabilitation robot: controlling challenge and quantifying finger individuation during musical computer game play. Journal of NeuroEngineering and Rehabilitation 11:10. DOI 10.1186/1743-0003-11-10. PMID 24495432. PMC3928667. [FT: success rate algorithm and equation 8, experimental protocol, Results, Discussion]
47. Thomas A, Paul L, Rasenyalo S, Jones B, Hendricks S. 2025. Challenge accepted: a systematic scoping review of the applications of the challenge point framework. Journal of Motor Behavior 57(4):444-462. DOI 10.1080/00222895.2025.2508283. PMID 40568842. [FT: published version in the Leeds Beckett repository; Results, sections on measuring the optimal challenge point, rehabilitation, limitations]
48. Wadden KP, Hodges NJ, De Asis KL, Neva JL, Boyd LA. 2019. Individualized challenge point practice as a method to aid motor sequence learning. Journal of Motor Behavior 51(5):467-485. DOI 10.1080/00222895.2018.1518310. PMID 30395786. [ABS]
49. Watson AB, Pelli DG. 1983. QUEST: a Bayesian adaptive psychometric method. Perception and Psychophysics 33(2):113-120. DOI 10.3758/BF03202828. PMID 6844102. [META]
50. Wichmann FA, Hill NJ. 2001. The psychometric function: I. Fitting, sampling, and goodness of fit. Perception and Psychophysics 63(8):1293-1313. DOI 10.3758/BF03194544. PMID 11800458. [META]
51. Wickens CD, Hutchins S, Carolan T, Cumming J. 2013. Effectiveness of part-task training and increasing-difficulty training strategies: a meta-analysis approach. Human Factors 55(2):461-470. DOI 10.1177/0018720812451994. PMID 23691838. [ABS]
52. Wilson RC, Shenhav A, Straccia M, Cohen JD. 2019. The Eighty Five Percent Rule for optimal learning. Nature Communications 10:4646. DOI 10.1038/s41467-019-12552-4. PMID 31690723. PMC6831579. [FT: Introduction, Results (equation 6, dynamics), Discussion, Methods on noise distributions]
53. Zimmerli L, Krewer C, Gassert R, Muller F, Riener R, Lunenburger L. 2012. Validation of a mechanism to balance exercise difficulty in robot-assisted upper-extremity rehabilitation after stroke. Journal of NeuroEngineering and Rehabilitation 9:6. DOI 10.1186/1743-0003-9-6. PMID 22304989. PMC3286404. [FT: study design, Results on successful trials, Discussion]
54. Zondervan DK, Friedman N, Chang E, Zhao X, Augsburger R, Reinkensmeyer DJ, Cramer SC. 2016. Home-based hand rehabilitation after chronic stroke: randomized, controlled single-blind trial comparing the MusicGlove with a conventional exercise program. Journal of Rehabilitation Research and Development 53(4):457-472. DOI 10.1682/JRRD.2015.04.0057. PMID 27532880. [META]

Counts: 54 sources; 20 FT, 19 ABS, 15 META. Of the 39 sources whose own text supplied a number or finding (FT plus ABS), 20 are FT. Every META source whose content is used above was read through a named FT secondary source or the repository's Reaction review; the rest (Alluisi et al. 1957, Bonett 2002, King-Smith et al. 1994, Rowe et al. 2017, Watson and Pelli 1983, Wichmann and Hill 2001, Zondervan et al. 2016) are records behind a method or a lineage the text names.

Not re-read here and left as the code and design cite them: Basner and Dinges 2011 (the 100 ms rule in the mode), Palmer 2024 (cue channels), Mueller and Dweck 1998, Bao et al. 2019 and Schwarb and Schumacher 2012 (engine banner rules), Chiviacowsky and Wulf 2007 and the other feedback-bank sources.

### Simulation assumptions (for Sections 1 to 6)

A headless replica of `AdaptiveMode` and the engine's recovery rule, using verbatim copies of `analytics/adaptive.py` and `game/scheduling.py`, with the shipped settings (start 30 BPM, band 0.65 to 0.80, step 10, bounds 10 and 180 BPM, weakness bias 2.5, floor 0.15, block size 4, window factor 0.90, three misses to recovery), cues on 60 Hz frames. Each simulated person: RT to the cued finger ex-Gaussian, person mean RT normal with mean 350 ms and SD 40 ms (25 and 60 ms for the spread sensitivity, 450 and 50 ms for the slow cohort), tau normal (60, 15) ms, sigma normal (35, 8) ms; finger offsets 0, 5, 20 and 15 ms from index to little (0, 5, 60 and 15 for the weak ring finger); a speed-up of up to about 30 ms when the mean RT exceeds the window; accuracy by a conditional accuracy function, chance below 150 ms and rising with a time constant of about 45 ms to 1 minus a floor of about 2 percent; 75 percent of wrong presses on a neighbouring finger; a central bottleneck so that a response cannot be selected earlier than about 150 ms after the previous one; a press later than the next cue lands in the next trial, as the game scores it. The hand's 72.5 percent pace is found by bisection on 3,000 parallel fixed-pace runs. Two independent 40-trial blocks per person with no learning between them; 300 to 400 people per scenario; cohort checks from 2,000 random draws of 10; ICC(2,1) by the absolute-agreement single-measure formula. The model reproduces the pilot's misses per block (7.7 against 3 to 11) and its post-climb hit rate (0.73 against 0.72 pooled); its hands are faster than the pilot hands (peaks 140 against 90 to 144 BPM).
