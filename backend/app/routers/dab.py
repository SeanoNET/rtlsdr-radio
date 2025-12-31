"""
DAB+ radio API router.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Request

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
async def tune_dab(tune_req: DabTuneRequest, request: Request):
    """Tune to a specific DAB+ program."""
    dab_service = request.app.state.dab_service

    success = await dab_service.tune(
        channel=tune_req.channel,
        program=tune_req.program,
        service_id=tune_req.service_id,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to tune to DAB+ channel {tune_req.channel}",
        )

    return {
        "success": True,
        "channel": tune_req.channel,
        "program": dab_service.get_status().program,
        "service_id": dab_service.get_status().service_id,
    }


@router.get("/status", response_model=DabStatus)
async def get_dab_status(request: Request):
    """Get current DAB+ tuner status."""
    dab_service = request.app.state.dab_service
    return dab_service.get_status()


@router.post("/stop")
async def stop_dab(request: Request):
    """Stop DAB+ playback."""
    dab_service = request.app.state.dab_service
    await dab_service.stop()
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
