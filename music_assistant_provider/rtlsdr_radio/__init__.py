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
            default_value=9080,
            description="Port for the RTL-SDR Radio API",
            required=True,
        ),
        ConfigEntry(
            key="enable_dab_discovery",
            type=ConfigEntryType.BOOLEAN,
            label="Enable DAB+ Auto-Discovery",
            default_value=True,
            description="Automatically discover DAB+ programs on configured channels",
            required=False,
        ),
        ConfigEntry(
            key="dab_channels",
            type=ConfigEntryType.STRING,
            label="DAB+ Channels to Scan",
            default_value="9A,9B,9C",
            description="Comma-separated DAB+ channel IDs (e.g., 9A,9B,9C for Perth)",
            required=False,
        ),
    )


class RTLSDRRadioProvider(MusicProvider):
    """Music Provider for RTL-SDR Radio stations."""

    _host: str
    _port: int
    _session: aiohttp.ClientSession | None = None
    _dab_programs_cache: list[dict] | None = None

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

    async def _discover_dab_programs(self) -> list[dict]:
        """Scan configured DAB+ channels and return discovered programs (cached)."""
        # Return cached results if available
        if self._dab_programs_cache is not None:
            return self._dab_programs_cache

        channels_str = self.config.get_value("dab_channels") or ""
        if not channels_str:
            return []

        channels = [c.strip().upper() for c in channels_str.split(",") if c.strip()]
        discovered: list[dict] = []

        if not self._session:
            return []

        for channel in channels:
            try:
                async with self._session.get(
                    f"{self._api_base_url}/dab/programs",
                    params={"channel": channel},
                ) as response:
                    if response.status == 200:
                        programs = await response.json()
                        discovered.extend(programs)
                        self.logger.info(
                            "Discovered %d programs on DAB+ channel %s",
                            len(programs),
                            channel,
                        )
            except aiohttp.ClientError as err:
                self.logger.warning("Failed to scan DAB+ channel %s: %s", channel, err)

        # Cache results
        self._dab_programs_cache = discovered
        return discovered

    async def _tune_dab_program(self, channel: str, service_id: int) -> bool:
        """Tune to a discovered DAB+ program."""
        if not self._session:
            return False
        try:
            async with self._session.post(
                f"{self._api_base_url}/dab/tune",
                json={"channel": channel, "service_id": service_id},
            ) as response:
                if response.status == 200:
                    self.logger.info(
                        "Tuned to DAB+ channel %s, service %d", channel, service_id
                    )
                    return True
                self.logger.error("Failed to tune DAB+: %s", response.status)
                return False
        except aiohttp.ClientError as err:
            self.logger.error("Error tuning DAB+: %s", err)
            return False

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

    def _dab_program_to_radio(self, program: dict) -> Radio:
        """Convert a discovered DAB+ program to a Music Assistant Radio item."""
        # Create unique ID from channel + service_id
        item_id = f"dab_{program['channel']}_{program['service_id']}"

        radio = Radio(
            item_id=item_id,
            provider=self.domain,
            name=program["name"],
            provider_mappings={
                ProviderMapping(
                    item_id=item_id,
                    provider_domain=self.domain,
                    provider_instance=self.instance_id,
                )
            },
        )

        # Add metadata
        ensemble = program.get("ensemble", "Unknown")
        channel = program.get("channel", "")
        bitrate = program.get("bitrate")
        program_type = program.get("program_type")  # PTY genre

        # Build description with available info
        description_parts = [f"DAB+ {channel}", ensemble]
        if program_type:
            description_parts.append(program_type)
        if bitrate:
            description_parts.append(f"{bitrate}kbps")
        radio.metadata.description = " • ".join(description_parts)

        # Set genre from PTY if available
        if program_type:
            radio.metadata.genres = {program_type}

        radio.metadata.links = UniqueList(
            [
                MediaItemLink(
                    type=LinkType.WEBSITE,
                    url=f"http://{self._host}:{self._port}",
                )
            ]
        )

        return radio

    async def get_library_radios(self) -> AsyncGenerator[Radio, None]:
        """Retrieve library/subscribed radio stations from the provider."""
        # Fetch saved stations from backend
        stations = await self._get_stations()
        for station in stations:
            yield self._station_to_radio(station)

        # Discover DAB+ programs if enabled
        if self.config.get_value("enable_dab_discovery"):
            programs = await self._discover_dab_programs()
            for prog in programs:
                yield self._dab_program_to_radio(prog)

    async def get_radio(self, prov_radio_id: str) -> Radio | None:
        """Get full radio station details by id."""
        # Check if it's a discovered DAB+ program
        if prov_radio_id.startswith("dab_"):
            programs = await self._discover_dab_programs()
            for prog in programs:
                item_id = f"dab_{prog['channel']}_{prog['service_id']}"
                if item_id == prov_radio_id:
                    return self._dab_program_to_radio(prog)
            return None

        # Otherwise, fetch from saved stations
        station = await self._get_station(prov_radio_id)
        if station:
            return self._station_to_radio(station)
        return None

    async def get_stream_details(
        self, item_id: str, media_type: MediaType
    ) -> StreamDetails:
        """Get stream details for a radio station."""
        # Check if it's a discovered DAB+ program
        if item_id.startswith("dab_"):
            # Parse item_id: dab_{channel}_{service_id}
            parts = item_id.split("_")
            if len(parts) >= 3:
                channel = parts[1]
                service_id = int(parts[2])
                await self._tune_dab_program(channel, service_id)
        else:
            # Tune the RTL-SDR to the correct frequency for saved stations
            station = await self._get_station(item_id)
            if station:
                await self._tune_to_station(station)

        # Use the API stream endpoint (works for both FM and DAB+)
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
