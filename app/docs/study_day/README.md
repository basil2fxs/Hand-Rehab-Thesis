# Study day kit

Everything needed to run the healthy baseline study with a research assistant in the room: one sitting per volunteer on one board, the right-hand device. The design and the reasons behind it are in `docs/research/healthy_baseline_study.txt`; this folder is the part that gets printed and followed. (The October 2026 sittings were run by the students themselves from a one-page sheet instead; that procedure is in [FINAL TRIAL RESULTS](../../../FINAL%20TRIAL%20RESULTS).)

| File | When | Print |
|---|---|---|
| [before_the_day.md](before_the_day.md) | once, in the week before | no |
| [run_sheet.md](run_sheet.md) | every participant, beside the computer | one copy, laminated or in a sleeve |
| [information_sheet.md](information_sheet.md) | handed over on arrival | one per participant |
| [consent_form.md](consent_form.md) | signed on arrival | one per participant |
| [intake_sheet.md](intake_sheet.md) | filled during the sitting | one per participant |
| [debrief.md](debrief.md) | read out at the end | one copy |
| [end_of_day.md](end_of_day.md) | after the last participant | no |
| [intake_sheet_template.csv](intake_sheet_template.csv) | typed up at the end of the day | no |

Two checks keep a sitting usable:

- `python3 app/scripts/check_sitting.py` before each participant leaves. It reads the session folders the game just wrote and prints READY, or what to fix while the person is still there: a game missing from the plan, Test Mode left on, a board that dropped out, a Rhythm block run before this computer's delays were measured.
- Settings, Setup, Audio delay, once on each computer (the lab PC too) and each audio output, before anyone plays Rhythm.

## The booking

Book the longest length the person can give: an hour for the 45 minute session, 75 minutes for the 60, less for the 30 or the 15. About 15 minutes of any booking is welcome, paperwork and debrief. The hour for the 45 runs like this:

| Minutes | What |
|---|---|
| 0 to 10 | Welcome, information sheet, consent, intake sheet with the Edinburgh short form, hand measurements |
| 10 to 15 | Hands washed, seated, login, quick calibration |
| 15 to 58 | The 45 minute session: pass 1 (eight games), a 3 minute rest, pass 2 (four games again). The app measures this at about 44 minutes on the rig, login and calibration included |
| 58 to 60 | Results screen, two fatigue questions, end the session, debrief |
| after | Wipe the pads, reset for the next person |

Book the slots back to back, with a spare one every three or four people for a late start or a board that needs replugging.

## Who can take part

Any healthy adult volunteer, right- or left-handed. The device is the right hand for everyone. Left-handers are welcome: the analysis pools everyone and also compares left- and right-handers, so a mix helps. Participants pick their real main hand at login (the hand they write with); the research assistant then picks Right hand on the hand screen for the device.
