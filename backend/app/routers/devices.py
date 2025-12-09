"""
Chromecast devices API router.
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List

from app.models import ChromecastDevice, VolumeRequest, MuteRequest

router = APIRouter()


@router.get("", response_model=List[ChromecastDevice])
async def list_devices(request: Request):
    """List all discovered Chromecast devices."""
    service = request.app.state.chromecast_service
    return service.get_devices()


@router.post("/refresh")
async def refresh_devices(request: Request):
    """Manually refresh the device list."""
    service = request.app.state.chromecast_service
    await service.refresh_devices()
    return {"message": "Device discovery refreshed"}


@router.get("/{device_id}", response_model=ChromecastDevice)
async def get_device(device_id: str, request: Request):
    """Get details for a specific device."""
    service = request.app.state.chromecast_service
    device = service.get_device_info(device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/{device_id}/volume")
async def get_volume(device_id: str, request: Request):
    """Get the current volume for a device."""
    service = request.app.state.chromecast_service
    volume = await service.get_volume(device_id)
    if volume is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"volume": volume}


@router.put("/{device_id}/volume")
async def set_volume(device_id: str, volume_req: VolumeRequest, request: Request):
    """Set the volume for a device (0.0 - 1.0)."""
    service = request.app.state.chromecast_service
    success = await service.set_volume(device_id, volume_req.volume)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"volume": volume_req.volume}


@router.post("/{device_id}/mute")
async def toggle_mute(device_id: str, mute_req: MuteRequest, request: Request):
    """Set mute state for a device."""
    service = request.app.state.chromecast_service
    success = await service.set_mute(device_id, mute_req.muted)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"muted": mute_req.muted}
