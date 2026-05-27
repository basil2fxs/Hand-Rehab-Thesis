"""Tests for Session metadata save. The atomic-write path is the
important contract: a crash mid-save must not destroy the prior file."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class SessionSaveTests(unittest.TestCase):

    def test_save_writes_valid_json_with_all_fields(self) -> None:
        from rehab.data.session import Session, SOFTWARE_VERSION
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            s = Session(participant="Basil", hand="right",
                         source_name="MultiSerial(right@COM3)",
                         notes="testing")
            s.save(path)
            payload = json.loads(path.read_text())
            self.assertEqual(payload["participant"], "Basil")
            self.assertEqual(payload["hand"], "right")
            self.assertEqual(payload["source_name"],
                              "MultiSerial(right@COM3)")
            self.assertEqual(payload["software_version"], SOFTWARE_VERSION)
            self.assertEqual(payload["notes"], "testing")

    def test_save_creates_parent_directory(self) -> None:
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "nested" / "deep" / "metadata.json"
            Session(participant="X").save(path)
            self.assertTrue(path.exists())

    def test_save_overwrites_existing_file(self) -> None:
        # Same file written twice should reflect the latest state - the
        # engine relies on this to update notes from "in progress" to
        # "completed".
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="A", notes="block in progress").save(path)
            Session(participant="A", notes="completed").save(path)
            payload = json.loads(path.read_text())
            self.assertEqual(payload["notes"], "completed")

    def test_save_leaves_no_tmp_file_behind(self) -> None:
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="A").save(path)
            tmps = list(Path(td).glob("*.tmp"))
            self.assertEqual(tmps, [])


class SessionAtomicityRegressionTests(unittest.TestCase):
    """If json.dumps or the tmp-file write raises, the prior metadata
    file must still be intact - that's the whole point of writing to a
    tmp file and atomically replacing."""

    def test_failed_save_preserves_prior_file(self) -> None:
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            # Lay down a good metadata first.
            Session(participant="A", notes="block in progress").save(path)
            prior = path.read_text()
            # Now force the next save to blow up during serialisation.
            with mock.patch("rehab.data.session.json.dumps",
                             side_effect=RuntimeError("disk forgot how to disk")):
                with self.assertRaises(RuntimeError):
                    Session(participant="A", notes="completed").save(path)
            # The original file must be untouched - that's the contract.
            self.assertEqual(path.read_text(), prior)

    def test_failed_replace_preserves_prior_file(self) -> None:
        # Even if os.replace raises (rare: permission flap, EBUSY on
        # Windows), the original file must still be intact.
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="A", notes="block in progress").save(path)
            prior = path.read_text()
            with mock.patch("rehab.data.session.os.replace",
                             side_effect=OSError("EBUSY")):
                with self.assertRaises(OSError):
                    Session(participant="A", notes="completed").save(path)
            self.assertEqual(path.read_text(), prior)


if __name__ == "__main__":
    unittest.main()
