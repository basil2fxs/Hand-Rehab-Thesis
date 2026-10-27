# tests

Over 4,000 tests, all headless: no screen, sound or board needed. Most build a real `GameEngine` on the keyboard source or on a fake board streaming 200 Hz samples, play blocks through it and check the files that come out.

```bash
cd app
python -m pytest tests -q                 # everything, about five minutes
python -m pytest tests/test_srt_mode.py   # one file
python -m pytest tests -k chords          # every test with chords in its name
```

## How they are grouped

The file name says what a test guards:

| Files | What they check |
| --- | --- |
| `test_<game>_mode.py`, and `test_adaptive.py`, `test_rhythm.py`, `test_force_pilot.py`, `test_buzz_hunt.py`, `test_classic.py` | A game played through the real engine, and the rows it writes |
| `test_<game>_research.py` | That the numbers a game took from its research review stay as the review set them |
| `test_<game>_review.py`, `test_engine_review.py`, `test_review_minor.py` | The faults found by the code review of 27 September 2026, each reproduced; they fail on the code as it was |
| `test_*_notebook.py`, `test_notebook_matches_software.py`, `test_rehab_analysis.py` | The notebook's chapters run on blocks the real engine wrote, and the notebook and the game agree on the file format |
| `test_fsr.py`, `test_calibration*.py`, `test_multi_serial.py`, `test_autoconnect.py`, `test_autostart*.py`, `test_flasher.py` | The press detector, calibration, boards and plug order, auto-start, flashing |
| `test_eeg_*.py` | The marker map and wire, the lab folder, the simulator, and the EEG analysis package |
| `test_sequence_task.py`, `test_press_check.py` | The analysis scripts in `analysis/` |
| `test_readme.py`, `test_contributing.py`, `test_hardware_docs.py`, `test_final_trial_results.py`, `test_lab_package.py` | The READMEs: sections, names, links, plain ASCII, and the numbers they quote, read back from the code |

## The rules they follow

- They read the real config and write only to temporary folders, never to `sessions/`.
- [`conftest.py`](conftest.py) points `user_settings.yaml` and the measured-delay profile at a temporary folder for the whole run, and fails any test that writes the real one. A cue switch once left flipped by a test ran a later block under a cue condition nobody chose, with nothing in the data to show it.
- [`realtime.py`](realtime.py) marks the few tests that run real frames on the wall clock. CI skips them, since a shared runner stalls frames by 50 ms and more, so run the whole suite on a real machine before a release.
- [`fixtures/`](fixtures) holds small recorded files, the force-sensor bench data among them, for the tests that need real numbers.
- Every change comes with a test that fails without it. For a new game, the tests it needs are listed in [the modes README](../finger_rehab/game/modes/README.md).
