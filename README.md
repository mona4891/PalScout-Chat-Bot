# PalScout

PalScout is an AI-powered chatbot and moderation tool for Palworld dedicated servers. Players can chat with an AI directly in-game, and its answers are grounded in **live game data** — your actual HP, level, position, and nearby creatures — not just generic chat.

**[Download the latest release](../../releases/latest)** — a standalone `.exe` build is available, no Python installation required.

## Features

- **AI chat, grounded in real game state** — ask questions in-game and get answers that reference your actual HP, level, guild, and nearby creatures with real distances
- **Multi-provider AI fallback** — automatically switches between AI providers if one is down or rate-limited, so PalScout stays online
- **Web and YouTube search** — automatically searches when a question needs current info (weather, news, scores, etc.), or on demand with `!search` / `!youtube`
- **Full moderation system** — warnings that auto-escalate to a kick, plus kick/ban commands, all logged
- **Admin-only moderation commands** — verified by Steam ID, so display names can't be spoofed to gain admin access
- **Admin protection** — admins can't be kicked, banned, or warned through the bot, even by other admins
- **Anti-spam cooldown** — toggleable, prevents command spam; admins are always exempt
- **Optional auto-moderation** — toggleable chat filter for banned words, excessive caps, and spam, off by default
- **Permanent memory** — save notes for the AI to remember with `!ai remember`
- **Optional Discord bridge** — run the same commands from Discord, not just in-game
- **No RCON dependency** — built entirely on Palworld's REST API, since RCON is being phased out by the developers

## Requirements

- A running Palworld dedicated server with `RESTAPIEnabled=True` set in `PalWorldSettings.ini`, launched with the `-enable-gamedata-api` flag
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS/releases) installed on the server, plus PalScout's own chat-logging mod (included in this repo under `PalScoutChatLogger/` — required because Palworld's REST API can only send chat, not read it)
- At least one AI provider API key (a free tier from [Groq](https://console.groq.com/keys) is enough to get started)
- Python 3.10+ — only if running from source. Not needed if using the prebuilt `.exe`.

## Installation

### Option A — prebuilt .exe (recommended, no Python needed)

1. Download `PalScout.exe` from the [latest release](../../releases/latest)
2. Follow steps 3–5 below to install UE4SS and the chat-logging mod
3. Run `PalScout.exe` once to generate a `config.txt` template next to it
4. Fill in `config.txt`, then run `PalScout.exe` again

### Option B — from source

1. Clone or download this repository into its own folder
2. Install dependencies:
   ```
   pip install requests groq openai discord.py duckduckgo-search
   ```
3. Install [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS/releases) on your server if you haven't already (unzip into `Pal\Binaries\Win64`)
4. Copy the `PalScoutChatLogger` folder from this repo into your server's `Pal\Binaries\Win64\Mods\` folder. The folder structure should look like:
   ```
   Mods\PalScoutChatLogger\
   ├── enabled.txt
   └── Scripts\
       └── main.lua
   ```
5. Launch the server with the `-enable-gamedata-api` flag and check the UE4SS console for `[PalScoutChatLogger] Loaded and hooked into chat.` to confirm it loaded
6. Run the bot once to generate a config file:
   ```
   python bot.py
   ```
7. Open the generated `config.txt` and fill in your real values (server admin password, at least one AI API key, the path to `PalScoutChat.log` — created next to the mod once it's running — and your admin Steam ID)
8. Run the bot again:
   ```
   python bot.py
   ```

## Configuration

All settings live in `config.txt`, created automatically on first run. Key fields:

| Setting | Description |
|---|---|
| `SERVER_ADMIN_PASSWORD` | Matches the `AdminPassword` set in your server's `PalWorldSettings.ini` |
| `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `MISTRAL_API_KEY` / `OPENROUTER_API_KEY` | AI provider keys — only one is required, more adds fallback resilience |
| `CHATLOG_PATH` | Path to `PalScoutChat.log`, written by the included chat-logging mod |
| `ADMIN_STEAM_IDS` | Comma-separated Steam IDs allowed to use moderation commands |
| `BOT_NAME` / `BOT_PREFIX` | The bot's display name and command prefix (default `!`) |
| `MAX_WARNINGS_BEFORE_KICK` | How many warnings before an automatic kick |
| `ANTI_SPAM_ENABLED` / `COOLDOWN_SECONDS` | Toggle and tune the per-player command cooldown |
| `AUTO_MODERATION_ENABLED` / `BANNED_WORDS` | Toggle the chat filter and set banned words (comma-separated) |
| `WEB_SEARCH_ENABLED` / `YOUTUBE_SEARCH_ENABLED` / `YOUTUBE_API_KEY` | Toggle search features; YouTube API key is optional (falls back to web search without it) |
| `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_ID` | Optional, enables the Discord bridge |

## Commands

| Command | Description | Access |
|---|---|---|
| `!ai <question>` | Ask the AI anything — answers use live game data, auto-searches the web if needed | Everyone |
| `!ai remember <note>` | Save a permanent note for the AI to reference later | Everyone |
| `!search <query>` | Search the web directly | Everyone |
| `!youtube <query>` | Find a YouTube video | Everyone |
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
config.py             # Settings loader
palworld_api.py       # REST API wrapper (server connection, chat, kick/ban, game data)
ai_providers.py        # Multi-provider AI fallback chain
chat_listener.py       # Reads incoming chat from the chat log file
moderation.py          # Warnings, kicks, bans, auto-moderation filter, and persistence
memory.py              # Permanent memory + recent chat history
commands.py            # Command routing, permission checks, and cooldown handling
search.py              # Web and YouTube search
discord_bridge.py      # Optional Discord integration
bot.py                 # Main entry point
PalScoutChatLogger/    # UE4SS Lua mod — writes chat to a log file the bot can read
```

## Known limitations

- Requires [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS/releases) plus the included chat-logging mod, since Palworld's REST API cannot read incoming chat on its own
- Position data assumes Unreal Engine units (~1 unit ≈ 1cm); distance calculations are approximate
- Antivirus software may flag the prebuilt `.exe` on first run — a common false positive for unsigned PyInstaller builds, not a sign of anything malicious (source is fully available in this repo)

## License

MIT License — see `LICENSE` for details.

## Support

Open an issue on this repository for bugs or feature requests.
