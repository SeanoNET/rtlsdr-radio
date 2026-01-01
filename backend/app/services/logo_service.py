"""
Logo service - fetches radio station logos from RadioBrowser API.
"""

import hashlib
import logging
import os
import re
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import aiohttp

# How long to wait before retrying a failed logo fetch (24 hours)
FAILED_RETRY_SECONDS = 24 * 60 * 60

logger = logging.getLogger(__name__)


def generate_search_variations(station_name: str) -> List[str]:
    """
    Generate variations of a station name to improve RadioBrowser matching.

    Examples:
        "Nova 937" -> ["Nova 937", "Nova 93.7", "Nova"]
        "92.9 Triple M" -> ["92.9 Triple M", "Triple M", "Triple M Perth"]
        "ABC PERTH" -> ["ABC PERTH", "ABC Perth", "ABC"]
    """
    variations = []
    name = station_name.strip()

    # 1. Original name
    variations.append(name)

    # 2. Try adding decimal point to frequencies (Nova937 -> Nova 93.7)
    freq_pattern = r'(\d{2,3})(\d)$'
    if re.search(freq_pattern, name):
        with_decimal = re.sub(freq_pattern, r'\1.\2', name)
        variations.append(with_decimal)

    # Also try pattern like "Nova 937" -> "Nova 93.7"
    freq_pattern2 = r'(\d{2})(\d)\s*$'
    match = re.search(freq_pattern2, name)
    if match:
        with_decimal = name[:match.start()] + match.group(1) + '.' + match.group(2)
        variations.append(with_decimal)

    # 3. Remove leading frequency numbers (92.9 Triple M -> Triple M)
    without_freq = re.sub(r'^[\d.]+\s*', '', name).strip()
    if without_freq and without_freq != name:
        variations.append(without_freq)

    # 4. Remove trailing city name from original (6PR Perth -> 6PR)
    cities = ['Perth', 'Sydney', 'Melbourne', 'Brisbane']
    without_city = re.sub(r'\s+(Perth|Sydney|Melbourne|Brisbane)$', '', name, flags=re.IGNORECASE)
    if without_city and without_city != name and without_city not in variations:
        variations.append(without_city)

    # 5. Try with common Australian city names appended
    base_name = without_freq if without_freq else name
    # Remove existing city suffix first
    base_clean = re.sub(r'\s+(Perth|Sydney|Melbourne|Brisbane)$', '', base_name, flags=re.IGNORECASE)
    for city in cities:
        city_variation = f"{base_clean} {city}"
        if city_variation not in variations:
            variations.append(city_variation)

    # 6. Title case variation (ABC PERTH -> ABC Perth)
    if name.isupper():
        title_case = name.title()
        if title_case not in variations:
            variations.append(title_case)

    # 7. Just the base name without numbers or city
    base_only = re.sub(r'[\d.]+', '', base_clean).strip()
    if base_only and base_only not in variations and len(base_only) > 2:
        variations.append(base_only)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for v in variations:
        if v.lower() not in seen and v:
            seen.add(v.lower())
            unique.append(v)

    return unique

# RadioBrowser API endpoints (fetched from all.api.radio-browser.info/json/servers)
# These change over time - update if logo fetching stops working
RADIO_BROWSER_SERVERS = [
    "https://de2.api.radio-browser.info",
    "https://fi1.api.radio-browser.info",
]

# Image storage path - must match the static files mount in main.py
LOGO_STORAGE_PATH = Path(__file__).parent.parent / "static" / "images" / "stations"


class LogoService:
    """Service for fetching and caching radio station logos."""

    def __init__(self, storage_path: Path = LOGO_STORAGE_PATH):
        self._storage_path = storage_path
        self._storage_path.mkdir(parents=True, exist_ok=True)

    def _get_logo_filename(self, station_name: str) -> str:
        """Generate a consistent filename based on station name hash."""
        name_hash = hashlib.md5(station_name.lower().encode()).hexdigest()[:12]
        return f"logo_{name_hash}"

    def _get_failed_marker_path(self, station_name: str) -> Path:
        """Get the path to the failed marker file for a station."""
        base_filename = self._get_logo_filename(station_name)
        return self._storage_path / f"{base_filename}.failed"

    def _is_fetch_failed(self, station_name: str) -> bool:
        """Check if logo fetch previously failed and shouldn't be retried yet."""
        failed_path = self._get_failed_marker_path(station_name)
        if not failed_path.exists():
            return False

        # Check if enough time has passed to retry
        try:
            mtime = failed_path.stat().st_mtime
            age = time.time() - mtime
            if age < FAILED_RETRY_SECONDS:
                logger.debug(
                    "Skipping logo fetch for %s (failed %d min ago, retry in %d min)",
                    station_name,
                    int(age / 60),
                    int((FAILED_RETRY_SECONDS - age) / 60),
                )
                return True
            # Enough time has passed, remove the marker and allow retry
            failed_path.unlink()
        except OSError:
            pass
        return False

    def _mark_fetch_failed(self, station_name: str) -> None:
        """Mark a station's logo fetch as failed to prevent repeated attempts."""
        failed_path = self._get_failed_marker_path(station_name)
        try:
            failed_path.touch()
            logger.info("Marked logo fetch as failed for %s (will retry in 24h)", station_name)
        except OSError as e:
            logger.warning("Could not create failed marker: %s", e)

    def _clear_failed_marker(self, station_name: str) -> None:
        """Clear the failed marker for a station (used on force refresh)."""
        failed_path = self._get_failed_marker_path(station_name)
        if failed_path.exists():
            try:
                failed_path.unlink()
            except OSError:
                pass

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
        # On force refresh, clear any failed marker
        if force_refresh:
            self._clear_failed_marker(station_name)

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_url = self.get_cached_logo_url(station_name)
            if cached_url:
                logger.debug("Using cached logo for %s: %s", station_name, cached_url)
                return cached_url

            # Check if previously failed - skip if so
            if self._is_fetch_failed(station_name):
                return None

        # Search RadioBrowser API
        favicon_url = await self._search_radio_browser(station_name)
        if not favicon_url:
            logger.debug("No logo found for station: %s", station_name)
            self._mark_fetch_failed(station_name)
            return None

        # Download and cache the logo
        local_path = await self._download_logo(station_name, favicon_url)
        if local_path:
            return f"/static/images/stations/{local_path.name}"

        # Download failed - mark as failed
        self._mark_fetch_failed(station_name)
        return None

    async def _search_radio_browser(self, station_name: str) -> Optional[str]:
        """Search RadioBrowser API for a station and return its favicon URL.

        Tries multiple name variations to improve matching success.
        """
        variations = generate_search_variations(station_name)
        logger.debug("Searching RadioBrowser for %s with variations: %s", station_name, variations)

        async with aiohttp.ClientSession() as session:
            headers = {"User-Agent": "rtlsdr-radio/1.0"}

            for server in RADIO_BROWSER_SERVERS:
                try:
                    # Try each name variation
                    for search_name in variations:
                        # First try exact name match
                        url = f"{server}/json/stations/byname/{search_name}"

                        async with session.get(
                            url,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as response:
                            if response.status == 200:
                                stations = await response.json()
                                favicon = self._find_best_favicon(stations)
                                if favicon:
                                    logger.info(
                                        "Found logo for '%s' (searched: '%s'): %s",
                                        station_name, search_name, favicon
                                    )
                                    return favicon

                        # Try flexible search
                        url = f"{server}/json/stations/search"
                        params = {"name": search_name, "limit": 10}
                        async with session.get(
                            url,
                            params=params,
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as search_response:
                            if search_response.status == 200:
                                stations = await search_response.json()
                                favicon = self._find_best_favicon(stations)
                                if favicon:
                                    logger.info(
                                        "Found logo for '%s' (searched: '%s'): %s",
                                        station_name, search_name, favicon
                                    )
                                    return favicon

                    # No favicon found with any variation on this server, try next
                    logger.debug("No logo found on %s for %s", server, station_name)
                    break  # Try next server instead of returning

                except aiohttp.ClientError as e:
                    logger.warning("RadioBrowser server %s failed: %s: %s", server, type(e).__name__, e)
                    continue
                except Exception as e:
                    logger.error("Error searching RadioBrowser: %s: %s", type(e).__name__, e)
                    continue

        return None

    def _find_best_favicon(self, stations: list) -> Optional[str]:
        """Find the best favicon from a list of station results.

        Prioritizes stations with higher votes/clicks as they're more likely
        to have valid, high-quality favicons.
        """
        if not stations:
            return None

        # Sort by votes (popularity) to get best quality icons
        sorted_stations = sorted(
            stations,
            key=lambda s: (s.get("votes", 0), s.get("clickcount", 0)),
            reverse=True
        )

        for station in sorted_stations:
            favicon = station.get("favicon")
            if favicon and favicon.strip():
                return favicon.strip()

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
