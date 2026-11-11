# finger_rehab

The game as a Python package. `main.py` loads the config, finds the boards (or falls back to the keyboard), makes a `GameEngine` and runs it. Everything else is run by the engine.

| Folder | What it does | Start with |
| --- | --- | --- |
| [`game/`](game) | The engine, timed sessions, scoring, who gets cued next | `engine.py`, `battery.py`, `scoring.py` |
| [`game/modes/`](game/modes) | One file per game, and how to add one | its [README](game/modes/README.md) |
| [`ui/`](ui) | Every screen, the theme and the widgets | its [README](ui/README.md) |
| [`hardware/`](hardware) | Boards, plug order, the press detector, calibration, EEG markers, auto-start, flashing | `discovery.py`, `fsr_detector.py`, `calibration_profile.py` |
| [`data/`](data) | Session folders, the CSV logs, study codes | `logger.py`, `session.py`, `intake.py` |
| [`audio/`](audio) | Cue sounds, music, rhythm charts, spoken instructions, the delay measurement | `engine.py`, `beatmap.py`, `latency_measure.py` |
| [`analytics/`](analytics) | The adaptive controller, the per-block summary and report, force-signal tools | `adaptive.py`, `metrics.py`, `report.py` |
| [`utils/`](utils) | Logging set-up and the EEG simulator | `eeg_simulator.py` |

`config.py` loads the YAML layers (see [config](../config)) and decides where writable files go.

## One session, start to finish

1. `main.py` reads the flags and `Config.load()` stacks the YAML files. A frozen exe with `eeg_lab.yaml` beside it loads that file automatically, which is how the lab build starts in lab mode from a double-click.
2. It takes a lock file, so a second copy won't start, then opens up to two Arduino boards, or the keyboard when there are none.
3. `GameEngine.run()` builds every screen once and runs the frame loop: drain the new samples, run them through the press detectors, hand events to the screen on show, update, draw, flip, and only then send any EEG stimulus byte, so it goes out as close to the moment the picture appears as software allows.
4. The login takes a name, the study details and a session length; the hand screen picks the hand, and the quick calibration measures it.
5. `GameEngine.begin_game()` looks up the game's starter in `_BLOCK_STARTERS`. The starter builds the mode from the config and calls `_begin_block()`, which opens the session folder, starts the loggers and runs the GET READY countdown (8 s before a sitting's first game).
6. The screen calls the mode's `update()` every frame. The mode cues fingers with `engine.on_stim()`, which lights the tile, buzzes, plays the tone and arms the EEG byte, and records each trial with `engine.log_trial()`.
7. `engine.finish_block()` ends it: the loggers close, `metadata.json` gets the block summary, the report is written and the results screen offers NEXT UP.

## Boards and plug order

Each board is one hand: four pads on an Arduino Nano sending `FSR: a,b,c,d` 200 times a second at 115200 baud. A reader thread per board stamps each line with the computer's clock as it arrives. Opening the port resets the Nano, which streams within 2 s and buzzes its four motors as a self-test while it does.

`hardware/discovery.py` decides which board is which hand, at start-up and whenever Settings reconnects:

1. A port saved in Settings (`serial.left_port`, `serial.right_port`) is used as long as that port exists. Port names can change each time a board is plugged in, so a saved port that no longer exists is ignored.
2. A hand that already had a board this run keeps it, so a replugged board comes back on the same hand.
3. Otherwise the first board found is the right hand and the second the left.

Boards are recognised by USB vendor ID (`serial.vendor_ids`). The lab's marker box is an Arduino too, so its port is never used as a hand board. The game checks for new boards once a second, and one plugged in mid-game is connected when that game ends. With one board the login offers right or left, and the board becomes that hand. The keyboard plays every game except Force Pilot and Buzz Hunt, which need a real force trace and real motors.

## Calibration and the press detector

A hand resting on the device puts a different load on each pad (most on the little finger's). A single threshold measured on an empty device set off presses from a resting hand on one finger and couldn't be reached on another, so each finger gets its own. The quick calibration at login records each pad empty, with the hand resting, and under a light press held for a second, and `hardware/calibration_profile.py` turns that into thresholds:

- The trigger is set 30% of the way from resting to the light press (`fsr.press_fraction`; Settings, Setup, Press point). It never goes under 12 counts, eight times the pad's noise, the resting load plus three times the noise, or 2.5 times the peak of a hand that shakes at rest.
- The gap it's taken from is capped at three times the smallest light press asked for, so pressing hard during calibration can't make the game hard to play.
- The release point is lower, at 20% of the gap and at least 10 counts under the trigger, so a finger hovering at the trigger can't chatter.
- A profile is refused when a finger travels under 20 counts, its trigger would need over 70% of its travel, or a pad reads zero empty.

Profiles are saved as `config/calibration/current_<hand>.json`, with a dated copy in `history/`, and each block copies the one it ran under into `metadata.json`.

`hardware/fsr_detector.py` then runs per hand, per sample. It keeps a slow baseline for each pad (`fsr.baseline_alpha`, about a ten-second time constant, so drift is absorbed but a slow push isn't), starting from the measured resting level. A press counts on the second raw sample in a row over baseline plus trigger (`fsr.count_on: raw`), so one noisy sample can't count; sessions before 3 November 2026 counted on the smoothed value instead, and replays read the rule from each session's own config. A press ends when the smoothed force drops under the release point, or, for a finger left resting on its pad, after 1.5 s below half its peak or 2 s held (`fsr.rest_release_s`, `fsr.hold_max_s`). A pad can't fire twice within 100 ms.

## Cues and the motors

A cue has four switches (`cue.buzz_before`, `cue.sound_before`, `cue.buzz_after`, `cue.sound_after`), plus whether the screen lights the finger (`cue.show_target`); every trial row records the mix in `cue_flags`, for example `BS/--`. The firmware only knows `STIM:n` (buzz finger n for 150 ms) and `STOP`, so a longer buzz is the command repeated (`motor.cue_ms`). EEG markers are sent the same way: `hardware/eeg_trigger.py` holds the code map and the writer, explained in [EEG_Lab/developer](../../EEG_Lab/developer).

## The session folder

`data/logger.py` makes one folder per game, `sessions/<YYYY-MM-DD>/<login>_<HHMMSS>_<game>/`, and never reuses a name. `sessions/` is beside the app, or wherever `--data-dir` points.

| File | What is in it |
| --- | --- |
| `trials.csv` | One row per trial, every column commented in `TRIAL_COLUMNS` (`data/logger.py`): the finger, the reaction time or timing error, the outcome, wrong presses, peak force and impulse, the cue mix, and for the force games the waveform and its scored segments |
| `raw.csv` | Every sample (`t_perf`, `fsr1` to `fsr8`, `hand`) and, on the same clock, event rows: presses, releases, cues, EEG bytes, pauses and each game's own events |
| `metadata.json` | `data/session.py`: who and when, the block summary, the calibration, a copy of the config, the EEG state, the software version |
| `report.html`, `summary.csv`, `charts/` | A quick look at the block (`analytics/report.py`) |
| `events.tsv`, `events.json`, `markers_codes.csv` | EEG blocks only: every marker, and the code map it was sent under |
| `SRT_*.csv` | The Reaction card only: the files the lab's own script writes |

`sessions_index.csv` at the top of `sessions/` gets a line per block. Force is in newtons, 51.2 counts to the newton from the pads' 10 N rating (`fsr.force_calibration_n_per_count`).

## Timed sessions

The 15, 30, 45 and 60 minute sessions are presets under `protocol` in `config/default.yaml`: an order of games, the hand for each, and shorter trial counts, with every threshold and scoring rule left unchanged. `game/battery.py` turns a preset into one person's plan, picking order A or B from their study code, and NEXT UP steps through it. Adding a new sitting only needs a config edit, and `scripts/measure_battery.py` times it.
