"""Deterministic, uncapped membership in a bell-shaped route corridor."""

import math
from dataclasses import asdict, dataclass

import numpy as np
from geopy.distance import geodesic

from app.routing.geometry import RouteMeasure

MILES_TO_METERS = 1609.344


@dataclass(frozen=True)
class CorridorConfig:
    endpoint_miles: float = 5.0
    midpoint_miles: float = 25.0
    sigma: float = 0.25

    def __post_init__(self):
        for key, lower, upper in (
            ("endpoint_miles", 0.0, 100.0),
            ("midpoint_miles", 0.0, 100.0),
            ("sigma", 0.05, 1.0),
        ):
            value = getattr(self, key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not lower <= value <= upper
            ):
                raise ValueError(f"{key} must be finite in {lower}..{upper}")
        if not 0 < self.endpoint_miles <= self.midpoint_miles:
            raise ValueError("Corridor widths require 0 < endpoint <= midpoint")

    def radius_miles(self, fraction):
        """A normalized Gaussian: exact endpoint minimum and midpoint maximum."""
        fraction = max(0.0, min(1.0, fraction))
        edge = math.exp(-0.5 * (0.5 / self.sigma) ** 2)
        bell = math.exp(-0.5 * ((fraction - 0.5) / self.sigma) ** 2)
        return self.endpoint_miles + (self.midpoint_miles - self.endpoint_miles) * (
            (bell - edge) / (1 - edge)
        )

    def snapshot(self):
        return {
            "policy": "gaussian-route-corridor-v1",
            **asdict(self),
            "progress_basis": "baseline_polyline_distance",
            "distance_basis": "geodesic_distance_to_projected_polyline",
            "candidate_limit": None,
        }


class RouteCorridor:
    """Project onto every route segment; no sample gaps or candidate quotas.

    Projection uses RouteMeasure's local segment approximation and WGS84 distance.
    At equal-distance crossings, the earliest route occurrence wins. The width is
    evaluated at that nearest projection, not at another, wider route segment.
    """

    def __init__(self, route, config=CorridorConfig()):
        self.config = config
        self.measure = RouteMeasure(route)
        self.lengths = np.array(
            [geodesic((a[1], a[0]), (b[1], b[0])).meters for a, b, _, _ in self.measure.segments]
        )
        self.offsets = np.concatenate(([0.0], np.cumsum(self.lengths)))
        self.total = float(self.lengths.sum())

    def project(self, coordinates):
        projection = self.measure.project(coordinates)
        index = projection["segment_index"]
        fraction = 0.0
        if index is not None and self.total:
            a, b, _, _ = self.measure.segments[index]
            lat, lon = coordinates
            scale = math.cos(math.radians((lat + a[1] + b[1]) / 3))
            dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
            length2 = dx * dx + dy * dy
            position = (
                max(0.0, min(1.0, ((lon - a[0]) * scale * dx + (lat - a[1]) * dy) / length2))
                if length2
                else 0.0
            )
            fraction = float((self.offsets[index] + position * self.lengths[index]) / self.total)
        radius = self.config.radius_miles(fraction)
        return {
            **projection,
            "route_distance_fraction": fraction,
            "corridor_radius_miles": radius,
            "inside_corridor": projection["distance_meters"] <= radius * MILES_TO_METERS,
        }

    def select(self, records):
        """Keep every geometric match in stable route-progress/identity order."""
        matches = []
        for record in records:
            projection = self.project(record["coordinates"])
            if projection["inside_corridor"]:
                matches.append({**record, **projection})
        return sorted(matches, key=lambda row: (row["route_distance_fraction"], row["provider_id"]))
