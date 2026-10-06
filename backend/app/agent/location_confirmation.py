"""Human selections resolve only this authenticated chat's persisted candidates."""

from app.agent.trip_profile import TripProfile
from app.utils.location_resolution import LocationConfirmation


def confirm_location(
    memory, user_id: str, chat_id: str, selection: LocationConfirmation
) -> TripProfile:
    return confirm_locations(memory, user_id, chat_id, [selection])


def confirm_locations(
    memory, user_id: str, chat_id: str, selections: list[LocationConfirmation]
) -> TripProfile:
    """Validate and save all selected matches together; a stale choice saves none."""
    if (
        not selections
        or len(selections) > 2
        or len({s.field for s in selections}) != len(selections)
    ):
        raise ValueError("Confirm each location only once.")
    profile = TripProfile.from_json(memory.load_trip_profile(user_id, chat_id))
    values = profile.model_dump()
    for selection in selections:
        pending = profile.pending_locations.get(selection.field)
        candidate = (
            next((c for c in pending.candidates if c.id == selection.candidateId), None)
            if pending
            else None
        )
        if candidate is None:
            raise ValueError(
                "That location choice has expired. Choose a current match or enter a new address."
            )
        values[selection.field] = candidate.address
        values[selection.field.replace("address", "coords")] = [
            candidate.latitude,
            candidate.longitude,
        ]
        if selection.field == "start_address":
            values["start_timezone"] = candidate.timezone
            if (profile.start_address, profile.start_coords, profile.start_timezone) != (
                candidate.address,
                [candidate.latitude, candidate.longitude],
                candidate.timezone,
            ):
                values["start_date"] = None
            if profile.pending_departure and candidate.timezone:
                try:
                    values["start_date"] = profile.pending_departure.resolve(
                        profile.departure_time, candidate.timezone
                    )
                    values["pending_departure"] = None
                except ValueError:
                    pass  # Save the chosen location; presentation asks for a corrected departure.
        values["pending_locations"].pop(selection.field)
    confirmed = TripProfile.model_validate(values)
    memory.save_trip_profile(user_id, chat_id, confirmed.to_json())
    return confirmed
