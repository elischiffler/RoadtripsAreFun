from typing import Optional

from pydantic import BaseModel


class location_payload(BaseModel):
    is_coordinates: bool

    class payload_data(BaseModel):
        coordinates: Optional[list] = []
        address: Optional[str] = None

    location: payload_data

class location_model(BaseModel):
    address: str
    latitude: float
    longitude: float