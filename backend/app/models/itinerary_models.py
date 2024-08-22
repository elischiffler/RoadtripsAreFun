from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel
from .routing_models import Route


class itinerary_payload(BaseModel):
    route: Route
    start_time: Optional[datetime] = datetime.now()


class itinerary_day(BaseModel):
    date: str
    stops: List[Dict[str, Any]]
