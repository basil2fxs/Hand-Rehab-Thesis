Finger Rehab, EEG lab folder

1. Copy this folder onto the lab PC. Plug the trigger box in first.
2. Open run_in_psychopy.py in PsychoPy Coder and press Run. ActiView's
   trigger byte goes 255 to 0 when the port opens. A port list instead:
   click the EEG marker's port (COM10), then Continue.
3. Log in. The menu names the recording, e.g. P07_2026-09-24.bdf: start
   ActiView with that name in sessions/eeg here, then pick a game.
4. Same wire as the old SRT task: COM10, 9600 baud, one byte, then 0.
5. Stimulus onset 30 to 38: 30 light only, as in the old task, +1 tone,
   +2 buzz, +4 nothing shown. Every stimulus here is 33.
6. Each game: 200+mode, 20, stimuli, 100-131 per press, 220+mode. 240 at
   the first game, 241 at End session. Feedback 140/141/142 (full, open,
   half ring) in reaction, chords, Force Pilot. Codes: markers_codes.csv.
7. Take home the whole sessions/ folder: the games and eeg/ together.
