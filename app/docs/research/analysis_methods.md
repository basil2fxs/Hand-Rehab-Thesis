# How the data is analysed: the format, Rayan's pipeline, true force and the literature

Written 30 September 2026, before any participant. It answers four questions: whether the analysis should move to MATLAB or R the way Rayan worked, whether all of Rayan's analysis is done the way he did it, how force is read so the newtons are true, and how the analysis compares with standard practice for each measure, with the figures the thesis should show.

Everything below was checked on the pilot sessions (68 blocks, run headless through every chapter of the notebook) and on a simulated 12-person cohort played through the real engine.

## 1. Format: stay in Python, export for MATLAB and R

Rayan's work is R (RStudio: dplyr, ggplot2, lmerTest, emmeans, pbkrtest) plus one Python script. No MATLAB code of his exists in the archive (`archive/old_rayyan_stuff`) or in the `folder_hierarchy_example` he sent; the note written for him is titled `csv_format_for_matlab.txt`, but his scripts are R. MATLAB is not installed on the development machine.

The analysis of record stays in `analysis/session_analysis.ipynb`, for four reasons:

- The game and the analysis share code. The Teasdale onset detector, the 250 ms look-back zero and the mixed model live in `finger_rehab/analytics/` and the notebook carries verbatim copies, pinned by tests, so the analysis measures a press exactly the way the game does.
- Several hundred tests, in two dozen test files that load the notebook or its package twins, hold the analysis to known answers, including Rayan's own output files to the last decimal and his emmeans plot. A MATLAB or R port would start that checking again from nothing.
- It runs on the lab and home computers without a licence, and the thesis build takes its figures directly.
- Nothing in these analyses needs a MATLAB toolbox. The one statistical tool the Python stack lacked, the mixed model Rayan fitted with lme4, is now implemented and checked (Section 2).

For anyone who works in MATLAB or R, the export cell now writes two things beside the CSVs:

- `shared/matlab/finger_rehab.mat`: the selected trials and the session summary, each a struct of columns (`struct2table(S.trials)` gives the table back), with a loading note.
- `shared/rayan_format/`: the selection in his layout, on which his R and Python scripts run unchanged (event rows carry the last sample's values, each pad is shifted to rest at his 255, the detail reads `trial=N`, the trial logs carry his block column, and the SRT task's practice, learning and post-test map onto his pretest, main and aftertest).

What the format still does badly: the notebook's definitions sit in one code cell of about 30,000 lines, which is hard to navigate. Moving them into a module with the notebook as thin chapter cells is the right change, but the tests load that cell directly and collection is about to start, so it waits until after collection.

## 2. Rayan's pipeline, script by script

| His file | What it computes | Where it is now | Checked against |
|---|---|---|---|
| `raw/process_force_peaks.py` | Teasdale onset per cue, peak per sensor after onset | `teasdale_onset` (verbatim port), `onset_table`, `four_finger_peaks` | His processed CSV: onsets within 0.05 ms at his sample rate |
| `analyze_baseline_drift_modified_newtons.R` | Force at each stim and response, raw (minus 255) and zeroed on the 250 ms before, in newtons, with a trend line | `lookback_baseline`, `drift_events`, `sec_baseline_drift`, and now `true_press_force` | His printed regression equations |
| `analyze_baseline_drift_modified.R` | Stim against response levels over the session | `rayan_stim_levels`, the baseline shift column | Pilot drift figures |
| `analyze_baseline_drift.R` | The 400 ms before the first five responses, dots every 50 ms | `rayan_lookback_zoom` | His response-waveform plots |
| `Max_Peak_Analysis.R` | Peak in the 1.2 s after each cue, per sensor | `rayan_stim_peaks`, the sensor table | His summary CSV, to the last decimal |
| `Noise_Analysis.R` | Rest noise outside the cue windows, SNR | `rayan_baseline_noise`, the SNR column | His summary CSV, to the last decimal |
| `repeatability.R` | Mean, SD and CV of the peak per 50 cues | `rayan_repeatability` | His summary CSV, all twelve rows |
| `raw/FingerRawforEachBlock.R` | Peak on every finger per trial, cued finger large | `sec_rayan_trial_peaks` | Figure layout |
| `Data_analysis_Final.R` | RT by block: `lmer(RT ~ block + (1 \| participant))`, emmeans, Holm pairwise, post against pre, linear trend over blocks 1 to 5 | `rayan_blocks`, `rayan_block_model`, and now the SRT chapter | His emmeans plot (below) |

Deliberate differences, each forced by the new logger: event rows hold zeros, so force is read off the nearest sample row; each pad rests somewhere between 250 and 320 counts, so the static offset is that pad's own resting median rather than his flat 255; timestamps arrive in bursts, so the sample rate is count over span rather than the median gap; the stim detail says `trial_id=N`.

**What changed on 30 September.** The block model was a stand-in (least squares with participant dummies), which gives his block means but intervals several milliseconds wide where his are about 220 ms wide. It is now his model: a random intercept per participant fitted by REML (`finger_rehab/analytics/mixed_model.py`), with the Satterthwaite degrees of freedom lmerTest reports. On his own three trial logs it reproduces his `plot_estimated_means.png`: block 0 spans 195.1 to 403.2 ms against about 195 to 404 on his plot, block 1 103.1 to 327.0 against about 103 to 328, block 4 32.7 to 256.5 against about 33 to 257. On balanced data it matches the exact ANOVA answers (both variances, the block means, N - n - k + 1 degrees of freedom for a within-block contrast, and the classical Satterthwaite value for a block mean). REML with Satterthwaite or Kenward-Roger degrees of freedom is also what holds the Type I error near .05 in small samples; likelihood-ratio tests and t-as-z are anti-conservative (Luke 2017).

His model now also runs on the lab's SRT task, which has his design: practice (random) as block 0, the eight learning blocks of 100 as blocks 1 to 8, the post-test (random) as block 9. Each timing group is fitted separately, and the chapter adds the SRT's own headline contrast, post-test minus the last learning block, with the between-participant interval the lab's median table lacks.

## 3. True force

**What the game logs.** `peak_force_n` in trials.csv is the target pad's peak so far at the moment the trial is logged. Reaction, Adaptive, Muscle Memory and Mirror end a trial on the press, so they log it as the press registers, near the trigger force. On the pilot Reaction block the logged value was a median 0.76 N, the force at the press moment 0.87 N, and the press's actual peak in the 1.2 s after the cue 1.75 N. Across the pilot data the logged value runs 1.1 to 1.8 N under the true peak in those modes. Chords log after their 200 ms hold and agree with it (0.07 N apart).

**What the analysis now quotes.** Every cued press is read off the raw stream the way Rayan's newton script reads it: the peak in the 1.2 s after the cue minus the mean of the 250 ms before it, so a pad that has drifted since the block began is zeroed where it actually rested. The force chapter and the sensor chapter print that per finger, with the game's logged value beside it and their agreement (bias and limits). The game's column is kept because it is what was recorded, and the thesis already says that a value re-scored from the raw stream replaces the in-game one.

**Counts to newtons.** Until the bench has been run, newtons use the SingleTact rating, 512 counts over the 10 N part (51.2 counts per newton, his constant too), or the session's own `fsr.force_calibration_n_per_count`. `scripts/pad_bench.py --characterise` measures each pad's own slope against known masses, with linearity, hysteresis and drift, and writes `config/calibration/pad_bench_<label>_<stamp>_summary.csv`. The notebook now reads the newest file for the `calibrated` set and converts each pad with its own slope; the table says which pads used the bench and which the rating. The pads matter here: the same light press read about 49 counts on the index pad and 115 on the pinky pad, and only the bench can say how much of that is the pad and how much the finger.

**What the zero cannot remove.** The datasheet gives linearity under 2 percent, hysteresis under 4 percent and drift of 2 percent of full scale in a minute at half load. The look-back zero removes slow drift between presses; it cannot remove hysteresis inside one press.

## 4. Each measure against standard practice

| Measure | Standard practice | This analysis | Gap closed or left |
|---|---|---|---|
| Reaction time, per person | Median of correct trials for a battery; trial-level mixed models where the design has repeated conditions (Baayen, Davidson and Bates 2008) | Median per person; Rayan's mixed model for block designs (his, SRT) | Mixed model added. RT is modelled untransformed, as Rayan did; transforming RT can change which effects look additive (Lo and Andrews 2015) |
| Tests from a mixed model | REML with Satterthwaite or Kenward-Roger degrees of freedom (Luke 2017; Kuznetsova, Brockhoff and Christensen 2017) | REML, Satterthwaite | Closed |
| Movement onset | Teasdale, Bard, Fleury, Young and Proteau (1993) | His exact port | Closed |
| Force in newtons | Per-press zero, calibrated conversion | 250 ms look-back zero; bench slope per pad when measured | Open until the bench is run on both sensor sets |
| Test-retest reliability | ICC with its form and 95 percent interval, SEM, MDC (Koo and Li 2016); Bland-Altman limits with their own intervals (Bland and Altman 1999) | ICC(2,1) with intervals, SEM, MDC95, Bland-Altman panels; each limit's 95 percent interval now in the table and shaded on the figure | Closed |
| Internal consistency | Report reliability routinely, permutation split-half (Parsons, Kruijt and Fox 2019) | Permutation split-half, Spearman-Brown corrected | Closed |
| Known-effect checks | Pre-specified tests, family-wise correction, equivalence by two one-sided tests | Wilcoxon with rank-biserial and dz, Holm, TOST on the 90 percent interval; feasibility checks named as such | Closed |
| Normal ranges | Reference intervals need large samples; small samples are descriptive | Median, IQR and every participant's point; no percentiles below n = 20 | Closed |
| Figures | Show the individual data, not bars or means alone (Weissgerber, Milic, Winham and Garovic 2015; raincloud plots, Allen and colleagues 2019) | Cohort figures show every participant | Per-session figures crowded at many blocks; fixed (below) |

Figures fixed on 30 September because they broke with many blocks selected: the repeatability figure (a legend entry per finger and block) now pools each finger across blocks past four; the SNR bars become one column of dots per finger past 16; the per-game comparison becomes one column per mode past 12 games; the per-session cross-talk matrices wrap five to a row; the progress chart keeps one legend outside the data. The run on the pilot data also caught one crash, the Muscle Memory chapter on a block that ended before its first probe, now fixed and tested.

## 5. What the thesis should show

| Thesis section | Figure or table | Source in the notebook |
|---|---|---|
| 4.1 Feasibility | Minutes per sitting against the plan; completion table | `sec_cohort_feasibility` |
| 4.2 Engineering verification | Timing chain; the logged peak against the true peak (Bland-Altman) | `fig:timing`; `true_force_report` |
| 4.3 Sensor comparison | Each pad's slope against 51.2, linearity, hysteresis and drift, both sets side by side | `pad_bench.py --characterise`; the bench files |
| 4.4 Normal ranges | Every participant's point with median and IQR per measure; the table of median (IQR) and range | `sec_cohort_describe` |
| 4.5 Validity checks | The checks table with intervals; C6 chord cost, P1 takes, Rh1 distribution as figures | `sec_cohort_validity` |
| 4.6 Reliability | ICC forest against the predicted classes; Bland-Altman panels | `sec_cohort_reliability` |
| 4.8 EEG and the SRT task | Model means with intervals per block and the sequence effect | `srt_rayan_model` |

## Sources

- Allen M, Poggiali D, Whitaker K, Marshall TR, van Langen J, Kievit RA. Raincloud plots: a multi-platform tool for robust data visualization. Wellcome Open Res. 2019;4:63. doi:10.12688/wellcomeopenres.15191.1
- Baayen RH, Davidson DJ, Bates DM. Mixed-effects modeling with crossed random effects for subjects and items. J Mem Lang. 2008;59(4):390-412. doi:10.1016/j.jml.2007.12.005
- Bates D, Mächler M, Bolker B, Walker S. Fitting linear mixed-effects models using lme4. J Stat Softw. 2015;67(1). doi:10.18637/jss.v067.i01
- Bland JM, Altman DG. Measuring agreement in method comparison studies. Stat Methods Med Res. 1999;8(2):135-160. doi:10.1177/096228029900800204
- Koo TK, Li MY. A guideline of selecting and reporting intraclass correlation coefficients for reliability research. J Chiropr Med. 2016;15(2):155-163. doi:10.1016/j.jcm.2016.02.012
- Kuznetsova A, Brockhoff PB, Christensen RHB. lmerTest package: tests in linear mixed effects models. J Stat Softw. 2017;82(13). doi:10.18637/jss.v082.i13
- Lo S, Andrews S. To transform or not to transform: using generalized linear mixed models to analyse reaction time data. Front Psychol. 2015;6:1171. doi:10.3389/fpsyg.2015.01171
- Luke SG. Evaluating significance in linear mixed-effects models in R. Behav Res Methods. 2017;49(4):1494-1502. doi:10.3758/s13428-016-0809-y
- Parsons S, Kruijt AW, Fox E. Psychological science needs a standard practice of reporting the reliability of cognitive-behavioral measurements. Adv Methods Pract Psychol Sci. 2019;2(4):378-395. doi:10.1177/2515245919879695
- Patterson HD, Thompson R. Recovery of inter-block information when block sizes are unequal. Biometrika. 1971;58(3):545-554. doi:10.1093/biomet/58.3.545
- Teasdale N, Bard C, Fleury M, Young DE, Proteau L. Determining movement onsets from temporal series. J Mot Behav. 1993;25(2):97-106. doi:10.1080/00222895.1993.9941644
- Weissgerber TL, Milic NM, Winham SJ, Garovic VD. Beyond bar and line graphs: time for a new data presentation paradigm. PLoS Biol. 2015;13(4):e1002128. doi:10.1371/journal.pbio.1002128

Each record was retrieved by DOI on Crossref on 30 September 2026; the Luke, Lo and Andrews, Parsons and Weissgerber abstracts were read on Europe PMC or PubMed.
