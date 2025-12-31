"""
Station presets API router.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import List

from app.models import Station, StationCreate, StationUpdate
from app.services.station_service import get_station_service
from app.services.logo_service import get_logo_service

router = APIRouter()


async def _fetch_and_update_logo(station_id: str, station_name: str):
    """Background task to fetch logo and update station."""
    logo_service = get_logo_service()
    station_service = get_station_service()

    logo_url = await logo_service.fetch_logo_for_station(station_name)
    if logo_url:
        station_service.update(station_id, StationUpdate(image_url=logo_url))


@router.get("", response_model=List[Station])
async def list_stations():
    """List all station presets."""
    service = get_station_service()
    return service.get_all()


@router.post("", response_model=Station, status_code=201)
async def create_station(station: StationCreate, background_tasks: BackgroundTasks):
    """Create a new station preset.

    If no image_url is provided, automatically searches RadioBrowser
    for a station logo in the background.
    """
    service = get_station_service()
    created_station = service.create(station)

    # If no image was provided, try to fetch one from RadioBrowser
    if not station.image_url:
        background_tasks.add_task(
            _fetch_and_update_logo,
            created_station.id,
            created_station.name,
        )

    return created_station


@router.get("/{station_id}", response_model=Station)
async def get_station(station_id: str):
    """Get a specific station preset."""
    service = get_station_service()
    station = service.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@router.put("/{station_id}", response_model=Station)
async def update_station(station_id: str, updates: StationUpdate):
    """Update a station preset."""
    service = get_station_service()
    station = service.update(station_id, updates)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@router.delete("/{station_id}", status_code=204)
async def delete_station(station_id: str):
    """Delete a station preset."""
    service = get_station_service()
    if not service.delete(station_id):
        raise HTTPException(status_code=404, detail="Station not found")


@router.post("/{station_id}/refresh-logo", response_model=Station)
async def refresh_station_logo(station_id: str):
    """
    Refresh the logo for a station by re-fetching from RadioBrowser.

    This will overwrite any existing logo with a fresh fetch.
    """
    station_service = get_station_service()
    logo_service = get_logo_service()

    station = station_service.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    # Force refresh the logo
    logo_url = await logo_service.fetch_logo_for_station(
        station.name, force_refresh=True
    )

    if logo_url:
        updated_station = station_service.update(
            station_id, StationUpdate(image_url=logo_url)
        )
        return updated_station

    # No logo found, return station as-is
    return station
