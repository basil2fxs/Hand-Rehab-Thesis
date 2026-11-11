# modes

One file per game, each opening with the research behind it: what it measures, where its numbers come from and what it logs. The key is the name the code, the config and the session folders use; the hub shows the title.

| File | Key | On the hub | Screen | Measures |
| --- | --- | --- | --- | --- |
| [`srt.py`](srt.py) | `srt` | Reaction | `srt_screen.py` | The lab's serial reaction time task, trial for trial |
| [`reaction.py`](reaction.py) | `reaction` | timed sessions only | gameplay | Simple and choice reaction time after a random wait |
| [`adaptive.py`](adaptive.py) | `adaptive` | Adaptive | gameplay | Speed at a held difficulty: the pace keeps the hit rate between 65 and 80% |
| [`pattern.py`](pattern.py) | `pattern` | Muscle Memory | gameplay | Learning of a repeated sequence, against random probes |
| [`chords.py`](chords.py) | `chords` | Chords | gameplay | Fingers moving together, the rest held still |
| [`rhythm.py`](rhythm.py) | `rhythm` | Rhythm | `RhythmScreen` | Timing against the beat of a song |
| [`syllables.py`](syllables.py) | `syllables` | Syllables | `syllables_screen.py` | Reading by sound; word lists, wrong options and age profiles are in the `syllables_*` files |
| [`mirror.py`](mirror.py) | `mirror` | Mirror | gameplay | The two hands pressing together (two boards) |
| [`force_pilot.py`](force_pilot.py) | `force_pilot` | Force Pilot | `force_pilot_screen.py` | Steady control of force along a moving line |
| [`buzz_hunt.py`](buzz_hunt.py) | `buzz_hunt` | Buzz Hunt | `buzz_hunt_screen.py` | Telling which finger buzzed |
| [`echo.py`](echo.py) | `echo` | Echo | gameplay | Memory span for a sequence of lit fingers |
| [`classic.py`](classic.py) | `classic` | retired | gameplay | The 2025 game, kept so old sessions still load |

"gameplay" is `GameplayScreen` in `ui/screens.py`, the lane strip most games share. [`_keys.py`](_keys.py) maps key names to pygame codes and picks the keymap for the hand in play. The research behind each game is in [docs/research](../../../docs/research), and what each review changed in [docs/research/deep](../../../docs/research/deep).

## What a game is

A game is a plain class. The engine builds it, its screen drives it, and it reports back through a few engine calls. [`adaptive.py`](adaptive.py) is the shortest complete one, so read it first.

| The game provides | Called | What it does |
| --- | --- | --- |
| `__init__(engine, ...)` | by its starter in `engine.py` | Takes what it needs, already read from the config |
| `queue_press(ev)` | by the engine, for every counted press | Queues a `PressEvent` (`lane` 0 to 3, or 0 to 7 with both hands, `t_perf`, `hand`) for `update` |
| `handle_event(e)` | by the screen, per pygame event | The keyboard stand-in: keymap keys become `PressEvent`s, logged as raw `press` rows with `detail="keyboard"` |
| `update(dt)` | by the screen, every frame | Handles presses, fires cues, closes trials, ends the block |
| `on_resume(pause_dur)` | by the engine after a pause | Moves stored times forward, so no reaction time includes the pause |
| `block_stats()` | by the engine at the end | A dict saved in `metadata.json` under `block_summary.<key>` |
| `on_release(ev)`, optional | by the engine, for every release | The press's whole peak (Mirror compares the hands with it) |

| The game calls | What it does |
| --- | --- |
| `engine.on_stim(lane, trial_id, t)` | The cue: lights the finger, buzzes, plays the tone and arms the EEG byte, as the cue switches allow |
| `engine.log_trial(trial, outcome, now, ...)` | One row of `trials.csv`; `trial` is a `PendingTrial` (in `classic.py`), `outcome` a `TrialResult` from `game/scoring.py` |
| `engine.apply_wrong_press_penalty()`, `apply_idle_press_penalty()` | Points lost to a wrong finger or a press between trials |
| `engine.raw_logger.queue_event(name, ...)` | An event row in `raw.csv` for anything the analysis will want |
| `engine.finish_block()` | Ends the block: summary, files, results screen |

`game/scoring.py` grades a reaction time as the 2025 game did, so old and new sessions compare: Perfect to 100 ms, Great to 200, Good to 500, then Late, and Miss with no press. A game can also have `current_timeout_s` (the timing bar reads it), `export_files(folder)` for files beside `trials.csv` (how the SRT writes the lab script's files), and the `WaitSkip` mixin in `game/rest_skip.py` for a rest the player can cut short with Space.

## Adding a game

1. **The game.** `modes/<key>.py` with the class above and a docstring on what it measures and why its numbers are what they are.
2. **Its settings.** A `<key>:` block in `config/default.yaml`, every key commented. The starter reads them with `cfg.get("<key>.<name>", default)`, the default matching the YAML.
3. **The starter.** `begin_<key>_block()` on `GameEngine` (`game/engine.py`): build the game, call `self._begin_block("<key>")`, then set `self.screen_obj` to its screen (`self._screens["gameplay"]` for a lane game). Register it in `_BLOCK_STARTERS` and add the key to `MODE_KEYS` in `main.py`; `tests/test_run_lock_order.py` fails when the two differ.
4. **The engine's lists.** The key goes in the list in `_begin_block()` that gets the GET READY countdown, and `_build_block_summary()` needs a branch that stores `block_stats()`; there is no catch-all, so without one nothing reaches `metadata.json`. A game with its own screen also goes in `_build_screens()` and `_BLOCK_SCREEN_KEYS`, which pause and the skip chip check. Its instruction goes in `GameplayScreen.GET_READY_LINES`, or in `EXTRA_LINES` in `audio/spoken.py` for a game with its own screen, so `instructions.spoken` can read it aloud.
5. **EEG.** An id in `MODE_IDS` (`hardware/eeg_trigger.py`) and a raised `CODES_VERSION`; without an id the block sends no start or end byte. Never reuse 9 (a retired game's) or go past 18, where block bytes run into reserved ones. `tests/test_eeg_contract.py` checks both.
6. **The hub.** A row in `ModeSelectScreen.MODES` (`ui/screens.py`: key, title, one short line) and a colour in `MODE_ACCENTS`. A game the keyboard can't play goes in `HARDWARE_MODES` (`game/battery.py`), which badges its card and refuses it without sensors. The grid holds ten cards and `tests/test_screen_layout.py` counts them, so an eleventh means reworking the grid and renaming the front page's "The ten games", which `tests/test_readme.py` pins. A game can skip the hub, as `reaction` does.
7. **Timed sessions.** A step in the presets under `protocol.presets` in `config/default.yaml`, then `scripts/measure_battery.py` to time the sitting again.
8. **Pictures and tables.** A row in the front page's game table (checked against `MODES`), a row here, and a screenshot: the name in `NAMES` in `scripts/make_screenshots.py` and, for a lane game, in the list in its `main()`.
9. **Tests.** A `tests/test_<key>_mode.py` that plays blocks through a real engine on the keyboard source, as `tests/test_keyboard_mode_coverage.py` does, and checks the rows that come out; the key also goes in `KEYBOARD_MODES` there. A new column or event the notebook reads belongs in `tests/test_notebook_matches_software.py` too.
10. **The notebook.** A `sec_<key>` function in the Setup cell of `analysis/session_analysis.ipynb`, then a heading and a cell that runs `check_selection(ctx, pick)` and calls it through `keep()`, like its neighbours (a test checks every chapter goes through `keep()`, which puts it in the HTML report).

Most of these steps have a test that fails when one is missed, so run the whole suite at the end.
