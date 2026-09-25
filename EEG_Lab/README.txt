Finger Rehab, EEG lab folder

1. Copy this folder onto the lab PC. Plug the trigger box in first.
2. Open run_in_psychopy.py in PsychoPy Coder and press Run. ActiView's
   trigger byte goes 255 to 0 when the port opens. A port list instead:
   click the EEG marker's port (COM10), then Continue.
3. Log in. The menu names the recording, e.g. P07_2026-09-24.bdf: start
   ActiView with that name in sessions/eeg here, then pick a game.
4. Same wire as the old SRT task: COM10, 9600 baud, one byte, then 0.
5. Reaction is the old SRT task, same trials and timing: one 30 at each
   red flash, nothing else per trial. Its setup screen sets the group.
6. Other games: 200+mode, 20, stimuli 30 to 38 (mostly 33), 100-131 per
   press, 220+mode; feedback 140/141/142 in chords and Force Pilot. 240
   at the first game, 241 at End session. Codes: markers_codes.csv.
7. Take home the whole sessions/ folder: the games and eeg/ together.
