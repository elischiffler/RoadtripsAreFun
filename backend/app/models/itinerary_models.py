from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel
from .routing_models import Route


class itinerary_payload(BaseModel):
    route: Route
    start_time: Optional[datetime] = datetime(2024, 9, 21, 9, 0, 0)


class itinerary_day(BaseModel):
    date: str
    stops: List[Dict[str, Any]]
