# Trial Mode

The login's SESSION picker: Free play, or a sitting of 15, 30, 45 or 60 minutes that runs its games in order from LOG IN. This page is why each length plays what it plays. Redesigned on 28 September 2026 and again on 2 October 2026.

No length plays Syllables. It is built for readers with dyslexia, the study's participants are healthy students, and the author runs it with a dyslexic participant on its own, from the hub.

## The rule

The study expects about ten students, each sitting one length once. With so few people, every block has to count. So every length plays the study sitting's own full-length games, with its counts and settings, and a length plays fewer games rather than shorter ones. A block from any length is then the same measure as the same block from every other, the notebook pools them all, and each student counts toward every check their games feed.

The notebook prints a check's statistics from 8 people (with about nine checks under Holm, the one-sided exact test first clears its threshold at eight). A game played twice in one sitting adds the change from the first go to the second and a test-retest estimate, so the 45 and the 60 still play games twice.

## The games

Minutes are measured through the real engine with a model participant.

| Game | Block | Minutes | Where improvement shows |
|---|---|---|---|
| Reaction | 20 trials | 2.4 | Not expected: it is the control, so its change is warm-up |
| Rhythm | the song | 2.1 | A second go |
| Echo | 2 games read by their mean | 3.1 | A second go; inside a block the span grows by design |
| Force Pilot | 12 waves | 3.5 | A second go; Storm against Uncharted separates learning these waves from getting used to the pad |
| Chords | 40 chords | 2.7 | Inside the block, and a second go |
| Buzz Hunt | 16 + 3 catch + 4 trials | 2.8 | Inside the block, and a second go |
| Muscle Memory | 296 presses | 6.3 | Inside the block (P1), and a second go (P2) |
| Adaptive | 40 trials | 0.5 | A second go: the pace reached |

Fixed costs: 5 minutes for login, seating and calibration, 10 seconds between games, and a 3 minute rest before the second goes.

## The four lengths

| Length | Plays | Games twice | Checks it feeds |
|---|---|---|---|
| 15 | Reaction, Force Pilot, Chords and Adaptive once | none | The four games' first-pass checks |
| 30 | All eight once: the 45's first pass | none | Every first-pass check |
| 45 | All eight, a 3 minute rest, then Reaction, Rhythm, Force Pilot and Chords again | 4 | Every first-pass check, R3 and the reliability rows |
| 60 | The 45, then Echo, Buzz Hunt, Muscle Memory and Adaptive again | all 8 | All of the 45's, P2 and the second-go table |

Why these:

- **15:** the core games. Reaction is the anchor every other timing is read against, Chords and Force Pilot are the two measures the device is built around, and Adaptive, the shortest game, fits beside them. They play in the order the 45 plays them.
- **30:** every game once, so every first-pass check gets this student. A second go at full length does not fit beside all eight.
- **45:** the study sitting.
- **60:** every game twice at full length. Muscle Memory's second go brings P2 back.

## What ten students give

A first-pass check counts everyone whose sitting played its game; R3 and the reliability rows count the 45s and the 60s; P2 counts the 60s. So with ten students:

- The checks on Reaction, Chords, Force Pilot and Adaptive have all ten, whatever the lengths.
- The checks on Rhythm, Echo, Buzz Hunt and Muscle Memory reach 8 while no more than two students sit the 15.
- R3 and the reliability rows reach 8 while no more than two sit the 15 or the 30.

Checked end to end on 2 October 2026: ten simulated students (two 60s, four 45s, two 30s, two 15s) through the real engine and the notebook pooled all ten, with no block left out. The four core games' checks ran on 10 people, the other four games' on 8, and R3 on 6, under the minimum, as the rule above says. Under the design of 28 September the same ten split into 6 full-length and 4 shortened, and no check reached 8.

## Timing

The shipped config, eight sittings on each of six codes, both orders, two left-handed: 48 per length. Medians are per code.

| Length | Medians, min | Range, min | Past the length | Hard stop |
|---|---|---|---|---|
| 15 | 14.2 to 14.5 | 13.9 to 15.2 | 2 of 48, by 13 s at most | 18 |
| 30 | 29.2 to 29.5 | 28.7 to 30.1 | 1 of 48, by 4 s | 35 |
| 45 | 44.4 to 44.9 | 43.8 to 45.6 | 10 of 48, by 33 s at most | 50 |
| 60 | 58.5 to 58.9 | 57.5 to 59.7 | 0 | 65 |

The 15 and the 30 were timed on 2 October 2026, the 45 and the 60 on 1 October 2026. The games draw fresh material every block, so no two sittings take the same time; a second batch of the same settings moved a code's median by up to half a minute, so plan on the ranges.

A real sitting adds questions and slower changeovers, about 3 minutes on the 45. The EEG lab's sitting, the same order with the lab's Reaction task in place of both Reaction blocks and no Muscle Memory, times at a median of 48.1 minutes over 12 sittings.

## Reading the results

- **One family.** Every length writes full-length blocks, and the notebook reads them together by default. `COHORT_FAMILY = "short"` remains only for blocks written by the 15 and the 30 between 28 September and 1 October 2026, which played shortened games; none were collected from participants.
- **Improvement** is each game's second go minus its first, from the 45 and the 60. Reaction, Force Pilot and Chords are the T rows; the rest are the second-go table. Read each against Reaction's own change, the warm-up.
- **P2** is tested for whoever sat the 60.
- **S6 and S7**, the Syllables checks, print as DROPPED with the reason: Syllables runs on its own with a dyslexic participant.

## Recommendation

- **Each student:** the longest length their slot allows. Hour-long slots first: the 45 and the 60 are the only lengths that feed R3 and the reliability rows.
- **Someone who can stay 75 minutes:** 60. Nothing of the 45 is lost, and every game shows its change.
- **A short slot:** the 30 before the 15. The 30 plays every game, the 15 four of them. Keep it to two students on the 15 or the 30 between them, and every check keeps its 8.
- **The EEG lab:** no session lengths. A length would start its games before the recording is running, so the RA starts ActiView from the name the game menu shows, then the hub's Lab session runs the lab's sitting.
- **Syllables:** from the hub, with a dyslexic participant, on its own.

## History

From 28 September to 1 October 2026 the 15 and the 30 played shortened games of their own (family short: 12 reaction trials, 20 chords, six Force Pilot waves, half of Buzz Hunt and Muscle Memory, one Echo game), so more games fit twice: the 15 played Reaction, Chords and Force Pilot twice, the 30 all eight and then four again. A shortened game is not the same measure, so those blocks could never pool with the 45 and the 60. With ten students that split the cohort, and on 2 October 2026 every length moved to the study's own games.
