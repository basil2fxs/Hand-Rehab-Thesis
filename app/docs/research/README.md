# research

What each game rests on, and the study that tests it. Every file names its sources, and the dated entries say when a decision was made and why. These notes are where a number in the code comes from: when a comment in `config/default.yaml` or a game's docstring cites a paper, the reasoning is here.

## The study

| Path | What it covers |
| --- | --- |
| [`healthy_baseline_study.txt`](healthy_baseline_study.txt) | The study design: one sitting on one board in two passes, every pre-registered check, the timings and the exclusions. HOW THE DESIGN GOT HERE logs each change with its date |
| [`design_check.md`](design_check.md) | Whether the collection gives the thesis every result it needs, checked before any participant |
| [`analysis_methods.md`](analysis_methods.md) | How the data is analysed: Python or MATLAB, the force-sensor bench scripts, true force, and each measure against standard practice |
| [`trial_mode.md`](trial_mode.md) | The 15, 30, 45 and 60 minute sessions: what each plays and why |

## The games

| Path | What it covers |
| --- | --- |
| [`new_modes/`](new_modes) | Where the games came from. [`ranked.md`](new_modes/ranked.md) ranks the candidates from five clinical clusters ([stroke](new_modes/stroke.md), [movement disorders](new_modes/movement-disorders.md), [force control](new_modes/force-control.md), [carpal tunnel and nerve](new_modes/carpal-nerve.md), [paediatric](new_modes/paediatric-cognitive.md)); the rest cover Force Pilot and Parkinson's disease, the SRT, Syllables and a review of seven modes |
| [`deep/`](deep) | One full-text review per game (October 2026): its parameters against the evidence, what changed and what is left |

## The EEG

| Path | What it covers |
| --- | --- |
| [`eeg/eeg_integration_spec.md`](eeg/eeg_integration_spec.md) | The marker layer: the code bands, how a cue's channels are coded, collisions and failures |
| [`eeg/erp.md`](eeg/erp.md) | Which brain responses the tasks can measure, stimulus- and response-locked |
| [`eeg/preparation_attention.md`](eeg/preparation_attention.md) | Motor preparation and attention: what EEG can and can't give the software |
| [`eeg/trigger_hardware.md`](eeg/trigger_hardware.md) | The trigger box and the serial path, ported from the lab's PsychoPy script |
| [`eeg/response_timing.md`](eeg/response_timing.md) | Whether the 30% press point suits the markers, and how a press is timed for response-locked epochs |
| [`eeg/mne_analysis.md`](eeg/mne_analysis.md) | Notes checked against MNE-Python for the BioSemi recordings, behind `analysis/eeg` |

## The device

| Path | What it covers |
| --- | --- |
| [`force_units.txt`](force_units.txt) | What the newton figures mean: the pads' 10 N rating, the counts-to-newtons constant and how accurate it is |
| [`rayan/`](rayan) | The force-sensor bench work from the hardware side of the project: its R and Python scripts, the CSV format they expect, and screenshots |
