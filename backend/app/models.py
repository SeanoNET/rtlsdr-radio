"""
Pydantic models for API requests and responses.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


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


class StationType(str, Enum):
    FM = "fm"
    DAB = "dab"


class RadioMode(str, Enum):
    FM = "fm"
    DAB = "dab"
    IDLE = "idle"


# Station models
class StationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    station_type: StationType = StationType.FM
    image_url: Optional[str] = Field(None, description="URL to station logo/artwork")
    # FM fields (required if station_type == FM)
    frequency: Optional[float] = Field(None, ge=24.0, le=1766.0, description="Frequency in MHz")
    modulation: Optional[Modulation] = Modulation.WFM
    # DAB fields (required if station_type == DAB)
    dab_channel: Optional[str] = Field(None, pattern=r"^[0-9]+[A-D]$", description="DAB channel (e.g., 9B)")
    dab_program: Optional[str] = Field(None, description="DAB program name")
    dab_service_id: Optional[int] = Field(None, description="DAB service ID")

    @model_validator(mode="after")
    def validate_station_fields(self):
        if self.station_type == StationType.FM:
            if self.frequency is None:
                raise ValueError("frequency is required for FM stations")
        elif self.station_type == StationType.DAB:
            if self.dab_channel is None:
                raise ValueError("dab_channel is required for DAB stations")
            if self.dab_program is None and self.dab_service_id is None:
                raise ValueError("dab_program or dab_service_id is required for DAB stations")
        return self


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    station_type: Optional[StationType] = None
    image_url: Optional[str] = None
    # FM fields
    frequency: Optional[float] = Field(None, ge=24.0, le=1766.0)
    modulation: Optional[Modulation] = None
    # DAB fields
    dab_channel: Optional[str] = Field(None, pattern=r"^[0-9]+[A-D]$")
    dab_program: Optional[str] = None
    dab_service_id: Optional[int] = None


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
    # FM parameters
    frequency: Optional[float] = None  # Direct frequency for FM
    modulation: Modulation = Modulation.WFM
    # DAB+ parameters
    dab_channel: Optional[str] = None  # DAB+ channel (e.g., "9B")
    dab_program: Optional[str] = None  # DAB+ program name
    dab_service_id: Optional[int] = None  # DAB+ service ID


class PlaybackStatus(BaseModel):
    state: PlaybackState
    radio_mode: RadioMode = RadioMode.IDLE
    device_id: Optional[str]
    device_name: Optional[str]
    # FM fields
    frequency: Optional[float] = None
    modulation: Optional[Modulation] = None
    # DAB fields
    dab_channel: Optional[str] = None
    dab_program: Optional[str] = None
    dab_service_id: Optional[int] = None
    stream_url: Optional[str] = None


# DAB+ models
class DabChannel(BaseModel):
    id: str = Field(..., description="Channel ID (e.g., 9B)")
    frequency: float = Field(..., description="Center frequency in MHz")
    label: str = Field(..., description="Human-readable channel label")


class DabProgram(BaseModel):
    service_id: int = Field(..., description="DAB service ID")
    name: str = Field(..., description="Program name")
    ensemble: str = Field(..., description="Ensemble name")
    channel: str = Field(..., description="DAB channel ID")
    bitrate: Optional[int] = Field(None, description="Audio bitrate in kbps")
    program_type: Optional[str] = Field(None, description="Program type (e.g., Pop, News)")


class DabTuneRequest(BaseModel):
    channel: str = Field(..., pattern=r"^[0-9]+[A-D]$", description="DAB channel (e.g., 9B)")
    program: Optional[str] = Field(None, description="Program name to match")
    service_id: Optional[int] = Field(None, description="Service ID (preferred over name)")


class DabScanRequest(BaseModel):
    channels: Optional[List[str]] = Field(None, description="Channels to scan (None = all)")


class DabScanResult(BaseModel):
    channel: str
    ensemble: Optional[str] = None
    programs: List[DabProgram] = []


class DabStatus(BaseModel):
    channel: Optional[str] = None
    program: Optional[str] = None
    service_id: Optional[int] = None
    ensemble: Optional[str] = None
    is_running: bool = False
