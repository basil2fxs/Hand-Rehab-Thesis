# EEG trigger plumbing: serial/parallel event markers for the rehab software

Research notes for porting the marker layer of Dr Marinovic's PsychoPy SRT program
(SRT_Sequence_learning_Final_v2.py) into Basil's pygame rehab engine.
Scope: hardware presentation, protocol, pulse width, reset byte, Windows timing,
PsychoPy vs pygame marker conventions, multimodal onset alignment,
hardware-agnostic design, validation, and thesis reporting.

Sources are cited inline. Everything cited was found in searches this session.
Claims without a citation are direct code analysis of the SRT file or standard
engineering reasoning, and are labelled as such.

---

## 1. What the old program actually does (code analysis, not literature)

File: `Webler EEG past program/SRT_Sequence_learning_Final_v2.py`

- Port: `serial.Serial(port='COM10', timeout=0)` opened once at startup
  (line 126). No baud rate specified, so pyserial's default 9600 is used.
  Irrelevant for a virtual COM port (see Section 2) but worth stating.
- Fallback: a `DummySerial` class with no-op `write`/`close` (lines 121-123),
  used only in test mode. In experiment mode a missing COM10 is fatal.
- Marker codes: `MARKER_FLASH_ONSET = 30`, `MARKER_RESET = 0` (lines 204-205).
  One code for everything. Every flash of every phase sends 30.
- Write call: `eeg_serial.write(bytes(chr(MARKER_FLASH_ONSET), 'UTF-8'))`
  (line 354), placed immediately after the `win.flip()` that displays the red
  square, and after `flash_onset = core.getTime()`.
- Sound: `sounds[finger].play()` is called BEFORE that flip (line 346), so the
  audio pipeline is already running when the marker goes out.
- Reset: `_MARKER_PULSE_SEC = 2.0/120.0` (16.7 ms) converted to frames:
  `MARKER_PULSE_FRAMES = max(1, round(16.7ms * frame_rate))`, giving 1 frame at
  60 Hz and 2 frames at 120 Hz. The reset byte 0 is written inside the
  response loop, after drawing but BEFORE that iteration's `win.flip()`
  (lines 383-386).

### Two implementation quirks worth flagging in the thesis

**Quirk 1: the actual pulse width is not 16.7 ms at 60 Hz.**
Trace the loop at 60 Hz: flip shows the stimulus at vsync t=0, marker write at
t of roughly 0 plus execution time. The first response-loop iteration then queues
draw calls (a few ms at most) and decrements `marker_frames_left` from 1 to 0,
writing the reset byte right there, before waiting for the next vsync. So the
wire-level pulse is roughly 1-4 ms, not one full frame. At 120 Hz the counter
survives one flip, so the reset lands early in the second frame: pulse of
roughly 9-11 ms. The intent (hold two 120 Hz frames) inverts in practice: the
SLOWER monitor gives the SHORTER pulse. Whether 1-4 ms is safe depends on the
amplifier sampling rate (Section 4). A port should hold the pulse by measured
time, not by frame counting.

**Quirk 2: `bytes(chr(code), 'UTF-8')` breaks for codes above 127.**
`chr(30).encode('utf-8')` is the single byte 0x1E, fine. But
`chr(200).encode('utf-8')` is TWO bytes (0xC3 0x88), which an 8-bit trigger
device reads as two bogus triggers, neither of them 200. The old script never
hits this because it only sends 30 and 0, but a port that adds more codes will.
Correct form: `bytes([code])` for 0-255.

**Also inherited:** on escape or crash the script closes the port without
writing a reset first. If the last byte written was nonzero, the trigger lines
stay latched high on some devices. Cheap fix: write 0 in the `finally` block
before `close()`.

---

## 2. How trigger boxes present as COM ports

Legacy EEG rigs used the PC parallel port (LPT): 8 data pins, set the pins to
your code value, amplifier samples them as a digital word. Modern PCs dropped
LPT, so vendors sell USB devices that emulate it.

- **Brain Products TriggerBox**: installs as a "TriggerBox VirtualSerial Port
  (COMx)" in Windows Device Manager. Each byte written to the COM port is
  placed on the 8 output lines (Bit 0 to Bit 7) feeding the amplifier's trigger
  input. Baud rate, parity etc. have no effect on speed because the port is
  virtual; data moves as fast as USB allows. Claimed timing accuracy below
  1 ms. To send consecutive triggers you must re-initialise by sending 0 after
  every trigger (their words). Sources:
  [Brain Products TriggerBox tips](https://pressrelease.brainproducts.com/triggerbox-tips/),
  [TriggerBox virtual serial port programming examples](https://www.brainproducts.com/support-resources/programming-examples-to-use-the-triggerbox-as-a-virtual-serial-port/).
  The newer TriggerBox 2 keeps the same idea (millisecond triggers without a
  parallel port): [TriggerBox 2 announcement](https://pressrelease.brainproducts.com/triggerbox2/).
- **Cedrus StimTracker / c-pod / m-pod**: a hybrid. It accepts USB event codes
  like a trigger box, but also has its own onset detectors: light sensors on
  the screen, microphone level threshold for audio, response pad lines. It then
  forwards hardware-timed markers to the EEG recorder, so software latency
  drops out of the loop for the detected modalities. Works with the major
  amplifier brands including Brain Products. Sources:
  [StimTracker overview](https://cedrus.com/stimtracker/index.htm),
  [audio onset marking](https://cedrus.com/support/stimtracker/tn1907_onset_audio.htm),
  [visual onset marking](https://cedrus.com/support/stimtracker/tn1908_onset_visual.htm),
  [StimTracker with Brain Products](https://cedrus.com/stimtracker/brain-products.htm).
- **USB-LPT adapters and driver-level LPT**: PsychoPy's parallel port support
  needs the inpout32/inpoutx64 driver DLLs on Windows, and its Builder
  component also targets LabJack U3 and USB2TTL8 devices. Plain USB-to-LPT
  printer adapters are a known source of grief; the PsychoPy forums are full of
  failed trigger threads about them. Sources:
  [PsychoPy parallel port instructions](https://psychopy.org/hardware/parallelPortInstr.html),
  [Parallel Out component](https://psychopy.org/builder/components/ParallelOutComponent.html),
  [example forum thread](https://discourse.psychopy.org/t/sending-triggers-using-usb-to-parallel-port/45182).

Practical read on the lab desktop: COM10 is a high port number, typical of a
USB virtual COM device, consistent with a TriggerBox or similar. The port name
is all our code needs; the device identity only matters for documenting claimed
accuracy in the thesis. Worth asking Dr Marinovic which box it is.

---

## 3. Why the reset byte matters

Trigger lines are LEVEL-based, not edge-based. Writing 30 sets the 8-bit word
to 00011110 and it STAYS there. Consequences if you never reset:

1. A second trigger with the same value produces no change on the lines, so the
   amplifier records nothing. This is exactly why Brain Products say to send 0
   after every trigger ([TriggerBox tips](https://pressrelease.brainproducts.com/triggerbox-tips/)).
2. Some recording software logs the trigger word continuously; a stuck value
   turns one event into a plateau and confuses onset extraction.
3. Overlapping codes: if code A is still high when code B is written, the
   amplifier sees a single transition from A to B, and depending on bit
   patterns can log a value that is neither.

So the protocol is: write code, hold long enough to be sampled, write 0, hold
0 long enough to be sampled, only then allow the next code.

---

## 4. Pulse width conventions

The amplifier samples its trigger input at the EEG sampling rate. A pulse
shorter than one sample interval can fall entirely between samples and vanish.
Brain Products' recommendation: minimum pulse width of 2 x (1/sampling rate).
Their worked example: at 5000 Hz sampling the pulse must be at least 0.4 ms.
Source: [Brain Products, trigger signal properties](https://www.brainproducts.com/support-resources/how-to-assess-trigger-signal-properties-and-adjust-settings-correctly-in-mr-experiments/)
(written for MR setups but the sampling argument is general).

Applied to typical lab rates:

| EEG sampling rate | Minimum safe pulse (2 samples) |
|---|---|
| 5000 Hz | 0.4 ms |
| 1000 Hz | 2 ms |
| 500 Hz | 4 ms |
| 250 Hz | 8 ms |

The same logic applies to the 0 between two triggers: the low period also needs
to span at least one sample or the two pulses merge.

Convention seen across vendor docs and the old script's intent: hold around
5-20 ms. The old script aims for 16.7 ms which is comfortably safe at any
plausible rate; its actual 1-4 ms at 60 Hz (Section 1, quirk 1) is unsafe at
250 Hz and marginal at 500 Hz once USB write-timing variability is added.
Recommendation for the port: default pulse of 10 ms held by wall-clock time,
configurable, and a minimum 10 ms low gap enforced before the next marker.
With minimum inter-stimulus intervals of 250 ms in the SRT design, and our
game's event spacing, a 20 ms marker cycle costs nothing.

Also fix the ceiling on marker rate in the design: 10 ms high + 10 ms low means
at most about 50 markers/s. Our force loop runs at 200 Hz; do NOT try to mark
per-sample force events over this channel. Mark discrete events only.

---

## 5. Marker timing precision on Windows

Three layers of delay between `serial.write()` returning and voltage changing
on the amplifier's trigger pins:

1. **pyserial/OS buffering**: `write()` copies to the driver buffer and
   returns. Sub-millisecond on an idle system.
2. **USB scheduling**: full-speed USB serves bulk transfers in 1 ms frames, so
   the byte leaves the host within roughly 1 ms. The FTDI application note
   on data throughput and latency covers how transfers are packetised and
   scheduled: [FTDI AN232B-04](https://www.ftdichip.com/Documents/AppNotes/AN232B-04_DataLatencyFlow.pdf).
3. **Device to pins**: trigger boxes convert the byte to line levels in
   microseconds; Brain Products claim below 1 ms end-to-end for the TriggerBox
   ([TriggerBox tips](https://pressrelease.brainproducts.com/triggerbox-tips/)).

Net effect: expect roughly 1-2 ms latency with sub-millisecond jitter on a good
device. That matches the lab folklore number in the task brief.

**The FTDI 16 ms latency timer trap**: FTDI USB-serial chips default to a
16 ms "latency timer". This timer governs how long the chip buffers data
travelling device-to-host before pushing a partial packet up. It is notorious
in EEG circles because it adds chunky delays and jitter to INBOUND streams
(OpenBCI's docs tell users to set it to 1 ms). For our OUTBOUND trigger bytes
the harm is smaller, but if the trigger device is FTDI-based, set the latency
timer to 1 ms anyway: Device Manager > USB Serial Port > Properties >
Port Settings > Advanced > Latency Timer. Sources:
[OpenBCI FTDI fix for Windows](https://docs.openbci.com/Troubleshooting/FTDI_Fix_Windows/),
[FTDI AN232B-04](https://www.ftdichip.com/Documents/AppNotes/AN232B-04_DataLatencyFlow.pdf).

**Windows scheduling**: the default timer granularity makes `time.sleep()`
unreliable below about 15 ms, so never sleep to time the pulse; check elapsed
`time.perf_counter()` inside the existing 60 Hz loop, or run the reset from the
next loop iterations as the old script does, but gated by time, not frames.

**Context on software stacks**: the timing mega-study (Bridges, Pitiot,
MacAskill and Peirce, 2020, PeerJ 8:e9414) measured visual, audio and response
timing across experiment generators. On Windows, Psychtoolbox, PsychoPy,
Presentation and E-Prime all reached mean precision under 1 ms lab-based. The
lesson for us is that the platform is capable of it, but only when the code
synchronises to vsync and writes markers at the right moment. Sources:
[PeerJ article](https://peerj.com/articles/9414/),
[PubMed record](https://pubmed.ncbi.nlm.nih.gov/33005482/).

---

## 6. PsychoPy convention vs our pygame loop

**PsychoPy convention**: schedule the write on the flip. The documented pattern
is `win.callOnFlip(port.write, str.encode('1'))` so the byte goes out the
moment the buffer swap happens, then reset to 0 after the pulse. Source:
[PsychoPy serial port instructions](https://psychopy.org/hardware/serialPortInstr.html),
plus forum threads showing the same pattern for the TriggerBox
([example](https://discourse.psychopy.org/t/sending-triggers-to-eeg-via-brain-vision-triggerbox-by-using-the-serial-port-component/30178)).

The old script does not use `callOnFlip`; it writes right after `flip()`
returns. Functionally near-identical when nothing sits between the flip and the
write, which is true in that code (one `core.getTime()` call between them).

**What our pygame loop can do**: pygame has no callOnFlip, but it does not need
one. With vsync enabled (`pygame.display.set_mode(..., vsync=1)` or a Windows
driver that forces it), `pygame.display.flip()` blocks until the swap, so:

```python
pygame.display.flip()                  # returns at (or near) vsync
t0 = time.perf_counter()
trigger.send(code)                     # serial write, ~1 ms to pins
```

is the same convention with the same guarantees. Two cautions:

1. Verify vsync is actually on. Without it, flip returns immediately and the
   marker leads the photons by an unknown amount. Test: measure frame
   intervals; free-running several hundred fps means vsync is off.
2. pygame's audio history is poor: early measurements had pygame sound
   latencies near 100 ms, far worse than PsychoPy's audio backends
  ([PsychoPy users list comparison](https://groups.google.com/g/psychopy-users/c/NWnf4lXpFSg),
  and the mega-study's audio results back the general point:
  [Bridges et al. 2020](https://peerj.com/articles/9414/)).
  Whatever audio path the rehab software uses must be measured, not assumed
  (Section 7).

Keyboard and force-sensor responses: pygame polls keys at the 60 Hz frame
loop, so a response marker written on detection carries up to 16.7 ms of
detection latency; the 200 Hz force loop carries up to 5 ms. That is fine as
long as the same timestamps are logged to CSV and the thesis states the
detection granularity. For response-locked analysis, see Section 9.

---

## 7. Aligning audio, visual and tactile onsets with the marker

The marker marks ONE instant. Every modality reaches the participant at its own
delay from that instant:

- **Visual**: flip return tracks the video signal, but the panel adds input lag
  and response time. Photons can trail the marker by a few ms up to tens of ms
  depending on the monitor; the Black Box ToolKit people specifically warn that
  event markers can be sent before the image appears on TFT monitors, and that
  the size of the error is only knowable empirically
  ([BBTK on event marking errors](https://www.blackboxtoolkit.com/otherequipment.html)).
- **Audio**: the request passes through OS mixers, driver buffers and the DAC.
  The Brainstorm stimulus-delays tutorial measured 11.5-12.8 ms of jittered
  sound-production delay in their rig, plus about 5 ms constant transmission
  delay through their tube system
  ([Brainstorm StimDelays tutorial](https://neuroimage.usc.edu/brainstorm/Tutorials/StimDelays)).
  PsychoPy addressed this class of problem by recommending the Psychtoolbox
  audio backend with latency mode 3 for near-hardware latency
  ([PsychoPy audio docs](https://psychopy.org/general/audio.html)).
- **Tactile (our buzzers)**: driver electronics plus mechanical rise time of
  the ERM/LRA motor. Coin ERMs take tens of ms to spin up; LRAs less. Must be
  measured with an accelerometer or by recording the drive voltage; no
  literature number substitutes for a bench measurement of our own hardware.

**What the old file hides**: it calls `sounds[finger].play()` (sounddevice
backend, latency mode 3, 48 kHz) BEFORE the flip, then writes the marker after
the flip. So the marker is anchored to the video frame, and the true audio
onset sits somewhere unmeasured relative to it: the head start of one
pre-flip code path minus the full audio output latency of the sounddevice
stack on that Realtek device. Audible onset could plausibly land anywhere from
a few ms before to 10-20 ms after the marker, and with sounddevice rather than
PTB the jitter is also unquantified. Since the study analyses stimulus-locked
ERPs to an audiovisual event, that offset is baked into every average. This is
exactly the "Delay #1" category Brainstorm documents as jittered and worth
correcting ([StimDelays](https://neuroimage.usc.edu/brainstorm/Tutorials/StimDelays)).

**Design rule for the port**: one marker per event, anchored to the modality
the analysis cares about (for visual ERPs: the flip). Fixed relationships
between modalities are then measured once at validation and reported as
constant offsets. If a modality's onset cannot be made constant relative to
the marker (bad audio stack), either fix the stack or give that modality its
own marker code written at its own best-known onset estimate.

---

## 8. Hardware-agnostic design

The requirement: identical game code drives a Brain Products TriggerBox, a
Cedrus StimTracker/c-pod, a raw LPT port, or nothing at all. All four reduce to
"present an 8-bit code, then clear it", so one small interface covers them:

```python
class TriggerBackend:
    def open(self): ...
    def write_code(self, code: int): ...   # 0..255; 0 clears the lines
    def close(self): ...

class SerialBackend(TriggerBackend):
    # TriggerBox virtual COM, StimTracker USB event codes, any COM device
    def __init__(self, port='COM10'):
        self.port_name = port
    def open(self):
        self.ser = serial.Serial(self.port_name, timeout=0)
    def write_code(self, code):
        self.ser.write(bytes([code]))      # NOT bytes(chr(code),'UTF-8')
    def close(self):
        self.ser.write(bytes([0])); self.ser.close()

class ParallelBackend(TriggerBackend):
    # LPT via inpoutx64 (psychopy.parallel or a thin ctypes wrapper)
    def __init__(self, address=0x0378): ...
    def write_code(self, code): self.port.setData(code)

class DummyBackend(TriggerBackend):
    # logs (perf_counter_ns, code) to CSV; development and demo mode
```

On top, one manager owns the protocol so no game code ever touches pulse
logic:

```python
class MarkerWriter:
    def __init__(self, backend, pulse_ms=10, min_gap_ms=10): ...
    def send(self, code):
        # refuses if a pulse or gap is still in progress (logs the collision)
        # writes code, records t_send = perf_counter()
    def update(self):
        # called once per game-loop iteration:
        # if pulse elapsed -> write 0; if gap elapsed -> ready for next send
    def close(self):
        # write 0, then backend.close()
```

Design points, each traceable to a finding above:

1. `bytes([code])`, never chr/UTF-8 (Section 1 quirk 2).
2. Pulse held by `perf_counter` time, not frames (Section 1 quirk 1); default
   10 ms high, 10 ms low satisfies any rate down to 250 Hz twice over
   (Section 4).
3. `send()` immediately after `pygame.display.flip()` for visual events,
   matching the PsychoPy callOnFlip convention (Section 6).
4. Every `send` and reset is also logged with a `perf_counter_ns` timestamp to
   the session CSV, so software timestamps and EEG marker channel can be
   cross-checked afterwards.
5. Backend chosen by config/CLI (`--trigger serial:COM10`, `--trigger lpt:0x378`,
   `--trigger none`), mirroring the old script's test-mode DummySerial but
   without silently defaulting: startup prints which backend is live, and
   experiment mode refuses to run on the dummy unless explicitly forced.
6. Optional future backend: LSL marker outlet. Useful for multimodal sync, but
   plain string markers carry roughly 10x the jitter of hardware triggers
   unless dejittered properly, so it complements rather than replaces the
   serial line ([Brain Products LSL tips](https://www.brainproducts.com/support-resources/tips-and-tricks-for-lsl/),
   [LSL reference paper, Imaging Neuroscience 2025](https://direct.mit.edu/imag/article/doi/10.1162/IMAG.a.136/132678/The-lab-streaming-layer-for-synchronized)).

A Cedrus StimTracker rig can additionally hang its own photodiode and
microphone on the screen and speaker, generating hardware-timed onset markers
independent of our code ([Cedrus docs](https://cedrus.com/stimtracker/index.htm)).
That is a validation asset, not a reason to change the game code.

---

## 9. Validating marker timing: photodiode and loopback

The principle across all vendor guidance: never trust software timestamps;
record the physical stimulus into the EEG system itself and measure the offset
to the marker channel.

- **Photodiode method** (visual): tape a photo sensor over the location where
  the target square flashes, wire it to an amplifier AUX input, run a few
  hundred trials, then compute the delay between photo-signal onset and the
  hardware trigger, plus its trial-to-trial spread. Brain Products' worked
  example uses 300 trials and reports mean delay and jitter per marker path
  ([Brain Products timing verification](https://pressrelease.brainproducts.com/timing-verification/)).
  The old SRT design helps here: the squares sit near screen centre, so a
  sensor on the flash location does not occlude anything the participant needs.
- **Audio loopback** (auditory): feed the audio output (or a mic next to the
  buzzer/speaker) into another AUX/bipolar input and measure marker-to-sound
  onset the same way. Brainstorm's tutorial demonstrates the analysis and shows
  jittered audio delays being replaced by detected analog onsets before ERP
  work ([StimDelays](https://neuroimage.usc.edu/brainstorm/Tutorials/StimDelays)).
- **Tactile**: same idea with the buzzer drive signal or a small accelerometer
  on the buzzer housing into an AUX channel.
- **Dedicated instrument**: the Black Box ToolKit packages opto-detectors,
  microphones and TTL I/O for exactly this audit, and its docs give the
  clearest statement of why (markers sent before photons on TFTs; millisecond
  event-marking errors in computer-based setups)
  ([BBTK worked example](http://www.blackboxtoolkit.com/bbtkv3_worked_example.html),
  [BBTK on event marking](https://www.blackboxtoolkit.com/otherequipment.html)).
- A cheap variant of the CLET idea (photodiode-based trigger latency
  computation, published for VR rigs) applies unchanged to a desktop monitor
  ([CLET, PMC 2023](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10546026/)).

Correction policy, following Brainstorm and Brain Products: constant offsets
can be corrected in preprocessing (or reported and left, if small and
jitter-free); jittered delays must be eliminated at the source or replaced by
measured analog onsets ([StimDelays](https://neuroimage.usc.edu/brainstorm/Tutorials/StimDelays),
[timing verification](https://pressrelease.brainproducts.com/timing-verification/)).

For response-locked ERPs the same discipline applies on the input side: the
response marker inherits the 60 Hz keyboard poll or 200 Hz force-sample
granularity (Section 6), so report that granularity, and where possible
validate with a solenoid/relay tapping a sensor while its drive signal is
recorded on AUX.

---

## 10. What the thesis should report about marker accuracy

Minimum reporting set, assembled from the practices above:

1. **Hardware chain**: amplifier model and sampling rate, trigger device model
   (and that it presents as a virtual COM port), cable path, monitor model,
   refresh rate, audio device and backend, buzzer type.
2. **Protocol**: marker code table (event -> code), pulse width, reset-to-zero
   behaviour, minimum inter-marker gap, and the code path (write immediately
   after flip; vsync confirmed on).
3. **Driver settings**: FTDI latency timer value if applicable; vsync state;
   any Windows power/USB-suspend settings changed.
4. **Validation numbers, per modality**: N validation trials (a few hundred,
   matching the Brain Products example of 300), mean marker-to-physical-onset
   offset, SD (jitter), min/max. State the measurement instrument
   (photodiode/mic/accelerometer into AUX, or BBTK).
5. **Correction applied**: which constant offsets were subtracted in
   preprocessing, which were left and why (jitter-free and small), and the
   residual uncertainty carried into ERP latency claims.
6. **Response side**: detection granularity for keyboard (frame-locked,
   16.7 ms at 60 Hz) and force sensors (5 ms at 200 Hz), and how
   response-locked epochs were built.
7. **Failure handling**: what happens on marker collision (event during an
   unfinished pulse) and how often it occurred; dummy-mode safeguards.

A one-paragraph summary plus one table of offsets and jitters per modality
covers items 4-5 and is the difference between "we sent triggers" and a
defensible ERP methods section.

---

## Source list

- Brain Products, TriggerBox marker triggering via USB: https://pressrelease.brainproducts.com/triggerbox-tips/
- Brain Products, TriggerBox virtual serial port programming examples: https://www.brainproducts.com/support-resources/programming-examples-to-use-the-triggerbox-as-a-virtual-serial-port/
- Brain Products, TriggerBox 2: https://pressrelease.brainproducts.com/triggerbox2/
- Brain Products, trigger signal properties and pulse width (2 x 1/sampling rate): https://www.brainproducts.com/support-resources/how-to-assess-trigger-signal-properties-and-adjust-settings-correctly-in-mr-experiments/
- Brain Products, timing verification with photo sensor (300-trial example): https://pressrelease.brainproducts.com/timing-verification/
- Brain Products, LSL tips and tricks: https://www.brainproducts.com/support-resources/tips-and-tricks-for-lsl/
- Bridges D, Pitiot A, MacAskill MR, Peirce JW (2020). The timing mega-study. PeerJ 8:e9414: https://peerj.com/articles/9414/
- PsychoPy, sending triggers via a serial port (callOnFlip pattern): https://psychopy.org/hardware/serialPortInstr.html
- PsychoPy, parallel port instructions (inpout32/inpoutx64): https://psychopy.org/hardware/parallelPortInstr.html
- PsychoPy, Parallel Out component (LabJack U3, USB2TTL8): https://psychopy.org/builder/components/ParallelOutComponent.html
- PsychoPy, audio latency and backends (PTB, latency mode): https://psychopy.org/general/audio.html
- PsychoPy forum, TriggerBox via serial port component: https://discourse.psychopy.org/t/sending-triggers-to-eeg-via-brain-vision-triggerbox-by-using-the-serial-port-component/30178
- PsychoPy forum, USB-to-parallel trigger issues: https://discourse.psychopy.org/t/sending-triggers-using-usb-to-parallel-port/45182
- PsychoPy users list, pygame vs pyo sound delay: https://groups.google.com/g/psychopy-users/c/NWnf4lXpFSg
- FTDI AN232B-04, data throughput, latency and handshaking: https://www.ftdichip.com/Documents/AppNotes/AN232B-04_DataLatencyFlow.pdf
- OpenBCI, FTDI latency timer fix on Windows (16 ms default to 1 ms): https://docs.openbci.com/Troubleshooting/FTDI_Fix_Windows/
- Cedrus StimTracker overview: https://cedrus.com/stimtracker/index.htm
- Cedrus, marking auditory onsets: https://cedrus.com/support/stimtracker/tn1907_onset_audio.htm
- Cedrus, marking visual onsets: https://cedrus.com/support/stimtracker/tn1908_onset_visual.htm
- Cedrus, StimTracker with Brain Products amplifiers: https://cedrus.com/stimtracker/brain-products.htm
- Brainstorm tutorial, stimulus presentation delays: https://neuroimage.usc.edu/brainstorm/Tutorials/StimDelays
- Black Box ToolKit, event marking errors: https://www.blackboxtoolkit.com/otherequipment.html
- Black Box ToolKit v3 worked example: http://www.blackboxtoolkit.com/bbtkv3_worked_example.html
- CLET, photodiode-based trigger latency computation (PMC, 2023): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10546026/
- LSL reference paper, Imaging Neuroscience (2025): https://direct.mit.edu/imag/article/doi/10.1162/IMAG.a.136/132678/The-lab-streaming-layer-for-synchronized

Flagged, not cited: no source was found this session giving a measured
end-to-end latency distribution for pyserial writes on Windows 10/11
specifically; the 1-2 ms figure is assembled from USB frame scheduling plus
vendor accuracy claims and should be verified on the lab machine with the
photodiode method before being stated as fact in the thesis.
