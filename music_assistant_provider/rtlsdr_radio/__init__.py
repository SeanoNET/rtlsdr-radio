"""RTL-SDR Radio provider for Music Assistant."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import aiohttp
from music_assistant.models.music_provider import MusicProvider
from music_assistant_models.config_entries import ConfigEntry
from music_assistant_models.enums import (
    ConfigEntryType,
    ContentType,
    ImageType,
    LinkType,
    MediaType,
    ProviderFeature,
    StreamType,
)
from music_assistant_models.media_items import (
    AudioFormat,
    MediaItemImage,
    MediaItemLink,
    ProviderMapping,
    Radio,
    UniqueList,
)
from music_assistant_models.streamdetails import StreamDetails

SUPPORTED_FEATURES = {
    ProviderFeature.LIBRARY_RADIOS,
    ProviderFeature.BROWSE,
}

if TYPE_CHECKING:
    from music_assistant.mass import MusicAssistant
    from music_assistant.models import ProviderInstanceType
    from music_assistant_models.config_entries import ConfigValueType, ProviderConfig
    from music_assistant_models.provider import ProviderManifest


async def setup(
    mass: MusicAssistant, manifest: ProviderManifest, config: ProviderConfig
) -> ProviderInstanceType:
    """Initialize provider(instance) with given configuration."""
    return RTLSDRRadioProvider(mass, manifest, config)


async def get_config_entries(
    mass: MusicAssistant,
    instance_id: str | None = None,
    action: str | None = None,
    values: dict[str, ConfigValueType] | None = None,
) -> tuple[ConfigEntry, ...]:
    """Return Config entries to setup this provider."""
    return (
        ConfigEntry(
            key="host",
            type=ConfigEntryType.STRING,
            label="RTL-SDR Radio Host",
            default_value="rtlsdr-backend",
            description="Hostname or IP of the RTL-SDR Radio backend",
            required=True,
        ),
        ConfigEntry(
            key="port",
            type=ConfigEntryType.INTEGER,
            label="API Port",
            default_value=8000,
            description="Port for the RTL-SDR Radio API",
            required=True,
        ),
    )


class RTLSDRRadioProvider(MusicProvider):
    """Music Provider for RTL-SDR Radio stations."""

    _host: str
    _port: int
    _session: aiohttp.ClientSession | None = None

    @property
    def supported_features(self) -> set[ProviderFeature]:
        """Return the features supported by this Provider."""
        return SUPPORTED_FEATURES

    async def handle_async_init(self) -> None:
        """Handle async initialization of the provider."""
        self._host = self.config.get_value("host")
        self._port = self.config.get_value("port")
        self._session = aiohttp.ClientSession()

    async def unload(self, is_removed: bool = False) -> None:
        """Handle close/cleanup of the provider."""
        if self._session:
            await self._session.close()
            self._session = None

    @property
    def _api_base_url(self) -> str:
        """Return the base URL for the RTL-SDR Radio API."""
        return f"http://{self._host}:{self._port}/api"

    async def _get_stations(self) -> list[dict]:
        """Fetch stations from the RTL-SDR Radio API."""
        if not self._session:
            return []
        try:
            async with self._session.get(f"{self._api_base_url}/stations") as response:
                if response.status == 200:
                    return await response.json()
                self.logger.error("Failed to fetch stations: %s", response.status)
                return []
        except aiohttp.ClientError as err:
            self.logger.error("Error connecting to RTL-SDR Radio: %s", err)
            return []

    async def _get_station(self, station_id: str) -> dict | None:
        """Fetch a single station from the RTL-SDR Radio API."""
        if not self._session:
            return None
        try:
            async with self._session.get(
                f"{self._api_base_url}/stations/{station_id}"
            ) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except aiohttp.ClientError as err:
            self.logger.error("Error fetching station %s: %s", station_id, err)
            return None

    async def _tune_to_station(self, station: dict) -> bool:
        """Tune the RTL-SDR to the station's frequency or DAB+ channel."""
        if not self._session:
            return False
        try:
            station_type = station.get("station_type", "fm")

            if station_type == "dab":
                # DAB+ tuning
                dab_channel = station.get("dab_channel")
                dab_program = station.get("dab_program")
                dab_service_id = station.get("dab_service_id")

                async with self._session.post(
                    f"{self._api_base_url}/dab/tune",
                    json={
                        "channel": dab_channel,
                        "program": dab_program,
                        "service_id": dab_service_id,
                    },
                ) as response:
                    if response.status == 200:
                        self.logger.info(
                            "Tuned to DAB+ %s (%s)", dab_channel, dab_program
                        )
                        return True
                    self.logger.error("Failed to tune DAB+: %s", response.status)
                    return False
            else:
                # FM tuning
                frequency = station.get("frequency")
                modulation = station.get("modulation", "wfm")

                async with self._session.post(
                    f"{self._api_base_url}/tuner/tune",
                    json={"frequency": frequency, "modulation": modulation},
                ) as response:
                    if response.status == 200:
                        self.logger.info("Tuned to %s MHz (%s)", frequency, modulation)
                        return True
                    self.logger.error("Failed to tune: %s", response.status)
                    return False
        except aiohttp.ClientError as err:
            self.logger.error("Error tuning: %s", err)
            return False

    def _station_to_radio(self, station: dict) -> Radio:
        """Convert an RTL-SDR station to a Music Assistant Radio item."""
        station_id = station["id"]
        station_type = station.get("station_type", "fm")

        radio = Radio(
            item_id=station_id,
            provider=self.domain,
            name=station["name"],
            provider_mappings={
                ProviderMapping(
                    item_id=station_id,
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                )
            },
        )

        # Add metadata based on station type
        if station_type == "dab":
            dab_channel = station.get("dab_channel", "")
            dab_program = station.get("dab_program", "")
            radio.metadata.description = f"DAB+ {dab_channel}"
            if dab_program:
                radio.metadata.description += f" • {dab_program}"
        else:
            modulation = station.get("modulation", "wfm").upper()
            frequency = station.get("frequency", 0)
            radio.metadata.description = f"{frequency} MHz {modulation}"
        radio.metadata.links = UniqueList(
            [
                MediaItemLink(
                    type=LinkType.WEBSITE,
                    url=f"http://{self._host}:{self._port}",
                )
            ]
        )

        # Add station image if available
        image_url = station.get("image_url")
        if image_url:
            # Convert relative URL to absolute URL
            if image_url.startswith("/"):
                image_url = f"http://{self._host}:{self._port}{image_url}"
            self.logger.debug("Setting image for %s: %s", station["name"], image_url)
            radio.metadata.images = UniqueList(
                [
                    MediaItemImage(
                        type=ImageType.THUMB,
                        path=image_url,
                        provider=self.lookup_key,
                        remotely_accessible=True,
                    )
                ]
            )

        return radio

    async def get_library_radios(self) -> AsyncGenerator[Radio, None]:
        """Retrieve library/subscribed radio stations from the provider."""
        stations = await self._get_stations()
        for station in stations:
            yield self._station_to_radio(station)

    async def get_radio(self, prov_radio_id: str) -> Radio | None:
        """Get full radio station details by id."""
        station = await self._get_station(prov_radio_id)
        if station:
            return self._station_to_radio(station)
        return None

    async def get_stream_details(
        self, item_id: str, media_type: MediaType
    ) -> StreamDetails:
        """Get stream details for a radio station."""
        # Tune the RTL-SDR to the correct frequency
        station = await self._get_station(item_id)
        if station:
            await self._tune_to_station(station)

        # Use the API stream endpoint
        stream_url = f"{self._api_base_url}/stream"

        return StreamDetails(
            provider=self.domain,
            item_id=item_id,
            audio_format=AudioFormat(
                content_type=ContentType.MP3,
            ),
            media_type=MediaType.RADIO,
            stream_type=StreamType.HTTP,
            path=stream_url,
            can_seek=False,
        )

    async def browse(self, path: str) -> list[Radio]:
        """Browse the provider's radio stations."""
        stations = await self._get_stations()
        return [self._station_to_radio(station) for station in stations]
