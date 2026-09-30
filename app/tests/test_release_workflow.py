"""The GitHub release is always the newest tested build.

build-apps.yml republishes the release for the code's version on every
push to main that passes the tests and both builds: the tag moves to
the commit and the three files are replaced. Two things once let it go
stale, and both are pinned here: an HTTP 500 from GitHub during the
upload (the calls are now retried), and no way to republish without a
new push (a manual run on main now publishes too). The last step checks
the release really is this build, so a stale release turns the run red
instead of passing quietly.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT.parent / ".github" / "workflows" / "build-apps.yml"


class ReleaseWorkflowTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.flow = yaml.safe_load(cls.text)
        cls.release = cls.flow["jobs"]["release"]
        cls.steps = {s.get("name", ""): s for s in cls.release["steps"]}

    def test_only_a_tested_build_is_released(self):
        self.assertEqual(set(self.release["needs"]), {"test", "build"})

    def test_a_manual_run_on_main_republishes(self):
        cond = self.release["if"]
        self.assertIn("workflow_dispatch", cond)
        self.assertIn("refs/heads/main", cond)

    def test_every_github_call_is_retried(self):
        run = self.steps["Publish the release"]["run"]
        self.assertIn("retry()", run)
        for call in ("retry gh release upload", "retry gh release edit",
                     "retry gh release create"):
            self.assertIn(call, run)
        self.assertIn("--clobber", run)
        self.assertIn("--latest", run)
        # The release record names the commit its tag points at.
        edit = run[run.index("retry gh release edit"):]
        self.assertIn('--target "$GITHUB_SHA"', edit.split("else")[0])

    def test_the_release_is_checked_against_this_build(self):
        run = self.steps["Check the release is this build"]["run"]
        for what in ("git/refs/tags/", "releases/latest", "GITHUB_SHA",
                     "targetCommitish",
                     "FingerRehab-Setup-Windows.exe", "FingerRehab-macOS.dmg",
                     "FingerRehab-EEGLab.zip", "exit 1"):
            self.assertIn(what, run)


if __name__ == "__main__":
    unittest.main()
