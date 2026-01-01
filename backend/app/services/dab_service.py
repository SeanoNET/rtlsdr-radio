"""
DAB+ tuner service - manages welle-cli subprocess for DAB+ radio.
"""

import asyncio
import subprocess
import logging
from typing import List, Optional

import aiohttp

from app.models import (
    DabProgram,
    DabScanResult,
    DabStatus,
    DabMetadata,
    DabSignalQuality,
    DabAudioInfo,
)
from app.config.dab_channels import get_channel_frequency, get_common_channels

logger = logging.getLogger(__name__)


class DabService:
    """Service for managing DAB+ radio via welle-cli."""

    def __init__(self, welle_port: int = 8188):
        self._welle_process: Optional[subprocess.Popen] = None
        self._channel: Optional[str] = None
        self._program: Optional[str] = None
        self._service_id: Optional[int] = None
        self._ensemble: Optional[str] = None
        self._welle_port = welle_port
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()  # Prevent concurrent stream reads
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._audio_response: Optional[aiohttp.ClientResponse] = None
        self._stream_ready = False  # Track if stream is ready for consumption

    @property
    def is_running(self) -> bool:
        """Check if welle-cli is currently running."""
        return (
            self._welle_process is not None
            and self._welle_process.poll() is None
        )

    @property
    def is_stream_ready(self) -> bool:
        """Check if audio stream is ready for consumption."""
        return self.is_running and self._stream_ready and self._service_id is not None

    @property
    def welle_base_url(self) -> str:
        """Get the base URL for welle-cli HTTP server."""
        return f"http://localhost:{self._welle_port}"

    @property
    def stream_url(self) -> Optional[str]:
        """Get the stream URL for the current program."""
        if self._service_id is not None and self.is_running:
            return f"{self.welle_base_url}/mp3/{self._service_id}"
        return None

    def get_status(self) -> DabStatus:
        """Get current DAB+ tuner status."""
        return DabStatus(
            channel=self._channel,
            program=self._program,
            service_id=self._service_id,
            ensemble=self._ensemble,
            is_running=self.is_running,
        )

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session for welle-cli communication."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()
        return self._http_session

    async def _close_http_session(self):
        """Close HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            self._http_session = None

    def _get_welle_cli_args(self, channel: str) -> List[str]:
        """Build welle-cli command arguments."""
        return [
            "welle-cli",
            "-c", channel.upper(),
            "-w", str(self._welle_port),
        ]

    async def tune(
        self,
        channel: str,
        program: Optional[str] = None,
        service_id: Optional[int] = None,
    ) -> bool:
        """
        Start welle-cli and tune to a DAB+ channel/program.

        Args:
            channel: DAB+ channel (e.g., "9B")
            program: Program name to match (optional)
            service_id: Service ID to tune to (optional, preferred over name)

        Returns:
            True if tuning successful, False otherwise.
        """
        async with self._lock:
            # Mark stream as not ready during tuning
            self._stream_ready = False

            # Validate channel
            freq = get_channel_frequency(channel)
            if freq is None:
                logger.error(f"Invalid DAB+ channel: {channel}")
                return False

            # Stop existing process
            await self._stop_process()

            # Store settings
            self._channel = channel.upper()
            self._program = program
            self._service_id = service_id

            logger.info(f"Tuning to DAB+ channel {channel}")

            try:
                # Start welle-cli
                args = self._get_welle_cli_args(channel)
                logger.debug(f"Starting welle-cli: {' '.join(args)}")

                self._welle_process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                # Give welle-cli time to start, find sync, and scan the ensemble
                await asyncio.sleep(5)

                # Check if process is still running
                if self._welle_process.poll() is not None:
                    # Capture stderr to see why it failed
                    _, stderr = self._welle_process.communicate()
                    error_msg = stderr.decode() if stderr else "unknown error"
                    logger.error(f"welle-cli failed to start: {error_msg}")
                    return False

                # If no service_id provided, try to find it from program name
                if self._service_id is None and program:
                    programs = await self.get_programs()
                    for prog in programs:
                        if program.lower() in prog.name.lower():
                            self._service_id = prog.service_id
                            self._program = prog.name
                            self._ensemble = prog.ensemble
                            logger.info(f"Found program '{prog.name}' with service_id {prog.service_id}")
                            break

                    if self._service_id is None:
                        logger.warning(f"Program '{program}' not found on channel {channel}")
                        # Don't fail - let the caller decide what to do

                # Mark stream as ready if we have a service_id
                if self._service_id is not None:
                    self._stream_ready = True

                logger.info(f"Successfully tuned to DAB+ channel {channel}")
                return True

            except FileNotFoundError:
                logger.error("welle-cli not found. Install with: sudo apt install welle.io")
                return False
            except Exception as e:
                logger.error(f"Failed to tune DAB+: {e}")
                await self._stop_process()
                return False

    async def get_programs(self, channel: Optional[str] = None) -> List[DabProgram]:
        """
        Get list of programs from welle-cli.

        Args:
            channel: If provided and different from current, tune first.

        Returns:
            List of available programs on the channel.
        """
        # If channel specified and different, we need to tune first
        if channel and channel.upper() != self._channel:
            if not await self.tune(channel):
                return []

        if not self.is_running:
            logger.warning("welle-cli not running, cannot get programs")
            return []

        try:
            session = await self._get_http_session()
            async with session.get(
                f"{self.welle_base_url}/mux.json",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    logger.error(f"Failed to get programs: HTTP {response.status}")
                    return []

                data = await response.json()
                programs = []

                # Parse welle-cli mux.json format
                # Labels can be either strings or nested dicts with 'label' key
                ensemble_data = data.get("ensemble", {}).get("label", "Unknown")
                if isinstance(ensemble_data, dict):
                    ensemble_name = ensemble_data.get("label", "Unknown")
                else:
                    ensemble_name = ensemble_data
                self._ensemble = ensemble_name

                for service in data.get("services", []):
                    # Handle nested label structure
                    label_data = service.get("label", "Unknown")
                    if isinstance(label_data, dict):
                        service_name = label_data.get("label", "Unknown")
                    else:
                        service_name = label_data

                    # Parse service_id - can be int or hex string like '0x3c01'
                    sid_raw = service.get("sid", 0)
                    if isinstance(sid_raw, str):
                        service_id = int(sid_raw, 16) if sid_raw.startswith("0x") else int(sid_raw)
                    else:
                        service_id = sid_raw

                    programs.append(DabProgram(
                        service_id=service_id,
                        name=service_name,
                        ensemble=ensemble_name,
                        channel=self._channel or "",
                        bitrate=service.get("bitrate"),
                        program_type=service.get("pty_label"),
                    ))

                return programs

        except asyncio.TimeoutError:
            logger.error("Timeout getting programs from welle-cli")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error getting programs: {e}")
            return []
        except Exception as e:
            logger.error(f"Error getting programs: {e}")
            return []

    async def scan_channels(
        self,
        channels: Optional[List[str]] = None,
    ) -> List[DabScanResult]:
        """
        Scan DAB+ channels for available programs.

        Args:
            channels: List of channels to scan (None = common channels)

        Returns:
            List of scan results with programs per channel.
        """
        if channels is None:
            channels = get_common_channels()

        results = []
        original_channel = self._channel
        original_service_id = self._service_id

        for channel in channels:
            logger.info(f"Scanning DAB+ channel {channel}")

            if await self.tune(channel):
                # Wait a bit for ensemble info to load
                await asyncio.sleep(2)
                programs = await self.get_programs()

                results.append(DabScanResult(
                    channel=channel,
                    ensemble=self._ensemble,
                    programs=programs,
                ))
            else:
                results.append(DabScanResult(
                    channel=channel,
                    ensemble=None,
                    programs=[],
                ))

        # Restore original tuning if we were tuned before
        if original_channel:
            await self.tune(original_channel, service_id=original_service_id)

        return results

    async def _connect_audio_stream(self) -> bool:
        """Establish persistent connection to welle-cli audio stream."""
        if self._audio_response is not None:
            return True

        url = self.stream_url
        if not url:
            return False

        try:
            session = await self._get_http_session()
            # Use a long timeout for streaming - welle-cli streams continuously
            self._audio_response = await session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=None, sock_read=5),
            )
            if self._audio_response.status != 200:
                logger.error(f"Failed to connect to audio stream: HTTP {self._audio_response.status}")
                await self._disconnect_audio_stream()
                return False
            logger.debug(f"Connected to audio stream: {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to audio stream: {e}")
            await self._disconnect_audio_stream()
            return False

    async def _disconnect_audio_stream(self):
        """Close persistent audio stream connection."""
        if self._audio_response is not None:
            try:
                self._audio_response.close()
            except Exception:
                pass
            self._audio_response = None
            logger.debug("Disconnected from audio stream")

    async def read_audio_chunk(self, chunk_size: int = 4096) -> Optional[bytes]:
        """
        Read a chunk of audio data from welle-cli stream.

        Uses a persistent HTTP connection to avoid reconnection overhead.

        Args:
            chunk_size: Number of bytes to read.

        Returns:
            Audio data bytes or None if not available.
        """
        if not self._stream_ready:
            return None

        # Use read lock to prevent concurrent readers
        async with self._read_lock:
            # Ensure we have a connection
            if self._audio_response is None:
                if not await self._connect_audio_stream():
                    return None

            try:
                chunk = await self._audio_response.content.read(chunk_size)
                return chunk if chunk else None
            except asyncio.TimeoutError:
                logger.debug("Audio stream read timeout")
                return None
            except aiohttp.ClientError as e:
                logger.debug(f"Audio stream error, reconnecting: {e}")
                await self._disconnect_audio_stream()
                return None
            except Exception as e:
                logger.debug(f"Error reading audio chunk: {e}")
                await self._disconnect_audio_stream()
                return None

    async def _stop_process(self):
        """Stop welle-cli process."""
        self._stream_ready = False

        # Disconnect audio stream first
        await self._disconnect_audio_stream()

        if self._welle_process and self._welle_process.poll() is None:
            logger.debug("Stopping welle-cli process")
            self._welle_process.terminate()
            try:
                self._welle_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._welle_process.kill()
                self._welle_process.wait()

        self._welle_process = None
        await self._close_http_session()

    async def stop(self):
        """Stop the DAB+ tuner."""
        async with self._lock:
            await self._stop_process()
            self._channel = None
            self._program = None
            self._service_id = None
            self._ensemble = None
            logger.info("DAB+ tuner stopped")

    async def get_metadata(self) -> DabMetadata:
        """
        Get current DAB+ program metadata including PAD data.

        Fetches real-time metadata from welle-cli including:
        - DLS (Dynamic Label Segment) - now playing text
        - MOT (Multimedia Object Transfer) - slideshow images
        - Signal quality metrics
        - Audio stream info
        - Program type (PTY)

        Returns:
            DabMetadata with current program information.
        """
        if not self.is_running or self._service_id is None:
            return DabMetadata(is_playing=False)

        try:
            session = await self._get_http_session()
            async with session.get(
                f"{self.welle_base_url}/mux.json",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status != 200:
                    logger.warning(f"Failed to get metadata: HTTP {response.status}")
                    return DabMetadata(
                        program=self._program,
                        service_id=self._service_id,
                        ensemble=self._ensemble,
                        channel=self._channel,
                        is_playing=True,
                    )

                data = await response.json()
                metadata = self._parse_metadata(data)

                # Fetch MOT slideshow image from separate endpoint
                mot_image, mot_content_type = await self._fetch_mot_image()
                if mot_image:
                    metadata.mot_image = mot_image
                    metadata.mot_content_type = mot_content_type

                return metadata

        except asyncio.TimeoutError:
            logger.warning("Timeout getting metadata from welle-cli")
            return DabMetadata(
                program=self._program,
                service_id=self._service_id,
                ensemble=self._ensemble,
                channel=self._channel,
                is_playing=True,
            )
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            return DabMetadata(
                program=self._program,
                service_id=self._service_id,
                ensemble=self._ensemble,
                channel=self._channel,
                is_playing=True,
            )

    async def _fetch_mot_image(self) -> tuple[Optional[str], Optional[str]]:
        """
        Fetch MOT slideshow image from welle-cli's /slide endpoint.

        Returns:
            Tuple of (base64_encoded_image, content_type), or (None, None) if not available.
        """
        if not self._service_id:
            return None, None

        try:
            # welle-cli serves slides at /slide/{hex_service_id}
            slide_url = f"{self.welle_base_url}/slide/0x{self._service_id:04x}"
            session = await self._get_http_session()

            async with session.get(
                slide_url,
                timeout=aiohttp.ClientTimeout(total=3),
            ) as response:
                if response.status != 200:
                    return None, None

                # Check content type
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("image/"):
                    return None, None

                # Read and base64 encode the image
                image_data = await response.read()
                if not image_data or len(image_data) < 100:
                    # Too small to be a valid image
                    return None, None

                import base64
                encoded = base64.b64encode(image_data).decode("utf-8")
                return encoded, content_type

        except asyncio.TimeoutError:
            logger.debug("Timeout fetching MOT slide")
            return None, None
        except Exception as e:
            logger.debug(f"Error fetching MOT slide: {e}")
            return None, None

    def _parse_metadata(self, data: dict) -> DabMetadata:
        """Parse welle-cli mux.json response into DabMetadata."""
        # Find the current service
        current_service = None
        for service in data.get("services", []):
            # Parse service_id - can be int or hex string
            sid_raw = service.get("sid", 0)
            if isinstance(sid_raw, str):
                sid = int(sid_raw, 16) if sid_raw.startswith("0x") else int(sid_raw)
            else:
                sid = sid_raw

            if sid == self._service_id:
                current_service = service
                break

        if not current_service:
            return DabMetadata(
                program=self._program,
                service_id=self._service_id,
                ensemble=self._ensemble,
                channel=self._channel,
                is_playing=True,
            )

        # Parse program name (handle nested label structure)
        label_data = current_service.get("label", "Unknown")
        if isinstance(label_data, dict):
            program_name = label_data.get("label", "Unknown")
        else:
            program_name = label_data

        # Parse DLS (Dynamic Label Segment) - welle-cli uses nested "dls" object
        dls = None
        dls_data = current_service.get("dls")
        if isinstance(dls_data, dict):
            dls = dls_data.get("label")
        elif isinstance(dls_data, str):
            dls = dls_data

        # Fallback to legacy field names
        if not dls:
            dls = current_service.get("dls_label")

        mot_data = current_service.get("mot", {})

        # MOT slideshow image - check multiple possible locations
        mot_image = None
        mot_content_type = None

        # welle-cli may provide MOT data in different ways
        if isinstance(mot_data, dict):
            # Try common field names for MOT image data
            mot_image = (
                mot_data.get("mot") or
                mot_data.get("data") or
                mot_data.get("slide") or
                mot_data.get("image")
            )
            mot_content_type = mot_data.get("mot_type") or mot_data.get("content_type", "image/jpeg")

        # Also check service-level MOT fields
        if not mot_image:
            mot_image = current_service.get("mot_data") or current_service.get("slide")

        # Parse PTY (program type)
        pty_label = current_service.get("pty_label")
        pty_code = current_service.get("pty")

        # Parse audio info
        audio_mode = current_service.get("audio_mode")
        bitrate = current_service.get("bitrate")
        sample_rate = current_service.get("samplerate")

        audio_info = None
        if audio_mode or bitrate or sample_rate:
            audio_info = DabAudioInfo(
                mode=audio_mode,
                bitrate=bitrate,
                sample_rate=sample_rate,
            )

        # Parse signal quality from ensemble
        ensemble_data = data.get("ensemble", {})
        snr = ensemble_data.get("snr")
        fic_quality = ensemble_data.get("fic_quality")

        signal_quality = None
        if snr is not None or fic_quality is not None:
            signal_quality = DabSignalQuality(
                snr=snr,
                fic_quality=fic_quality,
            )

        # Get ensemble name
        ensemble_label = ensemble_data.get("label", "Unknown")
        if isinstance(ensemble_label, dict):
            ensemble_name = ensemble_label.get("label", "Unknown")
        else:
            ensemble_name = ensemble_label

        return DabMetadata(
            program=program_name,
            service_id=self._service_id,
            ensemble=ensemble_name,
            channel=self._channel,
            dls=dls,
            mot_image=mot_image,
            mot_content_type=mot_content_type,
            pty=pty_label,
            pty_code=pty_code,
            signal=signal_quality,
            audio=audio_info,
            is_playing=True,
        )
