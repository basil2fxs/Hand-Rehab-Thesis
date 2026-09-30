"""Render the game's screens to docs/images/*.png, headless.

Real engine, real screens, a simulated player: the keyboard source for
the lane games, Rhythm and the menus, the test suite's wire rig (a fake
board streaming 200 Hz samples) for Buzz Hunt, Force Pilot and the
quick calibration. The clock is stepped by hand, so every picture is
the same on every machine. The READMEs show these pictures;
tests/test_readme.py checks they exist and tests/test_lane_screen_polish.py
that this script makes every one of them.

Run from app/:  python3 scripts/make_screenshots.py [--out docs/images]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import pygame  # noqa: E402

SIZE = (1280, 800)
FRAME = 1.0 / 60.0

# Every picture main() writes, by file name without .png.
NAMES = ("login", "hand", "hub", "settings", "eeg_port", "reaction_setup",
         "adaptive", "muscle_memory", "chords", "echo", "mirror",
         "syllables", "results", "reaction", "rhythm", "buzz_hunt",
         "calibration", "force_pilot")


class _Clock:
    """time.perf_counter, stepped by the script."""

    def __init__(self) -> None:
        self._real = time.perf_counter
        self.t = self._real()
        time.perf_counter = lambda: self.t

    def restore(self) -> None:
        time.perf_counter = self._real


def _press(lane: int, t: float, hand: str = "right"):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=600, baseline=50.0,
                      hand=hand)


def _keyboard_engine(root: Path, hand: str = "right"):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = list(SIZE)
    cfg.data["session"]["data_dir"] = str(root / "sessions")
    cfg.data["session"]["calibration_dir"] = str(root / "cal")
    cfg.data.setdefault("srt", {})["setups_file"] = str(root / "srt.json")
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    cfg.data["eeg"] = {"enabled": False}
    cfg.data["game"]["start_countdown_s"] = 0
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    cfg.data.setdefault("bilateral", {})["hand"] = hand
    eng = GameEngine(cfg, KeyboardOnlySource(cfg))
    eng.screen = pygame.display.get_surface() or pygame.display.set_mode(SIZE)
    eng._screens = eng._build_screens()
    return eng


def _frame(eng, clock, dt: float = FRAME) -> None:
    clock.t += dt
    eng._pump_source()
    if eng.screen_obj is not None:
        eng.screen_obj.update(dt)
    drain = getattr(eng, "_drain_motor_queue", None)
    if callable(drain):
        drain()
    eng.last_flip_t = clock.t


def _snap(eng, out: Path, name: str, screen=None) -> None:
    surf = pygame.Surface(SIZE)
    (screen or eng.screen_obj).draw(surf)
    out.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surf, str(out / f"{name}.png"))
    print("  ", name)


def _until(eng, clock, pred, frames: int = 3000) -> None:
    for _ in range(frames):
        if pred():
            return
        _frame(eng, clock)
    raise SystemExit(f"screen never reached: {pred}")


def _login(eng, code: str = "P07") -> None:
    eng.begin_session(code, "34", dominant_hand="right", visit="1")
    eng._uncal_ack = {"left", "right"}


def menus(out: Path, clock) -> None:
    with tempfile.TemporaryDirectory() as td:
        eng = _keyboard_engine(Path(td))
        eng.show_title()
        for _ in range(30):
            _frame(eng, clock)
        _snap(eng, out, "login")
        _login(eng)
        eng.show_hand_choice()
        for _ in range(10):
            _frame(eng, clock)
        _snap(eng, out, "hand")
        eng.show_mode_select()
        for _ in range(30):
            _frame(eng, clock)
        _snap(eng, out, "hub")
        eng.show_diagnostics()
        for _ in range(10):
            _frame(eng, clock)
        _snap(eng, out, "settings")
        eng.show_eeg_port()
        for _ in range(10):
            _frame(eng, clock)
        _snap(eng, out, "eeg_port")
        eng.show_srt_setup()
        for _ in range(10):
            _frame(eng, clock)
        _snap(eng, out, "reaction_setup")
        eng._close_loggers()


def lane_game(out: Path, clock, key: str, name: str, presses: int = 0,
              hand: str = "right") -> None:
    """A lane game mid-block: `presses` correct answers first, so the
    score and the streak are not zero, then the next cue on screen."""
    with tempfile.TemporaryDirectory() as td:
        eng = _keyboard_engine(Path(td), hand)
        _login(eng)
        if key == "mirror":
            eng.hand_mode = "both"
            eng._build_detectors()
            for k in ("gameplay", "rhythm"):
                sc = eng._screens.get(k)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()
            eng.begin_mirror_block()
        else:
            if not eng.begin_game(key, hand):
                raise SystemExit(f"{key} refused to start")
        mode = eng.mode

        def cue_up() -> bool:
            if key == "echo":
                return mode.phase == "play" and mode._lit_lane is not None
            return getattr(mode, "active", None) is not None

        for _ in range(presses):
            _until(eng, clock, cue_up)
            active = mode.active
            # A chord trial names its target lanes; every other trial
            # has the one lane.
            lanes = list(getattr(active, "targets", None)
                         or [active.lane])
            for lane in lanes:
                mode.queue_press(_press(lane, clock.t + 0.25,
                                        "left" if lane >= 4 else "right"))
            _frame(eng, clock, 0.3)
            _until(eng, clock, lambda: getattr(mode, "active", None) is None,
                   600)
        _until(eng, clock, cue_up)
        for _ in range(4):
            _frame(eng, clock)
        _snap(eng, out, name)
        eng._abandon_if_in_block()
        eng._close_loggers()


def syllables(out: Path, clock) -> None:
    """Syllables for a nine year old, in the hear and pick section: the
    word's first part already found, the four chunks for the next one
    on screen."""
    with tempfile.TemporaryDirectory() as td:
        eng = _keyboard_engine(Path(td))
        eng.cfg.data["syllables"]["speech"] = {"backend": "off"}
        eng.begin_session("P07", "9", dominant_hand="right", visit="1")
        eng._uncal_ack = {"left", "right"}
        if not eng.begin_game("syllables", "right"):
            raise SystemExit("syllables refused to start")
        mode = eng.mode
        answered: set = set()

        def open_set() -> bool:
            return (mode.phase == "choose" and mode.option_set is not None
                    and mode._set_close_t is None)

        for _ in range(60 * 60 * 10):
            _frame(eng, clock)
            if not open_set() or clock.t < mode._spawn_t + 0.6:
                continue
            if mode.section == "pick" and mode.pos == 1:
                if clock.t >= mode._spawn_t + 1.2:
                    break
                continue
            if mode.trial_counter not in answered:
                answered.add(mode.trial_counter)
                mode.queue_press(_press(mode.option_set.target_lane,
                                        clock.t))
        else:
            raise SystemExit("no second set in the pick section")
        _snap(eng, out, "syllables")
        eng._abandon_if_in_block()
        eng._close_loggers()


def results(out: Path, clock) -> None:
    with tempfile.TemporaryDirectory() as td:
        eng = _keyboard_engine(Path(td))
        _login(eng)
        eng.begin_game("adaptive", "right")
        mode = eng.mode
        for i in range(14):
            _until(eng, clock, lambda: mode.active is not None)
            lane = mode.active.lane
            if i % 5 == 3:
                lane = (lane + 1) % 4
            mode.queue_press(_press(lane, clock.t + 0.3))
            _frame(eng, clock, 0.35)
            _until(eng, clock, lambda: mode.active is None, 600)
        eng.finish_block()
        for _ in range(60):
            _frame(eng, clock)
        _snap(eng, out, "results")
        eng._close_loggers()


def reaction(out: Path, clock) -> None:
    from tests.test_srt_mode import Sim, _engine, _fast_cfg, _use
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _use(root)
        eng = _engine(root, **_fast_cfg())
        eng.set_hand_mode("right")
        eng.begin_srt_block()
        sim = Sim(eng)
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        tr = eng.mode.trial
        while tr.onset is None:
            sim.frame()
        for _ in range(2):
            sim.frame()
        _snap(eng, out, "reaction", eng._screens["srt"])
        eng._abandon_if_in_block()
        eng._close_loggers()


def rhythm(out: Path, clock) -> None:
    """Rhythm on the battery's song and difficulty, eight seconds in,
    every note so far pressed on its beat so the score and the streak
    are not zero. Without the song in assets/music the chart is a
    90 BPM procedural one."""
    from finger_rehab.audio.beatmap import extract_beatmap, procedural_beatmap
    from finger_rehab.game.battery import find_track
    with tempfile.TemporaryDirectory() as td:
        eng = _keyboard_engine(Path(td))
        _login(eng)
        track = find_track(eng.cfg, "Easy_Lemon.mp3")
        bm = (extract_beatmap(str(track), difficulty="medium", num_lanes=4)
              if track is not None
              else procedural_beatmap(bpm=90, beats=180))
        eng.begin_rhythm_block(bm)
        mode = eng.mode
        _frame(eng, clock)
        mode.skip_wait()
        pressed: set = set()
        while mode.song_time < 8.0:
            for i, note in enumerate(mode.beatmap.notes):
                if i not in pressed and note.t <= mode.song_time:
                    pressed.add(i)
                    mode.queue_press(_press(note.lane, clock.t))
            _frame(eng, clock)
        _snap(eng, out, "rhythm", eng._screens["rhythm"])
        eng._abandon_if_in_block()
        eng._close_loggers()


def force_pilot(out: Path) -> None:
    """Force Pilot on the fake board, six seconds into the first run,
    the index finger following the wave a little off its centre."""
    import math
    from tests.test_echo_mode import (RESTING, _make_wire_engine,
                                      patched_clock)
    with tempfile.TemporaryDirectory() as td, patched_clock() as clock:
        eng, rig = _make_wire_engine(td, clock, buzz_after=False)
        # The rig runs the short test ladder; the picture shows the game.
        eng.cfg.data["game"]["test_mode_enabled"] = False
        eng.cfg.data["game"]["start_countdown_s"] = 0
        eng._screens = eng._build_screens()
        max_counts = eng.calibration_profiles["right"].max_press
        next_sample = clock.t

        def frame(mode=None) -> None:
            nonlocal next_sample
            clock.t += FRAME
            while next_sample <= clock.t:
                vals = [RESTING] * 4
                target = getattr(mode, "target_now", None)
                if getattr(mode, "phase", "") == "run" and target is not None:
                    pct = target + 1.5 * math.sin(next_sample * 3.0)
                    vals[mode.lane] = int(round(
                        RESTING + pct / 100.0 * max_counts[mode.finger]))
                rig.push(next_sample, vals)
                next_sample += 1.0 / 200.0
            eng._pump_source()
            eng.screen_obj.update(FRAME)
            eng._drain_motor_queue()

        for _ in range(300):
            if (eng.detectors.get("right") is not None
                    and eng.detectors["right"].baseline[0] is not None):
                break
            frame()
        eng.begin_force_pilot_block()
        mode = eng.mode
        # Straight to the first run: the max-press probes need a real
        # squeeze and the calibration already carries the maximum. The
        # mode prepares run 1 on its first tick and announces it; the
        # finger stays off until the run, since the announce re-tares.
        mode._probe_queue.clear()
        for _ in range(600):
            if mode.phase == "announce":
                break
            frame(mode)
        mode.skip_wait()
        for _ in range(6 * 60):
            frame(mode)
        _snap(eng, out, "force_pilot", eng._screens["force_pilot"])
        eng._abandon_if_in_block()
        eng._close_loggers()


def wire_games(out: Path) -> None:
    """Buzz Hunt and the quick calibration on the fake board."""
    from tests.test_echo_mode import _Pump, _make_wire_engine, patched_clock
    with tempfile.TemporaryDirectory() as td, patched_clock() as clock:
        eng, rig = _make_wire_engine(td, clock, buzz_after=False)
        eng._screens = eng._build_screens()
        pump = _Pump(eng, rig, clock)
        pump.until(lambda: eng.detectors.get("right") is not None
                   and eng.detectors["right"].baseline[0] is not None, 300)
        eng.begin_buzz_hunt_block()
        mode = eng.mode
        pump.until(lambda: getattr(mode, "sub", "") == "respond", 6000)
        for _ in range(6):
            pump.frame()
        _snap(eng, out, "buzz_hunt", eng._screens["buzz_hunt"])
        eng._abandon_if_in_block()
        eng.show_quick_calibration(hands=["right"])
        for _ in range(240):
            pump.frame()
        _snap(eng, out, "calibration", eng._screens["quick_cal"])
        eng._close_loggers()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=APP / "docs" / "images")
    ap.add_argument("--only", nargs="*", default=None,
                    help="names to render (default: all)")
    args = ap.parse_args(argv)
    pygame.init()
    pygame.display.set_mode(SIZE)
    out = args.out
    want = set(args.only or [])

    def go(name: str) -> bool:
        return not want or name in want

    print("rendering to", out)
    clock = _Clock()
    try:
        if go("menus"):
            menus(out, clock)
        for key, name, presses in (("adaptive", "adaptive", 6),
                                   ("pattern", "muscle_memory", 5),
                                   ("chords", "chords", 3),
                                   ("echo", "echo", 0),
                                   ("mirror", "mirror", 0)):
            if go(name):
                lane_game(out, clock, key, name, presses)
        if go("syllables"):
            syllables(out, clock)
        if go("results"):
            results(out, clock)
        if go("reaction"):
            reaction(out, clock)
        if go("rhythm"):
            rhythm(out, clock)
    finally:
        clock.restore()
    if go("buzz_hunt") or go("calibration"):
        wire_games(out)
    if go("force_pilot"):
        force_pilot(out)
    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
