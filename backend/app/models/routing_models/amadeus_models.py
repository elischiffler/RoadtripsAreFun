from typing import Any, Optional, Dict

from pydantic import BaseModel
from pydantic import ConfigDict


class Amadeus_Meta(BaseModel):
    count: int
    links: Dict[str, str]
    sort: Optional[str] = None


class Amadeus_Hotel_Search(BaseModel):
    class Amadeus_Hotel_Data(BaseModel):
        subtype: Optional[str] = None
        name: str
        timeZoneName: Optional[str] = None
        iataCode: str
        address: Dict[str, str]
        geoCode: Dict[str, float]
        hotelId: str
        chainCode: str

        class Amadeus_Distance(BaseModel):
            unit: str
            value: float
            displayValue: Optional[str] = None
            isUnlimited: Optional[str] = None

        distance: Amadeus_Distance
        last_update: Optional[str] = None

    data: list[Amadeus_Hotel_Data]
    meta: Amadeus_Meta


class Qualified_Desc(BaseModel):
    text: str
    lang: str


class Amadeus_Hotel_Offers(BaseModel):
    class Amadeus_Hotel_Offer(BaseModel):
        class Hotel(BaseModel):
            hotelId: str
            chainCode: str
            brandCode: Optional[str] = None
            dupeId: Optional[str] = None
            name: str
            cityCode: Optional[str] = None
            model_config = ConfigDict(extra='allow')  # Poor documentation is available

        class Offer(BaseModel):
            class Rate_Family(BaseModel):
                code: str
                type: str

            class Commission(BaseModel):
                percentage: str
                amount: str
                description: Qualified_Desc

            class Room(BaseModel):
                class Room_Type(BaseModel):
                    category: str
                    beds: int
                    bedType: str

                type: str
                typeEstimated: Room_Type
                description: Qualified_Desc

            class Hotel_Guest(BaseModel):
                adults: int
                childAges: Optional[list[int]] = None

            class Hotel_Price(BaseModel):
                currency: str
                sellingTotal: Optional[str] = None
                total: str
                base: str
                taxes: Optional[list[Any]] = None
                markups: Optional[list[Any]] = None
                variations: Optional[dict[str, Any]]

            class Hotel_Policy(BaseModel):
                class checkInPolicy(BaseModel):
                    checkIn: str
                    checkInDescription: Qualified_Desc
                    checkOut: str
                    checkOutDescription: Qualified_Desc

                paymentType: Optional[str] = None
                guarantee: Optional[Dict[str, Any]] = None
                deposit: Optional[Dict[str, Any]] = None
                prepay: Optional[Dict[str, Any]] = None
                holdTime: Optional[Dict[str, Any]] = None
                cancellations: Optional[list[Any]] = None
                checkInOut: Optional[checkInPolicy] = None


            type: Optional[str] = None
            id: str
            checkInDate: Optional[str] = None
            checkOutDate: Optional[str] = None
            roomQuantity: Optional[str] = None
            rateCode: str
            rateFamilyEstimated: Optional[Rate_Family] = None
            category: Optional[str] = None
            description: Optional[Qualified_Desc] = None
            commission: Optional[Commission] = None
            boardType: Optional[str] = None
            room: Room
            guests: Optional[Hotel_Guest] = None
            price: Hotel_Price
            policies: Optional[Hotel_Policy] = None
            self: Optional[str] = None

        type: str
        is_available: Optional[bool] = None
        self: str
        hotel: Hotel
        offers: list[Offer] = []
    data: list[Amadeus_Hotel_Offer]


class Amadeus_Hotel_Ratings(BaseModel):
    class Hotel_Sentiment(BaseModel):
        hotelId: str
        type: Optional[str] = None
        overallRating: int
        numberOfRatings: int
        numberOfReviews: int
        sentiments: Optional[dict[str, int]] = None

    class Amadeus_Warning(BaseModel):
        code: int
        title: str
        detail: Optional[str] = None
        source: Optional[dict[str, str]] = None
        documentation: Optional[str] = None

    data: list[Hotel_Sentiment]
    meta: Amadeus_Meta
    warnings: Optional[list[Amadeus_Warning]] = []


class Amadeus_Access(BaseModel):
    type: str
    username: str
    application_name: str
    client_id: str
    token_type: str
    access_token: str
    expires_in: int
    state: str
    scope: str
