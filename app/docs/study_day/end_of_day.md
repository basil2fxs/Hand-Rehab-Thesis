# End of the day

## Check the data (5 min)

- [ ] Every code of the day in one go:

      ```
      python3 app/scripts/check_sitting.py --all
      ```

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

- [ ] The games save into the project's `sessions/` folder (where
      `Local_Runner.command` puts them, and where the notebook looks).
      That folder is gitignored, so nothing in it ever reaches GitHub;
      it does sync to your Google Drive with the rest of the project,
      which is the first backup. Codes only, no names.
- [ ] Copy the day's `sessions/<date>/` folder to one more place (the
      university storage or an external drive) before anything is
      deleted anywhere.
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
