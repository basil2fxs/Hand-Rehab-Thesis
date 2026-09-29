# scripts

Tools run by hand from `app/`, for example `python3 scripts/pad_bench.py`. Each file's docstring says how. None is part of the game.

| Script | What it does |
| --- | --- |
| **Before a study** | |
| [`test_device.py`](test_device.py) | Full hardware check of the hand device |
| [`pad_bench.py`](pad_bench.py) | Bench the four pads with known masses: a quick check before a collection day, or `--characterise` for the sensor comparison |
| [`force_check.py`](force_check.py) | Check the newton scale with known masses |
| [`audio_latency.py`](audio_latency.py) | This computer's sound and buzz delays, saved for the game: Settings, Audio delay from a terminal |
| [`latency_check.py`](latency_check.py) | The bench procedure for the cue delays |
| [`buzz_soak.py`](buzz_soak.py) | Run the motors for a long time and log failures |
| **On a study day** | |
| [`check_sitting.py`](check_sitting.py) | READY, or what to fix while the participant is still there |
| [`virtual_trigger_box.py`](virtual_trigger_box.py) | A fake EEG trigger box on a Mac that checks every byte against the logs. For a window with the markers over a simulated EEG: `python3 main.py --eeg-simulator` |
| **Simulation** | |
| [`measure_battery.py`](measure_battery.py) | Play whole sittings through the engine with a model hand and time them |
| [`simulate_cohort.py`](simulate_cohort.py) | A cohort of model hands with known traits, for checking the notebook |
| **Syllables** | |
| [`build_syllables_bank.py`](build_syllables_bank.py), [`build_syllables_pools.py`](build_syllables_pools.py) | Word lists into the files the game reads |
| [`syllables_tts.py`](syllables_tts.py), [`render_syllables_speech.py`](render_syllables_speech.py) | The synthetic voice for every word, chunk and syllable |
| [`syllables_recording_kit.py`](syllables_recording_kit.py) | Record a real voice instead |
| **The repository** | |
| [`build_lab_package.py`](build_lab_package.py) | Assemble the EEG lab folder from the app |
| [`check_lab_sync.py`](check_lab_sync.py) | Is the lab folder the same game as the app? `--fix` makes it so |
| [`make_screenshots.py`](make_screenshots.py) | Render every screen to `docs/images` for the READMEs |
