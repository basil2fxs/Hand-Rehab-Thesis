# app

The game's code and everything it ships with. To install the game, see the [front page](../README.md). [CONTRIBUTING.md](../CONTRIBUTING.md) goes from a fresh clone to a release.

| Folder | What is in it |
| --- | --- |
| [`finger_rehab/`](finger_rehab) | The code: engine, games, screens, boards, logging |
| [`config/`](config) | Settings, each one commented, and the lab's overlay |
| [`assets/`](assets) | Board firmware, icons, music, speech, word lists, the lab's tones |
| [`arduino/`](arduino) | Source code of the board firmware and the sensor address tool |
| [`docs/`](docs) | Study-day kit, research notes, the lab checklist, screenshots |
| [`scripts/`](scripts) | Tools run by hand: device checks, timing, simulation |
| [`tests/`](tests) | Automated tests: `python -m pytest tests`, about five minutes |
| [`builds/`](builds) | Build scripts for the installers, the firmware and avrdude |
| [`installers/`](installers) | The Windows installer script |
| [`tools/`](tools) | The bundled avrdude, fetched when building |

Run from source: `pip install -r requirements.txt`, then `python main.py`. Add `--config config/eeg_lab.yaml` for the lab's settings.
