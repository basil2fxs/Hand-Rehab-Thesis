# Analysis

`session_analysis.ipynb` reads what the game records and produces the figures and
numbers for the thesis. The work itself lives in `rehab_analysis.py`, which keeps
the notebook short and lets the same functions run from a plain script.

## Running it

```
pip install jupyter pandas numpy matplotlib ipywidgets
cd analysis
jupyter notebook session_analysis.ipynb
```

Click a save in the dropdown near the top, then run the cells under it. No
typing. The list is newest first with friendly dates (today, yesterday, Monday),
and offers three scopes: one game, one session, or one person across every day
they played.

Choosing only sets the selection. Each cell below it runs one section and prints
its own result underneath, so the working stays visible. Until you choose
anything the newest game is used.

`report("latest")`, `report(3)`, `report("Basil")` and the rest still work from a
script or a plain shell, and `catalogue()` prints the same list as a table.

## Picking what to analyse

A **game** is one folder, meaning one block of one mode. A **session** is one
person on one day.

| To analyse | Use |
|---|---|
| most recent game | `report("latest")` |
| one game | `report(3)` |
| a few games | `report([0, 2, 5])` |
| a whole session | `report("2026-07-29  Basil")` |
| everyone on a day | `report("2026-07-29")` |
| one person, every day | `report("Basil")` |
| one mode only | `report("adaptive")` |
| everything | `report("all")` |

Filters stack, so `report(["Basil", "rhythm"])` gives every rhythm game that
person played. Select more than one game and it compares them side by side.

## What comes out

- `figures/` PNGs at 160 dpi, sized to drop into the report
- `session_summary.csv` the headline numbers
- `selected_trials.csv` every trial in the selection
- `individuation_per_trial.csv` per-trial finger isolation

`report` also returns everything it built, so you can keep working with
`res["trials"]`, `res["rt"]`, `res["force"]`, `res["individuation"]`,
`res["rhythm"]`, `res["comparison"]` and `res["summary"]`.

## Sections in the report

Overview and dose, data quality, per-game comparison, reaction time, accuracy
against the 65 to 80 percent challenge band, force, finger individuation, rhythm
timing, both hands, and the 200 Hz raw stream.

Sections that do not apply skip themselves with a note, so a keyboard-mode session
or a non-rhythm block will not throw errors.
