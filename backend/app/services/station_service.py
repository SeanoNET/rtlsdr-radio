"""
Station storage service - manages station presets.
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.models import Modulation, Station, StationCreate, StationUpdate

logger = logging.getLogger(__name__)


class StationService:
    def __init__(self, storage_path: str = "data/stations.json"):
        self._storage_path = Path(storage_path)
        self._stations: Dict[str, Station] = {}
        self._load()

    def _load(self):
        """Load stations from storage file."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        station = Station(**item)
                        self._stations[station.id] = station
                logger.info(f"Loaded {len(self._stations)} stations")
            except Exception as e:
                logger.error(f"Failed to load stations: {e}")
        else:
            # Create default stations
            self._create_defaults()

    def _save(self):
        """Save stations to storage file."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                data = [s.model_dump() for s in self._stations.values()]
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stations: {e}")

    def _create_defaults(self):
        """Create some default FM station presets (Perth, Western Australia)."""
        # (name, frequency, modulation, image_filename or None)
        defaults = [
            ("Nova 93.7", 93.7, Modulation.WFM, "nova.webp"),
            ("Mix 94.5", 94.5, Modulation.WFM, "945.jpg"),
            ("96FM", 96.1, Modulation.WFM, "96.jpg"),
            ("Triple M Perth", 92.9, Modulation.WFM, "triplem.png"),
            ("Triple J", 99.3, Modulation.WFM, "triplej.png"),
            ("6IX", 1080, Modulation.AM, "6ix.png"),
        ]

        for name, freq, mod, image in defaults:
            # Image URL will be served from static files
            image_url = f"/static/images/stations/{image}" if image else None
            self.create(
                StationCreate(
                    name=name,
                    frequency=freq,
                    modulation=mod,
                    image_url=image_url,
                )
            )

        logger.info("Created default station presets (Perth, WA)")

    def get_all(self) -> List[Station]:
        """Get all stations."""
        return list(self._stations.values())

    def get(self, station_id: str) -> Optional[Station]:
        """Get a station by ID."""
        return self._stations.get(station_id)

    def create(self, station: StationCreate) -> Station:
        """Create a new station."""
        station_id = str(uuid.uuid4())[:8]
        new_station = Station(
            id=station_id,
            name=station.name,
            frequency=station.frequency,
            modulation=station.modulation,
            image_url=station.image_url,
        )
        self._stations[station_id] = new_station
        self._save()
        return new_station

    def update(self, station_id: str, updates: StationUpdate) -> Optional[Station]:
        """Update an existing station."""
        station = self._stations.get(station_id)
        if not station:
            return None

        update_data = updates.model_dump(exclude_unset=True)
        updated_station = Station(
            id=station_id,
            name=update_data.get("name", station.name),
            frequency=update_data.get("frequency", station.frequency),
            modulation=update_data.get("modulation", station.modulation),
            image_url=update_data.get("image_url", station.image_url),
        )

        self._stations[station_id] = updated_station
        self._save()
        return updated_station

    def delete(self, station_id: str) -> bool:
        """Delete a station."""
        if station_id not in self._stations:
            return False

        del self._stations[station_id]
        self._save()
        return True


# Singleton instance
_station_service: Optional[StationService] = None


def get_station_service() -> StationService:
    """Get the station service singleton."""
    global _station_service
    if _station_service is None:
        _station_service = StationService()
    return _station_service
