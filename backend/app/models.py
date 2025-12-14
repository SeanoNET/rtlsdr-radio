"""
Pydantic models for API requests and responses.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Modulation(str, Enum):
    FM = "fm"
    AM = "am"
    WFM = "wfm"  # Wideband FM (broadcast)
    NFM = "nfm"  # Narrowband FM


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    BUFFERING = "buffering"


class SpeakerType(str, Enum):
    CHROMECAST = "chromecast"


# Station models
class StationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    frequency: float = Field(..., ge=24.0, le=1766.0, description="Frequency in MHz")
    modulation: Modulation = Modulation.WFM
    image_url: Optional[str] = Field(None, description="URL to station logo/artwork")


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    frequency: Optional[float] = Field(None, ge=24.0, le=1766.0)
    modulation: Optional[Modulation] = None
    image_url: Optional[str] = None


class Station(StationBase):
    id: str


# Device models
class ChromecastDevice(BaseModel):
    id: str
    name: str
    model: str
    ip_address: str
    port: int
    volume: float = Field(..., ge=0.0, le=1.0)
    is_muted: bool
    is_idle: bool


# Unified speaker model for the frontend
class Speaker(BaseModel):
    id: str
    name: str
    type: SpeakerType
    model: str
    ip_address: str
    volume: float = Field(..., ge=0.0, le=1.0)
    is_available: bool  # not idle for Chromecast


class VolumeRequest(BaseModel):
    volume: float = Field(..., ge=0.0, le=1.0, description="Volume level 0.0-1.0")


class MuteRequest(BaseModel):
    muted: bool


# Tuner models
class TuneRequest(BaseModel):
    frequency: float = Field(..., ge=24.0, le=1766.0, description="Frequency in MHz")
    modulation: Modulation = Modulation.WFM
    gain: Optional[float] = Field(None, description="Gain in dB, None for auto")
    squelch: Optional[int] = Field(None, ge=0, le=100, description="Squelch level")


class TunerStatus(BaseModel):
    frequency: Optional[float]
    modulation: Optional[Modulation]
    gain: Optional[float]
    squelch: Optional[int]
    is_running: bool


# Playback models
class PlaybackStartRequest(BaseModel):
    device_id: str
    station_id: Optional[str] = None  # If provided, tune to station first
    frequency: Optional[float] = None  # Alternative: direct frequency
    modulation: Modulation = Modulation.WFM


class PlaybackStatus(BaseModel):
    state: PlaybackState
    device_id: Optional[str]
    device_name: Optional[str]
    frequency: Optional[float]
    modulation: Optional[Modulation]
    stream_url: Optional[str]
