HOW TO RUN
==========

1. Copy this folder onto the lab computer.
2. Plug the NeuroSpec trigger box (orange MMBT-S) in. Its switch
   beside the USB socket should read P.
3. Start the EEG recording in ActiView. The trigger low byte reads
   255 until the game opens the box.
4. Double-click "Finger Rehab.exe". The trigger value drops to 0:
   the box is alive.

That is the whole install. No Python, no PsychoPy, nothing else.
Markers go to the trigger box automatically.

IF IT WILL NOT START
The box must be on the COM port named in eeg_lab.yaml (COM10 on the
lab desktop). Check Device Manager > Ports (COM & LPT); unplug the
box and see which entry vanishes. If it is a different COM number,
open eeg_lab.yaml in Notepad and change eeg.port to match. Do not
change anything in Device Manager, and never set 1200 baud: that
resets the box. The game refusing to start without the box is on
purpose: it will not record a session with no markers.

WHAT YOU SEE IN ACTIVIEW
255 before launch, 0 once the game opens the port, 240 at login,
200+mode / 220+mode around each block, 30-38 per stimulus (22 then
31 per rhythm beat), 100-131 per press, 241 at the end. Each code is
an 8 ms pulse (16 samples at 2048 Hz) back to 0. The box LED only
flashes on odd codes.

SHIFTING EPOCHS FROM THE BYTE TO THE STIMULUS
The byte marks when the software acted; the stimulus reaches the
patient a little later. metadata.json in each session folder records
the constants (eeg.latency) and the offset per event class
(eeg.marker_offsets_ms). Shipped values, positive = stimulus after
the byte:
  screen (30, 31, 34, 35, 40, 41)      +20 ms   latency.visual_ms
  tone (any byte with the tone bit)     +12 ms   latency.tone_ms
  buzz with the beat (32, 33, 36, 37)   +45 ms   latency.buzzer_ms,
                                                 minus up to one frame
  22 rhythm leading buzz, 38 buzz hunt  +45 ms   latency.buzzer_ms
  presses (100-131)                      0       use the row's t_event
These are datasheet estimates until latency.measured is true in the
metadata; the procedure to measure them is in eeg_lab_setup.txt.

PREFER PSYCHOPY?
Open run_from_source.py in the PsychoPy Runner instead of the exe.
It needs the source code (github.com/basil2fxs/Hand-Rehab-Thesis)
and a one-time package install; the script prints the exact command
for anything missing. Same game, same markers either way.

Marker map, the trigger chain, the checklist and the latency
validation: eeg_lab_setup.txt
