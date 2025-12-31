"""
RTL-SDR tuner service - manages rtl_fm subprocess and audio transcoding.
"""
import asyncio
import subprocess
import signal
import logging
from typing import Optional
from pathlib import Path

from app.models import Modulation, TunerStatus

logger = logging.getLogger(__name__)


class TunerService:
    def __init__(self):
        self._rtl_process: Optional[subprocess.Popen] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None
        self._frequency: Optional[float] = None
        self._modulation: Optional[Modulation] = None
        self._gain: Optional[float] = None
        self._squelch: Optional[int] = None
        self._lock = asyncio.Lock()
        self._read_lock = asyncio.Lock()  # Prevent concurrent stream reads
        self._audio_fifo_path = Path("/tmp/rtlsdr_audio.fifo")
        self._stream_ready = False  # Track if stream is ready for consumption
    
    def _get_rtl_fm_args(
        self,
        frequency: float,
        modulation: Modulation,
        gain: Optional[float] = None,
        squelch: Optional[int] = None,
    ) -> list[str]:
        """Build rtl_fm command arguments."""
        # Convert frequency to Hz
        freq_hz = int(frequency * 1_000_000)
        
        # Map modulation to rtl_fm mode
        mode_map = {
            Modulation.FM: "fm",
            Modulation.AM: "am",
            Modulation.WFM: "wbfm",
            Modulation.NFM: "fm",
        }
        mode = mode_map.get(modulation, "wbfm")
        
        args = [
            "rtl_fm",
            "-f", str(freq_hz),
            "-M", mode,
            "-s", "200000",  # Sample rate
            "-r", "48000",   # Output rate
            "-E", "deemp",   # De-emphasis for FM broadcast
        ]
        
        if gain is not None:
            args.extend(["-g", str(gain)])
        else:
            args.extend(["-g", "auto"])
        
        if squelch is not None and squelch > 0:
            args.extend(["-l", str(squelch)])
        
        return args
    
    def _get_ffmpeg_args(self) -> list[str]:
        """Build ffmpeg transcoding arguments."""
        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
            "-f", "s16le",        # Input format: signed 16-bit little-endian
            "-ar", "48000",       # Input sample rate
            "-ac", "1",           # Input channels (mono)
            "-i", "pipe:0",       # Read from stdin
            "-c:a", "libmp3lame", # MP3 codec
            "-b:a", "128k",       # Bitrate
            "-f", "mp3",          # Output format
            "pipe:1",             # Output to stdout
        ]
    
    @property
    def is_running(self) -> bool:
        """Check if tuner is currently running."""
        return (
            self._rtl_process is not None
            and self._rtl_process.poll() is None
        )

    @property
    def is_stream_ready(self) -> bool:
        """Check if audio stream is ready for consumption."""
        return self.is_running and self._stream_ready
    
    def get_status(self) -> TunerStatus:
        """Get current tuner status."""
        return TunerStatus(
            frequency=self._frequency,
            modulation=self._modulation,
            gain=self._gain,
            squelch=self._squelch,
            is_running=self.is_running,
        )
    
    async def tune(
        self,
        frequency: float,
        modulation: Modulation = Modulation.WFM,
        gain: Optional[float] = None,
        squelch: Optional[int] = None,
    ) -> bool:
        """
        Tune to a frequency. Restarts the rtl_fm process if already running.
        """
        async with self._lock:
            # Mark stream as not ready during tuning
            self._stream_ready = False

            # Stop existing processes
            await self._stop_processes()
            
            # Store settings
            self._frequency = frequency
            self._modulation = modulation
            self._gain = gain
            self._squelch = squelch
            
            logger.info(f"Tuning to {frequency} MHz ({modulation.value})")
            
            try:
                # Start rtl_fm
                rtl_args = self._get_rtl_fm_args(frequency, modulation, gain, squelch)
                logger.debug(f"Starting rtl_fm: {' '.join(rtl_args)}")
                
                self._rtl_process = subprocess.Popen(
                    rtl_args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                
                # Start ffmpeg to transcode
                ffmpeg_args = self._get_ffmpeg_args()
                logger.debug(f"Starting ffmpeg: {' '.join(ffmpeg_args)}")
                
                self._ffmpeg_process = subprocess.Popen(
                    ffmpeg_args,
                    stdin=self._rtl_process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                
                # Allow rtl_fm to write directly to ffmpeg
                if self._rtl_process.stdout:
                    self._rtl_process.stdout.close()
                
                # Give it a moment to start
                await asyncio.sleep(0.5)
                
                # Check if processes are still running
                if self._rtl_process.poll() is not None:
                    stderr = self._rtl_process.stderr.read().decode(errors='replace') if self._rtl_process.stderr else ""
                    logger.error(f"rtl_fm failed to start: {stderr}")
                    return False

                # Mark stream as ready
                self._stream_ready = True
                logger.info(f"Successfully tuned to {frequency} MHz")
                return True
                
            except FileNotFoundError as e:
                logger.error(f"Required binary not found: {e}")
                return False
            except Exception as e:
                logger.error(f"Failed to tune: {e}")
                await self._stop_processes()
                return False
    
    async def _stop_processes(self):
        """Stop rtl_fm and ffmpeg processes."""
        self._stream_ready = False

        for proc, name in [
            (self._ffmpeg_process, "ffmpeg"),
            (self._rtl_process, "rtl_fm"),
        ]:
            if proc and proc.poll() is None:
                logger.debug(f"Stopping {name} process")
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        self._rtl_process = None
        self._ffmpeg_process = None
    
    async def stop(self):
        """Stop the tuner."""
        async with self._lock:
            await self._stop_processes()
            self._frequency = None
            self._modulation = None
            logger.info("Tuner stopped")
    
    def get_audio_stream(self):
        """
        Get the audio stream from ffmpeg.
        Returns the stdout pipe of the ffmpeg process.
        """
        if self._ffmpeg_process and self._ffmpeg_process.stdout:
            return self._ffmpeg_process.stdout
        return None
    
    async def read_audio_chunk(self, chunk_size: int = 4096) -> Optional[bytes]:
        """Read a chunk of audio data from the stream."""
        if not self._stream_ready or not self._ffmpeg_process or not self._ffmpeg_process.stdout:
            return None

        # Use read lock to prevent concurrent readers
        async with self._read_lock:
            if not self._ffmpeg_process or not self._ffmpeg_process.stdout:
                return None

            loop = asyncio.get_event_loop()
            try:
                chunk = await loop.run_in_executor(
                    None,
                    self._ffmpeg_process.stdout.read,
                    chunk_size,
                )
                return chunk if chunk else None
            except Exception as e:
                logger.debug(f"Error reading audio chunk: {e}")
                return None
