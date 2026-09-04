Spoken words and syllables for the Syllables mode
=================================================

This folder holds the rendered speech the mode plays:

    <word>.ogg        the whole word (ATTEND, and again when the word
                      is finished)
    <word>_<k>.ogg    the k-th syllable (modelled at the beat, spoken
                      again as the tiles spawn on the low rungs, and
                      once more as corrective feedback when a set
                      falls off the bottom unanswered)
    manifest.json     provider, voice, render date, and the file list

.wav is read as well as .ogg, ogg first.

It ships EMPTY. Nothing here is generated at run time, and the game
plays without it: with syllables.speech.backend set to auto (the
default) a missing file falls back to the macOS `say` command on a
developer Mac and to silence anywhere else, logged once per word, and
the game itself is unchanged either way.

To fill it:

    python3 scripts/render_syllables_speech.py --provider google \
        --voice en-AU-Neural2-C

That script's docstring carries the reasoning: why the files are
pre-rendered rather than spoken live (the lab machine is Windows,
where macOS `say` does not exist and the English (Australia) voices
are OneCore voices SAPI5 cannot reach), why the macOS voices must not
be shipped (Apple's licence), and why an isolated syllable wants SSML
phoneme control rather than a spelling the voice has to guess.

Two rules for whoever renders these:

1. Check the provider's current terms on using synthesised audio
   inside a distributed application BEFORE the first render, and
   record the voice name and the date in the manifest. The thesis
   methods section has to be able to say what spoke to the children.
2. Listen to a sample of the syllable files. A chunk read as letters
   ("na" as "en ay") is a broken stimulus, not a cosmetic problem:
   the whole task is matching what was heard to what is printed.

Files rendered with `--provider say` are for local testing only. Keep
them out of the build and out of git.
