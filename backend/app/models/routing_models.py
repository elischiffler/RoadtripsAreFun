from typing import Any, Optional

from pydantic import BaseModel


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


# Mapbox Base Models

class Mapbox_waypoint(BaseModel):
    name: str
    location: list[float]
    distance: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None


class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str


class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_notification(BaseModel):
                details: Optional[dict[str, str]] = None
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
        duration: float
        distance: float
        legs: list[Mapbox_leg]
        geometry: Mapbox_geo
        waypoints: Optional[Mapbox_waypoint] = []

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
    street1: str
    street2: str
    city: str
    state: str
    country: str
    postal_code: str
    address_string: str


class Trip_Advisor_Location_Search(BaseModel):
    class Trip_Advisor_Location(BaseModel):
        location_id: int
        name: str
        distance: str
        bearing: str
        address_obj: Trip_Advisor_Address

    data: list[Trip_Advisor_Location]
    error: Trip_Advisor_Error

class Trip_Advisor_Subcategory(BaseModel):
    name: str
    localized_name: str

class Trip_Advisor_Information(BaseModel):
    location_id: int
    name: str
    description: str
    web_url: str
    address_obj: Trip_Advisor_Address
    ancestors: list[dict]
    latitude: float
    longitude: float
    timezone: str
    email: str
    phone: str
    website: str
    write_review: str
    ranking_data: dict
    rating: float
    rating_image_url: str
    num_reviews: str
    review_rating_count: dict[str, str]
    subratings: dict[str, Any]
    photo_count: int
    see_all_photos: str
    price_level: str  # A number of dollar signs 1-5 indicating price

    class Trip_Advisor_Hours(BaseModel):
        class Trip_Advisor_Period(BaseModel):
            class Trip_Advisor_Time(BaseModel):
                day: int
                time: str

            open: Trip_Advisor_Time
            close: Trip_Advisor_Time

        periods: list[dict]
        weekday_text: str

    hours: list[Trip_Advisor_Hours]
    amenities: list[str]
    features: list[str]
    cuisine: list[Trip_Advisor_Subcategory]
    parent_brand: str
    brand: str
    category: Trip_Advisor_Subcategory
    subcategory: list[Trip_Advisor_Subcategory]

    class Trip_Advisor_Group(BaseModel):
        name: str
        localized_name: str
        categories: list[Trip_Advisor_Subcategory]
    groups: list[Trip_Advisor_Group]
    styles: list[str]
    neighborhood_info: list[Trip_Advisor_Subcategory] # List of nearby neighborhoods

    class Trip_Advisor_TripType(BaseModel):
        name: str
        localized_name: str
        value: str
    trip_types: list[Trip_Advisor_TripType]

    class Trip_Advisor_Award(BaseModel):
        award_type: str
        year: int

        class Trip_Advisor_Image(BaseModel):
            tiny: str
            small: str
            large: str
        images: list[Trip_Advisor_Image]
        categories: list[str]
        display_name: str
    awards: list[Trip_Advisor_Award]
    error: Trip_Advisor_Error


