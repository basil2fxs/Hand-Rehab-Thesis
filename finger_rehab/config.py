"""YAML config loader. Defaults + optional override file + dotted-key access."""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


log = logging.getLogger(__name__)


def _bundle_root() -> Path:
    """Return the folder that contains the bundled data files.

    Two cases:
      - Frozen by PyInstaller: data files are under sys._MEIPASS at runtime.
      - Source checkout: the repo root is one level above this file.
    Writable user data (sessions/, the calibration JSON the user edits) should
    live next to the executable, not inside _MEIPASS which is read-only.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def _user_root() -> Path:
    """Where writable files (sessions/, logs) go when frozen."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        # On macOS the executable lives at Foo.app/Contents/MacOS/Foo.
        # Writing next to the executable would bury sessions/ INSIDE
        # the .app bundle where nobody can find it. Walk up out of the
        # bundle so data lands next to the .app the user double-clicked.
        root = exe.parent
        for parent in exe.parents:
            if parent.name.endswith(".app"):
                root = parent.parent
                break
        # The app must run wherever it gets copied. If the folder next
        # to it can't be written (locked-down Applications folder, a
        # network share, running straight off a disk image), fall back
        # to a folder in the user's home so recording still works.
        if os.access(root, os.W_OK):
            return root
        fallback = Path.home() / "Finger Rehab Data"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Home is unwritable too; return it anyway so path
            # building stays sane and the failure surfaces where the
            # write happens, with a clearer error.
            pass
        return fallback
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _bundle_root()
USER_ROOT = _user_root()
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.yaml"
# Optional sibling file with user-set overrides (currently: per-hand
# port assignments from the Settings screen). Created lazily by
# Config.save_user_overrides when the user changes a setting, then
# auto-merged on top of default.yaml at next launch.
USER_OVERRIDES = USER_ROOT / "config" / "user_settings.yaml"


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


# Sentinel for "the override file did not mention this key at all",
# which is different from "it set it to None".
_UNSET = object()


def _dig(d: dict, *path: str):
    node: Any = d
    for part in path:
        if not isinstance(node, dict) or part not in node:
            return _UNSET
        node = node[part]
    return node


def apply_cue_migration(merged: dict, overrides: dict) -> list[str]:
    """Translate an older override file onto the cue.* toggles.

    Builds before the four sensory-cue switches stored the cue setup as
    game_cue.mode (both / visual / vibration) plus motor.enabled, and
    the pre-press tone as audio.stim_tone_enabled. Somebody who set
    those has a device that behaves a particular way, so we read them
    once rather than dropping them and silently handing them a
    different device.

    The mapping:
        motor.enabled false, or mode "visual"  -> buzz_before false
        mode "vibration"                       -> show_target false
        audio.stim_tone_enabled false          -> sound_before false

    `overrides` is what the user's own file said and `merged` is that
    file already sitting on top of default.yaml. A cue.* key the user
    has set explicitly always wins, so once the Settings screen has
    written the new keys the legacy ones stop mattering. Returns the
    names of the keys that were derived, for the log line.
    """
    if not isinstance(overrides, dict):
        return []
    user_cue = overrides.get("cue")
    if not isinstance(user_cue, dict):
        user_cue = {}
    legacy_mode = _dig(overrides, "game_cue", "mode")
    legacy_motor = _dig(overrides, "motor", "enabled")
    legacy_tone = _dig(overrides, "audio", "stim_tone_enabled")
    derived: dict[str, bool] = {}
    if legacy_mode is not _UNSET or legacy_motor is not _UNSET:
        mode = "both"
        if legacy_mode is not _UNSET:
            mode = str(legacy_mode or "both").strip().lower()
            if mode not in ("both", "visual", "vibration"):
                mode = "both"
        motors_on = True if legacy_motor is _UNSET else bool(legacy_motor)
        if "buzz_before" not in user_cue:
            derived["buzz_before"] = motors_on and mode != "visual"
        if "show_target" not in user_cue:
            derived["show_target"] = mode != "vibration"
    if legacy_tone is not _UNSET and "sound_before" not in user_cue:
        derived["sound_before"] = bool(legacy_tone)
    if derived:
        cue = merged.setdefault("cue", {})
        if not isinstance(cue, dict):
            cue = {}
            merged["cue"] = cue
        cue.update(derived)
    return sorted(derived)


@dataclass
class Config:
    data: dict = field(default_factory=dict)
    source: Path | None = None

    @classmethod
    def load(cls, override: str | Path | None = None) -> "Config":
        with DEFAULT_CONFIG.open("r", encoding="utf-8") as f:
            merged = yaml.safe_load(f) or {}
        src = DEFAULT_CONFIG
        # Auto-merge user_settings.yaml if it exists. This is how the
        # Settings screen on the title page persists per-hand COM port
        # assignments and any other user-tweakable config. A malformed
        # user file just logs a warning - we never crash startup on it.
        overrides: dict = {}
        if USER_OVERRIDES.exists() and override is None:
            try:
                with USER_OVERRIDES.open("r", encoding="utf-8") as f:
                    user = yaml.safe_load(f) or {}
                if isinstance(user, dict):
                    merged = _merge(merged, user)
                    overrides = user
                    src = USER_OVERRIDES
                else:
                    log.warning("user_settings.yaml is not a mapping; "
                                 "ignoring")
            except Exception as e:
                log.warning("Could not load user_settings.yaml: %s", e)
        if override:
            p = Path(override)
            with p.open("r", encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            merged = _merge(merged, user)
            if isinstance(user, dict):
                overrides = user
            src = p
        # An override file from an older build sets the cue up through
        # keys this one no longer reads. Translate them before anything
        # asks the config what the cues are.
        migrated = apply_cue_migration(merged, overrides)
        if migrated:
            log.info("Translated legacy cue settings onto %s",
                     ", ".join("cue." + k for k in migrated))
        cfg = cls(data=merged, source=src)
        # Feedback style is checked at load, not at first trial: a lab
        # session recorded with the feedback glyph inside the
        # response-locked window is unusable, and finding out at
        # startup costs nothing.
        from .ui.feedback_bank import check_style_config
        check_style_config(cfg)
        return cfg

    def save_user_overrides(self, overrides: dict) -> Path:
        """Persist user-set config to USER_OVERRIDES (atomic write).

        `overrides` is a flat dict of dotted-keys: e.g.
        `{'serial.left_port': '/dev/cu.A', 'serial.right_port': None}`.
        Existing keys in the file are preserved unless replaced. The
        in-memory `self.data` is also updated so the change takes
        effect for the current session without a reload.
        Returns the file path written.
        """
        import os as _os
        # Load the existing override file (if any) so we don't clobber
        # other keys the user has previously set.
        existing: dict = {}
        if USER_OVERRIDES.exists():
            try:
                with USER_OVERRIDES.open("r", encoding="utf-8") as f:
                    loaded = yaml.safe_load(f) or {}
                if isinstance(loaded, dict):
                    existing = loaded
            except Exception as e:
                log.warning("Could not read user_settings.yaml: %s", e)
        # Set each dotted key in both the on-disk dict and the in-memory
        # data so the running app sees the change immediately.
        for key, value in overrides.items():
            parts = key.split(".")
            for target in (existing, self.data):
                node = target
                for part in parts[:-1]:
                    if part not in node or not isinstance(node[part], dict):
                        node[part] = {}
                    node = node[part]
                node[parts[-1]] = value
        # Atomic write so a crash mid-save doesn't lose previous settings.
        USER_OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
        payload = yaml.safe_dump(existing, sort_keys=False)
        tmp = USER_OVERRIDES.with_name(USER_OVERRIDES.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                _os.fsync(f.fileno())
            except (OSError, AttributeError) as e:
                # fsync is best-effort. Some filesystems (network
                # mounts, mocked-file tests) raise; the atomic
                # replace below still gives the no-truncated-file
                # guarantee, so we keep going and log at debug for
                # diagnostics.
                log.debug("fsync on user_settings tmp failed: %s", e)
        _os.replace(tmp, USER_OVERRIDES)
        return USER_OVERRIDES

    def get(self, key: str, default: Any = None) -> Any:
        # Walk dotted path. Returns default if any segment is missing.
        node: Any = self.data
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def resolve_path(self, value: str | Path) -> Path:
        # Read-only assets live under the bundle root, writable files live
        # next to the executable. Whitelist the writable ones explicitly so
        # the frozen app doesn't try to write into _MEIPASS.
        #
        # Match on path PARTS, not string prefixes - otherwise a folder
        # named "sessions_old" or "logs_archive" would incorrectly route
        # to USER_ROOT because "sessions_old".startswith("sessions").
        p = Path(value)
        if p.is_absolute():
            return p
        writable_part_prefixes: tuple[tuple[str, ...], ...] = (
            ("sessions",),
            ("config", "calibration"),
            # Per-participant preferences (data/prefs.py): written by
            # the app, so it lives next to the exe, not in the bundle.
            ("config", "participant_prefs.json"),
            # The researcher's Patterns sequence file (data/
            # pattern_file.py): imported, archived and cleared by the
            # app, so all three live next to the exe rather than in
            # the read-only bundle.
            ("config", "pattern_sequence.yaml"),
            ("config", "pattern_sequence.json"),
            ("config", "pattern_sequences"),
            ("logs",),
        )
        parts = p.parts
        for pref in writable_part_prefixes:
            if parts[:len(pref)] == pref:
                return (USER_ROOT / p).resolve()
        return (PROJECT_ROOT / p).resolve()
