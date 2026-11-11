# scripts

Tools run by hand from `app/`, for example `python3 scripts/check_sitting.py`. None is part of the game, and each file's docstring says how to run it and what it writes. The simulations drive the real engine headless, so they measure what the game does, not a model of it.

| Script | What it does |
| --- | --- |
| **The device** | |
| [`test_device.py`](test_device.py) | Full hardware check, pass or fail per item: the stream rate, each pad's resting range and finger, each motor, and a normal press crossing the trigger. Run it after a rebuild or a long gap |
| [`pad_bench.py`](pad_bench.py) | Bench the four pads with known masses: a quick counts-per-gram check, or `--characterise` for the sensor comparison (future work) |
| [`force_check.py`](force_check.py) | Check the newton scale with known masses |
| [`buzz_soak.py`](buzz_soak.py) | Run the motors on a timer for as long as it's left going, logging failures |
| [`latency_check.py`](latency_check.py) | Drive the buzz and the screen on a fixed schedule, so a phone camera or a piezo disc can time what the game can't see |
| [`clip_delay.py`](clip_delay.py) | Read the screen's delay off a 240 fps phone clip of `latency_check.py --display` (needs ffmpeg) |
| [`audio_latency.py`](audio_latency.py) | This computer's sound and buzz delays, saved with `--write`: Settings, Setup, Audio delay from a terminal |
| **A study day** | |
| [`check_sitting.py`](check_sitting.py) | READY, or what to fix while the participant is still there |
| [`deidentify_sessions.py`](deidentify_sessions.py) | Copy the sessions with every name replaced by a code, P01 upwards, before any analysis |
| [`virtual_trigger_box.py`](virtual_trigger_box.py) | A fake EEG trigger box on a Mac that checks every byte against the logs. For a window with the markers over a simulated EEG: `python3 main.py --eeg-simulator` |
| **Simulation** | |
| [`measure_battery.py`](measure_battery.py) | Play whole timed sessions through the engine with a model hand and time them: run it after changing a sitting |
| [`simulate_cohort.py`](simulate_cohort.py) | A cohort of model hands with known traits, for checking that the notebook finds what was put in |
| **Syllables** | |
| [`build_syllables_bank.py`](build_syllables_bank.py), [`build_syllables_pools.py`](build_syllables_pools.py), [`build_syllables_probe.py`](build_syllables_probe.py) | Word lists and the fixed probe sets into the files the game reads |
| [`syllables_tts.py`](syllables_tts.py), [`render_syllables_speech.py`](render_syllables_speech.py) | The synthetic voice for every word, chunk and syllable |
| [`syllables_recording_kit.py`](syllables_recording_kit.py) | Record a real voice instead; `listen` has two listeners check the probe's syllables by ear |
| **Files the repository keeps** | |
| [`build_study_chart.py`](build_study_chart.py) | Freeze the study's Rhythm chart into `assets/charts/`, its notes moved onto the music's attacks |
| [`build_lab_package.py`](build_lab_package.py) | Assemble the EEG lab folder from the app |
| [`check_lab_sync.py`](check_lab_sync.py) | Checks that the lab folder matches the app. `--fix` updates it |
| [`make_screenshots.py`](make_screenshots.py) | Render every screen to `docs/images` for the READMEs |
| [`make_eeg_cheat_sheet.py`](make_eeg_cheat_sheet.py) | Draw the EEG marker cheat sheet, dark and light, from the marker map |
