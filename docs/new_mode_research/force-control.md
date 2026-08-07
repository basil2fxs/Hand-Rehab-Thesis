# Fine force control cluster: literature notes and game mode candidates

Research subagent notes, 2026-08-07. Cluster: visuomotor force tracking,
force steadiness, grip force scaling, precision isometric hold, force
ramps, proprioceptive force matching. Hardware frame: per-finger
SingleTact pads streaming 200 Hz analogue force, currently used only as
a press threshold. This cluster turns the full force signal into the
primary game input.

## 1. Why this cluster fits the device

The sensors already stream continuous force at 200 Hz. Every task in
this literature is isometric force against a fixed surface with visual
feedback on a screen, which is exactly what the rig does with hands
flat. No new hardware. The literature's standard measures (RMSE against
a target, coefficient of variation, spectral power of force
fluctuations, force matching error, rate of force rise and release) all
come straight out of a logged 200 Hz trace, so the analysis notebook
gets rich quantitative outcomes per session.

Force fluctuations of interest sit below about 12 Hz (visual control of
force literature), so 200 Hz sampling and a 60 Hz display are
comfortably sufficient.

## 2. Confirmed sources

### Force variability and steadiness in stroke

- Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH (2013).
  Increased Force Variability in Chronic Stroke: Contributions of Force
  Modulation below 1 Hz. PLOS ONE 8(12): e83468.
  13 chronic stroke vs 13 age-matched controls. Isometric grip at 5, 25,
  50 percent MVC held 20 s. Paretic hand CoV significantly higher than
  controls and non-paretic. Spectral signature: more normalised power
  0.1 to 0.3 Hz, less 0.5 to 0.8 Hz. Frequency structure predicted
  variability with R squared 0.82. Variability tracked Fugl-Meyer
  severity. This gives the notebook a validated biomarker: sub-1 Hz
  spectral shift, not just CoV.

- Naik SK, Patten C, Lodha N, et al (2011). Force control deficits in
  chronic stroke: grip formation and release phases. Experimental Brain
  Research 211: 1-15.
  9 stroke, 9 age-matched, 9 young. Ramp up, hold, release at 5, 10, 20
  percent MVC per second. Outcomes: RMSE, SD, step number, mean pause
  duration. Segmentation measures (step number, pause duration) were the
  discriminating outcomes between groups.

- Pennati GV, Plantin J, Carment L, et al (Lindberg PG senior author)
  (2020). Recovery and Prediction of Dynamic Precision Grip Force
  Control After Stroke. Stroke 51(3): 944-951.
  80 first-ever stroke patients tested at 3 weeks, 3 months, 6 months,
  plus 23 controls. Strength-Dexterity spring compression task.
  Coordination and dexterity improved over 6 months, repeatability did
  not; deficits persisted even in mild patients. Corticospinal tract
  lesion load was the strongest predictor of 6-month dexterity.
  Longitudinal force control metrics are sensitive where clinical scales
  saturate.

- Archer DB, Kang N, Misra G, Marble S, Patten C, Coombes SA (2017).
  Visual feedback alters force control and functional activity in the
  visuomotor network after stroke. NeuroImage: Clinical 17: 505-517.
  15 chronic stroke vs 15 controls, grip at 15 percent MVC under three
  visual gains. Stroke vs control force error gap shrank from about 21
  percent MVC at low gain to about 3 percent at high gain. Visual gain
  is a clean difficulty knob: raise gain to help weak patients, lower it
  to raise challenge.

- Wasaka T, Ando K, Nomura M, Toshima K, Tamaru T, Morita Y (2022).
  Visuomotor Tracking Task for Enhancing Activity in Motor Areas of
  Stroke Patients. Brain Sciences 12(8): 1063.
  Matching a target grip force pattern with real-time feedback enhanced
  movement-related cortical potentials from the affected hemisphere;
  simple movement without tracking did not. Direct evidence the tracking
  task itself, not mere pressing, drives use-dependent plasticity.

- Force variability is a potential biomarker of motor impairment in
  hemispheric stroke survivors. bioRxiv preprint, 2024
  (10.1101/2024.09.08.611881). Preprint only, not peer reviewed; noted
  for direction of the field, not as a load-bearing citation.

### Training and RCT evidence that force feedback tasks transfer

- Kurillo G, Gregoric M, Goljar N, Bajd T (2005). Grip force tracking
  system for assessment and rehabilitation of hand function. Technology
  and Health Care 13(3): 137-149.
  The template for this exact build: force sensor plus screen tracking
  used both as assessment (32 healthy across ages) and as a training
  tool in 10 post-stroke patients.

- Effect of task-oriented training assisted by force feedback hand
  rehabilitation robot on finger grasping function in stroke patients
  with hemiplegia: a randomised controlled trial. Journal of
  NeuroEngineering and Rehabilitation 21 (2024), 10.1186/s12984-024-01372-3.
  44 hemiplegic stroke patients, 22 per arm, 4 weeks. Experimental group
  beat controls on FMA-Hand, ARAT, grip strength, active range of motion.

- Effects of Computer-Aided Interlimb Force Coupling Training on Paretic
  Hand and Arm Motor Control following Chronic Stroke: A Randomized
  Controlled Trial. PLOS ONE 2015, 10.1371/journal.pone.0131048.
  Bilateral isometric handgrip force training, 4-week intervention,
  blinded assessment.

- Marmon AR, Gould JR, Enoka RM (2011). Practicing a Functional Task
  Improves Steadiness with Hand Muscles in Older Adults. Medicine and
  Science in Sports and Exercise 43(8).
  23 adults 70 plus. Pegboard performance was about 45 percent explained
  by pinch and finger abduction force steadiness, and practice improved
  steadiness. Steadiness is functionally meaningful, not a lab
  curiosity.

- Can Resistance Training Improve Upper Limb Postural Tremor, Force
  Steadiness and Dexterity in Older Adults? A Systematic Review. Sports
  Medicine 2019, 10.1007/s40279-019-01141-6.
  All eight studies in healthy older adults reported reduced tremor or
  improved steadiness and dexterity after training.

- Relationship Between Force Steadiness and Functionality in Older
  Adults: A Systematic Review With Meta-Analysis. Scandinavian Journal
  of Medicine and Science in Sports, 10.1111/sms.70040. Found in search;
  year not pinned down from the capture, listed for follow-up.

- Handgrip force steadiness in young and older adults: a reproducibility
  study. BMC Musculoskeletal Disorders 2018,
  10.1186/s12891-018-2015-9. Reproducibility data for steadiness
  protocols; authors not captured in my search snippet.

### Carpal tunnel syndrome

- Li K, Evans PJ, Seitz WH Jr, Li ZM (2014, issue dated 2015). Carpal
  tunnel syndrome impairs sustained precision pinch performance.
  Clinical Neurophysiology 126(1): 194-201.
  11 CTS vs 11 matched controls. 5 N pinch held 60 s, visual feedback
  removed at the 30 s mark. With feedback: groups equal on RMSE. Without
  feedback: CTS error significantly higher, p below 0.001. CTS CoV
  higher in both conditions. The vision-removed condition is the CTS
  discriminator, which a game can implement as a feedback-fade level.

- Functional sensibility assessment. Part II: Effects of sensory
  improvement on precise pinch force modulation after transverse carpal
  tunnel release. PMID 19402148 (2009). Sensory recovery after release
  surgery restored precise pinch force modulation. Venue not captured in
  snippet; verify before citing in the thesis.

- Additional CTS papers surfaced but details unverified by me: CTS
  impairs reach-to-pinch (PMC3954882), CTS impairs index finger
  responses to unpredictable perturbations (PMC5600639), CTS force
  coordination and muscle coherence during precision pinch, Journal of
  Medical and Biological Engineering 2017 (10.1007/s40846-017-0232-6).
  Consistent story: median nerve compression degrades afferent feedback,
  patients over-grip with excessive safety margin and go inaccurate when
  vision is removed.

### Parkinson's disease

- Davidson S, Learman K, Rosenfeldt AB, Zimmerman E, Alberts JL (2026).
  Parkinson's disease impairs grip force release during a sinusoidal
  force tracking task. Experimental Brain Research 244(4): 46.
  0.2 Hz sine tracking, 10 to 30 percent MVC, 32 s trials. 10 PD off
  medication, 10 older, 10 young. PD disproportionately impaired on
  force release versus generation, beyond normal ageing.

- Rate control deficits during pinch grip and ankle dorsiflexion in
  early-stage Parkinson's disease. PLOS ONE 2023,
  10.1371/journal.pone.0282203. Slower rates of force development and
  relaxation in PD across effectors.

- Measures of motor segmentation from rapid isometric force pulses are
  reliable and differentiate Parkinson's disease from age-related
  slowing. PMID 35768733 (2022). Segmented force-time curves; pulse
  duration prolonged with large effect sizes; measures reliable.

- Force Control Deficits in Individuals with Parkinson's Disease,
  Multiple Systems Atrophy, and Progressive Supranuclear Palsy. PLOS ONE
  2013, 10.1371/journal.pone.0058403. Force control deficits extend
  across parkinsonian syndromes.

- Older adults are impaired in the release of grip force during a force
  tracking task (PMC10894767). Release also degrades with normal ageing,
  so release metrics matter for older users generally. Venue not
  captured; verify.

### Multiple sclerosis

- Iyengar V, Santos MJ, Ko M, Aruin AS (2009). Grip Force Control in
  Individuals With Multiple Sclerosis. Neurorehabilitation and Neural
  Repair, 10.1177/1545968309338194.

- Grasping multiple sclerosis: do quantitative motor assessments provide
  a link between structure and function? Journal of Neurology 2013
  (10.1007/s00415-012-6639-7). Grip force variability elevated in MS and
  correlated with white matter fractional anisotropy near somatosensory
  and visual cortex. Deficits detectable even when standard clinical
  dexterity scores are normal.

### Proprioceptive force sense

- Upper Extremity Proprioception in Healthy Aging and Stroke
  Populations, and the Effects of Therapist- and Robot-Based
  Rehabilitation Therapies on Proprioceptive Function. Frontiers in
  Human Neuroscience 2015, 10.3389/fnhum.2015.00120. Proprioception
  impaired in over half of stroke survivors and impedes motor recovery.

- Pinch force sense test-retest reliability evaluation using
  contralateral force matching task. Scientific Reports 2024,
  10.1038/s41598-024-51644-0. Contralateral matching: normalised
  constant error ICC 0.76 to 0.85, normalised absolute error ICC 0.61
  to 0.81.

- Test-retest reliability of tip, key, and palmar pinch force sense in
  healthy adults. BMC Musculoskeletal Disorders 2020,
  10.1186/s12891-020-3187-7. Tip pinch ICC 0.783 to 0.895, palmar 0.752
  to 0.903, key 0.712 to 0.881.

- Assessment of grip force sense test-retest reliability in healthy male
  participants. Ergonomics 65(12), 2022, PMID 35179447. Absolute error
  ICC 0.42 to 0.63, constant error 0.49 to 0.60, most reliable at 20 N
  and 50 N targets.

- Effectiveness of a home training program on improving pinch force
  perception in older adults. Journal of Hand Therapy 2024,
  S0894-1130(24)00003-6. 11 healthy older adults (mean 77.2), 6 days a
  week for 6 weeks. 35 percent reduction in force matching errors
  (contralateral concurrent), plus Purdue pegboard and tactile acuity
  gains. Force sense is trainable, so a force matching game is therapy,
  not just assessment.

### Visual feedback as a controlled variable

- Intermittent visual information and the multiple time scales of visual
  motor control of continuous isometric force production. PMID 15971695
  (2005). Force variability decreased and force output irregularity
  increased as visual intermittency rate rose; vision influences force
  structure up to about 12 Hz.

- Greater amount of visual feedback decreases force variability by
  reducing force oscillations from 0-1 and 3-7 Hz. European Journal of
  Applied Physiology 2010, 10.1007/s00421-009-1301-5.

- Modulation of Force below 1 Hz: Age-Associated Differences and the
  Effect of Magnified Visual Feedback (PMC3569433). Magnified feedback
  changes sub-1 Hz force modulation in older adults. Venue not captured
  in snippet; verify.

- Enoka-lab style overview: Force Steadiness: From Motor Units to
  Voluntary Actions. Physiology, DOI 10.1152/physiol.00027.2020.
  Framework review linking motor unit discharge variability to
  steadiness. Author list not captured in my search snippet, so I have
  not attributed it; confirm before citing.

### Grip force scaling (context for the cluster)

- Grip force control during object manipulation in cerebral stroke.
  Clinical Neurophysiology 2003 (ScienceDirect S1388245703000427).
  Grip forces massively increased with excessive safety margins after
  stroke; sensory loss and impaired sensorimotor integration named as
  the major source. Authors not captured; verify.
- Parametric control of fingertip forces during precision grip lifts in
  children with DCD and DAMP. Neuropsychologia 2001 (S0028393200001329).
  Excessive grip force and high safety margins in DCD. Suggests
  paediatric DCD as a further patient group for force scaling games.
- Grip force scaling and sequencing of events during a manipulative task
  in Huntington's disease. PMID 11311303 (2001). Excessive grip force
  unrelated to task demands in HD.

## 3. What the cluster says, condensed

1. Patients across stroke, PD, CTS, MS and normal ageing share a family
   of continuous force control deficits invisible to threshold logic:
   elevated CoV, shifted sub-1 Hz spectral power, poor tracking, poor
   release, segmented ramps, degraded blind force sense, excessive
   scaling.
2. These measures correlate with clinical scales (Fugl-Meyer), predict
   function (pegboard about 45 percent explained by steadiness), and
   remain sensitive when clinical scores saturate (Pennati 2020).
3. They are trainable: tracking training in stroke (Kurillo 2005; JNER
   RCT 2024), steadiness practice in older adults (Marmon 2011; Sports
   Medicine 2019 review), force sense home training (J Hand Ther 2024,
   35 percent error cut).
4. Visual feedback gain and availability are validated difficulty
   levers with quantified effects (Archer 2017; intermittency work).
5. Condition-specific discriminators exist and map to game levels:
   feedback removal for CTS (Li 2014), release phase for PD (Davidson
   2026) and stroke (Naik 2011), low-force steadiness for ageing.

## 4. Candidate game modes

### Mode A: Glide (visuomotor force tracking)

Per trial: one finger drives a glider's altitude by force (10 to 30
percent MVC mapped to screen height). A target corridor scrolls right
to left for 30 s: sine at 0.1 to 0.5 Hz early, then ramps, steps,
sum-of-sines, pseudorandom. Coins sit on the corridor centreline;
staying in corridor builds a combo multiplier; leaving it stalls the
glider. Short vibration burst on corridor exit gives tactile error
feedback (one motor per hand, fine since one finger flies at a time).

Game not test: continuous scoring, coins, combo streaks, level map from
gentle hills (slow sine) to canyons (steps) to storms (pseudorandom),
per-finger characters.

Difficulty: corridor width, waveform frequency and predictability,
visual gain (Archer 2017 shows gain shifts patient error by an order of
magnitude), intermittent cursor blanking at expert levels.

Log per sample: t, finger, hand, raw force, target, corridor half
width, gain, feedback state. Per trial: MVC reference, waveform id.

Notebook: RMSE, CoV, time in corridor, tracking lag by
cross-correlation, normalised spectral power 0.1 to 0.3 and 0.5 to 0.8
Hz (Lodha stroke biomarker), release versus generation error on the
descending half of each cycle (Davidson PD marker), per-finger and
between-hand asymmetry, learning curves across sessions.

Conditions: stroke (Wasaka plasticity, Kurillo precedent, RCT
transfer), PD, CTS, MS, older adults.

### Mode B: Lighthouse (precision hold with feedback fade)

Per trial: press and hold one finger at a low target (5, 15, 25 percent
MVC) for 15 to 20 s to keep a lantern burning. Flame size tracks error;
flicker tracks fluctuation. At higher levels the room goes dark mid
hold (visual feedback removed) and the player holds by feel; the light
returns and scores the drift. This is Li 2014's CTS discriminator
turned into the core mechanic.

Game not test: nightly campaign, ships saved per steady night, wind
gust events, medals for blind-hold accuracy.

Difficulty: lower targets (steadiness is worst at low force), longer
blind windows, tighter tolerance, weakest-finger weighting borrowed
from the adaptive mode.

Log: 200 Hz force, target, feedback on and off timestamps.

Notebook: CoV and SD per lit and blind window, RMSE, post-fade drift
rate in N per s, drift direction (CTS tends to drift with error rather
than hold), sub-1 Hz spectra, lit-blind delta as the headline
CTS-sensitive metric, session-to-session reliability.

Conditions: CTS primary (deficit appears exactly when vision goes),
older adults (steadiness-function link), stroke, MS.

### Mode C: Echo (proprioceptive force matching)

Per trial: encode then reproduce. A bar shows the finger's force for 3
s at a cued target (10 to 40 percent MVC). Bar disappears. After a
delay (2 s early, up to 15 s later, which loads working memory), the
player reproduces the force blind for 3 s. Error is revealed as sonar
ping distance; closer pings score higher and buzz the vibration motor.
Variants: ipsilateral remembered (same finger), cross-finger (encode
index, reproduce ring), contralateral concurrent (reference finger on
one hand holds with feedback while the mirror finger matches blind;
uses the two-hand rig, cross-hand vibration allowed).

Game not test: submarine sonar theme, echo accuracy streaks, depth
levels for delay length, duet levels for cross-hand.

Difficulty: delay length, target level spread, cross-finger and
cross-hand variants, narrower scoring bands.

Log: target, full encode trace, full reproduction trace, delay, finger
pair, hand pair.

Notebook: constant error, absolute error, variable error, all
normalised to target, per force level and per delay (delay slope
separates memory load from sense), per finger, hand asymmetry.
Reliability benchmarks exist (ICC roughly 0.6 to 0.9 across pinch
force sense studies), and training effect size exists (35 percent
error reduction in 6 weeks, J Hand Ther 2024).

Conditions: CTS (sensory afferent loss), stroke (proprioception
impaired in over half), older adults, MS.

### Mode D: Throttle (ramp, hold, release rate control)

Per trial: fly a rocket through launch, cruise, landing by following a
trapezoid force profile: ramp up at a prescribed rate (5, 10 or 20
percent MVC per s, Naik 2011's exact levels), hold, then ramp down at a
prescribed rate to a soft landing. Abrupt or stepped release crashes
the landing. Very slow ramps are the hard levels because segmentation
shows up there.

Game not test: mission ladder, landing softness score, fuel bonus for
smooth throttle, planet themes per rate condition.

Difficulty: slower prescribed rates, higher plateaus, asymmetric up and
down rates, guide line replaced by endpoint markers only.

Log: 200 Hz force, target profile, phase markers.

Notebook: per-phase RMSE and SD, rate of force development, rate of
release, overshoot at plateau entry, undershoot at landing, step number
and mean pause duration (Naik segmentation metrics; also the reliable
PD discriminator from the motor segmentation work), release to
generation error ratio (PD and ageing marker).

Conditions: PD primary (release and segmentation), stroke (Naik), older
adults (release impairment), MS.

## 5. Feasibility notes common to all four

- Requires a per-finger MVC calibration routine (short max press per
  finger at session start); every target is then relative, which also
  handles SingleTact unit-to-unit variation.
- 200 Hz sampling covers the 0 to 12 Hz band the literature analyses.
  60 Hz display is standard in these paradigms.
- Single motor per hand is no constraint: modes A, B, D use one active
  finger at a time; mode C's cross-hand variant vibrates both hands,
  which the hardware allows.
- All modes log the same schema (t, finger, hand, force, target,
  feedback state), so one notebook section serves all four.
- None duplicates existing modes: rhythm is timing to a beat, chords is
  simultaneous thresholds, adaptive is threshold drill. These four are
  the first to use the continuous force value.

## 6. Unverified items flagged

- Enoka and Farina attribution for the Physiology steadiness review:
  title and DOI confirmed, author list not captured in my search.
- Venue for PMC10894767 (older adults release impairment), PMC3569433
  (sub-1 Hz magnified feedback), PMID 19402148 (sensibility after
  carpal tunnel release), and the 2003 Clinical Neurophysiology stroke
  grip scaling paper's author list: confirm before thesis citation.
- Scand J Med Sci Sports steadiness meta-analysis year: confirm.
