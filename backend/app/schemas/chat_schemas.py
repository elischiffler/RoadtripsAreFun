from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.guided_planning import Latitude, Longitude
from app.models.routing_models.routing_models import MapBox, Route
from app.models.trip_limits import ROAD_MAX_COORDINATES

_ROAD_FIELDS = {
    "geometry",
    "distance",
    "duration",
    "steps",
    "legs",
    "road_distance",
    "drive_seconds",
    "driving_duration",
    "route_summary",
    "directions",
    "provider_response",
    "transport_type",
    "typical_duration",
    "one_day_proof",
}


def without_road_data(value):
    if isinstance(value, dict):
        return {
            key: without_road_data(item) for key, item in value.items() if key not in _ROAD_FIELDS
        }
    if isinstance(value, list):
        return [without_road_data(item) for item in value]
    return value


def has_apple_route_intent(route, profile=None):
    return isinstance(route, dict) and (
        route.get("directions_provider") == "apple"
        or (isinstance(profile, dict) and profile.get("apple_route_intent") is True)
    )


class StoredAppleRoute(Route):
    """Keep only the ordered app-owned stops and schedule."""

    directions_provider: Literal["apple"]
    coordinates: list[tuple[Latitude, Longitude]] = Field(
        min_length=2, max_length=ROAD_MAX_COORDINATES
    )
    geometry: Any = Field(default=None, exclude=True)
    distance: Any = Field(default=None, exclude=True)
    duration: Any = Field(default=None, exclude=True)
    steps: Any = Field(default=None, exclude=True)


def apple_route_intent(route):
    return StoredAppleRoute.model_validate(
        {**without_road_data(route), "directions_provider": "apple"}
    ).model_dump(mode="json")


def stored_chat_data(chat):
    """Allow the previous backend to read Apple saves during a rollback."""
    data = chat.model_dump(mode="json")
    if has_apple_route_intent(data["route"], data["tripProfile"]):
        data["tripProfile"] = {**(data["tripProfile"] or {}), "apple_route_intent": True}
        data["route"].update(
            geometry={"type": "LineString", "coordinates": []}, distance=0, duration=0, steps=[]
        )
    return data


class ChatDataSchema(BaseModel):
    chatId: int
    agentChatId: str | None = None
    tripProfile: dict | None = None  # Saved trip snapshot; retained for storage compatibility.
    presentation: dict[str, Any] | None = None  # Trip-level UI state, including visited stops.
    action: str | None = None
    locationType: str
    startCoords: list[float] | None = None
    startAddress: list[str] | None = []
    endCoords: list[float] | None = None
    endAddress: list[str] | None = []
    stops: int
    showInputBar: bool
    showStopSlider: bool
    showBudgetSlider: bool
    showAddressInput: bool
    workflowStarted: bool
    startConfirmed: Any | None = None
    endConfirmed: Any | None = None
    initial: MapBox.MapBox_Route | None = None
    route: StoredAppleRoute | Route | None = None
    itinerary: Any | None = None
    loading: bool
    hotelBudget: int | None = None
    carBudget: int | None = None
    carDetails: list[str]
    budget: int | None = None
    isComplete: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_apple_route(cls, value):
        if not isinstance(value, dict):
            return value
        route, profile = value.get("route"), value.get("tripProfile")
        if has_apple_route_intent(route, profile):
            return {
                **value,
                "route": StoredAppleRoute.model_validate(
                    {**without_road_data(route), "directions_provider": "apple"}
                ),
                "initial": None,
                "itinerary": without_road_data(value.get("itinerary")),
            }
        return value


class ChatLogSchema(BaseModel):
    class ChatMessage(BaseModel):
        text: str
        sender: str
        presentation: dict[str, Any] | None = None  # Retain historical saved metadata.
        buttons: list[Any] | None = None

    id: int
    title: str
    messages: list[ChatMessage]


class ChatSchema(BaseModel):
    PartitionKey: str
    ExpectedRevision: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    ChatData: ChatDataSchema
    ChatLog: ChatLogSchema
