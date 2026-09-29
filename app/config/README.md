# config

| File | What it is |
| --- | --- |
| [`default.yaml`](default.yaml) | Every setting, each one commented. The game reads this first |
| [`eeg_lab.yaml`](eeg_lab.yaml) | The lab's changes over the defaults: markers on, the SRT in the Lab session |
| [`calibration/`](calibration) | Saved hand calibrations, `current_<hand>.json` and a dated history |
| [`pattern_sequence_template.yaml`](pattern_sequence_template.yaml) | A blank sequence file for Muscle Memory |

<p align="center"><img src="../docs/images/settings.png" width="72%" alt="The Settings screen"><br><sub>Settings writes <code>user_settings.yaml</code> here; the trigger box port, the measured audio delays and the saved SRT setups are three more files the app writes per machine. None of the four is committed.</sub></p>
