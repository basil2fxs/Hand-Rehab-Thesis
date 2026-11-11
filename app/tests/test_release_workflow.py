"""The GitHub release is always the newest tested build.

build-apps.yml republishes the release for the code's version on every
push to main that passes the tests and both builds: the tag moves to
the commit and the three files are replaced. Two things once let it go
stale, and both are pinned here: an HTTP 500 from GitHub during the
upload (the calls are now retried), and no way to republish without a
new push (a manual run on main now publishes too). The last step checks
the release really is this build, so a stale release turns the run red
instead of passing quietly.

A third came on 22 October 2026: pandas 3.1 was released, a notebook
table printed differently, one test failed and nothing was published
for three weeks. CI now installs the exact versions in constraints.txt.
The release also kept the date it was first published, 28 September,
beside files built in November, so each rebuild now dates it again.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT.parent / ".github" / "workflows" / "build-apps.yml"
CONSTRAINTS = ROOT / "constraints.txt"


def _norm(name: str) -> str:
    """pip treats pygame_ce, pygame-ce and Pygame.CE as one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _key(version: str) -> tuple:
    return tuple(int(n) for n in re.findall(r"\d+", version))


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

    def test_a_rebuilt_release_is_dated_by_its_build(self):
        # GitHub shows the day a release was first published. Going to
        # draft and back dates it by this build, and a step that always
        # runs publishes it again if the job died in between.
        run = self.steps["Publish the release"]["run"]
        self.assertLess(run.index("draft=true"), run.index("draft=false"))
        self.assertIn("make_latest=true", run)
        net = self.steps["Never leave the release a draft"]
        self.assertEqual(net["if"], "always()")
        self.assertIn("draft=false", net["run"])
        names = [s.get("name", "") for s in self.release["steps"]]
        self.assertLess(names.index("Publish the release"),
                        names.index("Never leave the release a draft"))
        self.assertLess(names.index("Never leave the release a draft"),
                        names.index("Check the release is this build"))
        check = self.steps["Check the release is this build"]["run"]
        self.assertIn("isDraft", check)
        self.assertIn("publishedAt", check)


class PinnedLibrariesTests(unittest.TestCase):
    """CI tests and builds with the versions in constraints.txt, so a
    library's new version cannot fail a build that passed the day
    before. requirements.txt keeps the minimums for running from
    source."""

    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        cls.pins = {}
        for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name, _, version = line.partition("==")
                cls.pins[_norm(name)] = version

    def test_every_install_uses_the_pins(self):
        installs = [ln.strip() for ln in self.workflow.splitlines()
                    if "pip install" in ln and "--upgrade pip" not in ln
                    and not ln.lstrip().startswith("#")]
        self.assertEqual(len(installs), 3, installs)
        for ln in installs:
            with self.subTest(line=ln):
                self.assertIn("-c constraints.txt", ln)

    def test_every_pin_is_one_exact_version(self):
        self.assertTrue(self.pins)
        for name, version in self.pins.items():
            with self.subTest(package=name):
                self.assertRegex(version, r"^[0-9][0-9A-Za-z.!+]*$")

    def test_every_requirement_is_pinned_at_or_above_its_minimum(self):
        wanted = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        found = re.findall(r"^([A-Za-z0-9_.-]+)>=([0-9.]+)", wanted, re.M)
        self.assertGreaterEqual(len(found), 10)
        for name, minimum in found:
            with self.subTest(package=name):
                self.assertIn(_norm(name), self.pins)
                self.assertGreaterEqual(_key(self.pins[_norm(name)]),
                                        _key(minimum))
        # The two the workflow installs by name.
        for name in ("pyinstaller", "platformio"):
            with self.subTest(package=name):
                self.assertIn(name, self.pins)


if __name__ == "__main__":
    unittest.main()
