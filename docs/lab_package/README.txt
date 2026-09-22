Finger Rehab, EEG lab folder

1. Copy this folder onto the lab PC.
2. Plug the trigger box in first. Start ActiView; the trigger low byte
   reads 255.
3. Open run_in_psychopy.py in PsychoPy Coder and press Run.
4. The byte drops to 0 when the game opens the port. If it stays 255,
   put the box's COM number in eeg_lab.yaml, line "port: COM10".
5. Log in, pick a game. Each block: 200+mode, 20, then 30-38 per
   stimulus (40/41 Patterns, 50/51 Syllables), 100-131 per press,
   220+mode at the end. 240 at login, 241 at exit.
6. Data lands in sessions/ next to the exe: trials.csv, raw.csv (eeg
   rows), metadata.json, events.tsv, markers_codes.csv.
7. Nothing appears: read the Runner's output pane. "needs its trigger
   box" means the COM number is wrong or the cable is out.
