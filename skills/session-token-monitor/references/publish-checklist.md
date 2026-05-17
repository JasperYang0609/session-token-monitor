# Publish Checklist

Use this checklist before sharing the skill with customers or publishing it to GitHub.

## Required files

- `SKILL.md`
- `scripts/session_footer.py`

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
