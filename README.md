# PalScout

PalScout is an AI-powered chatbot and moderation tool for Palworld dedicated servers. Players can chat with an AI directly in-game, and its answers are grounded in **live game data** — your actual HP, level, position, and nearby creatures — not just generic chat.

## Features

- **AI chat, grounded in real game state** — ask questions in-game and get answers that reference your actual HP, level, guild, and nearby creatures with real distances
- **Multi-provider AI fallback** — automatically switches between AI providers if one is down or rate-limited, so PalScout stays online
- **Full moderation system** — warnings that auto-escalate to a kick, plus kick/ban commands, all logged
- **Admin-only moderation commands** — verified by Steam ID, so display names can't be spoofed to gain admin access
- **Optional Discord bridge** — run the same commands from Discord, not just in-game
- **No RCON dependency** — built entirely on Palworld's REST API, since RCON is being phased out by the developers

## Requirements

- Python 3.10+
- A running Palworld dedicated server with `RESTAPIEnabled=True` set in `PalWorldSettings.ini`, launched with the `-enable-gamedata-api` flag
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS/releases) and a chat-logging mod installed on the server (required for the bot to read in-game chat — Palworld's REST API can only send chat, not read it)
- At least one AI provider API key (a free tier from [Groq](https://console.groq.com/keys) is enough to get started)

## Installation

1. Clone or download this repository into its own folder
2. Install dependencies:
   ```
   pip install requests groq openai discord.py
   ```
3. Run the bot once to generate a config file:
   ```
   python bot.py
   ```
4. Open the generated `config.txt` and fill in your real values (server admin password, at least one AI API key, chat log path, admin Steam IDs)
5. Run the bot again:
   ```
   python bot.py
   ```

## Configuration

All settings live in `config.txt`, created automatically on first run. Key fields:

| Setting | Description |
|---|---|
| `SERVER_ADMIN_PASSWORD` | Matches the `AdminPassword` set in your server's `PalWorldSettings.ini` |
| `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `MISTRAL_API_KEY` / `OPENROUTER_API_KEY` | AI provider keys — only one is required, more adds fallback resilience |
| `CHATLOG_PATH` | Path to the chat log file written by your chat-logging mod |
| `ADMIN_STEAM_IDS` | Comma-separated Steam IDs allowed to use moderation commands |
| `BOT_NAME` / `BOT_PREFIX` | The bot's display name and command prefix (default `!`) |
| `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` | Optional, enables the Discord bridge |

## Commands

| Command | Description | Access |
|---|---|---|
| `!ai <question>` | Ask the AI anything — answers use live game data | Everyone |
| `!status` | Show current world status | Everyone |
| `!players` | List online players | Everyone |
| `!help` | Show available commands | Everyone |
| `!warn <player> [reason]` | Warn a player, auto-kicks at the warning limit | Admins only |
| `!warnings <player>` | Check a player's warning count | Admins only |
| `!clearwarnings <player>` | Reset a player's warnings | Admins only |
| `!kick <player> [reason]` | Kick a player | Admins only |
| `!ban <player> [reason]` | Ban a player | Admins only |

## Why no RCON?

Palworld's original RCON system has been marked deprecated by the developers, with plans to remove it in a future update. PalScout is built entirely on Palworld's newer REST API instead, which is also more capable — it exposes live world data (player and creature positions, health, and status) that RCON never did, which is what makes the AI's grounded responses possible in the first place.

## Project structure

```
config.py           # Settings loader
palworld_api.py      # REST API wrapper (server connection, chat, kick/ban, game data)
ai_providers.py       # Multi-provider AI fallback chain
chat_listener.py      # Reads incoming chat from the chat log file
moderation.py         # Warnings, kicks, bans, and persistence
memory.py             # Permanent memory + recent chat history
commands.py           # Command routing and permission checks
discord_bridge.py     # Optional Discord integration
bot.py                # Main entry point
```

## Known limitations

- Requires a third-party chat-logging mod, since Palworld's REST API cannot read incoming chat on its own
- Position data assumes Unreal Engine units (~1 unit ≈ 1cm); distance calculations are approximate

## License

MIT

## Support

Open an issue on this repository for bugs or feature requests.
