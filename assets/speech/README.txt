Syllables speech

The game reads <word>.wav and <word>_<position>.wav from this folder.
The word bank has 695 entries. The recordings have not been made yet.

Render a sample first:
  python scripts/render_syllables_speech.py --provider google --voice en-AU-Neural2-C --limit 5

Install google-cloud-texttospeech and set up Google application default
credentials first. A billing account is required. Polly is also supported
with boto3, AWS credentials and --provider polly --voice Olivia.

Listen to every syllable before using the files in a study. A written
chunk can be pronounced as letters or with the wrong vowel. Correct its
speech material before proceeding; a large bank alone is not validation.

Then remove --limit to render the full bank. Existing files are kept.
manifest.json records the provider, voice, date and files. Keep this with
the study materials. Check the provider terms before redistribution.

macOS say is for local tests only. Do not distribute those recordings.
Missing or failed speech is shown on screen and logged as speech_failed.

Provider setup:
https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-client-libraries
https://docs.aws.amazon.com/boto3/latest/reference/services/polly/client/synthesize_speech.html
