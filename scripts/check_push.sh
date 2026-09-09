#!/bin/sh
set -eu
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"
python3 -m py_compile skills/session-token-monitor/scripts/*.py scripts/*.py tests/*.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 scripts/build_skill_archive.py --check
git diff --check
