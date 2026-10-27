# config

Every number the game runs on is a setting here, written down with the reason for its value. Code reads one with `cfg.get("section.key", default)`, and the default in the code matches the YAML, so a trimmed config behaves the same.

| File | What it is |
| --- | --- |
| [`default.yaml`](default.yaml) | Every setting, each one commented. The game reads this first |
| [`eeg_lab.yaml`](eeg_lab.yaml) | The lab's changes over the defaults: markers on, the trigger box, and a Lab session that plays the SRT and leaves out Muscle Memory |
| [`calibration/`](calibration) | Saved hand calibrations, `current_<hand>.json` and a dated `history/` |
| [`pattern_sequence_template.yaml`](pattern_sequence_template.yaml) | A blank sequence file for Muscle Memory, loaded from Settings, Data |

## The order the files are read

`finger_rehab/config.py` lays each file over the one before it, key by key, so a file only needs the keys it changes:

1. `default.yaml`.
2. `latency_profile.yaml`: this computer's measured sound and buzz delays, written by Settings, Setup, Audio delay or `scripts/audio_latency.py --write`. It may only set `latency.*` and the two rhythm offsets.
3. `user_settings.yaml`: whatever the Settings screen saved. Only read when no `--config` file is given.
4. A `--config` file, such as `eeg_lab.yaml`. A frozen exe with an `eeg_lab.yaml` beside it loads that one by itself. When the file is the app's own copy, a trigger box port picked in the game on this computer (`eeg_port.yaml`) goes on top.
5. Command-line flags: `--eeg-port`, `--no-eeg-box`, `--windowed`, `--hand`, `--mode`, `--participant`, `--data-dir`.

An older `user_settings.yaml` that set the cues through `game_cue.mode` and `motor.enabled` is translated onto the four `cue.*` switches at load, so a machine set up under an old build keeps behaving the same.

## Where the per-computer files live

From source they sit here in `app/config/`. An installed app keeps them in a `config/` folder beside itself, or under `~/Finger Rehab Data` when it can't write there; the lab launcher run from `source/` sets `FINGER_REHAB_DATA_ROOT` so they land beside it. The app writes `user_settings.yaml`, `eeg_port.yaml`, `latency_profile.yaml`, `srt_setups.json` (the Reaction card's saved set-ups) and the loaded Muscle Memory sequence, and git ignores all of those: they describe one machine.

<p align="center"><img src="../docs/images/settings.png" width="72%" alt="The Settings screen"></p>

## Changing a setting

- **On one computer:** use the Settings screen, or write the key into `user_settings.yaml` as nested YAML. For example, to turn on the chime after a correct press:

  ```yaml
  cue:
    sound_after: true
  ```

- **For every build:** edit `default.yaml`, say in the comment why the value is what it is, and run the tests. Never put a value meant for one machine here.
- **For the lab:** `eeg_lab.yaml` holds only what the lab needs on top (the trigger box, the markers, the lab sitting). A change to how a game looks, sounds or scores goes in `default.yaml`, so the lab plays exactly the game every other build plays. After editing it, refresh the lab folder with `python3 scripts/check_lab_sync.py --fix`.

## What is in default.yaml

| Section | Covers |
| --- | --- |
| `session` | Where data goes, and the participant details recorded with each block (affected side, dominant hand, impairment score, hand size) |
| `serial`, `autostart` | Boards: baud rate, ports pinned per hand, vendor IDs, plug-in watching |
| `firmware` | The hexes Settings flashes, avrdude, the bootloader speeds to try |
| `eeg` | Markers: on or off, the trigger box port and baud, pulse width, which feedback bytes go out |
| `fsr`, `quick_cal` | The pads and the press detector: newtons per count, smoothing, the press point, the resting-finger rules, the calibration steps |
| `cue`, `motor` | What the player gets before and after a press, and how long a buzz lasts |
| `bilateral`, `game` | The hand, equal practice per finger, the GET READY countdown, Test Mode, the keyboard maps |
| `scoring`, `metrics` | Points and reaction-time bands, wrong and idle press penalties, the force window |
| `adaptive`, `mirror`, `reaction`, `srt`, `pattern`, `chords`, `syllables`, `force_pilot`, `buzz_hunt`, `echo`, `rhythm` | One section per game, under its key |
| `latency`, `audio` | The stimulus delays, volumes, music folders |
| `ui`, `report`, `logging` | Screen size, theme and feedback wording; the per-block report; the log file |
| `protocol` | The timed sessions: each length's games, order, hand and shortened counts |
