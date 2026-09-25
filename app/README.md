# app

The game's source: one Python program, [`main.py`](main.py), and everything it ships with. People who only use
the device want the [main README](../README.md); this page is for whoever changes the code.

| Folder | What is in it |
| --- | --- |
| [`finger_rehab/`](finger_rehab) | The Python package: engine, games, screens, hardware, logging |
| [`config/`](config) | `default.yaml`, every setting, and `eeg_lab.yaml`, the lab's changes |
| [`assets/`](assets) | Firmware, icons, music, speech, word lists and the SRT tones |
| [`arduino/`](arduino) | The board's firmware and the sensor address tool |
| [`builds/`](builds) | Build scripts for the Windows and macOS installers |
| [`installers/`](installers) | The Windows installer script (Inno Setup) |
| [`scripts/`](scripts) | Bench checks, timing, simulation and packaging tools |
| [`tests/`](tests) | The test suite |
| [`docs/`](docs) | Lab setup, flashing, study-day papers and the research behind each game |
| [`tools/`](tools) | Where the bundled avrdude lands (fetched, not committed) |

## Run it

```bash
pip install -r requirements.txt
python main.py                                 # the game; the keyboard stands in without a board
python main.py --config config/eeg_lab.yaml    # the EEG lab version
python -m pytest tests                         # about 3,500 tests, about 4 minutes
```

**Start reading at** `main.py`, then [`finger_rehab/game/engine.py`](finger_rehab/game/engine.py): every screen,
block and log goes through the engine.

<sub>[Back to the main README](../README.md)</sub>
