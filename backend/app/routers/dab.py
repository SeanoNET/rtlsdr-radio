"""
DAB+ radio API router.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Request

from app.models import (
    DabChannel,
    DabMetadata,
    DabProgram,
    DabScanRequest,
    DabScanResult,
    DabStatus,
    DabTuneRequest,
)
from app.config.dab_channels import get_all_channels
from app.services.tuner_lock import TunerMode

router = APIRouter()


@router.get("/channels", response_model=List[DabChannel])
async def list_dab_channels():
    """List available DAB+ channels with frequencies."""
    return get_all_channels()


@router.get("/programs", response_model=List[DabProgram])
async def list_programs(channel: str, request: Request):
    """
    List programs available on a DAB+ channel.

    This will start welle-cli if not already running on the specified channel.
    """
    dab_service = request.app.state.dab_service
    programs = await dab_service.get_programs(channel)
    return programs


@router.post("/scan", response_model=List[DabScanResult])
async def scan_channels(scan_req: DabScanRequest, request: Request):
    """
    Scan DAB+ channels for available programs.

    This is a slow operation as it tunes to each channel and waits for
    the ensemble information to load.
    """
    dab_service = request.app.state.dab_service
    results = await dab_service.scan_channels(scan_req.channels)
    return results


@router.post("/tune")
async def tune_dab(
    tune_req: DabTuneRequest,
    request: Request,
    x_client_id: Optional[str] = Header(default="frontend", alias="X-Client-ID"),
    x_force_takeover: Optional[bool] = Header(default=False, alias="X-Force-Takeover"),
):
    """
    Tune to a specific DAB+ program.

    Headers:
        X-Client-ID: Identifier for this client (default: "frontend")
        X-Force-Takeover: If true, forcibly take over from another client
    """
    tuner_lock = request.app.state.tuner_lock
    dab_service = request.app.state.dab_service

    # Acquire tuner lock
    success, result = await tuner_lock.acquire(
        client_id=x_client_id,
        mode=TunerMode.DAB,
        force=x_force_takeover,
    )

    if not success:
        raise HTTPException(
            status_code=409,
            detail=f"Tuner conflict: {result}",
        )

    session_id = result

    tune_success = await dab_service.tune(
        channel=tune_req.channel,
        program=tune_req.program,
        service_id=tune_req.service_id,
    )

    if not tune_success:
        # Release lock on failure
        await tuner_lock.release(x_client_id, session_id)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to tune to DAB+ channel {tune_req.channel}",
        )

    return {
        "success": True,
        "channel": tune_req.channel,
        "program": dab_service.get_status().program,
        "service_id": dab_service.get_status().service_id,
        "session_id": session_id,
    }


@router.get("/status", response_model=DabStatus)
async def get_dab_status(request: Request):
    """Get current DAB+ tuner status."""
    dab_service = request.app.state.dab_service
    return dab_service.get_status()


@router.post("/stop")
async def stop_dab(
    request: Request,
    x_client_id: Optional[str] = Header(default="frontend", alias="X-Client-ID"),
):
    """Stop DAB+ playback and release the lock."""
    tuner_lock = request.app.state.tuner_lock
    dab_service = request.app.state.dab_service

    await dab_service.stop()
    await tuner_lock.release(x_client_id)

    return {"success": True, "message": "DAB+ tuner stopped"}


@router.get("/metadata", response_model=DabMetadata)
async def get_dab_metadata(request: Request):
    """
    Get current DAB+ program metadata including PAD data.

    Returns real-time information including:
    - **dls**: Dynamic Label Segment - "now playing" text (artist, song, show info)
    - **mot_image**: Base64-encoded slideshow image (station logo, album art)
    - **signal**: Signal quality metrics (SNR, FIC quality)
    - **audio**: Audio stream info (stereo/mono, bitrate, sample rate)
    - **pty**: Program type (genre)

    Poll this endpoint every 5-10 seconds when DAB+ is playing
    to get updated "now playing" information.
    """
    dab_service = request.app.state.dab_service
    return await dab_service.get_metadata()


@router.get("/debug/mux")
async def get_raw_mux_json(request: Request):
    """
    Debug endpoint: Get raw mux.json from welle-cli.

    This shows exactly what welle-cli is returning so we can
    debug metadata parsing issues.
    """
    import aiohttp

    dab_service = request.app.state.dab_service

    if not dab_service.is_running:
        return {"error": "welle-cli not running", "is_running": False}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{dab_service.welle_base_url}/mux.json",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status != 200:
                    return {"error": f"HTTP {response.status}", "is_running": True}

                data = await response.json()
                return {
                    "is_running": True,
                    "current_service_id": dab_service._service_id,
                    "welle_url": dab_service.welle_base_url,
                    "raw_mux_json": data,
                }
    except Exception as e:
        return {"error": str(e), "is_running": True}
