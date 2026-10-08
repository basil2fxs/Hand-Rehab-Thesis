# Syllables mode: deep research audit

1 October 2026. Scope: the Syllables mode (mode key `syllables`) as a reader with dyslexia meets it from the hub under a D code: `app/finger_rehab/game/modes/syllables.py`, `syllables_words.py`, `syllables_foils.py`, `syllables_profiles.py`, the `syllables:` block of `app/config/default.yaml`, the speech assets, the syllables screen and results-screen advice, the case procedure in `FINAL TRIAL RESULTS/README.md` and `app/docs/research/design_check.md` Section 8, and the notebook's Syllables chapters. The healthy-study block (classic profile, 12 words at rung 3) and its checks S6 and S7 left the study on 28 September 2026 and appear only where they still shape the code.

Tags: [FT] full text read, with the table or section named; [FT, PMC page] full text read from the PMC article page; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result on the real mode code or a stand-alone model, under the assumptions at the end of Section 7; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository. Values in Section 1 are (code) unless labelled. Line numbers refer to commit d6a93a7, which matched the working tree for every file cited when this was written (the four Syllables modules are unchanged since 30 September; `default.yaml`, the notebook and `screens.py` move with edits for other modes, so functions and keys are named beside lines). Notebook lines are lines of cell 2's source.

---

## 1. What the mode does now

### 1.1 Which block a case reader gets

- Procedure: code D01 upward, the reader's real age, SESSION Free play, then the Syllables card; each reader is one described case, one session each, no baseline (`FINAL TRIAL RESULTS/README.md`, "Syllables"; `design_check.md` Section 8).
- Profile: `age_band: auto` (default.yaml 1169) resolves through `resolve` and `band_for_age` (`syllables_profiles.py` 172-203): under 10 plays 6-9, 10 to 12 plays 10-12, 13 to 15 plays 13-15, 16 to 59 plays 16+, 60 and over plays 60+, a blank age plays 6-9. Classic (the healthy-study design) runs only if the config names it.
- Layout: `sections: true` (default.yaml 1178) gives every profile except classic the sectioned sitting (`syllables.py` 778).
- Size and settings: 30 words (default.yaml 1195); a fresh seed per block, logged in raw.csv as `syllables_config` (`engine.py` `begin_syllables_block`); `supervised: true` from the config, with no on-screen control (default.yaml 1273); speech backend `auto` (default.yaml 1285-1288). Test Mode is off by default and, when on, cuts the block to a demo (`engine._test_mode_trials`); `block_stats` records `demo`.

### 1.2 The sitting a case reader plays

| Step | What happens | Value | Where |
|---|---|---|---|
| Section plan | Review (unrelated F1 foils, moves no ladder), hear and pick, build the word, then a quick-look speed check for 10 to 59 | 4 review, 18 pick, 8 build words; 16 speed trials (10 to 15) or 20 (16+); none for 6-9 and 60+ (arithmetic from the rules) | `_plan_sections` 820-836; REVIEW_MAX 506, BUILD_SHARE 509; profiles 145, 153, 160 |
| Section card | One card per section, sticker per section; no round breaks in the sectioned sitting | 3.0 s | SECTION_CARD_S 498; `_advance_section` 844-864; `_after_word_bookkeeping` 2250-2259 |
| ATTEND | Word spoken; printed only while the rung is at or under the profile's print rung (6-9 up to 3, 10-15 up to 2, adults never) | 3.0 s | default.yaml 1215; `show_print` 1092-1098; profiles 134-167 |
| MODEL | Each syllable spoken as it sounds in its word, slot lit, then the whole word again; skipped for 16+ and 60+ and in build | beat at least 0.9 s; 0.5 s quiet after each file; 1.2 s after the blend | `_update_model` 1498-1543; MODEL_GAP_S 467, BLEND_HOLD_S 468; default.yaml 1184 |
| Option set | Four written chunks, one per finger; silent onset; target lane by least-used rule, never three in a row | | `_spawn_set` 1636-1706; `draw_target_lane` (foils 531-555) |
| Respeak | Syllable said again at spawn: rungs 1 to 3 (6-9), 1 to 4 (10-15), every rung (16+, 60+); never while building; sound 175 ms (6-9) or 100 ms (10-15) after the print | | 1688-1690; profiles 134-167 |
| Lockout | Presses in the first 0.25 s are anticipations | 0.25 s (floor 0.2) | default.yaml 1248; 607 |
| Time allowed | Per rung 6.0, 6.0, 5.5, 5.5, 5.0, 5.0, 4.5, 4.5 s (6-9, floor 4.0); 4.8 to 3.0 (10-12); 4.2 to 2.4 (13-15, 60+); 16+ fall staircase from 3.6 s between 1.0 and 4.5 s; tiles drop into place and stay still with a time bar | | default.yaml 1241; MIN_FALL_S 494; profiles 140-163; docstring 200-202 |
| Prompt | One buzz on the target finger at step x fall, steps 0.6, 0.75, 0.9 (6-9) or 0.75, 0.9 (10-15), none for adults; never before the median of the last 8 unaided correct times plus 300 ms once 3 exist; never after 0.9 of the fall | | `_prompt_delay_s` 1587-1600; `_answer_rts` 695; default.yaml 1210-1212 |
| Prompt fade | Per word: unaided right moves the word one step later (past the last step, no buzz), unaided wrong or a miss one step earlier, a prompted answer leaves it | | `_update_prompt_fade` 1621-1634 |
| Right press | Tile lifts and is held | 0.8 s | CORRECT_HOLD_S 455; 1768-1777 |
| Wrong press | Tile greys; a second wrong press shows the answer at once (glow, syllable spoken, slot filled and marked shown) | | 1778-1794; `_show_answer` 1836-1853 |
| Time out | Answer shown the same way | glow 1.5 s | `_miss_set` 1824-1834; MISS_GLOW_S 461 |
| Word end | Slots close into one word, held silent, then spoken; a word with a shown slot counts as missed | hold 1.5 s (1.0 s adults) | `_read_whole` 2232-2248; `_after_word` 2216-2230 |
| Returns | A missed word returns after 2, then 4 other words, then retires; at most 6 returns a block; review words never return | | `_park_word` 2114-2139; MAX_RETURNS 488; `_begin_word` 1378-1384 |
| Gaps and cap | 1.0 s between sets, 1.5 s between words; block ends at the first word boundary past 20 min | | default.yaml 1243, 1222, 1223 |
| Quick look | Real word of up to 9 letters flashed, hash-mark mask, four same-length look-alike words for up to 4 s, one press; exposure starts at 700, 600 or 500 ms, 80 ms steps between 100 ms and 1.5 s, down after every right answer until the first error, then 3-down-1-up | mask 150 ms | `_begin_speed_trial` to `speed_threshold` 2348-2639; constants 499-507 |

Block length for 30 words (simulation): 12.8 to 14.2 min (6-9), 15.5 to 18.0 (10-12), 14.8 (13-15) and 13.0 to 16.8 (16+), depending on the reader's speed. The config comment's "30 words is about 11 minutes" (default.yaml 1185-1194) predates the sections.

### 1.3 The material

- Child bank: 695 words of 2 to 4 syllables (band A 267 two-syllable and 25 three-syllable; B 83 and 109; C 21 two, 89 three and 101 four-syllable); draw pools A 292, B 192, C 211 (`all_words`, `words_for`). Teen pool 85 words (3 to 4 syllables), adult pool 95 (3 to 5), made-up 60 (3 to 4 syllables, every chunk a closed syllable such as ban-bit-cum, all stressed on the first syllable; 102 of their 200 chunk tokens also occur in the child bank) (`load_pools`).
- One split per word, at the spelling boundary nearest the spoken one (`syllables_words.py` 23-41). The -er family is split two ways: 12 words end in the chunk er (scoot-er, toast-er, riv-er) and 65 split before the consonant (but-ter, din-ner).
- 792 unique chunks; 491 of them occur in only one word.
- Weak syllables: the manifest's `syllable_map` marks 1,241 of 2,687 syllable slots as heard with a weak vowel; by pool, child band A 43 percent, B 44, C 53, teen 55, adult 60, made-up 0 (arithmetic from `app/assets/speech/manifest.json`). On a weak syllable every vowel swap is barred and F3 becomes F7 (`_foil_kinds` 1708-1742; `make_foil` 457-514), and the vowel family is skipped (`_pick_family` 880-906).
- Age shares of made-up words: 16+ 40 percent, 60+ 30, 10 to 15 20, children 0 (profiles 139-162).

### 1.4 Foils, the rung and the families

- Kinds (`syllables_foils.py` 4-80): F1 far, F2 onset, F3 vowel, F4 reversal (b/d, p/q, n/u, m/w; first reversible letter only), F5 adjacent transposition, F6 another syllable of the word, F7 coda, F8 pseudohomophone (off), F9 affix (teens and adults).
- Legality: not the target, 1 to 5 letters, a vowel letter, letter pairs seen in the bank, and a sound key that rejects sound-alikes for every kind but F8; a kind that cannot be made falls back down a chain to F1 and the kind actually produced is logged (`is_legal` 266-282; `sound_key` 248-263; `make_foil` 457-514).
- Classic: the rung (1 to 8) sets foil kinds (RUNG_SCHEDULE 113-122), time and respeak, by 3-down-1-up with one rung each way (`_move_rung` 2028-2059).
- Sectioned (every case profile): foils come from one confusion family at a time (`_section_kinds` 945-975). Level 0 is three F1 foils; level L puts L family foils in the set (build: always one F6 plus up to two family foils). Three unaided right first presses on that family raise the level, an error lowers it, a further run of 3 at level 3 marks the family "mastered" and drops it (`_move_family` 977-1014). Each family is taught for 3 words, then the next open one (FOCUS_WORDS 508; `_advance_focus` 908-935). Levels restart at 0 in every block (docstring 220). The rung still moves 3-down-1-up but now sets only time, print and respeak.
- Families: children onset, vowel, coda, reversal, position, order; teens add affix; adults vowel, affix, coda, position, onset (profiles 74-77).
- Adult (16+) fall staircase: four unaided right in a row shorten the fall by 0.17 s, an error or miss lengthens it by 0.20 s, within 1.0 to 4.5 s, replayed sets excluded; the threshold is the mean fall over the last 12 sets and the mean of the last 6 reversals (`_move_fall` 2061-2098; `fall_threshold` 2100-2112).

### 1.5 Speech

- Kokoro-82M v1.0, voice bf_emma (British); manifest metadata: accent en-GB, chunk_form spelling, syllable_form word, chunk RMS -20 dBFS, word loudness -23, latency_ms not measured, rendered 25 September (words, chunks) and 29 September 2026 (in-word syllables) (`app/assets/speech/manifest.json`).
- Words are phonemised by espeak-ng (British); each word's syllables are cut from its phonemes at the written chunks and each piece is synthesised on its own (`app/scripts/syllables_tts.py` docstring). 343 in-word syllable files and 923 spelt chunk files are on disk.
- No listener check of any file exists: `syllables_recording_kit.py check` lists missing files only.
- Backend `auto` plays a file and falls back to the macOS `say` command when a file is missing (`_speak` 2893-2972).

### 1.6 Age profiles

| Profile | Words | Made-up | Time allowed | Print before choice | Model | Respeak | Prompt | Families | Quick look |
|---|---|---|---|---|---|---|---|---|---|
| 6-9 (also blank age) | child bank, bands A to C | 0 | 6.0 to 4.5 s by rung | rungs 1 to 3 | yes | rungs 1 to 3 | 0.6, 0.75, 0.9 | child | none |
| 10-12 | bank B and C plus teen pool | 20% | 4.8 to 3.0 s | rungs 1 to 2 | yes | rungs 1 to 4 | 0.75, 0.9 | teen | 16 trials from 700 ms |
| 13-15 | as 10-12 | 20% | 4.2 to 2.4 s | rungs 1 to 2 | yes | rungs 1 to 4 | 0.75, 0.9 | teen | 16 from 600 ms |
| 16+ | adult pool, 3 to 5 syllables | 40% | staircase 3.6 s start, 1.0 to 4.5 | never | no | always | off | adult | 20 from 500 ms |
| 60+ | adult pool, 3 to 4 | 30% | 4.2 to 2.4 s | never | no | always | off | adult | none |

(`syllables_profiles.py` 132-168.)

### 1.7 Scoring, feedback and what the reader is told

- Points: 6 for an unaided right first press, 3 for a prompted right answer or a right press after a wrong one, 0 for a miss; streak stars at 3, 5 and 8 words all right first time; a sticker per section (`_score_set` 1920-1937; `_finish_word` 2180-2193; `_advance_section` 848).
- Section cards (`syllables_screen.py` SECTION_COPY): "Listen, then press the finger under the part you hear."; "Hear the word, then build it one part at a time."; "A word flashes up. Then pick the word you saw." Nothing tells the reader that a buzz may come or what it means.
- The line "Sit with your child and say the syllables together." is drawn only on the round-break screen of the child style (`_draw_break`), which the sectioned sitting never shows.
- The results-screen advice reads first-press accuracy, which counts prompted answers, and suggests band changes (`screens.py` `_syllables_advice`, 6165).
- R replays the chunk once per set (the whole word while building); the legend shows for adults only (`replay` 1280-1298; `controls_lines`).

### 1.8 Logging and block_stats

- trials.csv: one row per option set; the stimulus string carries every option with its lane and kind, every press with its time from spawn, `first`, `err`, `rt`, `pon`, `pstep`, `prompt`, `pat` (time of the buzz when one fired), `pclass`, `prof`, `lex`, `print`, `replay`, and in the sectioned sitting `sec`, `fam`, `flv`, `fn`, `shown`; speed rows carry `expo` (docstring 283-319; `_pack_stimulus` 2289-2345).
- Not logged: whether the target syllable was heard with a weak vowel, and the planned buzz time on sets where no buzz fired.
- block_stats (3012-3118): `first_press_accuracy` (prompted right answers count as right), `unaided_accuracy`, prompt classes, rung trace, `confusion_by_kind` (counts with no denominators), `fall_threshold` (16+), and `sections` (accuracy by section and family, family levels, answers shown, speed threshold).

### 1.9 The notebook's route for a case block

- `syllable_set_frame` (14084) unpacks set rows; `sec_syllables` (14422) sends single-section rows of the classic or 6-9 design to the full chapter (accuracy by rung with the 25 percent chance line and the 80 percent target, rung trace, foil capture with appearance denominators, position, word length, RT by rung, returns, per-lane counts, prompt classes by exposure, engagement); single-section rows of other profiles to `sec_syllables_profiles` (14730); and sectioned rows to `sec_syllables_sections` (14321), which prints first-press accuracy by section and by family and level, the count of answers shown, and a speed table with the stored reversal threshold.
- `sec_syllables_checks` (29139) reads only single-section classic and 6-9 rows; on a case block it prints "No syllable blocks of the child design in this selection." `cohort_sitting_people` (21420) keeps hub-only codes out of n. S6 and S7 print DROPPED (24952-24961, 26837-26856).
- Consequence: every case block (sectioned by default) reaches only `sec_syllables_sections`. No prompt table, no foil capture with denominators, no answer times and no adult fall threshold is printed for it, and its accuracy counts prompted answers as right. The author's data collection plan promises accuracy against chance and the 80 percent target and the foil captures for these sessions, and describes the block as 40 words in rounds of 10 with a 30 s break; both are out of date.

### 1.10 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| PA instruction: d 0.86 on PA, 0.53 on reading; PA with letters beat PA alone | syllables.py 23-27 | Ehri et al. 2001 | Verified through the NRP report [FT]: 52 studies, 96 comparisons; letters 0.67 against 0.38 on reading; for disabled readers reading 0.45 and spelling 0.15 (not significant); computers 0.33 against 0.55 (Q1, Q2) |
| Phonics is the only family with a confirmed effect in reading disability, g = 0.32 | 27-29 | Galuschka et al. 2014 | Verified [FT]; the approaches did not differ from each other (p = .788) and the effect was 0.198 after trim and fill |
| Graphosyllabic analysis improved struggling adolescents' decoding; whole-word practice did nothing | 29-33 | Bhattacharya and Ehri 2004 | Verified [ABS]; the benefit was mainly at a Grade 3 reading level |
| Syllable-based training improved German poor readers' fluency; both studies used written syllables, "which is what the falling tiles are" | 33-36 | Mueller et al. 2017 | Verified [FT]: ES 0.82 on word recognition fluency, none on comprehension; 16 group sessions of 45 min; readers below the class median, not diagnosed. Partly: neither study used a four-option recognition task |
| The syllable is the right grain to start at (46 percent of four year olds tapped syllables, none phonemes) | 36-41 | Liberman et al. 1974; Ziegler and Goswami 2005 | Age 4 to 6 data [META, ABS]; for readers of 7 and older the foils test contrasts inside the syllable (Q1) |
| GraphoGame shape: multiple-choice audio to print, adaptation to about 80 percent correct, immediate positive feedback | 58-62 | Richardson and Lyytinen 2014 | Verified [FT]; the same source adds re-picking after errors, separate static assessment levels and 8 to 12 minute sessions (Q2, Q7) |
| The EEF trial found no effect | 63-68 | Worth et al. 2018 | Verified [FT]: ES -0.06 (-0.23 to 0.12) against business as usual that included other literacy support |
| Negligible overall GraphoGame effect; adult interaction the only significant moderator | 68-73, 337-339 | McTigue et al. 2020 | Verified [ABS]: 19 studies, g = -0.02; high adult interaction g = 0.48 |
| Spaced retrieval beats massed for word learning in language disorder | 81-83 | Leonard and Deevy 2020 | Verified [FT]: preschool children with SLI and typical peers, novel words |
| Adults with dyslexia learn worse from immediate feedback, so negative feedback is quiet and late | 86-90, 126-131 | Gabay 2021 | Verified [ABS] for probabilistic reinforcement learning. In the sectioned sitting the answer is shown at once after a second wrong press (code) |
| Time delay is evidence-based for sight words (intellectual disability); progressive beat constant delay indirectly | 103-117 | Eyler and Ledford 2024; Browder et al. 2009; Walker 2008 | Verified [ABS] with the stated population limits; constant time delay starts with 0 s trials and uses fixed 2 to 5 s delays (Horn et al. 2023 [FT, PMC page]) |
| The floor (median answer time plus 300 ms) is how the method sets the delay from the learner's own latency | 122-126 | none | Not supported as built: the sample is censored at the buzz (Q5) |
| The unprompted correct rate is the learning measure | 136-141 | none | Partly: at fixed knowledge it falls from 0.84 to 0.29 as the reader slows (simulation, Q5) |
| 3-down-1-up converges on 79.4 percent (Levitt), the region GraphoGame targets | 142-149; notebook S1 | Levitt 1971 | Partly: equal steps miss the nominal target (Garcia-Perez 1998 [ABS]); 0.80 to 0.84 on ladder-moving sets in the classic design; in the sectioned sitting the rung sets only time and climbs to its ceiling (simulation, Q4) |
| Children are 1.8 times slower at 10 and 1.5 at 12; time pressure separates dyslexic binding | 159-169 | Hale 1990; Kail 1991; Aravena et al. 2013 | Verified [ABS] (Hale, Aravena) |
| 4-down-1-up settles at 84.1 percent; a step ratio of 0.85 is near Garcia-Perez's | `_move_fall` 2065-2067 | Levitt 1971; Garcia-Perez 1998 | Misstated: with a ratio of 0.8415 the 4-down-1-up rule converges on 85.84 percent [ABS] |
| Extra-large letter spacing improves dyslexic reading | 249-252 | Zorzi et al. 2012 | Verified [FT, PMC page] for text (errors 6 against 11.8); the tiles hold 1 to 5 letters |
| Reversal and letter-position foils follow the error literature | foils 17-25 | Terepocki et al. 2002; Kohnen et al. 2012 | Verified [ABS]; reversals are common in all beginners and do not predict reading (Treiman et al. 2014 [FT, PMC page]); letter position dyslexia is rare and needs migratable words (Q3) |
| Speed shows adult dyslexia more than accuracy | profiles 10-16 | Reis et al. 2020; Callens et al. 2012 | Verified for Callens [FT] |
| A foil kind picked on under 5 percent of its appearances is not working | notebook `sec_syllables_profiles` | Tarrant et al. 2009 | Misapplied: a group criterion over 73 to 146 examinees per item [FT] |
| S4 source "Kornell, Castel, Eich and Bjork 2009, Psychology and Aging 25(2):498-503"; "Leonard and Deevy 2020, JSLHR 63(11)" | notebook `MODE_LIT["syllables"]` (27659 onward) | | Wrong year (2010) and a study of adults learning painters' styles; Leonard and Deevy is 63(10):3252-3262 |
| S2 reference "letter-position foils hardest" | same | Kohnen et al. 2012 | Not supported: three selective cases [ABS] |
| RT anchor "four-choice RT in adults is about 450 to 550 ms" | notebook `sec_syllables` (14600) | none | No source given |
| "Hence the adult line on the rest screen" | syllables.py 72 | McTigue et al. 2020 | The line is never shown in the sectioned sitting (code) |

Also cited in the code and not re-read here: Mehringer et al. 2020, Ahmed et al. 2020, Kornell, Hays and Bjork 2009, Metcalfe, Kornell and Finn 2009, Metcalfe 2017, Foerde and Shohamy 2011, Fitts and Seeger 1953, Salmoni et al. 1984, Winstein and Schmidt 1990, Sigrist et al. 2013, Stevens et al. 2021, Kail 1991, Proctor and Schneider 2018, Wolff et al. 1990, Wery and Diliberto 2017, Kuster et al. 2018, Deci et al. 1999, Butler et al. 2007, Marsh et al. 2012, Share 1999, Kyte and Johnson 2006, Huemer et al. 2010, Gray et al. 2018, Kearns 2015, Herrmann et al. 2006, Kalyuga et al. 2003, Froyen et al. 2008 and 2009, Ocal and Ehri 2017, Hilte and Reitsma 2006, Cox and Palethorpe 2007, Brown 1988, Haladyna et al. 2002, Bruck and Treiman 1990, Kirkby et al. 2025.

### 1.11 Pilot blocks on disk (rig check only)

Seven choice-design blocks dated 4 to 29 September 2026 hold 60 option sets; none ran the sectioned sitting, the 6.0 s fall or the in-word syllable audio. In the 23 to 25 September blocks (fall 4.0 s, a constant buzz delay), 32 of the 39 sets with a prompt class were answered after the buzz, 6 unaided and 1 not at all; the median unaided right answer took 1,845 ms against 2,718 to 3,469 ms for answers after the buzz, which came at 2.4 to 3.0 s (pilot). The rung stayed at 1 in those blocks (pilot); prompted answers do not move it (code).

---

## 2. Research questions and findings

### Q1. What does the task measure, and what is the evidence for print-based syllable work in dyslexia?

- Phonemic awareness instruction (52 studies, 96 comparisons): d = 0.86 on PA, 0.53 on reading and 0.59 on spelling; with letters 0.67 (48 cases) against 0.38 without (42) on reading at the immediate test, 0.59 against 0.36 at follow-up; for disabled readers reading 0.45 (17 cases) at the immediate test and 0.28 (8) at follow-up, spelling 0.15, not different from zero; programs of 5 to 18 hours did best (National Reading Panel report, Chapter 2 Part I, executive summary and Tables 3 and 4 [FT]; the journal version is Ehri et al. 2001 [META]).
- Randomised trials in children and adolescents with reading disabilities (22 RCTs, 49 comparisons, 1,138 treated and 764 control participants): phonics g' = 0.322 (0.177 to 0.467, I squared 0, 29 comparisons) was the only approach whose interval excluded zero; phonemic awareness instruction 0.279 (-0.244 to 0.802, 3 comparisons) and fluency training 0.301 (-0.105 to 0.707, 5); the approaches did not differ significantly (p = .788); trim and fill took phonics to 0.198 (0.039 to 0.357); phonics on spelling 0.336 (0.062 to 0.610, 10 studies) (Galuschka et al. 2014, Results and Tables 1 to 4 [FT]).
- English-speaking poor readers (14 studies, 923 participants): phonics improved word reading accuracy, SMD 0.51 (0.13 to 0.90; 11 studies), low-quality evidence; word reading fluency 0.45 (0.19 to 0.72; 4 studies), moderate quality; comprehension 0.28 (-0.07 to 0.62) (McArthur et al. 2018, Abstract [FT, PMC page]).
- Syllable-level print work: graphosyllabic analysis of 100 multisyllabic words helped adolescents below grade level decode new words and remember spellings, whole-word study gave no transfer, and the benefit sat mainly at a Grade 3 reading level (Bhattacharya and Ehri 2004 [ABS]). In German Grade 4 poor readers (below the class median on word recognition and comprehension), 16 group sessions of 45 minutes on the 500 most frequent syllables gave ES 0.82 on word recognition fluency and no comprehension effect (43 trained against 32 wait-list, randomised by class) (Mueller et al. 2017, Methods and Table 3 [FT]). A syllable-based German app for low-skilled Grade 2 readers (66 against 66 wait-list) improved word recognition and phonological recoding but not comprehension (Hess et al. 2024 [ABS]).
- Syllable awareness is early: segmentation develops from syllables to phonemes (Liberman et al. 1974 [META]); English readers need several grain sizes because English spelling is inconsistent (Ziegler and Goswami 2005 [ABS]). Adults with dyslexia keep phonological deficits (Bruck 1992 [META], as cited in Vender and Delfitto 2025 [FT]).

Bearing. In every profile but the review, the four tiles differ from the target by one onset, vowel, coda, letter order or affix (Section 1.4). The task is therefore a receptive, speech-cued grapheme to phoneme discrimination inside written syllables of multisyllabic words: phonics with letters at the syllable grain, in the terms of the meta-analyses, more than syllable awareness. The evidence supports print-linked phonics for readers with reading disability at small to moderate effect sizes on standardised outcomes; none of it tested a four-option recognition game of this kind.

### Q2. What does the evidence on computer and game delivery, GraphoGame included, allow a case report to claim?

- Computer-delivered phonics, English-speaking poor readers: word reading accuracy SMD 0.18 (-0.17 to 0.54; 4 studies, 124 children) against 0.70 (0.17 to 1.23; 7 studies, 577) when a person delivered it; nonword reading accuracy 0.31 (-0.02 to 0.64; 6 studies) against 1.12 (0.48 to 1.76; 4 studies); the authors judged the subgroups too small for conclusions (McArthur et al. 2018, subgroup analyses 1.10, 1.11, 2.5 and 2.6 [FT, PMC page]). PA taught by computer: reading d = 0.33 (8 cases) against 0.55 for other delivery, spelling 0.09, not significant (NRP report, Table 3 and text [FT]). Across all treatment approaches, programs run on a computer with a teacher: g' = 0.364 (0.085 to 0.643, 9 comparisons) (Galuschka et al. 2014, Table 2 [FT]).
- GraphoGame. The method pairs a heard segment with its written form among alternatives, adapts to about 80 percent correct per level, makes the child re-select the right answer after an error, gives static assessment levels at points in training, and recommends sessions of 8 to 12 minutes in a quiet room with good headphones; some children concentrate better with an adult present (Richardson and Lyytinen 2014, sections on the method, feedback and playing sessions [FT]). Across 19 studies the effect on word reading was g = -0.02; studies with high adult interaction averaged g = 0.48 (McTigue et al. 2020 [ABS]). The largest English trial (398 Year 2 pupils randomised, 362 analysed) found ES -0.06 (-0.23 to 0.12, p = 0.48) against business as usual that included other small-group and one-to-one literacy support; playing time averaged 6 and 9 hours against a recommended 8.3 to 12.5 and showed no relation to outcome (Worth et al. 2018, executive summary and Table 1 [FT]). A Dutch cluster trial (247 first graders, 10 to 15 minutes a day for up to 7 weeks, about 28 sessions) improved letter knowledge against two control conditions with a small classroom-wide fluency benefit (Glatz et al. 2023, Abstract [FT]). Children who played at school played more and were more engaged than at home, and only parental involvement was associated with engagement and outcome (Ronimus and Lyytinen 2015, Abstract [FT]).
- Untrained controls improve too. 54 Polish children with dyslexia (9.0 to 13.2 years) randomised to an action or a phonological video game for 16 sessions improved reading speed in 82 percent and accuracy in 61 percent, and an untrained dyslexic group of 16 showed the same gains; there was no group by time effect (Luniewska et al. 2018, Results and Methods [FT]).
- Adults. 44 Italian young adults with dyslexia: an app played 15 to 20 minutes three days a week for 8 weeks, including a two-option "listen and choose the right match" task with phonologically or visually similar foils and a brief-exposure reading task, gave group by time effects of d = 0.70 on text reading and 0.46 on word reading, 0.39 on nonwords (p = 0.079), none on lexical decision or comprehension; allocation followed enrolment order (24 against 20, 20 and 18 completers) (Vender and Delfitto 2025, Participants, Literacy intervention and Results [FT]).

Bearing. A described case can say the game ran, how the reader played it and which contrasts caught them. It cannot attribute any pre to post change to the game: computer-only phonics has the weakest subgroup effects, the closest English game trial was null, and untrained dyslexic children improve over a few weeks by about as much as trained ones.

### Q3. Which foils make a set hard, and what can one session show about a reader's confusions?

- Letter reversals: 10 year olds with reading disability made more orientation confusions than average readers in reception and production (Terepocki et al. 2002 [ABS]); among 130 children aged 5 to 6, reversals made up 0.15 and 0.13 of letter productions in the speech-sound-disorder (92) and control (38) groups, 0.57 and 0.53 of left-facing letters and 0.05 and 0.04 of right-facing ones; reversal rate did not relate to reading 2.75 years later, and later poor readers made more errors but no more reversals (Treiman et al. 2014, Table 1 and Results [FT, PMC page]).
- Letter position: the first three cases of selective developmental letter position dyslexia in English were missed by standard tests and found only with migratable words (Kohnen et al. 2012 [ABS]).
- Distractor functioning is a group property: in 514 four-option items (1,542 distractors, 73 to 146 examinees per test), a distractor was non-functioning when fewer than 5 percent of examinees chose it or it discriminated the wrong way; 52.2 percent functioned and items averaged 1.54 functioning distractors (Tarrant et al. 2009, Methods, Results and Table 2 [FT]).
- Error counts per session (simulation, 6-9 to 13-15 profiles, assumed reader): 2 to 7 first-press errors in a 30-word block. A reader whose vowel foils capture 30 percent against 8 percent for the other near kinds was detected (p < 0.05, Monte Carlo multinomial test over near kinds, errors expected in proportion to appearances) in 0.08 of single sessions, 0.43 of three-session sets and 0.61 of six-session sets; a reader with equal capture gave 0.02, 0.02 and 0.00. A test that keeps F1 in its null gave false positives in 0.28, 0.90 and 0.99 of runs, because far foils are rarely chosen by design (simulation); the notebook's capture chart sets every kind side by side, F1 included, with no test.
- Weak syllables: 43 to 60 percent of real-word targets are heard with a weak vowel (Section 1.3), so vowel foils fall almost only on full-vowel syllables and, for adults, mostly on made-up words (made-up words have no weak syllables) (arithmetic). Ziegler et al. 2009 found dyslexic children's speech perception deficits only in noise, with place of articulation most affected [ABS]; onset and coda foils that differ by place are the ones a noisy room would make hardest.

Bearing. One session yields too few errors for a confusion profile; the capture chart needs appearance denominators and a null that leaves out F1. Reversal and transposition captures describe the session and must not be read as orientation or letter position difficulties. Accuracy on real against made-up words differs in foil mix as well as lexicality.

### Q4. Do the ladders converge where the code says, and what do the levels mean?

- Fixed-step staircases converge on their nominal targets only when the down and up steps stand in set ratios: 0.2845, 0.5488, 0.7393 and 0.8415 for 1, 2, 3 and 4-down-1-up, which give 77.85, 80.35, 83.15 and 85.84 percent correct; with equal steps the transformed rules miss their presumed targets, and short staircases (up to 20 reversals) are biased and imprecise unless the up step exceeds half the spread of the psychometric function (Garcia-Perez 1998 [ABS]). Unequal steps after every trial can target any point (Kaernbach 1991 [ABS]). Gradient-descent learners on binary tasks learn fastest at an error rate of 15.87 percent, about 85 percent correct (Wilson et al. 2019, derivation [FT]); GraphoGame aims at about 80 percent (Richardson and Lyytinen 2014 [FT]).
- Classic design (simulation, 150 blocks each): accuracy over the sets that move the ladder (unaided right, unaided wrong, misses) was 0.84, 0.80 and 0.80 for a mild reader, a weaker reader and a weaker slower reader, while the unaided rate over all sets was 0.65, 0.69 and 0.42; the mean rung in the second half was 4.8, 2.3 and 2.1. The level reached separates readers; accuracy does not.
- Sectioned sitting (every case profile, simulation): the rung only moves time, print and respeak, so it climbs while the family ladder keeps foils easy; for the weaker reader the mean rung in the second half was 6.3 with 12 percent of sets at rung 8. That reader's unaided accuracy fell from 0.84 at rung 1 to 0.59 at rung 8, partly because a shorter fall brings the buzz earlier.
- Family ladder (simulation, 6-9, 150 blocks per reader): each family got a median of 7 to 17 sets a block (5th to 95th percentile 3 to 46); "mastered" was reached in at most 1 percent of blocks; the final level median was 2 for a reader whose near foils capture 8 percent and 1 for readers at 20 and 30 percent; first-press accuracy by family stayed between 0.82 and 1.00 across all three readers.
- Mastery criteria in applied research: of 84 skill-acquisition studies with session-based criteria, 90 percent correct was the commonest level (32 percent of studies), 100 percent was used in 20 percent and 80 percent in 18 percent; two consecutive sessions was the commonest span (60 percent) (McDougale et al. 2020, Table 2 [FT, PMC page]). In three children with autism, targets mastered at 90 percent over one session were maintained best 3 to 4 weeks later, against 80 and 50 percent criteria (Fuller and Fienup 2018, Results [FT, PMC page]).
- Adult fall staircase (simulation, 16+, 150 blocks per reader): for readers with median decision times of 1.2, 1.8 and 2.4 s the last-12 fall had medians 2.39, 3.33 and 4.22 s and the last-6-reversal mean 2.36, 3.25 and 4.15 s, with 17 to 21 reversals in 134 sets; in every block the last 12 sets were build sets. At a fixed 1.2 s speed, raising per-foil capture from 5 to 7 to 9 percent moved the last-12 median from 2.71 to 2.90 to 3.35 s, because the family ladder eases foils after errors and the fall absorbs the rest.

Bearing. The 79.4 percent figure holds only loosely, and only in the classic design on ladder-moving sets. In the case sessions the rung is a time setting near its ceiling, the family levels say little within one block and reset every block, "mastered" is a run of three far below any criterion in the skill-acquisition literature, and the adult threshold mixes speed with foil discrimination and is set by the build section.

### Q5. Is the progressive-delay prompt sound, and is the unprompted correct rate a learning measure?

- Time delay: constant time delay presents the controlling prompt at 0 s first, then withholds it for a fixed interval; studies teaching reading to students with intellectual disability or autism used 2 to 5 s; unprompted correct responses count towards a mastery criterion such as 90 or 100 percent; the review's worked example of computer-delivered time delay shows a word with four pictures in the screen corners (Horn et al. 2023, Introduction, Table 1 and Results [FT, PMC page]). Time delay is an evidence-based practice for sight-word and picture recognition in severe developmental disabilities (30 experiments; Browder et al. 2009 [ABS]); results were mixed but supportive for young children with intellectual and developmental disabilities (33 sources; Eyler and Ledford 2024 [ABS]); constant delay came with more errors to criterion and later transfer of control than progressive delay, by indirect comparison over 22 studies (Walker 2008 [ABS]). Prompt delay is recommended for prompt dependence on a suggestion by Touchette (1971), and "no empirical studies have directly evaluated" it; most-to-least prompting is recommended for learners who err often before the prompt (Cowan et al. 2023, Table 1 and footnote [FT]). No study of a vibration prompt in reading was found.
- The game's delays at a 6.0 s fall are 3.6, 4.5 and 5.4 s, and 2.7 to 4.05 s at 4.5 s (arithmetic), comparable with the 2 to 5 s intervals above, with no 0 s stage.
- Speed confound (simulation, 6-9 sectioned, 200 blocks per reader, fixed foil capture): for median decision times of 1.5, 2.5, 3.5 and 4.5 s the unaided correct rate was 0.84, 0.63, 0.43 and 0.29, the share of sets prompted 0.10, 0.35, 0.56 and 0.71, and first-press accuracy counting prompted answers 0.92, 0.93, 0.95 and 0.95.
- Censored floor (simulation): the floor's sample holds only answers that beat the buzz, so at block end its median was 1.86, 2.35 and 2.54 s against true medians of 1.76, 2.76 and 3.71 s (6-9), and 1.67, 2.26 and 2.78 against 1.71, 2.62 and 3.64 s (10-12). The floor lifted the delay on a median of 0, 6, 16 and 17 percent of sets across the four speeds.
- A censoring-aware estimate recovers both parts (simulation, 80 blocks per reader): a Kaplan-Meier median of the time to an unaided first press, treating a set as censored at the buzz or at the end of the fall (Kaplan and Meier 1958 [META]), gave 1.77, 2.73, 3.65 and 4.40 s (estimable in 80, 80, 78 and 39 of 80 blocks), and accuracy among sets answered before any buzz was 0.93, 0.94, 0.96 and 0.97. Both are computable from fields already logged (`presses`, `pat`, `fall`).
- Per-word fade: words recur within a block only after a miss and the state resets every block (code), so the fade mostly runs across the 2 to 4 sets of one word attempt in the profiles that have a prompt, and the notebook's "by exposure" table rests mostly on exposure 1.

Bearing. The prompt follows the time-delay idea in a population the evidence does not cover, and its "own latency" floor is biased low for the slow readers it is meant to protect. The unprompted correct rate measures speed as much as knowledge; reported alone it would make a slow but accurate reader with dyslexia look like a poor learner, and a speed gain look like learning.

### Q6. Speech: synthetic against recorded voice, accent, and what the methods must report

- No study was found that validates neural text-to-speech for isolated syllables or made-up words with children or readers with dyslexia.
- Children: 22 children aged 8 to 11 processed natural speech faster than matched non-speech but synthetic speech more slowly than tones (Whitten et al. 2020 [ABS]); 90 children aged 3 to 5 repeated digitised and synthesised words in noise with difficulty, helped by context and sentences (Drager et al. 2006 [ABS]); 48 London children aged 4 and 7 understood single words less well in an unfamiliar regional accent, the younger more so (Nathan et al. 1998 [ABS]).
- Adults: neural text-to-speech (Amazon Polly) was rated more natural but its words were identified less well than concatenative speech at -6 dB SNR and in unpredictable sentences (28 adults; Cohn and Zellou 2020, Results [FT]).
- Dyslexia: speech perception is normal in quiet and impaired in noise, place of articulation most (Ziegler et al. 2009 [ABS]).
- Practice: quiet surroundings and good-quality headphones (Richardson and Lyytinen 2014 [FT]); ROAR-PA used one recorded native speaker for every item (Gijbels et al. 2024, Methods [FT]).
- The files: British phonemes and a British voice for Australian readers; weak syllables synthesised one at a time; loudness set at render; no output latency or playback level recorded; no listener check (Section 1.5).

Bearing. The voice is a fixed part of every item. The methods must name the model, voice, accent, render dates, how the syllables were produced, loudness, playback device and level, and room; and each syllable file used in a measure should pass a listening check against its own foils before the case runs.

### Q7. Timing and session length

- Children are about 1.8 times slower than young adults at 10 and 1.5 times at 12, and 15 year olds match adults, on four speeded tasks (Hale 1990 [ABS]); dyslexic children fell behind on a time-pressured letter-sound binding task in an artificial script (Aravena et al. 2013 [ABS]).
- Session length: GraphoGame's developers recommend 8 to 12 minutes for children's concentration (Richardson and Lyytinen 2014 [FT]); the EEF trial delivered 6 to 9 hours in total (Worth et al. 2018 [FT]).
- The block: 30 words take 12.8 to 18.0 minutes for children and teens and 13 to 17 for adults (simulation), under the 20-minute cap in every simulated block.

Bearing. The 6.0 to 4.5 s windows are design values that leave a child reading time; the block is longer than the developer guidance for children.

### Q8. Age profiles: what changes into adolescence and adulthood, and what does the adult profile measure?

- 100 Dutch-speaking first-year students with dyslexia against 100 controls: reading and writing accuracy deficits of d = 1 to 2, phonological processing over 0.7, larger for speed than accuracy except spelling; spoonerisms d = 0.70 for correct answers and 1.42 for time, reversals 1.00 and 1.30; word reading error rates 2.63 against 0.90 percent and nonword error rates 11.75 against 6.05 percent (Callens et al. 2012, Abstract and Tables 5 and 6 [FT]).
- Young Italian adults with dyslexia showed a text reading deficit of d = 1.52 against controls (Vender and Delfitto 2025, Results [FT]).
- In a browser lexical decision task, accuracy predicted single-word reading (r = 0.91 over 500 trials) while median RT did not (r = -0.06), except among people above 70 percent correct (r = -0.53, n = 28); pseudowords discriminated better than real words (r = 0.86 against 0.74) (Yeatman et al. 2021, Results [FT]).
- Adult profile (simulation): first-press accuracy about 0.88 to 0.89 and a fall staircase that settles at 2.4 to 4.2 s depending on speed; the threshold rises with foil capture at fixed speed (Q4).

Bearing. Taking away print, model and prompt and moving the adult measure to time is consistent with where adult deficits lie. The adult outcome is a joint speed and discrimination index under adaptive foils, set mostly by build sets, and needs to be described that way.

### Q9. The quick look

- An app for young adults with dyslexia used brief exposures from 1,200 down to 100 ms with progress at over 80 percent accuracy (Vender and Delfitto 2025, Literacy intervention [FT]); the German syllable app ended with a speed module (Hess et al. 2024 [ABS]).
- Precision (simulation, 4,000 runs per cell, steep four-option psychometric function): with 20 trials from 500 ms (16+) the reversal threshold had an SD of 0.036 to 0.040 s, two blocks differed with an SD of 0.052 to 0.056 s, and 1 to 3 percent of blocks gave no threshold; with 16 trials from 700 ms (10-12), 11 to 33 percent of blocks gave no threshold and the retest SD was 0.059 to 0.068 s; from 600 ms (13-15), 6 to 20 percent and 0.058 to 0.065 s. The estimates sat close to the 79.4 percent point in this model.

Bearing. The quick look is a usable rough threshold for adults; at 16 trials it often fails to give one, and a change between two sessions needs to exceed about 0.10 to 0.13 s (arithmetic, 1.96 times the retest SD) before it is more than noise.

### Q10. What can a described case claim, and which single-case designs fit this game?

- The single-case reporting guideline: the B-phase training study, the pre-post study and the case description are not single-case experiments; the A-B design is quasi-experimental with no control for history or maturation; professional guidelines ask for the effect to be shown at least three times by manipulating the intervention; the checklist has 26 items, among them participant characteristics, setting, measures with reliability, equipment, procedural fidelity and adverse events (Tate et al. 2016, Introduction and Table 1 [FT]).
- Design standards: at least three attempts to demonstrate an effect at three points in time; A-B, A-B-A and B-A-B designs do not meet the standard; a phase needs at least 3 data points to count; a multiple baseline design needs at least six phases with 5 points each to meet the standards, 3 each with reservations; an intervention that produces a lasting change belongs in a multiple baseline rather than a reversal design; visual analysis reads level, trend, variability, immediacy (last three against first three points), overlap and consistency (Kratochwill et al. 2010, Sections C and D and the visual analysis section [FT]).
- A dyslexia exemplar: 11 students with severe dyslexia, 32 individual sessions over 8 weeks, a non-concurrent multiple baseline and probe design across participants with 5 baseline, 8 intervention and 5 post measurements over 18 weeks, staggered start in random order, alternate forms drawn at random from item pools of regular words, pseudowords and irregular words, a pegboard task as an untrained control measure, 10 percent of lessons and 15 percent of test sessions rated for fidelity, Tau-U with baseline trend correction and a between-case standardised mean difference (Thurmann-Moe et al. 2021, Design, Measures and Analysis [FT]). A Curtin study of 8 children aged 7;6 to 8;11 used a single-subject crossover with researcher-made nonword lists as the repeated measure (Seiler et al. 2019 [ABS]). Single-case designs in rehabilitation typically use one to three patients with repeated measurement and sequential introduction of the intervention (Krasny-Pacini and Evans 2018 [ABS]).
- GraphoGame itself separates training levels from static assessment levels (Richardson and Lyytinen 2014 [FT]).
- The game as built has no repeated measure that is the same across sessions: words come from a seeded random draw, and foils, returns and ease-in draws depend on performance, so even a pinned seed does not reproduce the items; `return_after` cannot be switched off from the config (an empty list falls back to [2, 4]) (code).

Bearing. One session per reader is a case description: it can report feasibility and one session's play. An A-B design with a fixed probe gives a quasi-experimental case; three readers starting at staggered times would give a multiple baseline that could meet the standard with reservations if every phase holds at least 3 probe points. Either needs a probe that does not change with performance.

### Q11. Measures of change for one reader, and what change would count

- Reliable change: RCI = (T2 - T1) / SEdiff, with SEdiff from the measure's SD and test-retest reliability in a reference group; in the worked example (SD 15, r 0.85) SEdiff is 8.22; practice effects persist and a control group's change helps interpret an individual's (Duff 2012, sections on reliability, practice effects and Table 3 [FT, PMC page]; Jacobson and Truax 1991 [META]). This game has no reference SD or reliability, so an RCI applies only to a published test given before and after.
- Nonoverlap and effect sizes: Tau-U combines nonoverlap with a correction for baseline trend (Parker et al. 2011 [ABS]); its arithmetic gives hard-to-read results when correcting for baseline trend and several Tau-U statistics correlate weakly with visual analysis (Brossart et al. 2018 [ABS]); nonoverlap measures and the standardised mean difference depend on procedural details such as session length and number of observations, while the log response ratio does not (Pustejovsky 2019 [ABS]). In three special-education journals, 42.27 percent of single-case intervention studies reported an effect size, most often PND and, more recently, Tau-U (Balikci and Gulboy 2026, Results [FT]).
- Progress monitoring: curriculum-based reading measures need more than six weeks of data before visual or rule-based decisions are reliable (Van Norman and Christ 2016 [ABS]); most decision rules rest on expert opinion (Ardoin et al. 2013 [ABS]); schedule frequency and density change the standard error of the slope (January et al. 2019 [ABS]; Christ et al. 2013 [ABS]).
- What a fixed probe can detect for one reader (simulation; logistic item model, item SD 1.0 logit, day-to-day SD 0.3 logit, 1,500 runs): with 3 baseline and 3 later sessions, a one-sided nonoverlap (NAP) permutation test cannot fall below p = 0.05, because 1/20 is its smallest value (arithmetic). With 5 and 5 sessions, a rise in mean accuracy from 0.62 to 0.71 was detected by a t-test on session means in 0.34 (20 items) and 0.41 (40 items) of runs and by NAP in 0.28 and 0.35; a rise from 0.62 to 0.81 in 0.83 and 0.94 (t) and 0.77 and 0.92 (NAP). Pooling all items in one binomial test, ignoring day-to-day variation, gave 0.06 to 0.09 false positives with no change.
- In-game numbers with no true change (simulation, 200 blocks per reader): the unaided rate varied between blocks with an SD of 0.048 to 0.049 (6-9) and 0.034 (10-15), so a change under about 0.13 and 0.09 is within noise (1.96 times root 2 times the SD, arithmetic); first-press accuracy counting prompted answers had an SD of 0.018 to 0.025. The adult last-12 fall had an SD of 0.30 to 0.34 s (smallest detectable change 0.84 to 0.93 s) and the reversal mean 0.24 to 0.28 s (0.65 to 0.77 s).

Bearing. With the adaptive ladders, in-game accuracy is held near a target and its noise is large relative to likely change; the level reached, the thresholds and a fixed probe are the candidate measures. Five or more probe sessions per phase, 20 to 40 fixed items, and claims limited to large changes are what a case can support.

### Q12. Reliability of accuracy and RT in reading-related choice tasks, and practice

- Fixed, calibrated item lists can be reliable: three 76-item lexical decision lists chosen by item response theory gave an intraclass correlation of 0.91 per list and 0.97 for the composite, and r = 0.90 with Woodcock-Johnson word identification in 84 people aged 5;11 to 42;7 (Yeatman et al. 2021, Study 2 [FT]). Receptive three-option PA subtests of 19 to 25 items gave Cronbach's alpha of 0.89 to 0.90 (first sound matching) and a composite correlation of 0.74 to 0.76 with CTOPP-2 (Gijbels et al. 2024, Parts 1 and 2 [FT]). In-game measures of a Dutch GraphoGame: a timed letter-sound task (hear a phoneme, pick its grapheme among 5 to 10 distractors) alpha 0.87 to 0.93; a 32-item in-game lexical decision 0.68 to 0.70 (Glatz et al. 2023, Methods [FT]).
- Accuracy predicts reading better than RT except in high performers (Yeatman et al. 2021 [FT]).
- Practice and untrained gains: practice effects appear on repeat testing and can persist (Duff 2012 [FT, PMC page]); untrained dyslexic children improved as much as trained ones over a few weeks (Luniewska et al. 2018 [FT]).
- The Syllables items are drawn at random and never calibrated, and within a block they serve teaching as well as measurement (code).

Bearing. Reliability for this game is unknown. A probe built like ROAR or ROAR-PA (fixed, piloted items, no feedback) is the route to a number with known precision; until then, the precision figures in Q9 and Q11 are model-based.

### Q13. Feedback, spacing, rewards and motivation

- Delayed feedback removed the dyslexia deficit in probabilistic reinforcement learning (Gabay 2021 [ABS]); spaced retrieval beat repeated study and immediate retrieval for novel word form and meaning in preschool children with language impairment and typical peers (Leonard and Deevy 2020 [FT]); GraphoGame makes the child select the right answer after an error before moving on (Richardson and Lyytinen 2014 [FT]).
- Engagement depended on context and parental involvement (Ronimus and Lyytinen 2015 [FT]); the earlier rewards study had no abstract available (Ronimus et al. 2014 [META]).
- Code: in the sectioned sitting the answer is shown straight after a second wrong press, and a timed-out set the same way at the end of the fall; returns come 2 and 4 words later.

Bearing. The feedback design is defensible but its sources are indirect (probabilistic learning, novel spoken words, adults). The docstring's "negative feedback is quiet, informational and late" describes the single-section block; in the sectioned sitting the correction follows a second error immediately.

### Q14. The case procedure, as procedure

- Reporting needs: selection criteria, participant characteristics, setting, consent or assent, measures with their reliability, equipment, procedural fidelity and adverse events (Tate et al. 2016, Table 1 [FT]).
- Characterising the reader: the Castles and Coltheart test (40 regular words, 40 irregular words, 40 nonwords, stopping rule, free, with norms for children) (Castles et al. 2009 [ABS]); the Adult Reading History Questionnaire (alpha 0.94 and 0.92, retest 0.87 and 0.84, r = 0.57 to 0.70 with reading measures) (Lefly and Pennington 2000 [ABS]).
- Conditions: quiet room and good headphones (Richardson and Lyytinen 2014 [FT]); dyslexic listeners lose most in noise (Ziegler et al. 2009 [ABS]); supportive adult involvement mattered (McTigue et al. 2020 [ABS]; Ronimus and Lyytinen 2015 [FT]).
- Code: `supervised` is fixed at true in the config; nothing logs the supervisor's role, the room, the headphones or the playback level; the docstring's statement that the tactile prompt is a response prompt and not a reading aid fits the evidence gap in Q5.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Construct wording | syllable matching; "the syllable is the right grain" | Sub-syllabic grapheme-phoneme discrimination in print; phonics with letters (Q1) | Keep the task; reword the construct |
| Claimed effect base | Galuschka, Ehri, Bhattacharya, Mueller | Verified; small to moderate effects; computer-only weakest (Q1, Q2) | Keep; add the computer subgroup facts |
| Profile choice | typed age, sectioned sitting | Consistent with adult speed deficits (Q8) | Keep; record the profile in the case report |
| Block length | 30 words, 13 to 18 min (simulation) | 8 to 12 min for children (Richardson [FT]) | Change for 6-9 (DESIGN-CHANGE) |
| Sessions per reader | one, no baseline | Case description only (Tate [FT]; Kratochwill [FT]) | Add sessions with probes (DESIGN-CHANGE) |
| Repeated measure | none fixed | Fixed, calibrated lists; static assessment levels (Yeatman [FT]; Richardson [FT]; Thurmann-Moe [FT]) | Add a probe (DESIGN-CHANGE) |
| Word splits | one split; -er two ways | Division rules unreliable in English (Kearns [ABS]) | Keep; tidy -er after collection |
| Weak-vowel guard | F3 to F7 and vowel family skipped on 43 to 60 percent of real-word targets | Needed for a defensible answer by ear | Keep; log `weak` and analyse apart (SAFE-NOW) |
| Foil legality, sound key | in place | One defensible answer | Keep |
| F4 reversal foils | child and teen families | Reversals common and not predictive in beginners (Treiman [FT]) | Keep; do not interpret captures |
| F5 transposition | families | Letter position dyslexia rare, needs migratable words (Kohnen [ABS]) | Keep; do not interpret captures |
| Family ladder | 3 up, 1 down, "mastered" after 3 in a row at level 3, reset each block | Field criteria about 90 percent over 2 sessions (McDougale [FT]); simulation: mastery under 1 percent, levels 1 to 2 | Keep; rename in analysis; carry levels across sessions after collection |
| Rung (classic) | 3-down-1-up, equal steps | Equal steps miss 79.4 (Garcia-Perez [ABS]); 0.80 to 0.84 (simulation) | Keep; reword |
| Rung (sectioned) | sets time, print, respeak | Climbs to the ceiling (simulation) | Keep; never report as a threshold |
| Adult staircase | 4-down, 0.17 s down, 0.20 s up, threshold from last 12 sets | Ratio gives 85.84 percent (Garcia-Perez [ABS]); last 12 sets all build; accuracy-dependent (simulation) | Report by section now; per-section staircase after approval |
| Prompt steps | 0.6, 0.75, 0.9 of fall | Delays comparable with 2 to 5 s time delay (Horn [FT]); progressive favoured indirectly (Walker [ABS]) | Keep |
| Prompt floor | median of last 8 unaided correct times plus 300 ms | Censored sample, biased low (simulation) | Change to a censoring-aware median (DESIGN-CHANGE) |
| Unaided correct rate as the learning measure | primary in docstring and notebook | Tracks speed (simulation) | Report with Kaplan-Meier latency and conditional accuracy (SAFE-NOW) |
| Instructions about the buzz | none | Time-delay procedures open with 0 s trials, so the learner meets the prompt before any wait (Horn [FT]) | Add one standard supervisor sentence (SAFE-NOW) |
| Correction after errors | answer shown after a second wrong press | GraphoGame re-pick (Richardson [FT]); delayed feedback (Gabay [ABS]) | Keep; fix the docstring wording |
| Voice | Kokoro bf_emma, British, unchecked | No validation for syllables; accent and noise costs (Q6) | Listener check and reporting (SAFE-NOW); recorded Australian voice after collection |
| Playback conditions | not specified or logged | Quiet room and headphones (Richardson [FT]) | Add to the procedure (SAFE-NOW) |
| Time allowed | 6.0 to 4.5 s (6-9) and profile tables | Design values scaled by age (Hale [ABS]) | Keep; report as design values |
| Quick look | 16 or 20 trials, 80 ms steps | Retest SD 0.05 to 0.07 s; 11 to 33 percent no threshold at 16 (simulation) | Keep; report the final exposure too; 20 trials for 10 to 15 after approval |
| Rewards | points, stars, stickers | No claim made | Keep |
| Results-screen advice | first-press accuracy, band advice | Counts prompted answers; bands do not apply to pools | Change (SAFE-NOW) |
| Supervised flag | config true, no control | Adult involvement moderates (McTigue [ABS]) | Keep; log the supervisor's role in the procedure |
| Logging | no weak flag, `pat` only when fired | Needed for splits and latency | Add `weak` (SAFE-NOW) |
| Notebook route | sectioned rows get a thin chapter; checks skip case blocks | Case needs per-section classes, latency, captures, thresholds | Change (SAFE-NOW) |
| Notebook sources | Kornell 2009, Leonard 63(11), Kohnen "hardest", unsourced RT anchor, Tarrant rule per reader | Citation and scope errors (Section 1.10) | Correct (SAFE-NOW) |
| Reader characterisation | none | Reporting guideline items 10 to 11 (Tate [FT]); CC2, ARHQ (Q14) | Add (DESIGN-CHANGE) |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

The games stay as programmed unless marked DESIGN-CHANGE or AFTER-COLLECTION; every task change is flagged.

1. **Give the case blocks a chapter of their own in the notebook.** SAFE-NOW.
   In `analysis/session_analysis.ipynb` cell 2, extend `sec_syllables_sections` (14321) so a sectioned block prints, per section and per profile: the five prompt classes plus `shown` with Wilson 95 percent intervals, the 25 percent chance line beside the unaided first presses only, answer times, the foil capture table (from `sec_syllables` step 3, with appearance denominators), family results at levels 1 to 3 only using `family_n`, the adult fall threshold per section, and the quick-look threshold with its final exposure. Use `unprompted_ok`, not `first_ok`, as the accuracy column, and print `first_ok` beside it labelled "counting prompted answers". In `sec_syllables_checks` (29139), replace "No syllable blocks of the child design" with a line that names the sectioned case chapter. Add a warning when `block_stats.demo` is true or `supervised` is false, and print the speech backend and voice from the config snapshot and the raw `speech` events. Evidence: Section 1.9 (code); Tate et al. 2016 [FT] items 14, 15 and 19 to 21.

2. **Report speed and knowledge apart; stop presenting the unaided rate alone as learning.** SAFE-NOW (analysis and text).
   Add to `syllable_set_frame` (14084) the time to the first non-anticipation press, an event flag (press before any buzz), and a censoring time (the buzz time `pat`, or `fall` when nothing was pressed). In the case chapter, print the Kaplan-Meier median time to an unaided first press with its interval and the accuracy among sets answered before any buzz; split both by section, `respeak` and `print`. In `syllables.py` docstring lines 136-141 and in `MODE_LIT["syllables"]`, reword: the unaided rate mixes reading speed with accuracy, and the learning measure is the probe (recommendation 3), with speed and conditional accuracy reported apart. Evidence: simulation, Q5 (unaided 0.84 to 0.29 at fixed knowledge; Kaplan-Meier medians within 0.06 s of the true medians for the three faster readers; conditional accuracy 0.93 to 0.97); Kaplan and Meier 1958 [META].

3. **Add a fixed probe section and make it the case's repeated measure.** DESIGN-CHANGE (adds a section to the case sitting; log it in the design document).
   New section `probe` first in `_plan_sections` (820-836), on when `syllables.probe: true` (new key, default false so nothing else changes). Items: a fixed list per profile in a new `app/assets/words/syllables_probe.json` (for example 24 to 30 sets: equal numbers of each near foil kind with one family foil per set and F1 fillers, half full-vowel and half weak targets, real and made-up words, half from words the reader will train and half never trained), drawn by a separate `random.Random(probe_seed)` so performance cannot change the sequence; the word and then the target syllable played once at fixed times, no replay, no prompt, no returns, the same neutral display after every answer (no lift, no glow), fixed time per set; rows tagged `sec=probe`; `_move_rung`, `_move_family` and `_update_prompt_fade` skipped for probe rows (as `_score_set` already does for `review` at 2005-2007). Notebook: a `sec_syllables_probe` chapter (per-session accuracy with Wilson intervals, trained against untrained items, phase lines). Evidence: Richardson and Lyytinen 2014 [FT] (static assessment levels); Yeatman et al. 2021 [FT] and Gijbels et al. 2024 [FT] (fixed lists reach ICC 0.91 and alpha 0.89 to 0.90); Thurmann-Moe et al. 2021 [FT] (alternate forms from item pools); simulation, Q11.

4. **Turn one session into a design that can show change, and characterise each reader.** DESIGN-CHANGE (case procedure; no case has run).
   Minimum: an A-B case per reader, with at least 3 and ideally 5 probe-only sessions on separate days, then training sessions each opening with the probe; with three readers, stagger the start of training (non-concurrent multiple baseline across participants). Before the first session record age, how and when dyslexia was identified, first language, hearing and vision status, and one published measure: the Castles and Coltheart test for children, the Adult Reading History Questionnaire for adults; repeat the reading measure after the last session if time allows. Write it into `FINAL TRIAL RESULTS/README.md` and `app/docs/research/design_check.md` Section 8 and log the change. Evidence: Kratochwill et al. 2010 [FT] (3 demonstrations; 3 or 5 points per phase; A-B does not meet standards; multiple baseline for lasting change); Tate et al. 2016 [FT]; Thurmann-Moe et al. 2021 [FT]; Luniewska et al. 2018 [FT] (untrained gains); simulation (3 and 3 sessions cannot give p < 0.05 by NAP; 5 and 5 detect a 19-point rise 0.77 to 0.94 of the time and a 9-point rise, 0.62 to 0.71, only 0.28 to 0.41).

5. **Fix the prompt floor's censoring bias.** DESIGN-CHANGE (changes when the buzz comes).
   In `syllables.py`, keep a record per set of (time, event) where the event is an unaided first press and the censoring time is the buzz or the end of the fall; in `_prompt_delay_s` (1587-1600) replace the median of `_answer_rts` (695, filled at 1969-1970) with a Kaplan-Meier median over those records once at least 3 events exist, plus `prompt_floor_margin_ms`, still capped at 0.9 of the fall. Alternatively remove the floor and keep the fixed steps, which is simpler to describe. Evidence: simulation, Q5 (floor sample median 2.54 s against a true 3.71 s for a slow child reader).

6. **Log what the analysis needs.** SAFE-NOW (new fields; no measure changes).
   In `_pack_stimulus` (2289-2345) add `weak=<0|1>` (the target heard with a weak vowel, from `heard_weak` or the guard rule in `_weak_now` 866-878) and `pdue=<ms>` (planned buzz time from spawn, blank when the prompt is off). In `block_stats` (3012-3118) add the speech manifest's voice, model and render dates, and the seed. Evidence: Q3 (weak targets 43 to 60 percent of real-word sets; vowel foils otherwise unreadable by pool); Q5.

7. **Check the voice before it becomes a measure, and report it fully.** SAFE-NOW (procedure and a small script).
   Add a `listen` command to `app/scripts/syllables_recording_kit.py` (or a new script) that plays each syllable file used in the probe and the first sessions, audio only, with its real four options on screen, to two adult Australian English listeners; an item below 90 percent correct identification across listeners is re-rendered or dropped from the probe. Record listener results, the playback device, the headphone model and the level in the manifest and the case README. Methods text: Kokoro-82M v1.0, voice bf_emma (British), espeak-ng British phonemes, in-word syllables synthesised one at a time, loudness targets, render dates. Evidence: Q6 (no validation study; Whitten et al. 2020 [ABS]; Nathan et al. 1998 [ABS]; Ziegler et al. 2009 [ABS]; Richardson and Lyytinen 2014 [FT]).

8. **Correct the claims the evidence contradicts.** SAFE-NOW (text only).
   - `syllables.py` 36-41: the syllable-awareness argument (Liberman) covers ages 4 to 6; for older readers the foils test grapheme-phoneme contrasts inside the syllable.
   - 35-36: neither cited study used a recognition task; say "print-linked syllable work".
   - 86-90 and 126-131: in the sectioned sitting the answer follows a second wrong press immediately.
   - 122-126: the floor uses only answers that beat the buzz (until recommendation 5).
   - 142-149, notebook `MODE_LIT["syllables"]` S1 and `screens.py` `_syllables_advice`: the 79.4 percent figure holds loosely and only for ladder-moving sets in the classic design; in the sectioned sitting the rung is a time setting.
   - `_move_fall` 2065-2067: "settles near 85.8 percent (Garcia-Perez 1998, ratio 0.8415)", not 84.1.
   - `_move_expo` 2563-2565: equal steps; the threshold is rough (retest SD about 0.05 to 0.07 s, simulation).
   - `MODE_LIT["syllables"]` S4: Kornell, Castel, Eich and Bjork 2010 (adults, painters' styles) does not support children's word returns; Leonard and Deevy 2020 is 63(10):3252-3262. S2: drop "letter-position foils hardest" or replace it with "no prediction"; S3: drop the unsourced 450 to 550 ms anchor.
   - `sec_syllables_profiles` (14730): Tarrant's 5 percent rule is a group criterion; for one reader print the capture rate with its interval and the near-foil null instead.
   - `default.yaml` 1185-1194: 30 words take about 13 to 18 minutes with sections (simulation).
   - `syllables.py` 72 ("the adult line on the rest screen") and `syllables_screen.py` `_draw_break`: the line never shows in the sectioned sitting.
   - The author's data collection plan: 30 words, sectioned, no rounds; the notebook chapter for case blocks (recommendation 1).

9. **Adult threshold: report it per section now; consider a pick-only staircase.** SAFE-NOW for reporting; DESIGN-CHANGE for the staircase.
   Notebook: from the `fall` column, compute the mean fall of the last 12 pick sets and of the last 12 build sets per block, and the reversal mean per section; describe the result as a speed and discrimination index under adaptive foils. Code (after approval): in `_move_rung`/`_move_fall` (2028-2098) run the fall staircase on pick sets only, or keep one staircase state per section, so the threshold is not set by build sets. Evidence: simulation, Q4 (last 12 sets build in every block; threshold 2.71 to 3.35 s across foil capture at fixed speed); Garcia-Perez 1998 [ABS].

10. **Shorten the child block.** DESIGN-CHANGE (task length).
    A per-profile `words_per_block` (new optional field on `Profile` in `syllables_profiles.py`, read in `SyllablesMode.__init__`), 20 for 6-9, leaving 30 for older readers. Evidence: Richardson and Lyytinen 2014 [FT] (8 to 12 minutes); simulation (12.8 to 14.2 minutes for 30 words at 6-9).

11. **Write the case procedure down.** SAFE-NOW (procedure; changes no measure).
    One page in `FINAL TRIAL RESULTS/README.md`: consent (and a parent's consent with the child's own agreement for a minor); quiet room, the same closed headphones and the same level every session, checked with the reader; the supervisor's fixed role (seated beside the reader, neutral encouragement between sections, never names or points to an answer, presses R only when asked, records any interruption); one standard sentence about the buzz said before the first block ("If a finger buzzes, that is a hint; try first if you can"); a stop rule (the reader asks, or shows distress, or three words in a row are missed with signs of frustration: end at the word boundary and finish on an easy word); the wording used afterwards (the game is a practice game, not a test or treatment, and no result describes reading ability); data under the D code only. Evidence: Tate et al. 2016 [FT] items 11, 12, 14 to 17 and 21, and the consent part of item 13; Richardson and Lyytinen 2014 [FT]; McTigue et al. 2020 [ABS]; Ronimus and Lyytinen 2015 [FT].

12. **Name the family ladder for what it is.** SAFE-NOW (analysis wording); AFTER-COLLECTION (state across sessions).
    In the notebook and the thesis, call level 3 with a run of three "passed level 3", not "mastered", and report family levels as the block's end state. After collection, store each reader's family levels per profile (a per-code JSON next to the session data) and start the next block from them, so a multi-session reader reaches the harder contrasts. Evidence: McDougale et al. 2020 [FT]; Fuller and Fienup 2018 [FT]; simulation, Q4.

13. **Make the results-screen advice honest.** SAFE-NOW (UX).
    In `screens.py` `_syllables_advice`, read `unaided_accuracy` and the prompted share, and drop the band suggestion when the profile draws from pools (`_bank_bands` false). Evidence: Section 1.7 (code); simulation (first-press accuracy 0.92 to 0.95 for every reader speed).

14. **Quick look: more trials for 10 to 15.** DESIGN-CHANGE (low priority).
    `speed_trials=20` for 10-12 and 13-15 in `PROFILES` (`syllables_profiles.py` 137-154); report the final exposure beside the reversal mean in every case. Evidence: simulation (11 to 33 percent of 16-trial blocks give no threshold).

15. **After collection.** AFTER-COLLECTION.
    A recorded Australian English voice through `syllables_recording_kit.py`; item calibration of the probe across readers; per-reader persistence of family levels and the prompt state; one -er split policy; a separate family for schwa spellings on weak syllables (the contrast the weak-vowel guard currently removes); a 0 s first stage or most-to-least prompting for readers who err often before the buzz (Cowan et al. 2023 [FT]).

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Case chapter for sectioned blocks: five prompt classes plus shown per section with Wilson intervals; chance line on unaided presses only | `sec_syllables_sections` (14321), called from `sec_syllables` (14422) | Tate et al. 2016 [FT] |
| Kaplan-Meier median time to an unaided first press (censored at the buzz or the end of the fall) and accuracy among sets answered before any buzz | `syllable_set_frame` (14084) new columns; case chapter | Kaplan and Meier 1958 [META]; simulation, Q5 |
| Foil capture per kind: appearances, first-press captures, capture rate with interval, expected captures under errors spread over near foils on screen (F1 excluded), Monte Carlo multinomial p, n of errors printed | case chapter; replace the Tarrant 5 percent rule in `sec_syllables_profiles` (14730) | Tarrant et al. 2009 [FT]; simulation, Q3 |
| Family results only at levels 1 to 3, using `family_n`; level 0 labelled "no family foil on screen" | `sec_syllables_sections` | code |
| Weak against full-vowel targets (from the new `weak` field, or a join on the manifest's `syllable_map` for older rows) | case chapter | code; Q3 |
| Accuracy and latency split by `respeak` and `print` | case chapter | code |
| Real against made-up words with the foil mix shown, since vowel foils sit mostly on made-up words for adults | `sec_syllables_profiles`, case chapter | arithmetic, Section 1.3 |
| Adult fall threshold per section (last 12 pick sets, last 12 build sets, reversal mean per section) | case chapter; `sec_syllables_profiles` | Garcia-Perez 1998 [ABS]; simulation, Q4 |
| Quick look: reversal threshold, final exposure, number of reversals, and the retest SD from simulation as the noise band | `sec_syllables_sections` speed table | simulation, Q9 |
| Cross-session exposure per word for one code: accuracy on words first met this session against words met before | new helper on the case selection | Thurmann-Moe et al. 2021 [FT] (trained against untrained items) |
| Multi-session plot per reader: probe accuracy (or unaided rate, latency and thresholds) by session with phase lines and smallest-detectable-change bands; level, trend, variability, immediacy, overlap and consistency described | new `sec_syllables_case` | Kratochwill et al. 2010 [FT]; Lane and Gast 2014 [ABS] |
| Effect sizes only with enough points: NAP with an exact permutation p from 5 points per phase, Tau-U only with its baseline-trend caveat, a between-case standardised mean difference only with 3 or more readers, the log response ratio for count-type probes | `sec_syllables_case` | Parker et al. 2011 [ABS]; Brossart et al. 2018 [ABS]; Pustejovsky 2019 [ABS]; simulation, Q11 |
| Reliable change only for a published pre and post test, with its published SD and reliability | `sec_syllables_case` text | Duff 2012 [FT, PMC page]; Jacobson and Truax 1991 [META] |
| Demo, supervision, speech backend and voice printed per block | case chapter header | code |
| `sec_syllables_checks` message for sectioned blocks; `MODE_LIT["syllables"]` and `MODE_CLAIM_LIMITS["syllables"]` corrections (Section 1.10); claim limits gain "a single reader's change cannot be attributed to the game" | 29139; 27659 onward; 28283 onward | Section 1.10; Luniewska et al. 2018 [FT] |

Keep as they are: the separation of single-section and sectioned rows, the exclusion of rig-voided sets (`HARDWARE_VOID_ERRORS`), the hub-only exclusion from the healthy n (`cohort_sitting_people`), S6 and S7 printed as DROPPED, and the existing claim limits that the game is not a test or treatment.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat |
|---|---|---|---|
| Phonics for reading disability | g' = 0.32 (0.18 to 0.47), 0.20 after trim and fill; approaches did not differ (p = .788) | Galuschka et al. 2014 [FT] | 22 RCTs; mostly human-delivered |
| PA instruction | d = 0.53 on reading; 0.67 with letters against 0.38 without; disabled readers 0.45; computers 0.33 | NRP report [FT] | mostly young children; spelling null for disabled readers |
| Phonics, English poor readers | word reading accuracy SMD 0.51; computer-delivered 0.18 (-0.17 to 0.54) against human 0.70 | McArthur et al. 2018 [FT, PMC page] | low-quality evidence; small subgroups |
| GraphoGame | 19 studies g = -0.02; high adult interaction 0.48 | McTigue et al. 2020 [ABS] | meta-analysis of one program |
| GraphoGame Rime, England | ES -0.06 (-0.23 to 0.12); 6 to 9 hours played | Worth et al. 2018 [FT] | against business as usual with other support |
| Syllable-based training, German Grade 4 | ES 0.82 word recognition fluency; no comprehension effect | Mueller et al. 2017 [FT] | transparent orthography; group, human-delivered |
| Adult dyslexia app | group by time d = 0.70 text, 0.46 words | Vender and Delfitto 2025 [FT] | Italian; allocation by enrolment order |
| Untrained dyslexic controls | same gains as two game groups; 82 percent of trained children faster | Luniewska et al. 2018 [FT] | controls not randomised |
| Adult dyslexia profile | accuracy d = 1 to 2; speed larger than accuracy except spelling; nonword errors 11.75 against 6.05 percent | Callens et al. 2012 [FT] | Dutch students in higher education |
| Developer target and session length | about 80 percent correct per level; 8 to 12 minutes | Richardson and Lyytinen 2014 [FT] | design guidance |
| Staircase targets | 3-down-1-up with ratio 0.7393 gives 83.15 percent; 4-down-1-up with 0.8415 gives 85.84 percent; equal steps miss | Garcia-Perez 1998 [ABS] | simulation study |
| Fixed online reading lists | ICC 0.91 per 76-item list; accuracy beats RT | Yeatman et al. 2021 [FT] | lexical decision, US readers |
| Single-case standards | 3 demonstrations; 3 (with reservations) or 5 points per phase; A-B does not meet | Kratochwill et al. 2010 [FT] | version 1.0 (pilot); later WWC versions not read here |

How to use them: as context for what print-based phonics achieves in trials and what a single reader's data can support. None is a norm for this game, and no game number is comparable with a standardised score.

### 6.2 Reliability and change expectations (all simulation unless sourced)

- One 30-word block gives 2 to 7 first-press errors: no confusion profile from one session; a strong vowel-foil confusion is found in 0.08 of single sessions and 0.61 of six-session sets.
- Block-to-block noise with no true change: unaided rate SD 0.034 to 0.049 (smallest detectable change 0.09 to 0.14); adult last-12 fall SD 0.30 to 0.34 s (0.84 to 0.93 s); reversal mean SD 0.24 to 0.28 s (0.65 to 0.77 s); quick-look retest SD 0.052 to 0.068 s (about 0.10 to 0.13 s).
- A fixed 20 to 40-item probe with 5 sessions per phase detects a rise from about 0.62 to 0.81 in 0.77 to 0.94 of cases and from 0.62 to 0.71 in 0.28 to 0.41; with 3 sessions per phase NAP cannot reach p < 0.05.
- At fixed knowledge, the unaided correct rate runs from 0.84 to 0.29 as median decision time goes from 1.5 to 4.5 s, while accuracy among answers given before any buzz stays at 0.93 to 0.97.
- The game's reliability across days is unknown; fixed, calibrated lists can reach an ICC of 0.91 (Yeatman et al. 2021 [FT]).

### 6.3 Claims to avoid

- That the game treats, diagnoses or measures dyslexia, or that any in-game number is a reading score.
- That a reader improved because of the game, from one session, a pre-post comparison or an A-B case (Tate et al. 2016 [FT]; Luniewska et al. 2018 [FT]).
- That the unprompted correct rate shows learning, without the latency and conditional accuracy beside it.
- That the rung or the final rung is a threshold in the sectioned sitting, or that accuracy near 80 percent shows convergence there.
- That a family was "mastered".
- That a reversal or transposition capture shows an orientation or letter position difficulty (Kohnen et al. 2012 [ABS]; Treiman et al. 2014 [FT]).
- That one session's foil captures form a confusion profile.
- That the adult fall threshold is a pure speed measure, or that it is set by hearing and picking rather than building.
- That the synthetic voice is equivalent to a recorded one, or that the vibration prompt helps reading.
- That GraphoGame's evidence carries over: its largest English trial was null and its positive moderator is adult support.
- That the healthy study tested Syllables: S6 and S7 were dropped before any participant.

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, PubMed records, Crossref, OpenAlex, ERIC and publisher or repository pages.

1. Aravena S, Snellings P, Tijms J, van der Molen MW. 2013. A lab-controlled simulation of a letter-speech sound binding deficit in dyslexia. Journal of Experimental Child Psychology 115(4):691-707. DOI 10.1016/j.jecp.2013.03.009. PMID 23708733. [ABS]
2. Ardoin SP, Christ TJ, Morena LS, Cormier DC, Klingbeil DA. 2013. A systematic review and summarization of the recommendations and research surrounding Curriculum-Based Measurement of oral reading fluency (CBM-R) decision rules. Journal of School Psychology 51(1):1-18. DOI 10.1016/j.jsp.2012.09.004. PMID 23375170. [ABS]
3. Balikci S, Gulboy E. 2026. Quantifying intervention effects in single-case research: a 25-year review. Behavioral Sciences 16(4):507. DOI 10.3390/bs16040507. PMID 42073870. PMC13113260. [FT: Results, Tables 3 and 4]
4. Bhattacharya A, Ehri LC. 2004. Graphosyllabic analysis helps adolescent struggling readers read and spell words. Journal of Learning Disabilities 37(4):331-348. DOI 10.1177/00222194040370040501. PMID 15493405. [ABS]
5. Brossart DF, Laird VC, Armstrong TW. 2018. Interpreting Kendall's Tau and Tau-U for single-case experimental designs. Cogent Psychology 5(1):1518687. DOI 10.1080/23311908.2018.1518687. [ABS]
6. Browder D, Ahlgrim-Delzell L, Spooner F, Mims PJ, Baker JN. 2009. Using time delay to teach literacy to students with severe developmental disabilities. Exceptional Children 75(3):343-364. DOI 10.1177/001440290907500305. [ABS]
7. Bruck M. 1992. Persistence of dyslexics' phonological awareness deficits. Developmental Psychology 28(5):874-886. DOI 10.1037/0012-1649.28.5.874. [META; as cited in Vender and Delfitto 2025]
8. Callens M, Tops W, Brysbaert M. 2012. Cognitive profile of students who enter higher education with an indication of dyslexia. PLoS ONE 7(6):e38081. DOI 10.1371/journal.pone.0038081. PMID 22719864. PMC3374824. [FT: Abstract, Table 1, Tables 5 and 6]
9. Castles A, Coltheart M, Larsen L, Jones P, Saunders S, McArthur G. 2009. Assessing the basic components of reading: a revision of the Castles and Coltheart test with new norms. Australian Journal of Learning Difficulties 14(1):67-88. DOI 10.1080/19404150902783435. ERIC EJ855417. [ABS]
10. Christ TJ, Zopluoglu C, Monaghen BD, Van Norman ER. 2013. Curriculum-based measurement of oral reading: multi-study evaluation of schedule, duration, and dataset quality on progress monitoring outcomes. Journal of School Psychology 51(1):19-57. DOI 10.1016/j.jsp.2012.11.001. PMID 23375171. [ABS]
11. Cohn M, Zellou G. 2020. Perception of concatenative vs. neural text-to-speech (TTS): differences in intelligibility in noise and language attitudes. Proceedings of Interspeech 2020, 1733-1737. DOI 10.21437/Interspeech.2020-1336. [FT: Abstract, Methods, Results]
12. Cowan LS, Lerman DC, Berdeaux KL, Prell AH, Chen N. 2023. A decision-making tool for evaluating and selecting prompting strategies. Behavior Analysis in Practice 16(2):459-474. DOI 10.1007/s40617-022-00722-8. PMID 35698480. PMC9177132. [FT: Table 1 and its footnote]
13. Drager KDR, Clark-Serpentine EA, Johnson KE, Roeser JL. 2006. Accuracy of repetition of digitized and synthesized speech for young children in background noise. American Journal of Speech-Language Pathology 15(2):155-164. DOI 10.1044/1058-0360(2006/015). PMID 16782687. [ABS]
14. Duff K. 2012. Evidence-based indicators of neuropsychological change in the individual patient: relevant concepts and methods. Archives of Clinical Neuropsychology 27(3):248-261. DOI 10.1093/arclin/acr120. PMID 22382384. PMC3499091. [FT, PMC page: sections on reliability, practice effects and reliable change; Table 3]
15. Ehri LC, Nunes SR, Willows DM, Schuster BV, Yaghoub-Zadeh Z, Shanahan T. 2001. Phonemic awareness instruction helps children learn to read: evidence from the National Reading Panel's meta-analysis. Reading Research Quarterly 36(3):250-287. DOI 10.1598/RRQ.36.3.2. [META; findings read in the NRP report, source 46]
16. Eyler PB, Ledford JR. 2024. Systematic review of time delay instruction for teaching young children. Journal of Early Intervention 46(4):451-470. DOI 10.1177/10538151231179121. [ABS]
17. Fuller JL, Fienup DM. 2018. A preliminary analysis of mastery criterion level: effects on response maintenance. Behavior Analysis in Practice 11(1):1-8. DOI 10.1007/s40617-017-0201-0. PMID 29556443. PMC5843573. [FT, PMC page: Method, Results, Discussion]
18. Gabay Y. 2021. Delaying feedback compensates for impaired reinforcement learning in developmental dyslexia. Neurobiology of Learning and Memory 185:107518. DOI 10.1016/j.nlm.2021.107518. PMID 34508883. [ABS]
19. Galuschka K, Ise E, Krick K, Schulte-Korne G. 2014. Effectiveness of treatment approaches for children and adolescents with reading disabilities: a meta-analysis of randomized controlled trials. PLoS ONE 9(2):e89900. DOI 10.1371/journal.pone.0089900. PMID 24587110. PMC3935956. [FT: Results, Tables 1 to 4, publication bias]
20. Garcia-Perez MA. 1998. Forced-choice staircases with fixed step sizes: asymptotic and small-sample properties. Vision Research 38(12):1861-1881. DOI 10.1016/S0042-6989(97)00340-4. PMID 9797963. [ABS]
21. Gijbels L, Burkhardt A, Ma WA, Yeatman JD. 2024. Rapid online assessment of reading and phonological awareness (ROAR-PA). Scientific Reports 14:10249. DOI 10.1038/s41598-024-60834-9. PMID 38704429. PMC11069509. [FT: Parts 1 and 2, Methods]
22. Glatz T, Tops W, Borleffs E, Richardson U, Maurits N, Desoete A, Maassen B. 2023. Dynamic assessment of the effectiveness of digital game-based literacy training in beginning readers: a cluster randomised controlled trial. PeerJ 11:e15499. DOI 10.7717/peerj.15499. PMID 37547712. PMC10399564. [FT: Abstract, Introduction, Methods (in-game measures and their reliability)]
23. Hale S. 1990. A global developmental trend in cognitive processing speed. Child Development 61(3):653-663. DOI 10.1111/j.1467-8624.1990.tb02809.x. PMID 2364741. [ABS]
24. Hess J, Karageorgos P, Muller B, Riedmann A, Schaper P, Lugrin B, Richter T. 2024. Improving word reading skills of low-skilled readers: an intervention combining a syllable-based approach with digital game-based features. Journal of Computer Assisted Learning 40(5):2306-2324. DOI 10.1111/jcal.13021. [ABS]
25. Horn AL, Roitsch J, Murphy KA. 2023. Constant time delay to teach reading to students with intellectual disability and autism: a review. International Journal of Developmental Disabilities 69(2):123-133. DOI 10.1080/20473869.2021.1907138. PMID 37025336. PMC10071948. [FT, PMC page: Introduction (procedure), Table 1, Results]
26. Jacobson NS, Truax P. 1991. Clinical significance: a statistical approach to defining meaningful change in psychotherapy research. Journal of Consulting and Clinical Psychology 59(1):12-19. DOI 10.1037/0022-006X.59.1.12. PMID 2002127. [META; formula read in Duff 2012]
27. January SA, Van Norman ER, Christ TJ, Ardoin SP, Eckert TL, White MJ. 2019. Evaluation of schedule frequency and density when monitoring progress with curriculum-based measurement. School Psychology Quarterly 34(1):119-127. DOI 10.1037/spq0000274. PMID 30284886. [ABS]
28. Kaernbach C. 1991. Simple adaptive testing with the weighted up-down method. Perception and Psychophysics 49(3):227-229. DOI 10.3758/BF03214307. PMID 2011460. [ABS]
29. Kaplan EL, Meier P. 1958. Nonparametric estimation from incomplete observations. Journal of the American Statistical Association 53(282):457-481. DOI 10.1080/01621459.1958.10501452. [META]
30. Kearns DM. 2020. Does English have useful syllable division patterns? Reading Research Quarterly 55(S1). DOI 10.1002/rrq.342. [ABS]
31. Kohnen S, Nickels L, Castles A, Friedmann N, McArthur G. 2012. When 'slime' becomes 'smile': developmental letter position dyslexia in English. Neuropsychologia 50(14):3681-3692. DOI 10.1016/j.neuropsychologia.2012.07.016. PMID 22820637. [ABS]
32. Kornell N, Castel AD, Eich TS, Bjork RA. 2010. Spacing as the friend of both memory and induction in young and older adults. Psychology and Aging 25(2):498-503. DOI 10.1037/a0017807. [META; record checked for the citation in `MODE_LIT`]
33. Krasny-Pacini A, Evans J. 2018. Single-case experimental designs to assess intervention effectiveness in rehabilitation: a practical guide. Annals of Physical and Rehabilitation Medicine 61(3):164-179. DOI 10.1016/j.rehab.2017.12.002. PMID 29253607. [ABS]
34. Kratochwill TR, Hitchcock J, Horner RH, Levin JR, Odom SL, Rindskopf DM, Shadish WR. 2010. Single-case designs technical documentation, version 1.0 (pilot). What Works Clearinghouse, Institute of Education Sciences. https://ies.ed.gov/ncee/wwc/Docs/ReferenceResources/wwc_scd.pdf. [FT: Sections C and D, visual analysis]
35. Lane JD, Gast DL. 2014. Visual analysis in single case experimental design studies: brief review and guidelines. Neuropsychological Rehabilitation 24(3-4):445-463. DOI 10.1080/09602011.2013.815636. PMID 23883189. [ABS]
36. Lefly DL, Pennington BF. 2000. Reliability and validity of the Adult Reading History Questionnaire. Journal of Learning Disabilities 33(3):286-296. DOI 10.1177/002221940003300306. PMID 15505966. [ABS]
37. Leonard LB, Deevy P. 2020. Retrieval practice and word learning in children with specific language impairment and their typically developing peers. Journal of Speech, Language, and Hearing Research 63(10):3252-3262. DOI 10.1044/2020_JSLHR-20-00006. PMID 33064601. PMC8084525. [FT: Abstract, sections on repeated spaced retrieval and the experiments]
38. Levitt H. 1971. Transformed up-down methods in psychoacoustics. Journal of the Acoustical Society of America 49(2B):467-477. DOI 10.1121/1.1912375. PMID 5541744. [META]
39. Liberman IY, Shankweiler D, Fischer FW, Carter B. 1974. Explicit syllable and phoneme segmentation in the young child. Journal of Experimental Child Psychology 18(2):201-212. DOI 10.1016/0022-0965(74)90101-5. [META]
40. Luniewska M, Chyl K, Debska A, Kacprzak A, Plewko J, Szczerbinski M, Szewczyk J, Grabowska A, Jednorog K. 2018. Neither action nor phonological video games make dyslexic children read better. Scientific Reports 8:549. DOI 10.1038/s41598-017-18878-7. PMID 29323179. PMC5765029. [FT: Results, Discussion, Methods (participants, control group, training)]
41. McArthur G, Sheehan Y, Badcock NA, Francis DA, Wang HC, Kohnen S, Banales E, Anandakumar T, Marinus E, Castles A. 2018. Phonics training for English-speaking poor readers. Cochrane Database of Systematic Reviews 11:CD009115. DOI 10.1002/14651858.CD009115.pub3. PMID 30480759. PMC6517252. [FT, PMC page: Abstract, subgroup analyses 1.10, 1.11, 2.5, 2.6, Discussion]
42. McDougale CB, Richling SM, Longino EB, O'Rourke SA. 2020. Mastery criteria and maintenance: a descriptive analysis of applied research procedures. Behavior Analysis in Practice 13(2):402-410. DOI 10.1007/s40617-019-00365-2. PMID 32642396. PMC7314871. [FT, PMC page: Results, Tables 2 and 3]
43. McTigue EM, Solheim OJ, Zimmer WK, Uppstad PH. 2020. Critically reviewing GraphoGame across the world: recommendations and cautions for research and implementation of computer-assisted instruction for word-reading acquisition. Reading Research Quarterly 55(1):45-73. DOI 10.1002/rrq.256. [ABS]
44. Mueller B, Richter T, Karageorgos P, Krawietz S, Ennemoser M. 2017. Effects of a syllable-based reading intervention in poor-reading fourth graders. Frontiers in Psychology 8:1635. DOI 10.3389/fpsyg.2017.01635. PMID 28979233. PMC5611416. [FT: Methods (design, participants, intervention), Results and Table 3, Discussion]
45. Nathan L, Wells B, Donlan C. 1998. Children's comprehension of unfamiliar regional accents: a preliminary investigation. Journal of Child Language 25(2):343-365. DOI 10.1017/S0305000998003444. PMID 9770911. [ABS]
46. National Institute of Child Health and Human Development. 2000. Report of the National Reading Panel. Teaching children to read: reports of the subgroups (NIH Publication No. 00-4754), Chapter 2 Part I: Phonemic awareness instruction. US Government Printing Office. [FT: executive summary, results, Tables 3 and 4]
47. Parker RI, Vannest KJ, Davis JL, Sauber SB. 2011. Combining nonoverlap and trend for single-case research: Tau-U. Behavior Therapy 42(2):284-299. DOI 10.1016/j.beth.2010.08.006. PMID 21496513. [ABS]
48. Pustejovsky JE. 2019. Procedural sensitivities of effect sizes for single-case designs with directly observed behavioral outcome measures. Psychological Methods 24(2):217-235. DOI 10.1037/met0000179. [ABS]
49. Richardson U, Lyytinen H. 2014. The GraphoGame method: the theoretical and methodological background of the technology-enhanced learning environment for learning to read. Human Technology 10(1):39-60. DOI 10.17011/ht/urn.201405281859. [FT: sections on the method, adaptation, feedback and playing sessions]
50. Ronimus M, Kujala J, Tolvanen A, Lyytinen H. 2014. Children's engagement during digital game-based learning of reading: the effects of time, rewards, and challenge. Computers and Education 71:237-246. DOI 10.1016/j.compedu.2013.10.008. [META]
51. Ronimus M, Lyytinen H. 2015. Is school a better environment than home for digital game-based learning? The case of GraphoGame. Human Technology 11(2):123-147. DOI 10.17011/ht/urn.201511113637. [FT: Abstract, Introduction, Method]
52. Seiler A, Leitao S, Blosfelds M. 2019. WordDriver-1: evaluating the efficacy of an app-supported decoding intervention for children with reading impairment. International Journal of Language and Communication Disorders 54(2):189-202. DOI 10.1111/1460-6984.12388. PMID 29691983. [ABS]
53. Tarrant M, Ware J, Mohammed AM. 2009. An assessment of functioning and non-functioning distractors in multiple-choice questions: a descriptive analysis. BMC Medical Education 9:40. DOI 10.1186/1472-6920-9-40. PMID 19580681. PMC2713226. [FT: Methods, Results, Table 2]
54. Tate RL, Perdices M, Rosenkoetter U, Shadish W, Vohra S, Barlow DH, Horner R, Kazdin A, Kratochwill T, and others. 2016. The Single-Case Reporting guideline In BEhavioural interventions (SCRIBE) 2016 statement. Neuropsychological Rehabilitation 27(1):1-15 (2017 issue). DOI 10.1080/09602011.2016.1190533. PMID 27499422. PMC5214372. Published together in several journals, including Aphasiology 30(7):862-876 (DOI 10.1080/02687038.2016.1178022). [FT: Introduction, the design hierarchy text, Table 1]
55. Terepocki M, Kruk RS, Willows DM. 2002. The incidence and nature of letter orientation errors in reading disability. Journal of Learning Disabilities 35(3):214-233. DOI 10.1177/002221940203500304. PMID 15493319. [ABS]
56. Thurmann-Moe AC, Melby-Lervag M, Lervag A. 2021. The impact of articulatory consciousness training on reading and spelling literacy in students with severe dyslexia: an experimental single case study. Annals of Dyslexia 71(3):373-398. DOI 10.1007/s11881-021-00225-1. PMID 33928516. PMC8458204. [FT: Abstract, Design, Measures, Analysis, Table 4]
57. Treiman R, Gordon J, Boada R, Peterson RL, Pennington BF. 2014. Statistical learning, letter reversals, and reading. Scientific Studies of Reading 18(6):383-394. DOI 10.1080/10888438.2013.873937. PMID 25642131. PMC4309997. [FT, PMC page: Table 1, Results]
58. Van Norman ER, Christ TJ. 2016. How accurate are interpretations of curriculum-based measurement progress monitoring data? Visual analysis versus decision rules. Journal of School Psychology 58:41-55. DOI 10.1016/j.jsp.2016.07.003. PMID 27586069. [ABS]
59. Vender M, Delfitto D. 2025. Bridging the gap in adult dyslexia research: assessing the efficacy of a linguistic intervention on literacy skills. Annals of Dyslexia 75(1):42-70. DOI 10.1007/s11881-024-00314-x. PMID 39307875. PMC11954693. [FT: Participants, Literacy intervention, Results]
60. Walker G. 2008. Constant and progressive time delay procedures for teaching children with autism: a literature review. Journal of Autism and Developmental Disorders 38(2):261-275. DOI 10.1007/s10803-007-0390-4. PMID 17546491. [ABS]
61. Whitten A, Key AP, Mefferd AS, Bodfish JW. 2020. Auditory event-related potentials index faster processing of natural speech but not synthetic speech over nonspeech analogs in children. Brain and Language 207:104825. DOI 10.1016/j.bandl.2020.104825. PMID 32563764. [ABS]
62. Wilson RC, Shenhav A, Straccia M, Cohen JD. 2019. The Eighty Five Percent Rule for optimal learning. Nature Communications 10:4646. DOI 10.1038/s41467-019-12552-4. PMID 31690723. PMC6831579. [FT: Introduction, derivation of the optimal error rate]
63. Worth J, Nelson J, Harland J, Bernardinelli D, Styles B. 2018. GraphoGame Rime: evaluation report and executive summary. Education Endowment Foundation and NFER. https://www.nfer.ac.uk/media/idlhbicn/graphogame_rime_evaluation_report_and_executive_summary.pdf. [FT: executive summary, Table 1]
64. Yeatman JD, Tang KA, Donnelly PM, Yablonski M, Ramamurthy M, Karipidis II, Caffarra S, Takada ME, Kanopka K, Ben-Shachar M, Domingue BW. 2021. Rapid online assessment of reading ability. Scientific Reports 11:6396. DOI 10.1038/s41598-021-85907-x. PMID 33737729. PMC7973435. [FT: Results (Studies 1 and 2), Discussion]
65. Ziegler JC, Goswami U. 2005. Reading acquisition, developmental dyslexia, and skilled reading across languages: a psycholinguistic grain size theory. Psychological Bulletin 131(1):3-29. DOI 10.1037/0033-2909.131.1.3. PMID 15631549. [ABS]
66. Ziegler JC, Pech-Georgel C, George F, Lorenzi C. 2009. Speech-perception-in-noise deficits in dyslexia. Developmental Science 12(5):732-745. DOI 10.1111/j.1467-7687.2009.00817.x. PMID 19702766. [ABS]
67. Zorzi M, Barbiero C, Facoetti A, Lonciari I, Carrozzi M, Montico M, Bravar L, George F, Pech-Georgel C, Ziegler JC. 2012. Extra-large letter spacing improves reading in dyslexia. Proceedings of the National Academy of Sciences of the United States of America 109(28):11455-11459. DOI 10.1073/pnas.1205566109. PMID 22665803. PMC3396504. [FT, PMC page: Methods, Results, Experiment 2]
Counts: 67 sources; 28 FT, 31 ABS, 8 META. Of the 59 sources whose own text supplied a number or finding (FT plus ABS), 28 are FT. Of the sources that carry a recommendation's main evidence, Galuschka, the NRP report, the Cochrane review, Mueller, the EEF report, Richardson and Lyytinen, the reporting guideline, the WWC standards, Thurmann-Moe, Yeatman, Callens, Luniewska, Horn and McDougale are FT; McTigue, Garcia-Perez, Walker, Eyler and Ledford, and Bhattacharya and Ehri are ABS. The META entries are the classic papers behind the code's own citations (Levitt, Liberman, Ehri), method references (Kaplan and Meier, Jacobson and Truax), a citation-error check (Kornell 2010), and two papers read only through a named FT source or with no abstract available (Bruck, Ronimus 2014).

Not re-read here and left as the code and the repository's research notes cite them: the list at the end of Section 1.10, and the 140 and 126 sources of `app/docs/research/new_modes/syllables-all-ages.md` and `syllables-task-design.md`.

### Simulation assumptions (for Sections 2, 4 and 6)

- Game simulations ran the real `SyllablesMode` (the four Syllables modules as at commit d6a93a7) with a stub engine, speech off, the shipped config values (30 words, prompt steps 0.6, 0.75, 0.9, floor margin 300 ms, child fall table, 1.0 s set gap, 1.5 s word gap, 3.0 s attend), each profile's own overrides, and a 60-minute session cap except in the cap check, which used the shipped 20; a fresh seed per block; 60 to 200 blocks per cell.
- Reader model: each foil kind captures the first press with a set probability (child reader: F1 0.01, F2 0.05, F3 0.10, F4 0.07, F5 0.05, F6 0.04, F7 0.07, F8 0.12, F9 0.08; adult reader: F1 0.005, F2 0.015, F3 0.03, F4 0.01, F5 0.02, F6 0.02, F7 0.02, F9 0.03; family studies used equal capture of 0.08, 0.20 or 0.30 for every near kind); a set's first press is wrong with probability one minus the product of the three foils' complements, on a foil chosen in proportion to capture. Decision time is lognormal with the stated median, log SD 0.45 (children) or 0.40 (adults), plus 0.25 s (children) or 0.10 s (adults) per near foil on screen. If the buzz comes before the decision, the reader follows it with probability 0.9 (children; 0 for adults, who have no prompt) and presses 0.45 s after it; a decision after the end of the fall is no response; after a wrong press the reader presses again 0.9 s later and is right with probability 0.6. Quick-look accuracy is 0.25 plus 0.75 times a logistic function of exposure (centre 0.25 to 0.35 s, scale 0.05 s) or a flat 0.9 where stated.
- The censoring-aware latency is the Kaplan-Meier product-limit median of the time to an unaided first press, with sets censored at the buzz or at the end of the fall.
- Foil-pattern tests: Monte Carlo multinomial (4,000 draws) of a chi-square statistic, expected first-press captures in proportion to each near kind's appearances, F1 excluded unless stated.
- Quick-look precision: a copy of `_move_expo`'s rules (80 ms steps, 100 ms to 1.5 s, one-down until the first error then 3-down-1-up, threshold the mean of the reversals after the first, at least two needed) with a four-option logistic psychometric function (scale 0.04 s), 4,000 pairs of runs per cell.
- Probe change: one reader; each item's difficulty drawn from a normal distribution with SD 1.0 logit and held fixed across sessions; a session-level shift with SD 0.3 logit; baseline and later centres of 0.65 and 0.75 or 0.85 on the logit scale's probability (mean accuracies 0.62 to 0.81 as reported); 20 or 40 items; 3 or 5 sessions per phase; one-sided t-test on session means, a pooled two-proportion z-test, and NAP with an exact permutation p; 1,500 runs per cell.
- These are models with assumed parameters: they describe how the rules behave, not how any reader will play.
