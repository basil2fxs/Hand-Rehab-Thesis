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


class TmpFileCleanupTests(unittest.TestCase):
    """If the atomic-write fails partway through, the partial tmp file
    must be removed before the exception propagates. Before the
    cleanup was added, a failed os.replace left metadata.json.tmp on
    disk forever, slowly littering the sessions/ folder over time."""

    def test_tmp_file_removed_when_replace_fails(self) -> None:
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="A").save(path)
            with mock.patch("rehab.data.session.os.replace",
                             side_effect=OSError("EBUSY")):
                with self.assertRaises(OSError):
                    Session(participant="A",
                             notes="retry").save(path)
            # The partial tmp file must NOT linger.
            tmps = list(Path(td).glob("*.tmp"))
            self.assertEqual(
                tmps, [],
                "metadata.json.tmp should be unlinked after a failed "
                "replace, otherwise the sessions/ folder accumulates "
                "orphan files",
            )

    def test_tmp_file_removed_when_write_fails(self) -> None:
        # Simulate a disk-full or quota error during the write itself
        # by mocking the file handle's write method to raise.
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            real_open = Path.open

            def _flaky_open(self, *args, **kwargs):
                fh = real_open(self, *args, **kwargs)
                original_write = fh.write

                def _flaky_write(data):
                    original_write(data[:10])
                    raise OSError("ENOSPC")
                fh.write = _flaky_write
                return fh
            with mock.patch.object(Path, "open", _flaky_open):
                with self.assertRaises(OSError):
                    Session(participant="A").save(path)
            tmps = list(Path(td).glob("*.tmp"))
            self.assertEqual(
                tmps, [],
                "tmp file should be cleaned up after a partial write")


class UnicodeRoundtripTests(unittest.TestCase):
    """Participant names containing non-ASCII characters must survive
    a save / re-read cycle without escape-sequence damage. Before
    ensure_ascii=False was added, 'Müller' was written as
    'M\\u00fcload' which is valid JSON but unreadable to a researcher
    eyeballing the file."""

    def test_unicode_name_written_as_raw_characters(self) -> None:
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="Müller").save(path)
            text = path.read_text(encoding="utf-8")
            # Raw ü appears in the file, not the escaped form.
            self.assertIn("Müller", text)
            self.assertNotIn("M\\u00fc", text)

    def test_unicode_name_roundtrips_through_json(self) -> None:
        # JSON.load should give us back the original string regardless
        # of the file encoding details.
        from rehab.data.session import Session
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "metadata.json"
            Session(participant="张伟").save(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["participant"], "张伟")


if __name__ == "__main__":
    unittest.main()
