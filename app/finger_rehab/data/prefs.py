"""Per-participant preferences: small choices remembered per person.

Today that is one thing, whether the menu music is muted. It lives
here and not in config/user_settings.yaml because that file describes
the MACHINE (ports, levels, cue switches) and is read into every
session's config snapshot, whereas a mute is one person's taste and
must follow that person, not the laptop. Keyed by the same identity
the vs-last-time chip and the session folders use (the normalised
study code, or the trimmed name; NA for an anonymous login), so a
participant who mutes the menus at visit 1 gets silence at visit 2
on the same code.

The file is JSON, one object per identity, written atomically the
way metadata.json is. Missing or unreadable is the same as empty:
the default for every preference is what the app ships with (sound
on), and a broken prefs file must never stop a login.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path


log = logging.getLogger(__name__)

# The config key naming the file, and its default. The default sits
# under config/ next to user_settings.yaml so a study laptop keeps
# everything it remembers in one folder; config.resolve_path routes
# it to the writable root when the app is frozen.
PREFS_KEY = "session.prefs_file"
DEFAULT_PREFS_FILE = "config/participant_prefs.json"

MENU_MUTED = "menu_music_muted"


def identity_key(participant: str | None) -> str:
    """The prefs key for an identity: normalised code, trimmed name,
    NA when blank. Same rule as the session folders."""
    from .intake import normalise_code
    who = normalise_code(participant)
    return who or "NA"


class ParticipantPrefs:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._data: dict = {}
        self._loaded = False

    # ---- file ---------------------------------------------------------
    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        self._data = {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError, UnicodeDecodeError) as e:
            log.warning("participant prefs unreadable (%s): starting "
                        "empty", e)
            return
        people = raw.get("participants") if isinstance(raw, dict) else None
        if isinstance(people, dict):
            self._data = {str(k): dict(v) for k, v in people.items()
                          if isinstance(v, dict)}

    def _save(self) -> bool:
        payload = json.dumps({"version": 1, "participants": self._data},
                             indent=2, ensure_ascii=False, sort_keys=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    pass
            os.replace(tmp, self.path)
            return True
        except OSError as e:
            log.warning("participant prefs not saved: %s", e)
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            return False

    # ---- values -------------------------------------------------------
    def get(self, participant: str | None, key: str, default=None):
        self._load()
        return self._data.get(identity_key(participant), {}).get(key,
                                                                 default)

    def set(self, participant: str | None, key: str, value) -> bool:
        """Write one preference for one identity and save. Returns
        whether the save reached disk; the in-memory value stands
        either way so the running app behaves as asked."""
        self._load()
        self._data.setdefault(identity_key(participant), {})[key] = value
        return self._save()

    # ---- the menu mute ------------------------------------------------
    def menu_muted(self, participant: str | None) -> bool:
        return bool(self.get(participant, MENU_MUTED, False))

    def set_menu_muted(self, participant: str | None, muted: bool) -> bool:
        return self.set(participant, MENU_MUTED, bool(muted))


def prefs_from_config(cfg) -> ParticipantPrefs:
    """The prefs store the config names (session.prefs_file)."""
    path = cfg.get(PREFS_KEY) or DEFAULT_PREFS_FILE
    try:
        resolved = cfg.resolve_path(str(path))
    except Exception:
        resolved = Path(str(path))
    return ParticipantPrefs(resolved)
