`syllables_source.txt` is the word list for the Syllables mode, one word per line: the band (A, B or C), then the word split by hyphens with the stressed syllable in capitals, as in `A ba-NA-na`.
`python3 scripts/build_syllables_bank.py` checks every line and writes `syllables_bank.json`, the file the game reads; one bad line and it writes nothing.
The list is written by hand for this project; provenance and terms are in [LICENCE.txt](LICENCE.txt).
