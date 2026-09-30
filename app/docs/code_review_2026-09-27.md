# Code review of 27 September 2026

A line-by-line review of every mode, the two laboratory tasks and the shared engine and battery, before any participant. Ten reviews returned 103 findings: 100 were fixed, two were kept as deliberate choices and one was not a fault. This is every finding that changed the software or the analysis, by mode, with what it would have done. Each fix has a test that fails on the code as it was. Thesis Section 4.10.2 keeps the sixteen that would have changed a study number.

| Mode | Finding | What it would have done |
|---|---|---|
| Reaction | A board drop mid-trial was scored as a miss and a lapse | A loose plug read as a lapse of attention |
| Reaction | Check R1 read the median of the absolute correlation | A working foreperiod failed the check 28 percent of the time |
| Reaction | Pass 1 numbers were shown on screen during pass 2 | The retest was contaminated, against Section 3.5 |
| Reaction | Fingers were dealt from a bag of four | A quarter of the cues could be worked out from the three before |
| Force Pilot | A run restarted after a pause took its zero from the force frozen at the pause | A perfectly flown run scored 10 percent time in corridor |
| Force Pilot | Runs the game had voided for lost signal were re-scored beside their replays | The same rung counted twice, once from a dead board |
| Force Pilot | The corridor-exit EEG byte was tied to a buzz no configuration turns on | The laboratory's feedback record for the mode was empty |
| Force Pilot | The spectral measure had three definitions and cited the wrong journal | The same runs read 2.00 in one table and 0.67 in another |
| Chords | Forces in newtons were divided by references in counts | Pressing too hard could never be flagged |
| Chords | The row label followed the first finger's speed, not the outcome class | Most healthy clean chords read as late; the clean hit rate was a speed rate |
| Chords | Partial and wrong-finger chords counted as enslaving | Three misread cues changed which finger was most enslaved |
| Chords | Check C2 gave the four-finger chord a made-up enslaving ratio | The check hid its enslaving half whenever hit rate sat at ceiling |
| Rhythm | The cue tone was played at the beat and heard 77 ms after it | A second pacing signal 70 ms after the music and the buzz |
| Rhythm | Notes missed while the board was away counted as misses | A 2.5 s drop read as three misses and a broken streak |
| Rhythm | The song's play call landed up to a frame after the beats assumed | Every asynchrony in a block shifted late by 0 to 16 ms |
| Rhythm | Notes closed on the uncorrected clock | The late tier ended at 213 ms instead of 300 |
| Rhythm | The lag-1 check expected the sign Wing and Kristofferson predict for intervals | A healthy tapper failed the check and was described as drifting |
| Rhythm | The 39 ms reference was an absolute asynchrony in a Parkinson's group | The spread was compared with the wrong quantity from the wrong group |
| Muscle Memory | A trial lost to a board drop counted as a miss and as fatigue | A 12 s drop forced a rest; a second drop ended the block |
| Muscle Memory | Every block without a sequence file was labelled as a failed file | The analysis warned of a fallback on every study block |
| Buzz Hunt | Localisation RT ran from the frame before the buzz command | Every RT 17 ms short at 60 Hz, against the EEG byte |
| Buzz Hunt | Catch trials were drawn per trial inside the sixteen | A fifth of blocks had no false-alarm measure |
| Buzz Hunt | Check W5 needed eight trials at a level the ladder leaves after six | The check could never be decided on a healthy hand |
| Buzz Hunt | Check B2's reference was exactly chance | Pure guessing passed half the time |
| Buzz Hunt | A gap threshold was reported for a stage the study does not play | A phantom 320 ms threshold in every block |
| Echo | A silent turn while the board was away spent the spare life | A four second drop ended a game at span 0 |
| Echo | Press offsets went negative across a pause and inside a fast reply | A 30 s pause read as a 29 s interval between two presses |
| Echo | Check E2p was decided by two criteria in two tables | The same misses could pass in one table and fail in the other |
| Echo | The per-selection checks did not know the one-board rig | E3 was given a verdict the design had dropped |
| Syllables | A right answer given after the prompt buzz lowered the foil rung | Eight of twelve simulated blocks drifted off the rung the design pins |
| Syllables | A set that timed out while the board was away counted as a miss | The word was parked and the streak broken on a rig fault |
| Syllables | A pause on the finished-word card replayed the word | Every set of the word logged twice |
| Syllables | A press inside the spawn lockout left no marker while the set got a timeout byte | The EEG record said no press where one had landed |
| Mirror | The analysis counted wrong-finger trials as clean pairs | The synchrony gap disagreed with the game's own summary |
| Mirror | Every block drew the same finger order and recorded no seed | A repeat block was predictable finger by finger |
| SRT | A pause inside a trial logged an ordinary trial with a moved onset | A reaction time measured from the resume, not the flash |
| SRT | A silent trial the board was away for counted as a miss | A rig fault entered the accuracy and error rate |
| Battery | A board picked as Left at login was renamed but the hand was not switched | The calibration could not finish and the sitting ran on the previous participant's thresholds |
| Battery | A relaunch inside the rest started the next block at once | The one rest the retest depends on was logged as zero |
| Battery | The session clock ran from the start of the battery, not from login | The late warning came five minutes late |
| Battery | Enter on the results screen replayed the block just played | An unstamped extra block cost the sitting minutes |
| Simulator | The model hand's calibration, tap force and resting level were unrealistic | The app's own check refused the profile; presses registered 10 to 13 ms late |
