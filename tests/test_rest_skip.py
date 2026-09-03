"""Every enforced wait in every mode can be cut short, and every skip
is recorded.

Two promises are pinned here. The first is the patient-facing one: a
rest, a break, an announce card or the shared GET READY prep can be
ended at once with Space or with a click on the control the screens
draw, and play resumes immediately rather than after some leftover
timer. The second is the analyst-facing one: a skip is never invisible.
It lands in the block summary, it writes a rest_skipped row to raw.csv,
and where it shortened a wait that was protecting a measurement (the
chords quiet-settle gate, Patterns' forced fatigue rest, Reaction's
stability gate) the affected trial carries a flag of its own.

The modes are driven headless against a virtual clock, the same trick
the mode tests already use: no sleeping, and the wait really does have
to be released by the skip rather than by time passing.

Durations are pinned here too, because the reason the skip exists is
that blocks were long. Each mode is run to completion at shipped config
with a slow-but-compliant patient (answering just before the response
window closes, which is the longest a cooperative session can run) and
checked against a cap. A change that quietly doubles a block fails
here rather than in a clinic.
"""
from __future__ import annotations

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

DT = 1.0 / 60.0


class _Clock:
    """Virtual perf_counter. Patched over time.perf_counter so every
    module reading the clock sees the same fake one."""

    def __init__(self, t0: float = 10_000.0) -> None:
        self.t = t0

    def __call__(self) -> float:
        return self.t

    def advance(self, secs: float) -> None:
        self.t += secs


class _RawLogger:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def queue_event(self, event, lane=None, detail="", t_perf=None,
                    fsr_vals=None, hand="right"):
        self.events.append({"event": event, "detail": detail})

    def kinds(self, name: str) -> list[str]:
        return [e["detail"] for e in self.events if e["event"] == name]


def _engine(hand_mode: str = "right", motors: bool = False,
            overrides: dict | None = None):
    """A real engine on the shipped config, with the screens mocked and
    the block lifecycle stubbed, so begin_*_block builds the mode
    exactly as a session would."""
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    for dotted, val in (overrides or {}).items():
        node = cfg.data
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = val
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = {k: MagicMock() for k in
                    ("gameplay", "syllables", "force_pilot",
                     "buzz_hunt", "rhythm")}
    eng._begin_block = lambda *a, **kw: None
    eng._finished = []
    eng.finish_block = lambda *a, **kw: eng._finished.append(1)
    eng.log_trial = lambda *a, **kw: None
    eng.raw_logger = _RawLogger()
    eng.hand_mode = hand_mode
    eng.session.participant = "Skip Patient"
    if motors:
        # Buzz Hunt needs a rig with motors; a keyboard source sends
        # the block straight to its no-input screen.
        src = MagicMock()
        src.provides_samples = True
        src.is_connected = True
        src.send_command = lambda c: True
        src.get_sample = lambda timeout=0.0: None
        eng.source = src
    return eng


class _Driver:
    """Steps a mode on the virtual clock and answers its stimuli, so a
    block makes real progress without anybody sleeping."""

    def __init__(self, eng, clock: _Clock, latency: float = 0.3) -> None:
        self.eng = eng
        self.clock = clock
        self.latency = latency
        self._pending: list[int] = []
        self._stim_t: float | None = None
        real_stim, real_multi = eng.on_stim, eng.on_stim_multi

        def _one(lane, tid, now, *a, **kw):
            self._pending, self._stim_t = [lane], now
            try:
                return real_stim(lane, tid, now, *a, **kw)
            except Exception:
                return None

        def _many(lanes, tid, now, *a, **kw):
            self._pending, self._stim_t = list(lanes), now
            try:
                return real_multi(lanes, tid, now, *a, **kw)
            except Exception:
                return None

        eng.on_stim, eng.on_stim_multi = _one, _many

    def press(self, lanes) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        for lane in lanes:
            self.eng.mode.queue_press(PressEvent(
                lane=lane, t_perf=self.clock.t, value=600,
                baseline=0.0, hand=self.eng.hand_mode))

    def run_until(self, pred, limit: float = 400.0,
                  answer: bool = True) -> bool:
        mode = self.eng.mode
        start = self.clock.t
        while self.clock.t - start < limit:
            if pred(mode):
                return True
            self.clock.advance(DT)
            mode.update(DT)
            if not answer:
                continue
            if self._pending and self._stim_t is not None \
                    and self.clock.t - self._stim_t >= self.latency:
                self.press(self._pending)
                self._pending, self._stim_t = [], None
            # Buzz Hunt has no cue path: the open response window is
            # the signal to answer.
            if getattr(mode, "sub", None) == "respond":
                r0 = getattr(mode, "_respond_t0", None)
                if r0 is not None and self.clock.t - r0 >= self.latency:
                    lane = getattr(mode, "lane", 0)
                    self.press([lane if lane and lane >= 0 else 0])
        return pred(mode)


# ---- the shared mixin --------------------------------------------------


class WaitSkipMixinTests(unittest.TestCase):
    """The mixin's own contract, independent of any mode."""

    def _holder(self):
        from finger_rehab.game.rest_skip import WaitSkip

        class Holder(WaitSkip):
            def __init__(self):
                self.engine = None
                self.released_at = None

            def release(self, now):
                self.released_at = now

        return Holder()

    def test_nothing_armed_means_nothing_to_skip(self) -> None:
        h = self._holder()
        self.assertIsNone(h.wait_view())
        # A stray Space on a live trial must do nothing at all, not
        # quietly count as a skip.
        self.assertFalse(h.skip_wait(now=1.0))
        self.assertEqual(h.wait_skip_stats()["skipped_rests"], 0)

    def test_skip_calls_the_release_and_counts_the_time_saved(self) -> None:
        h = self._holder()
        h.arm_wait("rest", ends_at=130.0, on_skip=h.release,
                   started_at=100.0)
        self.assertTrue(h.skip_wait(now=110.0))
        self.assertEqual(h.released_at, 110.0)
        st = h.wait_skip_stats()
        self.assertEqual(st["skipped_rests"], 1)
        self.assertEqual(st["skipped_rest_s"], 20.0)
        self.assertEqual(st["skipped_rest_kinds"], {"rest": 1})
        self.assertEqual(st["skipped_rest_events"][0]["planned_s"], 30.0)

    def test_a_wait_can_only_be_skipped_once(self) -> None:
        h = self._holder()
        h.arm_wait("rest", ends_at=130.0, on_skip=h.release,
                   started_at=100.0)
        self.assertTrue(h.skip_wait(now=110.0))
        self.assertFalse(h.skip_wait(now=111.0))
        self.assertEqual(h.wait_skip_stats()["skipped_rests"], 1)

    def test_only_a_protecting_wait_flags_the_next_trial(self) -> None:
        h = self._holder()
        h.arm_wait("rest", ends_at=130.0, on_skip=h.release,
                   started_at=100.0)
        h.skip_wait(now=110.0)
        self.assertIsNone(h.take_skip_flag())
        h.arm_wait("settle", ends_at=130.0, on_skip=h.release,
                   started_at=100.0, protects="a still hand")
        h.skip_wait(now=110.0)
        self.assertEqual(h.take_skip_flag(), "settle")
        # Read once, cleared: the flag belongs to one trial, not every
        # trial after it.
        self.assertIsNone(h.take_skip_flag())

    def test_short_waits_keep_the_key_but_lose_the_control(self) -> None:
        # A control that flashes between every trial cannot be aimed
        # at and sits next to the thing being measured; the keyboard
        # skip still has to work on those waits.
        h = self._holder()
        for span in (0.8, 1.4, 2.0):
            h.arm_wait("gap", ends_at=100.0 + span, on_skip=h.release,
                       started_at=100.0)
            self.assertFalse(h.wait_view(now=100.1)["show"], span)
            self.assertTrue(h.skip_wait(now=100.1), span)
        # The sit-through waits do get one.
        for span in (2.5, 3.0, 10.0, 30.0):
            h.arm_wait("rest", ends_at=100.0 + span, on_skip=h.release,
                       started_at=100.0)
            self.assertTrue(h.wait_view(now=100.1)["show"], span)

    def test_an_overrunning_gate_keeps_its_control_on_screen(self) -> None:
        h = self._holder()
        h.arm_wait("settle", ends_at=103.0, on_skip=h.release,
                   started_at=100.0, hold_when_due=True)
        self.assertTrue(h.wait_view(now=104.0)["show"])
        # A self-paced floor does the opposite: once it has passed,
        # the mode is waiting on the patient, not on the clock.
        h.arm_wait("rest", ends_at=103.0, on_skip=h.release,
                   started_at=100.0)
        self.assertFalse(h.wait_view(now=104.0)["show"])

    def test_a_pause_does_not_eat_the_rest(self) -> None:
        # The deadline is absolute, like every mode's own timers, so a
        # pause has to move it or the pause counts as rest and the
        # control disagrees with the mode about what is left.
        h = self._holder()
        h.arm_wait("rest", ends_at=130.0, on_skip=h.release,
                   started_at=100.0)
        left_before = h.wait_view(now=110.0)["remaining"]
        h.shift_wait(45.0)
        self.assertEqual(h.wait_view(now=155.0)["remaining"], left_before)
        self.assertEqual(h.wait_view(now=155.0)["total"], 30.0)

    def test_refresh_keeps_the_start_and_moves_the_deadline(self) -> None:
        # A gate re-evaluated every frame must not rebuild its wait
        # sixty times a second, or its reported length resets forever.
        h = self._holder()
        h.refresh_wait("settle", 100.5, on_skip=h.release,
                       started_at=100.0)
        h.refresh_wait("settle", 103.5, on_skip=h.release,
                       started_at=103.0)
        self.assertEqual(h.armed_wait().started_at, 100.0)
        self.assertEqual(h.armed_wait().ends_at, 103.5)


# ---- the shared prep ---------------------------------------------------


class PrepCountdownSkipTests(unittest.TestCase):
    """The one wait the engine owns rather than a mode."""

    def _set_up(self, clock):
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        sc = GameplayScreen.__new__(GameplayScreen)
        sc._countdown_until = clock.t + 3.0
        sc._countdown_remaining = lambda: max(
            0.0, sc._countdown_until - time.perf_counter())
        eng._screens["gameplay"] = sc
        eng.screen_obj = sc
        eng.begin_pattern_block()
        eng.screen_obj = sc
        sc._countdown_until = clock.t + 3.0
        return eng, sc

    def test_the_prep_is_offered_and_can_be_skipped(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._set_up(clock)
            view = eng.current_wait_view()
            self.assertEqual(view["kind"], "prep")
            self.assertAlmostEqual(view["remaining"], 3.0, places=3)
            self.assertTrue(view["show"])
            self.assertTrue(eng.skip_current_wait())
            self.assertEqual(sc._countdown_remaining(), 0.0)

    def test_the_prep_skip_reaches_the_block_summary_and_raw(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, _sc = self._set_up(clock)
            eng.skip_current_wait()
            summary = eng.skipped_wait_summary()
            self.assertEqual(summary["skipped_rest_kinds"]["prep"], 1)
            self.assertEqual(summary["skipped_rest_s"], 3.0)
            self.assertTrue(eng.raw_logger.kinds("rest_skipped"))

    def test_nothing_waiting_means_the_key_does_nothing(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._set_up(clock)
            sc._countdown_until = 0.0
            eng.mode.clear_wait()
            self.assertIsNone(eng.current_wait_view())
            self.assertFalse(eng.skip_current_wait())


# ---- keyboard and mouse ------------------------------------------------


class SkipInputRoutingTests(unittest.TestCase):
    """Space and a click on the drawn control both reach the same skip,
    and neither leaks through to the mode as a game input."""

    def _live_screen(self, clock):
        eng = _engine()
        eng._screens = eng._build_screens()
        eng.begin_pattern_block()
        sc = eng._screens["gameplay"]
        sc._countdown_until = 0.0
        eng.screen_obj = sc
        eng.mode._enter_rest(clock.t, 30.0, "between", "Take 1 done")
        return eng, sc

    def _draw(self, eng, sc):
        import pygame
        sc.draw(pygame.Surface((1280, 800)))

    def test_space_skips_the_rest_and_is_swallowed(self) -> None:
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
            self.assertTrue(eng._event_consumed)
            self.assertEqual(eng.mode.phase, "play")
            self.assertEqual(
                eng.mode.wait_skip_stats()["skipped_rests"], 1)

    def test_a_click_on_the_control_skips(self) -> None:
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            rect = eng._skip_chip_rect
            self.assertIsNotNone(rect)
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
            self.assertTrue(eng._event_consumed)
            self.assertEqual(eng.mode.phase, "play")

    def test_the_hit_rect_is_the_rect_that_was_drawn(self) -> None:
        # House rule: what the patient aims at is what answers. Every
        # corner of the drawn pill must be live, and a pixel outside
        # it must not be.
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            rect = eng._skip_chip_rect
            for pt in (rect.topleft, (rect.right - 1, rect.top),
                       (rect.left, rect.bottom - 1),
                       (rect.right - 1, rect.bottom - 1), rect.center):
                self.assertTrue(eng._skip_chip_hit(pt), pt)
            self.assertFalse(eng._skip_chip_hit(
                (rect.left - 2, rect.centery)))
            self.assertFalse(eng._skip_chip_hit(
                (rect.centerx, rect.bottom + 2)))

    def test_a_click_that_misses_the_control_is_not_a_skip(self) -> None:
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=(8, 8)))
            self.assertFalse(eng._event_consumed)
            self.assertEqual(eng.mode.phase, "rest")

    def test_the_control_is_gone_and_dead_while_paused(self) -> None:
        # A paused block is already frozen. Offering to skip a wait
        # that is not counting down would be a lie, and the click must
        # not land either.
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            rect = eng._skip_chip_rect
            eng.paused = True
            self._draw(eng, sc)
            self.assertIsNone(eng._skip_chip_rect)
            self.assertFalse(eng._skip_chip_hit(rect.center))
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
            self.assertFalse(eng._event_consumed)
            self.assertEqual(eng.mode.phase, "rest")

    def test_a_stale_control_rect_cannot_swallow_a_menu_click(self) -> None:
        # The rect survives on the engine after the block screen is
        # gone. A click on a menu button at the same coordinates must
        # still reach the menu.
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, sc = self._live_screen(clock)
            self._draw(eng, sc)
            rect = eng._skip_chip_rect
            eng.screen_obj = MagicMock()
            self.assertFalse(eng._skip_chip_hit(rect.center))
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))
            self.assertFalse(eng._event_consumed)

    def test_space_off_a_block_screen_is_left_alone(self) -> None:
        # Space activates the focused button on the menu screens; the
        # skip must never take it away from them.
        import pygame
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng, _sc = self._live_screen(clock)
            eng.screen_obj = MagicMock()
            eng._event_consumed = False
            eng._handle_global_event(pygame.event.Event(
                pygame.KEYDOWN, key=pygame.K_SPACE, mod=0))
            self.assertFalse(eng._event_consumed)
            self.assertEqual(eng.mode.phase, "rest")


# ---- per-mode: the wait really is released -----------------------------


class ModeWaitSkipTests(unittest.TestCase):
    """Drive each mode to a real wait, skip it, and confirm play
    resumes at once and the skip was recorded."""

    def test_a_paused_rest_comes_back_with_the_same_time_left(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_pattern_block()
            m = eng.mode
            m._enter_rest(clock.t, 30.0, "between", "Take 1 done")
            clock.advance(4.0)
            left = m.wait_view()["remaining"]
            # Pause for twenty seconds, then resume the way the engine
            # does.
            clock.advance(20.0)
            m.on_resume(20.0)
            m.shift_wait(20.0)
            self.assertAlmostEqual(m.wait_view()["remaining"], left,
                                   places=3)
            self.assertAlmostEqual(m._rest_min_until,
                                   m.armed_wait().ends_at, places=3)

    def test_pattern_between_take_rest(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_pattern_block()
            d = _Driver(eng, clock)
            m = eng.mode
            self.assertTrue(d.run_until(lambda x: x.phase == "rest"))
            self.assertTrue(m.wait_view()["show"])
            seg_before = m._seg_idx
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "play")
            self.assertEqual(m._seg_idx, seg_before + 1)
            st = m.wait_skip_stats()
            self.assertEqual(st["skipped_rests"], 1)
            self.assertGreater(st["skipped_rest_s"], 5.0)
            self.assertTrue(eng.raw_logger.kinds("rest_skipped"))
            # Play really resumes: the next cue arrives without the
            # rest of the floor having to pass.
            self.assertTrue(d.run_until(lambda x: x.active is not None,
                                        limit=5.0))

    def test_pattern_forced_fatigue_rest_marks_the_take(self) -> None:
        # This rest protects a measurement: the same take resumes
        # afterwards and its post-rest trials go into that take's mean,
        # so a shortened one has to be visible in the take record.
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_pattern_block()
            d = _Driver(eng, clock)
            m = eng.mode
            m._seg_idx = next(i for i, sg in enumerate(m.segments)
                              if sg.kind == "seq")
            m._seg_announced = False
            m.phase = "play"
            self.assertTrue(d.run_until(
                lambda x: x.phase == "rest" and x._rest_kind == "forced",
                answer=False))
            self.assertEqual(m.wait_view()["kind"], "fatigue_rest")
            self.assertTrue(m.wait_view()["protects"])
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "play")
            self.assertTrue(m._forced_rest_positions[-1]["skipped"])
            self.assertIn("fatigue_rest_positions", m.block_stats())

    def test_pattern_reports_the_skips_in_block_stats(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_pattern_block()
            stats = eng.mode.block_stats()
            # Present and zero, so an analysis can tell "nobody
            # skipped" apart from "this mode does not report it".
            self.assertEqual(stats["skipped_rests"], 0)
            self.assertEqual(stats["skipped_rest_kinds"], {})

    def test_chords_subblock_rest(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_chords_block()
            d = _Driver(eng, clock)
            m = eng.mode
            self.assertTrue(d.run_until(lambda x: x.phase == "rest",
                                        limit=900.0))
            self.assertTrue(m.wait_view()["show"])
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "settle")
            self.assertEqual(m.wait_skip_stats()["skipped_rests"], 1)
            self.assertTrue(d.run_until(lambda x: x.active is not None,
                                        limit=10.0))

    def test_chords_settle_gate_flags_the_trial_it_releases(self) -> None:
        # The quiet gate is what makes the leak measurement mean
        # something. It stays skippable so a hand that will not settle
        # cannot trap the block, but the chord it releases has to say
        # its baseline was short.
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_chords_block()
            d = _Driver(eng, clock)
            m = eng.mode
            m.update(DT)
            m._hand_quiet = lambda: False
            self.assertTrue(d.run_until(
                lambda x: (x.wait_view() or {}).get("show") is True,
                limit=30.0, answer=False))
            view = m.wait_view()
            self.assertEqual(view["kind"], "settle")
            self.assertTrue(view["protects"])
            m._hand_quiet = lambda: True
            self.assertTrue(m.skip_wait())
            self.assertTrue(d.run_until(lambda x: x.active is not None,
                                        limit=5.0, answer=False))
            self.assertTrue(m.active.settle_skipped)

    def test_chords_settle_gate_shows_only_once_it_overruns(self) -> None:
        # A hand that settles in half a second needs no button; a gate
        # that keeps restarting is exactly when somebody wants one.
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_chords_block()
            m = eng.mode
            m.update(DT)
            m._hand_quiet = lambda: True
            for _ in range(30):
                clock.advance(DT)
                m.update(DT)
                view = m.wait_view()
                if view and view["kind"] == "settle":
                    self.assertFalse(view["show"])
                    break

    def test_syllables_break(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_syllables_block()
            d = _Driver(eng, clock)
            m = eng.mode
            self.assertTrue(d.run_until(lambda x: x.phase == "break",
                                        limit=900.0))
            self.assertTrue(m.wait_view()["show"])
            self.assertTrue(m.skip_wait())
            self.assertNotEqual(m.phase, "break")
            self.assertGreaterEqual(
                m.wait_skip_stats()["skipped_rests"], 1)

    def test_buzz_hunt_stage_card_announce_and_rest(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine(motors=True)
            eng.begin_buzz_hunt_block()
            d = _Driver(eng, clock)
            m = eng.mode
            m.update(DT)
            self.assertEqual(m.wait_view()["kind"], "stage")
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "announce")
            self.assertEqual(m.wait_view()["kind"], "announce")
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "trial")
            self.assertTrue(d.run_until(lambda x: x.phase == "feedback",
                                        limit=60.0))
            self.assertEqual(m.wait_view()["kind"], "feedback")
            self.assertTrue(m.skip_wait())
            self.assertIn(m.phase, ("announce", "stage", "trial"))
            self.assertGreaterEqual(
                m.wait_skip_stats()["skipped_rests"], 3)

    def test_buzz_hunt_foreperiod_is_never_offered(self) -> None:
        # The jittered wait before the buzz is the stimulus, not a
        # rest: a button that cut it short would hand the patient the
        # onset time.
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine(motors=True)
            eng.begin_buzz_hunt_block()
            m = eng.mode
            m.update(DT)
            m.skip_wait()
            m.skip_wait()
            self.assertEqual(m.phase, "trial")
            self.assertEqual(m.sub, "wait")
            self.assertIsNone(m.wait_view())
            self.assertFalse(m.skip_wait())

    def test_reaction_feedback_gap(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_reaction_block()
            d = _Driver(eng, clock)
            m = eng.mode
            self.assertTrue(d.run_until(lambda x: x._phase == "rest",
                                        limit=60.0))
            self.assertIsNotNone(m.wait_view())
            self.assertTrue(m.skip_wait())
            self.assertEqual(m._phase, "arm")

    def test_reaction_stability_gate_flags_its_trial(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_reaction_block()
            m = eng.mode
            # A finger that never lifts keeps the gate restarting.
            m._fingers_down = lambda: True
            for _ in range(200):
                clock.advance(DT)
                m.update(DT)
                view = m.wait_view()
                if view and view["kind"] == "settle" and view["show"]:
                    break
            view = m.wait_view()
            self.assertEqual(view["kind"], "settle")
            self.assertTrue(view["protects"])
            m._fingers_down = lambda: False
            self.assertTrue(m.skip_wait())
            clock.advance(DT)
            m.update(DT)
            self.assertTrue(m._trial_gate_skipped)
            self.assertEqual(m.block_stats()["n_rest_gate_skipped"], 1)
            self.assertTrue(eng.raw_logger.kinds("rest_gate_skipped"))

    def test_force_pilot_announce_and_between_run_rest(self) -> None:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.source = MagicMock()
            eng.source.provides_samples = True
            eng.begin_force_pilot_block()
            m = eng.mode
            m._probe_queue.clear()
            m._prepare_run()
            m._enter_announce(clock.t)
            self.assertEqual(m.wait_view()["kind"], "announce")
            self.assertTrue(m.skip_wait())
            self.assertEqual(m.phase, "run")
            self.assertEqual(m.wait_skip_stats()["skipped_rests"], 1)

    def test_rhythm_lead_in_jumps_straight_to_the_downbeat(self) -> None:
        # Every beat time is relative to the song, so pulling the whole
        # timeline forward moves when play starts and nothing else.
        from finger_rehab.audio.beatmap import procedural_beatmap
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_rhythm_block(procedural_beatmap(
                bpm=90, beats=40, difficulty="easy"))
            m = eng.mode
            m.update(DT)
            view = m.wait_view()
            self.assertEqual(view["kind"], "prep")
            self.assertGreater(view["remaining"], 3.0)
            gaps_before = [n.t for n in m.beatmap.notes]
            self.assertTrue(m.skip_wait())
            self.assertAlmostEqual(m.song_time, m._pre_song_lead_s,
                                   places=2)
            # The chart itself is untouched: the notes still sit where
            # the beatmap put them relative to the song.
            self.assertEqual([n.t for n in m.beatmap.notes], gaps_before)


# ---- durations ---------------------------------------------------------


class BlockDurationTests(unittest.TestCase):
    """Every mode run to completion at shipped config, with a slow but
    compliant patient. These caps are the clinic promise: a block that
    grows past one has to be a deliberate decision, argued for here,
    not something that drifted in."""

    # Measured worst case with a slow patient, plus headroom. Pattern
    # is a full SRTT session and is long by design (400 to 800
    # sequence trials is the envelope its docstring cites); the
    # shipped answer for a patient who cannot carry that is
    # pattern.short_session, not a thinner dose.
    CAPS_MIN = {
        "pattern": 30.0,
        "force_pilot": 7.0,
        "chords": 14.0,
        # 10.0 with the old word bank (8.5 min measured). The
        # two-plus-syllable bank of September 2026 measures 10.2 min
        # here at 40 words; the config comment on words_per_block
        # says whose call the word count now is.
        "syllables": 10.5,
        "buzz_hunt": 10.5,
        "reaction": 5.0,
        "classic": 2.0,
        "adaptive": 2.0,
        "mirror": 2.0,
    }
    # Slow-patient latencies: answering just before the response
    # window closes is the longest a cooperative session can run.
    LATENCY = {
        "pattern": 1.9, "chords": 2.9, "syllables": 1.2,
        "buzz_hunt": 2.9, "reaction": 1.9, "classic": 0.95,
        "adaptive": 0.95, "mirror": 0.9,
        "force_pilot": 0.0,
    }
    PREP_S = 3.0

    def _measure(self, name: str, begin: str, hand: str = "right",
                 motors: bool = False) -> float:
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine(hand, motors=motors)
            getattr(eng, begin)()
            d = _Driver(eng, clock, latency=self.LATENCY[name])
            mode = eng.mode
            start = clock.t
            last_nudge = clock.t
            while clock.t - start < 4000.0:
                if eng._finished or getattr(mode, "phase", None) == "done" \
                        or getattr(mode, "_phase", None) == "done":
                    break
                clock.advance(DT)
                mode.update(DT)
                if d._pending and d._stim_t is not None:
                    if clock.t - d._stim_t >= d.latency:
                        d.press(d._pending)
                        d._pending, d._stim_t = [], None
                    continue
                if getattr(mode, "sub", None) == "respond":
                    r0 = getattr(mode, "_respond_t0", None)
                    if r0 is not None and clock.t - r0 >= d.latency:
                        lane = getattr(mode, "lane", 0)
                        d.press([lane if lane and lane >= 0 else 0])
                    continue
                # A compliant patient taps out of a self-paced rest the
                # moment its floor has passed.
                phase = (getattr(mode, "phase", None)
                         or getattr(mode, "_phase", None))
                if phase in ("rest", "break") \
                        and clock.t - last_nudge > 0.4:
                    last_nudge = clock.t
                    d.press([0])
            return (clock.t - start + self.PREP_S) / 60.0

    def _check(self, name, begin, hand="right", motors=False):
        mins = self._measure(name, begin, hand, motors)
        self.assertLessEqual(
            mins, self.CAPS_MIN[name],
            f"{name} runs {mins:.1f} min at shipped config, over its "
            f"{self.CAPS_MIN[name]:.1f} min cap")
        # A block that collapses to nothing is a broken config, not a
        # win, so the floor is checked too.
        self.assertGreater(mins, 0.3, name)
        return mins

    def test_pattern_duration(self) -> None:
        self._check("pattern", "begin_pattern_block")

    def test_chords_duration(self) -> None:
        self._check("chords", "begin_chords_block")

    def test_syllables_duration(self) -> None:
        self._check("syllables", "begin_syllables_block")

    def test_buzz_hunt_duration(self) -> None:
        self._check("buzz_hunt", "begin_buzz_hunt_block", motors=True)

    def test_reaction_duration(self) -> None:
        self._check("reaction", "begin_reaction_block")

    def test_classic_duration(self) -> None:
        self._check("classic", "begin_classic_block")

    def test_adaptive_duration(self) -> None:
        self._check("adaptive", "begin_adaptive_block")

    def test_mirror_duration(self) -> None:
        self._check("mirror", "begin_mirror_block", hand="both")

    def _force_engine(self):
        """Force Pilot takes a force trace, not presses,
        so it needs a rig that provides samples and a probed max
        already on file (a fresh probe is its own measured stage, and
        a stale one belongs to somebody else)."""
        from finger_rehab.hardware.calibration_profile import (
            CalibrationProfile)
        eng = _engine()
        src = MagicMock()
        src.provides_samples = True
        src.is_connected = True
        src.send_command = lambda c: True
        src.get_sample = lambda timeout=0.0: None
        eng.source = src
        profiles = {}
        for hand in ("right", "left"):
            prof = CalibrationProfile(
                hand=hand, participant=eng.session.participant,
                resting=[100.0] * 4, press=[160.0] * 4)
            prof.set_max_press([400.0] * 4)
            profiles[hand] = prof
        eng.calibration_profiles = profiles
        return eng

    def _force_view(self):
        from finger_rehab.game.force_stream import ForceReading

        class _View:
            def __init__(self):
                self.counts = 400.0
                self.pct = 0.0
                self.pct_by_lane = {}

            def read(self, lane):
                return ForceReading(
                    counts=self.counts,
                    percent=self.pct_by_lane.get(lane, self.pct))

            def sample_age_s(self, lane, now):
                return 0.0

            def rebaseline(self, lanes=None):
                return None

        return _View()

    def test_force_pilot_duration(self) -> None:
        from finger_rehab.game.modes.force_pilot import target_pct
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = self._force_engine()
            eng.begin_force_pilot_block()
            m = eng.mode
            m.view = self._force_view()
            start = clock.t
            while clock.t - start < 4000.0:
                if eng._finished or m.phase in ("done", "no_input"):
                    break
                clock.advance(DT)
                if m.phase == "run" and m.run_t0 is not None:
                    # Fly the corridor: a run is a fixed-length plan,
                    # so this is the shape of every session.
                    m.view.pct = target_pct(m.sections,
                                            clock.t - m.run_t0)
                m.update(DT)
            mins = (clock.t - start + self.PREP_S) / 60.0
            self.assertEqual(m.runs_done, m.total_runs)
            self.assertLessEqual(mins, self.CAPS_MIN["force_pilot"],
                                 f"force_pilot runs {mins:.1f} min")

    def test_rhythm_is_bounded_by_the_longest_song(self) -> None:
        # Rhythm's length is the track, not a trial count. The
        # countdown and the silent lead ride in front of it.
        from finger_rehab.audio.beatmap import procedural_beatmap
        clock = _Clock()
        with patch.object(time, "perf_counter", clock):
            eng = _engine()
            eng.begin_rhythm_block(procedural_beatmap(
                bpm=90, beats=240, difficulty="medium"))
            m = eng.mode
            span = max(n.t for n in m.beatmap.notes)
            total = span + m._countdown_s
            self.assertLess(total / 60.0, 6.0)


if __name__ == "__main__":
    unittest.main()
