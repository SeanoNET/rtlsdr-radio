"""
Station presets API router.
"""
from fastapi import APIRouter, HTTPException
from typing import List

from app.models import Station, StationCreate, StationUpdate
from app.services.station_service import get_station_service

router = APIRouter()


@router.get("", response_model=List[Station])
async def list_stations():
    """List all station presets."""
    service = get_station_service()
    return service.get_all()


@router.post("", response_model=Station, status_code=201)
async def create_station(station: StationCreate):
    """Create a new station preset."""
    service = get_station_service()
    return service.create(station)


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
