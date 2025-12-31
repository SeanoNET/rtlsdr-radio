"""
ICY metadata injection service for Shoutcast/Icecast compatible streaming.

ICY metadata is an in-band signaling protocol that allows streaming servers
to send metadata (like "now playing" information) to clients alongside audio data.

Protocol:
1. Client requests metadata with header: Icy-MetaData: 1
2. Server responds with header: icy-metaint: N (bytes between metadata)
3. Every N bytes, server inserts a metadata frame:
   - 1 byte: length prefix (actual_length = byte_value * 16)
   - N bytes: metadata string padded to length
   - If no metadata: single 0x00 byte

Metadata format: StreamTitle='Artist - Song';StreamUrl='http://...';
"""

from typing import Optional


class IcyMetadataInjector:
    """
    Injects ICY metadata frames into an audio stream at fixed intervals.

    Usage:
        injector = IcyMetadataInjector(metaint=8192)
        injector.set_metadata("Artist - Song Title")

        # In stream generator:
        for chunk in audio_chunks:
            yield from injector.process_chunk(chunk)
    """

    def __init__(self, metaint: int = 8192):
        """
        Initialize the ICY metadata injector.

        Args:
            metaint: Number of audio bytes between metadata frames.
                     Standard values: 8192, 16384. Must match icy-metaint header.
        """
        self.metaint = metaint
        self._bytes_until_meta = metaint
        self._current_metadata: bytes = b"\x00"  # No metadata initially
        self._metadata_changed = False

    def set_metadata(self, title: str, url: Optional[str] = None) -> None:
        """
        Update the current metadata to be injected.

        Args:
            title: The StreamTitle value (e.g., "Artist - Song")
            url: Optional StreamUrl for cover art (limited client support)
        """
        # Build metadata string
        # Escape single quotes in title
        escaped_title = title.replace("'", "\\'")
        parts = [f"StreamTitle='{escaped_title}'"]

        if url:
            escaped_url = url.replace("'", "\\'")
            parts.append(f"StreamUrl='{escaped_url}'")

        metadata_str = ";".join(parts) + ";"

        # Encode and calculate padded length
        metadata_bytes = metadata_str.encode("utf-8")

        # Length byte = ceil(len / 16), actual padded length = length_byte * 16
        length_byte = (len(metadata_bytes) + 15) // 16
        padded_length = length_byte * 16

        # Pad with null bytes
        padded_metadata = metadata_bytes.ljust(padded_length, b"\x00")

        # Prepend length byte
        self._current_metadata = bytes([length_byte]) + padded_metadata
        self._metadata_changed = True

    def clear_metadata(self) -> None:
        """Clear metadata (send empty frame on next interval)."""
        self._current_metadata = b"\x00"
        self._metadata_changed = True

    def process_chunk(self, audio_data: bytes) -> bytes:
        """
        Process an audio chunk and inject ICY metadata at correct intervals.

        Args:
            audio_data: Raw audio bytes to process

        Returns:
            Audio bytes with ICY metadata frames injected
        """
        if not audio_data:
            return b""

        result = bytearray()
        data_offset = 0

        while data_offset < len(audio_data):
            # How many bytes can we send before next metadata frame?
            bytes_to_send = min(
                self._bytes_until_meta,
                len(audio_data) - data_offset
            )

            # Add audio bytes
            result.extend(audio_data[data_offset:data_offset + bytes_to_send])
            data_offset += bytes_to_send
            self._bytes_until_meta -= bytes_to_send

            # Time to insert metadata?
            if self._bytes_until_meta == 0:
                result.extend(self._current_metadata)
                self._bytes_until_meta = self.metaint

                # After sending changed metadata once, we can send empty frames
                # unless metadata changes again
                if self._metadata_changed:
                    self._metadata_changed = False

        return bytes(result)

    @staticmethod
    def get_response_headers(
        name: str = "RTL-SDR Radio",
        genre: str = "Various",
        bitrate: int = 128,
        metaint: int = 8192,
    ) -> dict:
        """
        Get ICY response headers to include in StreamingResponse.

        Args:
            name: Station name (icy-name)
            genre: Station genre (icy-genre)
            bitrate: Stream bitrate in kbps (icy-br)
            metaint: Bytes between metadata frames (icy-metaint)

        Returns:
            Dictionary of ICY headers
        """
        return {
            "icy-metaint": str(metaint),
            "icy-name": name,
            "icy-genre": genre,
            "icy-br": str(bitrate),
            "icy-pub": "1",  # Public stream
            "icy-audio-info": f"bitrate={bitrate}",
        }
