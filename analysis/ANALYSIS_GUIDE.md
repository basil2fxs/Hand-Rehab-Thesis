# What the analysis tells us

The notebook produces numbers and plots. This file says what they mean, which
thesis question each one answers, and what can honestly be concluded from it.

Keep the two apart on purpose: the Python stays plain so it is easy to check,
and the argument lives here where it can be edited without touching code.

Contents:

1. [Answering the research question](#1-answering-the-research-question)
2. [The twelve objectives, and what evidences each](#2-the-twelve-objectives)
3. [Every analysis section explained](#3-every-analysis-section-explained)
4. [Numbers from past theses to compare against](#4-comparison-baselines)
5. [What cannot be concluded, and why](#5-limits)
6. [Writing it up](#6-writing-it-up)

---

## 1. Answering the research question

The progress report asks:

> Can adaptive difficulty, music-driven cueing, bilateral operation and
> zero-setup deployment be integrated into a single clinic-ready device that
> captures objective, per-trial measures of hand and finger movement, ready for
> patient trials and analysis?

That splits into four claims, each with its own evidence:

| Claim | Evidence | Section |
|---|---|---|
| Adaptive difficulty works | share of the block held inside the 65 to 80 percent band, per finger | Objective 1 |
| Music cueing is measurable | beat offset accuracy, bias and lag-1 entrainment | Rhythm |
| Bilateral operation works | signed asymmetry per participant | Both hands |
| The data is research grade | exclusions, drift, cue delivery, sampling reality | Data quality |

The honest answer as of Semester 1 is "yes for capture, not yet demonstrated for
effect". The device records everything a trial needs. Whether the training helps
anyone is a Semester 2 question with patients in it, and no amount of analysis of
a healthy hand can answer it.

---

## 2. The twelve objectives

Each objective and the thing that evidences it.

**Objective 1, adaptive controller holds a per-finger hit rate of 65 to 80
percent over a 32-trial block.**
The Objective 1 section runs a rolling 32-trial window *per finger*, because that
is how the objective is worded. This matters: a session can average 72 percent
while the index finger sits at 90 and the pinky at 45, which does not meet the
objective even though the headline number looks fine. Report the per-finger
table, not the session average.

**Objective 2, record peak force for every press.**
The Force section. Both peak force and impulse are logged per trial. Peak says
how hard, impulse says how much effort was held. Two patients can share a peak
and differ entirely in impulse.

**Objective 3, chassis fits the ANSUR percentile range.**
Not answerable from the CSVs. Hand length and breadth are consent-time
measurements. The fields exist in `metadata.json` (`hand_length_mm`,
`hand_breadth_mm`) and have to be filled before a session or the data is gone.

**Objective 4, rhythm mode scores presses against song beats.**
The Rhythm section. Splits into three things that are often confused:
accuracy (how far off the beat), bias (consistently early or late) and
entrainment (actually tracking the tempo rather than landing near beats by
chance).

**Objective 5, bilateral measures including asymmetry and inter-hand
correlation.**
The Both hands section covers asymmetry. Inter-hand correlation is still a
placeholder in `session.json` and needs the force-stream resampling that is on
the Semester 2 list.

**Objectives 6 to 12** cover setup time, port auto-detection, ergonomics and
similar. Most are bench or procedural measurements rather than notebook
computations. `startup_latency_ms` is in `metadata.json` for the setup-time one.

---

## 3. Every analysis section explained

### Overview and dose

**Reports:** games, trials, time on task with pauses removed, presses per minute.

**What it tells you:** whether the session delivered a clinically meaningful
amount of practice. Veerbeek's review found the strongest gains came from high
repetition, and Lohse found more time on task meant more improvement. Lang's
figure of about 32 repetitions in a typical therapy session is the benchmark the
Dose section plots against.

**How to use it:** the repetition count is quotable on its own. If the device
delivers several times a clinical session's worth of practice in the same time,
that is a result, independent of whether anyone got better.

### Data quality

**Reports:** cue commands not delivered, trials with force data, pauses, worst
sensor drift.

**What it tells you:** whether anything below this can be trusted. Four things
quietly ruin a session: the Arduino dropping out so cues stop arriving, baseline
drift changing what the threshold means between the start and end, long pauses
making before-and-after comparisons meaningless, and running in keyboard mode by
accident so there is no force data at all.

**How to use it:** run it first and quote it in the methods. A hit rate without
a statement of what was excluded cannot be judged by a reader.

### Trial exclusions

**Reports:** trials with no cue delivered, presses faster than 100 ms, and the
headline numbers before and after removing them.

**What it tells you:** a press under about 100 ms is faster than a real cued
reaction, so it is a guess that happened to land, not a response. Nakayama's
search window let these count, which matters most in exactly the predictable
condition where anticipation is the confound.

**How to use it:** report the excluded counts. If removing them moves a headline
number much, say so rather than only quoting the cleaner figure.

### Reaction time

**Reports:** mean, median, sd, CV, 10th and 90th percentiles, per finger, and the
within-block slope.

**What it tells you:** three separate things. How fast on average. How consistent
(the CV), which matters because post-stroke hands are more variable and
consistency often improves before speed does. And which finger, since per-finger
measurement is the point of the device.

The distribution leans right, so a mean well above the median means a few slow
trials are dragging it up. Quote both.

**How to use it:** a falling CV with a flat mean is still a real improvement.
Do not dismiss it because the average did not move.

### Movement onset and rate of force development

**Reports:** onset reaction time, response stability, peak dForce, and the gap
between onset and threshold crossing.

**What it tells you:** the game records reaction time as the moment force crossed
a threshold, which happens some way into the press. Onset detection finds where
force first departs from baseline, which is closer to when the finger actually
started moving. The gap between them grows the harder someone presses, so the
threshold measure is biased in a way that differs between people. Onset is the
fairer comparison.

This reproduces Nakayama's Teasdale-style detector, so results sit directly
alongside his rather than being compared by eye.

Rate of force development (peak dForce) is how quickly force is built. A
shallower slope is a recognised deficit after stroke and is invisible in any
peak-only measure.

**How to use it:** quote onset RT as the primary measure and mention the
threshold figure for continuity with the game's own output.

### Accuracy and the challenge point

**Reports:** hit rate, share of the block inside 65 to 80 percent, per-finger
rates, the BPM staircase, recovery episodes.

**What it tells you:** whether the adaptive controller did its job. The band
comes from Guadagnoli and Lee, where learning is fastest when a task is hard
enough to demand attention but not so hard the learner disengages. Wilson and
colleagues put the optimum nearer 85 percent, which is why both lines are drawn.

**How to use it:** the in-band share is the number that supports or undercuts
Thread A. If the controller sat above the band the task was too easy, and the
adaptive logic needs tuning rather than the patient being praised.

### Two kinds of error

**Reports:** misses versus wrong-finger presses per finger, and which finger
fired instead.

**What it tells you:** a miss means nothing happened in time, which points at
weakness or slowness. A wrong-finger press means the intent was there but landed
on the wrong finger, which points at individuation. They are different problems
with different training implications.

**How to use it:** neighbouring fingers dominating the confusion is the classic
individuation pattern rather than inattention. Say which it is.

### Force

**Reports:** peak force and impulse per finger, force across the block.

**What it tells you:** peak is strength, impulse is effort sustained. The
across-block trend is the fatigue check. A falling peak over a block is fatigue;
a rising one can be the patient warming up or learning to press harder.

**How to use it:** always state the unit. If no newton calibration is configured
these are raw sensor counts and are not comparable with anyone else's newtons.

### Finger individuation

**Reports:** the individuation index per finger, and across the block.

**What it tells you:** when a healthy hand presses one finger the others stay
near their resting load. After a stroke that separation breaks down. The index is
the target finger's force over the total force across all fingers. 1.0 means
perfectly isolated, lower means force is spilling onto the neighbours.

This is the measure the earlier Curtin projects could not produce, and it is the
strongest single claim for what this device adds.

**Comparison:** Li and colleagues, via Lew, report enslavement of about 13
percent unimpaired against 25.1 percent stroke-impaired. Enslavement is the
inverse idea, so an individuation index near 0.87 corresponds to unimpaired and
near 0.75 to impaired.

**How to use it:** the finger sitting well below the others is losing the most
force to its neighbours and is the obvious training target.

### Rhythm

**Reports:** accuracy, bias, sd, timing through the song, lag-1 correlation.

**What it tells you:** accuracy is the absolute distance from the beat. Bias is
whether they sit consistently ahead or behind. Entrainment is the interesting
one: correlating each offset with the one before separates genuinely tracking the
tempo from landing near beats by luck. A positive correlation means consecutive
presses drift together, which is what tracking looks like.

**How to use it:** Magee found reasonable support for rhythmic cueing in walking
but very little for the hand, which is the gap this thesis aims at. Even a small
clean result here is worth reporting because the evidence base is so thin.

### Cue modality

**Reports:** speed, accuracy and wrong-finger errors under visual only, vibration
only and both, plus a per-finger breakdown.

**What it tells you:** this is the question the whole project line started from.
Palmer found reaction time differed between an LED-only cue and all cues
together. Vibration-only is the condition that isolates the tactile channel,
because the screen deliberately does not say which finger.

Expect vibration-only to be slower and less accurate. That is the point: the size
of the gap is the result.

**How to use it:** run blocks under at least two settings in the same session so
the comparison is within-participant. Watch whether a tactile-only cue hurts the
weaker fingers more than the strong ones, which the per-finger plot shows.

### Both hands

**Reports:** reaction time and force asymmetry, per finger, both hands.

**What it tells you:** the asymmetry index runs from -1 to +1 and 0 means the
hands performed identically. Cauraugh and Summers argue bilateral training helps
by engaging both hemispheres; the Cochrane review by Coupar found the evidence
mixed. That disagreement is the reason to measure it rather than assume it.

**Important:** the index is signed. In a cohort where some participants are
impaired on the left and some on the right, pooling them cancels the group mean
toward zero and reads as no asymmetry when the asymmetry is large. Record
`affected_side` in `metadata.json` at consent and flip the sign per participant
before pooling.

### Calibration this data was recorded under

**Reports:** the measured zero, resting load and press level per finger for the
calibration each session ran under, the thresholds derived from them, and the
multi-finger force deficit.

**Why it exists:** a press is not an absolute quantity. It depends on where the
pads sit, how the hand rests on them, and how hard that particular patient can
push. Calibration (the Calibrate button on the title screen) measures all of
that in about a minute, and every session records the calibration it used. So
the analysis can state what a press meant on the day rather than assuming the
current config applied.

**What the four measurements give you:**

| Step | Measures | Used for |
| --- | --- | --- |
| Hand off the device | true zero, noise SD | the counts-to-newtons origin, and the noise floor under every threshold |
| Hand resting, no press | resting load per pad | the tare point; thresholds are measured from here, not from zero |
| Each finger, light press | resting-to-press gap | that finger's trigger, set at 40% of its own gap |
| All four together | simultaneous press level | the multi-finger deficit |

**Multi-finger deficit:** the sum of the four single-finger presses against the
simultaneous one, as a fraction lost. Every hand loses some force pressing four
fingers at once rather than one; a larger loss is the deficit reported after
stroke. Measuring it at calibration is stronger than inferring it from gameplay,
because the instruction is explicit and the comparison is within the same minute
on the same hand.

**Two warnings this section raises, and both matter:**

- *Sessions with no calibration recorded.* Anything run before this feature
  existed. Force in counts is still valid, but the newton conversion rests on
  the SingleTact datasheet alone, not on a measurement of this device. Do not
  pool their absolute force values with calibrated sessions.
- *Sessions spanning different calibrations.* A press did not mean the same
  thing in each, so a force change across them is not necessarily a change in
  the patient. Compare within one calibration, or report the change in counts
  relative to that session's own threshold rather than in newtons.

**How to use it in a write-up:** state the calibration date and the per-finger
triggers in the methods, and cite the multi-finger deficit as a baseline
measure alongside the gameplay individuation index. If a participant spans more
than one calibration, say so and analyse the blocks separately.

### Press thresholds in newtons

**Reports:** each finger's trigger converted to newtons, against healthy force
data.

**What it tells you:** whether a weak finger can physically reach the trigger. If
the threshold sits above what a healthy little finger produces, an impaired one
certainly cannot, and every genuine attempt is logged as a miss. That reads as a
patient deficit when it is a threshold problem.

**Comparison:** Demouche measured healthy peak fingertip force on the 2025 button
device across 7 participants: little finger mean 2.66 N, maximum 5.60 N; index
mean 3.11 N, maximum 6.56 N. Different button geometry so not a direct
read-across, but it is the only same-lineage human data.

**How to use it:** check this before every participant session. If a trigger is
above the healthy range there are two fixes, and they are not equivalent.
Running Calibrate with that participant's own hand sets every trigger from
their light press, which is the right answer for a session going ahead today.
Reducing the resting load on the pad in hardware is the better answer, because
a pad carrying 30 counts at rest against 2 on its neighbour is a placement
problem that no threshold can fully undo.

The pinky on this build is the worked example. Its trigger was 6.77 N, above
Demouche's healthy maximum, because the threshold rule added the resting load on
top of a fraction of the press gap when the detector's baseline had already
absorbed that load. Removing the double count brought it to 4.04 N, under the
healthy maximum but still above the healthy mean. Software took it from
impossible to hard; the remaining gap is the pad.

### Participant progress

**Reports:** every session that person has done, in order, with speed, accuracy
and consistency, and the first-to-latest change.

**What it tells you:** a single block says how someone did that day. The trend
across blocks is the outcome measure. This is the view that answers whether the
training is doing anything.

**How to use it:** with the between-participant sd near 65 ms on this device
lineage, treat a change under roughly 100 ms as inside the noise at these sample
sizes. Consistency improving while speed stays flat is still a real change.

### Protocol phase

**Reports:** pretest, main and aftertest per participant.

**What it tells you:** Nakayama and Lee's central claim is that the gain is
specific to the trained sequence rather than general warm-up, and it rests on
comparing the aftertest against the last trained block. Two useful numbers come
out of it: rebound (how much of the gain disappears when the sequence changes,
which is the sequence-specific part) and transfer (aftertest against pretest,
which is the part that generalises).

### Sampling

**Reports:** logged rate, share of frames identical to the previous one,
effective new-data rate.

**What it tells you:** the SingleTact interface board refreshes its output
register at roughly 50 to 120 Hz regardless of how fast it is polled, so a share
of the 200 Hz log is repeated frames. Onset times and rate of force development
are quantised by that.

**How to use it:** state it in the limitations rather than quoting timings to the
millisecond as if they were resolved to the millisecond.

---

## 4. Comparison baselines

Numbers from the past theses in this project line, for putting results in
context.

**Reaction time, same device lineage** (Nakayama and Lee, healthy young adults,
mixed model): baseline about 408 ms. Between-participant sd 64.98 ms, residual sd
113.03 ms. That sets the practical resolution at roughly 100 ms for differences
between conditions at these sample sizes.

**Sequence specificity** (Nakayama and Lee): training reached about -148 ms below
baseline, and the aftertest with a changed sequence rebounded to only -45 ms, a
rebound of about +103 ms. The -45 ms that remained is the transferable part.

**Fingertip force** (Demouche, 2025 button device, 7 participants, 10 N sensors):
index mean 3.11 N, max 6.56 N. Little finger mean 2.66 N, max 5.60 N.

**Sensor quality** (Demouche): SNR 12.64 and 12.05 on working sensors, 6.00 on a
partially damaged one, 0.00 on a dead one. Her accepted pass line for reliable
onset detection was SNR at or above 10. Baseline drift at most 11 counts over
26.5 minutes, under 2.5 percent of the 512-count span.

**Enslavement** (Li et al. via Lew): 13 percent unimpaired against 25.1 percent
stroke-impaired, most prominent in two-finger tasks. Companion peak force 26.5 N
unimpaired against 17.2 N impaired.

**Drift under load** (Palmer): +6 counts total over 75 minutes under a constant
50 g load, rising until about 30 minutes then flat. Sets a precedent for how long
one pre-session calibration holds.

**Reaction time, uncalibrated FSRs** (Palmer, heavily caveated, n of one or two):
0.7 to 1.7 s benchmark, 0.33 to 1.8 s LED only, 0.3 to 1.7 s all cues on.

**Clinical dose** (Lang): about 32 repetitions in a typical therapy session,
against a 200 to 400 target achievable in 30 minutes.

**Usability** (Lee and Dixon): "the device was comfortable to use" 3.2 out of 5,
"felt secure and stable" 2.8 out of 5. If a survey is run, matching these
wordings gives direct comparison.

---

## 5. Limits

Things the analysis cannot show, worth stating rather than leaving for a marker
to notice.

**No patient data yet.** Everything so far is a healthy hand. Every number is a
demonstration that the measure works, not evidence about recovery.

**Sample sizes are small.** At three to seven participants, group statistics are
not meaningful. Report per participant with the individual change, and avoid
p-values that imply more power than exists.

**Force is in sensor counts unless calibrated.** Without a newton calibration
constant the force numbers are internally comparable but not comparable with
anyone else's published forces. The conversion used in the threshold audit
assumes a 45 N part.

**Timing resolution is limited by the sensor board**, not by the 200 Hz log. See
the Sampling section.

**Reaction time from a threshold crossing is biased** by how hard the person
pressed. Use the onset measure where it matters.

**Bilateral asymmetry is unsigned without `affected_side`.** Record it at
consent.

**These cannot be recovered after a session** and have to be captured at consent:
hand length and breadth, affected side, dominant hand, impairment score. The
fields exist in `metadata.json` and are set in `config/user_settings.yaml`.

**These need bench work, not the notebook:** sensor calibration curve, linearity,
repeatability at a fixed load, creep under sustained load, and linear actuator
stall detection. The last is the outstanding patient-safety item.

---

## 6. Writing it up

A results section that follows the evidence rather than the software would run:

1. **What was collected.** Participants, sessions, trials, time on task. Dose
   against Lang's 32 repetitions.
2. **Whether it is trustworthy.** Exclusions with reasons, drift, cue delivery,
   sampling. Do this before any result.
3. **Does the adaptive controller hold the band.** Per finger, not session
   average. This is Thread A.
4. **What the device measures that earlier versions could not.** Individuation,
   impulse, rate of force development, onset RT. This is the contribution.
5. **Rhythm.** Accuracy, bias, entrainment, against how thin the hand-specific
   evidence is.
6. **Cue modality.** The comparison the project line started from.
7. **Change over time.** Within block, and across sessions per participant.
8. **Limits.** Section 5.

Two habits worth keeping. Quote n alongside every number, since a hit rate over
12 trials and one over 400 are not the same claim. And when a result is inside
the noise, say so plainly rather than presenting it as a trend, because the
between-participant sd on this device lineage is already known and a reader can
check.
