# Ranked brief: new game modes for the finger rehab rig

Date: 2026-08-07. Synthesis of five research clusters (force-control,
movement-disorders, stroke, carpal-nerve, paediatric-cognitive). All
anchor citations below were spot-checked in live web searches this
session: author list, year and venue confirmed for every one. Papers
the clusters flagged as unverified stay flagged and are not used as
anchors.

## How the merge went

- Visuomotor force tracking was proposed independently by three
  clusters (Glide, Force Pilot, Hover gate rounds) plus a ramp-release
  variant (Throttle). Merged into one mode with trial types.
- Precision hold with feedback fade was proposed by three clusters
  (Lighthouse, Steady Squeeze, Hover cloud rounds), and blind force
  reproduction (Echo) is the same paradigm minus the concurrent
  target. Merged into one mode.
- Vibrotactile discrimination was proposed by three clusters
  (Vibration Detective, Buzz Hunt twice, Gap Radar). Merged into one
  stimulus suite.
- Stop-signal was proposed by two clusters (Gatekeeper, Stop the
  Launch). Merged.
- Bimanual asymmetric force was proposed by two clusters (Load Split,
  Crane Crew) and both carry the same free mirror-movement
  measurement. Merged.

## Rank 1: Force Pilot (visuomotor force tracking)

Pitch: turn the unused 200 Hz analogue force signal into the primary
game input. One finger's force drives a drone's altitude through a
scrolling corridor of plateaus, ramps, sines near 0.2 to 0.6 Hz, and
pseudorandom assessment sections, with the release half of every ramp
scored separately.

Conditions: stroke (primary), Parkinson's disease, multiple
sclerosis, carpal tunnel syndrome, older adults, essential tremor
(spectral analysis, exploratory).

Play, trial by trial: per-finger max-press calibration at session
start. 20 to 30 s runs, force mapped 0 to 40 percent of that finger's
max onto screen height. Rings score, corridor exits stall, a short
buzz signals exit. Corridor width, waveform bandwidth, visual gain and
brief cursor blanking are the difficulty axes. Weakest fingers get
extra runs via the existing adaptive weighting.

Verified anchors:
- Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH (2013).
  Increased Force Variability in Chronic Stroke: Contributions of
  Force Modulation below 1 Hz. PLOS ONE 8(12):e83468. Sub-1 Hz
  spectral shift (more power near 0.2 Hz, less near 0.6 Hz) explained
  about 80 percent of the elevated variability. A ready-made notebook
  biomarker.
- Pennati GV, Plantin J, et al (2020). Recovery and Prediction of
  Dynamic Precision Grip Force Control After Stroke. Stroke
  51(3):944-951. 80 first-ever stroke patients over 6 months; force
  control metrics stay sensitive where clinical scales saturate.

Supporting (verified by the source cluster, not re-checked here):
Kurillo 2005 build template; Archer 2017 visual gain lever; Taud 2021
Frontiers in Neurology RCT where tracking training itself drove
recovery; Naik 2011 ramp segmentation; Davidson 2026 PD release
deficit.

Notebook: RMSE, CoV, time in corridor, cross-correlation lag,
normalised power 0.1 to 0.3 vs 0.5 to 0.8 Hz, release vs generation
error, step count and pause duration on slow ramps, per-finger
asymmetry, session learning curves.

Biggest risk: SingleTact accuracy and drift at very low force is
uncharacterised; a bench characterisation must come first (and doubles
as a thesis instrumentation section).

## Rank 2: Lighthouse (precision hold, feedback fade, force sense)

RETIRED, September 2026: built, tested and then removed from the app
as impractical to play. Kept here as the record of the idea.

Pitch: hold a low target force to keep a lantern lit, then the room
goes dark and you hold by feel; blind reproduction trials extend the
same mechanic to force memory. The lit-versus-blind error delta is a
published carpal tunnel discriminator turned into the core mechanic.

Conditions: carpal tunnel syndrome (primary), older adults, diabetic
peripheral neuropathy, stroke, multiple sclerosis.

Play, trial by trial: press and hold one finger at 5 to 25 percent of
calibrated max for 15 to 20 s. Flame size tracks error, flicker tracks
fluctuation. Higher levels blank feedback mid-hold, then score the
drift when light returns. Echo trials: see a target for 3 s, wait,
reproduce it blind; delay length loads memory. Cross-hand matching
uses the two-hand rig.

Verified anchors:
- Li K, Evans PJ, Seitz WH Jr, Li ZM (2015). Carpal tunnel syndrome
  impairs sustained precision pinch performance. Clinical
  Neurophysiology 126(1):194-201. With visual feedback CTS matched
  controls; with feedback removed error rose sharply (p below 0.001).
- Camacho-Villa MA, et al (2025). Relationship Between Force
  Steadiness and Functionality in Older Adults: A Systematic Review
  With Meta-Analysis. Scandinavian Journal of Medicine and Science in
  Sports 35(4):e70040. Upper-limb steadiness vs function r = 0.58,
  tasks at 5 to 25 percent MVC, exactly this mode's range.

Supporting: J Hand Ther 2024 home force-sense training (35 percent
error cut in 6 weeks); pinch force sense reliability ICCs 0.6 to 0.9;
Lima 2017 DPN force control deficit with preserved strength; Peters
2016 Cochrane vacuum after carpal tunnel release, which makes an
objective tracker a defensible contribution on its own.

Notebook: CoV and RMSE per lit and blind window, post-fade drift rate
and direction, lit-blind delta as headline metric, constant and
variable reproduction error by delay, sub-1 Hz spectra, test-retest
ICC against published bars.

Biggest risk: the CTS literature is thumb-finger pinch; the rig
measures flat-finger normal force. Same sensorimotor loop, different
grip, and the thesis must say so plainly.

## Rank 3: Buzz Hunt (vibrotactile perception suite)

Pitch: promote the vibration motors from feedback device to stimulus
device and run real psychophysics: localisation, duration
discrimination, gap detection and tactile sequence span, all with
adaptive staircases. It is the only candidate that opens a second
therapy channel rather than refining the first.

Conditions: stroke somatosensory loss (about half of survivors),
post nerve repair, children with unilateral cerebral palsy (a named
evidence gap: no proven tactile intervention exists for them), focal
hand dystonia (temporal thresholds), diabetic neuropathy monitoring.

Play, trial by trial: hands flat, eyes on screen. A pulse fires on
one finger; press the finger that buzzed. Catch trials punish
guessing. Levels shorten pulses via 2-down 1-up staircases, add
distractors on the other hand, then sequences to replay (with a
hidden repeating Hebb sequence), then one-buzz-or-two gap trials.
Within-hand stimuli are sequential, which the one-motor-per-hand rule
forces and standard psychophysics prefers anyway; cross-hand pairs
give true simultaneity.

Verified anchors:
- Carey L, Macdonell R, Matyas TA (2011). SENSe: Study of the
  Effectiveness of Neurorehabilitation on Sensation: A Randomized
  Controlled Trial. Neurorehabilitation and Neural Repair
  25(4):304-313. n = 50 chronic stroke; 10 hours of graded
  discrimination training beat exposure control, gains held at 6
  months. The training principles (just-above-threshold grading,
  attention, feedback, transfer probes) map directly onto staircase
  game design.
- Zeuner KE, et al (2002). Sensory training for patients with focal
  hand dystonia. Annals of Neurology (doi 10.1002/ana.10174). Eight
  weeks of braille training improved spatial discrimination and the
  Fahn dystonia scale, and sensory gains correlated with motor gains.
  Pure sensory training moved a motor outcome.

Supporting: Weber 2023 Journal of Neurophysiology misreferral mapping
(the confusion matrix is its digital analogue); Vikström 2017
locognosia home-training gains at 1.5 and 3 years; Auld 2014 child CP
evidence gap; Jerosch-Herold 2016 negative RCT for post-release CTS
sensory relearning, so for CTS this mode is measurement, not claimed
therapy.

Notebook: per-finger confusion matrix, duration and gap thresholds
from staircase reversals plus logistic psychometric fits, d-prime and
criterion, span curves, Hebb learning slope, threshold learning
curves, ICC across sessions.

Biggest risk: ERM motor rise and stop time (around 20 ms or more)
biases every temporal threshold; an accelerometer characterisation of
the motors must precede data collection.

As built, 2026-09 revision. The duration staircase on localisation
was played on the rig and failed in exactly the way the risk above
predicts: each correct answer shortened the pulse until it could not
be felt, because the 10 mm coin ERM class on the rig has a lag of
about 40 ms and a rise of about 87 ms (Precision Microdrives 310-103
datasheet), so commands under about 100 ms are fainter twitches, not
shorter buzzes. Localisation now plays one fixed 150 ms pulse (inside
the 50 to 200 ms usable band Kaaresoja and Linjama 2005 found on a
phone motor) and the difficulty ladder moves the response window
(3.0, 2.0, 1.5, 1.2 s; up on 6 correct of the last 8, down on 2
misses in the last 4). The summary metrics are accuracy at the fixed
pulse, d-prime against the catch trials, median RT and the top window
level; the duration staircase survives behind
buzz_hunt.duration_staircase for reproducing earlier blocks. The gap
stage keeps its staircase with a 120 ms floor (the motor's 115 ms
spin-down) and 150 ms shorts. finger_rehab/game/modes/buzz_hunt.py,
section WHY THE PULSE IS FIXED, carries the sources.

## Rank 4: Load Split (bimanual asymmetric force sharing)

Pitch: the mirror mode is symmetric and synchronous; the stroke and
cerebral palsy literature says the therapeutic action is in
asymmetric, role-differentiated bimanual work where the weak hand has
a real job. Scoring weights the paretic share, so the game is
unwinnable by letting the strong hand carry it, a reinforcement
answer to learned non-use with no restraint mitt.

Conditions: stroke (primary), unilateral cerebral palsy in children
(primary for the paediatric arm), developmental coordination disorder
(secondary).

Play, trial by trial: both hands on pads. See-saw trials: hold a beam
level around an off-centre pivot so balance requires an unequal
split. Trade trials: keep total force constant while shifting share
along a ramp. Crane trials: the affected hand holds force in a band
while the other taps a sequence; roles swap. Anti-phase trials: a
metronome paces alternating left-right presses. During every
unimanual phase the resting hand's pads silently record involuntary
mirror force, a validated force-based mirror movement measure for
free.

Verified anchors:
- Cauraugh JH, et al (2009, online; issue 2010). Bilateral movement
  training and stroke motor recovery progress: a structured review and
  meta-analysis. Human Movement Science. 25 comparisons, 366 patients,
  SMD 0.734 (SE 0.125). Note: publicly contested in a response letter;
  the thesis must present both sides.
- Novak I, Morgan C, Fahey M, et al (2020). State of the Evidence
  Traffic Lights 2019: Systematic Review of Interventions for
  Preventing and Treating Children with Cerebral Palsy. Current
  Neurology and Neuroscience Reports 20(2):3. Bimanual training and
  CIMT are green-light interventions for hand function.

Supporting: Kang and Cauraugh 2014 bimanual variability deficit at 5
and 25 percent MVC; HABIT-ILE RCT lineage for intensive game-framed
bimanual practice; GriFT force-based mirror movement device paper;
Kuo 2018 mirror movement framework.

Notebook: paretic share time series and error, asymmetry index,
between-hand cross-correlation lag, relative phase and its
variability (circular stats) for anti-phase blocks, variance of sum
vs difference (bilateral synergy index), mirror ratio and coherence
from the resting hand, transfer onto Force Pilot unimanual metrics.

Biggest risk: the bilateral training efficacy literature is
contested, so the honest thesis position is measurement plus
mechanism, with training framed as evidence-informed rather than
proven.

## Rank 5: Tap Sprint (bradykinesia tapping and sequence effect)

Pitch: a 20 to 30 s tapping sprint that implements the validated
keyboard bradykinesia test family, with one upgrade no keyboard has:
per-tap peak force, so the Parkinsonian sequence effect (progressive
amplitude decrement) becomes measurable and gamified, with a boost
multiplier for holding tap force above 80 percent of baseline.

Conditions: Parkinson's disease (primary), multiple sclerosis
disability tracking, ageing baselines.

Play, trial by trial: single-finger or alternating index-middle
sprints per hand; each tap drives a racer, tap force sets stride
power, ghost replays personal bests, both hands race in their own
lanes so asymmetry is visible.

Verified anchors:
- Noyce AJ, et al (2014). Bradykinesia-Akinesia Incoordination Test:
  Validating an Online Keyboard Test of Upper Limb Function. PLOS ONE
  9(4):e96260. 58 PD, 93 controls; kinesia score correlated with
  UPDRS motor score (r = -0.53), test-retest CV 6 percent.
- Shribman S, Hasan H, Hadavi S, Giovannoni G, Noyce AJ (2018). The
  BRAIN test: a keyboard-tapping test to assess disability and
  clinical features of multiple sclerosis. Journal of Neurology
  265(2):285-290. Kinesia score vs EDSS r = -0.594; strong agreement
  with the nine-hole peg test; pyramidal AUC 0.84.

Supporting: Akram 2022 Scientific Reports distal tapping test (AUC
0.90 alone, 0.95 combined, ICC above 0.9), closest analogue to this
hardware; Bologna 2020 Brain review defining the sequence effect;
Stegemöller 2009 2 Hz breakdown as a later difficulty axis.

Notebook: tap count, mean dwell, inter-press interval variance,
sequence-effect slopes (peak force and interval vs tap index),
hesitations and halts, asymmetry index, session trends against
published reliability bars.

Biggest risk: force amplitude is a proxy for kinematic amplitude and
keyboard-family UPDRS correlations are moderate (about 0.4 to 0.6),
so it is pitched as a sensitive within-person tracker, not a UPDRS
replacement.

## Rank 6: Stop the Launch (stop-signal inhibition with graded force)

Pitch: a consensus-compliant stop-signal task in a game skin, with a
hardware novelty: the 200 Hz pads catch partial presses on successful
stops, a graded inhibition-depth measure that normally needs EMG.
Gamification is itself validated for this task family.

Conditions: ADHD assessment in children (primary), post-stroke
executive profiling (secondary), general paediatric impulse-control
research.

Play, trial by trial: choice-RT go trials (press the mapped finger to
launch a drone, 75 percent of trials); on 25 percent an abort tone
fires after a staircased stop-signal delay (50 ms steps, holding stop
success near 50 percent) and the child must withhold. Auditory stop
signal sidesteps 60 Hz frame quantisation. Dual-task blocks for the
stroke arm add a digit-monitoring load.

Verified anchors:
- Verbruggen F, et al (2019). A consensus guide to capturing the
  ability to inhibit actions and impulsive behaviors in the
  stop-signal task. eLife 8:e46323. The 12-recommendation methods
  standard this mode implements directly.
- Lipszyc J, Schachar R (2010). Inhibitory control and
  psychopathology: A meta-analysis of studies using the stop signal
  task. Journal of the International Neuropsychological Society
  16:1064-1076. SSRT deficit in ADHD g = 0.62.

Supporting: Friehs 2020 JMIR Serious Games (game skin preserves SSRT
validity and cuts variance); Kofler 2013 RT-variability meta; Ganesan
2024 Nature Neuroscience null RCT, which is why this is framed as
measurement, never as ADHD treatment.

Notebook: SSRT by the integration method with omission replacement,
inhibition function, ex-Gaussian RT fits (tau for ADHD), post-error
slowing, dual-task costs, partial-press amplitude and latency on stop
trials as the novel graded measure.

Biggest risk: furthest of the six from hand rehabilitation proper; it
earns its slot as the executive arm of an assessment battery, and the
partial-press analysis needs its own validation against the noise
floor of the pads.

## Near misses

- Carry the Beat (synchronisation-continuation timing): strong PD
  evidence, including a Human Movement Science 2019 RCT where four
  minutes of seated cued tapping raised gait velocity 9.5 percent,
  but it overlaps the existing rhythm mode; better shipped as an
  upgrade to rhythm (cue dropout, tempo staircase, Wing-Kristofferson
  analytics) than as a new mode.
- Hold the Line (MS fatigability, static fatigue index): validated
  and genuinely unique, but single-condition, needs sustained
  near-max effort that risks pad saturation and patient burden;
  strongest second-tier candidate if MS becomes a focus.
- Sound Forge (letter-sound binding for dyslexia): RCT-backed
  construct, but it uses fingers only as buttons, ignores the force
  asset, and the GraphoGame literature says outcomes hinge on adult
  co-play; dyslexia is already served by the syllables mode.
- Never Twice (anti-stereotypy retraining for focal hand dystonia):
  best mechanism story in the whole search, but a tiny recruitable
  population and no RCT-level evidence for any retraining variant;
  its temporal discrimination ingredient survives inside Buzz Hunt.
- Standalone TDT instrument (Gap Radar): folded into Buzz Hunt;
  motor rise time limits comparability with electrical-stimulus
  norms and the endophenotype claim failed to replicate in musician's
  dystonia.
- Working memory span and finger gnosis games: far-transfer training
  claims are dead on arrival (Melby-Lervag 2016); span and Hebb
  measures survive as Buzz Hunt analytics instead.
- Dual-task DCD mode: group effects in children with DCD are mixed
  to null; kept only as an optional overlay.

## Citation verification log (this session)

Confirmed by web search with author, year and venue: Lodha 2013 PLOS
ONE; Pennati 2020 Stroke; Li 2015 Clinical Neurophysiology;
Camacho-Villa 2025 Scand J Med Sci Sports; Carey 2011 Neurorehabil
Neural Repair; Zeuner 2002 Annals of Neurology; Cauraugh 2009/2010
Human Movement Science (response letter also confirmed); Novak 2020
Curr Neurol Neurosci Rep; Verbruggen 2019 eLife; Lipszyc and Schachar
2010 JINS; Noyce 2014 PLOS ONE; Shribman 2018 Journal of Neurology.
Items the clusters flagged as unverified (author lists for several
PMC-only locators, the Enoka steadiness review attribution, venue for
PMID 19402148 and PMC10894767) remain unverified and are excluded
from anchor status.
