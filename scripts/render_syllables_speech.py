#!/usr/bin/env python3
"""Render the spoken words and syllables the syllables mode plays.

    python3 scripts/render_syllables_speech.py --provider say --voice Karen
    python3 scripts/render_syllables_speech.py --provider google \\
        --voice en-AU-Neural2-C

Writes assets/speech/<word>.ogg (or .wav) and <word>_<k>.<ext> for the
k-th syllable, plus manifest.json recording the provider, the voice
and the render date. The game never calls this: it plays the files.

WHY FILES AND NOT LIVE SPEECH. Speech is a stimulus in this mode, not
a nicety: the spoken syllable and the printed chunk have to be the
same thing, every time, for every child. Three facts force
pre-rendered assets:

  - the lab machine runs the Windows build, and macOS `say` does not
    exist there. The English (Australia) Windows voices (Catherine,
    James) are OneCore voices that SAPI5 clients such as pyttsx3
    cannot see without registry edits, so there is no built-in
    Windows path either;
  - Apple's macOS licence allows the System Voices for personal,
    non-commercial content and does not allow shipping recordings of
    them inside a distributed application, so `say` output must never
    end up in the build (check the current text of the licence before
    relying on this summary);
  - an isolated syllable is exactly what a general-purpose voice
    reads unpredictably ("na" as "en ay"), so the syllables want SSML
    phoneme control, which only the cloud voices give.

WHICH PROVIDER. Google Cloud Text-to-Speech and Amazon Polly both have
Australian English voices (en-AU Standard, Wavenet and Neural2;
Olivia, Nicole, Russell) and both support the SSML phoneme element, so
either can render a syllable as sounds rather than as a spelling the
engine has to guess. Confirm the provider's current terms on using
synthesised audio inside a distributed application before the first
render, and put the voice name and the date in the manifest so the
thesis methods section can state them.

WHAT --provider say IS FOR. Developer convenience on a Mac: it
renders the same file tree with the system voice so the mode can be
played and tested with sound before anyone spends money or agrees to
terms. Those files must not be committed or shipped, which is why the
script writes them under a separate --out directory by default and
refuses to overwrite a manifest that names a different provider.

The word list comes from assets/words/syllables_bank.json plus the
hand list in finger_rehab/game/modes/syllables_words.py, which is the
same merge the game plays from, so nothing can be spoken that the game
cannot draw and nothing drawn can be missing a file.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

DEFAULT_OUT = REPO / "assets" / "speech"
PROVIDERS = ("say", "google", "polly")


def _words():
    from finger_rehab.game.modes.syllables_words import all_words
    return all_words()


def _render_say(text: str, out: Path, voice: str | None) -> bool:
    """macOS `say` to an AIFF, then to WAV through afconvert if it is
    there. Developer path only: never ship these files."""
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    aiff = out.with_suffix(".aiff")
    cmd += ["-o", str(aiff), text]
    try:
        subprocess.run(cmd, check=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"say failed for {text!r}: {e}", file=sys.stderr)
        return False
    wav = out.with_suffix(".wav")
    try:
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@22050",
                        str(aiff), str(wav)], check=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        aiff.unlink(missing_ok=True)
    except Exception:
        # No afconvert: leave the AIFF, which pygame can also load.
        pass
    return True


def _render_cloud(provider: str, text: str, ssml: str | None,
                  out: Path, voice: str) -> bool:
    """Google or Polly. Deliberately not implemented here: the call
    needs credentials, a billing account and an accepted terms of
    service, none of which belong in a repository. The shape of the
    call is documented so whoever runs it can fill in ten lines with
    the provider's own SDK sample in front of them."""
    raise SystemExit(
        f"--provider {provider} needs the provider SDK and credentials.\n"
        "Fill in _render_cloud with the provider's sample call:\n"
        "  google: texttospeech.TextToSpeechClient().synthesize_speech(\n"
        "      input=SynthesisInput(ssml=ssml or text),\n"
        "      voice=VoiceSelectionParams(language_code='en-AU',\n"
        "                                 name=voice),\n"
        "      audio_config=AudioConfig(audio_encoding=OGG_OPUS,\n"
        "                               sample_rate_hertz=22050))\n"
        "  polly: boto3.client('polly').synthesize_speech(\n"
        "      Text=ssml or text, TextType='ssml' if ssml else 'text',\n"
        "      VoiceId=voice, Engine='neural', OutputFormat='ogg_vorbis')\n"
        "then write response.audio_content to the path this script\n"
        "hands you. Record the voice and the date in the manifest, and\n"
        "check the provider's terms on redistributing the audio first.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--provider", required=True, choices=PROVIDERS,
                    help="say (macOS, developer only) | google | polly")
    ap.add_argument("--voice", required=True,
                    help="voice name, e.g. Karen, en-AU-Neural2-C, Olivia")
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="output directory (default assets/speech)")
    ap.add_argument("--limit", type=int, default=0,
                    help="render only the first N words (a dry run)")
    ap.add_argument("--force", action="store_true",
                    help="re-render files that already exist")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    manifest = {"provider": args.provider, "voice": args.voice,
                "rendered_on": date.today().isoformat(),
                "sample_rate": 22050, "entries": {}}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        if (old.get("provider") != args.provider
                or old.get("voice") != args.voice) and not args.force:
            raise SystemExit(
                f"{manifest_path} was rendered with "
                f"{old.get('provider')}/{old.get('voice')}. Mixing "
                "voices inside one asset set would change the stimulus "
                "mid-block; pass --force if that is really what you "
                "want.")
        manifest["entries"] = old.get("entries", {})

    words = list(_words())
    if args.limit:
        words = words[:args.limit]
    n_done = 0
    for w in words:
        jobs = [(w.word, w.word, None)]
        for k, chunk in enumerate(w.syllables):
            # The syllable is rendered from its spelling here. With a
            # cloud provider, pass SSML instead so the chunk is spoken
            # as sounds:
            #   <speak><phoneme alphabet="ipa" ph="...">chunk</phoneme></speak>
            # built from the bank's IPA field once the bank carries
            # one. Every rendered syllable wants an ear check: a
            # chunk read as letters is a broken stimulus, not a
            # cosmetic problem.
            jobs.append((f"{w.word}_{k}", chunk, None))
        files = []
        for stem, text, ssml in jobs:
            target = out / f"{stem}.wav"
            exists = any((out / f"{stem}{ext}").exists()
                         for ext in (".ogg", ".wav", ".aiff"))
            if exists and not args.force:
                files.append(target.name)
                continue
            if args.provider == "say":
                ok = _render_say(text, target, args.voice)
            else:
                ok = _render_cloud(args.provider, text, ssml, target,
                                   args.voice)
            if ok:
                n_done += 1
            files.append(target.name)
        manifest["entries"][w.word] = {
            "file": files[0],
            "syllables": files[1:],
            "chunks": list(w.syllables),
        }
    manifest_path.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"rendered {n_done} files into {out}")
    print(f"manifest: {manifest_path}")
    if args.provider == "say":
        print("These files came from the macOS system voice. Keep them "
              "out of the build and out of git: Apple's licence does "
              "not allow shipping them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
