#!/usr/bin/env python3
"""Install or update the session-token-monitor agent hook."""

from __future__ import annotations

import argparse
from pathlib import Path

START = "<!-- session-token-monitor:start -->"
END = "<!-- session-token-monitor:end -->"
BLOCK = f"""{START}
Before every user-visible reply, use the `session-token-monitor` skill and append its token/transcript footer. Treat this as a required pre-send gate; if footer collection fails, report the short failure instead of guessing.
{END}
"""

def install_hook(path: Path) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    return action

def main() -> int:
    parser = argparse.ArgumentParser(description="Install the session-token-monitor hook into AGENTS.md or equivalent.")
    parser.add_argument("path", nargs="?", default="AGENTS.md", help="Target instruction file (default: AGENTS.md)")
    args = parser.parse_args()
    target = Path(args.path).expanduser()
    action = install_hook(target)
    print(f"session-token-monitor hook {action}: {target}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
