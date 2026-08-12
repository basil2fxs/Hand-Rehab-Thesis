FINGER REHAB - EEG LAB PACKAGE
==============================

This folder is the whole install. Nothing else is needed on the lab
computer: no Python, no PsychoPy, no pip.

SETUP (once)
1. Copy this folder anywhere on the lab desktop (Desktop is fine).
2. Plug the EEG trigger box in. Check Device Manager > Ports: if it
   is not COM10, edit eeg_lab.yaml and change eeg.port to match.

EVERY SESSION
1. Start the EEG recording software first.
2. Double-click "EEG Lab.bat".
3. Log in (name and age), pick a game, play. Markers stream to the
   trigger box automatically; the marker map and analysis notes are
   in eeg_lab_setup.txt.

If the game refuses to start with a trigger-port message, that is
deliberate: a lab block recorded without markers is worthless, so it
fails loudly at launch instead of quietly mid-session. Plug the box
in, check the port, try again.
