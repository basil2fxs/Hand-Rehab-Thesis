# ui

One file per screen. [`screens.py`](screens.py) holds the login, the hub, the lane games, the results and Settings; the rest are one screen each. [`theme.py`](theme.py) is the palette, [`widgets.py`](widgets.py) the buttons and lane strips.

<table>
<tr>
<td align="center" width="33%"><img src="../../docs/images/login.png" alt="Login"><br><sub><b>Login</b> <code>screens.py</code> TitleScreen</sub></td>
<td align="center" width="33%"><img src="../../docs/images/hand.png" alt="Hand choice"><br><sub><b>Hand</b> <code>hand_choice_screen.py</code></sub></td>
<td align="center" width="33%"><img src="../../docs/images/calibration.png" alt="Quick calibration"><br><sub><b>Quick calibration</b> <code>quick_calibration_screen.py</code></sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="../../docs/images/hub.png" alt="Hub"><br><sub><b>Hub</b> <code>screens.py</code> ModeSelectScreen</sub></td>
<td align="center" width="33%"><img src="../../docs/images/adaptive.png" alt="Lane game"><br><sub><b>Lane games</b> <code>screens.py</code> GameplayScreen</sub></td>
<td align="center" width="33%"><img src="../../docs/images/rhythm.png" alt="Rhythm"><br><sub><b>Rhythm</b> <code>screens.py</code> RhythmScreen</sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="../../docs/images/syllables.png" alt="Syllables"><br><sub><b>Syllables</b> <code>syllables_screen.py</code></sub></td>
<td align="center" width="33%"><img src="../../docs/images/force_pilot.png" alt="Force Pilot"><br><sub><b>Force Pilot</b> <code>force_pilot_screen.py</code></sub></td>
<td align="center" width="33%"><img src="../../docs/images/buzz_hunt.png" alt="Buzz Hunt"><br><sub><b>Buzz Hunt</b> <code>buzz_hunt_screen.py</code></sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="../../docs/images/reaction.png" alt="Reaction"><br><sub><b>Reaction</b> <code>srt_screen.py</code></sub></td>
<td align="center" width="33%"><img src="../../docs/images/reaction_setup.png" alt="Reaction setup"><br><sub><b>Reaction setup</b> <code>srt_setup_screen.py</code></sub></td>
<td align="center" width="33%"><img src="../../docs/images/results.png" alt="Results"><br><sub><b>Results</b> <code>screens.py</code> ResultsScreen</sub></td>
</tr>
<tr>
<td align="center" width="33%"><img src="../../docs/images/settings.png" alt="Settings"><br><sub><b>Settings</b> <code>screens.py</code> DiagnosticsScreen</sub></td>
<td align="center" width="33%"><img src="../../docs/images/eeg_port.png" alt="EEG trigger box"><br><sub><b>EEG trigger box</b> <code>eeg_port_screen.py</code></sub></td>
<td align="center" width="33%"></td>
</tr>
</table>

Every picture here is rendered by `python3 scripts/make_screenshots.py` from the real screens, headless.
