from pydantic import BaseModel
from typing import List, Any, Optional
from app.models.routing_models.routing_models import MapBox, Route


class ChatDataSchema(BaseModel):
    chatId: int
    action: str
    locationType: str
    startCoords: List[float]
    startAddress: str
    endCoords: List[float]
    endAddress: str
    stops: int
    showInputBar: bool
    showStopSlider: bool
    showBudgetSlider: bool
    showAddressInput: bool
    workflowStarted: bool
    startConfirmed: Optional[Any] = None #TODO make schema for these
    endConfirmed: Optional[Any] = None
    initial: Optional[MapBox.MapBox_Route] = None
    route: Optional[Route] = None
    itinerary: Optional[Any] = None
    loading: bool
    hotelBudget: Optional[int] = None
    carDetails: List[str]
    budget: int


class ChatLogSchema(BaseModel):
    class ChatMessage(BaseModel):
        text: str
        sender: str
        buttons: Optional[List[Any]]
    id: int
    title: str
    messages: List[ChatMessage]


class ChatSchema(BaseModel):
    ChatData: ChatDataSchema
    ChatLog: ChatLogSchema
