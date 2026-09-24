from typing import Any

from pydantic import BaseModel, ConfigDict


class Amadeus_Meta(BaseModel):
    count: int
    links: dict[str, str]
    sort: str | None = None


class Amadeus_Hotel_Search(BaseModel):
    class Amadeus_Hotel_Data(BaseModel):
        subtype: str | None = None
        name: str
        timeZoneName: str | None = None
        iataCode: str
        address: dict[str, str]
        geoCode: dict[str, float]
        hotelId: str
        chainCode: str

        class Amadeus_Distance(BaseModel):
            unit: str
            value: float
            displayValue: str | None = None
            isUnlimited: str | None = None

        distance: Amadeus_Distance
        last_update: str | None = None

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
            brandCode: str | None = None
            dupeId: str | None = None
            name: str
            cityCode: str | None = None
            model_config = ConfigDict(extra="allow")  # Poor documentation is available

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
                childAges: list[int] | None = None

            class Hotel_Price(BaseModel):
                currency: str
                sellingTotal: str | None = None
                total: str
                base: str
                taxes: list[Any] | None = None
                markups: list[Any] | None = None
                variations: dict[str, Any] | None

            class Hotel_Policy(BaseModel):
                class checkInPolicy(BaseModel):
                    checkIn: str
                    checkInDescription: Qualified_Desc
                    checkOut: str
                    checkOutDescription: Qualified_Desc

                paymentType: str | None = None
                guarantee: dict[str, Any] | None = None
                deposit: dict[str, Any] | None = None
                prepay: dict[str, Any] | None = None
                holdTime: dict[str, Any] | None = None
                cancellations: list[Any] | None = None
                checkInOut: checkInPolicy | None = None

            type: str | None = None
            id: str
            checkInDate: str | None = None
            checkOutDate: str | None = None
            roomQuantity: str | None = None
            rateCode: str
            rateFamilyEstimated: Rate_Family | None = None
            category: str | None = None
            description: Qualified_Desc | None = None
            commission: Commission | None = None
            boardType: str | None = None
            room: Room
            guests: Hotel_Guest | None = None
            price: Hotel_Price
            policies: Hotel_Policy | None = None
            self: str | None = None

        type: str
        is_available: bool | None = None
        self: str
        hotel: Hotel
        offers: list[Offer] = []

    data: list[Amadeus_Hotel_Offer]


class Amadeus_Hotel_Ratings(BaseModel):
    class Hotel_Sentiment(BaseModel):
        hotelId: str
        type: str | None = None
        overallRating: int
        numberOfRatings: int
        numberOfReviews: int
        sentiments: dict[str, int] | None = None

    class Amadeus_Warning(BaseModel):
        code: int
        title: str
        detail: str | None = None
        source: dict[str, str] | None = None
        documentation: str | None = None

    data: list[Hotel_Sentiment]
    meta: Amadeus_Meta
    warnings: list[Amadeus_Warning] | None = []


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
