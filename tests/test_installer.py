#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_PATH = ROOT / "install.py"


def load_installer():
    spec = importlib.util.spec_from_file_location("session_token_monitor_installer", INSTALLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {INSTALLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


installer = load_installer()


class DeterministicInstallerTests(unittest.TestCase):
    def make_workspace(self, root: Path, agents_text: str = "# Existing rules\n") -> Path:
        workspace = root / "workspace"
        workspace.mkdir()
        (workspace / "AGENTS.md").write_text(agents_text, encoding="utf-8")
        return workspace

    def test_fresh_install_preserves_existing_rules_and_verifies(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(Path(directory))
            result = installer.install(workspace)
            installer.check_install(workspace)

            agents = (workspace / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(result.changed)
            self.assertIn("# Existing rules", agents)
            self.assertEqual(agents.count("session-token-monitor:start"), 1)
            self.assertTrue((result.skill_dir / "SKILL.md").is_file())

    def test_repeated_install_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(Path(directory))
            first = installer.install(workspace)
            first_agents = (workspace / "AGENTS.md").read_bytes()
            second = installer.install(workspace)

            self.assertTrue(first.changed)
            self.assertFalse(second.changed)
            self.assertIsNone(second.backup_dir)
            self.assertEqual((workspace / "AGENTS.md").read_bytes(), first_agents)

    def test_update_keeps_previous_install_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(Path(directory))
            old_skill = workspace / "skills" / "session-token-monitor"
            old_skill.mkdir(parents=True)
            (old_skill / "local-note.txt").write_text("keep me", encoding="utf-8")

            result = installer.install(workspace)

            self.assertIsNotNone(result.backup_dir)
            assert result.backup_dir is not None
            self.assertEqual(
                (result.backup_dir / "local-note.txt").read_text(encoding="utf-8"),
                "keep me",
            )
            installer.check_install(workspace)

    def test_malformed_hook_fails_before_changing_skill(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(
                Path(directory),
                "# Existing\n<!-- session-token-monitor:start -->\nbroken\n",
            )
            old_skill = workspace / "skills" / "session-token-monitor"
            old_skill.mkdir(parents=True)
            marker = old_skill / "untouched.txt"
            marker.write_text("original", encoding="utf-8")

            with self.assertRaisesRegex(installer.InstallError, "malformed"):
                installer.install(workspace)

            self.assertEqual(marker.read_text(encoding="utf-8"), "original")
            self.assertFalse((old_skill / "SKILL.md").exists())

    def test_reversed_hook_markers_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(
                Path(directory),
                "<!-- session-token-monitor:end -->\n"
                "broken\n"
                "<!-- session-token-monitor:start -->\n",
            )

            with self.assertRaisesRegex(installer.InstallError, "malformed"):
                installer.install(workspace)

            self.assertFalse((workspace / "skills" / "session-token-monitor").exists())

    def test_verification_failure_restores_skill_and_agent_file(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = self.make_workspace(Path(directory))
            old_agents = (workspace / "AGENTS.md").read_bytes()
            old_skill = workspace / "skills" / "session-token-monitor"
            old_skill.mkdir(parents=True)
            marker = old_skill / "old-version.txt"
            marker.write_text("original", encoding="utf-8")

            with mock.patch.object(
                installer,
                "check_install",
                side_effect=installer.InstallError("forced verification failure"),
            ):
                with self.assertRaisesRegex(installer.InstallError, "forced verification"):
                    installer.install(workspace)

            self.assertEqual((workspace / "AGENTS.md").read_bytes(), old_agents)
            self.assertEqual(marker.read_text(encoding="utf-8"), "original")
            self.assertEqual(
                list((workspace / "skills").glob(".session-token-monitor.backup-*")),
                [],
            )

    def test_missing_workspace_fails_with_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            with self.assertRaisesRegex(installer.InstallError, "does not exist"):
                installer.resolve_workspace(str(missing))


if __name__ == "__main__":
    unittest.main(verbosity=2)
