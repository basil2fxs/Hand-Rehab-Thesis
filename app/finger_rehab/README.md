# finger_rehab

The game as a Python package. `main.py` makes a `GameEngine`, hands it the boards (or the keyboard) and runs it.

| Folder | What it does |
| --- | --- |
| [`game/`](game) | The engine, timed sessions ([`battery.py`](game/battery.py)), scoring, scheduling |
| [`game/modes/`](game/modes) | One file per game |
| [`ui/`](ui) | Every screen |
| [`hardware/`](hardware) | Boards, press detection, calibration, EEG markers, auto-start, flashing |
| [`data/`](data) | Session folders, the CSV logs, intake and history |
| [`audio/`](audio) | Cues, music, the rhythm timing |
| [`analytics/`](analytics) | The adaptive controller and the in-game scores |
| [`utils/`](utils) | Small helpers, and the EEG simulator |
