#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts/build_skill_archive.py"

spec = importlib.util.spec_from_file_location("build_skill_archive", BUILDER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {BUILDER_PATH}")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SkillArchiveTests(unittest.TestCase):
    def test_packaged_artifact_matches_source(self):
        self.assertEqual(builder.archive_manifest(builder.OUTPUT), builder.expected_manifest())

    def test_build_is_logically_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.skill"
            second = Path(directory) / "second.skill"
            builder.build(first)
            builder.build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(builder.archive_manifest(first), builder.expected_manifest())

    def test_duplicate_member_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "duplicate.skill"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr("session-token-monitor/SKILL.md", b"first")
                    archive.writestr("session-token-monitor/SKILL.md", b"second")
            with self.assertRaisesRegex(ValueError, "duplicate archive member"):
                builder.archive_manifest(archive_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
