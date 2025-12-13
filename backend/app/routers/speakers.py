"""
Unified speakers API router - combines Chromecast and LMS players.
"""

from typing import List

from fastapi import APIRouter, HTTPException, Request

from app.models import MuteRequest, Speaker, SpeakerType, VolumeRequest

router = APIRouter()


def chromecast_to_speaker(device) -> Speaker:
    """Convert ChromecastDevice to unified Speaker."""
    return Speaker(
        id=f"chromecast:{device.id}",
        name=device.name,
        type=SpeakerType.CHROMECAST,
        model=device.model,
        ip_address=device.ip_address,
        volume=device.volume,
        is_available=not device.is_idle,
    )


def lms_to_speaker(player) -> Speaker:
    """Convert LMSPlayer to unified Speaker."""
    return Speaker(
        id=f"lms:{player.id}",
        name=player.name,
        type=SpeakerType.LMS,
        model=player.model,
        ip_address=player.ip_address,
        volume=player.volume,
        is_available=player.is_powered and player.connected,
    )


def parse_speaker_id(speaker_id: str) -> tuple[SpeakerType, str]:
    """Parse a unified speaker ID into type and device-specific ID."""
    if speaker_id.startswith("chromecast:"):
        return SpeakerType.CHROMECAST, speaker_id[11:]
    elif speaker_id.startswith("lms:"):
        return SpeakerType.LMS, speaker_id[4:]
    else:
        # Assume chromecast for backwards compatibility
        return SpeakerType.CHROMECAST, speaker_id


@router.get("", response_model=List[Speaker])
async def list_speakers(request: Request):
    """List all speakers (Chromecast and LMS combined)."""
    speakers = []

    # Get Chromecast devices
    chromecast_service = request.app.state.chromecast_service
    for device in chromecast_service.get_devices():
        speakers.append(chromecast_to_speaker(device))

    # Get LMS players
    lms_service = request.app.state.lms_service
    for player in lms_service.get_players():
        speakers.append(lms_to_speaker(player))

    return speakers


@router.post("/refresh")
async def refresh_speakers(request: Request):
    """Refresh all speaker sources."""
    chromecast_service = request.app.state.chromecast_service
    lms_service = request.app.state.lms_service

    await chromecast_service.refresh_devices()
    await lms_service.discover_players()

    return {"message": "Speaker discovery refreshed"}


@router.get("/{speaker_id}", response_model=Speaker)
async def get_speaker(speaker_id: str, request: Request):
    """Get details for a specific speaker."""
    speaker_type, device_id = parse_speaker_id(speaker_id)

    if speaker_type == SpeakerType.CHROMECAST:
        service = request.app.state.chromecast_service
        device = service.get_device_info(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return chromecast_to_speaker(device)

    elif speaker_type == SpeakerType.LMS:
        service = request.app.state.lms_service
        player = service.get_player(device_id)
        if not player:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return lms_to_speaker(player)


@router.get("/{speaker_id}/volume")
async def get_volume(speaker_id: str, request: Request):
    """Get the current volume for a speaker."""
    speaker_type, device_id = parse_speaker_id(speaker_id)

    if speaker_type == SpeakerType.CHROMECAST:
        service = request.app.state.chromecast_service
        volume = await service.get_volume(device_id)
    else:
        service = request.app.state.lms_service
        volume = await service.get_volume(device_id)

    if volume is None:
        raise HTTPException(status_code=404, detail="Speaker not found")

    return {"volume": volume}


@router.put("/{speaker_id}/volume")
async def set_volume(speaker_id: str, volume_req: VolumeRequest, request: Request):
    """Set the volume for a speaker (0.0 - 1.0)."""
    speaker_type, device_id = parse_speaker_id(speaker_id)

    if speaker_type == SpeakerType.CHROMECAST:
        service = request.app.state.chromecast_service
        success = await service.set_volume(device_id, volume_req.volume)
    else:
        service = request.app.state.lms_service
        success = await service.set_volume(device_id, volume_req.volume)

    if not success:
        raise HTTPException(status_code=404, detail="Speaker not found")

    return {"volume": volume_req.volume}


@router.post("/{speaker_id}/mute")
async def toggle_mute(speaker_id: str, mute_req: MuteRequest, request: Request):
    """Set mute state for a speaker (Chromecast only - LMS uses volume 0)."""
    speaker_type, device_id = parse_speaker_id(speaker_id)

    if speaker_type == SpeakerType.CHROMECAST:
        service = request.app.state.chromecast_service
        success = await service.set_mute(device_id, mute_req.muted)
        if not success:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return {"muted": mute_req.muted}

    else:
        # LMS doesn't have native mute - set volume to 0 instead
        service = request.app.state.lms_service
        if mute_req.muted:
            success = await service.set_volume(device_id, 0.0)
        else:
            # Can't restore previous volume, set to 50%
            success = await service.set_volume(device_id, 0.5)

        if not success:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return {"muted": mute_req.muted}


@router.post("/{speaker_id}/power")
async def set_power(speaker_id: str, request: Request, power: bool = True):
    """Power on/off a speaker. For LMS: power on/off. For Chromecast: stop casting."""
    speaker_type, device_id = parse_speaker_id(speaker_id)

    if speaker_type == SpeakerType.LMS:
        service = request.app.state.lms_service
        if power:
            success = await service.power_on(device_id)
        else:
            success = await service.power_off(device_id)

        if not success:
            raise HTTPException(status_code=404, detail="Speaker not found")
        return {"powered": power}

    elif speaker_type == SpeakerType.CHROMECAST:
        service = request.app.state.chromecast_service
        if not power:
            # Stop casting / quit app
            success = await service.quit_app(device_id)
            if not success:
                raise HTTPException(status_code=404, detail="Speaker not found")
        return {"powered": power}

    else:
        raise HTTPException(status_code=400, detail="Unknown speaker type")
