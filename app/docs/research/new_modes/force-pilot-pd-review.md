# Force Pilot and Parkinson's disease: audit, new literature, protocol and thesis plan

Prepared 30 September 2026: an audit of Force Pilot and its analysis against the Parkinson's literature, new literature, a protocol for Parkinson's research with the game, and what the thesis can claim. The analysis additions it recommends were built the same day, before any participant; Section E7 of [force-pilot-parkinsons.md](force-pilot-parkinsons.md) lists them. The protocol in Section 3 and the game changes wait until after the healthy collection. The device-check scripts were run outside the repository on copies of the pilot sessions named below.

---

## 0. Scope, method and words used

**Repository material read.** `app/docs/research/new_modes/force-pilot-parkinsons.md` (all 788 lines), `force-control.md`, `movement-disorders.md`, `app/docs/research/healthy_baseline_study.txt` (status block, Sections 1.8, 2.1 to 2.4, 4.2, 4.5 to 4.8), `app/docs/research/force_units.txt`, `app/finger_rehab/game/modes/force_pilot.py` (all), `app/finger_rehab/ui/force_pilot_screen.py` (header, geometry, probe text), `app/finger_rehab/game/force_stream.py` (ForceView, MaxPressProbe, needs_max_press_probe), the `fsr` and `force_pilot` blocks of `app/config/default.yaml`, the Force Pilot code of `analysis/session_analysis.ipynb` (every `fp_*` helper, `fp_pd_measures`, `fp_enslaving`, `force_tracking_runs`, `sec_force_tracking`, `sec_force_pilot_checks`, `FP_PD_SPECS`, `FP_PD_COHORT`, `sec_force_pilot_pd`, `_cohort_force_pilot`, `cohort_retest_stats`, `_cohort_reliability_pd`), the firmware sensor read (`app/arduino/firmware_on_device/lib/Sensor/Sensor.cpp`, `src/main.cpp`), `app/scripts/pad_bench.py` (reading and quick check), `hardware/README.md`.

**Device checks run (read-only).** Scripts read `raw.csv`, `trials.csv` and `metadata.json` of two existing pilot Force Pilot sessions (`sessions/2026-09-25/P673_104920_force_pilot`, 12 runs of which levels 10 to 12 were idle; `sessions/2026-09-23/P669_193831_force_pilot`, 4 runs) plus the recorded max presses of all Force Pilot sessions. Two people, 13 active runs. These are checks of the device, not results about people.

**Literature.** Europe PMC REST (search and core records with abstracts), PMC full text (Europe PMC `fullTextXML` or the PMC article page), Crossref for one record, and the SingleTact user manual PDF. Each source carries a tag:

- **FT**: full text read by me (methods and results).
- **FT-S**: full text read through a fetch tool that returns extracted passages; numbers are as it quoted them.
- **ABS**: abstract read.
- **META**: bibliographic record only.

Numbers appear only where they were read. My own calculations are marked **arithmetic**. Sources already in the research note are cited by the note's own labels (for example [A1.1 Davidson 2026]) and are not listed again unless a detail was corrected or added (list R in Section 7).

**Words used (defined once).**

- **ICC** (intraclass correlation): the share of the spread between people that survives a repeat. 1 is perfect agreement.
- **SEM** (standard error of measurement): the noise in one person's score. **MDC95** (minimal detectable change): the smallest change bigger than that noise with 95% confidence, 1.96 × √2 × SEM.
- **TOST**: two one-sided tests, the equivalence test F3 uses.
- **RRMSE** and **%TWR**: Davidson's error normalised to the peak target, and the share of time within ±5% of the target.
- **Enslaving**: force that appears in fingers the person did not mean to press.
- **Sequence effect** (decrement): movements get smaller or slower as they repeat.
- **MVC**: maximum voluntary contraction.
- **V3**: verification (does the sensor measure the physical quantity), analytical validation (does the algorithm turn it into the intended measure), clinical validation (does the measure reflect the clinical state in the target group) [N33 Goldsack 2020].

---

## 1. Status audit

### 1.1 Table B rows: what the notebook computes today

"Note" says whether the code does what `force-pilot-parkinsons.md` Table B specifies. "Source" says whether it matches the cited paper's method.

| Row | Measure | Status | Where | Note | Source |
|---|---|---|---|---|---|
| 1 | RMSE, MAE | Done | `force_tracking_runs` (`mae`, `rmse`) | Yes | Partly: raw 200 Hz force; Brewer low-passed at 2 Hz before RMSE [R5], Davidson filtered at 12 Hz [R1] |
| 2 | nRMSE | Computed, never reported | `fp_pd_measures` (`nrmse` = run RMSE / run peak target) | No: note asks per phase; not in `FP_PD_SPECS` or `FP_PD_COHORT` | Davidson computed per phase [R1] |
| 3 | TWR5 | Partly | `twr5_rise`, `twr5_fall` reported; `twr5` (whole run) and `twr5_max` (±5% of max) computed and dropped | Partly | Band matches Davidson (±5% of target) [R1] |
| 4 | Press vs release | Done | `press_mae`, `release_mae`, `release_ratio`, `asym_*` on roles `sym_ramp`, `osc`, `pulse` | Yes (also includes Heartbeat pulses and multisines) | Davidson used RMSE per phase; MAE ratio is close but not the same number |
| 5 | Terminal phase | Done | `term_ce`, `term_mae`, `term_twr5`, `term_settle_s`, `term_unsettled` | Yes | Band choice differs: Davidson 2025 defines ±5% of the target, which is zero in the terminal phase, so the paper's 0.81 vs 0.51 cannot be matched [R2] |
| 6 | Trial-to-trial SD (iSD) | Missing | none | No | Davidson 2025 iSD = SD over 10 trials [R2] |
| 7 | Rise and relaxation rate | Done, as 20 to 80% transition gains | `pulse_rise_gain`, `pulse_fall_gain`, `slip_rate_gain` via `fp_edge_rate` | Row 7 text still says peak rates; E5 describes the change but the row was not updated | Chung, Tobin, Neely measured ballistic rates; Force Pilot guides the rate |
| 8 | Pulse timing | Done | `pulse_peak_lag_ms`, `pulse_relax_lag_ms` | Yes | Construct differs (guided vs as fast as possible) |
| 9 | Segmentation | Done | `ramp_up_steps`, `release_steps`, `_rel`, `_pause_s`, `hold_rate_sd` on a 5 Hz low-pass | Yes | Knight lab counts zero crossings of the second derivative in ballistic pulses [N3], a different construct |
| 10 | Sine-fit gain and phase | Done | `gain`, `fit_lag_ms`, `fit_r2`, `sine_fit`, cohort `pd_gain_swell` | Yes | Yes (Davidson fitted a sine per trial) [R1] |
| 11 | Lag by wave class | Done | `lag_ms`, `lag_r`, `lag_class`; floor 0.35; bound 1.5 s | Yes | Brewer set the lag to its maximum when covariance was under 0.35 and bounded it at 2 s (sine) and 5 s (pseudorandom); the notebook drops the run instead [R5] |
| 12 | Signed error | Partly | `ce`, `ce_rise`, `ce_fall`, `ce_hold` | Turnaround (peak and trough) errors missing | n/a |
| 13 | Steadiness SD, CV | Done as written | `sd_hold`, `cv_hold` on Tide `slack` and Stairs treads | Yes | No: no low-pass (Blomkvist 20 Hz [R7], Chung 15 Hz [R3], Davidson 12 Hz [R1]), windows of 1.1 s (treads) and 2.5 s (slack) against 17 to 20 s analysed in the literature [R4, R7] |
| 14 | Force decay without vision | Not possible | no feedback blank | n/a | n/a |
| 15 | Tremor band | Partly | `fp_tremor_bands`: shares of 0.1 to 12 Hz error power only | Note asks power and share | No: Brewer took the area under the raw-force spectrum from 2 to 8 Hz, an absolute power [R5] |
| 16 | Sample entropy | Done | `fp_sample_entropy` (m 2, r 0.2 SD, 100 Hz, detrended error) | Yes | Vaillancourt used approximate entropy on holds (note A1.13) |
| 17 | Lodha sub-1 Hz split | Done | `lodha_bands`, `lodha_ratio` | Yes | Stroke measure, exploratory for PD |
| 18 | Decrement | Done | `pulse_decrement` (4 beats), `amp_decrement` (2 to 4 cycles) | Yes; `FP_PD_SPECS` wording says "peak force" but the code fits a gain | Tinaz fitted 20 squeezes (note A2.7) |
| 19 | Enslaving | Done as the note wrote it | `fp_enslaving` (each other finger in % of its own max regressed on the task finger in % of its max, whole run) | Yes | No: Park 2014 regressed each finger's force on total force in newtons over 10 s of a 0 to 40% MVC ramp [R6]; the 0.07 to 0.09 reference is not the same quantity |
| 20 | Multi-finger synergy | Not possible in this mode | n/a | n/a | n/a |
| 21 | Dual-task cost | Not possible | n/a | n/a | n/a |
| 22 | Practice | Done | pass 1 vs 2 in `sec_force_pilot_pd`; ICC, SEM, MDC95 in `_cohort_reliability_pd`; F6 on the latest play | Yes | Retention needs another day |
| 23 | UPDRS link | n/a in healthy adults | n/a | n/a | n/a |
| 24 | Strength | Recorded, never reported | `metadata.json` `calibration.max_press` | Partly | The newton constant exists (0.0195 N per count, `config/default.yaml` `fsr`) but is not applied to the max |

### 1.2 C1 to C11

| Item | Status | Comment |
|---|---|---|
| C1 press vs release on symmetric shapes | Done | Ratio and paired difference; Dunes apart. Not printed per finger. The in-session F3 row (`sec_force_pilot_checks`) uses a 95% bootstrap interval across runs; the cohort F3 uses the pre-registered 90% TOST. |
| C2 sine-fit frequency response | Done | Joint fit, 1 s entry skipped, Swell reported against 0.83. |
| C3 literature-unit accuracy | Partly | `nrmse`, `twr5`, `twr5_max` computed and thrown away; nRMSE not per phase. |
| C4 signed and turnaround error | Partly | No peak or trough error. |
| C5 segmentation on ladder ramps | Done | Fixed 3 %/s and relative 40% floors, 0.15 s pauses, 0.25 s trimmed ends. |
| C6 guided rate, timing, settle | Done | 20 to 80% transitions (per E5), settle within 2% of max for 0.2 s. |
| C7 decrement | Done, thin | 4 beats and 2 to 4 cycles per run; Slow breath has 2 cycles, so its slope is a two-point difference. |
| C8 enslaving | Done as written, not commensurate with Park | Mechanical cross-talk still unmeasured: `pad_bench.py` reads all four pads but `_reading` keeps only the loaded one. |
| C9 lag by class | Done | |
| C10 tremor and regularity | Done as shares | Not Brewer's measure; healthy tremor sits at the device floor (Section 1.4). |
| C11 reliability and practice | Done | Exploratory ICC, SEM, MDC95 and shift for every `pd_*` row. |

### 1.3 Places where code, notebook, note, docs or literature disagree

1. **Tremor measure** (`fp_tremor_bands`, `analysis/session_analysis.ipynb`): returns 2 to 8 and 8 to 12 Hz shares of 0.1 to 12 Hz *error* power. Tracking error is dominated by power under 1 Hz, so a worse tracker gets a smaller "tremor share". Brewer 2009, the paper cited for it, used the absolute area under the raw-force spectrum from 2 to 8 Hz [R5]. Table B row 15 asked for absolute power as well.
2. **Steadiness** (`fp_pd_measures`, steady-hold block): SD and CV on unfiltered force over 1.1 s (Stairs treads after the 0.6 s grace and 0.5 s drop) or 2.5 s (Tide slack), with a linear detrend. A detrend over 1.1 s removes most variance under 1 Hz, which carries most of force variability in the literature the references come from. `FP_PD_SPECS` still prints Tobin 0.034 and Moritz 0.014 as references for `cv_hold`. The literature filtered before SD (12 to 20 Hz) and analysed 17 to 20 s [R1, R3, R4, R7].
3. **Enslaving reference** (`fp_enslaving`, `FP_PD_SPECS`): regressor, units and window differ from Park 2014 [R6]. On pilot runs the notebook-style index and a Park-style index differed in size and in sign on 4 of 13 runs (Section 1.4).
4. **Terminal-phase band** (`term_twr5`): the note's choice (5% of the height the release came from) is sensible, but Davidson 2025 defines the band as ±5% of the target force [R2], which is zero at the 0% terminal target. The printed reference (0.81 controls, 0.51 PD) is not comparable.
5. **Lag handling** (`tracking_lag_ms`, `FP_LAG_R_FLOOR`): runs under r 0.35 are dropped; Brewer set them to the maximum lag [R5]. Dropping hides the worst trackers, which matters in a PD comparison.
6. **RMSE** (`force_tracking_runs`): on raw force, so it carries pad noise; Brewer low-passed at 2 Hz first [R5]. With noise near 0.5 to 1.8% of max and RMSE near 2 to 3% of max, the inflation is a few percent to about 15% (arithmetic, root-sum-square).
7. **Table B row 7** (note) still describes peak rates and "achieved peak / prescribed peak"; the notebook uses 20 to 80% transitions (the note's own E5). E6 says rows 5, 8 and 18 were brought up to date; row 7 was not.
8. **`FP_PD_SPECS` wording**: `pulse_decrement` is described as "slope of peak force over target peak"; the code fits a one-cycle gain per beat (as the note's row 18 says).
9. **Stale filter comment** (`sec_force_tracking`, segmentation block): says "from the 12 Hz filtered rate"; `FP_LP_HZ` is 5.0.
10. **Floor note** (`continuous_floor_note("tracking")`): says low-force accuracy and drift "has not been bench-checked"; noise and drift were measured on 24 September (baseline study Section 4.8 h). The slope check with masses is still pending (`config/default.yaml` says so), so the line is half right.
11. **Update rate**: `hardware/README.md` and `force_units.txt` say each pad updates at 50 to 120 Hz so values repeat; the baseline study says the stream is a true 200 Hz. The SingleTact manual says both "Sensor update rate ... Up to 120 Hz" and that its converter runs at 140 to 4000 Hz and updates the output register on every conversion [N64]. The pilot data side with the baseline study (Section 1.4).
12. **Tobin 2025 medication** (note A1.15 says the state was not stated): the paper tested PD after more than 12 h withdrawal of dopaminergic medication [R4].
13. **Feedback-blank length** (note D4 suggests 1 to 2 s blanks): after vision was removed, force began to decay 1.5 to 2.5 s later in both PD and controls [R8]. A 1 to 2 s blank ends before the decay starts.
14. **F3 scope**: the pre-registered text says Tide, Hills and "each sine"; `fp_pd_measures` also counts Heartbeat pulses and the multisines. Both are sine-based and symmetric, so this is defensible, but the thesis should say it.
15. **Max press procedure** (`MaxPressProbe`, `force_stream.py`): median of three presses at least 0.15 s long with at least 0.3 s quiet between. Davidson used the highest of three MVCs with 1 to 2 min rest [R1, R2]; Chung averaged three peaks with 5 s rest [R3]; Tobin took the best of 3 to 5 [R4].

### 1.4 Device checks on the pilot data (2 people, 13 active runs)

- **Sampling.** 198.7 samples per second (count over span). Overall 70 to 79% of consecutive samples repeat, but where force changes by 4 or more counts per sample only 0 to 3% repeat and 95 to 100% of samples change on consecutive samples. The stream carries a fresh reading every 5 ms; repeats at slow slopes are one-count quantisation. Host timestamps arrive in bursts, which the notebook already handles with a uniform grid. The firmware reads registers 128 to 133 of each pad (`READ_OFFSET` 128, `READ_LENGTH` 6 in `lib/Config/Config.h`) and keeps only the output bytes (132, 133). Registers 128 and 129 hold the frame index, which "increments on each new reading", and 130 and 131 a sensor timestamp in 0.1 ms steps [N64]. Both are read and thrown away; forwarding them would count duplicates and dropped readings exactly.
- **Max press.** Recorded maxima were 73 to 311 counts above rest across Force Pilot sessions: 1.4 to 6.1 N at 51.2 counts per newton (P669: 109, 120, 107, 73; P673: 272, 212, 195, 128). Raw peaks never neared the top of the output range. For scale, four-finger pressing MVC in early PD was 60 to 66 N [R6]. The "max" here is a pad-limited press, not a finger MVC.
- **Resolution.** One count is 0.37% (272-count max) to 1.36% (73-count max) of max. At the 8% base the ±5%-of-target band is ±0.4% of max, which is 0.29 to 1.09 counts (arithmetic): below one count for weaker pressers.
- **Noise.** Two-second hand-resting windows: SD 0.5 to 1.25 counts (P673, 6 windows); bench 1.2 to 1.5 counts (baseline Section 4.8 h). Hold SD on Stairs treads and Tide slack: 0.5 to 2.1 counts raw, 0.4 to 2.0 after a 10 Hz low-pass, CV 1.6 to 8.7%. Hold variability is one to two times the floor.
- **Tremor band.** SD of 1.5 Hz high-passed force in 8 to 12 Hz: 0.22 to 0.85 counts in active runs (mostly 0.22 to 0.35), 0.17 to 0.22 in idle runs, 0.19 to 0.32 in resting windows. Healthy physiological tremor at these forces is at the floor. The 3 to 12 Hz spectral peak sat at 3 to 5 Hz, the band of voluntary corrections.
- **Enslaving.** Notebook-style index: -0.32 to +0.13; Park-style index (each other pad in counts on total force): -0.01 to +0.33, same runs. Negative slopes mean neighbouring pads unload as the task finger presses, a posture effect a fixed-posture rig would not show.
- **Corridor against wave.** Slow breath's amplitude (6% of max) is smaller than its corridor half-width (8%): a finger held still at 14% scores time in corridor 1.0. On Swell and Beach waves a motionless finger scores 0.65 and 0.61 (arithmetic). F4 cannot fail on level 1.
- **In-game smoothing.** `fsr.value_alpha` 0.35 at 200 Hz gives a time constant of 11.6 ms, a delay of 9.3 ms and a -3 dB point near 14 Hz (arithmetic). Research numbers come from `raw.csv`, so this touches only the display and the in-game score.

---

## 2. New literature (mainly 2020 to 2026, plus classics the note lacks)

### 2.1 Isometric force control in PD

- **[N9 Vaillancourt 2001, Exp Brain Res]** 8 PD vs 8 controls (68 to 80 y), precision grip held at 25% MVC for 20 s while visual feedback was sampled from 0.2 to 25.6 Hz. Minimal visual processing time about 160 ms in both groups; corrections near 1 Hz in both; the amplitude of the 1 to 2 Hz corrective process was larger in PD and tracked their extra variability. A classic the note lacks, and it names a band (1 to 2 Hz) the notebook never computes. ABS.
- **[N1 Lee 2026]** Early PD vs healthy older adults, bimanual handgrip at 10% and 40% MVC. PD produced less force, more error and variability, more regular force and weaker bilateral synergy; worse rigidity and tremor went with worse control. Sample size not in the abstract. ABS.
- **[N3 Daniels 2025]** 57 PD (ON) vs 22 older adults, rapid index abduction pulses to 20 to 60% MVC. 68% of PD had segmented force rises (median two or more segments, from zero crossings of the second derivative). Segmented PD were slower than unsegmented PD and controls; unsegmented PD did not differ from controls. ABS.
- **[N4 Daniels 2026]** 16 PD (ON) vs 12 older adults, pulses to 40% MVC. Force segments tracked EMG bursts (ρ 0.84) and peak rate tracked initial EMG (ρ 0.83), so force alone can stand in for EMG. ABS.
- **[N11 Spirduso 2005]** 10 PD vs 10 older adults, isometric tracing; after separating tremor, PD force errors remained. ABS.
- **[N10 Inzelberg 2008]** 39 early to moderate PD, on-screen visuomotor tracking. Tracking measures correlated with total UPDRS more than with its hand items, and most with gait and posture; the authors read the deficit as largely executive. Relevant because a tracking deficit may not be a pure hand measure. ABS.
- **[N6 Salmon 2023]** 30 mild PD (H&Y mean 1.1, ON) vs 24 controls: upper-limb strength 22% lower on average. Normalising targets to each person's max hides this, so strength needs its own number. ABS.
- **[N2 Afsharipour 2026]** 10 PD, ankle dorsiflexion 40 s at 10 to 30% MVT, OFF and ON. OFF, the coefficient of variation rose over the contraction; medication lowered it. Ankle, small sample. ABS.
- **[N12 de Freitas 2020]** 13 levodopa-naïve PD vs 13 controls, single- and multi-finger pressing. Lower maximal force and lower force-stabilising synergy before any levodopa; one dose did not restore it. ABS.
- **[N13 Lewis 2016]** 20 asymptomatic welders vs 13 controls: the multi-finger synergy index was lower in the left hand without any UPDRS or pegboard difference. A pointer that four-finger tasks can see basal ganglia change before clinical scales do. Not PD. ABS.
- **[N14 Burciu 2016]** 112 people scanned a year apart during a unimanual grip force task: PD lost putamen and M1 activity over one year; controls did not. Force tasks are established probes of PD progression in imaging. ABS.
- **[N8 Gao 2026]** 20 early PD vs 18 controls, grip tracking under low, medium and high visual gain with EEG. PD tracked worse at every gain. A reported 100% classification accuracy on 38 people signals overfitting. The first PD study with gain conditions I found. ABS.
- **[N7 Chau 2026]** 95 healthy adults (21 to 79 y) and 34 PD, Adelaide: nigrosome-1 MRI against grip-lift, pinch MVC, maximal finger tapping and tremor; only a healthy pegboard effect survived correction. Exploratory; an Australian group working on the same measures. ABS.
- **Unverified:** Pinto Neto 2026 (Arch Gerontol Geriatr Plus 3:100309; visual feedback, hand dominance, severity) still has no readable abstract (Crossref record only, publisher blocked). META.

### 2.2 Finger tapping and bradykinesia

- **[N16 Williams 2023]** 21 movement disorder neurologists rated 133 finger-tapping videos (39 PD, 30 controls). MDS-UPDRS 3.4 agreement ICC 0.53 (linear model) and 0.65 (ordinal model); 53% of control videos were scored above 0. The paper reproduces item 3.4: tap the index finger on the thumb 10 times "as quickly AND as big as possible", scored on interruptions or hesitations, slowing and amplitude decrement. FT (introduction and Table 1) plus ABS.
- **[N17 Bologna 2023, "Redefining bradykinesia"]** Proposes that "bradykinesia" mean slowness only, with hypokinesia, decrement and hesitations as separate features of a "bradykinesia complex"; quotes the MDS criterion "slowness of movement AND decrement in amplitude or speed (or progressive hesitations/halts)". FT (partial).
- **[N18 Paparella 2026]** 192 PD OFF, 158 controls, 129 PD also ON; kinematic finger tapping. Slowness was the most common and most accurate single feature; combining features raised the probability of PD up to 95%. Levodopa improved performance but left the pattern of abnormalities unchanged. ABS. Large sample.
- **[N19 Paparella 2023]** 44 PD, 69 essential tremor, 77 healthy older adults. Raters agreed only fairly (Fleiss κ 0.32); kinematics overlapped heavily; PD showed irregular rhythm and a sequence effect. ABS.
- **[N20 Bologna 2016]** 14 drug-naïve early PD, 11 advanced PD, 20 controls. Early PD were slower and smaller and had a sequence effect; advanced PD had no sequence effect; selegiline improved speed and amplitude, not the sequence effect. ABS.
- **[N21 Ling 2012]** 15 PD, 9 PSP, 16 controls, 15 s taps. Amplitude slope -0.20°/cycle in PD OFF against 0.01 in PSP ("hypokinesia without decrement"). A classic the note lacks. ABS.
- **[N22 Taylor Tavares 2005]** 33 PD, repetitive alternating finger tapping (RAFT) on an engineered keyboard; metrics correlated with UPDRS motor, mostly bradykinesia; medication and STN DBS improved them. ABS.
- **[N23 Wilkins 2022]** 96 PD (OFF) and 42 controls. Index and middle finger on adjacent keys, alternate press and release as fast and regularly as possible for 30 s, eyes closed with white noise. Six metrics (press amplitude and its CV, inter-strike interval and its CV, release slope, dwell time). Against MDS-UPDRS III: amplitude r -0.38, interval CV r 0.36; release slope against rigidity ρ -0.43. Tracked progression over years in 18 people. The closest published template for tapping on this rig. FT-S.
- **[N24 Trager 2020]** 16 PD OFF vs 11 controls, 30 s RAFT: key release speed slower in PD and correlated with lateralised rigidity (r -0.58). A release-speed measure from tapping, which a force pad gives directly. ABS.
- **[N26 Maetzler 2015]** 16 early and 17 mid-stage PD, 18 controls, finger tapping on a force transducer (Q-Motor "digitomotography"). Variability measures separated PD best; over 12 months nothing but laterality changed. The one PD study of tapping on force sensors found. ABS.
- **[N27 Teismann 2022]** 726 community adults on Q-Motor force tapping and grasp-lift: older age slower, men faster and more regular. Norms for force-transducer tapping. ABS.
- **[N28 Hasan 2019]** BRAIN tap test, 61 PD vs 93 controls: a velocity-score slope (cut-off -0.002) detected the sequence effect with 58% sensitivity and 81% specificity (65% and 88% in validation); all parameters separated ON from OFF. ABS. Verifies the movement-disorders.md entry.
- **[N29 Akram 2022]** Distal finger tapping, 55 PD vs 65 controls: KS20 AUC 0.90 (79% sensitivity at 85% specificity); with the BRAIN test AUC 0.95; KS20 against MDS-UPDRS finger tapping r -0.40. ABS. Verifies the movement-disorders.md entry.
- **[N30 Heldman 2014; N31 Heldman 2017]** In DBS patients, sensor-based tapping had higher ICCs and lower MDCs than blinded clinician ratings for speed, amplitude and rhythm (not for tremor), in clinic and at home. ABS both.

### 2.3 Digital biomarkers and how they are validated

- **[N33 Goldsack 2020]** The V3 framework (verification, analytical validation, clinical validation). It is the cleanest way to say what a healthy study can and cannot deliver. ABS.
- **[N34 Virameteekul 2026]** Systematic review of digital tools as drug-trial outcomes in PD: 42 studies, 26 tools including force-sensing systems; only one (Opal) reached level 1a evidence; the PD Kinetigraph, Actiwatch and Roche app reached 1b. ABS.
- **[N35 Lipsmeier 2018]** 44 PD and 35 controls, smartphone tests: average test-retest ICC 0.84; abnormalities seen even where the matching MDS-UPDRS item was scored 0. ABS.
- **[N36 Lipsmeier 2022]** 316 early PD. Alternate tapping of two on-screen buttons with the index finger, 20 s per hand: tapping variability ICC 0.84 (left) and 0.88 (right), and ρ 0.32 and 0.37 with item 3.4. Those ICCs compare two-week averages of daily tests, not single sessions. FT-S.
- **[N37 Taylor 2025]** PASADENA trial: bilateral speeded tapping variability was among the digital measures that progressed less on prasinezumab (exploratory). ABS.
- **[N38 Hermle 2025]** Ataxia, Q-Motor: 2-week test-retest ICC 0.91 to 0.99; a digital reaching measure needed 33 people to detect one-year change against 79 for the clinical scale and 214 for the nine-hole peg test. Not PD, but the clearest numbers on why instrumented measures cut sample sizes. ABS.
- **[N39 Horváth 2015]** 260 patients: the clinically important change on MDS-UPDRS III is -3.25 points (improvement) and +4.63 (worsening). Anchor for any PD pilot. ABS.
- **[N32 Broeder 2023]** 32 PD, unsupervised smartphone tapping at home for 7 days: ICC 0.707 to 0.975 ON; learning effects over the week; ON against OFF AUC 0.72 to 0.80 on the right hand. ABS.

### 2.4 Early and prodromal PD

- **[N40 Postuma 2012]** 78 people with idiopathic REM sleep behaviour disorder (RBD), 20 converted. UPDRS left normal values about 4.5 years before diagnosis; the alternate-tap test about 8.2 years and the Purdue pegboard 8.6 years before. Pegboard plus alternate tap reached 71 to 82% sensitivity and specificity 3 years before diagnosis. ABS.
- **[N41 Arora 2018]** 334 PD, 104 RBD, 84 controls, seven smartphone tasks including tapping: pairwise sensitivity and specificity 84.6 to 91.9%; tremor and voice discriminated best. ABS.
- **[N42 Krupička 2020]** 40 RBD, 25 de novo PD, 25 controls; first ten taps by motion capture. RBD differed from controls in amplitude and velocity decrement but not peak speed; decrement correlated with MDS-UPDRS motor (r 0.36 RBD, 0.60 PD). ABS.
- **[N43 Noyce 2017]** 208 people in PREDICT-PD: higher-risk people had higher MDS-UPDRS III (median 3 vs 1). ABS.
- **[N44 Elasfar 2025]** Systematic review, 39 studies: quantitative motor tests beat clinical scales in RBD; tapping showed the earliest signs and clear progression. ABS.
- **[N45 Delva 2025]** 95 RBD phenoconverters: MDS-UPDRS III and quantitative motor tests drifted from about 10 years before diagnosis and accelerated about 4 years before. ABS.
- Force control in RBD is in the note [A1.15 Tobin 2025].

### 2.5 Medication ON vs OFF

- Speed and amplitude respond; the decrement and the pattern do not: [N18 Paparella 2026], [N20 Bologna 2016], note [A2.6 Kang 2010; A2.8 Espay 2011].
- Tapping separates ON from OFF: [N28 Hasan 2019], [N32 Broeder 2023], [N22 Taylor Tavares 2005], [N49 Syeda 2022: 27 PD vs 24 controls, bimanual tapping; OFF smaller and more variable amplitude in the more affected hand; amplitude and stride length improved together with levodopa; ABS].
- Steadiness: [N2 Afsharipour 2026] improved ON (ankle), against note [A2.4 Stewart 2009] (no PD vs control difference) and [A1.4 Chung 2023] (no variability difference in the early PD hand).
- Synergies: a single first dose did not restore them in drug-naïve PD [N12], unlike chronic users (note A2.1).

### 2.6 More vs less affected hand

- Chung tested the more affected side [R3]; Davidson the dominant hand [R1].
- **[N46 Haaxma 2010]** 107 early drug-naïve PD vs 100 controls: pegboard AUC 0.97; the clinically unaffected limb of 42 hemiparkinsonian patients still separated from controls (AUC 0.73). Both hands carry signal. ABS.
- **[N47 Kishore 2007]** 27 early asymmetric PD: doing the same task with both hands improved the more affected side and worsened the less affected side, so bradykinesia should be tested one limb at a time. ABS.
- **[N48 Kwon 2026]** 23 drug-naïve PD, 23 SWEDD, 20 controls: tapping asymmetry (gyro) did not separate groups; forearm rotation did. ABS.

### 2.7 Visual feedback dependence

- Decay after vision is removed starts 1.5 to 2.5 s later, and is larger and faster in PD [R8, note A1.12]; Jo 2016 found faster exponential drop in PD (note A1.26).
- The PD visuomotor correction process at 1 to 2 Hz is amplified [N9].
- **[N50 Cosgrove 2021]** (Tasmania) PD with dementia relied most on vision when reaching; reliance grew with cognitive decline. ABS.
- Gain: [N8 Gao 2026] PD worse at every gain; no gain-by-group result for force error found.

### 2.8 Game-based or force-feedback training for PD hands

- Gap re-confirmed: a Europe PMC search on 30 September 2026 (Parkinson with force tracking, force control training, grip or pinch force training, visuomotor force, isometric force, force steadiness or force feedback, and training, practice, rehabilitation or intervention, 2015 to 2026) returned 3 records, none a force-tracking training trial.
- **[N51 Mahmood 2026]** Randomised, 7 PD, five days of button pressing with haptic resistance in mixed reality: tremor and bradykinesia improved against no resistance. Seven people. ABS.
- **[N52 Hashemi 2022]** RCT, 45 PD, 24 sessions of Kinect upper-limb VR (supervised or not) against conventional exercise: all three groups improved sensory and dexterity measures; the abstract reports no group was better. ABS.
- **[N53 Lazzarini 2024]** 15 RCTs (629 people): evidence on robot-assisted training, upper limb included, is very uncertain. ABS.
- **[N54 Ishaq 2026]** 11 studies (278) of head-mounted VR: quality of life improved; no pooled effect on UPDRS III. ABS.
- **[N55 Pastore-Wapp 2023]** 9 PD, video-game dexterity training plus brain stimulation: 100% adherence, usability 80%. Feasibility only. ABS.
- **[N56 Schaeffer 2019]** RCT, 40 PD, occupational therapy: self-reported function (MDS-UPDRS II) improved while Q-Motor tapping did not change. ABS.
- The anchor stays note [A5.1 Proud 2024]: a small dexterity gain from hand training (SMD 0.26).

### 2.9 Reliability and design methods

- **[N57 Walter 1998]** sample size for testing an ICC; **[N58 Bonett 2002]** sample size for a target interval width. ABS both. Section 4.4 gives exact numbers.
- **[N60 Oomen 2017]** Meta-analysis, 20 studies: a large age effect on steadiness (pooled r 0.67), varying with muscle group, distal vs proximal and force level. ABS.
- **[N61 Häger-Ross 2000]** 10 adults: thumb, index and little finger moved more independently than middle and ring; the dominant hand was not more independent. A healthy known effect for the enslaving measure. ABS.
- **[N62 Shinohara 2003]** 12 young vs 12 older adults: enslaving was smaller in older adults and women and scaled with peak force. So enslaving must be read against strength. ABS.
- **[N63 Guadagnoli 2004]** Challenge point framework: difficulty should match skill for learning. Relevant to training, not to measurement. ABS.

### 2.10 Where sources disagree

1. **Sensor update rate**: SingleTact manual (up to 120 Hz; 50 to 120 Hz as shipped) against the same manual's 140 to 4000 Hz converter and against the rig's data (fresh values at 200 Hz). Settle with the frame index.
2. **Does PD use prediction?** Day 1984 and Bloxham 1984 (note A4.3, A4.4): yes, lag falls on repeated patterns. Davidson 2026 [R1], citing Flowers 1978: PD show similar error on regular and irregular waves, as if every wave were unpredictable. Flowers 1978 itself is unread (note E3).
3. **Is decrement a PD hallmark?** Yes in early PD and against PSP [N20, N21, N42]. Absent in advanced PD [N20]; slowness, not decrement, was the most accurate single feature [N18]; raters disagree on it [N16, N19].
4. **Does medication fix steadiness?** Yes [N2]; no difference to fix [A2.4 Stewart 2009; A1.4 Chung 2023].
5. **Asymmetry**: more affected hand differs [N49]; unaffected limbs also abnormal [N46]; tapping asymmetry did not separate PD from SWEDD [N48].
6. **Digital measures and clinical scores**: sensors are more reliable than raters [N30, N31, N16] yet correlate only modestly with MDS-UPDRS (ρ 0.12 to 0.71 [N36]; r -0.38 to -0.40 [N23, N29]). Some tracked progression [N23, N38]; others missed change [N26, N56].
7. **Segmentation**: in ballistic pulses it marks a PD subgroup with good reliability [note A1.6; N3]; Force Pilot's pauses on slow guided ramps partly count normal visual correction (note E5). Same word, different construct.

---

## 3. Protocol: running Force Pilot for PD research

### 3.0 What Force Pilot could give PD research

- One rig that records four fingers at once while one flies: release against generation, amplitude scaling, terminal settling and enslaving in the same run.
- Unlike grip devices, it can host four-finger synergy tasks, which are abnormal before levodopa [N12] and in at-risk groups [N13].
- The same pads can host a force-based tapping task (Section 3.7), the test clinicians use most [N16].
- EEG markers already run with every run (`force_pilot.py` sends run and segment bytes), which matches the force-task imaging and EEG line of PD work [N14; N15 Chung 2018, ABS: exaggerated SMA beta desynchronisation OFF, reduced by levodopa, during a ballistic movement].
- Low cost and game framing, which suits repeated measurement; averaging repeats is what gives digital tests their high ICCs [N36].

### 3.1 First rule: keep the pre-registered study as it is

`healthy_one_hand_v3` fixes Force Pilot at one climb of the 12-level ladder per pass, with its corridors, 8 s preview, gain 1.0, music on and the median-of-three max press. Any change to levels, durations, preview, gain, probe or scoring changes the task and breaks comparability inside the study. Everything below that changes the task goes in a **separate research preset**, used after the healthy collection or with other people. Analysis additions (Section 6, ADD-ANALYSIS) are safe now.

### 3.2 Which ladder levels match published PD tasks

| Level | Closest PD task | What differs |
|---|---|---|
| 1 Slow breath (0.15 Hz, 8 to 20%, index) | Brewer and Pradhan sine: 7.5 s period (0.133 Hz), 12.5 s preview, 3 min [R5] | 13 s long; corridor wider than the wave |
| 3 Swell (0.2 Hz, 8 to 26%, ring) | Davidson 2026: 0.2 Hz, 10 to 30% MVC, 10 × 32 s, ~4 s preview, 1 to 2 familiarisation trials [R1] | 15 s, one run per pass, ring finger, 8 s preview, corridor |
| 2 Tide (5 %/s to 28%, 3 s hold) | Davidson 2024 and 2025: 0 to 35% in 3.3 s (~10 %/s), 5 s hold, release, terminal phase at 0% [R2] | half the rate, shorter hold, never returns to zero, 1 s terminal |
| 7 Heartbeat (2 s pulses, 1 s rest, 10 to 25%) | Neely 2013, Chung 2023: 2 s on, 1 s off at 15% MVC, as fast as possible [R3] | guided raised cosine; peak rate 23.6 %/s against ballistic 38 to 57 %MVC/s in controls |
| 4 Stairs (2.2 s treads) | Steady holds at 5 to 50% MVC for 20 s [A1.12 to A1.14]; 15% for 120 s [R4] | 1.1 s analysable per tread |
| 10 to 12 multisines | Brewer and Pradhan pseudorandom, no preview, 3 min [R5] | 8 s preview, 14 s |
| 8 Dunes (fast drop) | Chung relaxation, Wing release | guided 12 %/s drop |
| 5 Hills | Naik ramps (stroke) | no hold |

Swell and Slow breath are the only near matches, and even they differ in length, finger, preview and scoring. Force Pilot has no ballistic pulses, no blank, no no-preview target and no tapping.

### 3.3 A research preset (`pd_reference`), in priority order

Each block names its source. Times are arithmetic, per hand.

1. **Max press** (Section 3.4). About 3 min for index and middle.
2. **Davidson sine.** 0.2 Hz, 10 to 30% of max, 32 s trials, 8 trials (Davidson ran 10), 15 s rest, ~4 s preview and ~5 s history, one or two familiarisation trials, index finger [R1]. Scored against the centre line, no corridor, so gain is not shaped by the corridor (note E5). About 6.5 min.
3. **Davidson ramp.** 0 to 35% at about 10 %/s, 5 s hold, release at the same rate, 3 s terminal at rest level, 8 trials, 15 s rest [R2]. Gives release vs generation, terminal settling and iSD. About 4 min.
4. **Ballistic pulses.** "As fast as possible" to 15% of max, 2 s on and 1 s off, 3 blocks of 10 [R3; A1.5 Neely 2013]; optionally 20 to 60% targets for rate scaling and segmentation, where 50 or more pulses are needed for ICC above 0.7 (note A7.11 Bellumori 2011) [N3]. This is the only way to reach the slowness deficit (Section 1.1 row 7). About 3 min.
5. **Tapping** (Section 3.7). About 2.5 min.
6. **Feedback removal.** Hold 15 to 20% of max, 5 s with vision then 8 s blank, 4 trials. Decay begins 1.5 to 2.5 s after the blank [R8], so shorter blanks miss it. Report decay slope and CV with and without vision (note A7.2 Tracy 2015). About 1.5 min.
7. **Paced repetition for the sequence effect.** 20 squeezes at 1.25 Hz to 30 to 50% of max, once with and once without feedback; slope over the first 20 (note A2.7 Tinaz 2016). About 1 min.
8. **No-preview pseudorandom.** 45 to 60 s multisine with only the current target shown; lag bounded at 5 s and set to the maximum when r is under 0.35, as Brewer did [R5]; an optional counting-backwards minute for dual-task cost (note A1.19). About 2 min.
9. **Four-finger synergy** (optional, research only): total-force ramp and steady tasks with feedback on total force (note A1.22, A2.1; N12). About 3 min.

Blocks 1 to 5 take about 19 min per hand; all nine about 26 min. For PD OFF testing, keep blocks 1 to 5 and add 6 to 9 only if time and fatigue allow. Music off (note D3), gain fixed at 1.0, fixed order within a person, block order counterbalanced across people.

### 3.4 Maximum press

- Current: median of three presses, at least 0.15 s long, at least 0.3 s quiet between (`MaxPressProbe`); values 1.4 to 6.1 N (Section 1.4).
- Literature: highest of three MVCs with 1 to 2 min rest [R1, R2]; mean of three peaks with 5 s rest [R3]; best of three to five [R4].
- Research preset: three presses of 3 to 5 s with a fixed instruction and encouragement, 30 to 60 s rest, keep the highest; store newtons; warn if a press nears the calibrated range (511 counts above zero is 10 N [N64]).
- Add an independent strength number (pinch gauge or dynamometer): PD are about 22% weaker even when mild and ON [N6], and a pad-limited max will not show it.
- Bench test first (Section 6 item 8): check what share of a fingertip-sized load the 8 mm sensing area actually sees. The manual's conversion assumes load spread evenly over the sensor head [N64].

### 3.5 Visual gain and preview

- Keep gain at 1.0 and fixed; report the visual angle of 1% of max (the plot is 440 px for 40% of max, 11 px per 1%) at the viewing distance used.
- Gain as a variable belongs to its own experiment: PD tracked worse at all gains [N8]; magnification made older hands more variable at very low force (note A7.7 Fox 2013).
- Preview: about 4 s for sines and ramps, to match Davidson [R1]; none for the pseudorandom block, to match Brewer and Pradhan [R5]. Force Pilot's 8 s preview lets periodic waves be flown ahead (note C9).

### 3.6 Feedback removal

Section 3.3 block 6. The retired Lighthouse (16 s at a few percent of max) failed on playability. The research version holds above the noise floor (15 to 20% of max), splits each trial into 5 s with vision and 8 s blank, and repeats four times. Scored as decay rate after the first 2 s of blank, and as the CV with and without vision.

### 3.7 Tapping: add it, as its own mode

**Recommendation:** yes, as a separate mode, not inside Force Pilot.

- Finger tapping is the core clinical bradykinesia test [N16, N17].
- Keyboard and smartphone versions are validated with published reliability [N28, N29, N36] and one force-transducer version exists [N26, N27].
- Force Pilot cannot measure slowness, because it prescribes the speed; slowness was the most accurate single PD feature [N18].
- Keeping it separate leaves the pre-registered study untouched and keeps the constructs apart.

Design on the existing pads:

- **Single-finger speed:** index, two 15 s bouts per hand, "tap as fast and as firmly as you can, lift each time". This matches the DFT (20 s) [N29], Ling's 15 s trials [N21] and Q-Motor [N26].
- **Alternating index-middle (RAFT analogue):** 30 s, as fast and regular as possible, screen blanked, as in QDG [N23, N24].
- **Metrics:** tap count and rate; inter-tap interval mean and CV; dwell (contact) time; peak force per tap and its CV; release slope (force fall rate, the force analogue of key release speed [N24]); slopes of peak force and interval across taps (decrement [N20, N28, N42]); hesitations as intervals over twice the bout median (a device norm).
- **Tap detection:** hysteresis thresholds in percent of the finger's own max.
- **Say plainly:** peak force is not finger excursion, so a force decrement is an analogue of the clinical amplitude decrement. The nearest force evidence is Tinaz's grip-peak decrement (note A2.7).
- An existing design, "Tap Sprint", is already in `movement-disorders.md` Section 8 Mode A.

### 3.8 Repeats needed for reliability

- Published protocols: 10 trials of 32 s [R1]; 3 × 17 s per level [R7]; 50 or more pulses for ICC above 0.7 (note A7.11); two-week averages of daily tapping for ICC 0.84 to 0.88 [N36].
- Force Pilot gives one run per level per pass, so any per-level PD measure rests on two runs per person across the sitting.
- Spearman-Brown (arithmetic): if one run has ICC 0.4, averaging 6 runs gives 0.8; at 0.5 it takes 4; at 0.6, 3.
- The healthy data can estimate single-run ICC per level from pass 1 against pass 2, which tells a PD study how many runs each measure needs (Section 6 item 2).

### 3.9 Which changes alter the pre-registered study

| Change | Alters the study? | Where it belongs |
|---|---|---|
| New or re-scored measures from existing `raw.csv` | No | ADD-ANALYSIS now |
| Bench tests (cross-talk, load geometry, newton slope) | No (no participants) | Bench now |
| Longer runs, new levels, ballistic pulses, blanks, preview change, gain change, music off | Yes | RESEARCH-PRESET |
| New max-press procedure | Yes (moves every target) | RESEARCH-PRESET; GAME-CHANGE only after collection |
| Tapping mode | Not if kept out of the battery | New mode, outside the battery |
| Forwarding the SingleTact frame index | Changes the serial format, no task change | GAME-CHANGE after collection |

---

## 4. Feasible results for this thesis without a PD cohort

### 4.1 Frame

In V3 terms [N33], the healthy study delivers **verification** (what the pads measure, with what noise, resolution and rate) and part of **analytical validation** (do the algorithms return known healthy effects, and how repeatable are they within a sitting). It cannot deliver clinical validation. Saying this in one sentence protects every result.

### 4.2 The strongest thesis results, in order

1. **Measurement floor and measurability table.** For every `pd_*` measure:
   - the pad noise and quantisation in % of each person's max;
   - the between-person SD against that floor;
   - within-session ICC, SEM and MDC95, with the practice shift;
   - a verdict: usable, borderline, or at the floor.

   Section 1.4 already predicts some verdicts: hold CV, TWR5 at low targets and 8 to 12 Hz tremor are at or near the floor; MAE, gain, lag class and the release ratio are well above it. This table is the most useful thing the thesis can hand a PD study, and it needs no patients.
2. **Reliability with the practice shift** (T2, T3 plus exploratory `pd_*`), and a run-count projection per measure (Section 3.8).
3. **Known-effect checks F1 to F4 and the frequency response** (gain falling and lag rising with frequency, periodic against non-periodic lag). The note's C2 and C9 predictions sit here.
4. **Device values beside published healthy values, only where comparable:**
   - the release-to-generation RMSE ratio on sines, where the normaliser and Davidson's time term cancel;
   - Swell gain against 0.83 in young adults;
   - rise and fall TWR5 against 0.47 and 0.52.

   The notebook currently uses an MAE ratio; add the RMSE ratio (Section 6 item 4).
5. **Feasibility**: completion, idle and voided runs, time, max-press problems.

A check on Davidson's RRMSE (arithmetic, supports note E3): young adults reproduced 83.4% of a 10% MVC half-amplitude with near-zero phase error, so amplitude alone gives RMSE of about 1.2% MVC. Their published RRMSE of 0.38 to 0.42 then fits RMSE of about 2.1 to 2.3% MVC if their sum over 30 Hz samples was divided by time in seconds (a factor √30 = 5.48). If it was divided by the sample count, RMSE would be 11 to 13% MVC, larger than the wave's own half-amplitude, which cannot fit a gain of 0.83. Compare ratios, not absolute RRMSE.

### 4.3 Known-group checks inside a young healthy sample

- **Finger individuation:** middle and ring task fingers should show more unintended neighbour force than index and little [N61], read against strength [N62]. This only means something after the bench cross-talk test and the Park-style index (Section 6 items 7 and 8), and it is confounded by level (each finger flies different waves).
- **Force level:** CV falls from very low to moderate force (note A7.1 Moritz 2005). On this rig pad noise produces the same trend (noise over a larger mean), so only the noise-corrected CV can test it.
- **Frequency and predictability:** error rising with bandwidth (F1), lag longer on non-periodic waves (F2).
- **Handedness:** left-handers play their non-dominant hand; finger independence did not differ by dominance [N61]. Exploratory at the expected one-in-ten.
- **Age:** a student sample is too narrow. If any older volunteers (for example staff over 60) could sit, age effects on steadiness are large [N60] and release impairment in older adults was g 2.69 with 10 per group (note A1.3). Plan for d near 1.0, since small studies overstate effects: about 17 per group (arithmetic). This changes the sample, not the task, so it is the owner's decision.

### 4.4 Sample sizes (arithmetic; normal approximations unless stated)

| Question | Needed |
|---|---|
| Describe the healthy range (median, IQR, every point) | Any n; at n = 10 the extremes sit near the 9th and 91st percentiles (baseline Section 2.1) |
| A proper reference interval (2.5th to 97.5th percentile) | The sample minimum falls under the true 2.5th percentile with 95% probability only from n = 119, so about 120 |
| ICC precision (exact F interval at the true value) | ICC 0.8: n 10 gives about 0.41 to 0.95; n 20: 0.57 to 0.92; n 30: 0.62 to 0.90; n 50: 0.67 to 0.88. ICC 0.9 at n 10: 0.67 to 0.97 (matches the baseline study's simulated 0.67 to 0.98) |
| Test ICC against a floor, two measurements, one-sided 0.05, power 0.8 (exact F test; Walter's approximation agrees within 1) | 0.8 vs 0.5: 22; 0.8 vs 0.6: 39; 0.85 vs 0.6: 21; 0.9 vs 0.7: 19 |
| Practice shift, paired, two-sided 0.05, power 0.8 | dz 1.0: 10; 0.8: 15; 0.5: 34 |
| F3 equivalence (margin ±2% of max, true difference 0, 5% each side, power 0.8) | About 8.6 × (SD of the paired difference / 2)², plus one or two: SD 1.5% of max gives about 6 to 7 people, SD 3% about 21 |

### 4.5 A future PD pilot

- **Design:** cross-sectional PD against age-matched controls, then a retest within one to two weeks for reliability in PD.
- **Who and how:**
  - H&Y I to III;
  - MDS-UPDRS III by a trained rater (note A2.10);
  - OFF after 12 h or more, as Davidson, Chung and Tobin did [R2, R3, R4], and ON in a second session;
  - more affected hand first, then the less affected, one hand at a time [N47, N46];
  - a cognitive screen, because tracking loads executive function [N10, N50];
  - the `pd_reference` preset and the tapping mode.
- **Primary measures, pre-registered:** release vs generation (per phase RMSE ratio and %TWR); sine gain; terminal settling; ballistic relaxation rate; RAFT release slope and interval CV; decay without vision. Correct for multiple comparisons; the device produces dozens of measures, and Brewer fitted 36 predictors on 26 people (note A1.20).
- **Group difference, two-sided 0.05, power 0.8:**

  | Effect size source | Size | Per group |
  |---|---|---|
  | Davidson 2025 release %TWR (note A1.2) | g 1.24 | about 11 |
  | Davidson 2026 amplitude, PD vs older adults (arithmetic from note A1.1 means and SDs) | d about 1.2 | about 12 |
  | Chung 2023 relaxation (arithmetic) | d about 1.17 | about 13 |
  | Tobin 2025 CV (arithmetic from note A1.15) | d about 0.77 | about 27 |

  Small samples overstate effects, so plan on d 0.8: 25 to 26 per group.
- **Correlation with MDS-UPDRS III** (two-sided 0.05, power 0.8): r 0.5 needs 29; r 0.4 needs 47; r 0.35 needs 62. Published digital measures sit at r 0.3 to 0.4 [N23, N29, N36].
- **Reliability in PD:** 30 or more people; at an ICC of 0.8 that gives an interval of about 0.62 to 0.90 (Section 4.4).
- **Change over time:** relate change to the MCID of 3.25 and 4.63 points [N39].
- **Prodromal (RBD):** a much larger undertaking (104 RBD in [N41], 40 in [N42]) and a sleep clinic partner.
- **Local groups** working on these measures: Adelaide [N7], Tasmania [N16, N50], Sydney (note A5.3), Melbourne (note A5.1).

---

## 5. Risks, and claims the thesis must not make

### 5.1 Device limits

| Limit | Measured or specified | Consequence |
|---|---|---|
| Resolution | 1 count = 0.0195 N nominal; 0.37 to 1.36% of max in pilot | ±5%-of-target bands at 8% are under one count for weaker pressers; TWR5 at low targets is quantisation |
| Noise | Bench 1.2 to 1.5 counts; resting hand 0.5 to 1.25 counts | Hold SD is one to two times the floor; CV mostly noise |
| Tremor band | 8 to 12 Hz force in runs ≈ idle and resting floor | Healthy tremor unmeasurable; PD tremor at 4 to 6 Hz is larger but untested here |
| Sampling | Fresh 200 Hz readings (0 to 3% repeats when force moves fast); manual says up to 120 Hz | Adequate for 4 to 12 Hz; confirm with the frame index |
| Smoothing | In-game EMA 11.6 ms time constant (arithmetic); research uses raw | Display lag adds to the measured lag with the unmeasured screen delay; within-device lags only |
| Max press | 1.4 to 6.1 N; median of three short presses | Not an MVC; percent of max is not %MVC; between-person max partly reflects finger placement and pad loading |
| Load geometry | Manual assumes even load over the 8 mm sensing head | Newtons uncertain; the ratio holds only if loading is the same in the probe and the run |
| Cross-talk | Unmeasured; bench discards the other pads | Enslaving mixes neural spill-over, hand posture and mechanics (pilot slopes change sign) |
| Drift | 2% of full scale per minute at half load (spec); runs 13 to 16 s, re-tared each run | Small inside a run |
| Output range | 0 to 511 counts is 0 to 10 N calibrated; overload beyond 3× full scale can damage [N64] | Irrelevant at pilot forces; matters for any MVC protocol |

### 5.2 Task limits

- The corridor is wider than the wave on level 1: a motionless finger scores 1.0.
- The corridor rewards being inside, not on the line, so gain partly reads the corridor (note E5).
- Fixed order confounds level with time on task and with finger.
- One run per level per pass.
- 8 s preview; no ballistic, blank, tapping or no-preview conditions.
- Music plays during blocks.

### 5.3 Claims not to make

1. That Force Pilot detects, diagnoses, stages or monitors PD, or separates PD from other conditions.
2. That any healthy number is a normal range or cut-off (about 120 people would be needed for percentile bounds).
3. That percent-of-max values equal %MVC values in the literature, or that any newton figure is accurate before the mass bench check.
4. That the within-session ICC or MDC95 is day-to-day reliability or defines real change in a patient.
5. That hold CV, TWR5 at low targets, 8 to 12 Hz tremor or sample entropy describe physiology on this rig. They sit at or near the pad floor unless the noise-corrected analysis shows otherwise.
6. That the enslaving index is neural enslaving.
7. That the release-press result is a PD marker. In healthy adults it is a norm.
8. That Force Pilot trains or improves hand function in PD. No trial exists (Section 2.8). The general hand-training evidence is small [A5.1], and game trials were null or equal to conventional therapy [A5.3, A5.4; N52].
9. That pass 2 improvement is learning. It is performance within a sitting.
10. That Storm against Uncharted shows sequence learning.
11. That time in corridor compares across levels.
12. That published PD cut-offs (such as the BRAIN slope -0.002 [N28]) apply to this device.

---

## 6. Recommended changes, ranked

Evidence strength: **strong** (a systematic review, a large or repeated finding, or measurement practice), **moderate** (consistent small studies), **weak** (a single small study, or design logic).

1. **Measurability table with the pad floor.**
   - Estimate noise per pad per session from existing rest data (the 15 s mid-ladder rest, announce cards, idle non-task pads) as SD and spectrum.
   - Express it and the one-count step in % of each person's max.
   - Add noise-corrected SD and CV (√(SD² - σ²)) after a 20 Hz low-pass.
   - Flag any measure under 1.5 times the floor.

   Tag ADD-ANALYSIS. Evidence: strong. Files: `analysis/session_analysis.ipynb` (`force_tracking_runs`, `fp_pd_measures`, new `fp_noise_floor`, `sec_force_pilot_pd`, `FP_PD_SPECS`).
2. **Reliability decision study.** Single-run ICC per level (pass 1 against pass 2), SEM, MDC95 and practice shift for every `pd_*` measure, with a Spearman-Brown projection of runs needed for ICC 0.8. Tag ADD-ANALYSIS. Evidence: strong (method); moderate (for this device). Files: notebook (`_cohort_reliability_pd`, `COHORT_DESCRIBE_ONLY`, `sec_force_pilot_pd`).
3. **Thesis framing and device facts.**
   - V3 framing (Section 4.1).
   - The claim list (Section 5.3).
   - Device facts: max press 1.4 to 6.1 N, quantisation, measured update rate, level 1 corridor ceiling.
   - The RRMSE arithmetic (Section 4.2).

   Tag THESIS-TEXT. Evidence: strong. Files: thesis methods and limitations; `app/docs/research/healthy_baseline_study.txt` Section 1.8 claim limits.
4. **Literature-unit numbers already computed, plus the Davidson-comparable ratio.**
   - Export `nrmse` (per phase, normalised by the run's peak target), `twr5` and `twr5_max`.
   - Add the rise-to-fall RMSE ratio on sines, with Swell separately.

   Tag ADD-ANALYSIS. Evidence: moderate. Files: notebook (`fp_pd_measures`, `FP_PD_SPECS`, `FP_PD_COHORT`, `_cohort_force_pilot`).
5. **Tremor and steadiness as the literature measures them.**
   - Absolute 2 to 8 and 8 to 12 Hz power of raw force against the pad's floor spectrum [R5].
   - A new 1 to 2 Hz correction-band power [N9].
   - Steadiness after a 20 Hz low-pass [R7].
   - RMSE on 2 Hz low-passed force beside the raw RMSE.
   - Brewer-style lag handling (maximum when r is under 0.35) as a sensitivity row.
   - Keep the current shares as secondary.

   Tag ADD-ANALYSIS. Evidence: moderate. Files: notebook (`fp_tremor_bands`, `fp_pd_measures`, `tracking_lag_ms` caller).
6. **Missing Table B rows.** Row 6 iSD (SD of per-repeat RMSE across Hills up1/up2 and down1/down2, Dunes windward and slipface 1/2, Heartbeat beats 1 to 4, and pass 1 against pass 2) and row 12 turnaround errors at sine peaks and troughs. Tag ADD-ANALYSIS. Evidence: moderate for iSD (g -1.27 in [A1.2]); weak for turnaround. Files: notebook (`fp_pd_measures`, `FP_PD_SPECS`).
7. **Enslaving rework.**
   - Add Park's index: each pad in counts regressed on the four-pad total over the rising ramps [R6].
   - Split positive (co-activation) from negative (unloading) slopes; report per task finger.
   - Test the middle and ring over index and little order [N61].
   - Relabel the 0.07 to 0.09 reference as not comparable.

   Tag ADD-ANALYSIS. Evidence: moderate/weak. Files: notebook (`fp_enslaving`, `FP_PD_SPECS`).
8. **Bench: cross-talk, load geometry and newtons.**
   - Keep all four pads' means at every load step (cross-talk matrix).
   - Compare a fingertip-sized soft load with the centred coin (load sharing).
   - Run the pending mass slope so the max press can be reported in newtons with its accuracy.

   Tag ADD-ANALYSIS (bench tool; no participants, no game change). Evidence: moderate (manufacturer's load note [N64]). Files: `app/scripts/pad_bench.py` (`_reading`, `run_check`, characterisation).
9. **Documentation corrections.**
   - Research note: A1.15 Tobin tested OFF; D4 blank of 1 to 2 s too short (use 6 to 8 s); Table B row 7 to 20 to 80% transitions; C8 and C12 enslaving reference not comparable; C12 CV references not comparable on this rig.
   - `hardware/README.md` update-rate line.
   - Notebook: stale 12 Hz comment; floor note; `pulse_decrement` wording; the F3 in-session interval (95% vs 90%).

   Tag THESIS-TEXT. Evidence: strong (each is a verified fact). Files: `app/docs/research/new_modes/force-pilot-parkinsons.md`, `hardware/README.md`, notebook (`sec_force_tracking`, `continuous_floor_note`, `FP_PD_SPECS`, `sec_force_pilot_checks`).
10. **`pd_reference` research preset** (Section 3.3): max-press protocol, Davidson sine and ramp against the line, ballistic pulses, feedback-removal holds, paced repetition with and without feedback, no-preview pseudorandom, music off, a new ladder id so no block pools with `waves_v1`. Tag RESEARCH-PRESET. Evidence: moderate to strong per block (repeated small PD studies). Files: `app/config/default.yaml` (new preset and keys), `app/finger_rehab/game/modes/force_pilot.py` (research level table, pulse and blank section kinds, preview override), `app/finger_rehab/ui/force_pilot_screen.py` (preview length, blank rendering, line without corridor), notebook, tests.
11. **Tapping mode** (Section 3.7): single-finger speed and alternating index-middle on the pads, force-based rate, rhythm, dwell, release slope and decrement. Tag RESEARCH-PRESET (a new mode kept outside the battery). Evidence: strong clinical relevance [N16, N18, N23, N29, N36]; moderate for force pads [N26, N27]. Files: new mode under `app/finger_rehab/game/modes/`, a new screen, a config block, a notebook chapter; design basis `movement-disorders.md` Mode A.
12. **Four-finger synergy task.** Tag RESEARCH-PRESET. Evidence: weak to moderate (small samples [N12, N13], note A1.22, A2.1). Files: new level or mode, notebook.
13. **Forward the SingleTact frame index and sensor timestamp** (registers 128 to 131, already read), after data collection. Tag GAME-CHANGE. Evidence: moderate (manufacturer [N64]). Files: `app/arduino/firmware_on_device/lib/Sensor/Sensor.cpp`, `src/main.cpp`, the Python serial parser and raw logger, notebook.
14. **Sustained max press, highest of three, shown in newtons**, after data collection. Tag GAME-CHANGE. Evidence: moderate [R1 to R4]. Files: `app/finger_rehab/game/force_stream.py` (`MaxPressProbe`), `force_pilot.py` probe flow, `force_pilot_screen.py`.
15. **Easy levels where holding still cannot fill the corridor**, after data collection and under a new ladder id. Tag GAME-CHANGE. Evidence: weak (design logic). Files: `force_pilot.py` (`LADDER`, `level_sections`), notebook.

---

## 7. Sources

### New sources (not in the research note)

- N1. Lee H, Byun K, Park K, Kim R, Kang N. Bimanual isometric force control impairments in patients with Parkinson's disease. Prog Neuropsychopharmacol Biol Psychiatry. 2026;147:111723. DOI 10.1016/j.pnpbp.2026.111723. PMID 42049076. ABS.
- N2. Afsharipour B, Roy FD, Xie H, Schindle M, Ba F, Kong L, Gorassini M, Sankar T. Muscular torque variability in Parkinson's Disease with and without dopaminergic medication. Neurophysiol Clin. 2026;56(5):103190. DOI 10.1016/j.neucli.2026.103190. PMID 42526408. ABS.
- N3. Daniels RJ, Knight CA. Motor segmentation: a key neuromuscular impairment in people with parkinson's disease. Exp Brain Res. 2025;243(12):241. DOI 10.1007/s00221-025-07189-3. PMID 41176739. PMC12580443. ABS.
- N4. Daniels RJ, Knight CA. EMG analysis and correlates of motor segmentation in Parkinson's disease. J Electromyogr Kinesiol. 2026;89:103161. DOI 10.1016/j.jelekin.2026.103161. PMID 42097041. ABS.
- N6. Salmon R, Preston E, Mahendran N, Ada L, Flynn A. People with mild Parkinson's disease have impaired force production in upper limb muscles: a cross-sectional study. Physiother Res Int. 2023;28(1):e1976. DOI 10.1002/pri.1976. PMID 36266769. PMC10078520. ABS.
- N7. Chau MT, Agzarian M, Wilcox RA, Todd G. Association between nigrosome-1 appearance on MRI and fine motor function in healthy adults and people living with Parkinson's disease. J Neural Transm. 2026;133(7):1339-1355. DOI 10.1007/s00702-025-03047-2. PMID 41081873. ABS.
- N8. Gao Z, Lv S, Ran X, et al. EEG microstate features under visual feedback gain conditions exhibit high sensitivity in identifying early Parkinson's disease patients. J Neuroeng Rehabil. 2026;23(1):67. DOI 10.1186/s12984-026-01882-2. PMID 41555363. PMC12895987. ABS.
- N9. Vaillancourt DE, Slifkin AB, Newell KM. Intermittency in the visual control of force in Parkinson's disease. Exp Brain Res. 2001;138(1):118-127. DOI 10.1007/s002210100699. PMID 11374078. ABS.
- N10. Inzelberg R, Schechtman E, Hocherman S. Visuo-motor coordination deficits and motor impairments in Parkinson's disease. PLoS One. 2008;3(11):e3663. DOI 10.1371/journal.pone.0003663. PMID 18987752. PMC2576439. ABS.
- N11. Spirduso WW, Francis K, Eakin T, Stanford C. Quantification of manual force control and tremor. J Mot Behav. 2005;37(3):197-210. DOI 10.3200/JMBR.37.3.197-210. PMID 15883117. ABS.
- N12. de Freitas PB, Freitas SMSF, Reschechtko S, Corson T, Lewis MM, Huang X, Latash ML. Synergic control of action in levodopa-naïve Parkinson's disease patients: I. Multi-finger interaction and coordination. Exp Brain Res. 2020;238(1):229-245. DOI 10.1007/s00221-019-05709-6. PMID 31838566. ABS.
- N13. Lewis MM, Lee EY, Jo HJ, Du G, Park J, Flynn MR, Kong L, Latash ML, Huang X. Synergy as a new and sensitive marker of basal ganglia dysfunction: a study of asymptomatic welders. Neurotoxicology. 2016;56:76-85. DOI 10.1016/j.neuro.2016.06.016. PMID 27373673. ABS.
- N14. Burciu RG, Chung JW, Shukla P, Ofori E, Li H, McFarland NR, Okun MS, Vaillancourt DE. Functional MRI of disease progression in Parkinson disease and atypical parkinsonian syndromes. Neurology. 2016;87(7):709-717. DOI 10.1212/WNL.0000000000002985. PMID 27421545. ABS.
- N15. Chung JW, Burciu RG, Ofori E, Coombes SA, Christou EA, Okun MS, Hess CW, Vaillancourt DE. Beta-band oscillations in the supplementary motor cortex are modulated by levodopa and associated with functional activity in the basal ganglia. NeuroImage Clin. 2018;19:559-571. DOI 10.1016/j.nicl.2018.05.021. PMID 29984164. PMC6029579. ABS.
- N16. Williams S, Wong D, Alty JE, Relton SD. Parkinsonian hand or clinician's eye? Finger tap bradykinesia interrater reliability for 21 movement disorder experts. J Parkinsons Dis. 2023;13(4):525-536. DOI 10.3233/JPD-223256. PMID 37092233. PMC10357208. FT (introduction and Table 1) and ABS.
- N17. Bologna M, Espay AJ, Fasano A, Paparella G, Hallett M, Berardelli A. Redefining bradykinesia. Mov Disord. 2023;38(4):551-557. DOI 10.1002/mds.29362. PMID 36847357. PMC10387192. FT (partial).
- N18. Paparella G, De Riggi M, Cannavacciuolo A, et al. Analyzing the 'bradykinesia complex' in Parkinson's disease. Mov Disord. 2026;41(1):143-155. DOI 10.1002/mds.70082. PMID 41104587. PMC12882039. ABS.
- N19. Paparella G, Cannavacciuolo A, Angelini L, et al. May bradykinesia features aid in distinguishing Parkinson's disease, essential tremor, and healthy elderly individuals? J Parkinsons Dis. 2023;13(6):1047-1060. DOI 10.3233/JPD-230119. PMID 37522221. PMC10578222. ABS.
- N20. Bologna M, Leodori G, Stirpe P, et al. Bradykinesia in early and advanced Parkinson's disease. J Neurol Sci. 2016;369:286-291. DOI 10.1016/j.jns.2016.08.028. PMID 27653910. ABS.
- N21. Ling H, Massey LA, Lees AJ, Brown P, Day BL. Hypokinesia without decrement distinguishes progressive supranuclear palsy from Parkinson's disease. Brain. 2012;135(Pt 4):1141-1153. DOI 10.1093/brain/aws038. PMID 22396397. PMC3326257. ABS.
- N22. Taylor Tavares AL, Jefferis GS, Koop M, Hill BC, Hastie T, Heit G, Bronte-Stewart HM. Quantitative measurements of alternating finger tapping in Parkinson's disease correlate with UPDRS motor disability and reveal the improvement in fine motor control from medication and deep brain stimulation. Mov Disord. 2005;20(10):1286-1298. DOI 10.1002/mds.20556. PMID 16001401. ABS.
- N23. Wilkins KB, Petrucci MN, Kehnemouyi Y, et al. Quantitative digitography measures motor symptoms and disease progression in Parkinson's disease. J Parkinsons Dis. 2022;12(6):1979-1990. DOI 10.3233/JPD-223264. PMID 35694934. PMC9535590. FT-S.
- N24. Trager MH, Wilkins KB, Koop MM, Bronte-Stewart H. A validated measure of rigidity in Parkinson's disease using alternating finger tapping on an engineered keyboard. Parkinsonism Relat Disord. 2020;81:161-164. DOI 10.1016/j.parkreldis.2020.10.047. PMID 33157435. ABS.
- N26. Maetzler W, Ellerbrock M, Heger T, Sass C, Berg D, Reilmann R. Digitomotography in Parkinson's disease: a cross-sectional and longitudinal study. PLoS One. 2015;10(4):e0123914. DOI 10.1371/journal.pone.0123914. PMID 25902182. PMC4406446. ABS.
- N27. Teismann H, Schubert R, Reilmann R, Berger K. Effects of age and sex on outcomes of the Q-Motor speeded finger tapping and grasping and lifting tests: findings from the population-based BiDirect Study. Front Neurol. 2022;13:965031. DOI 10.3389/fneur.2022.965031. PMID 36247774. PMC9561931. ABS.
- N28. Hasan H, Burrows M, Athauda DS, et al. The BRadykinesia Akinesia INcoordination (BRAIN) tap test: capturing the sequence effect. Mov Disord Clin Pract. 2019;6(6):462-469. DOI 10.1002/mdc3.12798. PMID 31392247. PMC6660282. ABS.
- N29. Akram N, Li H, Ben-Joseph A, et al. Developing and assessing a new web-based tapping test for measuring distal movement in Parkinson's disease: a Distal Finger Tapping test. Sci Rep. 2022;12(1):386. DOI 10.1038/s41598-021-03563-7. PMID 35013372. PMC8748736. ABS.
- N30. Heldman DA, Espay AJ, LeWitt PA, Giuffrida JP. Clinician versus machine: reliability and responsiveness of motor endpoints in Parkinson's disease. Parkinsonism Relat Disord. 2014;20(6):590-595. DOI 10.1016/j.parkreldis.2014.02.022. PMID 24661464. ABS.
- N31. Heldman DA, Urrea-Mendoza E, Lovera LC, et al. App-based bradykinesia tasks for clinic and home assessment in Parkinson's disease: reliability and responsiveness. J Parkinsons Dis. 2017;7(4):741-747. DOI 10.3233/JPD-171159. PMID 28922169. ABS.
- N32. Broeder S, Roussos G, De Vleeschhauwer J, D'Cruz N, de Xivry JO, Nieuwboer A. A smartphone-based tapping task as a marker of medication response in Parkinson's disease: a proof of concept study. J Neural Transm. 2023;130(7):937-947. DOI 10.1007/s00702-023-02659-w. PMID 37268772. PMC10237522. ABS.
- N33. Goldsack JC, Coravos A, Bakker JP, et al. Verification, analytical validation, and clinical validation (V3): the foundation of determining fit-for-purpose for Biometric Monitoring Technologies (BioMeTs). NPJ Digit Med. 2020;3:55. DOI 10.1038/s41746-020-0260-4. PMID 32337371. PMC7156507. ABS.
- N34. Virameteekul S, Shin C, Hirczy SS, et al. Assessing digital health technologies for outcome measurement in Parkinson's disease drug trials: a systematic review. Mov Disord. 2026;41(1):40-62. DOI 10.1002/mds.70097. PMID 41175008. ABS.
- N35. Lipsmeier F, Taylor KI, Kilchenmann T, et al. Evaluation of smartphone-based testing to generate exploratory outcome measures in a phase 1 Parkinson's disease clinical trial. Mov Disord. 2018;33(8):1287-1297. DOI 10.1002/mds.27376. PMID 29701258. PMC6175318. ABS.
- N36. Lipsmeier F, Taylor KI, Postuma RB, et al. Reliability and validity of the Roche PD Mobile Application for remote monitoring of early Parkinson's disease. Sci Rep. 2022;12(1):12081. DOI 10.1038/s41598-022-15874-4. PMID 35840753. PMC9287320. FT-S (tapping results).
- N37. Taylor KI, Lipsmeier F, Scelsi MA, et al. Exploratory digital outcome measures of motor sign progression in Parkinson's disease patients treated with prasinezumab. NPJ Digit Med. 2025;8(1):365. DOI 10.1038/s41746-025-01572-8. PMID 40523921. PMC12170883. ABS.
- N38. Hermle D, Schubert R, Barallon P, et al. Digital outcomes of upper limb ataxia capture meaningful longitudinal change and treatment response. Mov Disord. 2025;40(11):2486-2496. DOI 10.1002/mds.70012. PMID 40888004. PMC12661631. ABS.
- N39. Horváth K, Aschermann Z, Ács P, et al. Minimal clinically important difference on the Motor Examination part of MDS-UPDRS. Parkinsonism Relat Disord. 2015;21(12):1421-1426. DOI 10.1016/j.parkreldis.2015.10.006. PMID 26578041. ABS.
- N40. Postuma RB, Lang AE, Gagnon JF, Pelletier A, Montplaisir JY. How does parkinsonism start? Prodromal parkinsonism motor changes in idiopathic REM sleep behaviour disorder. Brain. 2012;135(Pt 6):1860-1870. DOI 10.1093/brain/aws093. PMID 22561644. ABS.
- N41. Arora S, Baig F, Lo C, et al. Smartphone motor testing to distinguish idiopathic REM sleep behavior disorder, controls, and PD. Neurology. 2018;91(16):e1528-e1538. DOI 10.1212/WNL.0000000000006366. PMID 30232246. PMC6202945. ABS.
- N42. Krupička R, Krýže P, Neťuková S, et al. Instrumental analysis of finger tapping reveals a novel early biomarker of parkinsonism in idiopathic rapid eye movement sleep behaviour disorder. Sleep Med. 2020;75:45-49. DOI 10.1016/j.sleep.2020.07.019. PMID 32853917. ABS.
- N43. Noyce AJ, Schrag A, Masters JM, Bestwick JP, Giovannoni G, Lees AJ. Subtle motor disturbances in PREDICT-PD participants. J Neurol Neurosurg Psychiatry. 2017;88(3):212-217. DOI 10.1136/jnnp-2016-314524. PMID 27986830. PMC5529958. ABS.
- N44. Elasfar S, Hameed H, Ehgoetz Martens K. Motor features that distinguish isolated REM sleep behavior disorder patients from healthy controls: a systematic review. J Parkinsons Dis. 2025;15(7):1155-1193. DOI 10.1177/1877718X251359225. PMID 40888450. PMC13347522. ABS.
- N45. Delva A, Fereshtehnejad SM, Vo A, et al. Evolution of motor and nonmotor characteristics in an idiopathic/isolated REM sleep behavior disorder cohort. Neurology. 2025;105(7):e214108. DOI 10.1212/WNL.0000000000214108. PMID 40921020. ABS.
- N46. Haaxma CA, Bloem BR, Overeem S, Borm GF, Horstink MW. Timed motor tests can detect subtle motor dysfunction in early Parkinson's disease. Mov Disord. 2010;25(9):1150-1156. DOI 10.1002/mds.23100. PMID 20629141. ABS.
- N47. Kishore A, Espay AJ, Marras C, et al. Unilateral versus bilateral tasks in early asymmetric Parkinson's disease: differential effects on bradykinesia. Mov Disord. 2007;22(3):328-333. DOI 10.1002/mds.21238. PMID 17216641. ABS.
- N48. Kwon DY, Ko J, Kwon Y, Kim JW. Sensor-based assessment of asymmetry in upper limb bradykinesia among patients with Parkinson's disease and scans without evidence of dopaminergic deficit (SWEDD). Parkinsons Dis. 2026;2026:6400390. DOI 10.1155/padi/6400390. PMID 41928915. PMC13042346. ABS.
- N49. Syeda HB, Glover A, Pillai L, et al. Amplitude setting and dopamine response of finger tapping and gait are related in Parkinson's disease. Sci Rep. 2022;12(1):4180. DOI 10.1038/s41598-022-07994-8. PMID 35264705. PMC8907286. ABS.
- N50. Cosgrove J, Hinder MR, St George RJ, et al. Significant cognitive decline in Parkinson's disease exacerbates the reliance on visual feedback during upper limb reaches. Neuropsychologia. 2021;157:107885. DOI 10.1016/j.neuropsychologia.2021.107885. PMID 33965420. ABS.
- N51. Mahmood N, Bektic M, Li C, Ridgel A, Kim K. Investigating the effectiveness of haptic resistive force feedback to improve tremors in Parkinson's disease: a training impact study. IEEE J Biomed Health Inform. 2026;30(7):6270-6278. DOI 10.1109/JBHI.2025.3644234. PMID 41396751. ABS.
- N52. Hashemi Y, Taghizadeh G, Azad A, Behzadipour S. The effects of supervised and non-supervised upper limb virtual reality exercises on upper limb sensory-motor functions in patients with idiopathic Parkinson's disease. Hum Mov Sci. 2022;85:102977. DOI 10.1016/j.humov.2022.102977. PMID 35932518. ABS.
- N53. Lazzarini SG, Mosconi B, Cordani C, Arienti C, Cecchi F. Effectiveness of robot-assisted training in adults with Parkinson's disease: a systematic review and meta-analysis. J Neurol. 2024;272(1):22. DOI 10.1007/s00415-024-12798-z. PMID 39666104. ABS.
- N54. Ishaq S, Shah IA, Lei WF, Lee SD, Wu BT. Effectiveness of head-mounted virtual reality rehabilitation in individuals with Parkinson's disease: a systematic review and meta-analysis. Assist Technol. 2026;38(2):187-197. DOI 10.1080/10400435.2025.2604079. PMID 41503973. ABS.
- N55. Pastore-Wapp M, Kaufmann BC, Nyffeler T, Wapp S, Bohlhalter S, Vanbellingen T. Feasibility of a combined intermittent theta-burst stimulation and video game-based dexterity training in Parkinson's disease. J Neuroeng Rehabil. 2023;20(1):2. DOI 10.1186/s12984-023-01123-w. PMID 36635679. PMC9837937. ABS.
- N56. Schaeffer E, Streich S, Wurster I, et al. How to evaluate effects of occupational therapy: lessons learned from an exploratory randomized controlled trial. Parkinsonism Relat Disord. 2019;67:42-47. DOI 10.1016/j.parkreldis.2019.09.013. PMID 31621606. ABS.
- N57. Walter SD, Eliasziw M, Donner A. Sample size and optimal designs for reliability studies. Stat Med. 1998;17(1):101-110. PMID 9463853. ABS. (Numbers in Section 4.4 come from the exact F test, which Walter's formula approximates.)
- N58. Bonett DG. Sample size requirements for estimating intraclass correlations with desired precision. Stat Med. 2002;21(9):1331-1335. DOI 10.1002/sim.1108. PMID 12111881. ABS.
- N60. Oomen NM, van Dieën JH. Effects of age on force steadiness: a literature review and meta-analysis. Ageing Res Rev. 2017;35:312-321. DOI 10.1016/j.arr.2016.11.004. PMID 27836706. ABS.
- N61. Häger-Ross C, Schieber MH. Quantifying the independence of human finger movements: comparisons of digits, hands, and movement frequencies. J Neurosci. 2000;20(22):8542-8550. DOI 10.1523/JNEUROSCI.20-22-08542.2000. PMID 11069962. PMC6773164. ABS.
- N62. Shinohara M, Li S, Kang N, Zatsiorsky VM, Latash ML. Effects of age and gender on finger coordination in MVC and submaximal force-matching tasks. J Appl Physiol. 2003;94(1):259-270. DOI 10.1152/japplphysiol.00643.2002. PMID 12391031. ABS.
- N63. Guadagnoli MA, Lee TD. Challenge point: a framework for conceptualizing the effects of various practice conditions in motor learning. J Mot Behav. 2004;36(2):212-224. DOI 10.3200/JMBR.36.2.212-224. PMID 15130871. ABS.
- N64. Pressure Profile Systems. SingleTact User Manual (2026 copyright edition). https://5361756.fs1.hubspotusercontent-na1.net/hubfs/5361756/SingleTact%20Documents/SingleTact_Manual.pdf. FT (Table 1, Sections 2.2, 2.3, 2.6, 2.7).
- (Metadata only, content unread) Pinto Neto O, Brizzi ACB, Campos SF, Sales MP, de Almeida FD, Pedroso W, de Mello Pedreiro RC. Influence of visual feedback, hand dominance, and disease severity on grip force control and tremor dynamics in Parkinson's disease. Arch Gerontol Geriatr Plus. 2026;3:100309. DOI 10.1016/j.aggp.2026.100309. META.

(N5, N25 and N59 were considered and dropped: not relevant enough, abstract not read, or already in the baseline study.)

### Research-note sources re-checked, with new details or corrections

- R1. Davidson 2026 [note A1.1], PMC12916958. FT. Three MVCs with 1 to 2 min rest, highest used; about 5 s of history and 4 s of preview; 1 to 2 familiarisation trials; 10 × 32 s; 30 Hz; second-order Butterworth at 12 Hz; first 2 s removed; RRMSE = √[(1/T) Σ (F0 - FT)² / max(FT)²]; %TWR within ±5% of the target force.
- R2. Davidson 2025 PD [note A1.2], PMC13041725. FT-S. Three MVCs with 2 min rest, highest used; 0 to 35% in 3.3 s, 5 s hold, release in 3.3 s, terminal phase at 0%; 10 trials, 15 s rest; 30 Hz, Butterworth 12 Hz; %TWR ±5% of target force; iSD = SD over the 10 trials.
- R3. Chung 2023 [note A1.4], PMC9983837. FT-S. MVC as the average of the peaks of three trials with 5 s rest; four cycles of 30 s force and 30 s rest, each force block ten 2 s on, 1 s off pulses at 15% MVC; sixth-order Butterworth at 15 Hz; more affected side, OFF 12 to 14 h; Kinesia ONE.
- R4. Tobin 2025 [note A1.15], PMC12320221. FT-S. **Correction:** PD tested after more than 12 h withdrawal. MVC best of 3 to 5; three 120 s holds at 15% MVC, 20 to 40 s analysed, 30 s practice, at least 30 s rest; rapid task 50 trials to 15% MVC in 160 ms.
- R5. Brewer 2009 [note A1.20], PMC4894031. FT-S. Tremor as the area under the raw-force spectrum from 2 to 8 Hz; then a 2 Hz low-pass before RMSE and lag; lag bounded at 2 s (sine) and 5 s (pseudorandom), set to the maximum when covariance was under 0.35; 12.5 s preview for the sine, none for the pseudorandom; 100 Hz; 3 min per waveform.
- R6. Park 2014 [note A2.1], PMC3946854. FT-S. Four-finger MVC 60 to 66 N; enslaving from each finger's force regressed on total force over 10 s of a ramp from 0 to 40% MVC over 12 s; EN 0.070 to 0.092.
- R7. Blomkvist 2018 [note A7.9], PMC5879800. FT-S. Three trials of 17 s analysed per hand and level; fourth-order Butterworth at 20 Hz; ICC for CV 0.77 to 0.88 and for area 0.41 to 0.52, in older adults only.
- R8. Vaillancourt 2001a [note A1.12], PMID 11585609. ABS. Vision removed after 8 s of a 20 s hold; decay began 1.5 to 2.5 s after removal in both groups. **Corrects** note D4 (1 to 2 s blanks).

### Project files cited

`app/docs/research/new_modes/force-pilot-parkinsons.md`; `force-control.md`; `movement-disorders.md`; `app/docs/research/healthy_baseline_study.txt`; `app/docs/research/force_units.txt`; `app/finger_rehab/game/modes/force_pilot.py`; `app/finger_rehab/ui/force_pilot_screen.py`; `app/finger_rehab/game/force_stream.py`; `app/config/default.yaml`; `analysis/session_analysis.ipynb`; `app/arduino/firmware_on_device/lib/Sensor/Sensor.cpp`; `app/scripts/pad_bench.py`; `hardware/README.md`.
