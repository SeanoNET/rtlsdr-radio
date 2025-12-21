"""
Playback service - orchestrates tuning and streaming to Chromecast.
Supports both FM (via rtl_fm) and DAB+ (via welle-cli) radio modes.
"""

import asyncio
import logging
import socket
from typing import Optional

from aiohttp import web

from app.models import Modulation, PlaybackState, PlaybackStatus, RadioMode
from app.services.chromecast_service import ChromecastService
from app.services.dab_service import DabService
from app.services.tuner_service import TunerService

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
        dab_service: DabService,
        chromecast_service: ChromecastService,
        stream_port: int = 8089,
        external_stream_url: str = None,
    ):
        self._tuner = tuner_service
        self._dab = dab_service
        self._chromecast = chromecast_service
        self._stream_port = stream_port
        self._external_stream_url = external_stream_url

        self._state = PlaybackState.STOPPED
        self._radio_mode = RadioMode.IDLE
        self._current_device_id: Optional[str] = None
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
        device_name = None

        if self._current_device_id:
            device_info = self._chromecast.get_device_info(self._current_device_id)
            if device_info:
                device_name = device_info.name

        # Get status based on current radio mode
        if self._radio_mode == RadioMode.FM:
            tuner_status = self._tuner.get_status()
            return PlaybackStatus(
                state=self._state,
                radio_mode=self._radio_mode,
                device_id=self._current_device_id,
                device_name=device_name,
                frequency=tuner_status.frequency,
                modulation=tuner_status.modulation,
                stream_url=self.stream_url
                if self._state == PlaybackState.PLAYING
                else None,
            )
        elif self._radio_mode == RadioMode.DAB:
            dab_status = self._dab.get_status()
            return PlaybackStatus(
                state=self._state,
                radio_mode=self._radio_mode,
                device_id=self._current_device_id,
                device_name=device_name,
                dab_channel=dab_status.channel,
                dab_program=dab_status.program,
                dab_service_id=dab_status.service_id,
                stream_url=self.stream_url
                if self._state == PlaybackState.PLAYING
                else None,
            )
        else:
            return PlaybackStatus(
                state=self._state,
                radio_mode=self._radio_mode,
                device_id=self._current_device_id,
                device_name=device_name,
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
        """Handle incoming stream requests from Chromecast."""
        logger.info(f"Stream request from {request.remote} (mode: {self._radio_mode.value})")

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
                # Read from appropriate source based on radio mode
                if self._radio_mode == RadioMode.FM:
                    chunk = await self._tuner.read_audio_chunk(8192)
                elif self._radio_mode == RadioMode.DAB:
                    chunk = await self._dab.read_audio_chunk(8192)
                else:
                    break

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
        # FM parameters
        frequency: Optional[float] = None,
        modulation: Modulation = Modulation.WFM,
        # DAB parameters
        dab_channel: Optional[str] = None,
        dab_program: Optional[str] = None,
        dab_service_id: Optional[int] = None,
    ) -> bool:
        """
        Start playback: tune and cast to Chromecast device.

        Supports both FM and DAB+ modes. If dab_channel is provided, uses DAB+ mode.
        Otherwise, uses FM mode with the provided frequency.
        """
        async with self._lock:
            # Determine mode based on parameters
            if dab_channel:
                return await self._start_dab(
                    device_id, dab_channel, dab_program, dab_service_id
                )
            elif frequency is not None:
                return await self._start_fm(device_id, frequency, modulation)
            else:
                logger.error("No frequency or DAB channel provided")
                return False

    async def _start_fm(
        self,
        device_id: str,
        frequency: float,
        modulation: Modulation = Modulation.WFM,
    ) -> bool:
        """Start FM playback."""
        logger.info(
            f"Starting FM playback: {frequency} MHz to device {device_id}"
        )

        # Verify device exists
        device = self._chromecast.get_device(device_id)
        if not device:
            logger.error(f"Chromecast device not found: {device_id}")
            return False

        # Stop DAB if running (single dongle constraint)
        if self._radio_mode == RadioMode.DAB:
            await self._dab.stop()

        self._state = PlaybackState.BUFFERING
        self._radio_mode = RadioMode.FM

        # Tune the SDR
        if not await self._tuner.tune(frequency, modulation):
            logger.error("Failed to tune FM")
            self._state = PlaybackState.STOPPED
            self._radio_mode = RadioMode.IDLE
            return False

        # Start stream server
        await self._start_stream_server()

        # Give the tuner a moment to buffer
        await asyncio.sleep(1)

        # Start casting
        cast_url = self.chromecast_stream_url
        logger.info(f"Casting to Chromecast using URL: {cast_url}")
        if not await self._chromecast.play_url(device_id, cast_url):
            logger.error("Failed to start Chromecast casting")
            await self._tuner.stop()
            self._state = PlaybackState.STOPPED
            self._radio_mode = RadioMode.IDLE
            return False

        self._current_device_id = device_id
        self._state = PlaybackState.PLAYING

        device_name = device.name if hasattr(device, "name") else device_id
        logger.info(f"FM playback started: {frequency} MHz on {device_name}")
        return True

    async def _start_dab(
        self,
        device_id: str,
        channel: str,
        program: Optional[str] = None,
        service_id: Optional[int] = None,
    ) -> bool:
        """Start DAB+ playback."""
        logger.info(
            f"Starting DAB+ playback: channel {channel} to device {device_id}"
        )

        # Verify device exists
        device = self._chromecast.get_device(device_id)
        if not device:
            logger.error(f"Chromecast device not found: {device_id}")
            return False

        # Stop FM if running (single dongle constraint)
        if self._radio_mode == RadioMode.FM:
            await self._tuner.stop()

        self._state = PlaybackState.BUFFERING
        self._radio_mode = RadioMode.DAB

        # Tune DAB+
        if not await self._dab.tune(channel, program, service_id):
            logger.error("Failed to tune DAB+")
            self._state = PlaybackState.STOPPED
            self._radio_mode = RadioMode.IDLE
            return False

        # Start stream server
        await self._start_stream_server()

        # Give DAB+ time to sync and buffer
        await asyncio.sleep(2)

        # Start casting
        cast_url = self.chromecast_stream_url
        logger.info(f"Casting to Chromecast using URL: {cast_url}")
        if not await self._chromecast.play_url(device_id, cast_url):
            logger.error("Failed to start Chromecast casting")
            await self._dab.stop()
            self._state = PlaybackState.STOPPED
            self._radio_mode = RadioMode.IDLE
            return False

        self._current_device_id = device_id
        self._state = PlaybackState.PLAYING

        dab_status = self._dab.get_status()
        device_name = device.name if hasattr(device, "name") else device_id
        logger.info(
            f"DAB+ playback started: {channel}/{dab_status.program} on {device_name}"
        )
        return True

    async def stop(self) -> bool:
        """Stop playback completely."""
        async with self._lock:
            logger.info("Stopping playback")

            # Stop device playback
            if self._current_device_id:
                await self._chromecast.stop_playback(self._current_device_id)

            # Stop the active radio source
            if self._radio_mode == RadioMode.FM:
                await self._tuner.stop()
            elif self._radio_mode == RadioMode.DAB:
                await self._dab.stop()

            # Stop stream server
            await self._stop_stream_server()

            self._state = PlaybackState.STOPPED
            self._radio_mode = RadioMode.IDLE
            self._current_device_id = None

            return True

    async def pause(self) -> bool:
        """Pause playback."""
        async with self._lock:
            if self._state != PlaybackState.PLAYING:
                return False

            if self._current_device_id:
                await self._chromecast.pause_playback(self._current_device_id)

            self._state = PlaybackState.PAUSED
            return True

    async def resume(self) -> bool:
        """Resume paused playback."""
        async with self._lock:
            if self._state != PlaybackState.PAUSED:
                return False

            if self._current_device_id:
                await self._chromecast.play_url(
                    self._current_device_id, self.stream_url
                )

            self._state = PlaybackState.PLAYING
            return True

    async def change_frequency(
        self,
        frequency: float,
        modulation: Modulation = Modulation.WFM,
    ) -> bool:
        """Change FM frequency while maintaining playback."""
        async with self._lock:
            if self._state not in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
                return False

            # If currently in DAB mode, switch to FM
            if self._radio_mode == RadioMode.DAB:
                await self._dab.stop()
                self._radio_mode = RadioMode.FM

            # Re-tune (this will restart the rtl_fm process)
            return await self._tuner.tune(frequency, modulation)

    async def change_dab_program(
        self,
        channel: str,
        program: Optional[str] = None,
        service_id: Optional[int] = None,
    ) -> bool:
        """Change DAB+ channel/program while maintaining playback."""
        async with self._lock:
            if self._state not in [PlaybackState.PLAYING, PlaybackState.PAUSED]:
                return False

            # If currently in FM mode, switch to DAB
            if self._radio_mode == RadioMode.FM:
                await self._tuner.stop()
                self._radio_mode = RadioMode.DAB

            # Re-tune DAB+
            return await self._dab.tune(channel, program, service_id)
