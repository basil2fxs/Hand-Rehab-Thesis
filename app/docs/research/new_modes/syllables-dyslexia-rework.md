# Syllables rework: from tapping the beats to picking the chunk

What changed in September 2026, why, and what the change is allowed to
claim. The full research note this was built from lives in the build
lane's scratch (1082 lines, every source checked); this file is the
part the repository needs to keep: the design decisions, the evidence
each one rests on, and the limits that go into the ethics application
and the thesis.

## What the mode was, and what it is now

WAS. A word appeared, its syllables lit left to right at a 2 Hz beat
with one finger buzzing per syllable, and the child tapped the beats
back on a sliding window of adjacent fingers. Six level rungs ran
from counting through beat-paced tapping, stress marking, onset-rime
and phonemes.

IS. The word is heard and seen, its syllables are modelled one at a
time, and then, for each syllable in order, four written chunks fall
slowly down four lanes that sit over the four fingers. One chunk is
the syllable; three are wrong for a reason. The child presses the
finger under the right one, and the word builds up in a strip at the
top. Nothing anywhere says which finger is right.

WHY. Three reasons, in order of weight.

1. Print. For children with a reading disability the only treatment
   family with a confirmed effect in the randomised-trial
   meta-analysis is phonics, print to sound (Galuschka, Ise, Krick and
   Schulte-Koerne 2014, PLOS ONE, g = 0.32 and 0.20 after
   publication-bias correction). The tapping task never showed the
   child a written chunk they had to choose. The two syllable-level
   PRINT studies both worked: Bhattacharya and Ehri (2004) improved
   struggling adolescent readers' decoding of unfamiliar words by
   having them analyse the graphosyllabic units of multisyllabic
   words, where whole-word practice did not; Mueller, Richter,
   Karageorgos, Krawietz and Ennemoser (2017) improved German poor
   readers' single-word reading fluency with syllable-based training.
2. A task with a right answer the child can be wrong about. Tapping a
   count measures whether the child heard three beats. Picking "na"
   out of ba, na, no, an measures whether the child can bind what they
   heard to what is written, which is the deficit the literature keeps
   pointing at (Ziegler and Goswami 2005 on grain size; Aravena,
   Snellings, Tijms and van der Molen 2013 on letter-sound binding
   under time pressure).
3. It is the shape of the one game in this space with a real
   literature. GraphoGame (Richardson and Lyytinen 2014) is
   multiple-choice trials pairing an audio segment with a written
   form, adapted to about 80 percent correct, with immediate positive
   feedback. Copying its shape means the cautions attached to it
   apply, which is the honest position (see LIMITS).

## The design decisions and what each rests on

FOUR OPTIONS, ONE PER FINGER. GraphoGame's own range is one to nine
distractors (Mehringer et al 2020). Four matches the hardware, keeps
chance at a flat 25 percent the analysis can draw as a line, and
avoids the crowding that extra-large letter spacing exists to fight
(Zorzi et al 2012, PNAS: wide spacing improved dyslexic children's
reading on the fly, attributed to crowding).

NOTHING NAMES THE TARGET FINGER. Fitts and Seeger (1953): response
selection is fastest when stimulus and response share a spatial code.
The tile falling in the lane over the finger that answers it IS that
code, and it is the only mapping the child gets. Consequences in the
build: the model's tactile pulse became a four-finger ROLL (a single
buzz would announce the lane before the tiles existed), the option-set
onset goes through the engine's cue path with a `silent_stim` flag so
it arms the force window, the timeout and the EEG marker but fires no
tone, no highlight and no buzzer, all four tiles are drawn identically
in one neutral colour, and the target lane is drawn by a deficit rule
with a random tie-break that also forbids the same lane three sets
running.

TILES FALL SLOWLY. Four-choice reaction time in adults is about 450 to
550 ms before any reading (Hick's law, reviewed in Proctor and
Schneider 2018); children of this age are slower by a factor near 1.5
to 1.8 (Kail 1991); and these children then have to read four chunks
and compare them. So a set is on screen 4.0 s at the entry rung and
never under 2.5 s. The window is a floor for thinking, not a target.

A WRONG PRESS IS QUIET; A MISSED SET IS CORRECTED LATE. GraphoGame
makes the child re-pick the right answer before moving on. This mode
does not: a wrong press greys that one tile, the others keep falling,
and if the set leaves unanswered the right tile glows once on its way
out and the syllable is spoken. The word then comes back after two
other words and again after four. The evidence: delayed feedback beat
immediate feedback in Grade 6 children (Metcalfe, Kornell and Finn
2009); adults with dyslexia were impaired at probabilistic learning
with immediate feedback but not with delayed feedback (Gabay 2021,
following Foerde and Shohamy 2011 on the striatal-to-hippocampal
shift); spaced retrieval beat massed for word learning in children
with language disorder (Leonard and Deevy 2020); and an unsuccessful
retrieval attempt followed by the answer still helps later learning
(Kornell, Hays and Bjork 2009). Positive feedback stays immediate and
loud, because that is what keeps a child playing (Ronimus, Kujala,
Tolvanen and Lyytinen 2014).

TWO DIFFICULTY CLOCKS. The foil rung (1 to 8: how similar the wrong
chunks are, how fast the fall, whether the syllable is spoken again at
spawn) moves by a 3-down-1-up staircase on first-press correctness,
which converges on the 79.4 percent point of the psychometric function
(Levitt 1971) and matches GraphoGame's about-80-percent target. The
word band (A, B, C) keeps the brief's 8-of-the-last-10 / under-5-of-10
rule on word outcomes at round boundaries, so word length moves slowly
and visibly.

THE FOILS ARE THE CONTENT. Each kind is a confusion the literature
names: vowel identity (Ziegler and Goswami 2005 on vowel
inconsistency), onset and coda consonants including cluster
simplification (Bruck and Treiman 1990), reversible letters b/d, p/q,
n/u, m/w (Terepocki, Kruk and Willows 2002), letter position
(Kohnen, Nickels, Castles, Friedmann and McArthur 2012 on migration
errors; Kirkby, Barrington, Drieghe and Liversedge 2025 on transposed
letters), the same word's other syllable (order tracking), and, off by
default, the pseudohomophone spelling. Every foil is checked for
legality before it is shown, and the kind that is LOGGED is the kind
actually produced, so a fallback can never be read as evidence for a
confusion that was never on screen.

HANDS ALTERNATE PER WORD, never within one. Dyslexic children were
worse than controls on asynchronous bimanual tapping but not on
unimanual tapping (Wolff, Michel, Ovrut and Drake 1990). Eight tiles
over eight fingers would double the alternatives and halve chance for
nothing; a mirrored set lets a child play a whole block on the hand
they favour.

LOWER CASE, ORDINARY FONT, WIDE TRACKING. Reversals only exist in
lower case and print is lower case. Special dyslexia fonts do not help
(Wery and Diliberto 2017; Kuster, van Weerdenburg, Gompel and Bosman
2018). Extra letter spacing does (Zorzi et al 2012).

## The word bank

690-odd words of two to four syllables with splits and stress, written
by hand for this project (assets/words/syllables_source.txt, built to
assets/words/syllables_bank.json). Nothing was copied: the Oxford
Wordlist is copyright OUP and the Macquarie convention is a rule, not
data. assets/words/LICENCE.txt records that and the open route
(cmudict, Moby Hyphenator, Kuperman age-of-acquisition, a children's
frequency list) if a bigger bank is ever wanted.

One caution carried into the design: English syllable division in
print is a convention, not a fact. Kearns (2020, Reading Research
Quarterly) analysed 14,844 words from Grade 1 to 8 texts and found the
two taught rules fit 70.6 percent (VC|CV) and 30.5 percent (V|CV) of
the words they apply to. So the bank stores ONE split per word, chosen
by the spoken boundary, and the game never asks a child to place a
boundary. It asks them to pick the chunk that was spoken.

Curriculum fit, for the ethics application: the Australian Curriculum
v9 lists syllables in spoken words at Foundation (AC9EFLY09) and "a
syllable must contain a vowel sound" at Year 1 (AC9E1LY12), which is
also the rule the bank builder enforces on every chunk. The NSW
English K-2 syllabus (2022) has Stage 1 students segmenting
multisyllabic words into syllables as a spelling strategy.

## Speech

Speech is a stimulus here, not decoration: the spoken syllable and the
printed chunk must be the same thing. The macOS `say` path cannot
ship (the lab machine runs the Windows build; Apple's licence does not
allow shipping recordings of the system voices; and a general-purpose
voice reads an isolated syllable unpredictably). So the mode plays
pre-rendered files from assets/speech, with `say` kept as a developer
fallback under `speech.backend: auto`.
scripts/render_syllables_speech.py renders them; the folder ships
empty and the game runs silent without it, logging once per word.
Whoever renders must check the provider's current terms on using
synthesised audio inside a distributed application, record the voice
and the date in the manifest, and listen to a sample of the syllable
files.

## LIMITS: what this mode may not claim

Everything the old docstring said still holds, plus:

- It measures in-task first-press accuracy, which foil kinds captured
  wrong presses, and how long the choice took, under a four-choice
  format. Those are not reading, decoding or spelling outcomes. A
  change in them means nothing outside the game without a standardised
  pre and post measure and a control group (Galuschka et al 2014).
- The game it copies has a weak record in English. Ahmed, Wilson,
  Mead, Noble, Richardson, Wolpert and Goswami (2020) ran GraphoGame
  Rime with 95 six to seven year olds who had failed the Year 1
  Phonics Check and found a small nonword-decoding effect (partial eta
  squared 0.017), with spelling gains only in children who had
  education plans. McTigue, Solheim, Zimmer and Uppstad (2020)
  meta-analysed the GraphoGame literature and found a negligible
  overall effect, with SUPPORTIVE ADULT INTERACTION the only
  significant moderator (mean effect 0.48 with high adult support).
  Hence the adult line on the rest screen and the `supervised` flag on
  every row: a session played alone is a different condition.
- Chance is 25 percent per set. Accuracy near 25 percent is guessing,
  and the notebook draws that line.
- The foil taxonomy counts confusions. It does not diagnose letter
  position dyslexia or letter orientation difficulty; those need
  purpose-built tests (Kohnen et al 2012).
- The tactile channel is engagement and cueing, not a claimed active
  ingredient (Stevens et al 2021, meta-analytic null on the
  multisensory element of structured literacy).
- The hardware was built and ethically scoped for adult stroke
  rehabilitation. Use with children needs new ethics approval, a
  finger-spacing check and hygiene procedures, and none of these
  parameters have been validated on children with this device. The
  first study is feasibility and acceptability, not efficacy.

## Sources

- Ahmed H, Wilson A, Mead N, Noble H, Richardson U, Wolpert MA, Goswami U (2020). An evaluation of the efficacy of GraphoGame Rime for promoting English phonics knowledge in poor readers. Frontiers in Education 5, 132.
- Aravena S, Snellings P, Tijms J, van der Molen MW (2013). A lab-controlled simulation of a letter-speech sound binding deficit in dyslexia. Journal of Experimental Child Psychology 115(4), 691-707.
- Bhattacharya A, Ehri LC (2004). Graphosyllabic analysis helps adolescent struggling readers read and spell words. Journal of Learning Disabilities 37(4), 331-348.
- Bruck M, Treiman R (1990). Phonological awareness and spelling in normal children and dyslexics: the case of initial consonant clusters. Journal of Experimental Child Psychology 50(1), 156-178.
- Ehri LC, Nunes SR, Willows DM, Schuster BV, Yaghoub-Zadeh Z, Shanahan T (2001). Phonemic awareness instruction helps children learn to read. Reading Research Quarterly 36(3), 250-287.
- Fitts PM, Seeger CM (1953). S-R compatibility: spatial characteristics of stimulus and response codes. Journal of Experimental Psychology 46(3), 199-210.
- Foerde K, Shohamy D (2011). Feedback timing modulates brain systems for learning in humans. Journal of Neuroscience 31(37), 13157-13167.
- Gabay Y (2021). Delaying feedback compensates for impaired reinforcement learning in developmental dyslexia. Neurobiology of Learning and Memory 185, 107518.
- Galuschka K, Ise E, Krick K, Schulte-Koerne G (2014). Effectiveness of treatment approaches for children and adolescents with reading disabilities: a meta-analysis of randomized controlled trials. PLOS ONE 9(2), e89900.
- Kail R (1991). Developmental change in speed of processing during childhood and adolescence. Psychological Bulletin 109(3), 490-501.
- Kearns DM (2020). Does English have useful syllable division patterns? Reading Research Quarterly, doi 10.1002/rrq.342.
- Kirkby JA, Barrington RS, Drieghe D, Liversedge SP (2025). Parafoveal processing and transposed-letter effects in developmental dyslexic reading. Dyslexia 31(1), e1791.
- Kohnen S, Nickels L, Castles A, Friedmann N, McArthur G (2012). When 'slime' becomes 'smile': developmental letter position dyslexia in English. Neuropsychologia 50(14), 3681-3692.
- Kornell N, Hays MJ, Bjork RA (2009). Unsuccessful retrieval attempts enhance subsequent learning. Journal of Experimental Psychology: Learning, Memory, and Cognition 35(4), 989-998.
- Kuster SM, van Weerdenburg M, Gompel M, Bosman AMT (2018). Dyslexie font does not benefit reading in children with or without dyslexia. Annals of Dyslexia 68(1), 25-42.
- Leonard LB, Deevy P (2020). Retrieval practice and word learning in children with specific language impairment and their typically developing peers. Journal of Speech, Language, and Hearing Research 63(10), 3252-3262.
- Levitt H (1971). Transformed up-down methods in psychoacoustics. Journal of the Acoustical Society of America 49(2), 467-477.
- McTigue EM, Solheim OJ, Zimmer WK, Uppstad PH (2020). Critically reviewing GraphoGame across the world. Reading Research Quarterly 55(1), 45-73.
- Mehringer H, Fraga-Gonzalez G, Pleisch G, et al (2020). (Swiss) GraphoLearn: an app-based tool to support beginning readers. Research and Practice in Technology Enhanced Learning 15, 5.
- Metcalfe J, Kornell N, Finn B (2009). Delayed versus immediate feedback in children's and adults' vocabulary learning. Memory and Cognition 37(8), 1077-1087.
- Mueller B, Richter T, Karageorgos P, Krawietz S, Ennemoser M (2017). Effects of a syllable-based reading intervention in poor-reading fourth graders. Frontiers in Psychology 8, 1635.
- Proctor RW, Schneider DW (2018). Hick's law for choice reaction time: a review. Quarterly Journal of Experimental Psychology 71(6), 1281-1299.
- Richardson U, Lyytinen H (2014). The GraphoGame method. Human Technology 10(1), 39-60.
- Ronimus M, Kujala J, Tolvanen A, Lyytinen H (2014). Children's engagement during digital game-based learning of reading. Computers and Education 71, 237-246.
- Stevens EA, Austin C, Moore C, Scammacca N, Boucher AN, Vaughn S (2021). Current state of the evidence: examining the effects of Orton-Gillingham reading interventions. Exceptional Children 87(4), 397-417.
- Terepocki M, Kruk RS, Willows DM (2002). The incidence and nature of letter orientation errors in reading disability. Journal of Learning Disabilities 35(3), 214-233.
- Wery JJ, Diliberto JA (2017). The effect of a specialized dyslexia font, OpenDyslexic, on reading rate and accuracy. Annals of Dyslexia 67(2), 114-127.
- Wolff PH, Michel GF, Ovrut M, Drake C (1990). Rate and timing precision of motor coordination in developmental dyslexia. Developmental Psychology 26(3), 349-359.
- Ziegler JC, Goswami U (2005). Reading acquisition, developmental dyslexia, and skilled reading across languages: a psycholinguistic grain size theory. Psychological Bulletin 131(1), 3-29.
- Zorzi M, Barbiero C, Facoetti A, et al (2012). Extra-large letter spacing improves reading in dyslexia. PNAS 109(28), 11455-11459.
- ACARA. Australian Curriculum v9.0, English: AC9EFLY09, AC9E1LY12.
- NSW Education Standards Authority. English K-10 Syllabus (2022), K-2 phonological awareness.
