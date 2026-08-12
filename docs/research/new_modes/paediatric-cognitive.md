# Paediatric cognitive-motor cluster: research notes

Cluster brief: developmental coordination disorder (DCD), cerebral palsy (CP) hand
therapy, dyslexia beyond syllable tapping, ADHD response inhibition, working memory
span via finger sequences, dual-task paradigms. Question: what fits a four-finger
press-and-buzz device for a child?

Hardware constraints kept in mind throughout: 4 fingers per hand (no thumb), one
SingleTact force pad per finger sampled at 200 Hz (analogue, currently only used as
a threshold), one vibration motor per finger (fixed intensity, variable duration and
pattern, only one motor per hand active at an instant, cross-hand simultaneous OK),
60 Hz screen, speaker, CSV logging, Python notebook analysis.

Existing modes to avoid duplicating: reaction (simple + choice RT), pattern (SRTT),
chords (multi-finger + enslavement), syllables (phonological beat tapping), adaptive
(weakest-finger drill), rhythm (metronome), mirror (bilateral synchronous).

All sources below were found in live searches this session. Where I could not
confirm the author list from search output, I say so and give the locator instead.

---

## Thread 1: ADHD response inhibition (stop-signal / go-no-go)

### What the literature says

- Verbruggen, Aron, Band, Beste, Bissett et al. (2019), "A consensus guide to
  capturing the ability to inhibit actions and impulsive behaviors in the
  stop-signal task", eLife 8:e46323. The definitive methods paper. Independent
  horse-race model (go runner vs stop runner, from Logan & Cowan 1984).
  Recommendations for a reliable SSRT estimate: about 25 percent stop trials,
  staircase-tracked stop-signal delay (SSD, typically 50 ms steps), SSRT estimated
  with the integration method with replacement of go omissions.
  https://elifesciences.org/articles/46323
- Lipszyc & Schachar (2010), "Inhibitory control and psychopathology: a
  meta-analysis of studies using the stop signal task", Journal of the
  International Neuropsychological Society. Medium SSRT deficit in ADHD,
  g = 0.62. Confirms SSRT as the marker of the inhibition deficit in ADHD.
  https://pubmed.ncbi.nlm.nih.gov/20719043/
- Friehs, Dechant, Vedress, Frings & Mandryk (2020), "Effective Gamification of
  the Stop-Signal Task: Two Controlled Laboratory Experiments", JMIR Serious
  Games 8(3):e17810. Gamified SST preserved the stopping effects and showed
  lower response variability than the plain version, so game skinning does not
  wreck SSRT validity and may improve data quality.
  https://games.jmir.org/2020/3/e17810/
- Follow-up validity work: "Preserved Inhibitory Control Deficits of Overweight
  Participants in a Gamified Stop-Signal Task" (JMIR Serious Games 2021,
  e25063): group differences survive gamification.
- Kofler et al. (2013), "Reaction time variability in ADHD: a meta-analytic
  review of 319 studies" (Psychology, FSU PDF found in search). RT variability
  (ex-Gaussian tau) is one of the most reliable ADHD markers, and it falls out
  of the same log data for free.
- IMPORTANT NULL RESULT: Ganesan et al. (2024), "Cognitive control training with
  domain-general response inhibition does not change children's brains or
  behavior", Nature Neuroscience 27:1364-1375. RCT, n = 235 children aged 6-13,
  8-week gamified response inhibition training vs response speed control.
  Trained measures improved and held at 1 year, but zero transfer to behaviour,
  academics, mental health, or any neural outcome.
  https://www.nature.com/articles/s41593-024-01672-w

### Design implication

Build the stop-signal mode as a measurement-grade instrument with a game skin,
not as a claimed "ADHD treatment". The honest pitch: engaging, repeatable,
clinic-free SSRT and RT-variability measurement in children, following the 2019
consensus parameters. The Ganesan null is about far transfer of training, not
about the task's validity as an assessment, which is exactly what a thesis can
quantify well. Novel hardware angle: the 200 Hz analogue force pads can capture
partial responses on stop trials (force ramps that stay under the press
threshold), giving a graded inhibition measure that button-based SSTs cannot see.
Partial-response measurement is normally done with EMG in the literature; force
pads get an approximation of it for free.

60 Hz screen quantises visual SSD steps to 16.7 ms, which is fine for a 50 ms
staircase. An auditory stop signal via the speaker avoids frame quantisation.
A vibrotactile stop signal is possible but motor spin-up latency must be
characterised first (good engineering sub-study).

---

## Thread 2: Dyslexia beyond syllables (letter-sound binding, RAN)

### Letter-speech sound binding

- Froyen, Willems & Blomert (2011), "Evidence for a specific cross-modal
  association deficit in dyslexia: an electrophysiological study of
  letter-speech sound processing", Developmental Science. Dyslexic children show
  much weaker and slower influence of print on speech-sound perception; the
  deficit lives in audiovisual integration, not just phonology.
  https://onlinelibrary.wiley.com/doi/10.1111/j.1467-7687.2010.01007.x
- Fraga González, Žarić, Tijms, Bonte, Blomert, van der Molen (2015), "A
  Randomized Controlled Trial on The Beneficial Effects of Training
  Letter-Speech Sound Integration on Reading Fluency in Children with
  Dyslexia", PLOS ONE 10(12):e0143914. n = 44 dyslexic children aged 8-9 plus 23
  typical readers; 34 sessions of 45 min over 5 months focused on letter-sound
  mapping; dyslexic trainees gained on word reading and spelling faster than
  waiting-list controls. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0143914
- Žarić et al. (2015), "Crossmodal deficit in dyslexic children: practice
  affects the neural timing of letter-speech sound integration", Frontiers in
  Human Neuroscience 9:369. Training shifts the neural timing of integration.
- Aravena, Snellings, Tijms & van der Molen (2013), "A lab-controlled simulation
  of a letter-speech sound binding deficit in dyslexia", Journal of Experimental
  Child Psychology. Artificial-script paradigm (Hebrew letters transcribing
  Dutch): 20 minutes of training on 8 correspondences; dyslexics were
  outperformed under time pressure. Time pressure is the discriminating factor.
- Aravena, Tijms, Snellings & van der Molen (2018), "Predicting Individual
  Differences in Reading and Spelling Skill With Artificial Script-Based
  Letter-Speech Sound Training", Journal of Learning Disabilities. Learning rate
  in the artificial script predicts real reading and spelling.
  https://journals.sagepub.com/doi/abs/10.1177/0022219417715407
- "Performance in Sound-Symbol Learning Predicts Reading Performance 3 Years
  Later" (PubMed 30258391). Author list not confirmed in my search output, so
  citing by title and PMID only. Supports sound-symbol learning rate as an early
  risk marker.
- GraphoGame lineage: Lyytinen et al. (2015), "GraphoGame: a catalyst for
  multi-level promotion of literacy in diverse contexts" (PMC4461812), and the
  critical review McTigue et al. (2020), "Critically Reviewing GraphoGame Across
  the World", Reading Research Quarterly. Meta-analysis of 19 GraphoGame studies:
  effects depend on context; the one significant moderator was level of
  supportive adult interaction (average ES 0.48 with high adult support).
  Standalone tablet drill without an adult tends to disappoint. Design lesson:
  build for co-play or supervised sessions, and keep sessions short and intense.

### RAN (rapid automatised naming)

- Meta-analytic base: a meta-analysis of 137 studies, n = 28,826, found a
  moderate-to-strong RAN-reading relationship (this is Araújo et al. 2015 as
  cited inside the Frontiers article below; I confirmed the meta-analysis via
  secondary citation, not the primary PDF). RAN predicts reading across
  orthographies and discriminates dyslexic from typical readers with high
  accuracy in some samples (88.3 percent classification in one study).
  Sources found: "Rapid Automatized Naming as a Universal Marker of
  Developmental Dyslexia in Italian Monolingual and Minority-Language Children",
  Frontiers in Psychology 2022 (PMC9021430); Carioti et al. (2021) meta-analysis
  cited therein.
- RAN itself requires naming aloud, which the device cannot capture. What the
  device CAN capture is the serial, speeded, automatised symbol-to-response
  pipeline: a continuous stream of symbols mapped to fingers. I am NOT claiming
  this is RAN; it borrows the serial automatisation construct. The defensible
  framing is automatisation of newly learned symbol-sound-finger mappings under
  time pressure (Aravena's construct, not RAN proper).

### Design implication

A cross-modal binding game: speaker plays a phoneme, screen shows candidate
symbols positioned over finger slots, child presses the finger under the
matching symbol. Use an artificial script option for research cleanliness
(controls prior exposure, works for pre-readers, direct lineage to Aravena).
Include congruent/incongruent verification trials (symbol + sound together,
respond match/mismatch) because the congruency cost indexes binding
automatisation. Add a serial "conveyor" level for speeded serial responding.
This complements the existing syllables mode (phonology) with the audiovisual
binding layer that syllable tapping does not touch.

---

## Thread 3: Cerebral palsy hand therapy (bimanual, mirror movements, tactile)

### Bimanual training evidence

- Novak et al. (2020), "State of the Evidence Traffic Lights 2019: Systematic
  Review of Interventions for Preventing and Treating Children with Cerebral
  Palsy" (PubMed 32086598). Bimanual training and CIMT are both green-light
  (do it) interventions for hand function in CP.
- HABIT-ILE RCT lineage (Bleyenheuft, Gordon and colleagues): "Hand and Arm
  Bimanual Intensive Therapy Including Lower Extremity (HABIT-ILE) in Children
  With Unilateral Spastic Cerebral Palsy: A Randomized Trial" (PubMed 25527487);
  early-childhood RCT (PMC10628844, 2023, n = 50, bimanual function improved vs
  usual activity); infant RCT (PMC11574690, 2024, n = 48, 50 hours over 2 weeks
  improved bimanual performance). Core ingredients: many repetitions, progressive
  shaping, child-friendly game framing, structured bimanual roles where the
  affected hand has a real job.
- Key HABIT principle relevant to game design: role-differentiated bimanual
  tasks (one hand stabilises or holds while the other manipulates), not just
  symmetric mirroring. The existing mirror mode covers symmetric; the gap is
  asymmetric role-differentiated play.

### Mirror movements (untapped measurement opportunity)

- GriFT device: "GriFT: A Device for Quantifying Physiological and Pathological
  Mirror Movements in Children" (PubMed 28692958). Two force-sensor handles,
  1000 Hz, quantifies involuntary mirror force in the passive hand during
  unimanual squeezing in a computer game. Validated in typically developing
  children and clinically applicable in unilateral CP. Author list not fully
  confirmed in my search output; citing by title and PMID.
- Kuo et al. (2018), "Neurophysiological mechanisms and functional impact of
  mirror movements in children with unilateral spastic cerebral palsy",
  Developmental Medicine and Child Neurology. Mirror movements relate to
  corticospinal reorganisation and contribute to non-use of the affected hand
  (developmental disregard).
- Search results also flagged impaired temporal coordination of bimanual grip
  force in unilateral CP vs typical children (source summary in search output;
  primary authorship not confirmed, treat as background).
- The rig already has per-finger 200 Hz analogue force on BOTH hands. During any
  unimanual task, the resting hand's pads record involuntary mirror force for
  free. That is a GriFT-class measurement without building new hardware.

### Tactile function in CP

- Prevalence: tactile impairment reported in a large majority of children with
  unilateral CP (one study over 77 percent; range 20-90 across assessments).
  Sources: "Somatosensory discrimination impairment in children with hemiplegic
  cerebral palsy as measured by the sense_assess kids" (PubMed 33738799); Auld
  et al. (2012), "Reproducibility of tactile assessments for children with
  unilateral cerebral palsy" (Physical and Occupational Therapy in Pediatrics;
  single-point localisation test-retest 69 percent within one point).
- Auld et al. (2014), "Determination of interventions for upper extremity
  tactile impairment in children with cerebral palsy: a systematic review",
  Developmental Medicine and Child Neurology. Conclusion: NO current
  intervention is proven to improve tactile function in children with CP,
  while adult stroke has effective options. This is an explicit evidence gap.
- Carey, Macdonell & Matyas (2011), "SENSe: Study of the Effectiveness of
  Neurorehabilitation on Sensation: a randomized controlled trial",
  Neurorehabilitation and Neural Repair. n = 50 adult stroke; 10 hours of
  perceptual-learning based somatosensory discrimination training beat exposure
  control; gains held at 6 months. The principle (graded discrimination
  training with feedback) is what a vibrotactile finger game can deliver.

---

## Thread 4: Working memory span, serial order, finger gnosis

### Serial order and span

- Corsi block-tapping developmental norms: span grows roughly linearly age 7-14,
  plateaus near 6.9 items by grade 8 ("Developmental Normative Data for the
  Corsi Block-Tapping Task", found via ResearchGate; also Orsini 1994
  standardisation for ages 11-16, Perceptual and Motor Skills). Span alone is a
  coarse score; trial-level accuracy is more stable for individual differences
  (recent Corsi methods papers in search output, PMC12398182).
- Mosse & Jarrold (2008), "Hebb learning, verbal short-term memory, and the
  acquisition of phonological forms in children" (PubMed 18300182). Hebb
  repetition learning (a repeated sequence improves faster than novel ones)
  works in young children in verbal AND visuospatial variants and correlates
  with novel word learning.
- Bogaerts, Szmalec, De Maeyer, Page & Duyck (2016), "The involvement of
  long-term serial-order memory in reading development: A longitudinal study",
  Journal of Experimental Child Psychology 145:139-156. Hebb learning predicts
  later nonword reading, explaining variance beyond phonological awareness.
  Related: "The contribution of serial order short-term memory and long-term
  learning to reading acquisition: a longitudinal study" (PubMed 32614211);
  serial-order learning impaired in dyslexia (multiple hits).
- CAUTION on training claims: Melby-Lervåg, Redick & Hulme (2016), "Working
  Memory Training Does Not Improve Performance on Measures of Intelligence or
  Other Measures of Far Transfer", Perspectives on Psychological Science.
  87 publications, 145 comparisons: near transfer only, no far transfer against
  treated controls. So a span mode is an ASSESSMENT and progress-tracking
  instrument, not a "brain training" claim.

### Finger gnosis

- Gracia-Bafalluy & Noël (2008), "Does finger training increase young
  children's numerical performance?" (PubMed 18387567, Cortex). 8 weeks of
  finger differentiation training in 5-6 year olds with poor finger gnosis
  improved finger gnosis and some numerical subtasks (subitizing, ordinality).
- But: a UCL reanalysis notes low power and no convincing causal evidence for
  arithmetic gains (Long et al. accepted version, UCL Discovery), and a
  well-controlled kindergarten study found no arithmetic benefit beyond an
  active control ("A Finger-Based Numerical Training Failed to Improve
  Arithmetic Skills in Kindergarten Children", Frontiers in Psychology 2020).
- Wasner et al. (2016), "Finger gnosis predicts a unique but small part of
  variance in initial arithmetic performance", Journal of Experimental Child
  Psychology. Association real but small.
- Verdict: finger gnosis is an honest secondary angle (measurable with the
  vibration motors as stimuli), not a headline claim.

### Dual-task in DCD (considered, then demoted)

- "Motor and cognitive dual-task performance under low and high task complexity
  in children with and without DCD" (PubMed 36773489, Research in Developmental
  Disabilities 2023) and "Locomotor-cognitive dual-tasking in children with
  developmental coordination disorder" (Frontiers in Psychology 2024,
  PMC10951910): dual-task costs in DCD are NOT dramatically larger than typical
  peers; children with DCD achieve similar performance at higher mental effort.
  Mixed and null-ish group effects make dual-task a weak headline for a thesis
  mode. Kept as an optional overlay (for example, span task layered on rhythm),
  not a standalone mode.

### DCD training background

- Yu, Burnett & Sit (2018), "Motor Skill Interventions in Children With
  Developmental Coordination Disorder: A Systematic Review and Meta-Analysis",
  Archives of Physical Medicine and Rehabilitation. Task-oriented interventions
  effective for motor outcomes.
- "Motor-Based Interventions in Children with DCD: systematic review and
  meta-analysis of RCTs", Sports Medicine Open 2025 (PMC12106291): task-oriented
  training improved motor skills, balance, activity performance.
- Implication: DCD support argues for task-oriented, game-framed fine-motor
  practice generally; the four candidate modes all serve DCD as secondary
  populations rather than needing a bespoke DCD mode.

---

## Candidate game modes (full specs)

### 1. Stop the Launch (stop-signal inhibition game)

Conditions: ADHD assessment and monitoring (primary), impulse control profiling
in DCD and typical development (secondary).

Trial by trial: choice-RT core. A drone appears on the left or right launchpad
(or one of four pads for a 4-choice level); the child presses the mapped finger
fast to launch it and earn points. On about 25 percent of trials, after a
variable stop-signal delay, an abort signal fires (red flash plus a tone from
the speaker; tone avoids 60 Hz frame quantisation of the delay). The child must
NOT press. SSD moves in a 50 ms staircase: successful stop makes the next stop
harder (longer SSD), failed stop makes it easier. The staircase holds stop
success near 50 percent, which is also self-balancing difficulty.

Game not test: points and streak multipliers for fast launches, bonus shields
for clean aborts, level themes change the go task (2-choice to 4-choice, new
liveries), a companion character reacts (Friehs 2020 showed this skin preserves
validity and reduces variance). Session length 8-10 min.

Logged per trial: trial type, go stimulus, mapped finger, SSD, responded or
not, RT, full 200 Hz force trace on all pads around the event window.

Notebook computes: SSRT via integration method with go-omission replacement
(Verbruggen 2019 consensus), inhibition function p(respond|signal) vs SSD,
staircase convergence, mean RT, ex-Gaussian sigma and tau for RT variability
(Kofler 2013), post-stop-error slowing, and the novel bit: partial-press
detection on successful stops (subthreshold force excursions, their amplitude
and latency), giving a graded inhibition depth measure that button hardware
cannot produce.

Honest framing: measurement instrument with strong ADHD sensitivity (SSRT
deficit g = 0.62, Lipszyc & Schachar 2010). Do not claim training transfer
(Ganesan 2024 null).

### 2. Sound Forge (cross-modal letter-sound binding game)

Conditions: dyslexia intervention support and risk screening (primary),
pre-reader literacy support (secondary). Complements the existing syllables
mode: syllables covers phonological rhythm, this covers audiovisual binding,
which is a distinct documented deficit (Froyen 2011).

Trial by trial: learn phase: a symbol appears above a finger slot and its sound
plays, child presses that finger to "forge" the pair. Test phase: a sound
plays, 2 to 4 candidate symbols sit over the finger slots, child presses the
finger under the matching symbol before the deadline. Verification trials:
symbol and sound together, child presses a designated "match" finger or
"mismatch" finger. Optional artificial-script mode (invented glyphs mapped to
native phonemes) for research cleanliness and pre-readers, per Aravena 2013.
Conveyor level: symbols stream across the screen in series and the child
presses the mapped fingers continuously, a speeded serial automatisation level.

Game not test: forge theme (pairs get "smithed" and upgrade visually with
mastery), item collection per mastered pair, deadline pressure presented as a
cooling ingot, adult co-play encouraged on screen prompts (McTigue 2020: adult
support is the moderator that makes these games work, ES 0.48).

Difficulty: symbol set grows 2 to 8, confusable glyphs introduced, response
deadline shrinks (time pressure is where dyslexic binding breaks, Aravena
2013), congruency ratio shifts, conveyor speeds up.

Logged per trial: pair ID, phase, foils shown, congruency, SOA, deadline,
chosen finger, RT, correct, block index.

Notebook computes: per-pair learning curves (exponential fit rate constant =
binding learning rate, the measure that predicted reading and spelling in
Aravena 2018), d-prime for match/mismatch discrimination, symbol confusion
matrix, congruency RT cost over sessions (automatisation index), deadline
compliance curve, conveyor throughput (correct symbols per minute) as the
serial automatisation metric.

Evidence: Fraga González 2015 PLOS ONE RCT (letter-sound training improved
word reading and spelling in dyslexic 8-9 year olds); Froyen 2011; Žarić 2015;
Aravena 2013, 2018; GraphoGame literature with the McTigue 2020 caveat.

### 3. Crane Crew (role-differentiated bimanual force game, two-hand rig)

Conditions: unilateral CP hand therapy (primary), bimanual coordination in DCD
(secondary). Distinct from the existing mirror mode: mirror is symmetric
synchronous tapping; this is asymmetric role-differentiated play plus
continuous force control, which is the HABIT ingredient the device does not
yet exercise, and it finally uses the analogue force signal.

Trial by trial: the affected hand is the "grip": press and hold one or more
fingers so the summed force stays inside a visible band (the crane's grip
meter), band shown as a tube on screen with the live force dot. While the grip
holds, the other hand taps a short sequence to drive the crane (lift, swing,
lower). Drop the force out of band and the cargo wobbles; recover within a
grace window or the trial ends. Roles swap each round. Symmetric bonus rounds:
both hands ramp force together to lift a heavy load (bimanual force
coordination). Solo levels for single-hand rigs degrade gracefully to pure
force tracking games.

Game not test: cargo variety, wobble physics on screen, combo scoring for
clean lifts, vibration on the gripping hand signals band exit (one motor per
hand constraint fits: grip hand gets the buzz, tap hand needs none).

Difficulty: narrower force bands, longer holds, moving band targets (slow
sinusoids for tracking), faster or longer tap sequences, shorter grace windows.

Logged: 200 Hz force traces from all eight pads, band parameters, phase
markers, tap events, role assignment.

Notebook computes: force tracking RMSE and time-in-band, coefficient of
variation of hold force, recovery latency after band exit, tap sequence
accuracy and timing under load, dual-role cost (tap accuracy with vs without
concurrent grip), and the headline measurement: mirror movement quantification
from the RESTING hand's pads during unimanual phases (mirror ratio = passive
hand force amplitude over active hand amplitude, cross-correlation lag,
coherence at the tapping frequency), following the GriFT force-based approach
(PubMed 28692958) and the Kuo 2018 framework.

Evidence: bimanual training is green-light for CP (Novak 2020 traffic lights);
HABIT-ILE RCTs (PubMed 25527487; PMC10628844; PMC11574690) show intensive
game-framed bimanual practice with role differentiation improves bimanual
function from infancy up; mirror movements are clinically meaningful and force
sensors are a validated way to measure them (GriFT; Kuo 2018).

### 4. Buzz Hunt (tactile finger localisation and span game)

Conditions: tactile discrimination in unilateral CP (primary, explicit evidence
gap: Auld 2014 found no proven tactile interventions for children with CP while
adult stroke discrimination training works, Carey 2011 SENSe RCT), serial-order
memory profiling relevant to reading risk (secondary), finger gnosis and
numeracy (exploratory only).

Trial by trial: hands rest flat, screen shows a garden, not the hands. Level 1
(localisation): one finger gets a short buzz; the child presses that finger to
catch the bug hiding under that leaf. Distractor-free at first, then shorter
buzzes and catch trials. Level 2 (tactile span): a sequence of 2 to 5+ buzzes
plays across fingers (sequential within a hand due to the one-motor rule,
cross-hand pairs allowed), then the child replays the sequence on the pads.
Adaptive length staircase holds about 80 percent success. Every third sequence
is secretly the same sequence (Hebb repetition), so long-term serial-order
learning is measured without the child knowing. Bimodal levels add on-screen
leaf flashes to compare tactile vs visual vs bimodal span.

Game not test: bug collection album, streak bonuses, buzz-length "difficulty
stars", short sessions.

Difficulty: buzz duration down (200 ms to 60 ms), inter-buzz interval down,
sequence length up via staircase, adjacent-finger sequences (hardest to
localise), cross-hand interleaving.

Logged per trial: stimulus sequence (finger, duration, gaps), response
sequence with per-press RT and force, staircase state, Hebb item flag.

Notebook computes: localisation accuracy per finger and a finger confusion
matrix (adjacent-finger error rate is the tactile discrimination metric,
analogous to single-point localisation in sense_assess kids, PubMed 33738799),
psychometric span (logistic fit of accuracy vs length, more stable than
all-or-nothing span per recent Corsi methods work), serial position curves,
Hebb learning slope (repeated minus novel sequence accuracy over repetitions,
the measure that predicts reading per Bogaerts 2016 and correlates with word
learning per Mosse & Jarrold 2008), and affected vs less-affected hand
asymmetry in CP.

Honest framing: for CP tactile training this is a research question sitting in
a named evidence gap, powered by the adult stroke SENSe result. For span and
Hebb it is measurement; no far-transfer training claims (Melby-Lervåg 2016).
Finger gnosis link to arithmetic is small and causally unproven (Wasner 2016;
Frontiers 2020 failed training replication), so it stays exploratory.

---

## Cross-cutting engineering notes

- The analogue force channel is the differentiator in three of four modes:
  partial-press inhibition depth (mode 1), mirror movement quantification
  (mode 3), press force profiles in children (all modes).
- Vibration motors get promoted from feedback device to STIMULUS device in
  mode 4; motor onset latency and rise time must be measured and calibrated
  first (bench characterisation chapter for the thesis).
- Speaker-based signals beat screen-based ones for precise event timing
  (60 Hz frame quantisation); audio latency should also be characterised.
- One motor per hand at an instant: within-hand buzz sequences must be
  sequential; cross-hand simultaneous pairs are allowed and are actually an
  interesting bimanual perception condition.
- All four modes log clean trial-level CSVs that fit the existing notebook
  pipeline; every proposed metric is computable from finger ID, timestamps,
  and 200 Hz force traces.

## Source list (all found in this session's searches)

1. Verbruggen et al. 2019, eLife 8:e46323, stop-signal consensus guide.
2. Lipszyc & Schachar 2010, J Int Neuropsychol Soc, SST meta-analysis, ADHD g = 0.62.
3. Friehs et al. 2020, JMIR Serious Games 8(3):e17810, gamified SST validity.
4. JMIR Serious Games 2021 e25063, gamified SST preserves group deficits.
5. Ganesan et al. 2024, Nature Neuroscience 27:1364-1375, inhibition training null RCT.
6. Kofler et al. 2013, RT variability in ADHD meta-analytic review (319 studies).
7. Froyen, Willems & Blomert 2011, Developmental Science, cross-modal deficit ERP.
8. Fraga González et al. 2015, PLOS ONE 10(12):e0143914, letter-sound training RCT.
9. Žarić et al. 2015, Frontiers in Human Neuroscience 9:369, practice and neural timing.
10. Aravena et al. 2013, J Exp Child Psychol, artificial-script binding deficit.
11. Aravena et al. 2018, J Learning Disabilities, artificial-script training predicts reading.
12. PubMed 30258391, sound-symbol learning predicts reading 3 years later (authors unconfirmed).
13. Lyytinen et al. 2015, PMC4461812, GraphoGame overview.
14. McTigue et al. 2020, Reading Research Quarterly, GraphoGame critical review, adult-support moderator ES 0.48.
15. Frontiers in Psychology 2022 (PMC9021430), RAN universal marker; cites Araújo et al. 2015 meta (137 studies, n = 28,826) and Carioti et al. 2021.
16. Novak et al. 2020, PubMed 32086598, CP traffic lights: bimanual training and CIMT green.
17. HABIT-ILE RCTs: PubMed 25527487 (2015); PMC10628844 (2023, n = 50); PMC11574690 (2024, infants, n = 48).
18. GriFT device paper, PubMed 28692958, force-based mirror movement quantification.
19. Kuo et al. 2018, Dev Med Child Neurol, mirror movement mechanisms in unilateral CP.
20. sense_assess kids somatosensory discrimination, PubMed 33738799.
21. Auld et al. 2012, Phys Occup Ther Pediatr, tactile assessment reproducibility.
22. Auld et al. 2014, Dev Med Child Neurol, systematic review: no proven tactile interventions in child CP.
23. Carey, Macdonell & Matyas 2011, Neurorehabil Neural Repair, SENSe RCT adult stroke.
24. Corsi developmental norms (Farrell Pagulayan et al., J Clin Exp Neuropsychol, via ResearchGate; authors partially confirmed); Orsini 1994, Percept Mot Skills.
25. Mosse & Jarrold 2008, PubMed 18300182, Hebb learning and word learning in children.
26. Bogaerts et al. 2016, J Exp Child Psychol 145:139-156, Hebb learning predicts reading.
27. PubMed 32614211, serial-order STM and reading acquisition longitudinal.
28. Melby-Lervåg, Redick & Hulme 2016, Perspect Psychol Sci, WM training no far transfer.
29. Gracia-Bafalluy & Noël 2008, PubMed 18387567, finger gnosis training.
30. Frontiers in Psychology 2020, finger-based numerical training failed replication.
31. Wasner et al. 2016, J Exp Child Psychol, finger gnosis small unique variance.
32. Yu, Burnett & Sit 2018, Arch Phys Med Rehabil, DCD motor skill meta-analysis.
33. Sports Medicine Open 2025 (PMC12106291), DCD motor-based interventions RCT meta.
34. PubMed 36773489 and PMC10951910, dual-task in DCD (mixed/null group effects).
