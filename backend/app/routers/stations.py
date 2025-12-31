"""
Station presets API router.
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from typing import List, Optional

from app.models import Station, StationCreate, StationUpdate
from app.services.station_service import get_station_service
from app.services.logo_service import get_logo_service

router = APIRouter()


def _get_base_url(request: Request) -> str:
    """Get the base URL for building absolute URLs.

    Uses X-Forwarded headers if behind a reverse proxy.
    """
    scheme = request.headers.get("X-Forwarded-Proto", request.url.scheme)
    host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", request.url.netloc))
    return f"{scheme}://{host}"


def _make_absolute_url(image_url: Optional[str], base_url: str) -> Optional[str]:
    """Convert a relative image URL to an absolute URL."""
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return image_url  # Already absolute
    return f"{base_url}{image_url}"


def _stations_with_absolute_urls(stations: List[Station], base_url: str) -> List[dict]:
    """Convert station list to dicts with absolute image URLs."""
    result = []
    for station in stations:
        station_dict = station.model_dump()
        station_dict["image_url"] = _make_absolute_url(station.image_url, base_url)
        result.append(station_dict)
    return result


async def _fetch_and_update_logo(station_id: str, station_name: str):
    """Background task to fetch logo and update station."""
    logo_service = get_logo_service()
    station_service = get_station_service()

    logo_url = await logo_service.fetch_logo_for_station(station_name)
    if logo_url:
        station_service.update(station_id, StationUpdate(image_url=logo_url))


async def _fetch_missing_logos(stations: List[Station]):
    """Background task to fetch logos for stations missing images."""
    logo_service = get_logo_service()
    station_service = get_station_service()

    for station in stations:
        if not station.image_url:
            logo_url = await logo_service.fetch_logo_for_station(station.name)
            if logo_url:
                station_service.update(station.id, StationUpdate(image_url=logo_url))


@router.get("")
async def list_stations(request: Request, background_tasks: BackgroundTasks):
    """List all station presets.

    If any stations are missing logos, a background task will attempt
    to fetch them from RadioBrowser. The logos will be available on
    subsequent requests.

    Image URLs are returned as absolute URLs for compatibility with
    external clients like Music Assistant.
    """
    service = get_station_service()
    stations = service.get_all()

    # Check if any stations are missing logos
    missing_logos = [s for s in stations if not s.image_url]
    if missing_logos:
        background_tasks.add_task(_fetch_missing_logos, missing_logos)

    # Return with absolute URLs
    base_url = _get_base_url(request)
    return _stations_with_absolute_urls(stations, base_url)


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


@router.post("/refresh-logos")
async def refresh_all_logos(background_tasks: BackgroundTasks):
    """
    Refresh logos for all stations by re-fetching from RadioBrowser.

    This runs in the background and will update stations as logos are found.
    Use this after fixing RadioBrowser connectivity issues or to bulk-update logos.
    """
    station_service = get_station_service()
    stations = station_service.get_all()

    async def _refresh_all(stations_to_refresh: List[Station]):
        logo_service = get_logo_service()
        for station in stations_to_refresh:
            logo_url = await logo_service.fetch_logo_for_station(
                station.name, force_refresh=True
            )
            if logo_url:
                station_service.update(station.id, StationUpdate(image_url=logo_url))

    background_tasks.add_task(_refresh_all, stations)

    return {
        "message": f"Refreshing logos for {len(stations)} stations in background",
        "station_count": len(stations),
    }


@router.get("/{station_id}")
async def get_station(station_id: str, request: Request):
    """Get a specific station preset."""
    service = get_station_service()
    station = service.get(station_id)
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    # Return with absolute URL
    base_url = _get_base_url(request)
    station_dict = station.model_dump()
    station_dict["image_url"] = _make_absolute_url(station.image_url, base_url)
    return station_dict


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
