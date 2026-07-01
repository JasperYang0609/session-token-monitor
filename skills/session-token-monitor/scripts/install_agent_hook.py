#!/usr/bin/env python3
"""Install, update, or verify the session-token-monitor agent hook."""

from __future__ import annotations

import argparse
from pathlib import Path

START = "<!-- session-token-monitor:start -->"
END = "<!-- session-token-monitor:end -->"
BLOCK = f"""{START}
Before every user-visible reply, use the `session-token-monitor` skill and append its token/transcript footer. Treat this as a required pre-send gate: fetch fresh runtime/session status every time, pass the current `📚 Context: used/limit` into the footer helper, never reuse prior token/limit values, and never use per-call `usage.totalTokens` or `sessions.json.totalTokens` as current context pressure. If footer collection fails, report the short failure instead of guessing.
{END}
"""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def install_hook(path: Path, dry_run: bool = False) -> str:
    text = read_text(path)
    start_idx = text.find(START)
    end_idx = text.find(END)

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        end_idx += len(END)
        new_text = text[:start_idx].rstrip() + "\n\n" + BLOCK + text[end_idx:].lstrip("\n")
        action = "updated"
    else:
        prefix = text.rstrip()
        new_text = (prefix + "\n\n" if prefix else "") + BLOCK
        action = "added"

    if not new_text.endswith("\n"):
        new_text += "\n"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
    return action


def check_hook(path: Path) -> int:
    text = read_text(path)
    start_idx = text.find(START)
    end_idx = text.find(END)
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        print(f"session-token-monitor hook missing: {path}")
        return 1
    block = text[start_idx : end_idx + len(END)]
    if block != BLOCK.rstrip("\n"):
        print(f"session-token-monitor hook present but stale: {path}")
        return 2
    print(f"session-token-monitor hook ok: {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or verify the session-token-monitor hook in AGENTS.md or equivalent.")
    parser.add_argument("path", nargs="?", default="AGENTS.md", help="Target instruction file (default: AGENTS.md)")
    parser.add_argument("--check", action="store_true", help="Verify marker block exists and is current; do not write")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen; do not write")
    parser.add_argument("--print-block", action="store_true", help="Print the marker block")
    args = parser.parse_args()

    if args.print_block:
        print(BLOCK, end="")
        return 0

    target = Path(args.path).expanduser()
    if args.check:
        return check_hook(target)

    action = install_hook(target, dry_run=args.dry_run)
    suffix = " (dry run; no file changed)" if args.dry_run else ""
    print(f"session-token-monitor hook {action}: {target}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
