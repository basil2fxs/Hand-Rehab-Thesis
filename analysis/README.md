# analysis

[`session_analysis.ipynb`](session_analysis.ipynb) turns recorded sessions into results: a chapter per game, the
cohort tables and figures, a report, and the reference list at the end.

1. Install once: `pip install -r ../app/requirements.txt`.
2. Open the notebook in VS Code or Jupyter and run the Setup cell.
3. Pick a save from the dropdown, then Run All.

It finds `sessions/` on its own, beside it or up to four levels above; for a copy kept elsewhere, set
`SESSIONS_DIR` in the Setup cell. Figures land in the session folder they describe, per-person summaries in
`sessions/individual_patient_results/<person>/` and cohort output in `sessions/cohort_results/`.

[`archive_pre_session_model/`](archive_pre_session_model) holds outputs from before sessions were saved one
folder per game; nothing reads it now.

<sub>[Back to the main README](../README.md)</sub>
