# EEG integration spec: marker layer for the finger-rehab engine

Deliverable of the three-lane research pass (erp.md, preparation_attention.md,
trigger_hardware.md, all in this folder). Precise enough to build from without
re-research. Grounded in code read this session:

- Old program: `Webler EEG past program/SRT_Sequence_learning_Final_v2.py`.
  One marker (30 at flash onset, ~16.7 ms intent, then 0), COM10, DummySerial
  in test mode.
- Our engine: `finger_rehab/` package, `main.py` entry, `config/default.yaml`,
  raw event logging already present in `finger_rehab/data/logger.py`
  (RAW_COLUMNS: iso_ts, t_perf, sample_idx, fsr1-8, hand, event, lane, detail).
- Already in the repo but wired to NOTHING: `finger_rehab/hardware/eeg.py`
  (class EEGMarker) plus `tests/test_eeg.py`. No engine call sites, no
  `eeg:` config block. Its code map comes from "Aiden's prototype" and
  CONFLICTS with the lab convention: it uses 30 = miss and 11-18 = stimulus.
  Welber's pipeline reads 30 = stimulus onset. This spec replaces that map.
  Before deleting the old map, ask Welber and Aiden whether any analysis
  script ever consumed the prototype codes; nothing in this repo does.

Conventions used below. REQUIRED = the thesis analyses in Section 4 fail
without it. NICE = adds an analysis or a convenience but nothing dies.
Lane numbering everywhere: 0-3 = right index, middle, ring, little;
4-7 = left index, middle, ring, little (matches keyboard_map_bilateral).

---

## 1. Marker scheme

Single byte, 1-255. 0 is the reset/idle state and never labels an event.
Code 30 stays a stimulus-onset code, as in the old program, so the lab's
existing habit of "epoch on 30" still finds stimuli.

### Band map

| Band | Meaning |
| --- | --- |
| 0 | reset / idle line (reserved) |
| 20-29 | preparation events |
| 30-39 | stimulus onsets, cue-condition coded |
| 40-49 | stimulus onsets, pattern mode (sequence status coded) |
| 100-131 | response events, correctness coded |
| 140-149 | feedback onsets |
| 200-231 | block boundaries, mode coded |
| 240-249 | session and flow control |

### Preparation band (20-29)

| Code | Event | Enables | Status |
| --- | --- | --- | --- |
| 20 | Block GET READY countdown onset (the 3 s `game.start_countdown_s` card; rhythm welds it to its note-fall lead-in) | segmentation; block-level baseline window | REQUIRED |
| 21 | Foreperiod onset / trial armed (reaction mode: the moment the wait starts after the rest gate; pair it with a visible ready cue, see Section 4 CNV) | CNV epochs (S1); pre-stimulus alpha windows | REQUIRED for reaction EEG blocks |
| 25 | Catch-trial virtual onset (the instant the go signal would have fired on a catch trial) | stimulus-free preparation epochs; false-alarm analysis | REQUIRED for reaction EEG blocks, NICE elsewhere |

### Stimulus band (30-39), all modes except pattern

Cue condition is coded in the byte because visual, auditory and tactile
stimuli produce different ERPs and must never be pooled. The offsets map
straight onto the `cue_flags` switches:

    code = 30 + (1 if cue.sound_before) + (2 if cue.buzz_before)
              + (4 if NOT cue.show_target)

| Code | Condition at stimulus onset | Notes |
| --- | --- | --- |
| 30 | screen highlight only (visual) | anchor code; closest analogue of a plain visual SRT |
| 31 | visual + tone | closest analogue of Welber's audiovisual flash (his 30) |
| 32 | visual + buzzer | |
| 33 | visual + buzzer + tone | the shipping default (buzz_before + sound_before on) |
| 34 | trial onset, nothing names the finger | show_target off, both cues off; logged, will read as misses |
| 35 | tone only | |
| 36 | buzzer only | the tactile-isolation condition |
| 37 | buzzer + tone, no visual | |
| 38 | buzz-as-stimulus (buzz_hunt perception pulses: the buzz IS the stimulus, it bypasses cue.* by design) | keeps perception trials out of the cued-response averages |
| 39 | spare | |

Whole band: REQUIRED. Lane identity is NOT in the byte; it rides in the
raw.csv marker row (Section 3) and in trials.csv. Reason: 8 lanes x 8 cue
conditions does not fit one band, cue condition is what changes ERP
morphology, and unlike the old program every marker is logged with its
code and timestamp so lane recovery by alignment is checkable, not blind.

### Pattern-mode stimulus band (40-49)

Sequence status varies trial to trial and drives the sequence-learning
ERPs (N2b/P3b deviance effects, Eimer et al. 1996; Ferdinand et al. 2008,
see erp.md Section 7), so it must ride the byte. Cue condition is fixed
within a pattern block and is recovered from cue_flags.

| Code | Event | Status |
| --- | --- | --- |
| 40 | stimulus onset, item from the repeating sequence | REQUIRED for pattern EEG blocks |
| 41 | stimulus onset, item from random or probe material | REQUIRED for pattern EEG blocks |
| 42 | spare (explicit deviant, if a future variant inserts one) | NICE |

### Response band (100-131)

Written at response onset with the correctness split Basil asked for.
Correctness is already known in software at the moment of detection, so
the code rides the same byte, no second pass.

| Code | Event | Enables | Status |
| --- | --- | --- | --- |
| 100 + lane (100-107) | correct press, lane = finger pressed | ERN/Pe correct baseline (CRN), response-locked LRP, MRCP, mu/beta ERD | REQUIRED |
| 110 + lane (110-117) | wrong-finger press, lane = finger actually pressed | ERN/Pe error trials | REQUIRED |
| 120 + lane (120-127) | anticipation / false start (press inside the anticipation cut or before the go) | separates guesses from reactions; keeps ERN averages clean | REQUIRED |
| 130 | timeout / miss, written when the response deadline expires | bookkeeping only; a miss has no response onset and is NEVER averaged response-locked | REQUIRED |
| 131 | idle press (press while no trial is active) | artifact bookkeeping | NICE |

Lane IS in the byte here because hand identity (right 0-3 vs left 4-7) is
what the LRP is made of, and per-finger response codes cost nothing.

Continuous-trial rows (force_pilot runs, lighthouse holds) emit NO
response-band marker at all: a run close has no press onset to lock
100 + lane to, and a low-tracking miss is not an expired deadline, so
130 would mislabel it. The same applies to their trial-close feedback
markers; force_pilot's discrete negative-feedback event is the
corridor-exit buzz, which emits 141 from the mode itself (see the
feedback band). Syllables trials lock their response marker to the
child's actual first tap (the mode's rt is not stim-to-press), and a
wrong-tap-count miss where the child DID press promptly emits no
response marker rather than a false 130.

### Feedback band (140-149)

| Code | Event | Enables | Status |
| --- | --- | --- | --- |
| 140 | positive feedback onset (hit chime / tile success flash, the discrete moment it appears) | FRN / reward positivity | NICE (REQUIRED only if the FRN analysis is run) |
| 141 | negative feedback onset (miss thunk, streak break, corridor-exit buzz in force_pilot) | FRN | NICE (same condition) |
| 142 | neutral / informational feedback onset (e.g. reaction mode ms readout) | control condition for FRN | NICE |

Continuous displays (score counters, the force corridor itself) get no
feedback marker; FRN needs discrete time-locked events (Miltner et al.
1997, see erp.md Section 6).

### Block boundaries (200-231)

`code = 200 + mode_id` at block start, `220 + mode_id` at block end.

| mode_id | Mode |
| --- | --- |
| 0 | reaction |
| 1 | classic |
| 2 | adaptive |
| 3 | rhythm |
| 4 | mirror |
| 5 | pattern |
| 6 | chords |
| 7 | syllables |
| 8 | force_pilot |
| 9 | lighthouse |
| 10 | buzz_hunt |
| 11 | syllables_words |

219 = block abandoned (maps the old eeg.py CODE_BLOCK_ABANDONED).
Start/end: REQUIRED for any mode used under EEG (segmentation, per-block
artifact bookkeeping, learning-stage bins). Abandoned: NICE.

### Session and flow (240-249)

| Code | Event | Status |
| --- | --- | --- |
| 240 | session start (engine up, participant confirmed) | REQUIRED |
| 241 | session end | REQUIRED |
| 242 | pause (engine `_pause_now`) | REQUIRED |
| 243 | resume (engine `_resume_now`) | REQUIRED |
| 244 | rest period start (between-round rests in chords, pattern takes, subblock rests, reaction inter-trial rest does NOT count, it is too short) | NICE |
| 245 | rest period end | NICE |

Pause and resume are required because any epoch spanning a pause must be
rejected, and without the codes the EEG record cannot know a pause
happened.

### What each analysis needs from the map (summary)

- P3b, P1/N1: band 30-39 (or 40-41). Nothing else.
- ERN/Pe: 100-127 (and 130 to exclude misses).
- CNV: 21 plus 30-39 plus 25.
- RP/LRP/MRCP: 100-127 with lane coding, bilateral blocks.
- Mu/beta ERD, beta rebound: 100-127 plus enough inter-press quiet.
- Sequence learning: 40/41 plus block boundaries for stage bins.
- FRN: 140/141.
- Alpha trends: block boundaries plus 242-245; no per-trial code needed.

---

## 2. Protocol on the wire

- **Encoding**: `bytes([code])`, one raw byte. NEVER `bytes(chr(code),
  'UTF-8')`: that emits two bytes for any code above 127 and every
  response, feedback, block and session code above sits over 127
  (trigger_hardware.md Section 1, quirk 2). The existing eeg.py already
  does this correctly.
- **Pulse**: write code, hold 10 ms measured by `time.perf_counter()`,
  then write 0. Rationale: the amplifier samples its trigger input at the
  EEG rate, and the vendor rule is a minimum pulse of 2 samples, which is
  8 ms at a 250 Hz worst case; 10 ms clears every plausible lab rate with
  margin (trigger_hardware.md Section 4). Held by wall clock, not frames:
  the old program held by frame counting and actually delivered 1-4 ms at
  60 Hz, the slower monitor giving the shorter pulse (quirk 1). Ask
  Welber the amplifier model and sampling rate and record both in the
  thesis methods; if the rate is 1000 Hz or above, 10 ms is generous and
  can stay.
- **Reset**: byte 0 after every pulse, exactly as the old program and the
  TriggerBox documentation require. Also write 0 in every shutdown path
  (close, crash handler, escape) BEFORE closing the port; the old script
  could leave the lines latched high on escape.
- **Minimum inter-marker interval**: 20 ms nominal (10 high + 10 low).
  Implementation reality: the reset is written from a once-per-frame
  `tick()`, so the actual high time is 10-27 ms at 60 Hz. The enforced
  rule is therefore: a new send waits until the line has been at 0 for at
  least 10 ms. Effective sustained ceiling is about one marker per 2-3
  frames, roughly 20-30 per second. Every event rate in the game sits far
  under that (fastest: adaptive at 140 BPM = 430 ms between stimuli).
  Never mark per-sample force data; discrete events only.
- **Collision rule** (two events in one frame, e.g. an anticipatory press
  landing in the stimulus frame, or feedback resolved in the response
  frame): priority stimulus > response > feedback > boundaries/control.
  The winner goes on the wire; the rest queue in priority order and emit
  as soon as the gap rule allows (so typically 1-2 frames later). Every
  emission logs its ACTUAL wire time (Section 3), so a delayed marker is
  late but never wrong: offline epoching uses the logged wire time and
  the logged intended-event time to correct. If the queue ever exceeds 3,
  drop the lowest-priority entry and log a `dropped` row; at our event
  rates this should never fire, and the validation report must state how
  often it did.
- **Port absent**: `DummyBackend`, the analogue of the old file's
  DummySerial, but better: instead of discarding writes it logs
  (perf_counter, code) rows through the normal logging path, so a
  no-hardware session still produces a checkable marker record. Selection
  logic mirrors the old program's modes: with `eeg.enabled: true` and
  `eeg.require_port: true` (the lab configuration) a missing or unopenable
  port refuses to start the session with a clear on-screen message, same
  as the old experiment mode's fatal exit. With `require_port: false`
  (development, demos, Test Mode) it falls back to the dummy and prints
  which backend is live at startup. Never silently.
- **Write failure mid-session**: log a warning with the failed code and
  timestamp (the existing eeg.py already catches and logs), increment a
  failure counter, and after 3 consecutive failures attempt exactly one
  reopen of the port. If the reopen fails, keep running: the behavioural
  session is still valid, a HUD banner shows "EEG markers lost", every
  subsequent intended marker still goes to the log with a `failed` flag,
  and metadata.json records the session as EEG-degraded with the
  timestamp of first failure. The block is unusable for ERPs from that
  point and the log says exactly which trials are affected. The
  `write_timeout=0.5` already in eeg.py stays: a yanked cable must not
  hang the frame loop.

---

## 3. Timing budget and logging

### Where each write sits

| Event | Write point | Honest jitter (marker vs physical event) |
| --- | --- | --- |
| Visual stimulus (30-41) | immediately after the `pygame.display.flip()` that shows the stimulus, before anything else in the frame | serial path ~1-2 ms; monitor lag constant but unknown until the photodiode run; vsync MUST be verified on the lab machine (free-running fps means flip returns before photons and the marker leads by an unknown amount) |
| Buzzer cue / buzz stimulus (32, 33, 36, 37, 38) | at the moment the `STIM:n` byte goes to the Arduino, same frame as the flip for cued trials | wire ~1 ms; firmware loop plus motor mechanical rise, expect 20-50 ms, ERM motors are slow; MUST be bench-measured (accelerometer on the pad into an amplifier AUX channel) and reported as a constant offset |
| Tone (31, 33, 35, 37) | marker is anchored to the flip, not the tone; the tone leaves the mixer 12-40 ms later (config `rhythm.audio_offset_ms` documents the same problem for scoring) | measure by loopback; treat as a constant offset; if the measured jitter exceeds ~5 ms SD, the tone path needs fixing before auditory-ERP claims |
| Force response (100-127) | in `_feed_detectors`, the same call that detects the threshold crossing | crossing is timestamped on the 200 Hz sample clock (5 ms granularity); detection runs when the frame loop drains the sample queue, so the wire marker trails the physical crossing by 0-17 ms; the correction is logged per event (below), so offline re-alignment to the crossing time leaves residual jitter of about 5 ms sample granularity plus 1-2 ms serial |
| Keyboard response (100-127) | in the frame that polls the key event | 16.7 ms frame granularity plus USB keyboard scan (8-30 ms); keyboard sessions are flagged in the data and are NOT pooled with force sessions for response-locked ERPs (erp.md Section 5) |
| Timeout (130) | the frame the deadline expires | frame granularity; irrelevant, never averaged |
| Boundaries, prep, session | at the state transition | frame granularity; irrelevant to ERPs |

Note the force-response point: the marker inherits one frame of queue
latency, but the SAMPLE timestamp does not. This is why the log row
matters more than the wire byte for response-locked work, and why both
are recorded.

### What gets logged next to each marker

One event row in raw.csv per emission attempt, through the existing
`queue_event` path (columns iso_ts, t_perf, event, lane, detail):

    event  = "eeg"
    lane   = lane if the code carries one, else blank
    detail = "code=<n>;t_event=<perf_counter of the physical event,
              e.g. the force-crossing sample time or the flip return>;
              t_wire=<perf_counter just after serial.write returned>;
              delayed=<0|1>;failed=<0|1>"

Plus, in metadata.json: backend type and port, pulse_ms, gap_ms, code
map version string, vsync check result, failure count. Because raw.csv
samples and the marker rows share the same `t_perf` clock, the
behavioural stream and the EEG stream can be cross-checked offline:
compare inter-marker intervals in the EEG recording's trigger channel
against inter-marker `t_wire` differences in raw.csv; they must agree to
within a couple of milliseconds with no drift, or something is wrong
with the chain.

### Validation the thesis runs and reports

Following the vendor-standard procedure (trigger_hardware.md Section 9):

1. **Photodiode**: sensor over the stimulus tile location, wired to an
   amplifier AUX input, 300 trials. Report mean marker-to-photon offset,
   SD, min, max. The tiles sit centre-screen so the sensor occludes
   nothing critical.
2. **Audio loopback**: audio output (or a microphone at the speaker)
   into a second AUX channel, same 300-trial treatment for the tone.
3. **Buzzer**: accelerometer on a pad (or the motor drive voltage) into
   AUX, same treatment; this yields the motor rise-time constant that
   buzz-locked analyses subtract.
4. **Response side**: solenoid or a finger tap while the force stream and
   marker channel record together; confirms the logged correction
   behaves.
5. **Software cross-check**: the raw.csv versus trigger-channel interval
   comparison above, run over a full pilot session.

Correction policy, per Brainstorm and Brain Products practice: constant
offsets are subtracted in preprocessing (or reported and left if small);
jittered delays are fixed at the source or that modality's ERP claims are
dropped. The thesis reports the offset table (mean, SD, min, max per
modality), the instrument used, the vsync state, the FTDI latency-timer
setting if the box is FTDI-based (set it to 1 ms), and the collision and
failure counts from Section 2.

---

## 4. What the analyses need, mode by mode

Trial counts are artifact-free trials per participant per condition.
"Solid" = well-replicated literature, our hardware and design support it.
"Exploratory" = defensible to attempt, must be labelled exploratory.

| Analysis | Epoch | Minimum trials | Modes that supply it | Standing |
| --- | --- | --- | --- | --- |
| P3b (stimulus categorisation, workload) | -200 to +800/1000 ms around 30-41; baseline -200 to 0 | ~30-50 per condition; it is the largest component and the most forgiving (Polich 2007; Boudewyn et al. 2018: more is better, no magic number) | reaction, classic, adaptive; pattern for learning-stage P3b | Solid |
| P1/N1 (early visual, attention gain) | same epochs | substantially more, they are a few microvolts; treat as manipulation check, not outcome | any visual mode | Solid as a check only |
| ERN/Pe (correct vs wrong press, Basil's question 3) | -500 to +800 ms around 100-127; state the baseline window and keep it fixed | stable from 6-8 errors (Olvet and Hajcak 2009), plan 20+ errors; at 5-10 percent error rates that means 200-400 scored trials, so an EEG session stacks several blocks | error-rich modes: adaptive at speed (wrong-finger presses), rhythm hard, chords (wrong-finger leaks), classic with a tightened window; reaction simple-mode barely errs, do not use it for ERN | Solid, the strongest single claim this project can make; misses (130) are excluded, they have no response onset |
| CNV (preparation, Basil's question 4a) | 21 (S1) to stimulus, 0 to ~3 s; needs 0.05 Hz or DC high-pass, an acquisition-software setting to agree with the lab | visible from 6-12 trials, plan 30+ per condition (2024 Neuromethods chapter) | reaction mode, with TWO additions this spec requires: (a) a visible ready cue at foreperiod onset carrying code 21, (b) a fixed-foreperiod EEG variant (constant 2.5-3.0 s wait, config flag) because the shipped exponential foreperiod keeps the hazard flat ON PURPOSE and a flat hazard suppresses exactly the expectancy ramp the CNV is (preparation_attention.md Section 3); catch trials (25) give stimulus-free preparation epochs | Solid with the fixed-foreperiod variant; exploratory without it |
| RP/MRCP and LRP (motor preparation) | -1500 to +500 ms around response onset | LRP: 100+ per hand per condition, it is ~1 uV (Eimer 1998); MRCP: several tens | LRP strictly needs left-versus-right responding: mirror mode and bilateral pattern/classic blocks only; four fingers of one hand cannot produce an LRP; strict self-initiated BP would need a free-press block that does not currently exist (NICE: a trivial "press when you like, every 5+ s" block) | LRP solid in bilateral blocks with the trial budget; strict BP not available without the new block |
| Mu/beta ERD and post-movement beta rebound | -2 to +3 s around response onset, band power vs pre-event baseline | 30+ (Pfurtscheller and Lopes da Silva 1999) | sparse-press modes only: reaction (~6 s cycle, ideal), chords (quiet-baseline gate, generous ITI), lighthouse holds; fast modes (rhythm, adaptive at speed) smear ERD and rebound together, do not use them for oscillatory measures (2025 Frontiers ISI paper) | Solid in the sparse modes |
| Sequence-learning ERPs (N2b/P3b to random vs sequence items) | stimulus-locked epochs on 40 vs 41, binned by block via 200/220 codes | enough probe items per bin: pattern's random takes supply 64-trial probe blocks | pattern mode, unchanged; the hidden-sequence design is exactly the Eimer et al. (1996) logic | Solid |
| FRN / reward positivity | -200 to +800 ms around 140/141 | 20+ per valence | any mode with discrete hit/miss feedback moments; needs the feedback markers implemented | Solid if implemented; NICE overall |
| Alpha attention index (Basil's question 4b) | continuous, block-averaged band power over posterior sites, baselined at session start, smoothed over tens of seconds | not trial-based; needs block boundaries and pause codes only | any mode; reaction's lapse counter (RT over 500 ms) is the behavioural partner | Partially defensible ONLY as below |

### Attention monitoring: what is and is not defensible

Basil asked whether EEG can tell that a patient is prepared, paying
attention, or using too much concentration. The honest position the
thesis must state:

**Defensible**:
- Preparation, averaged: CNV amplitude in the fixed-foreperiod reaction
  variant, pre-movement MRCP negativity and mu/beta ERD before presses.
  These are the textbook preparation measures and our design supports
  them (Walter et al. 1964; Shibasaki and Hallett 2006; Pfurtscheller
  and Lopes da Silva 1999).
- Disengagement and fatigue, as a within-person block-level TREND:
  posterior alpha rising alongside behavioural lapses (O'Connell et al.
  2009), always paired with the game's own RT and miss stream, always
  baselined to that participant's own session start.
- Effortful versus automatic control, across sessions: frontal midline
  theta falling at equal performance as a skill automatises (Cavanagh
  and Frank 2014). Direction of change within a patient, not a level.

**Not defensible, and the thesis says so explicitly**:
- Any single-trial or real-time "attention score", "concentration
  percentage" or engagement dial. Averaged ERPs are defined over many
  trials; the single-number engagement indices (Pope 1995 ratio,
  theta/beta ratio) have not survived validation (Arns et al. 2013;
  Frontiers in Neuroinformatics 2022), and band ratios are confounded by
  aperiodic 1/f activity. The consumer "attention headband" episode
  (BrainCo) is the cautionary tale.
- "Too much concentration" as a live readout. The nearest real
  literature (T7-Fz coherence, reinvestment) is contested and belongs in
  the thesis only as a labelled exploratory side-analysis, if at all.
- Any between-person threshold on any of these numbers.

---

## 5. Parity design: one engine, lab mode is a config

Requirement: the lab entry point runs the SAME engine as the shipping
game. Every future game change is automatically the lab version. No
copies, no fork, no second script.

### Module layout

```
finger_rehab/hardware/eeg_trigger.py   <- rename/evolve of finger_rehab/hardware/eeg.py
    CODES                        # the Section 1 map as one dict,
                                 # the single source of truth
    CODES_VERSION                # bumped when the map changes; logged
    class TriggerBackend         # open / write_code / close
    class SerialBackend          # bytes([code]), write_timeout kept
    class DummyBackend           # logs every code, discards nothing
    class MarkerWriter           # send(code, lane, t_event), tick(),
                                 # close(); owns pulse, gap, queue,
                                 # collision priority, failure policy
                                 # (Sections 2 and 3); keeps EEGMarker's
                                 # built-in silence: if disabled or the
                                 # port is absent in non-lab mode, every
                                 # call is a no-op the engine never
                                 # checks
```

Engine call sites (all inside `finger_rehab/game/engine.py` and the mode
classes, at the points named in Section 3): session start/end, block
start/end, countdown onset, foreperiod arm, stimulus dispatch, press
detection in `_feed_detectors`, timeout, feedback presentation,
`_pause_now`, `_resume_now`, rest gates. One `markers.tick()` per frame
in `run()`. The old eeg.py map (1, 2, 3, 30 = miss, 11-18, 21-28) is
deleted with the rename; `tests/test_eeg.py` updates to the new map.

### Config block (config/default.yaml)

```yaml
eeg:
  enabled: false          # shipping default: no EEG anywhere
  port: null              # e.g. COM10 on the lab desktop
  baud: 115200            # ignored by virtual COM trigger boxes, kept
                          # for real UARTs
  require_port: false     # true in the lab overlay: refuse to run
                          # without the box (old experiment mode)
  pulse_ms: 10
  gap_ms: 10
  feedback_markers: false # 140-142 are NICE; off until FRN is planned
```

Plus one flag under reaction for the CNV variant:

```yaml
reaction:
  fp_eeg_fixed_s: null    # set (e.g. 2.5) to run the fixed-foreperiod
                          # EEG variant with the visible ready cue;
                          # null keeps the shipped exponential draw
```

### Lab entry point

`config/eeg_lab.yaml`, an overlay on default.yaml (the existing
`--config` mechanism), containing ONLY the lab deltas:

```yaml
eeg:
  enabled: true
  port: COM10
  require_port: true
reaction:
  fp_eeg_fixed_s: 2.5
```

Launcher: `EEG Lab.command` (and a .bat for the lab's Windows desktop)
next to the existing `Finger Rehab.command`, one line of substance:

    python main.py --config config/eeg_lab.yaml

That is the whole lab build. It exercises `main.py`, `Config.load`,
`GameEngine` and every mode exactly as the shipping game does, so drift
is structurally impossible: there is nothing to drift.

### Test Mode mapping

Old program: mode=test meant DummySerial plus windowed display. Ours:
`game.test_mode_enabled` (short blocks for demos) is orthogonal to EEG,
and the dummy fallback is governed by `eeg.require_port`. A developer
run with `eeg.enabled: true` and no box gets the DummyBackend and a
logged marker stream, which is strictly better than the old silent
discard: the marker record can be inspected without an amplifier.

### Contract test (tests/test_eeg_contract.py)

The test that keeps the lab path welded to the game:

1. **Map integrity**: every code in `CODES` is 1-255, unique, inside its
   documented band; 30 is a stimulus-onset code; 0 appears only as
   reset.
2. **Encoding**: `SerialBackend.write_code(220)` puts exactly the single
   byte 0xDC on the fake port (guards any chr/UTF-8 regression, which
   the old program would have hit at code 128).
3. **Protocol**: with a fake clock, a send is followed by reset after
   pulse_ms; a second send inside the gap queues and emits after it; a
   simulated write failure trips the reopen-then-degrade policy and
   flags the log rows.
4. **Engine wiring**: run a scripted short block (fake source, dummy
   backend) and assert the emitted sequence is 240, 200 + mode, 20,
   then per trial a 30-band code matching the configured cue_flags and
   a response code matching the scored outcome, then 220 + mode; assert
   every emission produced a matching raw.csv `eeg` row whose detail
   parses (code, t_event, t_wire present).
5. **Parity**: `config/eeg_lab.yaml` loads over defaults and yields
   eeg.enabled, require_port, a port string; the launcher file contains
   a `main.py --config config/eeg_lab.yaml` invocation and no other
   Python entry; `finger_rehab.game.engine.GameEngine` is the only engine class
   in the repo (no module whose name or contents fork it).
6. **Correctness split**: feeding the engine a wrong-finger press, an
   anticipatory press and a timeout yields 110-band, 120-band and 130
   respectively, never a 100-band code.

### Build order for the implementer

1. Rename and rewrite the map in eeg_trigger.py, port MarkerWriter logic
   onto the existing EEGMarker skeleton (its threading, write_timeout
   and silence-when-absent behaviour are already right), update
   tests/test_eeg.py.
2. Add the `eeg:` config block and wire MarkerWriter construction plus
   `tick()` into GameEngine.
3. Add call sites: session, block, countdown, stimulus, response,
   timeout, pause/resume first (that is every REQUIRED code except the
   reaction ones); then the reaction ready cue, fixed-foreperiod
   variant and catch marker; feedback markers last, behind the flag.
4. Add raw.csv `eeg` event rows at every emission.
5. Add eeg_lab.yaml, the launchers, and the contract test.
6. On the lab machine: verify vsync, set the FTDI latency timer if
   applicable, then run the Section 3 validation and put the numbers in
   the thesis methods.

Open questions for Dr Marinovic, none blocking the build: trigger box
model and amplifier sampling rate (pins the pulse-width margin and the
thesis hardware table); whether any pipeline consumed Aiden's prototype
codes; whether his scripts hard-code "epoch on 30" or take a code list
(if hard-coded, our 30-39 band note in Section 1 covers the mapping).
