"""
moderation.py
------------------------------------------------
Handles the warning/kick/ban system: persists warnings and bans to
JSON files, and includes actual escalation logic (e.g. reaching a
warning limit triggers an automatic kick) -- something that existed
as separate pieces in the original bot but wasn't fully wired together.
"""

import os
import json
import time
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ModerationSystem:
    """
    Tracks warnings and bans per player (keyed by player ID, not
    display name, since names can change but IDs don't) and applies
    kick/ban actions through the game server API when needed.
    """

    def __init__(self, base_dir: str, server_api, max_warnings_before_kick: int = 3):
        self.warnings_file = os.path.join(base_dir, "warnings.json")
        self.bans_file = os.path.join(base_dir, "bans.json")
        self.warning_log_file = os.path.join(base_dir, "warning_log.txt")
        self.ban_log_file = os.path.join(base_dir, "ban_log.txt")
        self.server_api = server_api
        self.max_warnings_before_kick = max_warnings_before_kick

        self.warnings = self._load_json(self.warnings_file)
        self.bans = self._load_json(self.bans_file)

    # ── Persistence helpers ──────────────────────────

    def _load_json(self, path: str) -> Dict:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"[MODERATION] Failed to load {path}: {e}")
            return {}

    def _save_json(self, path: str, data: Dict):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"[MODERATION] Failed to save {path}: {e}")

    def _append_log(self, path: str, line: str):
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat()} - {line}\n")
        except OSError as e:
            logger.error(f"[MODERATION] Failed to write log {path}: {e}")

    # ── Warnings ──────────────────────────────────────

    def warn_player(self, player_name: str, reason: str, issued_by: str) -> str:
        """
        Issues a warning. If the player has now reached the warning
        limit, automatically kicks them and resets their warning count.
        Returns a message describing what happened.
        """
        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return f"Player '{player_name}' not found online."

        player_id = player.get("userid") or player.get("steamId") or player_name

        entry = self.warnings.get(player_id, {"name": player_name, "count": 0, "reasons": []})
        entry["count"] += 1
        entry["name"] = player_name  # keep display name up to date
        entry["reasons"].append({"reason": reason, "by": issued_by, "time": datetime.now().isoformat()})
        self.warnings[player_id] = entry
        self._save_json(self.warnings_file, self.warnings)
        self._append_log(self.warning_log_file, f"{player_name} warned by {issued_by}: {reason} (count: {entry['count']})")

        if entry["count"] >= self.max_warnings_before_kick:
            # Reset count after the auto-kick so it's not an instant re-kick
            entry["count"] = 0
            self.warnings[player_id] = entry
            self._save_json(self.warnings_file, self.warnings)

            kicked = self.server_api.kick_player(player_id, reason=f"Reached {self.max_warnings_before_kick} warnings")
            self._append_log(self.warning_log_file, f"{player_name} auto-kicked after reaching warning limit")

            if kicked:
                return f"{player_name} warned and automatically kicked (reached {self.max_warnings_before_kick} warnings)."
            return f"{player_name} warned (reached limit, but kick failed to send)."

        remaining = self.max_warnings_before_kick - entry["count"]
        return f"{player_name} warned: {reason}. ({entry['count']}/{self.max_warnings_before_kick} warnings, {remaining} until auto-kick)"

    def get_warning_count(self, player_name: str) -> int:
        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return 0
        player_id = player.get("userid") or player.get("steamId") or player_name
        return self.warnings.get(player_id, {}).get("count", 0)

    def clear_warnings(self, player_name: str) -> str:
        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return f"Player '{player_name}' not found online."
        player_id = player.get("userid") or player.get("steamId") or player_name
        if player_id in self.warnings:
            del self.warnings[player_id]
            self._save_json(self.warnings_file, self.warnings)
        return f"Cleared all warnings for {player_name}."

    # ── Kicks ─────────────────────────────────────────

    def kick_player(self, player_name: str, reason: str, issued_by: str) -> str:
        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return f"Player '{player_name}' not found online."

        player_id = player.get("userid") or player.get("steamId")
        if not player_id:
            return f"Could not determine player ID for '{player_name}'."

        if self.server_api.kick_player(player_id, reason):
            self._append_log(self.warning_log_file, f"{player_name} kicked by {issued_by}: {reason}")
            return f"Kicked {player_name}: {reason}"
        return f"Failed to kick {player_name}."

    # ── Bans ──────────────────────────────────────────

    def ban_player(self, player_name: str, reason: str, issued_by: str, duration_minutes: Optional[int] = None) -> str:
        """
        Bans a player. If duration_minutes is given, this is a
        temporary ban that expires automatically (checked via
        is_banned()); otherwise it's permanent.
        """
        player = self.server_api.find_player_by_name(player_name)
        if not player:
            return f"Player '{player_name}' not found online."

        player_id = player.get("userid") or player.get("steamId")
        if not player_id:
            return f"Could not determine player ID for '{player_name}'."

        if not self.server_api.ban_player(player_id, reason):
            return f"Failed to ban {player_name}."

        expires_at = None
        if duration_minutes:
            expires_at = time.time() + (duration_minutes * 60)

        self.bans[player_id] = {
            "name": player_name,
            "reason": reason,
            "by": issued_by,
            "banned_at": datetime.now().isoformat(),
            "expires_at": expires_at,
        }
        self._save_json(self.bans_file, self.bans)

        duration_text = f"for {duration_minutes} minutes" if duration_minutes else "permanently"
        self._append_log(self.ban_log_file, f"{player_name} banned by {issued_by} {duration_text}: {reason}")
        return f"Banned {player_name} {duration_text}: {reason}"

    def is_banned(self, player_id: str) -> bool:
        """
        Checks if a player is currently banned, respecting temp-ban
        expiry. Note: this only tracks state locally -- it does not
        automatically un-ban on the server side when a temp ban
        expires. Call unban_player() to actually lift it.
        """
        entry = self.bans.get(player_id)
        if not entry:
            return False
        if entry.get("expires_at") and time.time() > entry["expires_at"]:
            return False  # expired
        return True

    def get_expired_temp_bans(self) -> Dict:
        """Returns bans whose expiry time has passed but are still on record."""
        now = time.time()
        return {
            pid: entry for pid, entry in self.bans.items()
            if entry.get("expires_at") and now > entry["expires_at"]
        }
