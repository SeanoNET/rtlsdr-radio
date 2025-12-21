"""
DAB+ tuner service - manages welle-cli subprocess for DAB+ radio.
"""

import asyncio
import subprocess
import logging
from typing import List, Optional

import aiohttp

from app.models import DabProgram, DabScanResult, DabStatus
from app.config.dab_channels import get_channel_frequency, get_common_channels

logger = logging.getLogger(__name__)


class DabService:
    """Service for managing DAB+ radio via welle-cli."""

    def __init__(self, welle_port: int = 8088):
        self._welle_process: Optional[subprocess.Popen] = None
        self._channel: Optional[str] = None
        self._program: Optional[str] = None
        self._service_id: Optional[int] = None
        self._ensemble: Optional[str] = None
        self._welle_port = welle_port
        self._lock = asyncio.Lock()
        self._http_session: Optional[aiohttp.ClientSession] = None

    @property
    def is_running(self) -> bool:
        """Check if welle-cli is currently running."""
        return (
            self._welle_process is not None
            and self._welle_process.poll() is None
        )

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
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

                # Give welle-cli time to start, find sync, and scan the ensemble
                await asyncio.sleep(5)

                # Check if process is still running
                if self._welle_process.poll() is not None:
                    logger.error("welle-cli failed to start (process exited)")
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

    async def read_audio_chunk(self, chunk_size: int = 4096) -> Optional[bytes]:
        """
        Read a chunk of audio data from welle-cli stream.

        Args:
            chunk_size: Number of bytes to read.

        Returns:
            Audio data bytes or None if not available.
        """
        stream_url = self.stream_url
        if not stream_url:
            return None

        try:
            session = await self._get_http_session()

            # For streaming, we need a persistent connection
            # This is called repeatedly, so we use a simple request per chunk
            # In production, you'd want to keep the connection open
            async with session.get(
                stream_url,
                timeout=aiohttp.ClientTimeout(total=5, sock_read=2),
            ) as response:
                if response.status != 200:
                    return None

                chunk = await response.content.read(chunk_size)
                return chunk if chunk else None

        except asyncio.TimeoutError:
            return None
        except aiohttp.ClientError as e:
            logger.debug(f"Error reading audio chunk: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading audio chunk: {e}")
            return None

    async def _stop_process(self):
        """Stop welle-cli process."""
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
