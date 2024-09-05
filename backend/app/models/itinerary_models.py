from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from app.models.routing_models.routing_models import Route


class Itinerary_Payload(BaseModel):
    route: Route
    start_time: Optional[datetime] = datetime(2024, 9, 21, 9, 0, 0)


class Itinerary_Day(BaseModel):
    date: str

    class Itinerary_Stop(BaseModel):
        name: str
        time: str
        address: Optional[str] = None
        url: Optional[str] = None
    stops: List[Itinerary_Stop]

