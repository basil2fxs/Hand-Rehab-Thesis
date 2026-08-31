"""One skip path for every enforced wait in every mode.

WHY THIS EXISTS. A block is a sequence of things to do separated by
things to wait through: the shared GET READY prep, rests between takes
or sub-blocks, a child's break between rounds, the announce card before
a force run, the gap after feedback. Added up they are a large share of
a session, and until now none of them could be cut short. A clinician
running late, a patient who is ready before the floor expires and a
supervisor walking a demo all had the same option, which was to sit
there. Basil asked for the obvious fix: let anybody move on at will.

WHAT A SKIP MUST NOT DO. Some of these waits are not padding. Patterns'
forced fatigue rest exists because five lit keys with no press reads as
a tired hand, and the take RESUMES afterwards, so its post-rest trials
land in that take's mean. Chords' quiet-settle gate exists so every
chord launches from a genuinely still hand, which is what makes the
leak measurement mean anything. Cutting either one short is allowed,
because a patient who wants to keep going outranks a tidy number, but
it must never happen invisibly: an analyst reading the session
afterwards has to be able to see that this rest was shortened and this
trial started early. So every skip is counted in block_stats, written
to raw.csv as its own event, and where it changes a single trial it
also sets a flag on that trial.

HOW A MODE USES IT. Mix in WaitSkip, then wherever the mode already
starts an enforced wait, call arm_wait() alongside it with a callback
that ends the wait early. The mixin owns nothing about the mode's state
machine: skip_wait() just calls the callback, so a mode that leaves a
rest by advancing a segment index keeps doing exactly that. Clear the
armed wait when the wait ends on its own.

State is created lazily rather than in __init__, because several modes
are built by tests through __new__ and would otherwise have no state at
all when a screen asked them for the current wait.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable


log = logging.getLogger(__name__)


# Waits shorter than this never draw the skip chip. A control that
# appears for two seconds cannot be read, let alone aimed at with a
# mouse, and one flashing between every trial of a perception or
# reaction block is a moving distraction sitting next to the thing
# being measured. The keyboard skip still works on a short wait; only
# the drawn control is held back.
#
# 2.5 is where the two groups actually separate at shipped config.
# Below it sit the per-trial gaps nobody wants a button on: Buzz
# Hunt's announce (1.5) and feedback (2.0), Reaction's feedback plus
# inter-trial gap (up to 2.0), Syllables' feedback (1.4) and inter-word
# gap (0.8), the force modes' probe gap (1.2). At or above it sit the
# waits somebody genuinely sits through: the announce cards on the two
# force modes (2.5), the GET READY prep (3.0), Buzz Hunt's stage card
# (5.0), Lighthouse's between-trial rest (6.0), Force Pilot's
# between-run rest (10), Patterns' rests (10/30/45), Chords' rests
# (30/120) and Syllables' break (30). A gate that overruns, like the
# Chords quiet-settle, grows past the threshold on its own and takes
# the control when it does. Overridable through game.skip_chip_min_s.
DEFAULT_CHIP_MIN_S = 2.5

# Patient-facing wording. The kind is what goes in the data; the label
# is what the patient reads.
LABELS = {
    "prep": "Skip countdown",
    "rest": "Skip rest",
    "long_rest": "Skip rest",
    "fatigue_rest": "Skip rest",
    "break": "Skip break",
    "settle": "Skip wait",
    "announce": "Skip",
    "stage": "Skip",
    "feedback": "Skip",
    "gap": "Skip",
}


@dataclass
class ArmedWait:
    """One enforced wait that is running right now."""

    kind: str
    ends_at: float
    on_skip: Callable[[float], None]
    started_at: float
    # Plain-English note on what the wait protects, for waits that
    # exist for a research reason rather than for comfort. None means
    # the wait is pure pacing and shortening it costs the data nothing.
    protects: str | None = None
    label: str | None = None
    # Whether the control stays on screen once the deadline has passed.
    # False for a self-paced floor (the mode is then waiting on the
    # patient, not on the clock, and a button offering to skip nothing
    # is noise). True for a gate that can overrun, like the chords
    # quiet-settle: that is exactly the moment somebody wants out.
    hold_when_due: bool = False

    @property
    def total_s(self) -> float:
        return max(0.0, self.ends_at - self.started_at)

    def remaining(self, now: float) -> float:
        return max(0.0, self.ends_at - now)

    def button_label(self) -> str:
        return self.label or LABELS.get(self.kind, "Skip")


@dataclass
class _SkipState:
    armed: ArmedWait | None = None
    count: int = 0
    seconds: float = 0.0
    by_kind: dict[str, int] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    # Set when a skip lands on a wait that protects a measurement and
    # the very next trial is the one affected. The mode reads and
    # clears it when it builds that trial's record.
    pending_flag: str | None = None


class WaitSkip:
    """Mixin giving a mode one skippable wait at a time.

    Public surface used by the engine and the screens:
      wait_view(now)   what to draw, or None when nothing is waiting
      skip_wait(now)   end the current wait early, returns whether it did
    Public surface used by the mode itself:
      arm_wait(...)    declare a wait that has just started
      clear_wait()     the wait finished on its own
      take_skip_flag() read-and-clear the pending per-trial flag
      wait_skip_stats() the block_stats block
    """

    # ---- mode side ---------------------------------------------------

    def _skip_state(self) -> _SkipState:
        st = getattr(self, "_wait_skip_state", None)
        if st is None:
            st = _SkipState()
            self._wait_skip_state = st
        return st

    def arm_wait(self, kind: str, ends_at: float,
                 on_skip: Callable[[float], None],
                 started_at: float | None = None,
                 protects: str | None = None,
                 label: str | None = None,
                 hold_when_due: bool = False) -> None:
        st = self._skip_state()
        st.armed = ArmedWait(
            kind=kind, ends_at=float(ends_at), on_skip=on_skip,
            started_at=(float(started_at) if started_at is not None
                        else time.perf_counter()),
            protects=protects, label=label,
            hold_when_due=hold_when_due)

    def refresh_wait(self, kind: str, ends_at: float, **kw) -> None:
        """Arm `kind` if it is not already armed, otherwise just move
        its deadline. A gate re-evaluated every frame calls this so it
        does not rebuild the wait sixty times a second, and so the
        started_at it reports stays the moment the gate began."""
        w = self._skip_state().armed
        if w is not None and w.kind == kind:
            w.ends_at = float(ends_at)
            return
        self.arm_wait(kind, ends_at, **kw)

    def clear_wait(self) -> None:
        self._skip_state().armed = None

    def shift_wait(self, pause_dur: float) -> None:
        """Move the armed wait's deadline forward by a pause, the same
        way every mode shifts its own timestamps in on_resume. Without
        this a rest paused halfway would come back with its control
        reading zero while the mode was still resting, and the two
        would disagree about how much of the floor is left."""
        w = self._skip_state().armed
        if w is None:
            return
        w.ends_at += float(pause_dur)
        w.started_at += float(pause_dur)

    def armed_wait(self) -> ArmedWait | None:
        return self._skip_state().armed

    def take_skip_flag(self) -> str | None:
        """Read and clear the flag left by a skip that shortened a
        wait protecting the trial about to run. Called by the mode
        when it builds that trial's record, so the flag reaches the
        CSV rather than only the block summary."""
        st = self._skip_state()
        flag = st.pending_flag
        st.pending_flag = None
        return flag

    # ---- engine and screen side --------------------------------------

    def wait_view(self, now: float | None = None) -> dict | None:
        """What the screen should draw for the wait in flight, or None.

        `show` is the chip decision (long enough to be worth a target);
        the keyboard skip works whenever this returns anything at all.
        """
        st = self._skip_state()
        w = st.armed
        if w is None:
            return None
        now = time.perf_counter() if now is None else now
        remaining = w.remaining(now)
        return {
            "kind": w.kind,
            "label": w.button_label(),
            "remaining": remaining,
            "total": w.total_s,
            "protects": w.protects,
            "show": (w.total_s >= self._chip_min_s()
                     and (remaining > 0.05 or w.hold_when_due)),
        }

    def _chip_min_s(self) -> float:
        cfg = getattr(getattr(self, "engine", None), "cfg", None)
        if cfg is None:
            return DEFAULT_CHIP_MIN_S
        try:
            return float(cfg.get("game.skip_chip_min_s",
                                 DEFAULT_CHIP_MIN_S))
        except (TypeError, ValueError):
            # A MagicMock cfg in a test fixture returns something that
            # is not a number; the shipped threshold is the safe read.
            return DEFAULT_CHIP_MIN_S

    def skip_wait(self, now: float | None = None) -> bool:
        """Cut the current wait short. Returns False when nothing was
        waiting, so a stray Space press on a live trial does nothing."""
        st = self._skip_state()
        w = st.armed
        if w is None:
            return False
        now = time.perf_counter() if now is None else now
        saved = w.remaining(now)
        # Release first, book after: if the mode's own release raises,
        # nothing may claim the wait was skipped. The old order counted
        # the skip, queued the CSV row and THEN failed, leaving the
        # summary asserting a skip that never took effect while the
        # keypress fell through to the mode as input.
        st.armed = None
        try:
            w.on_skip(now)
        except Exception:
            log.exception("skip callback failed for wait %r", w.kind)
            st.armed = w
            return False
        st.count += 1
        st.seconds += saved
        st.by_kind[w.kind] = st.by_kind.get(w.kind, 0) + 1
        st.events.append({"kind": w.kind,
                          "saved_s": round(saved, 2),
                          "planned_s": round(w.total_s, 2),
                          "protects": w.protects})
        if w.protects:
            # The next trial ran with less of this wait than the design
            # asked for. Flag it so a row in the CSV carries the fact,
            # not just a count in the block summary.
            st.pending_flag = w.kind
        self._record_skip(w, saved, now)
        return True

    def _record_skip(self, w: ArmedWait, saved: float,
                     now: float) -> None:
        raw = getattr(getattr(self, "engine", None), "raw_logger", None)
        if not raw:
            return
        try:
            raw.queue_event(
                "rest_skipped",
                detail=(f"kind={w.kind};saved_s={saved:.2f};"
                        f"planned_s={w.total_s:.2f};"
                        f"protects={w.protects or ''}"),
                t_perf=now,
                hand=getattr(getattr(self, "engine", None),
                             "hand_mode", "right"))
        except Exception:
            log.debug("could not log the skipped rest", exc_info=True)

    def wait_skip_stats(self) -> dict:
        """The block_stats block. Present in every mode that can wait,
        zero when nobody skipped anything, so an analysis can tell
        'nobody skipped' apart from 'this mode does not report it'."""
        st = self._skip_state()
        return {
            "skipped_rests": st.count,
            "skipped_rest_s": round(st.seconds, 2),
            "skipped_rest_kinds": dict(st.by_kind),
            "skipped_rest_events": list(st.events),
        }
