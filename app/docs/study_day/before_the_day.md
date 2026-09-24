# Before the day

Do these once, in the week before the collection day. Each one closes
an open item in Section 4.8 of the design doc, so write down the date
and the result.

## 1. The pilot (item l): the first two participants

The rig side is done: a full Play all ran on the real board end to
end on 24 September 2026. The clock with real hands is an internal
pilot, decided in advance so it costs no participants:

- The first two participants run exactly as the run sheet says.
- After each, `check_sitting.py` must say READY and the first block
  to last must be under 46 minutes.
- Both fine: nothing changes, and they are participants 1 and 2.
- Either over 46 minutes: apply the trim ladder in Section 2.3 of the
  design doc from participant 3, and write down which rungs and from
  which code.

## 2. The pads (item h): nothing to do

Already covered: Force Pilot works in percent of each finger's own
maximum, so the pads' absolute gain cancels, and their noise and drift
were measured on 24 September 2026 (1.2 to 1.5 counts of noise, at
most 1.5 counts of drift in 60 s, every pad). If you want a
counts-per-gram figure for the thesis appendix, about five minutes,
game closed, board plugged in:

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

Done for this MacBook on 24 September 2026, and saved: the game reads
`app/config/latency_profile.yaml` at every start.

| Setting | Estimate before | Measured |
|---|---|---|
| `rhythm.audio_offset_ms` (the song) | 40 | 87 |
| `latency.tone_ms`, `rhythm.metronome_offset_ms` (short sounds) | 12 | 77 |
| `latency.buzzer_ms` (STIM to motor motion) | 45 | 74 |

- [ ] Play the study through the laptop's own speakers. The numbers
      belong to them: headphones or a Bluetooth speaker have their
      own delay (Bluetooth adds far more). For any other output, or
      another laptop, re-measure first, about two minutes, board
      plugged in, room quiet:

      ```
      python3 app/scripts/audio_latency.py --write
      ```

`check_sitting.py` says CHECK if a sitting's Rhythm block ran on
unmeasured delays.

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
