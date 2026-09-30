# Seven modes: review of 30 September 2026

Echo, Buzz Hunt, Mirror, Rhythm, Chords, Muscle Memory (`pattern` in the code) and Adaptive, read against their literature and the pilot data before any participant. Force Pilot has its own notes: [force-pilot-parkinsons.md](force-pilot-parkinsons.md) and the review of the same day, [force-pilot-pd-review.md](force-pilot-pd-review.md).

What was read: every mode file named above, the controller in `analytics/adaptive.py`, the chart builder in `audio/beatmap.py`, the press path in `hardware/`, the matching blocks of `config/default.yaml`, the study design ([healthy_baseline_study.txt](../healthy_baseline_study.txt)) and the notebook's per-mode functions, literature rows and claim limits.

How sources were checked: each one by DOI, PMID or title on Europe PMC or Crossref, tagged FT (full text read), ABS (abstract read) or META (bibliographic record only). A number appears only where it was read, or is marked arithmetic or pilot. The pilot blocks come from one to four codes per mode, mostly the development team, and several ran under settings the study no longer uses: they check the device and the software, not people.

## What changed

All of it before any participant. No registered row changed; every new row is a sensitivity or exploratory row.

- Presses on the board's own clock. The pads give a reading about every 5 ms, but the USB adapter hands them over in bursts and each sample is stamped when its burst arrives. The notebook rebuilds each sample's grid time from the lower envelope of arrival time against sample count and re-times each press on the sample that carries its exact stamp (`sample_grid_lateness`, `press_timing`, `timing_floor_rows`).
- Chords: each pad's rest floor (`chord_rest_peaks`), ER with that floor taken off, a flag on chords whose leak sits at the floor, and spans on the board's clock.
- Rhythm: asynchrony on the board's clock, the correction gain, an outlier-resistant SD, and more second-go rows.
- Echo: partial credit, mean span, edit distance and the games stopped by the ceiling.
- Buzz Hunt: errors by finger distance (row B2d) and false alarms as counts.
- Adaptive: time in band, recovery entries, the first band entry after the climb and the window at the peak (`adaptive_controller_rows`).
- Reliability: every retest row says how many runs would reach an ICC of 0.8 (Spearman-Brown).
- Holm: W3 is P1 under its Table 2 id, so it takes P1's verdict and counts once; F1's p now enters the family.
- Text: the design, the notebook's literature rows and claim limits, the mode docstrings and the config comments, wherever a source was misread or a claim went past what the task can show (the per-mode notes below).
- Bench: `scripts/pad_bench.py` records every pad for each loaded pad, which gives the cross-talk matrix.
- Tests: `tests/test_modes_review_analysis.py`.

## Left open

For the author to decide. Both are protocol amendments, so nothing has been changed. If adopted, log the start date and apply them from that participant on.

- An awareness check for Muscle Memory at the debrief, before the hidden sequence is explained: one open question, a free generation of 12 presses and a recognition test of four 4-item fragments. About two minutes.
- An intake line on musical training and rhythm-game experience, as a covariate for Rhythm, Chords and Muscle Memory.

After collection only, since each would change the task mid-study:

- Research presets: an even click track for Rhythm at 500, 800 and 1200 ms, auditory, tactile and combined, with continuation taps; a tactile Buzz Hunt with masking noise, responses by the other hand, 20 percent catch trials and a span staircase; a Corsi-standard Echo with modality and backward conditions; a deadline staircase for Adaptive; a two-board Mirror with unimanual, bimanual and non-homologous trials; a Chords individuation ramp. The protocol runner has to learn to set `cue.*` per preset first.
- Game changes: presses timed on the sample clock or the firmware frame index, chart times aligned to the music's onsets, and stimulus stamps on the screen flip.
- Bench: an accelerometer on each pad while each motor runs, and a sound level per motor.

## Device facts under every timed measure

| Link | Size | How it is known |
|---|---|---|
| Sampling | A new reading about every 5 ms (199 Hz) | Pilot fit; Force Pilot review |
| USB bursts | Samples arrive in packets about every 20 ms, about 10 ms late on average | Pilot |
| Press stamping | 10 to 11 ms late on average on a bursting board (SD about 6 ms, maximum about 21 ms); about 1 ms on the one port that did not burst | Pilot, each press matched to the sample with its exact stamp |
| Detector | 7 to 11 ms after the raw crossing on average | Design Section 1.6 |
| Display | The next frame (0 to 16.7 ms) plus a panel lag nobody has measured | Config |
| Sound | Tone 77 ms, song 87 ms | Measured on the study laptop, 24 September 2026 |
| Motor | 74 ms from command to motion | Measured the same day |
| Stimulus stamp | At the update tick, not the flip: 0 to 16.7 ms early | `pattern.py` DEVIATIONS; the same in Adaptive, Mirror and Chords |
| Chart zero | On the music's attacks since 1 October 2026 (frozen study chart); a chart built from the audio sits 26 to 37 ms after them | `scripts/build_study_chart.py`; the Rhythm deep review |
| Chord spans | Steps of about 20 ms on a bursting board | Pilot block summaries |
| Two boards | About 7 ms mean absolute difference from their bursts alone | Arithmetic |

The pads: one count is 0.0195 N. Over a chord's 3.2 s window a resting finger's peak reaches a median of 2 counts (169 rest windows). Light chord presses were 42 to 86 counts (0.8 to 1.7 N), so noise alone gives an ER near 0.05. The motors leave no trace on the pads (six blocks).

## By mode

### Echo

- A Simon span (one trial per length, a spare life, the prefix shown again) is not a Corsi span. The only comparable figure is about 7 on the retail toy, from Gendle and Ransom 2006 read only through [E-L3]. The toy lets a colour repeat straight away and Echo does not.
- Each item is a light, a buzz and a lane tone, so a sequence is also a melody.
- Partial credit retested better than span on a digital Corsi, 0.68 against 0.58 at one month [E-L1], and edit distance scores as well or better [E-L4]. Both are now reported.
- E2p follows from the rule: the game grows only after the whole prefix came back right. Games at the 10-item ceiling are censored.
- Not to claim: Corsi norms, a visuospatial-only span, a real change between two games, or training and transfer [E-L10].

### Buzz Hunt

- Accuracy sits at ceiling at the fixed 150 ms pulse. Median localisation RT is the continuous measure (pilot: 13 trials, all correct, median 330 ms from command to press).
- A neighbour error has three causes here: a mislocalisation, a slip onto the next pad, and vibration reaching the next finger [B-L4, B-L5]. B2 stays as registered; errors by distance sit beside it against chance shares of 0.50, 0.33 and 0.17.
- Two catch trials give false-alarm counts of 0, 1 or 2, and a person's d′ is set by that count and its correction [B-L9]. d′ is pooled over the cohort only.
- B4 cannot fail from above: four trials from length 2 cap the span at 5. The verified anchor is ordered tactile recall of about 4 items [B-L7].
- The motors are audible and nothing masks them.
- Not to claim: acuity or a threshold, somatotopic misreferral from B2, a match to published tactile RTs, training for carpal tunnel or nerve repair [B-L12], or a finger agnosia test [B-L14].

### Mirror

- Not played: it needs a board on each hand.
- M1 now rests on discrete two-handed movements, which start and peak together [M-L1]. Kelso 1984 is continuous oscillation.
- No verified source says which hand leads in one simultaneous press, so M2 has no direction.
- Two boards stamp their presses independently, so gaps under about 10 ms are not resolved.
- The bilateral training evidence conflicts [M-L10] and is not claimed.

### Rhythm

- It is not the metronome task Rh1 comes from. The study track's notes fall 697 to 2926 ms apart (median 743 ms), the finger changes on every note, each note is in view about 2.2 s ahead, and four signals pace the press (falling note, tone, buzz, music). Tactile pacing removed the lead [Rh-L4], and from about 2.4 s between beats people react instead [Rh-L7].
- Tapping to music shows little or no lead (Repp 2005: the same adults led tones by 38 ms, music by +4 and -16 ms, Dalla Bella et al. 2024), so since 1 October 2026 Rh1 asks that presses anticipate the beat (under 10 percent later than +150 ms) and the mean is reported as an estimate. The study chart's notes sit on the music's attacks; a chart built from the audio sits 26 to 37 ms after them, which makes a music-follower's mean MORE negative. A bursting board stamps presses about 10 ms late.
- Rh2 passes any SD from 10 to 100 ms, so it is a feasibility check. Rh-wk's lag-1 is negative by construction (the residual is the first difference of the asynchronies), so it is reported, not tested. A positive lag-1 of the asynchronies fits partial correction and slow drift alike [Rh-L8].
- About one note in ten plays its tone 35 percent louder (`audio.loud_trial`, on in every mode).

### Chords

- At the study's light presses ER sits at the pads' rest floor: on the pilot, quiet-finger peaks had the same median (2 counts) as rest windows of the same length. C1 can pass with no enslaving at all, so it is a feasibility check, and ER with the floor taken off sits beside it.
- A chord-conditioned cell is not an upper bound on single-finger enslaving: enslaving is not additive [C-L1]. The singles matrix is the comparable one.
- Spans came in steps of about 20 ms (0, 21.8, 40.5, 60.6 ms and so on), not 5 ms.
- C6's cue grows with chord size (one to three motors, one tone), so its direction compares with [C-L10] and its size does not.
- C3 has no test, and the pads differ in resting load (index +2.5 to little +30.7 counts).

### Muscle Memory

- Kal's 69 ms is the unaffected hand after stroke [MM-L5], and Nissen and Bullemer's figures could not be read [MM-L11]. There is no healthy size to compare.
- The cue plays a lane tone with every key, so the trained sequence is a melody, and tones mapped to responses help serial learning [MM-L8]. Nothing checks awareness. The result is sequence-specific learning within the sitting.
- The SRTT gain can be gone minutes after training [MM-L4], so a second go is read both ways.
- Individual learning scores retest under 0.40 [MM-L1]: group level only.
- Pilot random-take RTs were 314 and 324 ms. The fast cue leaves less room for a rebound.

### Adaptive

- Pilot hands peaked at 90 to 144 BPM, none at the cap, and entered the band at trials 21 to 33 in four of five blocks. A healthy block tests band keeping as well as speed.
- The 65 to 80 percent band is a design choice: [A-L1] gives no number and [A-L2] derives about 85 percent for a class of learners.
- Three misses drop the pace by 25 BPM, so the final pace depends on where a crash lands. Read the peak.
- A deadline threshold cannot be recovered from 40 trials.
- Adaptive plays in pass 1, and twice in the 30 and 60 minute sittings.

## Reliability and the Holm family

- Every ICC here is within one sitting, so it is an upper bound on day-to-day reliability. At n = 10 the lower end of the interval for a true ICC of 0.75 is about 0.28 (design_check.md).
- Runs needed for 0.8 (arithmetic): Echo span 2.9 and partial credit 1.9 [E-L1]; a force individuation index 4.3 at 0.48 to 1.0 at 0.80 [C-L7]; the SRTT 10.3 at 0.28 [MM-L1].
- The family Holm corrects is P1, P3, C2, C6, W4, Rh1, B2 and F1, plus P2 for 60 minute sitters. With eight tests Holm's first threshold is 0.00625, which a one-sided exact signed-rank test reaches at n = 8 only when all eight go the same way (arithmetic).
- Rh2, B4, A5 and C1 are decided on an interval and cannot fail for a healthy hand here. They are reported as feasibility checks.

## Sources

Retrieved by DOI, PMID or title on Europe PMC or Crossref on 30 September 2026.

### Echo

- E-L1. Bergman I, Franke Föyen L, Gustavsson A, Van den Hurk W. Test-retest reliability, practice effects and estimates of change: a study on the Mindmore digital cognitive assessment tool. Scand J Psychol. 2025;66(1):1-14. DOI 10.1111/sjop.13054. PMID 39072723. PMC11735254. FT (Tables 3 and 4).
- E-L2. Kessels RP, van den Berg E, Ruis C, Brands AM. The backward span of the Corsi Block-Tapping Task and its association with the WAIS-III Digit Span. Assessment. 2008;15(4):426-434. DOI 10.1177/1073191108315611. PMID 18483192. ABS.
- E-L3. Mathy F, Fartoukh M, Gauvrit N, Guida A. Developmental abilities to form chunks in immediate memory and its non-relationship to span development. Front Psychol. 2016;7:201. DOI 10.3389/fpsyg.2016.00201. PMID 26941675. PMC4763062. FT (introduction, method, discussion).
- E-L4. Gonthier C. An easy way to improve scoring of memory span tasks: the edit distance, beyond "correct recall in the correct serial position". Behav Res Methods. 2023;55(4):2021-2036. DOI 10.3758/s13428-022-01908-2. PMID 35794418. ABS.
- E-L5. Woods DL, Kishiyama MM, Lund EW, Herron TJ, Edwards B, Poliva O, Hink RF, Reed B. Improving digit span assessment of short-term verbal memory. J Clin Exp Neuropsychol. 2011;33(1):101-111. DOI 10.1080/13803395.2010.493149. PMID 20680884. PMC2978794. ABS.
- E-L6. Musfeld P, Souza AS, Oberauer K. Repetition learning is neither a continuous nor an implicit process. Proc Natl Acad Sci U S A. 2023;120(16):e2218042120. DOI 10.1073/pnas.2218042120. PMID 37040406. PMC10119999. ABS.
- E-L7. Oberauer K, Lewandowsky S, Awh E, et al. Benchmarks for models of short-term and working memory. Psychol Bull. 2018;144(9):885-958. DOI 10.1037/bul0000153. PMID 30148379. ABS.
- E-L8. Roe D, Allen RJ, Elsley J, Miles C, Johnson AJ. Working memory prioritisation effects in tactile immediate serial recall. Q J Exp Psychol (Hove). 2024;77(11):2354-2363. DOI 10.1177/17470218241231283. PMID 38282209. PMC11529111. FT (introduction, method). Roe D, Miles C, Johnson AJ. Tactile Ranschburg effects: facilitation and inhibitory repetition effects analogous to verbal memory. Memory. 2017;25(6):793-799. DOI 10.1080/09658211.2016.1222443. PMID 27556958. ABS.
- E-L9. Kane MJ, Conway ARA, Miura TK, Colflesh GJH. Working memory, attention control, and the N-back task: a question of construct validity. J Exp Psychol Learn Mem Cogn. 2007;33(3):615-622. DOI 10.1037/0278-7393.33.3.615. PMID 17470009. ABS. Jaeggi SM, Buschkuehl M, Perrig WJ, Meier B. The concurrent validity of the N-back task as a working memory measure. Memory. 2010;18(4):394-412. DOI 10.1080/09658211003702171. PMID 20408039. ABS.
- E-L10. Melby-Lervåg M, Redick TS, Hulme C. Working memory training does not improve performance on measures of intelligence or other measures of "far transfer": evidence from a meta-analytic review. Perspect Psychol Sci. 2016;11(4):512-534. DOI 10.1177/1745691616635612. PMID 27474138. PMC4968033. ABS.

### Buzz Hunt

- B-L1. Schweizer R, Maier M, Braun C, Birbaumer N. Distribution of mislocalizations of tactile stimuli on the fingers of the human hand. Somatosens Mot Res. 2000;17(4):309-316. DOI 10.1080/08990220020002006. PMID 11125874. ABS.
- B-L2. Manser-Smith K, Tamè L, Longo MR. Tactile confusions of the fingers and toes. J Exp Psychol Hum Percept Perform. 2018;44(11):1727-1738. DOI 10.1037/xhp0000566. PMID 30091637. ABS.
- B-L3. Weber M, Marshall A, Timircan R, et al. Touch localization after nerve repair in the hand: insights from a new measurement tool. J Neurophysiol. 2023;130(5):1126-1141. DOI 10.1152/jn.00271.2023. PMID 37728568. PMC10994642. ABS.
- B-L4. Tamè L, Moles A, Holmes NP. Within, but not between hands interactions in vibrotactile detection thresholds reflect somatosensory receptive field organization. Front Psychol. 2014;5:174. DOI 10.3389/fpsyg.2014.00174. PMID 24592252. PMC3937991. ABS.
- B-L5. Manfredi LR, Baker AT, Elias DO, et al. The effect of surface wave propagation on neural responses to vibration in primate glabrous skin. PLoS One. 2012;7(2):e31203. DOI 10.1371/journal.pone.0031203. PMID 22348055. PMC3278420. ABS. Shao Y, Hayward V, Visell Y. Spatial patterns of cutaneous vibration during whole-hand haptic interactions. Proc Natl Acad Sci U S A. 2016;113(15):4188-4193. DOI 10.1073/pnas.1520866113. PMID 27035957. PMC4839404. ABS.
- B-L6. Bao T, Su L, Kinnaird C, Kabeto M, Shull PB, Sienko KH. Vibrotactile display design: quantifying the importance of age and various factors on reaction times. PLoS One. 2019;14(8):e0219737. DOI 10.1371/journal.pone.0219737. PMID 31398207. PMC6688825. FT (methods, Tables 1 and 2).
- B-L7. Yeganeh N, Makarov I, Unnthorsson R, Kristjánsson Á. Assessing spatial and spatiotemporal tactile working memory using adaptive staircase procedures. Sensors (Basel). 2026;26(8):2361. DOI 10.3390/s26082361. PMID 42076469. PMC13120339. ABS.
- B-L8. See E-L8.
- B-L9. Stanislaw H, Todorov N. Calculation of signal detection theory measures. Behav Res Methods Instrum Comput. 1999;31(1):137-149. DOI 10.3758/bf03207704. PMID 10495845. ABS. Hautus MJ. Corrections for extreme proportions and their biasing effects on estimated values of d′. Behav Res Methods Instrum Comput. 1995;27(1):46-51. DOI 10.3758/bf03203619. META.
- B-L10. Leonard JA. Tactual choice reactions: I. Q J Exp Psychol. 1959;11(2):76-83. DOI 10.1080/17470215908416294. META. ten Hoopen G, Akerboom S, Raaymakers E. Vibrotactual choice reaction time, tactile receptor systems and ideomotor compatibility. Acta Psychol (Amst). 1982;50(2):143-157. DOI 10.1016/0001-6918(82)90004-x. PMID 7102358. META.
- B-L11. Kaaresoja T, Linjama J. Perception of short tactile pulses generated by a vibration motor in a mobile phone. First Joint Eurohaptics Conference and Symposium on Haptic Interfaces for Virtual Environment and Teleoperator Systems (World Haptics 2005): 471-472. DOI 10.1109/WHC.2005.103. META.
- B-L12. Oud T, Beelen A, Eijffinger E, Nollet F. Sensory re-education after nerve injury of the upper limb: a systematic review. Clin Rehabil. 2007;21(6):483-494. DOI 10.1177/0269215507074395. PMID 17613580. ABS.
- B-L13. Tong J, Mao O, Goldreich D. Two-point orientation discrimination versus the traditional two-point test for tactile spatial acuity assessment. Front Hum Neurosci. 2013;7:579. DOI 10.3389/fnhum.2013.00579. PMID 24062677. PMC3772339. ABS.
- B-L14. Anema HA, Kessels RP, de Haan EH, Kappelle LJ, Leijten FS, van Zandvoort MJ, Dijkerman HC. Differences in finger localisation performance of patients with finger agnosia. Neuroreport. 2008;19(14):1429-1433. DOI 10.1097/WNR.0b013e32830e017b. PMID 18766025. ABS.

### Mirror

- M-L1. Kelso JAS, Southard DL, Goodman D. On the nature of human interlimb coordination. Science. 1979;203(4384):1029-1031. DOI 10.1126/science.424729. PMID 424729. ABS.
- M-L2. Kelso JA. Phase transitions and critical behavior in human bimanual coordination. Am J Physiol. 1984;246(6 Pt 2):R1000-R1004. DOI 10.1152/ajpregu.1984.246.6.R1000. PMID 6742155. ABS.
- M-L3. Swinnen SP. Intermanual coordination: from behavioural principles to neural-network interactions. Nat Rev Neurosci. 2002;3(5):348-359. DOI 10.1038/nrn807. PMID 11988774. ABS. Swinnen SP, Wenderoth N. Two hands, one brain: cognitive neuroscience of bimanual skill. Trends Cogn Sci. 2004;8(1):18-25. DOI 10.1016/j.tics.2003.10.017. PMID 14697399. ABS. Mechsner F, Kerzel D, Knoblich G, Prinz W. Perceptual basis of bimanual coordination. Nature. 2001;414(6859):69-73. DOI 10.1038/35102060. PMID 11689944. ABS.
- M-L4. Heuer H. Intermanual interactions during programming of finger movements: transient effects of "homologous coupling". In: Generation and Modulation of Action Patterns. Springer; 1986:87-101. DOI 10.1007/978-3-642-71476-4_8. META. Kennerley SW, Diedrichsen J, Hazeltine E, Semjen A, Ivry RB. Callosotomy patients exhibit temporal uncoupling during continuous bimanual movements. Nat Neurosci. 2002;5(4):376-381. DOI 10.1038/nn822. META.
- M-L5. Armatas CA, Summers JJ, Bradshaw JL. Mirror movements in normal adult subjects. J Clin Exp Neuropsychol. 1994;16(3):405-413. DOI 10.1080/01688639408402651. PMID 7929708. ABS.
- M-L6. Koerte I, Eftimov L, Laubender RP, et al. Mirror movements in healthy humans across the lifespan: effects of development and ageing. Dev Med Child Neurol. 2010;52(12):1106-1112. DOI 10.1111/j.1469-8749.2010.03766.x. PMID 21039436. ABS.
- M-L7. Jaspers E, Klingels K, Simon-Martinez C, Feys H, Woolley DG, Wenderoth N. GriFT: a device for quantifying physiological and pathological mirror movements in children. IEEE Trans Biomed Eng. 2018;65(4):857-865. DOI 10.1109/TBME.2017.2723801. PMID 28692958. ABS. (`paediatric-cognitive.md` could not confirm the authors; they are confirmed here.)
- M-L8. Cincotta M, Ziemann U. Neurophysiology of unimanual motor control and mirror movements. Clin Neurophysiol. 2008;119(4):744-762. DOI 10.1016/j.clinph.2007.11.047. PMID 18187362. ABS. Addamo PK, Farrow M, Hoy KE, Bradshaw JL, Georgiou-Karistianis N. The effects of age and attention on motor overflow production: a review. Brain Res Rev. 2007;54(1):189-204. DOI 10.1016/j.brainresrev.2007.01.004. PMID 17300842. ABS.
- M-L9. Li S, Danion F, Latash ML, Li ZM, Zatsiorsky VM. Bilateral deficit and symmetry in finger force production during two-hand multifinger tasks. Exp Brain Res. 2001;141(4):530-540. DOI 10.1007/s002210100893. PMID 11810146. ABS.
- M-L10. Cauraugh JH, Lodha N, Naik SK, Summers JJ. Bilateral movement training and stroke motor recovery progress: a structured review and meta-analysis. Hum Mov Sci. 2010;29(5):853-870. DOI 10.1016/j.humov.2009.09.004. PMID 19926154. PMC2889142. ABS. van Delden AE, Peper CE, Beek PJ, Kwakkel G. Unilateral versus bilateral upper limb exercise therapy after stroke: a systematic review. J Rehabil Med. 2012;44(2):106-117. DOI 10.2340/16501977-0928. PMID 22266762. ABS. Pollock A, Morris J, van Wijck F, Coupar F, Langhorne P. Response to Cauraugh et al., Bilateral movement training and stroke motor recovery progress. Hum Mov Sci. 2011;30(1):143-146. DOI 10.1016/j.humov.2010.10.003. PMID 21185099. META.

### Rhythm

- Rh-L1. Repp BH. Sensorimotor synchronization: a review of the tapping literature. Psychon Bull Rev. 2005;12(6):969-992. DOI 10.3758/bf03206433. PMID 16615317. ABS. Repp BH, Su YH. Sensorimotor synchronization: a review of recent research (2006-2012). Psychon Bull Rev. 2013;20(3):403-452. DOI 10.3758/s13423-012-0371-2. PMID 23397235. ABS.
- Rh-L2. Aschersleben G, Prinz W. Synchronizing actions with events: the role of sensory information. Percept Psychophys. 1995;57(3):305-317. DOI 10.3758/bf03213056. PMID 7770322. ABS. Aschersleben G. Temporal control of movements in sensorimotor synchronization. Brain Cogn. 2002;48(1):66-79. DOI 10.1006/brcg.2001.1304. PMID 11812033. ABS.
- Rh-L3. Aschersleben G, Gehrke J, Prinz W. Tapping with peripheral nerve block: a role for tactile feedback in the timing of movements. Exp Brain Res. 2001;136(3):331-339. DOI 10.1007/s002210000562. PMID 11243475. ABS.
- Rh-L4. Müller K, Aschersleben G, Schmitz F, Schnitzler A, Freund HJ, Prinz W. Inter- versus intramodal integration in sensorimotor synchronization: a combined behavioral and magnetoencephalographic study. Exp Brain Res. 2008;185(2):309-318. DOI 10.1007/s00221-007-1155-1. PMID 17932661. PMC2755785. ABS.
- Rh-L5. Elliott MT, Wing AM, Welchman AE. Multisensory cues improve sensorimotor synchronisation. Eur J Neurosci. 2010;31(10):1828-1835. DOI 10.1111/j.1460-9568.2010.07205.x. PMID 20584187. ABS. Ammirante P, Patel AD, Russo FA. Synchronizing to auditory and tactile metronomes: a test of the auditory-motor enhancement hypothesis. Psychon Bull Rev. 2016;23(6):1882-1890. DOI 10.3758/s13423-016-1067-9. PMID 27246088. ABS.
- Rh-L6. Hove MJ, Iversen JR, Zhang A, Repp BH. Synchronization with competing visual and auditory rhythms: bouncing ball meets metronome. Psychol Res. 2013;77(4):388-398. DOI 10.1007/s00426-012-0441-0. PMID 22638726. ABS. Iversen JR, Patel AD, Nicodemus B, Emmorey K. Synchronization to auditory and visual rhythms in hearing and deaf individuals. Cognition. 2015;134:232-244. DOI 10.1016/j.cognition.2014.10.018. PMID 25460395. PMC4255154. ABS.
- Rh-L7. Mates J, Müller U, Radil T, Pöppel E. Temporal integration in sensorimotor synchronization. J Cogn Neurosci. 1994;6(4):332-340. DOI 10.1162/jocn.1994.6.4.332. PMID 23961729. ABS.
- Rh-L8. Semjen A, Schulze HH, Vorberg D. Timing precision in continuation and synchronization tapping. Psychol Res. 2000;63(2):137-147. DOI 10.1007/PL00008172. PMID 10946587. ABS. Wing AM, Kristofferson AB. Response delays and the timing of discrete motor responses. Percept Psychophys. 1973;14(1):5-12. DOI 10.3758/BF03198607. META. Vorberg D, Wing A. Modeling variability and dependence in timing. In: Handbook of Perception and Action, vol 2. Academic Press; 1996:181-262. DOI 10.1016/S1874-5822(06)80007-1. META.
- Rh-L9. Bégel V, Verga L, Benoit CE, Kotz SA, Dalla Bella S. Test-retest reliability of the Battery for the Assessment of Auditory Sensorimotor and Timing Abilities (BAASTA). Ann Phys Rehabil Med. 2018;61(6):395-400. DOI 10.1016/j.rehab.2018.04.001. PMID 29709607. ABS. Dalla Bella S, Farrugia N, Benoit CE, et al. BAASTA: Battery for the Assessment of Auditory Sensorimotor and Timing Abilities. Behav Res Methods. 2017;49(3):1128-1145. DOI 10.3758/s13428-016-0773-6. PMID 27443353. ABS. Dalla Bella S, et al. Mobile version of the Battery for the Assessment of Auditory Sensorimotor and Timing Abilities (BAASTA): implementation and adult norms. Behav Res Methods. 2024;56(4):3737-3756. DOI 10.3758/s13428-024-02363-x. PMID 38459221. ABS.
- Rh-L10. Bégel V, Di Loreto I, Seilles A, Dalla Bella S. Music games: potential application and considerations for rhythmic training. Front Hum Neurosci. 2017;11:273. DOI 10.3389/fnhum.2017.00273. PMID 28611610. PMC5447290. ABS.
- Rh-L11. Meek AW, Greenwell DR, Nishio H, Poston B, Riley ZA. Anodal M1 tDCS enhances online learning of rhythmic timing videogame skill. PLoS One. 2024;19(6):e0295373. DOI 10.1371/journal.pone.0295373. PMID 38870202. PMC11175489. FT (methods, results).
- Rh-L12. Taheri H, Rowe JB, Gardner D, et al. Design and preliminary evaluation of the FINGER rehabilitation robot: controlling challenge and quantifying finger individuation during musical computer game play. J Neuroeng Rehabil. 2014;11:10. DOI 10.1186/1743-0003-11-10. PMID 24495432. PMC3928667. FT (methods).
- Rh-L13. Ellis DPW. Beat tracking by dynamic programming. J New Music Res. 2007;36(1):51-60. DOI 10.1080/09298210701653344. META. McFee B, Raffel C, Liang D, Ellis DPW, et al. librosa: audio and music signal analysis in Python. Proceedings of the 14th Python in Science Conference. 2015:18-24. DOI 10.25080/Majora-7b98e3ed-003. META.

### Chords

- C-L1. Zatsiorsky VM, Li ZM, Latash ML. Enslaving effects in multi-finger force production. Exp Brain Res. 2000;131(2):187-195. DOI 10.1007/s002219900261. PMID 10766271. ABS.
- C-L2. Li ZM, Latash ML, Zatsiorsky VM. Force sharing among fingers as a model of the redundancy problem. Exp Brain Res. 1998;119(3):276-286. DOI 10.1007/s002210050343. PMID 9551828. ABS.
- C-L3. Häger-Ross C, Schieber MH. Quantifying the independence of human finger movements: comparisons of digits, hands, and movement frequencies. J Neurosci. 2000;20(22):8542-8550. DOI 10.1523/JNEUROSCI.20-22-08542.2000. PMID 11069962. PMC6773164. ABS.
- C-L4. Lang CE, Schieber MH. Human finger independence: limitations due to passive mechanical coupling versus active neuromuscular control. J Neurophysiol. 2004;92(5):2802-2810. DOI 10.1152/jn.00480.2004. PMID 15212429. ABS.
- C-L5. Kilbreath SL, Gandevia SC. Limited independent flexion of the thumb and fingers in human subjects. J Physiol. 1994;479(Pt 3):487-497. DOI 10.1113/jphysiol.1994.sp020312. PMID 7837104. ABS. van Duinen H, Gandevia SC. Constraints for control of the human hand. J Physiol. 2011;589(Pt 23):5583-5593. DOI 10.1113/jphysiol.2011.217810. PMID 21986205. ABS.
- C-L6. Xu J, Ejaz N, Hertler B, et al. Separable systems for recovery of finger strength and control after stroke. J Neurophysiol. 2017;118(2):1151-1163. DOI 10.1152/jn.00123.2017. PMID 28566461. PMC5547267. ABS. Ejaz N, Hamada M, Diedrichsen J. Hand use predicts the structure of representations in sensorimotor cortex. Nat Neurosci. 2015;18(7):1034-1040. DOI 10.1038/nn.4038. PMID 26030847. ABS. Xu J, Mawase F, Schieber MH. Evolution, biomechanics, and neurobiology converge to explain selective finger motor control. Physiol Rev. 2024;104(3):983-1020. DOI 10.1152/physrev.00030.2023. PMID 38385888. PMC11380997. ABS.
- C-L7. Knill AS, Shi S, Easthope CA, Branscheidt M, Lambercy O. Development and evaluation of a device to assess finger individuation in neurorehabilitation. IEEE Int Conf Rehabil Robot. 2025;2025:450-455. DOI 10.1109/ICORR66766.2025.11063048. PMID 40644104. ABS.
- C-L8. Shinohara M, Li S, Kang N, Zatsiorsky VM, Latash ML. Effects of age and gender on finger coordination in MVC and submaximal force-matching tasks. J Appl Physiol. 2003;94(1):259-270. DOI 10.1152/japplphysiol.00643.2002. PMID 12391031. ABS. Kim SW, Shim JK, Zatsiorsky VM, Latash ML. Finger inter-dependence: linking the kinetic and kinematic variables. Hum Mov Sci. 2008;27(3):408-422. DOI 10.1016/j.humov.2007.08.005. PMID 18255182. PMC2481561. ABS.
- C-L9. Abolins V, Stremoukhov A, Walter C, Latash ML. On the origin of finger enslaving: control with referent coordinates and effects of visual feedback. J Neurophysiol. 2020;124(6):1625-1636. DOI 10.1152/jn.00322.2020. PMID 32997555. PMC7814910. ABS.
- C-L10. Verwey WB. Chord skill: learning optimized hand postures and bimanual coordination. Exp Brain Res. 2023;241(6):1643-1659. DOI 10.1007/s00221-023-06629-2. PMID 37179513. PMC10224868. FT (methods, results).
- C-L11. Waters-Metenier S, Husain M, Wiestler T, Diedrichsen J. Bihemispheric transcranial direct current stimulation enhances effector-independent representations of motor synergy and sequence learning. J Neurosci. 2014;34(3):1037-1050. DOI 10.1523/JNEUROSCI.2282-13.2014. PMID 24431461. PMC3891947. ABS.
- C-L12. Jurinić A, Pranjić M, Huang A, Burkhart TA, Tan D, Namburi P. The biomechanics of piano playing: a systematic review of kinematic, kinetic, and electromyographic literature. Front Psychol. 2025;16:1690422. DOI 10.3389/fpsyg.2025.1690422. PMID 41561601. PMC12812707. ABS.

### Muscle Memory

- MM-L1. Oliveira CM, Hayiou-Thomas ME, Henderson LM. The reliability of the serial reaction time task: meta-analysis of test-retest correlations. R Soc Open Sci. 2023;10(7):221542. DOI 10.1098/rsos.221542. PMID 37476512. PMC10354485. ABS.
- MM-L2. Stark-Inbar A, Raza M, Taylor JA, Ivry RB. Individual differences in implicit motor learning: task specificity in sensorimotor adaptation and sequence learning. J Neurophysiol. 2017;117(1):412-428. DOI 10.1152/jn.01141.2015. PMID 27832611. PMC5253399. ABS.
- MM-L3. Hedge C, Powell G, Sumner P. The reliability paradox (full title shortened here). Behav Res Methods. 2018;50(3):1166-1186. DOI 10.3758/s13428-017-0935-1. PMID 28726177. PMC5990556. ABS.
- MM-L4. Trofimova O, Mottaz A, Allaman L, Chauvigné LAS, Guggisberg AG. The "implicit" serial reaction time task induces rapid and temporary adaptation rather than implicit motor learning. Neurobiol Learn Mem. 2020;175:107297. DOI 10.1016/j.nlm.2020.107297. PMID 32822865. ABS.
- MM-L5. Kal E, Winters M, van der Kamp J, et al. Is implicit motor learning preserved after stroke? A systematic review with meta-analysis. PLoS One. 2016;11(12):e0166376. DOI 10.1371/journal.pone.0166376. PMID 27992442. PMC5161313. ABS.
- MM-L6. Schwarb H, Schumacher EH. Generalized lessons about sequence learning from the study of the serial reaction time task. Adv Cogn Psychol. 2012;8(2):165-178. DOI 10.2478/v10053-008-0113-1. PMID 22723815. PMC3376886. ABS. Robertson EM. The serial reaction time task: implicit motor skill learning? J Neurosci. 2007;27(38):10073-10075. DOI 10.1523/JNEUROSCI.2747-07.2007. PMID 17881512. META.
- MM-L7. Destrebecqz A, Cleeremans A. Can sequence learning be implicit? New evidence with the process dissociation procedure. Psychon Bull Rev. 2001;8(2):343-350. DOI 10.3758/bf03196171. PMID 11495124. ABS. Vadillo MA, Konstantinidis E, Shanks DR. Underpowered samples, false negatives, and unconscious learning. Psychon Bull Rev. 2016;23(1):87-102. DOI 10.3758/s13423-015-0892-6. PMID 26122896. PMC4742512. ABS.
- MM-L8. Hoffmann J, Sebald A, Stöcker C. Irrelevant response effects improve serial learning in serial reaction time tasks. J Exp Psychol Learn Mem Cogn. 2001;27(2):470-482. DOI 10.1037/0278-7393.27.2.470. PMID 11294444. ABS.
- MM-L9. Abrahamse EL, Ruitenberg MF, de Kleine E, Verwey WB. Control of automated behavior: insights from the discrete sequence production task. Front Hum Neurosci. 2013;7:82. DOI 10.3389/fnhum.2013.00082. PMID 23515430. PMC3601300. ABS. Wymbs NF, Bassett DS, Mucha PJ, Porter MA, Grafton ST. Differential recruitment of the sensorimotor putamen and frontoparietal cortex during motor chunking in humans. Neuron. 2012;74(5):936-946. DOI 10.1016/j.neuron.2012.03.038. PMID 22681696. PMC3372854. ABS.
- MM-L10. Bönstrup M, Iturrate I, Thompson R, Cruciani G, Censor N, Cohen LG. A rapid form of offline consolidation in skill learning. Curr Biol. 2019;29(8):1346-1351. DOI 10.1016/j.cub.2019.02.049. PMID 30930043. PMC6482074. ABS. Gupta MW, Rickard TC. Dissipation of reactive inhibition is sufficient to explain post-rest improvements in motor sequence learning. NPJ Sci Learn. 2022;7(1):25. DOI 10.1038/s41539-022-00140-z. PMID 36202812. PMC9537514. ABS. Kantak SS, Winstein CJ. Learning-performance distinction and memory processes for motor skills: a focused review and perspective. Behav Brain Res. 2012;228(1):219-231. DOI 10.1016/j.bbr.2011.11.028. PMID 22142953. ABS.
- MM-L11. Nissen MJ, Bullemer P. Attentional requirements of learning: evidence from performance measures. Cogn Psychol. 1987;19(1):1-32. DOI 10.1016/0010-0285(87)90002-8. META.
- MM-L12. Shih PC, Hirano M, Furuya S. Bridging chunks during complex movement sequence execution. iScience. 2026;29(2):114562. DOI 10.1016/j.isci.2025.114562. PMID 41567241. PMC12816802. ABS.

### Adaptive

- A-L1. Guadagnoli MA, Lee TD. Challenge point: a framework for conceptualizing the effects of various practice conditions in motor learning. J Mot Behav. 2004;36(2):212-224. DOI 10.3200/JMBR.36.2.212-224. PMID 15130871. ABS.
- A-L2. Wilson RC, Shenhav A, Straccia M, Cohen JD. The Eighty Five Percent Rule for optimal learning. Nat Commun. 2019;10(1):4646. DOI 10.1038/s41467-019-12552-4. PMID 31690723. PMC6831579. ABS.
- A-L3. Levitt H. Transformed up-down methods in psychoacoustics. J Acoust Soc Am. 1971;49(2B):467-477. DOI 10.1121/1.1912375. ABS (Crossref record). Leek MR. Adaptive procedures in psychophysical research. Percept Psychophys. 2001;63(8):1279-1292. DOI 10.3758/bf03194543. PMID 11800457. ABS. Kaernbach C. Simple adaptive testing with the weighted up-down method. Percept Psychophys. 1991;49(3):227-229. DOI 10.3758/bf03214307. PMID 2011460. ABS. García-Pérez MA. Forced-choice staircases with fixed step sizes: asymptotic and small-sample properties. Vision Res. 1998;38(12):1861-1881. DOI 10.1016/s0042-6989(97)00340-4. PMID 9797963. ABS.
- A-L4. Choi Y, Qi F, Gordon J, Schweighofer N. Performance-based adaptive schedules enhance motor learning. J Mot Behav. 2008;40(4):273-280. DOI 10.3200/JMBR.40.4.273-280. PMID 18628104. ABS.
- A-L5. Onla-or S, Winstein CJ. Determining the optimal challenge point for motor skill learning in adults with moderately severe Parkinson's disease. Neurorehabil Neural Repair. 2008;22(4):385-395. DOI 10.1177/1545968307313508. PMID 18326891. ABS.
- A-L6. Lohse KR, Boyd LA, Hodges NJ. Engaging environments enhance motor skill learning in a computer gaming task. J Mot Behav. 2016;48(2):172-182. DOI 10.1080/00222895.2015.1068158. PMID 26296097. ABS. Leiker AM, Bruzi AT, Miller MW, Nelson M, Wegman R, Lohse KR. The effects of autonomous difficulty selection on engagement, motivation, and learning in a motion-controlled video game task. Hum Mov Sci. 2016;49:326-335. DOI 10.1016/j.humov.2016.08.005. PMID 27551820. ABS.
- A-L7. Keller J, Bless H. Flow and regulatory compatibility: an experimental approach to the flow model of intrinsic motivation. Pers Soc Psychol Bull. 2008;34(2):196-209. DOI 10.1177/0146167207310026. PMID 18212330. ABS.
- A-L8. Zohaib M. Dynamic difficulty adjustment (DDA) in computer games: a review. Adv Hum Comput Interact. 2018;2018:5681652. DOI 10.1155/2018/5681652. ABS (Crossref record). Hocine N, Gouaïch A, Cerri SA, Mottet D, Froger J, Laffont I. Adaptation in serious games for upper-limb rehabilitation: an approach to improve training outcomes. User Model User-Adapt Interact. 2015;25(1):65-98. DOI 10.1007/s11257-015-9154-6. META. Grimm F, Naros G, Gharabaghi A. Closed-loop task difficulty adaptation during virtual reality reach-to-grasp training assisted with an exoskeleton for stroke rehabilitation. Front Neurosci. 2016;10:518. DOI 10.3389/fnins.2016.00518. PMID 27895550. PMC5108796. ABS. Gorsic M, Darzi A, Novak D. Comparison of two difficulty adaptation strategies for competitive arm rehabilitation exercises. IEEE Int Conf Rehabil Robot. 2017;2017:640-645. DOI 10.1109/ICORR.2017.8009320. PMID 28813892. PMC5669049. ABS.
- A-L9. See Rh-L12.

### Cross-mode method

- X-L1. Koo TK, Li MY. A guideline of selecting and reporting intraclass correlation coefficients for reliability research. J Chiropr Med. 2016;15(2):155-163. DOI 10.1016/j.jcm.2016.02.012. META.
- X-L2. Weir JP. Quantifying test-retest reliability using the intraclass correlation coefficient and the SEM. J Strength Cond Res. 2005;19(1):231-240. DOI 10.1519/15184.1. META.
- X-L3. Bonett DG. Sample size requirements for estimating intraclass correlations with desired precision. Stat Med. 2002;21(9):1331-1335. DOI 10.1002/sim.1108. PMID 12111881. META.
- X-L4. Parsons S, Kruijt AW, Fox E. Psychological science needs a standard practice of reporting the reliability of cognitive-behavioral measurements. Adv Methods Pract Psychol Sci. 2019;2(4):378-395. DOI 10.1177/2515245919879695. META.
- X-L5. Heathcote A, Brown S, Mewhort DJK. The power law repealed: the case for an exponential law of practice. Psychon Bull Rev. 2000;7(2):185-207. DOI 10.3758/BF03212979. PMID 10909131. META.
- X-L6. Button KS, Ioannidis JPA, Mokrysz C, Nosek BA, Flint J, Robinson ESJ, Munafò MR. Power failure: why small sample size undermines the reliability of neuroscience. Nat Rev Neurosci. 2013;14(5):365-376. DOI 10.1038/nrn3475. PMID 23571845. META.
- X-L7. Bridges D, Pitiot A, MacAskill MR, Peirce JW. The timing mega-study: comparing a range of experiment generators, both lab-based and online. PeerJ. 2020;8:e9414. DOI 10.7717/peerj.9414. PMID 33005482. PMC7512138. META.
- X-L8. Plant RR. A reminder on millisecond timing accuracy and potential replication failure in computer-based psychology experiments: an open letter. Behav Res Methods. 2016;48(1):408-411. DOI 10.3758/s13428-015-0577-0. PMID 25761394. META.
- X-L9. Lakens D. Equivalence tests: a practical primer for t tests, correlations, and meta-analyses. Soc Psychol Personal Sci. 2017;8(4):355-362. DOI 10.1177/1948550617697177. META.
- X-L10. Collie A, Maruff P, Darby DG, McStephen M. The effects of practice on the cognitive test performance of neurologically normal individuals assessed at brief test-retest intervals. J Int Neuropsychol Soc. 2003;9(3):419-428. DOI 10.1017/S1355617703930074. META.

### Code and note sources re-checked, with corrections

- Kessels RP, van Zandvoort MJ, Postma A, Kappelle LJ, de Haan EH. The Corsi Block-Tapping Task: standardization and normative data. Appl Neuropsychol. 2000;7(4):252-258. DOI 10.1207/S15324826AN0704_8. PMID 11296689. ABS. The 6.2 (SD 1.3) figure is not in the abstract and was not re-read.
- Gendle and Ransom 2006 (J Behav Neurosci Res 4:1-7): not found in Crossref or Europe PMC; read only as quoted by Mathy 2016 [E-L3].
- Berch DB, Krikorian R, Huha EM. Brain Cogn. 1998;38(3):317-338. DOI 10.1006/brcg.1998.1039. PMID 9841789. ABS. Brunetti R, Del Gatto C, Delogu F. Front Psychol. 2014;5:939. DOI 10.3389/fpsyg.2014.00939. PMID 25228888. PMC4151195. ABS (107 participants, spans analogous to the standardisation studies). Arce T, McMullen K. Comput Hum Behav Rep. 2021;4:100099. DOI 10.1016/j.chbr.2021.100099. META. Couture M, Tremblay S. Mem Cognit. 2006;34(8):1720-1729. DOI 10.3758/BF03195933. PMID 17489297. ABS. Conway AR, Kane MJ, Bunting MF, Hambrick DZ, Wilhelm O, Engle RW. Psychon Bull Rev. 2005;12(5):769-786. DOI 10.3758/BF03196772. META. Chekaf M, Gauvrit N, Guida A, Mathy F. Cogn Sci. 2018;42 Suppl 3:904-922. DOI 10.1111/cogs.12601. PMID 29524237. META.
- Rose D, Delevoye-Turrell Y, Ott L, Annett LE, Lovatt PJ. Parkinsons Dis. 2019;2019:6530838. DOI 10.1155/2019/6530838. PMID 31531220. PMC6721399. ABS (30 PD, 26 older, 36 younger; 81, 116, 140 BPM).
- Kal 2016 [MM-L5]: **correction**, the 69 ms is the unaffected hand after stroke, not a healthy value.
- Zatsiorsky 2000 [C-L1]: **correction**, enslaving is non-additive, so chord-conditioned cells are not guaranteed upper bounds.
- Nissen and Bullemer 1987 [MM-L11]: RT figures in the code and design remain unverified (as `srt-sequence-learning.md` Section 6 already says).
- Abolins 2020 [C-L9]: the "8 to 10 percent at about 25 percent MVC" figure is not in the abstract; not re-read.
- Jerosch-Herold C, Houghton J, Miller L, Shepstone L. Does sensory relearning improve tactile function after carpal tunnel decompression? J Hand Surg Eur Vol. 2016;41(9):948-956. DOI 10.1177/1753193416657760. META (Crossref record).
- Das A, Karagiorgis A, Diedrichsen J, Stenner MP, Azañón E. Micro-offline gains do not reflect offline learning during early motor skill acquisition in humans. Proc Natl Acad Sci U S A. 2025;122(44):e2509233122. DOI 10.1073/pnas.2509233122. META (Crossref record; the preprint's title was "Micro-offline gains convey no benefit for motor skill learning").
- Eswari B, Balasubramanian S, Varadhan SKM. Comparable neural and behavioural performance in dominant and non-dominant hands during grasping tasks. Sci Rep. 2025;15:14690. DOI 10.1038/s41598-025-99941-6. META (Crossref record). The source behind C5; the notebook had it without authors.
