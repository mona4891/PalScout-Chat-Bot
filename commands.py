"""
commands.py
------------------------------------------------
Ties command names (like "!kick", "!ai", "!warn") to actual bot
behavior. Used identically by both in-game chat and Discord, so
commands behave the same regardless of where they're issued from.

Also contains ask_ai() -- the function that assembles everything the
AI needs to answer a question: the system prompt, permanent memory,
recent chat history, and live game-state context, then sends it
through the AI provider fallback chain.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Holds references to every subsystem (game server API, AI provider
    chain, moderation, memory) and routes commands to the right one.
    """

    def __init__(self, server_api, ai_chain, moderation, permanent_memory,
                 chat_history, bot_name: str, bot_prefix: str, admin_steam_ids: List[str] = None):
        self.server_api = server_api
        self.ai_chain = ai_chain
        self.moderation = moderation
        self.permanent_memory = permanent_memory
        self.chat_history = chat_history
        self.bot_name = bot_name
        self.bot_prefix = bot_prefix
        self.admin_steam_ids = set(admin_steam_ids or [])
        self.system_prompt = (
            f"You are {bot_name}, a helpful AI assistant for a game server. "
            "You have access to live game data including player positions, "
            "HP, levels, guilds, and nearby creatures. Use this information "
            "to provide helpful, contextual responses. Be friendly and "
            "conversational.\n\n"
            "STRICT FORMAT RULES (this is raw in-game chat text, not a "
            "document, and these rules are never broken):\n"
            "- Maximum 1-2 short sentences, under 40 words total.\n"
            "- Plain text ONLY. Never use **, *, -, #, or any other "
            "markdown or formatting symbols.\n"
            "- No lists, no bullet points, no headers, no bold, no "
            "italics -- just a normal spoken sentence.\n\n"
            "Example of a GOOD reply: Your HP is low at 319/600, and a "
            "level 22 Survivor is right next to you, so be careful.\n"
            "Example of a BAD reply (never do this): You're low on HP "
            "(319/600) and have a **Lv22 Scouting Party Survivor** right "
            "next to you."
        )

    # ── The core AI question/answer flow ─────────────

    def ask_ai(self, player_name: str, question: str) -> str:
        """
        Builds full context (game state + permanent memory + recent
        chat) and sends the question through the AI provider chain.
        """
        logger.info(f"[AI] {player_name} asked: {question}")
        try:
            game_context = self.server_api.build_game_context(player_name)
            memory_context = self.permanent_memory.load()
            chat_context = self.chat_history.as_context_string()

            system = self.system_prompt
            if memory_context:
                system += f"\n\nPermanent memory:\n{memory_context}"

            user_content = f"{game_context}\n\n{chat_context}\n\n{player_name} asks: {question}"

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ]

            return self._strip_markdown(self.ai_chain.ask(messages))
        except Exception as e:
            logger.error(f"[AI] Unexpected error building context or asking AI: {e}")
            return "An error occurred on my end. Try again."

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """
        Safety net in case the AI ignores the plain-text instruction --
        strips common markdown symbols so raw formatting characters never
        show up literally in game chat.
        """
        for symbol in ("**", "__", "*", "_", "###", "##", "#", "`"):
            text = text.replace(symbol, "")
        return text

    # ── Permission checking ──────────────────────────

    def is_admin(self, player_name: str) -> bool:
        """
        Checks if a player's Steam ID is in the admin list. Looks up
        their current connection info to get the Steam ID, since chat
        only gives us a display name.
        """
        if not self.admin_steam_ids:
            return False  # no admins configured -- fail closed, not open

        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return False  # can't verify identity if they're not found online

        steam_id = player.get("userid") or player.get("steamId") or ""
        return steam_id in self.admin_steam_ids

    # ── Command dispatch ──────────────────────────────

    # Commands that require admin permission -- everyone else is
    # rejected before the underlying handler ever runs.
    ADMIN_ONLY_COMMANDS = {"kick", "ban", "warn", "clearwarnings"}

    def handle(self, command: str, args: List[str], player_name: str) -> Optional[str]:
        """
        Routes a command to the right handler. Returns the text
        response to send back (in-game or Discord), or None if
        nothing should be sent.
        """
        handlers = {
            "players": self._cmd_players,
            "status": self._cmd_status,
            "kick": self._cmd_kick,
            "ban": self._cmd_ban,
            "warn": self._cmd_warn,
            "warnings": self._cmd_warnings,
            "clearwarnings": self._cmd_clear_warnings,
            "say": self._cmd_say,
            "ai": self._cmd_ai,
            "help": self._cmd_help,
        }

        handler = handlers.get(command)
        if not handler:
            return f"Unknown command. Type {self.bot_prefix}help for a list of commands."

        if command in self.ADMIN_ONLY_COMMANDS and not self.is_admin(player_name):
            logger.warning(f"[COMMANDS] {player_name} attempted admin command '{command}' without permission.")
            return "You don't have permission to use that command."

        return handler(args, player_name)

    # ── Individual command implementations ───────────

    def _cmd_players(self, args: List[str], player_name: str) -> str:
        players = self.server_api.get_players()
        if not players:
            return "No players online, or the server API is unavailable."
        names = ", ".join(p.get("name", "Unknown") for p in players)
        return f"Players online: {names}"

    def _cmd_status(self, args: List[str], player_name: str) -> str:
        context = self.server_api.build_game_context(player_name)
        return f"World Status:\n{context}"

    def _cmd_kick(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}kick <player_name> [reason]"
        target = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Kicked by admin"
        return self.moderation.kick_player(target, reason, issued_by=player_name)

    def _cmd_ban(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}ban <player_name> [reason]"
        target = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "Banned by admin"
        return self.moderation.ban_player(target, reason, issued_by=player_name)

    def _cmd_warn(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}warn <player_name> [reason]"
        target = args[0]
        reason = " ".join(args[1:]) if len(args) > 1 else "No reason given"
        return self.moderation.warn_player(target, reason, issued_by=player_name)

    def _cmd_warnings(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}warnings <player_name>"
        target = args[0]
        count = self.moderation.get_warning_count(target)
        return f"{target} has {count} warning(s)."

    def _cmd_clear_warnings(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}clearwarnings <player_name>"
        return self.moderation.clear_warnings(args[0])

    def _cmd_say(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}say <message>"
        message = " ".join(args)
        self.server_api.send_chat(message)
        return f"Sent: {message}"

    def _cmd_ai(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}ai <question>"
        question = " ".join(args)
        return self.ask_ai(player_name, question)

    def _cmd_help(self, args: List[str], player_name: str) -> str:
        p = self.bot_prefix
        return (
            f"Commands:\n"
            f"{p}players - List online players\n"
            f"{p}status - Show world status (live game data)\n"
            f"{p}kick <name> [reason] - Kick a player\n"
            f"{p}ban <name> [reason] - Ban a player\n"
            f"{p}warn <name> [reason] - Warn a player\n"
            f"{p}warnings <name> - Check a player's warning count\n"
            f"{p}clearwarnings <name> - Clear a player's warnings\n"
            f"{p}say <message> - Send a chat message\n"
            f"{p}ai <question> - Ask the AI (uses live game context)\n"
            f"{p}help - Show this help"
        )
