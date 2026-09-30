# Force Pilot mode: deep research audit

1 October 2026. Scope: the study battery's Force Pilot step, `app/finger_rehab/game/modes/force_pilot.py` (mode key `force_pilot`), the force view and max-press probe in `app/finger_rehab/game/force_stream.py`, the percent scale in `app/finger_rehab/hardware/calibration_profile.py`, the screen in `app/finger_rehab/ui/force_pilot_screen.py`, the config, and the notebook analysis (`analysis/session_analysis.ipynb`, cell 2). The Parkinson's notes (`force-pilot-parkinsons.md`, `force-pilot-pd-review.md`, `force-control.md`) were not redone: their load-bearing claims were re-checked only where they bear on the healthy study.

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the assumptions at the end of Section 7; "(pilot)" is the development team's own Force Pilot blocks under `sessions/`, which describe the rig and two developers, not participants; "(code)" and "(design doc)" are values read in the repository. Line numbers refer to the working tree as read on 1 October 2026 (HEAD 6183cf7); notebook line numbers are lines of cell 2's source. The design doc and the notebook changed on the same day for other modes (nothing in Force Pilot's checks), so every reference also names the section or function.

---

## 1. What the mode does now

### 1.1 The block under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Place in the sitting | Order A steps 4 (after the 60 s stretch) and 11; order B steps 1 and 9 | one hand (right), both passes | `default.yaml` 1961-1995 |
| Battery form | One climb of the fixed ladder, 12 runs | `passes: 1` (the same as the default) | `default.yaml` 2016-2017, 1308 |
| Block start | GET READY countdown, no instruction text | 3.0 s | `default.yaml` 599; `force_pilot_screen.py` 846-873 |
| Music | A track from the shuffled menu playlist at full music volume, not logged per block | on | `default.yaml` 1374-1379; `audio/block_music.py` 84-85, 127-130 |
| Probe (pass 1 only) | Per finger, index to little: a 1.2 s gap with a re-tare, then three presses; an attempt opens above 30 counts, closes below the larger of 30 counts and 20 percent of its own peak, must last 0.15 s, with 0.3 s quiet between; the median peak is kept | 3 presses, floor 30 counts | `force_pilot.py` 1238-1325; `force_stream.py` 246-337; `default.yaml` 1351-1352 |
| Probe screen text | "Press as hard as you can, then let go and rest." and "Every target in this game is a percentage of what you show here." | | `force_pilot_screen.py` 345-353 |
| Probe safeguards | No attempt banked for 25 s ends the block (offered again); a max under 150 counts (5 x the floor) logs `max_press_low` and continues | | `force_pilot.py` 1257, 1263, 1288-1313, 1876-1903 |
| Probe reuse | A stored max from the same login under 6 h old is reused, so pass 2 plays on pass 1's max | 21,600 s | `force_stream.py` 340-387; `default.yaml` 1353; `engine.record_max_press` 3730 |
| Between runs | One 1.8 s card: last run's time in corridor, rings and "mean distance from the line", the next wave's number, name, coach line, a small preview of the whole run, the finger chip and "Keep your line inside the band." The finger about to fly is re-tared as the card opens unless it just flew | 1.8 s | `force_pilot.py` 1388-1414; `force_pilot_screen.py` 413-529; `default.yaml` 1359 |
| Rest | One skippable rest after level 6 | 15 s | `force_pilot.py` 978-991, 1416-1431; `default.yaml` 1360 |
| The run | The band scrolls at 120 px/s past a marker at x = 300 on a 1280 x 800 canvas: 8.2 s visible ahead, 2.5 s of trace behind (arithmetic). 0 to 40 percent of max fills 440 px, 11 px per 1 percent of max (arithmetic). The scrolling band has no centreline; rings sit on the centreline every 1.5 s from 2.0 s | gain 1.0 | `force_pilot_screen.py` 108-118, 576-644, 734-755; `force_pilot.py` 883, 1377-1386; `default.yaml` 1319, 1337, 1341-1342 |
| Out of the band | Marker keeps its colour; a LIFT or EASE tag names the direction. The exit buzz rides `cue.buzz_after`, which is off | | `force_pilot_screen.py` 794-809; `feedback_bank.py` 278-279; `default.yaml` 435 |
| Game score | Time in corridor (TIC), MAE, ramp press and release MAE (walk-in ramps out), section MAE, stalls, rings; Great at TIC 0.8, Good at 0.5; 2 points a ring | | `force_pilot.py` 879-880, 1579-1635, 1714-1723 |
| Dropouts and pauses | A sample older than 0.25 s pauses scoring; a run covered under half its plan is voided and replayed up to twice; a pause restarts the run on its card zero | | `force_pilot.py` 876, 1540-1577, 1702-1705, 1804-1870, 1160-1195 |
| Block length | Measured with a model participant | 3.54 min | design doc Section 2.3 (lines 1240, 1248) |

### 1.2 The ladder: what each wave asks (arithmetic from `level_sections`, `force_pilot.py` 452-531, and `LADDER`, 376-393)

| Level | Wave | Finger | Shape | Half-width (% of max) | Run (s) | Target range | Target SD | RMS target velocity (%/s) | Still finger: best TIC | Still finger: MAE | Lag-only MAE at 200 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Slow breath | index | 0.15 Hz sine, amplitude 6 | 8 | 14.8 | 8 to 20 | 4.41 | 3.79 | 1.00 | 3.99 | 0.65 |
| 2 | Tide | middle | 5 %/s ramp to 28, 3 s hold, ramp down | 8 | 13.5 | 8 to 28 | 7.77 | 3.85 | 0.70 | 7.03 | 0.59 |
| 3 | Swell | ring | 0.2 Hz sine, amplitude 9 | 8 | 16.0 | 8 to 26 | 6.54 | 7.74 | 0.80 | 5.90 | 1.35 |
| 4 | Stairs | little | six 2.2 s treads, 0.6 s grace after each edge | 6 | 14.7 | 8 to 26 | 6.17 | steps | 0.86 | 5.14 | 0 (inside grace) |
| 5 | Hills | index | 5 %/s ramps up and down, twice | 6 | 13.8 | 8 to 24 | 4.91 | 4.81 | 0.77 | 4.27 | 0.90 |
| 6 | Beach waves | middle | 0.333 Hz sine, amplitude 7 | 6 | 13.0 | 8 to 22 | 5.11 | 9.96 | 0.77 | 4.62 | 1.71 |
| 7 | Heartbeat | ring | four 2 s raised-cosine pulses 10 to 25, 1 s rests | 5 | 13.5 | 10 to 25 | 5.50 | 12.82 | 0.77 | 4.39 | 1.76 |
| 8 | Dunes | little | 4 %/s up, 12 %/s down, twice | 5 | 14.0 | 8 to 26 | 5.75 | 6.41 | 0.62 | 5.04 | 1.00 |
| 9 | Chop | middle | 0.15 + 0.45 Hz (3:1) | 5 | 14.3 | 8 to 26 | 5.12 | 6.95 | 0.73 | 3.82 | 1.12 |
| 10 | Open ocean | ring | 0.12, 0.29, 0.47 Hz, fixed phases | 4 | 15.0 | 8 to 30.7 | 5.39 | 8.56 | 0.54 | 4.49 | 1.38 |
| 11 | Storm | index | eight components 0.08 to 0.50 Hz, amplitude as 1/f, fixed phases | 4 | 15.0 | 8 to 27.7 | 4.09 | 4.70 | 0.73 | 3.28 | 0.74 |
| 12 | Uncharted | index | Storm's statistics, phases redrawn per block | 4 | 15.0 | varies | 2.90 to 4.07 (5th to 95th percentile over 2,000 draws, oscillation only) | 4.70 | 0.63 to 0.83 | about 3.3 | 0.60 to 0.82 |

"Still finger" is a force held at the single best constant level for the whole run; "lag-only" is the target shifted 200 ms against itself. Rank correlations with level number (arithmetic): corridor half-width -0.97, still-finger MAE -0.61, target SD -0.49, RMS target velocity +0.20 (Stairs out), lag-only MAE +0.30. The 1/f amplitudes give every Storm component the same velocity amplitude (2 x pi x f x a, about 1.9 %/s each; arithmetic), so the eight-component storm moves slower overall than Swell, Beach waves, Heartbeat, Chop or Open ocean. The top frequency rises up the ladder; the quantities that drive tracking error do not.

### 1.3 The percent scale

- Force on screen = (smoothed counts - frozen reference) / probed max x 100 (`force_stream.py` 197-219; `calibration_profile.py` 294-305). Smoothing is the detector's value EMA, alpha 0.35 at 200 Hz (`default.yaml` 227): time constant 11.6 ms, low-frequency delay 9.3 ms, -3 dB near 14 Hz (arithmetic).
- Research numbers come from `raw.csv` (unsmoothed), zeroed at the logged `ref_counts` (`force_pilot.py` 1494-1497), resampled onto a uniform grid (notebook `uniform_grid`, 15796).
- Pads: SingleTact CS8-10N, 512 counts per 10 N (`default.yaml` 214-216; `force_units.txt`).

### 1.4 Logging and block_stats

One trial row per run with the whole section list in `waveform_params` (`params_from_level`, 544-584), `segment_times`, `ref_counts`, and a stimulus string with the game's TIC, MAE, press and release MAE, rings, stalls and scored time (1737-1746). `block_stats` (1907-2029) reports per lane, per level and per hand means, section MAE, the ladder record, `no_signal_runs` and skips.

### 1.5 Registered checks and the notebook

- F1 (design doc 767-782): per-person Spearman rho of level MAE against level number, cohort one-sided Wilcoxon above zero with a median above zero (`_ladder_bandwidth_row`, 24003; in-session form in `sec_force_pilot_checks`, 27873-27898).
- F2 (783-792): cohort median of each hand's mean lag on the non-periodic waves (runs with r at the lag of 0.35 or more) inside 100 to 300 ms, and the bootstrap interval of the median inside the same band, or the row reads "direction only" (`_mean_check`, called at 24759; `lag_np_ms` from `_cohort_force_pilot`, 21115).
- F3 (793-803): two one-sided tests, 90 percent interval of release minus press MAE inside plus or minus 2 percent of max (`COHORT_F3_MARGIN_PCT`, 20008; row at 24765-24799). Press and release read the symmetric shapes: Tide, Hills, every sine and multisine, Heartbeat's pulses (`fp_pd_measures`, 16454-16501; `fp_section_roles`, 16111).
- F4 (804-814): pooled share of pass 1 runs with TIC at or above 0.8, above 0.5; per-level shares in the detail text only (24801-24830).
- F5 and F6 (MODE_LIT, 25936-25946): exploratory; F6 is Storm against Uncharted MAE on the latest play, from the second play on (27988-28018).
- T2 and T3 (design doc 1999-2000): ICC(2,1) of the hand-level mean MAE and TIC, pass 1 against pass 2, predicted "moderate to good (0.5 to 0.9)".
- W6 dropped (2127-2142): level and run index correlate at r = 0.9974 in a one-climb block.
- `sec_force_ladder` (17554): per-level tables, level rho on play 1, learning per play, Storm against Uncharted with a phase-redraw noise floor (17757), and a fatigue check of levels 4 to 6 against 7 to 9 (17783).
- `sec_force_pilot_pd` (28474) and `FP_PD_SPECS` (28068): the Parkinson's-linked exploratory measures.

### 1.6 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| The twelve waves run slowest to fastest, so a level number is a bandwidth (F1) | design doc 767-782; notebook 24007-24011, 24730-24736; `force_pilot.py` 85-89 | "Kurillo et al 2005, Clinical Biomechanics 20(10):1071-1080" (MODE_LIT 25909-25915); design doc also Kurillo 2005 and Lodha 2013 | The cited paper does not exist: pages 1064-1071 and 1072-1078 of that issue are other papers [META, Crossref]. Kurillo 2004 (Clin Biomech 19(10):1014-1021) and Kurillo 2005 (Technol Health Care) do not test bandwidth [ABS]. Velocity rises only weakly with level (Section 1.2, arithmetic); pilot rho was negative in all three blocks (Q1) |
| Lag of 100 to 300 ms on non-periodic waves (F2) | design doc 783-792; `fp_lag_class` 16165-16171 | Brewer 2009 (r floor); Pradhan 2010 | The band belongs to targets shown without preview: Brewer and Pradhan's pseudorandom target had none [FT]. With 8 s shown ahead, near-zero or negative lags are expected (Q2) |
| Operator delay on unpredictable signals 250 to 350 ms | `force_pilot.py` 93-97 | McRuer and Jex 1967 via Drop et al 2016 | Verified in Drop 2016 [FT], for non-harmonic sums of sines on a pursuit display without preview, aircraft pitch dynamics, six trained subjects; the feedforward delay fell to zero for harmonic targets |
| Visual corrections about once a second | `force_pilot.py` 90-93 | Slifkin, Vaillancourt and Newell 2000 | Verified [ABS], for 15 s constant-force holds |
| Predictable sines can be followed far faster than irregular targets | `force_pilot.py` 97-101 | Cathers et al 1996 | Verified [ABS]; the usual visual tracking limit is about 2 Hz |
| Multisines are coloured-noise targets | `force_pilot.py` 103-107 | Sosnoff and Newell 2008 | Consistent [ABS] |
| Storm against Uncharted separates learning these waves from pad familiarity, as Yang 2017 detected | `force_pilot.py` 108-119; MODE_LIT F6 | Yang et al 2017; Wulf and Schmidt 1997 | Yang detected it with a correlation measure over three days and many repetitions; RMSE showed no segment effect [FT]. A repeated segment can win because it is easier (Chambaron et al 2006 [ABS]) (Q11) |
| Massed practice with short rests is what the literature uses | `force_pilot.py` 142-150 | Lee and Genovese 1988 | Misread: the meta-analysis found massed practice depresses performance and learning [ABS]; for continuous tasks distributed practice helped (Lee and Genovese 1989 [ABS]) |
| Visual gain moves stroke tracking error by an order of magnitude | `force_pilot.py` 33-35 | Archer 2017 | The stroke minus control gap fell from about 21 to 3 percent MVC across 0.039, 0.39 and 2.39 degrees, about sevenfold [FT] |
| Parkinson's disproportionately impairs release in 0.2 Hz sine tracking | `force_pilot.py` 38-41; design doc F3 | Davidson 2026 | Verified with a qualifier: the release effect appeared in time within 5 percent of target (group x phase p < 0.01), not in RRMSE (no interaction) [FT] |
| SingleTact drift "2 percent a minute at half load" | `force_pilot.py` 187-188; design doc 2279-2280 | spec sheet V8.0 | The datasheet gives 2 percent in 1 min and 4 percent in 10 min at 50 percent of full-scale load (V7.4 [FT]): a decelerating creep, not a rate |
| Median of two or three attempts follows standard MVC practice | `force_stream.py` 25-28 | none | Practice varies: highest of three with 1 to 2 min rest (Davidson [FT]); highest trial, repeated until two agree within 5 percent, with encouragement (Keenan and Massey [FT]); mean of three peaks (Lee and Kang [FT]) (Q8) |
| 0 to 40 percent of max keeps runs free of strength fatigue | `force_pilot.py` 44-48; `default.yaml` 1315-1319 | Lodha 2013; Camacho-Villa 2025 | Supported and conservative: the pilot maxima were 4 to 16 percent of a typical index pressing MVC (Q8, Q12) |
| Force variability structure explains about 80 percent (Lodha) | `force_pilot.py` 10-17 | Lodha 2013 | Verified [FT]: R2 0.82 (adjusted 0.80) from power at 0.28 and 0.63 Hz, stroke and control holds |
| T2 and T3 moderate to good | design doc 1999-2000 | none | Within-day force pursuit ICCs 0.87 and 0.95, between days 0.33 to 0.76 (Nagasawa et al 2003 [ABS]) (Q10) |
| F3 margin of plus or minus 2 percent of max | design doc 797-799 | none | No smallest effect of interest is justified (Lakens et al 2018 [FT]) (Q3) |

Also cited for this mode and not re-read here: Pennati 2020, Taud 2021, Naik 2011 (abstract checked: rates 5, 10, 20 percent of max per second), Russo 2017, Vaillancourt 2007, Boyd and Winstein 2004, Chung 2023, Davidson 2025, Camacho-Villa 2025.

### 1.7 Pilot blocks on disk (rig check only)

Three ladder blocks from two developers (23 and 25 September 2026): 22 runs, 19 active (levels 10 to 12 of one block were flown with the finger idle and are excluded as the notebook does). Offline re-score with a zero taken at card open (these runs predate `ref_counts`); it matched the game's own MAE within 0.15 percent of max on 16 of 19 active runs and differed by 0.23, 0.32 and 0.56 on a Stairs, a Chop and a Dunes run (pilot):

- MAE 2.01 to 4.01 percent of max (median 2.78); RMSE 2.76 to 10.57; TIC 0.83 to 1.00 (median 0.92); signed error median -0.96 (range -2.67 to +1.24), mostly below the target.
- Within-block Spearman rho of MAE against level: -0.20 (levels 1 to 4), -0.27 (1 to 9), -0.31 (1 to 6); on the game's own MAE -0.20, -0.44 and -0.03.
- Sine gain (least-squares fit, first second skipped) on the eight single-sine runs: 0.48 to 0.90, median 0.66.
- Cross-correlation lag on the periodic waves: -150 to +255 ms, six of ten negative; Tide +125, +240 and +590 ms; Stairs -245 to +240 ms.
- Tide press against release MAE: 1.76 and 2.02, 4.27 and 1.07, 6.25 and 2.52; signed error on the press ramp -0.53, -3.55 and -5.53.
- Stairs: in the block that anticipated the steps (lag -245 ms), MAE in the 0.3 s before each edge was 6.00 against 3.01 elsewhere; 2.16 against 3.36 and 2.60 against 2.63 in the other two.
- Probe: maxima 73 to 272 counts (1.4 to 5.3 N at 51.2 counts per N; the Parkinson's review found 73 to 311 counts, 1.4 to 6.1 N, over all Force Pilot sessions). The three presses behind each median spread by 1 to 55 counts (CV about 0.3 to 15 percent; peaks recovered from `raw.csv` against each window's 10th percentile, so approximate). `max_press_low` fired on 8 of 12 finger probes across the three blocks that probed (P669 on 23 September, P673 on 25 September, a test block on 2 September). P669's maxima were 46, 19 and 24 counts above the light calibration press gap on the index, middle and ring fingers, and 3 counts below it on the little finger.

---

## 2. Research questions and findings

### Q1. Does tracking error rise up the ladder? (F1)

- Frequency at fixed amplitude. Twelve young adults tracking a 15 percent MVC sine with index abduction had more trajectory error and variability at 1 Hz than at 0.5 Hz (Park, Kim, Yacoubi and Christou 2019 [ABS]). Visual tracking is typically limited to about 2 Hz, and sinusoids can be followed at higher frequencies than irregular targets because the rhythm can be generated internally (Cathers et al 1996 [ABS]).
- Predictability. With sums of two to four sines on a pursuit display and no preview, six trained subjects tracked harmonic targets better than non-harmonic ones of similar frequency content, and performance fell as components were added, less so for harmonic signals; the feedforward delay went to zero for harmonic targets and was 250 to 350 ms for non-harmonic ones, and the feedback delay was 300 to 320 ms in every condition (Drop et al 2016, Sections 4 and 5, Figures 7 and 8 [FT]). Every condition still used feedforward. Tracking lag fell below 20 ms on repeated patterns (Day et al 1984 [ABS]).
- Band width. In 25 young women holding 10 or 40 percent MVC grip for 30 s, a band of plus or minus 5 percent of target against plus or minus 10 percent lowered RMSE and CV for the non-dominant hand at 40 percent MVC; the dominant hand's RMSE differed only by force level (0.9 against 4.7 N, mean and SE); both hands spent much longer outside the narrow band: 2.6 against 0.4 s per trial (non-dominant) (Lee and Kang 2020, Results [FT]).
- The ladder's own geometry (Section 1.2, arithmetic): half-width falls 8 to 4 percent of max (rho -0.97 with level), target SD falls (rho -0.49), RMS target velocity barely rises (rho +0.20), and the storm levels move slower than five of the lower levels. A lag-only error model gives a rho of +0.30; a band-keeping error that scales with the corridor or with target SD gives a negative rho.
- The design's F1 sources do not test bandwidth: Kurillo 2004 compared ramp and sine tracking in five grips across patients and 9 healthy subjects; Kurillo 2005 reported age-group differences in 32 healthy subjects [ABS both].
- Pilot: rho of MAE on level was negative in all three blocks (-0.20 to -0.31; Section 1.7).
- Simulation (10 people, 400 cohorts per scenario, Section 7): F1 passed in 0.00 of cohorts when people keep inside the band and use the preview (median rho -0.27), 0.00 with a 4 percent per run time-on-task drift added (median rho -0.16), 0.08 when people track the line (median rho +0.04), and 0.47 only if people ignore the preview on the multisines (lag 220 ms; median rho +0.16).

Bearing. The level-number rho confounds bandwidth with corridor width, target amplitude, finger and time on task, and the one axis the literature supports cleanly, predictability, is weakened by the 8 s preview (Q7). F1 as registered is more likely to fail than pass for a healthy hand. A width-free contrast of non-periodic against periodic waves (force-target correlation, or RMSE over the target's own SD) passed in 0.84 to 1.00 of cohorts under line tracking or no preview use, but only 0.02 to 0.18 under band keeping (simulation), so the instruction and display decide whether any form of F1 can work (Q5).

### Q2. What lag should a healthy hand show, and how is it estimated? (F2)

- Estimation. Brewer 2009 took the lag that maximised the cross-covariance of force and target, bounded at 2 s (sine) and 5 s (pseudorandom), set to the bound when the covariance was under 0.35; the authors chose both values as the largest lag and smallest covariance at which a relationship could still be seen by eye. The sine had 12.5 s of preview and the pseudorandom target none (Brewer et al 2009, Methods [FT]). The notebook scores each lag as a Pearson r over the overlap, searches plus or minus 1.5 s, and keeps negative lags (`tracking_lag_ms`, 15830-15874). Davidson 2026 took phase from a least-squares sine fit [FT].
- Preview. Tracking improves with preview through a far-viewpoint response that cancels the human's own lags (van der El et al 2018, IEEE Trans Cybern [ABS]); with preview times from 0 to 2 s, adaptation stopped beyond about 0.6 s (single integrator) and 1.15 s (double integrator) (van der El et al 2018, IEEE THMS [ABS]). Force Pilot shows 8.2 s ahead (arithmetic).
- Healthy values with preview. In the young adults' least-squares fits at 0.2 Hz, with about 4 s of preview, the phase shift against the target was -0.50 percent (SD 0.96), with no group difference (Davidson et al 2026, Table 2 [FT]). Without preview the non-harmonic feedforward delay was 250 to 350 ms (Drop 2016 [FT]).
- The device. A perfect on-screen tracker would show raw force leading the scheduled target by about 19 ms: the marker lags the drawn band by the EMA's 9.3 ms plus a mean sample age near 10 ms on a board bursting every 20 ms (arithmetic from `default.yaml` 227 and the modes-review device table). Single-run lags resolve to about 10 ms (notebook floor note).
- Pilot: periodic-wave lags -150 to +255 ms, mostly negative (Section 1.7).
- Simulation: F2 passed in 0.00 to 0.01 of cohorts when the multisines are flown with the preview (median lag 67 to 73 ms), and in 0.80 only when people ignore the preview (median 227 ms).

Bearing. With 8 s of preview, 100 to 300 ms is the wrong expectation for this display. The design doc already says so in words (line 790: "even the non-periodic lag may sit under 100 ms; that is anticipation"), but the criterion still fails that case.

### Q3. Press against release in healthy adults, and the plus or minus 2 percent margin (F3)

- Release slightly better. Young adults, precision grip, 0.2 Hz sine between 10 and 30 percent MVC: RRMSE 0.42 (0.11) generation against 0.38 (0.09) release; time within 5 percent of target 46.98 (9.88) against 52.44 (8.83); pooled over groups release was 4 percent better (95 percent CI 0 to 8) (Davidson et al 2026, Table 2 and Results [FT]). Ramps 0 to 35 percent MVC in 3.3 s: RRMSE 0.47 (0.16) generation, 0.24 (0.07) hold, 0.39 (0.06) release; time within 5 percent 44.33, 75.36, 50.07 (Davidson et al 2024, Table 2 [FT]). Ankle tracking: RMSE larger during generation than release in young and older adults, except the random task in older adults (Ebisu et al 2022 [ABS]).
- Release worse. Ankle ramps at 10 percent MVC per s: force more variable while releasing, in young and older adults (Park et al 2016 [ABS]). Bimanual index flexion, trapezoid tracking, 17 young adults: less accurate and more variable in decrement (Patel, Zablocki and Lodha 2019 [ABS]). Stepwise elbow and knee force changes: relaxation errors greater than generation (Ohtaka and Fujiwara 2016, 2019 [ABS]). Davidson 2026 names this conflict and suggests the task and effector decide the direction [FT, Discussion].
- Different circuits. Controlled relaxation drew more right DLPFC and generation more M1 and caudate (Spraker et al 2009 [ABS]).
- What sets the difference on this rig. A lag gives equal and opposite errors on the two halves of a symmetric shape; a standing undershoot (the pilot's median signed error -0.96) adds to the press error and cancels part of the release error, so a biased tracker shows release better than press without any release skill (arithmetic). The pilot's Tide runs show it: press signed error -3.55 and -5.53, press MAE 4.27 and 6.25 against release 1.07 and 2.52 (pilot). Sensor hysteresis does not create a press-release difference in the sensor-unit MAE that F3 reads, because the participant closes the loop on the displayed pad value; it would matter only for claims about true force (Q9).
- The margin. At a press MAE near 2.5 percent of max, plus or minus 2 percent allows a release error up to 80 percent larger than press error (arithmetic). The ageing effect on ramps moved the release to generation RRMSE ratio from 0.83 (young) to 1.23 (older) (arithmetic from Davidson 2024 Table 2 [FT]). At n = 10 the plus or minus 2 percent test declares equivalence with a true release excess of 1.0 percent of max in 90 to 100 percent of cohorts (SD of the person-level difference 0.25 to 1.0), and with 1.4 percent in 54 to 100 percent; a plus or minus 1 percent margin passes 80 to 100 percent of the time at a true zero with SD up to 1.0 and 5 percent of the time at +1.0 (simulation). The simulated SD of the person-level difference was 0.20 to 0.25 percent of max, and F3 passed in 1.00 of cohorts in every scenario (simulation).
- Equivalence margins should be a smallest effect of interest fixed before the data, justified objectively or from related studies; a bare benchmark is the weakest justification (Lakens, Scheel and Isager 2018, section "Justifying the Smallest Effect Size of Interest" [FT]).

Bearing. F3 cannot fail for a plausible healthy hand; it is a feasibility check as it stands. The informative outputs are the ratio with its interval, the direction split by shape (Tide, Hills, sine halves, multisines, pulses) and the signed error, which separates a release skill from an undershoot.

### Q4. Time in corridor, rings and the corridor widths (F4, T3)

- A finger held still reaches TIC 1.00 on level 1, 0.86 on Stairs, 0.73 on Storm and 0.54 to 0.80 elsewhere (Section 1.2, arithmetic). The pilot's 19 active runs sat at 0.83 to 1.00 (pilot).
- The literature's band is relative and narrow: time within plus or minus 5 percent of the target force (Davidson 2024 and 2026 [FT]), which Davidson describes as more sensitive to small deviations than RRMSE. At Force Pilot's targets of 8 to 31 percent of max that band is 0.4 to 1.55 percent of max, so the corridor is 2.6 to 20 times wider (arithmetic). Young adults spent 44 to 52 percent of ramp and sine phases inside Davidson's band [FT].
- Rings test in-corridor state at 9 to 10 instants per run, so the ring share is TIC sampled with binomial noise, SD about 0.1 at TIC 0.9 (arithmetic).
- Simulation: F4 passed in every cohort of every scenario; mean TIC 0.93 to 0.99; T3's ICC had a lower 5th percentile (0.22 to 0.45) than T2's (0.57 to 0.59) because TIC crowds the ceiling.
- Stairs scores anticipation but not reaction: the 0.6 s grace covers only the time after each edge (`grace_windows`, 785-804), while a finger that leaves early is scored in the tread before (pilot: 6.00 against 3.01 percent of max in the anticipating block).

Bearing. TIC is a good game number and a poor measure of a healthy hand at these widths. F4 is a feasibility check. T3 will be the least informative reliability row.

### Q5. What the task asks for: the band, the instruction and the strategy

- Published tracking studies told people to follow or trace a visible target line as closely or accurately as they could (Davidson 2024 and 2026; Térémetz et al 2015; Carment et al 2018 [FT, Methods in each]).
- Force Pilot tells people "Keep your line inside the band." (`force_pilot_screen.py` 442), draws no centreline in the scrolling band (576-644), shows TIC as the large number (811-843) and pays rings for being anywhere inside the band (`force_pilot.py` 1625-1630). Only the between-run card mentions "mean distance from the line".
- Young adults undershot a 0.2 Hz sine by 16.57 percent (SD 4.09) when told to follow the line (Davidson 2026 [FT]). The pilot's sine gains were 0.48 to 0.90 (median 0.66) (pilot), and the Parkinson's notes (E5) already record that a player can stay inside the easy corridors while shrinking the wave.
- Band width changes behaviour, but modestly and not in every hand (Lee and Kang 2020 [FT], Q1).
- Continuous concurrent feedback improved performance during practice but degraded next-day retention (Schmidt and Wulf 1997 [ABS]); the trace-and-band display is concurrent feedback, so any pass 2 gain is performance, not retained learning.
- Simulation: line tracking gave MAE 1.42 and TIC 0.989; band keeping MAE 2.14 and TIC 0.948 (simulation). Under line tracking the width-free F1 contrast passed in 0.84 to 0.95 of cohorts; under band keeping in 0.02 to 0.05.

Bearing. MAE is measured against a line the participant cannot see and was not asked to follow. That is the root of the F1 and F2 problems, part of the F3 undershoot mechanism, and the reason the pilot's gain cannot be set against Davidson's 0.83.

### Q6. Visual gain and display geometry

- The size of the error on screen matters up to a point, and the point is expressed as a visual angle, not as gain or distance: force fluctuations changed up to about 1 degree and little above (Vaillancourt, Haibach and Newell 2006 [ABS]); small increases below 1 degree cut force error substantially and larger increases changed it little (Coombes et al 2010 [ABS]); Archer 2018 cites an asymptote near 0.5 degrees and used 0.039, 0.39 and 2.39 degrees [FT]. At the elbow and ankle, every gain effect sat in the three lowest levels (0.008 to 0.05 degrees), with visual gain defined from half the height of the force fluctuations at 762 mm (Prodoehl and Vaillancourt 2010, Methods, Figure 1 [FT]). Force SD fell from 0.09 N at 0.5 to 4 px/N to 0.06 N at 64 to 1,424 px/N in young adults at 2 and 10 percent MVC (Baweja et al 2010 [ABS]).
- On this rig: 11 logical px per 1 percent of max; with maxima of 1.4 to 6.1 N that is about 180 to 790 logical px per N, above Baweja's 64 px/N (arithmetic). On a 24 inch 1920 x 1080 screen (pygame SCALED fullscreen, scale 1.35) viewed at 60 cm, 1 percent of max is about 4.1 mm, about 0.39 degrees (arithmetic, assumed screen). The lab PC's screen is not recorded.
- The gain in px per N differs about fourfold between a weak and a strong presser because the display is in percent of max (arithmetic); both sit above the range where gain still moved variability.

Bearing. Gain 1.0 is not a limiting factor for healthy hands. The visual angle should be written down for the thesis.

### Q7. What the preview window does

- Preview benefit saturates by 0.6 to 1.15 s for integrator dynamics (van der El et al 2018 [ABS]); Davidson showed about 4 s ahead and 5 s behind [FT]; Brewer showed 12.5 s ahead for the sine and nothing for the pseudorandom target [FT]. Force Pilot shows 8.2 s ahead and 2.5 s behind, plus the whole run on the card before it (`_draw_wave_preview`, 480-529).
- Consequences: "unpredictable" in the docstring (90-102) and design doc means non-periodic, previewed; the lag criterion (Q2) and the Storm against Uncharted learning contrast (Q11) both assume a target the participant cannot see coming.

### Q8. The maximum-press probe

- What a maximum is elsewhere. Precision grip MVC: three trials, 1 to 2 min rest, highest kept; young adults 54.9 (9.2) N (Davidson 2026, Methods and Table 1 [FT]); median 57.68 N in Davidson 2024 [FT]. Index fingertip pressing in young adults: 37.38 (18.47) N, repeated until two trials fell within 5 percent, strong verbal encouragement, participants asked whether the effort was maximal, highest trial kept (Keenan and Massey 2012, Methods and Results [FT]). Grip MVC as the mean of three peaks (Lee and Kang 2020 [FT]); the mean of the 10 highest samples of three 6 s trials (Lodha 2013 [FT]). A discrete-peak MVC and a sustained 20 s MVC gave different force-variability functions in 32 young adults, mainly beyond about 65 percent MVC (Novak, Wilson and Newell 2021 [FT]).
- What the probe measured on the pilot: 1.4 to 6.1 N, 4 to 16 percent of Keenan's young index MVC (arithmetic). The targets of 8 to 31 percent of max are then about 0.1 to 1.9 N, roughly 0.3 to 5 percent of an index MVC (arithmetic), the range where force CV is highest and changes fastest (4.9 percent at 2 percent MVC, 1.4 percent at 15 percent MVC; Moritz et al 2005 [ABS]).
- The pad's limits. The 10 N part's output is calibrated to 511 counts at full scale; past full scale the output rises to 2 V and saturates, and over-pressure should stay under 3 times full scale (30 N) to avoid damage (SingleTact manual, Table 1 and Section 2.2 [FT]). A press of Keenan's mean index MVC would pass that limit; no pilot press came near it (pilot).
- Instructions disagree: the screen says "Press as hard as you can" (`force_pilot_screen.py` 346); the run sheet's recovery line says "as hard as is comfortable" (`run_sheet.md`, "If something goes wrong"); no RA line is given for Force Pilot.
- What a wrong maximum does (arithmetic model; assumptions in Section 7): tracking behaviour in percent units is unchanged, but the count noise and zero error scale as 1/max and the physiological noise rises as absolute force falls. For a person whose comfortable maximum is 1.5 N, a probe reading half of it raises RMS error from 4.08 to 5.91 percent of max; for 3 N from 3.38 to 4.08; for 6 N from 3.13 to 3.38. At a correct probe, a 1.5 N person carries RMS error 4.08 against 3.13 for a 6 N person with identical tracking.
- The max is shared by both passes (Q10), so a probe effect repeats in pass 2.

Bearing. The probe measures a brief maximal comfortable press on an 8 mm pad, not an MVC, and percent of max is a within-person, within-pad ratio. Its reproducibility within the probe (three peaks) is recoverable from the raw file and should be reported.

### Q9. The sensor: hysteresis, drift, creep, temperature, bandwidth, smoothing

- Specification (datasheet V7.4 [FT]): resolution under 0.2 percent of full scale; repeatability under 1.0 percent (1 sigma); linearity under 2.0 percent; hysteresis under 4.0 percent; drift 2 percent in 1 min and 4 percent in 10 min at 50 percent load; temperature sensitivity under 0.2 percent per degree C; response under 1 ms; I2C update up to 120 Hz. The manual adds that the converter runs at 140 to 4,000 Hz with a frame index for spotting duplicates, and that the load equation assumes load spread over the whole sensor head [FT].
- Independent tests. A 45 N, 15 mm SingleTact: hysteresis 0.93 to 1.3 percent of range at 1 N/s and 3.51 to 5.3 percent at 5 N/s; drift over 1 min 0.01 to 1.45 percent; 3.5 percent of full scale between room temperature and 40 degrees C; rise under 40 ms, settling under 65 ms; usable above 10 Hz but less accurate past 6 Hz (Armitage et al 2023, Results and Table 1 [FT]). The 10 N, 8 mm part: calibration linearity R2 0.909 bare to 0.979 with discs on both faces; sensitivity fell as contact temperature rose (R2 0.71); repeatability CV 57 percent under 1 kPa, 14.4 percent at 1 to 5 kPa, 5.0 at 5 to 9, 3.1 at 9 to 13, 2.3 at 13 to 17 kPa (22 degrees C); no drift trend over 5 h at 30 and 80 gf (Tang et al 2020, Tables 4 and 6, Figure 10 [FT]). 1 kPa on the 8 mm head is 0.05 N (arithmetic), so Force Pilot's base hold of 0.1 to 0.5 N sits at 2 to 10 kPa.
- What they do here (arithmetic). In closed loop the participant matches the displayed pad value, so hysteresis, creep and a slow gain change move the true force, not the pad-unit error that MAE, TIC and F3 read. The loop does feel the pad's dynamics, symmetric for press and release in a linear model. Temperature: at most 0.2 percent per degree, about 2 percent if a pad warms 10 degrees between the probe and pass 2, a 0.4 percent of max shift at a 20 percent target. Drift inside a 13 to 16 s run at these loads is under a count if creep scales with load (arithmetic from the datasheet's 2 percent in 1 min at half load). The EMA adds 9.3 ms to the display only. The research signal carries the pad noise (1.35 counts, the notebook's value, is 0.50 to 1.84 percent of the pilot maxima; arithmetic), which is where the sensor reaches MAE.

Bearing. The sensor limits absolute newtons and true-force claims, not pad-unit tracking error; its noise floor matters most for weak probes and the little finger (Q13).

### Q10. What reliability to expect for T2 and T3, and how many runs

- Grip force pursuit in 30 college students: trial-to-trial ICC 0.87 (bar display) and 0.95 (waveform); day-to-day 0.33 to 0.71 and 0.48 to 0.76; significant day-to-day improvement (Nagasawa, Demura and Nakada 2003 [ABS]). Quasi-random targets of mean 0.01 to 0.09 Hz one day apart: 0.37, 0.73, 0.57, 0.57, with improvement at one week (Nagasawa and Demura 2010 [ABS]). Handgrip tracking, 14 healthy adults, 20 min apart: acceptable ICCs and significant improvement (Carey et al 1988 [ABS]).
- Tracking error between days: 0.60 for a tablet line-tracking error in 34 adults, error falling from 81.6 to 72.3 px at session 2 (Rabah et al 2022, Table 2 [FT]); area between force and target 0.31 to 0.60 in older adults a week apart, against 0.77 to 0.91 for CV, with improvement at session 2 on every measure (Blomkvist et al 2018, Tables 2 and 3 [FT]).
- Spread between young people: FFM tracking error 4.44 (0.91) in 10 young adults, CV about 20 percent (Carment et al 2018, Table 2 [FT]); RRMSE 0.42 (0.11), CV about 26 percent (Davidson 2026 [FT]) (arithmetic).
- Arithmetic: with a between-person CV of 20 to 25 percent, a within-person run CV near 30 percent averaged over 12 runs (about 9 percent) and a pass-to-pass state change near 9 percent, ICC is about 0.71 to 0.79. If a single run carries 0.2, 0.3 or 0.4 of trait variance, the 12-run mean carries 0.75, 0.84 or 0.89 (Spearman-Brown).
- Simulation: T2 median 0.83 to 0.87 (5th percentile 0.57 to 0.59); T3 median 0.72 to 0.79 (5th percentile 0.22 to 0.45).
- The shared maximum adds between-person variance that repeats in pass 2 (Q8). In the simulation, where the max entered only through the pad-noise term, re-probing pass 2 with a 15 percent probe CV changed T2 by under 0.01; a zero error in counts or a larger physiological term would enlarge the effect.

Bearing. "Good" (0.75 to 0.9) is the likely centre for T2 within one session, with an interval at n = 10 spanning moderate to excellent; T3 sits lower and wider. A practice shift is expected and lowers ICC(2,1) against ICC(3,1).

### Q11. Practice between passes, learning in the block, and Storm against Uncharted

- Retest improvement is the rule in tracking: Carey 1988 (20 min), Nagasawa 2003 and 2010 (days), Blomkvist 2018 (7 days), Rabah 2022 (days) [ABS, ABS, FT, FT]. In a three-day continuous tracking study, RMSE fell across practice blocks for all segments (Yang et al 2017 [FT]).
- The repeated-segment design: participants track a target whose middle segment repeats while the outer segments are random; learning shows as a repeated-segment advantage. Chambaron et al 2006 failed to reproduce the advantage twice and found it only with Wulf and colleagues' own segment, which was easier to track in velocity and acceleration [ABS]. Yang et al 2017 (24 participants, three days, stylus tracking) found no segment effect on RMSE and detected waveform-specific learning with the cursor-target correlation [FT, Results]. Wulf and Schmidt 1997 is the original [META, paradigm as described by Yang].
- Here: Storm is fixed and Uncharted redraws its phases each block; each person flies each twice (one per pass), both with 8 s of preview and a whole-run preview on the card. Across 2,000 phase draws, Uncharted's target SD spans 2.90 to 4.07, its walk-in ramp 6 to 18 percent of max per s and its lag-only MAE 0.60 to 0.82; Storm's fixed phases sit at the 39th to 77th percentile of those distributions (arithmetic). The notebook already prints a phase-redraw floor of 0.132 percent of max (17748-17764).
- Massed practice depresses performance, and a rest brings some of it back (Lee and Genovese 1988 [ABS]); pass 2 follows a 3 min rest and other games, so part of any pass 2 gain is recovery from massed practice in pass 1.

Bearing. F6 on MAE after two exposures is noise-dominated and should be read on the force-target correlation, as descriptive. The pass 2 minus pass 1 shift is performance within a sitting.

### Q12. Massed practice, fatigue and rests at these forces

- The block holds about 173 s of tracking in about 3.5 min, with 1.8 s cards and one 15 s rest (arithmetic from Section 1.2 and the config). Lee and Genovese found massed practice depresses performance, with the benefit of distributed practice specific to continuous tasks (25 s against 0.5 s inter-trial intervals) [ABS, 1988 and 1989].
- Muscular fatigue is negligible at these absolute forces. The grip endurance model is ET = 33.55 x (MVC fraction)^-1.61 s (Frey Law and Avin 2010, Table 2 [FT]): about 230 s sustained at 30 percent MVC and 450 s at 20 percent (arithmetic), while Force Pilot's targets are near 0.3 to 5 percent of an index MVC and each finger flies two to four runs with rests between (arithmetic). Young adults reported fatigue of 36.2 (19.0) out of 100 after ten 32 s sine trials at 10 to 30 percent MVC (Davidson 2026 [FT]), a load well above this block's.
- The notebook's fatigue check compares levels 4 to 6 (half-width 6) with 7 to 9 (half-width 5), so corridor width and wave change with the rest (17773-17791).

### Q13. The finger table and the fixed order

- Middle and ring fingers move less independently than thumb, index and little; the dominant hand was not more independent (Häger-Ross and Schieber 2000 [ABS]).
- The little finger flies Stairs and Dunes and had the lowest pilot maxima (73 to 128 counts), so its pad noise is 1.1 to 1.8 percent of max against 0.5 percent for a 272-count index (arithmetic): levels 4 and 8 carry the highest noise floor.
- Level, finger and time on task are fixed together; the design already reports per (level, finger) and drops W6.

### Q14. Which Parkinson's and design claims survive, as far as they bear on the healthy study

- Release deficits: in Davidson 2026 the Parkinson's release effect is in time within 5 percent of target, not RRMSE; in Davidson 2024 the ageing release effect is in RRMSE on ramps [FT both]. F3 reads MAE, closer to RRMSE; `twr5_rise` and `twr5_fall` already exist in the notebook and are the measure nearer the published Parkinson's finding.
- Young-adult direction: release equal or slightly better in precision grip [FT], worse in several other effectors and tasks [ABS] (Q3). A healthy F3 result on this rig is a device norm, not evidence about Parkinson's.
- Swell is the nearest Force Pilot wave to Davidson's task but differs in finger (ring), preview (8.2 against about 4 s), corridor, length (15 against 32 s) and instruction, so its gain cannot be compared with the young adults' 16.57 percent undershoot without those caveats.
- Claims already corrected in the notes and holding: Taud 2021 cannot show training drives recovery; no Parkinson's force-tracking training trial exists (not re-checked here).

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Ladder order | fixed, levels 1 to 12, same for all (`force_pilot.py` 376-393, 970-977) | Needed for comparability; confounds level with time on task and finger (design doc; Q13) | Keep for this study; counterbalance after collection |
| Level heights | 8 to about 31 percent of max (code) | Inside the 10 to 35 percent MVC ranges of Davidson [FT] in construct only (Q8) | Keep |
| Top frequency | 0.5 Hz | Inside the visual tracking range (Cathers [ABS]) | Keep |
| Multisine amplitudes | 1/f, equal velocity per component (arithmetic) | Coloured-noise targets (Sosnoff and Newell [ABS]); low RMS velocity (4.7 %/s) | Keep; correct the bandwidth wording |
| Corridor half-widths | 8, 6, 5, 4 percent of max | A still finger reaches TIC 0.54 to 1.00 (arithmetic); band width moves time out of band strongly and accuracy a little (Lee and Kang [FT]) | Keep for the study; after collection, easy levels a still finger cannot fill |
| Centreline and instruction | band only; "Keep your line inside the band." | Published tasks: follow a visible line as closely as possible [FT]; pilot gain 0.48 to 0.90 (pilot) | Change (DESIGN-CHANGE, task) or reframe MAE |
| Preview | 8.2 s ahead, 2.5 s behind, whole run on the card | Benefit saturates by 0.6 to 1.15 s (van der El [ABS]); Davidson 4 s [FT] | Keep; change F2 and the "unpredictable" wording |
| Visual gain | 1.0; 11 px per percent of max; about 180 to 790 px per N | Above the range where gain still moves variability (Baweja [ABS]; Prodoehl [FT]) | Keep; record screen size and distance |
| Probe instruction | "Press as hard as you can" on screen; "as hard as is comfortable" on the run sheet | Pad damage limit 30 N (manual [FT]); index MVC 37 N (Keenan [FT]) | Change to one wording (DESIGN-CHANGE) |
| Probe method | median of three brief presses | Practice varies (highest, mean) [FT]; median rejects spikes | Keep; log the three peaks |
| Probe reuse | pass 2 reuses pass 1's max | Same scale in both passes; shared denominator | Keep; report 1/max against MAE |
| Low-max warning | under 150 counts | fired on 8 of 12 pilot probes (pilot) | Keep; count it in the notebook |
| Display smoothing | EMA 0.35, 9.3 ms (arithmetic) | Small against visuomotor delays | Keep |
| Stairs grace | 0.6 s after each edge only | Anticipation before the edge is scored (pilot) | Add a symmetric-window sensitivity row |
| Rings | every 1.5 s, in band at that instant | A sampled TIC (arithmetic) | Keep as a game layer |
| Score tiers | Great 0.8, Good 0.5 TIC | Feedback only | Keep |
| Card between runs | 1.8 s | Massed practice on a continuous task (Lee and Genovese [ABS]) | Keep for this study; lengthen after collection |
| Mid-ladder rest | 15 s after level 6 | | Keep |
| Music | random menu track, not logged | Uncontrolled presentation condition | Add logging |
| F1 | level rho above zero | Fails under preview use (simulation 0.00 to 0.08); pilot rho negative | Change (DESIGN-CHANGE) |
| F2 | median non-periodic lag within 100 to 300 ms | Fails under preview use (simulation 0.00 to 0.01) | Change (DESIGN-CHANGE) |
| F3 | TOST, plus or minus 2 percent of max | Passes even with a +1.0 percent true release excess (simulation) | Reclassify as feasibility or justify a ratio margin (DESIGN-CHANGE) |
| F4 | pooled share of runs at TIC 0.8 above 0.5 | Passes in every scenario; still finger 0.54 to 1.00 | Reclassify as feasibility; decide per level |
| F5 | Lodha split, within device | Stroke hold measure on a tracking residual | Keep exploratory |
| F6 | Storm against Uncharted MAE, latest play | MAE insensitive (Yang [FT]); phase-redraw spread (arithmetic) | Read on r_target; descriptive only |
| T2 | ICC(2,1) of hand MAE, moderate to good | Within-day 0.87 to 0.95 (Nagasawa [ABS]); simulation 0.83 to 0.87 | Keep; say good is the likely centre |
| T3 | ICC(2,1) of hand TIC, moderate to good | Ceiling; simulation 5th percentile 0.22 to 0.45 | Add width-free rows; consider replacing |
| W6 | dropped | Correct | Keep dropped |
| Lag estimator | Pearson cross-correlation, plus or minus 1.5 s, r floor 0.35 | Keeps negative lags; floor is a heuristic (Brewer [FT]) | Keep; read negative lags as anticipation |
| Idle rule | 95th percentile under 2 percent of max | Needed (pilot idle runs) | Keep |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

The author prefers the games to stay as programmed unless there is a clear reason. Two items below change what the participant sees or is told (4 and 5b); both are flagged, and each has a no-task-change fallback.

1. **F1: stop reading the level number as a bandwidth.** SAFE-NOW part: correct the wording in `force_pilot.py` (THE LADDER, 85-89), design doc Section 1.8 F1 (767-782, including "Kurillo 2005 varied target shape for exactly this reason"), the notebook comments at 24003-24011, 24720-24736 and 27871-27880, and the `sec_force_ladder` docstring. Replace the MODE_LIT F1 source (25909-25915), "Kurillo et al 2005, Clinical Biomechanics 20(10):1071-1080", which does not exist, with sources that test the effect (Park et al 2019, Hum Mov Sci 64:89-100; Drop et al 2016, IFAC-PapersOnLine 49(19):177-182). DESIGN-CHANGE part: F1 becomes a per-person width-free contrast, non-periodic waves (10, 11, 12) against periodic ones (1, 3, 6, 7, 9), on `r_target` (lower on non-periodic) or RMSE divided by the target's own SD (higher), one-sided Wilcoxon, with the level-number rho kept as a descriptive row beside the confounds. New helper beside `_ladder_bandwidth_row` (24003); the in-session form in `sec_force_pilot_checks`. State in the design doc that under the band instruction even this form passes rarely (simulation 0.02 to 0.18), so F1 depends on recommendation 4. Evidence: arithmetic (Section 1.2), pilot (rho -0.20 to -0.31), simulation, Drop 2016 [FT], Lee and Kang 2020 [FT].

2. **F2: expect anticipation, test the class contrast.** DESIGN-CHANGE. New rule: the lag on the non-periodic waves exceeds the lag on the periodic waves (paired, one-sided Wilcoxon), with the absolute median reported against a device band of -150 to +300 ms and the -19 ms display offset stated (arithmetic). Files: design doc Section 1.8 F2 (783-792); the `_mean_check` call at 24759 replaced by a paired class row reading `lag_np_ms` and `pd_lag_periodic_ms` (already emitted by `_cohort_force_pilot`, 21115-21145); `sec_force_pilot_checks` F2 (27901-27923); MODE_LIT F2 (25916-25922); the `fp_lag_class` docstring (16165-16171). Evidence: Brewer 2009 [FT] (no preview on the pseudorandom target), Drop 2016 [FT], van der El 2018 [ABS], Davidson 2026 [FT], Day 1984 [ABS], pilot, simulation.

3. **F3 and F4: call them feasibility checks and add the numbers that inform.** DESIGN-CHANGE for the labels and criteria; SAFE-NOW for the added rows. Add F3 and F4 to the design doc's feasibility list beside Rh2, B4, A5 and a noise-level C1 (Section 4.6, feasibility paragraph, 2074-2081). Report per person, in `_cohort_force_pilot` and the in-session F3 block: the release to press MAE ratio and `release_rmse_ratio` (already per run in `fp_pd_measures`, 16480-16501) with intervals, `twr5_rise` against `twr5_fall`, `ce_rise` against `ce_fall`, and the difference split by shape (Tide, Hills, sine halves, multisines, Heartbeat pulses). F4: decide per level and print each level's still-finger TIC beside it (`_level_row` data and the cohort F4 row, 24801-24830). If F3 is to remain a test, replace plus or minus 2 percent of max with a ratio margin justified by related work, for example release over press between 0.83 and 1.20, and state its power; the ageing effect moved Davidson's ramp ratio from 0.83 to 1.23 [FT] (Lakens et al 2018 [FT]).

4. **Make the task a line-tracking task, or say plainly that it is not.** DESIGN-CHANGE, and a task change. Option A: draw a thin centreline through the scrolling band in `ForcePilotScreen._build_corridor` (576-644), and change "Keep your line inside the band." (`_draw_announce`, 442) to "Keep your line on the centre line; the band is how far you can drift."; the run sheet and design doc say the same. The published healthy tasks all ask for this (Davidson 2024, 2026; Térémetz 2015; Carment 2018 [FT]); in the simulation it turns the width-free F1 from 0.02 to 0.05 into 0.84 to 0.95 and moves TIC to the ceiling. Option B, no task change (SAFE-NOW): keep the game, and in the notebook and thesis describe MAE as distance from the centre of a band the participant was asked to stay inside, printed beside each level's still-finger MAE and a skill index 1 minus MAE over still-finger MAE; F1 then stays descriptive.

5. **The probe: log it fully, and give it one instruction.**
   a. SAFE-NOW (logging and analysis): add the three peaks to the `max_press_low` detail in `ForcePilotMode._probe_frame` (1297-1313) and to the `max_press` event written by `engine.record_max_press` (3730 onward); log a `max_press_near_full_scale` event when any peak comes within 10 percent of 511 counts above rest (the calibrated range; manual [FT]). Add a notebook probe chapter: the three peaks and their CV per finger (recoverable from `raw.csv` for blocks already recorded), each finger's max in newtons against the 37 N young index MVC of Keenan and Massey [FT], the count of `max_press_low` events, and each finger's pad noise as a percentage of its max.
   b. DESIGN-CHANGE (a change to what participants are told): one wording on the screen (`_draw_probe`, 346-353) and the run sheet, "Press as hard as is comfortable, then let go and rest." It matches what the probe measures (a pad-limited press of 1.4 to 6.1 N on the pilot), keeps strong participants away from the pad's 30 N limit, and removes the contradiction. Say in the thesis that percent of max is percent of a maximal comfortable press on an 8 mm pad.

6. **Correct the claims the evidence contradicts.** SAFE-NOW (text only).
   - `force_pilot.py` 142-150: Lee and Genovese 1988 found that massed practice depresses performance and learning; the 1.8 s cards are a massed schedule chosen for time, and the 15 s rest and pass 2 recover part of it.
   - `force_pilot.py` 187-188, design doc Section 4.8 h (2279-2280) and `force_units.txt` (drift paragraph): write the drift as 2 percent in 1 minute and 4 percent in 10 minutes at half load (datasheet V7.4), not 2 percent a minute.
   - `force_pilot.py` 112-117 and MODE_LIT F6 (25941-25946): Yang 2017 detected waveform-specific learning with the cursor-target correlation in stylus position tracking after three days of practice, not with RMSE, and a repeated segment can win by being easier (Chambaron 2006).
   - `force_pilot.py` 33-35: Archer's gain effect was a roughly sevenfold narrowing of the stroke-control gap, 21 to 3 percent MVC.
   - `force_stream.py` 25-28: MVC practice keeps the highest (Davidson; Keenan) or the mean (Lee and Kang) of repeated maximal efforts; the median is a local choice against spikes.
   - `force_pilot.py` 90-102 and design doc F2: the multisines are non-periodic but fully previewed; the 250 to 350 ms delay is for targets without preview.
   - Design doc Section 1.8, 815-823: the level-pilot recipe uses `runs_per_finger`, a key that no longer exists anywhere in the code; a second climb is `passes: 2`.

7. **Reliability rows that can move.** SAFE-NOW: add `r_target` and RMSE over target SD to the exploratory reliability rows, with ICC(2,1), ICC(3,1), the shift, and single-run ICC per level with the Spearman-Brown runs needed (`fp_runs_for_icc`, 16443); split T2 and T3 by order A and B. DESIGN-CHANGE (optional): replace T3's TIC with `r_target`, or keep T3 and print the ceiling caveat and the still-finger baseline beside it.

8. **Log the music.** SAFE-NOW. In `audio/block_music.py`, where a track starts (127-130), queue a raw event `block_music` with the track name, and copy it into the block's metadata. The design doc calls music a fixed condition (750-754) while each block draws a random track.

9. **Give Force Pilot its RA line.** SAFE-NOW (UX; log it in the design doc because it changes what participants hear). In `docs/study_day/run_sheet.md`, beside the Reaction and Rhythm lines: "Force Pilot first asks for three firm presses with each finger, as hard as is comfortable. Then fly your line along the band as it scrolls." Order B starts the sitting with this block, straight after calibration.

10. **Stairs grace.** SAFE-NOW: a notebook sensitivity MAE for Stairs with a symmetric window (0.3 s before to 0.6 s after each edge) beside the registered one, via a variant of `fp_grace_windows`. DESIGN-CHANGE if the game's `grace_windows` (785-804) is made symmetric.

11. **Separate the hand from the pad in MAE.** SAFE-NOW: in `force_tracking_runs` (16942) add a noise-corrected RMSE (the resting floor removed in quadrature, as `sd_hold_nc` already does for holds) and, in the cohort chapter, the rank correlation of each person's MAE with 1/max; a strong correlation means part of T2 is the probe, not tracking.

12. **After collection.** AFTER-COLLECTION: a line-only research preset with no corridor, scored against the centre line (the Parkinson's review's `pd_reference`); a frequency manipulation at matched amplitude, finger and width; a no-preview or 0.5 s preview multisine block for a true visuomotor lag; counterbalanced or randomised level order; longer inter-run intervals; a balanced finger table; a sustained 3 s probe with the highest of three and an independent strength measure; forwarding the SingleTact frame index.

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| F1 as a width-free periodic against non-periodic contrast; level rho descriptive | `_ladder_bandwidth_row` (24003), `sec_force_pilot_checks` (27873-27898) | Drop et al 2016 [FT]; simulation |
| F2 as a paired lag-class contrast with a device band and the -19 ms offset | row at 24759; `sec_force_pilot_checks` (27901-27923) | Brewer 2009 [FT]; van der El 2018 [ABS]; Davidson 2026 [FT] |
| Negative lags reported as anticipation, with their share per class | `sec_force_tracking`, `sec_force_pilot_pd` lag tables | Day 1984 [ABS] |
| F3 ratio and RMSE ratio with intervals, TWR5 and CE by direction, split by shape | `_cohort_force_pilot` (21115), F3 rows (24765-24799, 27925-27943) | Davidson 2024, 2026 [FT]; Lakens 2018 [FT] |
| F4 per level with still-finger TIC | cohort F4 (24801-24830); `sec_force_pilot_checks` F4 | arithmetic (Section 1.2) |
| Still-finger MAE and TIC per level, and a skill index 1 - MAE/MAE_still | new helper from `fp_sections_from_params` and `fp_target_vec` | arithmetic |
| Width-free accuracy: RMSE / SD(target) beside `nrmse` (RMSE / peak target) and `r_target` | `fp_pd_measures` (16504-16512), `force_tracking_runs` | Yang 2017 [FT] (correlation more sensitive than RMSE) |
| Reliability rows for `r_target` and RMSE / SD(target); single-run ICC per level; runs needed; T rows by order | `cohort_retest_stats`, `_cohort_reliability_pd`, `fp_runs_for_icc` | Nagasawa 2003 [ABS]; Blomkvist 2018 [FT] |
| F6 on `r_target`, descriptive, beside the phase-redraw floor | `sec_force_pilot_checks` F6 (27988-28018); `sec_force_ladder` (17704-17764) | Yang 2017 [FT]; Chambaron 2006 [ABS] |
| Probe chapter: three peaks, CV, newtons, `max_press_low` count, noise as percent of max per finger | new, reading `raw.csv` probe windows | Keenan and Massey 2012 [FT]; manual [FT] |
| Noise-corrected RMSE; MAE against 1/max | `force_tracking_runs`; cohort chapter | arithmetic model (Q8) |
| Stairs symmetric-window sensitivity | `fp_grace_windows` variant | pilot |
| Fatigue check worded as confounded with width and wave | `sec_force_ladder` (17773-17791) | Lee and Genovese 1988 [ABS] |
| MODE_LIT F1 source corrected; F2 and F6 references updated | MODE_LIT (25908-25952) | Crossref check; Drop 2016 [FT] |
| Visual angle of 1 percent of max, from the screen size and distance on the intake sheet | `continuous_floor_note` (tracking) | Vaillancourt 2006 [ABS]; Prodoehl 2010 [FT] |

Keep as they are: the offline re-score from raw with the logged zero, idle and voided run handling, the Pearson-over-overlap lag estimator, the joint multisine fit, the measurability table against the pad floor, and the within-session wording of every reliability number.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Young adults, 0.2 Hz sine, 10 to 30 percent MVC | RRMSE 0.42 (0.11) generation, 0.38 (0.09) release; time within 5 percent of target 46.98 and 52.44; amplitude -16.57 percent (4.09); phase -0.50 percent (0.96) | Davidson et al 2026, Table 2 [FT] | precision grip, visible line, about 4 s preview, 10 x 32 s; RRMSE carries a time term, compare ratios only |
| Young adults, ramp to 35 percent MVC at about 10 percent/s | RRMSE 0.47, 0.24, 0.39 (generation, hold, release); time within 5 percent 44.33, 75.36, 50.07 | Davidson et al 2024, Table 2 [FT] | Tide and Hills run at 5 percent/s |
| Precision grip MVC, young adults | 54.9 (9.2) N; median 57.68 N | Davidson 2026 Table 1; Davidson 2024 [FT] | not comparable with a pad press |
| Index fingertip pressing MVC, young adults | 37.38 (18.47) N | Keenan and Massey 2012 [FT] | pilot pad maxima were 4 to 16 percent of this (arithmetic) |
| Index finger tracking at 1 and 2 N, young adults | error 4.44 (0.91) (summed), release duration 84.03 (33.60) ms | Carment et al 2018, Table 2 [FT] | spring pistons, visible line |
| Index finger tracking at 1 and 2 N, older controls | RMSE 0.13 (0.06) N; release duration 123 (84) ms | Térémetz et al 2015 [FT] | age-matched to stroke patients |
| Force CV against force level | 4.9 percent at 2 percent MVC; 1.4 percent at 15 percent MVC; 1.2 to 1.9 percent above | Moritz et al 2005 [ABS] | index abduction; Force Pilot's absolute forces sit near 0.3 to 5 percent MVC |
| Online band width, young women | time out of band 2.6 against 0.4 s per 30 s (plus or minus 5 against 10 percent of target, non-dominant); dominant-hand RMSE 0.9 (10 percent MVC) and 4.7 N (40 percent) | Lee and Kang 2020 [FT] | constant 1 degree visual angle; M plus or minus SE |
| Visuomotor delays without preview | feedforward 250 to 350 ms non-harmonic, about 0 harmonic; feedback 300 to 320 ms | Drop et al 2016 [FT] | six trained subjects, aircraft pitch dynamics |
| Preview saturation | 0.6 s (single integrator), 1.15 s (double integrator) | van der El et al 2018 [ABS] | force control is a gain element |
| Tracking reliability | within day 0.87 and 0.95; between days 0.33 to 0.76 | Nagasawa et al 2003 [ABS] | grip pursuit, college students |
| Tracking error reliability between days | 0.60 (tablet line tracking); area 0.31 to 0.60 (older adults) | Rabah et al 2022 [FT]; Blomkvist et al 2018 [FT] | different tasks; both improved at session 2 |
| Pad specification | resolution under 0.2 percent FS; repeatability under 1 percent; linearity under 2 percent; hysteresis under 4 percent; drift 2 percent in 1 min, 4 percent in 10 min at half load | SingleTact datasheet V7.4 [FT] | pad-unit error in closed loop is not biased by hysteresis (Q9) |

How to use them: report Force Pilot's values as the device's own, measured in percent of a maximal comfortable press on an 8 mm pad, inside a band, with 8 s of preview; published values are a frame for order of magnitude and direction, never a norm to test against.

### 6.2 Reliability and practice expectations

- T2 (hand MAE): most likely "good" within the sitting (Nagasawa's within-day 0.87 to 0.95 [ABS]; simulation median 0.83 to 0.87), with an interval at n = 10 that can reach from moderate to excellent; between-day values in the literature are lower (0.33 to 0.76).
- T3 (hand TIC): lower and less certain because of the ceiling (simulation median 0.72 to 0.79, 5th percentile 0.22 to 0.45).
- Pass 2 minus pass 1: an improvement is expected (Carey 1988; Nagasawa 2003, 2010; Blomkvist 2018; Rabah 2022), about 7 to 18 percent in the two FT sources (arithmetic from Blomkvist Tables 2 and 3, Area: left 1.85 to 1.59, 2.09 to 1.72, 2.88 to 2.38, right 1.92 to 1.71, 2.11 to 1.79, 2.60 to 2.42; Rabah Table 2, 81.6 to 72.3 px). Part of it is recovery from massed practice after the rest.
- The shared max repeats in pass 2, so T2 is an upper bound on tracking reliability in two ways: same sitting and same denominator.

### 6.3 Claims to avoid

- That error rises with bandwidth or unpredictability because it rises (or not) with ladder level.
- A visuomotor lag of 100 to 300 ms from this display; lags here are dominated by preview and anticipation.
- That release is as accurate as press as a finding: the registered test cannot fail at plus or minus 2 percent of max.
- That TIC at or above 0.8 shows healthy force control: a still finger reaches 0.54 to 1.00.
- That the probed max is an MVC or that percent of max equals percent MVC; the pilot maxima were 4 to 16 percent of a young index MVC.
- That Storm against Uncharted shows waveform-specific learning, or that pass 2 improvement is learning.
- That the within-session ICC is day-to-day reliability.
- Per-finger conclusions from the fixed finger table, and any claim about the little finger apart from its noise floor.
- Newton-accurate or true-force release claims before the mass bench check; hysteresis and creep act on true force.
- That the block causes no fatigue as a measured result: it is expected to be negligible (arithmetic), not measured.
- Any effect of visual gain: it was not varied.

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, NCBI E-utilities, Crossref, OpenAlex, the TU Delft repository and the manufacturer's documents.

1. Archer DB, Kang N, Misra G, Marble S, Patten C, Coombes SA. 2018. Visual feedback alters force control and functional activity in the visuomotor network after stroke. NeuroImage: Clinical 17:505-517. DOI 10.1016/j.nicl.2017.11.012. PMID 29201639. PMC5700823. [FT: Methods (MVC, visual gain), Results (force error, variability)]
2. Armitage L, Cho K, Sariyildiz E, Buller A, O'Brien S, Kark L. 2023. Validation of a custom interface pressure measurement system to improve fitting of transtibial prosthetic check sockets. Sensors 23(7):3778. DOI 10.3390/s23073778. PMID 37050838. PMC10099032. [FT: Results (temperature, drift Table 1, dynamic response, hysteresis), Discussion]
3. Baweja HS, Kennedy DM, Vu J, Vaillancourt DE, Christou EA. 2010. Greater amount of visual feedback decreases force variability by reducing force oscillations from 0-1 and 3-7 Hz. European Journal of Applied Physiology 108(5):935-943. DOI 10.1007/s00421-009-1301-5. PMID 19953262. PMC2863099. [ABS]
4. Blomkvist AW, Eika F, de Bruin ED, Andersen S, Jorgensen M. 2018. Handgrip force steadiness in young and older adults: a reproducibility study. BMC Musculoskeletal Disorders 19(1):96. DOI 10.1186/s12891-018-2015-9. PMID 29609577. PMC5879800. [FT: Methods, Tables 1 to 3, Results]
5. Bonett DG. 2002. Sample size requirements for estimating intraclass correlations with desired precision. Statistics in Medicine 21(9):1331-1335. DOI 10.1002/sim.1108. PMID 12111881. [META]
6. Brewer BR, Pradhan S, Carvell G, Delitto A. 2009. Application of modified regression techniques to a quantitative assessment for the motor signs of Parkinson's disease. IEEE Transactions on Neural Systems and Rehabilitation Engineering 17(6):568-575. DOI 10.1109/TNSRE.2009.2034461. PMID 19884100. PMC4894031. [FT: Methods (display, preview, lag definition and bounds), Discussion]
7. Carey JR, Patterson R, Hollenstein PJ. 1988. Sensitivity and reliability of force tracking and joint-movement tracking scores in healthy subjects. Physical Therapy 68(7):1087-1091. DOI 10.1093/ptj/68.7.1087. PMID 3290913. [ABS]
8. Carment L, Abdellatif A, Lafuente-Lafuente C, Pariel S, Maier MA, Belmin J, Lindberg PG. 2018. Manual dexterity and aging: a pilot study disentangling sensorimotor from cognitive decline. Frontiers in Neurology 9:910. DOI 10.3389/fneur.2018.00910. PMID 30420830. PMC6215834. [FT: Methods (tracking task), Table 2]
9. Cathers I, O'Dwyer N, Neilson P. 1996. Tracking performance with sinusoidal and irregular targets under different conditions of peripheral feedback. Experimental Brain Research 111(3):437-446. DOI 10.1007/BF00228733. PMID 8911938. [ABS]
10. Chambaron S, Ginhac D, Ferrel-Chapus C, Perruchet P. 2006. Implicit learning of a repeated segment in continuous tracking: a reappraisal. Quarterly Journal of Experimental Psychology 59(5):845-854. DOI 10.1080/17470210500198585. PMID 16608750. [ABS]
11. Coombes SA, Corcos DM, Sprute L, Vaillancourt DE. 2010. Selective regions of the visuomotor system are related to gain-induced changes in force error. Journal of Neurophysiology 103(4):2114-2123. DOI 10.1152/jn.00920.2009. PMID 20181732. PMC2853269. [ABS]
12. Davidson S, Learman K, Zimmerman E, Rosenfeldt AB, Koop M, Alberts JL. 2024. Older adults are impaired in the release of grip force during a force tracking task. Experimental Brain Research 242(3):665-674. DOI 10.1007/s00221-023-06770-y. PMID 38246931. PMC10894767. [FT: Methods (MVC, task, analysis), Results, Table 2]
13. Davidson S, Learman K, Rosenfeldt AB, Zimmerman E, Alberts JL. 2026. Parkinson's disease impairs grip force release during a sinusoidal force tracking task. Experimental Brain Research 244(4):46. DOI 10.1007/s00221-026-07241-w. PMID 41706132. PMC12916958. [FT: Methods (display, preview, instruction, MVC), Tables 1 and 2, Results, Discussion]
14. Day BL, Dick JP, Marsden CD. 1984. Patients with Parkinson's disease can employ a predictive motor strategy. Journal of Neurology, Neurosurgery and Psychiatry 47(12):1299-1306. DOI 10.1136/jnnp.47.12.1299. PMID 6512550. PMC1028137. [ABS]
15. Drop FM, de Vries R, Mulder M, Bülthoff HH. 2016. The predictability of a target signal affects manual feedforward control. IFAC-PapersOnLine 49(19):177-182. DOI 10.1016/j.ifacol.2016.10.482. [FT: TU Delft repository copy; Sections 1, 2.2, 4 and 5, Figures 7 and 8]
16. Ebisu S, Kasahara S, Saito H, Ishida T. 2022. Decrease in force control among older adults under unpredictable conditions. Experimental Gerontology 158:111649. DOI 10.1016/j.exger.2021.111649. PMID 34875350. [ABS]
17. Frey Law LA, Avin KG. 2010. Endurance time is joint-specific: a modelling and meta-analysis investigation. Ergonomics 53(1):109-129. DOI 10.1080/00140130903389068. PMID 20069487. PMC2891087. [FT: Methods, Table 2]
18. Häger-Ross C, Schieber MH. 2000. Quantifying the independence of human finger movements: comparisons of digits, hands, and movement frequencies. Journal of Neuroscience 20(22):8542-8550. DOI 10.1523/JNEUROSCI.20-22-08542.2000. PMID 11069962. PMC6773164. [ABS]
19. Keenan KG, Massey WV. 2012. Control of fingertip forces in young and older adults pressing against fixed low- and high-friction surfaces. PLoS One 7(10):e48193. DOI 10.1371/journal.pone.0048193. PMID 23110210. PMC3480490. [FT: Methods (MVC task), Results (MVC tasks)]
20. Koo TK, Li MY. 2016. A guideline of selecting and reporting intraclass correlation coefficients for reliability research. Journal of Chiropractic Medicine 15(2):155-163. DOI 10.1016/j.jcm.2016.02.012. PMID 27330520. PMC4913118. [META]
21. Kurillo G, Zupan A, Bajd T. 2004. Force tracking system for the assessment of grip force control in patients with neuromuscular diseases. Clinical Biomechanics 19(10):1014-1021. DOI 10.1016/j.clinbiomech.2004.07.003. PMID 15531051. [ABS]
22. Kurillo G, Gregoric M, Goljar N, Bajd T. 2005. Grip force tracking system for assessment and rehabilitation of hand function. Technology and Health Care 13(3):137-149. PMID 15990417. [ABS]
23. Lakens D, Scheel AM, Isager PM. 2018. Equivalence testing for psychological research: a tutorial. Advances in Methods and Practices in Psychological Science 1(2):259-269. DOI 10.1177/2515245918770963. [FT: accepted version on OSF (osf.io/v3zkt); sections on objective and subjective justification of the smallest effect size of interest]
24. Lee JH, Kang N. 2020. Effects of online-bandwidth visual feedback on unilateral force control capabilities. PLoS One 15(9):e0238367. DOI 10.1371/journal.pone.0238367. PMID 32941453. PMC7498075. [FT: Methods, Results]
25. Lee TD, Genovese ED. 1988. Distribution of practice in motor skill acquisition: learning and performance effects reconsidered. Research Quarterly for Exercise and Sport 59(4):277-287. DOI 10.1080/02701367.1988.10609373. [ABS: abstract through OpenAlex]
26. Lee TD, Genovese ED. 1989. Distribution of practice in motor skill acquisition: different effects for discrete and continuous tasks. Research Quarterly for Exercise and Sport 60(1):59-65. DOI 10.1080/02701367.1989.10607414. PMID 2489826. [ABS]
27. Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH. 2013. Increased force variability in chronic stroke: contributions of force modulation below 1 Hz. PLoS One 8(12):e83468. DOI 10.1371/journal.pone.0083468. PMID 24386208. PMC3873339. [FT: Methods, prediction of force variability section, Figure 7]
28. McGraw KO, Wong SP. 1996. Forming inferences about some intraclass correlation coefficients. Psychological Methods 1(1):30-46. DOI 10.1037/1082-989X.1.1.30. [META]
29. McRuer DT, Jex HR. 1967. A review of quasi-linear pilot models. IEEE Transactions on Human Factors in Electronics HFE-8(3):231-249. DOI 10.1109/THFE.1967.234304. [META; content as reported in Drop et al 2016]
30. Moritz CT, Barry BK, Pascoe MA, Enoka RM. 2005. Discharge rate variability influences the variation in force fluctuations across the working range of a hand muscle. Journal of Neurophysiology 93(5):2449-2459. DOI 10.1152/jn.01122.2004. PMID 15615827. [ABS]
31. Nagasawa Y, Demura S, Nakada M. 2003. Reliability of a computerized target-pursuit system for measuring coordinated exertion of force. Perceptual and Motor Skills 96(3 Pt 2):1071-1085. DOI 10.2466/pms.2003.96.3c.1071. PMID 12929759. [ABS]
32. Nagasawa Y, Demura S. 2010. Reproducibility of controlled force exertion measurements computed by a quasi-random target-pursuit system. Perceptual and Motor Skills 110(2):366-378. DOI 10.2466/PMS.110.2.366-378. PMID 20499549. [ABS]
33. Naik SK, Patten C, Lodha N, Coombes SA, Cauraugh JH. 2011. Force control deficits in chronic stroke: grip formation and release phases. Experimental Brain Research 211(1):1-15. DOI 10.1007/s00221-011-2637-8. PMID 21448576. [ABS]
34. Novak TS, Wilson SM, Newell KM. 2021. Establishing task-relevant MVC protocols for modelling sustained isometric force variability: a manual control study. Journal of Functional Morphology and Kinesiology 6(4):94. DOI 10.3390/jfmk6040094. PMID 34842771. PMC8628892. [FT: Abstract, Methods (MVC procedures)]
35. Ohtaka C, Fujiwara M. 2016. Control strategies for accurate force generation and relaxation. Perceptual and Motor Skills 123(2):489-507. DOI 10.1177/0031512516664778. PMID 27555365. [ABS]
36. Ohtaka C, Fujiwara M. 2019. Force control characteristics for generation and relaxation in the lower limb. Journal of Motor Behavior 51(3):331-341. DOI 10.1080/00222895.2018.1474337. PMID 29843580. [ABS]
37. Park SH, Kwon M, Solis D, Lodha N, Christou EA. 2016. Motor control differs for increasing and releasing force. Journal of Neurophysiology 115(6):2924-2930. DOI 10.1152/jn.00715.2015. PMID 26961104. PMC4922612. [ABS]
38. Park SH, Kim C, Yacoubi B, Christou EA. 2019. Control of oscillatory force tasks: low-frequency oscillations in force and muscle activity. Human Movement Science 64:89-100. DOI 10.1016/j.humov.2019.01.009. PMID 30690253. [ABS]
39. Patel P, Zablocki V, Lodha N. 2019. Bimanual force control differs between increment and decrement. Neuroscience Letters 701:218-225. DOI 10.1016/j.neulet.2019.03.002. PMID 30844474. [ABS]
40. Pressure Profile Systems. 2025. SingleTact datasheet, V7.4 (CS8-10N calibrated 8 mm, 10 N). SingleTact_Datasheet.pdf, SingleTact document store. [FT: sensor performance and electronics tables]
41. Pressure Profile Systems. 2026. SingleTact user manual. SingleTact_Manual.pdf, SingleTact document store. [FT: Table 1, Sections 2.2, 2.3, 2.6, 2.7]
42. Prodoehl J, Vaillancourt DE. 2010. Effects of visual gain on force control at the elbow and ankle. Experimental Brain Research 200(1):67-79. DOI 10.1007/s00221-009-1966-3. PMID 19680640. PMC2842579. [FT: Methods (visual gain definition, Figure 1), Results, Discussion]
43. Rabah A, Le Boterff Q, Carment L, Bendjemaa N, Térémetz M, Dupin L, Cuenca M, Mas JL, Krebs MO, Maier MA, Lindberg PG. 2022. A novel tablet-based application for assessment of manual dexterity and its components: a reliability and validity study in healthy subjects. Journal of NeuroEngineering and Rehabilitation 19(1):35. DOI 10.1186/s12984-022-01011-9. PMID 35331273. PMC8953393. [FT: Methods (line tracking), Table 2, Results]
44. Schmidt RA, Wulf G. 1997. Continuous concurrent feedback degrades skill learning: implications for training and simulation. Human Factors 39(4):509-525. DOI 10.1518/001872097778667979. PMID 9473972. [ABS]
45. Slifkin AB, Vaillancourt DE, Newell KM. 2000. Intermittency in the control of continuous force production. Journal of Neurophysiology 84(4):1708-1718. DOI 10.1152/jn.2000.84.4.1708. PMID 11024063. [ABS]
46. Sosnoff JJ, Newell KM. 2008. Age-related loss of adaptability to fast time scales in motor variability. Journals of Gerontology Series B 63(6):P344-P352. DOI 10.1093/geronb/63.6.p344. PMID 19092037. [ABS]
47. Spraker MB, Corcos DM, Vaillancourt DE. 2009. Cortical and subcortical mechanisms for precisely controlled force generation and force relaxation. Cerebral Cortex 19(11):2640-2650. DOI 10.1093/cercor/bhp015. PMID 19254959. PMC2758679. [ABS]
48. Tang KPM, Yick KL, Li PL, Yip J, Or KH, Chau KH. 2020. Effect of contacting surface on the performance of thin-film force and pressure sensors. Sensors 20(23):6863. DOI 10.3390/s20236863. PMID 33266213. PMC7729666. [FT: Table 1, calibration and temperature sections, Tables 4 to 6, drift section]
49. Térémetz M, Colle F, Hamdoun S, Maier MA, Lindberg PG. 2015. A novel method for the quantification of key components of manual dexterity after stroke. Journal of NeuroEngineering and Rehabilitation 12:64. DOI 10.1186/s12984-015-0054-0. PMID 26233571. PMC4522286. [FT: Methods (FFM, tracking task, measures), Results (force tracking)]
50. Vaillancourt DE, Haibach PS, Newell KM. 2006. Visual angle is the critical variable mediating gain-related effects in manual control. Experimental Brain Research 173(4):742-750. DOI 10.1007/s00221-006-0454-2. PMID 16604313. PMC2366211. [ABS]
51. van der El K, Padmos S, Pool DM, van Paassen MM, Mulder M. 2018. Effects of preview time in manual tracking tasks. IEEE Transactions on Human-Machine Systems 48(5):486-495. DOI 10.1109/THMS.2018.2834871. [ABS: abstract on the TU Delft research portal]
52. van der El K, Pool DM, van Paassen MM, Mulder M. 2018. Effects of preview on human control behavior in tracking tasks with various controlled elements. IEEE Transactions on Cybernetics 48(4):1242-1252. DOI 10.1109/TCYB.2017.2686335. PMID 28391217. [ABS]
53. Weir JP. 2005. Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. Journal of Strength and Conditioning Research 19(1):231-240. DOI 10.1519/15184.1. PMID 15705040. [META]
54. Wulf G, Schmidt RA. 1997. Variability of practice and implicit motor learning. Journal of Experimental Psychology: Learning, Memory, and Cognition 23(4):987-1006. DOI 10.1037/0278-7393.23.4.987. [META; paradigm as described in Yang et al 2017 and Chambaron et al 2006]
55. Yang L, Wan F, Nan W, Zhu F, Hu Y. 2017. Reliable detection of implicit waveform-specific learning in continuous tracking task paradigm. Scientific Reports 7(1):12333. DOI 10.1038/s41598-017-11977-5. PMID 28951576. PMC5615060. [FT: Introduction, Methods, Results (practice, immediate and consolidation tests)]

Counts: 55 sources; 21 FT (including the two manufacturer documents and one repository copy), 28 ABS, 6 META. Of the 30 sources the audit table and recommendations rest on (Davidson 2024 and 2026, Drop 2016, Brewer 2009, van der El 2018 twice, Day 1984, Lee and Kang 2020, Keenan and Massey 2012, the SingleTact datasheet and manual, Lakens 2018, Yang 2017, Chambaron 2006, Nagasawa 2003, Blomkvist 2018, Rabah 2022, Prodoehl 2010, Baweja 2010, Archer 2018, Cathers 1996, Sosnoff and Newell 2008, Lee and Genovese 1988, Park 2019, Frey Law 2010, Carment 2018, Térémetz 2015, Lodha 2013, Kurillo 2004 and 2005), 18 are FT. Armitage 2023 and Tang 2020 [FT] carry the sensor characterisation. Every META source whose content is used was read through a named FT source (McRuer and Jex through Drop; Wulf and Schmidt through Yang); the rest are the design's own method references.

Not re-read here and left as the design and notes cite them: Pennati 2020, Taud 2021, Vaillancourt 2007, Russo 2017, Boyd and Winstein 2004, Chung 2023, Davidson 2025, Camacho-Villa 2025, Pradhan 2010, Miall 1993, Zatsiorsky 2000.

### Simulation and arithmetic assumptions (for Sections 2 to 4)

The simulation scripts are not kept in the repository; the assumptions above are enough to rebuild them.

Cohort simulation (`cohort_sim.py`, 400 cohorts of 10 people per scenario, two passes of the twelve waves exactly as coded, Uncharted's phases drawn per block, 50 Hz grid). Force per run = the run's mean target + gain x (lagged target - mean) on oscillating sections (ramps, holds and steps follow the lagged target with gain 1) + an Ornstein-Uhlenbeck drift (time constant 1.5 s, SD a share s of the half-width) + a signed bias (person mean -0.8 percent of max, person SD 0.6, run SD 0.6) + white noise with SD sqrt(sensor^2 + (CV x target)^2), sensor noise 1.35 counts over a lognormal max (median 180 counts, log-SD 0.4), CV 0.04 (SD 0.01); force clamped at zero. Scenarios: band keeping (gain 0.70, SD 0.10; lags -40 ms periodic, 180 ms ramps and steps, 60 ms multisines; s 0.26, SD 0.07); band keeping with drift growing 4 percent a run; line tracking (gain 0.85, SD 0.06; lags -20, 150, 60 ms; s 0.08, SD 0.03); no preview use (gain 0.80, SD 0.08; lags -20, 180, 220 ms; s 0.12, SD 0.04). Person lag SD 50 ms (periodic), 70 (ramps), 60 (multisines); run lag SD 60 ms; run gain SD 0.05. Pass 2: gain +0.03 (SD 0.03), lag -20 ms (SD 30), drift x 0.95 (SD 0.08). Band keeping was set so its mean MAE (2.1 to 2.3 percent of max) and TIC (0.93 to 0.95) sit near the pilot's (median MAE 2.78, TIC 0.92). Checks replicate the notebook's rules: F1 per-person Spearman rho on level with a one-sided Wilcoxon and median above zero; F2 the median of per-person non-periodic lags (runs with r of 0.35 or more, Pearson cross-correlation over plus or minus 1.5 s) with its bootstrap interval inside 100 to 300 ms; F3 the 90 percent t interval of release minus press MAE on the symmetric shapes inside plus or minus 2; F4 the pooled share of runs at TIC 0.8 or more above 0.5; T2 and T3 ICC(2,1) of the 12-run means (McGraw and Wong absolute agreement, single measure). Width-free F1: per-person mean force-target correlation on levels 1, 3, 6, 7, 9 minus 10, 11, 12, or RMSE over target SD the other way, one-sided Wilcoxon. TOST power table: 20,000 cohorts of 10 normally distributed person differences per cell.

Arithmetic model of a mis-set maximum (Q8): RMS error = sqrt(behaviour^2 + count^2 + physiology^2), behaviour 3.0 percent of max RMS, count noise 1.35 counts of pad noise plus a 1.0 count zero error over the probed max in counts, physiological CV of 4.9 percent at 2 percent MVC and 1.4 percent at 15 percent MVC (Moritz et al 2005) joined by a power law and extended below 2 percent MVC, targets 8 to 31 percent of the probed max, an index MVC of 37 N (Keenan and Massey 2012) and 0.0195 N per count.

Target statistics (Section 1.2): computed from a standalone copy of `level_sections` and `target_pct` at 200 Hz; the Uncharted ranges from 2,000 random phase draws. Pilot re-score: three blocks under `sessions/2026-09-23` and `sessions/2026-09-25`, zero from the median raw value over the first 0.3 s of the announce card, sine gain from a least-squares fit skipping the first second of the oscillation.
