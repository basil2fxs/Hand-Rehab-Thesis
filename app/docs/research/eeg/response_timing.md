# Force response events and marker timing

Research pass of 7 October 2026 on Basil's question: is the 30 percent
press threshold right for the EEG markers, and how should presses be
marked for the analysis? `erp.md` (Section 5) and `trigger_hardware.md`
already covered parts of this; this pass verifies and extends them.
What was built from it is at the end, before the references.

## 1. How force-based ERP studies define the response

- **Coles/Donchin lab:** squeeze dynamometers with a Schmitt trigger registered the response online at 25% of each person's maximum, measured per hand [1]. Offline, squeeze and EMG onsets were scored by algorithm: a candidate was a sample followed by three or more rising samples (30 ms at 100 Hz), kept only if an EMG candidate came at most 100 ms earlier. Partial responses that never reached criterion were marked by eye against noise from the 1,000 ms before the stimulus [1].
- **Gehring et al. (1993), Gratton et al. (1988):** records and abstracts verified, methods not read [2,3]. Gehring's 1992 thesis abstract confirms force was measured: errors were weaker, and weaker errors had larger ERNs [4].
- **Hasbroucq, Vidal, Burle:** a fixed force registers the response (20 N in [7]) but analyses lock to EMG onset, marked by eye blind to condition [6,7] or by program plus hand correction [8,9]. Vidal et al. place the Ne peak about 100 ms after EMG onset (abstract) [5].
- **Masaki et al. (2004):** latency from EMG, response-synchronised LRPs; exact event and force criterion unverified [10].
- **Force keys:** 0.5 N for RT and the response-locked medial-frontal negativity [14]; 4 N online, RT rescored offline at 25% of each trial's peak [15]; 1.5 N [16]. I found no readable Ulrich, Mattes or Miller paper stating their own criterion.

Online registration and the analysis time-lock are usually different events.

## 2. Which time-lock is cleanest

- Spacing on ordinary (no-signal) trials [1]: LRP onset, EMG onset 109 ms later, force onset 34 ms after that, 25%-of-maximum criterion 52 ms after that.
- On partial errors the Ne locked to the incorrect EMG activation, not the later correct response [6]. [8] agrees, noting that long motor times distort button-locked ERN latency.
- Errors are weaker with longer motor times [4,8,9], so a force threshold crosses later on errors: a systematic error-versus-correct offset, not just noise.
- LRP amplitude at EMG onset is constant across RT and force kinetics [12]. Faster force development enlarged the LRP in self-paced tasks [11] but not in a cued task [13]; these conflict.
- Electromechanical delay depends on muscle and method: 34 ms for a hand squeeze at 100 Hz [1], under 13 ms at 1 kHz or more (cited in [17]).

Supported order: EMG onset, force onset, then threshold crossings, worse as the threshold rises (a switch is a high threshold). The middle steps are inferred, not tested directly in ERPs.

Jitter cost (my arithmetic; Luck's textbook could not be opened [32]): averaging with timing error convolves the component with the error distribution. For Gaussian width s and error SD j, the peak scales by s/sqrt(s^2 + j^2). With an assumed ERN s of 25 ms: j = 7.5 ms keeps 96%, j = 20 ms keeps 78%. A mean offset shifts latency one for one.

## 3. Offline onset detection

- Teasdale et al.: the initial rate of change alters the onset found (abstract) [18].
- Maffiuletti et al. [17]: systematic manual marking is the reference. In their knee-extensor example, thresholds of 2 to 3.6% of maximum landed 24 to 30 ms after manual onset; 3 SD of baseline noise gave about 1 N on low-noise rigs. Sample at 1 kHz or more and filter minimally; if filtering is unavoidable, use a zero-lag low-pass at the highest workable cut-off.
- Conflict: automated onsets were more repeatable than manual ones [19]. Manual wins on validity, automatic on repeatability.
- EMG: most of 27 filter, 1 to 3 SD and 20 to 100 ms window combinations missed visual onsets [20]; automated methods matched visual marking only with added constraints, so report accuracy [21].
- Zero-phase filters smear effects earlier; causal filters do not [22].

High thresholds give later onsets whose delay grows as force rises more slowly.

## 4. Trigger timing

- Good lab software reached sub-millisecond mean precision with a button box; USB keyboards add 20 to 40 ms; test your own system [23]. Timing error can cause replication failure [24]. Keil et al.'s checklist asks for full timing specification [25].
- Software clock sync cannot measure device throughput delays [26], such as the 20 ms USB bursts here.
- BioSemi's Analog Input Box (AIB) adds up to 32 channels at plus or minus 1 V, sampled in step with the EEG into the same BDF, for sources needing isolation such as mains-powered gear; an optical Ergo cable takes plus or minus 2 V [27].
- Burle et al. logged force separately at 1 kHz [7]; BioSemi studies record EMG on the amplifier at 1,024 or 2,048 Hz [6,8,9].

## 5. Is 30% of a light press reasonable?

The 0.23 N floor sits near the 0.5 N force-key criterion [14] and well below 20 N [7]; relative to maximum it is far lower than the 25% in [1]. Sound for registration; late and rate-dependent as a time-lock [17,18].

- **Low threshold:** nearer motor onset, less rate-dependent, more false triggers from noise, drift and enslaving (in maximal tasks non-instructed fingers reached up to 67.5% of their own maximum, more for neighbours [28]; stroke increases it [29]).
- **High threshold:** fewer false triggers, later, rate-dependent; weak error presses may never register [1,4].

Illustration (my arithmetic; linear rise, 150 ms to peak, within the 136 to 192 ms means cited in [14]): the 30% line is crossed at 45 ms for a light-press-sized press, 22 ms at double strength, 90 ms for a half-strength error. The online chain in the brief then adds 7 to 48 ms (random SD about 7.5 ms).

## Recommendations for this system

1. Keep the online rule for game logic and codes; check per participant that it clears baseline mean plus 3 SD [17] and neighbouring-finger force during presses.
2. Offline, per trial: raw threshold crossing, then force onset by backtracking with the lab's Teasdale-style detector on raw 200 Hz data, lightly zero-phase filtered. Validate on about 10% of trials against blind visual marks (last trough before force leaves baseline noise [17]).
3. Lock ERN/Ne, Pe, response LRP and RP to force onset, with threshold-locked averages as a check; N2, P3 and CNV to the stimulus, with its timing measured once on the lab PC [23]; chords to the first finger's onset; force tracking to target changes. The RP builds over about 2 s [30], so tens of ms matter little there.
4. Confirm sample times come from the Arduino's sample count, not PC arrival. Fit offset plus drift between logged send times and EEG trigger samples, place onsets in EEG samples, report residuals.
5. Hardware: route the SingleTact analog outputs (0 to 2 V, working 0.5 to 1.5 V, load above 5 kOhm [31]) through a 2:1 divider into the AIB (if the lab has one), or one pad via an optical Ergo cable, for onsets in EEG time and direct marker latency checks. The pads take USB power from a mains PC: isolated path only, approved by the lab's BioSemi technician. EMG on the amplifier [6,8,9] would lock the ERN best; whether surface EMG separates four fingers is my unchecked doubt.
6. Flag sub-threshold wrong-finger rises that start before the correct press as partial errors [1,6]; rises starting with the pressing finger are likely enslaving [28].
7. Log peak force, time to peak and force rise rate per trial; compare errors with correct [4,8,11,13].
8. Report smoothing, thresholds (counts and N), debounce, onset algorithm and its agreement with visual marks, marker latency (mean, SD, range), true sensor update rate (manual says up to 120 Hz [31]; check the frame index) and the time-lock per analysis [23,25].
9. `erp.md`: EMG in Gehring et al. (1993) is unverified; its flagged LRP paper is Ray et al. (2000) [11].

## What was built (7 October 2026)

- Recommendation 1: the online rule stays as it is. The lab build plays
  the Mac's game, and the 30 percent point decides the press and its
  byte in both.
- Recommendations 2 and 4: `events.tsv` gains `press_offset_ms` and
  `onset_offset_ms` for every press byte (100 to 129, 131), measured
  from the byte's write time. The press sample is put back on the
  board's own 5 ms grid by the timing floor's fit
  (`signal.sample_grid_lateness`), which removes the USB bursts and the
  frame the byte waited for. The onset is the Teasdale detector run
  back from the press (`signal.press_onset`): the search starts where
  the last rise into the press starts, so an earlier press or a
  pre-load step is not taken, and the minimum-rise gate is off because
  the game has already found the press. The notebook's export carries
  verbatim copies, pinned by tests.
- Pilot check, 1,334 presses from 55 sessions: an onset for 94 percent
  (Reaction 100 percent), a median 50 ms before the 30 percent sample
  (interquartile 45 to 65 ms, against 52 ms in [1]); the press sample
  was stamped a median 9 ms late (interquartile 3 to 15 ms). Plotted
  samples put the onset at the foot of the rise; the misses are slow
  stepped rises with no clear start.
- Not done: the blind visual check of about 10 percent of onsets, EMG
  or analog force on the amplifier (recommendation 5), the partial
  error flag (6). Recommendation 9 is done in `erp.md`.

## References

FT = full text read; AB = abstract only; MD = metadata only.

1. De Jong R et al. (1990). JEP:HPP 16:164-182. doi:10.1037/0096-1523.16.1.164. FT.
2. Gehring WJ et al. (1993). Psychol Sci 4:385-390. doi:10.1111/j.1467-9280.1993.tb00586.x. MD plus abstract.
3. Gratton G et al. (1988). JEP:HPP 14:331-344. doi:10.1037/0096-1523.14.3.331. AB.
4. Gehring WJ (1992). PhD thesis, University of Illinois. hdl:2142/72113. AB.
5. Vidal F et al. (2000). Biol Psychol 51:109-128. doi:10.1016/S0301-0511(99)00032-0. AB.
6. Burle B et al. (2008). J Cogn Neurosci 20:1637-1655. doi:10.1162/jocn.2008.20110. FT.
7. Burle B et al. (2016). Psychophysiology 53:1008-1019. doi:10.1111/psyp.12647. FT.
8. Smigasiewicz K et al. (2020). Dev Cogn Neurosci 41:100742. doi:10.1016/j.dcn.2019.100742. FT.
9. Korolczuk I et al. (2024). Psychophysiology 61:e14442. doi:10.1111/psyp.14442. FT.
10. Masaki H et al. (2004). Psychophysiology 41:220-230. doi:10.1111/j.1469-8986.2004.00150.x. AB.
11. Ray WJ et al. (2000). Psychophysiology 37:757-765. doi:10.1111/1469-8986.3760757. AB.
12. Mordkoff JT, Grosjean M (2001). Psychophysiology 38:777-786. doi:10.1111/1469-8986.3850777. AB.
13. Sommer W et al. (1994). Psychophysiology 31:503-512. doi:10.1111/j.1469-8986.1994.tb01054.x. AB.
14. Armbrecht AS et al. (2013). PLoS One 8:e54681. doi:10.1371/journal.pone.0054681. FT (methods).
15. Plewan T, Rinkenauer G (2016). Front Psychol 7:1939. doi:10.3389/fpsyg.2016.01939. FT (methods); no EEG.
16. Jaskowski P et al. (1995). Acta Neurobiol Exp 55:57-64. PMID 7597929. FT (methods).
17. Maffiuletti NA et al. (2016). Eur J Appl Physiol 116:1091-1116. doi:10.1007/s00421-016-3346-6. FT.
18. Teasdale N et al. (1993). J Mot Behav 25:97-106. doi:10.1080/00222895.1993.9941644. AB.
19. Thompson BJ et al. (2012). J Electromyogr Kinesiol 22:893-900. doi:10.1016/j.jelekin.2012.05.008. AB.
20. Hodges PW, Bui BH (1996). Electroencephalogr Clin Neurophysiol 101:511-519. doi:10.1016/S0013-4694(96)95190-5. AB.
21. van Boxtel GJM et al. (1993). Psychophysiology 30:405-412. doi:10.1111/j.1469-8986.1993.tb02062.x. AB.
22. Rousselet GA (2012). Front Psychol 3:131. doi:10.3389/fpsyg.2012.00131. FT.
23. Bridges D et al. (2020). PeerJ 8:e9414. doi:10.7717/peerj.9414. FT.
24. Plant RR (2016). Behav Res Methods 48:408-411. doi:10.3758/s13428-015-0577-0. AB.
25. Keil A et al. (2014). Psychophysiology 51:1-21. doi:10.1111/psyp.12147. AB, plus one checklist item via FieldTrip's copy.
26. Kothe C et al. (2025). Imaging Neurosci 3:IMAG.a.136. doi:10.1162/IMAG.a.136. AB.
27. BioSemi product pages: biosemi.com/aib.htm and biosemi.com/accessoires_A2.htm. Read.
28. Zatsiorsky VM et al. (2000). Exp Brain Res 131:187-195. doi:10.1007/s002219900261. AB.
29. Li S et al. (2003). Clin Neurophysiol 114:1646-1655. doi:10.1016/S1388-2457(03)00164-0. AB.
30. Shibasaki H, Hallett M (2006). Clin Neurophysiol 117:2341-2356. doi:10.1016/j.clinph.2006.04.025. AB.
31. SingleTact User Manual V3.1 (eu.singletact.com/s/SingleTact_Manual.pdf). Read.
32. Luck SJ (2014). An Introduction to the Event-Related Potential Technique, 2nd ed. MIT Press. ISBN 9780262525855. MD; not used for claims.
