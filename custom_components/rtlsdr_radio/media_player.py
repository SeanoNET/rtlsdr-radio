"""Media player platform for RTL-SDR Radio."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RTLSDRRadioCoordinator

_LOGGER = logging.getLogger(__name__)

STATE_MAP = {
    "stopped": MediaPlayerState.IDLE,
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "buffering": MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up RTL-SDR Radio media player from a config entry."""
    coordinator: RTLSDRRadioCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track which speakers we've created entities for
    tracked_speakers: set[str] = set()

    @callback
    def async_add_speaker_entities() -> None:
        """Add entities for any new speakers."""
        if not coordinator.data:
            return

        speakers = coordinator.data.get("speakers", [])
        new_entities = []

        for speaker in speakers:
            speaker_id = speaker["id"]
            if speaker_id not in tracked_speakers:
                tracked_speakers.add(speaker_id)
                new_entities.append(RTLSDRRadioMediaPlayer(coordinator, entry, speaker))
                _LOGGER.debug("Adding new speaker entity: %s", speaker["name"])

        if new_entities:
            async_add_entities(new_entities)

    # Add initial entities
    async_add_speaker_entities()

    # Listen for coordinator updates to add new speakers
    entry.async_on_unload(coordinator.async_add_listener(async_add_speaker_entities))


class RTLSDRRadioMediaPlayer(
    CoordinatorEntity[RTLSDRRadioCoordinator], MediaPlayerEntity
):
    """Representation of an RTL-SDR Radio speaker as a media player."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:radio"

    def __init__(
        self,
        coordinator: RTLSDRRadioCoordinator,
        entry: ConfigEntry,
        speaker: dict,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._entry = entry
        self._speaker_id = speaker["id"]
        self._speaker_name = speaker["name"]
        self._speaker_type = speaker.get("type", "unknown")
        self._attr_unique_id = f"{entry.entry_id}_{speaker['id']}"
        self._attr_name = speaker["name"]

        # Set icon based on speaker type
        if self._speaker_type == "chromecast":
            self._attr_icon = "mdi:cast-audio"
        elif self._speaker_type == "lms":
            self._attr_icon = "mdi:speaker"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "RTL-SDR Radio",
            "manufacturer": "RTL-SDR",
            "model": "FM Radio Receiver",
            "sw_version": "1.0.0",
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.data:
            return False

        # Check if this speaker still exists
        speakers = self.coordinator.data.get("speakers", [])
        return any(s["id"] == self._speaker_id for s in speakers)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features."""
        return (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_SET
        )

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        if not self.coordinator.data:
            return MediaPlayerState.IDLE

        playback = self.coordinator.data.get("playback", {})

        # Only show as playing if this speaker is the active one
        active_device = playback.get("device_id")
        if active_device != self._speaker_id:
            return MediaPlayerState.IDLE

        state_str = playback.get("state", "stopped")
        return STATE_MAP.get(state_str, MediaPlayerState.IDLE)

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        if not self.coordinator.data:
            return None

        speakers = self.coordinator.data.get("speakers", [])
        for speaker in speakers:
            if speaker["id"] == self._speaker_id:
                return speaker.get("volume")
        return None

    @property
    def media_title(self) -> str | None:
        """Return the title of the current media."""
        if self.state == MediaPlayerState.IDLE:
            return None

        if not self.coordinator.data:
            return None

        playback = self.coordinator.data.get("playback", {})
        frequency = playback.get("frequency")
        if frequency:
            # Check if this frequency matches a station
            stations = self.coordinator.data.get("stations", [])
            for station in stations:
                if abs(station.get("frequency", 0) - frequency) < 0.05:
                    return f"{station['name']} ({frequency} MHz)"
            return f"{frequency} MHz"
        return None

    @property
    def source(self) -> str | None:
        """Return the current source (station name)."""
        if self.state == MediaPlayerState.IDLE:
            return None

        if not self.coordinator.data:
            return None

        playback = self.coordinator.data.get("playback", {})
        frequency = playback.get("frequency")
        if frequency:
            stations = self.coordinator.data.get("stations", [])
            for station in stations:
                if abs(station.get("frequency", 0) - frequency) < 0.05:
                    return station["name"]
        return None

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available sources (stations)."""
        if not self.coordinator.data:
            return None

        stations = self.coordinator.data.get("stations", [])
        return [station["name"] for station in stations]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {
            "speaker_id": self._speaker_id,
            "speaker_type": self._speaker_type,
        }

        if self.coordinator.data and self.state != MediaPlayerState.IDLE:
            playback = self.coordinator.data.get("playback", {})
            attrs["frequency"] = playback.get("frequency")
            attrs["modulation"] = playback.get("modulation")

        return attrs

    async def async_select_source(self, source: str) -> None:
        """Select a source (station) to play on this speaker."""
        if not self.coordinator.data:
            _LOGGER.error("No data available")
            return

        stations = self.coordinator.data.get("stations", [])
        station = next((s for s in stations if s["name"] == source), None)

        if not station:
            _LOGGER.error("Station not found: %s", source)
            return

        await self.coordinator.async_play_station(station["id"], self._speaker_id)
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Play or resume playback."""
        if self.state == MediaPlayerState.PAUSED:
            await self.coordinator.async_resume()
            await self.coordinator.async_request_refresh()
        elif self.state == MediaPlayerState.IDLE:
            # If idle, user needs to select a source first
            _LOGGER.debug("Select a station source to start playback")

    async def async_media_pause(self) -> None:
        """Pause playback."""
        if self.state == MediaPlayerState.PLAYING:
            await self.coordinator.async_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Stop playback."""
        if self.state != MediaPlayerState.IDLE:
            await self.coordinator.async_stop()
            await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.coordinator.async_set_volume(self._speaker_id, volume)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
