"""Pure route-geometry helpers (no I/O).

``find_position`` translates an elapsed drive time into a coordinate along the
route. It is shared by planners and involves no network or DB access, so it
lives here as a reusable utility.
"""

from __future__ import annotations

import numpy as np
from geopy.distance import geodesic

from app.models.routing_models.routing_models import MapBox

Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step


def find_position(
    coordinates: list[list[float]], steps: list[Mapbox_step], elapsed_time: float
) -> list[float]:
    """
    Calculates the position along a route based on elapsed time and step information.

    Parameters:
    - coordinates (list[list[float]]): List of coordinates representing the route geometry.
    - steps (list[Mapbox_step]): List of steps representing the route.
    - elapsed_time (float): Elapsed time since the start of the route.

    Returns:
    - list[float]: Latitude and longitude of the position at the given elapsed time.
    """
    accumulated_time = 0  # Initialize accumulated travel time
    for step in steps:
        step_duration = step.duration  # Duration of the current step

        # Check if the elapsed time falls within the current step
        if step_duration > 0 and accumulated_time + step_duration >= elapsed_time:
            # Get a ratio for interpolation (Percentage of the step you are currently at)
            ratio = (elapsed_time - accumulated_time) / step_duration

            # Get the coordinates of the target step (form of lon,lat from Mapbox)
            step_coords = step.geometry.coordinates
            if len(step_coords) < 2:
                # Degenerate step with a single point; nothing to interpolate.
                return [step_coords[-1][1], step_coords[-1][0]]

            # Measure the FULL polyline by summing geodesic distances between each
            # pair of consecutive coordinates. The straight-line chord between the
            # step's endpoints understates a curved road, so the chord-based target
            # would land short; summing the real segments fixes that.
            segment_lengths = [
                geodesic(
                    (step_coords[i][1], step_coords[i][0]),
                    (step_coords[i + 1][1], step_coords[i + 1][0]),
                ).meters
                for i in range(len(step_coords) - 1)
            ]
            polyline_length = sum(segment_lengths)

            # The target distance is that same fraction of the true polyline length.
            target_distance = polyline_length * ratio

            # Walk the segments until the one that contains the target distance, then
            # interpolate WITHIN that segment (not along the endpoint chord).
            accumulated_distance = 0.0
            start_coord = step_coords[0]
            end_coord = step_coords[1]
            remaining_distance = target_distance
            segment_distance = segment_lengths[0]
            for i, seg_len in enumerate(segment_lengths):
                if accumulated_distance + seg_len >= target_distance:
                    start_coord = step_coords[i]
                    end_coord = step_coords[i + 1]
                    segment_distance = seg_len
                    remaining_distance = target_distance - accumulated_distance
                    break
                accumulated_distance += seg_len
            else:
                # Target is at/after the polyline end; snap to the last coordinate.
                start_coord = step_coords[-2]
                end_coord = step_coords[-1]
                segment_distance = segment_lengths[-1]
                remaining_distance = segment_distance

            if segment_distance > 0:
                # Get the interpolation ratio (Percentage of the segment the desired coordinates are in)
                segment_ratio = remaining_distance / segment_distance
            else:
                segment_ratio = 0

            # Interpolate the latitude and longitude based on the ratio
            lat = start_coord[1] + segment_ratio * (end_coord[1] - start_coord[1])
            lon = start_coord[0] + segment_ratio * (end_coord[0] - start_coord[0])

            # Return the interpolated coordinates
            return [lat, lon]

        # Update the accumulated travel time
        accumulated_time += step_duration

    # If the elapsed time exceeds the total duration, return the last coordinate
    return [coordinates[-1][1], coordinates[-1][0]]


class RouteMeasure:
    """Distance along step polylines mapped to their measured driving durations.

    Crossing ties choose the occurrence nearest the source query time, then the
    earliest occurrence. A query hint only resolves equal-distance projections.
    """

    def __init__(self, route):
        self.segments = []
        steps = [step for leg in route.legs for step in leg.steps]
        total = sum(max(0, step.duration) for step in steps)
        if not steps or total <= 0:
            pieces = [(route.geometry.coordinates, max(0, route.duration))]
        else:
            scale = max(0, route.duration) / total
            pieces = [(step.geometry.coordinates, max(0, step.duration) * scale) for step in steps]
        elapsed = 0.0
        for coords, duration in pieces:
            lengths = [
                geodesic((a[1], a[0]), (b[1], b[0])).meters for a, b in zip(coords, coords[1:])
            ]
            length = sum(lengths)
            if len(coords) == 1:
                self.segments.append((coords[0], coords[0], elapsed, elapsed + duration))
            travelled = 0.0
            for a, b, distance in zip(coords, coords[1:], lengths):
                start = elapsed + (duration * travelled / length if length else 0)
                travelled += distance
                end = elapsed + (duration * travelled / length if length else duration)
                self.segments.append((a, b, start, end))
            elapsed += duration
        self.duration = max(0, route.duration)
        self.coordinates = route.geometry.coordinates
        self._projection_segments = np.array(
            [[*a, *b, start, end] for a, b, start, end in self.segments], dtype=float
        ).reshape(-1, 6)

    def position(self, seconds):
        seconds = max(0, min(self.duration, seconds))
        for a, b, start, end in self.segments:
            if end > start and start <= seconds <= end:
                fraction = (seconds - start) / (end - start)
                return [a[1] + fraction * (b[1] - a[1]), a[0] + fraction * (b[0] - a[0])]
        last = self.coordinates[-1]
        return [last[1], last[0]]

    def project(self, point, hint_seconds=None):
        """Project a place onto the baseline route.

        Input is a [lat, lon] point; hint_seconds resolves ties at route crossings.
        Returns driving-time progress, distance from the route in meters, and
        the matched segment index. The hint does not override a nearer segment.
        """
        if not self.segments:
            return {
                "route_progress_seconds": 0.0,
                "distance_meters": geodesic(point, self.position(0)).meters,
                "segment_index": None,
            }
        # Project onto all road segments at once, then measure the winner geodesically.
        lat, lon = point
        a_lon, a_lat, b_lon, b_lat, starts, ends = self._projection_segments.T
        longitude_scale = np.cos(np.radians((lat + a_lat + b_lat) / 3))
        segment_dx, segment_dy = (b_lon - a_lon) * longitude_scale, b_lat - a_lat
        point_dx, point_dy = (lon - a_lon) * longitude_scale, lat - a_lat
        segment_length_squared = segment_dx * segment_dx + segment_dy * segment_dy
        fractions = np.clip(
            np.divide(
                point_dx * segment_dx + point_dy * segment_dy,
                segment_length_squared,
                out=np.zeros_like(segment_length_squared),
                where=segment_length_squared > 0,
            ),
            0,
            1,
        )
        distances = (
            np.hypot(point_dx - fractions * segment_dx, point_dy - fractions * segment_dy)
            * 111195.08
        )
        projected_seconds = starts + fractions * (ends - starts)
        ties = np.flatnonzero(distances <= distances.min() + 0.001)
        # At crossings, the search point's time identifies the intended route occurrence.
        index = min(
            ties,
            key=lambda i: (
                abs(projected_seconds[i] - hint_seconds)
                if hint_seconds is not None
                else projected_seconds[i],
                projected_seconds[i],
                i,
            ),
        )
        coordinate = [
            a_lat[index] + fractions[index] * (b_lat[index] - a_lat[index]),
            a_lon[index] + fractions[index] * (b_lon[index] - a_lon[index]),
        ]
        return {
            "route_progress_seconds": float(projected_seconds[index]),
            "distance_meters": geodesic(point, coordinate).meters,
            "segment_index": int(index),
        }


def project_place(route, coordinates, hint_seconds=None):
    """Pure public projection seam; coordinates are [lat, lon]."""
    return RouteMeasure(route).project(coordinates, hint_seconds)
