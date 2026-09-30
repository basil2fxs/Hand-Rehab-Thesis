# Echo mode: deep research audit

1 October 2026. Scope: the study battery's Echo step, `app/finger_rehab/game/modes/echo.py` (mode key `echo`, rule `simon`), its config block and battery override, the gameplay screen, logging, the pinned tests and the notebook analysis. The legacy ladder rule (`echo.rule: ladder`) is covered only where the design or the code still leans on it (E2 and the hidden Hebb stream).

Tags: [FT] full text read, with the table or section named; [ABS] abstract only; [META] bibliographic record only (where content is given for a META source it was read in a named FT secondary source). Number labels: "(arithmetic)" is computed here from source or code values; "(simulation)" is a Monte Carlo result under the assumptions listed at the end; "(pilot)" is the development team's blocks under `sessions/`, which describe the rig and not people; "(code)" and "(design doc)" are values read in the repository; "(reproduction)" is a run of the real `EchoMode` class in a scratch harness that imports the repository without writing to it. Line numbers refer to commit 6d4573d. The Reaction and Rhythm changes of the same day moved some of them (the `echo:` block starts at line 1519 instead of 1513 and the battery override sits 8 lines lower), so functions are named as well.

---

## 1. What the mode does now

### 1.1 The game loop under the study battery

| Step | What happens | Value | Where |
|---|---|---|---|
| Place in the sitting | Pass 1 only: order A step 3, order B step 7, straight after Rhythm in both orders; the 60 minute Trial Mode length plays it again after the pass 2 core | | `default.yaml` 1960, 1982; Trial Mode 2130 to 2222 |
| Battery override | Two games per block, ceiling 10 items | games 2, max_len 10 | `default.yaml` 2040 to 2042; design doc Section 2.4 |
| Before the block | NEXT UP card: title plus "Watch, then play it back"; GET READY card with a countdown and no instruction text | 3.0 s | `screens.py` 1539 (`ModeSelectScreen.MODES`), `_draw_next_up` 6711, `_draw_countdown_card` 3665; `default.yaml` 599 |
| Material | One sequence per game, drawn once from sha256(code, "echo_simon_v1", game index) over the four right-hand lanes: uniform, no immediate repeats, revisits allowed. Trial t plays the first t items. Game index = the code's earlier Simon games in the sessions tree plus the game number | 10 items (the cap) | `echo.py` `participant_simon_seed` 334, `simon_stream` 349, `count_prior_echo_games` 371, `_draw_game` 661; `engine.py` `begin_echo_block` 5074 |
| Announce | "Watch the echo..." chip, or "One more go" on the replay the life buys; first item after LEAD_S | chip 1.2 s; LEAD_S 1.0 s | `echo.py` 476, `_begin_announce` 799 |
| Presentation | Each item: tile lit in its finger's colour, buzz on that finger for the item's on-time, lane tone (C4 261.63, E4 329.63, G4 392.00, C5 523.25 Hz, index to little, 120 ms). Onsets run on absolute deadlines from the playback anchor | on 400 ms; onset to onset 800 ms at lengths 1 and 2, 750 at 3, 700 at 4, 650 at 5, 600 from 6 | `ioi_for` 700, `_play_frame` 915, `_fire_item` 956; `default.yaml` 1569 to 1576; `audio/engine.py` 103 |
| Motor floor | Onset to onset never under item-on plus MOTOR_CLEAR_S | 550 ms (code); the config floor of 600 ms binds | `echo.py` 483, 563 to 568 |
| Turn hand-over | Reproduction opens at the last item's offset on the presentation grid; "Your turn" chip; presses before that offset are logged as playback presses and ignored | chip 1.5 s | `_end_play` 940, `_begin_respond` 1002, `_handle_press` 1017 to 1041 |
| Reproduction | Rising-edge presses; each press resets the idle window; a correct press flashes its tile green and replays its lane tone, with no buzz; the first wrong press ends the attempt; a silent idle window ends it as an omission | idle 10.0 s; flash 0.25 s | `echo.py` 1008, 1044, 1059 to 1069, `_echo_back` 1071; `default.yaml` 1586 |
| Points | Correct: great_points plus 2 per item; failed: 2 per item before the error; a "Longest echo: N" chip on a new game best (drawn under the study's encouraging style) | 6 + 2L; 0 + 2 x n_right; chip 2.0 s | `echo.py` 1111 to 1139; `default.yaml` 717, 723, 1863 |
| Error record | First-error serial position (`pos`) and class: omission, transposition (pressed lane anywhere in the sequence) or intrusion | | `echo.py` 1160 to 1163, `_miss_class` 1293 |
| Growth | Correct: length plus one after a rest; past the cap the game ends as "ceiling" | rest 2.0 s | `_after_trial_simon` 1383 to 1390; `default.yaml` 1588 |
| Spare life | First miss: the same sequence at the same length once more. Rest before it: rest_s after a wrong press; a forced rest with "Take a breather" after an omission | lives 1; 2.0 s or 20.0 s | `echo.py` 1391 to 1404; `default.yaml` 1537 to 1538, 1596 |
| Game end | Second miss: game over ("second_miss"). If both of the game's misses are omissions, however far apart, the game ends as "fatigue" and the whole block ends with it | | `echo.py` 1405 to 1415, `_finish_game` 1439 |
| Between games | "New game", a rest, a fresh sequence and life, back to one item | 2.0 s | `echo.py` 1443 to 1454 |
| Board drop | A silent turn that overlaps a drop is voided (`device_drop`) and the length replayed | | `_rig_void` 1255, `_after_trial_void` 1271 |
| Block cap | Checked at trial close | 10 min | `default.yaml` 1601 |

Channel timing (study MacBook, measured 24 September 2026): motor motion 74 ms after the command, the tone 77 ms after dispatch; the tile appears on the next frame (0 to 16.7 ms) plus a panel lag nobody has measured (`docs/research/new_modes/modes-review.md`, "Device facts"). So the light leads the buzz and the tone by roughly 50 to 70 ms (arithmetic, taking 5 to 25 ms for the tile). At 600 ms onset to onset the command gap between items is 200 ms; with the class spin-down of about 115 ms quoted in `echo.py` 477 to 483, the finger is still for about 85 ms between items (arithmetic). No two consecutive items share a finger (code), so successive buzzes never land on the same finger.

What the timing tools model: `scripts/measure_battery.py` plays Echo with a hand that reproduces every sequence (first press 0.4 s, then 0.55 s per press), so both games reach the cap; the measured 3.06 minutes in design doc Section 2.3 is the ceiling case (code). `scripts/simulate_cohort.py` gives each simulated person a fixed span cap of 4 to 8 and no trial-to-trial noise, so the simulated cohort recovers span exactly by construction and says nothing about Echo's reliability (code; the research log records "the Echo span exactly").

### 1.2 Scoring, the screen and the instructions

- Results card after the block: SCORE, LONGEST ECHO (span, the best game) and ITEMS RIGHT (total_items) (`screens.py` SLIM_CARDS 6912, cards from 7079).
- Waiting tiles are neutral grey and a lit tile shows its finger's colour (`NEUTRAL_IDLE_BLOCKS`, `screens.py` 3138). Each item therefore carries four redundant codes for one of four identities: position, colour, touch on the finger that must press, and pitch (code).
- During reproduction every correct press replays its lane tone, so the four-note melody plays back as it is reproduced (code). The retail toy does the same: each of its four lenses lights and sounds its own tone when pressed (Milton Bradley 1978 manual [FT]).
- What the participant is told: "Watch, then play it back" on the NEXT UP card, nothing on the GET READY card, and the run sheet's "Press lightly, like typing. Some games have a hidden rule; don't try to work it out, just play." Nothing says that each round adds one item to the end of the same sequence, that speed does not count, that a miss buys one replay, or that there are two games (code; `docs/study_day/run_sheet.md`).
- The "Watch the echo..." chip lasts 1.2 s and the first item comes at 1.0 s, so the chip is still on screen during the first 200 ms of item 1 on every trial (arithmetic from `echo.py` 806 to 810).

### 1.3 Logging and block_stats

- Trial row: `echo;len;trial;run;hebb;played;pressed;n_right;outcome;pt=<press offsets from the turn opening, ms>;rule=simon;game;seed;life;lives_left;pos;miss`, plus `void=1` on a voided close; waveform params `seq`, `pulse_ms`, `ioi_ms`, `hebb`, `rule`, `game_seed` (`echo.py` 1164 to 1197).
- raw.csv: `echo_config`, `echo_game` (index, seed, lives, the whole sequence), `echo_trial`, one `stim` event per item and each playback press (`engine.py` 5160 to 5172; `echo.py` 680 to 697, 866 to 877, 982 to 987, 1034 to 1040).
- `block_stats` (1553 to 1629): rule, games, lives, games_played (per game: index, seed, span, total_items, n_trials, life_used_at, recovered, end_reason, misses), span_mean, total_items, the schedule parameters, span (best game), total_correct, n_trials, n_omissions, n_voided, per_length, hebb_trials (empty under Simon), playback_presses, fatigue_rests, run_end_reasons, end_reason.
- Logged but read by nothing: the first press latency (the first `pt` value) and `playback_presses` (code).

### 1.4 Registered checks and the notebook

- E1 (design doc Section 1.11, line 927 and the one-board note; notebook `sec_cohort_validity` 24344 to 24360): cohort median of span (best of two) within 5 to 9 on four lanes. `_mean_check` (23398) passes the row only when the percentile bootstrap interval of the median (4000 draws) sits inside the band; otherwise "direction only".
- E2 (Hebb) is DROPPED because the hidden repeat exists only under the ladder rule; E3 is DROPPED on four lanes because past four items every lane is a sequence lane (24362 to 24421).
- E2p (exploratory, outside Holm): per participant, the share of misses on the newest item minus the mean chance share 1/L, cohort one-sample test above zero (24377 to 24386; `_cohort_echo` 20611 to 20622).
- Metrics per block (`_cohort_echo` 20562): span (best game), span_mean, total_items (summed over games), n_omissions, life_used_share, edit_score_mean (length-weighted), ceiling_games, prefix_miss_share, newest_miss_excess.
- Reliability: Echo has no T row. `_sec_echo_simon` prints each block's two spans and their spread and, with three or more sessions in the selection, a between-game Spearman rho with no interval (18832 to 18866). `COHORT_NO_SPLIT_REASON` says span and span_mean have "nothing to split" (22711 to 22712). The 60 minute sitting feeds an exploratory second-go table for span, span_mean and total_items (`COHORT_SECOND_GO_METRICS` 29493).
- Chapter descriptives (18808 to 18950): a per-game table with two compressibility proxies, misses by class, the newest-item share against 1/L, life replays against first attempts at the same lengths, the median inter-press interval beside a "healthy-adult reference about 600 ms", a span trajectory across sessions, and the claim limits.
- Fine series (21878 to 21885): the running maximum of the attempted length across both games. Design doc Section 4.7 figure 4 (line 2083) asks for the "longest correct length so far".
- E1 figure (24730 to 24740): a histogram with a Corsi 6.2 line only; design doc Section 4.7 figure 6 asks for the four-lane Simon band.
- The ladder chapter (19674) and `MODE_CLAIM_LIMITS["echo"]` (25954) say that where omissions outnumber wrong presses the block is motor-limited or fatigue-limited.

### 1.5 What is already claimed, and the sources cited

| Claim | Where | Source cited | Status after this review |
|---|---|---|---|
| The rule is the 1978 toy's Game 1 (repeat and add one; an error or 5 s of silence ends it; LONGEST reads back the best run) with a two-error stop applied once | `echo.py` 6-16 | Milton Bradley manual | Verified [FT]; the LONGEST button replays the longest sequence since the unit was switched on, so a best-across-games readout is the toy's own measure |
| The toy "speeds up as you survive", which is Berch's drift | `echo.py` 94-97 | Berch 1998 | Partly: the toy's tempo steps come after the 5th, 9th and 13th signals of a sequence (manual [FT]), a fixed function of position like Echo's own length schedule |
| Woods 2011: maximum length retested at 0.68, two-error score at 0.39 | `echo.py` 18-29; config 1533-1535 | Woods et al. 2011 | Numbers verified (forward span, Table 3 [FT]); the 0.68 is the maximum over 14 staircase trials that continued after errors, and the spare life is still a stop rule (Q7) |
| Toy Monte Carlo: true span 6 gives 5.14 (SD 1.05) with no life, 5.81 (0.81) with one, 5.95 (0.83) for the Kessels ladder | `echo.py` 29-37 | own simulation | Reproduced exactly with a logistic slope of 1.5 per item (simulation); at 1.2 per item: 4.93 (1.25), 5.76 (0.95), 5.97 (0.97) (simulation) |
| Two games, "report the best and the mean" | `echo.py` 35-37; config 2041 | Woods 2011 | Supported, with the order reversed: the mean of two is the more reliable number (Q8) |
| Per-item credit is "the better-behaved span quantity" | `echo.py` 26-29, 468-471 | Conway et al. 2005 | Not supported as used: Conway's partial credit assumes every item of each list is recalled; Echo stops at the first wrong press (Q6) |
| Partial credit retested better than span on a digital Corsi, 0.68 against 0.58 | design doc 922; modes-review | Bergman et al. 2025 | Numbers verified (Table 3 [FT]); they do not transfer to truncated credit, which correlates 0.97 with span_mean (simulation) |
| Edit distance is as reliable as partial credit and more informative for weaker players | notebook 20587-20595 | Gonthier 2022 (sec_echo docstring) and 2023 (`_cohort_echo`) | Gonthier's gain comes from positional shifts in full recall [ABS]; under a first-error stop the edit score is partial credit plus at most 1/L (arithmetic) and tracks span_mean at r = 0.40 (simulation) |
| Chekaf et al. built on SIMON and showed each sequence whole (quoted) | `echo.py` 40-46 | Chekaf 2015, 2018 | Record verified [ABS]; the quotation could not be checked (no full text reached); Mathy et al. 2016 [FT] confirms whole sequences at 1000 ms per colour in the sister task |
| Repetition learning is explicit and abrupt | `echo.py` 51-53 | Musfeld et al. 2023 | Verified [FT] |
| 94 college students, four games with 30 s rests, no practice, spans about seven | `echo.py` 55-61; design doc 1.11 | Gendle and Ransom 2006 via Mathy 2016 | The figure of about seven and the absence of practice effects are verified as reported in Mathy 2016 [FT]; 94 and 30 s are unverified; the year is 2006 in Mathy 2016 and 2009 in Chekaf 2018's reference list (Crossref) |
| Corsi mean 6.2 (SD 1.3), n = 70 | design doc 927; notebook 24735 | Kessels et al. 2000 | 6.2 (SD 1.3) as quoted in Zhao et al. 2026 [FT, Methods]; n = 70 [ABS]; the primary table was not read |
| Start levels 1 to 3 and five stop criteria across 39 studies | `echo.py` 82-86 | Arce and McMullen 2021 | Verified [FT, Sections 2.5 to 2.7; 39 studies in the abstract] |
| One item per second is standard; eCorsi runs 500 ms on, 1000 ms onset to onset | `echo.py` 99-102 | Kessels 2000; Brunetti et al. 2014 | Verified [FT] (Arce; Brunetti Procedure) |
| No source supports slower presentation for motor-impaired players | `echo.py` 123-126 | own search | Not re-examined for patients; in healthy adults longer encoding time (3 against 1 s per block) improved Corsi span (Fischer 2001 [ABS]) |
| Paediatric pacing moves performance | `echo.py` 131-132 | "Simpson 2021, PMC8366059" | Wrong citation: PMC8366059 is Mason, Bowmer and Welch 2021, a peg-tapping inhibition task in children aged 5 to 6 [ABS] |
| Multisensory protocols are an active strand of post-stroke cognitive rehab | `echo.py` 142-144 | "Cheng 2022, J Clin Med 11:6324"; Johansson 2012 | Wrong author: J Clin Med 11(21):6324 is Parisi et al. 2022, a systematic review of 10 studies, mostly virtual reality [ABS]; Johansson 2012 not identified |
| Congruent multisensory stimulation aids learning | `echo.py` 139-141 | Shams and Seitz 2008 | [META]; for span specifically see Q13 |
| Ordered tactile recall caps near 4 | `echo.py` 153-154 | Yeganeh et al. 2026 | Record verified [META, Crossref]; content not re-read here |
| E3 cannot run on four lanes | design doc 1.11 | arithmetic | Correct (code) |
| E1: a cohort median of 5 to 9 is consistent | design doc 1.11 | Gendle and Ransom | E1 passes in 89 to 99 percent of simulated cohorts with 50 percent points of 6 to 7.5 and fails outright only from above (simulation, Q10) |
| Reliability: moderate for total_items and span_mean, "the upper end for span" | design doc 954 | none | Partly: span_mean about 0.69, best-of-two about 0.63, one game about 0.52 (population values, simulation); total_items duplicates span_mean |
| Omissions outnumbering wrong presses mark a motor- or fatigue-limited block | notebook 19674, 25954 | none | Not supported: omissions and transpositions are the main errors of healthy adults in spatial span (Woods et al. 2016 [ABS]) |
| Healthy-adult inter-press reference about 600 ms | notebook 18910, 19688 | eCorsi | Verified as 593 ms (SD 258) (Brunetti Results [FT]) for tablet taps with arm movements, not finger presses |
| The life replay should succeed more often than first attempts | notebook 18893-18901 | none | The comparison is biased: with no replay benefit, replays succeed about 0.50 and first attempts at the same lengths about 0.81 (simulation, Q12) |
| Two omissions in a row are a hand that stopped answering | `echo.py` 1405-1408; config 1590-1594 | none | Any game whose two misses are both omissions ends the whole block (reproduction, Section 1.7) |
| Debrief mentions a hidden pattern in Echo | design doc 5.1 (2295) | none | Stale for the Simon rule; `docs/study_day/debrief.md` already leaves Echo out |
| Couture and Tremblay 2007 | Reference Bank row E2 | | The paper is Memory and Cognition 34(8), December 2006 [META] |

Also cited for Echo: Corsi 1972 and Milner 1971 (the original task), Farrell Pagulayan et al. 2006 (developmental norms), Hebb 1961, Couture and Tremblay 2006, Melby-Lervåg et al. 2016 (no far transfer), Kessels et al. 2008, Oberauer et al. 2018, Roe et al. 2017 and 2024, Kane et al. 2007 and Jaeggi et al. 2010 (modes-review E-L1 to E-L10).

### 1.6 Pilot blocks on disk (rig check only)

Five Echo folders: two empty (2026-09-29, 0 trials), one Simon block (P669, 2026-09-23) and two legacy ladder blocks (2026-09-02 at the old 500/1000 grid; 2026-09-03). The Simon block reproduced lengths 1 to 4, then timed out silently at length 5 and was left unfinished (no game record). Its first press came 948 to 1713 ms after the turn opened and its inter-press intervals were 387 to 695 ms, shortening within each sequence (pilot, from the `pt` fields). Across the two blocks that had failures, 3 of 4 failed trials were silent timeouts rather than wrong presses (pilot).

### 1.7 A code finding, reproduced: two silent misses end the block

`_after_trial_simon` marks a game "fatigue" when the current miss is an omission and the game's previous miss was also an omission; `_finish_game` then ends the block for "fatigue" whatever games are left (`echo.py` 1405 to 1415, 1439). The game's two misses are always its only two (the life, then the end), so they need not be consecutive trials. Driving the real `EchoMode` with the battery settings (two games, cap 10, idle 10 s) (reproduction):

- silent at length 5 twice in game 1: block ends as "fatigue" after one game, span 4, 67.7 s of block time;
- silent at length 5 (replay correct), then silent again at length 8: block ends as "fatigue" after one game, span 7;
- the same player pressing a wrong key instead of waiting: both games play (spans 4 and 6).

So a healthy participant who waits when unsure loses game 2, the registered best-of-two becomes a one-game score, and the block summary reads like exhaustion. The pinned test `test_silence_spends_the_life_then_ends_the_game_as_fatigue` covers a one-game block only.

---

## 2. Research questions and findings

### Q1. Which established task is Echo closest to, and what follows for interpretation?

- Corsi block-tapping: nine blocks, the examiner taps one block per second, start at two, two trials per length, stop when both fail (Kessels et al. 2000 standard, as set out by Arce and McMullen 2021, Sections 2.5 to 2.6 [FT]). Recall of the whole sequence, pointing response.
- The toy: four lenses with light and tone, one sequence grown by one signal per round, an error or more than 5 s ends the game, tempo steps within long sequences, a LONGEST readout of the best run since power-on (manual [FT]).
- Research versions of the toy: the Indiana "memory game" with four backlit buttons, lights, spoken colour names or both, fresh sequences at each length (Karpicke and Pisoni 2004, Method [FT]; Cleary, Pisoni and Geers 2001, Method [FT]); a nonspatial colour version with whole sequences at 400 ms plus 600 ms blank per colour (Mathy et al. 2016, Design [FT]).
- Supraspan learning: a fixed eight-block Corsi sequence repeated until three consecutive correct reproductions or 18 presentations (Facchin et al. 2024, Tests and procedure [FT]); span plus one sequences repeated eight times among 25 (Gagnon et al. 2004 [ABS]). Repeated presentation lets people reproduce sequences longer than their span.
- Echo: four finger lanes, light, colour, buzz on the responding finger and a tone per item, one sequence per game grown by one item, no immediate repeats, stop at the first wrong press, one replay, best of two games (code).

Bearing: Echo's span mixes immediate span with learning of a prefix that is re-presented and reproduced on every trial, a within-game supraspan process (Q3). Its codes are visuospatial, somatotopic (touch on the effector), colour and pitch, and its response is a finger sequence; memory for movement patterns and for spatial sequences rehearse independently (Smyth and Pendleton 1990 [ABS]). Fewer response alternatives improved Corsi performance (all nine blocks against only the relevant positions; Fischer 2001 [ABS]), and Echo has four. No single-code norm transfers.

### Q2. Healthy adult spans for the closest tasks

| Task and sample | Value | Source |
|---|---|---|
| eCorsi forward, 18 to 30 years (n = 73, mean 21.6) | 6.11 (SD 0.80); backward 5.29 (1.20); over-50s 4.76 (1.19) | Brunetti et al. 2014, Table 1 [FT] |
| Corsi, healthy controls (n = 70) | 6.2 (SD 1.3) | Kessels et al. 2000 [ABS], figure via Zhao et al. 2026, Methods [FT] |
| Corsi, young adults (mean age 21) | 7.1; eighth graders 6.9 | Farrell Pagulayan et al. 2006 [ABS] |
| Computerised spatial span, 18 to 46 years (n = 49) | maximum length 6.51 (1.04); two-miss span 5.73 (1.32); mean span 5.95 (1.03) | Woods et al. 2015, Table 2 [FT] |
| Same test, 18 to 82 years (n = 187) | maximum length 5.93 (1.01); two-miss span 5.15 (1.20); mean span 5.27 (1.01) | Woods et al. 2015, Table 2 [FT] |
| Digital Corsi, 20 to 79 years (n = 131) | forward span 6.13 (1.18) | Bergman et al. 2025, Table 3 [FT] |
| Corsi, 21 to 89 years (n = 340, mean 51.6) | 4.97 (1.03), one block every 2 s, two of three to pass | Facchin et al. 2024, Table 1 [FT] |
| Large Italian norms (older samples, mean age in the 50s) | maximal span 5.38 | Monaco et al. 2013 [META], via Woods et al. 2015 Discussion [FT] |
| The retail toy, college students | about seven (no SD given) | Gendle and Ransom [META], via Mathy et al. 2016, Discussion [FT] |
| Simon-based nonspatial task, children 6 to 10 (n = 374) | 3.8 (all-or-nothing), 4.4 (highest span) | Mathy et al. 2016, Results [FT] |
| Tactile ordered recall | about 4 | Yeganeh et al. 2026 [META] |

Facchin's age and education correction (adjusted = raw + 0.7616 x (ln age - 3.864) - 0.4229 x (sqrt education - 3.555), Table 2 caption [FT]) puts a 21-year-old with 15 years of schooling at about 0.76 below their raw score, so a raw span of about 5.7 matches that sample's average adjusted score (arithmetic).

Bearing: nominally the same Corsi task gives young adult means from 5.7 to 7.1 across studies, which is Berch's point about administration drift (Berch et al. 1998 [ABS]). The one Simon figure for adults is second hand, with no SD and a disputed year. E1's band can only be a plausibility frame.

### Q3. What does re-presenting the prefix do?

- A fixed, repeated supraspan sequence is learnable within minutes: CSSL 18.67 (SD 7.18) out of 29.16 in Facchin's 340 adults (Table 1 [FT]), and a delayed recall after 5 minutes was scorable (CSSR 1.14 of 1.62).
- Repetition learning needs the list's start to stay fixed: varying the first two items of an otherwise repeated list abolished the Hebb effect (Schwartz and Bryden 1971 [META]), and repeating only every other item gave no learning (Hitch et al. 2005 [META]); both are reviewed in Musfeld and Oberauer 2026 [FT]. The Simon rule keeps the start fixed and adds at the end, the most favourable arrangement for learning the prefix.
- Learning is explicit and abrupt: in 301 visual and 308 verbal participants aged 18 to 35, awareness of the repetition preceded (visual) or accompanied (verbal) the onset of learning, and only three participants learned without awareness (Musfeld et al. 2023, Results [FT]).
- The effect on span size cannot be read from published means: the toy's figure of about seven against Corsi 6.1 to 6.2 in young adults suggests a gain, but Farrell Pagulayan's young adults reached 7.1 on Corsi (Q2).

Bearing: a Simon span is a span plus within-game learning of the prefix; E2p (misses on the newest item) follows from the rule; the replay after a miss is a repetition at lag zero, not a hidden Hebb trial.

### Q4. Presentation timing: item duration, interval and the length schedule

- Standard rate: one block per second; Arce and McMullen found no standard for how long each block is shown and no study of its effect, and movement time between blocks did not change span (Arce and McMullen 2021, Section 2.5 [FT], citing Smyth and Scholey 1994 [ABS]).
- Longer encoding time helps: 3 s against 1 s per block and a 9 s against 1 s retention interval both improved Corsi performance (Fischer 2001 [ABS]); showing the items one at a time or all together, and their spatial organisation, both changed Corsi span in 30 adults (Mukunda et al. 2026 [ABS]).
- Rate in digit span (30 adults, mean 20.2 years): 7.1 (SD 1.1) at 1000 ms onset to onset, 6.7 (1.2) at 700 ms (d = 0.40), 6.6 (1.0) with mixed 700 to 1300 ms (d = 0.49), 6.8 (1.0) at 1300 ms (Schwartze et al. 2020, Results [FT]).
- Other timings in use: eCorsi 500 ms on, 1000 ms onset to onset (Brunetti [FT]); 977 ms per item (Woods et al. 2015, Methods [FT]); 400 ms plus 600 ms (Mathy 2016 [FT]); 1 s glow plus 1 s gap (Malykh and Kuzmina 2025, Methods [FT]); about 2 items per second with a 100 ms gap (Cleary 2001 [FT]).
- Echo: 400 ms on; 800 ms onset to onset at one and two items falling to 600 ms from six items (code). From six items the interval is 40 percent shorter than the one-per-second standard (arithmetic), at exactly the lengths that decide a healthy adult's span.

Where sources disagree: Arce reads the display-time question as unstudied and movement time as irrelevant; Fischer found that encoding time matters and Mukunda that the display format matters; Schwartze found a rate effect in verbal span. None tested finger lanes.

Bearing: the faster schedule is expected to lower span somewhat against standard-rate tasks. It is pinned, length-only and logged, which is what Berch asks for; keep it for the study and name it with every number.

### Q5. Four lanes, no immediate repeats, revisits: what the material does

- Arithmetic on the shipped generator: from the third item on, each item repeats the one two back with probability 1/3; an 8-item sequence holds 2.0 such A-B-A returns on average (10th to 90th percentile 1 to 4 of 6 possible), 17.5 percent of 8-item sequences use three lanes or fewer, and half of the steps go to a neighbouring finger (10th to 90th percentile 0.29 to 0.71) (simulation of 100,000 sequences).
- Repeats inside a sequence: in verbal serial recall close repeats are recalled well and distant ones poorly (Henson 1998 [ABS]); in tactile finger sequences a repeat separated by two items lowered accuracy and an adjacent repeat raised it (Roe et al. 2017 [ABS]); across seven experiments with visuospatial and verbal lists the inhibitory effect did not replicate consistently (Remouchamps et al. 2026 [ABS]).
- Compressibility: span depends on the length after compression, about three or four chunks or about seven uncompressed items (Mathy and Feldman 2012 [ABS]); chunkable colour sequences raised span at every age from 6 to 10 (Mathy et al. 2016, Results [FT]); compressibility predicted working memory performance (Chekaf et al. 2018 [ABS]).
- Path structure in Corsi: the error odds ratio was 13 times higher for high-demand paths (Ginsberg et al. 2017 [ABS]); at a fixed length of eight, sequence design moved performance from almost 100 percent to 6 percent (Ginsberg as reported by Zhao et al. 2026 [FT]).
- The toy allows immediate repeats; Echo does not, to keep a bounce from reading as a double press (code). That removes the easiest chunk (AA) but also cuts information to log2(3) = 1.58 bits per item after the first, against 2 bits (arithmetic). The two effects point in opposite directions.

Bearing: sequence difficulty varies between games and between participants because the seed is per code and game. Standard tests fix their items (Kessels' standard sequences via Arce [FT]; Farrell Pagulayan's item set [ABS]; Facchin's fixed paths [FT]). With ten people, material variance sits inside the between-person spread and inside the between-game difference.

### Q6. Scoring: span, per-item credit and edit distance when the attempt stops at the first error

- Conway et al. 2005 [FT, scoring section and Tables 2 and 3]: partial-credit unit scoring is the mean proportion of elements recalled per item; internal consistency favoured it (counting span .768 against .668 all-or-nothing, operation span .814 against .698, reading span .788 against .697; n = 236); load-weighted scoring gives positive skew; the whole list is recalled on every item.
- Gonthier 2023 [ABS]: edit distance protects against positional shifts (ABCD and BCDE), with a small reliability gain and a large information gain for harder items and weaker participants.
- Bergman et al. 2025 [FT, Table 3]: forward span ICC 0.58 (6.13 to 6.40, d = 0.26), forward partial credit 0.68, Corsi index 0.74, one month apart, n = 129 to 131.
- Echo arithmetic: a first wrong press at position k after k - 1 correct gives per-item credit (k - 1)/L; the edit score is k/L when the pressed lane occurs later in the sequence (nearly always on four lanes) and (k - 1)/L otherwise; an omission after k - 1 presses gives (k - 1)/L. Nothing after the error is recorded.
- Simulation: total_items correlates 0.97 with span_mean; edit_score_mean averages 0.90 (SD 0.05, 5th to 95th percentile 0.81 to 0.96), correlates 0.40 with span_mean and 0.33 with the true 50 percent point, against 0.83 for span_mean.
- life_used_share: a game that does not reach the ceiling can only end on its second miss, so it has always used its life; the metric equals one minus the share of games at the ceiling (code).
- Better-behaved alternatives from the literature: the psychophysical mean span, 0.5 below the start length plus the fraction correct at each length (Woods et al. 2011, Method [FT]); the summed proportion of lists correct per length, which correlated 0.95 with the longest-length score and was far more continuous and closer to normal (Cleary et al. 2001, Results [FT]).

Bearing: under this rule the only primary quantities are the length reached, where each failure fell, whether the replay recovered, and timing. Everything else is a transform of those.

### Q7. What does the Simon rule with one life estimate, and how does it compare with other rules?

- Stop rules lose information: forward digit span retested at 0.39 for the two-error maximum and 0.68 for the maximum over all 14 trials of a 1:2 staircase that kept going after errors (Woods et al. 2011, Table 3 [FT]); the traditional two-miss delivery rule inflates variance and underestimates true spatial span (Woods et al. 2015, Discussion [FT]); Arce and McMullen note that stricter stop rules can lower scores [FT].
- Woods' 1:2 staircase moves up with probability p and down with probability (1 - p) squared, so it hovers near p = 0.38 (arithmetic, the transformed up-down logic of Levitt 1971 [META]); mean span then estimates the 50 percent point from all trials.
- The Simon rule only climbs. Under a logistic psychometric function with slope 1.2 per item (Woods et al. 2016 [ABS]: accuracy fell about 30 percent per item around the mean span), a single game scores 0.24 items below the 50 percent point (SD 0.94), the best of two 0.27 above it (SD 0.77) and the mean of two 0.24 below (SD 0.67) (simulation). A block takes 17.5 trials at a 50 percent point of 7 (simulation).

Bearing: the spare life does what the docstring says; the remaining noise is a stop-rule property that a second game only partly removes.

### Q8. Reliability, consistency and practice

- Anchors: 0.58 for Corsi span and 0.68 for partial credit at one month (Bergman [FT]); 0.50 at one year in older adults (Sanchez-Benavides et al. 2016 [META], Bergman Table 4 [FT]); 0.68 for maximal span, 0.67 total correct, 0.84 psychophysical mean span weekly (Woods et al. 2015, Test-retest [FT]); forward digit span 0.39, 0.68 and 0.67 for the two-error, maximum and mean spans (Woods et al. 2011 [FT]); internal consistency of span tasks typically 0.70 to 0.90 (Conway, Reliability section [FT]).
- Simulation (population, between-person SD 1.0 item, slope 1.2): game 1 against game 2 r = 0.53; pass to pass 0.52 for one game, 0.63 best of two, 0.69 mean of two, 0.68 summed proportions, 0.66 total items. With a between-person SD of 0.8: 0.41, 0.52 and 0.58. With slope 0.8: 0.37, 0.49, 0.54; slope 1.8: 0.66, 0.73, 0.79.
- At n = 10 (2000 cohorts): ICC(2,1) best of two median 0.59 (5th percentile 0.14, 95th 0.84); mean of two 0.65 (0.23, 0.88); the notebook's between-game Spearman rho median 0.54 (5th percentile 0.01) (simulation).
- Same person, no true change: the two games differ by 2 or more items 25 percent of the time and are equal 30 percent of the time; mean absolute difference 1.03 items (simulation), close to the 0.96 digits by which forward spans moved between days in Woods et al. 2011 [FT].
- Spearman-Brown from r = 0.53: three games 0.77, four games (60 minute sitters) 0.82 (arithmetic).
- Practice: none across four toy games (Gendle and Ransom via Mathy 2016 [FT]); no task-order effect in children (Mathy 2016 [FT]); mean span +2.4 percent, not significant, over three weekly sessions (Woods et al. 2015 [FT]); +0.30 digits from day 1 to day 3 (Woods et al. 2011 [FT]); +0.27 items at one month (Bergman [FT]); in 20 minutes of continuous adaptive Corsi play, best span rose along a log curve and 10 of 25 young adults reached the 9-block cap (Schaefer et al. 2022, Results [FT]), though a running best can only rise.

Where sources disagree: brief repeats show little practice; long continuous play shows gains. Two games of about a minute each sit near the brief end.

Bearing: the design's class is right for span_mean and too generous for span; no Echo reliability can be claimed from the 45 minute sitting beyond a within-block between-game agreement whose interval at n = 10 covers almost everything.

### Q9. Ceiling and floor with a cap of 10

- Per person, P(best of two at the cap) is 0.1 percent at a 50 percent point of 7, 0.9 percent at 7.5, 4.3 percent at 8 and 37 percent at 9 (simulation, slope 1.2).
- In a cohort of 10, P(at least one capped) is 31, 57 and 82 percent for cohort centres of 7, 7.5 and 8 (simulation).
- Schaefer 2022 [FT]: 40 percent of trainees reached a 9-block cap within 20 minutes of practice.
- Floor: lengths 1 to 3 are near certain for a healthy adult and act as a built-in warm-up (simulation; the Simon rule starts at one item).

Bearing: a median is little affected by a few capped values; a mean is. Capped games are censored and the notebook already counts them (`ceiling_games`).

### Q10. Can E1 fail?

Simulation of the notebook's own rule (median of best-of-two, 4000-draw bootstrap interval inside 5 to 9), n = 10, between-person SD 1.0:

| Cohort 50 percent point | Pass | Direction only | Fail | P(someone at the cap) |
|---|---|---|---|---|
| 6.0 | 0.912 | 0.088 | 0.000 | 0.049 |
| 6.5 | 0.985 | 0.015 | 0.000 | 0.118 |
| 7.0 | 0.985 | 0.015 | 0.000 | 0.312 |
| 7.5 | 0.890 | 0.110 | 0.000 | 0.570 |
| 8.0 | 0.591 | 0.400 | 0.009 | 0.818 |
| 8.5 | 0.232 | 0.666 | 0.102 | 0.958 |

Also: the comparator (about seven on the toy) is a per-game figure, while E1 reads the best of two, which sits about 0.5 items above a single game (simulation). The per-selection check in `sec_echo_checks` (28048) fails a single participant who reaches the cap of 10, because 10 is above the band's 9 (code).

Bearing: for a plausible healthy cohort E1 cannot fail from below and passes almost always; it fails, if at all, from above through the cap and the best-of-two bias. It belongs with Rh2, B4 and A5 as a feasibility check.

E2p at n = 10 with the notebook's one-sided Wilcoxon: it passes in 100 percent of simulated cohorts when 60 percent of failures fall on the newest item, 84 percent at 40, 43 percent at 30, and 1 percent when failure positions are uniform (simulation). Its outcome says how strongly the rule concentrates failures on the newest item, which is why it is a rule check and not a memory finding.

### Q11. Error types and serial position when only the first error is seen

- Spatial serial recall shares the verbal mechanisms: transposition latencies fall with displacement, consistent with a primacy gradient plus position markers and response suppression (Hurlstone and Hitch 2015 [ABS]; review in Hurlstone, Hitch and Baddeley 2014 [ABS]).
- In healthy adults' spatial span, omissions and transpositions predominate, with weaker primacy and recency than in digit span (Woods et al. 2016 [ABS]); error paths simplify the target path while span is usually kept (Ginsberg 2017 [ABS]).
- Echo stops at the first wrong press or the first 10 s silence, so no serial position curve exists beyond the first error; the transposition against intrusion split is fixed by the lane count on four lanes (E3 dropped); an omission is a 10 s wait, followed by a 20 s forced rest before the replay, against 2 s after a wrong press (code).
- A four-lane alternative: classify each wrong press relative to the sequence (the lane just pressed again, a return to item k - 2, an anticipation of item k + 1, other) and relative to the hand (a neighbour of the correct finger or not). Chance is exact per miss: a random wrong finger is one of three; a neighbour is 1/3 for index or little and 2/3 for middle or ring, 0.5 on average (arithmetic, as in design doc Section 1.10 B2).

Bearing: omissions are ordinary memory errors in healthy adults, so the notebook's motor or fatigue reading of them is unsupported, and the block-ending "fatigue" rule (Section 1.7) acts on a normal error.

### Q12. Hebb repetition learning: what the design can and cannot give

- Visuospatial Hebb effects exist: dot sequences repeated every third trial (Couture and Tremblay 2006 [ABS]); every fourth trial, with anticipatory eye movements to the next location growing over repetitions (Tremblay and Saint-Aubin 2009 [ABS]); nine locations with constant or grouped timing (Sukegawa et al. 2019 [ABS]); visuospatial repetition learning needs sequential presentation (Ueda et al. 2023 [ABS]); Corsi span-plus-one sequences repeated eight times among 25 (Gagnon et al. 2004 [ABS]).
- Age: visuospatial supraspan Hebb learning was reduced in older adults while verbal was not (Turcotte et al. 2005 [ABS]); intentional instructions gave faster and greater learning in young adults only (Gagnon, Bédard and Turcotte 2005 [ABS]).
- Spacing and material: Hebb (1961) repeated a nine-digit list every third trial; Melton found no learning at every sixth list; Cumming and colleagues found strong effects up to every twelfth list when fillers came from a different item set, and weak or no learning at any spacing when all lists shared the item set (Page and Norris 2009, section (a) [FT]; primaries [META]).
- Individual differences: serial recall was reliable over six months while individual Hebb learning retested near zero (Bogaerts et al. 2018 [ABS]).
- Under the Simon rule there are no hidden trials (code), so E2 is correctly dropped. The replay after a miss is the only repeat; with no replay benefit its success rate is 0.41 to 0.59 depending on slope (simulation), so it has no fixed benchmark, and the notebook's comparison with first attempts at the same lengths is biased (0.81 against 0.50 with no benefit, simulation), because replays happen exactly at the length where that person just failed.
- The legacy ladder on four lanes repeats a hidden prefix-stable stream every third trial among fillers drawn from the same four lanes (code). The verbal item-set finding predicts weak learning there; spatial Hebb studies found effects with locations drawn from one set (Couture and Tremblay [ABS]). Sources point different ways; it is a risk for any later ladder study.

### Q13. Light, buzz and tone: what does multisensory presentation do to span?

- Children with normal hearing (8 to 9 years): colour names plus lights beat lights alone (p = 0.001) and beat digit names plus lights (p = 0.008), while arbitrary digit names added nothing over lights (p = 0.33); the matched-subset gain was +0.72 span units (t(21) = 4.91) (Cleary et al. 2001, Results [FT]).
- Adults (120 undergraduates, 40 per group): acquisition-phase absolute span scores 68.98 with lights and spoken colour names, 63.40 with lights only and 64.38 with names only, F < 1 (Karpicke and Pisoni 2004, Table 1 [FT]).
- A Simon-patterned task with auditory, visual and audiovisual modes found age deficits in all three (Humes and Floyd 2005 [ABS]); spatially congruent audiovisual cues enlarged attentional effects on visuospatial working memory (Botta et al. 2011 [ABS]); multisensory working memory remains little studied (Quak et al. 2015 [ABS]).
- Echo's tone is an arbitrary lane code (C4, E4, G4, C5 from index to little), closer to Cleary's digit-name condition than to the colour-name one, although the rising pitch runs in the same left-to-right order as the fingers of a right hand on the pads (code). The buzz sits on the finger that must press, which cues the response as well as the item. Tones replay on correct presses during recall (code).

Bearing: there is no evidence here for or against a span gain from the three channels; the number is a light-colour-touch-pitch span and must not be compared with light-only, tone-only or tactile-only spans.

### Q14. Reproduction timing: latency, pace and chunking

- eCorsi young adults: first tap latency 1843 ms (SD 366) forward; inter-tap interval 593 ms (SD 258) forward and 639 backward; in supraspan trials first tap latency was 1655 ms before correct and 1935 ms before wrong reproductions (Brunetti, Table 2 and Results [FT]).
- Response-initiation times were a useful extra measure of spatial span (Fischer 2001 [ABS]); computerised spatial span response times retested at ICC 0.93 to 0.94 weekly and correlated negatively with mean span (Woods et al. 2015 [FT]).
- Chunking: in 25 young adults, visuospatial working memory capacity correlated R = 0.78 with the chunk length of an explicitly learned 12-element finger sequence, chunk boundaries being the longer inter-response times; longer chunks came with longer chunk-initial times (R = 0.48) (Bo and Seidler 2009, Results [FT]). Motor programming accounts hold that a chunk is loaded before it is executed (Sternberg et al. 1978 [META], as cited in Bo and Seidler 2009 [FT]).
- Device: presses are stamped 10 to 11 ms late on average on a bursting board (SD about 6 ms, maximum about 21 ms) (modes-review, device facts); an inter-press interval subtracts two stamps, so the mean delay cancels and the jitter SD is about 8.5 ms (arithmetic, 6 x sqrt 2); the turn opening is placed on the presentation grid, which is stamped at the update tick 0 to 16.7 ms before the flip (code). Both are small against latencies of 1 to 2 s and intervals of 400 to 700 ms.
- Pilot: latencies 948 to 1713 ms and intervals 387 to 695 ms in one block (pilot).

Bearing: the rows already carry what is needed for a first-press latency, its growth with length, the failed-against-correct latency contrast and an interval profile per sequence. These are exploratory, unscored and consistent with the design's untimed recall.

### Q15. Rehabilitation populations: what the healthy study can and cannot say

- Corsi separates patient groups: 20 percent of 70 patients with cerebral lesions scored borderline and over 8 percent impaired, right hemisphere worse (Kessels et al. 2000 [ABS]); right posterior parietal and dorsolateral prefrontal damage impaired Corsi (van Asselen et al. 2006 [ABS]); people with Parkinson's disease show a moderate deficit on simple and complex visuospatial span and a small one on verbal span (Siegert et al. 2008 [ABS]).
- Feasibility after stroke: 19 adults with stroke completed a computerised Corsi study; trainees' best spans reached 6 to 8 in 20 minutes, with no effect of lesion side (Kettlety et al. 2025, Results [FT]).
- Older adults learn repeated spatial sequences less (Turcotte 2005 [ABS]), so the prefix-learning share of a Simon span is likely to differ in older patients.
- Training: working memory training improves near measures only, with no far transfer against treated controls (Melby-Lervåg et al. 2016 [ABS]).

Bearing: the healthy cohort can give a device-specific reference distribution, feasibility (duration, completion, ceiling rate, error types) and a within-block consistency estimate. It cannot give clinical sensitivity, a Corsi-equivalent span, or evidence that errors in patients are memory rather than motor.

---

## 3. Audit table

| Parameter or behaviour | Current value | What the evidence supports | Verdict |
|---|---|---|---|
| Rule | simon: one sequence per game, grown by one (`default.yaml` 1529) | A span plus within-game prefix learning (Q3) | Keep; name it a Simon span everywhere |
| Start length | 1 (1544) | Near-certain first trials work as warm-up (Q9) | Keep |
| Spare life | 1 (1538) | Removes most of the single-shot bias (Q7) | Keep |
| Games per block | 2 (battery 2041) | Mean of two about 0.69 against 0.52 for one game (Q8) | Keep; do not use trim rung 2 unless forced |
| Ceiling | 10 (battery 2042) | Rarely reached below a centre of 8 (Q9) | Keep; treat capped games as censored |
| Material seeding | per code and game index (`_draw_game` 661) | Structure moves difficulty (Q5); standard tests fix items | Change: fixed material for everyone |
| Immediate repeats | forbidden (`simon_stream` 349) | Protects against bounce reads; changes material against the toy (Q5) | Keep; state it |
| Item on-time | 400 ms (1569) | No standard (Arce [FT]) | Keep |
| Onset to onset | 800 to 600 ms by length (1570 to 1576) | Interval 40 percent shorter than standard from six items; likely lowers span (Q4) | Keep for the study; state it; rate condition after collection |
| Lead before item 1 | 1.0 s with a 1.2 s chip (`_begin_announce`) | Chip overlaps item 1 by 200 ms (arithmetic) | Change: chip at most 0.9 s |
| Channels | light, colour, buzz, tone; tone replays on correct presses | No span evidence either way (Q13) | Keep; report as a multi-code span |
| Idle window | 10.0 s per press (1586) | Generous against 1.8 s latencies (Q14) | Keep; add a "best guess" instruction |
| Rest after an omission that spends the life | 20.0 s forced (1596) | Makes the replay a delayed repeat for silent misses only | Change to the ordinary rest in the battery |
| Two omissions end the block | yes (`_after_trial_simon` 1405, `_finish_game` 1439) | Omissions are normal errors (Woods 2016 [ABS]); game 2 lost (Section 1.7) | Change: end the game only |
| Playback presses | logged and ignored | Unreported risk of eager starts | Keep; report the count |
| Points | 6 + 2L; 2 per item before an error | No speed term, consistent with untimed recall | Keep |
| Instructions | "Watch, then play it back" only | Cumulative rule, untimed recall and guessing unstated | Add one line |
| Headline | span (best of two) | Mean of two more reliable; best is biased up about 0.5 (Q7, Q8) | Change the order: span_mean first |
| total_items | summed over games | r = 0.97 with span_mean (simulation) | Demote to exploratory, per game |
| edit_score_mean | length-weighted | Not Gonthier's construct here (Q6) | Demote to exploratory |
| life_used_share | share of games that used the life | Equals one minus the ceiling share (code) | Replace with the recovered share |
| E1 | median best-of-two in 5 to 9, interval inside | Cannot fail from below; a feasibility check (Q10) | Keep; report as feasibility; fix the band at the cap |
| E2p | newest-item share minus 1/L | Follows from the rule (Q3) | Keep as exploratory rule check |
| Between-game agreement | Spearman rho, no interval | Median 0.54, 5th percentile 0.01 at n = 10 (simulation) | Change: ICC with interval, Spearman-Brown, shift |
| Life replay comparison | against first attempts at the same lengths | Biased (0.81 against 0.50 with no benefit) | Change |
| Omission reading | "motor- or fatigue-limited" | Not supported (Q11) | Change wording |
| Timing measures | median inter-press interval only | Latency and pace are informative and reliable (Q14) | Add latency and interval profile |
| Fine series | running maximum of attempted length | Design asks for correct length | Change |
| Simulated cohort | fixed span cap, no noise | Cannot test reliability outputs | Change the simulator |

---

## 4. Recommendations, ranked by evidence strength and value for the thesis

1. **Stop two silent misses from ending the block.** DESIGN-CHANGE (task behaviour, before any participant; log it). SAFE-NOW part in the notebook.
   In `echo.py` `_after_trial_simon` (1405 to 1415) end the game as "second_miss" and store `both_silent` in the game record; in `_finish_game` (1439) end the block for fatigue only on a block-level rule (for example three silent trials with no press at all in the block), not on one game's two misses. In the battery, give the omission-life the ordinary rest: add `fatigue_rest_s: 2.0` to `protocol.presets.study_battery.overrides.echo` (a rest, so it fits the preset's "count, rest or frozen rung" rule), or use `rest_s` for the replay in code. Update `tests/test_echo_mode.py::test_silence_spends_the_life_then_ends_the_game_as_fatigue` and add a two-game test in which game 2 runs after a double omission in game 1. SAFE-NOW: emit `games_played` and a `short_block` flag from `_cohort_echo` (20562) and print it in `_sec_echo_simon`, so a one-game block is never read as a best of two. Evidence: reproduction (Section 1.7); pilot (3 of 4 failures were timeouts); omissions are normal errors in healthy spatial span (Woods et al. 2016 [ABS]).

2. **Lead with the mean of the two games.** SAFE-NOW for reporting; DESIGN-CHANGE for the design doc's "Primary" order and any change to E1's metric.
   In the notebook set `("echo", "span_mean")` as the headline in the metric metadata (19923 onward) and print span_mean first in the normative table, span (best of two) beside it. In design doc Section 1.11 (919, 954) and 4.2 (1620) list span_mean first and reword the class: "moderate for span_mean (about 0.65 to 0.69, simulation); lower for span, the best of two (about 0.6), and for one game (about 0.5)". Keep game 2 in the trim ladder's last position (design doc 2.3, line 1193), stating that dropping it lowers expected reliability from about 0.69 to 0.52 (simulation). Evidence: simulation (Q8); mean-type spans retest better than maximum-type spans (Woods et al. 2015 [FT]; Woods et al. 2011 [FT]).

3. **Report E1 as a feasibility check, and fix its band and figure.** SAFE-NOW (text and figure); DESIGN-CHANGE only if the band or metric changes.
   Add E1 to design doc Section 4.6's "Feasibility checks" paragraph (1958) with the reason (passes in 89 to 99 percent of simulated cohorts with centres 6 to 7.5; fails outright only from above). In `sec_echo_checks` (28048) count a span at the cap as inside the band (`lo <= span` and `span <= max(hi, cap)`). In the E1 figure (24730 to 24740) draw the 5 to 9 band and label the histogram "best of two". Reword `MODE_LIT["echo"]` E1 (25451) to say the band is a feasibility frame. Optional DESIGN-CHANGE: read E1 on span_mean with the band lowered by about 0.5 (simulation).

4. **Replace the metrics that carry no new information.** SAFE-NOW for new rows; DESIGN-CHANGE for the metric list in design doc Section 4.2.
   In `_cohort_echo` (20585 to 20603): replace `life_used_share` with `life_recovered_share` (share of used lives whose replay came back right, from `games_played[].recovered`) and `items_after_life` (span minus life_used_at); report `total_items` per game and label it "items before the first error"; move `edit_score_mean` under the exploratory heading; add `sumprop_span` (0.5 plus the summed fraction of attempts correct at each length, pooled over both games) in `_echo_simon_tables` (18717) as the Cleary and Woods style score. Drop the Conway and Bergman framing from `echo.py` 26-29 and 468-471 and design doc 922. Evidence: code (life), arithmetic and simulation (Q6); Cleary et al. 2001 [FT]; Woods et al. 2011 [FT].

5. **Give every participant the same material.** DESIGN-CHANGE.
   Add `seed: <integer>` under `protocol.presets.study_battery.overrides.echo` and, behind a new key such as `echo.seed_follows_game_count: true`, change `EchoMode._draw_game` (661 to 678) to use `forced_seed + game_index_base + run_idx`, so everyone meets the same two sequences in pass 1 and the 60 minute sitters' second block meets two new ones. Better still, add `echo.sequences` with two fixed 10-item sequences screened to be typical of the generator: all four lanes within the first five items, no alternation run longer than three, about two A-B-A returns in eight items and about half the steps to a neighbouring finger (simulation of the generator, Q5). The notebook keys material by seed already. Evidence: sequence structure changes Corsi accuracy several-fold (Ginsberg 2017 [ABS]; Zhao et al. 2026 [FT]); standard tests fix their items (Arce [FT]; Facchin [FT]).

6. **One instruction line.** SAFE-NOW (log it in the design doc because it changes what participants are told).
   Show on the GET READY card when `current_block == "echo"` (`GameplayScreen._draw_countdown_card`, `screens.py` 3665) and say once in the run sheet: "Watch the lights, then press the same fingers in the same order. Each round adds one more to the end of the same pattern. Speed does not count. If you're not sure, make your best guess." The NEXT UP description in `ModeSelectScreen.MODES` (1539) is shared with the hub, so it is the weaker route. Evidence: instructions change how people learn repeated sequences (Gagnon, Bédard and Turcotte 2005 [ABS]; Musfeld et al. 2023 [FT]); a guess replaces a 10 s wait and the fatigue path (Section 1.7).

7. **Correct the claims that the evidence contradicts.** SAFE-NOW (text only).
   - `echo.py` 18-37: Woods 2011's 0.68 is the maximum over 14 staircase trials that continued after errors; the spare life is still a stop rule; the toy Monte Carlo matches a slope of 1.5 per item.
   - `echo.py` 94-97: the toy's tempo steps after the 5th, 9th and 13th signals of a sequence (manual [FT]); it is not a function of success.
   - `echo.py` 131-132: replace "Simpson 2021, PMC8366059" with Mason, Bowmer and Welch 2021 and say it is a peg-tapping inhibition task in children.
   - `echo.py` 142-144: replace "Cheng 2022" with Parisi et al. 2022; drop or identify "Johansson 2012".
   - `echo.py` 55-61 and design doc 1.11: Gendle and Ransom's year is given as 2006 (Mathy 2016) and 2009 (Chekaf 2018); "94 students, four games, 30 s rests" is unverified.
   - Notebook 19674 and 25954: omissions are ordinary serial-recall errors in healthy adults (Woods et al. 2016 [ABS]).
   - Notebook 18910 and 19688: "about 600 ms" is eCorsi tablet tapping (593 ms, SD 258), not finger presses.
   - Notebook `sec_echo` docstring (19474) says Gonthier 2022, `_cohort_echo` says 2023: use 2023 (Behav Res Methods 55(4), published online 2022).
   - Design doc 954 (reliability class), 922 (Bergman transfer) and 2295 (Echo has no hidden pattern under the Simon rule).
   - Thesis notes (outside the repository): `Reference Bank.md` row E2 should read Couture and Tremblay 2006, not 2007; `NOTES FOR FINAL THESIS.md` (lines 246 to 249) still expects E1 "near the Corsi norm (about 6)" and E3 transpositions to dominate, both superseded on the one-board rig.

8. **Add reproduction timing as exploratory measures.** SAFE-NOW.
   In `echo_frame` (18606) add `ftl_ms` (the first `pt` value) and the interval list; in `_echo_simon_tables` add per game the median first-press latency, its slope over length, the median interval, and the position of the longest interval within each correct sequence of five or more (a chunk boundary); in `_sec_echo_simon` print the latency before failed against correct attempts at the same length, and the between-game agreement of median latency. Label all of it unscored and exploratory. Evidence: Brunetti [FT]; Woods et al. 2015 [FT] (response time ICC 0.93); Fischer 2001 [ABS]; Bo and Seidler 2009 [FT]; the device floor (Q14).

9. **Fix the life-replay comparison.** SAFE-NOW.
   In `_sec_echo_simon` (18889 to 18901) remove the comparison with first attempts at the same lengths, or replace it with a logistic mixed model of success on length with a replay term and a participant random intercept. Print the replay success with the no-benefit range 0.41 to 0.59 (simulation) and state why the old comparison was biased.

10. **A four-lane error table.** SAFE-NOW (exploratory); DESIGN-CHANGE only to reinstate a tested E3b.
    New notebook function beside `echo_miss_chance` (21649): for each wrong press, its relation to the sequence (repeat of the lane just pressed, return to item k - 2, anticipation of item k + 1, other) and whether it is a neighbour of the correct finger, each with its exact per-miss chance (one in three for a random wrong finger; neighbour 1/3 for index or little, 2/3 for middle or ring). Print pooled counts against summed chance. Evidence: Hurlstone and Hitch 2015 [ABS]; design doc Section 1.10 B2 arithmetic.

11. **Between-game consistency with its interval.** SAFE-NOW.
    In `_sec_echo_simon` replace the bare Spearman rho (18851 to 18866) with ICC(2,1) and ICC(3,1) of game 1 against game 2 with the exact interval (the notebook's existing `icc_ci`), the Spearman-Brown value for the mean of two, and the game 2 minus game 1 shift with its interval as a clean within-block practice estimate (same ladder, new material). Add `("echo", "span_mean")` to `COHORT_SPLIT_SOURCES` (22702) with the fixed game split and correct `COHORT_NO_SPLIT_REASON` (22712). Label it INTERNAL CONSISTENCY, WITHIN ONE BLOCK. Evidence: simulation (Q8).

12. **Presentation chip.** SAFE-NOW.
    In `_begin_announce` (806 to 807) show "Watch the echo..." and "One more go" for 0.9 s, so the chip is gone before item 1.

13. **Fine series and figure.** SAFE-NOW.
    In the fine-series echo branch (21878 to 21885) use the longest correctly reproduced length so far, restarting at game 2, as design doc Section 4.7 figure 4 says.

14. **Make the cohort simulator exercise Echo.** SAFE-NOW (tooling).
    In `scripts/simulate_cohort.py` `_echo` (369) replace the fixed span cap with per-trial success from a logistic around a per-person 50 percent point (slope about 1.2 per item) and occasional silent misses, so the between-game agreement, E1, the censoring and the fatigue path are tested before real data.

15. **After collection.** AFTER-COLLECTION.
    A Corsi-standard preset: one item per second, full reproduction without stopping at the first error, fresh sequences each trial and a 1:2 staircase over 14 trials scored by mean span (Woods et al. 2011 and 2015 [FT]); modality conditions (light only, buzz only, tone only, all three); a rate condition (600 against 1000 ms onset to onset); backward recall; three games per block where the slot allows (about 0.77, arithmetic). If the ladder's Hebb design is revived: span plus one lists, fillers that do not share the repeated list's pairs of items, and an awareness probe (Page and Norris 2009 [FT]; Musfeld et al. 2023 [FT]; Bogaerts et al. 2018 [ABS]).

---

## 5. Analysis recommendations for the notebook

| Add or fix | Where (cell 2) | Method source |
|---|---|---|
| Flag blocks with fewer games than configured; never call a one-game span a best of two | `_cohort_echo`, `_sec_echo_simon` | code finding (Section 1.7) |
| span_mean as the headline; best of two beside it | metric metadata near 19923; normative table | Woods et al. 2015 [FT]; simulation |
| E1 figure with the 5 to 9 band; capped spans inside the per-selection band | 24730; `sec_echo_checks` | simulation (Q10) |
| `life_recovered_share` and `items_after_life` in place of `life_used_share` | `_cohort_echo` 20585 | code |
| Summed-proportion span over both games | `_echo_simon_tables` | Cleary et al. 2001 [FT]; Woods et al. 2011 [FT] |
| total_items per game and edit_score_mean moved to exploratory | `_cohort_echo`; design doc 4.2 | arithmetic; simulation (Q6) |
| Game 1 against game 2: ICC(2,1), ICC(3,1), exact interval, Spearman-Brown, shift with interval | `_sec_echo_simon`; `COHORT_SPLIT_SOURCES` | McGraw and Wong 1996 (as the design uses); simulation |
| First-press latency, its slope over length, failed against correct latency, interval profile and chunk boundary | `echo_frame`, `_echo_simon_tables` | Brunetti 2014 [FT]; Fischer 2001 [ABS]; Bo and Seidler 2009 [FT] |
| Life replay without the biased comparator, or a mixed model with a replay term | `_sec_echo_simon` 18889 | simulation (Q12) |
| Wrong-press relation to the sequence and to the neighbouring finger, with exact chance | new, beside `echo_miss_chance` | Hurlstone and Hitch 2015 [ABS]; B2 arithmetic |
| Omission wording | 19674; `MODE_CLAIM_LIMITS` 25954 | Woods et al. 2016 [ABS] |
| Material covariates per game: A-B-A returns, share of neighbour steps, lanes used, beside the two existing proxies; span modelled with material as a covariate if seeds stay per participant | `_echo_simon_tables` | Mathy 2016 [FT]; Ginsberg 2017 [ABS] |
| Capped games treated as censored: medians and counts, no plain means | describe tables | simulation (Q9) |
| Spans split by order (step 3 in A, step 7 in B) | cohort tables | code |
| Playback presses per block, and trials with a press during the last item | `_sec_echo_simon` | code |
| Fine series: longest correct length so far, per game | 21878 | design doc 4.7 |

Keep as they are: E2 dropped, E3 dropped on four lanes, E2p as an exploratory rule check with its own caveat, the per-rule split (Simon and ladder never pooled), the protocol-deviation check on the presentation schedule, voiding of drop-overlapped silent turns, and the claim limits' refusal of Corsi comparisons and transfer claims.

---

## 6. Thesis facts

### 6.1 Reference values, with caveats

| Value | Figure | Source | Caveat for this rig |
|---|---|---|---|
| Corsi forward span, 18 to 30 years | 6.11 (SD 0.80), n = 73 | Brunetti et al. 2014, Table 1 [FT] | tablet, nine locations, 1 s rate, full reproduction, advance on one of two |
| Corsi span, healthy adults | 6.2 (SD 1.3), n = 70 | Kessels et al. 2000 [ABS], via Zhao et al. 2026 [FT] | primary table not read |
| Corsi span, young adults | 7.1 | Farrell Pagulayan et al. 2006 [ABS] | quasi-random item set |
| Computerised spatial span, 18 to 46 years | maximum 6.51 (1.04); two-miss 5.73 (1.32); mean span 5.95 (1.03), n = 49 | Woods et al. 2015, Table 2 [FT] | random layouts, mouse, 977 ms per item |
| Digital Corsi, 20 to 79 years | 6.13 (1.18) | Bergman et al. 2025, Table 3 [FT] | self-administered |
| The retail toy, college students | about seven | Gendle and Ransom [META], via Mathy 2016 [FT] | primary unread; year disputed; repeats allowed |
| Simon-based task, children 6 to 10 | 3.8 all-or-nothing, 4.4 highest span | Mathy et al. 2016 [FT] | nonspatial, repeats allowed |
| First tap latency, eCorsi young adults | 1843 ms (SD 366) | Brunetti, Table 2 [FT] | from the end of presentation, tablet |
| Inter-tap interval, eCorsi | 593 ms (SD 258) | Brunetti, Results [FT] | arm movements between blocks |
| Rate effect, digit span | 7.1 at 1000 ms, 6.7 at 700 ms onset to onset (d = 0.40) | Schwartze et al. 2020 [FT] | verbal, n = 30 |
| Practice at one month | +0.27 items (d = 0.26) | Bergman et al. 2025 [FT] | |
| Practice over three weeks | mean span +2.4 percent, not significant | Woods et al. 2015 [FT] | |

How to use them: Echo's numbers are the device's own, measured on four finger lanes with light, colour, touch and pitch per item, one growing sequence per game, a spare life, no immediate repeats, a 600 ms rate from six items and a first-error stop. The published values frame the order of magnitude; none is a norm to test against.

### 6.2 Reliability and practice expectations

- Two games in one block, no true change: the spans differ by 2 or more items in about a quarter of people; mean absolute difference about 1 item (simulation; Woods et al. 2011's day-to-day 0.96 digits [FT]).
- Between-game agreement: population r about 0.5 (0.37 to 0.66 across plausible slopes); at n = 10 the Spearman rho's 5th to 95th percentile runs from about 0 to 0.85 (simulation).
- Second go (60 minute sitters only): ICC(2,1) of the mean of two games most likely moderate, median 0.65 at n = 10 with a 5th percentile of 0.23; best of two 0.59 and 0.14 (simulation). Anchors: 0.58 span and 0.68 partial credit at one month (Bergman [FT]); 0.68 maximal span and 0.84 mean span weekly (Woods et al. 2015 [FT]).
- Three games would give about 0.77 and four about 0.82 (Spearman-Brown from r = 0.53, arithmetic).
- Game 2 minus game 1: small or none is the expectation for two short games (Mathy 2016 [FT]; Woods et al. 2015 [FT]); longer continuous play raises best span (Schaefer 2022 [FT]).

### 6.3 Claims to avoid

- A Corsi span, a comparison with Corsi or Wechsler norms, or a "visuospatial span" without the other codes named.
- Hebb learning, implicit learning or "sequence learning" from the Simon rule or the life replay.
- E1 as a demonstration of normal memory: it cannot fail from below for a plausible healthy cohort.
- "Partial credit (or edit distance) is more reliable than span" for Echo: that finding needs full recall.
- Omissions as signs of motor limitation or fatigue in healthy participants.
- Reliability from the between-game rho at n = 10, or test-retest from any within-session number.
- A multisensory benefit to span: no Echo condition isolates the channels, and the closest adult study found none (Karpicke and Pisoni 2004 [FT]).
- Chunk structure from inter-press intervals without a model and without the chance level.
- Training or transfer (Melby-Lervåg et al. 2016 [ABS]).
- Clinical sensitivity or a patient prediction: patients' wrong presses mix memory errors with motor slips, and older adults learn repeated spatial sequences less (Turcotte et al. 2005 [ABS]).

---

## 7. Sources

Retrieved and checked on 1 October 2026 through Europe PMC, PubMed E-utilities, Crossref, OpenAlex, PMC article pages and publisher, author or repository copies.

1. Arce T, McMullen K. 2021. The Corsi Block-Tapping Test: evaluating methodological practices with an eye towards modern digital frameworks. Computers in Human Behavior Reports 4:100099. DOI 10.1016/j.chbr.2021.100099. [FT: author copy via NSF Public Access Repository; Sections 2.5 to 2.8]
2. Berch DB, Krikorian R, Huha EM. 1998. The Corsi block-tapping task: methodological and theoretical considerations. Brain and Cognition 38(3):317-338. DOI 10.1006/brcg.1998.1039. PMID 9841789. [ABS]
3. Bergman I, Franke Föyen L, Gustavsson A, Van den Hurk W. 2025. Test-retest reliability, practice effects and estimates of change: a study on the Mindmore digital cognitive assessment tool. Scandinavian Journal of Psychology 66(1):1-14. DOI 10.1111/sjop.13054. PMID 39072723. PMC11735254. [FT: Methods, Table 3, Table 4]
4. Bo J, Seidler RD. 2009. Visuospatial working memory capacity predicts the organization of acquired explicit motor sequences. Journal of Neurophysiology 101(6):3116-3125. DOI 10.1152/jn.00006.2009. PMID 19357338. PMC2694099. [FT: Methods, Results]
5. Bogaerts L, Siegelman N, Ben-Porat T, Frost R. 2018. Is the Hebb repetition task a reliable measure of individual differences in sequence learning? Quarterly Journal of Experimental Psychology 71(4):892-905. DOI 10.1080/17470218.2017.1307432. PMID 28318415. [ABS]
6. Botta F, Santangelo V, Raffone A, Sanabria D, Lupiáñez J, Belardinelli MO. 2011. Multisensory integration affects visuo-spatial working memory. Journal of Experimental Psychology: Human Perception and Performance 37(4):1099-1109. DOI 10.1037/a0023513. PMID 21553989. [ABS]
7. Brunetti R, Del Gatto C, Delogu F. 2014. eCorsi: implementation and testing of the Corsi block-tapping task for digital tablets. Frontiers in Psychology 5:939. DOI 10.3389/fpsyg.2014.00939. PMID 25228888. PMC4151195. [FT: Participants, Procedure, Table 1, Table 2, Results on ITI and FTL]
8. Chekaf M, Gauvrit N, Guida A, Mathy F. 2018. Compression in working memory and its relationship with fluid intelligence. Cognitive Science 42 Suppl 3:904-922. DOI 10.1111/cogs.12601. PMID 29524237. [ABS]
9. Cleary M, Pisoni DB, Geers AE. 2001. Some measures of verbal and spatial working memory in eight- and nine-year-old hearing-impaired children with cochlear implants. Ear and Hearing 22(5):395-411. DOI 10.1097/00003446-200110000-00004. PMID 11605947. PMC3429119. [FT: Method, scoring, Results, Table 2]
10. Conway ARA, Kane MJ, Bunting MF, Hambrick DZ, Wilhelm O, Engle RW. 2005. Working memory span tasks: a methodological review and user's guide. Psychonomic Bulletin and Review 12(5):769-786. DOI 10.3758/BF03196772. PMID 16523997. [FT: author copy from the Engle lab; scoring section, Tables 2 and 3, Reliability section]
11. Couture M, Tremblay S. 2006. Exploring the characteristics of the visuospatial Hebb repetition effect. Memory and Cognition 34(8):1720-1729. DOI 10.3758/BF03195933. PMID 17489297. [ABS]
12. Cumming N, Page M, Norris D. 2003. Testing a positional model of the Hebb effect. Memory 11(1):43-63. DOI 10.1080/741938175. [META; findings as reported in Page and Norris 2009 and Musfeld and Oberauer 2026]
13. Facchin A, Pegoraro S, Rigoli M, Rizzi E, Strina V, Barera S, Castiglieri G, Daini R, Guarnerio C. 2024. Regression-based normative data for Corsi Span and Supraspan learning and recall among Italian adults. Neurological Sciences 45(12):5707-5718. DOI 10.1007/s10072-024-07756-6. PMID 39249691. PMC11554723. [FT: Participants, Tests and procedure, Table 1, Table 2 caption, Table 5]
14. Farrell Pagulayan K, Busch RM, Medina KL, Bartok JA, Krikorian R. 2006. Developmental normative data for the Corsi Block-tapping task. Journal of Clinical and Experimental Neuropsychology 28(6):1043-1052. DOI 10.1080/13803390500350977. PMID 16822742. [ABS]
15. Fischer MH. 2001. Probing spatial working memory with the Corsi Blocks task. Brain and Cognition 45(2):143-154. DOI 10.1006/brcg.2000.1221. PMID 11237363. [ABS]
16. Gagnon S, Foster J, Turcotte J, Jongenelis S. 2004. Involvement of the hippocampus in implicit learning of supra-span sequences: the case of SJ. Cognitive Neuropsychology 21(8):867-882. DOI 10.1080/02643290342000609. PMID 21038237. [ABS]
17. Gagnon S, Bédard MJ, Turcotte J. 2005. The effect of old age on supra-span learning of visuo-spatial sequences under incidental and intentional encoding instructions. Brain and Cognition 59(3):225-235. DOI 10.1016/j.bandc.2005.07.001. PMID 16182423. [ABS]
18. Gendle MH, Ransom MR. 2006 (2009 in some reference lists). Use of the electronic game SIMON as a measure of working memory span in college age adults. Journal of Behavioral and Neuroscience Research 4:1-7. No DOI found. [META; content as reported in Mathy et al. 2016]
19. Ginsberg ES, Rinehart N, Fielding J. 2017. Measures of task demand and error analysis in the Corsi Block-Tapping Test. Psychology and Neuroscience 10(4):404-413. DOI 10.1037/pne0000106. [ABS]
20. Gonthier C. 2023. An easy way to improve scoring of memory span tasks: the edit distance, beyond "correct recall in the correct serial position". Behavior Research Methods 55(4):2021-2036. DOI 10.3758/s13428-022-01908-2. PMID 35794418. [ABS]
21. Hebb DO. 1961. Distinctive features of learning in the higher animal. In: Delafresnaye JF (ed.), Brain Mechanisms and Learning. Oxford: Blackwell. Book chapter, no DOI; record not checked against a database. [META; design as reported in Page and Norris 2009 and Musfeld et al. 2023]
22. Henson RN. 1998. Item repetition in short-term memory: Ranschburg repeated. Journal of Experimental Psychology: Learning, Memory, and Cognition 24(5):1162-1181. DOI 10.1037/0278-7393.24.5.1162. PMID 9747528. [ABS]
23. Hitch GJ, Fastame MC, Flude B. 2005. How is the serial order of a verbal sequence coded? Some comparisons between models. Memory 13(3-4):247-258. DOI 10.1080/09658210344000314. [META; finding as reported in Musfeld and Oberauer 2026]
24. Humes LE, Floyd SS. 2005. Measures of working memory, sequence learning, and speech recognition in the elderly. Journal of Speech, Language, and Hearing Research 48(1):224-235. DOI 10.1044/1092-4388(2005/016). PMID 15938066. [ABS]
25. Hurlstone MJ, Hitch GJ, Baddeley AD. 2014. Memory for serial order across domains: an overview of the literature and directions for future research. Psychological Bulletin 140(2):339-373. DOI 10.1037/a0034221. PMID 24079725. [ABS]
26. Hurlstone MJ, Hitch GJ. 2015. How is the serial order of a spatial sequence represented? Insights from transposition latencies. Journal of Experimental Psychology: Learning, Memory, and Cognition 41(2):295-324. DOI 10.1037/a0038223. PMID 25436478. [ABS]
27. Karpicke JD, Pisoni DB. 2004. Using immediate memory span to measure implicit learning. Memory and Cognition 32(6):956-964. DOI 10.3758/BF03196873. PMID 15673183. PMC3429116. [FT: author manuscript; Method, Results, Table 1]
28. Kessels RPC, van Zandvoort MJE, Postma A, Kappelle LJ, de Haan EHF. 2000. The Corsi Block-Tapping Task: standardization and normative data. Applied Neuropsychology 7(4):252-258. DOI 10.1207/S15324826AN0704_8. PMID 11296689. [ABS; the 6.2 (SD 1.3) as quoted in Zhao et al. 2026]
29. Kessels RPC, van den Berg E, Ruis C, Brands AMA. 2008. The backward span of the Corsi Block-Tapping Task and its association with the WAIS-III Digit Span. Assessment 15(4):426-434. DOI 10.1177/1073191108315611. PMID 18483192. [ABS]
30. Kettlety SA, Kibler GL, Hooyman A, Holl CK, Schaefer SY, Leech KA. 2025. Twenty minutes of Corsi block tapping task training does not improve mental rotation in adults with stroke. Frontiers in Neurology 16:1601454. DOI 10.3389/fneur.2025.1601454. PMID 41180521. PMC12571597. [FT: Methods, Results]
31. Levitt H. 1971. Transformed up-down methods in psychoacoustics. Journal of the Acoustical Society of America 49(2B):467-477. DOI 10.1121/1.1912375. [META; staircase logic used for the arithmetic in Q7]
32. Malykh SB, Kuzmina YV. 2025. Age-related and sex differences in visuospatial working memory and its association with math achievement: insights from span, accuracy, and RT in Corsi Block Tapping Test. Psychology in Russia: State of the Art 18(2):77-96. DOI 10.11621/pir.2025.0205. PMID 40896534. PMC12398182. [FT: Methods]
33. Mason K, Bowmer A, Welch GF. 2021. How does task presentation impact motor inhibition performance in young children? Frontiers in Psychology 12:684444. DOI 10.3389/fpsyg.2021.684444. PMID 34408706. PMC8366059. [ABS]
34. Mathy F, Feldman J. 2012. What's magic about magic numbers? Chunking and data compression in short-term memory. Cognition 122(3):346-362. DOI 10.1016/j.cognition.2011.11.003. PMID 22176752. [ABS]
35. Mathy F, Fartoukh M, Gauvrit N, Guida A. 2016. Developmental abilities to form chunks in immediate memory and its non-relationship to span development. Frontiers in Psychology 7:201. DOI 10.3389/fpsyg.2016.00201. PMID 26941675. PMC4763062. [FT: Introduction, Design, Results, Discussion]
36. Melby-Lervåg M, Redick TS, Hulme C. 2016. Working memory training does not improve performance on measures of intelligence or other measures of "far transfer": evidence from a meta-analytic review. Perspectives on Psychological Science 11(4):512-534. DOI 10.1177/1745691616635612. PMID 27474138. PMC4968033. [ABS]
37. Melton AW. 1963. Implications of short-term memory for a general theory of memory. Journal of Verbal Learning and Verbal Behavior 2(1):1-21. DOI 10.1016/S0022-5371(63)80063-8. [META; finding as reported in Page and Norris 2009]
38. Milton Bradley. 1978. SIMON instructions. Hasbro document archive (PDF). No DOI. [FT: General description, Game 1, Game 2]
39. Monaco M, Costa A, Caltagirone C, Carlesimo GA. 2013. Forward and backward span for verbal and visuo-spatial data: standardization and normative data from an Italian adult population. Neurological Sciences 34(5):749-754. DOI 10.1007/s10072-012-1130-x. PMID 22689311. [META; value as reported in Woods et al. 2015]
40. Mukunda K, Nabizadeh D, Zhang J, Yang Y, De Lillo C, Arshad Q, Tevzadze N, Kheradmand A. 2026. Component-based analysis of visuospatial memory using the Corsi task. European Journal of Neuroscience 64(1):e70625. DOI 10.1111/ejn.70625. PMID 42437680. PMC13356980. [ABS]
41. Musfeld P, Souza AS, Oberauer K. 2023. Repetition learning is neither a continuous nor an implicit process. Proceedings of the National Academy of Sciences 120(16):e2218042120. DOI 10.1073/pnas.2218042120. PMID 37040406. PMC10119999. [FT: Introduction, Results, Methods]
42. Musfeld P, Oberauer K. 2026. Revisiting Hebb: the mechanisms of repetition learning. Perspectives on Psychological Science 21(3):229-250. DOI 10.1177/17456916251408052. PMID 41615421. PMC13095083. [FT: sections on chunk formation, awareness and spacing]
43. Page MPA, Norris D. 2009. A model linking immediate serial recall, the Hebb repetition effect and the learning of phonological word forms. Philosophical Transactions of the Royal Society B 364(1536):3737-3753. DOI 10.1098/rstb.2009.0173. PMID 19933143. PMC2846317. [FT: section on the Hebb effect and spacing]
44. Parisi A, Bellinzona F, Di Lernia D, Repetto C, De Gaspari S, Brizzi G, Riva G, Tuena C. 2022. Efficacy of multisensory technology in post-stroke cognitive rehabilitation: a systematic review. Journal of Clinical Medicine 11(21):6324. DOI 10.3390/jcm11216324. PMID 36362551. PMC9656411. [ABS]
45. Quak M, London RE, Talsma D. 2015. A multisensory perspective of working memory. Frontiers in Human Neuroscience 9:197. DOI 10.3389/fnhum.2015.00197. PMID 25954176. PMC4404829. [ABS]
46. Remouchamps R, Majerus S, Kowialiewski B. 2026. Ranschburg unrepeated. Journal of Experimental Psychology: Learning, Memory, and Cognition, online ahead of print. DOI 10.1037/xlm0001638. PMID 42406490. [ABS]
47. Roe D, Miles C, Johnson AJ. 2017. Tactile Ranschburg effects: facilitation and inhibitory repetition effects analogous to verbal memory. Memory 25(6):793-799. DOI 10.1080/09658211.2016.1222443. PMID 27556958. [ABS]
48. Sánchez-Benavides G, Peña-Casanova J, Casals-Coll M, Gramunt N, Manero RM, Puig-Pijoan A, et al. 2016. One-year reference norms of cognitive change in Spanish old adults: data from the NEURONORMA sample. Archives of Clinical Neuropsychology 31(4):378-388. DOI 10.1093/arclin/acw018. PMID 27193368. [META; the one-year Corsi retest of 0.50 as tabulated in Bergman et al. 2025, Table 4]
49. Schaefer SY, Hooyman A, Haikalis NK, Essikpe R, Lohse KR, Duff K, Wang P. 2022. Efficacy of Corsi Block Tapping Task training for improving visuospatial skills: a non-randomized two-group study. Experimental Brain Research 240(11):3023-3032. DOI 10.1007/s00221-022-06478-5. PMID 36227343. PMC9558013. [FT: Methods, Results, Figure 3 legend]
50. Schwartz M, Bryden MP. 1971. Coding factors in the learning of repeated digit sequences. Journal of Experimental Psychology 87(3):331-334. DOI 10.1037/h0030552. [META; finding as reported in Musfeld and Oberauer 2026]
51. Schwartze M, Brown RM, Biau E, Kotz SA. 2020. Timing the "magical number seven": presentation rate and regularity affect verbal working memory performance. International Journal of Psychology 55(3):342-346. DOI 10.1002/ijop.12588. PMID 31062352. PMC7317781. [FT: Method, Results]
52. Shams L, Seitz AR. 2008. Benefits of multisensory learning. Trends in Cognitive Sciences 12(11):411-417. DOI 10.1016/j.tics.2008.07.006. PMID 18805039. [META]
53. Siegert RJ, Weatherall M, Taylor KD, Abernethy DA. 2008. A meta-analysis of performance on simple span and more complex working memory tasks in Parkinson's disease. Neuropsychology 22(4):450-461. DOI 10.1037/0894-4105.22.4.450. PMID 18590357. [ABS]
54. Smyth MM, Pendleton LR. 1990. Space and movement in working memory. Quarterly Journal of Experimental Psychology A 42(2):291-304. DOI 10.1080/14640749008401223. PMID 2367683. [ABS]
55. Smyth MM, Scholey KA. 1994. Characteristics of spatial memory span: is there an analogy to the word length effect, based on movement time? Quarterly Journal of Experimental Psychology A 47(1):91-117. DOI 10.1080/14640749408401145. PMID 8177964. [ABS]
56. Sternberg S, Monsell S, Knoll RL, Wright CE. 1978. The latency and duration of rapid movement sequences: comparisons of speech and typewriting. In: Stelmach GE (ed.), Information Processing in Motor Control and Learning, 117-152. DOI 10.1016/B978-0-12-665960-3.50011-6. [META]
57. Sukegawa M, Ueda Y, Saito S. 2019. The effects of Hebb repetition learning and temporal grouping in immediate serial recall of spatial location. Memory and Cognition 47(4):643-657. DOI 10.3758/s13421-019-00921-9. PMID 30903464. [ABS]
58. Tremblay S, Saint-Aubin J. 2009. Evidence of anticipatory eye movements in the spatial Hebb repetition effect: insights for modeling sequence learning. Journal of Experimental Psychology: Learning, Memory, and Cognition 35(5):1256-1265. DOI 10.1037/a0016566. PMID 19686019. [ABS]
59. Turcotte J, Gagnon S, Poirier M. 2005. The effect of old age on the learning of supraspan sequences. Psychology and Aging 20(2):251-260. DOI 10.1037/0882-7974.20.2.251. PMID 16029089. [ABS]
60. Ueda Y, Huang TR, Shen Z, Sakata C, Yeh SL, Saito S. 2023. Sequential processing facilitates Hebb repetition learning in visuospatial domains. Journal of Experimental Psychology: General 152(9):2559-2577. DOI 10.1037/xge0001406. PMID 37307338. [ABS]
61. van Asselen M, Kessels RPC, Neggers SFW, Kappelle LJ, Frijns CJM, Postma A. 2006. Brain areas involved in spatial working memory. Neuropsychologia 44(7):1185-1194. DOI 10.1016/j.neuropsychologia.2005.10.005. PMID 16300806. [ABS]
62. Woods DL, Kishiyama MM, Yund EW, Herron TJ, Edwards B, Poliva O, Hink RF, Reed B. 2011. Improving digit span assessment of short-term verbal memory. Journal of Clinical and Experimental Neuropsychology 33(1):101-111. DOI 10.1080/13803395.2010.493149. PMID 20680884. PMC2978794. [FT: PMC author manuscript; Method, scoring metrics, Table 2, Table 3, learning effects]
63. Woods DL, Wyma JM, Herron TJ, Yund EW. 2015. The effects of repeat testing, malingering, and traumatic brain injury on computerized measures of visuospatial memory span. Frontiers in Human Neuroscience 9:690 (published online January 2016). DOI 10.3389/fnhum.2015.00690. PMID 26779001. PMC4700270. [FT: Methods, Scoring metrics, Table 2, Test-retest reliability, Learning effects, Discussion]
64. Woods DL, Wyma JM, Herron TJ, Yund EW. 2016. An improved spatial span test of visuospatial memory. Memory 24(8):1142-1155. DOI 10.1080/09658211.2015.1076849. PMID 26357906. [ABS]
65. Yeganeh N, Makarov I, Unnthorsson R, Kristjánsson Á. 2026. Assessing spatial and spatiotemporal tactile working memory using adaptive staircase procedures. Sensors 26(8):2361. DOI 10.3390/s26082361. [META; Crossref record]
66. Zhao Z, Joessel F, Green CS, Jaeggi SM, Seitz AR. 2026. Perceptual contaminants to assessments of visuospatial working memory: the influences of path clutterness and endpoint crowding. Journal of Cognition 9(1):44. DOI 10.5334/joc.517. PMID 42666959. PMC13523809. [FT: Introduction, Methods]

Counts: 66 sources; 20 FT, 34 ABS, 12 META. Of the 54 sources whose own text supplied a number or finding (FT plus ABS), 20 are FT. Of the 30 load-bearing sources (those whose numbers or findings drive a verdict, a recommendation or a thesis value), 19 are FT: Arce, Bergman, Bo and Seidler, Brunetti, Cleary, Conway, Facchin, Karpicke and Pisoni, Kettlety, Mathy 2016, the Milton Bradley manual, Musfeld 2023, Musfeld and Oberauer 2026, Page and Norris, Schaefer, Schwartze, Woods 2011, Woods 2015 and Zhao; the 11 at ABS are Woods 2016, Fischer 2001, Ginsberg 2017, Kessels 2000, Gonthier 2023, Farrell Pagulayan 2006, Mason 2021, Parisi 2022, Turcotte 2005, Siegert 2008 and Remouchamps 2026. Every number that carries a recommendation or a thesis value comes from an FT source, from simulation or from the code, except the 30 percent per item slope (Woods et al. 2016 [ABS]), the Corsi 6.2 (Kessels via an FT secondary) and the toy's figure of about seven (Gendle and Ransom via an FT secondary). Every META source whose content is used above was read through a named FT secondary source; the rest are method references (Levitt) or the primaries behind the code's own citations.

Not re-read here and left as the code and design cite them: Corsi 1972, Milner 1971, Chekaf et al. 2015 (conference paper), McGraw and Wong 1996 (the ICC forms the notebook uses), Oberauer et al. 2018, Kane et al. 2007, Jaeggi et al. 2010, Roe et al. 2024, the Precision Microdrives 310-103 datasheet, and Johansson 2012 (not identified).

### Simulation assumptions (for Sections 1.5, 2, 4 and 6)

- Each attempt at length L succeeds with p = 1 / (1 + exp(k (L - mu))); attempts independent given L; the prefix effect is folded into mu, the person's 50 percent point under the Simon rule. Base slope k = 1.2 per item (Woods et al. 2016 [ABS]: accuracy fell about 30 percent per item near the mean span, and k/4 = 0.3), with 0.8, 1.5 and 1.8 as sensitivities; k = 1.5 reproduces the docstring's toy numbers exactly.
- Between-person SD of mu 1.0 item (0.8 as sensitivity), cohort centres 6 to 8.5; one life; cap 10; replay success evaluated at L minus a boost of 0, 0.5 or 1 item; game 2 shift 0 or +0.3; pass-to-pass state noise SD 0.25 items for the ICC runs.
- Failure position: on the newest item with probability 0.6, otherwise uniform over earlier positions; for the edit score, the wrong lane occurs later in the sequence with probability 0.9.
- E1 is decided exactly as `_mean_check` does it: median of best-of-two, 4000-draw percentile bootstrap, band 5 to 9, "direction only" when the point is inside and the interval is not.
- E2p is decided as the cohort table does it: per participant, the newest-item share of misses minus the mean of 1/L over both games, then a one-sided Wilcoxon signed-rank test above zero with a positive mean; failures fall on the newest item with probability 0.6, 0.4 or 0.3, or at a uniform position.
- 20,000 simulated people or games per cell, 2000 cohorts of 10 for the small-sample runs; ICC(2,1) by the absolute-agreement single-measure formula. Material statistics come from 100,000 sequences of the shipped generator (length 8, four lanes, no immediate repeats).
- Section 1.7 is a reproduction through the real `EchoMode` with the battery settings, not a simulation.
