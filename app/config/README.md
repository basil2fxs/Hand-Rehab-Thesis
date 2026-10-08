# config

| File | What it is |
| --- | --- |
| [`default.yaml`](default.yaml) | Every setting, each one commented. The game reads this first |
| [`eeg_lab.yaml`](eeg_lab.yaml) | The lab's changes over the defaults: markers on, and a Lab session that plays the SRT and leaves out Muscle Memory |
| [`calibration/`](calibration) | Saved hand calibrations, `current_<hand>.json` and a dated history |
| [`pattern_sequence_template.yaml`](pattern_sequence_template.yaml) | A blank sequence file for Muscle Memory |

<p align="center"><img src="../docs/images/settings.png" width="72%" alt="The Settings screen"><br><sub>The app also writes four files here per machine, none committed: Settings' <code>user_settings.yaml</code>, the trigger box port, the measured audio delays and the saved SRT setups.</sub></p>
