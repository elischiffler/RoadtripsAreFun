from typing import Any, Optional, Dict

from pydantic import BaseModel
class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str

class Route_Step(BaseModel):
    distance: float
    duration: float
    instruction: str
    location: list[float]


class Route(BaseModel):
    coordinates: list[list[float]]
    distance: float
    duration: float
    steps: list[Route_Step]
    stops: list[Dict[str, Any]]
    geometry: Mapbox_geo

    class Stop(BaseModel):
        name: str
        coordinates: Optional[list[list[float]]] = []
        duration: float
        type: str


# Mapbox Base Models
class Mapbox_waypoint(BaseModel):
    name: str
    location: list[float]
    distance: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None



class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_notification(BaseModel):
                details: Optional[Dict[str, str]] = None
                subtype: Optional[str] = None
                type: str
                geometry_index_end: Optional[int] = None
                geometry_index_start: Optional[int] = None
                geometry_index: Optional[int] = None

            class Mapbox_admin(BaseModel):
                iso_3166_1_alpha3: str
                iso_3166_1: str

            class Mapbox_step(BaseModel):
                class Mapbox_Maneuver(BaseModel):
                    type: str
                    instruction: str
                    modifier: Optional[str] = None
                    bearing_after: int
                    bearing_before: int
                    location: list[float]

                intersections: list[Any]
                exits: Optional[str] = None
                destinations: Optional[str] = None
                maneuver: Mapbox_Maneuver
                name: str
                duration: float
                distance: float
                driving_side: str
                weight: float
                mode: str
                geometry: Mapbox_geo
                ref: Optional[str] = None

            notifications: Optional[list[Mapbox_notification]] = []
            via_waypoints: Optional[list[Any]] = []
            admins: list[Mapbox_admin]
            weight: float
            duration: float
            steps: list[Mapbox_step]
            distance: float
            summary: str

        weight_name: str
        weight: float
        duration: float  # Total length in seconds
        distance: float  # Total distance in meters
        legs: list[Mapbox_leg]  # A leg represents a route between two destinations of the journey
        geometry: Mapbox_geo  # Contains every coordinate of the route
        waypoints: Optional[Mapbox_waypoint] = []  # Contains start, end, and stops locations

    routes: list[MapBox_Route]
    waypoints: list[Mapbox_waypoint]
    code: str
    uuid: str


# Trip Advisor API Base Models
class Trip_Advisor_Error(BaseModel):
    message: str
    type: str
    code: int


class Trip_Advisor_Address(BaseModel):
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postalcode: Optional[str] = None
    address_string: Optional[str] = None


class Trip_Advisor_Location_Search(BaseModel):
    class Trip_Advisor_Location(BaseModel):
        location_id: str
        name: str
        distance: Optional[str] = None
        bearing: Optional[str] = None
        address_obj: Optional[Trip_Advisor_Address] = None

    data: list[Trip_Advisor_Location]
    error: Optional[Trip_Advisor_Error] = None


class Trip_Advisor_Subcategory(BaseModel):
    name: Optional[str] = None
    localized_name: Optional[str] = None


class Trip_Advisor_Information(BaseModel):
    class Trip_Advisor_Ancestors(BaseModel):
        abbrv: Optional[str] = None
        level: Optional[str] = None
        name: Optional[str] = None
        location_id: Optional[str] = None

    class Trip_Advisor_Ranking(BaseModel):
        geo_location_id: Optional[str] = None
        ranking_string: Optional[str] = None
        geo_location_name: Optional[str] = None
        ranking_out_of: Optional[str] = None
        ranking: Optional[str] = None

    location_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    web_url: Optional[str] = None
    address_obj: Optional[Trip_Advisor_Address] = None
    ancestors: Optional[list[Trip_Advisor_Ancestors]] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    timezone: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    write_review: Optional[str] = None
    ranking_data: Optional[Trip_Advisor_Ranking] = None
    rating: Optional[str] = None
    rating_image_url: Optional[str] = None
    num_reviews: Optional[str] = None
    review_rating_count: Optional[Dict[str, str]] = None
    subratings: Optional[Dict[str, Any]] = None
    photo_count: Optional[str] = None
    see_all_photos: Optional[str] = None
    price_level: Optional[str] = None  # A number of dollar signs 1-5 indicating price

    class Trip_Advisor_Hours(BaseModel):
        class Trip_Advisor_Period(BaseModel):
            class Trip_Advisor_Time(BaseModel):
                day: int
                time: str

            open: Trip_Advisor_Time
            close: Trip_Advisor_Time

        periods: Optional[list[Trip_Advisor_Period]] = None
        weekday_text: Optional[list[str]] = None

    hours: Optional[Trip_Advisor_Hours] = None
    amenities: Optional[list[str]] = None
    features: Optional[list[str]] = None
    cuisine: Optional[list[Trip_Advisor_Subcategory]] = None
    parent_brand: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[Trip_Advisor_Subcategory] = None
    subcategory: Optional[list[Trip_Advisor_Subcategory]] = None

    class Trip_Advisor_Group(BaseModel):
        name: str
        localized_name: str
        categories: list[Trip_Advisor_Subcategory]

    groups: Optional[list[Trip_Advisor_Group]] = None
    styles: Optional[list[str]] = None
    neighborhood_info: Optional[list[Trip_Advisor_Subcategory]] = None  # List of nearby neighborhoods

    class Trip_Advisor_TripType(BaseModel):
        name: str
        localized_name: str
        value: str

    trip_types: Optional[list[Trip_Advisor_TripType]] = None

    class Trip_Advisor_Award(BaseModel):
        award_type: str
        year: str

        class Trip_Advisor_Image(BaseModel):
            tiny: str
            small: str
            large: str

        images: Trip_Advisor_Image
        categories: list[str]
        display_name: str

    awards: Optional[list[Trip_Advisor_Award]] = None
    error: Optional[Trip_Advisor_Error] = None

    class Config:
        extra = 'allow'  # This will ignore any extra fields not defined in the model


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

    class Amadeus_Meta(BaseModel):
        count: int
        links: Dict[str, str]
        sort: Optional[str] = None

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
            class Config:
                extra = 'allow' # Poor documentation is available

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
