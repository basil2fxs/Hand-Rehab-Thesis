# finger_rehab

The game as a Python package. `main.py` builds a `GameEngine`, gives it an input source (the boards or the keyboard) and runs its frame loop; everything hangs off the engine.

```mermaid
flowchart LR
  E["game/engine.py<br>the engine"]:::root
  E --> G["game/modes<br>one file per game"]:::top
  E --> U["ui<br>one file per screen"]:::top
  E --> H["hardware<br>boards, presses, calibration, EEG"]:::top
  E --> D["data<br>session folders, CSV loggers, intake"]:::top
  E --> A["audio and analytics"]:::top
  classDef root fill:#0f172a,color:#fff,stroke:#0f172a
  classDef top fill:#2563eb,color:#fff,stroke:#1d4ed8
```

| Package | What it does |
| --- | --- |
| [`game/`](game) | The engine, Play all ([`battery.py`](game/battery.py)), scoring, scheduling |
| [`game/modes/`](game/modes) | One file per game; each file's docstring is that game's research case |
| [`ui/`](ui) | Every screen |
| [`hardware/`](hardware) | Serial boards, press detection, calibration, EEG markers, auto-start, flashing |
| [`data/`](data) | Session folders, the CSV loggers, intake and history |
| [`audio/`](audio) | Cues, music, the rhythm scheduler |
| [`analytics/`](analytics) | The adaptive controller and the in-game metrics |

<p align="center"><img src="../docs/images/login.png" width="32%" alt="Login"> <img src="../docs/images/hub.png" width="32%" alt="The hub"> <img src="../docs/images/results.png" width="32%" alt="Results"><br><sub>A session: log in, pick a game, read the results.</sub></p>
