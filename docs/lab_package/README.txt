FINGER REHAB - EEG LAB PACKAGE
==============================

This folder is the whole install. Copy it to the lab computer and run
the exe. Nothing else is needed: no Python, no PsychoPy, no pip.

WHAT IS IN HERE
  Finger Rehab.exe     the game, self-contained (Python ships inside)
  eeg_lab.yaml         lab config: markers on, trigger box required
  EEG Lab.bat          starts the exe; keeps the window open on errors
  eeg_lab_setup.txt    checklist, marker map and analysis notes
  run_from_source.py   optional Python route, see the last section

SETUP (once)
1. Copy this whole folder anywhere on the lab desktop.
2. Plug the EEG trigger box in. Check Device Manager > Ports: if it
   is not COM10, edit eeg_lab.yaml and change eeg.port to match.

EVERY SESSION
1. Start the EEG recording software first.
2. Double-click "Finger Rehab.exe", or "EEG Lab.bat", same thing.
   The exe finds eeg_lab.yaml sitting next to it and starts in lab
   mode on its own; the bat only adds a window that stays open with
   a hint if the launch fails.
3. Log in (name and age), pick a game, play. Markers stream to the
   trigger box automatically; the marker map and analysis notes are
   in eeg_lab_setup.txt.

If the game refuses to start with a trigger-port message, that is
deliberate: a lab block recorded without markers is worthless, so it
fails loudly at launch instead of quietly mid-session. Plug the box
in, check the port, try again.

RUNNING FROM PYTHON OR PSYCHOPY (optional)
The game is pygame, not PsychoPy, so there is no .psyexp to open.
PsychoPy's runner can still run it as a plain Python script:
1. Get the source: git clone
   https://github.com/basil2fxs/Hand-Rehab-Thesis.git
2. In PsychoPy's runner (or any Python 3.10+), open and run
   run_from_source.py from docs/lab_package inside that clone.
3. It checks for the four packages the game needs (pygame-ce,
   pyserial, pyyaml, numpy), then either starts the game in lab mode
   or prints the exact pip command for whatever is missing.
The exe needs none of this. The source route exists for anyone who
wants to read or tweak the task, not as a second install path.
