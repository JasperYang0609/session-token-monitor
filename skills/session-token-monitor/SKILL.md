---
name: session-token-monitor
description: Mandatory OpenClaw reply-footer workflow for every user-visible response: monitor conversation token pressure and transcript size, append consistent token/transcript footers, warn before context compaction/reset risk, and report short-term/weekly usage when asked about session, token, context, compaction, reset, transcript size, usage quota, or LLM conversation health.
---

# Session Token Monitor

## Purpose

Use this skill to keep OpenClaw conversations healthy as they grow. It standardizes session token footers, transcript-size classification, warning thresholds before compaction/reset risk, and concise status answers.

This skill is intentionally simple and model-agnostic: any LLM can follow it.

## Mandatory Reply Footer

For every user-visible reply, collect session status and append a footer. Treat this as a pre-send gate, not an optional status command.

Preferred sources, in order:

1. Use the runtime/session status tool for current context pressure (`📚 Context: <used>/<limit>`).
2. Run `scripts/session_footer.py` from this skill for transcript size, passing an exact `--session-key`, `--channel-id`, or `--to`.
3. If neither works, state that the footer is unavailable; do not guess.

Footer format:

```text
📝 Transcript: <size> MB｜<level>
📊 Context: <used> / <limit>
```

If an alert applies, place it directly above the footer.

Do **not** use per-call API usage fields, message `usage.totalTokens`, or ambiguous `sessions.json.totalTokens` as the context/session token count. Those fields may represent one model call rather than the current conversation context. If the runtime status is unavailable, show `📊 Context: unknown / <limit>` or `unknown tokens` instead of guessing.

## Install-Time Agent Hook

OpenClaw skills teach the model what to do, but a skill alone is not a global middleware. For reliable every-reply behavior, installation should add this minimal hook to the target agent instructions (`AGENTS.md`, equivalent agent profile, or another always-loaded instruction file):

```md
<!-- session-token-monitor:start -->
Before every user-visible reply, use the `session-token-monitor` skill and append its token/transcript footer. Treat this as a required pre-send gate; if footer collection fails, report the short failure instead of guessing.
<!-- session-token-monitor:end -->
```

Use the bundled helper to add or update the marker block safely:

```bash
python3 skills/session-token-monitor/scripts/install_agent_hook.py AGENTS.md
```

The helper is idempotent: re-running it replaces only the marker block above. For uninstall, remove the marker block and the skill folder.

## Transcript Size Levels

- `< 1 MB` → `輕微`
- `1–3 MB` → `中度`
- `3–6 MB` → `擁擠`
- `> 6 MB` → `極限`

## Token Warning Thresholds

Use the current runtime context token count when available, not a single-call usage total.

- `>100K` → `⚡ 本對話已累積 <XXK> tokens，接近壓縮門檻。`
- `>130K` → `⚡ 本對話已累積 <XXK> tokens，接近壓縮門檻。`
- `>150K` → `⚠️ 本頻道 session 已達 <XXK>，建議重置`
- `>200K` → `🔴 強烈建議先總結 + 備份 + reset`

Use the highest applicable warning only unless the user specifically asks for detailed status.

## When the User Asks About Session / Token / Quota

Answer with current model/runtime if available, current context tokens and context limit, transcript size and level, 5-hour usage remaining/reset countdown, weekly usage remaining/reset countdown, and whether reset/summary is recommended.

Keep the answer concise. Do not expose private paths unless useful for debugging.

## Script Usage

Use `scripts/session_footer.py` to generate the transcript/context footer. Important options:

- `--json` for machine-readable output
- `--session-key <openclaw-session-key>` to select an exact session
- `--channel-id <id>` to select a channel session
- `--to channel:<id>` to select by OpenClaw recipient
- `--context-tokens <n>` to inject current context tokens parsed from runtime/session status
- `--context-limit <n>` to inject the context window limit parsed from runtime/session status
- `--allow-latest` to opt in to fallback by most recent session; avoid this for live reply footers
- `--sessions-json /path/to/sessions.json` to override the default session index

The script reads OpenClaw's local session index by default: `~/.openclaw/agents/main/sessions/sessions.json`. By default it refuses to guess the current session; pass an exact selector. It also refuses to infer current context pressure from `totalTokens`.

Example when runtime status says `📚 Context: 101k/272k`:

```bash
python3 skills/session-token-monitor/scripts/session_footer.py \
  --session-key 'agent:main:discord:channel:123' \
  --context-tokens 101000 \
  --context-limit 272000
```

## Fallback Rules

If context token count is missing but transcript size is known, still show the transcript line and show `📊 Context: unknown / <limit>` when a limit is known, or `📊 Context: unknown tokens`.

If transcript size is missing but runtime status has context tokens, omit the transcript line and show the context line.

If everything fails, output:

```text
[session footer unavailable: <short reason>]
```

## Safety Rules

- Never store API keys, OAuth tokens, cookies, recovery codes, or private credentials in this skill.
- Never print secrets while reporting session status.
- Before publishing this skill, scan the package for common secret patterns.
- Do not include local customer-specific memory, transcripts, or config files.
