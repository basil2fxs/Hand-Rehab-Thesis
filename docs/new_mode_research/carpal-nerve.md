# Cluster notes: carpal tunnel, peripheral nerve, sensory relearning, focal hand dystonia

Research date: 2026-08-07. All citations below were confirmed in live searches this session.
Device constraints applied throughout: SingleTact force pad per finger at 200 Hz (analogue), one
vibration motor per finger (fixed intensity, variable duration and pulse pattern, one motor per
hand at an instant, cross-hand simultaneous OK), 60 Hz screen, speaker, CSV logging, Python
notebook analysis. No thumb.

## 1. What the literature says

### 1.1 Sensory re-education after nerve injury (Lundborg and Rosen school)

- Rosen B, Balkenius C, Lundborg G (2003). "Sensory Re-education Today and Tomorrow: A Review of
  Evolving Concepts." British Journal of Hand Therapy 8(2). DOI 10.1177/175899830300800201.
  Core rationale: after nerve repair, misdirected reinnervation scrambles the cortical hand map.
  Training exploits cortical plasticity to relearn the new input code and recover tactile gnosis
  (the ability to recognise what you touch without vision).
- Rosen B, Lundborg G (2004). "Sensory re-education after nerve repair: aspects of timing."
  Handchir Mikrochir Plast Chir 36(1):8-12. PMID 15083384. Argues for starting relearning early
  (phase 1, first week post-op) rather than waiting for reinnervation.
- Xia W, Bai Z, Dai R, Zhang J, Lu J, Niu W (2021). "The effects of sensory re-education on hand
  function recovery after peripheral nerve repair: A systematic review." NeuroRehabilitation,
  DOI 10.3233/NRE-201612. Supportive but evidence quality mixed.
- Vikström P et al. (2017). "Similar 2-point discrimination and stereognosia but better locognosia
  at long term with an independent home-based sensory reeducation program vs no reeducation after
  low-median nerve transection and repair." Journal of Hand Therapy. Locognosia (touch
  localisation) significantly better in the trained group at 1.5 and 3 years (17 vs 5 patients
  with excellent locognosia at 1.5 y), difference gone at 6 y in a small subsample. Key point:
  localisation is the modality that responded to home training.
- Paula MH et al. (2016). "Early sensory re-education of the hand after peripheral nerve repair
  based on mirror therapy: a randomized controlled trial." Brazilian Journal of Physical Therapy
  (PMC4835165). Early mirror-based re-education was NOT better than late classic re-education
  (Rosen scores 1.68 vs 1.65 at 3 months). Negative result worth knowing given the rig already
  has a mirror mode.

### 1.2 Measurement instruments this device can mimic

- Jerosch-Herold C (2003). "A Study of the Relative Responsiveness of Five Sensibility Tests for
  Assessment of Recovery after Median Nerve Injury and Repair." Journal of Hand Surgery (British)
  DOI 10.1016/S0266-7681(03)00017-2. Locognosia tests had effect sizes and standardised response
  means above 0.8, among the most responsive sensory outcomes after nerve repair.
- Locognosia test psychometrics (PMID 16877604): test-retest ICC 0.924 (95% CI 0.848 to 1.00) for
  median nerve injuries.
- Weber M, Marshall A, Timircan R, McGlone F, Watt SJ, Onyekwelu O, Booth L, Jesudason E, Lees V,
  Valyear KF (2023). "Touch localization after nerve repair in the hand: insights from a new
  measurement tool." Journal of Neurophysiology 130(5):1126-1141. After median or ulnar repair,
  localisation error rises sharply in the injured territory, t(17) = 4.5, p < 0.001, including
  misreferrals where touch on one digit is felt on another digit. A per-finger confusion matrix
  is a direct digital analogue of their measure.
- STI test (Shape Texture Identification), Rosen and Lundborg's tactile gnosis instrument:
  inter-tester reliability (Rosen B 2003, British Journal of Hand Therapy, SAGE
  10.1177/175899830300800304), responsiveness vs 2PD (Rosen B, Jerosch-Herold C 2000, British
  Journal of Hand Therapy 10.1177/175899830000500403), STI2 concurrent validity (PMID 30025838,
  Journal of Hand Therapy). The STI itself needs physical shapes and textures, which the rig
  cannot present. The rig CAN present vibrotactile spatial and temporal patterns as a
  gnosis-style identification task.

### 1.3 Carpal tunnel syndrome: what is actually impaired, what rehab evidence exists

- Peters S, Page MJ, Coppieters MW, Ross M, Johnston V (2016). "Rehabilitation following carpal
  tunnel release." Cochrane Database of Systematic Reviews CD004158.pub3. PMID 26884379. Verdict:
  limited, generally low quality evidence for every reviewed post-release intervention. There is
  an evidence vacuum here, which is an opportunity for instrumented outcome tracking rather than
  a claim that any game will treat CTS.
- Jerosch-Herold C, Houghton J, Miller L, Shepstone L (2016). "Does sensory relearning improve
  tactile function after carpal tunnel decompression? A pragmatic, assessor-blinded, randomized
  clinical trial." Journal of Hand Surgery (European) DOI 10.1177/1753193416657760, PMID 27402282.
  n = 104. No significant benefit on STI, touch threshold, localisation or dexterity at 6 or 12
  weeks; only self-reported hand function differed. IMPORTANT NEGATIVE RESULT: do not pitch a
  sensory relearning game as proven treatment for post-release CTS. Pitch measurement and motor
  control instead.
- Jerosch-Herold et al. (2012) pilot, Muscle and Nerve, PMID 23018869: earlier, smaller, appeared
  promising; superseded by the 2016 trial.
- Li K, Evans PJ, Seitz WH Jr, Li Z-M (2015). "Carpal tunnel syndrome impairs sustained precision
  pinch performance." Clinical Neurophysiology 126:194-201 (PMC4234695). CTS patients hold a
  target force fine WITH visual feedback but accuracy collapses and variability rises when
  feedback is removed (p < 0.001). Visual feedback masks the deficit; feedback withdrawal exposes
  it. This is a ready-made experimental contrast for the rig.
- "Bilateral deficits in fine motor control and pinch grip force in patients with unilateral
  carpal tunnel syndrome" (PMID 19066868): deficits are bilateral even in unilateral CTS.
- "Effects of Carpal Tunnel Syndrome on Force Coordination and Muscle Coherence during Precision
  Pinch" (PMID 28824352, Journal of Medical and Biological Engineering 2017).
- Vibrometry in CTS: sensitivity and specificity of vibrometry for CTS detection (PMID 8528719);
  quantitative vibration threshold testing reliability (PMID 14770135, Journal of Hand Therapy);
  multi-frequency vibrometry case-control (PMC5721389). Caveat from this literature: vibration
  thresholds track axonal loss, while early CTS is demyelinating, so vibration threshold is NOT a
  sensitive early-CTS screen. Use it as a monitoring measure, not a diagnostic claim.

### 1.4 Diabetic peripheral neuropathy (DPN)

- Lima KCA, Borges LS, Hatanaka E, Rolim LC, de Freitas PB (2017). "Grip force control and hand
  dexterity are impaired in individuals with diabetic peripheral neuropathy." Neuroscience
  Letters 659:54-59. PMID 28867590. Strength is preserved; dexterity and force control are not.
- "The effect of type 2 diabetes and diabetic peripheral neuropathy on predictive grip force
  control." Experimental Brain Research 2023, DOI 10.1007/s00221-023-06705-7. Diabetes alone is
  fine; neuropathy adds excessive grip force ratios and timing deficits.
- VPT screening evidence: "Vibration Perception Threshold as a Method for Detecting Diabetic
  Peripheral Neuropathy: A Systematic Review of Measurement Characteristics" (PMC12839646);
  "Diagnostic Accuracy of Screening Tests for Diabetic Peripheral Neuropathy: An Umbrella
  Review" (PMID 39664106). Moderate sensitivity and specificity, biothesiometer sensitivity
  0.61 to 0.80 vs tuning fork 0.10 to 0.46, poor standardisation across devices. DPN screening
  is normally done on feet; hands are involved later (glove distribution), so frame hand VPT as
  longitudinal monitoring of hand involvement, not primary screening.
- Hardware note: fixed motor intensity means the rig cannot run a classical amplitude-based VPT.
  It can run duration-based detection thresholds (shortest pulse reliably detected) as a proxy,
  which must be validated against motor rise time.

### 1.5 Focal hand dystonia (Byl and Merzenich line)

- Byl NN, Merzenich MM et al. (1997). "A primate model for studying focal dystonia and repetitive
  strain injury: effects on the primary somatosensory cortex." PMID 9062569. Attended, highly
  repetitive, stereotyped finger movement degrades and de-differentiates the S1 hand map. This is
  the mechanistic foundation: dystonia as learned map degradation.
- Byl NN, McKenzie A (2000). Learning-based sensorimotor training, Journal of Hand Therapy
  (confirmed as cited in PMC4496570, Frontiers in Human Neuroscience 2015 rTMS/retraining paper):
  gains in motor control and sensory discrimination; training modifies brain activation.
- Byl NN et al. (2009). "Focal hand dystonia: effectiveness of a home program of fitness and
  learning-based sensorimotor and memory training." Journal of Hand Therapy, PMID 19285832.
- Candia V et al. (2003). "Effective behavioral treatment of focal hand dystonia in musicians
  alters somatosensory cortical organization." PNAS 100, DOI 10.1073/pnas.1231193100. Sensory
  motor retuning normalises the cortical finger layout in treated musicians.
- Zeuner KE et al. (2002). "Sensory training for patients with focal hand dystonia." Annals of
  Neurology 51, PMID 12112105. 8 weeks of braille reading (30 to 60 min daily) improved spatial
  discrimination AND the Fahn dystonia scale; sensory gains correlated with motor gains.
  Follow-up: Zeuner and Hallett (2003), PMID 14502673, benefits held at 1 year in continuing
  trainees. Pure sensory discrimination training moved a motor outcome. That is the single most
  encouraging fact for a sensory-discrimination game on this rig.
- Treatment burden noted in the retraining literature: 8 to 12 weeks, hours per day, incomplete
  recovery, not universally beneficial. A home game rig directly attacks the burden problem.

### 1.6 Temporal discrimination threshold (TDT)

- Conte A et al. (2017). "Temporal Discrimination: Mechanisms and Relevance to Adult-Onset
  Dystonia." Review, PMC5712317 (Frontiers). TDT: minimum interval at which two sequential
  stimuli are perceived as two. Tactile pairs are the usual stimulus; interval stepped from 0 in
  small increments until asynchrony is reported. Abnormal TDT shows autosomal dominant
  transmission in unaffected first-degree relatives of cervical dystonia patients.
- Bradley D et al. (2009). "Temporal Discrimination Threshold: VBM evidence for an endophenotype
  in adult onset primary torsion dystonia." Brain 132:2327 onwards. Structural (putaminal)
  correlate of abnormal TDT in patients and unaffected relatives.
- Borngräber F et al. (2022). "Characterizing the temporal discrimination threshold in musician's
  dystonia." Scientific Reports (PMC9440005). TDT measured with 5 ms steps: musician's dystonia
  37.75 +/- 16.94 ms, healthy musicians 29.10 +/- 11.97 ms, healthy non-musicians 49.19 +/- 22.84
  ms; NO significant group differences. CONFLICT: the endophenotype claim is strong for
  adult-onset idiopathic focal dystonias (cervical, blepharospasm, writer's cramp) but did not
  replicate in musician's dystonia. Surface both sides; treat TDT as an outcome measure to
  characterise, not settled science.
- Healthy TDT values around 30 to 50 ms give the design target: the rig's stimulus timing must
  resolve well below that. Motor rise and stop time (ERM motors are slow, 20 ms or more) is the
  main engineering risk; characterise with an accelerometer and consider it a thesis
  contribution (instrument validation).

### 1.7 Psychophysics the rig can run with fixed-intensity motors

- "Percept of the duration of a vibrotactile stimulus is altered by changing its amplitude"
  (PMC4439551): duration difference limen approximately 13 percent, Weber's law holds for
  standards 500 to 1500 ms. So duration discrimination staircases are legitimate psychophysics.
- Francisco et al. finding via PMID 18651137: vibrotactile amplitude discrimination follows
  Weber's law (not usable here, amplitude fixed; cited to justify choosing duration and timing
  as the manipulated variables instead).

### 1.8 Force steadiness and force perception training (supports a graded-force game)

- Kornatz KW, Christou EA, Enoka RM (2005). "Practice reduces motor unit discharge variability in
  a hand muscle and improves manual dexterity in old adults." Journal of Applied Physiology,
  PMID 15691902. Light-load practice reduced discharge variability and improved dexterity.
- "Can Resistance Training Improve Upper Limb Postural Tremor, Force Steadiness and Dexterity in
  Older Adults? A Systematic Review." Sports Medicine 2019, DOI 10.1007/s40279-019-01141-6. All
  eight studies in healthy older adults reported steadiness or dexterity improvements.
- "Effectiveness of a home training program on improving pinch force perception in older adults."
  Journal of Hand Therapy 2024 (article S0894-1130(24)00003-6). Home force-perception training
  is feasible and effective in older adults.

### 1.9 Games and adherence (general support)

- "Serious games for upper limb rehabilitation after stroke: a meta-analysis." Journal of
  NeuroEngineering and Rehabilitation 2021, DOI 10.1186/s12984-021-00889-1.
- "Serious games for upper limb rehabilitation: a systematic review." PMID 28359181.
  Consistent adherence and engagement benefits; custom games outperform off-the-shelf for
  clinical outcomes. Motivators: real-time feedback, challenge, individualised difficulty.

## 2. Candidate game modes (buildable on this exact rig)

### Mode A: Buzz Hunt (vibrotactile localisation and detection)

Target groups: post nerve repair (median or ulnar), post carpal tunnel release monitoring, DPN
hand involvement monitoring.

Trial loop: hands rest flat. A single vibration pulse (start 300 ms) fires on one random finger.
Player presses the finger that buzzed. Correct press within the response window scores, streaks
multiply. Catch trials (roughly 10 percent, no stimulus) punish guessing and give false alarm
rate. Levels shorten the pulse via an adaptive staircase (2-down 1-up on duration converges on
70.7 percent correct), add distractor pre-pulses on the other hand (cross-hand simultaneous is
allowed by the hardware), then add two-pulse sequences on different fingers where the player must
press both fingers in the felt order.

Game dressing: whack-a-mole in the dark theme. The mole only reveals itself through the buzz. Combo
meter, level map, per-finger accuracy shown as mole tunnels lighting up.

Difficulty progression: pulse duration staircase per finger (interleaved staircases so the player
cannot predict), response window shrink, distractor probability, sequence length 1 to 3.

Logged per trial: stimulus finger, pulse duration, pattern id, catch flag, response finger(s),
press force curve, RT, staircase state and reversals.

Notebook computes: per-finger localisation accuracy and an 8-finger confusion matrix (digital
misreferral map, direct analogue of Weber et al. 2023), duration detection threshold per finger
(mean of last N staircase reversals plus logistic psychometric fit), d-prime and criterion from
hits vs catch-trial false alarms, RT distributions, session-over-session slopes with mixed models.
ICC across repeat sessions for the thesis reliability chapter.

Evidence chain: locognosia is among the most responsive outcomes after nerve repair (effect sizes
above 0.8, Jerosch-Herold 2003) and improved with home training at 1.5 and 3 years (Vikström
2017); misreferral mapping is current research practice (Weber 2023, Journal of Neurophysiology);
duration-based staircases are valid psychophysics (PMC4439551). For post-release CTS pitch this
as objective outcome tracking, because the 2016 RCT says sensory relearning does not beat control
on tactile outcomes there.

Honest limits: fixed intensity forces duration-proxy thresholds; motor rise time must be
characterised or thresholds are biased.

### Mode B: Gap Radar (temporal acuity: gap detection and TDT)

Target groups: focal hand dystonia characterisation, nerve repair recovery tracking, healthy
baselines; TDT is also a general basal ganglia and somatosensory processing measure.

Trial loop: sonar theme. On one finger, either one continuous buzz or two short buzzes separated
by a silent gap. Player answers "one contact or two" by pressing one of two designated response
fingers on the OTHER hand (keeps stimulus and response channels separate). Adaptive staircase on
gap length. Second stage: two pulses on two different fingers of the same hand at a stimulus
onset asynchrony at or above pulse length (hardware: one motor per hand at a time, so use 10 to
20 ms pulses to reach short asynchronies), or on opposite hands for true simultaneity; player
reports which finger came first (temporal order judgement).

Game dressing: submarine sonar operator. One ping or two? Which quadrant pinged first? Depth
levels as difficulty tiers, oxygen meter as the streak mechanic.

Difficulty progression: staircase drives gap and asynchrony down; pulse length shortens; lapse
catch trials with obvious gaps keep attention honest.

Logged per trial: finger(s), pulse lengths, gap or asynchrony, response, RT, staircase state.

Notebook computes: gap detection threshold and TDT-style threshold in ms per finger and hand
(staircase reversals plus full psychometric function fit, threshold and slope and lapse rate),
TOJ threshold, test-retest ICC, comparison against published healthy TDT values (about 29 to 49
ms across groups in Borngräber 2022).

Evidence chain: TDT is an established dystonia endophenotype candidate (Bradley 2009 Brain; Conte
2017 review) with a documented non-replication in musician's dystonia (Borngräber 2022), which
the thesis should cite as open science territory: a cheap home device that measures TDT
longitudinally is a contribution regardless of which side wins.

Honest limits: electrical taps are the literature standard; vibration motors are slower and the
absolute thresholds will not match published electrical-stimulus norms. Position as a
device-specific TDT variant with its own reliability estimate, and characterise motor onset and
offset latency with an accelerometer first.

### Mode C: Steady Squeeze (graded force control, the untapped analogue signal)

Target groups: CTS pre and post release, DPN, older adults, and as an adjunct for dystonia
retraining (grading of force is part of the Byl programme).

Trial loop: a target force band (for example 15 to 25 percent of that finger's calibrated
maximum) appears as a flight corridor. Player presses the cued finger to enter the corridor and
hold for 3 to 5 s. Three phase types per block: (1) full visual feedback, (2) lights-off, where
feedback freezes mid-hold and the player must maintain force blind, (3) echo trials, where the
player must reproduce the previous target with no corridor drawn at all. Vibration on the pressed
finger delivers success ticks (short pulse when entering the band), which doubles as augmented
sensory feedback.

Game dressing: drone in a wind corridor (Basil's home turf). Corridor narrows with skill, wind
gusts are lights-off phases, night flights are echo trials. Score is time-in-corridor.

Difficulty progression: corridor width narrows on success; hold lengthens; lights-off proportion
rises; per-finger targets diverge so weak fingers get their own corridor width (ties into the
existing adaptive mode logic without duplicating it: this is force grading, not press counting).

Logged per sample (200 Hz): force on all 8 pads, corridor bounds, feedback state. Per trial:
finger, target, phase type, entry time, exits.

Notebook computes: RMSE and coefficient of variation inside the hold, time-in-band, overshoot at
entry, rate of force development, and the headline thesis metric: sensory dependence index =
(lights-off error minus feedback error), the exact contrast where Li et al. 2015 showed CTS
collapses (p < 0.001). Echo trials give constant and variable error of force reproduction
(proprioceptive memory). Longitudinal mixed models per finger.

Evidence chain: CTS impairs blind force maintenance but visual feedback masks it (Li, Evans,
Seitz, Li 2015, Clinical Neurophysiology); deficits are bilateral in unilateral CTS (PMID
19066868); DPN impairs grip force control with preserved strength (Lima et al. 2017, Neuroscience
Letters; Experimental Brain Research 2023); force steadiness is trainable (Kornatz 2005; Sports
Medicine 2019 systematic review; Journal of Hand Therapy 2024 home pinch-force program). The
post-release Cochrane vacuum (Peters 2016) means an objective, cheap outcome tracker is itself a
defensible contribution.

Honest limits: SingleTact pads measure normal force of a flat finger press, not precision pinch
between thumb and finger; the deficit literature is mostly pinch grip. Same sensorimotor loop,
different grip configuration; say so in the thesis.

### Mode D: Never Twice (anti-stereotypy sensorimotor retraining for focal hand dystonia)

Target group: task-specific focal hand dystonia (writer's cramp, musician's dystonia). Small
population, exploratory positioning, strongest mechanism story in the cluster.

Trial loop: each trial welds a sensory gate to a motor production. The rig plays a short rhythm
pattern (2 to 4 pulses, varied gaps) on a random finger. Player must first answer a
discrimination question about it (same or different vs the previous pattern; response on the
other hand), and only if correct does the motor half unlock: reproduce that rhythm on a DIFFERENT
named finger while keeping each press inside a light force band. A constraint generator
guarantees no finger, force band and rhythm combination repeats within a session: the game
mechanically enforces the non-stereotyped, attended, sensory-first practice the Byl programme
prescribes, which is exactly what human therapists find hard to sustain for hours.

Game dressing: jazz improviser who is never allowed to play the same lick twice. The band calls a
riff by touch, you answer it on another string, clean and soft. Repetition literally scores zero.

Difficulty progression: pattern length up, gap differences down (this embeds a temporal
discrimination staircase inside the game), force band narrows, inter-finger transitions get
harder, cross-hand rounds.

Logged per trial: pattern spec, gate answer and RT, reproduced press onsets and force curves,
finger map, novelty hash of the trial spec.

Notebook computes: sensory gate accuracy and embedded discrimination thresholds over sessions;
rhythm reproduction error (onset asynchrony, inter-onset interval deviation); force band
compliance; a stereotypy index (entropy of produced timing and finger sequences) proving the
anti-repetition engine worked; per-finger independence trend borrowed as covariate from the
existing chords enslavement metric. Optional TDT from Mode B as a companion outcome.

Evidence chain: repetitive stereotyped input degrades the S1 hand map in primates (Byl and
Merzenich 1997, PMID 9062569); learning-based sensorimotor retraining improves motor control and
alters brain activation (Byl and McKenzie 2000; Byl 2009 home program, PMID 19285832); sensory
motor retuning normalises cortical finger maps in musicians (Candia 2003, PNAS); pure sensory
discrimination training improved both spatial acuity and the Fahn dystonia scale, gains held at 1
year (Zeuner 2002 Annals of Neurology; Zeuner and Hallett 2003). Known burden problem (8 to 12
weeks, hours daily) is the gap a home game fills.

Honest limits: no RCT-level evidence for any retraining variant; recruitment of FHD patients for
a thesis study is hard (position as design plus healthy-subject validation plus case study);
Borngräber 2022 warns that musician's dystonia may not show the TDT abnormality.

## 3. Cross-cutting engineering notes

- Motor characterisation study needed first: measure ERM (or LRA) rise and stop times with an
  accelerometer or the force pad itself; all duration and gap thresholds inherit this systematic
  error. This doubles as an instrument-validation section for the thesis.
- One motor per hand at an instant: all within-hand stimuli must be sequential with
  onset-to-onset spacing at or above pulse length; true simultaneity only cross-hand. Modes above
  are designed inside this envelope.
- Staircase infrastructure (2-down 1-up, interleaved, reversal averaging, logistic fit with lapse
  parameter) is shared across Modes A, B and D: build once.
- Signal detection (d-prime), confusion matrices, ICC and mixed-effects longitudinal slopes are
  shared notebook modules.

## 4. Conflicts surfaced (do not silently pick a side)

1. Sensory relearning post carpal tunnel release: pilot promising (Jerosch-Herold 2012) but the
   definitive RCT negative on tactile outcomes (Jerosch-Herold 2016). Design response: for CTS,
   lead with force control (Mode C) and use Mode A as measurement, not claimed therapy.
2. TDT as dystonia endophenotype: strong for adult-onset idiopathic focal dystonias (Bradley 2009;
   Conte 2017) but not replicated in musician's dystonia (Borngräber 2022).
3. Early vs late sensory re-education: Lundborg and Rosen argue early phase 1 training; the
   mirror-based early RCT (Paula 2016) found no advantage over late training.
4. Vibrometry for early CTS detection: some older studies claim vibrogram changes precede other
   findings; the counterposition is that early CTS is demyelinating while vibration thresholds
   track axonal loss, so early sensitivity is poor. Treat vibration thresholds as monitoring, not
   screening.
