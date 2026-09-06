# Changelog

## v1.0.2

- AI model names are now configurable in `config.txt` instead of hardcoded, so a provider deprecating a model no longer requires a code update — just edit the model name yourself
- Added `GROQ_MODEL`, `CEREBRAS_MODEL`, `MISTRAL_MODEL`, `OPENROUTER_MODEL`, and `LOCAL_MODEL` settings
- Added `LOCAL_AI_ENABLED` setting (previously worked but wasn't documented in `config.txt`)

**If you're updating from an earlier version**, add these new lines to your existing `config.txt` manually (your file won't update automatically):

```
GROQ_MODEL=openai/gpt-oss-20b
CEREBRAS_MODEL=gpt-oss-120b
MISTRAL_MODEL=mistral-tiny
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
LOCAL_MODEL=llama2
LOCAL_AI_ENABLED=false
```

## v1.0.1

- Fixed admin permission checks failing incorrectly due to a mismatched field name in player lookups — `!kick`, `!warn`, and `!ban` now correctly recognize admins
- Fixed a crash that could occur when an AI response contained certain special characters
- The AI no longer falsely claims to have performed a kick, ban, or warn when asked conversationally — it now points to the real commands instead
- Cleaned up log noise caused by multi-line bot messages (like `!help`) being split incorrectly in the chat log

## v1.0.0

- Initial release
- AI chat grounded in live game data (HP, level, guild, position, nearby creatures)
- Multi-provider AI fallback (Groq, Cerebras, Mistral, OpenRouter, optional local model)
- Web and YouTube search, automatic or via `!search` / `!youtube`
- Full moderation system: warnings with auto-kick escalation, kick, ban — admin-verified by Steam ID
- Admin protection — admins can't be kicked, banned, or warned through the bot
- Toggleable anti-spam cooldown and auto-moderation chat filter
- Permanent memory via `!ai remember`
- Optional Discord bridge
- Includes PalScoutChatLogger, a custom UE4SS mod for reading in-game chat
