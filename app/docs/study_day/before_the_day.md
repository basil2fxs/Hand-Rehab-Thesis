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
way.

1. Board plugged in, app open on Settings from the title screen (the
   hardware test screen: live counts per pad, and a Test STIM button
   that buzzes each motor in turn).
2. For each pad: nothing on it, then a 50 g, 100 g and 200 g mass (or
   anything weighed on a kitchen scale) placed in the middle of the
   pad. Write the counts after 3 s.
3. Leave the 200 g mass on one pad for 30 s and write the counts at 0,
   10, 20 and 30 s (the drift trace).
4. Keep the sheet for the thesis appendix: counts against mass per pad
   is the calibration curve, and the 30 s trace is the drift.

A pad that reads nothing, or reads half what its neighbours read for
the same mass, gets reseated before the study.

## 3. Audio latency of the study laptop (item i)

Rhythm scores each tap against the beat the app schedules. The sound
reaches the ear a little later than that, by the laptop's audio
latency, and every participant's mean asynchrony moves by the same
amount. The SD (Rh2) is unaffected; the sign of the mean (Rh1) is read
against it.

1. Put a phone next to the laptop speaker and record slow-motion video
   (240 fps if it has it) of a finger tapping a pad in time with the
   rhythm game for 20 beats.
2. On the video, count frames from the sound of each beat to the tap
   landing, and compare with the asynchrony the game logs for the same
   taps (the rhythm block's trials.csv, time_difference_ms).
3. The average gap is the audio latency. Write it down. If you skip
   this, the thesis says the asynchrony is within-device and that Rh1's
   sign includes the latency.

## 4. The laptop

- [ ] The app runs from a local folder, not a cloud-synced one, and
      `session.data_dir` points at the folder the sessions will live
      in. Participant data never goes into the Google Drive repo.
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
