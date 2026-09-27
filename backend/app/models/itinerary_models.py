from datetime import datetime

from pydantic import BaseModel

from app.models.routing_models.routing_models import Route


class Itinerary_Payload(BaseModel):
    route: Route
    start_time: datetime | None = datetime(2024, 9, 21, 9, 0, 0)


class Itinerary_Day(BaseModel):
    date: str

    class Itinerary_Stop(BaseModel):
        name: str
        time: str
        address: str | None = None
        url: str | None = None
        price: float | None = None

    stops: list[Itinerary_Stop]
