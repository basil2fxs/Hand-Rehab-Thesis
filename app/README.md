# app

The game: one program, [`main.py`](main.py), and what it ships with. Users want the [front page](../README.md); this page is for whoever changes the code, and [CONTRIBUTING.md](../CONTRIBUTING.md) is the whole loop from a fresh clone to a release.

```mermaid
flowchart LR
  A["app"]:::root
  A --> M["main.py"]:::top
  A --> F["finger_rehab<br>the package"]:::top
  A --> C["config<br>default.yaml, eeg_lab.yaml"]:::top
  A --> S["assets<br>firmware, icons, music, speech, words, srt"]:::top
  A --> R["arduino<br>board firmware"]:::top
  A --> D["docs<br>study kit, research, images"]:::top
  A --> P["scripts<br>bench and study tools"]:::top
  A --> T["tests<br>3,721 tests, headless"]:::top
  A --> B["builds<br>installer scripts"]:::top
  classDef root fill:#0f172a,color:#fff,stroke:#0f172a
  classDef top fill:#2563eb,color:#fff,stroke:#1d4ed8
```

| Folder | What is in it |
| --- | --- |
| [`finger_rehab/`](finger_rehab) | Engine, games, screens, hardware, logging |
| [`config/`](config) | Every setting, commented; the lab overlay |
| [`assets/`](assets) | Firmware, icons, music, speech, word lists, SRT tones |
| [`arduino/`](arduino) | The board's firmware and the sensor address tool |
| [`docs/`](docs) | Study-day kit, research, the lab checklist, screenshots |
| [`scripts/`](scripts) | Tools run by hand: device checks, latency, simulation |
| [`tests/`](tests) | `python -m pytest tests`, about four minutes |
| [`builds/`](builds) | `build_app.sh`, `build_app.bat`, firmware and avrdude fetch |

Run from source: `pip install -r requirements.txt`, then `python main.py`. The lab overlay: `python main.py --config config/eeg_lab.yaml`.
