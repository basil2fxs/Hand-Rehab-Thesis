# finger_rehab

The game as a Python package. `main.py` loads the config, finds the boards (or falls back to the keyboard), makes a `GameEngine` and runs it. Everything else hangs off the engine.

| Folder | What it does | Start with |
| --- | --- | --- |
| [`game/`](game) | The engine, timed sessions, scoring, who gets cued next | `engine.py`, `battery.py`, `scoring.py`, `scheduling.py` |
| [`game/modes/`](game/modes) | One file per game, and how to add one | its [README](game/modes/README.md) |
| [`ui/`](ui) | Every screen, the theme and the widgets | its [README](ui/README.md) |
| [`hardware/`](hardware) | Boards, plug order, the press detector, calibration, EEG markers, auto-start, flashing | `discovery.py`, `fsr_detector.py`, `calibration_profile.py` |
| [`data/`](data) | Session folders and the CSV logs, study codes, history | `logger.py`, `session.py`, `intake.py` |
| [`audio/`](audio) | Cue sounds, music, the rhythm charts, the delay measurement | `engine.py`, `beatmap.py`, `latency_measure.py` |
| [`analytics/`](analytics) | The adaptive controller, the per-block summary and report, force-signal tools | `adaptive.py`, `metrics.py`, `report.py`, `signal.py` |
| [`utils/`](utils) | Logging set-up and the EEG simulator | `eeg_simulator.py` |

`config.py` sits at the top: it loads the YAML layers (see [config](../config)) and decides where writable files go.

## One session, start to finish

1. `main.py` reads the flags and `Config.load()` stacks the YAML files. A frozen exe with `eeg_lab.yaml` beside it loads that file as if `--config` had named it, which is how the lab build starts in lab mode from a double-click.
2. It takes a lock file, so a second copy refuses to start, then builds the sample source: up to two Arduino boards, or the keyboard when none is found.
3. `GameEngine.run()` opens the window and builds every screen once (`_build_screens`). Each frame it drains the samples that arrived, feeds them through the press detectors, passes events to the screen on show, lets the screen update and draw, flips the display, and only then sends any EEG stimulus byte, so the byte goes out as close to the picture as the software can get it.
4. The login screen takes a name, the details the study needs and a session length. The hand screen picks the hand, and the quick calibration measures it.
5. A game starts through `GameEngine.begin_game()`, which looks up the game's starter in `_BLOCK_STARTERS`. The starter builds the mode object from the config and calls `_begin_block()`, which opens the session folder, starts the loggers and the GET READY countdown.
6. While the game runs, the screen calls the mode's `update()` every frame. The mode cues fingers with `engine.on_stim()`, which lights the tile, buzzes the motor, plays the tone and arms the EEG byte, and records each trial with `engine.log_trial()`.
7. When the mode is done it calls `engine.finish_block()`: the loggers close, `metadata.json` gets the block summary, the report is written and the results screen shows NEXT UP. A timed session moves on to its next step from there.

## Boards and plug order

Each board is one hand: four pads on an Arduino Nano sending `FSR: a,b,c,d` 200 times a second over USB at 115200 baud. A reader thread per board turns each line into a sample stamped with the computer's clock when it arrived. Opening the port resets a Nano, and the firmware buzzes all four motors as a self-test before it streams, so a board takes about three seconds to come up.

`hardware/discovery.py` decides which board is which hand, and the same rules run at start-up and whenever Settings reconnects:

1. A port saved in Settings (`serial.left_port`, `serial.right_port`) wins, but only while that port exists. Port names change between plug-ins, so a stale one is ignored rather than left blocking a hand.
2. A hand that already had a board this run keeps it, so a replugged board comes back on the same hand.
3. Otherwise the first board found is the right hand and the second the left.

Boards are recognised by their USB vendor IDs (`serial.vendor_ids`: Arduino, Adafruit, CP210x, CH340, FTDI). The lab's marker box is an Arduino too, so its port is kept off the hand boards. A port watcher looks for new boards once a second; one plugged in mid-game waits for that game to end. With one board, the login offers right or left and the board becomes that hand. The keyboard source plays every game except Force Pilot and Buzz Hunt, which need a real force trace and real motors.

## Calibration and the press detector

The quick calibration at login captures three things per finger: the pads with nothing on them, the hand resting, and a light press held for a second. `hardware/calibration_profile.py` turns them into thresholds:

- The gap is the light press minus the resting level. The trigger sits 30% of the way up it (`fsr.press_fraction`, Settings, Setup, Press point), and never lower than 12 counts, eight times the pad's noise, or its resting load plus three times the noise.
- The gap used is capped at three times the smallest light press the calibration asks for, so pressing hard during calibration can't make the game hard to play.
- The release point sits at 20% of the gap, lowered where needed to stay at least 10 counts under the trigger, so a finger hovering near the trigger can't chatter.
- A profile is refused when a finger travels under 20 counts, when its trigger would need more than 70% of its travel (a pad loaded too heavily at rest), or when a pad reads zero empty (a sensor fault).

Profiles are saved as `config/calibration/current_<hand>.json` with a dated copy in `history/`, and every block copies the one it ran under into `metadata.json`.

`hardware/fsr_detector.py` then runs per hand, per sample. It smooths each pad (`fsr.value_alpha`), tracks a slow baseline (`fsr.baseline_alpha`, a time constant of about ten seconds, so drift is absorbed but a slow press is not), primes that baseline with the measured resting level, and counts a press when the smoothed force rises past baseline plus the trigger. The baseline is frozen during a press. A press ends when the force falls back under the release point, or, for a finger left resting on its pad, after 1.5 s below half its peak or 2 s held (`fsr.rest_release_s`, `fsr.hold_max_s`); those two rules were added on 24 October 2026 after a finger resting on its pad kept it from ever releasing, and `analysis/stuck_pad_replay.py` shows what they change on a recorded session. A pad can't fire twice within 100 ms (`fsr.debounce_ms`).

Why it works this way: a hand resting on the device already loads each pad by a different amount (the little finger's pad by far the most), so one threshold read from an empty device fired presses from a resting hand on one finger and was out of reach on another.

## Cues and the motors

A cue has four switches, each on or off by itself (`cue.buzz_before`, `cue.sound_before`, `cue.buzz_after`, `cue.sound_after`), plus whether the screen lights the finger (`cue.show_target`). Every trial row records the mix in `cue_flags`, for example `BS/--`. The firmware only knows `STIM:n` (buzz finger n for 150 ms) and `STOP`, so the game holds a longer buzz by repeating the command (`motor.cue_ms`). The measured delays of this computer's sound and buzz live under `latency` and `rhythm`, written by Settings, Setup, Audio delay.

EEG markers are the same path with one more step: `hardware/eeg_trigger.py` holds the code map and the writer, and a block in the lab build sends a byte for every cue, press and boundary. How the codes are built: [EEG_Lab/developer](../../EEG_Lab/developer).

## The session folder

`data/logger.py` makes one folder per game, `sessions/<YYYY-MM-DD>/<login>_<HHMMSS>_<game>/`, and never reuses a name. `sessions/` sits beside the app, or wherever `--data-dir` points.

| File | What is in it |
| --- | --- |
| `trials.csv` | One row per trial (`TRIAL_COLUMNS` in `data/logger.py`, each column commented there): the finger, the reaction time or timing error, the outcome and points, wrong presses, peak force and impulse, the cue mix, the stimulus, and for the force games the waveform and its scored segments |
| `raw.csv` | Every sample (`iso_ts`, `t_perf`, `sample_idx`, `fsr1` to `fsr8`, `hand`) and, on the same clock, event rows: `press`, `release`, `stim`, `eeg`, block boundaries, pauses and each game's own events, with `lane` and `detail` |
| `metadata.json` | `data/session.py`: who and when, the block summary, the calibration, a copy of the whole config, the EEG state, the software and Python versions |
| `report.html`, `summary.csv`, `charts/` | A quick look at the block (`analytics/report.py`, `report.enabled`) |
| `events.tsv`, `events.json`, `markers_codes.csv` | EEG blocks only: every marker and the code map it was sent under |
| `SRT_*.csv` | The Reaction card only: copies of the files the lab's own script writes |

The top of `sessions/` also gets `sessions_index.csv`, one line per block. Force columns are in newtons whenever `fsr.force_calibration_n_per_count` is set (it is: 51.2 counts to the newton, from the pad's 10 N rating), and `block_summary.force_unit` says which.

## Timed sessions

The 15, 30, 45 and 60 minute sessions are presets under `protocol` in `config/default.yaml`: an order of games, the hand for each, and overrides that shorten counts without changing any threshold or scoring rule. `game/battery.py` turns a preset into a plan for one person, choosing order A or B from their study code's number, and the engine walks through it with NEXT UP. A new sitting is a config edit, not a code change, and `scripts/measure_battery.py` times it.
