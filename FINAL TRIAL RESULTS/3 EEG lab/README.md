# 3 EEG lab

The one EEG session. Thesis Section 4.8.

Copy the lab folder's whole `sessions/` in here, as `sessions/`: the game folders and `eeg/` with ActiView's `.bdf` file together.

Then, from `analysis/`, with MNE installed (`pip install mne python-picard`):

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

It pairs each recording with its game by the markers and writes `results/<date>_<participant>/`: the results page `EEG_results.html`, a short summary as Word and PDF, MNE's reports, the figures and the tables, plus a zip of the folder to send. About a minute for a lab session, a few more for MNE's reports (`--no-reports` skips them). A headline on the page claims an effect only when its test passes.
