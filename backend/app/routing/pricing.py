"""Dynamic hotel-budget pricing (pure, no I/O).

``get_price_range`` recomputes the nightly hotel band from the remaining budget
and trip length. Shared by planners and the candidate-sourcing layer.
"""

from __future__ import annotations


def get_price_range(
    remaining_budget: float, duration_left: float, stops_left: int, daily_drive_time: int
) -> tuple[tuple[float, float], str]:
    """
    Function to dynamically calculate a price range based on remaining trip length and budget

    Args:
        - remaining_budget(float): The remaining budget for the trip
        - duration_left(float): The driving duration of the trip
        - stops_left(int): The number of stops left for the trip
        - daily_drive_time(int): The daily drive time for the trip

    Returns:
        - tuple[tuple[float, float], str]: The dynamic price range for the next hotel

    """
    # Found the full days of driving left in the trip
    days_left = (duration_left + stops_left * (2 * 3600)) // (daily_drive_time * 3600)
    if days_left == 0:
        remaining_avg = remaining_budget
    else:
        remaining_avg = (
            remaining_budget / days_left
        )  # Get a new avg cost of hotels by taking away the current price
    min_cost = remaining_avg - 75 if remaining_avg < 225 else 150  # Ensures the min is reasonable
    max_cost = remaining_avg + 75
    if remaining_avg > 100:
        return (min_cost, max_cost), f"{min_cost:.2f}-{max_cost:.2f}"
    else:
        return (0, max_cost), f"0-{max_cost:.2f}"
