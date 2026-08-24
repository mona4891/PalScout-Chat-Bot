"""
config.py
------------------------------------------------
Loads bot settings and secrets from config.txt.
If config.txt doesn't exist yet, creates a template with placeholder
values and exits so the user can fill it in.
"""

import os
import sys
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.txt")

CONFIG_TEMPLATE = """# ─────────────────────────────────────────────
# Bot Configuration File
# ─────────────────────────────────────────────

# ── AI Provider API Keys ─────────────────────
# You only need at least ONE of these for the bot to work.
# More keys = more fallback options if one provider is down/rate-limited.
GROQ_API_KEY=your-groq-key-here
CEREBRAS_API_KEY=your-cerebras-key-here
MISTRAL_API_KEY=your-mistral-key-here
OPENROUTER_API_KEY=your-openrouter-key-here

# ── Game Server Connection ───────────────────
# Enable RESTAPIEnabled=True in PalWorldSettings.ini
# Launch the server with: -enable-gamedata-api
SERVER_HOST=127.0.0.1
SERVER_PORT=8212
SERVER_ADMIN_PASSWORD=your-admin-password-goes-here

# ── Chat Log Path ─────────────────────────────
# Path to the chat log file (from the chat logging mod)
# Default location: Palworld\\Pal\\Binaries\\Win64\\ChatLog.txt
CHATLOG_PATH=./ChatLog.txt

# ── Bot Identity ──────────────────────────────
BOT_NAME=PalScout
BOT_PREFIX=!
OWNER_DISCORD_ID=your-discord-id-here

# ── Admin Permissions ─────────────────────────
# Comma-separated Steam IDs allowed to use moderation commands
# (kick, ban, warn, clearwarnings). Everyone else can still use
# !ai, !status, !players, !help.
# Find your Steam ID: it appears as "userid" in the bot's logs when
# you're connected (e.g. steam_76561198859525565), or look yourself
# up at steamid.io using your profile URL.
ADMIN_STEAM_IDS=your-steamid-here

# ── Moderation Settings ──────────────────────
# How many warnings before an automatic kick
MAX_WARNINGS_BEFORE_KICK=3

# ── Anti-Spam ─────────────────────────────────
# Prevents players from spamming commands (especially !ai, which costs
# API calls). Admins are always exempt from cooldown.
ANTI_SPAM_ENABLED=true
COOLDOWN_SECONDS=10

# ── Auto-Moderation ───────────────────────────
# Automatically scans regular chat (not just commands) for banned
# words, excessive caps, and character spam, and issues a warning
# through the normal warning system when triggered. Off by default --
# turn on and tune BANNED_WORDS once you're ready to use it.
AUTO_MODERATION_ENABLED=false
BANNED_WORDS=

# ── Search ────────────────────────────────────
# Web search auto-triggers inside !ai when a question looks like it
# needs current info (weather, news, scores, etc.), and is also
# available directly via !search <query>.
# YouTube search needs no API key to work (falls back to a web
# search), but providing one gives more reliable, direct video links.
# Get a free key at: https://console.cloud.google.com/apis/library/youtube.googleapis.com
WEB_SEARCH_ENABLED=true
YOUTUBE_SEARCH_ENABLED=true
YOUTUBE_API_KEY=your-youtube-api-key-here

# ── Discord Bridge (optional) ────────────────
DISCORD_BOT_TOKEN=your-bot-token-here
DISCORD_CHANNEL_ID=your-channel-id-here
"""


def load_config() -> dict:
    """
    Loads config.txt into a dict of key -> value.
    Creates a template file with placeholders if none exists yet.
    Skips any value still left as a placeholder (contains "your-").
    """
    if not os.path.exists(CONFIG_FILE):
        logger.info(f"[CONFIG] No config found. Creating template at {CONFIG_FILE}")
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(CONFIG_TEMPLATE)
        logger.warning("[CONFIG] Please edit config.txt with your real settings, then restart.")
        sys.exit(0)

    config_data = {}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value and "your-" not in value.lower():
                config_data[key] = value

    logger.info(f"[CONFIG] Loaded {len(config_data)} settings: {', '.join(config_data.keys())}")
    return config_data


def require(config: dict, key: str, friendly_name: str = None) -> str:
    """
    Fetches a required config value, exits with a clear error if missing.
    Use this for settings the bot truly cannot run without
    (e.g. SERVER_ADMIN_PASSWORD).
    """
    value = config.get(key)
    if not value:
        name = friendly_name or key
        logger.error(f"[CONFIG] Missing required setting: {name} (set {key} in config.txt)")
        sys.exit(1)
    return value
