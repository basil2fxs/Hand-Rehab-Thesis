"""Tests for the Config layer: dotted-path lookups, override merge,
and the path resolver that picks between bundled assets and writable
user-data directories."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


class DottedGetTests(unittest.TestCase):
    """Config.get walks a dotted path. Must handle missing keys, wrong
    intermediate types, and empty keys without crashing."""

    def _cfg(self, data):
        from rehab.config import Config
        return Config(data=data)

    def test_simple_key(self) -> None:
        cfg = self._cfg({"foo": 1})
        self.assertEqual(cfg.get("foo"), 1)

    def test_nested_key(self) -> None:
        cfg = self._cfg({"a": {"b": {"c": 42}}})
        self.assertEqual(cfg.get("a.b.c"), 42)

    def test_missing_key_returns_default(self) -> None:
        cfg = self._cfg({"a": 1})
        self.assertIsNone(cfg.get("missing"))
        self.assertEqual(cfg.get("missing", "fallback"), "fallback")

    def test_partial_path_returns_default(self) -> None:
        cfg = self._cfg({"a": {"b": 1}})
        # 'a.b.c' tries to descend into the int 1; should bail out.
        self.assertIsNone(cfg.get("a.b.c"))
        self.assertEqual(cfg.get("a.b.c", "nope"), "nope")

    def test_intermediate_string_returns_default(self) -> None:
        # If a path passes through a non-dict, we shouldn't .split('.')
        # the value or crash on attribute access.
        cfg = self._cfg({"a": "this is a string"})
        self.assertEqual(cfg.get("a.b", "fallback"), "fallback")

    def test_empty_key_string_returns_default(self) -> None:
        cfg = self._cfg({"a": 1})
        # Empty key splits to [''], which lookup misses.
        self.assertEqual(cfg.get("", "fallback"), "fallback")

    def test_get_returns_dict_when_path_ends_at_dict(self) -> None:
        cfg = self._cfg({"a": {"b": {"c": 1}}})
        got = cfg.get("a.b")
        self.assertEqual(got, {"c": 1})


class MergeBehaviourTests(unittest.TestCase):
    """_merge does a deep merge for dicts; non-dict values from the
    override replace the base. Lists are NOT concatenated."""

    def test_override_adds_new_keys(self) -> None:
        from rehab.config import _merge
        out = _merge({"a": 1}, {"b": 2})
        self.assertEqual(out, {"a": 1, "b": 2})

    def test_override_replaces_scalar(self) -> None:
        from rehab.config import _merge
        out = _merge({"a": 1}, {"a": 99})
        self.assertEqual(out, {"a": 99})

    def test_nested_dicts_merge_deeply(self) -> None:
        from rehab.config import _merge
        out = _merge({"a": {"b": 1, "c": 2}}, {"a": {"b": 99}})
        self.assertEqual(out, {"a": {"b": 99, "c": 2}})

    def test_lists_are_replaced_not_concatenated(self) -> None:
        # A therapist who overrides on_delta should get their list,
        # not their list appended to the default.
        from rehab.config import _merge
        out = _merge({"on_delta": [45, 90, 45, 45]},
                      {"on_delta": [60, 60]})
        self.assertEqual(out["on_delta"], [60, 60])

    def test_scalar_replaces_dict_in_override(self) -> None:
        # If the override has a scalar where the default had a dict,
        # the scalar wins. Unusual but defensible.
        from rehab.config import _merge
        out = _merge({"a": {"b": 1}}, {"a": 99})
        self.assertEqual(out, {"a": 99})

    def test_dict_replaces_scalar_in_override(self) -> None:
        from rehab.config import _merge
        out = _merge({"a": 1}, {"a": {"b": 2}})
        self.assertEqual(out, {"a": {"b": 2}})


class LoadOverrideTests(unittest.TestCase):
    """Config.load merges a YAML override file onto the defaults."""

    def test_override_merges_onto_default(self) -> None:
        from rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "user.yaml"
            path.write_text("game:\n  trigger_interval_s: 2.5\n")
            cfg = Config.load(path)
            # User's value won.
            self.assertEqual(cfg.get("game.trigger_interval_s"), 2.5)
            # Default's other game keys preserved.
            self.assertIsNotNone(cfg.get("game.mode"))
            self.assertEqual(cfg.source, path)

    def test_load_without_override_uses_defaults(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        self.assertIsNotNone(cfg.get("game.mode"))


class ResolvePathTests(unittest.TestCase):
    """resolve_path routes writable paths to USER_ROOT and read-only
    asset paths to PROJECT_ROOT. Absolute paths pass through."""

    def test_absolute_path_returns_unchanged(self) -> None:
        from rehab.config import Config
        cfg = Config()
        abs_path = Path("/tmp/foo.csv")
        self.assertEqual(cfg.resolve_path(abs_path), abs_path)

    def test_sessions_routes_to_user_root(self) -> None:
        from rehab.config import Config, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("sessions/foo.csv")
        self.assertTrue(str(got).startswith(str(USER_ROOT)))

    def test_logs_routes_to_user_root(self) -> None:
        from rehab.config import Config, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("logs/app.log")
        self.assertTrue(str(got).startswith(str(USER_ROOT)))

    def test_calibration_routes_to_user_root(self) -> None:
        from rehab.config import Config, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("config/calibration/user.json")
        self.assertTrue(str(got).startswith(str(USER_ROOT)))

    def test_assets_routes_to_project_root(self) -> None:
        from rehab.config import Config, PROJECT_ROOT
        cfg = Config()
        got = cfg.resolve_path("assets/music/song.mp3")
        self.assertTrue(str(got).startswith(str(PROJECT_ROOT)))


class SaveUserOverridesTests(unittest.TestCase):
    """Settings screen persists per-hand COM port assignments via
    Config.save_user_overrides. New file is created if absent;
    existing keys are preserved when only some are updated."""

    def test_save_creates_file_with_dotted_key(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock
        from rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            override = Path(td) / "user_settings.yaml"
            with mock.patch("rehab.config.USER_OVERRIDES", override):
                cfg = Config(data={"serial": {"left_port": None,
                                                 "right_port": None}})
                cfg.save_user_overrides({
                    "serial.left_port": "/dev/cu.A",
                    "serial.right_port": "/dev/cu.B",
                })
            self.assertTrue(override.exists())
            import yaml as _y
            payload = _y.safe_load(override.read_text())
            self.assertEqual(payload["serial"]["left_port"], "/dev/cu.A")
            self.assertEqual(payload["serial"]["right_port"], "/dev/cu.B")
            # In-memory state must also reflect the change.
            self.assertEqual(cfg.get("serial.left_port"), "/dev/cu.A")

    def test_save_preserves_existing_unrelated_keys(self) -> None:
        # Regression: a partial save must not blow away other user-set
        # keys (e.g. updating only right_port leaves left_port intact).
        import tempfile
        from pathlib import Path
        from unittest import mock
        from rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            override = Path(td) / "user_settings.yaml"
            override.write_text(
                "serial:\n"
                "  left_port: /dev/cu.OLD\n"
                "audio:\n"
                "  master_volume: 0.5\n"
            )
            with mock.patch("rehab.config.USER_OVERRIDES", override):
                cfg = Config(data={})
                cfg.save_user_overrides(
                    {"serial.right_port": "/dev/cu.NEW"})
            import yaml as _y
            payload = _y.safe_load(override.read_text())
            self.assertEqual(payload["serial"]["left_port"], "/dev/cu.OLD")
            self.assertEqual(payload["serial"]["right_port"], "/dev/cu.NEW")
            self.assertEqual(payload["audio"]["master_volume"], 0.5)

    def test_save_atomic_does_not_leak_tmp(self) -> None:
        import tempfile
        from pathlib import Path
        from unittest import mock
        from rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            override = Path(td) / "user_settings.yaml"
            with mock.patch("rehab.config.USER_OVERRIDES", override):
                Config(data={}).save_user_overrides(
                    {"serial.left_port": "/dev/cu.X"})
            tmps = list(Path(td).glob("*.tmp"))
            self.assertEqual(tmps, [])


class ResolvePathPrefixRegressionTests(unittest.TestCase):
    """Regression: resolve_path used str.startswith on the joined path,
    so directories like sessions_old or logs_archive accidentally
    matched the writable prefixes and routed to USER_ROOT. Only matters
    when USER_ROOT and PROJECT_ROOT differ (frozen PyInstaller build),
    but the routing should be correct everywhere."""

    def test_sessions_old_routes_to_project_root(self) -> None:
        from rehab.config import Config, PROJECT_ROOT, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("sessions_old/foo.csv")
        # When USER_ROOT == PROJECT_ROOT (source checkout) both starts
        # would match - we assert against a different root only when
        # they actually differ. In all cases the path part must be the
        # first segment of the relative path, not a string prefix.
        if USER_ROOT != PROJECT_ROOT:
            self.assertTrue(str(got).startswith(str(PROJECT_ROOT)))
            self.assertFalse(str(got).startswith(str(USER_ROOT)))
        # And the resolved name must contain the original folder.
        self.assertIn("sessions_old", got.parts)

    def test_logs_archive_routes_to_project_root(self) -> None:
        from rehab.config import Config, PROJECT_ROOT, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("logs_archive/old.log")
        if USER_ROOT != PROJECT_ROOT:
            self.assertTrue(str(got).startswith(str(PROJECT_ROOT)))
        self.assertIn("logs_archive", got.parts)

    def test_config_other_routes_to_project_root(self) -> None:
        # 'config/calibration' is writable but 'config/themes' must not
        # match - same string-prefix trap if someone gets sloppy.
        from rehab.config import Config, PROJECT_ROOT, USER_ROOT
        cfg = Config()
        got = cfg.resolve_path("config/themes/dark.yaml")
        if USER_ROOT != PROJECT_ROOT:
            self.assertTrue(str(got).startswith(str(PROJECT_ROOT)))
        self.assertIn("themes", got.parts)


if __name__ == "__main__":
    unittest.main()
