"""The Patterns sequence file: schema, validation, import and the
persistence that makes a loaded file survive a restart.

What is pinned here is the contract a researcher relies on. A file
either loads whole or changes nothing on disk, so a bad edit can never
take the built-in riff away mid-study. Every rejection is a plain
sentence, and the sentences are pinned exactly because the Settings
screen shows them and a test that only checked "some error" would let
them rot into stack traces. An accepted file is archived before it
becomes active, so the thesis can say which schedule ran on which day.
And the sha256 of the exact bytes becomes the schedule id, which is
what stops two different tasks pooling in the analysis.

Nothing here touches the real config/pattern_sequence* paths: every
test points the three config keys at a temp directory, and
tearDownModule fails the run if the real ones appeared anyway.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

REPO = Path(__file__).resolve().parents[1]
REAL_PATHS = (REPO / "config" / "pattern_sequence.yaml",
              REPO / "config" / "pattern_sequence.json",
              REPO / "config" / "pattern_sequences")
_REAL_BEFORE: dict = {}


def setUpModule() -> None:
    for p in REAL_PATHS:
        _REAL_BEFORE[p] = p.exists()


def tearDownModule() -> None:
    for p in REAL_PATHS:
        if p.exists() != _REAL_BEFORE.get(p, False):
            raise AssertionError(
                f"the run changed {p}; point pattern.sequence_file, "
                f"pattern.sequence_pointer and pattern.sequence_drop_dir "
                f"at a temp path")


class _Cfg:
    """The two bits of Config the module uses. Real Config objects are
    built in the engine tests; here the point is the file logic, and a
    stub keeps every path inside the temp directory by construction."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.data = {
            "pattern.sequence_file": str(self.root / "pattern_sequence.yaml"),
            "pattern.sequence_pointer": str(
                self.root / "pattern_sequence.json"),
            "pattern.sequence_drop_dir": str(self.root / "pattern_sequences"),
            "pattern.sequence_file_enabled": True,
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    def resolve_path(self, value):
        return Path(value)


GOOD = """\
pattern_file: 1
name: Test riff
hands: one
timeout_ms: 2000
defaults:
  gaps_ms: 500
  rest_after_s: 10
blocks:
  - name: warm
    kind: warmup
    trials: 8
  - name: base
    kind: random
    trials: 8
  - name: riff_1
    kind: seq
    sequence: [2, 4, 1, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
  - name: fresh
    kind: probe
    sequence: [1, 4, 2, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
  - name: riff_2
    kind: seq
    sequence: [2, 4, 1, 3]
    gaps_ms: [400, 400, 800, 1200]
    repeats: 3
    rest_after_s: 30
"""


def _minimal(blocks: str, **top) -> str:
    head = {"pattern_file": 1, "name": "F", "hands": "one"}
    head.update(top)
    lines = []
    for k, v in head.items():
        if isinstance(v, bool):
            v = "true" if v else "false"
        lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\nblocks:\n" + blocks


def _errors(text: str) -> list[str]:
    from finger_rehab.data.pattern_file import SequenceFileError, parse_plan
    try:
        parse_plan(text)
    except SequenceFileError as e:
        return e.errors
    return []


class TemplateTests(unittest.TestCase):
    """A template a researcher cannot load is worse than no template:
    they would edit it, load it, and be told their own edits broke a
    file that was already broken."""

    def test_both_templates_parse_with_no_warnings(self) -> None:
        from finger_rehab.data import pattern_file as pf
        for name, text in (("one", pf.TEMPLATE_ONE_HAND),
                           ("both", pf.TEMPLATE_BOTH_HANDS)):
            plan = pf.parse_plan(text, file_name=f"{name}.yaml")
            self.assertEqual(plan.warnings, [], name)
            self.assertEqual(plan.hands, "one" if name == "one" else "both")
            self.assertEqual(plan.n_lanes, 4 if name == "one" else 8)
            self.assertTrue(plan.seq_blocks())
            self.assertTrue(plan.probe_blocks())

    def test_write_templates_puts_both_in_the_drop_folder(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            cfg = _Cfg(Path(td))
            paths = pf.write_templates(cfg)
            self.assertEqual([p.name for p in paths],
                             ["template_one_hand.yaml",
                              "template_both_hands.yaml"])
            for p in paths:
                self.assertTrue(p.is_file())
                pf.parse_plan(p.read_text(encoding="utf-8"), file_name=p.name)

    def test_the_committed_template_is_the_one_settings_writes(self) -> None:
        # Two copies of the same instructions drift. The committed file
        # is generated from the constant, so this fails the moment they
        # stop matching.
        from finger_rehab.data.pattern_file import TEMPLATE_ONE_HAND
        committed = REPO / "config" / "pattern_sequence_template.yaml"
        self.assertTrue(committed.is_file())
        self.assertEqual(committed.read_text(encoding="utf-8"),
                         TEMPLATE_ONE_HAND)

    def test_the_shipped_examples_parse_to_their_stated_counts(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        folder = REPO / "docs" / "pattern_sequences"
        one = parse_plan((folder / "example_one_hand.yaml").read_text())
        both = parse_plan((folder / "example_both_hands.yaml").read_text())
        self.assertEqual(one.total_trials, 284)
        self.assertEqual(one.cycle_len, 8)
        self.assertTrue(one.explicit)
        self.assertTrue(one.show_sequence)
        self.assertEqual(both.total_trials, 304)
        self.assertEqual(both.cycle_len, 16)
        self.assertFalse(both.explicit)
        self.assertEqual(one.warnings, [])
        self.assertEqual(both.warnings, [])


class ValidationTests(unittest.TestCase):
    """One test per rule, each with the exact sentence the screen
    shows. Exact because the researcher fixes the file from that
    sentence and nothing else."""

    def test_a_good_file_becomes_a_plan(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(GOOD, file_name="good.yaml")
        self.assertEqual(plan.name, "Test riff")
        self.assertEqual(plan.cycle_len, 4)
        self.assertEqual(plan.total_trials, 8 + 8 + 12 + 12 + 12)
        self.assertEqual(plan.labels(), ["W", "1", "2", "3", "4"])
        self.assertEqual([b.trials for b in plan.blocks], [8, 8, 12, 12, 12])
        self.assertEqual(plan.blocks[2].gaps_ms, [400, 400, 800, 1200])
        self.assertEqual(plan.blocks[2].sequence, [1, 3, 0, 2])
        self.assertEqual(plan.blocks[-1].rest_after_s, 30.0)
        self.assertEqual(plan.timeout_s, 2.0)
        self.assertEqual(len(plan.sha256), 64)
        self.assertEqual(plan.schedule_id, plan.sha256[:12])

    def test_not_yaml_at_all(self) -> None:
        errs = _errors("pattern_file: 1\n  bad: [\n")
        self.assertEqual(len(errs), 1)
        self.assertTrue(errs[0].startswith("The file is not valid YAML ("),
                        errs[0])
        self.assertIn("line ", errs[0])
        self.assertIn("column ", errs[0])

    def test_not_a_mapping(self) -> None:
        self.assertEqual(
            _errors("- 1\n- 2\n"),
            ["The file must be a mapping with pattern_file: 1 at the top."])

    def test_wrong_schema_version(self) -> None:
        self.assertIn("pattern_file must be 1 (this build reads version 1).",
                      _errors(_minimal("  - {name: a, kind: seq, "
                                       "sequence: [1, 2]}\n",
                                       pattern_file=2)))

    def test_hands_must_be_one_or_both(self) -> None:
        self.assertIn("hands must be one or both.",
                      _errors(_minimal("  - {name: a, kind: seq, "
                                       "sequence: [1, 2]}\n", hands="left")))

    def test_name_is_required(self) -> None:
        text = ("pattern_file: 1\nhands: one\nblocks:\n"
                "  - {name: a, kind: seq, sequence: [1, 2]}\n")
        self.assertIn("name is required (1 to 40 characters).",
                      _errors(text))

    def test_an_unknown_key_is_refused_by_name(self) -> None:
        # gap_ms instead of gaps_ms is the exact slip that would run a
        # whole cohort on the default timing with nobody told.
        errs = _errors(_minimal("  - {name: riff, kind: seq, "
                                "sequence: [1, 2], gap_ms: 300}\n"))
        self.assertIn(
            "Unknown key gap_ms at block riff. Allowed keys: name, kind, "
            "sequence, trials, repeats, gaps_ms, rest_after_s.", errs)

    def test_an_unknown_top_level_key(self) -> None:
        errs = _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2]}\n",
                                tempo=3))
        self.assertTrue(any(e.startswith("Unknown key tempo at the top level.")
                            for e in errs), errs)

    def test_blocks_must_be_a_list(self) -> None:
        self.assertEqual(
            _errors("pattern_file: 1\nname: F\nhands: one\nblocks: 3\n"),
            ["blocks must be a list of 1 to 40 blocks."])

    def test_a_block_needs_a_usable_name(self) -> None:
        self.assertIn(
            "Block 1 needs a name (letters, digits, _ or -, up to 24).",
            _errors(_minimal("  - {name: 'has space', kind: seq, "
                             "sequence: [1, 2]}\n")))

    def test_block_names_are_unique(self) -> None:
        errs = _errors(_minimal(
            "  - {name: riff, kind: seq, sequence: [1, 2]}\n"
            "  - {name: riff, kind: probe, sequence: [2, 1]}\n"))
        self.assertIn("Block riff repeats the name of block 1; names must "
                      "be unique.", errs)

    def test_kind_must_be_one_of_four(self) -> None:
        self.assertIn("Block a: kind must be warmup, random, seq or probe.",
                      _errors(_minimal("  - {name: a, kind: rest}\n")))

    def test_a_lane_out_of_range_is_named(self) -> None:
        self.assertIn(
            "Block a: sequence must be a list of 2 to 64 lane numbers "
            "between 1 and 4.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 5]}\n")))

    def test_a_lane_may_not_follow_itself(self) -> None:
        self.assertIn(
            "Block a: lane 2 follows itself at item 2 (set allow_repeats: "
            "true to permit this).",
            _errors(_minimal("  - {name: a, kind: seq, "
                             "sequence: [1, 2, 2, 3]}\n")))

    def test_allow_repeats_permits_it(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(_minimal(
            "  - {name: a, kind: seq, sequence: [1, 2, 2, 3]}\n",
            allow_repeats=True))
        self.assertEqual(plan.blocks[0].sequence, [0, 1, 1, 2])

    def test_the_wrap_counts_as_a_repeat_too(self) -> None:
        # Item 4 followed by item 1: the take loops, so a sequence that
        # ends on the lane it starts with does press that lane twice.
        self.assertIn(
            "Block a: lane 1 follows itself at item 4 (set allow_repeats: "
            "true to permit this).",
            _errors(_minimal("  - {name: a, kind: seq, "
                             "sequence: [1, 2, 3, 1]}\n")))

    def test_every_sequence_must_be_the_same_length(self) -> None:
        errs = _errors(_minimal(
            "  - {name: riff_1, kind: seq, sequence: [1, 2, 3, 4]}\n"
            "  - {name: fresh, kind: probe, sequence: [2, 1, 3]}\n"))
        self.assertIn(
            "Block fresh: sequence has 3 items but block riff_1 has 4; "
            "every seq and probe sequence must be the same length.", errs)

    def test_trials_bounds(self) -> None:
        self.assertIn(
            "Block b: trials must be a whole number from 1 to 400.",
            _errors(_minimal(
                "  - {name: a, kind: seq, sequence: [1, 2]}\n"
                "  - {name: b, kind: random, trials: 900}\n")))

    def test_repeats_bounds(self) -> None:
        self.assertIn(
            "Block a: repeats must be a whole number from 1 to 50.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2], "
                             "repeats: 99}\n")))

    def test_a_gap_list_must_match_the_sequence_length(self) -> None:
        self.assertIn(
            "Block a: gaps_ms must be one number or a list of exactly 4 "
            "numbers, each 0 to 5000.",
            _errors(_minimal("  - {name: a, kind: seq, "
                             "sequence: [1, 2, 3, 4], gaps_ms: [100, 200]}\n")))

    def test_a_gap_out_of_range(self) -> None:
        self.assertIn(
            "Block a: gaps_ms must be one number or a list of exactly 2 "
            "numbers, each 0 to 5000.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2], "
                             "gaps_ms: 9000}\n")))

    def test_rest_bounds(self) -> None:
        self.assertIn(
            "Block a: rest_after_s must be a number from 0 to 300.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2], "
                             "rest_after_s: 600}\n")))

    def test_a_key_from_the_other_kind_of_block_is_refused(self) -> None:
        self.assertIn(
            "Block a: trials does not apply to a seq block.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2], "
                             "trials: 60}\n")))

    def test_only_one_warmup_and_it_goes_first(self) -> None:
        errs = _errors(_minimal(
            "  - {name: a, kind: seq, sequence: [1, 2]}\n"
            "  - {name: w, kind: warmup, trials: 8}\n"))
        self.assertIn("Only one warmup block is allowed and it must be "
                      "first.", errs)

    def test_a_file_with_no_seq_block(self) -> None:
        self.assertIn(
            "The file has no seq block, so there is nothing to learn.",
            _errors(_minimal("  - {name: b, kind: random, trials: 8}\n")))

    def test_a_probe_that_is_the_riff_rotated(self) -> None:
        # A rotation is the same material: the participant's knowledge
        # transfers straight into it and the rebound measures nothing.
        errs = _errors(_minimal(
            "  - {name: riff_1, kind: seq, sequence: [1, 2, 3, 4]}\n"
            "  - {name: fresh, kind: probe, sequence: [3, 4, 1, 2]}\n"))
        self.assertIn("Probe fresh is the trained riff (riff_1) rotated; a "
                      "probe must be a different order.", errs)

    def test_timeout_bounds(self) -> None:
        self.assertIn(
            "timeout_ms must be a whole number from 300 to 10000.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2]}\n",
                             timeout_ms=50)))

    def test_show_sequence_needs_explicit(self) -> None:
        self.assertIn(
            "show_sequence needs explicit: true.",
            _errors(_minimal("  - {name: a, kind: seq, sequence: [1, 2]}\n",
                             show_sequence=True)))

    def test_the_total_trial_ceiling(self) -> None:
        seq = ", ".join(str((i % 4) + 1) for i in range(64))
        errs = _errors(_minimal(
            f"  - {{name: a, kind: seq, sequence: [{seq}], repeats: 50}}\n"))
        self.assertIn("The file has 3200 trials in total; the limit is 2000.",
                      errs)

    def test_a_rejected_file_reports_every_problem_at_once(self) -> None:
        errs = _errors(_minimal(
            "  - {name: a, kind: seq, sequence: [1, 2], repeats: 99, "
            "rest_after_s: 999}\n", timeout_ms=1))
        self.assertGreaterEqual(len(errs), 3)


class WarningTests(unittest.TestCase):
    """Warnings never block a load: they are judgement calls the
    researcher may have made on purpose."""

    def test_a_probe_with_no_flanker_on_both_sides(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(_minimal(
            "  - {name: riff_1, kind: seq, sequence: [1, 2, 3, 4]}\n"
            "  - {name: fresh, kind: probe, sequence: [2, 4, 1, 3]}\n"))
        self.assertTrue(any("cannot be scored against flanking takes"
                            in w for w in plan.warnings), plan.warnings)

    def test_a_probe_whose_gaps_differ_from_every_seq_block(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(_minimal(
            "  - {name: riff_1, kind: seq, sequence: [1, 2, 3, 4], "
            "gaps_ms: 500}\n"
            "  - {name: fresh, kind: probe, sequence: [2, 4, 1, 3], "
            "gaps_ms: 300}\n"
            "  - {name: riff_2, kind: seq, sequence: [1, 2, 3, 4], "
            "gaps_ms: 500}\n"))
        self.assertTrue(any("changes the timing as well as the order" in w
                            for w in plan.warnings), plan.warnings)

    def test_lopsided_hands_on_a_both_hands_file(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(_minimal(
            "  - {name: riff_1, kind: seq, sequence: [1, 2, 3, 4, 1, 5]}\n",
            hands="both"))
        self.assertTrue(any("the hands are not balanced" in w
                            for w in plan.warnings), plan.warnings)

    def test_random_trials_that_do_not_divide_over_the_lanes(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(_minimal(
            "  - {name: b, kind: random, trials: 9}\n"
            "  - {name: a, kind: seq, sequence: [1, 2]}\n"))
        self.assertTrue(any("does not divide evenly across 4 lanes" in w
                            for w in plan.warnings), plan.warnings)

    def test_a_file_longer_than_the_session_cap(self) -> None:
        from finger_rehab.data.pattern_file import cap_warning, parse_plan
        plan = parse_plan(GOOD)
        self.assertIsNone(cap_warning(plan, 30))
        self.assertIn("the session cap is 1", cap_warning(plan, 1))


class EstimateTests(unittest.TestCase):
    def test_the_minute_estimate_adds_up(self) -> None:
        from finger_rehab.data import pattern_file as pf
        plan = pf.parse_plan(GOOD)
        # 52 trials, each its gap plus a nominal response; five block
        # lead-ins; four rests (the last block's is not played).
        gaps = sum(sum(b.expanded_gaps_s()) for b in plan.blocks)
        expect = (gaps + 52 * pf.NOMINAL_RESPONSE_S
                  + 5 * pf.BLOCK_LEAD_S
                  + sum(b.rest_after_s for b in plan.blocks[:-1]))
        self.assertAlmostEqual(plan.estimated_minutes(),
                               round(expect / 60.0, 2), places=2)


class ImportTests(unittest.TestCase):
    """Import is the only thing that writes. A rejected file must leave
    the disk exactly as it was, because the alternative is a study
    laptop with half a schedule on it."""

    def test_a_good_file_becomes_active_with_a_pointer_and_an_archive(
            self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "riffA.yaml"
            src.write_text(GOOD, encoding="utf-8")
            res = pf.import_file(src, cfg)
            self.assertTrue(res.ok, res.errors)
            active = pf.active_path(cfg)
            # Byte-for-byte, comments and all: the active copy is the
            # audit record of what ran, not a re-serialised version.
            self.assertEqual(active.read_text(encoding="utf-8"), GOOD)
            ptr = pf.pointer(cfg)
            self.assertEqual(ptr["file_name"], "riffA.yaml")
            self.assertEqual(ptr["sha256"], res.plan.sha256)
            self.assertEqual(ptr["source_path"], str(src))
            self.assertEqual(ptr["hands"], "one")
            self.assertIsNotNone(res.archived)
            self.assertTrue(res.archived.is_file())
            self.assertEqual(res.archived.parent.name, "history")
            self.assertTrue(res.archived.name.endswith("_riffA.yaml"))
            self.assertIn("Loaded Test riff", res.message())

    def test_a_bad_file_writes_nothing(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "broken.yaml"
            src.write_text("pattern_file: 1\nname: X\nhands: sideways\n"
                           "blocks: []\n", encoding="utf-8")
            res = pf.import_file(src, cfg)
            self.assertFalse(res.ok)
            self.assertFalse(pf.active_path(cfg).exists())
            self.assertFalse(pf.pointer_path(cfg).exists())
            self.assertFalse((root / "pattern_sequences").exists())
            self.assertTrue(res.message().startswith("broken.yaml not "
                                                     "loaded: "))

    def test_a_bad_file_does_not_replace_a_good_one(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            good = root / "good.yaml"
            good.write_text(GOOD, encoding="utf-8")
            pf.import_file(good, cfg)
            bad = root / "bad.yaml"
            bad.write_text("nope: 1\n", encoding="utf-8")
            self.assertFalse(pf.import_file(bad, cfg).ok)
            plan, reason = pf.load_active_plan(cfg)
            self.assertEqual(reason, "")
            self.assertEqual(plan.name, "Test riff")

    def test_a_file_that_is_not_utf8(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "bin.yaml"
            src.write_bytes(b"\xff\xfe\x00pattern_file: 1")
            res = pf.import_file(src, cfg)
            self.assertFalse(res.ok)
            self.assertIn("not UTF-8", res.errors[0])

    def test_a_huge_file_is_refused_before_it_is_parsed(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "big.yaml"
            src.write_bytes(b"# padding\n" * 40000)
            res = pf.import_file(src, cfg)
            self.assertFalse(res.ok)
            self.assertIn("the limit is 256 KB", res.errors[0])


class PersistenceTests(unittest.TestCase):
    """The requirement in Basil's words: once loaded it applies to every
    future session until it is changed, and the software remembers it
    indefinitely. That means re-reading from disk, not caching."""

    def test_the_plan_survives_a_fresh_config_object(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "riffA.yaml"
            src.write_text(GOOD, encoding="utf-8")
            pf.import_file(src, _Cfg(root))
            # Everything the first config knew is gone; only the files
            # remain, which is what an app restart looks like.
            plan, reason = pf.load_active_plan(_Cfg(root))
            self.assertEqual(reason, "")
            self.assertEqual(plan.name, "Test riff")
            self.assertEqual(plan.file_name, "riffA.yaml")
            self.assertEqual(plan.source_path, str(src))
            self.assertTrue(plan.imported_at)

    def test_no_file_means_no_plan_and_a_reason(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            plan, reason = pf.load_active_plan(_Cfg(Path(td)))
            self.assertIsNone(plan)
            self.assertEqual(reason, "no sequence file loaded")

    def test_an_edited_active_file_is_read_again_not_cached(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "riffA.yaml"
            src.write_text(GOOD, encoding="utf-8")
            pf.import_file(src, cfg)
            pf.active_path(cfg).write_text(
                GOOD.replace("name: Test riff", "name: Edited riff"),
                encoding="utf-8")
            plan, _ = pf.load_active_plan(cfg)
            self.assertEqual(plan.name, "Edited riff")

    def test_a_corrupted_active_file_reports_instead_of_raising(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "riffA.yaml"
            src.write_text(GOOD, encoding="utf-8")
            pf.import_file(src, cfg)
            pf.active_path(cfg).write_text("pattern_file: 1\nblocks: [\n",
                                           encoding="utf-8")
            plan, reason = pf.load_active_plan(cfg)
            self.assertIsNone(plan)
            self.assertIn("pattern_sequence.yaml is not valid", reason)

    def test_clear_puts_the_builtin_riff_back_and_keeps_the_archive(
            self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            src = root / "riffA.yaml"
            src.write_text(GOOD, encoding="utf-8")
            archived = pf.import_file(src, cfg).archived
            pf.clear_active(cfg)
            self.assertFalse(pf.active_path(cfg).exists())
            self.assertFalse(pf.pointer_path(cfg).exists())
            self.assertTrue(archived.is_file())
            self.assertEqual(pf.load_active_plan(cfg)[0], None)
            # Clearing twice is not an error: the researcher should be
            # able to press it without checking first.
            pf.clear_active(cfg)


class DropFolderTests(unittest.TestCase):
    """The no-click route: save the file into the folder and the next
    menu screen picks it up."""

    def test_current_yaml_is_imported_once_then_left_alone(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            self.assertIsNone(pf.sync_drop_folder(cfg))
            # Never creates the folder: a machine that has never used a
            # sequence file stays exactly as it was.
            self.assertFalse((root / "pattern_sequences").exists())
            drop = pf.drop_dir(cfg)
            drop.mkdir(parents=True)
            (drop / pf.DROP_NAME).write_text(GOOD, encoding="utf-8")
            res = pf.sync_drop_folder(cfg)
            self.assertIsNotNone(res)
            self.assertTrue(res.ok)
            self.assertIsNone(pf.sync_drop_folder(cfg))

    def test_editing_current_yaml_reimports_it(self) -> None:
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = _Cfg(root)
            drop = pf.drop_dir(cfg)
            drop.mkdir(parents=True)
            (drop / pf.DROP_NAME).write_text(GOOD, encoding="utf-8")
            first = pf.sync_drop_folder(cfg)
            (drop / pf.DROP_NAME).write_text(
                GOOD.replace("name: Test riff", "name: Second riff"),
                encoding="utf-8")
            second = pf.sync_drop_folder(cfg)
            self.assertIsNotNone(second)
            self.assertEqual(second.plan.name, "Second riff")
            self.assertNotEqual(first.plan.schedule_id,
                                second.plan.schedule_id)
            hist = sorted((drop / "history").iterdir())
            self.assertEqual(len(hist), 2)


class HandMatchTests(unittest.TestCase):
    def test_a_both_hands_file_refuses_a_one_hand_session(self) -> None:
        from finger_rehab.data import pattern_file as pf
        plan = pf.parse_plan(pf.TEMPLATE_BOTH_HANDS)
        self.assertIn("needs both hands", pf.hand_mismatch(plan, "right"))
        self.assertIsNone(pf.hand_mismatch(plan, "both"))

    def test_a_one_hand_file_refuses_a_bimanual_session(self) -> None:
        from finger_rehab.data import pattern_file as pf
        plan = pf.parse_plan(pf.TEMPLATE_ONE_HAND)
        self.assertIn("is for one hand", pf.hand_mismatch(plan, "both"))
        for hand in ("left", "right"):
            self.assertIsNone(pf.hand_mismatch(plan, hand))

    def test_no_plan_never_refuses_anything(self) -> None:
        from finger_rehab.data.pattern_file import hand_mismatch
        for hand in ("left", "right", "both"):
            self.assertIsNone(hand_mismatch(None, hand))


class SummaryTests(unittest.TestCase):
    """block_stats writes plan.summary() into metadata.json. That dict
    IS the schedule the notebook reads instead of assuming the built-in
    layout, so its shape is a contract."""

    def test_the_summary_carries_the_schedule_in_1_based_lanes(self) -> None:
        from finger_rehab.data.pattern_file import parse_plan
        plan = parse_plan(GOOD, file_name="riffA.yaml")
        s = plan.summary()
        self.assertEqual(s["schema"], 1)
        self.assertEqual(s["hands"], "one")
        self.assertEqual(s["n_lanes"], 4)
        self.assertEqual(s["cycle_len"], 4)
        self.assertEqual(s["total_trials"], 52)
        self.assertEqual(s["timeout_ms"], 2000)
        self.assertEqual(s["default_gap_ms"], 500)
        self.assertEqual(s["schedule_id"], plan.sha256[:12])
        self.assertEqual([b["label"] for b in s["blocks"]],
                         ["W", "1", "2", "3", "4"])
        riff = s["blocks"][2]
        self.assertEqual(riff["name"], "riff_1")
        self.assertEqual(riff["sequence"], [2, 4, 1, 3])
        self.assertEqual(riff["gaps_ms"], [400, 400, 800, 1200])
        self.assertEqual(riff["repeats"], 3)
        self.assertEqual(riff["trials"], 12)
        # Has to survive metadata.json, which is plain JSON.
        json.dumps(s)


if __name__ == "__main__":
    unittest.main()


class WritablePathTests(unittest.TestCase):
    """The three sequence-file paths must resolve to the writable root,
    not into the bundle. A frozen exe cannot write inside _MEIPASS, so
    a path missed off config.resolve_path's whitelist means the picker
    works from source and silently fails on the lab laptop."""

    def test_the_three_paths_route_to_the_user_root(self) -> None:
        import finger_rehab.config as fconfig
        from finger_rehab.data import pattern_file as pf
        cfg = fconfig.Config.load()
        for value in (pf.DEFAULT_ACTIVE, pf.DEFAULT_POINTER, pf.DEFAULT_DROP):
            got = cfg.resolve_path(value)
            self.assertEqual(got, (fconfig.USER_ROOT / value).resolve(),
                             value)

    def test_the_defaults_in_the_config_match_the_module(self) -> None:
        from finger_rehab.config import Config
        from finger_rehab.data import pattern_file as pf
        cfg = Config.load()
        self.assertEqual(cfg.get(pf.ACTIVE_KEY), pf.DEFAULT_ACTIVE)
        self.assertEqual(cfg.get(pf.POINTER_KEY), pf.DEFAULT_POINTER)
        self.assertEqual(cfg.get(pf.DROP_KEY), pf.DEFAULT_DROP)
        self.assertTrue(cfg.get(pf.ENABLED_KEY))
