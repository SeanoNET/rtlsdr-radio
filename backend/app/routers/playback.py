"""
Playback control API router.
"""
from fastapi import APIRouter, HTTPException, Request

from app.models import PlaybackStartRequest, PlaybackStatus, Modulation, StationType
from app.services.station_service import get_station_service
from app.routers.speakers import parse_speaker_id

router = APIRouter()


@router.get("/status", response_model=PlaybackStatus)
async def get_playback_status(request: Request):
    """Get current playback status."""
    service = request.app.state.playback_service
    return service.get_status()


@router.post("/start")
async def start_playback(playback_req: PlaybackStartRequest, request: Request):
    """
    Start playback to a Chromecast device.

    Supports both FM and DAB+ modes:
    - If station_id is provided, uses the station's type and settings
    - If dab_channel is provided, uses DAB+ mode
    - Otherwise uses FM mode with frequency
    """
    service = request.app.state.playback_service

    # Parse unified speaker ID if it contains a prefix
    if ":" in playback_req.device_id:
        _, device_id = parse_speaker_id(playback_req.device_id)
    else:
        device_id = playback_req.device_id

    # Initialize parameters
    frequency = playback_req.frequency
    modulation = playback_req.modulation
    dab_channel = playback_req.dab_channel
    dab_program = playback_req.dab_program
    dab_service_id = playback_req.dab_service_id
    station_type = None

    # If station_id provided, use station settings
    if playback_req.station_id:
        station_service = get_station_service()
        station = station_service.get(playback_req.station_id)
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        station_type = station.station_type

        if station.station_type == StationType.DAB:
            dab_channel = station.dab_channel
            dab_program = station.dab_program
            dab_service_id = station.dab_service_id
        else:
            frequency = station.frequency
            modulation = station.modulation

    # Determine mode based on parameters
    if dab_channel:
        # DAB+ mode
        success = await service.start(
            device_id=device_id,
            dab_channel=dab_channel,
            dab_program=dab_program,
            dab_service_id=dab_service_id,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to start DAB+ playback. Check device and RTL-SDR connection.",
            )

        return {
            "message": "DAB+ playback started",
            "device_id": device_id,
            "radio_mode": "dab",
            "dab_channel": dab_channel,
            "dab_program": dab_program,
            "stream_url": service.stream_url,
        }
    elif frequency is not None:
        # FM mode
        success = await service.start(
            device_id=device_id,
            frequency=frequency,
            modulation=modulation,
        )

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to start FM playback. Check device and RTL-SDR connection.",
            )

        return {
            "message": "FM playback started",
            "device_id": device_id,
            "radio_mode": "fm",
            "frequency": frequency,
            "stream_url": service.stream_url,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Either station_id, frequency (FM), or dab_channel (DAB+) must be provided",
        )


@router.post("/stop")
async def stop_playback(request: Request):
    """Stop playback completely."""
    service = request.app.state.playback_service
    await service.stop()
    return {"message": "Playback stopped"}


@router.post("/pause")
async def pause_playback(request: Request):
    """Pause playback (keeps tuner running)."""
    service = request.app.state.playback_service
    success = await service.pause()
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause - not currently playing")
    return {"message": "Playback paused"}


@router.post("/resume")
async def resume_playback(request: Request):
    """Resume paused playback."""
    service = request.app.state.playback_service
    success = await service.resume()
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resume - not currently paused")
    return {"message": "Playback resumed"}


@router.post("/tune")
async def change_tune(tune_req: PlaybackStartRequest, request: Request):
    """
    Change tuning while playing.

    Supports switching between FM and DAB+ modes:
    - If station_id is provided, uses the station's type and settings
    - If dab_channel is provided, switches to DAB+ mode
    - If frequency is provided, switches to FM mode
    """
    service = request.app.state.playback_service

    # Initialize parameters
    frequency = tune_req.frequency
    modulation = tune_req.modulation
    dab_channel = tune_req.dab_channel
    dab_program = tune_req.dab_program
    dab_service_id = tune_req.dab_service_id

    # If station_id provided, use station settings
    if tune_req.station_id:
        station_service = get_station_service()
        station = station_service.get(tune_req.station_id)
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        if station.station_type == StationType.DAB:
            dab_channel = station.dab_channel
            dab_program = station.dab_program
            dab_service_id = station.dab_service_id
        else:
            frequency = station.frequency
            modulation = station.modulation

    # Determine mode based on parameters
    if dab_channel:
        # Switch to DAB+ mode
        success = await service.change_dab_program(
            channel=dab_channel,
            program=dab_program,
            service_id=dab_service_id,
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot tune DAB+ - not currently playing",
            )
        return {
            "message": f"Tuned to DAB+ channel {dab_channel}",
            "radio_mode": "dab",
            "dab_channel": dab_channel,
            "dab_program": dab_program,
        }
    elif frequency is not None:
        # Switch to FM mode
        success = await service.change_frequency(frequency, modulation)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot tune FM - not currently playing",
            )
        return {
            "message": f"Tuned to {frequency} MHz",
            "radio_mode": "fm",
            "frequency": frequency,
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Either station_id, frequency (FM), or dab_channel (DAB+) must be provided",
        )
