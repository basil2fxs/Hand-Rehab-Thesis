Finger Rehab, EEG lab folder

1. Copy this folder onto the lab PC. Plug the trigger box in first.
2. Open run_in_psychopy.py in PsychoPy Coder and press Run.
3. ActiView's trigger low byte reads 255, then 0 when the port opens.
   Wrong COM number: the game opens on a port list; click the box and
   it is saved. Settings, EEG box, changes it later.
4. Same wire as the old SRT task: COM10, 9600 baud, one byte, then 0.
5. Stimulus onset is 30 to 38: 30 light only, as in the old task, +1
   tone, +2 buzz, +4 nothing shown. Every stimulus here is 33.
6. Each block: 200+mode, 20, stimuli, 100-131 per press (Force Pilot
   23/24, Buzz Hunt none), 220+mode. 240 login, 241 exit. Feedback
   140/141/142 (full, open, half ring) in reaction, chords, Force Pilot.
7. Data lands in sessions/: events.tsv names every marker, and
   markers_codes.csv is the full table. Nothing opens: read rehab.log.
