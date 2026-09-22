Finger Rehab, EEG lab folder

1. Copy this folder onto the lab PC.
2. Plug the trigger box in first. Start ActiView; the trigger low byte
   reads 255.
3. Open run_in_psychopy.py in PsychoPy Coder and press Run.
4. The byte drops to 0 when the game opens the port. If it stays 255,
   put the box's COM number in eeg_lab.yaml, line "port: COM10".
5. Log in, pick a game. Each block: 200+mode, 20, then a 30-51 byte
   per stimulus and 100-131 per press (Force Pilot 23/24 instead, Buzz
   Hunt no press bytes), 220+mode at the end. 240 login, 241 exit.
6. Data lands in sessions/ next to the exe: trials.csv, raw.csv (eeg
   rows), metadata.json, events.tsv, markers_codes.csv, rehab.log.
7. Nothing opens: read sessions/rehab.log. "needs its trigger box"
   means the COM number is wrong or the cable is out.
