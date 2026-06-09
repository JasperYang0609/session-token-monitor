# session-token-monitor

OpenClaw skill for consistent context-token monitoring, transcript-size footers, and compaction/reset warnings.

## Install from source

Copy the skill folder into an OpenClaw workspace:

```bash
mkdir -p /path/to/openclaw-workspace/skills
cp -R skills/session-token-monitor /path/to/openclaw-workspace/skills/
```

Then install the minimal agent hook so every reply remembers to show the footer:

```bash
cd /path/to/openclaw-workspace
python3 skills/session-token-monitor/scripts/install_agent_hook.py AGENTS.md
```

Then start a new session or restart/reload OpenClaw so the skill catalog refreshes.

## Install from packaged skill

The packaged artifact is:

```text
dist/session-token-monitor.skill
```

A `.skill` file is a zip archive. If your OpenClaw setup does not provide a direct local `.skill` installer, unzip it and place the contained `session-token-monitor/` folder under your workspace `skills/` directory. Then run the hook installer above.

## What it does

- Adds mandatory reply footer rules: transcript size + current context token pressure
- Warns at 100K / 130K / 150K / 200K token thresholds
- Provides a dependency-free helper script: `scripts/session_footer.py` that requires an exact session selector by default and avoids single-call token totals
- Provides an idempotent hook installer: `scripts/install_agent_hook.py`
- Avoids storing or printing API keys, tokens, cookies, or recovery codes

## Agent hook

The installer adds this marker block to `AGENTS.md` or another always-loaded instruction file:

```md
<!-- session-token-monitor:start -->
Before every user-visible reply, use the `session-token-monitor` skill and append its token/transcript footer. Treat this as a required pre-send gate; if footer collection fails, report the short failure instead of guessing.
<!-- session-token-monitor:end -->
```

The full monitoring logic remains in the skill. The hook is intentionally thin so updates stay centralized.

## Publish safety

Before publishing, scan for secrets. This repository should not contain API keys, OAuth tokens, cookies, recovery codes, `.env`, local config, transcripts, or customer memory files.

## Maintainer use of Codex

This project is maintained as part of the OpenClaw ecosystem. We plan to use Codex to review pull requests, improve compatibility with OpenClaw session/runtime changes, expand safety checks for transcript and token footers, and keep installation documentation current.

API-assisted maintenance should focus on issue triage, regression tests, documentation updates, and release notes. Codex should not be used to collect, store, or reveal private transcripts, API keys, OAuth tokens, cookies, or recovery codes.

## Token source rules

Use runtime/session status `📚 Context: <used>/<limit>` as the source of truth for context pressure. Do not display message API `usage.totalTokens` or ambiguous session-index `totalTokens` as the current session size; those can represent a single model call.

For automation, pass parsed runtime values into the helper:

```bash
python3 skills/session-token-monitor/scripts/session_footer.py \
  --session-key 'agent:main:discord:channel:123' \
  --context-tokens 101000 \
  --context-limit 272000
```

Without `--session-key`, `--channel-id`, or `--to`, the helper fails closed unless `--allow-latest` is explicitly provided.
