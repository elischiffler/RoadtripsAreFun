from typing import Any

from pydantic import BaseModel

from app.models.routing_models.routing_models import MapBox, Route


class ChatDataSchema(BaseModel):
    chatId: int
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
    route: Route | None = None
    itinerary: Any | None = None
    loading: bool
    hotelBudget: int | None = None
    carBudget: int | None = None
    carDetails: list[str]
    budget: int | None = None
    isComplete: bool = False


class ChatLogSchema(BaseModel):
    class ChatMessage(BaseModel):
        text: str
        sender: str
        buttons: list[Any] | None = None

    id: int
    title: str
    messages: list[ChatMessage]


class ChatSchema(BaseModel):
    PartitionKey: str
    ChatData: ChatDataSchema
    ChatLog: ChatLogSchema
