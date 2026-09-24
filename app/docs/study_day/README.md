# Study day kit

Everything needed to run the healthy baseline study: one sitting per
volunteer, one board (the right-hand device), about 60 minutes door to
door. The design and the reasons behind it are in
`docs/research/healthy_baseline_study.txt`; this folder is the part you
print and follow.

| File | When | Print |
|---|---|---|
| [before_the_day.md](before_the_day.md) | once, in the week before | no |
| [run_sheet.md](run_sheet.md) | every participant, beside the laptop | one copy, laminated or in a sleeve |
| [information_sheet.md](information_sheet.md) | handed over on arrival | one per participant |
| [consent_form.md](consent_form.md) | signed on arrival | one per participant |
| [intake_sheet.md](intake_sheet.md) | filled during the sitting | one per participant |
| [debrief.md](debrief.md) | read out at the end | one copy |
| [end_of_day.md](end_of_day.md) | after the last participant | no |
| [intake_sheet_template.csv](intake_sheet_template.csv) | typed up at the end of the day | no |

Two commands do the checking, both from the project folder:

- `python3 app/scripts/check_sitting.py` before each participant
  leaves: READY, or what to fix while they are still there.
- `python3 app/scripts/audio_latency.py --write`: the laptop's sound
  and buzz delays, already measured and saved for this MacBook; run it
  again only on another laptop or another audio output.
- `python3 app/scripts/pad_bench.py`: optional, a counts-per-gram
  figure for the thesis appendix (coins work).

## The one-hour booking

| Minutes | What |
|---|---|
| 0 to 10 | Welcome, information sheet, consent, intake sheet with the Edinburgh short form, hand measurements |
| 10 to 15 | Hands washed, seated, login, quick calibration |
| 15 to 58 | Play all: pass 1 (nine games), a 3 minute rest, pass 2 (three games again). The app measures this at about 43 minutes on the rig including login and calibration |
| 58 to 60 | Results screen, two fatigue questions, end the session, debrief |
| after | Wipe the pads, reset for the next person |

Book 60 minute slots with no gap, and a spare slot every three or four
people for a late start or a board that needs replugging.

## Who can take part

Any healthy adult volunteer, right- or left-handed. The device is the
right hand for everyone. Left-handers are welcome: the analysis pools
everyone and also compares left- and right-handers, so a mix is useful,
not a problem. Participants pick their real main hand at login (the
hand they write with); the research assistant then picks Right hand on
the hand screen for the device.
