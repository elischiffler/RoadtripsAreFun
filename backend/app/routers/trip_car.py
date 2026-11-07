"""Authenticated trip-specific car editor, with no provider or model calls."""

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Path, Response

from app.crud.trip_car import update_trip_car
from app.schemas.trip_car import TripCarChoices, TripCarUpdate
from app.utils.auth import require_authenticated_user

router = APIRouter()


@router.put("/chats/{chat_id}/car", response_model=TripCarChoices)
def save_trip_car(
    value: TripCarUpdate,
    response: Response,
    chat_id: int = Path(gt=0, le=9007199254740991),
    user_id: str = Depends(require_authenticated_user),
):
    response.headers["Cache-Control"] = "no-store"
    try:
        revision = update_trip_car(user_id, chat_id, value)
        if not revision:
            raise HTTPException(
                status_code=404, detail="Trip no longer available. Reload before editing."
            )
        response.headers["X-Trip-Revision"] = revision
        return TripCarChoices(car_status=value.car_status, car=value.car)
    except psycopg2.Error:
        raise HTTPException(
            status_code=503, detail="Car settings could not be saved. Please retry."
        ) from None
