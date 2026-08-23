HOW TO RUN
==========

1. Copy this folder onto the lab computer.
2. Plug the EEG trigger box in.
3. Start the EEG recording.
4. Double-click "Finger Rehab.exe".

That is the whole install. No Python, no PsychoPy, nothing else.
Markers go to the trigger box automatically.

IF IT WILL NOT START
The box must be on COM10. Check Device Manager > Ports. If it shows
a different COM number, open eeg_lab.yaml in Notepad and change
eeg.port to match. The game refusing to start without the box is on
purpose: it will not record a session with no markers.

PREFER PSYCHOPY?
Open run_from_source.py in the PsychoPy Runner instead of the exe.
It needs the source code (github.com/basil2fxs/Hand-Rehab-Thesis)
and a one-time package install; the script prints the exact command
for anything missing. Same game, same markers either way.

Marker map and analysis notes: eeg_lab_setup.txt
