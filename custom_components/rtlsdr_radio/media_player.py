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
    async_add_entities([RTLSDRRadioMediaPlayer(coordinator, entry)])


class RTLSDRRadioMediaPlayer(
    CoordinatorEntity[RTLSDRRadioCoordinator], MediaPlayerEntity
):
    """Representation of the RTL-SDR Radio media player."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:radio"

    def __init__(
        self,
        coordinator: RTLSDRRadioCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "RTL-SDR Radio",
            "manufacturer": "RTL-SDR",
            "model": "FM Radio Receiver",
            "sw_version": "1.0.0",
        }
        self._selected_speaker: str | None = None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features."""
        features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.VOLUME_SET
        )
        return features

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the player."""
        if not self.coordinator.data:
            return MediaPlayerState.IDLE

        playback = self.coordinator.data.get("playback", {})
        state_str = playback.get("state", "stopped")
        return STATE_MAP.get(state_str, MediaPlayerState.IDLE)

    @property
    def media_title(self) -> str | None:
        """Return the title of the current media."""
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
        attrs = {}

        if self.coordinator.data:
            playback = self.coordinator.data.get("playback", {})
            attrs["frequency"] = playback.get("frequency")
            attrs["modulation"] = playback.get("modulation")
            attrs["device_id"] = playback.get("device_id")
            attrs["device_name"] = playback.get("device_name")
            attrs["device_type"] = playback.get("device_type")

            # Add available speakers
            speakers = self.coordinator.data.get("speakers", [])
            attrs["available_speakers"] = [
                {"id": s["id"], "name": s["name"], "type": s["type"]} for s in speakers
            ]

            # Selected speaker
            attrs["selected_speaker"] = self._selected_speaker or playback.get(
                "device_id"
            )

        return attrs

    async def async_select_source(self, source: str) -> None:
        """Select a source (station)."""
        if not self.coordinator.data:
            return

        stations = self.coordinator.data.get("stations", [])
        station = next((s for s in stations if s["name"] == source), None)

        if not station:
            _LOGGER.error("Station not found: %s", source)
            return

        # Get current device or first available speaker
        playback = self.coordinator.data.get("playback", {})
        device_id = self._selected_speaker or playback.get("device_id")

        if not device_id:
            # Use first available speaker
            speakers = self.coordinator.data.get("speakers", [])
            if speakers:
                device_id = speakers[0]["id"]
                self._selected_speaker = device_id

        if device_id:
            await self.coordinator.async_play_station(station["id"], device_id)
            await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Play or resume playback."""
        if self.state == MediaPlayerState.PAUSED:
            await self.coordinator.async_resume()
        elif self.state == MediaPlayerState.IDLE:
            # If we have a selected source and speaker, play it
            if self.source and self._selected_speaker:
                await self.async_select_source(self.source)
        await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self.coordinator.async_pause()
        await self.coordinator.async_request_refresh()

    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self.coordinator.async_stop()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        if not self.coordinator.data:
            return

        playback = self.coordinator.data.get("playback", {})
        device_id = playback.get("device_id")

        if device_id:
            await self.coordinator.async_set_volume(device_id, volume)
            await self.coordinator.async_request_refresh()

    def set_speaker(self, speaker_id: str) -> None:
        """Set the selected speaker for playback."""
        self._selected_speaker = speaker_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
