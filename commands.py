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
import time
from typing import List, Optional

import search

logger = logging.getLogger(__name__)


class CommandHandler:
    """
    Holds references to every subsystem (game server API, AI provider
    chain, moderation, memory) and routes commands to the right one.
    """

    def __init__(self, server_api, ai_chain, moderation, permanent_memory,
                 chat_history, bot_name: str, bot_prefix: str, admin_steam_ids: List[str] = None,
                 anti_spam_enabled: bool = True, cooldown_seconds: int = 10,
                 web_search_enabled: bool = True, youtube_search_enabled: bool = True,
                 youtube_api_key: str = None):
        self.server_api = server_api
        self.ai_chain = ai_chain
        self.moderation = moderation
        self.permanent_memory = permanent_memory
        self.chat_history = chat_history
        self.bot_name = bot_name
        self.bot_prefix = bot_prefix
        self.admin_steam_ids = set(admin_steam_ids or [])
        self.anti_spam_enabled = anti_spam_enabled
        self.cooldown_seconds = cooldown_seconds
        self.web_search_enabled = web_search_enabled
        self.youtube_search_enabled = youtube_search_enabled
        self.youtube_api_key = youtube_api_key
        self._last_command_time: dict = {}  # player_name -> timestamp of last command
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
        chat + web search results if the question needs current info)
        and sends the question through the AI provider chain.
        """
        logger.info(f"[AI] {player_name} asked: {question}")
        try:
            game_context = self.server_api.build_game_context(player_name)
            memory_context = self.permanent_memory.load()
            chat_context = self.chat_history.as_context_string()

            system = self.system_prompt
            if memory_context:
                system += f"\n\nPermanent memory:\n{memory_context}"

            search_context = ""
            if self.web_search_enabled and search.needs_current_info(question):
                logger.info(f"[SEARCH] Question looks like it needs current info, searching: {question}")
                results = search.web_search(question)
                if results:
                    search_context = f"\n\nCurrent web search results (use these for up-to-date info):\n{results}"

            user_content = f"{game_context}\n\n{chat_context}{search_context}\n\n{player_name} asks: {question}"

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

    def _check_cooldown(self, player_name: str) -> bool:
        """
        Returns True if the player is allowed to run a command right
        now. Admins are always exempt. Updates the last-used timestamp
        as a side effect when allowed.
        """
        if not self.anti_spam_enabled or self.is_admin(player_name):
            return True

        now = time.time()
        last_used = self._last_command_time.get(player_name, 0)
        if now - last_used < self.cooldown_seconds:
            return False

        self._last_command_time[player_name] = now
        return True

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
            "search": self._cmd_search,
            "youtube": self._cmd_youtube,
            "help": self._cmd_help,
        }

        handler = handlers.get(command)
        if not handler:
            return f"Unknown command. Type {self.bot_prefix}help for a list of commands."

        if command in self.ADMIN_ONLY_COMMANDS and not self.is_admin(player_name):
            logger.warning(f"[COMMANDS] {player_name} attempted admin command '{command}' without permission.")
            return "You don't have permission to use that command."

        if not self._check_cooldown(player_name):
            return None  # silently ignore spammed commands rather than adding more chat noise

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
        if self.is_admin(target):
            return "Admins cannot be kicked or banned through this command."
        reason = " ".join(args[1:]) if len(args) > 1 else "Kicked by admin"
        return self.moderation.kick_player(target, reason, issued_by=player_name)

    def _cmd_ban(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}ban <player_name> [reason]"
        target = args[0]
        if self.is_admin(target):
            return "Admins cannot be kicked or banned through this command."
        reason = " ".join(args[1:]) if len(args) > 1 else "Banned by admin"
        return self.moderation.ban_player(target, reason, issued_by=player_name)

    def _cmd_warn(self, args: List[str], player_name: str) -> str:
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}warn <player_name> [reason]"
        target = args[0]
        if self.is_admin(target):
            return "Admins cannot be warned through this command."
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
            return f"Usage: {self.bot_prefix}ai <question>  (or: {self.bot_prefix}ai remember <note>)"

        if args[0].lower() == "remember":
            if len(args) < 2:
                return f"Usage: {self.bot_prefix}ai remember <note to save>"
            note = " ".join(args[1:])
            self.permanent_memory.append(f"{player_name}: {note}")
            return "Got it, I'll remember that."

        question = " ".join(args)
        return self.ask_ai(player_name, question)

    def _cmd_search(self, args: List[str], player_name: str) -> str:
        if not self.web_search_enabled:
            return "Web search is currently disabled."
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}search <query>"
        query = " ".join(args)
        results = search.web_search(query)
        if not results:
            return f"No results found for '{query}'."
        # Keep this short for in-game chat -- just the first result line
        first_line = results.split("\n")[0]
        return first_line[:300]

    def _cmd_youtube(self, args: List[str], player_name: str) -> str:
        if not self.youtube_search_enabled:
            return "YouTube search is currently disabled."
        if len(args) < 1:
            return f"Usage: {self.bot_prefix}youtube <query>"
        query = " ".join(args)
        result = search.youtube_search(query, api_key=self.youtube_api_key)
        if not result:
            return f"No video found for '{query}'."
        return result

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
            f"{p}ai remember <note> - Save a permanent note for the AI\n"
            f"{p}search <query> - Search the web\n"
            f"{p}youtube <query> - Find a YouTube video\n"
            f"{p}help - Show this help"
        )
