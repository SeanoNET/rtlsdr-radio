"""
Logitech Media Server (LMS/Squeezebox) service.
Uses the JSON-RPC API to discover and control players.
"""
import asyncio
import aiohttp
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LMSPlayer:
    """Represents an LMS player."""
    id: str  # MAC address
    name: str
    model: str
    ip_address: str
    is_powered: bool
    is_playing: bool
    volume: float  # 0.0 - 1.0
    connected: bool


class LMSService:
    def __init__(self, server_host: str = "localhost", server_port: int = 9000):
        self._server_host = server_host
        self._server_port = server_port
        self._base_url = f"http://{server_host}:{server_port}/jsonrpc.js"
        self._players: Dict[str, LMSPlayer] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def _request(self, player_id: str, command: List) -> Optional[dict]:
        """Send a JSON-RPC request to LMS."""
        session = await self._get_session()
        
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [player_id, command]
        }
        
        try:
            async with session.post(self._base_url, json=payload) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"LMS request failed: {resp.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"LMS connection error: {e}")
            return None
    
    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def discover_players(self) -> List[LMSPlayer]:
        """Discover all players connected to LMS."""
        result = await self._request("", ["players", "0", "100"])
        
        if not result or "result" not in result:
            logger.warning("Failed to discover LMS players")
            return []
        
        players_data = result["result"].get("players_loop", [])
        self._players.clear()
        
        for p in players_data:
            player_id = p.get("playerid", "")
            
            # Get detailed status for each player
            status = await self._get_player_status(player_id)
            
            player = LMSPlayer(
                id=player_id,
                name=p.get("name", "Unknown"),
                model=p.get("model", "Unknown"),
                ip_address=p.get("ip", "").split(":")[0],  # Remove port
                is_powered=p.get("power", 0) == 1,
                is_playing=status.get("mode", "") == "play",
                volume=status.get("mixer volume", 50) / 100.0,
                connected=p.get("connected", 0) == 1,
            )
            self._players[player_id] = player
        
        logger.info(f"Discovered {len(self._players)} LMS players")
        return list(self._players.values())
    
    async def _get_player_status(self, player_id: str) -> dict:
        """Get detailed status for a player."""
        result = await self._request(player_id, ["status", "-", "1"])
        if result and "result" in result:
            return result["result"]
        return {}
    
    def get_players(self) -> List[LMSPlayer]:
        """Get cached list of players."""
        return list(self._players.values())
    
    def get_player(self, player_id: str) -> Optional[LMSPlayer]:
        """Get a specific player by ID."""
        return self._players.get(player_id)
    
    async def refresh_player(self, player_id: str) -> Optional[LMSPlayer]:
        """Refresh status for a specific player."""
        player = self._players.get(player_id)
        if not player:
            return None
        
        status = await self._get_player_status(player_id)
        player.is_powered = status.get("power", 0) == 1
        player.is_playing = status.get("mode", "") == "play"
        player.volume = status.get("mixer volume", 50) / 100.0
        
        return player
    
    async def play_url(self, player_id: str, url: str, title: str = "RTL-SDR Radio") -> bool:
        """Play a URL on an LMS player."""
        player = self._players.get(player_id)
        if not player:
            logger.error(f"Player not found: {player_id}")
            return False
        
        # Power on if needed
        if not player.is_powered:
            await self._request(player_id, ["power", "1"])
        
        # Clear playlist and play URL
        result = await self._request(player_id, ["playlist", "play", url, title])
        
        if result:
            player.is_playing = True
            logger.info(f"Started playback on LMS player: {player.name}")
            return True
        return False
    
    async def stop(self, player_id: str) -> bool:
        """Stop playback on a player."""
        result = await self._request(player_id, ["stop"])
        if result:
            player = self._players.get(player_id)
            if player:
                player.is_playing = False
            return True
        return False
    
    async def pause(self, player_id: str) -> bool:
        """Pause playback on a player."""
        result = await self._request(player_id, ["pause", "1"])
        if result:
            player = self._players.get(player_id)
            if player:
                player.is_playing = False
            return True
        return False
    
    async def resume(self, player_id: str) -> bool:
        """Resume playback on a player."""
        result = await self._request(player_id, ["pause", "0"])
        if result:
            player = self._players.get(player_id)
            if player:
                player.is_playing = True
            return True
        return False
    
    async def set_volume(self, player_id: str, volume: float) -> bool:
        """Set volume for a player (0.0 - 1.0)."""
        volume_int = int(volume * 100)
        result = await self._request(player_id, ["mixer", "volume", str(volume_int)])
        if result:
            player = self._players.get(player_id)
            if player:
                player.volume = volume
            return True
        return False
    
    async def get_volume(self, player_id: str) -> Optional[float]:
        """Get current volume for a player."""
        player = self._players.get(player_id)
        if player:
            await self.refresh_player(player_id)
            return player.volume
        return None
    
    async def power_on(self, player_id: str) -> bool:
        """Power on a player."""
        result = await self._request(player_id, ["power", "1"])
        if result:
            player = self._players.get(player_id)
            if player:
                player.is_powered = True
            return True
        return False
    
    async def power_off(self, player_id: str) -> bool:
        """Power off a player."""
        result = await self._request(player_id, ["power", "0"])
        if result:
            player = self._players.get(player_id)
            if player:
                player.is_powered = False
            return True
        return False
