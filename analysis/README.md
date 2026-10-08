# analysis

[`session_analysis.ipynb`](session_analysis.ipynb) turns recorded sessions into results: a chapter per game, the cohort tables and figures, a report, and the reference list.

1. `pip install -r ../app/requirements.txt`
2. Open the notebook in VS Code or Jupyter and run the Setup cell.
3. Pick a save from the dropdown, then Run All.

<p align="center"><img src="../app/docs/images/analysis_norms.png" width="48%" alt="A normal-range figure from the cohort chapter"> <img src="../app/docs/images/analysis_reliability.png" width="48%" alt="A reliability figure from the cohort chapter"><br><sub>Two of the cohort chapter's figures, from a simulated cohort.</sub></p>

It finds `sessions/` beside it or up to four levels above; set `SESSIONS_DIR` in the Setup cell for a copy kept elsewhere. Figures land in the session folder they describe, per-person summaries in `sessions/individual_patient_results/<person>/`, cohort output in `sessions/cohort_results/`.

The export cell also writes `shared/matlab/finger_rehab.mat` for MATLAB and `shared/rayan_format/`, on which Rayan's R scripts run unchanged. Methods and their sources: [`app/docs/research/analysis_methods.md`](../app/docs/research/analysis_methods.md).

## EEG recordings

[`eeg/`](eeg) analyses a lab session's BioSemi recordings with MNE-Python: it pairs each `.bdf` with its game block by the marker bytes, cleans the data (average reference, 0.1-40 Hz, ICA for the eyes), and measures the ERPs, the error signal and the brain rhythms for the SRT and Buzz Hunt. `pip install mne python-picard`, then from this folder:

    python3 -m eeg "../FINAL TRIAL RESULTS/3 EEG lab/sessions"

The output goes beside the sessions, in `results/`, where git never sees it.
