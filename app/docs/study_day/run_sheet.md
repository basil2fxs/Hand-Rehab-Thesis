# Run sheet, one participant

Booked for the longest length the student can give: an hour for the
45 (75 minutes for the 60), less for the 30 or 15. About 15 minutes
of it is welcome, paperwork and debrief. Tick as you go; anything unusual goes in the
notes box on the intake sheet.

## Between participants (2 min)

- [ ] Wipe the pads and the frame with an isopropyl wipe.
- [ ] Board plugged in and the app on the title screen. On the lab
      PC, start Finger Rehab from the Start menu; on the Mac, with
      `Local_Runner.command` (double-click). Give the board about
      three seconds after it opens: it buzzes each finger once as it
      starts up.
- [ ] New intake sheet, information sheet and consent form on the
      clipboard.

## Welcome and paperwork (10 min, clock not running)

- [ ] Give the information sheet. Let them read it and ask questions.
- [ ] Consent form signed. No signature, no session.
- [ ] Assign the next code in order of consent: P01, P02 and so on.
      Write it on the intake sheet and the consent form. The code is
      the only link to their name, and the consent forms are kept
      apart from everything else.
- [ ] Intake sheet: age, sex, the four Edinburgh questions (they tick
      the boxes themselves), caffeine in the last 2 hours, hours of
      sleep, any hand pain or injury today (if yes, thank them and
      stop: they cannot take part today).
- [ ] Measure the RIGHT hand with the ruler: length from the wrist
      crease to the tip of the middle finger. Millimetres.

## Seat and log in (5 min)

- [ ] Hands washed or sanitised. Offer finger cots.
- [ ] Seat height so the forearm rests flat and the fingers sit index
      to little on the four pads, thumb off the frame.
- [ ] Say once: "This runs about three quarters of an hour, all on
      your right hand, with a short stretch early on and a proper
      break later, after which four of the games come round again.
      Press lightly, like typing. Some games have a hidden rule; don't
      try to work it out, just play."
- [ ] Say once: "After each game the screen shows how your last few
      goes compared with your first few." Don't repeat it and don't
      comment on scores during the session.
- [ ] Login screen: type the code in NAME, then age, sex and hand
      length. SESSION: the longest length the slot allows, 60 (a 75
      minute slot), 45 (an hour), then 30, then 15.
- [ ] MAIN HAND: ask "Which hand do you write with?" and pick that one,
      Left or Right. This is their real handedness, recorded for the
      analysis. It does not change the device.
- [ ] LOG IN. The app puts the board on the right hand, the device
      hand for everyone, left-handers included.
- [ ] Quick calibration opens by itself: hand off, hand resting, then
      one light press per finger. If a finger fails, redo it once,
      then carry on and note it.

## Play all (about 44 minutes on the rig for the 45)

- [ ] The first game starts after the calibration. After each game
      press Start on the NEXT UP card (or N). The strip shows PLAY ALL
      k/12 on the 45 and the minutes: amber past the length, red past its hard
      stop (18, 35, 50 or 65 minutes). The 60 plays every game twice;
      the 15 and 30 play shortened games (docs/research/trial_mode.md).
- [ ] Don't coach during a game. Let them skip a game's own rest
      (Space) only when they say they're ready.
- [ ] Tick each game on the intake sheet as it ends.

The order comes from the code, and every game is the right hand:

| Step | Order A (odd codes) | Order B (even codes) |
|---|---|---|
| 1 | Reaction | Force Pilot |
| 2 | Rhythm | (60 s stretch) Chords |
| 3 | Echo | Buzz Hunt |
| 4 | (60 s stretch) Force Pilot | Adaptive |
| 5 | Chords | Reaction |
| 6 | Buzz Hunt | Rhythm |
| 7 | Pattern | Echo |
| 8 | Adaptive | Pattern |
| rest | 3 minutes | 3 minutes |
| 9 | Reaction | Force Pilot |
| 10 | Rhythm | Chords |
| 11 | Force Pilot | Reaction |
| 12 | Chords | Rhythm |

Syllables is not in the sitting. It is built for readers with
dyslexia and is played with a dyslexic participant on its own, from
the hub.

### At the 3 minute rest

- [ ] Hands off the pads, water offered. Don't talk about the games.
- [ ] Ask, and write the numbers with the clock time:
      "Tired in the head?" 0 to 10.
      "Tired in the hands?" 0 to 10.
- [ ] Take the full 3 minutes. The Start button unlocks after 1 minute
      and reads "Start early"; only use it if they ask to go on, and
      write down that the rest was cut short. The reliability numbers
      are measured across this gap.
- [ ] Pass 2 is four of the games again. Don't say they are
      repeats and don't mention the first scores.

### If something goes wrong

- Board drops between games: the card says "Waiting for the board".
  Replug it, wait for the buzz, press Start. Note the step.
- Force Pilot or Buzz Hunt refuses to start: the board is not live.
  Same fix.
- Force Pilot goes straight back to the menu after MAX PRESS CHECK,
  with a note under the header: no press came in 25 seconds, so
  nothing was measured and the step is still waiting. Show a firm
  press ("as hard as is comfortable when it says PRESS"), then PLAY
  ALL again.
- Test Mode left on in Settings does not matter for a study code:
  Play all switches it off for the sitting and back on afterwards.
- A game can't be run at all: Skip step (S) on the hub, confirm, and
  write the reason.
- The app closes: open it, log in with the same code, main hand and
  SESSION length. It carries on from the first game not finished;
  finished games are not played again.
- Past 50 minutes: let the current game finish, stop, write down what
  was missed. Pattern is the one to lose.
- They want to stop: stop. No reason needed. Write down where.

## End (3 min)

- [ ] The last screen shows the TODAY table. Let them read it. Answer
      questions about their own numbers only: it compares the start of
      each game with the end of the same game, a small change is not
      necessarily a real one, and nobody is being compared with other
      people.
- [ ] Ask the two tiredness questions again and write them down.
- [ ] Ask the two ratings and write them down:
      "How comfortable were the pads?" 0 to 10.
      "How clear was what each game asked of you?" 0 to 10.
- [ ] End the session from the hub and confirm.
- [ ] Check the data before they leave. On the lab PC: the strip
      shows every step done; the READY check below runs later on the
      laptop, once the data is copied (FINAL TRIAL RESULTS, After each
      day). On the Mac, in Terminal, from the project folder:

      ```
      python3 app/scripts/check_sitting.py
      ```

      It reads the newest code's folders and prints OK or CHECK for:
      all 12 steps done, the passes, full counts, the rest, board
      drops, failed buzzes and the intake fields. READY on the last
      line means the sitting is complete. A CHECK tells you what to
      do; a step not finished can still be played now with PLAY ALL
      if they have time.
- [ ] Read the [debrief](debrief.md). Thank them.
- [ ] Wipe the pads and frame.
