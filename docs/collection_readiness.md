# Collection readiness

Reviewed 6 September 2026 against the current code and the earlier requests.
Software checks and simulated participants do not validate physical timing,
force accuracy, pronunciation or treatment benefit.

## Implemented and checked in software

| Request | Current behaviour and evidence |
| --- | --- |
| Simple sessions and intake | One login, main hand, optional dimensions, autofill, session calibration, hub and early-exit saving. Session, intake and calibration tests. |
| Automatic boards and skippable rests | Port watcher, deferred mid-block assignment, rest-skip event records. Connection and wait tests. |
| All fingers | Per-mode hand tests exercise unilateral and bilateral routing. Mirror is bilateral; Force Pilot and Buzz Hunt require the physical device. |
| Muscle Memory file | Pattern template, validation, saved schedule and per-item timing. Pattern-file and notebook reconstruction tests. |
| Chords | Mixed two-to-four-finger combinations, no single-finger gameplay probes. Chord and hand tests. |
| Adaptive | Pace controller with the 65-80 percent target and 180 BPM ceiling. A short block or a ceiling can still leave a participant outside the target. |
| Rhythm | Four-second song previews; separate tactile lead, on-beat and feedback options. Timing is checked on a simulated wire, not yet established at the skin. |
| Syllables | Four-choice falling syllables, correct-finger scoring, error-driven returns, five warm-up taps and 695 multi-syllable words. Speech is not complete: see below. |
| Echo | Growing prefix from one item, one spare life and new game sequences. The result is Simon game span, not a standard Corsi score. |
| Force Pilot | Fixed wave ladder and short transitions; final novel wave retained as requested. Tracking and reconstruction tests. |
| Buzz Hunt | Fixed perceptible-duration commands, difficulty through response windows, recovery and pulse tests. Sensation still needs a rig check. |
| Lighthouse | Removed from the menu; legacy data support retained. |
| Menus and games | Regular/bold typography, calmer cards, readable controls and finger labels in all themes. Force Pilot dark-theme corridor contrast improved. Reaction retains the static-trial display. |
| Music | Menu mute and saved preference, quiet menu volume, previews and Force Pilot music. Dummy audio used in checks. |
| Data and EEG | Trial/raw/metadata logging, early-exit preservation, marker contracts and PsychoPy launcher. EEG itself is recorded by BioSemi. |
| Firmware tools | Flashing and address-change UI, packaged helpers and tests. No physical board was flashed during this review. |
| Lab package | Minimal four-entry package. A rebuild now refuses to delete recordings inside the PsychoPy source folder. |
| Own analysis | All ten modes have notebook chapters. Ported force analyses operate on this game's CSVs in Python. Historical recordings are optional and off by default. |
| Thesis figures | Ten-panel individual-results overview, coverage map, PDF/SVG export, plus existing per-finger, force, timing, within-block and data-quality figures. |
| Cohort validity | Older phases, ambiguous repeats, multiple days for one code, differing task configurations and known speech failures are excluded from affected comparisons. Files are preserved. |
| Study schedule | One sitting, eleven blocks, ten modes, about 45 minutes. The current plan permits 30-60 minutes; it is not a 30-minute protocol. |
| Thesis notes | The notes contain the 84 mark, Nasrin's feedback and the need for quantitative evidence. Do not turn simulated checks into participant findings. |

## Still needed before collection

1. **Syllables recordings and review.** There are no bundled word or syllable recordings. The cloud renderer is now implemented, but needs configured provider credentials. Render and listen to a sample before the full bank, then check every pronunciation. A spelling split is not proof that a spoken syllable is correct. The screen and logs now flag unavailable speech; those blocks cannot support the intended auditory task comparison.
2. **Bench measurements.** Check the SingleTact scale with known loads. Measure visual onset, motor onset and marker timing together on the lab computer. Existing offsets are estimates; a passing software test cannot establish physical latency or newton accuracy.
3. **One complete human pilot.** Use the actual Windows package, both hands and BioSemi marker recording. Check comfort, cue sensation, speech, fatigue, port assignment and all eleven block saves. Confirm ethics and the booking schedule with the supervisor.

The one-pass student study can describe device performance, task performance and
within-block trends. It cannot establish rehabilitation efficacy, durable learning,
test-retest reliability or clinical norms. Read uncertainty and exclusions alongside
any favourable result. A literature reference line is context, not a pass mark for a person.

Verification on 6 September: 103 test files, 3018 tests passed;
64 packaging and startup tests also passed after restricting release configuration;
116 presentation and audio-control tests passed after the final Settings spacing fix;
the notebook executed all 149 cells without errors on eight simulated
sittings. These are software checks, not collected participant results.
