#!/usr/bin/env python3
"""Generate an OpenClaw transcript/context footer without exposing secrets.

This helper intentionally treats transcript size and context-token pressure as
separate signals:

- transcript size comes from the local session jsonl file;
- context tokens must come from a runtime/session-status source or an explicit
  CLI override.

Do not infer context pressure from per-call API usage fields such as
``totalTokens`` in message usage records. Those values can represent a single
model call, not the current conversation context.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

DEFAULT_SESSIONS_JSON = "~/.openclaw/agents/main/sessions/sessions.json"


def load_sessions(path: str) -> Dict[str, Any]:
    p = Path(os.path.expanduser(path))
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("sessions JSON root is not an object")
    return data


def find_session_entry(
    data: Dict[str, Any],
    session_key: Optional[str],
    to_value: Optional[str],
    channel_id: Optional[str],
    allow_latest: bool,
) -> Tuple[str, Dict[str, Any]]:
    if session_key:
        entry = data.get(session_key)
        if not isinstance(entry, dict):
            raise KeyError(f"session_key not found: {session_key}")
        return session_key, entry

    if to_value:
        matches = [
            (k, v)
            for k, v in data.items()
            if isinstance(v, dict) and v.get("lastTo") == to_value
        ]
        if not matches:
            raise KeyError(f"no session with lastTo={to_value}")
        matches.sort(key=lambda kv: kv[1].get("updatedAt", 0), reverse=True)
        return matches[0]

    if channel_id:
        wanted = f"channel:{channel_id}"
        matches = [
            (k, v)
            for k, v in data.items()
            if isinstance(v, dict) and v.get("lastTo") == wanted
        ]
        if not matches:
            # Some OpenClaw versions encode channel sessions only in the key.
            marker = f":channel:{channel_id}"
            matches = [
                (k, v)
                for k, v in data.items()
                if isinstance(v, dict) and marker in k and v.get("sessionFile")
            ]
        if not matches:
            raise KeyError(f"no session with channel_id={channel_id}")
        matches.sort(key=lambda kv: kv[1].get("updatedAt", 0), reverse=True)
        return matches[0]

    if not allow_latest:
        raise ValueError(
            "refusing to guess the current session; pass --session-key, --channel-id, "
            "or --to, or opt in with --allow-latest"
        )

    candidates = [
        (k, v)
        for k, v in data.items()
        if isinstance(v, dict) and v.get("sessionFile")
    ]
    if not candidates:
        raise KeyError("no session entries with sessionFile found")
    candidates.sort(key=lambda kv: kv[1].get("updatedAt", 0), reverse=True)
    return candidates[0]


def classify_transcript(size_mb: float) -> str:
    if size_mb < 1:
        return "輕微"
    if size_mb < 3:
        return "中度"
    if size_mb < 6:
        return "擁擠"
    return "極限"


def parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        parsed = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def format_k_tokens(value: Optional[int]) -> str:
    if value is None:
        return "unknown"
    if value < 1000:
        return str(value)
    k = value / 1000.0
    if k >= 100:
        return f"{round(k):.0f}K"
    if k >= 10:
        return f"{k:.1f}K".replace(".0K", "K")
    return f"{k:.1f}K"


def context_alert(context_tokens: Optional[int]) -> Optional[str]:
    if context_tokens is None:
        return None
    label = format_k_tokens(context_tokens)
    if context_tokens > 200_000:
        return "🔴 強烈建議先總結 + 備份 + reset"
    if context_tokens > 150_000:
        return f"⚠️ 本頻道 session 已達 {label}，建議重置"
    if context_tokens > 130_000:
        return f"⚡ 本對話已累積 {label} tokens。"
    if context_tokens > 100_000:
        return f"⚡ 本對話已累積 {label} tokens。"
    return None


def resolve_context_tokens(args: argparse.Namespace, entry: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], str]:
    """Return (current_context_tokens, context_limit, source).

    `sessions.json.totalTokens` is intentionally not used here: in some
    OpenClaw/provider paths it reflects a single model-call usage value. Prefer
    explicit values parsed from a runtime status card. The local session index is
    only trusted for the context limit when available.
    """
    context_tokens = parse_int(args.context_tokens)
    context_limit = parse_int(args.context_limit)
    source = "cli" if context_tokens is not None else "unknown"

    if context_limit is None:
        context_limit = parse_int(entry.get("contextTokens"))
        if context_limit is not None and source == "unknown":
            source = "session-index-limit-only"

    return context_tokens, context_limit, source


def build_payload(args: argparse.Namespace) -> Dict[str, Any]:
    data = load_sessions(args.sessions_json)
    key, entry = find_session_entry(
        data,
        args.session_key,
        args.to,
        args.channel_id,
        args.allow_latest,
    )

    session_file = entry.get("sessionFile")
    transcript_line = None
    size_bytes = None
    size_mb = None
    level = None

    if session_file:
        expanded = os.path.expanduser(str(session_file))
        try:
            size_bytes = os.stat(expanded).st_size
            size_mb = size_bytes / (1024 * 1024)
            level = classify_transcript(size_mb)
            transcript_line = f"📝 Transcript: {size_mb:.2f} MB｜{level}"
        except OSError as exc:
            if args.strict:
                raise FileNotFoundError(f"cannot stat sessionFile: {expanded}: {exc}") from exc

    context_tokens, context_limit, token_source = resolve_context_tokens(args, entry)
    if context_limit is not None:
        context_line = f"📊 Context: {format_k_tokens(context_tokens)} / {format_k_tokens(context_limit)}"
    else:
        context_line = f"📊 Context: {format_k_tokens(context_tokens)} tokens"
    alert_line = context_alert(context_tokens)

    lines = []
    if alert_line:
        lines.append(alert_line)
    if transcript_line:
        lines.append(transcript_line)
    lines.append(context_line)

    return {
        "sessionKey": key,
        "sessionFile": session_file,
        "sizeBytes": size_bytes,
        "sizeMb": round(size_mb, 2) if size_mb is not None else None,
        "level": level,
        "contextTokens": context_tokens,
        "contextLimit": context_limit,
        "tokenSource": token_source,
        "transcriptLine": transcript_line,
        "contextLine": context_line,
        "alertLine": alert_line,
        "lines": lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an OpenClaw transcript/context footer.")
    parser.add_argument("--sessions-json", default=DEFAULT_SESSIONS_JSON)
    parser.add_argument("--session-key")
    parser.add_argument("--to")
    parser.add_argument("--channel-id")
    parser.add_argument("--context-tokens", help="Current context tokens from runtime/session status")
    parser.add_argument("--context-limit", help="Context window limit from runtime/session status")
    parser.add_argument("--allow-latest", action="store_true", help="Allow fallback to most recently updated session")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true", help="fail if the transcript file cannot be inspected")
    args = parser.parse_args()

    try:
        payload = build_payload(args)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("\n".join(payload["lines"]))
        return 0
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"[session footer unavailable: {exc}]", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
