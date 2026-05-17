---
name: session-token-monitor
description: Monitor OpenClaw conversation token pressure and transcript size, produce consistent reply footers, warn before context compaction/reset risk, and report short-term/weekly usage when a user asks about session, token, context, compaction, reset, transcript size, usage quota, or LLM conversation health. Use for any OpenClaw assistant or LLM that must keep replies safe as sessions grow.
---

# Session Token Monitor

## Purpose

Use this skill to keep OpenClaw conversations healthy as they grow. It standardizes session token footers, transcript-size classification, warning thresholds before compaction/reset risk, and concise status answers.

This skill is intentionally simple and model-agnostic: any LLM can follow it.

## Required Reply Footer

Before every user-visible reply, collect session status and append a footer.

Preferred sources, in order:

1. Use the runtime/session status tool if available.
2. Run `scripts/session_footer.py` from this skill if local files are available.
3. If neither works, state that the footer is unavailable; do not guess.

Footer format:

```text
📝 Transcript: <size> MB｜<level>
📊 Session: <tokens> tokens
```

If an alert applies, place it directly before the session line or directly above the footer.

## Transcript Size Levels

- `< 1 MB` → `輕微`
- `1–3 MB` → `中度`
- `3–6 MB` → `擁擠`
- `> 6 MB` → `極限`

## Token Warning Thresholds

Use the total conversation/session token count when available.

- `>100K` → `⚡ 本對話已累積 <XXK> tokens，接近壓縮門檻。`
- `>130K` → `⚡ 對話即將觸發大綱壓縮，下一次回覆可能需要 30-60 秒，請稍等！`
- `>150K` → `⚠️ 本頻道 session 已達 <XXK>，建議重置`
- `>200K` → `🔴 強烈建議先總結 + 備份 + reset`

Use the highest applicable warning only unless the user specifically asks for detailed status.

## When the User Asks About Session / Token / Quota

Answer with current model/runtime if available, session tokens and context limit, transcript size and level, 5-hour usage remaining/reset countdown, weekly usage remaining/reset countdown, and whether reset/summary is recommended.

Keep the answer concise. Do not expose private paths unless useful for debugging.

## Script Usage

Use `scripts/session_footer.py` to generate the footer. Important options:

- `--json` for machine-readable output
- `--session-key <openclaw-session-key>` to select an exact session
- `--channel-id <id>` to select a channel session
- `--to channel:<id>` to select by OpenClaw recipient
- `--sessions-json /path/to/sessions.json` to override the default session index

The script reads OpenClaw's local session index by default: `~/.openclaw/agents/main/sessions/sessions.json`.

## Fallback Rules

If token count is missing but transcript size is known, still show the transcript line and show `📊 Session: unknown tokens`.

If transcript size is missing but runtime status has token count, omit the transcript line and show the session token line.

If everything fails, output:

```text
[session footer unavailable: <short reason>]
```

## Safety Rules

- Never store API keys, OAuth tokens, cookies, recovery codes, or private credentials in this skill.
- Never print secrets while reporting session status.
- Before publishing this skill, scan the package for common secret patterns.
- Do not include local customer-specific memory, transcripts, or config files.
