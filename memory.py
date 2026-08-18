"""
memory.py
------------------------------------------------
Two kinds of memory the AI can draw on:

1. Permanent memory -- persistent notes stored in a text file, meant
   for things the bot should always remember (server rules, lore,
   admin preferences, etc.). Edited manually or added to via commands.

2. Recent chat history -- a short rolling buffer of the last N chat
   messages, kept in memory only (not saved to disk), giving the AI
   short-term conversational context so replies don't feel completely
   disconnected from what was just said.
"""

import os
import logging
from collections import deque
from typing import List, Tuple

logger = logging.getLogger(__name__)


class PermanentMemory:
    """Persistent, file-backed notes the AI includes in its context."""

    def __init__(self, base_dir: str):
        self.memory_file = os.path.join(base_dir, "memory.txt")

    def load(self) -> str:
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    return f.read()
            return ""
        except OSError as e:
            logger.error(f"[MEMORY] Load failed: {e}")
            return ""

    def save(self, content: str):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            logger.error(f"[MEMORY] Save failed: {e}")

    def append(self, note: str):
        """Adds a new line to permanent memory without overwriting existing notes."""
        current = self.load()
        updated = f"{current}\n{note}".strip() if current else note
        self.save(updated)


class ChatHistory:
    """
    Rolling buffer of the most recent chat messages, used to give the
    AI short-term context. Not persisted to disk -- resets each time
    the bot restarts, by design (this is short-term memory only;
    PermanentMemory is for things that should survive restarts).
    """

    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)

    def add(self, player_name: str, message: str):
        self._buffer.append((player_name, message))

    def recent(self, count: int = 10) -> List[Tuple[str, str]]:
        """Returns the most recent `count` messages, oldest first."""
        items = list(self._buffer)
        return items[-count:] if count < len(items) else items

    def as_context_string(self, count: int = 10) -> str:
        """Formats recent history as a text block for the AI's context."""
        recent = self.recent(count)
        if not recent:
            return ""
        lines = "\n".join(f"  {name}: {msg}" for name, msg in recent)
        return f"Recent chat:\n{lines}"
