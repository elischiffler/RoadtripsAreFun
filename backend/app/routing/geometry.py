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

            # Get the coordinates/distance of the target step (form of lon,lat from Mapbox)
            step_coords = step.geometry.coordinates

            # Get the geodisic distance in meters you are currently at in the step
            target_distance = (
                geodesic(
                    (step_coords[0][1], step_coords[0][0]), (step_coords[-1][1], step_coords[-1][0])
                ).meters
                * ratio
            )

            # Track accumulated distance over the step to determine the nearest coordinates
            accumulated_distance = 0
            # print(len(step_coords))
            while (
                len(step_coords) > 3
            ):  # Search for the closest two-three coordinates using a binary search
                center_idx = len(step_coords) // 2 - 1  # Get the middle index of the coordinates

                # Get the first half of the step coordinates and find the distance of the half
                left_half = step_coords[:center_idx]
                half_distance = geodesic(
                    (left_half[0][1], left_half[0][0]), (left_half[-1][1], left_half[-1][0])
                ).meters

                # Determine if the half contains the current distance
                if half_distance + accumulated_distance >= target_distance:
                    # Set coordinates to left half if it contains the distance
                    step_coords = left_half
                else:
                    # Set coordinates to right half if step is not found and accumulate the distance of the left half
                    step_coords = step_coords[center_idx:]
                    accumulated_distance += half_distance

            # Get the starting and ending coordinates of the reduced step
            start_coord = step_coords[0]
            end_coord = step_coords[-1]

            # Get the remaining distance from the start coord to the end coord
            remaining_distance = target_distance - accumulated_distance

            # Get the distance of the currently examined segment
            segment_distance = geodesic(
                (start_coord[1], start_coord[0]), (end_coord[1], end_coord[0])
            ).meters

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
