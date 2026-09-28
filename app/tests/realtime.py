"""Tests that run real frames on the wall clock.

A few tests drive the game at 60 Hz with real sleeps and check timing
to within one frame: a tone on the beat, a buzz ahead of it, a marker
pulse 10 ms wide. A shared CI runner stalls frames by 50 ms and more,
so there they measure the runner, not the game. They run on a real
machine, the study laptop or a developer's, and CI skips them. Run the
whole suite locally before a release.
"""
from __future__ import annotations

import os
import unittest

# GitHub Actions sets CI=true on every runner.
ON_CI = os.environ.get("CI", "").strip().lower() == "true"

real_time = unittest.skipIf(
    ON_CI, "real-time frame loop: a shared CI runner stalls frames by "
           "50 ms and more, so it times the runner, not the game")
