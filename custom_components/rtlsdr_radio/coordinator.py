"""DataUpdateCoordinator for RTL-SDR Radio."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=5)


class RTLSDRRadioCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for RTL-SDR Radio API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.config_entry = entry
        self._host = entry.data[CONF_HOST]
        self._port = entry.data[CONF_PORT]
        self._base_url = f"http://{self._host}:{self._port}/api"
        self._session: aiohttp.ClientSession | None = None

    @property
    def base_url(self) -> str:
        """Return the base URL."""
        return self._base_url

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API."""
        try:
            session = await self._get_session()

            # Fetch playback status
            async with session.get(
                f"{self._base_url}/playback/status", timeout=10
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"API returned {response.status}")
                playback = await response.json()

            # Fetch stations
            async with session.get(
                f"{self._base_url}/stations", timeout=10
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"API returned {response.status}")
                stations = await response.json()

            # Fetch speakers
            async with session.get(
                f"{self._base_url}/speakers", timeout=10
            ) as response:
                if response.status != 200:
                    raise UpdateFailed(f"API returned {response.status}")
                speakers = await response.json()

            return {
                "playback": playback,
                "stations": stations,
                "speakers": speakers,
            }

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_play_station(self, station_id: str, device_id: str) -> bool:
        """Play a station on a device."""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/playback/start",
                json={"station_id": station_id, "device_id": device_id},
                timeout=30,
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_play_frequency(
        self, frequency: float, device_id: str, modulation: str = "wfm"
    ) -> bool:
        """Play a frequency on a device."""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/playback/start",
                json={
                    "frequency": frequency,
                    "modulation": modulation,
                    "device_id": device_id,
                },
                timeout=30,
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_stop(self) -> bool:
        """Stop playback."""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/playback/stop", timeout=10
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_pause(self) -> bool:
        """Pause playback."""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/playback/pause", timeout=10
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_resume(self) -> bool:
        """Resume playback."""
        try:
            session = await self._get_session()
            async with session.post(
                f"{self._base_url}/playback/resume", timeout=10
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_set_volume(self, device_id: str, volume: float) -> bool:
        """Set volume on a device."""
        try:
            session = await self._get_session()
            async with session.put(
                f"{self._base_url}/speakers/{device_id}/volume",
                json={"volume": volume},
                timeout=10,
            ) as response:
                return response.status == 200
        except aiohttp.ClientError:
            return False

    async def async_shutdown(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
