# config

| File | What it is |
| --- | --- |
| [`default.yaml`](default.yaml) | Every setting, each one commented. The game reads this first |
| [`eeg_lab.yaml`](eeg_lab.yaml) | The EEG lab's changes, laid over the defaults: markers on, the SRT in Play all |
| [`calibration/`](calibration) | Saved hand calibrations: `current_<hand>.json` and a dated history |
| [`pattern_sequence_template.yaml`](pattern_sequence_template.yaml) | A blank sequence file for Muscle Memory |

The app also writes four files here on each machine, and none is committed: `user_settings.yaml` (the Settings
screen), `eeg_port.yaml` (the trigger box port), `latency_profile.yaml` (this laptop's measured sound and buzz
delays) and `srt_setups.json` (the Reaction card's saved setups).

**To change a setting,** edit `default.yaml` for everyone or `eeg_lab.yaml` for the lab only. The game reads
both at launch.

<sub>[Back to app](../README.md)</sub>
