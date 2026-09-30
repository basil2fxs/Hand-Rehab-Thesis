# Rhythm mode: deep research audit

30 September to 1 October 2026. Scope: the study battery's Rhythm step (`app/finger_rehab/game/modes/rhythm.py`, mode key `rhythm`), the chart builder (`app/finger_rehab/audio/beatmap.py`), the scheduler, the `rhythm:` and `latency:` config, the latency tooling, `RhythmScreen`, logging and the notebook analysis. Free play (the song picker and the adaptive buzz lead) is covered only where it bears on the study block.

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the stated assumptions (listed at the end); "(track analysis)" is computed on a scratch copy of `Easy_Lemon.mp3` with a copy of the repository's `beatmap.py` and librosa 0.11.0, the version installed on the development Mac; "(takes)" is the saved latency takes file `app/config/calibration/audio_latency_20260924_121500.csv`; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository. Line numbers refer to commit 86c8124; `screens.py` and the notebook were being edited in the working tree during this review, so functions are named as well. Notebook line numbers are lines of the source of cell index 2.

---

## 1. What the mode does now

### 1.1 The block under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Place in the sitting | Order A steps 2 and 10 (straight after Reaction), order B steps 6 and 12 (straight after Reaction) | Easy_Lemon.mp3, medium, both passes | `default.yaml` 1956-1989 |
| Chart | Built at block start from the mp3: librosa onset envelope and dynamic-programming beat tracker, beats ranked by onset strength, top 35 percent kept, gaps under 0.42 s thinned, gaps over 3.2 s backfilled, lanes in the fixed cycle index, middle, ring, little, middle, ring, index, little | 107 notes (track analysis) | `beatmap.py` 95-139, 166, 334-426; `engine._begin_protocol_rhythm` 6701-6721 |
| Start | GET READY card with a number counting down, welded to the note timeline; then a silent 2.0 s lead while the first notes fall; audio starts at song time 2.0 s and the play call's frame lag is absorbed into the clock | 3.0 s + 2.0 s | `default.yaml` 599, 1615; `rhythm.py` 176-186, 531-563 |
| Note display | Each note is in view 2.2 s ahead and falls 370 logical px (from y 140 to the strike line at y 510 on the 1280x800 surface), 168 px/s (arithmetic); drawn on `display_song_time`, which runs `latency.visual_ms` (20 ms, an estimate) ahead and the audio offset behind; ring thickens from 0.4 s before to 0.2 s after the note; note radius 30 px, 34 px within 0.3 s | 2.2 s lookahead | `screens.py` `RhythmScreen` (`LOOKAHEAD_S` 4330, 4648-4711, 4760); `rhythm.py` 318-327 |
| Cues at each note (study) | Falling note; lane tone (pure sine, 120 ms, C4 261.63, E4 329.63, G4 392.00, C5 523.25 Hz, index to little) sent `latency.tone_ms` early so it is heard at the scored zero; buzz under the target finger, STIM sent `latency.buzzer_ms` early so the motor starts at the scored zero, held 250 ms; the song | tone 77 ms early, buzz 74 ms early (study MacBook) | `audio/engine.py` 103-105, 605-619; `rhythm.py` 584-621; `default.yaml` 388, 398, 493, 2039; `latency_profile.yaml` 13-14 |
| Loud notes | About one stimulus in ten plays its tone 35 percent louder, as in every mode | fraction 0.10, boost 1.35 | `default.yaml` 1835-1837; `engine.on_tone_lead` 8508-8533 |
| Scored zero | Note time plus `rhythm.audio_offset_ms` | 87 ms measured on the study MacBook (default 40) | `rhythm.py` 651-685; `latency_profile.yaml` 16; `default.yaml` 1635 |
| Press | Stamped when the EMA-smoothed pad value (alpha 0.35) crosses 30 percent of the finger's calibrated light-press travel (with noise and preload floors), debounce 100 ms; timed from its own `t_perf` | trigger at 30 percent of travel | `calibration_profile.py` 50, 99; `fsr_detector.py` 78, 93, 307-323; `rhythm.py` 402-415 |
| Matching | Nearest unhit note on the same lane in -300 to +600 ms of its zero; a note closes 300 ms after its zero on the corrected clock, so the usable window is -300 to +300 ms | | `rhythm.py` 635-643, 687-762 |
| Labels and points | Absolute offset at or under 50 ms Perfect 10, 100 Great 6, 175 Good 3, 300 Late or Early 1, else Miss 0; streak multiplier up to 1.5 | 50/100/175/300 ms | `scoring.py` 71-100; `default.yaml` 1622-1625; `engine._streak_multiplier` 8079-8086 |
| Wrong or idle press | Unmatched press: wrong-press penalty, grey flash, logged `rhythm_spurious_press`; EEG byte says wrong finger or idle | | `rhythm.py` 731-748; `engine.log_rhythm_unmatched` 9931 |
| Feedback | Lane and ring flash 0.6 s: gold for Perfect, green for Great, Good, Late and Early, grey for Miss; particle burst on hits; no words per press in the encouraging style; score and streak chip; banners at 10, 20, 30, 50, 75 and 100 in a row (Rhythm is not in the quiet list); no chime (`cue.sound_after` off) | | `engine._outcome_colour` 8030-8048, `_feedback_popup` 8326-8342, `_ENCOURAGEMENT` 8453-8461; `screens.py` `RhythmScreen.add_encouragement` 4469; `default.yaml` 415 |
| End | Block ends 1 s after the last note (track time 117.1 s); the last 8.2 s of the 126.4 s track are not played (arithmetic) | measured block 2.05 min | `scheduler.py` 116-117; `beatmap.py` 56-58; design doc Section 2.3 table |
| Results | AVG OFFSET and BEST OFFSET show the mean and smallest absolute offset (no direction) | | `screens.py` 6971-6979 |
| Instructions | NEXT UP card line "Press in time with a song"; the GET READY card carries its heading and the count only; the run sheet has no Rhythm line beyond "Press lightly, like typing" | | `screens.py` 1534, 4816-4865; `docs/study_day/run_sheet.md` |

### 1.2 The study chart (track analysis)

- Tempo. librosa's tracker reports 161.5 BPM and places beats 348 or 371.5 ms apart (15 or 16 frames of 23.2 ms; mean 365.9 ms over the song). The composer's own record (incompetech `pieces.json`, "Easy Lemon", ISRC USUAN1200076) lists 82 BPM, 2:06, guitar, bass, drum kit, celesta and marimba. A comb search over a percussive onset envelope finds the song's pulse at 731.6 ms (82.0 BPM). The tracker therefore runs at the eighth-note level, double the beat. `assets/music/ATTRIBUTION.md` line 10 says "~120 BPM, jazzy, swing feel"; the folded onset envelope has its second peak at half the beat, so the eighths are straight, not swung.
- Metrical position. 90 of the 107 notes sit on the quarter-note beat and 17 (15.9 percent) on the off-beat eighth. 14 of the 17 are syncopated accents that ranked in the top 35 percent by onset strength (60th to 90th percentile); 3 came from the gap backfill (one at the 18th percentile). The strong-beat filter gave 100 notes and the backfill added 7; the medium stride of 2 is only a fallback for a filter that keeps under 56 notes here, and it did not fire.
- Gaps. 69 of the 106 gaps are one beat (732 ms); 18 are 1.5, 2.5 or 3.5 beats (a switch between on-beat and off-beat); 17 exceed 1.8 s and 8 exceed 2.4 s. Minimum 697 ms, median 743 ms, maximum 2926 ms, as the docstring says.
- Structure. The first 30 s differs from the rest: 17 notes, median gap 2.02 s, 5 off-beat. The next three 30 s windows hold 29, 34 and 27 notes with a median gap of 743 ms. The first note falls at 0.07 s of the track, so it lands with no music before it; the second is off-beat. Lanes get 27, 27, 27 and 26 notes.
- Where the chart's zero sits. Each note time minus the attack of the nearest high-frequency transient (above 2 kHz, 2 ms RMS envelope, the point where the rise reaches 20 percent): median +36.9 ms, interquartile range +30.2 to +41.5 ms, per-note SD 7.8 ms; +32.6 to +37.2 ms at thresholds from 10 to 90 percent of the rise. The same detector places known synthetic onsets within 1 ms. On synthetic tracks with known onsets the unmodified librosa pipeline puts beats a median +26 ms after click and kick onsets (IQR +20.5 to +31.8 ms), and +40, +52 and +58 ms after tones with 10, 30 and 60 ms linear rises (simulation). The cause is framing: librosa 0.11's `onset_strength_multi` shifts the envelope by lag plus `n_fft // (2 * hop_length)`, 3 frames, and frames are 23.2 ms (code, library source).

### 1.3 Latency compensation and the lead

- Study MacBook profile, measured 24 September 2026 by `scripts/audio_latency.py --write`: song path 87 ms from the play call, short sound 77 ms, motors 74 ms from STIM to the acoustic onset of the motor, microphone delay 31.5 ms taken from CoreAudio's reported fixed input latency (`latency_profile.yaml` 1-17; `latency_measure.py` 78-134, 381-453). The five song takes ran 81.1 to 89.9 ms after the microphone delay (SD 3.9 ms) and the click takes had SD 5.7 ms (takes, arithmetic). The song path is found by cross-correlating the recorded envelope with the decoded file over the first 8 s (`latency_measure.py` 192-213), so any decoder offset between pygame and libsndfile is inside the 87 ms.
- The display lag is not measured (`latency.visual_ms` 20, an estimate; `default.yaml` 1757-1768). The felt onset of the buzz is not measured; 74 ms is where the averaged motor sound clears 5 SD of the noise.
- The study runs on the lab PC (design doc line 9), which has no measured profile; unmeasured, the game runs on the defaults (song 40 ms, tone 12 ms, buzzer 45 ms) (`default.yaml` 1635, 1756, 1774; `docs/study_day/before_the_day.md` Section 3).
- The lead. In free play (`rhythm.tactile_mode: lead`) the buzz goes 350 ms plus the motor rise ahead of the beat and adapts every 4 scored presses by half the median of the last 8 offsets, at most 25 ms a step, with a 5 ms dead-band, carried across blocks (`rhythm.py` 72-110, 221-247, 764-808; `default.yaml` 1640-1711). The battery overrides `tactile_mode` to `on_beat` (`default.yaml` 2029-2039; the override is flattened to `rhythm.tactile_mode` by `battery.apply_overrides`, `battery.py` 416-436, and inherited by the 30 and 60 minute presets through `overrides_from`, 264-289). With `on_beat` the lead is 0, adaptation is off and a carried lead is ignored (`rhythm.py` 221-247). Nothing person-dependent enters the study score: the audio offset is a fixed per-machine constant and the start-lag correction is a device correction (code).
- Pause. A pause stops the audio; resume replays the mp3 from the paused position with a new play call (`engine._pause_now` 1103-1142, `_resume_now` 1186-1216). The start-lag correction of `RhythmMode.update` is not reapplied and mp3 seeking in pygame "may snap to the nearest frame" (code comment); one mp3 frame is 1152 samples, 26 ms at 44.1 kHz (arithmetic).

### 1.4 Logging and block summary

Every note writes a row (`engine.log_rhythm_hit` 9647-9929): `time_difference_ms` (signed offset), `early_late` label, `loud_trial`, `waveform_params` (tactile mode, lead, rise compensation), `cue_flags`, force columns, and `song_time_s`. `song_time_s` is the live song clock when the row is written (`engine` 9823-9836 with `_trial_context` 9421-9469): the drain time of the press, on the raw clock, not corrected for the audio offset, and for an unpressed note the moment it expired. No column holds the note's own chart time. The block summary holds `beat_offset_stats` (mean, SD, absolute mean, `chart_ioi_cv`, `entrainment_lag1_r`, `interval_resid_lag1_r`), `tap_variability_cv`, `tap_variability_rel_cv`, the song record (source, applied offset, tone lead, start lag) and the song title, bpm and note count (`engine` 5940-5958, 6238-6300). The note list itself and a hash of it are not stored.

### 1.5 Registered checks and the notebook

- Rh1 (design doc Section 1.6; `_mean_check` call at cell 2 lines 24168-24190): cohort per-person mean asynchrony below zero, one-sided Wilcoxon signed-rank on per-person means (`cohort_paired` 21985 via `cohort_one_sample` 22078), in the Holm family of eight (modes-review, "Reliability and the Holm family"). The detail text adds the chart-lag and tactile-pacing caveats and the board-clock sensitivity (`press_late_mean` 9247).
- Rh2: cohort median of per-person asynchrony SD inside 10 to 100 ms; declared a feasibility check on 30 September.
- Rh3 dropped (one board); Rh-wk descriptive; Rh-ras not available.
- Per-person metrics (`_cohort_rhythm` 20498): `asyn_mean_ms`, `asyn_sd_ms`, `asyn_abs_mean_ms`, `asyn_rsd_ms` (1.4826 x MAD), `asyn_mean_ms_grid` (board clock), `correction_gain` (one minus the least-squares slope of each asynchrony on the one before, pairs under 1.2 s apart; 20473-20493), `hit_rate`, `interval_cv` (SD of press interval minus note interval over the mean note interval).
- Second go: exploratory table `COHORT_SECOND_GO_METRICS` (29493) with ICC(2,1), ICC(3,1), SEM, MDC and the shift (`cohort_retest_stats` 29253).
- Internal consistency: split-half only for `asyn_abs_mean_ms` (`COHORT_SPLIT_SOURCES` 22702).
- Fine series: asynchrony SD per 30 s window (21860-21876), windows cut on the note time rebuilt from `song_time_s` minus the offset, which still carries the 2 s pre-song lead and the audio offset, so window k starts about 2.1 s before track time 30k (arithmetic).
- Chapters: `sec_rhythm` 5537, `sec_tap_variability` 5789, `sec_rhythm_checks` 26697; literature rows `MODE_LIT["rhythm"]` 25283; claim limits `MODE_CLAIM_LIMITS["rhythm"]` 25811.

### 1.6 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| Taps precede the beat by tens of ms; Rh1 tests mean below zero | design doc 1.6 Rh1; `MODE_LIT` 25284; `default.yaml` 2031-2038 | Repp 2005; Repp and Su 2013 | Repp 2005 [FT] describes the NMA as "generally not evident in tapping to music"; music gave +4 and -16 ms against -38 ms for tones in the same adults (Q1) |
| Tactile pacing removed the lead | docstring 21-22; design doc; claim limits | Mueller et al. 2008 | Correct for an air-cushion pulse on the other index finger (n = 7, -8 ms, not significant); earlier tactile studies found small negative values; not the same stimulus as a buzz under the pressing finger with three other cues (Q2) |
| From about 2.4 s between beats people react | docstring 22-23; `rhythm_correction_gain` | Mates et al. 1994 | Supported [ABS]; Repp 2005 [FT] gives 1.8 s as the general limit; the chart's long gaps are filled by the music's beat (Q6) |
| The chart's zero sits a median 26 ms after the music's attacks, so a mean near zero or above is not a device fault | docstring 23-28; design doc 1.6; claim limits; modes-review device facts | review of 30 September | The lag is real: 26 ms for ideal clicks, 33 to 37 ms for this track (track analysis). It moves logged means more negative for anyone who follows the music's attacks; only the press stamping and detector delays move them less negative (Q4, Q14) |
| Each press stamped about 10 ms late on a bursting board | same | pilot | Supported (modes-review device facts) |
| Four signals pace the press at once | docstring 15-18 | none | Correct; the tone and buzz land 33 to 37 ms after the music's attack (Q3, Q4) |
| Windows are game feel; the signed offset is the research number | docstring 32-38 | none | Supported; the windows are about twice StepMania's (Q9) |
| RAS is an established gait and upper-limb technique after stroke | docstring 3-11 | Thaut, McIntosh and Rice 1997 | Thaut 1997 is gait only [ABS]; upper-limb evidence is for music-based training, moderate certainty (Q13) |
| Reliability class good for SD and absolute offset, moderate for the signed mean | design doc 1.6 | none | Consistent with BAASTA and REPP, but design doc 4.5 says no class is predicted for Rhythm (Q10) |
| The buzz lead of 350 ms suits a reactor (young adults 200 to 230 ms) | `rhythm.py` 84-94; `default.yaml` 1675-1683 | Bao et al. 2019 | Bao 2019 [FT] text gives reported vibrotactile RTs of 200 to 2000 ms and a coin motor 46 ms slower than a C-2 tactor; free play only |
| The lead makes the block a reaction task with a per-person stimulus; on_beat gives everyone the same pacing | design doc 1.6 | none | Supported (simulation; Fink 2022 [FT]; Repp and Keller 2008 [ABS]) (Q7) |
| The display lag moves only where the note is drawn, never a score; screen timing is cosmetic for rhythm work | design doc 4.8 i; `new_modes/movement-disorders.md` 107 | none | True for the score; not for the task, because the falling note is a pacing cue (Iversen 2015 [FT]) (Q3) |
| A positive asynchrony lag-1 is partial correction; the interval residual's lag-1 is negative by construction | notebook 5655-5670, 26806-26825 | Vorberg and Wing 1996; Repp 2005; Semjen 2000 | Supported (Repp 2005 [FT]; Vishne 2021 [FT]); the correction gain is biased upward (Q8) |
| `song_time_s` on a hit row "is the press itself" | notebook `tap_series` 5742, `sec_tap_variability` printout | none | Not so (code); the error cancels in differences |
| Easy_Lemon is about 120 BPM with a swing feel | `assets/music/ATTRIBUTION.md` 10 | none | The composer lists 82 BPM; the eighths are straight (track analysis) |

Also cited in the code and design for this mode: Rose et al. 2019 (Rh2 note), Wing and Kristofferson 1973, Vorberg and Wing 1996, Semjen et al. 2000, Robinson 1934 via Kosinski 2013 (old lead), Precision Microdrives datasheets (motor lag), and in the modes-review Rh-L1 to Rh-L13 (mostly abstract-level).

### 1.7 Pilot blocks on disk (rig check only)

Ten Rhythm blocks by the development team (6 August to 25 September 2026) on Bright_Wish, 8bit_Dungeon_Boss, Beachfront_Celebration and Cheery_Monday; none on Easy_Lemon and none with `tactile_mode: on_beat`; audio offset 40 ms in eight, 87 ms in two; lead 150 or 350 ms where set. The nine blocks with hits had block mean asynchronies of -4 to -170 ms and SDs of 51 to 194 ms (pilot). They check the software under older settings, not people.

---

## 2. Research questions and findings

### Q1. What mean asynchrony should a healthy young adult show on a pop song near 82 BPM? (Rh1)

- Metronome. Taps usually precede clicks by about 30 to 50 ms (Aschersleben and Prinz 1995 [ABS]); by some tens of ms in most studies, by as much as 100 ms in some people and hardly at all in others; the NMA shrinks as the IOI shrinks and is smaller or absent in musicians (Repp 2005, Section 3 [FT]). People are not aware of it (same).
- Music. Repp 2005 [FT, Section 3] describes the NMA as small or absent in musical settings, reduced or removed by explicit auditory feedback and by rhythmic subdivision, and attributes its usual absence in tapping to music to the subdivision of the interval between beats (after Wohlschlager and Koch 2000 [META]); studies with rhythmically complex materials found none (Snyder and Krumhansl 2001; Thaut, Rathbun and Miller 1997; Toiviainen and Snyder 2003 [all META, via Section 8]).
- Same people, tones against music. Mobile BAASTA, 108 non-musician adults aged 18 to 87, tap times taken from the tablet's microphone to within 1 ms (Dalla Bella et al. 2024, Methods and Table 3 [FT]): tones -7.1, -6.4 and -5.4 percent of the IOI at 450, 600 and 750 ms, that is -32, -38 and -41 ms (arithmetic); two music excerpts at a 600 ms beat +0.6 and -2.7 percent, +4 and -16 ms (arithmetic). The two excerpts differed from each other (F(1, 91.3) = 47.06, p < .001), so the track itself moves the mean.
- Music against metronome elsewhere. 16 healthy controls (mean age 56.7) and 19 people with progressive MS tapping near 600 ms on a piezo pad: metronome -64.95 ms, self-chosen music -42.96 ms (t = -5.85, p < .001), no group difference (Vanbilsen et al. 2025, Results [FT]). Songs of 77 to 85 BPM gave less asynchrony than a metronome at the slow tempo, 50.4 against 66.3 ms (difference 15.8 ms, p < .001), but the paper labels this measure absolute while printing negative means at the fast tempo, so its sign convention is unclear (Rose et al. 2019, Section 3.2.2 and Table 1 [FT]). 20 non-musicians were equally accurate (absolute asynchrony) with metronome and music (Dalla Bella et al. 2017, Results [FT]).
- Auditory pacing at 800 ms in 7 untrained adults: -39 ms, between-person SD 26 ms, within-person SD 37 ms (Muller et al. 2008, Results [FT]).
- How the press is timed. 236 museum visitors tapping on a force sensor, timed from the initial rise of force: -81 ms (reported as plus or minus 40 ms), which the authors attribute to detecting tap onsets rather than peaks (Serre et al. 2026, Asynchrony section [FT]).
- Culture. French participants showed the classic NMA; Indian participants a mean asynchrony close to zero (Le Guennec et al. 2026 [ABS]).

Where sources disagree: Repp 2005 and mobile BAASTA put the music NMA near zero; Vanbilsen 2025 found -43 ms with music. Every study finds music at or below the metronome value in the same people. The beat reference differs across studies (onset annotations, beat trackers, perceptual centres; Q4), as do devices and ages.

Bearing: against an annotated musical beat at 732 ms, the literature supports a mean asynchrony anywhere from about 0 to -40 ms, smaller than the same person's metronome value. Rh1 cites Repp 2005 for an effect that Repp 2005 says is generally absent with music.

### Q2. What does a buzz under the pressing finger do?

- Tactile pacing. An air-cushion pulse of about 35 ms on the left index fingertip, tapping with the right index at 800 ms: -8 ms (between-person SD 9, within-person SD 42), not different from zero (t = 1.76, P > 0.13); on the left big toe -4 ms; auditory pacing -39 ms in the same seven people (Muller et al. 2008, Methods and Results [FT]). Earlier tactile studies found smaller but still negative asynchronies (Kolers and Brewster 1985; Al-Attar, O'Boyle and Cody 1998, both as reported in Muller 2008 [FT]). Muller and colleagues chose the air cushion because it felt like touching the pad, and explain the result by pacing and feedback sharing one modality (Discussion [FT]).
- Tactile feedback. Synchrony is set centrally between the tap's tactile and kinaesthetic code and the click's auditory code (Aschersleben and Prinz 1995 [ABS]); local anaesthesia of the finger increased the asynchrony (Aschersleben, Gehrke and Prinz 2001 [ABS]).
- Tactile against auditory metronomes. With a large stimulated area and simple rhythms, tactile synchronisation closely matched auditory; auditory information kept an advantage for complex rhythms (Ammirante et al. 2016 [ABS]).
- Reacting to a buzz. Vibrotactile reaction times in the literature run from about 200 ms upward, and a coin-style motor was 46 ms slower than a C-2 tactor in young adults (Bao et al. 2019, Introduction and Part 1 [FT]).
- On the rig (code, takes): the buzz is commanded 74 ms ahead so the motor's acoustic onset lands on the zero, and it lasts 250 ms, so the press's own touch arrives while the finger vibrates. No study was found that places the pacing vibration under the tapping finger itself (Europe PMC searches).

Two mechanisms pull opposite ways: a same-modality cue can remove the NMA (Muller 2008), while vibration masking the press's own touch would act like reduced tactile feedback, which enlarged it (Aschersleben 2001). A player who treats the buzz as a go signal would press about +200 ms or more after it (Bao 2019), well inside the Late tier.

### Q3. Four cues at once: which one sets the press?

- Weighting. Auditory, visual and tactile metronome cues were combined in proportion to their reliability; at large discrepancies, taps followed the most reliable cue, with a bias to sound (Elliott, Wing and Welchman 2010 [ABS]). An auditory plus haptic metronome gave less variable tapping than either alone, close to maximum-likelihood predictions (Wing, Doumas and Welchman 2010 [ABS]).
- Moving visual targets. At a 600 ms IOI, tapping to a bouncing ball had a circular SD of 0.052 cycles (31.8 ms) against 0.044 cycles (26.4 ms) for tones (P = 0.09); flashes gave 0.116 cycles and 28 to 29 percent failed trials (Iversen et al. 2015, Results [FT]). For musicians and video-game players a bouncing ball disrupted tapping to tones as much as the reverse (Hove et al. 2013 [META], as reported in Iversen 2015 [FT]). The falling note here is a constant-speed approach to a ring that vanishes at the zero, so it is a moving visual pacing cue, not a flash.
- A second sound after the music. Two instruments slightly out of step shift the compound sound's perceptual centre later; a fast-attack sound anchors it; two fast-attack sounds whose centres are 40 ms or more apart can split into two events (Danielsen et al. 2026 [ABS]). Here the lane tone (5 ms attack) sounds at the zero, 33 to 37 ms after the music's high-frequency attack (track analysis).
- Pitch. Across 110 to 3520 Hz the pacing tone's pitch changed asynchrony in a U shape; in the lower register higher tones drew earlier taps (Pazdera and Trainor 2025, Results and Figure 3 [FT]). The four lane tones span C4 to C5, one per finger.

Bearing: the logged asynchrony is against a composite of four cues that are not aligned to within about 35 ms, and a person's mean depends on which cue they follow. The visual note's timing depends on the unmeasured display lag, so screen timing is part of the stimulus, not cosmetic.

### Q4. Where is the beat in a musical sound, and where does the chart put it?

- Perceptual centres. 59 expert musicians aligned clicks and tapped with clave sticks to musical and neutral sounds through a latency-free loopback: perceptual centres sat 26 ms (producers), 37 ms (jazz) and 40 ms (folk) after the physical onset on average; slow attacks and long durations moved them later and widened them; acoustic instrument sounds were 19 ms later than electronic ones and 46 ms later than noise bursts (Danielsen et al. 2022, Results [FT]). A perceptual centre can lie from a few to over 100 ms after the onset (Danielsen et al. 2026 [ABS]). Longer durations and rise times of metronome sounds reduced the NMA, which suggests taps are aimed at the perceptual centre (Vos, Mates and van Kruysbergen 1995 [ABS]; Repp 2005, Section 3 [FT]).
- The chart. The zero sits a median 36.9 ms after the high-frequency attack (IQR 30.2 to 41.5, per-note SD 7.8 ms; track analysis), mostly because librosa's envelope is shifted three frames and quantised to 23.2 ms (Section 1.2).
- Two readings. Against the physical attack, the convention for clicks in the tapping literature, the zero is about 35 ms late, so a player who follows the music is logged about 35 ms more negative than an attack-referenced measure. Against the perceptual centre of musical sounds (about 26 to 40 ms after onset), the zero may sit close to the heard beat. The sources do not settle which reference suits a song; neither reading supports the current text, which uses the chart lag to explain a mean near zero or above.
- The per-note error of 7.8 ms SD adds about 1 ms to a 30 ms asynchrony SD (sqrt(30^2 + 7.8^2) = 31.0 ms, arithmetic).

### Q5. How accurate is the beat tracker, and what did it do to this song?

- The tracker. Ellis's dynamic-programming tracker, the one librosa implements, scored 58.8 percent average beat accuracy on the MIREX-06 training excerpts, counting a beat as matched inside a collar of 20 percent of the beat period; its tempo estimate matched the expert tempo in 35.7 to 45.8 percent of 465 song excerpts, and within a factor of 2 or 3 in 74.4 to 80.6 percent; the original system used 4 ms steps, where librosa's default uses 23.2 ms frames (Ellis 2007, Sections 3 and 4 [FT]). Ellis also notes that listeners smooth inter-beat intervals rather than following onset-strength peaks (Section 1).
- Standard metrics. The beat F-measure counts a beat correct within plus or minus 70 ms, Cemgil's score uses a 40 ms Gaussian, and continuity scores allow 17.5 percent of the inter-beat interval (mir_eval, Raffel et al. 2014 [FT] with the `beat.py` defaults, implementing Davies, Degara and Plumbley 2009 [META]). These tolerances are wider than the effects being measured.
- This song (track analysis): tempo octave error (161.5 against 82 BPM), 17 notes on off-beat eighths, 7 backfilled notes. Tapping off the beat is harder than tapping on it, and synchronisation thresholds are lower on metrically accented tones (Repp 2005, Section 2 [FT]).

Bearing: the chart is a rhythm-game chart, not a beat track. 84 percent of its notes are on the quarter-note beat and 16 percent on syncopated eighths, and its zero carries a systematic 33 to 37 ms lag.

### Q6. Tempo, gaps and note density

- Limits. In-phase synchronisation with a metronome works for IOIs of about 200 to 1800 ms; above about 1.8 s responses begin to lag behind; variability grows in proportion to the interval from about 250 to 2000 ms and faster beyond; slow music is usually subdivided (Repp 2005, Sections 2 and 4 [FT]). Anticipation held from about 600 to 1800 ms and broke down into reactions at ISIs of 2400 ms or more, with an integration window near 3 s (Mates et al. 1994 [ABS]). Anticipation was automatic from 450 to 1500 ms and depended on attention from 1800 to 3600 ms (Miyake, Onishi and Poppel 2004 [ABS]).
- The chart. 65 percent of gaps are one beat (732 ms), inside the automatic range; 16 percent exceed 1.8 s and 7.5 percent exceed 2.4 s (arithmetic); the long gaps cluster in the first 30 s. The music keeps its 732 ms beat through every gap and each note is visible 2.2 s ahead, so the empty-interval limits of Mates 1994 do not apply directly.
- Medium difficulty: keep 35 percent of beats, minimum gap 0.42 s (on this grid at least one full beat between notes), maximum gap 3.2 s with backfill; the stride of 2 is a fallback that does not fire (code, track analysis).

Bearing: the tempo is comfortable. The first 30 s (sparse, syncopated, first note without context) will behave differently from the rest; asynchrony after long gaps may be more positive.

### Q7. Latency compensation and the adaptive lead

- How labs do it. REPP plays the stimulus with marker sounds through the laptop's speakers and records the markers and the tap sounds on the same microphone, which cancels output and input latency; latency and jitter were within 2 ms against an independent calibration system (Anglada-Tort, Harrison and Jacoby 2022, Experiment 1 and Table 1 [FT]). Mobile BAASTA times taps from the tablet microphone and aligns them with the stimulus to within 1 ms, flagging trials whose touchscreen-to-audio match IQR exceeds 10 ms (Dalla Bella et al. 2024, Methods [FT]). TeensyTap stamps taps and plays the metronome on the microcontroller's own clock, feedback 1.79 ms (SD 0.53) after the physical tap, so host communication latency stops mattering (van Vugt 2020, Results and Discussion [FT]).
- pygame-class audio. The pygame-based Expyriment had audio onset lags of 106.83 ms on Windows 10, 118.67 ms on Ubuntu and 42.81 ms on macOS, each with a trial-to-trial SD of about 13.5 to 13.8 ms (Bridges et al. 2020, Table 2 [FT]).
- This rig. Scheduling is on the host's `perf_counter`, with one measured constant per path per machine: song 87 ms, takes SD 3.9 ms (takes), so each block's song start carries a few ms of unrecorded error; the microphone delay is the CoreAudio figure, not checked by loopback; the Windows tap method (`latency_measure.run_tap`) assumes 3.5 ms of board delay where a bursting adapter adds about 10 ms (modes-review), which would bias that estimate by several ms (arithmetic); drift of the audio clock over the 120 s song is not measured (an audio clock 50 parts per million off would drift 6 ms, arithmetic).
- Adaptive pacing. When the pacing sequence corrects part of each asynchrony, participants' behaviour and inferred correction parameters change with the computer's settings (Repp and Keller 2008 [ABS]); an adaptive metronome with gains of 0.25 and 0.5 lowered the SD of asynchrony by 8.1 and 6.6 ms against a fixed one (Fink, Alexander and Janata 2022, Experiment 1 [FT]).
- The lead controller on the real chart (simulation, 200 runs a cell): a player whose press mixes prediction (true asynchrony -30 ms, SD 30) and reaction to the felt buzz (RT 230 ms, SD 40) with weight w ends the block, over the last 50 notes, at -3.6 ms (w = 0.25), -0.3 ms (0.5), -0.1 ms (0.75) and -0.1 ms (1.0), with the lead settling at the controller's fixed point (140 to 230 ms); a pure predictor keeps -29.9 ms. Under `on_beat` the same players score -29.9, +100.1 and +226.5 ms (w = 0, 0.5, 1).

Bearing: the battery's `on_beat` choice is right: the lead nulls the mean asynchrony of anyone who leans on the buzz at all. The remaining risks are the unmeasured lab PC, the per-block start error, the unverified microphone delay, the display lag, the felt buzz onset and resumption after a pause.

### Q8. Spread, consistency and error correction

- Methods in a validated battery. BAASTA discards the first 10 taps, removes intervals under 100 ms and outliers beyond 3 IQR, uses linear statistics only where taps pair one-to-one with beats within plus or minus 50 percent of the IOI, and reports circular consistency (resultant length R, logit-transformed) and accuracy (angle, computed only when the Rayleigh test rejects uniformity) (Dalla Bella et al. 2017, Methods [FT]; Begel et al. 2018, Section 3.2 [FT]).
- Sizes. The SD of asynchronies can be as low as 2 percent of the IOI in trained musicians and is at least twice that in novices (Repp 2005, Section 4 [FT]): 15 and 29 ms at 732 ms (arithmetic). Circular SD 26.4 ms for tones and 31.8 ms for a bouncing ball at 600 ms (Iversen 2015 [FT]); within-person SD 37 ms at 800 ms (Muller 2008 [FT]); mobile BAASTA's group mean logit R gives about 30.5 ms for tones and 31.9 and 38.7 ms for the two music excerpts at 600 ms (arithmetic from Table 3 [FT]).
- Serial structure. Models predict a negative lag-1 correlation of intervals and a positive one of asynchronies (Repp 2005, Section 4 [FT]); neurotypical adults' phase-correction gain, fitted by bGLS, had a median of 0.37 (IQR 0.21) (Vishne et al. 2021, Results [FT]; method Jacoby et al. 2015 [META]).
- The notebook's gain. One minus the least-squares slope of each asynchrony on the previous one overestimates the true gain because motor noise enters both: true 0.37 is estimated at 0.40, 0.45 and 0.53 with motor SD 5, 10 and 12 ms; true 0.25 at 0.28 to 0.41; true 0.50 at 0.53 to 0.64 (simulation on the real chart). Press-stamping jitter and per-note chart error behave like motor noise.
- `interval_cv` equals SD(A) x sqrt(2(1 - r1)) / mean IOI, where r1 is the asynchrony lag-1 (arithmetic), so it adds nothing to the SD and the lag-1.

### Q9. Hit windows, scoring and feedback

- Game windows. StepMania's built-in tiers are plus or minus 22.5 ms (flawless), 45, 90, 135 and 180 ms (miss beyond), for arrows scrolling to a target silhouette (Meek et al. 2024, Methods [FT]). This mode's 50/100/175/300 are about twice as wide.
- Commercial rhythm games mostly ask players to react to visual targets while music plays, vary difficulty by the number of targets rather than rhythmic features, and record timing to about 100 ms in Guitar Hero (Begel et al. 2017, review of 27 games [FT]). Rhythm Workers, a tablet game built for rhythm training, selected excerpts by tapping difficulty and trained healthy young adults over two weeks (Begel, Seilles and Dalla Bella 2018 [ABS]; its windows could not be read: the full text returned 403 and a challenge page).
- Feedback and the NMA. Visual feedback on the size and direction of each asynchrony trained participants to a zero mean, and they reported having to delay their taps (Aschersleben 2003 [META], as reported in Repp 2005, Section 3 [FT]).
- Here the flash says only whether the offset was within 50 ms (gold) or within 300 ms (green); for a person with mean 0 to -20 ms and SD 35 ms, 78 to 85 percent of notes flash gold (arithmetic, normal approximation). The results screen shows the mean absolute offset. Neither gives direction, so neither pushes the sign much. Streak banners appear up to six times a block.

### Q10. Reliability and how many notes (second-go table; design doc 1.6 class)

- BAASTA, 20 adults aged 50 to 76, two weeks apart, ICC(3,1): metronome accuracy 0.80 and consistency 0.75; music accuracy 0.77 and consistency 0.96 (Begel et al. 2018, Table 1 [FT]; bands there: over 0.75 excellent, 0.40 to 0.75 good).
- Mobile BAASTA, 93 adults retested after about 30 days, ICC(3,1): music accuracy 0.47 and 0.52, music consistency 0.79 and 0.74, tone accuracy 0.47 to 0.63, tone consistency 0.58 to 0.66, music CV of ITI 0.23 and 0.57 (Dalla Bella et al. 2024, Table 3 [FT]).
- REPP, SD of asynchrony averaged over isochronous and music trials, test and retest in one session: r = .87, ICC .86 [.72, .93] (N = 20, lab) and ICC .82 [.77, .86] (N = 166, online) (Anglada-Tort et al. 2022, Experiments 2 and 3 [FT]).
- Sampling. With about 100 scored notes a person's mean asynchrony has a standard error of about 3.5 ms if notes are independent and about 4.8 ms with a lag-1 of 0.3 (effective n about 54); against a between-person SD of 29 to 36 ms (mobile BAASTA, arithmetic from Table 3) the sampling reliability of one block's mean is about 0.97 to 0.99 (arithmetic). Between passes, the song-start error adds about 5.5 ms SD to each person's shift (sqrt 2 x 3.9, takes).

Bearing: the number of notes is not the limit; state changes and learning are. Within a sitting, ICC(3,1) is likely good for the SD and the mean; ICC(2,1) will be lower if pass 2 shifts. The literature fits design doc 1.6's classes, but 4.5 says no class is predicted; one of the two needs to change.

### Q11. Practice within a song and across two plays of the same track

- Retesting the same music excerpts, synchronisation consistency improved by 4.05 percent (t(19) = 3.91, p < .05, Bonferroni), which the authors attribute to learning the excerpts (Begel et al. 2018, Results and Discussion [FT]). At 30 days, tone accuracy at 600 ms moved from -6.4 to -4.6 percent (p = .002) while music accuracy did not change (Dalla Bella et al. 2024, Table 3 [FT]). Within one session REPP found no change in mean tapping performance between test and retest (p > .05) (Anglada-Tort et al. 2022 [FT]). StepMania performance rose across a single session of practice in both groups (Meek et al. 2024 [FT]).
- Warm-up. BAASTA discards the first 10 taps and gives practice trials (Dalla Bella et al. 2017 [FT]); REPP gives a practice phase (Anglada-Tort et al. 2022 [FT]). Rhythm has neither, and its first 30 s is the chart's sparsest, most syncopated stretch (track analysis).

Bearing: expect a smaller SD in pass 2 from learning the chart, and treat the 30 s windows as different material, not a learning curve.

### Q12. Person factors: musical training, rhythm games, culture

- Nine trained musicians showed smaller asynchronies, lower variability and greater perceptual sensitivity than 31 students (Repp 2010 [ABS]); drummers were less variable than pianists, singers and non-musicians (Krause, Pollok and Schnitzler 2010 [ABS]); tapping variability correlated -.32 with Gold-MSI musical training (N = 226; Anglada-Tort et al. 2022, Experiment 3 [FT]); informal music experience lowered ITI error and variability and, at the preferred tempo, normalised asynchrony (Serre et al. 2026 [FT]), whose review puts the musician against non-musician difference in mean asynchrony at 40 ms at most.
- Genre training moved perceptual centres of familiar instrument sounds by up to 38 ms (folk against producers) (Danielsen et al. 2022 [FT]).
- Culture changed the NMA (Le Guennec et al. 2026 [ABS]).
- No study was found on rhythm-game experience and tapping asynchrony (Europe PMC searches); video-game players were among the expert perceivers in Hove 2013 (via Iversen 2015 [FT]).

Bearing: the modes-review left an intake line on musical training and rhythm-game play open; the evidence supports adding it before collection.

### Q13. Rhythmic auditory stimulation: what a healthy cohort can claim

- Thaut, McIntosh and Rice 1997 trained gait in 20 hemiparetic patients; with RAS, velocity rose 164 against 107 percent and stride length 88 against 34 percent (P < 0.05) (Thaut 1997 [ABS]). It is not an upper-limb study.
- Consistent evidence supports RAS for gait in Parkinson's disease and subacute stroke; for the upper limb, music-supported therapy has a strong body of evidence, therapeutic instrumental performance is emerging, rhythmically cued patterned sensory enhancement is growing, and trials of fine and gross motor function are still few (Braun Janzen et al. 2022, sections on RAS and upper extremity [FT]).
- 21 RCTs, 1,029 stroke patients: music-based interventions added to conventional rehabilitation improved upper-limb motor function by SMD 0.58 (95 percent CI 0.26 to 0.91; 8 trials, 470 patients), moderate certainty on GRADE (Liu et al. 2026, Results and GRADE table [FT]).

Bearing: a healthy study of this mode measures timing on this device. It supports no therapy, dose or RAS claim, and Thaut 1997 cannot carry "upper-limb".

### Q14. The device's timing floor against the effects

| Link | Size | Constant or variable | Effect on a logged asynchrony | How known |
|---|---|---|---|---|
| Chart zero after the music's attack | +33 to +37 ms (median), per-note SD 7.8 ms | constant per note | more negative by that much for a player following the music's attacks | track analysis |
| Press stamping on a bursting board | +10 to +11 ms, SD about 6 ms | per press | less negative | modes-review, pilot |
| Detector (EMA) | +7 to +11 ms, 4 to 15 per press | per press | less negative | design doc 1.6 |
| Trigger at 30 percent of the calibrated travel | unmeasured; depends on press speed and calibration | per person and finger | less negative than a contact onset | code |
| Song start | SD about 3.9 ms around 87 ms | per block | shifts the whole block | takes |
| Microphone delay | 31.5 ms, reported by CoreAudio | per machine | shifts every score | code |
| Tone | sent 77 ms early, SD about 5.7 ms | per note | moves the cue, not the score | takes |
| Buzz | 74 ms to acoustic onset; felt onset unmeasured | per note | moves the cue | code |
| Display | 20 ms assumed; unmeasured | per machine | moves the visual cue | code |
| Pause and resume | up to one 26 ms mp3 frame plus a frame of play-call lag | after a pause | shifts later notes | code, arithmetic |
| Lab PC | unmeasured; pygame-class Windows lag 106.83 ms, SD 13.72 ms | per machine | on defaults (40 ms), about +60 ms to every score (arithmetic) | Bridges et al. 2020 [FT] |

Effects: music NMA 0 to -40 ms, metronome about -30 to -65 ms (Q1); between-person SD of the mean 29 to 36 ms; within-person SD 26 to 42 ms (Q8); musicians up to 40 ms different (Q12).

Net offsets (arithmetic): for a player who follows the music's attacks, the logged asynchrony is about 16 ms more negative than their asynchrony to the attack (-35 + 10 + 9 = -16); for a player who follows the tone, buzz or note, it is about 19 ms less negative than their asynchrony to that cue (10 + 9). With the music values of Q1 (0 to -40 ms) this puts the expected logged cohort mean anywhere from about -55 to +20 ms. The variable parts add about 10 ms of per-note noise (stamping SD 6, chart SD 7.8), which turns a 35 ms SD into about 36.3 ms (arithmetic). An onset-based press definition moved the NMA by tens of ms in Serre 2026 [FT].

### Q15. What can Rh1 and Rh2 decide?

- Rh1 (simulation, one-sided Wilcoxon on per-person means, between-person SD 25 or 35 ms, sampling SE 4 ms, 4,000 runs a cell): pass rates at p < .05 and at Holm's first step (p < .00625), n = 10: true mean -40 ms: 1.00 and 0.89 (SD 25), 0.93 and 0.59 (SD 35); -25 ms: 0.85 and 0.46, 0.60 and 0.21; -15 ms: 0.49 and 0.15, 0.31 and 0.07; -10 ms: 0.28 and 0.06, 0.18 and 0.04; 0 ms: 0.04 and 0.00. With n = 15 at -15 ms: 0.68 and 0.31 (SD 25).
- So Rh1 passes if the cohort behaves like metronome tappers and usually fails if it behaves like the music studies, even when every hand synchronises well. Its outcome depends on the cue mix and device offsets (Q3, Q14) as much as on the hand.
- Rh2's band (10 to 100 ms) holds every reference value in Q8 (26 to 42 ms) and every simulated strategy, reactors included (SD 25 to 42 ms, simulation). It cannot fail for a working rig.
- A check that the task elicits synchronisation rather than reaction would inform: under `on_beat`, a reacting player sits near +100 to +230 ms (simulation), while synchronising players sit within tens of ms of zero.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Track | Easy_Lemon.mp3, 82 BPM (composer), 126.4 s | Comfortable tempo (Repp 2005 [FT]); the track moves the mean (mobile BAASTA [FT]) | Keep; state the track with every number |
| Chart built at run time by librosa | extracted every block (`_begin_protocol_rhythm`) | Only `n_notes` and `bpm` recorded; installer bundles its own librosa | Change: freeze the chart as a file, record a hash |
| Metrical level | 16 percent of notes on off-beat eighths | Off-beat tapping is harder (Repp 2005 [FT]) | Keep for this study; tag and report on-beat notes; regenerate after collection |
| Chart zero | 33 to 37 ms after the high-band attack (track analysis) | Perceptual centres 26 to 40 ms after onset (Danielsen 2022 [FT]); clicks are referenced to onset | Keep; add an attack-referenced row; fix the text; decide alignment (design change) |
| Gaps | 697 to 2926 ms; 16 percent over 1.8 s, mostly in the first 30 s | Limits 1.8 to 2.4 s for empty intervals (Repp 2005 [FT]; Mates 1994 [ABS]) | Keep; report the first 30 s apart |
| Preview and fall | 2.2 s, 168 px/s | Moving targets pace well (Iversen 2015 [FT]) | Keep |
| Display compensation | 20 ms estimate | The note is a pacing cue | Measure on the lab PC |
| Lane tone | C4 to C5 by finger, 120 ms, heard at the zero, about 35 ms after the music's attack | Pitch biases asynchrony (Pazdera 2025 [FT]); two attacks 40 ms apart can split (Danielsen 2026 [ABS]) | Change (design change: align or drop) or state it |
| Buzz | on_beat, 74 ms acoustic compensation, 250 ms | Tactile pacing shrinks the NMA (Muller 2008 [FT]); felt onset unknown | Keep; bench the felt onset later |
| Free-play lead | 350 ms, adaptive | Nulls the mean asynchrony (simulation; Fink 2022 [FT]) | Keep out of the study; guard the notebook |
| Audio offset | 87 ms MacBook, takes SD 3.9 ms; lab PC unmeasured | pygame Windows lag about 107 ms (Bridges 2020 [FT]) | Measure the lab PC before any participant |
| Loud notes | 10 percent, +35 percent | Unplanned (design doc) | Keep; add a sensitivity row |
| Matching | -300 to +300 ms effective | One tap per note (BAASTA pairs within half an IOI [FT]) | Keep |
| Windows | 50/100/175/300 ms | Game feel; about twice StepMania (Meek 2024 [FT]) | Keep; never a research criterion |
| Flash and results feedback | magnitude only | Direction feedback moves the NMA (Aschersleben 2003 via Repp 2005 [FT]) | Keep |
| Streak banners | up to six per block | Unscheduled visual events; Reaction is quiet | Quiet them in the battery (low) |
| Instruction | "Press in time with a song" | Synchronisation tasks instruct and practise (BAASTA, REPP [FT]) | Add a line |
| Practice | none; first note has no musical context | BAASTA drops 10 taps and gives practice [FT] | Sensitivity now; practice notes as a design change |
| Pause | resume by mp3 seek | Alignment after resume unverified (code) | Restart instead; flag paused blocks |
| Rh1 | mean below zero, one-sided Wilcoxon, Holm | Music NMA near zero to -40 ms (Q1); pass 18 to 49 percent at -10 to -15 ms (simulation) | Change (design change) |
| Rh2 | SD 10 to 100 ms | References 26 to 42 ms | Keep as feasibility; print the reference |
| Primary list includes tempo-tracking r | design doc 1.6 | Inflated by construction (notebook's own caveat) | Drop from the primary list |
| `interval_cv` | reported as a primary | Function of SD and lag-1 (arithmetic) | Keep as descriptive |
| `correction_gain` | 1 minus the OLS lag slope | Biased upward by motor noise (simulation) | Label, or use bGLS |
| Split-half | absolute mean only | Mean and SD are the headline measures | Add |
| 30 s windows | cut on a clock carrying the 2 s lead | Design says track time | Fix with a logged note time |
| Second go | ICC(2,1), ICC(3,1), shift | Literature reports ICC(3,1) | Keep; exploratory |
| Intake | no musical training item | Training moves SD and NMA (Q12) | Add (design change) |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

1. **Measure the lab PC before any participant and keep unmeasured Rhythm blocks out of Rh1 and Rh2.** SAFE-NOW (procedure and analysis).
   Run `scripts/audio_latency.py --write` on the lab PC through its own speakers (the tap method, as CoreAudio is absent on Windows) and `scripts/latency_check.py` with a 240 fps phone for the display lag. `scripts/check_sitting.py` (lines 251-262) already prints CHECK for a Rhythm block run on unmeasured delays, which withholds READY, but only after the sitting; add an up-front warning where the battery starts a Rhythm step (`engine._begin_protocol_rhythm` 6701) when `latency.measured` is false, so the RA measures before the participant plays. In the notebook, `_cohort_rhythm` (20498) should drop blocks whose `config_snapshot.latency.measured` is false from the Rh1 and Rh2 inputs and print them apart; `rhythm_offset_note` (26874) already describes them. In `latency_measure.write_profile` (536-558) write the SD and range of the song and click takes into the profile header so the per-block uncertainty is on record. Evidence: pygame-class audio lag 106.83 ms with 13.7 ms SD on Windows 10 (Bridges et al. 2020 [FT]); on the defaults every score would move by about +60 ms (arithmetic).

2. **Correct the claims the evidence contradicts.** SAFE-NOW (text only; log in the design document).
   - `rhythm.py` 23-28, `default.yaml` 2031-2038, design doc Section 1.6 Rh1 text, `MODE_CLAIM_LIMITS["rhythm"]` (25811 onward), the Rh1 detail in `sec_rhythm_checks` (26769-26779) and the modes-review Rhythm bullet and device-facts row: the chart's zero sits 26 ms (ideal clicks) to 33 to 37 ms (this track's attacks) after the attack, which makes logged means more negative for a player who follows the music; the press stamping (10 to 11 ms) and detector (7 to 11 ms) delays make them less negative; the reasons a mean near zero is plausible are musical, tactile and visual pacing (Repp 2005 [FT]; Dalla Bella et al. 2024 [FT]; Muller 2008 [FT]), not the chart lag.
   - `MODE_LIT["rhythm"]` Rh1 (25284) and design doc Rh1: Repp 2005 describes the NMA as a metronome effect and says it is generally not evident in tapping to music; give the music values beside the metronome ones (Q1).
   - `rhythm.py` 3-11: Thaut 1997 is gait training; cite Braun Janzen et al. 2022 and Liu et al. 2026 for the upper limb.
   - `assets/music/ATTRIBUTION.md` line 10: 82 BPM (composer), straight eighths.
   - Notebook `tap_series` (5742) docstring and the `sec_tap_variability` printout: `song_time_s` is the clock when the row is written, not the press.
   - Design doc 4.8 i and `new_modes/movement-disorders.md` line 107: the display lag never moves a score, but it moves the falling note, which is a pacing cue (Iversen 2015 [FT]).

3. **Re-specify Rh1 before collection.** DESIGN-CHANGE (log the date and reason in design doc Section 1.6 and Table 1; no participant yet).
   The registered directional test is expected to fail about half the time or more for well-synchronising people on this task (Q15, simulation) and its outcome is set by the cue mix and device offsets (Q14). Two options, for the author to choose:
   (a) Keep Rh1's statistic but move it out of the Holm family and report it as an estimate: the cohort mean of per-person mean asynchrony with its 95 percent interval, read against the literature range for music (0 to -40 ms, Q1), beside the board-clock, attack-referenced and on-beat rows (recommendation 4).
   (b) Replace it with a check the task can support: presses anticipate rather than react, for example the cohort median of each person's share of presses later than +150 ms under 10 percent and the cohort median mean asynchrony below +100 ms. A reaction to an on-beat buzz lands about +200 ms or later (Bao et al. 2019 [FT]; simulation +100 to +227 ms).
   Files: design doc Sections 1.6 and 4.6 Table 1; the `_mean_check` call for Rh1 (24168-24190), `COHORT_PRESPECIFIED` (23368) and the Holm family list; `MODE_LIT["rhythm"]` (25284); for (b), a new per-person metric in `_cohort_rhythm` (20498).

4. **Log the note time and add attack-referenced, on-beat and warm-up rows.** SAFE-NOW (logging and analysis; no registered measure changes).
   In `engine.log_rhythm_hit` (9647) add `note_time_s` (the chart time before the pre-song shift, `sched_note.note.t - mode._pre_song_lead_s`) and `press_time_s` (the press's own corrected song time, which `_score_press` already computes at `rhythm.py` 749). In the notebook, build a per-note table for the study chart from the mp3 (note index, time, lane, on-beat or off-beat on the 82 BPM grid, high-band attack lag), as done in this review, and in `_cohort_rhythm` emit `asyn_mean_ms_attack` (each note's lag removed), `asyn_mean_ms_onbeat` and `asyn_sd_ms_onbeat` (90 on-beat notes), and `asyn_mean_ms_ex_warmup` (first 30 s or first 10 notes out, as BAASTA discards the first 10 taps [FT]). Print them beside Rh1 in `sec_cohort_validity` and `sec_rhythm_checks`.

5. **Freeze the study chart as a file and record its hash.** SAFE-NOW if the saved chart reproduces today's 107 notes exactly; DESIGN-CHANGE if any note moves.
   Save the chart with `Beatmap.save` (`beatmap.py` 82-92) to, for example, `app/assets/charts/Easy_Lemon_medium.json`; have `engine._begin_protocol_rhythm` (6701) load it when the step's track matches; store a hash of the note list in the block summary's song record (`engine` 5940-5958); make `check_sitting.py` flag a Rhythm block whose hash or `n_notes` (107) differs. Reason: the chart is rebuilt by whatever librosa the installer bundled (`finger_rehab.spec` 69-72), and today only the note count and tempo are logged.

6. **Tell the participant what to do.** SAFE-NOW (UX; log it in the design document because it changes what participants are told).
   One line on the GET READY card of a Rhythm block (`RhythmScreen.draw` countdown card, `screens.py` 4816-4865) and in the NEXT UP description (1534): "Press each finger as its ball reaches the ring, in time with the music. The buzz and the tone come at that moment, so don't wait for them." Add the same line to the run sheet, said once before the first Rhythm block. Evidence: synchronisation batteries instruct and practise synchronisation (Dalla Bella et al. 2017; Anglada-Tort et al. 2022 [FT]); a player who waits for the buzz scores about +200 ms (Bao 2019 [FT]; simulation).

7. **Reconcile the tone and buzz with the music.** DESIGN-CHANGE (choose before collection) or SAFE-NOW (state it).
   (a) Shift every note by its measured lag, or by the median of -35 ms, so the tone, buzz and ball coincide with the music's attack; this moves the zero to the attack and raises logged means by about 35 ms for music-followers (Q4). (b) Drop the lane tone in the study Rhythm block: a new key such as `rhythm.cue_tone: false` read in `RhythmMode.__init__` (`rhythm.py` 262-263) and passed as `tone=False` through `on_stim`, set in the battery's `rhythm` override (`default.yaml` 2029-2039). Evidence: the tone lands about 35 ms after the music's attack (track analysis), close to the 40 ms at which two attacks segregate (Danielsen et al. 2026 [ABS]), and tone pitch biases asynchrony by finger (Pazdera and Trainor 2025 [FT]). If neither is adopted, state the 35 ms tone-after-attack offset as part of the stimulus in the thesis.

8. **Keep lead-mode and paused blocks out of the registered rows.** SAFE-NOW.
   In `_cohort_rhythm` and `rhythm_rows` (1386) keep for Rh1 and Rh2 only blocks whose rows show `tactile_mode` on_beat with a lead of 0 (from `waveform_params`, read by `buzz_lead_ms` 5472), and flag blocks with a pause (raw `pause` events; `_block_pause_count`) with asynchrony before and after the pause. Run sheet: do not pause a Rhythm block; if it pauses, Retry it. Evidence: the lead nulls the mean (simulation; Fink 2022 [FT]); resumption seeks the mp3 without the start correction (code).

9. **Fix the notebook's time reconstruction and redundant measures.** SAFE-NOW.
   Use `note_time_s` and `press_time_s` in `tap_series` (5742) and cut the 30 s windows (21860-21876) on track time. Label `correction_gain` (20476) as biased upward, or fit bGLS (Jacoby et al. 2015 [META]; implementation published with Vishne et al. 2021 [FT]); the bias is +0.03 to +0.16 (simulation). Drop the tempo-tracking r from the design doc's primary list and describe `interval_cv` as a function of SD and lag-1. Add `asyn_mean_ms` and `asyn_sd_ms` to `COHORT_SPLIT_SOURCES` (22702). Report circular R, angle and the Rayleigh test against the 732 ms beat as secondary outputs, for comparison with BAASTA (Dalla Bella et al. 2017 [FT]).

10. **Record musical training and rhythm-game play at intake.** DESIGN-CHANGE (protocol amendment, already left open in the modes-review).
    Two lines on the intake sheet (years of formal training; hours a week of rhythm games), entered with the code; used as covariates, never as a gate. Evidence: Repp 2010 [ABS]; Anglada-Tort et al. 2022 [FT] (r = -.32); Serre et al. 2026 [FT]; Danielsen et al. 2022 [FT].

11. **Reconcile the reliability wording.** SAFE-NOW (text).
    Design doc 1.6 predicts classes; 4.5 says none are predicted for Rhythm. Keep the second go exploratory and quote the literature beside it: consistency or SD ICC(3,1) 0.74 to 0.96 and mean asynchrony 0.47 to 0.80 over 2 to 30 days (Begel 2018; Dalla Bella 2024 [FT]), SD 0.82 to 0.86 within a session (REPP [FT]).

12. **Check audio clock drift over the whole song.** SAFE-NOW (procedure).
    Add a `--full-song` option to `scripts/audio_latency.py` that records the full 126 s track and cross-correlates its first and last 10 s against the decoded file; report the drift in ms. Nothing on the rig measures it now (Q7).

13. **Quiet the streak banners in the battery Rhythm block.** SAFE-NOW (UX; low value).
    Add `rhythm` to `engine._QUIET_STREAK_MODES` (8461) while a protocol runs, as for Reaction; the flash, score and streak chip stay.

14. **After collection.** AFTER-COLLECTION.
    A chart on the quarter-note grid (a tempo prior near the listed BPM, notes on the chosen level only), aligned to measured attacks; practice notes before the song; presses timed on the board's sample clock or firmware frame index; a free-field recording check of the whole chain in the style of REPP (song and pad taps on one microphone); research presets from the modes-review (an even click track at 500, 800 and 1200 ms, auditory, tactile and combined, with continuation taps); a bench measurement of the felt buzz onset.

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Drop unmeasured-latency and lead-mode blocks from Rh1 and Rh2; flag paused blocks | `_cohort_rhythm` 20498, `rhythm_rows` 1386, `buzz_lead_ms` 5472 | Bridges et al. 2020 [FT]; simulation; code |
| Rh1 as an estimate with its interval, or a synchronisation-against-reaction check (after approval) | Rh1 rows 24168-24190, `COHORT_PRESPECIFIED` 23368, `MODE_LIT` 25284 | Repp 2005 [FT]; Dalla Bella et al. 2024 [FT]; simulation |
| Attack-referenced mean, on-beat mean and SD, warm-up-excluded mean | `_cohort_rhythm`; per-note table built from the mp3 | track analysis; Dalla Bella et al. 2017 [FT] (first 10 taps) |
| Per-person share of presses later than +150 ms | `_cohort_rhythm` | Bao et al. 2019 [FT]; simulation |
| Board-clock row kept; add a force-onset (Teasdale) row | `press_late_mean` 9247; `teasdale_onset` 4524 | Serre et al. 2026 [FT]; modes-review device facts |
| Circular R, angle and Rayleigh against the 732 ms beat | `sec_rhythm_checks` 26697 | Dalla Bella et al. 2017 [FT]; Begel et al. 2018 [FT] |
| Correction gain labelled or refitted by bGLS | `rhythm_correction_gain` 20476 | Vishne et al. 2021 [FT]; Jacoby et al. 2015 [META]; simulation |
| Split-half for the mean and SD | `COHORT_SPLIT_SOURCES` 22702 | Parsons et al. 2019, as in analysis_methods.md |
| Windows on track time, first 30 s reported apart | 21860-21876 | track analysis |
| Loud-note sensitivity (mean on loud against other notes) | `sec_rhythm_checks` | design doc 1.6 |
| Per-finger means from a mixed model only, with the tone pitch and lane named as confounds | `per_finger_table` callers | Pazdera and Trainor 2025 [FT] |
| Second go read against the literature ICC(3,1) values | `_cohort_second_goes` 29512 | Begel 2018; Dalla Bella 2024; Anglada-Tort 2022 [FT] |
| Musical training covariate once collected | cohort tables | Anglada-Tort 2022 [FT]; Repp 2010 [ABS] |

Keep as they are: the per-block computation of bias and lag-1 (never across blocks), the outlier-resistant SD (`asyn_rsd_ms`), the reading of a positive asynchrony lag-1 as partial correction, the Rh-wk row as descriptive, the second-go table's exploratory heading, and `rhythm_offset_note`.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Mean asynchrony to tones, non-musician adults | -32, -38 and -41 ms at 450, 600 and 750 ms | Dalla Bella et al. 2024, Table 3 [FT] (arithmetic from percent of IOI) | tablet with microphone timing; ages 18 to 87 |
| Mean asynchrony to music, same people | +4 and -16 ms at a 600 ms beat | same (arithmetic) | a Bach and a Rossini excerpt; beat annotation theirs |
| Music against metronome, middle-aged controls | -43 against -65 ms | Vanbilsen et al. 2025 [FT] | self-chosen music; piezo pad |
| Auditory metronome, untrained adults | -39 ms (between-person SD 26, within-person SD 37) at 800 ms | Muller et al. 2008 [FT] | n = 7 |
| Tactile metronome (other index finger) | -8 ms, not different from zero | Muller et al. 2008 [FT] | air-cushion pulse, not a buzz under the tapping finger |
| Force-onset timing, museum sample | -81 ms (reported as plus or minus 40 ms) | Serre et al. 2026 [FT] | onset definition inflates the NMA |
| SD of asynchrony | 26.4 ms tones, 31.8 ms moving ball at 600 ms; about 30 to 39 ms tones and music (mobile BAASTA, arithmetic); 2 percent of the IOI trained, at least 4 percent novice (15 and 29 ms at 732 ms, arithmetic) | Iversen 2015; Dalla Bella 2024; Repp 2005 [FT] | this rig adds about 10 ms of per-note noise (arithmetic) |
| Between-person SD of the mean | 29 to 36 ms | Dalla Bella 2024 [FT] (arithmetic) | |
| Phase-correction gain | median 0.37 (IQR 0.21) | Vishne et al. 2021 [FT] | bGLS on a metronome, not this chart |
| Upper limit of anticipation | about 1.8 s; reactions from 2.4 s | Repp 2005 [FT]; Mates 1994 [ABS] | empty intervals, not a song |
| Perceptual centre of musical sounds | 26 to 40 ms after onset on average | Danielsen et al. 2022 [FT] | expert musicians; later for slow attacks |
| Musical training | smaller asynchrony and variability; r = -.32 with variability | Repp 2010 [ABS]; Anglada-Tort 2022 [FT] | |
| Reaction to vibration | about 200 ms or more; coin motor 46 ms slower than a lab tactor | Bao et al. 2019 [FT] | torso and body sites; thumb trigger |

How to use them: report this device's asynchronies as the device's own, measured against the chart's zero (a librosa beat 33 to 37 ms after the high-frequency attack, plus the measured audio delay), with a four-cue pacing signal and a force-threshold press that is logged about 17 to 22 ms after the raw crossing (arithmetic from the stamping and detector delays). The published values frame the order of magnitude and the direction of cue effects; they are never norms to test against.

### 6.2 Reliability and practice expectations

- Within-sitting ICC(3,1): likely good for the SD (REPP within-session 0.82 to 0.86 [FT]) and for the mean (sampling reliability of one block about 0.97 to 0.99, arithmetic; between-day values 0.47 to 0.80 [FT]); ICC(2,1) lower if pass 2 shifts. At n = 10 the interval spans two or three bands.
- Pass 2 against pass 1: a smaller SD from learning the chart is the expected direction (Begel 2018 [FT]: +4.05 percent consistency with the same excerpts); a change in the mean of a few percent of the IOI is possible (Dalla Bella 2024 [FT]); the song-start error alone adds about 5.5 ms SD to each person's shift (takes, arithmetic).
- Internal consistency will be high and says nothing about stability across days.

### 6.3 Claims to avoid

- That the NMA was "reproduced" or "absent" as a fact about the hand, without the chart's zero, the cue mix and the device offsets beside it.
- That the chart's lag behind the music explains a mean near zero (it works the other way for a player following the music).
- That tactile pacing removes the NMA on this device (Muller 2008 used a different stimulus, site and cue mix).
- Any comparison of absolute asynchronies with BAASTA, REPP or other norms.
- Interval CV or the tempo-tracking correlation as a person's timing consistency on this chart.
- A trend in SD across the 30 s windows as learning or fatigue.
- Per-finger asynchrony differences as finger effects (lane tone pitch, calibration thresholds and the chart's lane cycle all differ by finger).
- The correction gain as a phase-correction parameter.
- Any RAS efficacy, dose or therapy claim; "upper-limb RAS" on the strength of Thaut 1997.
- Any result from free-play (lead-mode) blocks pooled with battery blocks, or from a computer whose delays were not measured.
- The within-session ICC as test-retest reliability between days.

---

## 7. Sources

Retrieved and checked on 30 September and 1 October 2026 through Europe PMC, PubMed E-utilities, NCBI PMC, Crossref, OpenAlex, publisher and repository pages. Where a source is marked FT through a repository or course copy, the copy is named.

1. Al-Attar Z, O'Boyle DJ, Cody FWJ. 1998. Effects of site of delivery of an electrical cutaneous metronome on the magnitude of the synchronization error during human temporal tracking. Journal of Physiology 509P:181-182. [META; finding as reported in Muller 2008]
2. Ammirante P, Patel AD, Russo FA. 2016. Synchronizing to auditory and tactile metronomes: a test of the auditory-motor enhancement hypothesis. Psychonomic Bulletin and Review 23(6):1882-1890. DOI 10.3758/s13423-016-1067-9. PMID 27246088. [ABS; the publisher's full text required an authorisation redirect]
3. Anglada-Tort M, Harrison PMC, Jacoby N. 2022. REPP: A robust cross-platform solution for online sensorimotor synchronization experiments. Behavior Research Methods 54(5):2271-2285. DOI 10.3758/s13428-021-01722-2. PMID 35149980. PMC8853279. [FT: Experiments 1 to 3, Discussion]
4. Aschersleben G. 2003. Effects of training on the timing of repetitive movements. In: Shohov SP (ed), Advances in Psychology Research 23:15-30. Nova Science. [META; finding as reported in Repp 2005]
5. Aschersleben G, Gehrke J, Prinz W. 2001. Tapping with peripheral nerve block: a role for tactile feedback in the timing of movements. Experimental Brain Research 136(3):331-339. DOI 10.1007/s002210000562. PMID 11243475. [ABS]
6. Aschersleben G, Prinz W. 1995. Synchronizing actions with events: the role of sensory information. Perception and Psychophysics 57(3):305-317. DOI 10.3758/BF03213056. PMID 7770322. [ABS]
7. Aschersleben G. 2002. Temporal control of movements in sensorimotor synchronization. Brain and Cognition 48(1):66-79. DOI 10.1006/brcg.2001.1304. PMID 11812033. [ABS]
8. Bao T, Su L, Kinnaird C, Kabeto M, Shull PB, Sienko KH. 2019. Vibrotactile display design: quantifying the importance of age and various factors on reaction times. PLoS One 14(8):e0219737. DOI 10.1371/journal.pone.0219737. PMID 31398207. PMC6688825. [FT: Introduction, Methods, Results Parts 1 and 2]
9. Begel V, Di Loreto I, Seilles A, Dalla Bella S. 2017. Music games: potential application and considerations for rhythmic training. Frontiers in Human Neuroscience 11:273. DOI 10.3389/fnhum.2017.00273. PMID 28611610. PMC5447290. [FT: game review sections, Conclusion]
10. Begel V, Seilles A, Dalla Bella S. 2018. Rhythm Workers: a music-based serious game for training rhythm skills. Music and Science 1. DOI 10.1177/2059204318794369. [ABS, via DOAJ; the full text returned 403]
11. Begel V, Verga L, Benoit CE, Kotz SA, Dalla Bella S. 2018. Test-retest reliability of the Battery for the Assessment of Auditory Sensorimotor and Timing Abilities (BAASTA). Annals of Physical and Rehabilitation Medicine 61(6):395-400. DOI 10.1016/j.rehab.2018.04.001. PMID 29709607. [FT: publisher's version in the Maastricht repository; Methods, Table 1, Discussion]
12. Braun Janzen T, Koshimori Y, Richard NM, Thaut MH. 2022. Rhythm and music-based interventions in motor rehabilitation: current evidence and future perspectives. Frontiers in Human Neuroscience 15:789467. DOI 10.3389/fnhum.2021.789467. PMID 35111007. PMC8801707. [FT: sections on RAS in Parkinson's disease and stroke, upper extremity interventions]
13. Bridges D, Pitiot A, MacAskill MR, Peirce JW. 2020. The timing mega-study: comparing a range of experiment generators, both lab-based and online. PeerJ 8:e9414. DOI 10.7717/peerj.9414. PMID 33005482. PMC7512138. [FT: Table 2, lab-based results]
14. Dalla Bella S, Farrugia N, Benoit CE, Begel V, Verga L, Harding E, Kotz SA. 2017. BAASTA: Battery for the Assessment of Auditory Sensorimotor and Timing Abilities. Behavior Research Methods 49(3):1128-1145. DOI 10.3758/s13428-016-0773-6. PMID 27443353. [FT: Maastricht repository copy; Methods (tapping tasks, analyses), Results]
15. Dalla Bella S, Foster NEV, Laflamme H, Zagala A, Melissa K, Komeilipoor N, Blais M, Rigoulot S, Kotz SA, et al. 2024. Mobile version of the Battery for the Assessment of Auditory Sensorimotor and Timing Abilities (BAASTA): implementation and adult norms. Behavior Research Methods 56(4):3737-3756. DOI 10.3758/s13428-024-02363-x. PMID 38459221. [FT: accepted version in the Maastricht repository; Methods, Table 3, test-retest results]
16. Danielsen A, London J, Langerod MT, Schmidt Camara G. 2026. All about that bass drum? Asynchrony effects on the perceived timing of compound musical sounds. Annals of the New York Academy of Sciences 1560(1):e70306. DOI 10.1111/nyas.70306. PMID 42301156. PMC13390590. [ABS]
17. Danielsen A, Nymoen K, Langerod MT, Jacobsen E, Johansson M, London J. 2022. Sounds familiar(?): expertise with specific musical genres modulates timing perception and micro-level synchronization to auditory stimuli. Attention, Perception, and Psychophysics 84(2):599-615. DOI 10.3758/s13414-021-02393-z. PMID 34862587. PMC8888399. [FT: Method, Results, Discussion]
18. Davies MEP, Degara N, Plumbley MD. 2009. Evaluation methods for musical audio beat tracking algorithms. Technical Report C4DM-TR-09-06, Centre for Digital Music, Queen Mary University of London. [META; metric defaults read in the mir_eval source]
19. Elliott MT, Wing AM, Welchman AE. 2010. Multisensory cues improve sensorimotor synchronisation. European Journal of Neuroscience 31(10):1828-1835. DOI 10.1111/j.1460-9568.2010.07205.x. PMID 20584187. [ABS]
20. Ellis DPW. 2007. Beat tracking by dynamic programming. Journal of New Music Research 36(1):51-60. DOI 10.1080/09298210701653344. [FT: author's copy; Sections 3 and 4]
21. Fink LK, Alexander PC, Janata P. 2022. The Groove Enhancement Machine (GEM): a multi-person adaptive metronome to manipulate sensorimotor synchronization and subjective enjoyment. Frontiers in Human Neuroscience 16:916551. DOI 10.3389/fnhum.2022.916551. PMID 35782041. PMC9240653. [FT: design, Experiment 1 Results and Discussion]
22. Hove MJ, Iversen JR, Zhang A, Repp BH. 2013. Synchronization with competing visual and auditory rhythms: bouncing ball meets metronome. Psychological Research 77(4):388-398. DOI 10.1007/s00426-012-0441-0. PMID 22638726. [META; finding as reported in Iversen 2015]
23. Iversen JR, Patel AD, Nicodemus B, Emmorey K. 2015. Synchronization to auditory and visual rhythms in hearing and deaf individuals. Cognition 134:232-244. DOI 10.1016/j.cognition.2014.10.018. PMID 25460395. PMC4255154. [FT: author manuscript; Methods, Results, Discussion]
24. Jacoby N, Keller PE, Repp BH, Ahissar M, Tishby N. 2015. Parameter estimation of linear sensorimotor synchronization models: phase correction, period correction, and ensemble synchronization. Timing and Time Perception 3(1-2):52-87. DOI 10.1163/22134468-00002048. [META]
25. Kolers PA, Brewster JM. 1985. Rhythms and responses. Journal of Experimental Psychology: Human Perception and Performance 11(2):150-167. DOI 10.1037/0096-1523.11.2.150. [META; finding as reported in Muller 2008]
26. Krause V, Pollok B, Schnitzler A. 2010. Perception in action: the impact of sensory information on sensorimotor synchronization in musicians and non-musicians. Acta Psychologica 133(1):28-37. DOI 10.1016/j.actpsy.2009.08.003. PMID 19751937. [ABS]
27. Le Guennec M, Tchechmedjiev A, Kelso JAS, Lagarde J. 2026. Universal and cross-cultural variations in audio-motor synchronization between French and Indian participants. Annals of the New York Academy of Sciences 1560(1):e70309. DOI 10.1111/nyas.70309. PMID 42229371. PMC13390598. [ABS]
28. Liu D, Kang T, Liang Y, Tong C, Xue Y. 2026. Effects of music-based interventions on rehabilitation outcomes after stroke: a systematic review and meta-analysis of randomized controlled trials. Frontiers in Neurology 17:1907080. DOI 10.3389/fneur.2026.1907080. PMID 42729195. PMC13561795. [FT: Methods, Results (upper limb), GRADE table]
29. Mates J, Muller U, Radil T, Poppel E. 1994. Temporal integration in sensorimotor synchronization. Journal of Cognitive Neuroscience 6(4):332-340. DOI 10.1162/jocn.1994.6.4.332. PMID 23961729. [ABS]
30. McFee B, Raffel C, Liang D, Ellis DPW, McVicar M, Battenberg E, Nieto O. 2015. librosa: audio and music signal analysis in Python. Proceedings of the 14th Python in Science Conference:18-24. DOI 10.25080/Majora-7b98e3ed-003. [META; the library's 0.11.0 source for `onset_strength_multi` and `beat_track` read directly]
31. Meek AW, Greenwell DR, Nishio H, Poston B, Riley ZA. 2024. Anodal M1 tDCS enhances online learning of rhythmic timing videogame skill. PLoS One 19(6):e0295373. DOI 10.1371/journal.pone.0295373. PMID 38870202. PMC11175489. [FT: Methods (StepMania windows), Results]
32. Miyake Y, Onishi Y, Poppel E. 2004. Two types of anticipation in synchronization tapping. Acta Neurobiologiae Experimentalis 64(3):415-426. DOI 10.55782/ane-2004-1524. PMID 15283483. [ABS]
33. Muller K, Aschersleben G, Schmitz F, Schnitzler A, Freund HJ, Prinz W. 2008. Inter- versus intramodal integration in sensorimotor synchronization: a combined behavioral and magnetoencephalographic study. Experimental Brain Research 185(2):309-318. DOI 10.1007/s00221-007-1155-1. PMID 17932661. PMC2755785. [FT: Participants, Stimuli and apparatus, behavioural Results, Discussion]
34. Pazdera JK, Trainor LJ. 2025. Pitch biases sensorimotor synchronization to auditory rhythms. Scientific Reports 15:17012. DOI 10.1038/s41598-025-00827-4. PMID 40379668. PMC12084412. [FT: Methods, Results (synchronisation tapping), Figure 3]
35. Raffel C, McFee B, Humphrey EJ, Salamon J, Nieto O, Liang D, Ellis DPW. 2014. mir_eval: a transparent implementation of common MIR metrics. Proceedings of the 15th International Society for Music Information Retrieval Conference (ISMIR). [FT: Section 3.1; beat metric defaults from the mir_eval `beat.py` source]
36. Repp BH, Keller PE. 2008. Sensorimotor synchronization with adaptively timed sequences. Human Movement Science 27(3):423-456. DOI 10.1016/j.humov.2008.02.016. PMID 18405989. [ABS]
37. Repp BH. 2010. Sensorimotor synchronization and perception of timing: effects of music training and task experience. Human Movement Science 29(2):200-213. DOI 10.1016/j.humov.2009.08.002. PMID 20074825. [ABS]
38. Repp BH. 2005. Sensorimotor synchronization: a review of the tapping literature. Psychonomic Bulletin and Review 12(6):969-992. DOI 10.3758/BF03206433. PMID 16615317. [FT: course copy of the published version; Sections 2 (rate limits), 3 (negative mean asynchrony), 4 (variability), 8 (musical contexts)]
39. Repp BH, Su YH. 2013. Sensorimotor synchronization: a review of recent research (2006-2012). Psychonomic Bulletin and Review 20(3):403-452. DOI 10.3758/s13423-012-0371-2. PMID 23397235. [ABS]
40. Rose D, Delevoye-Turrell Y, Ott L, Annett LE, Lovatt PJ. 2019. Music and metronomes differentially impact motor timing in people with and without Parkinson's disease: effects of slow, medium, and fast tempi on entrainment and synchronization performances in finger tapping, toe tapping, and stepping on the spot tasks. Parkinson's Disease 2019:6530838. DOI 10.1155/2019/6530838. PMID 31531220. PMC6721399. [FT: participants, Table 1, Section 3.2.2]
41. Serre H, Harrigian K, Park SW, Sternad D. 2026. Testing sensorimotor timing across age and music experience in a real-world environment. Scientific Reports 16:8300. DOI 10.1038/s41598-026-38073-x. PMID 41673201. PMC12966301. [FT: Introduction, Asynchrony results, Methods (tap onset detection), Discussion]
42. Snyder J, Krumhansl CL. 2001. Tapping to ragtime: cues to pulse finding. Music Perception 18(4):455-489. DOI 10.1525/mp.2001.18.4.455. [META; finding as reported in Repp 2005]
43. Sun Y, Michalareas G, Ghitza O, Poeppel D. 2025. Complex impact of stimulus envelope on motor synchronization to sound. Journal of Neuroscience 45(25):e1488242025. DOI 10.1523/JNEUROSCI.1488-24.2025. PMID 40345839. PMC12178282. [ABS]
44. Thaut MH, McIntosh GC, Rice RR. 1997. Rhythmic facilitation of gait training in hemiparetic stroke rehabilitation. Journal of the Neurological Sciences 151(2):207-212. DOI 10.1016/S0022-510X(97)00146-9. PMID 9349677. [ABS]
45. Thaut MH, Rathbun JA, Miller RA. 1997. Music versus metronome timekeeper in a rhythmic motor task. International Journal of Arts Medicine 5:4-12. [META; finding as reported in Repp 2005]
46. Toiviainen P, Snyder JS. 2003. Tapping to Bach: resonance-based modeling of pulse. Music Perception 21(1):43-80. DOI 10.1525/mp.2003.21.1.43. [META; finding as reported in Repp 2005]
47. Vanbilsen N, Feys P, Rosso M, Van Wijmeersch B, Kos D, Leman M, Kotz SA, Moumdjian L. 2025. Preserved auditory-motor synchronization during finger-tapping to music and metronomes at various tempi in progressive multiple sclerosis. Frontiers in Neurology 16:1547573. DOI 10.3389/fneur.2025.1547573. PMID 40386018. PMC12083085. [FT: Methods, Results (mean asynchrony)]
48. van Vugt FT. 2020. The TeensyTap framework for sensorimotor synchronization experiments. Advances in Cognitive Psychology 16(4):302-308. DOI 10.5709/acp-0304-y. PMID 33500741. PMC7809920. [FT: design, validation Results, Discussion]
49. Vishne G, Jacoby N, Malinovitch T, Epstein T, Frenkel O, Ahissar M. 2021. Slow update of internal representations impedes synchronization in autism. Nature Communications 12:5439. DOI 10.1038/s41467-021-25740-y. PMID 34521851. PMC8440645. [FT: Results (phase correction), Methods (bGLS)]
50. Vorberg D, Wing A. 1996. Modeling variability and dependence in timing. In: Heuer H, Keele SW (eds), Handbook of Perception and Action 2:181-262. Academic Press. DOI 10.1016/S1874-5822(06)80007-1. [META]
51. Vos PG, Mates J, van Kruysbergen NW. 1995. The perceptual centre of a stimulus as the cue for synchronization to a metronome: evidence from asynchronies. Quarterly Journal of Experimental Psychology A 48(4):1024-1040. DOI 10.1080/14640749508401427. PMID 8559964. [ABS]
52. Wing AM, Doumas M, Welchman AE. 2010. Combining multisensory temporal information for movement synchronisation. Experimental Brain Research 200(3-4):277-282. DOI 10.1007/s00221-009-2134-5. PMID 20039025. [ABS]
53. Wohlschlager A, Koch R. 2000. Synchronization error: an error in time perception. In: Desain P, Windsor L (eds), Rhythm Perception and Production:115-127. Swets and Zeitlinger. [META; finding as reported in Repp 2005]

Counts: 53 sources; 23 FT, 18 ABS, 12 META. Of the 41 sources whose own text supplied a number or finding (FT plus ABS), 23 are FT. Every META source whose content is used above was read through a named FT secondary source, or is a method reference (Jacoby 2015, Vorberg and Wing 1996, Davies 2009, McFee 2015) whose implementation was read in code.

Not re-read here and left as the code or design already cites them: Wing and Kristofferson 1973, Semjen, Schulze and Vorberg 2000, Robinson 1934 via Kosinski 2013, Precision Microdrives datasheets, Koo and Li 2016, Parsons et al. 2019, Tranchant et al. 2016, Taheri et al. 2014, Ghai et al. 2018 (movement-disorders note).

### Assumptions behind the simulations and track analysis

- Track analysis: `Easy_Lemon.mp3` decoded as the game decodes it (`decode_mono`, 22050 Hz) for the chart, and at its native 44.1 kHz for the attack analysis; librosa 0.11.0 on Python 3.14. Quarter-note grid by a comb search over a percussive (HPSS) spectral-flux envelope at 2.9 ms hops, period 700 to 760 ms. Off-beat means a phase of 0.25 to 0.75 of the beat. Attack: the 2 ms RMS envelope of the signal above 2 kHz, steepest 3 ms rise in the 150 ms before to 60 ms after the note, 20 percent of the rise from the preceding minimum to the following peak; checked on synthetic clicks and kicks (error within 1 ms).
- Chart-lag simulation: 120 synthetic onsets at 500 ms with low-level noise, onsets spread over the frame grid, run through `onset_strength` and `beat_track` with the game's defaults.
- Lead simulation: the real 107-note chart; press offset = w x (RT - lead) + (1 - w) x (-30 ms + noise SD 30 ms), RT normal 230 ms SD 40; the controller exactly as `_adapt_lead` (every 4 scored presses, median of 8, gain 0.5, step 25 ms, dead-band 5 ms, clamp 0 to 700 ms, start 350 ms); presses beyond 300 ms drop out as Miss; 200 runs a cell.
- Rh1 simulation: per-person means normal with the stated mean and between-person SD 25 or 35 ms, plus a sampling error of SD 4 ms; one-sided Wilcoxon signed-rank (scipy); 4,000 runs a cell.
- Correction-gain simulation: linear phase correction on the real chart's gaps, A(k+1) = (1 - alpha) A(k) + T(k) + M(k+1) - M(k), timekeeper SD 15 or 20 ms scaled by the square root of the gap over 732 ms, motor SD 5 to 12 ms, pairs with gaps under 1.2 s, the notebook's estimator; 3,000 runs a cell.
