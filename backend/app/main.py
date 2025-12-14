"""
RTL-SDR Chromecast Radio - Main FastAPI Application
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import devices, playback, speakers, stations, stream, tuner
from app.services.chromecast_service import ChromecastService
from app.services.lms_service import LMSService
from app.services.playback_service import PlaybackService
from app.services.tuner_service import TunerService


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    app.state.chromecast_service = ChromecastService()
    app.state.tuner_service = TunerService()

    # LMS configuration from environment or defaults
    lms_host = os.environ.get("LMS_HOST", "localhost")
    lms_port = int(os.environ.get("LMS_PORT", "9000"))
    lms_https = os.environ.get("LMS_HTTPS", "").lower() in ("true", "1", "yes")
    app.state.lms_service = LMSService(
        server_host=lms_host, server_port=lms_port, use_https=lms_https
    )

    # External stream URL for Chromecast (HTTPS required)
    external_stream_url = os.environ.get("EXTERNAL_STREAM_URL")

    app.state.playback_service = PlaybackService(
        tuner_service=app.state.tuner_service,
        chromecast_service=app.state.chromecast_service,
        lms_service=app.state.lms_service,
        external_stream_url=external_stream_url,
    )

    # Start Chromecast discovery
    await app.state.chromecast_service.start_discovery()

    # Discover LMS players
    await app.state.lms_service.discover_players()

    yield

    # Shutdown
    await app.state.playback_service.stop()
    await app.state.chromecast_service.stop_discovery()
    await app.state.lms_service.close()
    await app.state.tuner_service.stop()


app = FastAPI(
    title="RTL-SDR Chromecast Radio",
    description="Stream FM radio from RTL-SDR to Chromecast or LMS devices",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(speakers.router, prefix="/api/speakers", tags=["speakers"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(stations.router, prefix="/api/stations", tags=["stations"])
app.include_router(tuner.router, prefix="/api/tuner", tags=["tuner"])
app.include_router(playback.router, prefix="/api/playback", tags=["playback"])
app.include_router(stream.router, prefix="/api", tags=["stream"])

# Mount static files for station images
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
