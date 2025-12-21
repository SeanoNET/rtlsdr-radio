"""
Station storage service - manages station presets.
"""

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from app.models import Modulation, Station, StationCreate, StationType, StationUpdate

logger = logging.getLogger(__name__)


class StationService:
    def __init__(self, storage_path: str = "data/stations.json"):
        self._storage_path = Path(storage_path)
        self._stations: Dict[str, Station] = {}
        self._default_mode: str = "all"
        self._load()

    def _get_current_mode(self) -> str:
        """Get the current DEFAULT_STATIONS mode from env."""
        return os.environ.get("DEFAULT_STATIONS", "all").lower().strip()

    def _load(self):
        """Load stations from storage file, regenerating if mode changed."""
        current_mode = self._get_current_mode()

        if self._storage_path.exists():
            try:
                with open(self._storage_path, "r") as f:
                    data = json.load(f)

                # Handle new format with mode tracking
                if isinstance(data, dict) and "stations" in data:
                    saved_mode = data.get("default_mode", "all")
                    stations_data = data.get("stations", [])
                else:
                    # Legacy format: just an array of stations
                    saved_mode = None
                    stations_data = data

                # Check if mode changed - regenerate defaults
                if saved_mode != current_mode:
                    logger.info(
                        f"DEFAULT_STATIONS changed from '{saved_mode}' to '{current_mode}', "
                        "regenerating default stations"
                    )
                    self._default_mode = current_mode
                    self._create_defaults()
                    return

                # Load stations normally
                self._default_mode = saved_mode or current_mode
                for item in stations_data:
                    station = Station(**item)
                    self._stations[station.id] = station
                logger.info(f"Loaded {len(self._stations)} stations")

            except Exception as e:
                logger.error(f"Failed to load stations: {e}")
                self._default_mode = current_mode
                self._create_defaults()
        else:
            # No file exists, create defaults
            self._default_mode = current_mode
            self._create_defaults()

    def _save(self):
        """Save stations to storage file with mode tracking."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._storage_path, "w") as f:
                data = {
                    "default_mode": self._default_mode,
                    "stations": [s.model_dump() for s in self._stations.values()]
                }
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save stations: {e}")

    def _create_defaults(self):
        """Create default station presets based on DEFAULT_STATIONS env var.

        Env var options:
            - "dab" or "dab+" : Only DAB+ stations (for DAB+ antenna setups)
            - "fm" : Only FM stations (for FM antenna setups)
            - "all" or "both" : Both FM and DAB+ stations (default)
            - "none" : No default stations
        """
        mode = self._default_mode

        if mode == "none":
            logger.info("DEFAULT_STATIONS=none, skipping default station creation")
            return

        # FM defaults: (name, frequency, modulation, image_filename)
        fm_defaults = [
            ("Nova 93.7", 93.7, Modulation.WFM, "nova.webp"),
            ("Mix 94.5", 94.5, Modulation.WFM, "945.jpg"),
            ("96FM", 96.1, Modulation.WFM, "96.jpg"),
            ("Triple M Perth", 92.9, Modulation.WFM, "triplem.png"),
            ("Triple J", 99.3, Modulation.WFM, "triplej.png"),
        ]

        # DAB+ defaults: (name, channel, program_name, image_filename)
        # Perth DAB+ commercial stations on 9C, ABC stations on 9A/9B
        dab_defaults = [
            ("Nova 937", "9C", "Nova 937", "nova.webp"),
            ("Mix 94.5", "9C", "Mix 94.5", "945.jpg"),
            ("96FM", "9C", "96FM", "96.jpg"),
            ("Triple M", "9C", "Triple M", "triplem.png"),
            ("Triple J", "9B", "Triple J", "triplej.png"),
            ("Double J", "9B", "Double J", None),
            ("ABC Perth", "9A", "ABC Perth", "abc.png"),
        ]

        created = []

        # Create FM defaults
        if mode in ("fm", "all", "both"):
            for name, freq, mod, image in fm_defaults:
                image_url = f"/static/images/stations/{image}" if image else None
                self.create(
                    StationCreate(
                        name=name,
                        station_type=StationType.FM,
                        frequency=freq,
                        modulation=mod,
                        image_url=image_url,
                    )
                )
            created.append("FM")

        # Create DAB+ defaults
        if mode in ("dab", "dab+", "all", "both"):
            for name, channel, program, image in dab_defaults:
                image_url = f"/static/images/stations/{image}" if image else None
                self.create(
                    StationCreate(
                        name=name,
                        station_type=StationType.DAB,
                        dab_channel=channel,
                        dab_program=program,
                        image_url=image_url,
                    )
                )
            created.append("DAB+")

        if created:
            logger.info(f"Created default {' and '.join(created)} station presets (Perth, WA)")

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
            station_type=station.station_type,
            image_url=station.image_url,
            # FM fields
            frequency=station.frequency,
            modulation=station.modulation,
            # DAB fields
            dab_channel=station.dab_channel,
            dab_program=station.dab_program,
            dab_service_id=station.dab_service_id,
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
            station_type=update_data.get("station_type", station.station_type),
            image_url=update_data.get("image_url", station.image_url),
            # FM fields
            frequency=update_data.get("frequency", station.frequency),
            modulation=update_data.get("modulation", station.modulation),
            # DAB fields
            dab_channel=update_data.get("dab_channel", station.dab_channel),
            dab_program=update_data.get("dab_program", station.dab_program),
            dab_service_id=update_data.get("dab_service_id", station.dab_service_id),
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
