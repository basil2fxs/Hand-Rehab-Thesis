# Motor preparation and attention monitoring: what EEG can and cannot give the rehab software

Lane: readiness potential (BP/RP), lateralised readiness potential (LRP), contingent
negative variation (CNV), mu/beta desynchronisation, alpha and theta attention/effort
indices, and the honest limits of "is the patient paying attention or over-concentrating".

Grounding facts checked in the code this session:

- Dr Marinovic's SRT program (SRT_Sequence_learning_Final_v2.py): one marker only,
  byte 30 written to COM10 at flash onset, held ~16.7 ms (2 frames at 120 Hz), then
  byte 0. No response marker, no warning marker, no block markers. ISIs 250 to 750 ms.
- Basil's reaction mode (rehab/game/modes/reaction.py): exponential foreperiod above
  fp_min truncated at fp_max (flat hazard by design, citing Naatanen 1971 and Niemi
  and Naatanen 1981 in its own docstring), optional uniform 2 to 10 s PVT-style
  draw, 10 percent catch trials, rest gate before each trial, false starts aborted.
  The foreperiod begins silently after the rest gate. There is no discrete visible
  warning stimulus (no S1) and no EEG markers anywhere in the engine yet.

Every claim below carries the paper it stands on. Sources found and verified in this
session's searches are cited author-year-venue. Anything I could not verify is
flagged as such.

---

## 1. Readiness potential (Bereitschaftspotential, BP or RP)

**What it is.** A slow negative drift over motor cortex that builds for one to two
seconds before a self-initiated movement. Like watching a capacitor charge before a
MOSFET fires: the brain ramps up before the finger moves, and you can see the ramp.

**Why it matters here.** It is the classic index of the motor system readying itself.
In rehab it shows the patient's cortex is genuinely driving the movement rather than
the movement being passive or reflexive.

**How it works and what it needs.**

- First described by Kornhuber and Deecke (1965, Pfluegers Archiv fuer die gesamte
  Physiologie 284). Voluntary movements are preceded by a slowly rising negative
  potential of roughly 10 to 15 uV starting 1 to 2 s before movement onset, recorded
  at central electrodes (Cz, C3, C4).
- The methodological reference is Shibasaki and Hallett (2006, "What is the
  Bereitschaftspotential?", Clinical Neurophysiology). Two phases: an early
  symmetric BP from about minus 2 s, and a late steeper phase (NS prime) from about
  minus 400 ms that lateralises contralateral to the moving hand.
- Requirements: epochs time-locked to movement onset (EMG onset is the gold
  standard; a precise response timestamp from the force sensor is the practical
  substitute here), movements self-paced and separated by several seconds so one
  trial's ramp does not sit inside the previous trial's activity, DC or very long
  time-constant recording (high-pass at 0.05 Hz or lower, because this is a slow
  drift and a normal 0.5 Hz high-pass filter erases it), and many trials averaged.
  Classic BP studies average tens of movements; scoping work on real-world
  movements treats several dozen as the floor (Frontiers in Neuroscience 2021
  scoping review of MRCP recording in ecologically valid movements).
- Strict BP requires SELF-INITIATED movement with no eliciting stimulus. Almost all
  of Basil's game modes are stimulus-driven, so the strict BP is only available in
  a free-press block (press whenever you like, roughly every 5+ s). Stimulus-driven
  modes instead give stimulus-locked ERPs plus response-locked movement-related
  cortical potentials (MRCPs), which carry the same late pre-movement negativity.
- Rehab relevance is real: BCI systems for stroke and cerebral palsy detect the
  MRCP peak negativity (typically within ~500 ms before movement) or sensorimotor
  ERD online and trigger electrical stimulation from it (reviews:
  "A comprehensive guide to BCI-based stroke neurorehabilitation interventions",
  PMC 2023; BCI-neurofeedback with motor attempt in cerebral palsy, PMC 2024).

**What it demands from the software.** A response-onset marker. Without a byte
written at press onset, response-locked averaging is impossible and the whole BP,
LRP and MRCP family is out of reach. The current SRT program does not have one.

---

## 2. Lateralised readiness potential (LRP)

**What it is.** Subtract the motor cortex signal on the same side as the responding
hand from the opposite side. What survives is the part of preparation specific to
choosing THAT hand. Like differential signalling on a sensor line: common-mode
noise cancels, the side-specific signal remains.

**Why it matters.** The LRP tells you WHEN the brain committed to a specific
response, and it can reveal covert preparation of the wrong hand on error trials
before the correct response wins.

**How it works and what it needs.**

- Standard treatments: Smulders and Miller, "The Lateralized Readiness Potential",
  chapter in The Oxford Handbook of Event-Related Potential Components (Oxford
  University Press, 2012; verified via Maastricht University's publication record),
  and Eimer (1998, Behavior Research Methods, Instruments and Computers 30,
  "The lateralized readiness potential as an on-line measure of central response
  activation processes").
- Computed at C3/C4 with the double-subtraction: average of (contralateral minus
  ipsilateral) across left-hand and right-hand response trials, which cancels
  stimulus-side confounds. Both stimulus-locked LRP onset (when selection begins)
  and response-locked LRP onset (motor execution stage) are used.
- Hard requirement: responses must be assigned to LEFT versus RIGHT hand. Four
  fingers of one hand will not produce an LRP; the hemispheric asymmetry is what
  the measure IS. In Basil's suite only the bilateral modes (mirror mode, both-hands
  blocks, 4 sensors per hand on two boards) can feed an LRP analysis.
- The LRP is small (order of 1 uV or a few uV), so it needs a lot of trials. Eimer
  (1998) states plainly that a relatively large number of trials is needed for
  acceptable signal-to-noise. For concrete power numbers use Boudewyn, Luck,
  Farrens and Kappenman (2018, Psychophysiology 55, e13049, "How many trials does
  it take to get a significant ERP effect? It depends"): power depends jointly on
  trial count, participant count and effect size, and doubling trials can more than
  double power. Jensen et al. (2023, Psychophysiology, "Towards thoughtful planning
  of ERP studies") extends the same simulation logic across seven components.
  Planning rule for the thesis: budget 100+ artifact-free trials per hand per
  condition rather than quoting a single magic number.

---

## 3. Contingent negative variation (CNV)

**What it is.** When a warning cue tells you a go-signal is coming, a slow negative
wave builds during the wait. It is the EEG picture of "get ready... almost...".
Think of it as the integrator in a control loop winding up toward the expected
event time.

**Why it matters.** The CNV is the cleanest window this project has on preparation
and anticipatory attention, because Basil's reaction mode already has a real
foreperiod that is seconds long. It quantifies HOW prepared the patient is on each
block, and clinically it moves with attention pathology (CNV differences reported
as a biomarker of abnormal attention in functional movement disorders, PMC 2021).

**How it works and what it needs.**

- First described by Walter, Cooper, Aldridge, McCallum and Winter (1964, Nature
  203, the "expectancy wave"): a negative slow potential between a warning stimulus
  (S1) and an imperative stimulus (S2) that demands a response.
- With S1-S2 intervals of about 3 s or more the CNV splits into an initial CNV
  (orienting to S1, frontal, roughly 0.5 to 1.5 s after the cue) and a late CNV
  (centro-parietal ramp peaking just before S2). Brunia and van Boxtel ("CNV and
  SPN: Indices of Anticipatory Behavior", in The Bereitschaftspotential, Springer,
  2003) flag the key confound: in a warned reaction task the late CNV mixes
  anticipatory attention to the stimulus with motor preparation for the response,
  and the two cannot be separated without a design trick (they use time-estimation
  tasks to pull the motor part away from the perceptual part).
- Practical requirements: a DISCRETE warning event, an S1-S2 interval of at least
  ~1 s (classically 1 to 4 s), long-time-constant or DC recording like the BP, eye
  movement control, and trial averaging. A current methods chapter (Contingent
  Negative Variation (CNV), in a 2024 Springer Neuromethods protocols volume)
  states the CNV is not visible in raw EEG and becomes discernible after averaging
  as few as 6 to 12 trials in healthy adults, though stable amplitude estimates
  want far more. Treat 30+ per condition as the planning floor.

**Fit with our software, stated plainly.**

- The old SRT program cannot produce a CNV: ISIs of 250 to 750 ms with no discrete
  warning stimulus.
- Basil's reaction mode has the right TIMESCALE (seconds-long foreperiod) but two
  design decisions currently work against a textbook CNV. First, there is no
  explicit S1: the foreperiod starts silently once the rest gate clears, so there
  is no event for the brain (or the epoching script) to lock to. Second, the
  exponential foreperiod keeps the stimulus hazard flat ON PURPOSE, and the CNV
  ramp is precisely an expectancy signal, so a flat-hazard design attenuates and
  temporally smears the late CNV. This is the same behavioural logic as Niemi and
  Naatanen (1981, Psychological Bulletin) applied in reverse.
- Resolution that keeps both goals: add a visible-plus-marker "ready" cue at
  foreperiod onset, and add a fixed-foreperiod EEG variant (for example a constant
  2.5 or 3 s wait) used only in EEG blocks. Exponential blocks keep the clean
  behavioural RT number; fixed-foreperiod blocks buy the CNV. Both need only a
  config flag and one extra marker code.

---

## 4. Mu and beta desynchronisation (ERD) and the beta rebound

**What it is.** The sensorimotor cortex idles with rhythms at ~10 Hz (mu) and
~15 to 30 Hz (beta). When you prepare and make a movement those rhythms drop in
power (event-related desynchronisation, ERD), and after the movement ends beta
overshoots above baseline (post-movement beta rebound, PMBR). Like a motor's idle
whine dipping under load and briefly surging when the load releases.

**Why it matters.** ERD is the workhorse of motor rehab EEG: it happens on every
press, works for attempted movement even when the limb barely moves, and is the
signal stroke BCI systems train on. It does not need left-versus-right hands the
way the LRP does.

**How it works and what it needs.**

- Foundational reference: Pfurtscheller and Lopes da Silva (1999, Clinical
  Neurophysiology 110, "Event-related EEG/MEG synchronization and
  desynchronization: basic principles"). ERD is quantified as percentage band-power
  change against a pre-event baseline; mu localises over somatosensory cortex,
  beta over motor cortex.
- Timing: beta and mu ERD can begin up to ~2 s before self-paced movement (about
  0.5 s before cued movement in many reports), persists through the press, and
  PMBR peaks roughly 0.5 to 1 s after movement offset. Hard constraint for game
  design: a 2025 study (Frontiers in Neuroscience, "Demonstrating the need for
  long inter-stimulus intervals when studying the post-movement beta rebound
  following a simple button press") shows the PMBR takes seconds to resolve, so
  short inter-press intervals contaminate both the next trial's baseline and the
  rebound estimate. Fast modes (rhythm, chords at speed) will smear ERD/PMBR
  together; only sparse-press modes give clean oscillatory measures.
- Requirements: response markers (again), a movement-free baseline window per
  trial, electrodes over C3/C4/Cz, and roughly 30+ trials for stable ERD maps.
  Single-trial ERD detection is exactly what motor-imagery BCIs do, so block-level
  online feedback is feasible, just noisy per trial.
- Rehab evidence: reviews of BCI stroke rehab (PMC 2023 guide;
  ScienceDirect 2020 review of MI-BCI for upper limb post-stroke) describe ERD
  and MRCP detection driving FES and feedback with clinically meaningful upper
  limb gains.

---

## 5. Attention and effort indices: alpha, frontal theta, and the ratio zoo

### 5a. Posterior alpha and lapses (solid end of the spectrum)

- O'Connell, Dockree, Robertson, Bellgrove, Foxe and Kelly (2009, Journal of
  Neuroscience 29(26), "Uncovering the neural signature of lapsing attention")
  showed pre-stimulus posterior alpha power rises up to 20 s before a missed
  target in a sustained attention task. Elevated posterior alpha as a marker of
  disengagement from the external task, mind wandering and fatigue is one of the
  better-replicated findings in this space, with the caveat that recent vigilance
  work (bioRxiv 2024 preprint on vigilance, fatigue and motivation; preprint, not
  peer reviewed) reads time-on-task alpha rises as fatigue rather than effort.
- Realistic use in a rehab session: within-subject, baselined at session start,
  smoothed over tens of seconds, alpha trend plus the game's own behavioural
  stream (RT median drift, lapse count over 500 ms, misses) can flag "this block
  shows disengagement or fatigue, consider a break". Group-level validity decent;
  moment-to-moment single-trial claims weak.

### 5b. Frontal midline theta and effortful control

- Cavanagh and Frank (2014, Trends in Cognitive Sciences 18, "Frontal theta as a
  mechanism for cognitive control"): midfrontal theta generated around midcingulate
  and pre-SMA scales with the need for cognitive control. Meta-analytic support:
  Cavanagh and Shackman (2014, PubMed 24787485, "Frontal midline theta reflects
  anxiety and cognitive control: meta-analytic evidence").
- This is the closest legitimate signal to Basil's "using too much concentration"
  question: high sustained frontal theta suggests the task is being run under
  effortful control rather than automatically. But it indexes NEED for control,
  not "bad" concentration, and it also rises with anxiety. Direction of a
  within-patient change across sessions (less frontal theta for the same score as
  skill automatises) is defensible; a live "you are over-concentrating" alarm from
  it is not.

### 5c. Engagement and workload ratios (the chequered part, said plainly)

- Engagement index beta/(alpha+theta): Pope, Bogart and Bartolome (1995,
  Biological Psychology 40, "Biocybernetic system evaluates indices of operator
  engagement in automated task"), extended in NASA reports (e.g. Freeman et al.,
  NASA NTRS 19970003078). The index was selected because it made a feedback loop
  behave stably, not because it was validated against a construct of attention.
  Later applied work reuses it uncritically. Treat any single-number "engagement"
  claim built on it as weak.
- Theta/beta ratio (TBR): proposed by Lubar (1991) as an ADHD marker, FDA-cleared
  as an adjunct, then dismantled: Arns, Conners and Kraemer (2013, Journal of
  Attention Disorders, "A decade of EEG Theta/Beta Ratio research in ADHD: a
  meta-analysis", PubMed 23086616) found large heterogeneity and effect sizes
  shrinking over time, concluding TBR is not a reliable diagnostic measure. A 2026
  multiverse analysis (medRxiv/eLife reviewed preprint 111114; preprint status
  noted) found TBR group effects contingent on analytic choices and largely driven
  by aperiodic (1/f) activity and individual alpha frequency, not genuine
  theta-beta oscillatory differences. That aperiodic confound applies to EVERY
  band-ratio index, including 5b and 5c measures, unless the aperiodic slope is
  modelled out.
- Alpha-to-theta workload ratios: a direct evaluation (Frontiers in
  Neuroinformatics 2022, "An evaluation of the EEG alpha-to-theta and
  theta-to-alpha band ratios as indexes of mental workload") states validation
  for these ratios as cognitive load indicators is minimal.

### 5d. "Over-concentrating" during movement: the reinvestment literature

- There IS a real literature adjacent to Basil's intuition: conscious motor
  processing ("reinvestment") measured by EEG coherence between left temporal
  (T7, verbal-analytical) and frontal midline (Fz, motor planning) sites. Zhu,
  Poolton, Wilson, Maxwell and Masters (2011; venue not verified in this
  session's searches, flagged) linked T7-Fz co-activation to conscious control
  propensity. A meta-analysis (Raman and Filho 2024, Experimental Brain Research,
  "The relationship between T7-Fz alpha coherence and peak performance in
  self-paced sports") finds lower T7-Fz alpha coherence accompanies better
  performance, consistent with skilled automaticity being LESS verbally
  supervised. A systematic review exists (International Review of Sport and
  Exercise Psychology, vol 16, 2023, "EEG correlates of verbal and conscious
  processing of motor control").
- Counter-evidence in the same searches: a bioRxiv preprint ("All talk? Left
  temporal alpha oscillations are not specific to verbal-analytical processing
  during conscious motor control") fails to endorse the T7 alpha interpretation,
  and a published comment disputes the 2024 meta-analysis. Status: plausible,
  contested, exploratory only. Fine as a thesis side-analysis, not a claim.

### 5e. The neuromyth line

- A live per-second "attention score" for an individual is marketing, not
  measurement. The BrainCo Focus classroom headband is the cautionary tale:
  neuroscientists quoted in press coverage (EdSurge 2017; UCSF's Theodore Zanto)
  said EEG cannot dissociate attending to the task from attending to a phone or a
  daydream, units reportedly registered signals while not being worn, and Chinese
  authorities suspended classroom use after public backlash (People's Daily 2019).
- What survives scrutiny: within-person, baselined, block-averaged trends (alpha
  up plus RT lapses up = disengaging; frontal theta down across sessions at equal
  performance = automatising), always paired with behaviour. What does not: any
  between-person threshold, any single-trial attention verdict, any
  "concentration percentage".

---

## 6. What this lane asks of the trigger layer and the experiment design

Markers (single-byte serial, same protocol as the SRT program; codes 1 to 255
available, 0 reserved for reset):

1. Response onset marker, distinct codes for correct and incorrect, and per hand
   in bilateral blocks. Non-negotiable: BP/MRCP, response-locked LRP, ERD and PMBR
   all die without it. Timestamp source should be the 200 Hz force stream crossing,
   not the 60 Hz render loop.
2. Warning/foreperiod-onset marker (with a visible ready cue added to reaction
   mode). Enables CNV epochs and defines the pre-stimulus baseline.
3. Stimulus onset marker (already the SRT precedent, byte 30). Keep per-lane or
   per-mode variants as distinct codes.
4. Catch-trial marker at the moment the stimulus WOULD have fired: gives
   stimulus-free foreperiod epochs, the cleanest possible preparation window.
5. Block start/end and mode-identity markers for segmentation.

Design constraints from this lane:

- Fixed-foreperiod EEG variant of reaction mode (2.5 to 3 s) for CNV; keep the
  exponential draw for behavioural blocks; log which variant ran.
- fp_min of at least ~2 s in EEG blocks so pre-stimulus baselines and pre-movement
  ERD windows are movement-free; enforce inter-trial rest of several seconds where
  PMBR is analysed.
- Trial budgets: think in the Boudewyn et al. (2018) frame, not magic numbers.
  Floors that the cited literature supports: CNV visible from ~6 to 12 trials but
  plan 30+; ERD ~30+; BP/MRCP several tens; LRP 100+ per hand per condition.
- Amplifier settings matter for the slow potentials: BP and CNV need a high-pass
  of 0.05 Hz or lower (or DC), which is a recording decision made in the lab's
  acquisition software, not in our code, but worth stating in the thesis methods.

Bottom line for Basil's two questions in this lane. "Can we measure the brain being
prepared for presses?" Yes, three ways, all standard: CNV in the foreperiod (needs
an S1 cue and ideally a fixed-foreperiod variant), pre-movement MRCP negativity and
mu/beta ERD (need a response marker), and LRP if bilateral blocks are used.
"Can we tell paying attention from too much concentration?" Partially and only
honestly: disengagement/fatigue trends via posterior alpha plus behaviour are
defensible; effortful-versus-automatic control via frontal midline theta trends
across sessions is defensible as a secondary measure; T7-Fz coherence is an
exploratory extra; any real-time attention dial or fixed engagement ratio is the
part of the literature that has not held up, and the thesis should say so.

---

## Source list (verified in this session's searches unless flagged)

- Kornhuber H and Deecke L (1965). Hirnpotentialaenderungen bei Willkuerbewegungen
  und passiven Bewegungen des Menschen. Pfluegers Archiv 284.
- Shibasaki H and Hallett M (2006). What is the Bereitschaftspotential? Clinical
  Neurophysiology.
- Smulders F and Miller J (2012). The Lateralized Readiness Potential. In The
  Oxford Handbook of Event-Related Potential Components, OUP.
- Eimer M (1998). The lateralized readiness potential as an on-line measure of
  central response activation processes. Behavior Research Methods, Instruments
  and Computers 30.
- Boudewyn M, Luck S, Farrens J and Kappenman E (2018). How many trials does it
  take to get a significant ERP effect? It depends. Psychophysiology 55, e13049.
- Jensen et al. (2023). Towards thoughtful planning of ERP studies.
  Psychophysiology.
- Walter W G, Cooper R, Aldridge V, McCallum W and Winter A (1964). Contingent
  negative variation. Nature 203.
- Brunia C and van Boxtel G (2003). CNV and SPN: Indices of Anticipatory
  Behavior. In The Bereitschaftspotential, Springer.
- Contingent Negative Variation (CNV) protocol chapter (2024). Springer
  Neuromethods (978-1-0716-3545-2_2).
- Niemi P and Naatanen R (1981). Foreperiod and simple reaction time.
  Psychological Bulletin. (Also cited in reaction.py's own docstring.)
- Pfurtscheller G and Lopes da Silva F (1999). Event-related EEG/MEG
  synchronization and desynchronization: basic principles. Clinical
  Neurophysiology 110.
- Frontiers in Neuroscience (2025). Demonstrating the need for long
  inter-stimulus intervals when studying the post-movement beta rebound following
  a simple button press. (PMC12061888.)
- O'Connell R, Dockree P, Robertson I, Bellgrove M, Foxe J and Kelly S (2009).
  Uncovering the neural signature of lapsing attention. Journal of Neuroscience
  29(26).
- Cavanagh J and Frank M (2014). Frontal theta as a mechanism for cognitive
  control. Trends in Cognitive Sciences 18.
- Cavanagh J and Shackman A (2014). Frontal midline theta reflects anxiety and
  cognitive control: meta-analytic evidence. (PubMed 24787485.)
- Pope A, Bogart E and Bartolome D (1995). Biocybernetic system evaluates indices
  of operator engagement in automated task. Biological Psychology 40.
- Arns M, Conners C and Kraemer H (2013). A decade of EEG Theta/Beta Ratio
  research in ADHD: a meta-analysis. Journal of Attention Disorders.
  (PubMed 23086616.)
- Theta-Beta Ratio in ADHD: a multiverse analysis (2026). medRxiv / eLife
  reviewed preprint 111114. PREPRINT, flag in thesis.
- An evaluation of the EEG alpha-to-theta and theta-to-alpha band ratios as
  indexes of mental workload (2022). Frontiers in Neuroinformatics.
- Raman and Filho (2024). The relationship between T7-Fz alpha coherence and peak
  performance in self-paced sports: a meta-analytical review. Experimental Brain
  Research. (A published comment disputes it; both sides noted in text.)
- Zhu, Poolton, Wilson, Maxwell and Masters (2011). Neural co-activation and
  conscious motor control. VENUE NOT VERIFIED this session, flagged.
- EEG correlates of verbal and conscious processing of motor control in sport and
  human movement: a systematic review (2023). International Review of Sport and
  Exercise Psychology 16.
- All talk? Left temporal alpha oscillations are not specific to verbal-analytical
  processing during conscious motor control. bioRxiv. PREPRINT, counter-evidence.
- BCI stroke rehab reviews: A comprehensive guide to BCI-based stroke
  neurorehabilitation interventions (PMC, 2023); Review on motor imagery based BCI
  systems for upper limb post-stroke neurorehabilitation (Computers in Biology and
  Medicine, 2020, via ScienceDirect); BCI-neurofeedback with motor attempt in
  cerebral palsy (PMC, 2024).
- Frontiers in Neuroscience (2021). Electroencephalographic recording of the
  movement-related cortical potential in ecologically valid movements: a scoping
  review.
- Press coverage for the neuromyth section: EdSurge (2017) on BrainCo Focus EDU
  with the Zanto quote; People's Daily Online (2019) on the classroom suspension.
