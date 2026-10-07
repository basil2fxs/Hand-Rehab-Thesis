<h1 align="center">EEG lab folder</h1>
<p align="center">Finger Rehab for the EEG lab: the game, its marker settings and a PsychoPy launcher.<br>Copy it to the lab PC without <code>developer/</code>, or use <code>FingerRehab-EEGLab.zip</code> from the release, which leaves it out.</p>

## Run it

1. Plug the trigger box in first. On a new lab PC, time the screen and the tone against the markers once, with a light sensor and a microphone on the amplifier's spare inputs ([eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt), Validate).
2. Open `run_in_psychopy.py` in PsychoPy Coder and press **Run**. ActiView's trigger byte goes 255 to 0 when the port opens. If a port list shows instead, pick the EEG marker's port (COM10), then **Continue**.
3. Log in. The menu shows the recording's name, for example `P07_2026-09-24.bdf`. Start ActiView under that name, saved in `sessions/eeg`.
4. On the hub, pick **Lab session**, then **Start**. It runs the lab sitting in the code's order: the lab's Reaction task first, in place of both Reaction blocks, and no Muscle Memory. Reaction opens on its setup screen, turned away from the participant: pick the timing group, say it aloud, then **START**. After the recall, ask what they noticed about the order of the lit cards and write the answer down word for word.
5. Take the whole `sessions` folder home. The games and `eeg/` go together.

## Markers

While ActiView records, the game writes a number onto the recording the moment something happens, so the brain signal can be cut around each event afterwards.

<picture><source media="(prefers-color-scheme: dark)" srcset="../app/docs/images/eeg_cheat_sheet_dark.svg"><img alt="EEG markers: 33 when a finger lights up, 100 plus the finger for a right press, 110 plus for a wrong one, 120 plus for too early, 130 for too slow, 140 and 141 for the result, and 20, 200 plus and 220 plus around each game" src="../app/docs/images/eeg_cheat_sheet_light.svg" width="100%"></picture>

Reaction, the lab's own task, marks each flash with 30, the number the lab's script used. Every session also saves `markers_codes.csv`: the full map it was recorded under, with the numbers single games add.

<details><summary>Timing, for the analysis</summary>

A stimulus byte goes out straight after the frame that draws the stimulus; the monitor's delay in lighting the picture and the tone's delay are timed once per lab PC with a light sensor and a microphone, and until then visual epochs carry an unknown fixed offset per monitor. In SRT blocks the response byte goes out at the trial's end, with the press time as `t_event`. A press byte (100 and up) goes out when the finger's smoothed force first passes its trigger, 30% of the way from resting to the light press at calibration. It leaves 0 to one frame (17 ms) after that 200 Hz sample, and that sample reaches the computer in USB bursts about 20 ms apart, so it can itself be up to 20 ms late. `events.tsv` moves every press byte back: `press_offset_ms` to its sample on the board's own clock, `onset_offset_ms` to where the push began on the force trace, a median 50 ms before the 30% point. Lock response-locked epochs to the onset.
</details>

## In this folder

| | |
| --- | --- |
| `run_in_psychopy.py` | Starts the game: the exe on Windows, `source/` anywhere else |
| `Finger Rehab.exe` | The game, from the latest [release](https://github.com/basil2fxs/Hand-Rehab-Thesis/releases/latest) |
| `eeg_lab.yaml` | Lab settings: COM10, 9600 baud, 8 ms pulses and the SRT's response bytes. The games are the same as in every build |
| `source/` | The game's code, for PsychoPy's own Python |
| `sessions/` | Everything recorded here |
| `developer/` | For setting up, not for the lab: an EEG simulator for rehearsing, the PsychoPy download and a new-PC check ([README](developer/README.md)) |

`eeg_lab.yaml` and `source/` are copies of the app, never edited here: `python3 app/scripts/check_lab_sync.py --fix` rebuilds them. Full checklist: [eeg_lab_setup.txt](../app/docs/eeg_lab_setup.txt).
