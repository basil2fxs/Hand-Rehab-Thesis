"""Quick calibration, run automatically after the hand pick the first
time a session needs a hand.

Why this exists. The clinical CalibrationScreen on the menu is right
for a therapist doing a deliberate measurement, but it is the wrong
first minute for a new player: nothing on it says how hard a press is
meant to be, and a session started without any profile runs on config
defaults measured on a different hand. This screen closes both gaps at
once: it collects the exact same three captures the clinical flow
collects (empty, resting, a light press per finger), and it teaches
the light press by showing it. The player presses a big vertical bar
into a goal band and holds it there; the level they hold IS the light
press the profile stores, so the press they just learned is the press
every mode will score.

What it deliberately is not: a fork of the threshold maths. Every
number saved here goes through CalibrationProfile, the same class the
clinical screen fills in, saved to the same per-hand file and applied
through the same engine.apply_calibration path. The GOAL BAND is not a
tuning knob either: it comes from calibration_profile.target_gap_band,
built out of the same MIN_USABLE_GAP / MIN_DELTA_COUNTS /
MIN_NOISE_MULTIPLE / MAX_TRIGGER_FRACTION the thresholds are computed
from, fed with THIS run's own empty and resting captures. So the band
sits higher on a preloaded pinky than on a clean index, because that is
exactly where those fingers' thresholds will sit, and a press held
anywhere in the band is guaranteed to produce a profile usable() will
accept. If the threshold rules ever change, the coaching changes with
them.

Flow, kept under a minute per hand:

    hands off      sensors must read QUIET before this captures, and
                   the screen names the finger that is still down
    hands resting  the tare point, with the rest level drawn as it is
                   learned
    per finger     press the bar into the band, hold the ring round,
                   pop, next finger
    summary        one warm line per finger, then straight to the game

Both rest captures cover EVERY hand in the run at once: with two
boards all eight sensors ride in the same sample vector, so a
bilateral run pays the waiting cost once, not twice. Only the
per-finger part repeats per hand, left hand first, matching the lane
strips which put the left hand on the left of the screen.

The one rule the visuals follow: the screen always says the ONE thing
to do next, and nothing else competes with it. Below the band the bar
is cool and asks for more; inside it the bar is green and the hold ring
fills; above it the bar is amber, the ring STOPS, and it asks for less,
because rewarding a crush would save a trigger the same finger cannot
reach when it is tired. A finger that is not the one being asked for is
named rather than silently ignored.

The skip rules mirror the rest of the app. A keyboard session never
sees this screen at all (there is no force to calibrate, and the game
notice for that lives on mode select, not here). Calibration is a
session event: each hand runs the flow once, the first time a game in
the session needs it, and every later game in that session skips it,
hand-mode changes included; the trigger decision is the engine's, in
maybe_start_quick_calibration, with the per-session memory held on
the engine and cleared when the session ends. "Skip for now" is
always on screen and leaves whatever profile was saved before
completely untouched. Esc asks before abandoning, so a stray key
cannot throw away a half-done run.

Flash safety: every colour change here is state-driven (the bar's
three zones, the band glow, the quiet line) so none of them can
oscillate on their own; the capture pop and the chip pop are one-shots
of 0.7 s; the countdown arc and the live traces sweep continuously.
Nothing repeats at any rate, let alone above 3 Hz. Screen conventions
match the rest of the app: 1280x800 logical layout, theme-aware, Esc
handled through the engine's global event path.
"""
from __future__ import annotations

import logging
import math
import statistics
import time
from typing import TYPE_CHECKING, Callable

import pygame

from .screens import Screen, _draw_header
from .widgets import (
    Button, FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL,
    draw_text, make_font,
)
from .calibration_screen import _percentile
from ..hardware.calibration_profile import (
    CalibrationProfile, FINGER_NAMES, MIN_DELTA_COUNTS, N_FINGERS,
    target_gap_band,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine

log = logging.getLogger(__name__)

PHASE_OFF = "hands_off"
PHASE_REST = "resting"
PHASE_PRESS = "press"
PHASE_DONE = "done"

# How long the completion pop and the GOT IT! text stay up before the
# next finger takes over. Long enough to feel like a reward, short
# enough that eight fingers still finish inside a minute.
POP_S = 0.7

# Seconds of samples the live traces draw, and the slice of that used to
# decide the sensors have stopped moving.
HIST_S = 3.0
QUIET_WINDOW_S = 0.6

# Peak-to-peak counts a sensor may wander over QUIET_WINDOW_S and still
# count as settled. Set above the per-sample noise of a quiet board so a
# genuinely empty device passes on the first look, and well under
# MIN_DELTA_COUNTS so a finger coming off the pad does not.
QUIET_SPREAD_COUNTS = 6.0

# How long the settled reading must hold before a rest capture starts on
# its own. Long enough that the tail of a hand lifting off does not
# trigger it, short enough that it feels automatic.
QUIET_HOLD_S = 0.8

# No sample this recently means the device, not the player, is the
# problem, and the screen has to say so instead of waiting silently.
STALE_S = 1.0

# Counts a lane may sit above the lowest it has read during the hands-off
# phase before the screen calls that finger "still down". MIN_DELTA_COUNTS
# is the smallest press threshold the maths will ever set, so anything at
# or above it is a load the empty capture must not include.
LANE_DOWN_COUNTS = float(MIN_DELTA_COUNTS)

# Full-scale of the quiet line, in counts above each lane's own floor.
QUIET_TRACE_COUNTS = 80.0

# How far a settled lane's trace is pulled toward the page colour. The
# alert amber is drawn at full strength, so every quiet trace has to
# sit clearly under it; see the note where it is used for why 0.15 was
# not enough.
QUIET_TRACE_FADE = 0.45

# ---- press-phase geometry, 1280x800 logical -----------------------------
BAR = pygame.Rect(500, 300, 160, 352)
HAND_MAP = pygame.Rect(168, 322, 216, 250)
RING_CENTRE = (990, 462)
RING_R = 78


class QuickCalibrationScreen(Screen):
    """Visual light-press capture. Fills a CalibrationProfile per hand
    by coaching a press into a band the threshold maths derives, then
    saves and applies it exactly as the clinical screen would."""

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.hands: list[str] = ["right"]
        self._continue: Callable[[], None] | None = None
        self.phase = PHASE_OFF

        # Captures per hand, raw counts, same shape the clinical flow
        # measures. press starts at zeros and is filled one finger at
        # a time by the bar.
        self._captures: dict[str, dict[str, list[float]]] = {}

        # Rest-capture state (hands off / hands resting). The buffer
        # holds one row of four values per hand per sample.
        self._collecting = False
        self._collect_until = 0.0
        self._rest_buffers: dict[str, list[list[float]]] = {}

        # Rolling raw history, (sample time, whole value vector), used
        # for every live trace and for the settled test. Sample time is
        # the device's own, so the window maths works the same headless
        # as it does at frame rate.
        self._hist: list[tuple[float, tuple[float, ...]]] = []
        self._last_sample_at = 0.0
        # Lowest each sensor has read since the hands-off phase began.
        # The only zero reference available before the empty capture
        # exists, which is what makes "lift your ring finger" possible
        # at all. A finger held down for the entire phase reads as its
        # own floor, so this names a finger that comes off, and the
        # settled test is what stops the capture running mid-lift.
        self._floor: list[float] = []
        self._quiet_since = 0.0
        self._phase_started_at = time.perf_counter()

        # Press-game state.
        self._hand_idx = 0
        self._finger_idx = 0
        self._hold = 0.0               # 0..1 fill of the hold ring
        self._in_zone = False
        self._zone_buffer: list[float] = []
        self._landed = False           # this finger's press captured
        self._advance_at = 0.0         # when to move to the next finger
        self._pop_at = 0.0             # when the completion pop started
        self._started_finger_at = 0.0  # for the struggling-finger hint
        self._wrong: int | None = None  # a finger down that was not asked for

        # Built once the whole run has captured, so the summary and the
        # save button work off the same objects.
        self._profiles: dict[str, CalibrationProfile] = {}
        self._problems: list[str] = []

        self._confirm = False          # Esc guard overlay
        self._dim_cache: pygame.Surface | None = None

        self._status = ""
        self._buttons: list[Button] = []
        self._confirm_buttons: list[Button] = []
        self._rebuild_buttons()

    # ---- tunables --------------------------------------------------------

    def _cfgf(self, key: str, default: float) -> float:
        try:
            return float(self.engine.cfg.get(f"quick_cal.{key}", default))
        except (TypeError, ValueError):
            return default

    def _rest_capture_s(self) -> float:
        return max(0.5, self._cfgf("rest_capture_s", 2.0))

    def _hold_s(self) -> float:
        return max(0.3, self._cfgf("hold_s", 1.0))

    # ---- the goal band ---------------------------------------------------

    def _band(self, hand: str, finger: int) -> tuple[float, float]:
        """The gap this finger's press should land in, in counts above
        its resting level.

        Straight out of the threshold maths: preload and sensor noise
        from this run's own captures, through the same
        target_gap_band the profile's on_delta and usable() are built
        on. There is no separate tuning for the visuals, deliberately,
        because a band the player can hit that the maths then rejects
        is the exact failure this screen exists to remove.
        """
        cap = self._captures.get(hand)
        if not cap:
            return target_gap_band(0.0, 0.0)
        preload = max(0.0, cap["resting"][finger] - cap["empty"][finger])
        return target_gap_band(preload, cap["empty_noise"][finger])

    def _bar_max(self) -> float:
        """Full scale of the pressure bar. Headroom above the band so a
        press that overshoots visibly climbs out of the goal instead of
        pinning at the top with nothing left to show."""
        return self._band(self._current_hand(), self._finger_idx)[1] * 1.35

    # ---- entry -----------------------------------------------------------

    def begin(self, hands: list[str],
              continue_cb: Callable[[], None] | None = None) -> None:
        """Start a run over the given hands. continue_cb is what
        happens when the run finishes or is skipped; the engine passes
        the block start when the flow gates a session, and the menu
        passes nothing, which lands back on the title."""
        wanted = [h for h in hands if h in ("left", "right")]
        # Left first: the lane strips put the left hand on the left of
        # the screen, so the flow reads in the same order the lanes do.
        self.hands = (sorted(set(wanted), key=lambda h: h != "left")
                      or ["right"])
        self._continue = continue_cb or self.engine.show_title
        self._captures = {
            h: {"empty": [0.0] * N_FINGERS,
                "empty_noise": [0.0] * N_FINGERS,
                "resting": [0.0] * N_FINGERS,
                "press": [0.0] * N_FINGERS}
            for h in self.hands
        }
        self.phase = PHASE_OFF
        self._collecting = False
        self._rest_buffers = {}
        self._hist = []
        self._last_sample_at = 0.0
        self._floor = []
        self._quiet_since = 0.0
        self._phase_started_at = time.perf_counter()
        self._hand_idx = 0
        self._finger_idx = 0
        self._reset_finger_state()
        self._profiles = {}
        self._problems = []
        self._confirm = False
        self._status = ""
        self._rebuild_buttons()

    def _reset_finger_state(self) -> None:
        self._hold = 0.0
        self._in_zone = False
        self._zone_buffer = []
        self._landed = False
        self._advance_at = 0.0
        self._pop_at = 0.0
        self._wrong = None
        self._started_finger_at = time.perf_counter()

    # ---- who is being measured ------------------------------------------

    def _current_hand(self) -> str:
        return self.hands[min(self._hand_idx, len(self.hands) - 1)]

    def _finger_no(self) -> tuple[int, int]:
        """1-based (current, total) across the whole run, for the
        "Finger 3 of 8" counter."""
        return (self._hand_idx * N_FINGERS + self._finger_idx + 1,
                len(self.hands) * N_FINGERS)

    def _per_hand(self) -> int:
        try:
            return int(self.engine.cfg.get("fsr.num_sensors_per_hand", 4))
        except (TypeError, ValueError):
            return N_FINGERS

    def _hand_offset(self, hand: str, length: int) -> int:
        """Where one hand's values start in the sample vector.

        Mirrors _feed_detectors' rule exactly: an 8-value sample is
        right then left, and a short sample in a left-only session IS
        the left board. Slicing right-first here regardless would
        measure the idle right board while the player presses with
        their left, the same fault the clinical screen documents.

        Split out from _hand_slice because the live traces re-slice a
        few hundred buffered samples every frame, and re-deriving this
        (a config lookup each time) per sample is the one thing on this
        screen that could cost frames.
        """
        n = self._per_hand()
        if hand != "left":
            return 0
        if self.engine.hand_mode == "left" and length < n * 2:
            return 0
        return n

    def _hand_slice(self, values, hand: str) -> list[float]:
        """One hand's four raw values out of the sample vector."""
        vals = list(values)
        off = self._hand_offset(hand, len(vals))
        out = [float(v) for v in vals[off:off + N_FINGERS]]
        while len(out) < N_FINGERS:
            out.append(0.0)
        return out

    def _live_all(self) -> list[float]:
        """Every finger on the current hand, smoothed, above its
        captured resting level. Read from the same detector value the
        game itself scores on, so what the bar shows is what the mode
        will see."""
        hand = self._current_hand()
        det = (self.engine.detectors or {}).get(hand)
        cap = self._captures.get(hand)
        if det is None or cap is None:
            return [0.0] * N_FINGERS
        out = []
        for i in range(N_FINGERS):
            try:
                v = det.val_ema[i]
                if v is None:
                    v = float(det.last_value[i])
            except (AttributeError, IndexError, TypeError):
                v = 0.0
            out.append(float(v) - cap["resting"][i])
        return out

    def _live_counts(self) -> float:
        """The finger currently being asked for."""
        return self._live_all()[self._finger_idx]

    def _wrong_finger(self, live: list[float]) -> int | None:
        """A finger other than the one being asked for that is loaded
        past its own goal floor, or None.

        The same floor the target finger has to clear is the test:
        below it a lane is inside the run of a resting hand, above it
        the lane is genuinely being pressed, and letting that ride
        would fold a second finger's force into this finger's press
        level.
        """
        hand = self._current_hand()
        worst, worst_v = None, 0.0
        for i in range(N_FINGERS):
            if i == self._finger_idx:
                continue
            lo, _ = self._band(hand, i)
            if live[i] >= lo and live[i] > worst_v:
                worst, worst_v = i, live[i]
        return worst

    # ---- sample intake ---------------------------------------------------

    def on_sample(self, t_perf: float, values) -> None:
        """Every sample off the device, pushed by the engine's pump,
        exactly as the clinical screen receives them. Rest captures
        buffer all hands at once; the press phase buffers only the
        current finger, and only while the press sits in the band, so
        the 95th percentile lands on the held plateau."""
        if self._confirm:
            return
        vals = tuple(float(v) for v in values)
        if self._hist and float(t_perf) < self._hist[-1][0]:
            # Stamps went backwards. A board reconnecting restarts its
            # clock, and keeping the rows either side would have the
            # settle window comparing readings from two different ones,
            # which reads as movement that is not there.
            self._hist = []
        self._hist.append((float(t_perf), vals))
        cutoff = float(t_perf) - HIST_S
        if self._hist[0][0] < cutoff:
            self._hist = [row for row in self._hist if row[0] >= cutoff]
        self._last_sample_at = time.perf_counter()
        if self.phase == PHASE_OFF:
            if len(self._floor) != len(vals):
                self._floor = list(vals)
            else:
                self._floor = [min(f, v)
                               for f, v in zip(self._floor, vals)]
        if self._collecting and self.phase in (PHASE_OFF, PHASE_REST):
            for hand in self.hands:
                self._rest_buffers.setdefault(hand, []).append(
                    self._hand_slice(vals, hand))
        elif (self.phase == PHASE_PRESS and self._in_zone
                and not self._landed):
            hand = self._current_hand()
            self._zone_buffer.append(
                self._hand_slice(vals, hand)[self._finger_idx])

    def _start_collecting(self) -> None:
        self._rest_buffers = {}
        self._collecting = True
        self._collect_until = time.perf_counter() + self._rest_capture_s()
        self._rebuild_buttons()

    def _seconds_left(self) -> float:
        return max(0.0, self._collect_until - time.perf_counter())

    # ---- the settled test ------------------------------------------------

    def _stale(self) -> bool:
        """No sample arrived recently. The device is the problem, and
        the screen has to say so rather than sit on a prompt the
        player cannot satisfy."""
        return (self._last_sample_at <= 0.0
                or time.perf_counter() - self._last_sample_at > STALE_S)

    def _window_rows(self) -> list[tuple[float, ...]]:
        """Samples inside the settle window, measured against the last
        sample's own timestamp so the test behaves identically at
        frame rate and in a headless run."""
        if not self._hist:
            return []
        now = self._hist[-1][0]
        return [v for (t, v) in self._hist if now - t <= QUIET_WINDOW_S]

    def _spread(self) -> float | None:
        """Widest peak-to-peak any single sensor shows over the settle
        window, or None when there is not enough to judge.

        Only the hands this run covers. A bilateral rig always sends all
        eight sensors, so watching the whole vector would let the OTHER
        hand, sitting on its pads and doing nothing in particular, hold
        up a calibration it is not part of.
        """
        rows = self._window_rows()
        if len(rows) < 3:
            return None
        worst: float | None = None
        for hand in self.hands:
            off = self._hand_offset(hand, len(rows[-1]))
            for i in range(N_FINGERS):
                vals = [r[off + i] for r in rows if off + i < len(r)]
                if len(vals) < 3:
                    continue
                worst = max(worst or 0.0, max(vals) - min(vals))
        return worst

    def _lanes_down(self) -> list[tuple[str, int]]:
        """(hand, finger) for every lane carrying load during the
        hands-off phase, worst first."""
        if self.phase != PHASE_OFF or not self._hist or not self._floor:
            return []
        cur = self._hist[-1][1]
        over: list[tuple[float, str, int]] = []
        for hand in self.hands:
            here = self._hand_slice(cur, hand)
            floor = self._hand_slice(self._floor, hand)
            for i in range(N_FINGERS):
                lift = here[i] - floor[i]
                if lift >= LANE_DOWN_COUNTS:
                    over.append((lift, hand, i))
        over.sort(reverse=True)
        return [(h, i) for _, h, i in over]

    def _lanes_leaning(self) -> list[tuple[str, int]]:
        """(hand, finger) for every lane so loaded during the resting
        phase that the maths could not carry it.

        Derived, not guessed: a pad whose load pushes its goal floor
        above the light-press ceiling a clean pad would get is one no
        light press can satisfy, which is either a finger pressing or a
        pad sitting wrong. Either way the run has to say so before it
        captures the level as "rest".
        """
        if self.phase != PHASE_REST or not self._hist:
            return []
        cur = self._hist[-1][1]
        out: list[tuple[float, str, int]] = []
        for hand in self.hands:
            here = self._hand_slice(cur, hand)
            cap = self._captures[hand]
            for i in range(N_FINGERS):
                noise = cap["empty_noise"][i]
                load = max(0.0, here[i] - cap["empty"][i])
                if target_gap_band(load, noise)[0] > target_gap_band(
                        0.0, noise)[1]:
                    out.append((load, hand, i))
        out.sort(reverse=True)
        return [(h, i) for _, h, i in out]

    def _blockers(self) -> list[tuple[str, int]]:
        return (self._lanes_down() if self.phase == PHASE_OFF
                else self._lanes_leaning())

    def _settled(self) -> bool:
        """Whether a rest capture may start. Everything has to be true:
        samples arriving, nothing moving, no lane carrying load it
        should not be."""
        if self._stale():
            return False
        sp = self._spread()
        if sp is None or sp > QUIET_SPREAD_COUNTS:
            return False
        return not self._blockers()

    # ---- flow ------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._confirm:
            return
        if self._collecting and self._seconds_left() <= 0:
            self._collecting = False
            self._finish_rest_capture()
            self._rebuild_buttons()
            return
        if self.phase in (PHASE_OFF, PHASE_REST) and not self._collecting:
            self._maybe_auto_start()
        elif self.phase == PHASE_PRESS:
            self._update_press_game(dt)

    def _maybe_auto_start(self) -> None:
        """The rest captures start themselves once the sensors go
        quiet and stay quiet.

        No "I'm ready" button on purpose. A button is a second thing on
        screen competing with the instruction, and it lets a capture
        run while a finger is still down: the player says ready, the
        press gets averaged into the zero, and every threshold in the
        session is built on it. Waiting for the sensors to agree makes
        that impossible.
        """
        now = time.perf_counter()
        if not self._settled():
            self._quiet_since = 0.0
            return
        if self._quiet_since <= 0.0:
            self._quiet_since = now
        elif now - self._quiet_since >= QUIET_HOLD_S:
            self._quiet_since = 0.0
            self._start_collecting()

    def _finish_rest_capture(self) -> None:
        empty_step = self.phase == PHASE_OFF
        for hand in self.hands:
            rows = self._rest_buffers.get(hand) or []
            if not rows:
                self._status = ("No samples arrived. Check the device on "
                                "the Settings screen, then try again.")
                return
            cols = list(zip(*rows))
            cap = self._captures[hand]
            if empty_step:
                # Same reduction the clinical flow uses: mean for the
                # level, population SD for the noise floor.
                cap["empty"] = [statistics.fmean(c) for c in cols]
                cap["empty_noise"] = [
                    statistics.pstdev(c) if len(c) > 1 else 0.0
                    for c in cols]
            else:
                cap["resting"] = [statistics.fmean(c) for c in cols]
        self._status = ""
        self._quiet_since = 0.0
        self._phase_started_at = time.perf_counter()
        if empty_step:
            self.phase = PHASE_REST
        else:
            self.phase = PHASE_PRESS
            self._hand_idx = 0
            self._finger_idx = 0
            self._reset_finger_state()

    def _update_press_game(self, dt: float) -> None:
        now = time.perf_counter()
        if self._landed:
            if now >= self._advance_at:
                self._advance_finger()
            return
        live = self._live_all()
        me = live[self._finger_idx]
        lo, hi = self._band(self._current_hand(), self._finger_idx)
        self._wrong = self._wrong_finger(live)
        # Over the ceiling or contaminated by a second finger, the hold
        # stops rather than banking. A crush press sets a trigger this
        # finger will not reach again once it is tired, and a two-finger
        # press is not this finger's level at all.
        self._in_zone = (lo <= me <= hi) and self._wrong is None
        if self._in_zone:
            self._hold = min(1.0, self._hold + dt / self._hold_s())
        else:
            # Drain rather than reset: a wobble out of the band costs a
            # moment, not the whole hold. A drained meter also clears
            # the buffer so a stale plateau cannot leak into the next
            # attempt's percentile.
            self._hold = max(0.0, self._hold - dt / (self._hold_s() * 0.6))
            if self._hold <= 0.0:
                self._zone_buffer = []
        if self._hold >= 1.0 and self._zone_buffer:
            self._capture_press()

    def _capture_press(self) -> None:
        hand = self._current_hand()
        i = self._finger_idx
        # 95th percentile of the held plateau, the same statistic the
        # clinical flow takes, for the same reason: one corrupt frame
        # must not become the press level.
        press = _percentile(self._zone_buffer, 0.95)
        lo, _ = self._band(hand, i)
        gap = press - self._captures[hand]["resting"][i]
        if gap < lo:
            # The band floor makes this nearly unreachable, but a noisy
            # buffer can still land short. Ask again rather than saving
            # a threshold that cannot both trigger and release.
            self._status = "Almost. A touch firmer this time."
            self._hold = 0.0
            self._zone_buffer = []
            return
        self._captures[hand]["press"][i] = press
        self._status = ""
        self._landed = True
        self._in_zone = False
        now = time.perf_counter()
        self._pop_at = now
        self._advance_at = now + POP_S

    def _advance_finger(self) -> None:
        self._finger_idx += 1
        if self._finger_idx >= N_FINGERS:
            self._finger_idx = 0
            self._hand_idx += 1
            if self._hand_idx >= len(self.hands):
                self._enter_summary()
                return
        self._reset_finger_state()

    def _enter_summary(self) -> None:
        """Build one CalibrationProfile per hand from the captures.
        Built here, once, so the summary text and the save button work
        off the same objects and the same usable() verdict."""
        self.phase = PHASE_DONE
        self._profiles = {}
        self._problems = []
        for hand in self.hands:
            cap = self._captures[hand]
            prof = CalibrationProfile(
                hand=hand,
                participant=getattr(self.engine.session, "participant",
                                    "") or "",
                empty=list(cap["empty"]),
                empty_noise=list(cap["empty_noise"]),
                resting=list(cap["resting"]),
                press=list(cap["press"]),
            )
            try:
                prof.device_port = str(
                    getattr(self.engine.source, "port", "") or "")
            except Exception:
                prof.device_port = ""
            self._profiles[hand] = prof
            ok, problems = prof.usable()
            if not ok:
                self._problems.extend(problems)
        self._rebuild_buttons()

    # ---- finish / skip / abandon ----------------------------------------

    def _finish(self) -> None:
        """Save every hand's profile through the same path the clinical
        screen uses, apply through the engine, then hand over to
        whatever the run was gating."""
        cfg = self.engine.cfg
        for hand, prof in self._profiles.items():
            try:
                path = cfg.resolve_path(
                    f"config/calibration/current_{hand}.json")
                prof.save(path)
                # Dated copy, same convention as the clinical save, so
                # a quick calibration never silently destroys the one
                # before it.
                stamp = prof.created_at.replace(":", "").replace("-", "")
                prof.save(cfg.resolve_path(
                    f"config/calibration/history/{stamp}.json"))
            except OSError as e:
                log.warning("quick calibration save failed for %s: %s",
                            hand, e)
                self._status = f"Could not save: {e}"
                return
            self.engine.apply_calibration(prof)
        log.info("quick calibration saved and applied for %s",
                 ", ".join(self._profiles))
        self._go_on()

    def _skip(self) -> None:
        """Proceed without measuring. Anything saved earlier stays
        exactly as it was; the session runs on whatever thresholds are
        already applied. Deliberate escape hatch for a hurried
        clinician, so it must never write anything."""
        log.info("quick calibration skipped")
        self._go_on()

    def _go_on(self) -> None:
        cb = self._continue or self.engine.show_title
        self._continue = None
        cb()

    def _retry(self) -> None:
        self.begin(list(self.hands), self._continue)

    def on_escape(self) -> None:
        """Esc asks before abandoning. First Esc raises the guard,
        Esc again (or the Stop button) confirms; Keep going lowers it.
        Abandoning discards the run and lands where the player came
        from: game select mid-session (the flow gated a game start),
        the login screen otherwise (a menu launch before any login)."""
        if self._confirm:
            self._abandon()
        else:
            self._confirm = True
            self._rebuild_buttons()

    def _keep_going(self) -> None:
        self._confirm = False
        self._quiet_since = 0.0
        self._rebuild_buttons()

    def _abandon(self) -> None:
        self._confirm = False
        self._continue = None
        if getattr(self.engine, "_session_active", False):
            self.engine.show_mode_select()
        else:
            self.engine.show_title()

    # ---- buttons ---------------------------------------------------------

    def _rebuild_buttons(self) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        self._buttons = []
        self._confirm_buttons = []
        if self._confirm:
            y = ly.height // 2 + 40
            self._confirm_buttons = [
                Button(pygame.Rect(cx - 250, y, 230, 56), "Keep going",
                       self._keep_going, th, ly, primary=True),
                Button(pygame.Rect(cx + 20, y, 230, 56), "Stop",
                       self._abandon, th, ly),
            ]
            return
        if self.phase == PHASE_DONE:
            if self._problems:
                self._buttons.append(Button(
                    pygame.Rect(cx - 170, ly.height - 118, 340, 64),
                    "Try again", self._retry, th, ly, primary=True))
            else:
                self._buttons.append(Button(
                    pygame.Rect(cx - 170, ly.height - 118, 340, 64),
                    "Let's play", self._finish, th, ly, primary=True))
        # Skip is small and out of the way, but always there: keyboard
        # hands, a hurried clinician, a flaky sensor. It never writes.
        self._buttons.append(Button(
            pygame.Rect(ly.width - 220, ly.height - 70, 180, 48),
            "Skip for now", self._skip, th, ly, font_pt=FONT_SMALL + 2))

    def handle_event(self, e: pygame.event.Event) -> None:
        # Esc arrives through the engine's global path (on_escape), so
        # the KEYDOWN that follows it here must not double-handle.
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            return
        if self._confirm:
            for b in self._confirm_buttons:
                b.handle_event(e)
            return
        for b in self._buttons:
            b.handle_event(e)

    # ---- small drawing helpers ------------------------------------------

    @staticmethod
    def _mix(a, b, t: float) -> tuple[int, int, int]:
        """Blend a toward b. Used so every tint here derives from the
        theme instead of hard-coding a palette."""
        return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))

    def _lane_colour(self, i: int) -> tuple[int, int, int]:
        th = self.theme
        return (th.lane_active[i] if i < len(th.lane_active) else th.accent)

    def _quiet_trace_colour(self, i: int) -> tuple[int, int, int]:
        """Trace colour for a sensor that is settled where it should be.

        Amber at full strength is reserved for the one lane holding the
        capture up, so a settled lane has to sit clearly under it
        whatever finger it belongs to. The old 0.15 fade did not
        manage that for the pinky: its lane colour IS theme.warning to
        the byte in both shipped colour themes (202,138,4 clinical,
        250,204,21 dark), so a quiet pinky drew in exactly the alert
        colour and only the green tick beside it said otherwise. The
        finger keeps its identity regardless, because every row is
        named in text.
        """
        return self._mix(self._lane_colour(i), self.theme.background,
                         QUIET_TRACE_FADE)

    def _too_light_colour(self) -> tuple[int, int, int]:
        """The cool "not there yet" colour. theme.accent is the blue in
        both shipped colour themes and the yellow in high contrast, so
        it stays clear of the green and amber the other two zones use
        whichever theme is on."""
        return self.theme.accent

    def _panel(self, surf: pygame.Surface, rect: pygame.Rect,
               tint=None, alpha: int = 22, radius: int = 18) -> None:
        """Soft grouping panel: the tint at low alpha over the page.
        Cheap, theme-safe, and readable on a light or dark background."""
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        c = tint or self.theme.muted
        pygame.draw.rect(s, (c[0], c[1], c[2], alpha), s.get_rect(),
                         border_radius=radius)
        surf.blit(s, rect.topleft)

    def _bold(self, surf: pygame.Surface, text: str, pos, pt: int,
              colour, centre: bool = True) -> pygame.Rect:
        font = make_font(int(pt * self.layout.font_scale), bold=True)
        r = font.render(text, True, colour)
        rect = r.get_rect()
        if centre:
            rect.center = pos
        else:
            rect.topleft = pos
        surf.blit(r, rect)
        return rect

    def _pill(self, surf: pygame.Surface, centre, text: str, fg,
              pt: int = FONT_SMALL + 2, bold: bool = True) -> pygame.Rect:
        font = (make_font(int(pt * self.layout.font_scale), bold=True)
                if bold else self.layout.font(pt))
        t = font.render(text, True, fg)
        rect = pygame.Rect(0, 0, t.get_width() + 30, t.get_height() + 14)
        rect.center = centre
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (fg[0], fg[1], fg[2], 40), s.get_rect(),
                         border_radius=rect.height // 2)
        pygame.draw.rect(s, (fg[0], fg[1], fg[2], 150), s.get_rect(), 2,
                         border_radius=rect.height // 2)
        surf.blit(s, rect.topleft)
        surf.blit(t, t.get_rect(center=rect.center))
        return rect

    def _arc(self, surf: pygame.Surface, centre, radius: int, frac: float,
             colour, width: int = 12) -> None:
        """Progress arc sweeping clockwise from the top. Drawn as a few
        nested arcs because a single thick pygame arc frays at the
        ends."""
        frac = max(0.0, min(1.0, frac))
        if frac <= 0.0:
            return
        start = math.pi / 2 - frac * 2 * math.pi
        for k in range(width):
            r = radius - k
            pygame.draw.arc(
                surf, colour,
                pygame.Rect(centre[0] - r, centre[1] - r, r * 2, r * 2),
                start, math.pi / 2, 2)

    def _ring(self, surf: pygame.Surface, centre, radius: int, colour,
              width: int = 12) -> None:
        pygame.draw.circle(surf, colour, centre, radius, width)

    # ---- drawing ---------------------------------------------------------

    def _hand_word(self) -> str:
        if len(self.hands) == 1:
            return f"{self.hands[0]} hand"
        return "both hands"

    _STEPS = ("Hands off", "Rest", "Press", "Done")

    def draw(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        surf.fill(th.background)
        _draw_header(surf, "Quick calibration",
                     f"Learning your light press  |  {self._hand_word()}",
                     th, ly)
        self._draw_step_rail(surf)
        if self.phase in (PHASE_OFF, PHASE_REST):
            self._draw_rest_step(surf)
        elif self.phase == PHASE_PRESS:
            self._draw_press_step(surf)
        else:
            self._draw_summary(surf)
        for b in self._buttons:
            b.draw(surf)
        if self._confirm:
            self._draw_confirm(surf)

    def _draw_step_rail(self, surf: pygame.Surface) -> None:
        """Four dots along the top so the run always says where it is
        and how much is left."""
        th, ly = self.theme, self.layout
        order = (PHASE_OFF, PHASE_REST, PHASE_PRESS, PHASE_DONE)
        here = order.index(self.phase)
        w, gap = 150, 14
        total = len(order) * w + (len(order) - 1) * gap
        x0 = ly.width // 2 - total // 2
        y = 174
        for k, label in enumerate(self._STEPS):
            x = x0 + k * (w + gap)
            done = k < here
            now = k == here
            colour = (th.success if done
                      else th.accent if now else th.muted)
            bar = pygame.Rect(x, y, w, 5)
            pygame.draw.rect(surf, colour if (done or now)
                             else self._mix(th.muted, th.background, 0.6),
                             bar, border_radius=3)
            draw_text(surf, label, (x + w // 2, y + 18), th, ly,
                      pt=FONT_SMALL, centre=True,
                      colour=colour if now else th.muted)

    # ---- phases 1 and 2: the rest captures -------------------------------

    def _draw_rest_step(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        blockers = self._blockers()
        stale = self._stale()

        # ONE instruction, and it changes to name the exact problem the
        # moment there is one. Nothing else on this screen is bigger.
        if self.phase == PHASE_OFF:
            head = "Hands right off the pads"
            body = "Nothing touching. This reads the sensors' zero."
        else:
            head = ("Rest your hands on the pads" if len(self.hands) > 1
                    else f"Rest your {self.hands[0]} hand on the pads")
            body = "Relax. No pressing. This is your starting level."
        colour = th.foreground
        if stale:
            head = "Waiting for the device"
            body = "No readings are arriving. Check it on Settings."
            colour = th.warning
        elif blockers:
            hand, i = blockers[0]
            side = f"{hand} " if len(self.hands) > 1 else ""
            if self.phase == PHASE_OFF:
                head = f"Lift your {side}{FINGER_NAMES[i]} finger"
                body = "That pad is still carrying something."
            else:
                head = f"Relax your {side}{FINGER_NAMES[i]} finger"
                body = "It is pressing. Let it sit without pushing."
            colour = th.warning

        self._bold(surf, head, (cx, 240), FONT_H1, colour)
        draw_text(surf, body, (cx, 284), th, ly, pt=FONT_BODY,
                  centre=True, colour=th.muted)

        # Picture of the hand on the left so "ring finger" never has to
        # be worked out, traces of every sensor on the right.
        hot = {h: {i for hh, i in blockers if hh == h} for h in self.hands}
        on_pads = self.phase == PHASE_REST
        if len(self.hands) > 1:
            self._draw_hand_map(surf, pygame.Rect(122, 340, 146, 190),
                                self.hands[0], None, hot[self.hands[0]],
                                on_pads)
            self._draw_hand_map(surf, pygame.Rect(302, 340, 146, 190),
                                self.hands[1], None, hot[self.hands[1]],
                                on_pads)
            panel = pygame.Rect(500, 316, 640, 300)
        else:
            self._draw_hand_map(surf, pygame.Rect(160, 336, 200, 210),
                                self.hands[0], None, hot[self.hands[0]],
                                on_pads)
            panel = pygame.Rect(430, 316, 710, 300)
        self._draw_sensor_rows(surf, panel)
        self._draw_state_strip(surf, pygame.Rect(panel.x, panel.bottom + 18,
                                                 panel.w, 54),
                               stale, bool(blockers))

        if self._status:
            draw_text(surf, self._status, (cx, ly.height - 92), th, ly,
                      pt=FONT_BODY, centre=True, colour=th.warning)
        elif (not self._collecting
                and time.perf_counter() - self._phase_started_at > 15.0):
            draw_text(surf, "Not settling? Skip for now keeps the saved "
                      "settings.", (cx, ly.height - 92), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.muted)

    def _draw_state_strip(self, surf: pygame.Surface, rect: pygame.Rect,
                          stale: bool, blocked: bool) -> None:
        """One strip that says what the capture is doing right now.
        While measuring it doubles as the progress bar, so the wait has
        a visible end."""
        th = self.theme
        if self._collecting:
            span = self._rest_capture_s()
            frac = (1.0 - self._seconds_left() / span) if span > 0 else 1.0
            colour, text = th.accent, (
                f"MEASURING, HOLD STILL   {self._seconds_left():.1f}s")
        elif stale:
            colour, frac, text = th.warning, 0.0, "NO SIGNAL"
        elif blocked:
            colour, frac, text = th.warning, 0.0, "WAITING FOR A CLEAR PAD"
        elif self._settled():
            colour, frac, text = th.success, 0.0, "ALL QUIET, STARTING"
        else:
            colour, frac, text = th.muted, 0.0, "SETTLING..."
        self._panel(surf, rect, tint=colour, alpha=30, radius=16)
        w = int(rect.w * max(0.0, min(1.0, frac)))
        if w > 0:
            # Clipped out of a full-width rounded rect rather than drawn
            # as its own rect, so the growing edge stays a straight cut
            # instead of a lozenge sliding across the words.
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (colour[0], colour[1], colour[2], 70),
                             layer.get_rect(), border_radius=16)
            surf.blit(layer, rect.topleft, pygame.Rect(0, 0, w, rect.h))
        pygame.draw.rect(surf, colour, rect, 2, border_radius=16)
        self._bold(surf, text, rect.center, FONT_BODY, colour)

    def _draw_sensor_rows(self, surf: pygame.Surface,
                          rect: pygame.Rect) -> None:
        """One live trace per sensor, each against its own reference.

        Small multiples rather than one shared graph because the whole
        job of this panel is to attribute movement to a named finger,
        and overlaid lines on a shared axis do the opposite. A row that
        sits flat on its base is a settled sensor; a row that climbs is
        the finger the instruction above is talking about.
        """
        th, ly = self.theme, self.layout
        self._panel(surf, rect)
        lanes = [(h, i) for h in self.hands for i in range(N_FINGERS)]
        rh = min(66, (rect.h - 20) // max(1, len(lanes)))
        rows = self._hist
        blocked = set(self._blockers())

        if len(rows) < 2:
            draw_text(surf, "no readings yet",
                      (rect.centerx, rect.centery), th, ly, pt=FONT_BODY,
                      centre=True, colour=th.muted)
            return

        t1 = rows[-1][0]
        width = max(1e-6, max(t1 - rows[0][0], HIST_S))
        # Sliced once per hand for the whole buffer, not once per point.
        cols: dict[str, list[list[float]]] = {}
        for hand in self.hands:
            off = self._hand_offset(hand, len(rows[-1][1]))
            cols[hand] = [[float(v[off + i]) if off + i < len(v) else 0.0
                           for _, v in rows] for i in range(N_FINGERS)]
        xs = [0.0] * len(rows)
        for k, (t, _) in enumerate(rows):
            xs[k] = t

        for k, (hand, i) in enumerate(lanes):
            row = pygame.Rect(rect.x + 14, rect.y + 12 + k * rh,
                              rect.w - 28, rh - 6)
            hot = (hand, i) in blocked
            label = FINGER_NAMES[i]
            if len(self.hands) > 1:
                label = f"{hand[0].upper()}  {label}"
            self._bold(surf, label, (row.x + 6, row.centery - 8),
                       FONT_SMALL + 2, th.warning if hot else th.muted,
                       centre=False)
            track = pygame.Rect(row.x + 104, row.y + 2,
                                row.w - 104 - 76, row.h - 4)
            base = track.bottom - 2
            span = max(6, track.h - 6)
            pygame.draw.line(surf, self._mix(th.muted, th.background,
                                             0.45),
                             (track.x, base), (track.right, base), 1)
            if self.phase == PHASE_OFF:
                ref = self._hand_slice(self._floor, hand)[i] if self._floor \
                    else cols[hand][i][0]
            else:
                ref = self._captures[hand]["empty"][i]
            pts = []
            for k2, v in enumerate(cols[hand][i]):
                f = max(0.0, min(1.0, (v - ref) / QUIET_TRACE_COUNTS))
                x = track.right - (t1 - xs[k2]) / width * track.w
                pts.append((x, base - f * span))
            colour = th.warning if hot else self._quiet_trace_colour(i)
            if len(pts) >= 2:
                pygame.draw.lines(surf, colour, False, pts, 3 if hot else 2)
                pygame.draw.circle(surf, colour,
                                   (int(pts[-1][0]), int(pts[-1][1])),
                                   5 if hot else 3)
            now_v = cols[hand][i][-1] - ref
            draw_text(surf, f"{now_v:+.0f}", (track.right + 14,
                                              row.centery - 9), th, ly,
                      pt=FONT_SMALL + 2,
                      colour=th.warning if hot else th.muted)
            # Green tick once this sensor is sitting still where it
            # should, so "which ones are ready" needs no reading.
            if not hot:
                tx, ty = track.right + 58, row.centery
                pygame.draw.lines(surf, th.success, False,
                                  [(tx - 7, ty), (tx - 2, ty + 5),
                                   (tx + 8, ty - 6)], 3)
            # The mean being learned during the resting capture is what
            # the profile actually stores, so it is drawn as it lands.
            if self._collecting and self.phase == PHASE_REST:
                buf = self._rest_buffers.get(hand) or []
                if buf:
                    lvl = statistics.fmean([r[i] for r in buf]) - ref
                    f = max(0.0, min(1.0, lvl / QUIET_TRACE_COUNTS))
                    y = int(base - f * span)
                    pygame.draw.line(surf, self._lane_colour(i),
                                     (track.right - 70, y),
                                     (track.right, y), 3)

    # ---- phase 3: the press ----------------------------------------------

    def _y_for_counts(self, counts: float) -> int:
        frac = max(0.0, min(1.0, counts / max(1.0, self._bar_max())))
        return int(BAR.bottom - frac * BAR.height)

    def _draw_press_step(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        hand = self._current_hand()
        i = self._finger_idx
        lo, hi = self._band(hand, i)
        live = self._live_all()
        me = live[i]
        over = me > hi
        under = me < lo

        # Which hand, named large, whenever the run covers more than one.
        if len(self.hands) > 1:
            self._bold(surf, f"{hand.upper()} HAND", (cx, 226), FONT_H2,
                       th.accent)
            head_y = 268
        else:
            head_y = 244

        self._bold(surf, f"Press your {FINGER_NAMES[i].upper()} finger",
                   (cx, head_y), FONT_H1, th.foreground)
        cur, total = self._finger_no()
        draw_text(surf, f"Finger {cur} of {total}", (ly.width - 140, 226),
                  th, ly, pt=FONT_SMALL + 2, centre=True, colour=th.muted)

        self._draw_hand_map(surf, HAND_MAP, hand, i,
                            {self._wrong} if self._wrong is not None
                            else set())
        self._draw_bar(surf, lo, hi, me)
        self._draw_hold_ring(surf, i)
        self._draw_coach_line(surf, lo, hi, me, under, over)
        self._draw_tick_row(surf)

    def _fill_colour(self, lo: float, hi: float,
                     me: float) -> tuple[int, int, int]:
        """Colour of the pressure bar's live fill.

        The three zones, plus one override: a finger down that was not
        asked for takes the bar out of the goal whatever the target
        finger reads. Without the override the bar went full green the
        moment the target finger reached the band, while the line
        under it said "that's your MIDDLE finger, use your INDEX" and
        the hold ring sat still. Green is this screen's "yes, that is
        it", so the frame told the player two opposite things at once.
        The press is not being counted, so nothing on the bar may say
        it is.
        """
        th = self.theme
        if me > hi or self._wrong is not None:
            return th.warning
        return th.success if me >= lo else self._too_light_colour()

    def _draw_bar(self, surf: pygame.Surface, lo: float, hi: float,
                  me: float) -> None:
        th, ly = self.theme, self.layout
        zone_top = self._y_for_counts(hi)
        zone_bot = self._y_for_counts(lo)
        band = pygame.Rect(BAR.x, zone_top, BAR.w, zone_bot - zone_top)

        # Trough with a faint scale so small changes in the fill are
        # readable rather than a smooth featureless climb.
        self._panel(surf, BAR.inflate(16, 16), radius=24)
        pygame.draw.rect(surf, self._mix(th.muted, th.background, 0.55),
                         BAR, 2, border_radius=18)
        step = 10.0
        while self._bar_max() / step > 14:
            step *= 2
        v = step
        while v < self._bar_max():
            y = self._y_for_counts(v)
            pygame.draw.line(surf, self._mix(th.muted, th.background, 0.78),
                             (BAR.x + 3, y), (BAR.right - 3, y), 1)
            v += step

        # Goal band tint, under the fill.
        glow = self._in_zone or self._landed
        pygame.draw.rect(surf, self._mix(th.success, th.background,
                                         0.55 if glow else 0.82), band,
                         border_radius=10)

        colour = self._fill_colour(lo, hi, me)
        fill_top = self._y_for_counts(max(0.0, me))
        if me > 0.4 and fill_top < BAR.bottom - 6:
            pygame.draw.rect(surf, colour,
                             pygame.Rect(BAR.x + 5, fill_top, BAR.w - 10,
                                         BAR.bottom - fill_top - 4),
                             border_radius=13)

        # Goal band OUTLINE, on top of the fill. Without this the fill
        # swallows the band whole on a hard press and the player loses
        # the one reference they are aiming at.
        pygame.draw.rect(surf, th.success if glow else self._mix(
            th.success, th.background, 0.15), band, 5 if glow else 3,
            border_radius=10)

        # The level line, in the page's own foreground so it reads
        # against green, amber and blue alike.
        if me > 0.4:
            pygame.draw.line(surf, th.foreground,
                             (BAR.x - 4, fill_top), (BAR.right + 4,
                                                     fill_top), 3)
        py = max(BAR.y + 18, min(BAR.bottom - 18, fill_top))
        self._pill(surf, (BAR.x - 64, py),
                   f"{max(0.0, me):.0f}", colour if me > 0.4 else th.muted,
                   pt=FONT_BODY)

        # Zone labels down the right of the bar, each against its own
        # slice, so "too hard" and "too light" are places on the bar and
        # not just words that appear after the fact.
        lx = BAR.right + 24
        self._bold(surf, "TOO HARD", (lx, (BAR.y + zone_top) // 2 - 8),
                   FONT_SMALL + 4,
                   th.warning if me > hi else self._mix(
                       th.warning, th.background, 0.45), centre=False)
        self._bold(surf, "GOAL", (lx, band.centery - 20), FONT_H2,
                   th.success, centre=False)
        draw_text(surf, f"{lo:.0f} to {hi:.0f}",
                  (lx, band.centery + 10), th, ly, pt=FONT_SMALL + 2,
                  colour=th.muted)
        draw_text(surf, "counts above rest", (lx, band.centery + 32),
                  th, ly, pt=FONT_SMALL, colour=th.muted)
        self._bold(surf, "TOO LIGHT",
                   (lx, (zone_bot + BAR.bottom) // 2 - 8), FONT_SMALL + 4,
                   self._too_light_colour() if me < lo else self._mix(
                       self._too_light_colour(), th.background, 0.45),
                   centre=False)

    def _draw_hand_map(self, surf: pygame.Surface, rect: pygame.Rect,
                       hand: str, target: int | None,
                       hot: set[int], on_pads: bool = False) -> None:
        """A stylised hand with a finger lit. The word alone leaves
        "ring" to be worked out; the picture does not."""
        th, ly = self.theme, self.layout
        # Palm down: a right hand reads index to pinky left to right, a
        # left hand the other way round, so the picture matches the hand
        # actually on the pad.
        order = list(range(N_FINGERS))
        if hand == "left":
            order.reverse()
        gap = max(6, rect.w // 20)
        fw = (rect.w - gap * (N_FINGERS - 1)) // N_FINGERS
        span = rect.h - 78
        frac = {0: 0.87, 1: 1.0, 2: 0.9, 3: 0.7}
        base_y = rect.y + 22 + span
        self._panel(surf, rect.inflate(28, 44), radius=22)
        self._bold(surf, f"{hand.upper()} HAND",
                   (rect.centerx, rect.y - 24), FONT_SMALL + 4, th.muted)
        for slot, i in enumerate(order):
            h = int(span * frac[i])
            r = pygame.Rect(rect.x + slot * (fw + gap), base_y - h, fw, h)
            rad = min(20, fw // 2)
            if i in hot:
                pygame.draw.rect(surf, th.warning, r, border_radius=rad)
            elif i == target:
                pygame.draw.rect(surf, self._lane_colour(i), r,
                                 border_radius=rad)
                pygame.draw.rect(surf, th.accent, r.inflate(8, 8), 4,
                                 border_radius=rad + 4)
            elif on_pads:
                # Hand is meant to be ON the pads for this step, so the
                # picture says so: the fingers carry their own colours
                # instead of the greyed-out "lift off" look.
                pygame.draw.rect(surf, th.lane_idle[i] if i < len(
                    th.lane_idle) else th.muted, r, border_radius=rad)
            else:
                pygame.draw.rect(surf, self._mix(
                    th.muted, th.background, 0.72), r, border_radius=rad)
            name = FINGER_NAMES[i] if fw >= 40 else FINGER_NAMES[i][:3]
            draw_text(surf, name, (r.centerx, base_y + 8),
                      th, ly, pt=FONT_SMALL, centre=True,
                      colour=(th.warning if i in hot
                              else th.foreground if i == target
                              else th.muted))
            if i == target or i in hot:
                self._bold(surf, FINGER_NAMES[i].upper(),
                           (r.centerx, r.y - 16), FONT_SMALL + 2,
                           th.warning if i in hot else th.accent)
        palm = pygame.Rect(rect.x, base_y + 28, rect.w, 44)
        pygame.draw.rect(surf, self._mix(th.muted, th.background, 0.78),
                         palm, border_radius=20)

    def _draw_hold_ring(self, surf: pygame.Surface, i: int) -> None:
        """Hold-to-fill ring. The arc only moves while the press is in
        the band, which is what makes "too hard" read as a stall rather
        than a punishment."""
        th, ly = self.theme, self.layout
        self._ring(surf, RING_CENTRE, RING_R,
                   self._mix(th.muted, th.background, 0.6), 12)
        colour = th.success if (self._in_zone or self._landed) else th.muted
        self._arc(surf, RING_CENTRE, RING_R,
                  1.0 if self._landed else self._hold, colour, 12)
        if self._landed:
            cxr, cyr = RING_CENTRE
            pygame.draw.lines(surf, th.success, False,
                              [(cxr - 26, cyr), (cxr - 8, cyr + 20),
                               (cxr + 28, cyr - 22)], 9)
            self._bold(surf, "GOT IT", (cxr, cyr + 46), FONT_BODY,
                       th.success)
        else:
            self._bold(surf, FINGER_NAMES[i].upper(), RING_CENTRE,
                       FONT_H2, self._lane_colour(i))
            draw_text(surf, "HOLD", (RING_CENTRE[0], RING_CENTRE[1] + 34),
                      th, ly, pt=FONT_SMALL, centre=True, colour=th.muted)
        draw_text(surf, f"hold {self._hold_s():.0f}s in the goal",
                  (RING_CENTRE[0], RING_CENTRE[1] + RING_R + 26), th, ly,
                  pt=FONT_SMALL, centre=True, colour=th.muted)

        # One-shot completion pop, a ring expanding out of the hold ring.
        now = time.perf_counter()
        if self._landed and now - self._pop_at < POP_S:
            t = (now - self._pop_at) / POP_S
            pygame.draw.circle(surf, th.success, RING_CENTRE,
                               int(RING_R + t * 90),
                               max(2, int(9 * (1.0 - t))))

    def _draw_coach_line(self, surf: pygame.Surface, lo: float, hi: float,
                         me: float, under: bool, over: bool) -> None:
        """The ONE thing to do next, in the biggest words on the lower
        half of the screen. Exactly one of these is ever on screen."""
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        i = self._finger_idx
        y = 692
        if self._landed:
            msg, colour = f"Got your {FINGER_NAMES[i]} press.", th.success
        elif self._status:
            msg, colour = self._status, th.warning
        elif self._wrong is not None:
            msg = (f"That's your {FINGER_NAMES[self._wrong].upper()} finger. "
                   f"Use your {FINGER_NAMES[i].upper()}.")
            colour = th.warning
        elif over:
            msg, colour = "Ease off a bit", th.warning
        elif not under:
            msg, colour = "Perfect. Hold it there...", th.success
        elif me < lo * 0.25:
            msg = f"Press your {FINGER_NAMES[i]} finger gently onto the pad"
            colour = self._too_light_colour()
        else:
            msg, colour = "Press a little harder", self._too_light_colour()
        self._bold(surf, msg, (cx, y), FONT_H2 + 4, colour)
        if (not self._landed
                and time.perf_counter() - self._started_finger_at > 12.0):
            draw_text(surf, "Nothing happening? Skip for now keeps the "
                      "saved settings.", (cx, y + 30), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.muted)

    def _draw_tick_row(self, surf: pygame.Surface) -> None:
        """One chip per finger in the run, ticked as each press lands,
        so progress is visible without counting. The chip that just
        landed pops, once."""
        th, ly = self.theme, self.layout
        total = len(self.hands) * N_FINGERS
        cw, gap = (86, 8) if total > 4 else (120, 14)
        row_w = total * cw + (total - 1) * gap
        x0 = ly.width // 2 - row_w // 2
        y = ly.height - 62
        done_upto = self._hand_idx * N_FINGERS + self._finger_idx
        now = time.perf_counter()
        for k in range(total):
            hand = self.hands[k // N_FINGERS]
            fi = k % N_FINGERS
            r = pygame.Rect(x0 + k * (cw + gap), y, cw, 44)
            is_done = k < done_upto or (k == done_upto and self._landed)
            is_now = k == done_upto and not is_done
            if (k == done_upto and self._landed
                    and now - self._pop_at < POP_S):
                grow = int(10 * (1.0 - (now - self._pop_at) / POP_S))
                r = r.inflate(grow, grow)
            fill = (self._mix(th.success, th.background, 0.55) if is_done
                    else th.lane_idle[fi] if fi < len(th.lane_idle)
                    else th.muted)
            pygame.draw.rect(surf, fill, r, border_radius=10)
            if is_now:
                pygame.draw.rect(surf, th.accent, r, 3, border_radius=10)
            lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
            fg = (255, 255, 255) if lum < 140 else (15, 23, 42)
            label = (f"{hand[0].upper()} {FINGER_NAMES[fi][:3]}"
                     if len(self.hands) > 1 else FINGER_NAMES[fi])
            draw_text(surf, label, (r.centerx, r.y + 9), th, ly,
                      pt=FONT_SMALL, centre=True, colour=fg)
            if is_done:
                # Tick drawn as two strokes, no glyph dependency.
                pygame.draw.lines(
                    surf, th.success, False,
                    [(r.centerx - 10, r.y + 28), (r.centerx - 3, r.y + 35),
                     (r.centerx + 11, r.y + 21)], 4)
            else:
                # Hollow slot where the tick will land, so "not done
                # yet" is visibly a pending state, not a blank chip.
                pygame.draw.circle(surf, fg, (r.centerx, r.y + 30), 6, 2)

    # ---- phase 4: the summary --------------------------------------------

    @staticmethod
    def _kind_words(gap: float, band: tuple[float, float]) -> str:
        """Warm plain words for where a press landed, keyed off that
        finger's own band rather than a fixed count, so a preloaded
        pinky is not told off for a press its pad demanded."""
        lo, hi = band
        if gap < lo:
            return "very light, we can work with it"
        if gap <= lo + (hi - lo) * 0.45:
            return "a lovely light touch"
        if gap <= hi:
            return "a nice steady press"
        return "a firm press, lighter is fine too"

    def _draw_summary(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        name = getattr(self.engine.session, "participant", "") or ""
        ok = not self._problems
        head = (f"All set, {name}!" if ok and name not in ("", "NA")
                else "All set!" if ok else "Nearly there")
        self._bold(surf, head, (cx, 234), FONT_H1, th.foreground)
        draw_text(surf,
                  "That light touch is all the game ever needs."
                  if ok else "One finger needs another go.",
                  (cx, 276), th, ly, pt=FONT_BODY, centre=True,
                  colour=th.muted)

        # Bilateral gets two columns so eight fingers still fit above
        # the button without shrinking the type.
        cols = len(self.hands)
        row_h = 56
        col_w = 470 if cols > 1 else 640
        head_h = 34 if cols > 1 else 0
        span = cols * col_w + (cols - 1) * 40
        x0 = cx - span // 2
        legend = 322 + 34 + head_h + N_FINGERS * row_h + 18
        for c, hand in enumerate(self.hands):
            prof = self._profiles.get(hand)
            if prof is None:
                continue
            x = x0 + c * (col_w + 40)
            panel = pygame.Rect(x, 322, col_w,
                                34 + head_h + N_FINGERS * row_h)
            self._panel(surf, panel)
            y = panel.y + 30
            if cols > 1:
                self._bold(surf, f"{hand.upper()} HAND",
                           (panel.centerx, y), FONT_BODY, th.muted)
                y += head_h
            gaps = prof.gap()
            bands = prof.target_band()
            for i in range(N_FINGERS):
                dot = pygame.Rect(panel.x + 24, y - 8, 16, 16)
                pygame.draw.rect(surf, self._lane_colour(i), dot,
                                 border_radius=5)
                self._bold(surf, FINGER_NAMES[i].title(),
                           (panel.x + 50, y - 10), FONT_BODY,
                           th.foreground, centre=False)
                draw_text(surf, self._kind_words(gaps[i], bands[i]),
                          (panel.x + 142, y - 10), th, ly, pt=FONT_BODY,
                          colour=th.muted)
                # Where this press landed inside its own band, so the
                # words and the number agree.
                track = pygame.Rect(panel.x + 24, y + 18, col_w - 92, 8)
                pygame.draw.rect(surf, self._mix(
                    th.muted, th.background, 0.7), track, border_radius=4)
                lo, hi = bands[i]
                full = hi * 1.35
                gx = track.x + int(track.w * max(0.0, min(1.0, lo / full)))
                gw = max(6, int(track.w * max(0.0, min(
                    1.0, (hi - lo) / full))))
                pygame.draw.rect(surf, self._mix(
                    th.success, th.background, 0.45),
                    pygame.Rect(gx, track.y, gw, track.h), border_radius=4)
                px = track.x + int(track.w * max(0.0, min(
                    1.0, gaps[i] / full)))
                pygame.draw.circle(surf, self._lane_colour(i),
                                   (px, track.centery), 7)
                draw_text(surf, f"{gaps[i]:.0f}", (track.right + 16,
                                                   track.centery - 10),
                          th, ly, pt=FONT_SMALL + 2, colour=th.muted)
                y += row_h
            legend = panel.bottom + 18
        draw_text(surf, "The dot is where your press landed. The green "
                  "stretch is what that finger was aiming for.",
                  (cx, legend), th, ly, pt=FONT_SMALL + 2, centre=True,
                  colour=th.muted)
        if self._problems:
            draw_text(surf, self._problems[0], (cx, legend + 26), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.warning)

    def _draw_confirm(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        if (self._dim_cache is None
                or self._dim_cache.get_size() != (ly.width, ly.height)):
            self._dim_cache = pygame.Surface((ly.width, ly.height),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 160))
        surf.blit(self._dim_cache, (0, 0))
        cx, cy = ly.width // 2, ly.height // 2
        card = pygame.Rect(cx - 320, cy - 130, 640, 240)
        pygame.draw.rect(surf, th.background, card, border_radius=18)
        pygame.draw.rect(surf, th.muted, card, 2, border_radius=18)
        self._bold(surf, "Stop calibrating?", (cx, cy - 80), FONT_H2,
                   th.foreground)
        draw_text(surf, "Nothing measured so far will be saved.",
                  (cx, cy - 35), th, ly, pt=FONT_BODY, centre=True,
                  colour=th.muted)
        for b in self._confirm_buttons:
            b.draw(surf)
