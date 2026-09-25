# scripts

Tools run by hand from `app/`, for example `python3 scripts/pad_bench.py`. Each file's opening docstring says how
to use it. None of them is part of the game.

| Script | What it does |
| --- | --- |
| **Before a study** | |
| [`test_device.py`](test_device.py) | Full hardware check of the hand device |
| [`pad_bench.py`](pad_bench.py) | Bench-check the four force pads with known masses |
| [`force_check.py`](force_check.py) | Check the newton scale with known masses |
| [`audio_latency.py`](audio_latency.py) | Measure this laptop's sound and buzz delays and save them for the game |
| [`latency_check.py`](latency_check.py) | Bench the stimulus delays the game cannot see |
| [`buzz_soak.py`](buzz_soak.py) | Buzz every finger on a timer, for as long as it runs |
| **On the day** | |
| [`check_sitting.py`](check_sitting.py) | Check one participant's sitting before they leave the room |
| **Planning and analysis** | |
| [`measure_battery.py`](measure_battery.py) | Time the whole Play all sitting headless (add `--config config/eeg_lab.yaml` for the lab) |
| [`simulate_cohort.py`](simulate_cohort.py) | Simulate the healthy cohort through the real engine |
| **EEG lab** | |
| [`build_lab_package.py`](build_lab_package.py) | Assemble the `EEG_Lab` folder |
| [`virtual_trigger_box.py`](virtual_trigger_box.py) | Stand in for the trigger box when testing the lab build on a Mac |
| **Syllables material** | |
| [`build_syllables_bank.py`](build_syllables_bank.py) | Build the child word bank |
| [`build_syllables_pools.py`](build_syllables_pools.py) | Build the teen, adult and made-up word pools |
| [`syllables_tts.py`](syllables_tts.py) | Make the Syllables voice with Kokoro, a free text-to-speech model (the one that ships) |
| [`syllables_recording_kit.py`](syllables_recording_kit.py) | Record a human voice to replace it: reading script, cutter, check |
| [`render_syllables_speech.py`](render_syllables_speech.py) | The older per-word synthetic voice |

<sub>[Back to app](../README.md)</sub>
