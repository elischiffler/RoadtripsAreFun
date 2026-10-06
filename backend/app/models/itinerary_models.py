from datetime import datetime

from pydantic import BaseModel

from app.models.routing_models.routing_models import Route


class Itinerary_Payload(BaseModel):
    route: Route
    start_time: datetime | None = None


class Itinerary_Day(BaseModel):
    date: str

    class Itinerary_Stop(BaseModel):
        name: str
        time: str
        address: str | None = None
        url: str | None = None
        price: float | None = None
        kind: str | None = None
        timezone: str | None = None
        notice: str | None = None
        optional: bool = False
        status: str | None = None
        return_by: str | None = None
        return_time: str | None = None
        traveler_count: int | None = None
        hotel_rooms: list[dict] | None = None
        room_offers: list[dict] | None = None
        price_scope: str | None = None

    stops: list[Itinerary_Stop]
