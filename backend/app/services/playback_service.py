"""
Playback service - orchestrates tuning and streaming to Chromecast or LMS.
"""
import asyncio
import logging
from typing import Optional
from aiohttp import web
import socket

from app.models import PlaybackState, PlaybackStatus, Modulation, SpeakerType
from app.services.tuner_service import TunerService
from app.services.chromecast_service import ChromecastService
from app.services.lms_service import LMSService

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """Get the local IP address of this machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class PlaybackService:
    def __init__(
        self,
        tuner_service: TunerService,
        chromecast_service: ChromecastService,
        lms_service: LMSService,
        stream_port: int = 8089,
        external_stream_url: str = None,
    ):
        self._tuner = tuner_service
        self._chromecast = chromecast_service
        self._lms = lms_service
        self._stream_port = stream_port
        self._external_stream_url = external_stream_url
        
        self._state = PlaybackState.STOPPED
        self._current_device_id: Optional[str] = None
        self._current_device_type: Optional[SpeakerType] = None
        self._stream_server: Optional[web.AppRunner] = None
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> PlaybackState:
        return self._state
    
    @property
    def stream_url(self) -> str:
        """Get the internal URL where the audio stream is available."""
        local_ip = get_local_ip()
        return f"http://{local_ip}:{self._stream_port}/stream.mp3"
    
    @property
    def chromecast_stream_url(self) -> str:
        """Get the URL for Chromecast (external HTTPS if configured, otherwise internal)."""
        if self._external_stream_url:
            return self._external_stream_url
        return self.stream_url
    
    def get_status(self) -> PlaybackStatus:
        """Get current playback status."""
        tuner_status = self._tuner.get_status()
        device_name = None
        
        if self._current_device_id and self._current_device_type:
            if self._current_device_type == SpeakerType.CHROMECAST:
                device_info = self._chromecast.get_device_info(self._current_device_id)
                if device_info:
                    device_name = device_info.name
            else:
                player = self._lms.get_player(self._current_device_id)
                if player:
                    device_name = player.name
        
        return PlaybackStatus(
            state=self._state,
            device_id=self._current_device_id,
            device_type=self._current_device_type,
            device_name=device_name,
            frequency=tuner_status.frequency,
            modulation=tuner_status.modulation,
            stream_url=self.stream_url if self._state == PlaybackState.PLAYING else None,
        )
    
    async def _start_stream_server(self):
        """Start the HTTP server that serves the audio stream."""
        if self._stream_server:
            return
        
        app = web.Application()
        app.router.add_get("/stream.mp3", self._handle_stream_request)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, "0.0.0.0", self._stream_port)
        await site.start()
        
        self._stream_server = runner
        logger.info(f"Stream server started on port {self._stream_port}")
    
    async def _stop_stream_server(self):
        """Stop the HTTP stream server."""
        if self._stream_server:
            await self._stream_server.cleanup()
            self._stream_server = None
            logger.info("Stream server stopped")
    
    async def _handle_stream_request(self, request: web.Request) -> web.StreamResponse:
        """Handle incoming stream requests from Chromecast or LMS."""
        logger.info(f"Stream request from {request.remote}")
        
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "audio/mpeg",
                "Cache-Control": "no-cache, no-store",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
            },
        )
        await response.prepare(request)
        
        try:
            while self._state == PlaybackState.PLAYING:
                chunk = await self._tuner.read_audio_chunk(8192)
                if chunk:
                    await response.write(chunk)
                else:
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        except ConnectionResetError:
            logger.info("Stream client disconnected")
        except Exception as e:
            logger.error(f"Stream error: {e}")
        
        return response
    
    async def start(
        self,
        device_id: str,
        device_type: SpeakerType,
        frequency: float,
        modulation: Modulation = Modulation.WFM,
    ) -> bool:
        """Start playback: tune and cast to device."""
        async with self._lock:
            logger.info(f"Starting playback: {frequency} MHz to {device_type.value} device {device_id}")
            
            # Verify device exists
            if device_type == SpeakerType.CHROMECAST:
                device = self._chromecast.get_device(device_id)
                if not device:
                    logger.error(f"Chromecast device not found: {device_id}")
                    return False
            else:
                device = self._lms.get_player(device_id)
                if not device:
                    logger.error(f"LMS player not found: {device_id}")
                    return False
            
            self._state = PlaybackState.BUFFERING
            
            # Tune the SDR
            if not await self._tuner.tune(frequency, modulation):
                logger.error("Failed to tune")
                self._state = PlaybackState.STOPPED
                return False
            
            # Start stream server
            await self._start_stream_server()
            
            # Give the tuner a moment to buffer
            await asyncio.sleep(1)
            
            # Start casting based on device type
            if device_type == SpeakerType.CHROMECAST:
                cast_url = self.chromecast_stream_url
                logger.info(f"Casting to Chromecast using URL: {cast_url}")
                if not await self._chromecast.play_url(device_id, cast_url):
                    logger.error("Failed to start Chromecast casting")
                    await self._tuner.stop()
                    self._state = PlaybackState.STOPPED
                    return False
            else:
                if not await self._lms.play_url(device_id, self.stream_url, "RTL-SDR Radio"):
                    logger.error("Failed to start LMS playback")
                    await self._tuner.stop()
                    self._state = PlaybackState.STOPPED
                    return False
            
            self._current_device_id = device_id
            self._current_device_type = device_type
            self._state = PlaybackState.PLAYING
            
            device_name = device.name if hasattr(device, 'name') else device_id
            logger.info(f"Playback started: {frequency} MHz on {device_name}")
            return True
    
    async def stop(self) -> bool:
        """Stop playback completely."""
        async with self._lock:
            logger.info("Stopping playback")
            
            # Stop device playback
            if self._current_device_id and self._current_device_type:
                if self._current_device_type == SpeakerType.CHROMECAST:
                    await self._chromecast.stop_playback(self._current_device_id)
                else:
                    await self._lms.stop(self._current_device_id)
            
            # Stop tuner
            await self._tuner.stop()
            
            # Stop stream server
            await self._stop_stream_server()
            
            self._state = PlaybackState.STOPPED
            self._current_device_id = None
            self._current_device_type = None
            
            return True
    
    async def pause(self) -> bool:
        """Pause playback."""
        async with self._lock:
            if self._state != PlaybackState.PLAYING:
                return False
            
            if self._current_device_id and self._current_device_type:
                if self._current_device_type == SpeakerType.CHROMECAST:
                    await self._chromecast.pause_playback(self._current_device_id)
                else:
                    await self._lms.pause(self._current_device_id)
            
            self._state = PlaybackState.PAUSED
            return True
    
    async def resume(self) -> bool:
        """Resume paused playback."""
        async with self._lock:
            if self._state != PlaybackState.PAUSED:
                return False
            
            if self._current_device_id and self._current_device_type:
                if self._current_device_type == SpeakerType.CHROMECAST:
                    await self._chromecast.play_url(self._current_device_id, self.stream_url)
                else:
                    await self._lms.resume(self._current_device_id)
            
            self._state = PlaybackState.PLAYING
            return True
    
    async def change_frequency(
        self,
        frequency: float,
        modulation: Modulation = Modulation.WFM,
    ) -> bool:
        """Change frequency while maintaining playback."""
        async with self._lock:
            if self._state not in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
                return False
            
            # Re-tune (this will restart the rtl_fm process)
            return await self._tuner.tune(frequency, modulation)
