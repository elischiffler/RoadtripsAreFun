from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from .routing_models import Route


class itinerary_payload(BaseModel):
    route: Route
    start_time: Optional[datetime] = datetime.now()
