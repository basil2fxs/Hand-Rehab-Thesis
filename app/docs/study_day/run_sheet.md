# Run sheet, one participant

60 minutes booked. About 43 minutes on the rig, the rest is welcome,
paperwork and debrief. Tick as you go; anything unusual goes in the
notes box on the intake sheet.

## Between participants (2 min)

- [ ] Wipe the pads and the frame with an isopropyl wipe.
- [ ] Board plugged in and the app on the title screen. Start the app
      with `Local_Runner.command` (double-click). Give the board about
      three seconds after it opens: it buzzes each finger once as it
      starts up.
- [ ] New intake sheet, information sheet and consent form on the
      clipboard.

## Welcome and paperwork (10 min, clock not running)

- [ ] Give the information sheet. Let them read it and ask questions.
- [ ] Consent form signed. No signature, no session.
- [ ] Assign the next code (the login screen suggests the next free
      one, P01, P02 and so on). Write it on the intake sheet and the
      consent form. The code is the only link to their name, and the
      consent forms are kept apart from everything else.
- [ ] Intake sheet: age, sex, the four Edinburgh questions (they tick
      the boxes themselves), caffeine in the last 2 hours, hours of
      sleep, any hand pain or injury today (if yes, thank them and
      stop: they cannot take part today).
- [ ] Measure the RIGHT hand with the ruler: length from the wrist
      crease to the tip of the middle finger, breadth across the
      knuckles (index to little finger). Millimetres.

## Seat and log in (5 min)

- [ ] Hands washed or sanitised. Offer finger cots.
- [ ] Seat height so the forearm rests flat and the fingers sit index
      to little on the four pads, thumb off the frame.
- [ ] Say once: "This runs about three quarters of an hour, all on
      your right hand, with a short stretch early on and a proper
      break later, after which three of the games come round again.
      Press lightly, like typing. Some games have a hidden rule; don't
      try to work it out, just play."
- [ ] Say once: "After each game the screen shows how your last few
      goes compared with your first few." Don't repeat it and don't
      comment on scores during the session.
- [ ] Login screen: code, age, sex, hand length and breadth.
- [ ] MAIN HAND: ask "Which hand do you write with?" and pick that one,
      Left or Right. This is their real handedness, recorded for the
      analysis. It does not change the device.
- [ ] LOG IN.
- [ ] Hand screen: pick RIGHT HAND. The device is the right hand for
      everyone, left-handers included. (Picking Left by mistake is not
      fatal: Play all moves the board to the right hand anyway.)
- [ ] Quick calibration: hand off, hand resting, then one light press
      per finger. If a finger fails, redo it once, then carry on and
      note it.

## Play all (about 43 minutes on the rig)

- [ ] Press PLAY ALL on the hub (or A). After each game press Start on
      the NEXT UP card (or N). The strip shows PLAY ALL k/12 and the
      minutes: amber past 45, red past the 50 minute hard stop.
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
| 5 | Chords | Syllables |
| 6 | Buzz Hunt | Reaction |
| 7 | Pattern | Rhythm |
| 8 | Adaptive | Echo |
| 9 | Syllables | Pattern |
| rest | 3 minutes | 3 minutes |
| 10 | Reaction | Force Pilot |
| 11 | Force Pilot | Chords |
| 12 | Chords | Reaction |

### At the 3 minute rest

- [ ] Hands off the pads, water offered. Don't talk about the games.
- [ ] Ask, and write the numbers with the clock time:
      "Tired in the head?" 0 to 10.
      "Tired in the hands?" 0 to 10.
- [ ] Take the full 3 minutes. The Start button unlocks after 1 minute
      and reads "Start early"; only use it if they ask to go on, and
      write down that the rest was cut short. The reliability numbers
      are measured across this gap.
- [ ] Pass 2 is the same three games again. Don't say they are
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
- The app closes: open it, log in with the same code and main hand,
  press PLAY ALL. Finished games are not played again.
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
- [ ] End the session from the hub and confirm.
- [ ] Check the data before they leave. In Terminal, from the project
      folder:

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
