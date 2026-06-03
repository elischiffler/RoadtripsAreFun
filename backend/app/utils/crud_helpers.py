from typing import Any


def segment_route(geometry: list[float], seg_size: int = 10000) -> list[list[float]]:
    """Split a route geometry into chunks for storage."""
    segments = []
    for i in range(0, len(geometry), seg_size):
        segments.append(geometry[i : i + seg_size])
    return segments
