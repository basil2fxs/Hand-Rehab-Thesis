# modes

One file per game. Each file opens with the research behind its game: what it measures, the papers behind its numbers and what it logs. The key is the name the code, the config and the session folders use; the hub shows the title.

| File | Key | On the hub | Screen | Measures |
| --- | --- | --- | --- | --- |
| [`srt.py`](srt.py) | `srt` | Reaction | `srt_screen.py` | The lab's serial reaction time task, trial for trial |
| [`reaction.py`](reaction.py) | `reaction` | timed sessions only | gameplay | Simple and choice reaction time after a random wait |
| [`adaptive.py`](adaptive.py) | `adaptive` | Adaptive | gameplay | Speed at a held difficulty: the pace keeps the hit rate between 65 and 80% |
| [`pattern.py`](pattern.py) | `pattern` | Muscle Memory | gameplay | Learning of a repeated sequence, against random probes |
| [`chords.py`](chords.py) | `chords` | Chords | gameplay | Fingers moving together, the rest held still |
| [`rhythm.py`](rhythm.py) | `rhythm` | Rhythm | `RhythmScreen` | Timing against the beat of a song |
| [`syllables.py`](syllables.py) | `syllables` | Syllables | `syllables_screen.py` | Reading by sound. Word lists, wrong options and age profiles are in the `syllables_*` files |
| [`mirror.py`](mirror.py) | `mirror` | Mirror | gameplay | The two hands pressing together (two boards) |
| [`force_pilot.py`](force_pilot.py) | `force_pilot` | Force Pilot | `force_pilot_screen.py` | Steady control of force along a moving line |
| [`buzz_hunt.py`](buzz_hunt.py) | `buzz_hunt` | Buzz Hunt | `buzz_hunt_screen.py` | Telling which finger buzzed |
| [`echo.py`](echo.py) | `echo` | Echo | gameplay | Memory span for a sequence of lit fingers |
| [`classic.py`](classic.py) | `classic` | retired | gameplay | The 2025 game, kept so old sessions still load |

"gameplay" is `GameplayScreen` in `ui/screens.py`, the lane strip most games share. [`_keys.py`](_keys.py) turns key names into pygame codes and picks the keymap for the hand in play. The full research behind each game is in [docs/research](../../../docs/research), and what each review changed is in [docs/research/deep](../../../docs/research/deep).

## What a game is

A plain class. The engine builds it, its screen drives it, and it talks back through a few engine calls. [`adaptive.py`](adaptive.py) is the shortest complete one and the best place to start reading.

| The game provides | Called | What it does |
| --- | --- | --- |
| `__init__(engine, ...)` | by the starter in `engine.py` | Takes everything it needs as arguments, already read from the config |
| `queue_press(ev)` | by the engine, for every press the detector counts | Queues a `PressEvent` (`lane` 0 to 3, or 0 to 7 with both hands, `t_perf`, `hand`) to be handled in `update` |
| `handle_event(e)` | by the screen, for each pygame event | The keyboard stand-in: turns the keymap's keys into `PressEvent`s and logs a raw `press` row with `detail="keyboard"` |
| `update(dt)` | by the screen, every frame | Handles the queued presses, fires cues, closes trials, ends the block |
| `on_resume(pause_dur)` | by the engine after a pause | Moves every stored time forward by the pause, so no reaction time includes it |
| `block_stats()` | by the engine at the end | A dict that lands in `metadata.json` under `block_summary.<key>` |

| The game calls | What it does |
| --- | --- |
| `engine.on_stim(lane, trial_id, t)` | The cue: lights the finger, buzzes, plays the tone and arms the EEG byte, each as the cue switches allow |
| `engine.log_trial(trial, outcome, now, ...)` | Writes one row of `trials.csv`. `trial` is a `PendingTrial` (in `classic.py`), `outcome` a `TrialResult` from `game/scoring.py` |
| `engine.apply_wrong_press_penalty()`, `apply_idle_press_penalty()` | The points lost to a wrong finger or a press between trials |
| `engine.raw_logger.queue_event(name, ...)` | An event row in `raw.csv` for anything the analysis will want later |
| `engine.finish_block()` | Ends the block: summary, files, results screen |

`game/scoring.py` grades a reaction time the way the 2025 game did, so old and new sessions compare: Perfect up to 100 ms, Great up to 200, Good up to 500, Late after that, Miss with no press. Optional extras a game can carry: `current_timeout_s` (the timing bar reads it), `export_files(folder)` for extra files beside `trials.csv` (the SRT writes the lab script's files this way), and the `WaitSkip` mixin in `game/rest_skip.py` for a rest the player can cut short with Space.

## Adding a game

1. **The game.** `modes/<key>.py` with the class above, opening with a docstring on what it measures and where its numbers come from.
2. **Its settings.** A `<key>:` block in `config/default.yaml`, every key commented with the reason for its value. The starter reads them with `cfg.get("<key>.<name>", default)`, the default matching the YAML so a trimmed config behaves the same.
3. **The starter.** `begin_<key>_block()` on `GameEngine` in `game/engine.py`: build the game from the config, call `self._begin_block("<key>")`, then set `self.screen_obj` to its screen (`self._screens["gameplay"]` for a lane game). Register it in `GameEngine._BLOCK_STARTERS` and add the key to `MODE_KEYS` in `main.py`; `tests/test_run_lock_order.py` fails when the two differ.
4. **The engine's lists.** Add the key to the list in `_begin_block()` that gets the GET READY countdown, and a branch in `_build_block_summary()` that stores `block_stats()`: there is no catch-all, so without it nothing reaches `metadata.json`. A game with a screen of its own also goes in `_build_screens()` and `_BLOCK_SCREEN_KEYS`, which is what pause and the skip chip check.
5. **EEG.** An id in `MODE_IDS` in `hardware/eeg_trigger.py`, and `CODES_VERSION` raised. Without an id the block sends no start or end byte. Id 9 belonged to a retired game and is never reused, and ids stop at 18 so block bytes stay clear of the reserved ones; `tests/test_eeg_contract.py` checks both.
6. **The hub.** A row in `ModeSelectScreen.MODES` in `ui/screens.py` (key, title, one short line) and a colour in `MODE_ACCENTS`. A game the keyboard can't play goes in `HARDWARE_MODES` in `game/battery.py`, which badges the card and refuses it without sensors. The grid is sized for ten cards and `tests/test_screen_layout.py` counts them, so an eleventh means reworking the grid and renaming the front page's "The ten games" section, which `tests/test_readme.py` pins. A game doesn't need a card: `reaction` only plays inside timed sessions.
7. **Timed sessions.** Add a step to the presets under `protocol.presets` in `config/default.yaml`, then time the sitting again with `scripts/measure_battery.py`.
8. **The pictures and the tables.** A row in the front page's game table (its test checks the table against `MODES`), a row here, and a screenshot: add the name to `NAMES` in `scripts/make_screenshots.py` and, for a lane game, to the list in its `main()`.
9. **Tests.** A `tests/test_<key>_mode.py` that plays blocks through a real engine on the keyboard source, the way `tests/test_keyboard_mode_coverage.py` does, and checks the rows that come out. Add the key to `KEYBOARD_MODES` in that file. A new column or event the notebook reads belongs in `tests/test_notebook_matches_software.py` as well.
10. **The notebook.** A chapter for it: a `sec_<key>` function in the Setup cell of `analysis/session_analysis.ipynb`, then a heading and a cell that runs `check_selection(ctx, pick)` and calls the function through `keep()`, like the chapters around it (a test checks every chapter goes through `keep()`, which is how it reaches the HTML report).

Run the whole suite at the end. Most of the steps above have a test that fails when one is missed, which is the point of them.
