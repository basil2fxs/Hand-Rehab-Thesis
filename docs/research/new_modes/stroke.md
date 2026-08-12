# Stroke cluster research notes

Cluster: stroke hand rehab beyond the existing modes. Force modulation and
grading, sensory loss and re-education, learned non-use, proprioception,
spasticity-compatible training, bimanual asymmetric coordination, executive
deficits (inhibition, dual-task cost).

Device constraints kept in view throughout: one SingleTact force pad per
finger read as analogue at 200 Hz (currently threshold-only, full signal
unused), one vibration motor per finger (fixed intensity, variable duration
and pulse pattern, one motor per hand at a time, cross-hand simultaneous
fine), 60 Hz screen, speaker, seated, hands flat, CSV logging, Python
notebook analysis.

Existing modes not to duplicate: reaction (simple + choice RT), pattern
(SRTT), chords, syllables, adaptive, rhythm, mirror (bilateral synchronous).

## Gap analysis against existing modes

1. The force signal is only a threshold. Nothing trains or measures graded,
   continuous force control. This is the single biggest untapped asset.
2. The vibration motors are output-only cues. Nothing uses them as afferent
   stimuli for sensory discrimination training.
3. Mirror mode is synchronous and symmetric. No mode trains asymmetric force
   division or anti-phase bimanual coordination, which is where the stroke
   bimanual literature sits.
4. Reaction mode measures going fast. No mode measures or trains stopping,
   and no mode imposes a concurrent cognitive load, so inhibition and
   dual-task cost are unmeasured.
5. No mode removes visual feedback to probe memory-guided or sense-guided
   force, which is the closest this hardware gets to proprioceptive
   (force sense) training.

## Literature found (all confirmed in searches this session)

### Force modulation and grading after stroke

- Carey JR, Kimberley TJ, Lewis SM, Auerbach EJ, Dorsey L, Rundquist P,
  Ugurbil K. Analysis of fMRI and finger tracking training in subjects with
  chronic stroke. Brain, 125(4), 2002. 10 chronic stroke subjects, 18 to 20
  sessions of finger tracking training against target waveforms, randomised
  treatment vs control with crossover. Outcomes: Box and Block, tracking
  accuracy, fMRI activation. Foundational for tracking training of fingers.
  https://academic.oup.com/brain/article/125/4/773/260755
  https://pubmed.ncbi.nlm.nih.gov/11912111/

- Kurillo G, Gregoric M, Goljar N, Bajd T. Grip force tracking system for
  assessment and rehabilitation of hand function. Technology and Health
  Care, 2005. Force tracking against ramp, sine and rectangular targets,
  difficulty via target shape, force level and dynamics, performance scored
  as relative tracking error. Tested in 32 healthy subjects and applied as a
  training tool in 10 post-stroke patients.
  https://pubmed.ncbi.nlm.nih.gov/15990417/

- Taud B, Lindenberg R, Darkow R, Wevers J, Hofflin D, Grittner U, Meinzer M,
  Floel A. Limited Add-On Effects of Unilateral and Bilateral Transcranial
  Direct Current Stimulation on Visuo-Motor Grip Force Tracking Task Training
  Outcome in Chronic Stroke. A Randomized Controlled Trial. Frontiers in
  Neurology, 2021. 40 chronic stroke patients, 5 consecutive days, 240
  trials per session in 8 blocks, isometric paretic-thumb force to a 30 to
  40 percent MVC window, about 23 min per session. Training improved
  performance in all groups; anodal tDCS added 2.6 to 2.8 FM-UE points vs
  sham (Cohen's d 0.34). Key point for us: the tracking training itself
  drove recovery.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8631774/

- Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH. Increased Force
  Variability in Chronic Stroke: Contributions of Force Modulation below
  1 Hz. PLOS ONE, 2013. Chronic stroke vs controls, submaximal isometric
  grip. Stroke subjects showed more spectral power near 0.2 Hz and less
  near 0.6 Hz; this shifted modulation predicted about 80 percent of the
  variance in increased force variability. Gives us an exact notebook
  analysis to replicate.
  https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0083468

- Nowak DA, Hermsdorfer J, Topka H. Deficits of predictive grip force
  control during object manipulation in acute stroke. Journal of Neurology,
  250(7), 2003. Acute stroke patients grip with markedly elevated,
  poorly anticipated forces. Deficit evidence for predictive force scaling.
  https://pubmed.ncbi.nlm.nih.gov/12883929/

- Hermsdorfer et al. Grip force control during object manipulation in
  cerebral stroke. Clinical Neurophysiology, 2003 (found via ScienceDirect,
  author list not confirmed in my searches beyond Hermsdorfer as lead).
  Elementary grip force control impaired vs controls.
  https://www.sciencedirect.com/science/article/abs/pii/S1388245703000427

- Pennati GV, Plantin J, Carment L, Roca P, Baron JC, et al. Recovery and
  Prediction of Dynamic Precision Grip Force Control After Stroke. Stroke,
  2020. 80 first-ever stroke patients tested at 3 weeks, 3 and 6 months
  plus 23 controls. Force control and dexterity in the affected hand were
  dramatically lower even with mild motor impairment; force control
  improved over recovery.
  https://pubmed.ncbi.nlm.nih.gov/31906829/

- Improvements in force variability and structure from vision- to
  memory-guided submaximal isometric knee extension in subacute stroke.
  PubMed 2017. Vision-to-memory-guided force paradigm exists in the stroke
  literature; supports a feedback-fade difficulty axis.
  https://pubmed.ncbi.nlm.nih.gov/29097632/

- Force control deficit reviews found but authorship not confirmed in my
  searches: "Force control in chronic stroke" (Neuroscience and
  Biobehavioral Reviews, 2015, ScienceDirect S0149763415000500). Summary
  from search results: post-stroke force deficits include lower magnitude,
  higher task error, greater variability, increased regularity, and
  greater time lags.

### Sensory loss and re-education

- Carey L, Macdonell R, Matyas TA. SENSe: Study of the Effectiveness of
  Neurorehabilitation on Sensation: A Randomized Controlled Trial.
  Neurorehabilitation and Neural Repair, 2011. n = 50, median 48 weeks
  post-stroke, impaired texture discrimination, limb position sense or
  tactile object recognition. 10 hours of somatosensory discrimination
  training vs exposure to sensory stimuli. Significantly greater
  improvement in a standardised somatosensory deficit index with
  discrimination training, maintained at 6 weeks and 6 months. Training
  principles: graded discrimination just above threshold, attentive
  exploration, feedback, progression, transfer to untrained stimuli.
  https://journals.sagepub.com/doi/10.1177/1545968310397705
  https://www.researchgate.net/publication/50196104

- Serrada I, Hordacre B, Hillier SL. Does Sensory Retraining Improve
  Sensation and Sensorimotor Function Following Stroke: A Systematic Review
  and Meta-Analysis. Frontiers in Neuroscience, 2019. 38 trials, n = 1093.
  Some evidence for passive techniques (thermal, pneumatic compression,
  peripheral nerve stimulation); active sensory training data limited and
  mostly narrative. The evidence gap in active discrimination training is
  an opportunity for a well-instrumented device study.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6503047/

- Effects of somatosensory discrimination training on motor and functional
  recovery in patients with stroke: a systematic review and meta-analysis.
  Topics in Stroke Rehabilitation (Taylor and Francis), 2025. Found in
  search; confirms discrimination training is an active current topic.
  https://www.tandfonline.com/doi/full/10.1080/10749357.2025.2463285

- Vibrotactile enhancement in hand rehabilitation has a reinforcing effect
  on sensorimotor brain activities. Frontiers in Neuroscience, 2022.
  Vibration stimulation strengthened bilateral sensorimotor activation in
  stroke patients and improved training outcomes for poor performers.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9577243/

- Evaluation of Intervention Effectiveness of Sensory Compensatory Training
  with Tactile Discrimination Feedback on Sensorimotor Dysfunction of the
  Hand after Stroke. 2021 (PMC8534145). Tactile discrimination feedback
  training improved sensorimotor cortical reorganisation, deep sensation
  and hand movement quality.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8534145/

- To stimulate or not to stimulate? A rapid systematic review of repetitive
  sensory stimulation for the upper limb following stroke. PubMed 33292869.
  Context for passive stimulation approaches.

### Proprioception and force sense

- Correlation Between Proprioceptive Impairment and Motor Deficits After
  Stroke: A Meta-Analysis Review. PMC8793362. Proprioceptive impairment
  correlates with motor deficits.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8793362/

- Impact of proprioceptive deficit on control of joint torques during force
  matching task in hemispheric stroke survivors. Biomedical Engineering
  Letters, 2025. 12 chronic stroke survivors, blindfolded force matching;
  severe proprioceptive deficit gave much larger force direction errors.
  https://link.springer.com/article/10.1007/s13534-025-00538-9

- Force sense methodology: force reproduction at a percentage of MVC is the
  standard measure (found via ClinicalTrials NCT03852199 and the force
  matching literature above). Our device can do force reproduction but not
  joint position sense, since hands rest flat and nothing moves the finger.
  Honest scope: we reach force sense, not position sense.

- Characterizing visual compensation for proprioceptive impairments during
  the subacute phase of stroke. PMC13104422. 89 stroke survivors, matching
  without then with vision; up to 26 percent showed absent or maladaptive
  visual compensation. Supports vision-removed test blocks.

### Learned non-use

- Taub's learned non-use concept and CIMT: EXCITE randomised trial.
  Retention of upper limb function in stroke survivors who have received
  constraint-induced movement therapy: the EXCITE randomised trial.
  PubMed 18077218 (Lancet Neurology 2008 per trial family; year not
  directly confirmed in my search snippets, PMID confirmed). The EXCITE
  Trial commentary in Stroke: https://www.ahajournals.org/doi/10.1161/strokeaha.107.486555
  CIMT = massed paretic-limb practice plus restraint of the other hand.
  Design implication for us: game scoring can structurally require paretic
  contribution instead of physically restraining the good hand.
  https://pubmed.ncbi.nlm.nih.gov/18077218/

- Counteracting learned non-use in chronic stroke patients with
  reinforcement-induced movement therapy. Journal of NeuroEngineering and
  Rehabilitation, 2016. Reinforcement-based (rather than restraint-based)
  approaches to non-use exist in the literature.
  https://link.springer.com/article/10.1186/s12984-016-0178-x

### Bimanual asymmetric coordination

- Whitall J, McCombe Waller S, Silver KH, Macko RF. Repetitive bilateral arm
  training with rhythmic auditory cueing improves motor function in chronic
  hemiparetic stroke. Stroke, 31(10), 2000. n = 14 chronic, 6 weeks, 4 x
  5 min per session 3x/week. FM-UE gain p < 0.0004, sustained at 8 weeks.
  https://pubmed.ncbi.nlm.nih.gov/11022069/

- Luft AR et al. Repetitive bilateral arm training and motor cortex
  activation in chronic stroke: a randomized controlled trial. PubMed
  15494583 (JAMA 2004 per PubMed listing found in search). BATRAC vs
  dose-matched exercise with fMRI.
  https://pubmed.ncbi.nlm.nih.gov/15494583/

- Whitall J et al. Bilateral and unilateral arm training improve motor
  function through differing neuroplastic mechanisms: a single-blinded
  randomized controlled trial. Neurorehabilitation and Neural Repair, 2011.
  n = 111 chronic, 6 weeks 3x/week BATRAC vs DMTE; BATRAC increased
  hemispheric activation during paretic arm movement.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3548606/
  https://pubmed.ncbi.nlm.nih.gov/20930212/

- Cauraugh JH et al. Bilateral movement training and stroke motor recovery
  progress: a structured review and meta-analysis. Human Movement Science,
  2010 (online 2009). Random effects SMD 0.734 (SE 0.125), fail-safe N 532,
  I2 63 percent. BATRAC subgroup 0.842 (SE 0.155); coupled bilateral plus
  EMG-triggered stimulation 1.142 (SE 0.176). Note: contested by a response
  letter (Glasgow Caledonian), so present both sides in the thesis.
  https://www.sciencedirect.com/science/article/abs/pii/S0167945709000992

- Stewart et al. (authors not confirmed in my search) Bilateral movement
  training and stroke rehabilitation: a systematic review and meta-analysis.
  Journal of the Neurological Sciences, 2006. PubMed 16476449. 11 studies.
  https://pubmed.ncbi.nlm.nih.gov/16476449/

- Kang N, Cauraugh JH. Bimanual force variability and chronic stroke:
  asymmetrical hand control. PLOS ONE 9(7), 2014. 9 stroke + 9 controls,
  bimanual isometric force at 5, 25, 50 percent MVC. Greater bimanual
  variability in stroke; paretic hand worse at 5 and 25 percent.
  https://pubmed.ncbi.nlm.nih.gov/25000185/

- Patel P, Lodha N. Dynamic bimanual force control in chronic stroke:
  contribution of non-paretic and paretic hands. Experimental Brain
  Research, 2019. 13 stroke + 13 controls, bimanual isometric finger
  flexion tracking a trapezoid with increment and decrement phases.
  https://pubmed.ncbi.nlm.nih.gov/31197412/

- Bilateral synergy as an index of force coordination in chronic stroke.
  Experimental Brain Research, 2017 (Springer, author list not confirmed).
  Synergy-style decomposition of bimanual force sharing exists as an
  analysis method in this exact population.
  https://link.springer.com/article/10.1007/s00221-017-4904-9

- Force control improvements in chronic stroke: bimanual coordination and
  motor synergy evidence after coupled bimanual movement training.
  Experimental Brain Research, 2014 (Springer, author list not confirmed;
  likely the Kang and Cauraugh group). Training evidence that bimanual
  force coordination improves with coupled bimanual training.
  https://link.springer.com/article/10.1007/s00221-013-3758-z

- Bimanual force control strategies in chronic stroke: finger extension
  versus power grip. Neuropsychologia, 2012 (ScienceDirect
  S0028393212002758). Task-type matters for bimanual force strategies.

### Executive deficits: inhibition and dual-task

- Verbruggen F, Logan GD. Models of response inhibition in the stop-signal
  and stop-change paradigms. PubMed 18822313, 2008. Horse-race model of
  going vs stopping; SSRT as the latency of the stop process. STOP-IT is
  their free reference implementation (Verbruggen, Logan and Stevens).
  https://pubmed.ncbi.nlm.nih.gov/18822313/

- Fictitious inhibitory differences: how skewness and slowing distort the
  estimation of stopping latencies. PubMed 23399493, 2013. Use the
  integration method for SSRT, not the mean method, especially with slowed
  patients. Direct methods guidance for the notebook.
  https://pubmed.ncbi.nlm.nih.gov/23399493/

- Executive (dys)function after stroke (review). PMC6152929. Executive
  impairment incl. inhibitory control is common post-stroke.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6152929/

- Scheffer et al. 2016 (per search summary). Right frontal stroke:
  extra-frontal lesions, executive functioning and impulsive behaviour.
  Psicologia: Reflexao e Critica. Right-frontal stroke patients worse than
  controls on a go/no-go motor impulsivity task.
  https://link.springer.com/article/10.1186/s41155-016-0018-8

- Preserved but less efficient control of response interference after
  unilateral lesions of the striatum. PMC6232767. Stroke-induced striatal
  lesions show stop-signal deficits (per search summary of group studies).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6232767/

- Dual task effects on speed and accuracy during cognitive and upper limb
  motor tasks in adults with stroke hemiparesis. PubMed 34220473 /
  PMC8250862, 2021. Demonstrated cognitive-upper-limb interference in
  stroke; negative speed-accuracy correlation under load.
  https://pubmed.ncbi.nlm.nih.gov/34220473/

- Upper extremity-cognitive dual-task capacity post-stroke. PubMed
  39932232, 2025. Recent confirmation the topic is live and upper-limb
  dual-task studies remain scarce (gait dominates the field).
  https://pubmed.ncbi.nlm.nih.gov/39932232/

- Cognitive-motor interference during goal-directed upper-limb movements.
  PubMed 30251278, 2018. CMI protocol for upper limb in healthy and stroke.
  https://pubmed.ncbi.nlm.nih.gov/30251278/

- Kinematic studies of the go/no-go task as a dynamic sensorimotor
  inhibition task for assessment of motor and executive function in stroke
  patients (exploratory, neurotypical sample). PMC9688448. Go/no-go as a
  combined motor-executive probe aimed at stroke assessment.

## Candidate game modes (full specs)

### 1. Force Pilot: continuous force tracking and grading

Deficit: graded force control, predictive scaling, force variability
structure. Current modes use force only as a press threshold.

Player, trial by trial: MVC calibration per finger at session start (2 x 3 s
squeezes, take max). A drone flies left to right through a side-scrolling
cave at fixed speed. Fingertip force on the active finger maps to altitude
(0 to 40 percent MVC maps to screen height). The cave ceiling and floor draw
the target force corridor. Corridor shapes per 20 to 30 s run: plateaus
(hold 10 or 20 percent MVC), ramps up and down (release control is trained
explicitly, the decrement phase is where Patel and Lodha 2019 found the
paretic deficit), sine sections at 0.2 to 0.6 Hz (directly the band Lodha
2013 found disturbed), and pseudorandom sum-of-sines for assessment blocks
so the target is unpredictable. Rings inside the corridor give points;
touching a wall costs shield. Finger changes per run; weakest fingers get
more runs (reuse the adaptive weighting logic).

Game not test: continuous scoring (rings, shield, combo multiplier for
sustained in-corridor time), level map through the cave system, cosmetic
unlocks. Assessment blocks (pseudorandom, no rings) are disguised as "night
flights" and kept short.

Difficulty progression: corridor width shrinks (force tolerance from about
8 percent down to 2 percent MVC), waveform bandwidth rises, force range
extends both down (precision near 5 percent MVC, hard for stroke per Kang
and Cauraugh 2014) and up, and feedback fades: the drone blinks out for 2
to 5 s stretches and the player must hold or continue the profile from
force sense alone (memory-guided force, the vision-to-memory paradigm from
PubMed 29097632; also our honest proprioception angle: force sense, not
position sense). Spasticity-compatible: fully isometric, hand flat, no
finger lift required, low force floor.

Logging: per-sample (200 Hz) target force, actual force, finger id, feedback
on/off flag, per-run MVC, events (ring, wall hit).

Notebook: RMSE and relative tracking error (Kurillo's metric), time lag via
cross-correlation of target and response, CV of force in holds, spectral
power in bands below 1 Hz (replicate Lodha 2013's 0.2 vs 0.6 Hz split),
sample entropy of force in holds, increment vs decrement phase error
separately (Patel and Lodha 2019), feedback-on vs feedback-off drift
(force sense measure), per-finger and per-session learning curves.

### 2. Vibration Detective: vibrotactile discrimination for sensory re-education

Deficit: somatosensory impairment (about half of stroke survivors; SENSe
trial population). Motors currently used only as reaction cues. Sensory
discrimination training has RCT support (Carey 2011) and a thin active
training evidence base (Serrada 2019), which is exactly where a rigorously
instrumented device study lands well.

Player, trial by trial: hands rest flat, eyes on screen. The device sends a
vibration stimulus, the player answers by pressing. Three stimulus families:
(a) localisation: one short buzz on one of 4 (or 8) fingers, press that
finger; (b) duration discrimination: two buzzes in succession on the same
finger (sequential is required by the one-motor-per-hand constraint and is
also the standard psychophysics format), press once if the first was
longer, twice if the second; (c) pattern discrimination: 2 vs 3 pulses, or
long-short vs short-long "code words". Hardest levels use cross-hand pairs
(allowed simultaneously) for bilateral integration. Game skin:
safecracking spy. Each correct answer turns a tumbler; a cracked safe ends
the level; wrong answers add guards. Streak bonuses reward sustained
attention, matching SENSe's attentive-exploration principle.

Difficulty progression: adaptive staircase per finger and family (2-down
1-up on the duration difference or pulse-gap), converging on about 71
percent correct so the task always sits just above threshold, which is the
SENSe calibration principle. Anticipation trials (predict then feel then
confirm) mirror SENSe's feedback structure. Novel untrained patterns appear
in transfer blocks.

Logging: per trial: stimulus family, finger(s), stimulus parameters
(durations, gaps, pulse counts), response, correct flag, response time,
staircase level, reversal flag.

Notebook: duration-discrimination threshold (JND) per finger from staircase
reversals, psychometric function fit (logistic) per session, d-prime and
response bias from the confusion matrix, finger localisation confusion
matrix (which fingers get confused, adjacent vs distant), threshold
learning curve across sessions, RT for correct identifications. Clean
psychophysics gives the thesis strong quantitative teeth.

Constraint check: fixed motor intensity means no amplitude discrimination;
all discrimination is temporal (duration, gap, count, order) or spatial
(which finger). That is fine; temporal and locognosia tasks are standard.

### 3. Load Split: bimanual asymmetric force sharing

Deficit: asymmetric bimanual coordination and paretic under-contribution
(learned non-use). Mirror mode covers synchronous symmetric only. Bimanual
training has meta-analytic support (Cauraugh 2010: SMD 0.734, BATRAC
subgroup 0.842) and the deficit is documented at exactly our force levels
(Kang and Cauraugh 2014 at 5 and 25 percent MVC).

Player, trial by trial: both hands on pads. A see-saw beam on screen with a
ball on it. Summed left-hand force and summed right-hand force are the two
sides of the beam. Trial types per 15 to 25 s: (a) static split: hold the
beam level while the pivot moves off-centre, so level requires an unequal
split, e.g. paretic 60 / non-paretic 40; (b) load trade: keep total force
constant while smoothly transferring share from one side to the other along
a displayed ramp; (c) anti-phase pump: audio metronome paces alternating
left-right presses that keep a platform bouncing (BATRAC's anti-phase mode
transposed to fingers, cued by sound exactly as BATRAC cues by rhythm);
(d) finger-level splits for advanced play: index vs index only, then mixed
finger pairs. Ball stays on beam = points; drops end the trial.

Learned non-use lever: scoring weights the paretic side share. The game is
unwinnable by letting the strong hand do the work, which is a
reinforcement-style answer to non-use (JNER 2016) rather than a restraint,
and needs no mitt.

Difficulty progression: split ratio moves toward the paretic hand, force
band narrows, trade ramps steepen, metronome speeds up, and at high levels
individual hand bars vanish leaving only the beam (sum feedback only), so
the split must be produced from internal calibration.

Logging: per-sample left and right (and per-finger) force, target split,
metronome phase, ball position, events.

Notebook: paretic force share time series and error, asymmetry index per
session, cross-correlation lag between hands, relative phase and phase
variability for anti-phase blocks (circular statistics), bilateral synergy
decomposition: variance of the sum vs variance of the difference across
repeats (the Exp Brain Res 2017 bilateral synergy index in this exact
population), transfer: does unimanual variability (Force Pilot metrics)
improve after Load Split training.

### 4. Gatekeeper: response inhibition and dual-task executive mode

Deficit: executive control after stroke. Reaction mode measures going;
nothing measures stopping or performance under cognitive load. Stop-signal
deficits are documented after striatal stroke (PMC6232767) and go/no-go
deficits after right frontal stroke (Scheffer 2016); upper-limb dual-task
cost in stroke is demonstrated but under-studied (PubMed 34220473,
39932232), so a precise instrument here is a contribution.

Player, trial by trial: factory conveyor. Parts arrive at a stamping
station; a per-finger cue says which stamp to press (choice RT go trial,
about 75 percent of trials). On 25 percent of trials the part flashes red
with an alarm tone after a stop-signal delay (SSD): withhold the press.
SSD staircases: plus 50 ms after a successful stop, minus 50 ms after a
failed stop, converging on about 50 percent inhibition, which is the
standard design from Verbruggen and Logan's stop-signal framework. Blocks
of about 60 trials. Dual-task blocks: an auditory stream plays digits; the
player also keeps a running count of a target digit (or 1-back), reported
between blocks. Compare single vs dual-task go RT, accuracy and SSRT.
Vibration is used only as no-go-error feedback (a buzz on a failed stop),
never as the stop signal itself, so the tactile channel stays free for
mode 2.

Game not test: stamped parts build a machine across levels, failed stops
break parts visibly, streak bonuses for clean runs, "rush orders" for
paced pressure. The staircase keeps success near 50 percent on stop trials,
so the framing (saving most parts, occasional dud) matters to keep it
motivating.

Difficulty progression: go pace quickens, stop-signal rate varies, dual-task
load rises (count one digit, then two, then 1-back), cross-hand blocks mix
left and right cues.

Logging: per trial: trial type, cue finger, go RT, SSD, stop outcome,
stimulus and response timestamps at ms precision, dual-task condition,
secondary-task answers.

Notebook: SSRT by the integration method (mean method is biased with slowed
patients per PubMed 23399493), inhibition function P(respond | SSD), go RT
distribution and ex-Gaussian fit, proactive slowing (go RT drift with stop
expectation), post-error slowing, dual-task cost percentages for RT,
accuracy and SSRT, per-hand comparison (paretic vs non-paretic cued
fingers). The horse-race model gives the thesis a principled computational
model, not just descriptive stats.

## Ranking within cluster

1. Force Pilot: biggest deficit-to-asset match (unused analogue signal),
   strongest and most direct training literature (Carey 2002, Kurillo 2005,
   Taud 2021 all trained tracking itself), richest signal analysis.
2. Vibration Detective: turns the motors into a second therapy channel,
   RCT-backed principle (SENSe), publishable psychophysics, and the active
   sensory training evidence gap is a genuine opening.
3. Load Split: strong meta-analytic backing, unique bimanual-asymmetric
   niche the mirror mode misses, and it carries the learned non-use story.
4. Gatekeeper: solid science and very clean analytics, but furthest from
   hand impairment per se; strongest as the cognitive arm of a battery.

## Caveats logged for the thesis

- BATRAC efficacy is contested (Cauraugh 2010 meta was challenged in a
  published response; and one trial title found: "Bilateral arm training
  with rhythmic auditory cueing in chronic stroke: not always efficacious",
  PubMed 17660456). Present both sides.
- Serrada 2019 found the active sensory retraining evidence limited; SENSe
  (Carey 2011) is the key positive RCT. Frame mode 2 as implementing SENSe
  principles on new hardware, not as settled science.
- SSRT estimation requires enough stop trials (dozens) and race-model
  assumptions can break with very slow patients; use the integration
  method and report checks (PubMed 23399493).
- Our proprioception reach is force sense only (no joint movement, no
  position sense); say so plainly.
- Author lists marked "not confirmed" above were not verified in this
  session's searches; verify before citing them with authors in the thesis.
