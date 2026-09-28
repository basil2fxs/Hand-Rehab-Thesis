<h1 align="center">EEG lab folder</h1>
<p align="center">Finger Rehab for the EEG lab: the game, its marker settings and a PsychoPy launcher.<br>Copy this whole folder onto the lab PC.</p>

## Run it

1. Plug the trigger box in first.
2. Open `run_in_psychopy.py` in PsychoPy Coder and press **Run**. ActiView's trigger byte goes 255 to 0 when the port opens. A port list instead: pick the EEG marker's port (COM10), then **Continue**.
3. Log in. The menu shows the recording's name, for example `P07_2026-09-24.bdf`. Start ActiView under that name, saved in `sessions/eeg`.
4. **Play all** runs the lab sitting in the code's order, with the lab's Reaction task in place of both Reaction blocks. Reaction opens on its setup screen: pick the timing group, then **START**.
5. Take the whole `sessions` folder home. The games and `eeg/` go together.

## Markers

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../app/docs/images/eeg_cheat_sheet_dark.svg">
  <img alt="EEG marker cheat sheet: one trial on the recording, the codes before, at and after each press, around each game, the finger numbers, the lab's Reaction task and the game numbers" src="../app/docs/images/eeg_cheat_sheet_light.svg" width="100%">
</picture>

Every session also saves `markers_codes.csv`: the full map it was recorded under.

## In this folder

| | |
| --- | --- |
| `run_in_psychopy.py` | Starts the game: the exe on Windows, `source/` anywhere else |
| `Finger Rehab.exe` | The game, from the latest [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) |
| `eeg_lab.yaml` | Lab settings: COM10, 9600 baud, 8 ms pulses |
| `source/` | The game's code, for PsychoPy's own Python |
| `sessions/` | Everything recorded here |

`eeg_lab.yaml` and `source/` are copies of the app, never edited here: `python3 app/scripts/check_lab_sync.py --fix` rebuilds them. Full checklist: [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt).
