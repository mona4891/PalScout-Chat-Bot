#!/usr/bin/env python3
"""
bot.py
------------------------------------------------
Main entry point. Loads config, connects to the game server, and
starts the chat listener (and optionally the Discord bridge) as
background threads. This is the file you actually run.

Usage:
    python bot.py
"""

import os
import sys
import time
import logging
import threading

from config import load_config, require
from palworld_api import GameServerAPI
from ai_providers import AIProviderChain
from moderation import ModerationSystem, ChatFilter
from memory import PermanentMemory, ChatHistory
from commands import CommandHandler
from chat_listener import tail_chatlog
import discord_bridge

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Logging setup ─────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "bot.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

_shutdown_requested = False


def _should_stop() -> bool:
    return _shutdown_requested


def build_bot():
    """
    Loads config and wires up every subsystem. Returns the pieces
    main() needs: the command handler, server API, config, and
    bot identity settings.
    """
    config = load_config()

    bot_name = config.get("BOT_NAME", "PalScout")
    bot_prefix = config.get("BOT_PREFIX", "!")
    max_warnings = int(config.get("MAX_WARNINGS_BEFORE_KICK", "3"))

    host = config.get("SERVER_HOST", "127.0.0.1")
    port = int(config.get("SERVER_PORT", "8212"))
    password = require(config, "SERVER_ADMIN_PASSWORD", "server admin password")

    server_api = GameServerAPI(host, port, password, bot_name=bot_name)

    if not server_api.test_connection():
        logger.error(
            "Could not connect to the game server's REST API.\n"
            "Check that:\n"
            "  1. The game server is running\n"
            "  2. The REST API is enabled in the server settings\n"
            "  3. The admin password in config.txt matches the server's\n"
        )
        sys.exit(1)

    ai_chain = AIProviderChain(config, local_enabled=config.get("LOCAL_AI_ENABLED", "false").lower() == "true")
    moderation = ModerationSystem(BASE_DIR, server_api, max_warnings_before_kick=max_warnings)
    permanent_memory = PermanentMemory(BASE_DIR)
    chat_history = ChatHistory(max_size=50)

    admin_ids_raw = config.get("ADMIN_STEAM_IDS", "")
    admin_steam_ids = [s.strip() for s in admin_ids_raw.split(",") if s.strip()]
    if not admin_steam_ids:
        logger.warning("[CONFIG] No ADMIN_STEAM_IDS set -- moderation commands will be unusable until this is configured.")

    anti_spam_enabled = config.get("ANTI_SPAM_ENABLED", "true").lower() == "true"
    cooldown_seconds = int(config.get("COOLDOWN_SECONDS", "10"))

    web_search_enabled = config.get("WEB_SEARCH_ENABLED", "true").lower() == "true"
    youtube_search_enabled = config.get("YOUTUBE_SEARCH_ENABLED", "true").lower() == "true"
    youtube_api_key = config.get("YOUTUBE_API_KEY")  # optional -- falls back to web search if missing

    command_handler = CommandHandler(
        server_api=server_api,
        ai_chain=ai_chain,
        moderation=moderation,
        permanent_memory=permanent_memory,
        chat_history=chat_history,
        bot_name=bot_name,
        bot_prefix=bot_prefix,
        admin_steam_ids=admin_steam_ids,
        anti_spam_enabled=anti_spam_enabled,
        cooldown_seconds=cooldown_seconds,
        web_search_enabled=web_search_enabled,
        youtube_search_enabled=youtube_search_enabled,
        youtube_api_key=youtube_api_key,
    )

    auto_mod_enabled = config.get("AUTO_MODERATION_ENABLED", "false").lower() == "true"
    banned_words_raw = config.get("BANNED_WORDS", "")
    banned_words = [w.strip() for w in banned_words_raw.split(",") if w.strip()]
    chat_filter = ChatFilter(enabled=auto_mod_enabled, banned_words=banned_words)
    if auto_mod_enabled:
        logger.info(f"[AUTOMOD] Auto-moderation enabled with {len(banned_words)} banned word(s).")
    else:
        logger.info("[AUTOMOD] Auto-moderation is disabled (AUTO_MODERATION_ENABLED=false).")

    return command_handler, server_api, config, bot_name, bot_prefix, chat_history, chat_filter


def make_chat_message_handler(command_handler: CommandHandler, server_api: GameServerAPI,
                                bot_prefix: str, chat_history: ChatHistory, moderation: ModerationSystem,
                                chat_filter: ChatFilter):
    """
    Returns the function that gets called for every real chat message
    detected by the chat listener. Records it to chat history, and if
    it's a command (starts with bot_prefix), routes it through the
    command handler and sends the response back into the game.

    Regular (non-command) messages are also passed through the
    ChatFilter if auto-moderation is enabled -- a violation issues a
    warning through the normal warning system, so it benefits from
    the same auto-kick-at-limit escalation as manual warnings.
    """
    def handle_chat_message(player_name: str, message: str):
        chat_history.add(player_name, message)

        if message.startswith(bot_prefix):
            parts = message[len(bot_prefix):].split()
            if not parts:
                return

            command = parts[0].lower()
            args = parts[1:]

            response = command_handler.handle(command, args, player_name)
            if response:
                server_api.send_chat(response)
            return

        # Not a command -- regular chat, check it against the filter
        # (a no-op if auto-moderation is disabled).
        violation_reason = chat_filter.check_message(message)
        if violation_reason:
            result = moderation.warn_player(player_name, f"Auto-moderation: {violation_reason}", issued_by="AutoMod")
            server_api.send_chat(result)

    return handle_chat_message


def periodic_expired_ban_check(moderation: ModerationSystem, interval_seconds: int = 300):
    """
    Background loop that periodically checks for temp bans that have
    expired, so they can be reviewed/lifted. Runs until shutdown.
    """
    while not _should_stop():
        expired = moderation.get_expired_temp_bans()
        for player_id, entry in expired.items():
            logger.info(f"[MODERATION] Temp ban expired for {entry.get('name', player_id)}")
        time.sleep(interval_seconds)


def main():
    global _shutdown_requested

    logger.info("=" * 50)
    logger.info("Bot starting...")
    logger.info("=" * 50)

    command_handler, server_api, config, bot_name, bot_prefix, chat_history, chat_filter = build_bot()

    chatlog_path = config.get("CHATLOG_PATH", os.path.join(BASE_DIR, "ChatLog.txt"))
    if not os.path.exists(chatlog_path):
        logger.warning(f"[CHATLOG] Chat log not found at: {chatlog_path}")
        logger.warning("[CHATLOG] Make sure the chat logging mod is installed and enabled.")
        logger.warning("[CHATLOG] The bot will run, but won't respond to in-game chat until this is fixed.")

    server_api.send_chat(f"{bot_name} online! Type {bot_prefix}help for commands.")

    on_message = make_chat_message_handler(
        command_handler, server_api, bot_prefix, chat_history, command_handler.moderation, chat_filter
    )

    if os.path.exists(chatlog_path):
        chat_thread = threading.Thread(
            target=tail_chatlog,
            args=(chatlog_path, on_message, _should_stop),
            daemon=True,
        )
        chat_thread.start()
        logger.info("[CHATLOG] Chat listener thread started.")

    if config.get("DISCORD_BOT_TOKEN"):
        def discord_command_bridge(command, args, author_name):
            return command_handler.handle(command, args, author_name)

        discord_thread = threading.Thread(
            target=discord_bridge.start_discord_bridge,
            args=(config.get("DISCORD_BOT_TOKEN"), config.get("DISCORD_CHANNEL_ID"), discord_command_bridge),
            daemon=True,
        )
        discord_thread.start()
        logger.info("[DISCORD] Discord bridge thread started.")

    ban_check_thread = threading.Thread(
        target=periodic_expired_ban_check,
        args=(command_handler.moderation,),
        daemon=True,
    )
    ban_check_thread.start()

    logger.info(f"{bot_name} is running! Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        _shutdown_requested = True
        server_api.send_chat(f"{bot_name} is going offline.")
        sys.exit(0)


if __name__ == "__main__":
    main()
