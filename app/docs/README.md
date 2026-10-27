# docs

The written side of the project: how a study day runs, why each game is built the way it is, and how the EEG lab is set up. Nothing here runs.

| Path | What it is |
| --- | --- |
| [`study_day/`](study_day) | The collection-day kit: run sheet, consent, intake, debrief, printed and followed in order |
| [`research/`](research) | The study design and the research behind each game, every file with its sources |
| [`eeg_lab_setup.txt`](eeg_lab_setup.txt) | The EEG lab checklist: the wiring from game to amplifier, the steps at the lab PC, the marker code table and the timing checks |
| [`code_review_2026-09-27.md`](code_review_2026-09-27.md) | The line-by-line review held before any participant, and every fault it found, by game, with what it would have done to the data |
| [`pattern_sequences/`](pattern_sequences) | Example sequence files for Muscle Memory, one hand and both; drop one on the game window to load it |
| [`images/`](images) | The pictures the READMEs show. The screens come from `scripts/make_screenshots.py`, the EEG cheat sheet from `scripts/make_eeg_cheat_sheet.py` |
| [`Guide for Hand Rehabilitation Device.docx`](Guide%20for%20Hand%20Rehabilitation%20Device.docx) | The earlier hardware guide: wiring the SingleTact boards and moving their addresses with the Arduino IDE. Settings, Setup, Sensor address now does the address job from inside the app |

Flashing the board and moving a sensor's address: [`../arduino`](../arduino). Building the device: [hardware](../../hardware).
