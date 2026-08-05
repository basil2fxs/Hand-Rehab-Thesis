"""Test setup that applies to every test file.

The important thing here is that a test can never write to the real
config/user_settings.yaml. Anything that drives the Settings screen, the
results screen or Config.save_user_overrides writes to that file for
real, and it is the file that decides how the device behaves in a
session.

That has already gone wrong three times in this repository. A cue switch
left flipped by a test meant the game ran a block with the wrong cue
condition, and the only sign was a trial row reading BS/B- when it
should have read BS/--. Nothing failed, nothing warned; the data was
just quietly recorded under a setting nobody chose.

So every test session redirects the overrides file into a temp
directory. Tests still exercise the real save path, they just cannot
reach the real file.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True, scope="session")
def _never_touch_the_real_user_settings(tmp_path_factory):
    """Point USER_OVERRIDES at a temp file for the whole run."""
    import rehab.config as config

    real = config.USER_OVERRIDES
    fake = tmp_path_factory.mktemp("user-config") / "user_settings.yaml"
    # Start from whatever the real file holds, so tests see the same
    # shape of config a user would, without being able to write back.
    if real.exists():
        try:
            fake.write_text(real.read_text())
        except OSError:
            pass
    config.USER_OVERRIDES = fake
    yield
    config.USER_OVERRIDES = real


@pytest.fixture(autouse=True)
def _real_user_settings_is_untouched():
    """Fail loudly if a test writes to the real file anyway.

    The redirect above covers anything going through rehab.config. This
    catches a test that reaches the path some other way, which is how it
    would slip through again.
    """
    real = Path(__file__).resolve().parents[1] / "config" / "user_settings.yaml"
    before = real.read_text() if real.exists() else None
    yield
    after = real.read_text() if real.exists() else None
    if before != after:
        # Put it back before failing, so one bad test does not leave the
        # device configured wrongly for the next session.
        if before is None:
            real.unlink(missing_ok=True)
        else:
            real.write_text(before)
        pytest.fail(
            "a test wrote to the real config/user_settings.yaml. It has "
            "been restored, but the write needs to go to a temp path: "
            "that file decides how the device behaves in a session.")
