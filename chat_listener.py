"""
chat_listener.py
------------------------------------------------
Watches the chat log file (written by the chat logging mod) and
parses out real player messages in real time. The game server's own
REST API cannot read incoming chat, so this file-tailing approach is
what makes "respond to in-game chat" possible at all.

Expected log line format:
    2026-08-13 19:01:05 mona said test

SYSTEM lines (join/leave announcements) are skipped automatically.
"""

import os
import time
import logging
from typing import Callable

logger = logging.getLogger(__name__)


def tail_chatlog(chatlog_path: str, on_message: Callable[[str, str], None], stop_flag: Callable[[], bool] = None):
    """
    Continuously watches chatlog_path for new lines and calls
    on_message(player_name, message) for each real chat message found.

    on_message: a function taking (player_name, message) -- this is
        where the rest of the bot's logic (commands, AI, moderation)
        plugs in.
    stop_flag: optional function returning True when the loop should
        stop. If not provided, runs forever until the process exits.
    """
    if not os.path.exists(chatlog_path):
        logger.error(f"[CHATLOG] File not found: {chatlog_path}")
        logger.error("[CHATLOG] Make sure the chat logging mod is installed and enabled.")
        return

    logger.info(f"[CHATLOG] Tailing: {chatlog_path}")

    with open(chatlog_path, "r", encoding="utf-8", errors="ignore") as f:
        # Start at the end of the file -- only react to NEW messages
        # from this point forward, not the entire chat history.
        f.seek(0, os.SEEK_END)

        while True:
            if stop_flag and stop_flag():
                logger.info("[CHATLOG] Stop signal received, ending tail loop.")
                return

            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue

            line = line.strip()
            if not line:
                continue

            parsed = _parse_chat_line(line)
            if parsed is None:
                continue

            player_name, message = parsed

            if player_name.upper() == "SYSTEM":
                continue  # join/leave announcements, not real chat

            if not message.strip():
                continue

            logger.info(f"[CHAT] <{player_name}> {message}")

            try:
                on_message(player_name, message)
            except Exception as e:
                logger.error(f"[CHATLOG] Error handling message from {player_name}: {e}")


def _parse_chat_line(line: str):
    """
    Parses a single log line into (player_name, message).
    Expected format: "<date> <time> <playername> said <message>"
    Returns None if the line doesn't match this format.
    """
    parts = line.split(" said ", 1)
    if len(parts) != 2:
        return None

    timestamp_and_name = parts[0]  # e.g. "2026-08-13 19:01:05 mona"
    message = parts[1]

    name_parts = timestamp_and_name.split()
    if len(name_parts) < 3:
        return None

    player_name = name_parts[2]
    return player_name, message
