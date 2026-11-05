# deep

One review per game, from October 2026, reading the sources each game leans on in full rather than their abstracts. Each sets the game's parameters, scoring and analysis against the evidence, ranks what to change, and marks every source as read in full, abstract only or record only. Read a game's review before changing its numbers: most settings in `config/default.yaml` that look odd have their reason here. Codes like R1 or Rh1 are the checks named in the study design.

| File | Game | The main changes |
| --- | --- | --- |
| [`reaction.md`](reaction.md) | Reaction, the study's first block | The task stayed as it was; R1 became one-sided, failing only when reaction time falls as the wait grows, and claims were corrected |
| [`rhythm.md`](rhythm.md) | Rhythm | Rh1 became the share of presses more than 150 ms late, where a reaction to the buzz would land, and the study's chart was frozen with its notes on the music's attacks |
| [`echo.md`](echo.md) | Echo | Two silent misses end a game rather than the block, everyone gets the same sequences, and the mean of two games is the headline |
| [`force_pilot.md`](force_pilot.md) | Force Pilot | The centre line is drawn and followed, and F1 and F2 were rebuilt around the irregular and repeating waves |
| [`chords.md`](chords.md) | Chords | At light presses most of the leak into other fingers comes before the press, so the leak measures became exploratory beside a press-locked one |
| [`buzz_hunt.md`](buzz_hunt.md) | Buzz Hunt | The timed sessions play one 2.0 s window with three catch trials, B5 was dropped and B2 became exploratory |
| [`pattern.md`](pattern.md) | Muscle Memory | A paper awareness check before the debrief, and no sequence-recall game straight before it |
| [`adaptive.md`](adaptive.md) | Adaptive | A late answer just after the next cue counts for its own trial, presses under 100 ms don't count, and the steady pace is read beside the peak |
| [`syllables.md`](syllables.md) | Syllables, the dyslexia case | Every case sitting opens with a fixed probe that never adapts or gives feedback, so a reader's sittings form an A-B series |
| [`mirror.md`](mirror.md) | Mirror, two-board rig only | Described as two-hand training, not mirror therapy; each board's samples keep their own time stamps, and the gap between the hands is reported several ways |
| [`srt.md`](srt.md) | The lab's SRT, Lab session only | The copy matches the lab's script frame for frame and plays first in the Lab session, with a response byte per trial and a neutral setup screen |

What each change did to the pre-registered design is logged, dated, in [`../healthy_baseline_study.txt`](../healthy_baseline_study.txt) under HOW THE DESIGN GOT HERE.
