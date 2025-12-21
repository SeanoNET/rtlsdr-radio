"""
DAB+ channel definitions for Band III (174-230 MHz).
Covers Australian and European DAB+ channel allocations.
"""

from typing import List, Optional

from app.models import DabChannel

# DAB+ Band III channel definitions
# Channel ID -> (Center frequency MHz, Label)
DAB_CHANNELS = {
    # Block 5
    "5A": (174.928, "Channel 5A"),
    "5B": (176.640, "Channel 5B"),
    "5C": (178.352, "Channel 5C"),
    "5D": (180.064, "Channel 5D"),
    # Block 6
    "6A": (181.936, "Channel 6A"),
    "6B": (183.648, "Channel 6B"),
    "6C": (185.360, "Channel 6C"),
    "6D": (187.072, "Channel 6D"),
    # Block 7
    "7A": (188.928, "Channel 7A"),
    "7B": (190.640, "Channel 7B"),
    "7C": (192.352, "Channel 7C"),
    "7D": (194.064, "Channel 7D"),
    # Block 8
    "8A": (195.936, "Channel 8A"),
    "8B": (197.648, "Channel 8B"),
    "8C": (199.360, "Channel 8C"),
    "8D": (201.072, "Channel 8D"),
    # Block 9
    "9A": (202.928, "Channel 9A"),
    "9B": (204.640, "Channel 9B"),
    "9C": (206.352, "Channel 9C"),
    "9D": (208.064, "Channel 9D"),
    # Block 10
    "10A": (209.936, "Channel 10A"),
    "10B": (211.648, "Channel 10B"),
    "10C": (213.360, "Channel 10C"),
    "10D": (215.072, "Channel 10D"),
    # Block 11
    "11A": (216.928, "Channel 11A"),
    "11B": (218.640, "Channel 11B"),
    "11C": (220.352, "Channel 11C"),
    "11D": (222.064, "Channel 11D"),
    # Block 12
    "12A": (223.936, "Channel 12A"),
    "12B": (225.648, "Channel 12B"),
    "12C": (227.360, "Channel 12C"),
    "12D": (229.072, "Channel 12D"),
    # Block 13 (some regions)
    "13A": (230.784, "Channel 13A"),
    "13B": (232.496, "Channel 13B"),
    "13C": (234.208, "Channel 13C"),
    "13D": (235.776, "Channel 13D"),
    "13E": (237.488, "Channel 13E"),
    "13F": (239.200, "Channel 13F"),
}

# Common channels used in Australia
AUSTRALIA_COMMON_CHANNELS = ["9A", "9B", "9C"]


def get_channel_frequency(channel: str) -> Optional[float]:
    """Get frequency for a DAB+ channel."""
    channel_upper = channel.upper()
    if channel_upper in DAB_CHANNELS:
        return DAB_CHANNELS[channel_upper][0]
    return None


def get_all_channels() -> List[DabChannel]:
    """Get all DAB+ channel definitions."""
    return [
        DabChannel(id=channel_id, frequency=freq, label=label)
        for channel_id, (freq, label) in DAB_CHANNELS.items()
    ]


def get_common_channels() -> List[str]:
    """Get commonly used DAB+ channels for scanning."""
    return AUSTRALIA_COMMON_CHANNELS.copy()
