# Before the day

Do these once, in the week before the collection day. Each one closes
an open item in Section 4.8 of the design doc, so write down the date
and the result.

## 1. Pilot two people on the real rig (item l)

1. Run two volunteers (friends are fine) through the full
   [run sheet](run_sheet.md), timing the sitting with a phone
   stopwatch from LOG IN to the end of the last block.
2. The app's own estimate is about 43 minutes on the rig. If either
   pilot goes past 46 minutes, apply the trim ladder in Section 2.3 of
   the design doc and note which rungs were used.
3. Run the notebook's cohort chapter on the pilot sessions with
   `min_n=2`. Every table and figure should fill; the checks will say
   n is under the minimum, which is right at two.
4. Move the pilot session folders out of `sessions/` before the first
   real participant, so they never mix with the study data. The
   notebook treats any letters-then-digits code (T01 as much as P01)
   as a study code, so moving the folders is the only safe way.

## 2. Bench-check the force pads (item h)

Force Pilot's numbers lean on the pads reading the same force the same
way. About five minutes, game closed, board plugged in:

```
python3 app/scripts/pad_bench.py --masses 31.1 62.2 155.5
```

It walks you through each pad empty and with each mass, then a 30 s
hold for the drift, and prints counts per gram, how straight each
pad's line is and whether any pad reads unlike the others. Coins are
exact weights: a 50c piece is 15.55 g, so 2, 4 and 10 of them are
31.1, 62.2 and 155.5 g (stack them in a small cup). A pad flagged
CHECK gets reseated flat and the script run again. Keep the printout
(and the CSV it writes in `app/config/calibration/`) for the thesis
appendix.

## 3. Audio latency of the study laptop (item i)

Rhythm scores each tap against the beat the app schedules. The sound
reaches the ear later than that by the laptop's audio delay, and the
game subtracts `rhythm.audio_offset_ms` to make up for it. A wrong
offset moves every participant's mean asynchrony by the same amount:
the SD (Rh2) is unaffected, the sign of the mean (Rh1) is not.

One command, about two minutes, board plugged in, room quiet:

```
python3 app/scripts/audio_latency.py --with-board
```

It plays the study song and a click through the speakers while the
built-in microphone records, then asks you to tap the index pad with
a fingernail for 15 seconds (the pad and the microphone catch the same
instant, which times the microphone itself), then buzzes the index
motor. It prints the true delays and the config keys they belong to
(`rhythm.audio_offset_ms`, `latency.tone_ms`, `latency.buzzer_ms`).
Put the numbers in `app/config/user_settings.yaml`, set
`latency.measured: true` and the date, before the first participant.
If macOS asks for microphone access, allow it.

## 4. The laptop

- [ ] Start the game with `Local_Runner.command` (double-click). It
      runs the newest code and saves into the project's `sessions/`
      folder, which is gitignored (never on GitHub) and is where the
      notebook and `check_sitting.py` look.
- [ ] Power settings: never sleep on mains, screen never dims.
- [ ] Notifications off (Focus mode), volume set once to a comfortable
      level and left there. Write the level on the day's first intake
      sheet.
- [ ] The board self-tests with a short buzz on each finger when
      plugged in. If it does not, replug it and restart the app.
- [ ] Note the app version (the footer of the title screen, for example
      v1.x) on the first intake sheet of the day. Every session's
      metadata records it too.

## 5. Stock for the whole day

- [ ] Intake sheets, information sheets and consent forms: one per
      booking plus spares.
- [ ] Ruler (mm), pen, clipboard.
- [ ] 70 percent isopropyl wipes, hand sanitiser, disposable finger
      cots.
- [ ] Water and cups.
- [ ] A spare USB cable for the board.
