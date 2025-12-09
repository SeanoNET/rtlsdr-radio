"""
Chromecast discovery and control service.
"""
import asyncio
import pychromecast
from pychromecast.controllers.media import MediaController
from typing import Dict, Optional
import logging
import hashlib

from app.models import ChromecastDevice

logger = logging.getLogger(__name__)


class ChromecastService:
    def __init__(self):
        self._devices: Dict[str, pychromecast.Chromecast] = {}
        self._browser = None
        self._discovery_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def _generate_device_id(self, cast: pychromecast.Chromecast) -> str:
        """Generate a stable ID for a Chromecast device."""
        unique_str = f"{cast.uuid}"
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]
    
    async def start_discovery(self):
        """Start discovering Chromecast devices on the network."""
        logger.info("Starting Chromecast discovery...")
        
        def discovery_callback(chromecast: pychromecast.Chromecast):
            device_id = self._generate_device_id(chromecast)
            chromecast.wait()
            self._devices[device_id] = chromecast
            logger.info(f"Discovered Chromecast: {chromecast.name} ({device_id})")
        
        def remove_callback(uuid, name):
            # Find and remove device by UUID
            for device_id, cast in list(self._devices.items()):
                if str(cast.uuid) == str(uuid):
                    del self._devices[device_id]
                    logger.info(f"Removed Chromecast: {name}")
                    break
        
        # Run discovery in thread pool to not block
        loop = asyncio.get_event_loop()
        self._browser = await loop.run_in_executor(
            None,
            lambda: pychromecast.get_chromecasts(
                blocking=False,
                callback=discovery_callback,
            )
        )
    
    async def stop_discovery(self):
        """Stop Chromecast discovery."""
        if self._browser:
            self._browser[1].stop_discovery()
        
        # Disconnect all devices
        for cast in self._devices.values():
            cast.disconnect()
        
        self._devices.clear()
        logger.info("Chromecast discovery stopped")
    
    async def refresh_devices(self):
        """Manually refresh device list."""
        await self.stop_discovery()
        await self.start_discovery()
        # Give it a moment to discover
        await asyncio.sleep(3)
    
    def get_devices(self) -> list[ChromecastDevice]:
        """Get all discovered Chromecast devices."""
        devices = []
        for device_id, cast in self._devices.items():
            try:
                status = cast.status
                devices.append(ChromecastDevice(
                    id=device_id,
                    name=cast.name,
                    model=cast.model_name or "Unknown",
                    ip_address=str(cast.host),
                    port=cast.port,
                    volume=status.volume_level if status else 0.5,
                    is_muted=status.volume_muted if status else False,
                    is_idle=cast.is_idle,
                ))
            except Exception as e:
                logger.warning(f"Error getting status for {cast.name}: {e}")
        
        return devices
    
    def get_device(self, device_id: str) -> Optional[pychromecast.Chromecast]:
        """Get a specific Chromecast device by ID."""
        return self._devices.get(device_id)
    
    def get_device_info(self, device_id: str) -> Optional[ChromecastDevice]:
        """Get device info by ID."""
        cast = self._devices.get(device_id)
        if not cast:
            return None
        
        status = cast.status
        return ChromecastDevice(
            id=device_id,
            name=cast.name,
            model=cast.model_name or "Unknown",
            ip_address=str(cast.host),
            port=cast.port,
            volume=status.volume_level if status else 0.5,
            is_muted=status.volume_muted if status else False,
            is_idle=cast.is_idle,
        )
    
    async def set_volume(self, device_id: str, volume: float) -> bool:
        """Set volume for a device (0.0 - 1.0)."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cast.set_volume, volume)
        return True
    
    async def get_volume(self, device_id: str) -> Optional[float]:
        """Get current volume for a device."""
        cast = self._devices.get(device_id)
        if not cast or not cast.status:
            return None
        return cast.status.volume_level
    
    async def set_mute(self, device_id: str, muted: bool) -> bool:
        """Set mute state for a device."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cast.set_volume_muted, muted)
        return True
    
    async def play_url(self, device_id: str, url: str, content_type: str = "audio/mp3") -> bool:
        """Play a URL on a Chromecast device."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        
        def _play():
            mc = cast.media_controller
            mc.play_media(url, content_type, title="RTL-SDR Radio", stream_type="LIVE")
            mc.block_until_active()
        
        await loop.run_in_executor(None, _play)
        return True
    
    async def stop_playback(self, device_id: str) -> bool:
        """Stop playback on a device."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cast.media_controller.stop)
        return True
    
    async def pause_playback(self, device_id: str) -> bool:
        """Pause playback on a device."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cast.media_controller.pause)
        return True
    
    async def resume_playback(self, device_id: str) -> bool:
        """Resume playback on a device."""
        cast = self._devices.get(device_id)
        if not cast:
            return False
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, cast.media_controller.play)
        return True
