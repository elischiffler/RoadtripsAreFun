"""Pure route-geometry helpers (no I/O).

``find_position`` translates an elapsed drive time into a coordinate along the
route. It is shared by planners and involves no network or DB access, so it
lives here as a reusable utility.
"""

from __future__ import annotations

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
        if accumulated_time + step_duration >= elapsed_time:
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
    return coordinates[-1]
