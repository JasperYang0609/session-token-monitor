#!/usr/bin/env python3
"""Deterministic installer for session-token-monitor.

The installer intentionally keeps all installation decisions in code so a
small model (or a human following one command) does not need to copy files or
edit AGENTS.md manually.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parent
SOURCE_SKILL = ROOT / "skills" / "session-token-monitor"
HOOK_SCRIPT = SOURCE_SKILL / "scripts" / "install_agent_hook.py"
REQUIRED_FILES = (
    "SKILL.md",
    "scripts/install_agent_hook.py",
    "scripts/session_footer.py",
)
IGNORED_NAMES = {".DS_Store", "__pycache__"}


class InstallError(RuntimeError):
    """An expected installation failure with a user-actionable message."""


@dataclass(frozen=True)
class InstallResult:
    workspace: Path
    skill_dir: Path
    hook_file: Path
    changed: bool
    backup_dir: Optional[Path]


def load_hook_module():
    spec = importlib.util.spec_from_file_location("session_token_monitor_hook", HOOK_SCRIPT)
    if spec is None or spec.loader is None:
        raise InstallError(f"cannot load hook installer: {HOOK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def should_ignore(path: Path) -> bool:
    return any(part in IGNORED_NAMES for part in path.parts) or path.suffix == ".pyc"


def tree_manifest(root: Path) -> Dict[str, str]:
    if not root.is_dir():
        raise InstallError(f"skill directory missing: {root}")
    manifest: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if should_ignore(relative):
            continue
        if path.is_symlink():
            raise InstallError(f"symbolic links are not allowed in the skill package: {relative}")
        if path.is_file():
            manifest[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def validate_skill(root: Path) -> Dict[str, str]:
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            raise InstallError(f"required skill file missing: {relative}")

    skill_text = (root / "SKILL.md").read_text(encoding="utf-8")
    if not skill_text.startswith("---\n") or "name: session-token-monitor" not in skill_text:
        raise InstallError("SKILL.md frontmatter is invalid")

    for relative in ("scripts/install_agent_hook.py", "scripts/session_footer.py"):
        path = root / relative
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            raise InstallError(f"Python syntax check failed for {relative}: {exc.msg}") from exc
    return tree_manifest(root)


def resolve_workspace(explicit: Optional[str]) -> Path:
    if explicit:
        workspace = Path(explicit).expanduser().resolve()
    elif os.environ.get("OPENCLAW_WORKSPACE"):
        workspace = Path(os.environ["OPENCLAW_WORKSPACE"]).expanduser().resolve()
    else:
        cwd = Path.cwd().resolve()
        default = Path.home() / ".openclaw" / "workspace"
        if (cwd / "AGENTS.md").is_file() and cwd != ROOT:
            workspace = cwd
        elif default.is_dir():
            workspace = default.resolve()
        else:
            raise InstallError(
                "OpenClaw workspace was not found. Re-run with "
                "--workspace /path/to/openclaw-workspace"
            )

    if not workspace.is_dir():
        raise InstallError(f"workspace does not exist: {workspace}")
    return workspace


def validate_hook_shape(path: Path, hook) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise InstallError(f"refusing to edit a symbolic-link instruction file: {path}")
    text = path.read_text(encoding="utf-8")
    starts = text.count(hook.START)
    ends = text.count(hook.END)
    reversed_markers = starts == 1 and ends == 1 and text.find(hook.END) < text.find(hook.START)
    if starts != ends or starts > 1 or reversed_markers:
        raise InstallError(
            "AGENTS.md contains malformed or duplicate session-token-monitor markers; "
            "no files were changed"
        )


def copy_skill(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
    )


def check_install(workspace: Path) -> None:
    hook = load_hook_module()
    source_manifest = validate_skill(SOURCE_SKILL)
    target = workspace / "skills" / "session-token-monitor"
    installed_manifest = validate_skill(target)
    if installed_manifest != source_manifest:
        raise InstallError("installed skill does not match this package version")
    if hook.check_hook(workspace / "AGENTS.md") != 0:
        raise InstallError("agent hook verification failed")


def install(workspace: Path) -> InstallResult:
    hook = load_hook_module()
    source_manifest = validate_skill(SOURCE_SKILL)
    target = workspace / "skills" / "session-token-monitor"
    agent_file = workspace / "AGENTS.md"
    validate_hook_shape(agent_file, hook)

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        raise InstallError(f"refusing to replace a symbolic-link skill directory: {target}")

    target_manifest = tree_manifest(target) if target.exists() else None
    skill_changed = target_manifest != source_manifest
    agent_existed = agent_file.exists()
    agent_before = agent_file.read_bytes() if agent_existed else None
    backup: Optional[Path] = None
    installed_new_target = False

    with tempfile.TemporaryDirectory(prefix=".session-token-monitor-install-", dir=workspace) as temp_dir:
        staged = Path(temp_dir) / "session-token-monitor"
        staged_agent = Path(temp_dir) / "AGENTS.md"
        copy_skill(SOURCE_SKILL, staged)
        if validate_skill(staged) != source_manifest:
            raise InstallError("staged skill verification failed")
        if agent_existed:
            shutil.copy2(agent_file, staged_agent)
        else:
            staged_agent.write_text("", encoding="utf-8")
        hook.install_hook(staged_agent)
        if hook.check_hook(staged_agent) != 0:
            raise InstallError("staged agent hook verification failed")
        staged_agent_bytes = staged_agent.read_bytes()
        hook_changed = staged_agent_bytes != agent_before

        try:
            if skill_changed:
                if target.exists():
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    backup = target.parent / f".session-token-monitor.backup-{stamp}"
                    counter = 1
                    while backup.exists():
                        backup = target.parent / f".session-token-monitor.backup-{stamp}-{counter}"
                        counter += 1
                    target.replace(backup)
                staged.replace(target)
                installed_new_target = True

            if hook_changed:
                staged_agent.replace(agent_file)
            check_install(workspace)
        except Exception:
            if agent_existed and agent_before is not None:
                agent_file.write_bytes(agent_before)
            elif agent_file.exists():
                agent_file.unlink()

            if installed_new_target and target.exists():
                shutil.rmtree(target)
            if backup is not None and backup.exists():
                backup.replace(target)
                backup = None
            raise

    return InstallResult(
        workspace=workspace,
        skill_dir=target,
        hook_file=agent_file,
        changed=skill_changed or hook_changed,
        backup_dir=backup,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install and verify session-token-monitor with one deterministic command."
    )
    parser.add_argument(
        "--workspace",
        help="OpenClaw workspace. Defaults to OPENCLAW_WORKSPACE, the current workspace, or ~/.openclaw/workspace.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the installed skill and hook without changing files.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        workspace = resolve_workspace(args.workspace)
        if args.check:
            check_install(workspace)
            print("CHECK_OK")
            print(f"workspace={workspace}")
            return 0

        result = install(workspace)
        print("INSTALL_OK")
        print("VERIFY_OK")
        print(f"workspace={result.workspace}")
        print(f"skill={result.skill_dir}")
        print(f"hook={result.hook_file}")
        print(f"changed={'yes' if result.changed else 'no'}")
        if result.backup_dir is not None:
            print(f"previous_install_backup={result.backup_dir}")
        print("next=start a new OpenClaw session or reload OpenClaw")
        return 0
    except Exception as exc:
        print(f"INSTALL_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
