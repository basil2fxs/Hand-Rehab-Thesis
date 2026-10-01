# Muscle Memory mode: deep research audit

1 October 2026. Scope: the study battery's Muscle Memory step, `app/finger_rehab/game/modes/pattern.py` (mode key `pattern`), its configuration and battery override, what the participant is told and shown, its logging, and the notebook analysis (P1, P2, P3, W3, the cohort rows, the second-go table). Free play, the bimanual 24-item material and researcher sequence files are out of scope except where they touch the battery.

Tags: [FT] full text read, with the table or section named; [FT, PMC page] full text read from the PMC article page; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the assumptions at the end of Section 7; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository. Line numbers refer to commit 25924da, where `pattern.py` matches the working tree; `default.yaml`, `engine.py`, `screens.py` and the notebook carry later edits for other modes, so functions and config keys are named beside the lines. Notebook line numbers are lines of cell 2's source.

---

## 1. What the mode does now

### 1.1 The block under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Settings | The battery lays `short_session: true`, `soc_cycles_per_block: 3` and `random_block_trials: 32` over the shipped `pattern:` block (defaults 4 cycles and 48 random trials) | 8 takes, 296 presses (arithmetic: 12 + 32 + 7 x 36) | `default.yaml` protocol.presets.study_battery.overrides.pattern (line 2035); defaults 952-1004 |
| Before the block | NEXT UP card: title "Muscle Memory" and the hub line "Play takes of a piano riff"; GET READY countdown with no instruction line for this game | 3.0 s | `screens.py` MODES (1532), `_draw_next_up` (6706, description 6760), GET_READY_LINES (3743, entries for echo and chords only); `default.yaml` 599 |
| Warm-up | 12 trials from a balanced bag, no finger twice running; out of every analysis | 12 | `pattern.py` 916-919; `default.yaml` 956 |
| Take 1 | Random baseline from the same kind of bag | 32 | `_build_layout` 924-935 |
| Takes 2 to 8 | trained, trained, trained, PROBE, trained, PROBE, trained; 3 cycles of the 12-item sequence per take; every take starts at cycle position 0 | 36 trials per take | 924-927; `soc_block` 910-914 |
| Take start | "Take k of 8" for 1.2 s; first cue 1.5 s after the take starts; probe takes look the same as trained takes | | `_begin_segment` 1035-1041; `SEGMENT_LEAD_S` 620 |
| Cue | Tile lit in its finger colour on grey idle tiles; buzzer under the target finger; lane tone C4, E4, G4, C5 from index to little, 0.12 s; every tenth stimulus of the block plays with gain 1.35 | buzz 250 ms | `engine.on_stim_multi` (8667); `audio/engine.py` 103-105; `default.yaml` 388, 398, 493, 1845-1847; `engine._is_loud_trial` 812-821 |
| Response | The cue stays lit until the correct finger presses or 2.0 s pass. A wrong press is logged with its lane and time, costs the wrong-press penalty, and turns the trial into a Miss row that still carries the correct press's RT | 2.0 s | `update` 1025-1026; `_handle_press` 1133-1144; `_close` 1146-1162; `default.yaml` 978 |
| Interval | Next cue 500 ms after the correct press is processed; median 510 to 511 ms from the press stamp to the next stimulus stamp (pilot) | 500 ms | `_close` 1203-1207; `default.yaml` 974 |
| Press between cues | No penalty and no trial row; counted per take as `n_rsi_presses`. A press is a rising threshold crossing with a 100 ms debounce, so a finger still down when the cue comes must lift and press again | | `_handle_press` 1120-1132; `hardware/fsr_detector.py` (`debounce_ms`, the press branch of `feed`) |
| Rests | Self-paced after a 10 s floor (any finger continues); no long rest in the short session | 10 s | 948-949, 1112-1117, 1256-1260; `default.yaml` 993-994 |
| Fatigue guard | Five straight timeouts in a non-probe take force a 45 s rest; a second run ends the block; 30 min cap | | 1214-1227; `default.yaml` 1000-1004 |
| Feedback | Lane flash green on a hit, grey on a miss, gold when the correct press lands at or under 100 ms (the Perfect tier); tier points flattened to one value; stars per take for accuracy only (3 at 95 percent, 2 at 85, 1 at 70) and a three-star streak; RT never shown | | engine `_outcome_colour` (8066-8084), `begin_pattern_block` (4659-4663), `log_trial` flash (9073-9105); `_stars` 1262-1275; `scoring.perfect_ms` (`default.yaml` 714) |
| RT hygiene | Per take: misses out, the first 12 trials (one cycle) out, under 100 ms out, then over take mean + 2.5 SD out; accuracy keeps every trial | | `_segment_rt_stats` 1382-1418; `ANTICIPATION_CUT_MS` 614; `OUTLIER_SD` 617 |
| Score | Each probe's trimmed mean RT minus the mean of its two flanking trained-take means (take 5 against takes 4 and 6; take 7 against takes 6 and 8); the session score is the mean of the two; accuracy rebound the same way | | `block_stats` 1469-1498; `_flanker_indices` 1420-1432 |
| Length | 6.28 min with a model participant | | design doc Section 2.3 (M) |

Exposure (arithmetic): probe 1 follows 108 trained trials (9 cycles) and probe 2 follows 144 (12 cycles). The full ten-take layout puts them after 144 and 288. About 23 RTs per take enter a take mean after the trim and about 6 percent errors (simulation).

Place in the sitting: order A step 7, straight after Buzz Hunt, whose last stage asks the participant to replay buzz sequences on the same four fingers under the heading REPLAY THE PATTERN (`buzz_hunt.py` STAGE_ORDER and stage titles, 627-631); order B step 8, straight after Echo, which shows a sequence of lit and sounded fingers and asks for it back (`default.yaml` 1975, 1993; design doc Section 2.2). The 60 minute sitting plays the block again at step 15 (order A, after Buzz Hunt) or 16 (order B, straight after Echo), about 22 minutes after the first (arithmetic from the block minutes in design doc Section 2.3 plus 10 s transitions). The 30 minute sitting plays a short-family block of 204 presses (2 cycles per take, a 24-trial random take; `trial_short`), whose takes keep 12 RTs each after the trim (arithmetic). Pattern is the block to drop if a sitting runs over (design doc Section 2.2).

### 1.2 The material

- Trained sequence: a 12-item second-order conditional (SOC) cycle seeded from SHA-256 of the trimmed, lower-cased participant code plus "|srtt_v1" (`participant_seed` 316-323), drawn by randomised backtracking over the 12 ordered finger pairs (`generate_soc` 326-354). Each finger appears 3 times and each ordered pair of different fingers once per cycle.
- Probes: a pool of up to 4 SOC cycles that share no triplet with the trained cycle (no finger pair is followed by the same finger) and differ from each other up to rotation (`build_sequences` 483-535). Each block draws a random offset and plays two consecutive pool members (707, 952-955).
- Structure of all 12-item SOC cycles (simulation, full enumeration): 256 cycles up to rotation, 12 up to relabelling the fingers. Reversals (x-y-x) per cycle: 1 in 48 cycles, 3 in 112, 4 in 96. Runs of three neighbouring fingers (for example 1-2-3) per cycle: 0 to 4. Neighbouring-finger transitions: 6 per cycle in every SOC.
- What the generator gives codes P01 to P99 (simulation): a pool of 4 for 80 codes and 3 for 19; zero shared triplets in every pool member; trained reversals 1 (18 codes), 3 (39) or 4 (42); probe minus trained reversals 0 for 289 of 377 pool members, +3 for 59 and -3 for 29.
- Random material (warm-up and take 1) has no immediate repeats, so about one triplet in three is a reversal (arithmetic), against 1 to 4 in 12 for the SOC material.
- The second block in the 60 minute sitting uses the same trained cycle and pool with a new random offset, so at least one probe repeats with probability 3/4 for a pool of 4 and always for a pool of 3 (arithmetic).

### 1.3 What the participant is told and shown

- Information sheet (`docs/study_day/information_sheet.md` 58): some games have a hidden rule that is explained at the end. Run sheet (`run_sheet.md` 42): the RA says once "Some games have a hidden rule; don't try to work it out, just play." The run sheet gives game lines for Reaction, Rhythm, Echo, Force Pilot and Chords (a Buzz Hunt line is being added in the working tree), none for Muscle Memory.
- On screen: the NEXT UP card's "Play takes of a piano riff", a REC chip "TAKE k OF 8 n/36", rest cards with stars, never an RT and never the word sequence (`screens.py` `_draw_take_chip` 4160).
- Debrief (`debrief.md` 5-8): the repeating pattern and the switched takes are explained.
- Nothing asks about awareness before the debrief. An awareness check was left open for the author on 30 September (`docs/research/new_modes/modes-review.md`, Left open).
- Intake: years playing a keyboard or string instrument (music_years) joined the intake sheet on 1 October 2026; the notebook's `COHORT_MUSIC_METRICS` (20714-20719) already includes the pattern learning score as a descriptive split.

### 1.4 Logging and block_stats

- trials.csv: one row per trial, `stimulus` packing "kind;b=take;soc=id;pos=cycle position", `pattern_trial` TRUE for trained takes only, `time_difference_ms` (the correct press), `first_incorrect_ms`, `first_incorrect_lane`, `cue_flags`, `loud_trial` (1187-1196).
- raw.csv: every press and release with lane and time, every stimulus with its trial id, the `pattern_config` line with both seeds, and `fatigue_rest` events (1293-1304; engine 4683-4692).
- block_stats (1434-1551): seeds, material and schedule id, trained cycle, probe pool and offset, layout, interval and window, rests, `start_trim`, and per take n, accuracy, trimmed mean RT, `n_rt_used`, `n_start_excluded`, `n_anticipation`, `n_rt_outliers`, `n_rsi_presses`; then `fatigue_rest_positions`, per-probe `learning_score_ms` and `accuracy_rebound_pct`, and `session_learning_score_ms`.

### 1.5 Registered checks and the notebook

- P1 (design doc Section 1.2; notebook 25106-25108): cohort mean of each person's session learning score above zero, one-sample Wilcoxon, one-sided. A pass also needs the two-sided 95 percent t interval to clear zero (`_mean_check`, 24309). P1's p sits in the Holm family of nine tested rows (P1, P3, C2, C6, W4, Rh1, B2, F1, F2), whose first threshold is 0.0056 (`modes-review.md`, Reliability and the Holm family).
- W3 (25658, 25772): P1 under its Table 2 id, counted once.
- P3 (25110-25112): mean accuracy rebound above zero, the same test.
- P2 (`_p2_row`, 24243): pass 2 minus pass 1 learning score above zero, one-sided Wilcoxon; DROPPED when nobody played the block twice and "n under the design minimum" below 8 (`COHORT_MIN_N`, 20206).
- Cohort rows (`_cohort_pattern`, 21720): learning_score_ms, learning_score_prop, accuracy_rebound_pct, random_take_rt_ms, trained_take_rt_ms.
- Per-selection chapters (`sec_pattern_srtt` 11722, `_pattern_srtt_group` 11874, `sec_pattern_checks` 27522, `pattern_accuracy_rebound` 27629): the take table with the mode's hygiene, per-probe scores with a bootstrap interval over pooled trial RTs, a per-finger median, the literature rows and claim limits.
- Reliability: no split-half for the learning score (`COHORT_NO_SPLIT_REASON`, 23514: "a contrast between takes, not a trial value"); pass 2 against pass 1 in the exploratory second-go table for 60 minute sitters (31097); no T row.
- Never read for this mode (code search): `n_rsi_presses`, `n_anticipation`, `fatigue_rest_positions`, `first_incorrect_lane`, and the presses between cues in raw.csv.
- `_cohort_p1_figure` (25986) draws every pattern game in `cohort["trials"]`, which also holds the 60 minute sitters' pass 2 blocks (code).

### 1.6 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status |
|---|---|---|---|
| Probe minus trained RT is the learning index; the effect is consistently found | `pattern.py` 7-16; design doc Section 1.2 P1 ("one of the most replicated effects in cognitive psychology") | Nissen and Bullemer 1987; Robertson 2007 | The standard within-subject transfer measure (Schwarb and Schumacher 2012 [FT]; Robertson 2007 [FT, PMC page]); the "most replicated in cognitive psychology" wording has no source |
| SOC material separates sequence knowledge from location and transition frequency, and makes awareness less likely | 18-27, 85-99 | Reed and Johnson 1994 | The matching logic is verified via Schwarb and Schumacher [FT]; awareness is still common (Q4) |
| Nissen and Bullemer used a 500 ms interval | 161-165 | Nissen and Bullemer 1987 | Verified via Schwarb and Schumacher [FT]; 11 of their 12 participants noticed the sequence |
| 48-trial takes match the 50-trial blocks current SRTT work runs with a 12-item SOC | 116-118; `default.yaml` pattern comment | Oliveira et al. 2024 | Partly: 50-trial blocks of a probabilistic task built from two SOCs, 1,000 trials a session [FT]; the battery's takes are 36 |
| Learning within 4 blocks of 100 | 119-120 | Nissen and Bullemer | Their Experiment 2 ran four 100-trial blocks [FT, via Schwarb and Schumacher]; RT values not read |
| Split-half about .66, retest under .40 | 121-125; design doc Section 1.2 | Oliveira et al. 2023 | Verified [FT], with the caveat that every pooled study ran 380 trials or more (Q5) |
| A rest boosts the next take, so the first cycle of each take leaves the means | 137-159, 173-181 | Gupta and Rickard 2022; Das et al. 2025 | Both [FT] are self-paced tapping tasks; the boost lasts seconds and partly reflects preplanning; SRTT studies drop the first one or two trials (Oliveira 2024 [FT]); a whole-cycle trim is a design choice (Q2) |
| Rest length does not change learning | 148-153 | Szucs-Bencze et al. 2023 | Verified for statistical learning in the ASRT [FT]; general skill learning was weaker with self-paced rests |
| Explicit knowledge impairs implicit learning, so the sequence stays hidden | 194-202; design doc Section 1.2 last lines | Boyd and Winstein 2003, 2004 | True after stroke; explicit information helped the healthy controls (2004 [FT, PMC page]; 2003 [ABS]) |
| Reward tied to performance improves retention | 206-208 | Abe et al. 2011 | Sources disagree: in a pinch-force tracking task, money earned for time on target (13 per group) kept gains at 6 h, 24 h and 30 days better than punishment or neutral feedback (Abe et al. 2011 [FT, PMC page]); in an SRTT and a force-tracking task neither reward nor punishment changed retention at 1 h, 24 to 48 h or 30 days (Steel et al. 2016 [FT]) |
| Unaffected hand after stroke: 69 ms; affected hand: null | 224-228; design doc | Kal et al. 2016 | Verified [FT] |
| A single-session rebound can be temporary adaptation that fades in minutes; P2 "the sequence gain was gone minutes after training" | 228-230; design doc Section 4.6 P2; `MODE_CLAIM_LIMITS["pattern"]` | Trofimova et al. 2020 | Misread in part [FT]: the extra gain from a 300-trial training block was gone at a post-test minutes later, but the sequence advantage stayed above zero at the pretest, the post-test and 8 h later, at the level reached after 60 to 180 sequence trials (Q6) |
| The lane tones make the sequence a melody, which helps serial learning | 231-235; design doc P1; claim limits | Hoffmann, Sebald and Stoecker 2001 | Hoffmann's tones followed the press as response effects and helped only with time before the next stimulus [ABS]; stimulus-locked informative tones gave a small, late advantage under explicit instructions (Leow et al. 2025 [FT, preprint]); redundant cues often add nothing (Abrahamse et al. 2009, 2012 [FT]) (Q7) |
| The melody may make learning explicit; the result is sequence-specific learning within the sitting, not implicit learning | 231-235; design doc P1 | none | Supported and strengthened: the interval, the probes and the melody all favour awareness (Q4) |
| `log_trial` flashes the tier word, a speed hint | 252-261 | none | Out of date: no word is shown per press in the shipped feedback style; the one speed-contingent signal left is the gold flash at or under 100 ms (code) |
| No healthy size to compare | `MODE_LIT["pattern"]` (26311); claim limits; `_pattern_srtt_group` ANCHORS (11956-11965) | Nissen and Bullemer; Kal | Healthy sizes exist for full-length designs and for a mid-task probe (Q1); the battery's exposure is shorter |
| A higher second go is further gain, a lower one temporary adaptation | `MODE_CLAIM_LIMITS["pattern"]`; design doc Section 4.6 P2 | Trofimova 2020 | Sources disagree on what a second go shows (Q6) |
| The cue on the responding finger keeps RTs short and leaves the rebound less room | `MODE_CLAIM_LIMITS["pattern"]` | none | Direction supported: tactile cues at the responding fingers gave smaller sequence effects than visual cues (38 against 60 ms), while adding them to a visual cue changed nothing (Abrahamse et al. 2009 [FT]) |
| Reliability POOR for the individual score; no MDC | design doc Section 1.2 | Oliveira et al. 2023 | Verified; this block's short takes make within-session consistency lower still (Q5, simulation) |

Also cited for this mode and not re-read here: Shin and Ivry 2002 and O'Reilly et al. 2008 (sequence files), Stephan et al. 2009, Savion-Lemieux and Penhune 2005, Wulf and Lewthwaite 2016, Bonstrup et al. 2019 and Buch et al. 2021 (rests), Verwey and Japikse et al. 2003 (bimanual play).

### 1.7 Pilot blocks on disk (rig check only)

Five pattern folders dated 31 August to 29 September 2026; none reached a probe. Two hold no trials, P670 stopped after 21 trials, Test after 31, and P669 ended through the fatigue guard after 69 (ten straight timeouts at the end). Correct RTs: warm-up medians 311 to 331 ms with within-take SDs of 39 to 75 ms; random-take median 319 ms (P669). Wrong-finger rows: 5 of 69 (P669) and 3 of 21 (P670), first wrong presses at 82 to 364 ms, 3 of the 5 in P669 on a neighbouring finger. Interval from the press stamp to the next stimulus stamp: median 510 to 511 ms (interquartile about 503 to 515); press duration from press to release: median 230 to 250 ms. Cue flags BS/-- (buzz and tone before, nothing after) on every row; loud trials on trials 10, 20, 30 and so on (pilot).

---

## 2. Research questions and findings

### Q1. How large is the learning score in healthy young adults with SOC material, how does it grow with exposure, and what can probes after 108 and 144 trained trials show? (P1)

- Full-length SOC designs. Two 12-item SOCs (342312143241 and 341243142132), 15 blocks of 96 trials, the other SOC at block 13: transfer costs of 111 ms (RSI 250 ms, n = 17, t = 8.024) and 91 ms (RSI 0, n = 21, t = 11.091) (Destrebecqz et al. 2005, Methods and Results [FT, PMC page]), which is dz 1.95 and 2.42 and an SD of the cost of about 57 and 38 ms (arithmetic from t and n). One hand, index to little finger, the SOC 242134123143 nine times per 108-trial block, RSI 400 ms, a block of nine different SOCs between blocks 8 and 10: 58 ms (position cue), 61 ms (colour) and 51 ms (position plus colour) after 756 sequence trials, errors under 4 percent (Abrahamse et al. 2012, Experiment 1 [FT]). Two hands, the same SOC, RSI 210 ms, 1,080 sequence trials: 60 ms (visual), 56 ms (visual plus tactile), 38 ms (tactile only) (Abrahamse et al. 2009, Results [FT]).
- Mid exposure. A 12-element deterministic sequence, four fingers of the right hand, about 200 ms from press to next target, 84-trial blocks: a random block after 5 sequence blocks (420 trials) gave 11.2 ms (SD 22.5, t(52) = 3.6); random blocks late in the run gave 36.1 ms (SD 23.6, t(52) = 11.1) (Stark-Inbar et al. 2017, Results [FT, PMC page]), which is dz 0.50 and 1.53 (arithmetic). A 10-item first-order sequence, right hand, 5 sequence blocks of 60 trials (300 trials): random block 7 against sequence block 6, Cohen's d 1.09 (Lum et al. 2023, Results [FT]).
- Early exposure. A 12-item sequence (2-3-1-4-3-2-4-1-3-4-2-1, which is an SOC: its 12 ordered pairs are all different, arithmetic), RSI 500 ms, the target staying until the correct press: the sequence advantage was above zero after 60 sequence trials (t32 = 3.41, p = 0.002) and grew with the number of repetitions (rho 0.24) (Trofimova et al. 2020, Section 3.1 [FT]). The values are in figures only.
- Awareness raises it: with a deterministic sequence, explicit knowledge improves SRT performance (Stefaniak et al. 2008 [ABS]).
- Stroke reference only: 69 ms with the unaffected hand, not different from controls (mean difference -7.5 ms, -34.3 to 19.2) (Kal et al. 2016, Results [FT]).

Bearing. The battery's probes follow 108 and 144 trained trials, a fifth to a tenth of the full-length designs (arithmetic). Read together, the anchors place a cohort mean of roughly 10 to 30 ms at this exposure (a judgement from the sources above, not a source value), larger at probe 2 than at probe 1, and larger in participants who become aware.

What P1 can decide at n = 10 (simulation; the notebook's rule; between-person SD of true learning 10 or 20 ms):

| True cohort mean | Pass at 0.05, trial SD about 63 ms | Pass at 0.0056 (Holm worst case) | Pass at 0.05, trial SD about 85 ms |
|---|---|---|---|
| 0 ms | 0.02 to 0.03 | 0.00 to 0.01 | 0.02 to 0.03 |
| 10 ms | 0.44 / 0.24 | 0.16 / 0.08 | 0.32 / 0.20 |
| 20 ms | 0.96 / 0.69 | 0.75 / 0.36 | 0.83 / 0.59 |
| 30 ms | 1.00 / 0.95 | 0.98 / 0.73 | 0.99 / 0.90 |

(Pairs are for between-person SD 10 / 20 ms.) At n = 8, 12 and 20 with SD 15 ms, a true 20 ms passes 0.70, 0.93 and 1.00 of the time at 0.05 (simulation). P1 is likely to pass if the true effect is near 20 ms or more and unlikely if it is near 10 ms.

### Q2. Is the probe design sound at this length: interleaved SOC probes, flanker subtraction, 36-trial takes and the first-cycle trim?

- The standard within-subject test is several sequence blocks, an alternate-sequence block (usually a different SOC), then a return to the sequence; slower or less accurate alternate blocks are the transfer effect (Schwarb and Schumacher 2012, "Measuring Sequence Learning" [FT]). Reed and Johnson trained one SOC and tested another, which matches location and transition frequency, so the difference can only be sequence knowledge (same source [FT]; Reed and Johnson 1994 [META]). The flanker average matches Abrahamse et al. (block 12 against 11 and 13 [FT]) and Stark-Inbar et al. (random 13 and 15 against sequence 12 and 14 [FT, PMC page]).
- Random comparison material holds more reversal trials, which inflates the learning measure; structurally analogous sequences avoid this and show learning within a short session (Vaquero, Jimenez and Lupianez 2006 [ABS]).
- Learning the probe: Abrahamse et al. built each 108-trial pseudo-random block from nine different SOCs with no element or sequence repetition and never repeated a pseudo-random block for a participant (2009 and 2012, Methods [FT]). Muscle Memory plays one probe SOC three times per probe take (code), and the advantage can appear within 60 trials (Trofimova [FT]), so part of a probe can be learnt inside the take. The first-cycle trim then removes the probe's least-learnt cycle (code).
- Short transfer blocks work: 48-trial sequence blocks between 48-trial pseudo-random blocks showed transfer in every training group (Abrahamse et al. 2009 and 2012, Transfer [FT]).
- First trials of a take: SOC-based SRTT analyses drop the first two trials of each block because they cannot be predicted (Oliveira et al. 2024, Experiment 1 analyses [FT]); a tapping study dropped the first sequence of each trial (Gupta and Rickard 2022, Statistical analysis [FT]). Post-break gains in tapping are transient, appear for non-repeating sequences too, and are partly preplanning (Das et al. 2025, Significance and Experiments 3 to 5 [FT]); reactive inhibition builds within 10 to 30 s of tapping, and a 30 s break cleared what built in 10 s (Gupta and Rickard, Results and Discussion [FT]). Preplanning after a rest helps only someone who knows what comes next, so on trained takes more than on probes (inference from Das et al.); no source trims a whole 12-trial cycle.
- Cost of the trim (simulation): from trial noise alone the SD of a person's session score is 10.4, 12.3 and 17.0 ms with the 12-trial trim and 8.5, 10.3 and 14.0 ms with a 2-trial trim (trial SD about 51, 63 and 85 ms); P1's pass rate at a true 20 ms moves from 0.82 to 0.88 (n = 10, between-person SD 15 ms).
- Reversals: trained and probe material differ by 3 reversals per cycle in 88 of 377 pool members (simulation, Section 1.2).

Bearing: the probe logic meets the standard. At this length three things weaken it: one SOC repeated three times per probe, a trim that drops the probe's first cycle, and reversal mismatches in about a quarter of draws. All three can be checked in the analysis without changing the task.

### Q3. How much should accuracy drop on probes, and can P3 detect it? (P3)

- Sequence groups were faster and more accurate (Nissen and Bullemer Experiment 1, via Schwarb and Schumacher [FT]). Accuracy on sequence blocks was higher than on random blocks by 2.2 percentage points (SD 3.3) late and 1.8 (SD 4.9) mid-run (Stark-Inbar et al. [FT, PMC page]). Error percentages stayed under 4 to 5 percent; learning showed in errors (F(1,50) = 11.7 and F(1,63) = 35.9), while transfer in errors was significant only for some training and test pairings (Abrahamse et al. 2012 and 2009 [FT]). Accuracy sat at 0.88 to 0.92 in every block of a 60-trial-block SRTT (Lum et al. 2023 [FT]).
- Error level follows the instructions: 5.86 percent under "as fast as you can without making too many errors", 4.16, 1.32 and 0.86 percent with accuracy emphasis, feedback and a reward (Trofimova et al., Table 2 [FT]); 6.10 percent in a 500 ms RSI audiovisual SRT with Curtin undergraduates (Leow et al. 2026, Data cleaning [FT]).
- Simulation (n = 10, 6 percent base error, between-person SD of the effect 1.5 points, observed SD of the rebound 3.3 to 3.6 points): P3 passes 0.15 of the time for a true 1-point drop, 0.36 for 2 points, 0.67 for 3 and 0.90 for 4 (0.04, 0.11, 0.31 and 0.60 at the Holm worst case).
- An RT-free alternative (arithmetic, code): on a probe trial whose last two cues were a and b, the trained cycle's successor of the pair (a, b) is never the probe's next finger (zero shared triplets) and never b. A wrong press on that finger is a trained intrusion; among the three fingers other than the target, chance is 1/3. Robertson describes the same thing: when random trials replace the sequence, the participant at first keeps playing the sequence [FT, PMC page]. `first_incorrect_lane` carries the data (code; populated in the pilot rows). About 4 probe errors per person, about 43 per cohort of 10 (arithmetic, 72 probe trials at 6 percent). With 40 pooled errors, a true intrusion share of 0.5 gives one-sided binomial p < 0.05 in 68 percent of cohorts and 0.6 in 96 percent (simulation). Error lanes are biased towards neighbouring fingers (pilot: 3 of 5), so the baseline should be the same share computed on random-take errors rather than 1/3.

Bearing: P3 is weak at n = 10 unless errors fall by 3 points or more on trained takes; the intrusion share is a sharper, RT-free reading of the same knowledge.

### Q4. Will participants become aware of the sequence, and how should awareness be measured?

- Base rates differ widely. 11 of 12 noticed a 10-item hybrid sequence at a 500 ms RSI (Nissen and Bullemer, via Schwarb and Schumacher [FT]). 8 of 63 recalled 5 or more consecutive elements of a 12-item SOC at a 500 ms RSI and were excluded (Trofimova et al., Participants [FT]). 40 percent reported noticing a change; recall match index 0.21 (SD 0.15) against chance 0.136 (Stark-Inbar et al. [FT, PMC page]). Process dissociation (PDP) inclusion 0.45 and 0.42 and exclusion 0.38, all above chance 0.33 (Abrahamse et al. 2009 and 2012, Awareness [FT]); inclusion 0.71 (RSI 250) and 0.59 (RSI 0) against 0.33, exclusion 0.31 and 0.37, with exclusion above chance only at RSI 0 (Destrebecqz et al. 2005, Results [FT, PMC page]). Leow et al. call their 500 ms RSI audiovisual SRT explicit learning (2026, Abstract [FT]).
- What drives awareness. A longer RSI produced more premature responses and more verbal report (Haider and Frensch 2009 [ABS]); a systematic transfer sequence raised reportable knowledge where random transfer did not (Runger and Frensch 2008 [ABS]); blocks alternating sequence and deviant material produced explicit knowledge where randomly mixed trials did not (Esser and Haider 2017, Experiment 3 [FT]); these are reviewed together in Esser, Lustig and Haider 2022 [FT]. Against: the training RSI did not change recognition after incidental learning (Runger 2012 [ABS]); with RSI 0 people showed RT learning yet could neither recognise nor exclude the sequence, with RSI 250 they could control it (Destrebecqz and Cleeremans 2001 [ABS]); a close replication found control at both (Wilkinson and Shanks 2004 [ABS]); objective tests found the knowledge accessible (Shanks and Johnstone 1999 [ABS]).
- This block carries each driver: a 500 ms RSI with room for a press before the cue (510 ms gap, 230 to 250 ms presses, pilot); systematic SOC probes; a 12-note melody on C, E, G, C; a hub line that calls it a riff; the run-sheet line that a hidden rule exists; and, in both orders, a game straight before it that ends in explicit sequence recall on the same fingers (Buzz Hunt's REPLAY THE PATTERN stage in order A, Echo in order B; code). Every take also restarts at cycle position 0 (code), while one SRTT design started each block at a different position to keep explicit knowledge from developing (Steel et al. 2016, Methods [FT]).
- Instructions. Being told about a pattern and asked to find it did not impair learning in young adults but did in older adults (Howard and Howard 2001 [ABS]); search instructions attenuated learning of an alternating sequence in a small imaging study, F(1,8) = 6.1 (Fletcher et al. 2005 [FT, PMC page]).
- Measures and their limits. Verbal report misses knowledge people are unsure of; recognition and generation can run on familiarity; exclusion invites shortcuts such as repeating one sequence (Malassis et al. 2026, Introduction [FT]). There is no consensus measure and awareness may be a continuum (Robertson 2007 [FT, PMC page]). Free generation is scored as the share of generated triplets that belong to the trained cycle, chance 0.33 with no repeats (Destrebecqz et al. 2005 [FT, PMC page]; Abrahamse et al. 2009 [FT]). Awareness tests are underpowered: a meta-analytic dz of 0.31, and power about 0.21 at the median sample of 16 (Vadillo et al. 2016 [FT]). Split-half reliabilities of awareness measures ran 0.34 to 0.75, and at typical lengths the expected reliability is 0.12 (2AFC, 12 trials), 0.16 (recognition, 24 trials) and 0.40 (generation, 12 trials) (Vadillo et al. 2022, author's version [FT]).
- Chance levels for this block's SOCs (simulation): a random 24-press generation without repeats gives a trained-triplet share of 0.33 on average with a 95th percentile of 0.50 (0.60 for 12 presses). A run of 5 or more consecutive elements matching the trained cycle occurs by chance in 21 percent of 12-press and 43 percent of 24-press random generations, because every ordered pair occurs in an SOC; the 95th percentile of the longest run is 6 (12 presses) and 7 (24 presses). Someone who follows the trained successor half the time scores 0.66 on average and clears the 95th percentile 92 percent of the time.

Bearing: some of the cohort will likely become aware, and the RT data cannot say how many. A two-minute generation test can identify explicit learners; at n = 10 it cannot show that the rest learned implicitly. The five-element run criterion is too lenient for SOC material; the triplet share against its chance distribution is the better score.

### Q5. How reliable is the learning score, and what does that mean for P2 and any ICC?

- Retest: pooled r 0.28 (0.16 to 0.40), 0.30 (0.18 to 0.42) with every effect size, 0.37 (0.20 to 0.51) without the authors' laboratory; 0.36 in adults and 0.11 in children; no moderator significant (age, 380 to 3,825 trials, interval, deterministic or probabilistic, index) (Oliveira et al. 2023, Results and Table 2 [FT]). Split-half: 0.63 (0.52 to 0.72) and 0.66 (0.56 to 0.74) (same [FT]).
- Single studies: late learning retest 0.07 (-0.21 to 0.33), mid-run 0.27 (0.00 to 0.50), baseline RT 0.63 (Stark-Inbar et al. [FT, PMC page]). With 1,000 trials a session, split-half 0.50 to 0.62 for difference scores and 0.63 to 0.71 for random slopes, retest 0.08 to 0.17 for both, Bland-Altman limits for the difference score -57.5 to 55.5 ms (Oliveira et al. 2024, Tables 3 and 4 [FT]). Quoted there: a deterministic SRTT 0.38 (Kalra et al. 2019), probabilistic 0.47 (Siegelman and Frost 2015) and 0.70 (West et al. 2021, adults, 1,500 trials, the same sequence, 2 to 3 days), adult split-half 0.84 to 0.92 [FT]. Children: split-half 0.75 and 0.49, retest 0.21 (West et al. 2018, Table 1 [FT]).
- Difference scores are less reliable than their parts when the parts correlate and have similar variance (Hedge et al. 2018, "Difficulties with difference scores" [FT]).
- Sources disagree: Kalra et al. read their medium retest values as stable individual differences in implicit learning [ABS]; Oliveira et al. read the pooled estimate as below acceptable standards [FT].
- This block (simulation): the reliability of the session score (true variance over observed variance) is 0.39 or 0.72 at a trial SD of about 63 ms and 0.25 or 0.58 at about 85 ms, as the true between-person SD runs 10 or 20 ms. An odd-even split-half estimated at n = 10 falls between about -0.45 and 0.79 (10th to 90th percentile) when the truth is 0.39, and between 0.42 and 0.91 when it is 0.72. For 60 minute sitters, the pass 1 against pass 2 correlation has a median of 0.46 or 0.77 if true learning is perfectly stable, and 0.22 or 0.38 if its stability is 0.5, with 10th to 90th percentiles as wide as -0.27 to 0.60.
- Splitting method: permuted splits, stratified by design, are the least confounded with time and task structure (Pronk et al. 2022, Introduction and Discussion [FT]).

Bearing: the design's POOR class for the individual score is right, and within-session consistency here will sit below the pooled 0.63 to 0.66 because the takes are short. The split-half is still worth computing, with its interval, to show how much of the cohort spread is person rather than trial noise.

### Q6. What should the second go show? (P2, retention)

- Trofimova et al. (2020, Results 3.4 and Discussion [FT]): the sequence advantage was above zero in the pretest, training, post-test and 8 h retest (t52 = 5.86, 7.53, 5.77 and 6.11); it did not change from pretest to post-test (t52 = 0.15) or from post-test to retest (t52 = 0.16); it dropped from the end of training to the post-test minutes later (t52 = 2.32, p = 0.02); overall RT fell over the 8 h (t52 = 3.64).
- Offline gains take hours: none at 15 minutes (Robertson et al. 2004 [ABS]); gains at 4 and 12 h, not 1 h (Press et al. 2005 [ABS]); sequence-specific knowledge neither lost nor gained over 24 h or a week, while general skill improved (Meier and Cock 2014 [ABS]); no sequence-specific offline gain over 12 h in the ASRT (Nemeth et al. 2010 [ABS]).
- Larger on a second go: a probabilistic SRT with the same sequences about three months apart, 18.4 ms then 37.5 ms, 64 of 75 better (Siegelman and Frost 2015 [FT, PMC page]); larger in a second session a week later when the sequences were more alike (Oliveira et al. 2024, Experiment 1 [FT]). Sequence knowledge was present at 1 h, 24 to 48 h and 30 days (main effect of sequence F(1,33) = 100.2) (Steel et al. 2016 [FT]).
- Interference: watching a new visual sequence 2 minutes after acquisition held back the RT gain on the original sequence (-11.7 and -8.4 ms against -67.2 ms), while a new auditory mapping alone did not (Leow et al. 2026, Results [FT]); a second 12-unit sequence learned 5 minutes to 24 hours after the first interfered with it at a 48 h test, to the same extent at every delay, and the authors found no evidence of consolidation (Goedert and Willingham 2002, sequence experiments [FT, PMC page]).
- In the 60 minute sitting about 22 minutes separate the two blocks (arithmetic), filled with Reaction, Rhythm, Force Pilot, Chords, Echo and Buzz Hunt on the same four fingers. Straight before the second block comes Buzz Hunt with its sequence-replay stage (order A) or Echo, which shows new sequences on the same lanes with the same tones and asks for them back (order B) (code).
- Simulation: with a true gain of +10 ms and stability 0.5, the change has an SD of about 22 ms; P2 passes 0.25 of the time at n = 6 and 0.22 at n = 8; at n = 4 the one-sided exact signed-rank test cannot reach 0.05 (smallest p 1/16, arithmetic).

Bearing: no offline gain is expected after 22 minutes. The likely outcomes are a similar score (knowledge kept) or a slightly larger one from the second block's own 108 to 144 trained trials; a smaller one after the sequence-recall game that precedes it would fit interference as well as temporary adaptation. P2 among the few 60 minute sitters cannot separate these, and it prints only from n = 8.

### Q7. What do the tile, the buzz on the responding finger and the lane tones do to sequence learning?

- Adding congruent tactile stimuli at the fingers to visual stimuli changed neither sequence learning (56 against 60 ms) nor PDP awareness; tactile-only training gave smaller effects (38 ms), which the authors put down to the high stimulus-response compatibility of a stimulus on the responding finger, leaving less for sequence knowledge to shorten (Abrahamse et al. 2009, Results and Discussion [FT]). Tactile sequence learning occurs, to a lesser degree than visual (Abrahamse et al. 2008 [ABS]).
- Redundant colour and position cues at one location did not enhance learning (51 against 58 and 61 ms), and transfer pointed to response-based learning (Abrahamse et al. 2012 [FT]).
- Compatibility: an incompatible mapping gave more sequence learning than a compatible one (Deroost and Soetens 2006 [ABS]); learning still occurs at maximal compatibility, with saccades to the targets (Kinder et al. 2008 [ABS]); explicit learners shield preplanned responses from conflicting stimulus information (Koch 2007 [ABS]).
- Tones: key-contingent tones after the press improved learning only when there was enough time before the next stimulus (Hoffmann et al. 2001 [ABS]), and only when mapped contingently and in a highly compatible way (Stocker et al. 2003 [ABS]). Stimulus-locked informative tones (C4 to F4, 100 ms) against randomly assigned tones: a later-block advantage in normalised RT, Bayesian evidence only, frequentist contrasts not significant after correction, under explicit instructions and with no random block (Leow et al. 2025, Study 2 [FT, preprint of 1 April 2025]). After acquisition with synchronous informative tones, a new auditory mapping alone did not interfere while a new visual sequence did, which the authors read as learning tied to the visual-spatial cue with sound as an accessory (Leow et al. 2026, Discussion [FT]).
- This block (code): the lane tones rise from index to little finger (C4, E4, G4, C5), so each SOC is a 12-note melody; the buzz lands under the responding finger; every tenth stimulus plays with gain 1.35. About 2 or 3 of the roughly 23 kept RTs per take are loud trials, in trained and probe takes alike (arithmetic), so they add a little noise and no systematic bias.

Bearing: "the melody helps learning" is not supported as a firm claim; "the cue mix changes how learning is expressed and may change awareness" is. The RT cost here is a cost measured to an audio-tactile-visual cue, which must stay fixed (it does: `cue_flags` on every row, `pattern_consistency_groups`, notebook 11669).

### Q8. Timing: the 500 ms interval, the 100 ms cut and presses between cues

- 500 ms is Nissen and Bullemer's interval (Schwarb and Schumacher [FT]); intervals are "often between 200 and 500 ms" (Robertson 2007 [FT, PMC page]).
- Interval and learning: an inconsistent interval did not harm learning and a long one sometimes hid its expression (Willingham et al. 1997 [ABS]); presentation rate changed the RT measure of learning (Frensch and Miner 1994 [ABS]). 500 ms against 200 ms gave a block 2 advantage that reversed at block 4 and equal performance at block 5, with fewer errors at 500 ms (Leow et al. 2025, Study 1 [FT, preprint]); the abstract reports the 500 ms interval as better.
- Anticipation is how learning shows: RT distributions became bimodal with practice, with an anticipatory mode below 182 ms (170 to 189 ms block by block) that grew across blocks and was larger in musicians, who were also 45.93 ms faster (Leow et al. 2026, Results [FT]). That study kept fast responses and removed only errors (6.10 percent) and RTs over 1,000 ms (2.18 percent) [FT].
- Premature responses lead to verbal report (Haider and Frensch 2009 [ABS]).
- This block (code): correct presses under 100 ms leave the RT means (counted as `n_anticipation`); presses between cues leave no row (counted as `n_rsi_presses`); a finger still down when the cue comes must lift and press again, so an early press on a trained take can turn into a long RT. Both rules fall mostly on trained takes, which makes the measured learning score conservative.
- Rig: every RT carries 0 to 16.7 ms between the update tick and the frame and the press-stamping delay (`pattern.py` 278-286; `modes-review.md`, Device facts); both are common to probe and trained takes and cancel in the score.

Bearing: keep the interval (classic and fixed). Report anticipations as a learning measure rather than only removing them.

### Q9. Does drawing a different SOC for every participant matter?

- Facts in Section 1.2 (simulation): 12 distinct structures up to relabelling; trained reversals of 1, 3 or 4 per cycle; a 3-reversal mismatch between trained and probe in 88 of 377 pool members.
- Reversal trials are excluded in ASRT analyses (9.09 percent of trials were trills) (Szucs-Bencze et al. 2023, Methods [FT]); reversal-rich random comparisons inflate learning (Vaquero et al. 2006 [ABS]).
- The usual design counterbalances two fixed SOCs (Destrebecqz et al. 2005 [FT, PMC page]; the pair from Shanks and colleagues in West et al. 2018 and Oliveira et al. 2024 [FT]).

Bearing: per-code sequences spread sequence-specific quirks across people instead of biasing the whole cohort, at the cost of between-person noise. A sensitivity score without reversal trials removes the mismatch; logging each person's sequence features costs nothing.

### Q10. Feedback, score and instructions

- Feedback tied to performance (mean RT over accuracy per block, as money won or lost) increased early sequence knowledge in an SRTT, and punishment speeded RT during training; neither changed retention (Steel et al. 2016, Results [FT]).
- Instructions move errors from 5.86 percent to 0.86 percent (Trofimova et al., Table 2 [FT]). Typical instructions ask for speed and accuracy: "as quickly and accurately as possible" (Leow et al. 2026 [FT]; Steel et al. 2016 [FT]), "as fast as they could without making errors" (Trofimova [FT]); one SRTT gave no speed instruction at all (Lum et al. 2023 [FT]).
- Explicit information helped healthy controls and hurt people after stroke (Boyd and Winstein 2004 [FT, PMC page]; 2003 and 2006 [ABS]).
- This block (code): accuracy-only stars, flattened tier points, a streak multiplier on hits, a wrong-press penalty, the gold flash at or under 100 ms, and no instruction line on screen or on the run sheet.

Bearing: the feedback follows the mode's own guard rail (reward accuracy, never speed) except the gold flash, which pays only for presses fast enough to be anticipations. With no instruction, each participant picks their own speed-accuracy setting, which moves both RT and P3.

### Q11. Fingers, hand, handedness and errors

- One-hand four-finger mappings are the norm: right hand on V, B, N, M (Stark-Inbar et al. [FT, PMC page]); dominant hand, index to little (Abrahamse et al. 2012 [FT]); right hand, digits 2 to 5 (Lum et al. 2023 [FT]); right hand on a four-button box (Trofimova et al. [FT]).
- The non-dominant hand learns: SRT learning with the left hand of right-handers transferred to the right hand (Grafton et al. 2002 [ABS]).
- Every SOC uses each finger 3 times and each ordered finger pair once per cycle, with 6 neighbouring-finger transitions (simulation), so finger difficulty matches between trained and probe material at the level of single transitions.
- Post-error trials are slower and some SRTT analyses drop them; participants with over 15 percent errors were excluded (Esser and Haider 2017, Experiment 1 Results [FT]).

Bearing: no change needed. Left-handers on the right-hand device are in the pooled sample on their non-dominant hand, which the design already handles (design doc Section 4.9).

### Q12. What should the analysis compute?

- Trimming by SD keeps bias small; median-absolute-deviation and Tukey rules inflate Type I errors; no exclusion gives the largest bias (Berger and Kiefer 2021, Discussion [FT]).
- Index: difference, ratio and random-slope indices did not differ significantly in retest reliability (Oliveira et al. 2023 [FT]); random slopes had higher split-half than difference scores (Oliveira et al. 2024, Table 3 [FT]); there is no empirical support for normalising by baseline RT (Abrahamse et al. 2012, Experiment 1 introduction [FT]).
- Trial-level models: log RT with participant random slopes (Oliveira et al. 2024 [FT]); a Student-t likelihood with maximal random effects (Leow et al. 2026 [FT]); Barr et al. 2013 [META]. The project's own REML helper fits a random intercept only (`finger_rehab/analytics/mixed_model.py`, module docstring).
- First trials: drop the first two of each block (Oliveira et al. 2024 [FT]).
- Exclusions in this family of tasks: errors, trills and RTs over 1,000 ms (Szucs-Bencze et al. 2023 [FT]; Leow et al. 2026 [FT]); post-error trials (Esser and Haider 2017 [FT]).
- Split-half: stratified permuted splits (Pronk et al. 2022 [FT]).

### Q13. What may the thesis say about patients?

- Stroke: the unaffected hand learns (69 ms, 45.1 to 92.9), the affected hand shows no clear learning (SMD -0.11, -0.45 to 0.25), risk of bias is high, and most studies tested one session with no retention (Kal et al. 2016, Results and Discussion [FT]).
- Explicit information: helpful in healthy controls, harmful after basal ganglia or middle cerebral artery stroke (Boyd and Winstein 2003 [ABS], 2004 [FT, PMC page], 2006 [ABS]).
- Parkinson's: worse sequence learning than controls, SMD 0.73 (0.38 to 1.07) over 6 studies (Siegert et al. 2006 [ABS]); 0.531 over 27 studies, I-squared 58 percent, with an abstract interval of 0.332 to 0.470 that does not contain the estimate (Clark et al. 2014 [ABS]).
- Learning claims need a delayed retention or transfer test (Kantak and Winstein 2012 [ABS]; Trofimova et al. 2020 [FT]).

Bearing: the healthy study can show that the rig reproduces a sequence-specific RT cost in a short block; it says nothing about patients.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Sequence type | 12-item SOC per participant code (`generate_soc`) | SOC is the standard control for frequency (Schwarb and Schumacher [FT]); per-person cycles spread sequence quirks across people (Q9) | Keep; log sequence features |
| Probe material | One zero-overlap SOC repeated 3 cycles per probe take | Zero overlap meets the standard; blocks of several SOCs stop within-block learning (Abrahamse 2009, 2012 [FT]) | Keep; check RT by probe cycle; several SOCs per probe after collection |
| Probe placement | Takes 5 and 7, flanked by 4 and 6, and 6 and 8 | The standard sandwich [FT] | Keep |
| Exposure before probes | 108 and 144 trained trials | Effects grow with exposure (Trofimova [FT]; Stark-Inbar [FT]) | Keep (time); state the expected size |
| Take length and trim | 36 trials, first 12 out of RT | First one or two trials dropped in SRTT work (Oliveira 2024 [FT]); post-rest transients last seconds (Das; Gupta [FT]) | Keep as registered; add a 2-trial sensitivity row |
| Random take | 32 trials, not SOC-matched | Baseline only; reversal rate 1 in 3 against 1 to 4 in 12 (arithmetic) | Keep; never read random minus trained as learning |
| Warm-up | 12 random trials (44 random trials in all before training) | 50 random practice trials in a comparable study (Leow 2026 [FT]) | Keep |
| Interval | 500 ms fixed | Nissen and Bullemer's value [FT]; favours awareness (Haider and Frensch [ABS]) | Keep; measure awareness |
| Window | 2.0 s; the cue waits for the correct finger | Same rule as Trofimova [FT]; 2,000 ms in Stark-Inbar [FT] | Keep |
| Anticipation cut | Correct presses under 100 ms out of RT | Fast responses are the learning signal (Leow 2026 [FT]) | Keep for P1; add anticipation measures and a sensitivity score that keeps them |
| Presses between cues | No row, counted per take, the finger must re-press | Premature responses index knowledge (Haider and Frensch [ABS]) | Change logging (lane and match); rule after collection |
| Outlier trim | Mean + 2.5 SD within take | SD rules keep bias small (Berger and Kiefer [FT]) | Keep |
| Errors | Miss row, RT kept in the row, out of the mean | Standard; intrusions carry knowledge (Q3) | Keep; add the intrusion share and a post-error sensitivity row |
| Cue mix | Tile + buzz on the finger + lane tone | Redundant cues add no learning; a cue on the responding finger compresses expression (Abrahamse 2009, 2012 [FT]) | Keep fixed; state it with every number |
| Loud trials | Every tenth stimulus, gain 1.35 | No systematic effect on the score (arithmetic) | Keep |
| Take start | Cycle position 0 every take | Varied start positions are used to limit awareness (Steel 2016 [FT]) | Keep now; vary after collection |
| Rests | 10 s floor, self-paced | Rest length does not change statistical learning (Szucs-Bencze [FT]) | Keep |
| Stars and points | Accuracy only; points flattened | Performance feedback changes expression (Steel [FT]) | Keep |
| Gold flash | At or under 100 ms | The one speed-contingent reward; lands on anticipations | Change (low priority) or document |
| Instructions | No game line on screen or on the run sheet | Instructions set the error rate (Trofimova Table 2 [FT]) | Add |
| Hidden-rule line | Information sheet and run sheet | Indirect evidence that it invites search (Q4) | Keep (consent wording); measure awareness |
| Awareness check | None | Needed to read P1 (Q4) | Add |
| Second block in the 60 | Same layout, new probe offset | No offline gain expected at 22 minutes [ABS]; P2 underpowered (simulation); probe repeats likely (arithmetic) | Keep; report as an estimate; use the unused probes |
| P1 rule | One-sided Wilcoxon, t interval clears zero, Holm | Pass chance 0.24 to 0.96 at n = 10 for true 10 to 20 ms (simulation) | Keep; print the expected range beside it |
| P3 rule | The same on accuracy | Pass chance 0.36 at a 2-point drop (simulation) | Keep; add the intrusion share |
| Reliability outputs | None for the learning score | A split-half of a difference score is computable (Oliveira; West [FT]; Pronk [FT]) | Add |
| P1 figure | Draws pass 2 blocks too | Pass 1 only is registered | Fix |
| Fatigue rests | Positions logged, never read | Forced rests inside a flanker move the score (code docstring) | Add a flag |
| Order | An explicit sequence-recall game straight before Muscle Memory in both orders (Buzz Hunt's replay stage in A, Echo in B) | Interference and awareness triggers, indirect (Q4, Q6) | Report by order; a buffer block optional |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

Only four items touch the game itself: the probe material of the 60 minute second block (item 8, DESIGN-CHANGE part), the block order (item 10), the gold flash (item 11) and the after-collection list (item 12). Item 1 adds a step after the last block; item 7 adds an instruction line; everything else is text, logging or analysis.

1. **Add a two-minute awareness check at the end of the sitting.** DESIGN-CHANGE (a protocol amendment that adds a measure; no registered row changes; log it in the design document with its start date).
   What: after the sitting's last block (the 45: after step 12; the 60: after step 16) and before the debrief, the RA (a) asks "In the long pressing game, did you notice anything about the order of the lights? If so, what?" and writes the answer down; (b) asks the participant to play 24 presses on the pads, or write 24 finger numbers (1 index to 4 little), "in the order the lights came in that game, guessing where unsure". Score the trained-triplet share against chance (mean 0.33, 95th percentile 0.50 for 24 presses) and the longest run matching the trained cycle (95th percentile 7), never the five-element run rule, which random guessing meets 43 percent of the time with SOC material (simulation). Report P1 for everyone and again without the participants above the 95th percentile, as description only; do not correlate awareness with learning at this n (Vadillo et al. 2022 [FT]); do not read a null awareness result as implicit learning (Vadillo et al. 2016 [FT]).
   Files: `docs/study_day/run_sheet.md` (AT THE REST AND AT THE END, before the debrief), `docs/study_day/intake_sheet.md` and `intake_sheet_template.csv` (columns pattern_noticed, pattern_report, pattern_generation), design doc Sections 1.2 and 5.2; in the notebook a reader beside `cohort_intake_sheet` and a scoring function `pattern_generation_score(trained_soc, presses)` that reads `block_summary.pattern.trained_soc`, called from `sec_pattern_checks` (27522) and the P1 detail in `sec_cohort_validity` (25106). A software step reusing the recall screen design in `srt.py` (lines 51-55, `_recall_add` 841) is an alternative that logs the presses directly.
   Evidence: 11 of 12 aware at a 500 ms RSI (Nissen and Bullemer via Schwarb and Schumacher [FT]); 13 to 40 percent in other deterministic designs (Trofimova; Stark-Inbar [FT]); the drivers present in this block (Q4).

2. **Correct the claims the evidence contradicts.** SAFE-NOW (text only).
   - Trofimova 2020, in `pattern.py` 228-230, design doc Section 4.6 P2 and `MODE_CLAIM_LIMITS["pattern"]` (26919 onward): "the extra gain from a long training block was gone at a post-test minutes later; the sequence advantage itself stayed above zero, at the level reached after 60 to 180 sequence trials, and showed no offline gain over 8 h".
   - The melody, in `pattern.py` 231-235, design doc P1 and the first claim limit: Hoffmann et al. 2001 studied response-effect tones after the press; for tones at the cue the evidence is a small late-block advantage under explicit instructions (Leow et al. 2025) and no gain from redundant cues (Abrahamse et al. 2009, 2012). Reword to "may change how learning is expressed and may make it explicit".
   - Reward and retention, `pattern.py` 206-208: say the sources disagree. Reward kept gains at 6 h, 24 h and 30 days in a pinch-force tracking task (Abe et al. 2011), while neither reward nor punishment changed retention in an SRTT or a force-tracking task (Steel et al. 2016).
   - Why the sequence stays hidden, `pattern.py` 194-202 and design doc Section 1.2: explicit information hurt stroke groups and helped healthy controls (Boyd and Winstein 2004); in the healthy study the reason is the construct (sequence learning with as little explicit help as possible), not harm.
   - Design doc P1: replace "one of the most replicated effects in cognitive psychology" with "the standard within-subject measure (Schwarb and Schumacher 2012; Robertson 2007)", and "expect tens of ms" with "roughly 10 to 30 ms at this exposure, against 51 to 111 ms after 756 to 1,152 trials (Abrahamse et al. 2012; Destrebecqz et al. 2005) and 11 ms after about 420 trials (Stark-Inbar et al. 2017)".
   - `MODE_LIT["pattern"]` P1 reference (26311) and the ANCHORS print in `_pattern_srtt_group` (11956-11965): the same anchors with their exposure.
   - `pattern.py` 116-118 and the `soc_cycles_per_block` comment in `default.yaml`: Oliveira et al. 2024 ran a probabilistic task of 1,000 trials in 50-trial blocks; the battery's takes are 36.
   - `pattern.py` 252-261: the shipped feedback shows no tier word; the lane flashes green on a hit, grey on a miss and gold at or under 100 ms.
   - Design doc Section 1.2 reliability paragraph: add that the pooled studies ran 380 to 3,825 trials a session, while this block keeps about 23 RTs per take.

3. **Add RT-free and anticipation-based readings of sequence knowledge.** SAFE-NOW (analysis and logging only; no registered measure changes).
   - Notebook, new `pattern_intrusions(trials, metas)`: on probe trials with a wrong press, the share whose `first_incorrect_lane` is the trained cycle's successor of the previous two cues, against the same share on random-take errors (lane bias baseline) and against 1/3; pooled binomial across the cohort, printed as an exploratory row in `sec_pattern_checks` and beside P3.
   - Notebook, new `pattern_anticipations(rows, raw)`: per take kind, correct presses under 100 ms and under 182 ms (Leow et al. 2026), and presses between cues from raw.csv with the share that match the next cue (trained takes) or the trained successor (probes); a sensitivity learning score that keeps correct presses under 100 ms.
   - `pattern.py` `_handle_press` (1120-1132) and `block_stats` per_take (1453-1468): count `n_rsi_match_next` (the press lane equals the coming cue's lane, known from `seg.fingers[self._trial_in_seg]`) and, on probes, `n_rsi_trained_successor`, and write a raw.csv event with the pressed and coming lanes. The task does not change.

4. **Give the learning score a reliability output.** SAFE-NOW.
   Replace the `COHORT_NO_SPLIT_REASON["learning_score_ms"]` entry (23514) with a split: permuted halves stratified by take and cycle position (Pronk et al. 2022), the learning score recomputed in each half with the mode's hygiene, the Spearman-Brown value and its interval over 1,000 splits, printed in the internal-consistency forest (`COHORT_SPLIT_SOURCES`, 23492). Print beside it the simulation's expectation (true reliability about 0.25 to 0.72; an n = 10 estimate that can fall below zero). For 60 minute sitters, keep the second-go ICC exploratory and say that retest values of 0.07 to 0.38 are what the literature reports (Stark-Inbar; Oliveira 2023; Kalra via Oliveira 2024).

5. **Report P1 with what it can and cannot show.** SAFE-NOW.
   In `sec_cohort_validity` (25106) add to the P1 detail line: probe 1 and probe 2 scores separately (exposure 108 and 144 trials), the expected range (roughly 10 to 30 ms), and the simulated pass chance at the observed spread (0.24 to 0.96 for true 10 to 20 ms at n = 10). Add an exploratory trial-level model beside it: log RT on take kind (probe against flanker) with a participant random intercept using the existing REML helper (`fit_random_intercept`), and a shrunken individual score (each person's score pulled towards the cohort mean by its reliability) for any individual display. Methods: Oliveira et al. 2024 and Leow et al. 2026 [FT].

6. **Sensitivity rows that need no task change.** SAFE-NOW.
   In `_pattern_srtt_group` (11874) and `_cohort_pattern` (21720): (a) the score with only the first 2 trials of each take dropped (Oliveira et al. 2024); (b) probe RT per cycle (1, 2, 3, untrimmed) to show learning inside the probe; (c) the score without reversal trials (x-y-x) in all takes (Szucs-Bencze et al. 2023; Vaquero et al. 2006), with each person's trained and probe reversal counts in the cohort CSV; (d) the score without post-error trials (Esser and Haider 2017); (e) takes containing a forced rest flagged from `fatigue_rest_positions`, with the score recomputed without them; (f) loud against quiet trials using the existing `loud_trial_split`.

7. **Tell the participant what to do in this game.** SAFE-NOW (UX; it changes what participants are told, so the author approves the wording and it is logged in the design document).
   `screens.py` GET_READY_LINES (3743): add `"pattern": ("Press each finger as it lights up,", "as quickly and accurately as you can.")`. Run sheet: add the same line to the list of first-time game lines. It must not mention a pattern, a repeat or a riff. Evidence: instructions set the error rate and the speed-accuracy balance (Trofimova et al., Table 2 [FT]); the common SRTT instruction (Leow et al. 2026; Steel et al. 2016 [FT]).

8. **P2 and the second block in the 60.** SAFE-NOW for the reporting; DESIGN-CHANGE for the material.
   SAFE-NOW: in `_p2_row` (24243), when fewer than 8 people sat the 60, print each person's pass 2 minus pass 1 score and the median change with its interval, flagged as description; mark which probe ids repeated between the blocks (the `soc` field) and which game came straight before. Reword the design doc's P2 expectation: no offline gain is expected after about 22 minutes (Robertson et al. 2004; Press et al. 2005), so a similar or slightly larger score is the likely result, and a smaller one fits interference as well as temporary adaptation.
   DESIGN-CHANGE: give the second block the probe pool members the first block did not use. `engine.begin_pattern_block` (4573) passes the battery phase to `PatternMode`; in `__init__` (707) the offset becomes a function of the participant seed plus 2 for pass 2 (with a pool of 3, the unused member first).

9. **Fix two analysis slips.** SAFE-NOW.
   `_cohort_p1_figure` (25986): keep rows with `phase == COHORT_PHASE` (pass 2 blocks are drawn now) and draw pass 2 as its own panel when present. `pattern_learning_scores` (11598): build the per-probe interval by resampling within each take and combining take means, to match the point estimate's mean of take means.

10. **Both orders put an explicit sequence-recall game straight before Muscle Memory.** SAFE-NOW for the reporting; DESIGN-CHANGE for the order.
    Report P1, P3 and (once collected) awareness by order A and B as description, and name the preceding game in the claim limits. Optional: a non-sequence block between them, by swapping order A's steps 7 and 8 (Adaptive, then Muscle Memory) and order B's steps 7 and 8 (Muscle Memory, then Echo) in `default.yaml` study_battery and trial_60 orders, logged as a battery change. The evidence is indirect (a new visual sequence interfered with a learned one, Leow et al. 2026 [FT]; changes in experienced fluency trigger explicit search, Esser and Haider 2017 [FT]), so this is the weakest item.

11. **The gold flash.** SAFE-NOW (UX; flag it in the design document because participants see a change).
    In engine `_outcome_colour` (8066-8084), return the hit green for "perfect" when `current_block == "pattern"`, so no feedback depends on speed, as the mode's docstring promises (`pattern.py` 209-214). Low priority: it affects only presses at or under 100 ms.

12. **After the healthy study.** AFTER-COLLECTION (each changes the task).
    Probe takes built from three different zero-overlap SOCs with no element repeats at the joins (Abrahamse et al. 2009, 2012); each take starting at a different cycle position (Steel et al. 2016); presses before the cue recorded as anticipations rather than discarded; two fixed, counterbalanced SOCs instead of per-code cycles; a cue-condition study (tile only, tile and buzz, tile and tone) to test the melody; and more trained exposure before probe 1 if a longer sitting allows.

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Awareness columns and generation score (triplet share against chance, longest run); P1 with and without explicit learners, descriptive | new reader beside `cohort_intake_sheet`; `sec_pattern_checks` (27522); P1 detail (25106) | Destrebecqz et al. 2005 [FT]; Abrahamse et al. 2009 [FT]; Vadillo et al. 2016, 2022 [FT]; simulation |
| Trained-intrusion share on probe errors against the random-take baseline | new `pattern_intrusions`; `sec_pattern_checks` | Robertson 2007 [FT]; arithmetic |
| Anticipation shares (under 100 and 182 ms) and presses between cues by take kind; sensitivity score keeping sub-100 ms presses | new `pattern_anticipations` reading raw.csv | Leow et al. 2026 [FT]; Haider and Frensch 2009 [ABS] |
| Split-half of the learning score, stratified permuted splits | `COHORT_SPLIT_SOURCES` (23492), `COHORT_NO_SPLIT_REASON` (23514) | Pronk et al. 2022 [FT]; Oliveira et al. 2023, 2024 [FT] |
| Probe 1 and probe 2 separately; expected range and pass chance beside P1 | `sec_cohort_validity` (25106) | simulation; Q1 sources |
| Trial-level model of log RT on take kind (random intercept); shrunken individual scores | beside P1; `fit_random_intercept` copy | Oliveira et al. 2024 [FT]; Leow et al. 2026 [FT]; Barr et al. 2013 [META] |
| Two-trial trim, probe RT by cycle, reversal-free, post-error-free, forced-rest-free and loud-split scores | `_pattern_srtt_group` (11874), `_cohort_pattern` (21720) | Oliveira et al. 2024 [FT]; Szucs-Bencze et al. 2023 [FT]; Esser and Haider 2017 [FT] |
| Sequence features per person (reversals, runs) in the cohort CSV | `_cohort_pattern` extra fields | simulation |
| P1 figure on pass 1 only | `_cohort_p1_figure` (25986) | registered design |
| Per-probe interval resampled within takes | `pattern_learning_scores` (11598) | consistency with the point estimate |
| P2 printed as an estimate under n = 8; repeated probes and order flagged | `_p2_row` (24243) | Q6 |
| P1, P3 and awareness by order A and B; anticipation share in the music split | `cohort_music_split` (20714 onward) and the validity print | Leow et al. 2026 [FT] |

Keep as they are: the per-take hygiene (SD trim, misses out), the mean-of-take-means score, the flanker rule, the one-sided Wilcoxon with the interval rule, the `cue_flags` and schedule consistency groups, the descriptive music split, the claim that the individual score gets no MDC.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| SOC transfer cost after 1,152 trials | 111 ms (RSI 250), 91 ms (RSI 0); dz 1.95 and 2.42 (arithmetic) | Destrebecqz et al. 2005 [FT] | 15 blocks of 96; visual cue; PET study |
| SOC, one hand, 756 trials, RSI 400 ms | 58, 61 and 51 ms by cue; errors under 4 percent | Abrahamse et al. 2012 [FT] | probe block of nine SOCs |
| SOC, 1,080 trials, RSI 210 ms | 60 ms visual, 56 ms visual plus tactile, 38 ms tactile only | Abrahamse et al. 2009 [FT] | two hands; tactile at the fingers |
| Mid-run probe after 420 trials | 11.2 ms (SD 22.5); late 36.1 ms (SD 23.6); accuracy 96.5 percent, baseline RT 373 ms (SD 65) | Stark-Inbar et al. 2017 [FT, PMC page] | 12-element deterministic sequence; about 200 ms interval |
| First-order sequence after 300 trials | d 1.09 | Lum et al. 2023 [FT] | easier sequence type |
| SOC at a 500 ms RSI | above zero after 60 trials; no growth with 300 more; no offline gain over 8 h | Trofimova et al. 2020 [FT] | 53 adults after excluding 8 who recalled the sequence |
| Error rate | 5.86 percent under a speed-and-accuracy instruction; 6.10 percent in a 500 ms audiovisual SRT | Trofimova [FT]; Leow et al. 2026 [FT] | pads are lighter than keys (pilot wrong-finger rows 7 to 14 percent) |
| Awareness | 11 of 12 (hybrid, 500 ms); 8 of 63 (SOC, 500 ms); 40 percent noticed a change | Schwarb and Schumacher [FT]; Trofimova [FT]; Stark-Inbar [FT, PMC page] | measures differ |
| Musicians | 45.93 ms faster; more anticipatory responses | Leow et al. 2026 [FT] | Curtin undergraduates; two hands |
| Stroke, unaffected hand | 69 ms (45.1 to 92.9) | Kal et al. 2016 [FT] | patients, multi-day designs in part |

How to use them: report the device's score as the device's own, measured after 108 and 144 trained trials, to an audio-tactile-visual cue, on force pads, with a 500 ms interval. The published values set an order of magnitude and a direction (larger with more exposure and with awareness), not a norm to test against.

### 6.2 Reliability expectations

- Individual learning scores: retest about 0.28 pooled (0.16 to 0.40), 0.07 to 0.47 in single studies, 0.70 in one adult study with 1,500 trials (Oliveira et al. 2023, 2024 [FT]; Stark-Inbar [FT]).
- Within session: split-half 0.63 to 0.66 pooled at 380 trials or more [FT]; this block's short takes put the true value near 0.25 to 0.72 and an n = 10 estimate anywhere from below zero to about 0.9 (simulation).
- Group effect: detectable at n = 10 if the true mean is near 20 ms or more (simulation, Q1).
- No MDC and no individual change score for this measure.

### 6.3 Claims to avoid

- "Implicit learning": no awareness measure exists yet, and the interval, the probes, the melody and the hidden-rule line all favour awareness. Say "sequence-specific learning within the sitting".
- "Consolidation", "retention" or "memory" from one block or from the 60's second block (no offline gain is expected within an hour).
- "The gain was gone within minutes" for Trofimova et al. 2020; the advantage stayed above zero and did not grow.
- "The melody (or the buzz) helps sequence learning" as a finding.
- Comparing the score with full-length designs without the exposure; any healthy norm.
- An individual learning score as a trait, a change score or an MDC; an ICC for it as test-retest reliability between days.
- Unawareness from a null awareness test at n = 10, or a correlation between awareness and learning at this n.
- "One of the most replicated effects in cognitive psychology".
- That telling healthy adults about the sequence harms learning; it helped healthy controls (Boyd and Winstein 2004).
- That the games before it are neutral: in both orders Muscle Memory follows a game that ends in explicit sequence recall on the same fingers.
- Any statement about patients beyond the cited meta-analyses.

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, PubMed E-utilities, Crossref, OpenAlex, the PMC article pages and publisher or repository copies.

1. Abe M, Schambra H, Wassermann EM, Luckenbaugh D, Schweighofer N, Cohen LG. 2011. Reward improves long-term retention of a motor memory through induction of offline memory gains. Current Biology 21(7):557-562. DOI 10.1016/j.cub.2011.02.030. PMID 21419628. PMC3075334. [FT, PMC page: task, groups, retention results]
2. Abrahamse EL, van der Lubbe RHJ, Verwey WB. 2008. Asymmetrical learning between a tactile and visual serial RT task. Quarterly Journal of Experimental Psychology 61(2):210-217. DOI 10.1080/17470210701566739. PMID 17896207. [ABS]
3. Abrahamse EL, van der Lubbe RHJ, Verwey WB. 2009. Sensory information in perceptual-motor sequence learning: visual and/or tactile stimuli. Experimental Brain Research 197(2):175-183. DOI 10.1007/s00221-009-1903-5. PMID 19565229. PMC2713025. [FT: Method, Awareness, Training, Transfer, Discussion]
4. Abrahamse EL, van der Lubbe RHJ, Verwey WB, Szumska I, Jaskowski P. 2012. Redundant sensory information does not enhance sequence learning in the serial reaction time task. Advances in Cognitive Psychology 8(2):109-120. DOI 10.5709/acp-0108-y. PMID 22679466. PMC3367906. [FT: Experiment 1 Method, Awareness, Training, Transfer]
5. Barr DJ, Levy R, Scheepers C, Tily HJ. 2013. Random effects structure for confirmatory hypothesis testing: keep it maximal. Journal of Memory and Language 68(3):255-278. DOI 10.1016/j.jml.2012.11.001. PMID 24403724. PMC3881361. [META]
6. Berger A, Kiefer M. 2021. Comparison of different response time outlier exclusion methods: a simulation study. Frontiers in Psychology 12:675558. DOI 10.3389/fpsyg.2021.675558. PMID 34194371. PMC8238084. [FT: Discussion]
7. Boyd LA, Winstein CJ. 2003. Impact of explicit information on implicit motor-sequence learning following middle cerebral artery stroke. Physical Therapy 83(11):976-989. DOI 10.1093/ptj/83.11.976. PMID 14577825. [ABS]
8. Boyd LA, Winstein CJ. 2004. Providing explicit information disrupts implicit motor learning after basal ganglia stroke. Learning and Memory 11(4):388-396. DOI 10.1101/lm.80104. PMID 15286181. PMC498316. [FT, PMC page: Methods, Results for healthy controls and stroke]
9. Boyd L, Winstein C. 2006. Explicit information interferes with implicit motor learning of both continuous and discrete movement tasks after stroke. Journal of Neurologic Physical Therapy 30(2):46-57. DOI 10.1097/01.NPT.0000282566.48050.9b. PMID 16796767. [ABS]
10. Clark GM, Lum JAG, Ullman MT. 2014. A meta-analysis and meta-regression of serial reaction time task performance in Parkinson's disease. Neuropsychology 28(6):945-958. DOI 10.1037/neu0000121. PMID 25000326. [ABS]
11. Das A, Karagiorgis A, Diedrichsen J, Stenner MP, Azanon E. 2025. Micro-offline gains do not reflect offline learning during early motor skill acquisition in humans. Proceedings of the National Academy of Sciences 122(44):e2509233122. DOI 10.1073/pnas.2509233122. PMID 41150724. PMC12595466. [FT: Significance, Experiments 1 to 5, Discussion]
12. Deroost N, Soetens E. 2006. The role of response selection in sequence learning. Quarterly Journal of Experimental Psychology 59(3):449-456. DOI 10.1080/17470210500462684. PMID 16627348. [ABS]
13. Destrebecqz A, Cleeremans A. 2001. Can sequence learning be implicit? New evidence with the process dissociation procedure. Psychonomic Bulletin and Review 8(2):343-350. DOI 10.3758/BF03196171. PMID 11495124. [ABS]
14. Destrebecqz A, Peigneux P, Laureys S, Degueldre C, Del Fiore G, Aerts J, Luxen A, Van der Linden M, Cleeremans A, Maquet P. 2005. The neural correlates of implicit and explicit sequence learning: interacting networks revealed by the process dissociation procedure. Learning and Memory 12(5):480-490. DOI 10.1101/lm.95605. PMID 16166397. PMC1240060. [FT, PMC page: Methods (sequences, blocks, groups), Results (transfer, generation scoring)]
15. Esser S, Haider H. 2017. The emergence of explicit knowledge in a serial reaction time task: the role of experienced fluency and strength of representation. Frontiers in Psychology 8:502. DOI 10.3389/fpsyg.2017.00502. PMID 28421018. PMC5378801. [FT: General method, Experiment 1 Results, Experiment 3, General discussion]
16. Esser S, Lustig C, Haider H. 2022. What triggers explicit awareness in implicit sequence learning? Implications from theories of consciousness. Psychological Research 86(5):1442-1457. DOI 10.1007/s00426-021-01594-3. PMID 34586489. PMC9177494. [FT: sections on the Unexpected Event Hypothesis]
17. Fletcher PC, Zafiris O, Frith CD, Honey RAE, Corlett PR, Zilles K, Fink GR. 2005. On the benefits of not trying: brain activity and connectivity reflecting the interactions of explicit and implicit sequence learning. Cerebral Cortex 15(7):1002-1015. DOI 10.1093/cercor/bhh201. PMID 15537672. PMC3838938. [FT, PMC page: Methods, behavioural Results]
18. Frensch PA, Miner CS. 1994. Effects of presentation rate and individual differences in short-term memory capacity on an indirect measure of serial learning. Memory and Cognition 22(1):95-110. DOI 10.3758/BF03202765. PMID 8035689. [ABS]
19. Goedert KM, Willingham DB. 2002. Patterns of interference in sequence learning and prism adaptation inconsistent with the consolidation hypothesis. Learning and Memory 9(5):279-292. DOI 10.1101/lm.50102. PMID 12359837. PMC187137. [FT, PMC page: sequence-learning experiments, interference result, conclusion]
20. Grafton ST, Hazeltine E, Ivry RB. 2002. Motor sequence learning with the nondominant left hand: a PET functional imaging study. Experimental Brain Research 146(3):369-378. DOI 10.1007/s00221-002-1181-y. PMID 12232693. [ABS]
21. Gupta MW, Rickard TC. 2022. Dissipation of reactive inhibition is sufficient to explain post-rest improvements in motor sequence learning. npj Science of Learning 7(1):25. DOI 10.1038/s41539-022-00140-z. PMID 36202812. PMC9537514. [FT: Results, Discussion, Methods]
22. Haider H, Frensch PA. 2009. Conflicts between expected and actually performed behavior lead to verbal report of incidentally acquired sequential knowledge. Psychological Research 73(6):817-834. DOI 10.1007/s00426-008-0199-6. PMID 19034498. [ABS]
23. Hedge C, Powell G, Sumner P. 2018. The reliability paradox: why robust cognitive tasks do not produce reliable individual differences. Behavior Research Methods 50(3):1166-1186. DOI 10.3758/s13428-017-0935-1. PMID 28726177. PMC5990556. [FT: Abstract, "Difficulties with difference scores"]
24. Hoffmann J, Sebald A, Stocker C. 2001. Irrelevant response effects improve serial learning in serial reaction time tasks. Journal of Experimental Psychology: Learning, Memory, and Cognition 27(2):470-482. DOI 10.1037/0278-7393.27.2.470. PMID 11294444. [ABS]
25. Howard DV, Howard JH Jr. 2001. When it does hurt to try: adult age differences in the effects of instructions on implicit pattern learning. Psychonomic Bulletin and Review 8(4):798-805. DOI 10.3758/BF03196220. PMID 11848602. [ABS]
26. Kal E, Winters M, van der Kamp J, Houdijk H, Groet E, van Bennekom C, Scherder E. 2016. Is implicit motor learning preserved after stroke? A systematic review with meta-analysis. PLoS ONE 11(12):e0166376. DOI 10.1371/journal.pone.0166376. PMID 27992442. PMC5161313. [FT: Abstract, Results 3.4.1 and 3.4.2, Discussion]
27. Kalra PB, Gabrieli JDE, Finn AS. 2019. Evidence of stable individual differences in implicit learning. Cognition 190:199-211. DOI 10.1016/j.cognition.2019.05.007. PMID 31103837. [ABS; the 0.38 as reported in Oliveira et al. 2024]
28. Kantak SS, Winstein CJ. 2012. Learning-performance distinction and memory processes for motor skills: a focused review and perspective. Behavioural Brain Research 228(1):219-231. DOI 10.1016/j.bbr.2011.11.028. PMID 22142953. [ABS]
29. Kinder A, Rolfs M, Kliegl R. 2008. Sequence learning at optimal stimulus-response mapping: evidence from a serial reaction time task. Quarterly Journal of Experimental Psychology 61(2):203-209. DOI 10.1080/17470210701557555. PMID 17886161. [ABS]
30. Koch I. 2007. Anticipatory response control in motor sequence learning: evidence from stimulus-response compatibility. Human Movement Science 26(2):257-274. DOI 10.1016/j.humov.2007.01.004. PMID 17346838. [ABS]
31. Leow LA, Nguyen A, Corti E, Marinovic W. 2025. Informative auditory cues enhance motor sequence learning. European Journal of Neuroscience 61(10):e70140. DOI 10.1111/ejn.70140. PMID 40399234. Preprint DOI 10.1101/2024.10.07.617139. [FT of the bioRxiv version of 1 April 2025: Methods, Studies 1 and 2 Results; the published version was not read]
32. Leow LA, Lum J, Johnson S, Corti E, Marinovic W. 2026. Musical training increases anticipatory responding and predictive control in sequence learning. Psychological Research 90(4):124. DOI 10.1007/s00426-026-02333-2. PMID 42390630. PMC13328134. [FT: Participants, Task, Data cleaning, Data analysis, Results, Discussion]
33. Lum JAG, Clark GM, Barhoun P, Hill AT, Hyde C, Wilson PH. 2023. Neural basis of implicit motor sequence learning: modulation of cortical power. Psychophysiology 60(2):e14179. DOI 10.1111/psyp.14179. PMID 36087042. PMC10078012. [FT: Method, behavioural Results]
34. Malassis R, Moscado L, Sackur J, Nemeth D. 2026. A non-verbal process dissociation procedure to disentangle explicit from implicit sequence learning. Neuroscience of Consciousness 2026(1):niag021. DOI 10.1093/nc/niag021. PMID 42266415. PMC13245152. [FT: Abstract, Introduction]
35. Meier B, Cock J. 2014. Offline consolidation in implicit sequence learning. Cortex 57:156-166. DOI 10.1016/j.cortex.2014.03.009. PMID 24861420. [ABS]
36. Nemeth D, Janacsek K, Londe Z, Ullman MT, Howard DV, Howard JH Jr. 2010. Sleep has no critical role in implicit motor sequence learning in young and old adults. Experimental Brain Research 201(2):351-358. DOI 10.1007/s00221-009-2024-x. PMID 19795111. [ABS]
37. Nissen MJ, Bullemer P. 1987. Attentional requirements of learning: evidence from performance measures. Cognitive Psychology 19(1):1-32. DOI 10.1016/0010-0285(87)90002-8. [META; design and awareness count as reported in Schwarb and Schumacher 2012]
38. Oliveira CM, Hayiou-Thomas ME, Henderson LM. 2023. The reliability of the serial reaction time task: meta-analysis of test-retest correlations. Royal Society Open Science 10(7):221542. DOI 10.1098/rsos.221542. PMID 37476512. PMC10354485. [FT: Results 3.1 to 3.4, Tables 1 to 4, Discussion]
39. Oliveira CM, Hayiou-Thomas ME, Henderson LM. 2024. Reliability of the serial reaction time task: if at first you don't succeed, try, try, try again. Quarterly Journal of Experimental Psychology 77(11):2256-2282. DOI 10.1177/17470218241232347. PMID 38311604. PMC11529135. [FT: Introduction, Experiment 1 Method, Tables 3 to 5, Discussion]
40. Press DZ, Casement MD, Pascual-Leone A, Robertson EM. 2005. The time course of off-line motor sequence learning. Cognitive Brain Research 25(1):375-378. DOI 10.1016/j.cogbrainres.2005.05.010. PMID 15990282. [ABS]
41. Pronk T, Molenaar D, Wiers RW, Murre J. 2022. Methods to split cognitive task data for estimating split-half reliability: a comprehensive review and systematic assessment. Psychonomic Bulletin and Review 29(1):44-54. DOI 10.3758/s13423-021-01948-3. PMID 34100223. PMC8858277. [FT: Introduction, Results, Discussion]
42. Reed J, Johnson P. 1994. Assessing implicit learning with indirect tests: determining what is learned about sequence structure. Journal of Experimental Psychology: Learning, Memory, and Cognition 20(3):585-594. DOI 10.1037/0278-7393.20.3.585. [META; design and argument as reported in Schwarb and Schumacher 2012]
43. Robertson EM. 2007. The serial reaction time task: implicit motor skill learning? Journal of Neuroscience 27(38):10073-10075. DOI 10.1523/JNEUROSCI.2747-07.2007. PMID 17881512. PMC6672677. [FT, PMC page]
44. Robertson EM, Pascual-Leone A, Press DZ. 2004. Awareness modifies the skill-learning benefits of sleep. Current Biology 14(3):208-212. DOI 10.1016/j.cub.2004.01.027. PMID 14761652. [ABS]
45. Runger D. 2012. How sequence learning creates explicit knowledge: the role of response-stimulus interval. Psychological Research 76(5):579-590. DOI 10.1007/s00426-011-0367-y. PMID 21786123. [ABS]
46. Runger D, Frensch PA. 2008. How incidental sequence learning creates reportable knowledge: the role of unexpected events. Journal of Experimental Psychology: Learning, Memory, and Cognition 34(5):1011-1026. DOI 10.1037/a0012942. PMID 18763888. [ABS]
47. Schwarb H, Schumacher EH. 2012. Generalized lessons about sequence learning from the study of the serial reaction time task. Advances in Cognitive Psychology 8(2):165-178. DOI 10.5709/acp-0113-1. PMID 22723815. PMC3376886. [FT: The Serial Reaction Time Task, Sequence structure, Measures of explicit knowledge, Measuring Sequence Learning, Stimulus-response rule hypothesis]
48. Shanks DR, Johnstone T. 1999. Evaluating the relationship between explicit and implicit knowledge in a sequential reaction time task. Journal of Experimental Psychology: Learning, Memory, and Cognition 25(6):1435-1451. DOI 10.1037/0278-7393.25.6.1435. PMID 10605830. [ABS]
49. Siegelman N, Frost R. 2015. Statistical learning as an individual ability: theoretical perspectives and empirical evidence. Journal of Memory and Language 81:105-120. DOI 10.1016/j.jml.2015.02.001. PMID 25821343. PMC4371530. [FT, PMC page: SRT task and reliability results]
50. Siegert RJ, Taylor KD, Weatherall M, Abernethy DA. 2006. Is implicit sequence learning impaired in Parkinson's disease? A meta-analysis. Neuropsychology 20(4):490-495. DOI 10.1037/0894-4105.20.4.490. PMID 16846267. [ABS]
51. Stark-Inbar A, Raza M, Taylor JA, Ivry RB. 2017. Individual differences in implicit motor learning: task specificity in sensorimotor adaptation and sequence learning. Journal of Neurophysiology 117(1):412-428. DOI 10.1152/jn.01141.2015. PMID 27832611. PMC5253399. [FT, PMC page: SRT Methods, Results, reliability and awareness]
52. Steel A, Silson EH, Stagg CJ, Baker CI. 2016. The impact of reward and punishment on skill learning depends on task demands. Scientific Reports 6:36056. DOI 10.1038/srep36056. PMID 27786302. PMC5081526. [FT: Results, SRTT Methods]
53. Stefaniak N, Willems S, Adam S, Meulemans T. 2008. What is the impact of the explicit knowledge of sequence regularities on both deterministic and probabilistic serial reaction time task performance? Memory and Cognition 36(7):1283-1298. DOI 10.3758/MC.36.7.1283. PMID 18927043. [ABS]
54. Stocker C, Sebald A, Hoffmann J. 2003. The influence of response-effect compatibility in a serial reaction time task. Quarterly Journal of Experimental Psychology A 56(4):685-703. DOI 10.1080/02724980244000585. PMID 12745836. [ABS]
55. Szucs-Bencze L, Fanuel L, Szabo N, Quentin R, Nemeth D, Vekony T. 2023. Manipulating the rapid consolidation periods in a learning task affects general skills more than statistical learning and changes the dynamics of learning. eNeuro 10(2):ENEURO.0228-22.2022. DOI 10.1523/ENEURO.0228-22.2022. PMID 36792360. PMC9961365. [FT: Abstract, Participants, Methods (exclusions, PDP)]
56. Trofimova O, Mottaz A, Allaman L, Chauvigne LAS, Guggisberg AG. 2020. The "implicit" serial reaction time task induces rapid and temporary adaptation rather than implicit motor learning. Neurobiology of Learning and Memory 175:107297. DOI 10.1016/j.nlm.2020.107297. PMID 32822865. [FT: published version in the Archive ouverte UNIGE; Methods, Tables 1 and 2, Results 3.1 to 3.5, Discussion]
57. Vadillo MA, Konstantinidis E, Shanks DR. 2016. Underpowered samples, false negatives, and unconscious learning. Psychonomic Bulletin and Review 23(1):87-102. DOI 10.3758/s13423-015-0892-6. PMID 26122896. PMC4742512. [FT: Results, effect sizes and power]
58. Vadillo MA, Malejka S, Lee DYH, Dienes Z, Shanks DR. 2022. Raising awareness about measurement error in research on unconscious mental processes. Psychonomic Bulletin and Review 29(1):21-43. DOI 10.3758/s13423-021-01923-y. PMID 34131891. [FT: author's version, PsyArXiv DOI 10.31234/osf.io/5xrf4; Abstract, reliability section and Table 1 text]
59. Vaquero JMM, Jimenez L, Lupianez J. 2006. The problem of reversals in assessing implicit sequence learning with serial reaction time tasks. Experimental Brain Research 175(1):97-109. DOI 10.1007/s00221-006-0523-6. PMID 16724176. [ABS]
60. West G, Vadillo MA, Shanks DR, Hulme C. 2018. The procedural learning deficit hypothesis of language learning disorders: we see some problems. Developmental Science 21(2):e12552. DOI 10.1111/desc.12552. PMID 28256101. PMC5888158. [FT: SRT method, Table 1, Reliabilities]
61. West G, Shanks DR, Hulme C. 2021. Sustained attention, not procedural learning, is a predictor of reading, language and arithmetic skills in children. Scientific Studies of Reading 25(1):47-63. DOI 10.1080/10888438.2020.1750618. [META; values as reported in Oliveira et al. 2023 and 2024]
62. Wilkinson L, Shanks DR. 2004. Intentional control and implicit sequence learning. Journal of Experimental Psychology: Learning, Memory, and Cognition 30(2):354-369. DOI 10.1037/0278-7393.30.2.354. PMID 14979810. [ABS]
63. Willingham DB, Greenberg AR, Thomas RC. 1997. Response-to-stimulus interval does not affect implicit motor sequence learning, but does affect performance. Memory and Cognition 25(4):534-542. DOI 10.3758/BF03201128. PMID 9259630. [ABS]

Counts: 63 sources; 31 FT (11 of them read from the PMC article page, a repository copy, the authors' version or the preprint), 28 ABS, 4 META. Of the 59 sources whose own text supplied a number or finding (FT plus ABS), 31 are FT. The sources behind P1's expected size, the reliability values, the awareness measures and the cue findings are all FT; the timing of offline gains rests on abstracts (Robertson et al. 2004; Press et al. 2005; Meier and Cock 2014; Nemeth et al. 2010) beside Trofimova et al.'s full text, and the other ABS entries are supporting or opposing results named beside FT ones. Each META source with content above was read through a named FT secondary source; Barr et al. is a method reference.

Not re-read here and left as the code and design cite them: Shin and Ivry 2002, O'Reilly et al. 2008, Stephan et al. 2009, Savion-Lemieux and Penhune 2005, Wulf and Lewthwaite 2016, Bonstrup et al. 2019, Buch et al. 2021, Japikse et al. 2003.

### Simulation assumptions (for Sections 1, 2 and 4)

- Block: the battery layout from the code (W12, R32, then seven 36-trial takes, probes at takes 5 and 7); RT = person mean (normal, 350 ms, SD 50) + practice trend (-3 ms per take) - learned benefit on trained takes + trial noise (normal SD 45, 55 or 75 ms plus exponential tau 25, 30 or 40 ms, total SD about 51, 63 or 85 ms, bracketing the pilot's within-take SDs of 39 to 75 ms); errors at 6 percent per trial, lower on trained takes by a person-level drop (mean 0 to 4 points, SD 1.5); the mode's hygiene (first 12 or 2 trials out, misses out, under 100 ms out, over mean + 2.5 SD out) and the mode's score.
- True learning: person-level benefit with cohort mean 0 to 40 ms and SD 10, 15 or 20 ms (the SD bracket follows from Stark-Inbar et al.'s observed SDs of 22.5 and 23.6 ms minus their block noise, arithmetic), 20 percent larger at probe 2. P1 and P3 decided by the notebook's rule (mean above zero, two-sided 95 percent t interval clear of zero, one-sided Wilcoxon below 0.05 or 0.0056); 1,000 or 2,000 cohorts per cell.
- Split-half: odd against even trials within each take, Spearman-Brown corrected. Retest: a second block with true learning correlated 1.0 or 0.5 with the first. P2: true gain +10 ms, stability 0.5.
- Material: full enumeration of 12-item SOC cycles and the shipped generator's logic (copied from `pattern.py` `participant_seed`, `generate_soc`, `build_sequences`) run for codes P01 to P99.
- Awareness chance levels: 20,000 random generations without immediate repeats against P01's trained cycle; partial knowledge as following the trained successor with probability 0.3, 0.5 or 0.8. Intrusion power: binomial counts of 20, 40 or 80 pooled probe errors against 1/3.
