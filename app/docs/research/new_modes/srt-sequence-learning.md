# SRT sequence learning: verified literature base

Prepared 25 September 2026 for the thesis replication of Dr Welber Marinovic's PsychoPy script `SRT_Sequence_learning_Final_v2.py` (`archive/Webler EEG past program/`).

## Status in the software (25 September 2026)

**Built.** The Reaction card on the hub runs the script as the `srt` mode (`finger_rehab/game/modes/srt.py`), trial for trial:

- Practice 48 random trials with Correct, Incorrect and Miss! feedback, 8 learning blocks of the 10-item sequence 10 times over, a 48-trial random post-test, then the recall. SPACE screens between phases and blocks; a 1000 ms wait opens every block.
- 100 ms red flash with the lab's own tone files (`assets/srt`), a 2.6 s response window from the flash, presses up to 100 ms before the flash scored as anticipations, a 200 ms pause after a miss, the script's accuracy labels.
- The script's frame structure: the interval runs after the frame that ends a trial, so the flash lands one frame after the RSI (measured +16.7 ms at 60 Hz in simulation, every trial). Scheduled on the flip clock, so one dropped frame shifts one onset only.
- EEG byte 30 on the flip that shows the red square, nothing else per trial; block bytes 213 and 233 (mode id 13, code map 1.6).
- The script's three CSVs written into each block folder under the script's names and columns, with extra columns after the script's own.

**Added.** A setup screen on the card: timing group, learning RSI (200 to 2000 ms; cyclical and random scale as half, equal and one and a half times it, so every group keeps the chosen mean), custom sequences (all four squares, no square twice in a row, 4 to 16 items), named setups kept in `config/srt_setups.json`, and the script's 0 to 5 musical experience question. The sequence stays hidden on that screen until Show is pressed. The EEG lab's Play all runs the SRT once in place of the study's first Reaction block and drops the second; the healthy study battery keeps its pre-registered Reaction block.

**Adopted from Section 4 below.** RT measures without each block's first trial and without RTs over 1000 ms (the lab's own rule in B7 and G1); the timing-matched sequence effect (last learning block trials that followed a 500 ms interval only); the proportional effect; triplet and longest-run recall scores beside the script's position-by-position score, with the chance levels; the accuracy cost; the anticipation rate; calling the interval an RSI in the thesis. All are in the block summary (`metadata.json`) and the notebook's SRT chapter.

**Kept as the lab's protocol.** No return-to-sequence block after the post-test; the post-test at 500 ms for every group; one lab sequence (custom sequences are per setup); response bytes off by default (`srt.response_markers` turns on 100, 110, 120 and 130).

**Hands.** Each setup picks one hand's four fingers or two hands. Two hands follows the lab's own studies (B7, G1): V and B under the left middle and index fingers, N and M under the right index and middle, which is what makes an LRP possible. It needs both boards (or the keyboard), and the performance file's hand column reads `both`.

Short glossary (terms used throughout):

- **SRT (serial reaction time) task**: a target appears at one of four places and the participant presses the matching key or pad as fast as possible. Without being told, the targets follow a repeating order.
- **RSI (response-stimulus interval)**: the wait from the participant's response to the next target. The script calls this "ISI", but because the wait starts after the response, it is an RSI. **ISI or SOA** means a gap timed from one stimulus onset to the next, independent of the response.
- **Sequence-specific learning index**: RT on random trials minus RT on sequence trials. General practice speeds up both, so only this difference shows knowledge of the order.
- **Hybrid, FOC and SOC sequences**: in a first-order conditional (FOC) sequence the current location alone predicts the next. In a second-order conditional (SOC) sequence the previous two locations are needed. Hybrid sequences mix predictable and ambiguous transitions and can have unequal location frequencies.
- **PDP (process dissociation procedure)**: after training, participants generate the sequence twice, once trying to reproduce it (inclusion) and once trying to avoid it (exclusion). Failing to avoid it suggests knowledge outside conscious control.
- **ERP**: the EEG signal averaged over many trials, time-locked to an event marker. N2 and P3 are negative and positive peaks around 200 to 350 ms and 300 to 500 ms. **LRP** is the difference between left and right motor cortex signals, so it tracks which hand is being prepared. **CNV** is a slow negative drift while a person waits for an expected stimulus. **ERD** is a drop in oscillatory power (for example alpha or beta) during movement or learning.

---

## 1. How sources were checked

**Folder mapped first.** I read the script in `archive/Webler EEG past program/` and searched every `.md` note in `Thesis Project A` for SRT, sequence learning, Marinovic or Welber. There are no existing literature notes on the SRT. Two files are relevant:

- `Software - Basil Toufexis/app/assets/srt/README.md`: the four tones measure about 660, 700, 790 and 890 Hz (E5, F5, G5, A5) and each lasts about 200 ms. The red flash lasts 100 ms, so the tone outlasts the flash.
- `NOTES FOR FINAL THESIS.md` (Section 4.4): the EEG headset was unavailable, and the plan is marker timing validation plus a small pilot in the Marinovic lab.

**What I confirmed in the script** (these points feed the design table and analysis):

- The programmed wait starts after the frame in which the response was detected. The real response-to-onset gap is therefore the set value plus about one to two frames.
- In practice, the 200 ms feedback text runs before the wait, so the practice RSI is about 700 ms rather than 500 ms.
- Every block starts at sequence position 1 after a 1000 ms pause.
- Only an onset marker (code 30) is sent. There are no response or block markers.
- The `too_early` accuracy label cannot occur in practice. Presses more than about 100 ms before onset are flushed or ignored, never logged.
- The recall file scores recall position by position, starting from sequence position 1.

**Databases and tools used for external checks:**

- PubMed E-utilities (esearch, esummary) for PMIDs and DOIs.
- Europe PMC REST for metadata, abstracts and open full text.
- Crossref REST for DOI metadata and bibliographic search.
- doi.org handle checks and Unpaywall for open access status.
- Semantic Scholar for abstract availability.
- WebFetch for PMC article pages and one bioRxiv preprint. When numbers came from a WebFetch summary, I asked for verbatim sentences and cross-checked them where possible. For example, Stark-Inbar's t value is consistent with the reported plus-or-minus figure being an SD.

**Verification levels used in Section 2:**

- **V1**: metadata confirmed; finding read in the full text.
- **V2**: metadata confirmed; finding taken from the abstract.
- **V3**: metadata confirmed in Crossref; finding taken from a named, verified secondary source because the primary text was blocked.
- **V4**: metadata only. The paper is listed so the thesis can cite it for existence or title, but its content was not relied on.

**Fetches that failed** (content from these sources was not read):

- ScienceDirect (403): Nissen and Bullemer 1987.
- Wiley (403): Leow et al. 2025 published version, Romano Bergstrom et al. 2012.
- Springer (login redirect): Willingham et al. 1997, Shin 2008.
- APA PsycNet (page loads by script only): Stadler 1995, Reed and Johnson 1994, Cohen et al. 1990.
- Cambridge Core (403): Shanks and St John 1994.
- journals.physiology.org (403): O'Reilly et al. 2008.
- ERIC (connection dropped).
- pmc.ncbi.nlm.nih.gov blocks scripted downloads with a browser check. I did not try to get around it and used WebFetch instead.

**DOI problem found.** PubMed and PMC list old DOIs (prefix 10.2478) for two *Advances in Cognitive Psychology* papers, and these do not resolve at doi.org. Crossref gives working DOIs with prefix 10.5709. Use the Crossref DOIs below.

**Own calculations.** Chance levels for recall scoring, sequence structure statistics and sample sizes were computed by me with Python (100,000 simulated recalls; exact noncentral t and F power). They are labelled "own calculation" wherever they appear.

---

## 2. Verified reference list

Format: citation; identifiers; study type and sample; key finding in my words; how verified; confidence.

### A. The SRT paradigm, reviews and standard analysis

**A1.** Nissen, M. J., & Bullemer, P. (1987). Attentional requirements of learning: Evidence from performance measures. *Cognitive Psychology, 19*(1), 1-32.
- DOI 10.1016/0010-0285(87)90002-8. No PMID (not indexed in PubMed).
- Four experiments; healthy adults and Korsakoff patients.
- Experiment 1 is the design the lab's script follows:
  - An asterisk appeared at one of four spatially compatible locations, and the next trial began 500 ms after each response.
  - One group saw a 10-item sequence (4-2-3-1-3-2-4-3-2-1) repeated 10 times per 100-trial block, for 8 blocks. The other saw random order with no immediate repeats.
  - The sequence group became faster and more accurate than the random group.
  - 11 of 12 sequence participants noticed the repetition, so healthy-adult learning in this design was largely aware.
  - Korsakoff patients learned without noticing. A tone-counting secondary task (Experiment 2, four 100-trial blocks) removed the learning effect.
- Verified: V3. Crossref metadata; design details from the Schwarb and Schumacher (2012) full text (A3). No RT values were verified.
- Confidence: high for metadata and design; none for RT numbers.

**A2.** Robertson, E. M. (2007). The serial reaction time task: Implicit motor skill learning? *Journal of Neuroscience, 27*(38), 10073-10075.
- PMID 17881512; PMCID PMC6672677; DOI 10.1523/JNEUROSCI.2747-07.2007.
- Short review.
- Findings:
  - The four-position task usually uses a short fixed delay after each response, often 200 to 500 ms.
  - The sequence versus random RT contrast is the specific learning measure; overall speed-up is not. Random-block RT is inflated partly because participants keep expecting the sequence.
  - Awareness is usually tested with free recall or recognition, and may be graded rather than all-or-none.
  - Performance has perceptual, motor and declarative parts.
- Verified: V1 (PMC page via WebFetch, verbatim extraction). Confidence: high.

**A3.** Schwarb, H., & Schumacher, E. H. (2012). Generalized lessons about sequence learning from the study of the serial reaction time task. *Advances in Cognitive Psychology, 8*(2), 165-178.
- PMID 22723815; PMCID PMC3376886; DOI 10.5709/acp-0113-1. PubMed lists 10.2478/v10053-008-0113-1, which does not resolve.
- Narrative review.
- Findings:
  - Describes the Nissen and Bullemer designs.
  - Defines hybrid versus SOC sequences.
  - Lists awareness measures: questionnaires, forced-choice recognition, free generation and PDP.
  - The now-standard learning test is within-subject: a random or alternate-sequence block placed between sequence blocks, then a return to the sequence.
  - Summarises Stadler (1995) and Schmidtke and Heuer (1997) on timing and integration (B6, B13).
- Verified: V1 (Europe PMC full text). Confidence: high.

**A4.** Cohen, A., Ivry, R. I., & Keele, S. W. (1990). Attention and structure in sequence learning. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 16*(1), 17-30.
- DOI 10.1037/0278-7393.16.1.17. Not found in PubMed.
- Behavioural experiments.
- Compared unique, hybrid and ambiguous sequences. All were learned under single-task conditions; ambiguous sequences were not learned with tone counting. Introduced the term "hybrid" for Nissen and Bullemer-type sequences.
- Verified: V3 (Crossref; content via A3). Confidence: medium.

**A5.** Reed, J., & Johnson, P. (1994). Assessing implicit learning with indirect tests: Determining what is learned about sequence structure. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 20*(3), 585-594.
- DOI 10.1037/0278-7393.20.3.585. Not found in PubMed.
- Behavioural experiments.
- Many older sequences confound location frequency and simple transitions with sequence knowledge. Training on one SOC sequence and testing on a matched SOC sequence isolates true sequence learning. SOC sequences also make awareness less likely.
- Verified: V3 (Crossref; content via A3). Confidence: medium.

**A6.** Vaquero, J. M. M., Jiménez, L., & Lupiáñez, J. (2006). The problem of reversals in assessing implicit sequence learning with serial reaction time tasks. *Experimental Brain Research, 175*(1), 97-109.
- PMID 16724176; DOI 10.1007/s00221-006-0523-6.
- Two experiments.
- Random comparison blocks contain more reversal trials (x-y-x) than training sequences, and this inflates the learning measure. Recommends a structurally matched control sequence.
- Verified: V2. Confidence: high.

**A7.** Willingham, D. B., Nissen, M. J., & Bullemer, P. (1989). On the development of procedural knowledge. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 15*(6), 1047-1060.
- PMID 2530305; DOI 10.1037/0278-7393.15.6.1047.
- Healthy adults.
- A subgroup showed clear RT learning while generating the sequence at chance. More training raised both procedural and declarative knowledge.
- Verified: V2. Confidence: high.

**A8.** Willingham, D. B. (1999). Implicit motor sequence learning is not purely perceptual. *Memory & Cognition, 27*(3), 561-572.
- PMID 10355244; DOI 10.3758/BF03211549.

**A8 (companion).** Willingham, D. B., Wells, L. A., Farrell, J. M., & Stemwedel, M. E. (2000). Implicit motor sequence learning is represented in response locations. *Memory & Cognition, 28*(3), 366-375.
- PMID 10881554; DOI 10.3758/BF03198552.
- Transfer experiments (both papers).
- Implicit SRT learning transferred when the sequence of response locations was kept, not the sequence of stimuli or finger movements. This matters for a force-pad device, where each pad is a response location.
- Verified: V2. Confidence: high.

**A9.** Abrahamse, E. L., Jiménez, L., Verwey, W. B., & Clegg, B. A. (2010). Representing serial action and perception. *Psychonomic Bulletin & Review, 17*(5), 603-623.
- PMID 21037157; DOI 10.3758/PBR.17.5.603.
- Review.
- SRT learning can rest on stimulus-stimulus, response-response or response-stimulus links, depending on task demands.
- Verified: V2. Confidence: high.

**A10.** Clegg, B. A., DiGirolamo, G. J., & Keele, S. W. (1998). Sequence learning. *Trends in Cognitive Sciences, 2*(8), 275-281.
- PMID 21227209; DOI 10.1016/S1364-6613(98)01202-9.
- Review.
- Sequences of stimuli or responses can be learned, with or without awareness, by several neural systems.
- Verified: V2. Confidence: high.

**A11.** Keele, S. W., Ivry, R., Mayr, U., Hazeltine, E., & Heuer, H. (2003). The cognitive and neural architecture of sequence representation. *Psychological Review, 110*(2), 316-339.
- PMID 12747526; DOI 10.1037/0033-295X.110.2.316.
- Theory paper.
- Proposes a dorsal system that learns implicitly within one dimension and a ventral system that can link events across dimensions. Correlated streams (for example timing and location) can be integrated; uncorrelated streams interfere.
- Verified: V2. Confidence: high.

**A12.** Janacsek, K., & Nemeth, D. (2012). Predicting the future: From implicit learning to consolidation. *International Journal of Psychophysiology, 83*(2), 213-221.
- PMID 22154521; DOI 10.1016/j.ijpsycho.2011.11.012.
- Review.
- Sequence learning differs by phase (fast and slow), modality (perceptual and motor) and awareness. Consolidation between sessions depends on awareness, the length of the offline period and age.
- Verified: V2. Confidence: high.

**A13.** Stark-Inbar, A., Raza, M., Taylor, J. A., & Ivry, R. B. (2017). Individual differences in implicit motor learning: Task specificity in sensorimotor adaptation and sequence learning. *Journal of Neurophysiology, 117*(1), 412-428.
- PMID 27832611; PMCID PMC5253399; DOI 10.1152/jn.01141.2015.
- Test-retest study; young adults (whole sample age 21.2 ± 2.4 years). SRT data analysed for 53 participants.
- Task:
  - V, B, N and M keys with four right-hand fingers; a 12-element deterministic sequence.
  - The target cleared 100 ms after the press, then a 100 ms interval.
  - 15 blocks of 84 trials. Random blocks 1, 7, 13 and 15 had no repeats, no x-y-x "trills" and no runs.
- Results:
  - Late learning (random blocks 13 and 15 minus sequence blocks 12 and 14): 36.1 ± 23.6 ms (SD; t(52) = 11.1).
  - Mid-task learning: 11.2 ± 22.5 ms.
  - Baseline RT: 373 ± 65 ms in run 1 and 343 ± 59 ms in run 2. Accuracy: 93 ± 7%.
  - Test-retest r of late learning = 0.07 (mid-task r = 0.27).
  - 40% reported noticing a change. Recall match index 0.21 ± 0.15 against a chance of 0.136.
- Verified: V1 (abstract plus verbatim sentences from the PMC page). Confidence: medium-high.

**A14.** Oliveira, C. M., Hayiou-Thomas, M. E., & Henderson, L. M. (2023). The reliability of the serial reaction time task: Meta-analysis of test-retest correlations. *Royal Society Open Science, 10*(7), 221542.
- PMID 37476512; PMCID PMC10354485; DOI 10.1098/rsos.221542.
- Meta-analysis: 7 studies, 719 participants, mean age 20.8.
- Results:
  - Pooled test-retest r = 0.28 (95% CI 0.16 to 0.40), or 0.30 (0.18 to 0.42) with all effect sizes.
  - Split-half r = 0.63 (0.52 to 0.72) for difference scores.
  - Age, trial count and sequence type did not fix the low retest value.
- Verified: V1. Confidence: high.

**A15.** Oliveira, C. M., Hayiou-Thomas, M. E., & Henderson, L. M. (2024). Reliability of the serial reaction time task: If at first you don't succeed, try, try, try again. *Quarterly Journal of Experimental Psychology, 77*(11), 2256-2282.
- PMID 38311604; PMCID PMC11529135; DOI 10.1177/17470218241232347.
- Adult experiments.
- Retest correlations stayed low (r below .31 across sequence-similarity conditions; .42 and .60 across later sessions).
- Verified: V2. Confidence: high.

**A16.** Howard, J. H., Jr., & Howard, D. V. (1997). Age differences in implicit learning of higher order dependencies in serial patterns. *Psychology and Aging, 12*(4), 634-656.
- PMID 9416632; DOI 10.1037/0882-7974.12.4.634.
- Three experiments; younger and older adults.
- Introduced the alternating pattern-random design (ASRT). No one could describe the regularity, yet all age groups learned it; younger adults learned more.
- Verified: V2. Confidence: high. (Relevant to future work.)

**Location-specific tones.** These sources are grouped here because the tones are a task feature. Leow et al. (2025) is listed in B7.

**A17.** Hoffmann, J., Sebald, A., & Stöcker, C. (2001). Irrelevant response effects improve serial learning in serial reaction time tasks. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 27*(2), 470-482.
- PMID 11294444; DOI 10.1037/0278-7393.27.2.470.
- Three experiments.
- Tones produced by key presses improved learning of a 10-element sequence, but only when tones were mapped to responses consistently and there was enough time before the next stimulus.
- These are response-effect tones, which differ from the script's stimulus-onset tones.
- Verified: V2. Confidence: high.

**A18.** Stöcker, C., Sebald, A., & Hoffmann, J. (2003). The influence of response-effect compatibility in a serial reaction time task. *Quarterly Journal of Experimental Psychology A, 56*(4), 685-703.
- PMID 12745836; DOI 10.1080/02724980244000585.
- Two experiments with an SOC sequence.
- Key-specific tone effects helped only when mapped consistently and in a highly compatible way.
- Verified: V2. Whether ascending pitch from left to right counts as their "compatible" mapping was not checked in the full text. Confidence: high for the abstract claim.

**A19.** Han, Z., Sanchez, D., Levitan, C. A., & Sherman, A. (2024). Stimulus-locked auditory information facilitates real-time visuo-motor sequence learning. *Psychonomic Bulletin & Review, 31*(2), 828-838.
- PMID 37735341; PMCID PMC11061001; DOI 10.3758/s13423-023-02378-z.
- Three experiments using the SISL interception task.
- Sound synchronised with visual cues improved real-time accuracy and speed. The benefit did not carry over to visual-only testing.
- Verified: V2. Confidence: high.

**A20.** Abrahamse, E. L., van der Lubbe, R. H. J., Verwey, W. B., Szumska, I., & Jaśkowski, P. (2012). Redundant sensory information does not enhance sequence learning in the serial reaction time task. *Advances in Cognitive Psychology, 8*(2), 109-120.
- PMID 22679466; PMCID PMC3367906; DOI 10.5709/acp-0108-y. PubMed lists 10.2478/v10053-008-0108-y.
- Two experiments.
- Redundant visual features (position plus colour, or shape plus colour) did not improve sequence learning. Learning was mostly response-based.
- Verified: V2. Confidence: high.

### B. Timing and interval effects

**B1.** Destrebecqz, A., & Cleeremans, A. (2001). Can sequence learning be implicit? New evidence with the process dissociation procedure. *Psychonomic Bulletin & Review, 8*(2), 343-350.
- PMID 11495124; DOI 10.3758/BF03196171.
- Healthy adults; RSI of 0 versus 250 ms. The values are confirmed by B2 and by MacIntyre et al. (2023, B19).
- With no RSI, participants showed sequence knowledge in RT but could neither recognise the sequence nor avoid it under exclusion instructions. With a 250 ms RSI they could control it.
- Verified: V2 plus secondary sources for the RSI values. Confidence: high.

**B2.** Destrebecqz, A., Peigneux, P., Laureys, S., Degueldre, C., Del Fiore, G., Aerts, J., Luxen, A., Van Der Linden, M., Cleeremans, A., & Maquet, P. (2005). The neural correlates of implicit and explicit sequence learning: Interacting networks revealed by the process dissociation procedure. *Learning & Memory, 12*(5), 480-490.
- PMID 16166397; PMCID PMC1240060; DOI 10.1101/lm.95605.
- PET study; healthy adults; RSI 0 versus 250 ms.
- Design: 12-element SOC sequences, 15 blocks of 96 trials, block 13 a different sequence.
- Results:
  - Transfer costs were 111 ms (RSI 250) and 91 ms (RSI 0).
  - Generation was scored as the share of generated triplets (runs of three consecutive items) that belong to the training sequence, with chance 0.33 when repeats are not allowed.
  - Inclusion: 0.71 (RSI 250) and 0.59 (RSI 0). Exclusion: 0.31 and 0.37.
- Verified: V1 (verbatim sentences from the PMC page). Confidence: medium-high.

**B3.** Wilkinson, L., & Shanks, D. R. (2004). Intentional control and implicit sequence learning. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 30*(2), 354-369.
- PMID 14979810; DOI 10.1037/0278-7393.30.2.354.
- Three experiments, including a close replication of B1.
- Participants could both include and exclude the sequence in generation, so the knowledge looked explicit. This does not support B1's claim.
- Verified: V2. Confidence: high.

**B4.** Willingham, D. B., Greenberg, A. R., & Thomas, R. C. (1997). Response-to-stimulus interval does not affect implicit motor sequence learning, but does affect performance. *Memory & Cognition, 25*(4), 534-542.
- PMID 9259630; DOI 10.3758/BF03201128.
- Six experiments.
- An inconsistent (variable) RSI did not harm implicit learning. A long RSI did not stop learning but sometimes hid its expression.
- Verified: V2. The RSI values used were not accessed. Confidence: high for the abstract claims.

**B5.** Frensch, P. A., & Miner, C. S. (1994). Effects of presentation rate and individual differences in short-term memory capacity on an indirect measure of serial learning. *Memory & Cognition, 22*(1), 95-110.
- PMID 8035689; DOI 10.3758/BF03202765.
- Three experiments using the Nissen and Bullemer task.
- Presentation rate reliably changed the RT learning measure under incidental and intentional instructions. MacIntyre et al. (2023) summarise it as a 1500 ms RSI reducing learning.
- Verified: V2 plus secondary source. Confidence: medium-high.

**B6.** Stadler, M. A. (1995). Role of attention in implicit learning. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 21*(3), 674-685.
- DOI 10.1037/0278-7393.21.3.674. Not in PubMed.
- Behavioural experiments.
- In a single-task SRT, inserting irregular pauses between trials disrupted learning about as much as tone counting did. The proposed reason is that consistent temporal organisation of the sequence supports learning.
- Schwarb and Schumacher (2012) describe it as long or short pauses. MacIntyre et al. (2023) describe randomly inserted 2 s pauses that slowed RT.
- Verified: V3 (two secondary sources). Confidence: medium.

**B7.** Leow, L.-A., Nguyen, A., Corti, E., & Marinovic, W. (2025). Informative auditory cues enhance motor sequence learning. *European Journal of Neuroscience, 61*(10), e70140.
- PMID 40399234; DOI 10.1111/ejn.70140. Preprint DOI 10.1101/2024.10.07.617139.
- This is the Marinovic lab's direct precursor. Curtin undergraduates; the preprint reports three studies with n = 32, 137 and 32.
- Task: four grey squares flashed red with 100 ms tones C4 to F4. V and B were pressed with the left hand, N and M with the right. Trials with errors or RT over 1000 ms were excluded.
- Findings:
  - A 500 ms RSI gave better sequence learning than 200 ms.
  - Audiovisual cues beat visual-only cues.
  - Tones that predicted the location beat uninformative tones.
- Verified: V2 (PubMed abstract) plus preprint methods via WebFetch. The published full text was blocked. Confidence: medium-high.

**B8.** Shin, J. C., & Ivry, R. B. (2002). Concurrent learning of temporal and spatial sequences. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 28*(3), 445-457.
- PMID 12018497; DOI 10.1037/0278-7393.28.3.445.
- Two experiments. An incidental temporal sequence (RSIs in Experiment 1, SOAs in Experiment 2) ran alongside the spatial one.
- Spatial learning happened whatever the timing. The temporal pattern was learned only when it was the same length as, and correlated with, the spatial sequence. Spatial learning was larger in that correlated condition.
- Verified: V2. Confidence: high.

**B9.** Shin, J. C. (2008). The procedural learning of action order is independent of temporal learning. *Psychological Research, 72*(4), 376-386.
- PMID 17569989; DOI 10.1007/s00426-007-0115-5.
- Behavioural SRT with RSIs that were random, constant, or a fixed RSI sequence locked in phase with the response sequence. These are the same three conditions as the lab's groups.
- The response order was learned to a similar degree in all three conditions. Learning and integrating the timing made responses faster but did not strengthen knowledge of the order.
- Verified: V2. RSI values and sample were not accessed. Confidence: high for the main claim.

**B10.** O'Reilly, J. X., McCarthy, K. J., Capizzi, M., & Nobre, A. C. (2008). Acquisition of the temporal and ordinal structure of movement sequences in incidental learning. *Journal of Neurophysiology, 99*(5), 2731-2735.
- PMID 18322005; DOI 10.1152/jn.01141.2007.
- SRT with temporal structure, ordinal (order) structure, or both.
- A predictable temporal structure greatly helped learning of the order. A temporal pattern on its own, with random order, was not learned. Timing appears to be stored as part of the ordered sequence.
- Verified: V2. Confidence: high.

**B11.** Salidis, J. (2001). Nonconscious temporal cognition: Learning rhythms implicitly. *Memory & Cognition, 29*(8), 1111-1119.
- PMID 11913747; DOI 10.3758/BF03206380.
- Two experiments with single-key responses to beeps. The RSI followed a repeating pattern of 180, 450 and 1125 ms.
- Responses were faster for the patterned timing than for random timing, with no more explicit knowledge than controls.
- Verified: V2. Confidence: high.

**B12.** Buchner, A., & Steffens, M. C. (2001). Simultaneous learning of different regularities in sequence learning tasks: Limits and characteristics. *Psychological Research, 65*(2), 71-80.
- PMID 11414006; DOI 10.1007/s004260000052.
- Two experiments.
- An unattended RSI regularity was learned when each RSI was uniquely tied to the tone sequence, but not when the link was ambiguous.
- Verified: V2. Confidence: high.

**B13.** Schmidtke, V., & Heuer, H. (1997). Task integration as a factor in secondary-task effects on sequence learning. *Psychological Research, 60*(1-2), 53-71.
- DOI 10.1007/BF00419680.
- A visual 6-item sequence was paired with an auditory go/no-go stream that was 6 items long, 5 items long or random.
- Learning was best when both streams had the same length (integrable) and worst when the auditory stream was random.
- Verified: V3 (Crossref; content via A3). Confidence: medium.

**B14.** Miyawaki, K. (2006). The influence of the response-stimulus interval on implicit and explicit learning of stimulus sequence. *Psychological Research, 70*(4), 262-272.
- PMID 16044316; DOI 10.1007/s00426-005-0216-y.
- Three experiments with alternating long and short RSIs.
- Changing the RSI pattern at test reduced the expression of both incidental and intentional learning. In implicit learning, sub-sequences marked off by long RSIs were what counted.
- Verified: V2. Confidence: high.

**B15.** Verwey, W. B., & Dronkert, Y. (1996). Practicing a structured continuous key-pressing task: Motor chunking or rhythm consolidation? *Journal of Motor Behavior, 28*(1), 71-79.
- PMID 12529225; DOI 10.1080/00222895.1996.9941735.
- N = 36; a 9-key sequence.
- 750 ms RSIs at fixed positions split the sequence into motor chunks (groups of responses produced as one unit). The chunks persisted after the pauses were removed.
- Verified: V2. Confidence: high.

**B16.** Kornysheva, K., Sierk, A., & Diedrichsen, J. (2013). Interaction of temporal and ordinal representations in movement sequences. *Journal of Neurophysiology, 109*(5), 1416-1424.
- PMID 23221413; PMCID PMC3602834; DOI 10.1152/jn.00509.2012.
- Modified SRT.
- A learned timing pattern transferred to a new order when that new order was fixed within a block. This supports a separate timing representation that interacts with order.
- Verified: V2. Confidence: high.

**B17.** Ullén, F., & Bengtsson, S. L. (2003). Independent processing of the temporal and ordinal structure of movement sequences. *Journal of Neurophysiology, 90*(6), 3725-3735.
- PMID 14665684; DOI 10.1152/jn.00458.2003.
- Rhythmic key-press reproduction task, not an SRT.
- Timing and order were learned and transferred separately, including implicit timing learning.
- Verified: V2. Confidence: high.

**B18.** Gobel, E. W., Sanchez, D. J., & Reber, P. J. (2011). Integration of temporal and ordinal information during serial interception sequence learning. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 37*(4), 994-1000.
- PMID 21417511; PMCID PMC3130823; DOI 10.1037/a0022959.
- SISL task, where the response must be timed.
- Disrupting either the order or the timing dropped performance to the level of a new sequence, indicating one integrated representation.
- Verified: V2. Confidence: high.

**B19.** MacIntyre, A. D., Lo, H. Y. J., Cross, I., & Scott, S. (2023). Task-irrelevant auditory metre shapes visuomotor sequential learning. *Psychological Research, 87*(3), 872-893.
- PMID 35690927; PMCID PMC10017598; DOI 10.1007/s00426-022-01690-y.
- 46 adults retained (18 to 34 years, mean 21.6); 41 in the RT analysis.
- Task:
  - 12-item sequence at a fixed 1 Hz, with each cue paired to a drum sound.
  - The drum pattern gave a 3/4 or 4/4 metre (a repeating pattern of strong and weak beats).
  - 8 learning blocks of 120 trials.
- Findings:
  - Shifting the metre's phase against the visual sequence slowed RT, more so in people with better rhythm discrimination.
  - A new visual sequence slowed RT by about 38 ms. Mean RT was about 431 ms.
  - Explicit recognition was about 49% correct.
  - Participants with more than 10% correct presses under 50 ms were excluded.
- Verified: V1. Confidence: high.

**B20.** Brandon, M., Terry, J., Stevens, C. J., & Tillmann, B. (2012). Incidental learning of temporal structures conforming to a metrical framework. *Frontiers in Psychology, 3*, 294.
- PMID 22936921; PMCID PMC3425964; DOI 10.3389/fpsyg.2012.00294.
- Two experiments; auditory syllable identification with fixed inter-onset intervals.
- A metrical timing pattern was learned even with an uncorrelated order. A new timing pattern slowed RT, and there was no explicit knowledge.
- Verified: V2. Confidence: high.

**B21.** Schultz, B. G., Stevens, C. J., Keller, P. E., & Tillmann, B. (2013). The implicit learning of metrical and nonmetrical temporal patterns. *Quarterly Journal of Experimental Psychology, 66*(2), 360-380.
- PMID 22943558; DOI 10.1080/17470218.2012.712146.
- Two experiments.
- Temporal patterns were learned without an ordinal pattern in a stimulus-detection task, but not in a multiple-choice task. Metrical patterns were not learned faster.
- Verified: V2. Confidence: high.

**B22.** Soetens, E., Melis, A., & Notebaert, W. (2004). Sequence learning and sequential effects. *Psychological Research, 69*(1-2), 124-137.
- PMID 15160294; DOI 10.1007/s00426-003-0163-4.
- Probabilistic SRT with RSI length varied.
- At short RSIs, sequence learning ran in parallel with changes in automatic effects of the previous trial.
- Verified: V2. Confidence: high.

**B23.** Hsiao, A. T., & Reber, A. S. (2001). The dual-task SRT procedure: Fine-tuning the timing. *Psychonomic Bulletin & Review, 8*(2), 336-342.
- PMID 11495123; DOI 10.3758/BF03196170.

**B23 (companion).** Rah, S. K.-Y., Reber, A. S., & Hsiao, A. T. (2000). Another wrinkle on the dual-task SRT experiment: It's probably not dual task. *Psychonomic Bulletin & Review, 7*(2), 309-313.
- PMID 10909138; DOI 10.3758/BF03212986.
- Behavioural experiments (both papers).
- When a tone falls within the RSI, its timing relative to the response changes learning. Tones can act as extra patterns to be learned rather than as a pure distraction.
- Verified: V2. Confidence: high.

**B24.** Steinborn, M. B., Rolke, B., Bratzke, D., & Ulrich, R. (2008). Sequential effects within a short foreperiod context: Evidence for the conditioning account of temporal preparation. *Acta Psychologica, 129*(2), 297-307.
- PMID 18804193; DOI 10.1016/j.actpsy.2008.08.005.
- Three experiments.
- When the wait before a target (the foreperiod) varies, RT depends on both the current and the previous foreperiod, including for short foreperiods.
- Verified: V2. Confidence: high.

**B25.** Los, S. A., Kruijne, W., & Meeter, M. (2014). Outlines of a multiple trace theory of temporal preparation. *Frontiers in Psychology, 5*, 1058.
- PMID 25285088; PMCID PMC4168672; DOI 10.3389/fpsyg.2014.01058.
- Theory.
- A memory-trace model accounts for how RT changes with foreperiod length under different foreperiod mixes, and for carry-over effects between trials.
- Verified: V2. Confidence: high.

**B26.** Nobre, A., Correa, A., & Coull, J. (2007). The hazards of time. *Current Opinion in Neurobiology, 17*(4), 465-470.
- PMID 17709239; DOI 10.1016/j.conb.2007.07.006.
- Review.
- Temporal expectations change both perception and action.
- Verified: V2. Confidence: high.

**B27.** Destrebecqz, A., & Cleeremans, A. (2003). Temporal effects in sequence learning. In L. Jiménez (Ed.), *Attention and implicit learning* (pp. 181-213). John Benjamins.
- DOI 10.1075/aicr.48.11des.
- V4 (Crossref metadata only). Content not read.

**B28.** Niemi, P., & Näätänen, R. (1981). Foreperiod and simple reaction time. *Psychological Bulletin, 89*(1), 133-162.
- DOI 10.1037/0033-2909.89.1.133.
- V4 (Crossref metadata only). A classic foreperiod review; content not read.

**What each timing study found, by timing type:**

| Study | Constant timing | Structured timing (cyclical, rhythmic, phase-matched) | Random or irregular timing |
|---|---|---|---|
| Nissen and Bullemer 1987 (A1) | 500 ms RSI; clear learning; most participants aware | not tested | not tested |
| Destrebecqz and Cleeremans 2001, 2005 (B1, B2) | 0 vs 250 ms: both learn; 250 ms allows explicit control | not tested | not tested |
| Leow et al. 2025 (B7) | 500 ms better learning than 200 ms | not tested | not tested |
| Frensch and Miner 1994 (B5) | rate changes the measured learning; very long RSI reduces it | not tested | not tested |
| Stadler 1995 (B6) | learning intact | not tested | irregular pauses disrupt learning |
| Willingham et al. 1997 (B4) | long RSI can hide learning | not tested | inconsistent RSI does not harm learning |
| Shin and Ivry 2002 (B8) | (baseline) | timing learned only if same length and correlated; spatial learning larger then | not the focus |
| Shin 2008 (B9) | order learned | order learned to the same degree; timing learning speeds responses | order learned to the same degree |
| O'Reilly et al. 2008 (B10) | (baseline) | predictable timing greatly helps order learning | timing alone, with random order, not learned |
| Miyawaki 2006 (B14) | not the focus | alternating long and short RSIs group items; changing the pattern cuts expression | not the focus |
| Verwey and Dronkert 1996 (B15) | 0 ms RSI (unstructured) | 750 ms pauses at fixed spots create chunks | not tested |
| Schmidtke and Heuer 1997 (B13) | not the focus | same-length second stream integrates and helps | random second stream hurts most |
| Salidis 2001 (B11) | not the focus | repeating RSI pattern learned implicitly | random timing slower |
| MacIntyre et al. 2023 (B19) | fixed 1 Hz | metre linked to the sequence is integrated; phase shift slows RT | not tested |
| Brandon et al. 2012; Schultz et al. 2013 (B20, B21) | not the focus | timing patterns learned with fixed inter-onset intervals, even with uncorrelated order | new timing slows RT |

### C. Awareness measures

**C1.** Shanks, D. R., & St John, M. F. (1994). Characteristics of dissociable human learning systems. *Behavioral and Brain Sciences, 17*(3), 367-395.
- DOI 10.1017/S0140525X00035032. Not in PubMed.
- Target article.
- An awareness test must be sensitive enough before a null result counts as evidence of unawareness. It is cited for this point by Esser and Haider (2017) and by Malassis et al. (2026, C7).
- I did not read the primary text, so the full list of criteria is not verified here.
- Verified: V3. Confidence: medium-low for detail.

**C2.** Perruchet, P., & Amorim, M.-A. (1992). Conscious knowledge and changes in performance in sequence learning: Evidence against dissociation. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 18*(4), 785-800.
- PMID 1385616; DOI 10.1037/0278-7393.18.4.785.
- Three experiments, including the Nissen and Bullemer task.
- Free recall and recognition showed explicit knowledge after very little practice. RT gains were limited to the recalled or recognised chunks.
- Verified: V2. Confidence: high.

**C3.** Shanks, D. R., & Johnstone, T. (1999). Evaluating the relationship between explicit and implicit knowledge in a sequential reaction time task. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 25*(6), 1435-1451.
- PMID 10605830; DOI 10.1037/0278-7393.25.6.1435.
- Three experiments with a 12-element sequence.
- Objective free-generation and recognition tests showed that the sequence knowledge was consciously accessible.
- Verified: V2. Confidence: high.

**C4.** Rünger, D., & Frensch, P. A. (2010). Defining consciousness in the context of incidental sequence learning: Theoretical considerations and empirical implications. *Psychological Research, 74*(2), 121-137.
- PMID 19142657; DOI 10.1007/s00426-008-0225-8.
- Theory plus data.
- Argues that verbal report is a sensitive and specific test of conscious sequence knowledge, and that recognition and generation tests are not. Which measure you pick can change the conclusion.
- Verified: V2. Confidence: high.

**C5.** Haider, H., Eichler, A., & Lange, T. (2011). An old problem: How can we distinguish between conscious and unconscious knowledge acquired in an implicit learning task? *Consciousness and Cognition, 20*(3), 658-672.
- PMID 21106394; DOI 10.1016/j.concog.2010.10.021.
- Two experiments.
- A behavioural marker during the SRT identified which participants became aware. It was validated against inclusion/exclusion and wagering.
- Verified: V2. Confidence: high.

**C6.** Vadillo, M. A., Konstantinidis, E., & Shanks, D. R. (2016). Underpowered samples, false negatives, and unconscious learning. *Psychonomic Bulletin & Review, 23*(1), 87-102.
- PMID 26122896; PMCID PMC4742512; DOI 10.3758/s13423-015-0892-6.
- Systematic review of 73 contextual cueing studies (a visual search task, not the SRT).
- Awareness tests were usually underpowered. The pooled awareness effect was dz = 0.31, so "no awareness" claims were often false negatives. The lesson applies directly to SRT recall tests.
- Verified: V1. Confidence: high.

**C7.** Malassis, R., Moscado, L., Sackur, J., & Németh, D. (2026). A non-verbal process dissociation procedure to disentangle explicit from implicit sequence learning. *Neuroscience of Consciousness, 2026*(1), niag021.
- PMID 42266415; PMCID PMC13245152; DOI 10.1093/nc/niag021.
- Method study with a review in its introduction.
- Each awareness test has limits:
  - Verbal report misses knowledge people are unsure of.
  - Recognition and generation can be driven by familiarity.
  - Under exclusion instructions, people use shortcuts (repeating one sequence, or one location) that look like good exclusion.
- Verified: V1. Confidence: high.

**C8.** Tal, A., Bloch, A., Cohen-Dallal, H., Aviv, O., Schwizer Ashkenazi, S., Bar, M., & Vakil, E. (2021). Oculomotor anticipation reveals a multitude of learning processes underlying the serial reaction time task. *Scientific Reports, 11*(1), 6190.
- PMID 33737700; PMCID PMC7973553; DOI 10.1038/s41598-021-85842-x.
- Eye-tracked SRT.
- Eye movements made before the target appeared revealed several learning processes running at the same time, which mean RT hides.
- Verified: V2. Confidence: high.

Also relevant here: B1 to B3 (PDP), A2 (free recall and recognition, graded awareness), A7 (generation at chance despite learning), and A13 and D14 (examples of recall scoring).

### D. EEG and the SRT

**D1.** Eimer, M., Goschke, T., Schlaghecken, F., & Stürmer, B. (1996). Explicit and implicit learning of event sequences: Evidence from event-related brain potentials. *Journal of Experimental Psychology: Learning, Memory, and Cognition, 22*(4), 970-987.
- PMID 8708606; DOI 10.1037/0278-7393.22.4.970.
- ERP study. A 10-item standard sequence had rare (Experiment 1) or frequent (Experiment 2) deviants (single items that broke the sequence).
- Responses were faster on standard items, and deviants produced a larger N2. Both effects were bigger in participants with explicit knowledge.
- The LRP showed correct responses being prepared earlier after training. Explicit learners briefly prepared the expected, now wrong, response on deviant trials.
- Verified: V2. Confidence: high.

**D2.** Rüsseler, J., & Rösler, F. (2000). Implicit and explicit learning of event sequences: Evidence for distinct coding of perceptual and motor representations. *Acta Psychologica, 104*(1), 45-67.
- PMID 10769939; DOI 10.1016/S0001-6918(99)00053-0.
- n = 21; an 8-element sequence with perceptual and motor deviants.
- Explicit learners showed a larger N200 to both deviant types and a larger P300 to motor deviants.
- Both explicit and implicit learners showed partial LRP activation of the expected response.
- Verified: V2. Confidence: high.

**D3.** Rüsseler, J., Hennighausen, E., Münte, T. F., & Rösler, F. (2003). Differences in incidental and intentional learning of sensorimotor sequences as revealed by event-related brain potentials. *Cognitive Brain Research, 15*(2), 116-126.
- PMID 12429364; DOI 10.1016/S0926-6410(02)00145-3.
- A 16-letter sequence with deviants.
- N2b and P3b to deviants were larger only in intentional learners.
- Verified: V2. Confidence: high.

**D4.** Schlaghecken, F., Stürmer, B., & Eimer, M. (2000). Chunking processes in the learning of event sequences: Electrophysiological indicators. *Memory & Cognition, 28*(5), 821-831.
- PMID 10983456; DOI 10.3758/BF03198417.
- A 16-item sequence with deviants, followed by PDP.
- N2b and P3b effects appeared only for sequence parts that were explicitly known. RT effects did not depend on explicit knowledge.
- Verified: V2. Confidence: high.

**D5.** Ferdinand, N. K., Mecklinger, A., & Kray, J. (2008). Error and deviance processing in implicit and explicit sequence learning. *Journal of Cognitive Neuroscience, 20*(4), 629-642.
- PMID 18052785; DOI 10.1162/jocn.2008.20046.
- Regular, irregular and random sequences, with and without instructions about the sequence.
- Errors produced an ERN (error-related negativity). A deviant N2b developed in both groups, faster in explicit learners. A P3b appeared only in explicit learners.
- Verified: V2. Confidence: high.

**D6.** Miyawaki, K., Sato, A., Yasuda, A., Kumano, H., & Kuboki, T. (2005). Explicit knowledge and intention to learn in sequence learning: An event-related potential study. *NeuroReport, 16*(7), 705-708.
- PMID 15858410; DOI 10.1097/00001756-200505120-00010.
- The N2 increase to deviants went with explicit knowledge; the P3 link was weak.
- Verified: V2. Confidence: high.

**D7.** Jongsma, M. L. A., Eichele, T., Van Rijn, C. M., Coenen, A. M. L., Hugdahl, K., Nordby, H., & Quiroga, R. Q. (2006). Tracking pattern learning with single-trial event-related potentials. *Clinical Neurophysiology, 117*(9), 1957-1973.
- PMID 16854620; DOI 10.1016/j.clinph.2006.05.012.
- Learning-oddball task (random targets followed by a regular pattern).
- As targets became predictable, the N2 and P3 shrank and a CNV appeared before them. The changes followed sigmoid learning curves in single-trial data.
- Verified: V2. Confidence: high.

**D8.** Beaulieu, C., Bourassa, M.-È., Brisson, B., Jolicoeur, P., & De Beaumont, L. (2014). Electrophysiological correlates of motor sequence learning. *BMC Neuroscience, 15*, 102.
- PMID 25164514; PMCID PMC4162918; DOI 10.1186/1471-2202-15-102.
- n = 22 adults aged 18 to 29.
- Task: right-hand four-finger SRT with a 12-item sequence; 10 sequence blocks of 120 trials plus random blocks.
- Learning definition: the last random block minus the last sequence block, which is the same contrast the lab's script allows.
- Results:
  - Accuracy was about 95%.
  - The growth in ERN from early to late blocks correlated with sequence-specific learning.
- EEG windows used:
  - Response-locked epochs of -300 to +300 ms, with a -200 to 0 ms baseline.
  - Stimulus-locked P1 at 115 to 155 ms, N1 at 165 to 205 ms, P3 at 365 to 405 ms (Pz).
- Verified: V1. Confidence: high.

**D9.** Kóbor, A., Takács, Á., Kardos, Z., Janacsek, K., Horváth, K., Csépe, V., & Nemeth, D. (2018). ERPs differentiate the sensitivity to statistical probabilities and the learning of sequential structures during procedural learning. *Biological Psychology, 135*, 180-193.
- PMID 29634990; DOI 10.1016/j.biopsycho.2018.04.001.
- ASRT with ERPs; n = 40.
- RT and N2 tracked both probability learning and sequence learning. P3 tracked the gradual sequence learning.
- Verified: V2. Confidence: high.

**D10.** Zhuang, P., Toro, C., Grafman, J., Manganotti, P., Leocani, L., & Hallett, M. (1997). Event-related desynchronization (ERD) in the alpha frequency during development of implicit and explicit learning. *Electroencephalography and Clinical Neurophysiology, 102*(4), 374-381.
- PMID 9146500; DOI 10.1016/S0013-4694(96)96030-7.
- n = 13.
- Alpha ERD over central sites opposite the responding hand peaked when explicit knowledge became complete, then fell.
- Verified: V2. Confidence: high.

**D11.** Pollok, B., Latz, D., Krause, V., Butz, M., & Schnitzler, A. (2014). Changes of motor-cortical oscillations associated with motor learning. *Neuroscience, 275*, 47-53.
- PMID 24931763; DOI 10.1016/j.neuroscience.2014.06.008.
- MEG; n = 15.
- Alpha ERD declined step by step with training. The amount of beta suppression correlated with the drop in RT.
- Verified: V2. Confidence: high.

**D12.** Tzvi, E., Verleger, R., Münte, T. F., & Krämer, U. M. (2016). Reduced alpha-gamma phase amplitude coupling over right parietal cortex is associated with implicit visuomotor sequence learning. *NeuroImage, 141*, 60-70.
- PMID 27403869; DOI 10.1016/j.neuroimage.2016.07.019.
- EEG; n = 73.
- Parietal alpha power and alpha/low-gamma coupling fell with learning. Errors rose when the sequence switched to random.
- Verified: V2. Confidence: high.

**D13.** Lum, J. A. G., Clark, G. M., Barhoun, P., Hill, A. T., Hyde, C., & Wilson, P. H. (2023). Neural basis of implicit motor sequence learning: Modulation of cortical power. *Psychophysiology, 60*(2), e14179.
- PMID 36087042; PMCID PMC10078012; DOI 10.1111/psyp.14179.
- n = 50 adults aged 19 to 37.
- Task:
  - Seven 60-trial blocks, right-hand digits 2 to 5.
  - A 10-element FOC sequence (3-4-1-2-4-1-3-4-2-1).
  - Random blocks matched the sequence for location frequency and pairwise transitions.
  - Fixed pacing: 500 ms blank, then a 650 ms stimulus.
- Behaviour:
  - Accuracy 0.88 to 0.92.
  - Sequence effect (block 7 random vs block 6): d = 1.09.
  - General practice (block 1 vs block 7, both random): d = 0.40.
- EEG method:
  - Stimulus and response markers.
  - Response-locked epochs from -1000 to +1000 ms, with ±500 ms analysed.
  - The baseline was the whole-epoch average, because trials have no rest period.
- EEG result: frontal and central theta (4 to 7 Hz) was higher on random trials. There was no alpha or beta sequence effect.
- Verified: V1. Confidence: high.

**D14.** Lum, J. A. G., Barham, M. P., Hyde, C., Hill, A. T., White, D. J., Hughes, M. E., & Clark, G. M. (2024). Top-down and bottom-up oscillatory dynamics regulate implicit visuomotor sequence learning. *Cerebral Cortex, 34*(7), bhae266.
- PMID 39046456; PMCID PMC11267723; DOI 10.1093/cercor/bhae266.
- n = 85 adults aged 18 to 58 (mean 26.4).
- Task:
  - Five 96-trial blocks.
  - A 12-element FOC sequence (1-3-2-3-4-2-1-3-4-1-4-2).
  - The random block matched the sequence for location frequency and first-order transitions.
  - 150 ms blank, then a 600 ms stimulus.
- Behaviour:
  - Accuracy 0.89.
  - Practice RT 422 ms; final random block 407 ms, so fatigue did not explain the random-block slowing.
  - Reliability of the learning difference score: 0.715.
  - Mouse-click generation: 1.1 correct elements on average (lenient scoring); no one reproduced the sequence.
- EEG method:
  - Stimulus-onset markers only.
  - Epochs from -1000 to +1650 ms, trimmed to the trial.
  - Whole-epoch baseline.
- EEG result: vertex theta and C3 alpha/beta fell across sequence blocks and rose on the random block.
- Verified: V1. Confidence: high.

**D15.** Wessel, J. R., Haider, H., & Rose, M. (2012). The transition from implicit to explicit representations in incidental learning situations: More evidence from high-frequency EEG coupling. *Experimental Brain Research, 217*(1), 153-162.
- PMID 22186962; DOI 10.1007/s00221-011-2982-7.
- Gamma coupling between right prefrontal and occipital sites rose just before explicit sequence knowledge showed in behaviour.
- Verified: V2. Confidence: high.

**D16.** Daltrozzo, J., & Conway, C. M. (2014). Neurocognitive mechanisms of statistical-sequential learning: What do event-related potentials tell us? *Frontiers in Human Neuroscience, 8*, 437.
- PMID 24994975; PMCID PMC4061616; DOI 10.3389/fnhum.2014.00437.
- Review of ERP work on sequence learning.
- Verified: V2. Confidence: high.

**EEG method sources:**

**D17.** Walter, W. G., Cooper, R., Aldridge, V. J., McCallum, W. C., & Winter, A. L. (1964). Contingent negative variation: An electric sign of sensorimotor association and expectancy in the human brain. *Nature, 203*, 380-384.
- PMID 14197376; DOI 10.1038/203380a0.
- The original CNV report.
- Verified: PubMed metadata; no abstract available (V4 for content). Confidence: medium.

**D18.** Coles, M. G. H. (1989). Modern mind-brain reading: Psychophysiology, physiology, and cognition. *Psychophysiology, 26*(3), 251-269.
- PMID 2667018; DOI 10.1111/j.1469-8986.1989.tb01916.x.
- Describes the LRP as a measure of motor preparation from motor cortex.
- Verified: V2. Confidence: high.

**D19.** Eimer, M. (1998). The lateralized readiness potential as an on-line measure of central response activation processes. *Behavior Research Methods, Instruments, & Computers, 30*(1), 146-156.
- DOI 10.3758/BF03209424.
- V4 (Crossref metadata only).

**D20.** Woldorff, M. G. (1993). Distortion of ERP averages due to overlap from temporally adjacent ERPs: Analysis and correction. *Psychophysiology, 30*(1), 98-119.
- PMID 8416067; DOI 10.1111/j.1469-8986.1993.tb03209.x.
- Short intervals make the brain responses to neighbouring events overlap. This distorts averages, especially when comparing trials by what came before, and randomising order does not fix it.
- Verified: V2. Confidence: high.

**D21.** Smith, N. J., & Kutas, M. (2015). Regression-based estimation of ERP waveforms: I. The rERP framework, and II. Nonlinear effects, overlap correction, and practical considerations. *Psychophysiology, 52*(2), 157-168 and 169-181.
- PMIDs 25141770 and 25195691; DOIs 10.1111/psyp.12317 and 10.1111/psyp.12320.
- Verified: V2. Confidence: high.

**D22.** Ehinger, B. V., & Dimigen, O. (2019). Unfold: An integrated toolbox for overlap correction, non-linear modeling, and regression-based EEG analysis. *PeerJ, 7*, e7838.
- PMID 31660265; PMCID PMC6815663; DOI 10.7717/peerj.7838.
- Verified: V2. Confidence: high.

**D23.** Keil, A., Debener, S., Gratton, G., Junghöfer, M., Kappenman, E. S., Luck, S. J., Luu, P., Miller, G. A., & Yee, C. M. (2014). Committee report: Publication guidelines and recommendations for studies using electroencephalography and magnetoencephalography. *Psychophysiology, 51*(1), 1-21.
- PMID 24147581; DOI 10.1111/psyp.12147.
- Reporting checklist.
- Verified: V2. Confidence: high.

**D24.** Bridges, D., Pitiot, A., MacAskill, M. R., & Peirce, J. W. (2020). The timing mega-study: Comparing a range of experiment generators, both lab-based and online. *PeerJ, 8*, e9414.
- PMID 33005482; PMCID PMC7512138; DOI 10.7717/peerj.9414.
- In the lab, PsychoPy was among the most precise packages (mean precision under 1 ms). The authors still urge each lab to measure its own stimulus and response timing.
- Verified: V2. Confidence: high.

### E. Healthy-adult reference values

The values below all come from entries above. Comparability depends on sequence type, pacing, awareness and response device, so these are ranges, not norms for the lab's design.

| Source | Population | Task details | Sequence trials | RT | Learning effect | Accuracy | Awareness or recall |
|---|---|---|---|---|---|---|---|
| Nissen and Bullemer 1987 (A1) | young adults | 4 locations, 500 ms RSI, 10-item hybrid, 8 x 100 | 800 | not verified | group difference in RT and accuracy (values not verified) | sequence group more accurate | 11 of 12 noticed the sequence |
| Stark-Inbar et al. 2017 (A13) | n = 53, about 21 years | V B N M, right hand, 12-element deterministic, about 200 ms RSI | 924 per run | 373 and 343 ms early baseline | 36.1 ± 23.6 ms (SD), sandwich random blocks | 93 ± 7% | 40% noticed a change; match index 0.21 vs chance 0.136 |
| MacIntyre et al. 2023 (B19) | n = 41 in RT analysis (46 retained, 18 to 34 years) | two hands, 12-item, fixed 1 Hz, drum sounds | 960 | mean about 431 ms | about 38 ms slowing to a new sequence | not extracted | recognition about 49% |
| Destrebecqz et al. 2005 (B2) | young adults | 12-element SOC, RSI 0 or 250 ms | 1152 | not extracted | 91 ms (RSI 0), 111 ms (RSI 250) | not extracted | inclusion 0.59 and 0.71 vs chance 0.33 |
| Lum et al. 2023 (D13) | n = 50, 19 to 37 years | right hand, 10-element FOC, fixed pacing (650 ms window) | 300 | in figure only | d = 1.09 (sequence), d = 0.40 (general) | 0.88 to 0.92 | all unaware on questioning |
| Lum et al. 2024 (D14) | n = 85, 18 to 58 years | right hand, 12-element FOC, fixed pacing (600 ms window) | 384 | practice 422 ms; random 407 ms | significant; difference-score reliability 0.715 | 0.89 | 1.1 correct elements in generation |
| Beaulieu et al. 2014 (D8) | n = 22, 18 to 29 years | right hand, 12-item | 1200 | in figure only | significant, t(21) = 4.65 | about 95% | not reported in text |
| Leow et al. 2026 (G1) | n = 151 Curtin undergraduates, about 20.5 years | same lab's audiovisual SRT: 10-item sequence, informative tones, 500 ms RSI, two hands | 500 | RT fell about 40 ms per block | no random block; musicians faster overall by about 46 ms | about 94% correct (6.1% error trials) | recall measured; values in figure only |

Summary of expectations for healthy young adults:

- **Random-block RT:** about 350 to 450 ms on keyboards.
- **Accuracy:** about 90 to 95%.
- **Sequence-specific learning after roughly 800 to 1200 sequence trials:** about 35 to 110 ms across these designs. It is larger when the sequence is simpler, the RSI is longer and participants become aware (A1, B1, B2).
- **Recall:** no verified source gives a normative recall score for a 10-item sequence like the lab's. Recall ranges from near chance in fast-paced FOC or SOC designs (A13, D14) to most participants noticing the sequence in the original 500 ms design (A1).
- **What to expect here:** the lab's design has a 500 ms RSI, informative tones, 800 trials, and a block start that always marks position 1. It should favour explicit knowledge. Leow et al. (2026) describe their closely related task as explicit sequence learning. This is my inference and should be tested with the recall data.

### F. Motor rehabilitation relevance (kept short)

**F1.** Siegert, R. J., Taylor, K. D., Weatherall, M., & Abernethy, D. A. (2006). Is implicit sequence learning impaired in Parkinson's disease? A meta-analysis. *Neuropsychology, 20*(4), 490-495.
- PMID 16846267; DOI 10.1037/0894-4105.20.4.490.
- Meta-analysis: 6 studies, 67 people with PD (Parkinson's disease).
- Outcome: RT on the random block minus RT on the last sequence block. Learning was smaller in PD: standardised mean difference 0.73 (95% CI 0.38 to 1.07).
- Verified: V2. Confidence: high.

**F2.** Clark, G. M., Lum, J. A. G., & Ullman, M. T. (2014). A meta-analysis and meta-regression of serial reaction time task performance in Parkinson's disease. *Neuropsychology, 28*(6), 945-958.
- PMID 25000326; DOI 10.1037/neu0000121.
- Meta-analysis: 27 studies, 505 people with PD and 460 controls.
- PD showed worse sequence learning (p < .001), with a weighted effect size of .531 and I² = 58%.
- Dual-task conditions combined with disease severity, or sequence features, may moderate the effect.
- The abstract prints the 95% CI as [.332, .470], which does not contain .531. Check the full text before quoting the CI.
- Verified: V2. Confidence: high, apart from the CI.

**F3.** Clark, G. M., & Lum, J. A. G. (2017). Procedural learning in Parkinson's disease, specific language impairment, dyslexia, schizophrenia, developmental coordination disorder, and autism spectrum disorders: A second-order meta-analysis. *Brain and Cognition, 117*, 41-48.
- PMID 28710941; DOI 10.1016/j.bandc.2017.07.004.
- SRT learning was impaired to a similar degree in PD and in four developmental or psychiatric groups, but spared in autism.
- Verified: V2. Confidence: high.

**F4.** Ruitenberg, M. F. L., Duthoo, W., Santens, P., Notebaert, W., & Abrahamse, E. L. (2015). Sequential movement skill in Parkinson's disease: A state-of-the-art. *Cortex, 65*, 102-112.
- PMID 25681652; DOI 10.1016/j.cortex.2015.01.005.
- Review.
- Most, but not all, studies find impaired SRT learning in PD. Dopamine medication is a major source of the mixed results.
- Verified: V2. Confidence: high.

**F5.** Shin, J. C., & Ivry, R. B. (2003). Spatial and temporal sequence learning in patients with Parkinson's disease or cerebellar lesions. *Journal of Cognitive Neuroscience, 15*(8), 1232-1243.
- PMID 14709239; DOI 10.1162/089892903322598175.
- Spatial and temporal sequences had the same length and a fixed phase relationship, with phase-shift test blocks.
- People with PD learned each sequence alone but not the link between them. People with cerebellar damage showed no sequence learning.
- Verified: V2. Confidence: high. This is directly relevant to the cyclical group.

**F6.** Smith, J., Siegert, R. J., McDowall, J., & Abernethy, D. (2001). Preserved implicit learning on both the serial reaction time task and artificial grammar in patients with Parkinson's disease. *Brain and Cognition, 45*(3), 378-391.
- PMID 11305880; DOI 10.1006/brcg.2001.1286.
- 13 people with PD; verbal SRT.
- Learning was preserved, which shows the heterogeneity in the PD literature.
- Verified: V2. Confidence: high.

**F7.** Meissner, S. N., Krause, V., Südmeyer, M., Hartmann, C. J., & Pollok, B. (2018). The significance of brain oscillations in motor sequence learning: Insights from Parkinson's disease. *NeuroImage: Clinical, 20*, 448-457.
- PMID 30128283; PMCID PMC6095950; DOI 10.1016/j.nicl.2018.08.009.
- MEG; 20 people with PD on medication and 20 controls.
- People with PD learned less and showed less beta suppression over motor cortex during training.
- Verified: V2. Confidence: high.

**F8.** Kal, E., Winters, M., van der Kamp, J., Houdijk, H., Groet, E., van Bennekom, C., & Scherder, E. (2016). Is implicit motor learning preserved after stroke? A systematic review with meta-analysis. *PLoS One, 11*(12), e0166376.
- PMID 27992442; PMCID PMC5161313; DOI 10.1371/journal.pone.0166376.
- 20 studies, 19 of them SRT variants.
- With the unaffected hand, random minus repeated RT = 69 ms (95% CI 45.1 to 92.9; I² = 87%). With the affected hand, there was no clear learning (SMD -0.11, 95% CI -0.45 to 0.25).
- Risk of bias was high and samples small.
- Verified: V1. Confidence: high.

**F9.** Boyd, L. A., & Winstein, C. J. (2003). Impact of explicit information on implicit motor-sequence learning following middle cerebral artery stroke. *Physical Therapy, 83*(11), 976-989.
- PMID 14577825; DOI 10.1093/ptj/83.11.976.
- 10 stroke and 10 control participants.
- Explicit sequence information helped controls but hurt the stroke group, and the effect lasted to retention.
- Verified: V2. Confidence: high.

**F10.** Boyd, L. A., & Winstein, C. J. (2004). Providing explicit information disrupts implicit motor learning after basal ganglia stroke. *Learning & Memory, 11*(4), 388-396.
- PMID 15286181; PMCID PMC498316; DOI 10.1101/lm.80104.
- Continuous tracking task.
- The same pattern as F9 held after basal ganglia stroke.
- Verified: V2. Confidence: high.

**F11.** Boyd, L., & Winstein, C. (2006). Explicit information interferes with implicit motor learning of both continuous and discrete movement tasks after stroke. *Journal of Neurologic Physical Therapy, 30*(2), 46-57.
- PMID 16796767; DOI 10.1097/01.NPT.0000282566.48050.9b.
- 10 sensorimotor cortex stroke, 10 basal ganglia stroke and 10 controls; SRT and a tracking task.
- Explicit information interfered in both stroke groups on both tasks.
- Verified: V2. Confidence: high.

**F12.** Boyd, L. A., & Winstein, C. J. (2004). Cerebellar stroke impairs temporal but not spatial accuracy during implicit motor learning. *Neurorehabilitation and Neural Repair, 18*(3), 134-143.
- PMID 15375273; DOI 10.1177/0888439004269072.
- 7 people with cerebellar stroke and 10 controls; a tracking task.
- Spatial accuracy on the repeated sequence improved, but the timing lag stayed impaired.
- Verified: V2. Confidence: high.

**F13.** Pohl, P. S., McDowd, J. M., Filion, D. L., Richards, L. G., & Stiers, W. (2001). Implicit learning of a perceptual-motor skill after stroke. *Physical Therapy, 81*(11), 1780-1789.
- PMID 11694171; DOI 10.1093/ptj/81.11.1780.
- 47 stroke and 36 control participants, using the hand on the same side as the lesion.
- Both groups got faster on the pattern, slower on random, and faster again when the pattern returned.
- Verified: V2. Confidence: high.

### G. Musical experience

**G1.** Leow, L.-A., Lum, J., Johnson, S., Corti, E., & Marinovic, W. (2026). Musical training increases anticipatory responding and predictive control in sequence learning. *Psychological Research, 90*(4), 124.
- PMID 42390630; PMCID PMC13328134; DOI 10.1007/s00426-026-02333-2.
- This is the lab's own recent paper. n = 151 Curtin undergraduates, mean age 20.5; 77 had at least some formal musical training.
- Task:
  - Four grey squares with a 100 ms colour change and synchronous 100 ms tones C4 to F4.
  - V and B pressed with the left hand, N and M with the right.
  - 500 ms RSI after a correct response.
  - 50 random practice trials, then 5 blocks of 100 trials. The 10-item sequence was 1-3-1-4-3-2-4-2-3-1.
- Findings:
  - RT fell about 40 ms per block (95% CrI -53.8 to -25.5).
  - A two-component mixture model on log RT put the boundary between anticipatory and reactive responses at about 182 ms.
  - The share of anticipatory responses grew with practice and was consistently higher in musicians.
  - Musicians were faster overall (about 46 ms, in the block 5 vs 6 model).
  - The group difference in learning rate was not credible. Recall of the practised sequence was similar across groups.
- Error trials (6.1%) and RT over 1000 ms (2.2%) were excluded.
- Verified: V1. Confidence: high.

**G2.** Schwizer Ashkenazi, S., Raiter-Avni, R., & Vakil, E. (2022). The benefit of assessing implicit sequence learning in pianists with an eye-tracked serial reaction time task. *Psychological Research, 86*(5), 1426-1441.
- PMID 34468856; DOI 10.1007/s00426-021-01586-3.
- 29 pianists and 31 controls; eye-tracked SRT.
- Pianists did better on RT and on correct anticipations, and gained more explicit knowledge.
- Verified: V2. Confidence: high.

**G3.** Romano Bergstrom, J. C., Howard, J. H., Jr., & Howard, D. V. (2012). Enhanced implicit sequence learning in college-age video game players and musicians. *Applied Cognitive Psychology, 26*(1), 91-96.
- DOI 10.1002/acp.1800.
- V4: Crossref metadata only; the abstract was not accessible. The title claims an advantage; G1 groups this paper with mixed findings on implicit learning.
- Confidence: low for content.

**G4.** Anaya, E. M., Pisoni, D. B., & Kronenberger, W. G. (2017). Visual-spatial sequence learning and memory in trained musicians. *Psychology of Music, 45*(1), 5-21.
- PMID 31031513; PMCID PMC6483398; DOI 10.1177/0305735616638942.
- 24 musicians and 24 non-musicians; a visual-spatial sequence task (not the SRT).
- Musicians did better, even after controlling for vocabulary, reasoning and short-term memory.
- Verified: V2. Confidence: high.

**G5.** Sobierajewicz, J., Naskręcki, R., Jaśkowski, W., & Van der Lubbe, R. H. J. (2018). Do musicians learn a fine sequential hand motor skill differently than non-musicians? *PLoS One, 13*(11), e0207449.
- PMID 30462721; PMCID PMC6248955; DOI 10.1371/journal.pone.0207449.
- Discrete sequence production task with EEG.
- Musicians learned faster and more accurately in practice, and at test showed a general (not sequence-specific) benefit.
- Verified: V2. Confidence: high.

**G6.** Landau, S. M., & D'Esposito, M. (2006). Sequence learning in pianists and nonpianists: An fMRI study of motor expertise. *Cognitive, Affective, & Behavioral Neuroscience, 6*(3), 246-259.
- PMID 17243360; DOI 10.3758/CABN.6.3.246.
- Alternating sequence and random epochs.
- Pianists were faster and acquired the sequence better.
- Verified: V2. Confidence: high.

**G7.** Pau, S., Jahn, G., Sakreida, K., Domin, M., & Lotze, M. (2013). Encoding and recall of finger sequences in experienced pianists compared with musically naïve controls: A combined behavioral and functional imaging study. *NeuroImage, 64*, 379-387.
- PMID 22982586; DOI 10.1016/j.neuroimage.2012.09.012.
- 14 amateur pianists and 15 controls.
- Pianists replayed finger sequences from memory more accurately.
- Verified: V2. Confidence: high.

**G8.** Hughes, C. M. L., & Franz, E. A. (2007). Experience-dependent effects in unimanual and bimanual reaction time tasks in musicians. *Journal of Motor Behavior, 39*(1), 3-8.
- PMID 17251166; DOI 10.3200/JMBR.39.1.3-8.
- 20 musicians and 20 non-musicians.
- Musicians had faster simple RT.
- Verified: V2. Confidence: high.

**G9.** Watanabe, D., Savion-Lemieux, T., & Penhune, V. B. (2007). The effect of early musical training on adult motor performance: Evidence for a sensitive period in motor learning. *Experimental Brain Research, 176*(2), 332-340.
- PMID 16896980; DOI 10.1007/s00221-006-0619-z.
- Musicians who started training before age 7 did better on a timed motor sequence task, mainly in synchronisation, than later starters matched for years of training.
- Verified: V2. Confidence: high.

**G10.** Müllensiefen, D., Gingras, B., Musil, J., & Stewart, L. (2014). The musicality of non-musicians: An index for assessing musical sophistication in the general population. *PLoS One, 9*(2), e89642.
- PMID 24586929; PMCID PMC3935919; DOI 10.1371/journal.pone.0089642.
- Develops the Gold-MSI questionnaire (n = 147,636 online) with good psychometric properties.
- Verified: V2. Confidence: high.

Also relevant: MacIntyre et al. (2023, B19). Self-rated musical experience on a 5-point scale correlated with rhythm discrimination (rs = 0.65), and better rhythm discrimination predicted faster RT.

---

## 3. Design elements mapped to the literature

"Lab's choice" means I found no source that sets that value. It does not mean the value is wrong.

| Design element (script) | Literature support | Status and notes |
|---|---|---|
| Four locations, one finger per location, spatially compatible keys (V B N M) | A1 (four compatible locations); A13 (same four keys, four right-hand fingers); B7, G1 (same keys, two hands); A8 (learning is tied to response locations) | Supported. A force-pad version keeps the location mapping, which A8 suggests is what matters. |
| Red flash 100 ms plus a location-specific tone (E5 to A5, about 200 ms per README) | B7 (informative tones improve learning; 100 ms tones C4 to F4); G1; A19 (synchronised sound helps real-time performance); A17, A18 (response-effect tones help if consistent and compatible); A20 (redundant visual cues do not help) | Partly supported. Pitch range, tone length (200 ms vs the 100 ms flash) and tone timing at onset rather than after the response are lab choices. |
| Practice: 48 random trials, balanced, no immediate repeats, 500 ms, feedback | A1 (random group had no repeats); D14 (52 practice trials, no repeats, equal frequencies); G1 (50 random practice trials) | Mostly lab's choice. Feedback adds 200 ms, so the practice RSI is about 700 ms (from the script). |
| 10-item sequence 1-3-2-1-4-3-2-4-1-3 | A1 (10-item hybrid); D1 (10-item standard sequence); A17 (10-element); D13 (10-element FOC); B7, G1 (10-item) | Length supported; the specific sequence is the lab's own. It is not Nissen and Bullemer's sequence, even allowing for relabelling, rotation or reversal (own check). Own calculation of its structure: locations 1 and 3 occur 3 times, 2 and 4 twice; no location predicts the next on its own; the previous two locations predict 6 of 10 positions and the previous three predict all 10; no immediate repeats; 2 of the 10 three-item runs per cycle are reversals (x-y-x). A4 to A6 caveats apply. |
| Learning: 8 blocks x 100 trials (10 cycles each) | A1 Experiment 1 (8 x 100, 10 repetitions per block) | Supported. This is a close structural replication of Nissen and Bullemer. |
| Constant 500 ms interval | A1 (500 ms); A2 (200 to 500 ms typical); B7 (500 ms better than 200 ms); B1, B2 (a longer RSI allows explicit control); B4, B5 | Supported. Call it an RSI in the thesis. |
| Cyclical group: 10-value pattern locked to sequence position, mean 500 ms | B9 (the same phase-matched condition); B8 (correlated, same-length timing); B10 (predictable timing helps order learning); B13, A11 (integration of correlated streams); B14, B15 (long intervals mark chunks); B12 | Supported as a manipulation; the outcome is contested (Section 6). The 250/500/750 values are the lab's choice. Own calculation: the 750 ms gaps come before positions 4, 7 and 10, which predicts rhythmic groups of 3, 3 and 4 items. The interval is predictable only from the previous three locations or the position. |
| Random group: each 10-trial cycle a shuffle of 250 x 3, 500 x 4, 750 x 3 | B9 (random RSI condition); B4 (inconsistent RSI harmless); B6 (irregular pauses harmful); B24, B25 (RT depends on current and previous interval) | Supported as a manipulation, with conflicting predictions. The fixed within-cycle mix is the lab's choice. |
| Post-test: 48 random trials, constant 500 ms, no feedback | A2, A13, D8, D13, D14 (random block after sequence blocks); A3 (standard is to return to the sequence afterwards) | Partly supported. There is no return-to-sequence block. For the cyclical and random groups, the post-test also changes the timing, which is a confound (Section 4). |
| 2.5 s deadline; 200 ms pause after a miss | A13 (target stayed up to 2000 ms without a response); D13, D14 (fixed 650 or 600 ms windows) | Lab's choice. The long deadline keeps misses rare, but no source sets this value. |
| Presses up to 100 ms before the flash counted as anticipatory | G1 (anticipatory responses grow with learning and musical training; about 182 ms boundary after onset); G2, C8 (correct anticipations as a learning measure); B19 (heavy anticipators excluded in an implicit-learning study) | Lab's choice, consistent with the literature's interest in anticipation. Pre-onset presses cannot come from seeing the target, so they index prediction. |
| 1 s pause before each block's first trial; every block starts at position 1 | B19 started each block at a different sequence position | Lab's choice. A fixed start may help participants find the sequence's first item and helps position-by-position recall. |
| No feedback in learning and post-test | none found | Lab's choice. |
| Explicit recall: key in 10 items | A2 (free recall); A7 (generation); C2 (free recall and recognition); B1, B2 (PDP generation and triplet scoring); D14, G1 (mouse-click generation or recall); C4 (verbal report) | Supported as a measure. Scoring needs changing (Section 4). |
| Between-subjects timing groups | B9 (random, constant and sequenced RSI conditions); B8, B10 | Supported as a manipulation. The low reliability of the learning index (A13 to A15) limits power. |
| EEG marker at each target onset | D14 (onset markers); D13 (onset and response markers); D1 to D8 (stimulus-locked ERPs); D23, D24 | Supported. Response, block and phase markers would widen what can be analysed. |
| Musical experience coded 0 to 5 by years | B19 (5-point self-rating); G1 (none vs some formal training); G10 (validated Gold-MSI) | Lab's choice. Gold-MSI or at least years and age of onset (G9) would be more defensible. |
| New software: adjustable interval, custom sequences, saved setups | RSI affects learning and awareness (B1, B4, B5, B7); sequence structure matters (A4 to A6); timing-group designs (B9) | Supported. Custom sequences allow SOC or FOC sequences with matched random controls. |

Two further differences from the lab's own prior task, both taken from G1 and B7:

- In Leow et al., a trial ended only after a correct response. In the script, any response ends the trial.
- Leow et al. used C4 to F4 tones of 100 ms; the script uses E5 to A5 files of about 200 ms.

---

## 4. Recommended analysis

**Data checks before analysis** (column names as the script writes them):

- Each participant should have 896 rows: 48 practice, 800 learning, 48 post-test.
- `isi_before_ms` is empty on trial 1 of every block, because of the 1000 ms pause. Otherwise it should match the group:
  - constant: 500 everywhere;
  - cyclical: by `seq_position`, position 1 = 500, 2 = 250, 3 = 500, 4 = 750, 5 = 250, 6 = 500, 7 = 750, 8 = 250, 9 = 500, 10 = 750 (own derivation from the script);
  - random: every 10-trial cycle contains 3 x 250, 4 x 500 and 3 x 750.
- `too_early` should never appear. If it does, the key-flush timing is not working as intended.

**Trial coding and exclusions:**

- Drop trial 1 of every block, because its preceding interval is different.
- Mean RT uses `correct` trials only.
- `anticipatory_correct` (-100 to 0 ms) is analysed as its own outcome, not averaged into RT.
- Errors are `incorrect` plus `anticipatory_incorrect`. Misses are `miss`.
- Upper cut-off: RT over 1000 ms, matching the lab's own studies (B7, G1). Run a sensitivity check using 2.5 SD within each participant and block.
- Ratcliff (1993; *Psychological Bulletin, 114*(3), 510-532; PMID 8272468; DOI 10.1037/0033-2909.114.3.510; V2) showed that cut-off choices change power. Report medians or a heavy-tailed model alongside means.
- Keep fast post-onset responses (0 to about 180 ms) in the primary analysis. In this paradigm they are the learning signal (G1). Report a sensitivity analysis that drops RT under 100 ms; that cut-off is the lab's choice, not a sourced value.
- Optionally drop trials that follow an error. This is common practice but I found no specific source for it.
- Set participant exclusions in advance (for example accuracy under 80%; lab's choice) and report the percentage of trials excluded per group. G1 excluded 7.6%.

**Primary outcome: sequence-specific learning index (SSL), per participant.**

- SSL_ms = mean correct RT in the post-test minus mean correct RT in learning block 8. This is the contrast used by A2, D8, D13, D14 and F1.
- Also report a proportional version, SSL_prop = SSL_ms / post-test mean RT. This allows for baseline speed differences, such as musicians being faster (G1).

**Timing-matched SSL, needed because the post-test always uses 500 ms:**

- Recompute block 8 using only trials with `isi_before_ms` = 500.
  - Cyclical group: positions 1, 3, 6 and 9, which is 39 trials before error exclusions (block-start trial removed).
  - Random group: about 40% of trials.
  - Constant group: all trials.
- Also add `isi_before_ms` as a covariate in trial-level models.
- Without this, part of the SSL in the cyclical and random groups reflects the change in timing rather than the removal of the sequence (B9, B10, B24).

**Secondary outcomes:**

- **General practice:** practice RT minus post-test RT (both random). This follows D13 (block 1 vs 7) and D14 (practice vs final random), and also checks for fatigue. Note the practice block had feedback and an RSI of about 700 ms, so this contrast is approximate.
- **Learning curve:** RT across blocks 1 to 8, reported as the slope per block. For reference, G1 found about 40 ms per block in a similar task. The slope mixes general and sequence-specific learning.
- **Accuracy:** error rate per block; the accuracy cost is post-test error rate minus block 8 error rate (A1 found accuracy effects). Report misses separately.
- **Anticipation:**
  - Proportion of `anticipatory_correct` per block.
  - Proportion of RTs under the fast-mode boundary. Re-estimate that boundary from your own data with a two-component mixture on log RT, as G1 did, rather than copying 182 ms.
  - Compare block 8 with the post-test. In random blocks a correct pre-onset guess happens about 1 time in 3 when participants avoid the current location (own calculation).
  - Anticipation opportunities differ by timing group, because onset time is predictable only in the constant group (and in the cyclical group once learned). Compare groups on this outcome with that in mind.
- **Position effects:** RT by `seq_position` in blocks 7 and 8 against blocks 1 and 2. Split positions into those predictable from the previous two locations (2, 5, 6, 7, 9, 10) and those needing the previous three (1, 3, 4, 8) (own calculation).
- **Timing effects:**
  - Within the cyclical and random groups, RT by current and previous interval (B24, B25).
  - Cyclical group only: RT at positions after a 750 ms gap (4, 7, 10) against the same positions in the constant group, as a chunking test (B14, B15).
- **Recall (score several ways and state chance levels; own simulation, 100,000 random recalls):**
  - *Position by position, as the script saves it.* Chance mean 2.5 of 10 (SD about 1.4; 95th percentile 5). Perfect recall that starts at the wrong point scores only 0 to 3, so this score understates knowledge.
  - *Triplet score (from B2).* The proportion of the 8 recalled triplets that occur anywhere in the repeating sequence, which has 10 distinct triplets. It does not depend on the starting point. Chance is 0.28 if the participant never repeats a key and 0.16 if keys are random with repeats; the 95th percentile of chance is about 0.63.
  - *Longest correct run.* The longest stretch of recalled items that matches the repeating sequence. Chance mean about 3 to 3.5 items; 95th percentile 4 to 5.
  - *Best-rotation match.* Chance is about 5 of 10, too high to be useful.
  - Add one verbal question ("did you notice a pattern, describe it"; C4).
  - Set the "aware" criterion in advance (for example triplet score of at least 0.75, or a correct run of 6 or more) and report SSL with and without aware participants.
  - Treat "unaware" results cautiously (C1, C6).

**Group comparisons:**

- **Trial-level model.** log RT (or raw RT with a Student-t likelihood, as in G1) ~ group x phase (block 8 vs post-test) + `isi_before_ms` + `seq_position`. Include random intercepts and phase slopes by participant, following Barr, D. J., Levy, R., Scheepers, C., & Tily, H. J. (2013), *Journal of Memory and Language, 68*(3), 255-278 (PMID 24403724; DOI 10.1016/j.jml.2012.11.001; metadata verified in Europe PMC). The group x phase term tests whether SSL differs by timing group.
- **Learning curve.** RT ~ group x block (1 to 8) + `isi_before_ms`.
- **Participant level.** Welch ANOVA on SSL_ms and SSL_prop with planned contrasts: constant vs cyclical and constant vs random. Report estimates with 95% intervals.
- **Supporting a null.** Because B9 predicts similar order learning across timing groups, use equivalence tests or Bayes factors, not a non-significant p value alone.
- **Other factors.** Treat awareness and musical experience as moderators, and label them exploratory.
- **Power (own calculation; 80% power, two-sided α = .05):**
  - Two groups: d = 0.8 needs 26 per group; d = 0.5 needs 64 per group.
  - Three-group ANOVA: f = 0.25 needs N = 158; f = 0.40 needs N = 64.
  - SSL itself, within participants: d = 1.0 needs 10; d = 0.5 needs 34.
  - So the SSL should be easy to detect, but timing-group differences need large samples.
  - The low test-retest reliability of SSL (A13 to A15) also weakens any correlation with musical experience or EEG.

**Expected healthy values:** see the table in Section 2E. In short: random RT about 350 to 450 ms; accuracy about 90 to 95%; SSL about 35 to 110 ms after roughly 800 to 1200 sequence trials, with larger values if participants become aware. Recall is likely to be well above chance in this design (inferred from A1, B1 and G1; unverified for this exact sequence).

**EEG analysis (secondary):**

- **Stimulus-locked ERPs.** An epoch of about -200 to +600 ms covers P1 and N1 (about 100 to 200 ms), N2 and P3; D8 used P1 115 to 155, N1 165 to 205 and P3 365 to 405 ms.
  - With a 250 ms RSI and RTs around 350 to 450 ms, the next onset can arrive about 600 to 700 ms after the current one. Longer epochs therefore include the next trial.
  - Use overlap correction (D20 to D22) or restrict to trials with long following intervals.
- **Baselines.** The pre-stimulus period contains the previous response and anticipatory drift (CNV: D7, D17), and that drift differs between timing groups.
  - For time-frequency analysis, use whole-epoch baselines as D13 and D14 did, or regression baselines (D21).
  - State the choice (D23).
- **Contrasts.**
  - Block 8 vs post-test: sequence-specific.
  - Practice vs post-test: general.
  - Early vs late learning blocks (D8).
  - There are no embedded deviants, so the classic deviant N2 and P3 contrasts (D1 to D6) are only available as block 8 vs post-test, which is confounded with time on task.
- **Oscillations.** Expect midline theta and contralateral alpha/beta over motor cortex to fall with learning and rise on random trials (D10 to D14).
- **Response-locked analyses** need response events. Add a response marker, or reconstruct responses from onset plus RT once marker latency has been measured (D24, and the thesis plan in NOTES Section 4.4).
- **LRP** needs responses split across the two hands (D1, D18). It works if V/B and N/M are pressed with different hands (as in G1). It cannot separate four fingers of one hand, as on a single-hand force-pad device.

---

## 5. Thesis notes

**Rationale:**

- The SRT is the standard test of motor sequence learning (A1 to A3, A12). Its core measure, random minus sequence RT, is simple to compute from the device's trial log (A2).
- Rehabilitation relevance:
  - Sequence learning with the unaffected hand survives stroke. Learning with the affected hand is uncertain (F8).
  - PD reduces SRT learning on average, with wide variation (F1, F2, F4, F6).
  - Explicit instructions can hurt learning after stroke (F9 to F11).
  - Timing and order can be affected separately by cerebellar and basal ganglia damage (F5, F12).
  - A device that controls timing, sequence and instructions can test these factors.
- The task continues the Marinovic lab's line of work: audiovisual SRT with informative tones and a 500 ms RSI (B7, G1).

**Methods justification:**

- **Replicating Nissen and Bullemer.** 8 x 100 trials, a 10-item sequence, a 500 ms RSI and random blocks without repeats reproduce Nissen and Bullemer's Experiment 1 structure (A1).
- **Tones.** Informative tones are backed by the lab's own data (B7).
- **Timing groups.** Constant, phase-locked and random RSIs mirror Shin (2008, B9). They let the thesis ask whether timing structure changes order learning (B8, B10) or only speed (B9).
- **Recall.** Free recall is an accepted awareness test (A2, C2), and the PDP extension exists (B1, C7).
- **EEG markers.** Onset markers support stimulus-locked ERP and time-frequency analysis (D13, D14). Timing must be validated on the actual hardware (D24).

**Discussion points:**

- Does predictable timing help order learning (B8, B10) or just make responses faster (B9)? Is the cyclical benefit, if any, due to chunking at the 750 ms gaps (B14, B15) or to temporal preparation (B24 to B26)?
- Does the random group show impaired learning, supporting Stadler (B6), or none, supporting Willingham (B4) and Shin (B9)?
- Awareness: with a 500 ms RSI, informative tones and 800 trials, most healthy participants may become aware (A1, B1, G1). The SSL may then reflect explicit knowledge. Report it as sequence learning, not as "implicit" learning, unless recall and verbal report support that (C1 to C6).
- Anticipation as a learning measure, and the musician advantage in anticipation (G1, G2).
- How far keyboard-based reference values (Section 2E) transfer to force pads.

**Limitations to state:**

- **No return-to-sequence block.** The post-test is not "sandwiched" between sequence blocks (A3, A13), so fatigue or time on task can inflate the SSL. The practice vs post-test comparison is a partial check (D14).
- **Timing confound.** For the cyclical and random groups, the post-test changes timing as well as sequence.
- **Sequence structure.** Unequal location frequencies (30/30/20/20%) and fewer reversals in the sequence than in the random blocks (20% vs about 32%, own calculation) can produce an SSL without true order learning (A5, A6).
- **Single sequence.** No counterbalancing, so sequence-specific or finger-specific effects cannot be separated.
- **Reliability.** SSL has low test-retest reliability (A13 to A15), and small groups are underpowered for group differences (Section 4).
- **Recall scoring.** Position-by-position scoring understates knowledge when recall starts mid-cycle.
- **Measurement.** Tone and flash durations differ; the practice RSI is about 700 ms. Keyboard values may not transfer to force pads, where RT depends on the force threshold chosen.
- **EEG.** Overlap at short RSIs, baselines contaminated by anticipation, no response markers, and no LRP with one-hand responses.

**Future work:**

- Add a final sequence block after the random post-test (A3).
- Use a random or alternate-SOC post-test matched on frequencies and transitions (A5, A6, D13, D14), with timing matched to each group's learning phase.
- Counterbalance sequences across participants.
- Add a phase-shift block for the cyclical group to test timing-order integration (F5, B19).
- Add PDP inclusion/exclusion (B1, C7) or the ASRT (A16) for a more implicit measure.
- Test retention on a later day (A12).
- Embed rare deviants for N2 and P3 contrasts (D1 to D5), and add response and block markers.
- Use the Gold-MSI for musical background (G10).
- Test the protocol in stroke and PD cohorts with the affected hand (F2, F8).

---

## 6. Conflicts and gaps

**Where sources disagree:**

- **RSI and awareness.** Destrebecqz and Cleeremans (B1, B2) report that with no RSI participants learn but cannot control their knowledge. Wilkinson and Shanks (B3) found control in a close replication.
- **Irregular timing.** Stadler (B6) found that irregular pauses disrupted learning. Willingham et al. (B4) and Shin (B9) found variable or random RSIs did not reduce learning.
- **Structured timing.**
  - Shin and Ivry (B8) and O'Reilly et al. (B10) found that correlated, predictable timing improves sequence learning.
  - Shin (B9) found phase-locked timing only speeded responses and did not strengthen knowledge of the order.
  - The measures differ (size of the RT cost vs transfer of order knowledge), which may explain part of the disagreement.
- **Can timing be learned alone?**
  - With RSIs, timing was learned only when tied to the order (B8, B10, B12).
  - With fixed onset-to-onset intervals, timing patterns were learned with uncorrelated or no order (B20, B21), and timing was also learned independently in B16 and B17.
  - MacIntyre et al. (B19) argue that RSI timing depends on each participant's own RTs, which muddies the RSI studies.
- **Extra sensory channels.** Informative tones helped in the lab's own studies (B7, G1). Synchronised sound helped real-time performance but did not transfer (A19). Redundant visual cues did not help (A20).
- **Reliability.**
  - Test-retest reliability of SSL is low (r = 0.07 in A13; pooled r about 0.28 to 0.30 in A14; up to 0.60 across later sessions in A15).
  - Within-session reliability is higher (split-half 0.63 to 0.66 in A14; 0.715 in D14).
  - These are different kinds of reliability and should not be mixed.
- **Musicians.**
  - Pianists showed better implicit sequence learning (G2), and Romano Bergstrom et al. claim the same (title only; G3).
  - In the lab's own data (G1), the difference in learning rate was not credible, while anticipation and overall speed differed.
  - G1 describes the evidence on implicit learning as mixed.
- **PD.** The meta-analyses (F1, F2) find impairment, but single studies and reviews show preserved learning in some samples (F4, F6).
- **Stroke.** Learning is preserved with the unaffected hand, but there is no clear evidence for the affected hand (F8).

**What could not be verified:**

- Nissen and Bullemer's RT values. The primary text was blocked; the design comes from A3.
- Primary-text details for:
  - Stadler 1995, Cohen et al. 1990, Reed and Johnson 1994 and Schmidtke and Heuer 1997 (all via A3 or B19 only);
  - Shin 2008's RSI values and sample;
  - O'Reilly et al. 2008's interval values;
  - Willingham et al. 1997's RSI values.
- Contents of B27 (Destrebecqz and Cleeremans 2003 chapter), B28 (Niemi and Näätänen 1981), D17 (Walter et al. 1964; metadata only), D19 (Eimer 1998) and G3 (Romano Bergstrom et al. 2012).
- The full list of Shanks and St John's (1994) criteria (C1). Only the sensitivity point is confirmed, via secondary sources.
- Leow et al. (2025) published full text. The methods come from the bioRxiv preprint and may differ from the final version.
- Clark et al. (2014): the confidence interval printed in the abstract does not contain the point estimate.

**Gaps in the literature for this design:**

- No source sets the 100 ms pre-onset anticipation window, the 2.5 s deadline, the 1 s block-start pause, 48-trial random blocks, or E5 to A5 tones. These are lab choices.
- No source reports normative recall for the lab's exact 10-item sequence, or SSL for this exact audiovisual, 800-trial, 500 ms design with a random post-test. The closest data are the lab's own (B7, G1), which have no random test block in the published acquisition phase.
- No source tests the exact 250/500/750 cyclical pattern or the within-cycle random shuffle. Shin (2008) is the nearest match and its interval values were not accessed.
- No SRT force-pad reference values were found.
