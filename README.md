# session-token-monitor

OpenClaw skill for consistent session token monitoring, transcript-size footers, and compaction/reset warnings.

## Install from source

Copy the skill folder into an OpenClaw workspace:

```bash
mkdir -p skills
cp -R skills/session-token-monitor /path/to/openclaw-workspace/skills/
```

Then start a new session or restart/reload OpenClaw so the skill catalog refreshes.

## Install from packaged skill

The packaged artifact is:

```text
dist/session-token-monitor.skill
```

A `.skill` file is a zip archive. If your OpenClaw setup does not provide a direct local `.skill` installer, unzip it and place the contained `session-token-monitor/` folder under your workspace `skills/` directory.

## What it does

- Adds standard reply footer rules: transcript size + session token count
- Warns at 100K / 130K / 150K / 200K token thresholds
- Provides a dependency-free helper script: `scripts/session_footer.py`
- Avoids storing or printing API keys, tokens, cookies, or recovery codes

## Publish safety

Before publishing, scan for secrets. This repository should not contain API keys, OAuth tokens, cookies, recovery codes, `.env`, local config, transcripts, or customer memory files.
