"""
Audio stream router - for direct browser playback (not Chromecast).

Supports ICY metadata injection for Shoutcast/Icecast compatible clients
(VLC, Music Assistant, etc.) to display "now playing" information.
"""
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse

from app.services.icy_metadata import IcyMetadataInjector

router = APIRouter()

# ICY metadata interval - must match icy-metaint header
ICY_METAINT = 8192

# How often to poll for metadata updates (seconds)
METADATA_POLL_INTERVAL = 5.0


async def fm_audio_stream_generator(tuner_service):
    """Generate FM audio stream chunks (no ICY metadata)."""
    while True:
        chunk = await tuner_service.read_audio_chunk(8192)
        if chunk:
            yield chunk
        else:
            await asyncio.sleep(0.01)
            if not tuner_service.is_running:
                break


async def fm_icy_stream_generator(tuner_service, station_name: Optional[str] = None):
    """Generate FM audio stream with ICY metadata injection."""
    injector = IcyMetadataInjector(ICY_METAINT)

    # FM doesn't have dynamic metadata, use station name
    if station_name:
        injector.set_metadata(station_name)

    while True:
        chunk = await tuner_service.read_audio_chunk(8192)
        if chunk:
            yield injector.process_chunk(chunk)
        else:
            await asyncio.sleep(0.01)
            if not tuner_service.is_running:
                break


async def dab_audio_stream_generator(dab_service):
    """Generate DAB+ audio stream chunks (no ICY metadata)."""
    while True:
        chunk = await dab_service.read_audio_chunk(8192)
        if chunk:
            yield chunk
        else:
            await asyncio.sleep(0.01)
            if not dab_service.is_running:
                break


async def dab_icy_stream_generator(dab_service, slide_url: Optional[str] = None):
    """
    Generate DAB+ audio stream with ICY metadata injection.

    Polls DAB+ metadata every METADATA_POLL_INTERVAL seconds and
    injects DLS (Dynamic Label Segment) as StreamTitle.
    Optionally includes StreamUrl for album art (MOT slideshow).
    """
    injector = IcyMetadataInjector(ICY_METAINT)
    last_meta_update = 0.0
    last_dls = ""

    while True:
        # Poll metadata periodically
        current_time = time.time()
        if current_time - last_meta_update >= METADATA_POLL_INTERVAL:
            try:
                metadata = await dab_service.get_metadata()
                if metadata and metadata.dls and metadata.dls != last_dls:
                    # Include slide URL if MOT image is available
                    url = slide_url if metadata.mot_image else None
                    injector.set_metadata(metadata.dls, url=url)
                    last_dls = metadata.dls
                elif metadata and metadata.program and not metadata.dls:
                    # Fallback to program name if no DLS
                    if metadata.program != last_dls:
                        url = slide_url if metadata.mot_image else None
                        injector.set_metadata(metadata.program, url=url)
                        last_dls = metadata.program
            except Exception:
                pass  # Don't interrupt stream on metadata errors
            last_meta_update = current_time

        chunk = await dab_service.read_audio_chunk(8192)
        if chunk:
            yield injector.process_chunk(chunk)
        else:
            await asyncio.sleep(0.01)
            if not dab_service.is_running:
                break


@router.get("/stream/ready")
async def check_stream_ready(request: Request):
    """
    Check if audio stream is ready for consumption.
    Use this before connecting to /stream to avoid connection errors during tuning.
    """
    tuner_service = request.app.state.tuner_service
    dab_service = request.app.state.dab_service

    if dab_service.is_stream_ready:
        return {"ready": True, "mode": "dab"}
    elif tuner_service.is_stream_ready:
        return {"ready": True, "mode": "fm"}
    else:
        return {"ready": False, "mode": None}


@router.get("/stream")
async def get_audio_stream(request: Request):
    """
    Get the raw audio stream.

    This endpoint can be used for direct browser playback or other clients.
    Automatically selects FM or DAB+ based on which is currently running.

    ICY Metadata Support:
    - Add header `Icy-MetaData: 1` to receive in-stream metadata
    - Server will respond with `icy-metaint` header indicating metadata interval
    - Metadata frames contain StreamTitle with "now playing" information

    Returns HTTP 503 if stream is not ready (e.g., during channel switching).
    """
    tuner_service = request.app.state.tuner_service
    dab_service = request.app.state.dab_service

    # Check if client wants ICY metadata
    wants_icy = request.headers.get("Icy-MetaData") == "1"

    # Base headers
    headers = {
        "Cache-Control": "no-cache, no-store",
        "Connection": "keep-alive",
    }

    # Check which service has a ready stream
    if dab_service.is_stream_ready:
        # Get station info for ICY headers
        status = dab_service.get_status()
        station_name = status.program or "DAB+ Radio"
        bitrate = 128  # Default, could get from metadata

        if wants_icy:
            headers.update(IcyMetadataInjector.get_response_headers(
                name=station_name,
                genre="DAB+",
                bitrate=bitrate,
                metaint=ICY_METAINT,
            ))
            # Build slide URL for album art from request
            # Use X-Forwarded headers if behind reverse proxy, otherwise use request URL
            scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
            host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", request.url.netloc))
            slide_url = f"{scheme}://{host}/api/dab/slide"
            generator = dab_icy_stream_generator(dab_service, slide_url=slide_url)
        else:
            generator = dab_audio_stream_generator(dab_service)

        return StreamingResponse(
            generator,
            media_type="audio/mpeg",
            headers=headers,
        )

    elif tuner_service.is_stream_ready:
        # Get station info for ICY headers
        station_name = "FM Radio"  # Could get from tuner_service if available

        if wants_icy:
            headers.update(IcyMetadataInjector.get_response_headers(
                name=station_name,
                genre="FM",
                bitrate=128,
                metaint=ICY_METAINT,
            ))
            generator = fm_icy_stream_generator(tuner_service, station_name)
        else:
            generator = fm_audio_stream_generator(tuner_service)

        return StreamingResponse(
            generator,
            media_type="audio/mpeg",
            headers=headers,
        )

    else:
        # Return 503 Service Unavailable during tuning or when no station is selected
        return JSONResponse(
            status_code=503,
            content={"error": "Stream not ready. Tune to a station first."},
            headers={"Retry-After": "1"},
        )
