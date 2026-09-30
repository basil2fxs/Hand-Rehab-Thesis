# Syllables: task format, structure, presentation and voice

Literature review, 30 September 2026, for four questions about the Syllables mode: which task format teaches best, whether a sitting should be split into sections, how syllables and words should be shown, and which voice to use. Nothing in the game has changed from it yet; the proposed design is in Section 6.

It builds on `syllables-dyslexia-rework.md` and `syllables-all-ages.md` and does not repeat their sources. A source marked "(existing note)" is listed and verified there. Section 1 corrects four points in those notes; the corrections have been made in both files.

**Verification levels** (given for every source in Section 7): FT full text read, or the relevant pages; FT (summary) full text read through a fetch tool that returns a summary; AB abstract read (Europe PMC, Crossref, ERIC or the publisher); MD metadata only, the finding taken from a named secondary source. Seven load-bearing sources were checked a second time against Europe PMC, Crossref and the EEF report itself: [15], [23], [25], [29], [68], [96], [99].

**Evidence tags:** [MA] meta-analysis or systematic review; [RCT] randomised trial; [quasi] non-randomised comparison; [small] under about 40 per group; [lab] laboratory study; [adults] adults only; [theory] argument, not a test; [guideline] consensus advice without cited trials; [transparent] Finnish, German, Italian, Spanish or Polish, where spelling maps to sound far more regularly than in English; [French] more regular than English for reading.

**Terms:**
- *Foil*: a wrong option shown beside the right one.
- *Errorless learning*: teaching arranged so the learner almost never errs, usually by starting with very easy contrasts and making them harder in small steps (*fading*).
- *Errorful learning*: the learner tries first, may be wrong, then sees the answer.
- *Easy-to-hard training*: fading applied to difficulty.
- *Blocking* vs *interleaving*: practising one kind of item or task at a time vs mixing kinds within a session.
- *Self-teaching*: a child stores a word's spelling mainly by decoding it themselves [96].
- *Effect size* (d, g, SMD): the difference between groups in standard-deviation units; about 0.2 is small, 0.5 medium, 0.8 large.
- *Crowding*: letters are harder to identify when other letters sit close by.
- *Visual attention span*: how many separate letters a reader takes in at once.
- *SSML*: the markup that tells a text-to-speech service how to speak. A *phoneme tag* gives the exact pronunciation, usually in IPA; a *lexicon* (PLS file) is a list of words with pronunciations the service applies automatically.
- *LUFS*: loudness units relative to full scale (ITU-R BS.1770). *dBA*: sound level weighted to human hearing.
- *Clear speech*: how people speak when asked to be understood by someone who struggles to hear: fuller vowels, clearer consonants, usually a slower rate.

---

## 1. Corrections to the existing notes

1. **GraphoGame Rime in English.** The rework note cited Ahmed et al 2020 as finding a small nonword-decoding effect. That paper is a later re-analysis of part of the sample of the Education Endowment Foundation trial [24]. The trial itself randomised 398 Year 2 pupils in 15 schools and found no effect on reading (effect size -0.06, 95% CI -0.23 to 0.12, p = 0.48) or on spelling, a result the evaluator rated very high security [23]. Bishop and Hulme simulated both analyses and showed the subset re-analysis inflates effects [25]. The honest statement: the largest, best-controlled English trial of the game this mode copies found no benefit over usual teaching.
2. **Kyle et al 2013.** The all-ages note listed it as showing reading, spelling and phonological gains. The EEF report describes it as one of two small non-randomised studies: 31 children, GG Rime effect sizes 0.66 and 0.53 on reading and 0.91 and 1.43 on spelling and decoding, smaller for GG Phoneme [22][23]. A pilot, not efficacy evidence.
3. **"Slowed or stretched speech has no evidence of benefit"** (all-ages note). Too strong. Training with stretched speech had no lasting benefit (Strong et al 2011, existing note), and time-stretching conversational speech does not reproduce the clear-speech advantage [101]. But slower sentences improved immediate comprehension in children with language disorder [102][103][104], clear speech helps children with learning disabilities [99], and clear speech keeps its advantage at a normal rate [100]. Section 5 gives the reconciled rule.
4. **Rewards and engagement.** The rework note said loud positive feedback is "what keeps a child playing" (Ronimus et al 2014). As summarised on the developer's blog (the abstract could not be read), rewards raised engagement only in the first sessions, playing time fell over 8 weeks in every group, and a 60 vs 80 percent success level made no difference to engagement [74]. Keep the positive feedback, but do not rely on it to hold play.

---

## 2. Question 1: task format

The options: (a) pick the heard syllable from similar-sounding or similar-looking foils; (b) pick it from unrelated chunks; (c) build the word from all its syllables shown scrambled, picked one at a time; (d) other formats.

### Findings

**A. What the syllable programs that worked asked children to do**

1. Every syllable-level print program with a positive controlled result combined recognising syllables with producing something: reading them aloud, blending them into the word, or spelling them. Graphosyllabic analysis (Bhattacharya and Ehri 2004, existing note); syllable types, division and syllable spelling from dictation in middle school (Diliberto et al 2009, as described in [41]); multisyllabic lessons of 40 minutes, three a week for 8 weeks [39]; PHAST and WIST strategy teaching [33][34][35][36][37]; REWARDS [31][32]; the German program in which children draw syllable arcs, find each syllable's vowel and read syllable by syllable (ES 0.82 on word recognition fluency, no effect on comprehension) [60]; and its Grade 2 version, randomised by class against a wait list, with gains in decoding, word recognition and comprehension [59]. [RCT and quasi; the English programs are teacher-led; the software ones are German or French]
2. The two closest software analogues both worked on word reading, and neither used a plain "pick the syllable" loop alone.
   - *Chassymo* (France): the child hears a syllable, sees it 500 ms later, hears a word 500 ms after that, then clicks the syllable's position in the word. About 10 hours, 30 minutes a day for 5 weeks, against a randomly allocated group using other software. Poor decoders trained this way in Grade 1 read better silently and aloud, and understood text better, than a grapho-phonemic group at the end of Grade 2 [18][19]; an earlier study found it beat whole-word training over 9 months [18][20]. [RCT per the authors' summary; French]
   - *Willy Wortbär app* (Germany, Heß et al 2024): 70 tasks in a fixed order, an accuracy module (mark syllable arcs, tap each syllable's vowel, read syllable by syllable) before a speed module (a brief-exposure "syllable buzzer", affix and stem reading). One task presents a word syllable by syllable, then the child picks the word from a set; another asks for the missing prefix from four. Low-skilled Grade 2 readers (66 vs 66 wait-listed, randomised by class) improved on word recognition and phonological recoding but not comprehension [58]. [quasi; transparent]
3. Software-only phonics in English has a weak record. Beyond the EEF null [23]: in India, GraphoLearn English Rime produced in-game gains but no difference on oral and paper tests after 5 weeks [27]; a synthesis of 65 rigorous studies found technology-supported adaptive instruction had no significant effect for struggling readers, while one-to-one tutoring did [30]. On the other side, a Cochrane review of 14 studies (923 English-speaking poor readers, human or computer delivery) found phonics probably improves word reading accuracy (SMD 0.51, low-quality evidence) and fluency (0.45, moderate quality) [29]; a French trial of 921 disadvantaged Grade 1 children found small GraphoGame effects (0.18 to 0.27) [26]; in Singapore a phoneme-level tablet program beat a rime-level one for decoding [28]. Smaller: a French computer game pairing phoneme discrimination with written units improved dyslexic secondary students' reading after 10 hours (pre-post) [21]; a German home reading game improved the trained words only [61]; at Curtin, an app-supported decoding program improved nonword reading in all 8 children with persistent word-reading impairment, with little generalisation [46]. [MA, RCT, single case]
4. No meta-analysis of syllable-level or multisyllabic instruction as such was found. A June 2025 systematic review (14 studies, Grades 4 to 9, not peer reviewed) states that none exists, and finds positive word-reading effects where programs explicitly taught vowel patterns, affixes, syllabication and morphemic analysis [41]. The nearest meta-analysis, of interventions for Grades 3 to 12 with significant word reading difficulties, found a small overall effect (g = 0.14), larger on pseudoword reading (0.38) and fluency (0.29), and larger with more hours [40]. [MA]

**B. Similar vs unrelated foils**

5. Introducing confusable items together slows the first stage of learning. Preschoolers learning letter-like symbols similar in shape and name (a b/d analogue) needed fewer trials when the similar pair was first taught apart [4][3]; raising the salience of the relevant feature and changing one feature at a time helped young children [5]; pigeons learned a hard discrimination with no errors when it was faded in from an easy one [1][2]; and 7 to 9 year olds learned new object names better errorlessly than errorfully [6]. [small, lab]
6. Once learning has started, hard contrasts are learned well if feedback is given. Adults learning English r and l improved with a fixed hard contrast when feedback was given; without feedback only the easy-to-hard version worked [10]. Easy trials enable learning, after which hard trials work [9]. Easy-to-hard beat random order for a hard auditory contrast [12]. But fading improved training without improving final learning for simple one-dimension discriminations; it helped when irrelevant variation was present [11]. [lab, adults]
7. Plausible foils make a multiple-choice item a learning event. In adults, competitive alternatives made people retrieve information about every option, improving later recall of related facts without extra intrusions [13][14]. In Grade 2 children, hard multiple-choice items without feedback led children to give the lures as answers later; immediate feedback showing the right answer removed that cost [15]. Adults who see misspellings spell worse later, but 10 year olds did not (Brown 1988; Dixon and Kaminska 2007, existing note). [lab]
8. *Word Building* (McCandliss et al 2003): poor decoders after Grade 1 read a word's first letter correctly and then broke down on vowels and later consonants. Twenty sessions of building chains of words that differ by one letter at a time improved decoding at every letter position, word identification, comprehension and phoneme awareness against a randomly assigned control group [16]. [RCT, small; English] The mechanism matters: foils that differ only in a middle or final letter force the reader past the first letter; unrelated foils can be rejected on the first letter alone.
9. Errors followed by the answer help school-age children. Children in kindergarten, Grade 2 and Grade 3 who guessed first and then got feedback learned more than those simply told; preschoolers did not benefit [7]. For 3 and 4 year olds, learning from errors was never better than errorless modelling [8]. [lab]
10. Mixing confusable categories within practice improves telling them apart (g = 0.42 over 59 studies, larger when categories resemble each other), but blocking was better for word materials (g = -0.39) [68]. In German Grade 3, interleaved spelling-rule practice beat blocked practice at 8 weeks, mainly for children with more prior knowledge; children with little prior knowledge did better with blocked practice plus guidance [71]. [MA, RCT]

**C. Build the word from its scrambled syllables**

11. No study was found that tested reordering a word's scrambled syllables. The nearest evidence is on encoding (spelling): building and writing words with letter tiles improved phonemic awareness, spelling, decoding and fluency in at-risk and learning-disabled students across 11 studies [43]; in Grade 2, practising spelling transferred to reading more than practising reading transferred to spelling [44]; spelling new letter strings produced more orthographic learning than reading them [45]; spelling interventions had moderate to large effects in dyslexia across 34 controlled trials [42]. Stepping on syllable cards in word order was one game inside the effective German program [60]. [MA for spelling; the tile format itself is untested]
12. Task logic of format (c) as first described: if all the word's syllables are on screen, the only foils are the word's own syllables (the current F6 kind). The choice then tests order, not sound-to-spelling mapping; chance rises from 1 in 4 to 1 in 3 to 1 in 2, and the last tile is forced; and because the word is modelled in print first, a player can rebuild it from visual memory without listening. [theory]

**D. Other formats**

13. *Counting syllables, tapping to a beat, rhythm and music.* Music training gave a small gain in phonological awareness (d = 0.2) and no significant effect on reading fluency across 13 studies [50]; with study quality controlled, the effect on academic outcomes was about zero [52], though another meta-analysis found a small benefit (g about 0.26) for instrumental training [53]. The one RCT in dyslexic children (Italian, 24 vs 22) found gains in rhythm, phonological awareness and reading [47]; a rhythm program and a phoneme program both raised phonological awareness in 33 dyslexic children, but literacy gains were not significant against controls [49]; a rhythm program matched GraphoGame's gains in 19 children with no untrained control [48][23]; Cochrane found no RCT for dyslexia as of 2012 [51]. Phonological training helps reading more with letters than without, and with one or two skills rather than many [54]. [MA; mixed]
14. *Blending* is the last step of graphosyllabic analysis; continuous blending beat pausing between sounds (Gonzalez-Frey and Ehri 2021, existing note).
15. *Segmenting.* In the German programs the child marks the syllables and finds each vowel [58][60]; in this game the model segments for the child.
16. *Missing syllable (cloze).* No study found.
17. *Speeded reading.* Repeated reading of syllables sped up the trained syllables and pseudowords built from them, but not text reading, in Finnish Grade 4 to 6 poor readers [56]; training German consonant clusters helped the trained units and generalised little [57]; the German programs end with brief-exposure reading [58][60]. [transparent]
18. *Reading the finished word yourself.* Children store a new spelling mainly when they decode it themselves: orthographic learning fell when phonological recoding was suppressed [96][97]. Older disabled readers needed significantly more exposures than beginning readers to learn the same words by sight [98]. [lab]

### What it means for this game

- **Format (a) is the better learning format, with two conditions.** Similar foils supply the discrimination that Word Building [16], the phonics trials [29] and the multiple-choice work [13][14] rely on; unrelated foils can be solved on the first letter [16]. First, new contrasts start easy, with confusable pairs taught apart and then together [4][9][10]. Second, after an error the child promptly sees and hears the right answer [15][10]. The current design starts at F1 and moves to similar foils, but with one global rung, a child who has mastered onsets meets a new vowel contrast at whatever rung they are on. Make easy-to-hard a per-contrast rule (Section 6.3).
- **Format (b) is a warm-up and a check, not a teaching format.** Keep F1 for a new player's first sets and for review, where high success is the aim [75].
- **Format (c) as first described teaches order and whole-word spelling but drops the discrimination.** Keep it as a spelling section with two changes: the word is heard without being shown, and the spare lanes hold similar foils, so every slot is a real choice to the end (Section 6.2). Spelling practice transfers to reading better than the reverse [44][45], so this section adds something the pick task lacks.
- **Format (d).** Do not bring back tapping or rhythm as a core task: the evidence is small and mixed [47][50][52], phonological work without print is weaker [54], and dyslexic children were worse at asynchronous two-handed tapping (Wolff et al 1990, existing note). Keep blending and add a read-it-whole step [96][97]. Cloze has no evidence. Speeded reading belongs at the end of a sitting for older players [56][58].
- **The ceiling.** The best English software trial was null [23], and in-game gains often do not reach paper tests [27][30]. The mode can claim to train sound-to-spelling discrimination at the syllable level, not to improve reading, until it is tested against a control group.

### Conflicts or gaps

- Errorless vs errorful: errorless won for new object names in 7 to 9 year olds [6]; errorful won for word associates in children over 5 [7]. The difference may be whether a wrong guess is related to the answer (associates) or arbitrary (names). Letter-sound mappings are closer to arbitrary, which favours starting errorless and adding errors once the mapping exists. An inference, not a tested rule.
- Fading helped training but not final learning in one set of adult studies [11], and helped in another [12]. No study tested fading of syllable foils in children.
- Interleaving helps discrimination [68][69][70], but blocking was better for word materials [68] and for low-knowledge children [71].
- Music and rhythm: small positive vs null meta-analyses [50][52][53].
- Software phonics: positive in French and German trials [18][26][58], null in the best English trial [23].
- Kearns and Whaley 2019 [38] exists but was not read.
- Gaps: no study of scrambled-syllable building, syllable cloze, or distractor similarity in a children's reading game; no English syllable software trial; no study with adults over 60.

---

## 3. Question 2: structure

### Findings

1. **Programs that worked use a fixed order inside each lesson**, from review, to modelled accuracy work, to practice, to speed. The Willy Wortbär app runs an accuracy module before a speed module in a fixed sequence of 70 tasks [58]. The German teacher-led program starts with syllable structure (arcs, vowel nucleus, prefixes and stems), then syllable-by-syllable reading, then fluency games, with words growing from regular words of up to 4 syllables to irregular words of up to 8, then sentences [60]. PHAST moves from direct instruction to strategy use [35]; WIST teaches its four strategies in a set order (analogy, variable vowels, seek the part you know, peeling off affixes) [37]; REWARDS moves from an overt to a covert strategy with rate practice [31][32]. A synthesis of instruction research recommends a short review first, small steps with practice after each, high success, and weekly and monthly review [75]. [RCT and quasi; the synthesis is practitioner guidance]
2. **Oral syllable warm-ups alone have less support than print-linked ones.** Phonological training helps reading more with letters than without, with one or two skills, and with 5 to 18 hours in total rather than more [54]. Phonics effects are larger when started early (d = 0.55) than after Grade 1 (0.27) [55][65]; extensive interventions do best in kindergarten or Grade 1 [67]; phonics and fluency effects shrink more at follow-up than phonological awareness and comprehension effects [66]. [MA]
3. **Total dose.** More hours go with larger effects in struggling readers from Grade 3 to 12 [40] (and Hall et al 2023, existing note). GraphoGame's developer recommended 8.3 to 12.5 hours, 10 to 15 minutes a day, 5 days a week for 10 to 12 weeks; the trial achieved 6 hours in year 1 and 9 in year 2, and more play did not predict better outcomes [23]. Chassymo: about 10 hours [18]. The German app: planned 20 sessions of 45 minutes; achieved about 9 hours [58]. French GraphoGame: 30 minutes, 4 times a week for about 4 months [26]. Toste: 24 lessons of 40 minutes [39]. WIST: 35 hours [37]. PHAST PACES: 60 to 70 hours [36].
4. **Short, frequent sittings.** Year 1 children taught phonics in three 2-minute sessions a day gained more over 2 weeks than children taught in one 6-minute session (8.3 vs 1.3 points) [63]; one class per condition, so teacher and school are confounded [quasi, small]. In a Grade 1 RCT, 4 sessions a week for 16 weeks, 4 a week for 8 weeks and 2 a week for 16 weeks gave the same outcomes [64]. [RCT]
5. **Engagement falls when children play alone.** Playing time fell over 8 weeks at home and rewards helped only briefly [74]; usage in the EEF trial fell short of target [23]; supportive adult interaction was the one significant moderator of GraphoGame effects (McTigue et al 2020, existing note).
6. **Mixing vs blocking.** Interleaving four kinds of maths problems made practice harder but doubled next-day test scores [69], and a cluster RCT in 54 Grade 7 maths classes found 61 vs 38 percent a month later (d = 0.83) [70]. But blocking was better for word materials [68]; in Grade 3 spelling, children with little prior knowledge did better with blocked practice plus guidance [71]; children gained less from interleaving than young adults in category learning [72]. Children with reading difficulties are weaker on executive-function tasks on average (ES 0.57, varying by task) [73], an argument for few task switches per sitting. [MA, RCT; maths and spelling, not syllables]

### What it means for this game

- **Split each sitting into sections in a fixed order:** review, hear and pick, build (spell), read it whole, speed check for older players, finish. This mirrors the accuracy-then-speed order of the programs that worked [58][60] and the review-first principle [75].
- **Block the task formats, mix the items.** One format per section, so the child is not switching rules every trial [73]. Within hear and pick, start a new contrast in a short block (3 or 4 words aimed at the same confusion), then mix it with contrasts already learned [68][71].
- **Sitting length and frequency.** About 10 to 15 hours in total over 8 to 12 weeks, in sittings of about 12 to 15 minutes for 6 to 9 year olds and 15 to 20 minutes for older players, 4 or 5 days a week [23][54][58][63]. The current 30-word block (about 11 minutes) already fits the youngest profile. The exact minutes are design choices inside these ranges, not tested optima.
- **Plan for fading engagement:** an adult present, a visible end point for each sitting, and a log of sittings played vs scheduled [23][74].

### Conflicts or gaps

- Distributed beat massed in a confounded classroom comparison [63], but schedule did not matter in an RCT [64].
- Interleaving: positive [68][69][70] vs blocking better for words and low prior knowledge [68][71].
- Dose: more hours help [40], but GraphoGame showed no dose-response [23], and phonological training peaked at 5 to 18 hours [54].
- Gaps: no study of sitting length for children with dyslexia in a game; no study of the order of syllable tasks within a session.

---

## 4. Question 3: presentation

### Findings

1. **Hyphens between syllables slow reading.** In Finnish, where first-grade books hyphenate at syllable boundaries, hyphens gave Grade 1 and 2 children longer gazes, more fixations and longer regressions, more so for longer words and better readers, even with a small hyphen [79]; hyphenated stories lowered cued recall in Grade 2 [80]; hyphens did not help children read new made-up words, even on first sight [81]. In skilled German adults, hyphens that broke syllables slowed reading more than hyphens that broke morphemes, and colour alternation at either boundary made no difference [78]. [lab; transparent]
2. **Colour-coded syllables: one positive study, with reporting concerns.** In Italian, dyslexic children and adults read syllable-coloured text faster and with fewer errors, while typical readers read it more slowly [76]. Some reported degrees of freedom do not fit groups of 50, and it is one study in a transparent orthography. Alternating colour between words helped Grade 2 Chinese readers, whose script has no spaces [77]. The German programs mark syllables with arcs that the child draws, as an active task [58][60]. No English study of syllable colouring was found. [small; transparent]
3. **Background colour.** In 341 Spanish-speaking adults (89 with dyslexia or at risk) reading on their own screens, warm backgrounds (peach #EDD1B0, orange #EDDD6E, yellow #F8FD89) gave the shortest reading times and blue-grey the longest; white was not tested [82]. [adults; not English; online] The BDA Style Guide 2023 advises dark text on a light, not white, background, cream or soft pastel, and avoiding green and red or pink because of colour-vision deficiency [95]. [guideline] Coloured overlays and lenses cannot be endorsed: better-controlled studies show effects similar to placebo [84], and overlays had no effect on reading speed or errors in dyslexic 13 year olds [85]. [MA]
4. **Font and case.** Sans-serif, upright and monospaced fonts were read faster than serif, proportional and italic fonts by 97 readers (48 with dyslexia) [83]. The BDA recommends sans-serif fonts, lower case for continuous text, and bold rather than italics or underline [95]. [adults, Spanish; guideline]
5. **Size.** Dyslexic children aged 7 to 10 needed a larger print size than reading-matched younger children before reaching full reading speed [86]. Italian dyslexic children showed more crowding and a larger critical print size [87]. The BDA sets 12 to 14 point as a minimum for body text [95]. [lab]
6. **Letter spacing.** Extra-large letter spacing raised reading speed more for dyslexic 13 year olds than for controls and cut missed words [85]. The BDA recommends about 35 percent of the average letter width and warns that too much reduces readability [95]. This adds to the existing notes' conflict (Zorzi 2012 helped; van den Boer and Hakvoort 2015 no help for word naming; Joo et al 2018 only for crowding-prone readers).
7. **Several options at once.** A reduced visual attention span, independent of phonology, was reported in French and British dyslexic children [88], but dyslexic children were impaired for letter and digit strings and not symbol strings, which points to symbol-sound mapping rather than attention [89]. In adults, seeing similar items side by side improved later discrimination more than seeing them in separate blocks [17]. No study compared all options at once with one at a time in a reading game. [lab; contested theory]
8. **Moving vs still text.** No study of reading falling or moving words in dyslexia was found. Coherent-motion sensitivity is lower in dyslexia on average (d = 0.68 over 35 studies, smaller in children) [90], but motion-area activity in dyslexic children matched reading-matched younger children and rose after a reading intervention, so it looks like a consequence of little reading rather than a cause [91]. Action video game training improved Italian dyslexic children's reading speed [92], and a review of 18 small studies judged visuo-attentional training effective [94], but a Polish trial of 54 dyslexic children found neither action nor phonological games beat an untrained dyslexic group [93]. [MA, RCT; mixed]
9. **The finished word.** Decoding a word yourself is what stores it [96][97]; poor readers need more exposures [98]; blending into the whole word is the last graphosyllabic step (existing note).

### What it means for this game

- **Show syllable boundaries with space and position, not marks.** While building, each syllable sits in its own slot with a clear gap; when the word is complete, the gaps close into one unbroken lower-case word. No hyphens or dots inside the finished word [79][80][81]. Alternating colours in the building strip are an option for the 6 to 9 profile only, faded out as rungs rise; one positive study is too weak for a default [76][78].
- **Colours.** Dark grey or near-black text on a warm off-white or cream background, high contrast, no red or green carrying meaning [95][82]. No overlays or per-user tints offered as a treatment [84][85].
- **Type.** An ordinary sans-serif, upright, lower case, bold only for emphasis [83][95]; no special dyslexia font (existing note). Letter spacing about 0.35 of the average letter width in the tiles, not more [85][95].
- **Size.** Tile letters far above the body-text minimum: at least the existing floor of 0.5 degrees x-height (about 5 mm at 60 cm), larger for children [86][87].
- **All four options at once, well apart, and still while being read.** Keep the four lanes (the finger mapping is sound), keep generous space between tiles [87][17], and let tiles drop quickly into place and then stay still, with the time limit shown by a separate shrinking bar. Reading moving text has no evidence of benefit [90][91][93], and a still tile removes a load the task does not need. A design inference, not a tested result.
- **Finished word read-back.** Close the gaps, hold the whole word silently for a moment so the player reads it, then play the word as confirmation. The word returns later (the existing spaced returns), because poor readers need more exposures [96][97][98].

### Conflicts or gaps

- Syllable colouring helped Italian dyslexic readers [76] vs no effect on skilled German adults [78]; nothing in English.
- Letter spacing helps [85] vs no help for word naming vs only crowding-prone readers (existing note).
- Visual attention span: independent deficit [88] vs symbol-sound mapping account [89].
- Action games: positive [92][94] vs failed replication with an untrained control [93].
- Gaps: no study of falling text; no study of simultaneous vs sequential options with children; the background-colour study was adults on uncontrolled screens without a white baseline [82]; the BDA guide cites no evidence [95].

---

## 5. Question 4: voice

### Findings

1. **No study compared a recorded human voice with current neural TTS for isolated syllables or made-up words, with children or dyslexic readers.** This is the central gap.
2. **Adults, sentences.** Voices from three major synthesis platforms were within the range of human voices in noise, some more intelligible [106]. In another study TTS voices were less intelligible overall, but a clear speaking style helped TTS more than human speech [105]. Varying pitch made synthetic sentences sound more natural but less intelligible, and slowing them did not help [107]. Neural TTS was less intelligible in noise than older concatenative TTS in one study (Cohn and Zellou 2020, existing note). [adults]
3. **Children.** Children aged 8 to 11 processed natural speech faster than matched non-speech, but synthetic speech more slowly than tones [108]. Text-to-speech improved passage comprehension for 8 to 12 year olds with dyslexia [109]. The effective German syllable app voiced every word with a commercial TTS voice (CereProc) [58]. Single words are the hardest case for synthetic speech in children (Mirenda 1990; Drager 2006, existing note). [small]
4. **Clear speech helps children with learning disabilities.** 63 children with learning disabilities heard sentences in noise less well than 36 controls and lost more as noise rose; naturally produced clear speech helped both groups substantially, the female talker's more than the male's, and for many of the children it brought them into the controls' range [99]. Clear speech keeps its advantage at a normal rate [100]. Time-stretching conversational speech degraded it, and adding pauses to conversational sentences lowered scores [101]. [small, English]
5. **Slower input helps some children in the moment.** Slowing sentences by 25 percent raised the comprehension of children with language impairment to the level of younger language-matched children, with no effect on controls [102]; slow-rate sentences gave them their fastest word recognition [103]; slowing enabled real-time pronoun linking in children with developmental language disorder, but not final comprehension [104]. Training with stretched speech did not improve outcomes (Strong et al 2011, existing note). [small; language disorder, not dyslexia]
6. **Why TTS fails on isolated syllables and made-up words, and the fix.** A TTS front end guesses a pronunciation from spelling, so a lone chunk can come out as a letter name, a real word or a vowel no speaker would use, and single tokens get sentence-final or question intonation. (Cutting items out of running speech is no answer: words cut from fluent speech are poorly identified, Pollack and Pickett 1964, existing note.) The fix is to supply the pronunciation:
   - Microsoft Azure: SSML `phoneme` element with IPA, SAPI, UPS or X-SAMPA; custom lexicons as PLS files of up to 100 KB, one locale per lexicon [111]. Microsoft's voice table carries no footnote excluding phonemes or custom lexicons for the en-AU standard neural voices [110].
   - Google Cloud: SSML `phoneme` with IPA or X-SAMPA, and a custom-pronunciation dictionary in the request [116]. Chirp 3 HD voices do not take SSML [114] but accept custom pronunciations in IPA or X-SAMPA, a pace control and pause tags, and support en-AU [115].
   - Amazon Polly: `phoneme` fully available for neural voices, partly for generative voices [119].
   - ElevenLabs: phoneme tags work only with the `eleven_flash_v2` model (CMU Arpabet more reliable than IPA), one word per tag; pronunciation dictionaries with phoneme or alias rules [122].
   - Kokoro-82M already takes phonemes (existing note).
7. **Australian English voices available on 30 September 2026:**
   - Microsoft Azure: 14 standard neural en-AU voices (Natasha, William, Annette, Carly, Darren, Duncan, Elsie, Freya, Joanne, Ken, Kim, Neil, Tim, Tina), William Multilingual, and HD voices [110].
   - Google Cloud: en-AU Standard, WaveNet, Neural2, News, Polyglot and Chirp HD voices, and 28 Chirp 3 HD voices [114][115].
   - Amazon Polly: Olivia (neural and generative); Nicole and Russell (standard only) [118].
   - ElevenLabs: Australian-accented community voices [122]; individual voices and their owners' terms were not checked.
   - Open models: Piper has only en_GB and en_US voices; Kokoro has American and British voices, no Australian; MeloTTS has an EN-AU speaker and OpenVoice V2 an en-au base speaker, both MIT [123]. For cloning a consenting Australian speaker, Chatterbox (MIT) and NeuTTS Air (Apache 2.0) permit commercial use; XTTS-v2 (Coqui Public Model License) and F5-TTS (CC BY-NC 4.0) do not [123].
8. **Terms on shipping pre-rendered audio in a desktop app** (read 30 September 2026; a reading of published terms, not legal advice):
   - *Microsoft.* Universal License Terms for Online Services: "Output Content is Customer Data. Microsoft does not own Customer's Output Content." [112]. The Code of Conduct for Microsoft AI Services (version 4.0, 1 May 2026) requires customers to disclose when output is AI-generated, including the synthetic nature of generated voices [113]. No clause forbidding distribution of pre-rendered audio was found; the full Product Terms page did not render, so not every Azure-specific term was read.
   - *Google.* Service Specific Terms (last modified 24 September 2026), Section 20: Google does not assert ownership of Generated Output, which may not be used to substitute a Google model or to create or improve similar models [117]. Whether Cloud Text-to-Speech counts as a generative AI service for Section 20 was not confirmed.
   - *Amazon.* AWS Service Terms (last updated 15 September 2026), Section 50.2: "The output that you generate using AI Services is Your Content." Section 50.3 lets AWS use content processed by Amazon Polly to improve its services unless an opt-out policy is set [120].
   - *ElevenLabs.* Terms of Service (non-EEA, 31 March 2026): free users may only use the services for non-commercial purposes; paid users may use them commercially; users retain rights in their Output and grant ElevenLabs a broad licence over their Content [121].
   - *Open models:* the model licence governs; MIT and Apache 2.0 allow shipping the audio [123].
9. **Loudness and listening conditions.** ITU-T H.870 sets a weekly reference of 80 dBA for 40 hours for adults and 75 dBA in a mode meant for children (from a summary) [124]. EBU R 128 normalises loudness to -23 LUFS with a true peak no higher than -1 dBTP [125]. Classroom standards set background noise no higher than 35 dBA, and children with learning disabilities and auditory processing problems are among those most affected by poor acoustics [126]. Dyslexic children perceive speech normally in quiet but worse in noise (Ziegler et al 2009, existing note).

### What it means for this game

- **A recorded human voice is still the better choice for isolated syllables and made-up words**, because nothing validates neural TTS for exactly these items with children, and a person can be told precisely how to say each chunk and checked against a written pronunciation key. TTS is acceptable if every file is checked by listeners; the recording kit's listener check applies to either route.
- **Clear speech, natural rate, no stretching.** Every syllable and word in a clear citation style at a natural-to-careful rate; no time-stretching; the extra time goes between items, not inside them; one replay per set [99][100][101]. For instruction sentences, a slightly slower delivery is defensible for young children and those with language difficulties [102][103][104].
- **The reconciled rule for the existing note:** slowing the voice does not teach (Strong 2011) and stretching conversational speech does not make it clear [101], but clear articulation helps [99][100] and slower sentence input can help comprehension in the moment [102][104]. So: clear style, natural rate for syllables and words, extra time around them.
- **An Australian accent is now available with pronunciation control** from Azure and Google (and Polly with one neural voice), which removes the main reason the British voice was chosen.

### Conflicts or gaps

- TTS within human intelligibility [106] vs less intelligible [105], and neural worse in noise than concatenative (existing note).
- Slower input helps comprehension [102][103] vs no training benefit (Strong 2011) and no intelligibility gain from slowing synthetic sentences [107].
- Gaps: no validation of neural TTS for syllables or pseudowords with children; no study of an Australian vs British voice for this task; the evidence for a female voice is one study with two talkers [99].

---

## 6. Proposed design

Strength of evidence per item: **Strong** (meta-analyses or RCTs close to this task), **Moderate** (single RCTs or quasi-experiments, transparent orthographies, or lab studies with a clear mechanism), **Weak** (theory, guidelines, or design choices inside ranges that studies used). Section 6.7 ranks them.

### 6.1 Sections and their order (one sitting)

| # | Section | Task | 6 to 9 | 10 to 15 | 16+ | 60+ |
|---|---|---|---|---|---|---|
| 1 | Review | Hear and pick with the easiest foils for known contrasts, words from earlier sittings | 4 words | 4 words | 3 words | 4 words |
| 2 | Hear and pick | The current task with similar foils; a new contrast blocked for 3 or 4 words, then mixed | 8 to 10 | 10 to 12 | 10 to 12 | 8 to 10 |
| 3 | Build it (spell) | Hear the word only; build it slot by slot from its syllables plus similar foils | 3 or 4 | 4 to 6 | 5 or 6, some made-up | 4 |
| 4 | Read it whole | After each build: the gaps close, the player reads the word, then the audio confirms | within 3 | within 3 | within 3 | within 3 |
| 5 | Speed check | A whole word flashed briefly; press when read; then pick it from four heard and shown | off | last 1 to 2 min | last 2 min | off |
| 6 | Finish | One screen: words done, one thing to practise next time | 20 s | 20 s | 20 s | 20 s |

- **Sitting length:** about 12 to 15 minutes for 6 to 9, 15 to 20 minutes for 10 to 15 and 16+, 15 minutes with a pause for 60+. **Frequency:** 4 or 5 sittings a week for 8 to 12 weeks, 10 to 15 hours in total, with an adult present for children. (Moderate for total hours and short frequent sittings [40][54][23][58][63]; weak for the exact minutes.)
- **Why this order:** review first at high success [75]; accuracy before speed [58][60]; production after recognition, because spelling transfers to reading [44][45]; read-it-whole last, so each word ends as one unit the player decoded [96][97]. (Moderate)
- **Formats blocked by section; items mixed within a section** once each contrast has had its short block [68][71][73]. (Moderate)

### 6.2 The task in each section

- **Review (format b, then a):** unrelated foils (F1) for a new player's first set; otherwise the easiest similar foils the player has already mastered. A warm-up and a check the player can use the pads; not counted in the learning measures.
- **Hear and pick (format a):** as now: the word is heard and seen, the syllables modelled, then four chunks per syllable. Changes: foils chosen by the contrast being learned (6.3); after a wrong first press, one more press is allowed, then the right tile is shown and its syllable replayed before the next set. The child sees the answer promptly [15] and cannot guess through all four (answering until correct was no better than being told: Butler, Karpicke and Roediger 2007, existing note).
- **Build it (format c, changed):** play the whole word without printing it (for 6 to 9 at the lowest rungs, allow the printed model first and fade it, as the print-fading rule already does). For each slot the four lanes hold the correct syllable, one or two of the word's other syllables (order), and one or two similar foils of the kinds the player is learning (mapping), so the last slot is still a real choice. For 10 and over, include affix slots with F9 foils, following the pick-the-prefix task [58] and Lovett's peeling-off strategy [37].
- **Read it whole:** when the last slot fills, the slots slide together into one unbroken lower-case word, held silently for about 1.5 s (children) or 1 s (adults) so the player can read it; then the word plays. No hyphens or dots. The word returns after two and four other words, as now.
- **Speed check (10 and over):** a whole word appears briefly, the player presses when it is read, then picks which of four heard-and-shown words it was. Practice plus a fluency measure [56][58]; not claimed to improve reading.

### 6.3 How foils progress

- **Per contrast, not one global rung.** A small state for each confusion family (vowels, onsets and clusters, codas, reversible letters, letter order, syllable order, affixes). A new family starts with its target among unrelated or already-mastered foils, then one similar foil, then two, then three; step up after 3 unaided correct first presses in that family, step back after an error. (Moderate for easy-to-hard [4][9][10][12]; weak for the exact rule)
- **Reversible letters (F4) apart first.** b and d on separate words before they appear as each other's foils [4][3]. (Moderate, preschool evidence)
- **Keep the 3-down-1-up staircase for the time limit** (about 79 percent correct); challenge between 60 and 80 percent did not change engagement [74]. (Moderate)
- **Mix families once each is above chance for two sittings** [68][71]. (Moderate)
- **Log the foil chosen on every error** to build a confusion table per player, as GraphoGame's developers describe for adaptive confusability estimates [62]. (Weak for the adaptation; the logging costs nothing)

### 6.4 Presentation rules

1. Lower case, an ordinary sans-serif, upright, no italics; bold only for emphasis [83][95]. (Moderate for font style; guideline for the rest)
2. Letter spacing about 0.35 of the average letter width in tiles [85][95]. (Moderate)
3. Dark grey or near-black text on warm off-white or cream; no red or green carrying meaning [82][95]. (Weak)
4. Tile text well above the critical print size: at least 0.5 degrees x-height, larger for children [86][87]. (Moderate)
5. Four tiles, one per lane, all visible at once and widely separated [87][17]. (Moderate for spacing; weak for showing all at once)
6. Tiles drop into place quickly, then stay still; the time limit shows as a shrinking bar [90][91][93]. (Weak: design inference)
7. Syllable boundaries shown by slot gaps while building; the finished word shown whole, with no hyphens or dots [79][80][81]. (Moderate, Finnish evidence)
8. Alternating syllable colours only in the building strip for 6 to 9 at low rungs, faded out; never in the finished word [76][78]. (Weak)
9. No overlays or tint options offered as help [84][85]. (Strong against overlays)

### 6.5 Voice plan

- **Primary: record one Australian speaker with the existing recording kit.** One adult speaker of general Australian English, clear citation style at a natural rate: each syllable as it sounds in its word, each whole word, each made-up word, and the instructions. Written consent to ship the recordings with the software. A second listener checks a sample against the pronunciation key with a four-option test. Why: no study validates TTS for isolated syllables or pseudowords with children; a person can be told exactly what to say; clear natural speech helps children with learning difficulties [99][100]; an unfamiliar accent costs young children most (existing note). (Moderate)
- **Fallback: Microsoft Azure AI Speech, an en-AU standard neural voice, rendered once offline.** SSML with an IPA `phoneme` tag for every syllable and made-up word, generated from the bank's pronunciation key, and a PLS lexicon for real words the voice misreads [110][111]. Choose the voice by a listening test with the kit's four-option check (Natasha or William, for example; no study ranks them). Keep the SSML with the files, record voice, date and terms read in the manifest, check the current Azure terms before release, and say in the app that the voice is synthetic [113]. Why Azure: the largest set of en-AU neural voices with phoneme and lexicon support [110][111], and output that is the customer's [112]. Google Chirp 3 HD with custom IPA pronunciations is a close second [115][117]; Polly has one neural en-AU voice [118]; ElevenLabs supports phoneme tags on one model only and limits free use to non-commercial [121][122]. (Weak to moderate: terms read, voices not tested)
- **Keep Kokoro bf_emma as the development fallback** until the files are replaced (existing note).
- **Audio handling for every route:** clear style; no time-stretching; a short gap between modelled syllables, with the extra time before and after words; one replay per set; words normalised to one integrated loudness and short syllable files matched by RMS within 1 dB, true peak no higher than -1 dBTP [125]; headphone level for children at or below about 75 dBA [124]; a quiet room or closed headphones [126]. (Weak for the numbers; moderate for quiet listening [99])

### 6.6 What to measure

- **In the game** (describes play; proves nothing about reading): first-press accuracy per confusion family and foil kind, response time from audio onset, prompt and replay use, the confusion table [62], words per sitting, sittings played vs scheduled, early quits [23][74].
- **Transfer inside the game format:** untrained real words and made-up words built from trained syllables, read aloud to the adult and timed [56].
- **Outside the game:** a standardised word and nonword reading test and a spelling test before and after (for Australian children, the Castles and Coltheart 2 test in the existing note), with a comparison group, because untrained dyslexic children also improve over the same period [93] and in-game gains often fail to transfer [27][30].
- **Report the dose received** in hours, not the dose planned [23][58].

### 6.7 Recommendations ranked by strength of evidence

1. Keep a print-linked task with a right answer, and add production steps (build/spell and read it whole). **Strong** [29][42][43][54] (Galuschka 2014, existing note)
2. Plan 10 to 15 hours over 8 to 12 weeks, several short sittings a week, an adult present. **Strong to moderate** [40][54][23] (McTigue 2020, existing note)
3. Similar foils as the teaching format, with the right answer shown promptly after an error. **Moderate** [13][14][15][16]
4. Measure transfer with standardised tests and a comparison group; do not claim in-game gains as reading gains. **Moderate** [23][27][30][93]
5. Order sections review, accuracy, production, speed; block formats and mix items. **Moderate** [58][60][68][71][75]
6. Each contrast easy-to-hard, confusable pairs apart first. **Moderate** [4][9][10][12]
7. Show the finished word whole and let the player read it before the audio. **Moderate** [96][97][98]
8. No hyphens or dots in words; boundaries by slot gaps. **Moderate** [79][80][81]
9. Clear, natural-rate speech; no stretching; extra time between items. **Moderate** [99][100][101][102]
10. Record an Australian speaker; fall back to Azure en-AU with IPA phoneme tags. **Moderate to weak** [99][110][111][112]
11. Sans-serif, 0.35 letter spacing, large tiles, warm off-white background. **Moderate to weak** [82][83][85][86][95]
12. Tiles still while being read, time shown by a bar. **Weak** [90][91][93]
13. Optional syllable colours for the youngest, faded out. **Weak** [76][78]
14. The exact section lengths and item counts in 6.1. **Weak** (design choices inside studied ranges)

---

### 6.8 As built (30 September 2026)

Built into the game, on by default (`syllables.sections: true`), for every age profile except classic:

- The sitting runs in parts, each opened by a card: review (up to 4 words, unrelated foils, moves no ladder), hear and pick, build the word, and for 10 to 59 a quick look speed check. From the block's words, 30 percent of those after the review are built.
- Foils come from one confusion family at a time. Each family has a level (0 to 3 similar foils in the set), up after 3 unaided right first presses and down after an error, mastered at level 3. A family is taught for 3 words, then the next open one takes over. The rung staircase still sets the time allowed.
- Tiles drop into place in 0.2 s and stay still, with a shrinking time bar. Two wrong presses show the answer; a set that times out is shown the same way. A word with a shown slot counts as missed and returns after two and four words.
- Every word ends whole: the slots close into one word, held silent for 1.5 s (1.0 s for adults), then it is heard.
- Build words are heard and not printed from 10 up (6 to 9 keep the printed model while their print rung allows it). Each slot's lanes hold one of the word's other syllables and family foils. R replays the whole word while building.
- Speed check: a real word of up to 9 letters is flashed, masked by hash marks for 150 ms, then four words of the same syllable count sit over the fingers for up to 4 s. The exposure starts at 700, 600 or 500 ms (10 to 12, 13 to 15, 16 and over), goes down 80 ms after each right answer until the first error, then runs 3-down-1-up between 100 ms and 1.5 s. 16 trials for 10 to 15, 20 for 16 to 59. EEG code 53 marks the four words.
- Warm off-white page on the light theme, letter spacing 0.35 of the average letter width, one font size for all four tiles of a set.

Not built, or changed from the proposal:

- The speed check does not ask for a press when the word is read; the pick from four words is the only response, timed from the four words.
- Family levels restart at 0 in every block; carrying them across sittings, and reviewing words from earlier sittings, needs a per-reader store the game does not have.
- No alternating syllable colours in the building strip, no finish screen with one thing to practise, and no affix-only slots.
- The voice is still Kokoro bf_emma; recording an Australian speaker or rendering Azure en-AU is the developer's decision (Section 6.5).
- The section sizes follow the configured block length (30 words by default), so a sitting has more pick and build words than the counts in Section 6.1.

## 7. Sources

Sources marked "existing note" in the text are listed and verified in `syllables-dyslexia-rework.md` and `syllables-all-ages.md`.

**Question 1: task format**

1. Terrace HS (1963). Discrimination learning with and without "errors". *Journal of the Experimental Analysis of Behavior* 6, 1-27. doi:10.1901/jeab.1963.6-1. PMID 13980667. AB.
2. Terrace HS (1963). Errorless transfer of a discrimination across two continua. *Journal of the Experimental Analysis of Behavior* 6, 223-232. doi:10.1901/jeab.1963.6-223. PMID 13980669. AB.
3. Carnine DW (1976). Similar sound separation and cumulative introduction in learning letter-sound correspondences. *Journal of Educational Research* 69(10), 368-372. doi:10.1080/00220671.1976.10884928. ERIC EJ150782. AB (brief).
4. Carnine DW (1981). Reducing training problems associated with visually and auditorily similar correspondences. *Journal of Learning Disabilities* 14(5), 276-279. doi:10.1177/002221948101400510. ERIC EJ247206. AB.
5. Carnine D (1980). Three procedures for presenting minimally different positive and negative instances. *Journal of Educational Psychology* 72(4), 452-456. doi:10.1037/0022-0663.72.4.452. ERIC EJ235503. AB.
6. Warmington M, Hitch GJ, Gathercole SE (2013). Improving word learning in children using an errorless technique. *Journal of Experimental Child Psychology* 114(3), 456-465. doi:10.1016/j.jecp.2012.10.007. PMID 23201155. AB.
7. Carneiro P, Lapa A, Finn B (2018). The effect of unsuccessful retrieval on children's subsequent learning. *Journal of Experimental Child Psychology* 166, 400-420. doi:10.1016/j.jecp.2017.09.010. PMID 29032207. AB.
8. Waller M, Yurovsky D, Nozari N (2024). Of mouses and mans: a test of errorless versus error-based learning in children. *Cognitive Science* 48(11), e70006. doi:10.1111/cogs.70006. PMID 39467041. AB.
9. Ahissar M, Hochstein S (1997). Task difficulty and the specificity of perceptual learning. *Nature* 387, 401-406. doi:10.1038/387401a0. PMID 9163425. AB.
10. McCandliss BD, Fiez JA, Protopapas A, Conway M, McClelland JL (2002). Success and failure in teaching the [r]-[l] contrast to Japanese adults: tests of a Hebbian model of plasticity and stabilization in spoken language perception. *Cognitive, Affective, & Behavioral Neuroscience* 2(2), 89-108. doi:10.3758/CABN.2.2.89. PMID 12455678. AB.
11. Pashler H, Mozer MC (2013). When does fading enhance perceptual category learning? *Journal of Experimental Psychology: Learning, Memory, and Cognition* 39(4), 1162-1173. doi:10.1037/a0031679. PMID 23421513. AB.
12. Church BA, Mercado E, Wisniewski MG, Liu EH (2013). Temporal dynamics in auditory perceptual learning: impact of sequencing and incidental learning. *Journal of Experimental Psychology: Learning, Memory, and Cognition* 39(1), 270-276. doi:10.1037/a0028647. PMID 22642235. AB.
13. Little JL, Bjork EL, Bjork RA, Angello G (2012). Multiple-choice tests exonerated, at least of some charges: fostering test-induced learning and avoiding test-induced forgetting. *Psychological Science* 23(11), 1337-1344. doi:10.1177/0956797612443370. PMID 23034566. AB.
14. Little JL, Bjork EL (2015). Optimizing multiple-choice tests as tools for learning. *Memory & Cognition* 43(1), 14-26. doi:10.3758/s13421-014-0452-8. PMID 25123774. AB.
15. Marsh EJ, Fazio LK, Goswick AE (2012). Memorial consequences of testing school-aged children. *Memory* 20(8), 899-906. doi:10.1080/09658211.2012.708757. PMID 22891857. AB; re-checked 30 September 2026.
16. McCandliss B, Beck IL, Sandak R, Perfetti C (2003). Focusing attention on decoding for children with poor reading skills: design and preliminary tests of the Word Building intervention. *Scientific Studies of Reading* 7(1), 75-104. doi:10.1207/S1532799XSSR0701_05. ERIC EJ672809. AB (sample size not confirmed).
17. Mundy ME, Honey RC, Dwyer DM (2007). Simultaneous presentation of similar stimuli produces perceptual learning in human picture processing. *Journal of Experimental Psychology: Animal Behavior Processes* 33(2), 124-138. doi:10.1037/0097-7403.33.2.124. PMID 17469961. AB.
18. Ecalle J, Magnan A (2016). Quels types d'interventions pour réduire les difficultés en lecture? Conférence de consensus Lire, comprendre, apprendre, CNESCO and IFÉ. https://www.cnesco.fr/wp-content/uploads/2018/04/10-Ecalle-Magnan.pdf. FT.
19. Ecalle J, Kleinsz N, Magnan A (2013). Computer-assisted learning in young poor readers: the effect of grapho-syllabic training on the development of word reading and reading comprehension. *Computers in Human Behavior* 29(4), 1368-1376. doi:10.1016/j.chb.2013.01.041. MD (findings from [18]).
20. Ecalle J, Magnan A, Calmus C (2009). Lasting effects on literacy skills with a computer-assisted learning using syllabic units in low-progress readers. *Computers & Education* 52(3), 554-561. doi:10.1016/j.compedu.2008.10.010. MD (design from [18]).
21. Ecalle J, Magnan A, Bouchafa H, Gombert JE (2009). Computer-based training with ortho-phonological units in dyslexic children: new investigations. *Dyslexia* 15(3), 218-238. doi:10.1002/dys.373. PMID 18646049. AB.
22. Kyle F, Kujala J, Richardson U, Lyytinen H, Goswami U (2013). Assessing the effectiveness of two theoretically motivated computer-assisted reading interventions in the United Kingdom: GG Rime and GG Phoneme. *Reading Research Quarterly* 48(1), 61-76. doi:10.1002/rrq.038. AB (design and effect sizes from [23]).
23. Worth J, Nelson J, Harland J, Bernardinelli D, Styles B (2018). *GraphoGame Rime: evaluation report and executive summary.* Education Endowment Foundation and NFER. https://www.nfer.ac.uk/media/idlhbicn/graphogame_rime_evaluation_report_and_executive_summary.pdf. FT (pages 1 to 12); re-checked 30 September 2026.
24. Ahmed H, Wilson A, Mead N, Noble H, Richardson U, Wolpert MA, Goswami U (2020). An evaluation of the efficacy of GraphoGame Rime for promoting English phonics knowledge in poor readers. *Frontiers in Education* 5, 132. doi:10.3389/feduc.2020.00132. AB.
25. Bishop DVM, Hulme C (2024). When alternative analyses of the same data come to different conclusions: a tutorial using DeclareDesign with a worked real-world example. *Advances in Methods and Practices in Psychological Science* 7(3). doi:10.1177/25152459241267904. AB; re-checked 30 September 2026.
26. Lassault J, Sprenger-Charolles L, Albrand J-P, Alavoine E, Richardson U, Lyytinen H, Ziegler JC (2022). Testing the effects of GraphoGame against a computer-assisted math intervention in primary school. *Scientific Studies of Reading* 26(6), 449-468. doi:10.1080/10888438.2022.2052884. ERIC EJ1370152. AB.
27. Patel P, Torppa M, Aro M, Richardson U, Lyytinen H (2022). Assessing the effectiveness of a game-based phonics intervention for first and second grade English language learners in India: a randomized controlled trial. *Journal of Computer Assisted Learning* 38(1), 76-89. doi:10.1111/jcal.12592. AB.
28. O'Brien BA, Habib M, Onnis L (2019). Technology-based tools for English literacy intervention: examining intervention grain size and individual differences. *Frontiers in Psychology* 10, 2625. doi:10.3389/fpsyg.2019.02625. PMID 31849754. AB.
29. McArthur G, Sheehan Y, Badcock NA, Francis DA, Wang H-C, Kohnen S, Banales E, Anandakumar T, Marinus E, Castles A (2018). Phonics training for English-speaking poor readers. *Cochrane Database of Systematic Reviews* 11, CD009115. doi:10.1002/14651858.CD009115.pub3. PMID 30480759. AB; re-checked 30 September 2026.
30. Neitzel AJ, Lake C, Pellegrini M, Slavin RE (2022). A synthesis of quantitative research on programs for struggling readers in elementary schools. *Reading Research Quarterly* 57(1), 149-179. doi:10.1002/rrq.379. ERIC EJ1325761. AB.
31. Archer AL, Gleason MM, Vachon VL (2003). Decoding and fluency: foundation skills for struggling older readers. *Learning Disability Quarterly* 26(2), 89-101. doi:10.2307/1593592. AB.
32. Shippen ME, Houchins DE, Steventon C, Sartor D (2005). A comparison of two direct instruction reading programs for urban middle school students. *Remedial and Special Education* 26(3), 175-182. doi:10.1177/07419325050260030501. AB.
33. Lovett MW, Borden SL, DeLuca T, Lacerenza L, Benson NJ, Brackstone D (1994). Treating the core deficits of developmental dyslexia: evidence of transfer of learning after phonologically- and strategy-based reading training programs. *Developmental Psychology* 30(6), 805-822. doi:10.1037/0012-1649.30.6.805. ERIC EJ498078. AB.
34. Lovett MW, Steinbach KA (1997). The effectiveness of remedial programs for reading disabled children of different ages: does the benefit decrease for older children? *Learning Disability Quarterly* 20(3), 189-210. doi:10.2307/1511308. ERIC EJ556903. AB.
35. Lovett MW, Lacerenza L, Borden SL (2000). Putting struggling readers on the PHAST track: a program to integrate phonological and strategy-based remedial reading instruction and maximize outcomes. *Journal of Learning Disabilities* 33(5), 458-476. doi:10.1177/002221940003300507. AB.
36. Lovett MW, Lacerenza L, De Palma M, Frijters JC (2012). Evaluating the efficacy of remediation for struggling readers in high school. *Journal of Learning Disabilities* 45(2), 151-169. doi:10.1177/0022219410371678. ERIC EJ954838. AB.
37. LD@School (2015, 30 July). WIST program: a strategy to improve orthographic memory in students with reading disabilities. https://www.ldatschool.ca/wist-program/. FT (summary).
38. Kearns DM, Whaley VM (2019). Helping students with dyslexia read long words: using syllables and morphemes. *TEACHING Exceptional Children* 51(3), 212-225. doi:10.1177/0040059918810010. MD.
39. Toste JR, Capin P, Vaughn S, Roberts GJ, Kearns DM (2017). Multisyllabic word-reading instruction with and without motivational beliefs training for struggling readers in the upper elementary grades: a pilot investigation. *Elementary School Journal* 117(4), 593-615. doi:10.1086/691684. ERIC EJ1143665. AB.
40. Boucher AN, Bhat BH, Clemens NH, Vaughn S, O'Donnell K (2024). Reading interventions for students in grades 3-12 with significant word reading difficulties. *Journal of Learning Disabilities* 57(4), 203-223. doi:10.1177/00222194231207556. PMID 37937699. AB.
41. Fry E (2025, 9 June). *A systematic review of literature on multisyllabic word reading interventions for students in grades 4-9.* Kentucky Reading Research Center, University of Louisville. https://www.kyreadingresearch.org/wp-content/uploads/2025/06/Adolescent-Multisyllabic-Word-Reading-Interventions.pdf. FT (pages 1 to 13). Not peer reviewed.
42. Galuschka K, Görgen R, Kalmar J, Haberstroh S, Schmalz X, Schulte-Körne G (2020). Effectiveness of spelling interventions for learners with dyslexia: a meta-analysis and systematic review. *Educational Psychologist* 55(1), 1-20. doi:10.1080/00461520.2019.1659794. ERIC EJ1241982. AB.
43. Weiser B, Mathes P (2011). Using encoding instruction to improve the reading and spelling performances of elementary students at risk for literacy difficulties: a best-evidence synthesis. *Review of Educational Research* 81(2), 170-200. doi:10.3102/0034654310396719. AB.
44. Conrad NJ (2008). From reading to spelling and spelling to reading: transfer goes both ways. *Journal of Educational Psychology* 100(4), 869-878. doi:10.1037/a0012544. ERIC EJ823717. AB.
45. Shahar-Yames D, Share DL (2008). Spelling as a self-teaching mechanism in orthographic learning. *Journal of Research in Reading* 31(1), 22-39. doi:10.1111/j.1467-9817.2007.00359.x. AB.
46. Seiler A, Leitão S, Blosfelds M (2019). WordDriver-1: evaluating the efficacy of an app-supported decoding intervention for children with reading impairment. *International Journal of Language & Communication Disorders* 54(2), 189-202. doi:10.1111/1460-6984.12388. PMID 29691983. AB.
47. Flaugnacco E, Lopez L, Terribili C, Montico M, Zoia S, Schön D (2015). Music training increases phonological awareness and reading skills in developmental dyslexia: a randomized control trial. *PLOS ONE* 10(9), e0138715. doi:10.1371/journal.pone.0138715. PMID 26407242. AB.
48. Bhide A, Power A, Goswami U (2013). A rhythmic musical intervention for poor readers: a comparison of efficacy with a letter-based intervention. *Mind, Brain, and Education* 7(2), 113-123. doi:10.1111/mbe.12016. ERIC EJ1009592. AB (sample and design from [23]).
49. Thomson JM, Leong V, Goswami U (2013). Auditory processing interventions and developmental dyslexia: a comparison of phonemic and rhythmic approaches. *Reading and Writing* 26(2), 139-161. doi:10.1007/s11145-012-9359-6. ERIC EJ998193. AB.
50. Gordon RL, Fehd HM, McCandliss BD (2015). Does music training enhance literacy skills? A meta-analysis. *Frontiers in Psychology* 6, 1777. doi:10.3389/fpsyg.2015.01777. PMID 26648880. AB.
51. Cogo-Moreira H, Andriolo RB, Yazigi L, Ploubidis GB, Brandão de Ávila CR, Mari JJ (2012). Music education for improving reading skills in children and adolescents with dyslexia. *Cochrane Database of Systematic Reviews* CD009133. doi:10.1002/14651858.CD009133.pub2. PMID 22895983. AB.
52. Sala G, Gobet F (2020). Cognitive and academic benefits of music training with children: a multilevel meta-analysis. *Memory & Cognition* 48(8), 1429-1441. doi:10.3758/s13421-020-01060-2. PMID 32728850. AB.
53. Román-Caballero R, Vadillo MA, Trainor LJ, Lupiáñez J (2022). Please don't stop the music: a meta-analysis of the cognitive and academic benefits of instrumental musical training in childhood and adolescence. *Educational Research Review* 35, 100436. doi:10.1016/j.edurev.2022.100436. MD.
54. Ehri LC, Nunes SR, Willows DM, Schuster BV, Yaghoub-Zadeh Z, Shanahan T (2001). Phonemic awareness instruction helps children learn to read: evidence from the National Reading Panel's meta-analysis. *Reading Research Quarterly* 36(3), 250-287. doi:10.1598/RRQ.36.3.2. AB.
55. Ehri LC, Nunes SR, Stahl SA, Willows DM (2001). Systematic phonics instruction helps students learn to read: evidence from the National Reading Panel's meta-analysis. *Review of Educational Research* 71(3), 393-447. doi:10.3102/00346543071003393. AB.
56. Huemer S, Aro M, Landerl K, Lyytinen H (2010). Repeated reading of syllables among Finnish-speaking children with poor reading skills. *Scientific Studies of Reading* 14(4), 317-340. doi:10.1080/10888430903150659. ERIC EJ893273. AB.
57. Huemer S, Landerl K, Aro M, Lyytinen H (2008). Training reading fluency among poor readers of German: many ways to the goal. *Annals of Dyslexia* 58(2), 115-137. doi:10.1007/s11881-008-0017-2. PMID 18777137. AB.
58. Heß J, Karageorgos P, Müller B, Riedmann A, Schaper P, Lugrin B, Richter T (2024). Improving word reading skills of low-skilled readers: an intervention combining a syllable-based approach with digital game-based features. *Journal of Computer Assisted Learning* 40(5), 2306-2324. doi:10.1111/jcal.13021. FT (pages 2308 to 2318; open-access copy at opus.bibliothek.uni-wuerzburg.de).
59. Müller B, Richter T, Karageorgos P (2020). Syllable-based reading improvement: effects on word reading and reading comprehension in Grade 2. *Learning and Instruction* 66, 101304. doi:10.1016/j.learninstruc.2020.101304. AB.
60. Müller B, Richter T, Karageorgos P, Krawietz S, Ennemoser M (2017). Effects of a syllable-based reading intervention in poor-reading fourth graders. *Frontiers in Psychology* 8, 1635. doi:10.3389/fpsyg.2017.01635. FT (summary) (existing note, spelt Mueller there).
61. Görgen R, Huemer S, Schulte-Körne G, Moll K (2020). Evaluation of a digital game-based reading training for German children with reading disorder. *Computers & Education* 150, 103834. doi:10.1016/j.compedu.2020.103834. MD (finding as reported in [58]).
62. Kujala JV, Richardson U, Lyytinen H (2010). Estimation and visualization of confusability matrices from adaptive measurement data. *Journal of Mathematical Psychology* 54(1), 196-207. doi:10.1016/j.jmp.2008.05.007. MD.

**Question 2: structure**

63. Seabrook R, Brown GDA, Solity JE (2005). Distributed and massed practice: from laboratory to classroom. *Applied Cognitive Psychology* 19(1), 107-122. doi:10.1002/acp.1066. FT (summary page and Experiment 3).
64. Denton CA, Cirino PT, Barth AE, Romain M, Vaughn S, Wexler J, Francis DJ, Fletcher JM (2011). An experimental study of scheduling and duration of "Tier 2" first-grade reading intervention. *Journal of Research on Educational Effectiveness* 4(3), 208-230. doi:10.1080/19345747.2010.530127. PMID 21796271. AB.
65. Suggate SP (2010). Why what we teach depends on when: grade and reading intervention modality moderate effect size. *Developmental Psychology* 46(6), 1556-1579. doi:10.1037/a0020612. PMID 20873927. AB.
66. Suggate SP (2016). A meta-analysis of the long-term effects of phonemic awareness, phonics, fluency, and reading comprehension interventions. *Journal of Learning Disabilities* 49(1), 77-96. doi:10.1177/0022219414528540. PMID 24704662. AB.
67. Wanzek J, Vaughn S (2007). Research-based implications from extensive early reading interventions. *School Psychology Review* 36(4), 541-561. doi:10.1080/02796015.2007.12087917. ERIC EJ788353. AB.
68. Brunmair M, Richter T (2019). Similarity matters: a meta-analysis of interleaved learning and its moderators. *Psychological Bulletin* 145(11), 1029-1052. doi:10.1037/bul0000209. PMID 31556629. AB; re-checked 30 September 2026.
69. Taylor K, Rohrer D (2010). The effects of interleaved practice. *Applied Cognitive Psychology* 24(6), 837-848. doi:10.1002/acp.1598. AB.
70. Rohrer D, Dedrick RF, Hartwig MK, Cheung C-N (2020). A randomized controlled trial of interleaved mathematics practice. *Journal of Educational Psychology* 112(1), 40-52. doi:10.1037/edu0000367. ERIC EJ1237752. AB.
71. Klimovich M, Richter T (2025). Spelling acquisition in children through interleaved practice: the role of instructional guidance. *Cognitive Research: Principles and Implications* 10(1), 68. doi:10.1186/s41235-025-00680-z. PMID 41065883. AB.
72. Dong X, He X, Fang L, Xing Q, Ren R (2025). Learning natural categories: effects of interleaving practice in children and young adults. *Journal of Intelligence* 13(9), 107. doi:10.3390/jintelligence13090107. PMID 41003247. AB.
73. Booth JN, Boyle JME, Kelly SW (2010). Do tasks make a difference? Accounting for heterogeneity of performance of children with reading difficulties on tasks of executive function: findings from a meta-analysis. *British Journal of Developmental Psychology* 28(1), 133-176. doi:10.1348/026151009X485432. PMID 20306629. AB.
74. Ronimus M, Kujala J, Tolvanen A, Lyytinen H (2014). Children's engagement during digital game-based learning of reading: the effects of time, rewards, and challenge. *Computers & Education* 71, 237-246. doi:10.1016/j.compedu.2013.10.008. MD (findings from the GraphoLearn blog summary of 14 January 2014; no abstract available from Crossref or Semantic Scholar).
75. Rosenshine B (2012). Principles of instruction: research-based strategies that all teachers should know. *American Educator* (ERIC EJ971753); condensed in *Education Digest* (ERIC EJ1002984). AB. Practitioner synthesis, not a trial.

**Question 3: presentation**

76. Pinna B, Deiana K (2018). On the role of color in reading and comprehension tasks in dyslexic children and adults. *i-Perception* 9(3). doi:10.1177/2041669518779098. PMID 35145618. FT (summary).
77. Perea M, Wang X (2017). Do alternating-color words facilitate reading aloud text in Chinese? Evidence with developing and adult readers. *Memory & Cognition* 45(7), 1160-1170. doi:10.3758/s13421-017-0717-0. PMID 28608193. AB.
78. De Simone E, Moll K, Feldmann L, Schmalz X, Beyersmann E (2023). The role of syllables and morphemes in silent reading: an eye-tracking study. *Quarterly Journal of Experimental Psychology* 76(11), 2493-2513. doi:10.1177/17470218231160638. PMID 36803303. AB.
79. Häikiö T, Bertram R, Hyönä J (2016). The hyphen as a syllabification cue in reading bisyllabic and multisyllabic words among Finnish 1st and 2nd graders. *Reading and Writing* 29(1), 159-182. doi:10.1007/s11145-015-9584-x. ERIC EJ1087269. AB.
80. Häikiö T, Heikkilä TT, Kaakinen JK (2018). The effect of syllable-level hyphenation on reading comprehension: evidence from eye movements. *Journal of Educational Psychology* 110(8), 1149-1159. doi:10.1037/edu0000261. ERIC EJ1195591. AB.
81. Häikiö T, Luotojärvi T (2022). The effect of syllable-level hyphenation on novel word reading in early Finnish readers: evidence from eye movements. *Scientific Studies of Reading* 26(1), 38-46. doi:10.1080/10888438.2021.1874384. ERIC EJ1328252. AB.
82. Rello L, Bigham JP (2017). Good background colors for readers: a study of people with and without dyslexia. *Proceedings of ASSETS '17*, 72-80. doi:10.1145/3132525.3132546. FT (pages 1 to 5, author copy at cs.cmu.edu).
83. Rello L, Baeza-Yates R (2016). The effect of font type on screen readability by people with dyslexia. *ACM Transactions on Accessible Computing* 8(4), article 15. doi:10.1145/2897736. FT (pages 1 and 2).
84. Griffiths PG, Taylor RH, Henderson LM, Barrett BT (2016). The effect of coloured overlays and lenses on reading: a systematic review of the literature. *Ophthalmic and Physiological Optics* 36(5), 519-544. doi:10.1111/opo.12316. PMID 27580753. AB.
85. Stagg SD, Kiss N (2021). Room to read: the effect of extra-large letter spacing and coloured overlays on reading speed and accuracy in adolescents with dyslexia. *Research in Developmental Disabilities* 119, 104065. doi:10.1016/j.ridd.2021.104065. PMID 34600780. AB.
86. O'Brien BA, Mansfield JS, Legge GE (2005). The effect of print size on reading speed in dyslexia. *Journal of Research in Reading* 28(3), 332-349. doi:10.1111/j.1467-9817.2005.00273.x. ERIC EJ694319. AB.
87. Martelli M, Di Filippo G, Spinelli D, Zoccolotti P (2009). Crowding, reading, and developmental dyslexia. *Journal of Vision* 9(4), 14. doi:10.1167/9.4.14. PMID 19757923. AB.
88. Bosse M-L, Tainturier MJ, Valdois S (2007). Developmental dyslexia: the visual attention span deficit hypothesis. *Cognition* 104(2), 198-230. doi:10.1016/j.cognition.2006.05.009. PMID 16859667. AB.
89. Ziegler JC, Pech-Georgel C, Dufau S, Grainger J (2010). Rapid processing of letters, digits and symbols: what purely visual-attentional deficit in developmental dyslexia? *Developmental Science* 13(4), F8-F14. doi:10.1111/j.1467-7687.2010.00983.x. PMID 20590718. AB.
90. Benassi M, Simonelli L, Giovagnoli S, Bolzani R (2010). Coherence motion perception in developmental dyslexia: a meta-analysis of behavioral studies. *Dyslexia* 16(4), 341-357. doi:10.1002/dys.412. PMID 20957687. AB.
91. Olulade OA, Napoliello EM, Eden GF (2013). Abnormal visual motion processing is not a cause of dyslexia. *Neuron* 79(1), 180-190. doi:10.1016/j.neuron.2013.05.002. PMID 23746630. AB.
92. Franceschini S, Gori S, Ruffino M, Viola S, Molteni M, Facoetti A (2013). Action video games make dyslexic children read better. *Current Biology* 23(6), 462-466. doi:10.1016/j.cub.2013.01.044. PMID 23453956. AB.
93. Łuniewska M, Chyl K, Dębska A, Kacprzak A, Plewko J, Szczerbiński M, Szewczyk J, Grabowska A, Jednoróg K (2018). Neither action nor phonological video games make dyslexic children read better. *Scientific Reports* 8, 549. doi:10.1038/s41598-017-18878-7. PMID 29323179. AB.
94. Peters JL, De Losa L, Bavin EL, Crewther SG (2019). Efficacy of dynamic visuo-attentional interventions for reading in dyslexic and neurotypical children: a systematic review. *Neuroscience & Biobehavioral Reviews* 100, 58-76. doi:10.1016/j.neubiorev.2019.02.015. PMID 30802473. AB.
95. British Dyslexia Association (2023). *Dyslexia Style Guide 2023.* The official URL returned "access denied" on 30 September 2026; read in full from a copy at https://lbhfinspirehub.com/wp-content/uploads/2024/05/BDA-Style-Guide-2023.pdf. FT (3 pages).
96. Share DL (1999). Phonological recoding and orthographic learning: a direct test of the self-teaching hypothesis. *Journal of Experimental Child Psychology* 72(2), 95-129. doi:10.1006/jecp.1998.2481. PMID 9927525. AB; re-checked 30 September 2026.
97. Kyte CS, Johnson CJ (2006). The role of phonological recoding in orthographic learning. *Journal of Experimental Child Psychology* 93(2), 166-185. doi:10.1016/j.jecp.2005.09.003. PMID 16246358. AB.
98. Ehri LC, Saltmarsh J (1995). Beginning readers outperform older disabled readers in learning to read words by sight. *Reading and Writing* 7(3), 295-326. doi:10.1007/BF03162082. ERIC EJ537340. AB.

**Question 4: voice**

99. Bradlow AR, Kraus N, Hayes E (2003). Speaking clearly for children with learning disabilities: sentence perception in noise. *Journal of Speech, Language, and Hearing Research* 46(1), 80-97. doi:10.1044/1092-4388(2003/007). PMID 12647890. AB; re-checked 30 September 2026.
100. Krause JC, Braida LD (2002). Investigating alternative forms of clear speech: the effects of speaking rate and speaking mode on intelligibility. *Journal of the Acoustical Society of America* 112(5), 2165-2172. doi:10.1121/1.1509432. PMID 12430828. AB.
101. Uchanski RM, Choi SS, Braida LD, Reed CM, Durlach NI (1996). Speaking clearly for the hard of hearing IV: further studies of the role of speaking rate. *Journal of Speech and Hearing Research* 39(3), 494-509. doi:10.1044/jshr.3903.494. PMID 8783129. AB.
102. Montgomery J (2004). Sentence comprehension in children with specific language impairment: effects of input rate and phonological working memory. *International Journal of Language & Communication Disorders* 39(1), 115-133. doi:10.1080/13682820310001616985. PMID 14660189. AB.
103. Montgomery JW (2005). Effects of input rate and age on the real-time language processing of children with specific language impairment. *International Journal of Language & Communication Disorders* 40(2), 171-188. doi:10.1080/13682820400011069. PMID 16101273. AB.
104. Abbott N, Nip I, Love T (2024). Rate of speech affects the comprehension of pronouns in children with developmental language disorder. *Frontiers in Language Sciences* 3, 1394742. doi:10.3389/flang.2024.1394742. PMID 39268499. AB.
105. Aoki NB, Cohn M, Zellou G (2022). The clear speech intelligibility benefit for text-to-speech voices: effects of speaking style and visual guise. *JASA Express Letters* 2(4), 045204. doi:10.1121/10.0010274. PMID 36154231. AB.
106. Yang Y, Nguyen D, Chen K, Zeng F-G (2025). Evaluating synthesized speech intelligibility in noise. *JASA Express Letters* 5(4), 045202. doi:10.1121/10.0036397. PMID 40243623. AB.
107. Vojtech JM, Noordzij JP, Cler GJ, Stepp CE (2019). The effects of modulating fundamental frequency and speech rate on the intelligibility, communication efficiency, and perceived naturalness of synthetic speech. *American Journal of Speech-Language Pathology* 28(2S), 875-886. doi:10.1044/2019_AJSLP-MSC18-18-0052. PMID 31306599. AB.
108. Whitten A, Key AP, Mefferd AS, Bodfish JW (2020). Auditory event-related potentials index faster processing of natural speech but not synthetic speech over nonspeech analogs in children. *Brain and Language* 207, 104825. doi:10.1016/j.bandl.2020.104825. PMID 32563764. AB.
109. Keelor JL, Creaghead NA, Silbert NH, Breit AD, Horowitz-Kraus T (2023). Impact of text-to-speech features on the reading comprehension of children with reading and language difficulties. *Annals of Dyslexia* 73(3), 469-486. doi:10.1007/s11881-023-00281-9. PMID 37119436. AB.
110. Microsoft. Language and voice support for the Speech service, text to speech. https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts (updated 10 September 2026). Read 30 September 2026.
111. Microsoft. Pronunciation with Speech Synthesis Markup Language (SSML). https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-pronunciation (updated 5 June 2026). Read 30 September 2026.
112. Microsoft. Product Terms: Universal License Terms for Online Services. https://www.microsoft.com/licensing/terms/product/ForOnlineServices/EAEAS. Read 30 September 2026 through a fetch summary; no date shown.
113. Microsoft. Code of Conduct for Microsoft AI Services, version 4.0, 1 May 2026. https://learn.microsoft.com/en-us/legal/ai-code-of-conduct. Read 30 September 2026.
114. Google Cloud. Supported voices and languages (Text-to-Speech). https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types. Read 30 September 2026.
115. Google Cloud. Chirp 3: HD voices. https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd (updated 24 September 2026). Read 30 September 2026.
116. Google Cloud. Speech Synthesis Markup Language (SSML). https://docs.cloud.google.com/text-to-speech/docs/ssml (updated 24 September 2026). Read 30 September 2026.
117. Google Cloud. Service Specific Terms (last modified 24 September 2026). https://cloud.google.com/terms/service-terms. Read 30 September 2026.
118. Amazon Web Services. Available voices, Amazon Polly Developer Guide. https://docs.aws.amazon.com/polly/latest/dg/available-voices.html. Read 30 September 2026.
119. Amazon Web Services. Supported SSML tags, Amazon Polly Developer Guide. https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html. Read 30 September 2026.
120. Amazon Web Services. AWS Service Terms (last updated 15 September 2026). https://aws.amazon.com/service-terms/. Read 30 September 2026.
121. ElevenLabs. Terms of Service (non-EEA), last updated 31 March 2026. https://elevenlabs.io/terms-of-use. Read 30 September 2026.
122. ElevenLabs. Controls: phoneme tags and pronunciation dictionaries. https://elevenlabs.io/docs/best-practices/prompting/controls. Read 30 September 2026.
123. Hugging Face model metadata, read 30 September 2026: rhasspy/piper-voices (en_GB and en_US only); myshell-ai/MeloTTS-English (MIT); myshell-ai/OpenVoiceV2 (MIT; base speaker en-au); hexgrad/Kokoro-82M (Apache-2.0; American and British English only); ResembleAI/chatterbox (MIT); neuphonic/neutts-air (Apache-2.0); coqui/XTTS-v2 (Coqui Public Model License); SWivid/F5-TTS (CC BY-NC 4.0). Licence fields read; licence texts not read in full.
124. ITU-T (2022). Recommendation H.870 (V2): Guidelines for safe listening devices/systems. https://www.itu.int/epublications/publication/itu-t-h-870-v2-2022-03-guidelines-for-safe-listening-devices-systems. MD (mode figures from the WHO-ITU summary).
125. European Broadcasting Union (2023). R 128: Loudness normalisation and permitted maximum level of audio signals, version 5.0. https://tech.ebu.ch/publications/r128. MD.
126. Acoustical Society of America (2010, reaffirmed 2020). ANSI/ASA S12.60 Part 1: Acoustical performance criteria, design requirements, and guidelines for schools. MD. American Speech-Language-Hearing Association. Classroom acoustics, Practice Portal. https://www.asha.org/practice-portal/professional-issues/classroom-acoustics/. Read 30 September 2026.
