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

**Always re-fetch fresh on every reply.** Do not carry over the previous turn's context tokens or limit. Do not increment by feel (e.g. "+2K every turn"). The runtime status is the source of truth — call it every time.

**Model-switch invalidates the limit.** Different models have different context windows (e.g. Codex GPT-5.5 ≈ 272K, Claude Opus 4.7 ≈ 1M, Claude Sonnet 4.6 ≈ 200K). When the active model changes mid-conversation, the previous limit is stale. Re-fetch from runtime status before reporting the next footer.

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
Before every user-visible reply, use the `session-token-monitor` skill and append its token/transcript footer. Treat this as a required pre-send gate: fetch fresh runtime/session status every time, pass the current `📚 Context: used/limit` into the footer helper, never reuse prior token/limit values, and never use per-call `usage.totalTokens` or `sessions.json.totalTokens` as current context pressure. If footer collection fails, report the short failure instead of guessing.
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

- `>100K` → `⚡ 本對話已累積 <XXK> tokens。`
- `>130K` → `⚡ 本對話已累積 <XXK> tokens。`
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
- `--status-text <text>` or `--status-file <path>` to parse `📚 Context: used/limit`, model, runtime, and compaction count from a status card
- `--token-source <label>` to explicitly label injected values; prefer `runtime-status`
- `--history-json <path>` to compare against the previous footer state and warn on suspicious token drops or context-limit changes
- `--audit-log <path>` to append JSONL diagnostics for customer troubleshooting
- `--no-history` to disable local state comparison
- `--allow-latest` to opt in to fallback by most recent session; avoid this for live reply footers
- `--sessions-json /path/to/sessions.json` to override the default session index

The script reads OpenClaw's local session index by default: `~/.openclaw/agents/main/sessions/sessions.json`. By default it refuses to guess the current session; pass an exact selector. It also refuses to infer current context pressure from `totalTokens`.

The helper keeps a small local history at `~/.openclaw/session-token-monitor/history.json` by default. It uses this only to detect suspicious changes, such as context tokens suddenly dropping without a compaction/model switch or context limits changing mid-session. Only trusted runtime-status or explicit CLI samples update this baseline; unknown, weak-source, and unexplained-drop samples are reported but do not overwrite the last-known-good record. History updates are atomic and owner-only (`0600`). Use `--no-history` to disable this.

Example when runtime status says `📚 Context: 101k/272k`:

```bash
python3 skills/session-token-monitor/scripts/session_footer.py \
  --session-key 'agent:main:discord:channel:123' \
  --context-tokens 101000 \
  --context-limit 272000
```

## Diagnostic Warnings

The helper emits inline warnings before the footer when it detects suspicious conditions:

- `Context token unavailable` — no reliable runtime context was provided, so it refuses to guess.
- `Context token source suspicious` — values came from a weak source instead of runtime status.
- `Context limit changed` — the same session's limit changed, often due to model switch or runtime reporting changes.
- `Context token suspicious drop` — tokens dropped sharply without a known compaction/model switch; this often means a per-call reply token was used by mistake or the wrong session was selected. The suspicious sample is not promoted to trusted history.
- `Context source conflict` — runtime status and explicit CLI values disagree; runtime status wins.

For customer debugging, run with `--audit-log logs/session-token-monitor.jsonl` so each footer writes a compact JSON record with time, session key, model, runtime, context tokens, context limit, source, compaction count, and warnings.

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
