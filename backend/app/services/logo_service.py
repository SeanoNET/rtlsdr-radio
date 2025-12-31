"""
Logo service - fetches radio station logos from RadioBrowser API.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)

# RadioBrowser API endpoints (fetched from all.api.radio-browser.info/json/servers)
# These change over time - update if logo fetching stops working
RADIO_BROWSER_SERVERS = [
    "https://de2.api.radio-browser.info",
    "https://fi1.api.radio-browser.info",
]

# Image storage path
LOGO_STORAGE_PATH = Path("static/images/stations")


class LogoService:
    """Service for fetching and caching radio station logos."""

    def __init__(self, storage_path: Path = LOGO_STORAGE_PATH):
        self._storage_path = storage_path
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _get_logo_filename(self, station_name: str) -> str:
        """Generate a consistent filename based on station name hash."""
        name_hash = hashlib.md5(station_name.lower().encode()).hexdigest()[:12]
        return f"logo_{name_hash}"

    def _get_cached_logo_path(self, station_name: str) -> Optional[Path]:
        """Check if a logo already exists for this station name."""
        base_filename = self._get_logo_filename(station_name)
        # Check for common image extensions
        for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"]:
            path = self._storage_path / f"{base_filename}{ext}"
            if path.exists():
                return path
        return None

    def get_cached_logo_url(self, station_name: str) -> Optional[str]:
        """Get the URL for a cached logo, if it exists."""
        cached_path = self._get_cached_logo_path(station_name)
        if cached_path:
            return f"/static/images/stations/{cached_path.name}"
        return None

    async def fetch_logo_for_station(
        self, station_name: str, force_refresh: bool = False
    ) -> Optional[str]:
        """
        Fetch and cache a logo for the given station name.

        Args:
            station_name: Name of the radio station to search for
            force_refresh: If True, re-fetch even if cached

        Returns:
            Relative URL to the cached logo, or None if not found
        """
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_url = self.get_cached_logo_url(station_name)
            if cached_url:
                logger.debug("Using cached logo for %s: %s", station_name, cached_url)
                return cached_url

        # Search RadioBrowser API
        favicon_url = await self._search_radio_browser(station_name)
        if not favicon_url:
            logger.debug("No logo found for station: %s", station_name)
            return None

        # Download and cache the logo
        local_path = await self._download_logo(station_name, favicon_url)
        if local_path:
            return f"/static/images/stations/{local_path.name}"

        return None

    async def _search_radio_browser(self, station_name: str) -> Optional[str]:
        """Search RadioBrowser API for a station and return its favicon URL."""
        # Clean up station name for search
        search_name = station_name.strip()

        async with aiohttp.ClientSession() as session:
            for server in RADIO_BROWSER_SERVERS:
                try:
                    url = f"{server}/json/stations/byname/{search_name}"
                    headers = {"User-Agent": "rtlsdr-radio/1.0"}

                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=5),
                    ) as response:
                        if response.status != 200:
                            continue

                        stations = await response.json()
                        if not stations:
                            # Try a more flexible search
                            url = f"{server}/json/stations/search"
                            params = {"name": search_name, "limit": 5}
                            async with session.get(
                                url,
                                params=params,
                                headers=headers,
                                timeout=aiohttp.ClientTimeout(total=5),
                            ) as search_response:
                                if search_response.status == 200:
                                    stations = await search_response.json()

                        # Find best match with a favicon
                        for station in stations:
                            favicon = station.get("favicon")
                            if favicon and favicon.strip():
                                logger.info(
                                    "Found logo for %s from RadioBrowser: %s",
                                    station_name,
                                    favicon,
                                )
                                return favicon

                        # No favicon found in results
                        return None

                except aiohttp.ClientError as e:
                    logger.warning("RadioBrowser server %s failed: %s", server, e)
                    continue
                except Exception as e:
                    logger.error("Error searching RadioBrowser: %s", e)
                    continue

        return None

    async def _download_logo(
        self, station_name: str, favicon_url: str
    ) -> Optional[Path]:
        """Download a logo from URL and save it locally."""
        try:
            # Determine file extension from URL
            parsed = urlparse(favicon_url)
            path_ext = Path(parsed.path).suffix.lower()
            if path_ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"]:
                path_ext = ".png"  # Default to PNG

            base_filename = self._get_logo_filename(station_name)
            local_path = self._storage_path / f"{base_filename}{path_ext}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    favicon_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"User-Agent": "rtlsdr-radio/1.0"},
                ) as response:
                    if response.status != 200:
                        logger.warning(
                            "Failed to download logo from %s: HTTP %d",
                            favicon_url,
                            response.status,
                        )
                        return None

                    # Check content type
                    content_type = response.headers.get("Content-Type", "")
                    if not content_type.startswith("image/"):
                        logger.warning(
                            "Invalid content type for logo: %s", content_type
                        )
                        return None

                    # Download and save
                    content = await response.read()
                    if len(content) < 100:  # Probably not a valid image
                        logger.warning("Downloaded logo too small, skipping")
                        return None

                    # Remove old cached versions with different extensions
                    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico"]:
                        old_path = self._storage_path / f"{base_filename}{ext}"
                        if old_path.exists() and old_path != local_path:
                            old_path.unlink()

                    with open(local_path, "wb") as f:
                        f.write(content)

                    logger.info("Saved logo for %s to %s", station_name, local_path)
                    return local_path

        except aiohttp.ClientError as e:
            logger.warning("Failed to download logo from %s: %s", favicon_url, e)
            return None
        except Exception as e:
            logger.error("Error saving logo: %s", e)
            return None

    def delete_cached_logo(self, station_name: str) -> bool:
        """Delete the cached logo for a station."""
        cached_path = self._get_cached_logo_path(station_name)
        if cached_path and cached_path.exists():
            cached_path.unlink()
            logger.info("Deleted cached logo: %s", cached_path)
            return True
        return False


# Singleton instance
_logo_service: Optional[LogoService] = None


def get_logo_service() -> LogoService:
    """Get the logo service singleton."""
    global _logo_service
    if _logo_service is None:
        _logo_service = LogoService()
    return _logo_service
