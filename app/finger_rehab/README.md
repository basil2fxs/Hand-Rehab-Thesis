# finger_rehab

The game as a Python package. `main.py` builds a `GameEngine`, hands it an input source (the boards or the
keyboard) and runs its frame loop; everything else hangs off the engine.

| Package | What it does |
| --- | --- |
| [`game/`](game) | The engine ([`engine.py`](game/engine.py)), Play all ([`battery.py`](game/battery.py)), scoring and scheduling |
| [`game/modes/`](game/modes) | One file per game. Each file's opening docstring is that game's research case |
| [`ui/`](ui) | Every screen. [`screens.py`](ui/screens.py) holds the hub, hand picker and results; the rest are per game |
| [`hardware/`](hardware) | Serial boards, press detection, calibration, EEG markers, auto-start, flashing |
| [`data/`](data) | Session folders, the CSV loggers, intake and history |
| [`audio/`](audio) | Sounds, music and the rhythm beatmaps |
| [`analytics/`](analytics) | The per-session report and its charts |
| [`config.py`](config.py) | Loads `config/default.yaml` and whatever is laid over it |

**Adding a game** touches five places: the mode in `game/modes/`, its starter in `_BLOCK_STARTERS`
([`game/engine.py`](game/engine.py)), its card in `ModeSelectScreen.MODES` ([`ui/screens.py`](ui/screens.py)), a
mode id in [`hardware/eeg_trigger.py`](hardware/eeg_trigger.py), and a row in the main README's game table.
Several tests check these stay in step.

<sub>[Back to app](../README.md)</sub>
