#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
FOOTER_PATH = ROOT / "skills/session-token-monitor/scripts/session_footer.py"
HOOK_PATH = ROOT / "skills/session-token-monitor/scripts/install_agent_hook.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


footer = load_module("session_footer", FOOTER_PATH)
hook = load_module("install_agent_hook", HOOK_PATH)


def args_for(tmp: Path, **overrides):
    values = {
        "status_text": None,
        "status_file": None,
        "context_tokens": None,
        "context_limit": None,
        "token_source": None,
        "model": None,
        "runtime": None,
        "no_history": False,
        "history_json": str(tmp / "history.json"),
        "drop_min_previous": 20_000,
        "drop_ratio": 0.5,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class SessionSelectionTests(unittest.TestCase):
    def test_exact_selector_and_fail_closed_default(self):
        data = {
            "session:a": {"sessionFile": "/tmp/a", "updatedAt": 1},
            "session:b": {"sessionFile": "/tmp/b", "updatedAt": 2},
        }
        key, entry = footer.find_session_entry(data, "session:a", None, None, False)
        self.assertEqual(key, "session:a")
        self.assertEqual(entry["sessionFile"], "/tmp/a")
        with self.assertRaisesRegex(ValueError, "refusing to guess"):
            footer.find_session_entry(data, None, None, None, False)

    def test_channel_selector_prefers_latest_match(self):
        data = {
            "old": {"lastTo": "channel:123", "updatedAt": 1},
            "new": {"lastTo": "channel:123", "updatedAt": 2},
        }
        key, _ = footer.find_session_entry(data, None, None, "123", False)
        self.assertEqual(key, "new")


class RuntimeSourceTests(unittest.TestCase):
    def test_parses_runtime_status_units(self):
        parsed = footer.parse_status_text(
            "🧠 Model: openai/gpt-test · oauth\n"
            "📚 Context: 123.4K/1M (12%) · 🧹 Compactions: 2\n"
            "⚙️ Execution: direct · Runtime: OpenClaw Default · Think: high"
        )
        self.assertEqual(parsed["contextTokens"], 123_400)
        self.assertEqual(parsed["contextLimit"], 1_000_000)
        self.assertEqual(parsed["compactions"], 2)
        self.assertEqual(parsed["model"], "openai/gpt-test")
        self.assertEqual(parsed["runtime"], "OpenClaw Default")

    def test_runtime_status_wins_over_conflicting_cli_values(self):
        with tempfile.TemporaryDirectory() as directory:
            args = args_for(
                Path(directory),
                status_text="📚 Context: 120K/272K",
                context_tokens="10",
                context_limit="100",
            )
            tokens, limit, source, meta = footer.resolve_context_tokens(args, {})
        self.assertEqual((tokens, limit, source), (120_000, 272_000, "runtime-status"))
        self.assertEqual(meta["cliContextConflict"], 10)
        self.assertEqual(meta["cliLimitConflict"], 100)

    def test_only_exact_source_labels_are_trusted(self):
        self.assertTrue(footer.is_trusted_token_source("runtime-status"))
        self.assertTrue(footer.is_trusted_token_source("cli"))
        self.assertFalse(footer.is_trusted_token_source("vendor-runtime-status"))
        self.assertFalse(footer.is_trusted_token_source("not-runtime-status"))
        self.assertFalse(footer.is_trusted_token_source("runtime-status-extended"))
        self.assertFalse(footer.is_trusted_token_source("runtime-status-evil"))

    def test_alert_threshold_boundaries_are_explicit(self):
        self.assertIsNone(footer.context_alert(100_000))
        self.assertIn("100K", footer.context_alert(100_001))
        self.assertIn("130K", footer.context_alert(130_000))
        self.assertIn("130K", footer.context_alert(130_001))
        self.assertIn("150K", footer.context_alert(150_000))
        self.assertIn("建議重置", footer.context_alert(150_001))
        self.assertIn("建議重置", footer.context_alert(200_000))
        self.assertIn("reset", footer.context_alert(200_001))

    def test_negative_token_number_fails_closed(self):
        self.assertIsNone(footer.parse_token_number("-5", "K"))

    def test_sessions_total_tokens_is_never_current_context(self):
        with tempfile.TemporaryDirectory() as directory:
            args = args_for(Path(directory))
            tokens, limit, source, _ = footer.resolve_context_tokens(
                args,
                {"totalTokens": 999_999, "contextTokens": 272_000},
            )
        self.assertIsNone(tokens)
        self.assertEqual(limit, 272_000)
        self.assertEqual(source, "session-index-limit-only")


class TrustedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp_context = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_context.name)
        self.args = args_for(self.tmp)
        self.session_key = "agent:main:discord:channel:synthetic"
        self.previous = {
            "time": 1,
            "sessionKey": self.session_key,
            "contextTokens": 120_000,
            "contextLimit": 272_000,
            "tokenSource": "runtime-status",
            "model": "model-a",
            "runtime": "test",
            "compactions": 0,
            "trusted": True,
            "historyUpdated": True,
        }
        footer.save_history(self.args.history_json, {self.session_key: self.previous})

    def tearDown(self):
        self.tmp_context.cleanup()

    def load_saved(self):
        return json.loads(Path(self.args.history_json).read_text(encoding="utf-8"))[self.session_key]

    def test_unknown_sample_does_not_overwrite_last_good(self):
        warnings, previous, current = footer.anomaly_warnings(
            self.session_key, None, 272_000, "unknown", {}, self.args
        )
        self.assertEqual(previous["contextTokens"], 120_000)
        self.assertFalse(current["trusted"])
        self.assertFalse(current["historyUpdated"])
        self.assertIn("unavailable", " ".join(warnings))
        self.assertEqual(self.load_saved(), self.previous)

    def test_suspicious_source_does_not_overwrite_last_good(self):
        warnings, _, current = footer.anomaly_warnings(
            self.session_key, 2_000, 272_000, "message-usage", {}, self.args
        )
        self.assertFalse(current["trusted"])
        self.assertIn("source suspicious", " ".join(warnings))
        self.assertEqual(self.load_saved(), self.previous)

    def test_unexplained_large_drop_warns_and_preserves_history(self):
        warnings, _, current = footer.anomaly_warnings(
            self.session_key,
            20_000,
            272_000,
            "runtime-status",
            {"model": "model-a", "compactions": 0},
            self.args,
        )
        self.assertFalse(current["trusted"])
        self.assertIn("suspicious drop", " ".join(warnings))
        self.assertEqual(self.load_saved(), self.previous)

    def test_compaction_explains_drop_and_updates_history(self):
        warnings, _, current = footer.anomaly_warnings(
            self.session_key,
            20_000,
            272_000,
            "runtime-status",
            {"model": "model-a", "compactions": 1},
            self.args,
        )
        self.assertTrue(current["trusted"])
        self.assertNotIn("suspicious drop", " ".join(warnings))
        self.assertEqual(self.load_saved()["contextTokens"], 20_000)

    def test_model_switch_explains_drop_and_limit_change(self):
        warnings, _, current = footer.anomaly_warnings(
            self.session_key,
            20_000,
            200_000,
            "runtime-status",
            {"model": "model-b", "compactions": 0},
            self.args,
        )
        self.assertTrue(current["trusted"])
        joined = " ".join(warnings)
        self.assertNotIn("suspicious drop", joined)
        self.assertIn("limit changed", joined)

    def test_history_replace_is_private_and_leaves_no_temporary_file(self):
        path = Path(self.args.history_json)
        mode = stat.S_IMODE(path.stat().st_mode)
        self.assertEqual(mode, 0o600)
        footer.save_history(self.args.history_json, {self.session_key: self.previous})
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(list(path.parent.glob(f".{path.name}.*")), [])

    def test_corrupt_history_fails_soft_then_recovers(self):
        path = Path(self.args.history_json)
        path.write_text("{broken", encoding="utf-8")
        warnings, previous, current = footer.anomaly_warnings(
            self.session_key,
            80_000,
            272_000,
            "runtime-status",
            {"model": "model-a", "compactions": 0},
            self.args,
        )
        self.assertIsNone(previous)
        self.assertEqual(warnings, [])
        self.assertTrue(current["trusted"])
        self.assertEqual(self.load_saved()["contextTokens"], 80_000)

    def test_audit_file_is_private(self):
        audit = self.tmp / "audit.jsonl"
        footer.append_audit(str(audit), {"sessionKey": self.session_key, "contextTokens": 1})
        self.assertEqual(stat.S_IMODE(audit.stat().st_mode), 0o600)
        self.assertEqual(json.loads(audit.read_text(encoding="utf-8"))["contextTokens"], 1)


class HookInstallerTests(unittest.TestCase):
    def test_add_update_and_check_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "AGENTS.md"
            path.write_text("# Existing\n", encoding="utf-8")
            self.assertEqual(hook.install_hook(path), "added")
            first = path.read_text(encoding="utf-8")
            self.assertEqual(hook.check_hook(path), 0)
            self.assertEqual(hook.install_hook(path), "updated")
            self.assertEqual(path.read_text(encoding="utf-8"), first)
            self.assertEqual(path.read_text(encoding="utf-8").count(hook.START), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
