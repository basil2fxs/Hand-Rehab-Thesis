# End of the day

## Check the data (5 min)

- [ ] `sessions/<today>/` holds one folder per game played, each with
      trials.csv, raw.csv and metadata.json. A full sitting is twelve
      folders per code.
- [ ] Nothing from a pilot or a demo is in there (move it out).

## The intake sheet file (10 min)

Type each participant's Edinburgh LQ into `sessions/intake_sheet.csv`,
one row per code. Start from
[intake_sheet_template.csv](intake_sheet_template.csv):

```
participant,edinburgh_lq
P01,87.5
P02,-75
```

The notebook reads it for the handedness chapter (the LQ correlation)
and the participants table. The login already recorded the main hand,
age, sex and hand size, so nothing else needs typing.

## Back up (5 min)

- [ ] Copy the whole `sessions/` folder to the university storage and
      to one second place (an external drive). Two copies before
      anything is deleted anywhere.
- [ ] Never into the Google Drive repo folder: participant data stays
      out of anything that syncs to GitHub.
- [ ] Consent forms in their own envelope, apart from the intake
      sheets.

## Run the analysis

Open `analysis/session_analysis.ipynb` and run the cohort chapter. It
finds `sessions/` beside the notebook or up the folder tree; if the
day's data sits somewhere else, set `SESSIONS_DIR` in the config cell
to that folder. Everything lands in
`sessions/cohort_results/`: the validity table, the reliability table,
the handedness and sensitivity tables, the chord size table and the
figures. With fewer than eight people the checks say n is under the
minimum; that is expected until the day is done.

## Reset the rig

- [ ] Wipe the pads and frame, unplug the board, pack the cable.
