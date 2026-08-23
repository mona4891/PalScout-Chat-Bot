"""
palworld_api.py
------------------------------------------------
Wraps the game server's REST API (default port 8212) into a clean
class other parts of the bot can call. Handles connecting, sending
chat, looking up players, kicking/banning, and building a live
game-state summary for the AI to use.
"""

import logging
from typing import Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class GameServerAPI:
    """REST API wrapper for the dedicated game server."""

    def __init__(self, host: str, port: int, admin_password: str, bot_name: str = None):
        self.base_url = f"http://{host}:{port}"
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth("admin", admin_password)
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.connected = False
        # Since Palworld's /announce shows all bot messages under the
        # generic "SYSTEM" sender, prefixing with the bot's name makes
        # its responses visually distinguishable from other server
        # announcements (join/leave messages, etc.) in chat.
        self.chat_prefix = f"[{bot_name}] " if bot_name else ""

    def test_connection(self) -> bool:
        """Confirms the REST API is reachable and credentials are valid."""
        try:
            resp = self.session.get(f"{self.base_url}/v1/api/info", timeout=5)
            self.connected = resp.status_code == 200
            if self.connected:
                logger.info("[SERVER] Connected and authenticated!")
            else:
                logger.error(f"[SERVER] API returned status {resp.status_code}")
            return self.connected
        except requests.RequestException as e:
            logger.error(f"[SERVER] Connection failed: {e}")
            self.connected = False
            return False

    def send_chat(self, message: str) -> bool:
        """Broadcasts a message into the game's chat, prefixed with the
        bot's name so it's visually distinguishable from other SYSTEM
        messages (Palworld labels all /announce messages as "SYSTEM")."""
        full_message = f"{self.chat_prefix}{message}"
        try:
            resp = self.session.post(
                f"{self.base_url}/v1/api/announce",
                json={"message": full_message[:400]},
                timeout=5,
            )
            if resp.status_code == 200:
                logger.info(f"[BOT] {full_message}")
                return True
            logger.error(f"[SERVER] Send failed: status {resp.status_code}")
            return False
        except requests.RequestException as e:
            logger.error(f"[SERVER] Send failed: {e}")
            return False

    def get_players(self) -> List[Dict]:
        """Returns the list of currently connected players."""
        try:
            resp = self.session.get(f"{self.base_url}/v1/api/players", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # Some server versions wrap the list in a "players" key,
                # others return it directly -- handle both.
                if isinstance(data, dict):
                    return data.get("players", [])
                return data
            return []
        except requests.RequestException as e:
            logger.error(f"[SERVER] Get players failed: {e}")
            return []

    def get_game_data(self) -> Dict:
        """
        Returns a full live world snapshot: every player and creature,
        with health, level, and position. This is the data source for
        grounding AI responses in real game state.
        """
        try:
            resp = self.session.get(f"{self.base_url}/v1/api/game-data", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            logger.error(f"[SERVER] game-data returned status {resp.status_code}")
            return {}
        except requests.RequestException as e:
            logger.error(f"[SERVER] Get game data failed: {e}")
            return {}

    def find_player_by_name(self, name: str) -> Optional[Dict]:
        """
        Looks up a connected player by display name. Needed because
        kick/ban require a numeric player ID, not a display name.
        """
        for p in self.get_players():
            if p.get("name", "").lower() == name.lower():
                return p
        return None

    def kick_player(self, player_id: str, reason: str = "") -> bool:
        """Kicks a player by their numeric ID."""
        try:
            payload = {"userid": player_id}
            if reason:
                payload["message"] = reason
            resp = self.session.post(f"{self.base_url}/v1/api/kick", json=payload, timeout=5)
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.error(f"[SERVER] Kick failed: {e}")
            return False

    def ban_player(self, player_id: str, reason: str = "") -> bool:
        """Bans a player by their numeric ID."""
        try:
            payload = {"userid": player_id}
            if reason:
                payload["message"] = reason
            resp = self.session.post(f"{self.base_url}/v1/api/ban", json=payload, timeout=5)
            return resp.status_code == 200
        except requests.RequestException as e:
            logger.error(f"[SERVER] Ban failed: {e}")
            return False

    def build_game_context(self, asking_player_name: str = None) -> str:
        """
        Builds a short text summary of live world state for the AI to
        reference -- online players (with HP/level/guild/position) and
        any creatures within roughly 100m of the asking player.
        """
        game_data = self.get_game_data()
        if not game_data:
            return "Game state unavailable."

        actors = game_data.get("ActorData", [])
        players = [a for a in actors if a.get("UnitType") == "Player"]
        creatures = [a for a in actors if a.get("UnitType") and a.get("UnitType") != "Player"]

        player_lines = []
        for p in players:
            name = p.get("NickName", "Unknown")
            level = p.get("level", 1)
            hp = p.get("HP", 0)
            max_hp = p.get("MaxHP", 100)
            guild = p.get("GuildName", "No Guild")
            loc = f"({p.get('LocationX', 0):.0f}, {p.get('LocationY', 0):.0f})"
            player_lines.append(f"  {name} — Lv{level}, HP:{hp}/{max_hp}, Guild:{guild}, Pos:{loc}")

        # Find the asking player's position for distance calculations
        asking_pos = None
        if asking_player_name:
            for p in players:
                if p.get("NickName", "").lower() == asking_player_name.lower():
                    asking_pos = (p.get("LocationX", 0), p.get("LocationY", 0), p.get("LocationZ", 0))
                    break

        creature_lines = []
        if asking_pos:
            for c in creatures[:20]:
                dx = c.get("LocationX", 0) - asking_pos[0]
                dy = c.get("LocationY", 0) - asking_pos[1]
                dz = c.get("LocationZ", 0) - asking_pos[2]
                distance_m = ((dx**2 + dy**2 + dz**2) ** 0.5) / 100

                if distance_m < 100:
                    c_name = c.get("NickName") or c.get("Type", "Unknown")
                    level = c.get("level", 1)
                    hp = c.get("HP", 0)
                    max_hp = c.get("MaxHP", 100)
                    creature_lines.append(f"  {c_name} — Lv{level}, HP:{hp}/{max_hp}, ~{distance_m:.0f}m away")

        # InGameTime can come back as a string on some server versions --
        # handle both cases rather than assuming it's always a number.
        in_game_time = game_data.get("InGameTime", 0)
        try:
            time_display = f"{float(in_game_time):.1f}h"
        except (ValueError, TypeError):
            time_display = f"{in_game_time}h"

        context_parts = [
            f"World: Day {game_data.get('InGameDays', 0)}, Time: {time_display}",
            f"Players Online: {len(players)}",
            "\n".join(player_lines) if player_lines else "  No players online",
        ]

        if creature_lines:
            context_parts.append(f"Nearby creatures ({len(creature_lines)} within 100m):")
            context_parts.extend(creature_lines)

        return "\n".join(context_parts)
