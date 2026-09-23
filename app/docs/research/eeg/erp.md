# ERP research notes: event-related potentials for the SRT replacement

Lane: stimulus-locked components (P1/N1, P3b), response-locked correctness
components (ERN/Ne, Pe), FRN, sequence-learning ERP findings in SRT
paradigms, force-transducer response onsets, and what a modest lab setup
can legitimately claim.

Source of ground truth: SRT_Sequence_learning_Final_v2.py (read in full,
11 Aug 2026). All papers below were found and verified in web searches on
11 Aug 2026. Anything not verifiable is flagged, not cited.

## 1. What the existing program actually does (from the code)

- Serial port COM10, one byte per event. MARKER_FLASH_ONSET = 30 written
  at the flip that turns the target square red, held for
  MARKER_PULSE_FRAMES (2/120 s scaled to the frame rate, so ~16.7 ms),
  then MARKER_RESET = 0. DummySerial fallback in test mode.
- That is the entire marker vocabulary. No response markers, no
  correctness codes, no phase, block or sequence-position codes, no
  feedback markers. Correctness is computed in software on every trial
  (correct, incorrect, miss, anticipatory variants) but never leaves the
  CSV log.
- Timing: flash 100 ms, response deadline 2500 ms, anticipation window
  100 ms, ISI 500 ms average (250/500/750 in the cyclical and random
  groups), 1000 ms pause before each block's first trial.
- Trial counts: practice 48 random, learning 8 blocks x 100 (fixed
  10-item sequence x 10 reps), post-test 48 random. 896 trials total.
- Feedback text (Correct / Incorrect / Miss) is shown in the practice
  phase only. Learning and post-test show none.
- Visual layout keeps the four squares close together to minimise eye
  movement, stated in the header comment. Keep that property in the
  pygame port for any EEG mode.

Implication: with the current scheme, only stimulus-locked averaging is
possible, and only by collapsing across all conditions, or by
reconstructing condition labels offline by lining marker times up with
the CSV. Response-locked ERPs are impossible without either a response
marker or offline reconstruction from logged RTs, which then inherits
keyboard timestamp jitter with no way to check it.

## 2. Q1: which events deserve markers, and what each enables

The serial protocol carries one byte, values 1 to 255 (0 is the reset
state), so the whole scheme must fit in 255 codes. What the ERP
literature requires:

| Event | Marker content | Component unlocked | Research question served |
| --- | --- | --- | --- |
| Stimulus onset | lane (1-4), phase (random/sequence), sequence position or deviant status | P1, N1, N2b, P3b | stimulus processing, attention, sequence learning |
| Response onset | correctness code (correct, incorrect, anticipatory, miss timeout), lane pressed | ERN/Ne, Pe, response-locked LRP | error monitoring, Basil's "correct or not" question |
| Feedback onset | valence (positive/negative/neutral) | FRN / reward positivity | feedback processing, only if the game shows discrete feedback |
| Block/phase boundaries | phase ID, block number | none directly | segmentation, artifact bookkeeping, learning-stage bins |
| Trial-start or warning event (if a game mode has one) | condition | CNV, pre-stimulus LRP | preparation, Basil's "prepared for presses" question |

Design rules the components impose on the scheme:

- One unique code per condition cell you ever want to average
  separately. You cannot split retrospectively on information the marker
  never carried unless you also trust the log-file alignment.
- The response marker must be written at response onset (force threshold
  crossing) in the same loop iteration that detects it, and correctness
  is already known at that moment in software, so the correctness code
  can ride on the response byte itself. No second pass needed.
- Marker jitter must be small relative to the component measured. P1 is
  a ~100 ms component with tens-of-ms width; frame-locked stimulus
  markers at 60 Hz (16.7 ms granularity) are the accepted standard in
  the existing program and in PsychoPy practice, provided the marker is
  written at the flip. Response markers from a 200 Hz force loop have
  5 ms granularity, which is better than typical USB keyboard scan
  jitter.
- Pulse-then-reset (30 then 0) must be kept, and pulse width must stay
  shorter than the shortest possible interval between two events,
  otherwise consecutive events merge. With 250 ms minimum ISI and fast
  correct responses landing 200-400 ms after onset, a 10-16 ms pulse is
  safe; anticipatory presses inside the flash need a rule (for example,
  delay the response byte until the stimulus pulse has reset).
- Keil et al. (2014), the Society for Psychophysiological Research
  committee report (Psychophysiology 51, 1-21), requires reporting of
  trigger definition, timing accuracy, trial counts per cell after
  rejection, epoch windows, baselines and filters. Design the scheme so
  those numbers exist.

## 3. Stimulus-locked components

### P1 and N1 (exogenous visual, attention-modulated)
- What they are: early visual responses over lateral occipital sites,
  P1 ~80-130 ms, N1 ~150-200 ms after stimulus onset. Their amplitude
  is increased for attended locations, the classic "sensory gain
  control" finding: Hillyard and Anllo-Vento (1998), PNAS 95(3),
  781-787.
- What they need: precise stimulus-onset markers (photodiode validation
  worth doing once on the lab monitor), pre-stimulus baseline (commonly
  -200 to 0 ms), epochs of ~-200 to 800 ms, and many trials because they
  are small (a few microvolts). Boudewyn, Luck, Farrens and Kappenman
  (2018, Psychophysiology 55, e13049) show statistical power is a joint
  function of trials, participants and effect size; there is no single
  magic trial number, but small components need substantially more
  trials than P3b.
- Role for Basil: mostly a manipulation check (were stimuli seen,
  attended), not a primary outcome.

### P3b
- What it is: large centro-parietal positivity, ~300-600 ms, indexing
  stimulus categorisation and context updating; amplitude scales with
  target probability and attentional resource allocation, latency with
  stimulus evaluation time. Polich (2007), "Updating P300: an
  integrative theory of P3a and P3b", Clinical Neurophysiology 118,
  2128-2148 (about 7000+ citations, the standard review).
- What it needs: same stimulus markers, epochs out to 800-1000 ms.
  It is big (10+ microvolts), so it tolerates fewer trials and modest
  equipment better than any other component here.
- Role for Basil: workload and target-processing index across game
  modes, and a learning index in sequence paradigms (below).

### The overlap trap at 500 ms ISI
- With a 500 ms average ISI, the P3b and slow waves of trial n are still
  unfolding when trial n+1 appears, and preparation activity for n+1
  contaminates the pre-stimulus baseline of n+1. Woldorff (1993),
  Psychophysiology 30, 98-119, is the standard treatment of overlap
  distortion and its correction (ADJAR).
- Mitigations available in Basil's design: the ISI jitter that already
  exists in the cyclical and random groups actually helps overlap
  averaging out; keep epochs short; compare conditions with identical
  ISI statistics so overlap subtracts out in difference waves. This
  point matters for the thesis method chapter.

## 4. Response-locked components: correct versus incorrect

This answers Basil's question 3 directly. The brain generates an
internal error signal within ~100 ms of an incorrect response, without
any external feedback.

### ERN / Ne
- Discovered independently by Falkenstein, Hohnsbein, Hoormann and
  Blanke (1991), Electroencephalography and Clinical Neurophysiology 78,
  447-455 (they called it Ne), and Gehring, Goss, Coles, Meyer and
  Donchin (1993), "A neural system for error detection and
  compensation", Psychological Science 4, 385-390.
- Sharp fronto-central negativity, maximal at FCz, peaking 0-100 ms
  after response onset on error trials. Generally attributed to anterior
  cingulate cortex. Gehring et al. (1993) showed it grows when accuracy
  is emphasised and shrinks under speed emphasis, so instructions
  modulate it.
- Tutorial reference: Falkenstein et al. (2000), "ERP components on
  reaction errors and their functional significance: a tutorial",
  Biological Psychology 51, 87-107 (PubMed 10686361).
- Correct trials show a smaller correct-response negativity (CRN), so
  the standard analysis is the error-minus-correct difference wave:
  Vidal, Hasbroucq, Grapperon and Bonnet (2000), "Is the 'error
  negativity' specific to errors?", Biological Psychology 51, 109-128,
  found Ne-like activity on correct trials with Laplacian methods, and
  amplitude graded errors > partial errors > correct.

### Pe
- Centro-parietal positivity ~150-500 ms (commonly measured 200-400 ms)
  after errors, linked to conscious recognition of the error. Review:
  Overbeek, Nieuwenhuis and Ridderinkhof (2005), Journal of
  Psychophysiology 19(4), 319-329. ERN can occur without awareness; Pe
  tracks awareness. So ERN vs Pe dissociates "the brain caught the slip"
  from "the person noticed".

### What they require from the marker scheme and design
- Response markers time-locked to response onset carrying a correctness
  code. Stimulus markers alone cannot give response-locked averages
  because RT varies trial to trial.
- Epochs of roughly -500 to +800 ms around response onset. Baseline is
  taken pre-response (windows like -400 to -200 ms or -200 to -50 ms
  appear across the literature; conventions vary, pick one and report
  it) or pre-stimulus; both appear in published work.
- Trial counts: Olvet and Hajcak (2009), "The stability of error-related
  brain activity with increasing trials", Psychophysiology 46, 957-961:
  ERN and Pe averages stabilise at about 6 error trials (correlations
  with the grand average above .80, SNR plateau by 8 and 4 trials
  respectively). That is a floor for a stable within-subject estimate,
  not a target; for between-condition or between-group contrasts,
  Boudewyn et al. (2018) argue for as many trials as feasible.
- Arithmetic for Welber's design: 896 trials at a typical SRT error rate
  of 5-10 % gives roughly 45-90 errors per participant, comfortably
  above the floor. Basil's game modes must be checked mode by mode: any
  mode intended to support ERN analysis needs enough trials, and enough
  difficulty, that participants actually commit 20+ usable errors after
  artifact rejection. An easy rhythm mode with 2 % errors will not
  support an ERN contrast.
- Speed pressure matters: participants must be pushed fast enough to
  err. The 2.5 s deadline in the current SRT produces mostly misses
  rather than commission errors if people slow down; commission errors
  (wrong lane) are what the ERN needs. Misses have no response onset and
  produce no response-locked epoch at all; code them separately.

### What this buys Basil
Answer to his question: yes. With correctness-coded response markers he
can show, within his own participants, a fronto-central negativity
within ~100 ms of wrong presses that is absent or reduced for correct
presses, without the game telling anyone they were wrong. That is a
clean, well-replicated, thesis-sized claim, and it is the single
strongest argument for adding response markers to the trigger layer.

## 5. Force-sensor response onsets: what the literature says

This is the pleasant surprise: continuous force responses are not a
deviation from ERN methodology, they are its founding method.

- Gehring et al. (1993) had participants respond by squeezing
  dynamometers, recording continuous squeeze force and EMG, in a flanker
  task (H/S letter arrays). Response-related measures were defined on
  squeeze and EMG activity, not on key switches. So defining response
  onset by a force threshold crossing has precedent in the original ERN
  paper itself.
- Vidal et al. (2000) time-locked the Ne to EMG onset and found it peaks
  about 100 ms after EMG onset. EMG onset precedes any mechanical switch
  closure by a variable electromechanical delay, so aligning to an
  earlier, physiologically closer event sharpens response-locked
  averages. A low force threshold crossing sits between EMG onset and a
  full keypress: earlier and less variable than a key switch, later than
  EMG. Practical consequence: force-defined onsets should give equal or
  better response-locked alignment than the keyboard fallback, and the
  keyboard condition is the one that needs the caveat, not the sensors.
- Continuous force also enables partial-error analysis: sub-threshold
  activation of the wrong effector followed by a correct response.
  In EMG work, ERN amplitude grades errors > partial errors > correct
  (Vidal et al. 2000). Basil's 200 Hz force streams can capture the
  force-domain analogue (wrong-finger force ripples that never reach
  threshold), a genuinely novel little analysis for a rehab context.
- Response-locked motor components with isometric force responses are
  established for the lateralised readiness potential too: Masaki et al.
  (2004), "The functional locus of the lateralized readiness potential",
  Psychophysiology 41; methods overview in Eimer (1998), Behavior
  Research Methods, Instruments and Computers 30, 146-156. (A paper
  titled "Rate of force development and the lateralized readiness
  potential" also exists but its author list was not verifiable in my
  searches, so it is flagged rather than cited.)

Requirements this imposes on Basil's software:
1. Fix the online response threshold, report it in newtons or % of max
   voluntary force per participant, and never change it silently
   (Keil et al. 2014 reporting standards).
2. Write the response marker byte at the sample where force crosses the
   threshold, in the 200 Hz sensor loop, not in the 60 Hz render loop.
3. Log raw force traces per trial so response onset can be re-defined
   offline (for example back-extrapolation to a lower threshold), the
   same way EMG onset re-scoring is done.
4. In keyboard-fallback sessions, mark the modality in the data file;
   keyboard and force sessions should not be pooled for response-locked
   analyses without checking alignment.

## 6. FRN, only if the game shows discrete feedback

- Miltner, Braun and Coles (1997), Journal of Cognitive Neuroscience
  9(6), 788-798: negative feedback in a time-estimation task elicits a
  fronto-central negativity ~250 ms after feedback onset, interpreted as
  a generic error-detection response to external error information.
- Modern reading: the difference is driven by a reward positivity to
  positive outcomes that is absent after non-reward. Proudfit (2015),
  Psychophysiology 52(4), 449-459.
- Requirements: a feedback marker with valence code, feedback delivered
  as a discrete time-locked event (a score popup, a hit/miss flash), a
  fixed response-to-feedback delay if possible, and separation from
  response-locked activity. Continuous score counters or health bars do
  not produce a usable FRN event.
- Fit to the current programs: the SRT shows feedback only in practice.
  Basil's games show hit/miss effects constantly, so his software is
  actually better positioned for FRN than Welber's, provided each
  feedback event gets a marker and a valence code. ERN needs no feedback
  at all, which is why questions 3 (ERN) and feedback (FRN) are separate
  analyses.

## 7. Sequence-learning ERP findings in SRT paradigms

Verified core literature:

- Eimer, Goschke, Schlaghecken and Stürmer (1996), "Explicit and
  implicit learning of event sequences: evidence from event-related
  brain potentials", Journal of Experimental Psychology: Learning,
  Memory, and Cognition 22, 970-987. Deviant items inserted into a
  learned 10-item sequence elicit enhanced negativities (N2-family) and
  learning shows up as anticipatory response preparation (LRP effects
  before stimulus onset for predictable items).
- Rüsseler and Rösler (2000), "Implicit and explicit learning of event
  sequences: evidence for distinct coding of perceptual and motor
  representations", Acta Psychologica: implicit learners show ERP
  deviance effects for motor deviants only; explicit learners show them
  for perceptual deviants too.
- Rüsseler et al., "Differences in incidental and intentional learning
  of sensorimotor sequences as revealed by event-related brain
  potentials", Cognitive Brain Research (2003 per journal listing):
  enhanced N2b and P3b to deviants in intentional learners only.
  (Existence and title verified; check exact author list and pages when
  citing in the thesis.)
- Ferdinand, Mecklinger and Kray (2008), "Error and deviance processing
  in implicit and explicit sequence learning", Journal of Cognitive
  Neuroscience 20(4), 629-642: N2b to deviants appears in both implicit
  and explicit conditions and grows as learning proceeds; actual
  commission errors elicit a clear response-locked ERN/Ne.
- Schlaghecken, Stürmer and Eimer (2000), "Chunking processes in the
  learning of event sequences: electrophysiological indicators", Memory
  and Cognition 28(5), 821-831: ERP markers differ at chunk boundaries,
  suggesting sequences are learned in chunks.

What this means for the marker scheme: to reproduce any of these
analyses the stimulus marker must encode, at minimum, (a) phase (random
vs fixed sequence), and ideally (b) sequence position 1-10, or at least
a flag distinguishing sequence-consistent stimuli from deviant or random
ones. Then the standard learning analyses become available: N2b/P3b to
random-phase stimuli before vs after learning, deviance responses, and
their growth across blocks as a neural learning curve alongside the RT
learning curve. With only marker 30, none of this exists.

## 8. Preparation and attention (question 4), the ERP part

- CNV: Walter, Cooper, Aldridge, McCallum and Winter (1964), Nature 203,
  380-384. A slow negative build-up between a warning event and an
  imperative stimulus, the classic electrophysiological sign of
  preparation and expectancy.
- In an SRT with a fixed 500 ms ISI, each response effectively warns of
  the next stimulus, so CNV-like preparation and pre-stimulus LRP
  lateralisation build before predictable stimuli; Eimer et al. (1996)
  used exactly this logic to show sequence knowledge as anticipatory
  response preparation before stimulus onset.
- What is claimable: averaged pre-stimulus negativity differences
  between conditions or learning stages (prepared vs unprepared), with
  the honest caveat that at 500 ms ISI the "baseline" contains the
  previous trial's late components (Woldorff 1993 overlap point again;
  the jittered-ISI groups help).
- What is not claimable: a single-trial online "attention meter" or a
  "too much concentration" readout. Averaged ERPs are defined over many
  trials; single-trial preparation classification is a different, much
  harder methodology and nothing in this literature licenses it for a
  thesis-scale setup. Basil's anticipatory-press codes (already in the
  SRT logic) are the behavioural face of the same construct and are free.
- Oscillatory measures (frontal midline theta, alpha suppression) are a
  better fit for "attention level" questions but are outside this lane.

## 9. What Basil can legitimately claim with this setup

Working assumptions: the lab's research EEG amplifier with the serial
trigger line (the same rig Welber's program targets), modest channel
count, force-sensor responses, one session per participant.

Defensible claims:
1. Stimulus-locked visual responses (P1/N1/P3b) to game events, with
   P3b condition effects (probability, workload) as the workhorse.
2. Error vs correct difference waves showing ERN and Pe with
   correctness-coded response markers, given 20+ artifact-free errors
   per participant (floor of 6-8 per Olvet and Hajcak 2009, more for
   contrasts per Boudewyn et al. 2018).
3. Sequence-learning effects: N2b/P3b deviance and learning-stage
   effects, given phase and position codes in the stimulus markers.
4. FRN / reward positivity to discrete game feedback, given valence-
   coded feedback markers.
5. Averaged preparation differences (CNV-like, pre-stimulus LRP) between
   conditions, with the overlap caveat.
6. Force-defined response onsets as a methodological strength, citing
   Gehring et al. (1993) squeeze responses and Vidal et al. (2000)
   EMG-locking precedent, plus a partial-error analysis nobody else in
   the rehab-game space is doing.

Not defensible:
- Source localisation claims ("the ACC did X") from few channels; say
  "fronto-central negativity consistent with the ERN literature".
- Single-trial cognitive state readouts (attention, concentration,
  effort) or any online adaptive claim based on ERPs.
- Clinical or diagnostic claims about rehabilitation outcomes from ERP
  amplitudes.
- Pooling keyboard and force-sensor sessions in response-locked
  analyses without an alignment check.

Perspective on hardware adequacy: even a consumer gaming EEG headset has
been validated against a research system for auditory ERPs (Badcock et
al. 2013, PeerJ 1:e38), so a lab-grade amplifier with a dedicated serial
trigger line is not the limiting factor here. The limiting factors are
trial counts per cell, marker completeness and response-onset precision,
all of which are software decisions Basil controls.

## 10. Concrete marker map proposal (one byte, fits the COM10 protocol)

Keep 0 as reset and 30 free to remain compatible with Welber's analysis
scripts if wanted.

- 1-49: stimulus onsets. Suggested: 10 + lane (11-14) random phase,
  20 + lane (21-24) sequence phase standard, 40 + lane (41-44) deviant.
  Sequence position can go in the log file rather than the byte if code
  space runs short; byte codes must cover every cell averaged separately.
- 100-149: response onsets. 100 + lane for correct (101-104), 110 + lane
  for incorrect (111-114), 120 + lane for anticipatory (121-124).
- 150: miss (deadline expired, written at deadline, never averaged as a
  response event).
- 200-209: feedback onsets, 201 positive, 202 negative.
- 210-219: phase and block boundaries.
- Pulse ~10-16 ms then 0, with a guard so a response byte never
  overwrites a still-high stimulus byte (queue it until after reset).
- Log every byte with its timestamp in the game's data file so
  EEG-to-behaviour alignment can be verified offline.

## Verified reference list (all found in searches, 11 Aug 2026)

- Falkenstein, Hohnsbein, Hoormann, Blanke (1991). EEG and Clinical
  Neurophysiology 78, 447-455.
- Gehring, Goss, Coles, Meyer, Donchin (1993). Psychological Science 4,
  385-390.
- Walter, Cooper, Aldridge, McCallum, Winter (1964). Nature 203, 380-384.
- Woldorff (1993). Psychophysiology 30, 98-119.
- Eimer, Goschke, Schlaghecken, Stürmer (1996). JEP: LMC 22, 970-987.
- Miltner, Braun, Coles (1997). J Cognitive Neuroscience 9(6), 788-798.
- Hillyard, Anllo-Vento (1998). PNAS 95(3), 781-787.
- Eimer (1998). Behavior Research Methods, Instruments and Computers 30,
  146-156.
- Falkenstein, et al. (2000). Biological Psychology 51, 87-107.
- Vidal, Hasbroucq, Grapperon, Bonnet (2000). Biological Psychology 51,
  109-128.
- Rüsseler, Rösler (2000). Acta Psychologica (motor vs perceptual
  deviant coding).
- Schlaghecken, Stürmer, Eimer (2000). Memory and Cognition 28(5),
  821-831.
- Rüsseler et al. (2003). Cognitive Brain Research (incidental vs
  intentional; verify exact author list before thesis citation).
- Masaki et al. (2004). Psychophysiology 41 (LRP functional locus).
- Overbeek, Nieuwenhuis, Ridderinkhof (2005). Journal of
  Psychophysiology 19(4), 319-329.
- Polich (2007). Clinical Neurophysiology 118, 2128-2148.
- Ferdinand, Mecklinger, Kray (2008). J Cognitive Neuroscience 20(4),
  629-642.
- Olvet, Hajcak (2009). Psychophysiology 46, 957-961.
- Badcock et al. (2013). PeerJ 1:e38.
- Keil et al. (2014). Psychophysiology 51, 1-21.
- Proudfit (2015). Psychophysiology 52(4), 449-459.
- Boudewyn, Luck, Farrens, Kappenman (2018). Psychophysiology 55, e13049.

Flagged, not cited: Pontifex et al. (2010) on ERN reliability (not
verified in searches); "Rate of force development and the lateralized
readiness potential" (title seen, authors unverified); Gehring and
Willoughby (2002) FRN gambling study (not searched, use Miltner 1997 and
Proudfit 2015 instead).
