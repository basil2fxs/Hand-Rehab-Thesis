"""YAML config loader. Defaults + optional override file + dotted-key access."""
from __future__ import annotations

import logging
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
        # Folder that contains the running executable.
        return Path(sys.executable).resolve().parent
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
        if USER_OVERRIDES.exists() and override is None:
            try:
                with USER_OVERRIDES.open("r", encoding="utf-8") as f:
                    user = yaml.safe_load(f) or {}
                if isinstance(user, dict):
                    merged = _merge(merged, user)
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
            src = p
        return cls(data=merged, source=src)

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
            except (OSError, AttributeError):
                pass
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
            ("logs",),
        )
        parts = p.parts
        for pref in writable_part_prefixes:
            if parts[:len(pref)] == pref:
                return (USER_ROOT / p).resolve()
        return (PROJECT_ROOT / p).resolve()
