# EEG lab setup

How to run the game as the lab task on the EEG desktop. The lab build
IS the shipping game: `EEG Lab.bat` (Windows) and `EEG Lab.command`
(Mac) run the same `main.py` with `config/eeg_lab.yaml` layered over
the defaults. Nothing is forked, so any game update updates the lab
task with it.

## What lab mode changes

- `eeg.enabled: true`: every stimulus, response, boundary and pause
  writes a single-byte marker to the trigger box (code map in
  `rehab/hardware/eeg_trigger.py`, `CODES`), 10 ms high then reset
  to 0, and one `eeg` event row in the session's raw.csv carrying the
  intended-event time and the actual wire time on the same clock as
  the force samples.
- `eeg.require_port: true`: no trigger box, no session. The app exits
  at launch with a message instead of recording an unmarked block.
- `reaction.fp_eeg_fixed_s: 2.5`: reaction blocks run a constant
  2.5 s wait with a visible "Ready" cue at its onset (the CNV
  variant). Do not pool these RTs with normal reaction blocks.

## Windows desktop checklist (the lab machine)

1. Plug the trigger box in BEFORE launching. Check Device Manager,
   Ports (COM and LPT): the box is COM10 on the lab desktop. If it
   enumerates elsewhere, edit `eeg.port` in `config/eeg_lab.yaml`.
   COM ports 10 and above are fine; pyserial handles the naming.
2. If the box is FTDI-based, set its latency timer to 1 ms: Device
   Manager, the box's COM port, Port Settings, Advanced, Latency
   Timer. The 16 ms default adds a buffering delay to every marker.
3. Double-click `EEG Lab.bat`. If it refuses to start, the message
   says which port failed; that refusal is `require_port` working.
4. Verify vsync ON for the game's window (GPU control panel). With
   vsync off, the flip returns before photons and every visual marker
   leads the screen by an unknown amount.
5. Session data lands in `sessions/` exactly as normal, plus:
   raw.csv gains `eeg` event rows, and metadata.json gains an `eeg`
   section (backend, port, pulse and gap widths, code map version,
   failure counts, degraded flag).

## Marker channel behaviour worth knowing

- Session-level markers (240 session start, 241 session end) bracket
  one login: 240 fires when the participant logs in on the title
  screen, 241 when the session ends on game select (or when the app
  closes with a session still open, whichever comes first; never
  both). They fire outside any block, where no raw.csv is open, so
  they reach the wire and the app log, and each block's own record
  starts at its 200-band boundary marker.
- If the box dies mid-session the app keeps running: after 3 failed
  writes it reopens the port once, and if that fails the HUD shows
  "EEG markers lost", every intended marker is still logged with a
  failed flag, and metadata.json marks the block degraded with the
  first-failure time. The behavioural data stays valid; the block is
  unusable for ERPs from that timestamp.
- Two events in the same frame queue by priority (stimulus first);
  the queued marker goes out 1-2 frames late and its raw.csv row
  records both its intended time and its wire time, so offline
  epoching corrects it.

## Adapting the pipeline: old SRT script versus this game

For Welber. The old task
(`Webler EEG past program/SRT_Sequence_learning_Final_v2.py`) marked
exactly one thing: code 30 at flash onset, then reset 0. Everything
else in a recording had to be reconstructed from the behavioural CSV.
This game keeps that anchor (a stimulus-band code accompanies every
scorable stimulus, so epoch-on-stimulus still sees every trial) and
marks what the old file could not. Side by side:

| Event | Old file | This game |
| --- | --- | --- |
| Stimulus onset | 30 on every flash, written straight after the flip, one code whatever the cues | 30-38, cue condition in the byte: 30 screen highlight only, 31 +tone, 32 +buzzer, 33 +both (the shipping default), 34 uncued, 35 tone only, 36 buzzer only, 37 buzzer+tone, 38 buzz-as-stimulus. Written straight after the flip, same anchor |
| Stimulus onset, pattern blocks | n/a (one condition) | 40 trained-sequence item, 41 random or probe item; cue condition is fixed per block and recoverable from the trial CSV's cue_flags |
| Response / press | never marked | at response onset: 100+lane correct, 110+lane wrong finger (lane = finger actually pressed), 120+lane anticipation or false start, 130 timeout (bookkeeping only, never epoch response-locked on it), 131 idle press |
| Correctness | never marked; recovered offline from the CSV | in the byte, known at detection time |
| Block boundaries | never marked | 200+mode start, 220+mode end, 219 abandoned (reaction=0, classic=1, adaptive=2, rhythm=3, mirror=4, pattern=5, chords=6, syllables=7, force_pilot=8, lighthouse=9, buzz_hunt=10) |
| Session and flow | never marked | 240 session start, 241 session end, 242 pause, 243 resume, 244/245 rest bounds |
| Preparation | never marked | 20 GET READY onset, 21 foreperiod armed (CNV S1), 25 catch-trial virtual onset |
| Reset | 0 after each pulse | same |
| Lane identity of the stimulus | in the CSV only | same choice, on purpose: 8 lanes x 8 cue conditions does not fit one band. The lane rides the raw.csv eeg row logged with every marker, alignable by timestamp instead of blind row order |

Two places we deliberately do NOT copy the old file, both bugs the
research pass documented:

1. Pulse width. The old script intended a two-frame pulse but held it
   by frame counting: the reset went out inside the next drawn frame,
   so the line was actually high for roughly 1-4 ms, shorter on
   slower monitors. At a 250 Hz amplifier the vendor rule is at least
   two samples (8 ms), so those pulses risked being missed entirely.
   Ours holds 10 ms on the wall clock (time.perf_counter), then
   resets; the contract test measures 10 plus or minus 2 ms on a fake
   wire, and a new code waits until the line has been low for 10 ms.
2. Encoding. The old script wrote bytes(chr(code), 'UTF-8'). Fine for
   30, but any code above 127 becomes TWO bytes on the wire, and
   every response, block and session code above sits over 127. Ours
   writes bytes([code]), one raw byte always, and the contract test
   pins that at code 220.

Practical notes for the epoching script:

- Epoch on the band, not the single value 30. A recording made on the
  shipping default cue mix carries 33 at stimulus onset, not 30, and
  the conditions must not be pooled.
- Counts reconcile exactly: stimulus-band markers match trials.csv
  rows one for one, and each inter-stimulus span holds exactly one
  response-band code. The contract test
  (tests/test_eeg_contract.py) runs that reconciliation on real
  headless blocks, keyboard and force input both.
- Response markers can ride the wire up to a frame late: force
  presses are detected when the frame loop drains the 200 Hz sample
  queue, so the byte trails the physical crossing by 0-17 ms. The
  raw.csv eeg row logged with every marker carries t_event (the
  crossing's own sample timestamp) next to t_wire, so response-locked
  epochs should re-align to the logged t_event.
- Two events in one frame queue by priority (stimulus first); the
  delayed marker's row says delayed=1 and both times. Nothing is
  silently dropped without a dropped=1 row.

## Before the first real recording

Run the validation pass and put the numbers in the thesis methods:
photodiode on a stimulus tile, audio loopback for the tone,
accelerometer on a pad for the buzzer rise time, and the raw.csv
versus trigger-channel interval cross-check over a pilot session.
Also confirm with Welber: the amplifier model and sampling rate (pins
the pulse-width margin), and whether any pipeline ever consumed the
old prototype's codes (30 = miss, 11-18 stimulus): recordings made
under that map must not be pooled with recordings made under this
one.
