# Movement disorders cluster: research notes

Cluster: Parkinson's disease (PD), multiple sclerosis (MS), essential tremor (ET), ageing dexterity decline.
Question: which validated clinical finger measures could become both a game and an outcome measure on the rig (SingleTact force pads at 200 Hz per finger, vibration motors, no thumb, hands flat, CSV logging, Python notebook).

Date searched: 2026-08-07. All sources below were found and confirmed in these searches. Where I could not confirm author names I say so.

## 1. Finger tapping as a clinical measure

### 1.1 Bradykinesia definition and components
- Bologna M, Paparella G, Fasano A, Hallett M, Berardelli A (2020). Evolving concepts on bradykinesia. Brain 143(3):727-750. Confirmed via Oxford Academic and PubMed 31834375. Bradykinesia in PD is slowness plus reduced movement amplitude plus the sequence effect (progressive decrement across repetitions). Sequence effect is common in PD, not common in atypical parkinsonisms.
- MDS-UPDRS item 3.4 (finger tapping) is rated 0-4 by eye. Inter-rater agreement is moderate at best; the integer scale misses subtle change (noted in the ReTap validation paper, PMC10256040, and the interrater study of 21 movement disorder experts, PMC10357208).

### 1.2 Keyboard tapping tests (the direct template for a game mode)
- Noyce AJ, Nagy A, Acharya S, Hadavi S, Bestwick JP, Fearnley J, Lees AJ, Giovannoni G (2014). Bradykinesia-Akinesia Incoordination Test: Validating an Online Keyboard Test of Upper Limb Function. PLOS ONE 9(4):e96260.
  - 58 PD patients, 93 age-matched controls. Alternate tapping of two distant keys for 30 s per hand.
  - Metrics: KS30 (taps in 30 s), AT30 (mean dwell time on key, ms), IS30 (variance of travel time between keys), DS30 (accuracy index).
  - KS30: r = -0.53 with UPDRS motor score, 50% sensitivity at 85% specificity, test-retest CV 6.0%. IS30 less reliable.
- Akram N, Li H, Ben-Joseph A, et al. (2022). Developing and assessing a new web-based tapping test for measuring distal movement in Parkinson's disease: a Distal Finger Tapping test. Scientific Reports 12:386.
  - 55 PD, 65 controls, plus 9 PD for fluctuation monitoring. Distal single-finger tapping (closer to our hardware than the whole-arm BRAIN test).
  - KS20 AUC 0.90 (79% sensitivity at 85% specificity). DFT combined with BRAIN: AUC 0.95.
  - Test-retest ICC 0.91-0.93 across the three parameters. KS20 vs MDS-UPDRS finger tapping subscore r = -0.40; AT20 r = 0.36.
- Hasan H, et al. (2019). The BRadykinesia Akinesia INcoordination (BRAIN) Tap Test: Capturing the Sequence Effect. Movement Disorders Clinical Practice (Wiley, doi 10.1002/mdc3.12798, PMC6660282). Extends the keyboard test to detect within-trial decrement. Confirmed to exist via multiple hits; I did not fetch full metrics.
- General calibration point from the web tapping literature (Distal Finger Tapping paper and related): keyboard and smartphone tapping tests correlate with UPDRS subscores around r = 0.4-0.5 overall, with occasional r near 0.8.

### 1.3 Sequence effect quantification
- Sequence effect = progressive reduction in amplitude and/or speed and progressive lengthening of tap interval within a bout. Quantified by fitting a linear trend to per-tap amplitudes and to inter-tap intervals; the slope is the measure (described in an arXiv 2025 video quantification paper, arXiv:2506.18925, and the Frontiers in Neurology 2016 paper below).
- Sequence Effect in Parkinson's Disease Is Related to Motor Energetic Cost. Frontiers in Neurology 2016, 7:83 (PMC4877367). Ties the decrement to cumulative energetic cost.
- Sequence effect reported as the most useful sign discriminating PD from SWEDD (scans without evidence of dopaminergic deficit) in that literature.
- Key design fact: dopaminergic medication does not fix the sequence effect well, so it stays measurable in treated patients.

### 1.4 Paced movement breakdown near 2 Hz
- Stegemöller EL, Simuni T, MacKinnon C (2009). Effect of movement frequency on repetitive finger movements in patients with Parkinson's disease. Movement Disorders 24(8):1162-1169.
  - 9 PD, 9 controls. Auditory-paced index finger flexion, tones stepped 1 to 3 Hz in 0.25 Hz increments.
  - PD: amplitude fell from 1.75 Hz, loss of 1:1 synchronisation at and above 2.0 Hz, hastening (moving faster than the tone). Persisted on medication. Controls held 1:1 at all rates.
  - Gives a principled difficulty axis and a clinical outcome (breakdown frequency).

## 2. Timing, rhythm, external cueing

### 2.1 Synchronisation-continuation paradigm and the Wing-Kristofferson model
- Wing AM, Kristofferson AB (1973). Foundational two-process model: continuation tapping variance decomposes into central timekeeper (clock) variance and motor implementation variance, estimated from the lag-1 autocovariance of inter-tap intervals. Confirmed as the standard reference via several hits (Springer, Frontiers). I did not fetch the 1973 original; it is universally cited.
- Modeling Accuracy and Variability of Motor Timing in Treated and Untreated Parkinson's Disease and Healthy Controls. Frontiers in Integrative Neuroscience 2011, 5:81. PD best discriminated from controls on timing accuracy rather than raw variability; clock vs motor variance estimates differed from controls.
- Timing precision in continuation and synchronization tapping. Psychological Research 2000 (Springer, PubMed 10946587). Paradigm reference.

### 2.2 Cueing evidence in PD
- Ghai et al. (2018). Effect of rhythmic auditory cueing on parkinsonian gait: A systematic review and meta-analysis. Scientific Reports 8:506. 50 studies, 1892 participants. Positive effects on gait velocity and stride length, negative on cadence. (Author list confirmed only as far as the paper being the well-known Scientific Reports meta-analysis; PMC5764963.)
- Effects of Rhythmic Auditory Stimulation on Gait and Motor Function in Parkinson's Disease: systematic review and meta-analysis of RCTs (PMC9053573, 2022). Corroborates.
- Rose D, Delevoye-Turrell Y, Ott L, Annett LE, Lovatt PJ (2019). Music and Metronomes Differentially Impact Motor Timing in People with and without Parkinson's Disease. Parkinson's Disease 2019:6530838.
  - 30 PD (H&Y mean 1.78), 26 older controls, 36 young. Tempi 81, 116, 140 BPM. Finger tapping, toe tapping, stepping.
  - Music gave better entrainment than metronome at medium and fast tempi; finger tapping asynchrony about 39 ms; PD did not differ from controls on synchronisation at these tempi (mild cohort). So a cued tapping game is playable by PD patients, and the deficit shows at higher rates (see 1.4) and in continuation, not simple sync at comfortable tempo.
- Rhythmic priming across effector systems: A randomized controlled trial with Parkinson's disease patients. Human Movement Science, 2019 (ScienceDirect S0167945718305979; authors not confirmed in my searches, paywalled).
  - 37 PD randomised: finger-tap training n=11, arm swing n=14, control n=12.
  - Intervention: four minutes total (three 1-min blocks), tapping the index finger of the less affected hand to a metronome set 20% faster than pre-training walking cadence, seated.
  - Result: gait velocity +9.5% (69.75 to 76.03 m/min), cadence +8%. No change in arm-swing or control groups. Seated finger tapping to a beat transferred to gait. This is the strongest impact case for a cued tapping mode as therapy, not just measurement.

## 3. Multiple sclerosis

### 3.1 Tapping as an MS disability measure
- Shribman S, Hasan H, Hadavi S, Giovannoni G, Noyce AJ (2018). The BRAIN test: a keyboard-tapping test to assess disability and clinical features of multiple sclerosis. Journal of Neurology 265(2):285-290.
  - 39 MS patients. KS vs EDSS r = -0.594 (p<0.001); KS vs 9-hole peg test r = 0.926 as reported (p<0.001, magnitude is the point; the 9-HPT is the standard MS upper-limb outcome); KS vs cerebellar functional score r = -0.665. KS separated pyramidal dysfunction AUC 0.840 and cerebellar dysfunction AUC 0.829.
  - Same instrument family as the PD tapping tests, so one game mode serves both conditions.
- Gulde P, Vojta H, Hermsdörfer J, Rieckmann P (2021). State and trait of finger tapping performance in multiple sclerosis. Scientific Reports 11:17095.
  - 40 MS inpatients, EDSS mean 4.0, 10 s max tapping, three sessions. Tapping rate was stable within trials (trial variance 0.5%) and unrelated to self-reported day form; EDSS explained 22% of variance, association R^2 = 0.45.
  - Design consequence: short max tapping is a trait measure in MS, not a fatigability probe. Fatigability needs sustained contractions (see 3.2).
- Quantitative Assessment of Finger Motor Impairment in Multiple Sclerosis. PLOS ONE 2013 (PMC3669283; sensor glove, finger opposition; authors not confirmed in my searches). Rate of movement and inter-hand interval independently discriminated MS from controls.

### 3.2 Motor fatigability
- Severijns D, Zijdewind I, Dalgas U, Lamers I, Lismont C, Feys P (2017). The Assessment of Motor Fatigability in Persons With Multiple Sclerosis: A Systematic Review. Neurorehabilitation and Neural Repair 31(5) (SAGE, doi 10.1177/1545968317690831). Motor fatigability = decline in force or power during sustained or repeated use. Sustained and intermittent contraction protocols both used; static fatigue index (SFI) over 30 s has high reliability in people with MS.
- Motor fatigability in persons with multiple sclerosis: relation between different upper limb muscles, and with fatigue and the perceived use of the arm in daily life. Multiple Sclerosis and Related Disorders, 2017 (ScienceDirect S2211034817303346, Severijns and colleagues). About 30 people with MS vs 16 controls in the related work; fatigability during sustained contraction higher in MS than controls; SFI related to EDSS.
- Schwid SR, et al. (1999). Quantitative assessment of motor fatigue and strength in MS. Neurology 53(4):743 (PubMed 10489035). 20 ambulatory MS, 20 controls, two sessions. Sustained maximal contractions (static fatigue), repetitive maximal contractions, 500 m walk. Fatigue measurements reliable; fatigability distinct from weakness (not correlated muscle by muscle). Origin of the static fatigue index approach.
- Hand grip fatigability in persons with multiple sclerosis according to hand dominance and disease progression. Journal of Rehabilitation Medicine (medicaljournals.se, doi 10.2340/16501977-1897). Corroborates hand-level fatigability testing in MS.
- Fatigability in MS is believed central rather than peripheral (noted across the above).

## 4. Ageing: force steadiness and dexterity decline

- Camacho-Villa MA, Giraldez-Garcia MA, Sevilla-Sanchez M, et al. (2025). Relationship Between Force Steadiness and Functionality in Older Adults: A Systematic Review With Meta-Analysis. Scandinavian Journal of Medicine and Science in Sports 35(4):e70040.
  - 21 studies, 15 meta-analysed. Upper limb steadiness vs function: r = 0.58 (95% CI 0.49-0.65). Lower limb r = 0.45. Upper-limb tasks were mostly index finger and pinch at 5-25% of max voluntary contraction (MVC). Heterogeneous protocols; standardisation called for.
- Aging and skeletal muscle force control: current perspectives and future directions. Review, PMC9541459 (approx 2022; authors not recorded in my search). CV of force higher in older adults, biggest gap at the lowest forces (about 2% MVC); four weeks of training at 10% or 80% MVC reduced CV at low intensities. So steadiness is trainable, which makes it a game target, not just a test.
- "Visuomotor Correction is a Robust Contributor to Force Variability During Index Finger Abduction by Older Adults" (paper title verbatim; PMC4678381; PubMed 26696881; 2015). Young 27, old 14. At 2.5% MVC older adults were LESS steady with visual feedback than without (CV 6.6% vs 4.2%, p<0.001). Visual gain manipulation is therefore an experimental variable worth building in.
- Finger tapping ability in healthy elderly and young adults. Medicine and Science in Sports and Exercise, 2010 (PubMed 19952813). Older adults slower in all fingers and finger pairs.
- Age-related differences in the quantitative analysis of the finger tapping task (PMC9028619, 2022). Tap rate falls and variability rises with age; variability also rises with cognitive decline (multi-finger selection errors in MCI, PMC5992087).

## 5. Tremor on a force sensor

- Héroux ME, et al. (2010). The effect of contraction intensity on force fluctuations and motor unit entrainment in individuals with essential tremor. Clinical Neurophysiology. 21 ET, 22 age-similar controls. During isometric force production ET shows tremor peaks in the force power spectrum; tremor-band force power stayed roughly constant or decreased as contraction intensity rose. Demonstrates ET tremor is measurable from an isometric force signal, which is exactly what a SingleTact pad gives.
- Correlates Between Force and Postural Tremor in Older Individuals with Essential Tremor. The Cerebellum, 2015 (Springer s12311-015-0732-2). Force tremor and postural tremor related in ET; supports force-based tremor metrics.
- Differential Diagnosis of Parkinson Disease, Essential Tremor, and Enhanced Physiological Tremor with the Tremor Analysis of EMG. Parkinson's Disease (Wiley/Hindawi), 2017 (PMC5573102). Frequencies: PD tremor 4-6 Hz, ET overlapping 4-7 Hz, enhanced physiological tremor 6-12 Hz.
- Physiological tremor (8-12 Hz component) in isometric force control. Neuroscience Letters 2017 (ScienceDirect S0304394017300447). The 8-12 Hz band persists in force output recordings; practice, age, vision and neural drive shape the spectrum up to at least 12 Hz.
- Muscle loading as a method to isolate the underlying tremor components in essential tremor and Parkinson's disease (PubMed 15318346). Load-dependent vs load-independent tremor components separable under isometric loading.
- Hardware check: 200 Hz sampling gives a 100 Hz Nyquist limit, comfortably above the 4-12 Hz tremor band. A 20-30 s hold gives 0.03-0.05 Hz spectral resolution with Welch averaging trade-offs; fine for band-power estimates.

## 6. PD force control (release deficit)

- Neely KA, Planetta PJ, Prodoehl J, et al. (2013). Force Control Deficits in Individuals with Parkinson's Disease, Multiple Systems Atrophy, and Progressive Supranuclear Palsy. PLOS ONE 8(3):e58403. 12 PD, 12 MSA-P, 8 PSP, 12 controls, off medication. Ten 2 s pulses at 15% MVC with precision grip on a force transducer. All patient groups slower to contract AND to relax, longer pulses; PSP produced extra unintended pulses.
- Grip force release is impaired in Parkinson's disease during a force tracking task. Experimental Brain Research, 2024 (Springer s00221-024-06966-w; authors not confirmed). PD less accurate with greater error and trial-to-trial variability specifically during release.
- Parkinson's disease impairs grip force release during a sinusoidal force tracking task (PMC12916958, approx 2026). Sinusoidal tracking: older adults show generation and release deficits vs young; PD shows global decline with release disproportionately affected; two-point discrimination correlated with tracking accuracy.
- Design consequence: tracking tasks must score the down-ramp separately from the up-ramp.

## 7. What this means for the rig

Untapped asset: the full 200 Hz analogue force signal per finger. Current modes use it as a press threshold only. Every candidate below exploits the analogue signal or validated tapping metrics.

Hardware fit notes:
- No thumb: MDS-UPDRS finger tapping is thumb-index opposition. Our analog is table tapping with index or alternating index-middle, which matches the DFT and BRAIN keyboard tests, whose correlations with clinical scores are the ones to quote (moderate, r 0.4-0.6, and excellent separation from controls, AUC up to 0.90-0.95).
- Force amplitude is a proxy for movement amplitude. The sequence effect on our rig is a decrement in peak tap force and a lengthening of intervals; that is an analog, not the kinematic decrement itself. Honest limitation, still novel: keyboards measure no amplitude at all, we do.
- Vibration motors: one per hand at a time is enough for a haptic metronome (one cue finger per hand); cross-hand simultaneous supports bilateral cueing.
- Audio cue timing matters more than screen timing for rhythm work; measure and log the audio output latency once, screen at 60 Hz is only cosmetic for these modes.
- SingleTact pads: confirm model force range (common variants 10 N and 45 N) before designing maximal-effort tasks; prefer "maximum comfortable press" calibration per finger per session, and submaximal targets defined as % of that.

## 8. Candidate game modes (full designs)

### Mode A: Tap Sprint (bradykinesia sprint with anti-decrement scoring)
- Conditions: PD primary; MS disability tracking; ageing normative decline. Same instrument family validated in both PD (Noyce 2014, Akram 2022) and MS (Shribman 2018).
- Trial: 20-30 s bout per hand. Player taps one pad with the index, or alternates index-middle on two pads (both variants logged as distinct sub-modes). Each tap drives a racer forward; tap force sets stride power. A power bar shows current peak force against the player's session-start baseline; staying above 80% of baseline lights a boost multiplier, which directly gamifies resisting the sequence effect. Ghost replay of personal best; medals for distance.
- Game vs test: the racer, ghost, boost multiplier, and medal ladder; bouts are short and repeatable; both hands get their own lanes so left-right asymmetry is visible as a race.
- Difficulty: bout length 10 to 30 s; single finger then alternating fingers; then bilateral alternation (left index, right index, ...). Target-rate bands can be layered later using the 2 Hz literature.
- Logged per tap: onset and offset timestamps (threshold crossing at 200 Hz), peak force, dwell time, inter-press interval, finger ID, hand, bout metadata, session-start baseline forces.
- Notebook: KS30 analog (tap count), AT30 analog (mean dwell), IS30 analog (IPI variance), sequence-effect slopes (linear fit of peak force vs tap index and IPI vs tap index), hesitation count (IPI above 3x median), halt count, left-right asymmetry index, and session-over-session trend lines. Benchmarks: KS30 test-retest CV 6% and ICCs above 0.9 in the source tests give the reliability bar to aim for.
- Risks: force amplitude is a proxy for kinematic amplitude; UPDRS-subscore correlations for keyboard analogs are moderate (about 0.4-0.5), so pitch it as a sensitive within-person tracker rather than a UPDRS replacement.

### Mode B: Carry the Beat (synchronisation-continuation with tempo staircase)
- Conditions: PD primary (timing and cueing), also a general timing outcome for MS and ageing.
- Trial: a track (metronome or music, audio and optional haptic pulse on the cue finger) plays 12 beats; the player taps along (synchronisation). The backing then drops out and the player keeps the beat solo for 20-30 taps (continuation). The track re-enters and alignment at re-entry is scored. Framing: you are the drummer holding the song together when the band drops out.
- Game vs test: song structure, streaks for tight beats, "band trust meter" that grows when continuation drift is low, unlockable cue types (metronome, then music, per Rose 2019 music helps at medium and fast tempi). A staircase across trials raises tempo until 1:1 entrainment fails, and the fastest held tempo becomes a displayed personal stat ("max groove speed"); the PD literature predicts breakdown near 2 Hz (Stegemöller 2009), so this stat is itself a clinical measure.
- Difficulty: tempo staircase; continuation length; cue type; single finger, alternating fingers, or bilateral alternation; haptic-only rounds (no audio) as a stretch goal.
- Logged: cue onset times, audio latency constant, tap onset times and forces, phase labels (sync, continuation, re-entry), tempo, cue type.
- Notebook: mean and SD of asynchrony in sync phase; continuation drift (% change of mean IPI); Wing-Kristofferson decomposition (motor variance = negative lag-1 autocovariance of IPIs, clock variance = total variance minus twice motor variance, with a validity check that lag-1 autocovariance is negative); hastening index (tapping faster than cue); breakdown tempo; music vs metronome contrasts.
- Impact case: an RCT in Human Movement Science (2019) got a 9.5% gait velocity gain in PD from four minutes of seated metronome-paced index tapping at 20% above walking cadence. The mode can deliver that exact priming dose before physio walking practice, so it is therapy and measurement in one. RAS meta-analytic support for cueing in PD is strong (Scientific Reports 2018 meta-analysis, 50 studies, n=1892).
- Distinct from the existing rhythm mode (metronome-paced pressing): the continuation phase, the tempo staircase to breakdown, cue-type manipulation, and the clock vs motor variance analytics are all new; the existing mode never removes the cue.
- Risks: needs low-jitter audio scheduling (measure once, log constant); Wing-Kristofferson assumes stationarity, so keep continuation runs short and discard post-halt segments.

### Mode C: Hover (isometric force steadiness, tracking and tremor spectroscopy)
- Conditions: ageing primary (steadiness); PD (force release); ET (force tremor band power); MS baseline. This is the mode that finally uses the full analogue signal.
- Trial: calibrate max comfortable press per finger (3 s, twice, take median peak). Then: (1) Hover rounds: hold force at 5-15% of calibrated max to keep a drone inside a hoop for 15-30 s; (2) Gate rounds: track a slowly moving target (sinusoid 0.1-1 Hz) through gates, with the down-ramp ("descend and land") scored separately because PD impairs release disproportionately; (3) Gust rounds: step changes in target; (4) Cloud rounds: visual feedback blanks for a few seconds mid-hold, because older adults are less steady WITH visual feedback at very low forces (CV 6.6% vs 4.2% at 2.5% MVC), which makes feedback dependence itself a measurable outcome.
- Game vs test: FPV drone framing (fits Basil's domain), hoops, gates, wind, weather; score is time-in-band plus smoothness bonus; per-finger progression feeds the existing adaptive mode's weakest-finger weighting.
- Difficulty: lower %max targets (harder), narrower band, faster sinusoids, longer holds, cloud rounds, weaker fingers.
- Logged: full 200 Hz force trace, target trace, band edges, calibration values, round type.
- Notebook: CV of force and RMSE per round; time-in-band; Welch PSD of the hold segments; tremor-band metrics (4-12 Hz power, peak frequency, ratio of 4-12 Hz to 0.5-4 Hz power); up-ramp vs down-ramp error asymmetry; visual-dependence delta (CV with vs without feedback); tracking lag by cross-correlation.
- Evidence: upper-limb force steadiness correlates r = 0.58 with function in older adults (2025 meta-analysis, tasks at 5-25% MVC, exactly our range); steadiness improves within 4 weeks of low-force training, so the game has a trainable target; PD and atypical parkinsonisms are slower to contract and relax with longer pulses at 15% MVC (Neely 2013) and release is disproportionately impaired in sinusoidal tracking; ET tremor appears as spectral peaks in isometric force (Héroux 2010; The Cerebellum 2015), and 200 Hz sampling covers the 4-12 Hz band with a Nyquist margin of 8x.
- Risks: SingleTact accuracy and drift at very low forces needs a bench characterisation (a good thesis section in itself); % of max on a pad is a pragmatic proxy for true MVC; tremor from a fingertip pressing a pad is less validated than accelerometry, so frame tremor metrics as an exploratory instrumentation contribution, powered by the isometric force tremor literature rather than by a direct device precedent.

### Mode D: Hold the Line (sustained-contraction fatigability)
- Conditions: MS primary; ageing secondary. Fills a real gap: fatigability is a defining MS symptom and the systematic review confirms sustained contraction protocols with a static fatigue index are the standard quantitative approach, reliable in people with MS, and related to EDSS.
- Trial: after per-finger calibration, hold a target force (30-50% of calibrated max; clinically SFI uses maximal sustained effort, we adapt submaximal for pad range and comfort) for 30 s. Framing: your press holds a bridge up while a convoy crosses; force sag makes the bridge dip and slows the convoy. One finger per bout, enforced rest timers between bouts, maximum bouts per session capped.
- Game vs test: convoy theme, per-finger "garrison" progression, milestones for holding within band longer; deliberately NOT a daily leaderboard on maximal effort (progression is longer holds and more fingers covered, not bigger forces, to keep fatigue burden sane).
- Why not tapping decline: 10 s maximal tapping in MS is stable within trials (Gulde 2021), so short tapping bouts cannot measure fatigability; sustained contraction is the validated probe (Severijns systematic review 2017; Schwid 1999). Cite this to justify the design choice in the thesis.
- Logged: full 200 Hz force trace, calibration, bout order, rest durations, optional 0-10 perceived-effort prompt after each bout.
- Notebook: Static Fatigue Index (area lost between the initial-force ideal line and the actual force curve, as a % of the ideal area, Schwid 1999 lineage); linear slope of force decline; end/start ratio (mean of last 5 s over first 5 s); per-finger and left-right comparisons; relation between measured fatigability and self-reported fatigue (the literature says they dissociate, fatigability is also distinct from weakness, which is an interesting quantitative result to reproduce).
- Risks: pad saturation on strong fingers (check SingleTact variant range); an adapted submaximal SFI needs its own test-retest study (thesis-friendly); MS heat sensitivity and session fatigue mean session caps are a safety requirement, not a nicety.

## 9. Cross-cutting thesis analytics

- Every mode above outputs a metric with a published clinical anchor (KS/AT/IS family, sequence-effect slope, asynchrony and clock/motor variance, CV of force, tremor band power, SFI).
- Reliability study design: repeat sessions across days, compute ICC and CV, compare against published bars (KS30 CV 6%, DFT ICCs above 0.9, SFI high reliability in MS).
- Discrimination potential if patient cohorts become available: published AUCs (0.90 DFT alone, 0.95 combined; 0.84 pyramidal, 0.83 cerebellar in MS) give effect-size context for power calculations.
- All modes run on unmodified hardware; the only new engineering is software plus one bench characterisation of pad accuracy at low force.
