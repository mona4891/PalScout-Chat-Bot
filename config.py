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


def _get_base_dir() -> str:
    """
    Returns the folder config.txt (and other data files) should live
    in. When running as a normal Python script, that's just the
    script's own folder. When running as a PyInstaller-built exe,
    __file__ points to a temporary internal extraction folder instead
    of where the .exe actually sits -- sys.executable gives the real
    location in that case.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
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

# ── AI Provider Model Names ───────────────────
# Which specific model each provider uses. AI providers periodically
# retire/rename models with little warning -- if a provider suddenly
# stops working and the bot log shows a "model not found" type error,
# check that provider's website for their current model names and
# update the matching line below. No code changes needed.
GROQ_MODEL=openai/gpt-oss-20b
CEREBRAS_MODEL=gpt-oss-120b
MISTRAL_MODEL=mistral-tiny
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
# Only used if you run a local Ollama instance (LOCAL_AI_ENABLED=true)
LOCAL_MODEL=llama2

# ── Local AI (optional) ───────────────────────
# If true, tries a locally-running Ollama instance before any cloud
# provider -- free and unlimited, but requires you to have Ollama
# installed and running yourself.
LOCAL_AI_ENABLED=false

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

# ── Web Dashboard (optional) ──────────────────
# View live stats and manage players/settings from a browser.
# Visit http://localhost:5000 once running (or whatever port you set).
DASHBOARD_ENABLED=false
DASHBOARD_PORT=5000
DASHBOARD_PASSWORD=your-dashboard-password-goes-here
# When false (default), suppresses the per-request "GET /api/status
# 200" lines the dashboard's web server logs on every page refresh --
# useful noise while debugging the dashboard itself, but clutters the
# console during normal use. Set to true to see them again.
DASHBOARD_VERBOSE_LOGGING=false
# Background image and content-panel color can be set from the
# Customize tab in the dashboard itself -- these two lines are managed
# automatically once you do, no need to edit them by hand.
DASHBOARD_PANEL_COLOR=#1a2320
DASHBOARD_PANEL_OPACITY=88
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


def update_config_value(key: str, value: str) -> bool:
    """
    Updates a single setting in config.txt on disk, so changes made
    from the dashboard (toggles, model names, banned words) survive a
    restart instead of only applying to the current running session.

    Rewrites only the matching "KEY=..." line, preserving every other
    line (comments, formatting, unrelated settings) exactly as-is. If
    the key doesn't exist yet in the file, appends it at the end
    rather than failing silently.

    Returns True on success, False if the file couldn't be read/written
    (e.g. permissions issue) -- callers should treat a False return as
    "the in-memory change worked, but wasn't saved to disk" rather than
    a hard failure.
    """
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"[CONFIG] Cannot update {key}: config.txt doesn't exist.")
        return False

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError as e:
        logger.error(f"[CONFIG] Failed to read config.txt: {e}")
        return False

    found = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # Key wasn't in the file at all (e.g. an older config.txt
        # predating this setting) -- add it rather than losing the change.
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        logger.info(f"[CONFIG] Updated {key} in config.txt")
        return True
    except OSError as e:
        logger.error(f"[CONFIG] Failed to write config.txt: {e}")
        return False
