# -*- coding: utf-8 -*-
"""
SRT Sequence Learning Experiment
@author: Dr. Welber Marinovic

Design (3 phases + Recall):
  1. Practice SRT    (random sequence, constant 500 ms ISI)
  2. Learning SRT    (fixed 10-item sequence, group-specific ISI — 8 blocks)
  3. Post-test SRT   (random sequence, constant 500 ms ISI)
  4. Explicit Recall (participant clicks squares to indicate perceived sequence)

Between-subjects IV: timing group (selected in GUI)
  constant  — ISI after every keypress = 500 ms
  cyclical  — ISI cycles tied to sequence position (avg 500 ms)
  random    — ISI randomly shuffled each cycle from {250x3, 500x4, 750x3}
              (avg 500 ms); no consistent positional pattern.

Visual: four grey squares (centred on screen, closer together vertically
        to minimise eye movement during EEG recording);
        target square turns red for 100 ms (synced with sound).
Anticipatory window: 100 ms before flash onset.
Response deadline: 2.5 s (miss -> 200 ms pause, then next trial).

Practice phase: colour-coded feedback appears below squares.
Learning and post-test phases: no feedback shown.
First trial of every block: precedes with a 1000 ms pause.

Supports laptop (test mode) and lab desktop (COM10 + Realtek audio device).
"""

import os
import traceback
import random
import csv
import gc
import serial

# ---------------------------------------------------------------------------
# PATH SETUP
# ---------------------------------------------------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))

AUDIO_FOLDER_PRIMARY  = r'H:\Wren 2025 Honours\latest version'
AUDIO_FOLDER_FALLBACK = script_dir

os.chdir(script_dir)

# ---------------------------------------------------------------------------
# PSYCHOPY INITIAL IMPORTS
# ---------------------------------------------------------------------------
from psychopy import prefs, gui, data
from psychopy import __version__ as psychopyVersion

# ===========================================================================
# EXPERIMENT SETUP GUI
# ===========================================================================
expName = 'SRT Sequence Learning'

MUSICAL_EXP_OPTIONS = [
    '0 - no experience',
    '1 - less than 6 months',
    '2 - 6 months to 1 year',
    '3 - 1 to 2 years',
    '4 - 2 to 3 years',
    '5 - 3+ years',
]

expInfo = {
    'participant':        '',
    'age':                '',
    'gender':             ['male', 'female', 'non-binary', 'prefer not to say'],
    'musical_experience': MUSICAL_EXP_OPTIONS,
    'group':              ['constant', 'cyclical', 'random'],
    'mode':               ['experiment', 'test'],
    'date|hid':           data.getDateStr(),
    'expName|hid':        expName,
    'psychopyVersion|hid': psychopyVersion,
}

dlg = gui.DlgFromDict(dictionary=expInfo, title=expName, sortKeys=False)
if not dlg.OK:
    from psychopy import core
    core.quit()

TEST_MODE  = expInfo['mode'] == 'test'
GROUP      = expInfo['group']
GENDER     = expInfo['gender']
MUSIC_CODE = int(expInfo['musical_experience'][0])

if TEST_MODE:
    print("*** RUNNING IN TEST MODE ***")
print(f"Group: {GROUP} | Gender: {GENDER} | Musical experience: {MUSIC_CODE}")

# ---------------------------------------------------------------------------
# AUDIO PREFERENCES
# ---------------------------------------------------------------------------
prefs.hardware['audioLib']         = ['sounddevice']
prefs.hardware['audioLatencyMode'] = 3
prefs.hardware['audioSampleRate']  = 48000

if not TEST_MODE:
    prefs.hardware['audioDevice'] = 'Speakers (Realtek High Definition Audio)'

from psychopy import visual, core, event, sound
from psychopy.hardware import keyboard

# ---------------------------------------------------------------------------
# WINDOW & KEYBOARD
# ---------------------------------------------------------------------------
win = visual.Window(
    fullscr=not TEST_MODE, screen=1, color='black', units='norm',
    allowGUI=False, useFBO=True
)
win.mouseVisible = False

kb = keyboard.Keyboard()

# ---------------------------------------------------------------------------
# EEG SERIAL PORT
# ---------------------------------------------------------------------------
class DummySerial:
    def write(self, *args): pass
    def close(self):        pass

try:
    eeg_serial = serial.Serial(port='COM10', timeout=0)
except Exception as e:
    if TEST_MODE:
        print("Serial port not found - using DummySerial (test mode).")
        eeg_serial = DummySerial()
    else:
        print(f"FATAL: Serial port COM10 not found ({e}).\n"
              "Select 'test' mode to run without EEG hardware.")
        core.quit()

# ===========================================================================
# VISUAL ELEMENTS
# ===========================================================================
SQUARE_SIZE    = 0.13
SQUARE_Y       = 0.0
LANE_POSITIONS = [-0.225, -0.075, 0.075, 0.225]
LANES          = ['v', 'b', 'n', 'm']
COLOUR_DEFAULT = 'grey'
COLOUR_FLASH   = 'red'
COLOUR_SELECT  = 'yellow'

squares = {
    lane: visual.Rect(
        win,
        width=SQUARE_SIZE, height=SQUARE_SIZE,
        fillColor=COLOUR_DEFAULT, lineColor=COLOUR_DEFAULT,
        pos=[pos, SQUARE_Y]
    )
    for lane, pos in zip(LANES, LANE_POSITIONS)
}

lane_labels = {
    lane: visual.TextStim(
        win, text=lane.upper(),
        pos=[pos, SQUARE_Y - 0.10],
        height=0.05, color='white'
    )
    for lane, pos in zip(LANES, LANE_POSITIONS)
}

instructions_srt = visual.TextStim(
    win,
    text='Press the key that matches the flashing square as fast as you can',
    pos=[0, 0.85], height=0.05, color='white', wrapWidth=1.8
)

feedback_stim = visual.TextStim(
    win, text='', pos=[0, SQUARE_Y - 0.25], height=0.055, color='white', wrapWidth=1.8
)

# ---------------------------------------------------------------------------
# FRAME RATE DETECTION
# ---------------------------------------------------------------------------
SUPPORTED_RATES = [60, 120]

raw_frame_rate = win.getActualFrameRate(nIdentical=20, nMaxFrames=200, nWarmUpFrames=50)
if raw_frame_rate is None:
    frame_rate = 60.0
else:
    rounded    = int(round(raw_frame_rate))
    frame_rate = float(min(SUPPORTED_RATES, key=lambda r: abs(r - rounded)))

if int(frame_rate) not in SUPPORTED_RATES:
    print(f"Frame rate {int(frame_rate)} Hz is not supported. Exiting.")
    core.quit()

# ---------------------------------------------------------------------------
# SRT TIMING PARAMETERS
# ---------------------------------------------------------------------------
FLASH_MS        = 100
DEADLINE_MS     = 2500
ANTICIPATION_MS = 100
MISS_PAUSE_MS   = 200
FEEDBACK_MS     = 200
CONSTANT_ISI_MS = 500

CYCLICAL_ISI = [250, 500, 750, 250, 500, 750, 250, 500, 750, 500]

MARKER_FLASH_ONSET  = 30
MARKER_RESET        = 0
_MARKER_PULSE_SEC   = 2.0 / 120.0
MARKER_PULSE_FRAMES = max(1, int(round(_MARKER_PULSE_SEC * frame_rate)))

# ===========================================================================
# AUDIO LOADING
# ===========================================================================
_sound_files = {'v': 'V.wav', 'b': 'B.wav', 'n': 'N.wav', 'm': 'M.wav'}
sounds = {}

for key, filename in _sound_files.items():
    loaded = False
    for folder in (AUDIO_FOLDER_PRIMARY, AUDIO_FOLDER_FALLBACK):
        fpath = os.path.join(folder, filename)
        if os.path.exists(fpath):
            try:
                sounds[key] = sound.Sound(fpath)
                loaded = True
            except Exception:
                pass
            break

# ===========================================================================
# SEQUENCE CONFIGURATION
# ===========================================================================
SEQ_LENGTH = 10
FIXED_SEQUENCE = ['v', 'n', 'b', 'v', 'm', 'n', 'b', 'm', 'v', 'n']

def generate_random_sequence(n_trials, fingers=None):
    if fingers is None:
        fingers = list(LANES)
    n_each    = n_trials // len(fingers)
    remainder = n_trials % len(fingers)
    pool      = fingers * n_each + random.sample(fingers, remainder)

    for _ in range(200):
        result, remaining = [], list(pool)
        random.shuffle(remaining)
        ok = True
        while remaining:
            cands = [i for i, x in enumerate(remaining) if not result or x != result[-1]]
            if not cands:
                ok = False
                break
            result.append(remaining.pop(random.choice(cands)))
        if ok:
            return result
    raise RuntimeError("Failed to generate random sequence.")

def generate_isi_list(group, n_trials):
    if group == 'constant':
        return [CONSTANT_ISI_MS] * n_trials
    elif group == 'cyclical':
        return [CYCLICAL_ISI[i % SEQ_LENGTH] for i in range(n_trials)]
    elif group == 'random':
        base = [250] * 3 + [500] * 4 + [750] * 3
        isi  = []
        for _ in range(0, n_trials, SEQ_LENGTH):
            chunk = base.copy()
            random.shuffle(chunk)
            isi.extend(chunk)
        return isi[:n_trials]

# ===========================================================================
# TRIAL COUNTS
# ===========================================================================
RANDOM_TRIALS   = 48
RANDOM_TRIALS   = 48
LEARNING_BLOCKS = 8
LEARNING_BLOCKS = 8
LEARNING_REPS   = 10
LEARNING_REPS   = 10
LEARNING_TRIALS = LEARNING_REPS * SEQ_LENGTH

# ===========================================================================
# DRAWING HELPERS
# ===========================================================================
def reset_squares():
    for sq in squares.values():
        sq.fillColor = COLOUR_DEFAULT
        sq.lineColor = COLOUR_DEFAULT

def draw_scene(feedback_text=''):
    for sq in squares.values(): sq.draw()
    for lbl in lane_labels.values(): lbl.draw()
    instructions_srt.draw()
    if feedback_text:
        feedback_stim.text = feedback_text
        feedback_stim.draw()

def show_message(text, wait_key='space'):
    visual.TextStim(win, text=text, height=0.07, wrapWidth=1.6, color='white').draw()
    win.flip()
    event.waitKeys(keyList=[wait_key])

# ===========================================================================
# SRT BLOCK RUNNER
# ===========================================================================
def run_srt_block(finger_seq, isi_list, phase_name, block_number=None):
    global performance_log

    show_feedback = (phase_name == 'practice')

    flash_frames        = max(1, int(round(FLASH_MS        / 1000 * frame_rate)))
    deadline_frames     = int(round(DEADLINE_MS            / 1000 * frame_rate))
    anticipation_frames = max(1, int(round(ANTICIPATION_MS / 1000 * frame_rate)))
    miss_pause_frames   = max(1, int(round(MISS_PAUSE_MS   / 1000 * frame_rate)))
    feedback_frames     = max(1, int(round(FEEDBACK_MS     / 1000 * frame_rate)))

    reset_squares()

    for trial_idx, finger in enumerate(finger_seq):
        seq_position = (trial_idx % SEQ_LENGTH) + 1

        # --------------------------------------------------------------------
        # WAIT INTERVAL (1000 ms before very first trial, then defined ISI)
        # --------------------------------------------------------------------
        if trial_idx > 0:
            isi_ms = isi_list[trial_idx - 1]
        else:
            isi_ms = 1000.0  # 1-second pause at the start of the block

        isi_frames   = max(1, int(round(isi_ms / 1000 * frame_rate)))
        flush_frames = max(0, isi_frames - anticipation_frames)

        for f in range(isi_frames):
            win.clearBuffer()
            draw_scene()
            win.flip()
            if f < flush_frames:
                kb.clearEvents()
                event.clearEvents()

        # --------------------------------------------------------------------
        # FLASH ONSET
        # --------------------------------------------------------------------
        reset_squares()
        squares[finger].fillColor = COLOUR_FLASH
        squares[finger].lineColor = COLOUR_FLASH

        if finger in sounds:
            sounds[finger].play()

        win.clearBuffer()
        draw_scene()
        win.flip()

        flash_onset        = core.getTime()
        marker_frames_left = MARKER_PULSE_FRAMES
        eeg_serial.write(bytes(chr(MARKER_FLASH_ONSET), 'UTF-8'))

        response_key = None
        response_rt  = None

        keys = kb.getKeys(keyList=['v', 'b', 'n', 'm', 'escape'], waitRelease=False)
        for k in keys:
            if k.name == 'escape':
                eeg_serial.close(); win.close(); core.quit()
            if k.name in LANES and response_key is None:
                rt_ms = (k.tDown - flash_onset) * 1000
                if rt_ms >= -ANTICIPATION_MS:
                    response_key = k.name
                    response_rt  = rt_ms

        flash_on  = True
        frame_cnt = 0

        while frame_cnt < (flash_frames + deadline_frames):
            frame_cnt += 1

            if flash_on and frame_cnt >= flash_frames:
                squares[finger].fillColor = COLOUR_DEFAULT
                squares[finger].lineColor = COLOUR_DEFAULT
                flash_on = False

            win.clearBuffer()
            draw_scene()

            if marker_frames_left > 0:
                marker_frames_left -= 1
                if marker_frames_left == 0:
                    eeg_serial.write(bytes(chr(MARKER_RESET), 'UTF-8'))

            if response_key is None:
                keys = kb.getKeys(keyList=['v', 'b', 'n', 'm', 'escape'], waitRelease=False)
                for k in keys:
                    if k.name == 'escape':
                        eeg_serial.close(); win.close(); core.quit()
                    if k.name in LANES and response_key is None:
                        response_key = k.name
                        response_rt  = (k.tDown - flash_onset) * 1000

            win.flip()

            if response_key is not None and marker_frames_left == 0:
                break

        squares[finger].fillColor = COLOUR_DEFAULT
        squares[finger].lineColor = COLOUR_DEFAULT

        if response_key is None:
            for _ in range(miss_pause_frames):
                win.clearBuffer()
                draw_scene()
                win.flip()
            kb.clearEvents()
            event.clearEvents()

        if response_key is None:
            accuracy = 'miss'
        elif response_rt < -ANTICIPATION_MS:
            accuracy = 'too_early'
        elif response_key == finger:
            accuracy = 'anticipatory_correct' if response_rt < 0 else 'correct'
        else:
            accuracy = 'anticipatory_incorrect' if response_rt < 0 else 'incorrect'

        isi_before_ms = isi_list[trial_idx - 1] if trial_idx > 0 else None

        if show_feedback:
            if accuracy == 'miss':
                fb_text = 'Miss!'
                feedback_stim.color = 'white'
            elif accuracy in ('correct', 'anticipatory_correct'):
                fb_text = 'Correct'
                feedback_stim.color = 'green'
            elif accuracy in ('incorrect', 'anticipatory_incorrect'):
                fb_text = 'Incorrect'
                feedback_stim.color = 'red'
            else:
                fb_text = ''
                feedback_stim.color = 'white'

            if fb_text:
                for _ in range(feedback_frames):
                    win.clearBuffer()
                    draw_scene(feedback_text=fb_text)
                    win.flip()
                kb.clearEvents()
                event.clearEvents()

        performance_log.append({
            'participant':        expInfo['participant'],
            'age':                expInfo['age'],
            'gender':             GENDER,
            'musical_experience': MUSIC_CODE,
            'group':              GROUP,
            'phase':              phase_name,
            'block':              block_number,
            'trial':              trial_idx + 1,
            'seq_position':       seq_position,
            'target_lane':        finger,
            'response_key':       response_key or 'none',
            'accuracy':           accuracy,
            'rt_ms':              round(response_rt, 2) if response_rt is not None else None,
            'isi_before_ms':      isi_before_ms,
            'monitor_hz':         int(frame_rate),
        })


# ===========================================================================
# EXPLICIT RECALL ROUTINE
# ===========================================================================
def run_explicit_recall():
    instruction_text = (
        "Did you notice a repeating sequence during the main task?\n\n"
        "Press V, B, N, or M to enter the 10-item sequence you learned.\n\n"
        "Press BACKSPACE to remove your last entry. "
        "Press ENTER or SPACE to submit when all 10 items are entered.\n\n"
        "If you are unsure, please guess."
    )

    recall_instruction = visual.TextStim(
        win, text=instruction_text, pos=[0, 0.6], height=0.05, wrapWidth=1.8, color='white'
    )

    # Key hint labels shown below the squares (reuse lane_labels already defined)
    key_hint = visual.TextStim(
        win, text="V          B          N          M",
        pos=[0, SQUARE_Y - 0.10], height=0.05, color='white'
    )

    recalled_sequence = []
    submitted = False

    kb.clearEvents()
    event.clearEvents()

    while not submitted:
        # ------------------------------------------------------------------
        # Flash confirmation: briefly highlight the last-pressed square
        # (reset all to default first, then highlight if sequence non-empty)
        # ------------------------------------------------------------------
        reset_squares()

        win.clearBuffer()
        recall_instruction.draw()

        for sq in squares.values():
            sq.draw()
        for lbl in lane_labels.values():
            lbl.draw()

        progress_str = " - ".join([s.upper() for s in recalled_sequence])
        progress_text = visual.TextStim(
            win,
            text=(f"Items entered: {len(recalled_sequence)} / {SEQ_LENGTH}"
                  f"\n\nYour sequence: {progress_str}"),
            pos=[0, -0.35], height=0.05, color='white'
        )
        progress_text.draw()

        # Show a submit hint only once all 10 items have been entered
        if len(recalled_sequence) == SEQ_LENGTH:
            visual.TextStim(
                win,
                text="Press ENTER or SPACE to submit  |  BACKSPACE to undo",
                pos=[0, -0.60], height=0.045, color='lime'
            ).draw()
        elif len(recalled_sequence) > 0:
            visual.TextStim(
                win,
                text="BACKSPACE = undo last entry",
                pos=[0, -0.60], height=0.045, color='white'
            ).draw()

        win.flip()

        # ------------------------------------------------------------------
        # Wait for a single keypress
        # ------------------------------------------------------------------
        keys = event.waitKeys(
            keyList=['v', 'b', 'n', 'm', 'backspace', 'return', 'space', 'escape']
        )

        if not keys:
            continue

        key = keys[0]

        if key == 'escape':
            eeg_serial.close()
            win.close()
            core.quit()

        elif key in LANES and len(recalled_sequence) < SEQ_LENGTH:
            recalled_sequence.append(key)

            # Brief yellow flash on the corresponding square
            squares[key].fillColor = COLOUR_SELECT
            squares[key].lineColor = COLOUR_SELECT
            win.clearBuffer()
            recall_instruction.draw()
            for sq in squares.values(): sq.draw()
            for lbl in lane_labels.values(): lbl.draw()
            progress_str = " - ".join([s.upper() for s in recalled_sequence])
            visual.TextStim(
                win,
                text=(f"Items entered: {len(recalled_sequence)} / {SEQ_LENGTH}"
                      f"\n\nYour sequence: {progress_str}"),
                pos=[0, -0.35], height=0.05, color='white'
            ).draw()
            win.flip()
            core.wait(0.15)
            squares[key].fillColor = COLOUR_DEFAULT
            squares[key].lineColor = COLOUR_DEFAULT

        elif key == 'backspace' and len(recalled_sequence) > 0:
            recalled_sequence.pop()

        elif key in ('return', 'space') and len(recalled_sequence) == SEQ_LENGTH:
            submitted = True

        kb.clearEvents()
        event.clearEvents()

    # Final screen before moving on
    win.clearBuffer()
    visual.TextStim(
        win, text="Sequence recorded.\n\nSaving your data...",
        pos=[0, 0], height=0.06, color='white'
    ).draw()
    win.flip()
    core.wait(1.5)

    return recalled_sequence


# ===========================================================================
# PERFORMANCE LOG
# ===========================================================================
performance_log = []

# ===========================================================================
# MAIN EXPERIMENT FLOW
# ===========================================================================
try:
    show_message(
        "Welcome to the experiment.\n\n"
        "Four grey squares will appear on screen.\n"
        "When a square flashes RED, press the matching key\n"
        "(V, B, N, or M) as quickly as you can.\n\n"
        "Press SPACE to begin."
    )

    # ------------------------------------------------------------------
    # PHASE 1 - Practice
    # ------------------------------------------------------------------
    show_message(
        "PRACTICE\n\n"
        "Get familiar with the task.\n"
        "Press the key that matches the red square as fast as you can.\n\n"
        "Press SPACE to start."
    )
    prac_seq = generate_random_sequence(RANDOM_TRIALS)
    prac_isi = [CONSTANT_ISI_MS] * len(prac_seq)
    run_srt_block(prac_seq, prac_isi, phase_name='practice', block_number=1)

    # ------------------------------------------------------------------
    # PHASE 2 - Learning
    # ------------------------------------------------------------------
    show_message(
        "MAIN TASK\n\n"
        "You will now complete several blocks.\n"
        "Keep responding to the flashing square as fast as you can.\n\n"
        "Press SPACE to start."
    )

    for blk in range(1, LEARNING_BLOCKS + 1):
        show_message(
            f"Block {blk} of {LEARNING_BLOCKS}\n\n"
            "Press SPACE when ready."
        )
        block_seq = FIXED_SEQUENCE * LEARNING_REPS
        block_isi = generate_isi_list(GROUP, len(block_seq))
        run_srt_block(block_seq, block_isi, phase_name='learning', block_number=blk)
        gc.collect()
        kb.clearEvents()
        event.clearEvents()

    # ------------------------------------------------------------------
    # PHASE 3 - Post-test
    # ------------------------------------------------------------------
    show_message(
        "FINAL PHASE\n\n"
        "Almost done! One last set of trials.\n\n"
        "Press SPACE to start."
    )
    post_seq = generate_random_sequence(RANDOM_TRIALS)
    post_isi = [CONSTANT_ISI_MS] * len(post_seq)
    run_srt_block(post_seq, post_isi, phase_name='posttest', block_number=1)

    # ------------------------------------------------------------------
    # PHASE 4 - Explicit Recall
    # ------------------------------------------------------------------
    show_message(
        "SEQUENCE RECALL\n\n"
        "You will now answer one final question.\n\n"
        "Press SPACE to continue."
    )
    recalled_seq = run_explicit_recall()

    # ------------------------------------------------------------------
    # END
    # ------------------------------------------------------------------
    show_message(
        "Thank you for participating!\n"
        "The experiment is now complete.\n\n"
        "Press SPACE to exit."
    )

    # --- Save data ---
    ts          = expInfo['date|hid']
    perf_file   = f"SRT_{expInfo['participant']}_{GROUP}_{ts}.csv"
    seq_file    = f"SRT_SEQUENCE_{expInfo['participant']}_{ts}.csv"
    recall_file = f"SRT_RECALL_{expInfo['participant']}_{GROUP}_{ts}.csv"

    # Save fixed sequence with cyclical ISI reference values
    with open(seq_file, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['participant', 'seq_position', 'finger', 'cyclical_isi_after_ms'])
        for pos, (finger, isi) in enumerate(zip(FIXED_SEQUENCE, CYCLICAL_ISI), start=1):
            w.writerow([expInfo['participant'], pos, finger, isi])
    print(f"Sequence file saved: {seq_file}")

    # Save explicit recall
    with open(recall_file, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['participant', 'position', 'recalled_finger', 'actual_finger', 'correct'])
        for pos, (recalled, actual) in enumerate(zip(recalled_seq, FIXED_SEQUENCE), start=1):
            is_correct = int(recalled == actual)
            w.writerow([expInfo['participant'], pos, recalled, actual, is_correct])
    print(f"Recall file saved: {recall_file}")

    # Save full performance log
    all_fields = []
    for entry in performance_log:
        for k in entry:
            if k not in all_fields:
                all_fields.append(k)

    with open(perf_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=all_fields)
        writer.writeheader()
        for entry in performance_log:
            writer.writerow(entry)

    print(f"Performance file saved: {perf_file}")
    print(f"Total trials logged: {len(performance_log)}")

except Exception:
    visual.TextStim(
        win,
        text=f"ERROR:\n{traceback.format_exc()}\n\nPress SPACE to quit.",
        color='red', height=0.04
    ).draw()
    win.flip()
    event.waitKeys(keyList=['space'])

finally:
    eeg_serial.close()
    win.close()
    core.quit()