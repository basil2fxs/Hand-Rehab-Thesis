"""The root README is the handover. Nobody hands this rig over in person.

The README is written so the next student can pick the project up with
nothing else, which means the parts that answer a question in the middle
of a clinic are the parts worth pinning: the game table (a mode added to
the hub and not to the table is a mode nobody outside the code knows
exists), the troubleshooting entries (the only place the failure modes
of the hardware are written down), and the names those entries tell
somebody to click or edit. A button renamed in the UI or a config key
renamed in default.yaml leaves the README quietly telling the next
person to look for something that is gone, and nothing else would catch
it. The rest is cheap rot cover: the screenshots it opens with, links to
files that were moved, its length, and the plain ASCII house rule.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
ASSET_READMES = sorted((REPO / "assets").glob("*/README.md"))
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

# The order a reader meets them: what it is, how to start it, what the
# games are, what to do when the hardware misbehaves, then the data and
# the handover notes.
SECTIONS = [
    "How it works",
    "Run it",
    "The ten games",
    "Troubleshooting",
    "Data and analysis",
    "If you are taking this over",
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

# Config keys the README quotes by name. A key renamed in default.yaml
# without the README following turns advice into a wild goose chase.
CONFIG_KEYS = [
    "eeg.port",
    "eeg.require_port",
    "eeg.baud",
    "game.test_mode_enabled",
    "reaction.block_trials",
    "reaction.response_windows_s",
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
        lines = _readme().splitlines()
        self.assertLess(len(lines), 170,
                        f"README is {len(lines)} lines; keep it near 160")

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


class LinksAndImagesResolveTests(unittest.TestCase):

    def _targets(self) -> list[str]:
        text = _readme()
        # Markdown images and links, plus the src/href of any raw HTML.
        # Anything starting with a scheme is external.
        found = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
        found += re.findall(r'(?:src|href)="([^"]+)"', text)
        return [t for t in found
                if not t.startswith(("http://", "https://", "#"))]

    def test_both_screenshots_are_committed(self):
        """One of the hub and one of a game in play. Rendered from the
        real screens, so a screenshot that vanishes is a README opening
        on a broken image."""
        text = _readme()
        for name in ("hub.png", "reaction.png"):
            shot = REPO / "docs" / "images" / name
            with self.subTest(shot=name):
                self.assertTrue(shot.is_file(),
                                f"docs/images/{name} is missing")
                self.assertIn(f"docs/images/{name}", text)

    def test_every_local_link_points_at_something(self):
        for target in self._targets():
            with self.subTest(target=target):
                self.assertTrue((REPO / target).exists(),
                                f"README links to {target}, which is gone")


class HouseStyleTests(unittest.TestCase):

    def test_plain_ascii(self):
        for path in (README, *ASSET_READMES):
            text = path.read_text(encoding="utf-8")
            for ch in BANNED_CHARS:
                with self.subTest(file=path.parent.name, char=hex(ord(ch))):
                    self.assertNotIn(ch, text)

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


if __name__ == "__main__":
    unittest.main()
