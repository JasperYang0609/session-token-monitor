# Publish Checklist

Use this checklist before sharing the skill with customers or publishing it to GitHub.

## Required files

- `SKILL.md`
- `scripts/session_footer.py`
- `scripts/install_agent_hook.py`

## Install verification

- Skill folder is copied under the target workspace `skills/` directory.
- Agent hook is installed into `AGENTS.md` or equivalent always-loaded instruction file.
- Re-running `scripts/install_agent_hook.py` updates only the marker block.
- A fresh session can load the skill and the hook.

## Must not include

- API keys
- OAuth tokens
- GitHub personal access tokens
- OpenAI/Anthropic/Gemini keys
- cookies
- recovery codes
- local `openclaw.json`
- `.env` files
- transcript/session logs
- customer memory files

## Basic secret scan patterns

Search for these patterns before publishing:

```text
ghp_
github_pat_
sk-
sk-proj-
sk-ant-
AIza
xoxb-
xoxp-
Bearer 
eyJ
OPENAI_API_KEY
ANTHROPIC_API_KEY
GEMINI_API_KEY
GOOGLE_API_KEY
DISCORD_BOT_TOKEN
TELEGRAM_BOT_TOKEN
NOTION_TOKEN
SUPABASE_SERVICE_ROLE_KEY
```

A variable name by itself is usually safe; a real credential value is not.

## Runtime diagnostics verification

- Run the helper with real runtime status values or `--status-text` and confirm `tokenSource` is `runtime-status` or explicitly labeled.
- Run once with a high trusted token value, then again with a much lower unexplained value using the same `--history-json`; confirm `Context token suspicious drop` appears and the trusted history baseline is unchanged.
- Run with a changed `--context-limit`; confirm `Context limit changed` appears.
- Run without `--context-tokens` or `--status-text`; confirm it shows `unknown` instead of guessing a per-call token total.
- If installing for a customer, run `scripts/install_agent_hook.py --check AGENTS.md` after installation.


## Automated verification

- `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- `python3 -m py_compile skills/session-token-monitor/scripts/*.py scripts/*.py tests/*.py`
- `python3 scripts/build_skill_archive.py --check`
- Confirm history/audit fixtures are mode `0600` and no real session data appears in tests.
