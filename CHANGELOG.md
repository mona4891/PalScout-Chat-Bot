# Changelog

## v1.1.0 — Web Dashboard

- Added an optional local web dashboard (`DASHBOARD_ENABLED=true` in `config.txt`), password-protected, with six sections:
  - **Status** — live connection state, player count, in-game time, active AI provider
  - **Players** — HP, nearby creatures with real distances, admin/player role, kick/ban/warn buttons
  - **Moderation** — warnings and active bans (with live countdown for temp bans), unban/clear-warning actions, auto-moderation toggle and banned-word list editor, one-click backup export
  - **AI and search** — per-provider status and cooldown, editable model names, web/YouTube search toggles, a live "test the AI" box
  - **Settings** — bot name/prefix, anti-spam cooldown, warning limit, admin Steam ID management, Discord bridge config, verbose logging toggle
  - **Memory and activity** — view and delete `!ai remember` notes, a live feed of recent AI questions and answers
  - **Customize** — upload a background image and choose the content panel's color/opacity, both persisted on disk
- All dashboard settings changes are saved directly to `config.txt` and survive a restart
- Fixed: `!kick`/`!ban`/`!warn` from the dashboard now correctly block targeting an admin, matching in-game command behavior
- Fixed: live connection status now updates continuously instead of only reflecting the state at bot startup
- Fixed: repeated connection-error log spam when the Palworld server is unreachable is now throttled
- Fixed: a crash from certain Unicode characters in AI responses on Windows consoles
- Fixed: the AI could falsely claim to have performed a kick/ban/warn when asked conversationally instead of via the real command
- Fixed: the AI didn't understand "Pal" refers to the game's creatures, sometimes confusing it with "player"
- Fixed: YouTube search query cleanup and switched to the current `ddgs` package (renamed from `duckduckgo-search`)

## Distribution

PalScout is now available on multiple platforms:
- [GitHub](https://github.com/mona4891/PalScout-Chat-Bot) — source code and releases
- [CurseForge](https://www.curseforge.com/palworld/miscellaneous/palscout)
- [Thunderstore](https://thunderstore.io/c/palworld/p/PalScout/PalScout/)
- Steam Workshop — the companion `PalScoutChatLogger` mod only (the full bot isn't distributable through Workshop, see the mod's own page for details): https://steamcommunity.com/sharedfiles/filedetails/?id=3798992368

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
