from pydantic import BaseModel
from typing import List, Any, Optional
from app.models.routing_models.routing_models import MapBox, Route


class ChatDataSchema(BaseModel):
    chatId: int
    action: Optional[str] = None
    locationType: str
    startCoords: Optional[List[float]] = None
    startAddress: Optional[List[str]] = []
    endCoords: Optional[List[float]] = None
    endAddress: Optional[List[str]] = []
    stops: int
    showInputBar: bool
    showStopSlider: bool
    showBudgetSlider: bool
    showAddressInput: bool
    workflowStarted: bool
    startConfirmed: Optional[Any] = None
    endConfirmed: Optional[Any] = None
    initial: Optional[MapBox.MapBox_Route] = None
    route: Optional[Route] = None
    itinerary: Optional[Any] = None
    loading: bool
    hotelBudget: Optional[int] = None
    carBudget: Optional[int] = None
    carDetails: List[str]
    budget: Optional[int] = None
    isComplete: bool = False


class ChatLogSchema(BaseModel):
    class ChatMessage(BaseModel):
        text: str
        sender: str
        buttons: Optional[List[Any]] = None

    id: int
    title: str
    messages: List[ChatMessage]


class ChatSchema(BaseModel):
    PartitionKey: str
    ChatData: ChatDataSchema
    ChatLog: ChatLogSchema
