# Trial Mode

The login's SESSION picker: Free play, or a sitting of 15, 30, 45 or 60 minutes that runs its games in order from LOG IN. This page is why each length plays what it plays. Redesigned 28 September 2026.

No length plays Syllables. It is built for readers with dyslexia, the study's participants are healthy students, and the author runs it with a dyslexic participant on its own, from the hub.

## The rule

Improvement needs repetition. A game played twice in one sitting, the same way both times, gives two things one game cannot: the change from the first go to the second, and a test-retest estimate of how repeatable the game is. So every length plays as many games twice as its minutes allow.

To fit more games twice into the 15 and the 30, their games are shortened: same task, same scoring, fewer trials. The 45 and the 60 keep the study sitting's full-length games. Each block records its family, full or short, and the notebook reads one family at a time, because a shortened game is not the same measure as a full one.

## Full and short games

Minutes are measured through the real engine with a model participant.

| Game | Full | Short | Where improvement shows |
|---|---|---|---|
| Reaction | 20 trials, 2.4 min | 12 trials, 1.3 min | Not expected: it is the control, so its change is warm-up |
| Rhythm | the song, 2.1 min | the same | A second go |
| Echo | best of 2 games, 3.1 min | 1 game, 1.5 min | A second go; inside a block the span grows by design |
| Force Pilot | 12 waves, 3.5 min | 6 waves, 1.9 min | A second go; Storm against Uncharted separates learning these waves from getting used to the pad |
| Chords | 40 chords, 2.7 min | 20 chords, 1.1 min | Inside the block (full only), and a second go |
| Buzz Hunt | 16 + 4 trials, 2.6 min | 8 + 2 trials, 1.4 min | Inside the block, and a second go |
| Muscle Memory | 296 presses, 6.3 min | 204 presses, 4.9 min | Inside the block (P1), and a second go (P2) |
| Adaptive | 40 trials, 0.5 min | the same | A second go: the pace reached |

The short Force Pilot flies six waves the mode file names: Tide, Stairs, Hills, Dunes, Storm and Uncharted. They keep a ramp and hold, the steps, the fast release, and the learned-against-novel pair. The config can switch between the two ladders but cannot list levels.

What shortening costs: fewer trials make each block noisier, Chords needs its full two halves for its inside-the-block reading, and Echo loses its best-of-two.

Fixed costs: 5 minutes for login, seating and calibration, 10 seconds between games, and a 2 or 3 minute rest before the second goes.

## The four lengths

| Length | Family | Plays | Games twice |
|---|---|---|---|
| 15 | short | Reaction, Chords, Force Pilot, then the same three again | 3 |
| 30 | short | All eight, a 2 minute rest, then Reaction, Force Pilot, Chords and Adaptive again | 4 |
| 45 | full | All eight, a 3 minute rest, then Reaction, Rhythm, Force Pilot and Chords again | 4 |
| 60 | full | The 45, then Echo, Buzz Hunt, Muscle Memory and Adaptive again | all 8 |

Why these, from the candidates timed (one sitting each):

- **15:** the most repetition in the least time. Reaction is the control, and Chords and Force Pilot are the two measures the device is built around. The second go follows straight on; a rest took it past 15. With a 1 minute rest, adding Adaptive ran 16.7 minutes, and Buzz Hunt and Adaptive in place of Force Pilot ran 15.4.
- **30:** every game once, so all eight carry their first-go checks, Muscle Memory's learning score included; then the reliability core (Reaction, Force Pilot, Chords) and Adaptive, the shortest game, twice. Seven games twice without Muscle Memory ran 29.6 minutes but lost its learning score; all eight twice ran 39.9.
- **45:** the study sitting. The 1.75 minutes Syllables gave back went to a second go at Rhythm, whose asynchrony is expected to be repeatable; a second Adaptive would only repeat a ceiling. A second Buzz Hunt and Adaptive instead ran 45.8.
- **60:** every game twice at full length. Every game gets its improvement reading and a test-retest, and Muscle Memory's second go brings P2 back.

## Timing

The shipped config, eight sittings on each of six codes, both orders, two left-handed: 48 per length. Medians are per code.

| Length | Medians, min | Range, min | Past the length | Hard stop |
|---|---|---|---|---|
| 15 | 14.4 to 14.8 | 14.0 to 15.3 | 4 of 48, by 17 s at most | 18 |
| 30 | 28.0 to 28.5 | 27.7 to 29.3 | 0 | 35 |
| 45 | 44.1 to 44.9 | 43.9 to 45.1 | 2 of 48, by 5 s at most | 50 |
| 60 | 58.3 to 58.7 | 57.8 to 59.5 | 0 | 65 |

The games draw fresh material every block, so no two sittings take the same time. A second batch of the same settings moved a code's median by up to half a minute (the 45 came out at 44.2 to 44.4, one sitting past by 11 s; the 15 at 14.4 to 14.8, eight past by 15 s at most), so plan on the ranges.

A real sitting adds questions and slower changeovers, about 3 minutes on the 45. The EEG lab's sitting, the same order with the lab's Reaction task in place of both Reaction blocks, times at a median of 54.6 minutes over 12 sittings.

## Reading the results

- **One family at a time.** The notebook reads the full family by default: the 45, the 60 and the lab. Set `COHORT_FAMILY = "short"` in its setup cell to read the 15 and the 30.
- **Improvement** is each game's second go minus its first. Reaction, Force Pilot and Chords are the T rows; the rest are the second-go table. Read each against Reaction's own change, the warm-up.
- **P2** is tested for whoever sat the 60.
- **S6 and S7**, the Syllables checks, print as DROPPED with the reason: Syllables runs on its own with a dyslexic participant.

## Recommendation

- **Each student:** the longest length their slot allows (28 September 2026). The checks and the reliability table come from the full family, the 45 and the 60, so hour-long slots come first.
- **Someone who can stay 75 minutes:** 60. Nothing of the 45 is lost, and every game shows its change.
- **A short slot:** 30 before 15. Only the 30 plays every game. The short family is read on its own and needs 8 of its own.
- **The EEG lab:** no SESSION picker. A length would start its games before the recording is running, so the RA starts ActiView from the name the game menu shows, then PLAY ALL runs the lab's sitting.
- **Syllables:** from the hub, with a dyslexic participant, on its own.
