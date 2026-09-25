"""The root README is the handover. Nobody hands this rig over in person.

Two things ship: an installer for home use and a folder for the EEG
lab. The README is written around those two, so the parts worth
pinning are the ones somebody reads with a broken rig or a fresh
laptop in front of them: the installer names (they must match what CI
uploads), the game table (a mode added to the hub and not to the table
is a mode nobody outside the code knows exists), the troubleshooting
entries (the only place the hardware's failure modes are written down)
and the buttons and config keys those entries tell somebody to press
or edit. The rest is cheap rot cover: the screenshots, links to files
that were moved, the length, and the plain ASCII house rule, which the
short READMEs beside the assets and the builds share.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
# README.md sits at the top level beside app/: it is the front door of
# the whole thing, not of the package. app/ has a short README of its own
# for whoever changes the code, so the top level is looked at first.
README = (REPO.parent / "README.md" if (REPO.parent / "README.md").is_file()
          else REPO / "README.md")
ASSET_READMES = sorted((REPO / "assets").glob("*/README.md"))
# The short instruction files this README points at or sits beside.
SIDE_DOCS = [
    REPO / "builds" / "README.txt",
    REPO / "docs" / "flashing.txt",
    REPO / "docs" / "eeg_lab_setup.txt",
    # The lab folder sits at the top level, beside app/, because it is
    # the thing that gets copied to a USB stick.
    REPO.parent / "EEG_Lab" / "README.txt",
]
# The house rule bans these outright. The em dash and the section sign
# are the two that keep coming back from pasted text.
# Written as escapes so this file is itself plain ASCII.
BANNED_CHARS = (
    "\u2014"  # em dash
    "\u2013"  # en dash
    "\u00a7"  # section sign
    "\u2018\u2019\u201c\u201d"  # curly quotes
    "\u2026"  # ellipsis
    "\u00a0"  # non-breaking space
)
# Words the house style bans in any file. Matched as whole words,
# case-insensitively.
BANNED_WORDS = ("delve", "leverage", "robust", "seamless", "showcase",
                "crucial", "pivotal", "intricate", "testament", "foster",
                "comprehensive", "profound")

# The order a reader meets them: what it is, how to install it, what
# happens at the USB socket, the games, the repairs, the failures, the
# data, the lab, the licence.
SECTIONS = [
    "Where things are",
    "How it works",
    "Install",
    "When a board is plugged in",
    "The ten games",
    "Settings",
    "Troubleshooting",
    "Data",
    "The lab folder",
    "Licence",
]

# One entry per failure the device actually has. Each is a bolded
# symptom, because that is what somebody scans for with a broken rig in
# front of them.
SYMPTOMS = [
    "A sensor reads nothing, or sits at zero.",
    "A sensor drifts, or reads high at rest.",
    "The board is not found, or the port keeps changing.",
    "Calibration is asked for every time.",
    "A buzzer does not buzz.",
    "Presses register on the wrong finger.",
    "The game does not open when I plug the board in.",
    "The board needs re-flashing.",
    "The game runs but no data lands.",
    "The EEG box does not appear.",
    "Sessions look empty in the notebook.",
]

# Things the troubleshooting entries tell somebody to click. These are
# button labels built in finger_rehab/ui, so renaming one there has to
# rename it here too.
SETTINGS_CONTROLS = [
    "Sensor address",
    "Flash firmware",
    "Open data folder",
    "Scan",
]

# The three repairs the Settings section lists, one bold lead each,
# and the label the UI draws for each. The auto-start switch carries
# its state in the label.
REPAIRS = {
    "Auto-start": "Auto-start: on",
    "Flash firmware": "Flash firmware",
    "Sensor address": "Sensor address",
}

# Config keys the README quotes by name. A key renamed in default.yaml
# without the README following turns advice into a wild goose chase.
CONFIG_KEYS = [
    "eeg.port",
    "eeg.require_port",
    "eeg.baud",
    "game.test_mode_enabled",
]

# What CI uploads, by file name. The Install and lab sections name
# them, so a rename in the workflow has to reach the README.
ARTEFACTS = [
    "FingerRehab-Setup-Windows.exe",
    "FingerRehab-macOS.dmg",
    "FingerRehab-EEGLab.zip",
]


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def _section(name: str) -> str:
    """The body of one "## " section, up to the next one."""
    text = _readme()
    m = re.search(rf"^## {re.escape(name)}$(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    assert m, f"README has no section called {name}"
    return m.group(1)


class ReadmeExistsTests(unittest.TestCase):

    def test_markdown_not_plain_text(self):
        """GitHub renders .md and not .txt, which is the whole reason
        the old README.txt was replaced."""
        self.assertTrue(README.is_file(), "README.md is missing")
        self.assertFalse((REPO / "README.txt").exists(),
                         "README.txt came back; README.md replaced it")

    def test_it_stays_short(self):
        # Lines of text only. The header and the screenshot gallery are
        # HTML that GitHub draws as pictures, not text anyone reads.
        lines = [ln for ln in _readme().splitlines()
                 if not ln.lstrip().startswith("<")]
        # Two deliverables, one page. The bound moves when a feature
        # does and not for padding.
        self.assertLess(len(lines), 162,
                        f"README has {len(lines)} lines of text; keep it "
                        f"under 162")

    def test_every_section_is_there_in_order(self):
        found = re.findall(r"^## (.+)$", _readme(), re.M)
        self.assertEqual(found, SECTIONS)

    def test_the_chain_is_drawn(self):
        """A mermaid block, so GitHub draws the hand-to-notebook chain
        without an image anyone has to remember to re-export."""
        body = _section("How it works")
        self.assertIn("```mermaid", body)
        for part in ("Arduino", "STIM:n", "trials.csv"):
            with self.subTest(part=part):
                self.assertIn(part, body)


class TwoDeliverablesTests(unittest.TestCase):
    """The installers and the lab folder, by the names CI gives them."""

    def test_the_readme_names_what_ci_uploads(self):
        ci = (REPO.parent / ".github" / "workflows" / "build-apps.yml").read_text(
            encoding="utf-8")
        text = _readme()
        for name in ARTEFACTS:
            with self.subTest(artefact=name):
                self.assertIn(name, ci, f"CI no longer makes {name}")
                self.assertIn(name, text, f"the README does not name {name}")

    def test_the_first_open_notes_are_there(self):
        # Neither installer is signed, so both first opens need one
        # click through. The exact wording is what a person searches
        # the README for while the dialog is on screen.
        body = _section("Install")
        self.assertIn("Windows protected your PC", body)
        self.assertIn("Open Anyway", body)

    def test_the_lab_section_is_four_lines(self):
        lines = [ln for ln in _section("The lab folder").splitlines()
                 if ln.strip()]
        self.assertEqual(len(lines), 4, lines)
        self.assertIn("run_in_psychopy.py", "\n".join(lines))

    def test_the_settings_section_lists_the_three_repairs(self):
        ui = "\n".join(p.read_text(encoding="utf-8")
                       for p in sorted((REPO / "finger_rehab" / "ui")
                                       .glob("*.py")))
        body = _section("Settings")
        leads = re.findall(r"^- \*\*(.+?):\*\*", body, re.M)
        self.assertEqual(leads, list(REPAIRS))
        for label in REPAIRS.values():
            with self.subTest(label=label):
                self.assertIn(f'"{label}"', ui,
                              f"no button labelled {label} in the UI")


class EveryLiveModeIsListedTests(unittest.TestCase):
    """The hub's own MODES table is the source of truth."""

    def _titles(self) -> list[str]:
        from finger_rehab.ui.screens import ModeSelectScreen
        return [title for _key, title, _desc in ModeSelectScreen.MODES]

    def test_every_hub_mode_has_a_readme_row(self):
        text = _readme()
        for title in self._titles():
            with self.subTest(mode=title):
                self.assertIn(f"| **{title}** |", text,
                              f"the README game table is missing {title}")

    def test_the_table_lists_nothing_extra(self):
        """A mode retired from the hub has to leave the table too, or
        the README advertises a game that cannot be picked."""
        rows = re.findall(r"^\| \*\*(.+?)\*\* \|", _readme(), re.M)
        self.assertEqual(sorted(rows), sorted(self._titles()))

    def test_one_line_each(self):
        for row in re.findall(r"^\| \*\*.+?\*\* \| (.+?) \|$",
                              _readme(), re.M):
            self.assertLessEqual(len(row), 110,
                                 f"table row runs long: {row[:40]}...")


class TroubleshootingTests(unittest.TestCase):
    """The section the next person actually reads, under pressure."""

    def test_every_symptom_has_an_entry(self):
        body = _section("Troubleshooting")
        for symptom in SYMPTOMS:
            with self.subTest(symptom=symptom):
                self.assertIn(f"**{symptom}**", body)

    def test_nothing_extra_and_nothing_lost(self):
        leads = re.findall(r"^\*\*(.+?)\*\*", _section("Troubleshooting"),
                           re.M)
        self.assertEqual(leads, SYMPTOMS)

    def test_it_is_the_biggest_section(self):
        """Handover value lives here, so it outweighs every other
        section. A troubleshooting entry trimmed away to make room for
        prose elsewhere is the wrong trade."""
        sizes = {name: len(_section(name).split()) for name in SECTIONS}
        biggest = max(sizes, key=sizes.get)
        self.assertEqual(biggest, "Troubleshooting", sizes)

    def test_the_buttons_it_names_still_exist(self):
        ui = "\n".join(p.read_text(encoding="utf-8")
                       for p in sorted((REPO / "finger_rehab" / "ui")
                                       .glob("*.py")))
        body = _section("Troubleshooting")
        for label in SETTINGS_CONTROLS:
            with self.subTest(control=label):
                self.assertIn(label, body,
                              "the README stopped naming this control")
                self.assertIn(f'"{label}"', ui,
                              f"no button labelled {label} in the UI")

    def test_the_config_keys_it_names_still_exist(self):
        from finger_rehab.config import Config
        cfg = Config.load()
        text = _readme()
        sentinel = object()
        for key in CONFIG_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, text,
                              "the README stopped naming this key")
                self.assertIsNot(cfg.get(key, sentinel), sentinel,
                                 f"{key} is gone from default.yaml")

    def test_no_launcher_that_the_lab_folder_does_not_ship(self):
        # The lab folder ships run_in_psychopy.py and the exe. An entry
        # that sends the lab to a .bat or .command file sends them to
        # nothing.
        body = _section("Troubleshooting")
        self.assertNotIn("EEG Lab.bat", body)
        self.assertNotIn("EEG Lab.command", body)


class LinksAndImagesResolveTests(unittest.TestCase):

    def _targets(self) -> list[str]:
        text = _readme()
        # Markdown images and links, plus the src/href of any raw HTML.
        # Anything starting with a scheme is external.
        found = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
        found += re.findall(r'(?:src|href)="([^"]+)"', text)
        return [t for t in found
                if not t.startswith(("http://", "https://", "#"))]

    # The hub up top, then the games as they look in play. Rendered
    # from the real screens by a simulated player, so a screenshot that
    # vanishes is a README opening on a broken image.
    SCREENSHOTS = ("hub.png", "adaptive.png", "chords.png", "rhythm.png",
                   "force_pilot.png", "syllables.png", "results.png")

    def test_the_screenshots_are_committed(self):
        text = _readme()
        for name in self.SCREENSHOTS:
            shot = REPO / "docs" / "images" / name
            with self.subTest(shot=name):
                self.assertTrue(shot.is_file(),
                                f"docs/images/{name} is missing")
                self.assertIn(f"app/docs/images/{name}", text)

    def test_every_local_link_points_at_something(self):
        for target in self._targets():
            with self.subTest(target=target):
                # Links are relative to the README, which sits at the
                # top level, not to the package root.
                self.assertTrue((README.parent / target).exists(),
                                f"README links to {target}, which is gone")


class HouseStyleTests(unittest.TestCase):

    def _files(self) -> list[Path]:
        return [README, *ASSET_READMES, *SIDE_DOCS]

    def test_plain_ascii(self):
        for path in self._files():
            text = path.read_text(encoding="utf-8")
            for ch in BANNED_CHARS:
                with self.subTest(file=path.name, char=hex(ord(ch))):
                    self.assertNotIn(ch, text)

    def test_no_banned_words(self):
        for path in self._files():
            text = path.read_text(encoding="utf-8")
            for word in BANNED_WORDS:
                with self.subTest(file=path.name, word=word):
                    self.assertIsNone(
                        re.search(rf"\b{word}\b", text, re.I),
                        f"{path.name} uses the banned word {word}")

    def test_asset_readmes_are_three_lines(self):
        """They sit under the file list on GitHub. Three lines is what
        somebody reads there; a page is not."""
        self.assertTrue(ASSET_READMES, "no assets/*/README.md found")
        for path in ASSET_READMES:
            lines = [ln for ln in path.read_text(encoding="utf-8").splitlines()
                     if ln.strip()]
            with self.subTest(file=path.parent.name):
                self.assertEqual(len(lines), 3,
                                 f"{path.parent.name}/README.md is "
                                 f"{len(lines)} lines")

    def test_flashing_notes_fit_on_one_screen(self):
        lines = [ln for ln in (REPO / "docs" / "flashing.txt")
                 .read_text(encoding="utf-8").splitlines() if ln.strip()]
        self.assertLessEqual(len(lines), 10, len(lines))

    def test_builds_has_one_instruction_file(self):
        # builds/README.txt covers both installers. The per-platform
        # HOW TO files it replaced described the bare exe and app,
        # which are not what anyone installs now.
        self.assertTrue((REPO / "builds" / "README.txt").is_file())
        stray = [p for p in (REPO / "builds").rglob("HOW TO*")]
        self.assertEqual(stray, [])


if __name__ == "__main__":
    unittest.main()
