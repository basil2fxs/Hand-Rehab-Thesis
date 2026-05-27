# Music files for rhythm mode

Drop one or more audio files in this folder. Supported: `.mp3 .wav .ogg .flac`. The first one found is the one rhythm mode picks.

## Licensing

Only use CC0, CC-BY, or public-domain tracks. Save the licence text alongside each file as `<song>.LICENCE.txt` so attribution survives.

Good sources:

- **incompetech.com** (Kevin MacLeod) - CC-BY 4.0. Pick anything tagged with a BPM that suits rehab pacing (60-110 BPM is good).
- **freemusicarchive.org** - filter to CC-BY or CC0 licences. The "Instrumental" and "Ambient" genres work well.
- **opengameart.org** - filter to "Music" + a CC licence.

## Rules of thumb

- Under 5 MB per track keeps repository size reasonable.
- Steady tempo (no big slow-fast transitions). `librosa.beat.beat_track` handles steady tempos best.
- Mostly instrumental. Vocals distract from the press timing.

## What happens if this folder is empty

Rhythm mode needs at least one track to start. If the folder is empty the Start button on the rhythm setup screen does nothing. Drop an audio file in and press Rescan.
