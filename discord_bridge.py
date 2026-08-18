"""
discord_bridge.py
------------------------------------------------
Optional Discord integration: lets admins/players run bot commands
from a Discord channel (not just in-game chat). Runs in its own
thread since discord.py needs its own event loop.

Entirely optional -- if DISCORD_BOT_TOKEN isn't set in config.txt,
this is simply never started. The rest of the bot works fine without it.
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

try:
    import discord
    from discord.ext import commands
except ImportError:
    discord = None
    commands = None


def is_discord_available() -> bool:
    """Checks if the discord.py library is installed."""
    return discord is not None


def start_discord_bridge(token: str, channel_id: str, on_command: Callable[[str, list, str], Optional[str]]):
    """
    Starts the Discord bot and blocks (meant to be run in its own
    thread). Relays messages starting with "!" in the configured
    channel to on_command(command, args, author_name), and sends the
    returned response back to that Discord channel.

    on_command should be the same command handler used for in-game
    chat commands, so behavior stays consistent between Discord and
    in-game.
    """
    if not discord:
        logger.warning("[DISCORD] discord.py is not installed. Skipping Discord bridge.")
        return

    if not token or not channel_id:
        logger.warning("[DISCORD] Missing bot token or channel ID. Skipping Discord bridge.")
        return

    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"[DISCORD] Logged in as {bot.user}")

    @bot.event
    async def on_message(message):
        if message.author == bot.user:
            return
        if message.channel.id != int(channel_id):
            return
        if not message.content.startswith("!"):
            return

        parts = message.content.split()
        command = parts[0][1:].lower()
        args = parts[1:]

        try:
            response = on_command(command, args, message.author.name)
            if response:
                await message.channel.send(response)
        except Exception as e:
            logger.error(f"[DISCORD] Error handling command '{command}': {e}")
            await message.channel.send("An error occurred processing that command.")

    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"[DISCORD] Failed to start: {e}")


def send_to_discord_webhook(webhook_url: str, message: str) -> bool:
    """
    Sends a one-way message to Discord via webhook -- simpler than the
    full bot connection above, useful for relaying game events (joins,
    kicks, etc.) to a Discord channel without needing bidirectional commands.
    """
    import requests
    try:
        resp = requests.post(webhook_url, json={"content": message[:2000]}, timeout=5)
        return resp.status_code in (200, 204)
    except requests.RequestException as e:
        logger.error(f"[DISCORD] Webhook send failed: {e}")
        return False
