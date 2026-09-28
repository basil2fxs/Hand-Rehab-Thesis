# Trial Mode

The login's SESSION picker: Free play, or a sitting of 15, 30, 45 or 60 minutes that runs its games in order from LOG IN. This page is why each length plays what it plays. Measured 28 September 2026.

## The rule

Every length plays the study sitting's own blocks with the study sitting's own settings (`overrides_from: study_battery` in [`config/default.yaml`](../../config/default.yaml)). A Reaction block in a 15 minute sitting is the same task, scored the same way, as pass 1 Reaction in the 45. So a block of one pass pools across lengths, and someone who only had 15 minutes still adds to every number their blocks feed. What changes is which blocks, and how many passes.

The 45 is the pre-registered sitting ([`healthy_baseline_study.txt`](healthy_baseline_study.txt)) and stays the one for the collection day.

## What each block buys

Minutes are the study sitting's measured block times. Checks are the design's pre-specified rows (its Section 4.6).

| Game | Minutes | Checks | Where change shows |
|---|---|---|---|
| Reaction | 2.4 | R1, W1 | Not expected: its drift is the yardstick for every other game's trend |
| Adaptive | 0.5 | A5, A6, objective A1 | A second go: the pace reached |
| Chords | 2.7 | C1, C2, C3, C6, W4 | Inside the block (W4), and a second go |
| Force Pilot | 3.5 | F1 to F4, the Parkinson's table | A second go (the T2 and T3 shift) |
| Syllables | 1.8 | S6, S7, the dyslexia extension | Little: healthy adults sit near its ceiling |
| Rhythm | 2.1 | Rh1, Rh2, objective B1 | A second go |
| Buzz Hunt | 2.4 | B1 to B4, W5 | Inside the block (W5) |
| Echo | 3.1 | E1 | A second go (inside a block the span grows by design) |
| Muscle Memory | 6.3 | P1, P3, W3 | Inside the block (P1), and a second go (P2) |

Fixed costs: 5 minutes for login, seating and calibration, 10 seconds between games, and a 3 minute rest before any second go. A second go is the only way to get test-retest (T1 to T5) and the pass 2 minus pass 1 change, which is where improvement across a sitting shows.

## The four lengths

| Length | Plays | Gives |
|---|---|---|
| 15 | Reaction, Adaptive, Chords, Force Pilot | The anchor, finger independence, force control and the Parkinson's measures: 13 pre-specified rows |
| 30 | The 15 plus Syllables, a rest, then Reaction, Chords and Force Pilot again | The whole reliability table (T1 to T5), R3, the practice shift for the core, the dyslexia checks |
| 45 | The study sitting | Everything pre-registered |
| 60 | The 45 block for block, then Rhythm, Echo, Muscle Memory and Adaptive again | The 45's numbers, plus P2 and an exploratory second-go table |

Why these:

- **The core goes in first.** Reaction, Chords and Force Pilot carry the reliability chapter and what the device is for, and Reaction calibrates every within-block trend.
- **Adaptive is nearly free.** Half a minute for two checks.
- **The 30 spends 11.5 minutes on the rest and three second goes.** Only a second go gives the reliability table, so that beats adding Rhythm or Echo once.
- **The 60's Muscle Memory second go restores P2**, the one pre-registered learning check the 45 dropped for time. Syllables was taken out of the second goes: adults sit near its ceiling, and with it the sitting ran past 60 minutes (median 59.6).

## Timing

Through the real engine with a model participant (`scripts/measure_battery.py --preset trial_30`, and so on): 8 sittings on each of 6 codes, both orders, 2 left-handed, 48 per length.

| Length | Medians, min | Range, min | Over the length | Hard stop |
|---|---|---|---|---|
| 15 | 14.3 to 14.5 | 13.9 to 15.2 | 1 of 48 | 18 |
| 30 | 28.2 to 28.6 | 27.6 to 29.4 | 0 | 35 |
| 45 | 43.9 to 44.3 | 43.4 to 45.2 | 3 of 48, by 9 s at most | 50 |
| 60 | 57.4 to 57.7 | 56.9 to 58.7 | 0 | 65 |

A real sitting adds questions and slower changeovers, about 3 minutes on the 45.

## What mixing lengths costs

- n per game is whoever played it: a 15 minute participant adds nothing to Rhythm.
- Both orders run inside every length, so a game's place in the sitting is balanced within a length but not across lengths.
- The gap between a game's two goes is shorter in the 30, whose first pass is five games instead of nine. The notebook pools the passes, so say which lengths the T rows came from.
- The notebook names each participant's sitting and reads feasibility against that sitting's own budget.

## Recommendation

- **Collection day:** 45 for everyone. The checks and the reliability table need n more than anything else.
- **Someone who can stay 75 minutes:** 60. Nothing of the 45 is lost, and P2 comes back.
- **A short slot:** 30 before 15. Only the 30 keeps the retest.
- **The EEG lab:** no SESSION picker. A length would start its games before the recording is running; the RA starts ActiView from the name the game menu shows, then PLAY ALL runs the lab's sitting as before.
