# 4 Syllables case

The readers with dyslexia, codes D01 upward, each a case of their own and reported apart from the healthy study. Copy each code's dated folders from your computer's `sessions/` in here, as `sessions/`.

## Before the first session

- Consent from the reader; for a child, a parent's consent and the child's own agreement.
- Note the reader's age, how and when dyslexia was identified, first language, and any hearing or vision problem.
- One published reading measure: the Castles and Coltheart test for a child, the Adult Reading History Questionnaire for an adult. Repeat it after the last session if there is time.
- The listening check, once: two adult listeners of Australian English each run `python3 app/scripts/syllables_recording_kit.py listen --listener L1 --device "the headphones" --level "the volume"` (then L2). `listen --report` names any probe set fewer than 90 percent of answers got right; re-render or drop it before the probe is used.

## The sessions

Log in with the code, the reader's real age and SESSION Free play, then the Syllables card. Every sitting opens with the probe, the same sets in the same order every time, with no hints and no feedback.

- Baseline: 3 to 5 sessions on separate days with the probe alone. After its last set, at the WARM UP card, press Esc twice; every answer is kept.
- Training: then sessions with the whole sitting (the probe, then the game). 6 to 9 year olds play 20 words, older readers 30; about 12 to 20 minutes with the probe.
- With three readers, start their training at different times.

One session alone is a case description: it shows the game ran and how the reader played, and nothing about change.

## Each session

- A quiet room, the same closed headphones at the same level every time, checked with the reader before starting.
- Sit beside the reader. Encourage between sections in neutral words, never name or point to an answer, press R only when asked, and note any interruption.
- Before the first block, say: "If a finger buzzes, that is a hint; try first if you can."
- Stop if the reader asks, is upset, or misses three words in a row and is frustrated: end after the word in play (Esc twice).
- Afterwards: it is a practice game, not a test or a treatment, and no number describes reading ability.

## The analysis

Set `SESSIONS_DIR` in `analysis/session_analysis.ipynb` to this folder's `sessions` and Run All. The chapters SYLLABLES: THE CASE SITTING and SYLLABLES: THE PROBE are the case.
