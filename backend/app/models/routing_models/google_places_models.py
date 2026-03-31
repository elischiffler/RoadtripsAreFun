from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Union


class LatLngLiteral(BaseModel):
    lat: float
    lng: float


class GooglePlaces(BaseModel):
    class GooglePlace(BaseModel):
        class address_component(BaseModel):
            long_name: str
            short_name: str
            types: List[str]

        class PlaceOpeningHours(BaseModel):
            class PlaceOpeningHoursPeriod(BaseModel):
                class OpeningHoursPeriodDetail(BaseModel):
                    day: int
                    time: str
                    date: Optional[str] = None
                    truncated: Optional[bool] = None

                open: OpeningHoursPeriodDetail
                close: Optional[OpeningHoursPeriodDetail] = None

            class PlaceSpecialDay(BaseModel):
                date: Optional[str] = None
                exceptional_hours: Optional[bool] = None

            open_now: Optional[bool] = None
            periods: Optional[List[PlaceOpeningHoursPeriod]] = []
            special_days: Optional[List[PlaceSpecialDay]] = []
            type: Optional[str] = None
            weekday_text: Optional[List[str]] = []

        class PlaceEditorialSummary(BaseModel):
            language: Optional[str] = None
            overview: Optional[str] = None

        class Geometry(BaseModel):
            class Bounds(BaseModel):
                northeast: LatLngLiteral
                southwest: LatLngLiteral

            location: LatLngLiteral
            viewport: Bounds

        class Photo(BaseModel):
            height: int
            html_attributions: List[str]
            photo_reference: str
            width: int

        class PlusCode(BaseModel):
            global_code: str
            compound_code: Optional[str] = None

        class PlaceReview(BaseModel):
            author_name: str
            rating: Union[int, float]
            relative_time_description: str
            time: Union[int, float]
            author_url: Optional[str] = None
            language: Optional[str] = None
            original_language: Optional[str] = None
            profile_photo_url: Optional[str] = None
            text: Optional[str] = None
            translated: Optional[bool] = None

        address_components: Optional[List[address_component]] = []
        adr_address: Optional[str] = None
        business_status: Optional[str] = None
        curbside_pickup: Optional[bool] = None
        current_opening_hours: Optional[List[PlaceOpeningHours]] = []
        delivery: Optional[bool] = None
        dine_in: Optional[bool] = None
        editorial_summary: Optional[PlaceEditorialSummary] = None
        formatted_address: Optional[str] = None
        formatted_phone_number: Optional[str] = None
        geometry: Optional[Geometry] = None
        icon: Optional[str] = None
        icon_background_color: Optional[str] = None
        icon_mask_base_uri: Optional[str] = None
        international_phone_number: Optional[str] = None
        name: Optional[str] = None
        opening_hours: Optional[PlaceOpeningHours] = None
        photos: Optional[List[Photo]] = []
        place_id: Optional[str] = None
        plus_code: Optional[PlusCode] = None
        price_level: Optional[int] = None
        rating: Optional[float] = None
        reservable: Optional[bool] = None
        reviews: Optional[List[PlaceReview]] = []
        secondary_opening_hours: Optional[List[PlaceOpeningHours]] = []
        serves_beer: Optional[bool] = None
        serves_breakfast: Optional[bool] = None
        serves_brunch: Optional[bool] = None
        serves_dinner: Optional[bool] = None
        serves_lunch: Optional[bool] = None
        serves_vegetarian_food: Optional[bool] = None
        serves_wine: Optional[bool] = None
        takeout: Optional[bool] = None
        types: Optional[List[str]] = []
        url: Optional[str] = None
        user_ratings_total: Optional[int] = None
        utc_offset: Optional[Union[int, float]] = None
        vicinity: Optional[str] = None
        website: Optional[str] = None
        wheelchair_accessible_entrance: Optional[bool] = None

    html_attributions: List[str]
    results: List[GooglePlace]
    status: str
    error_message: Optional[str] = None
    info_messages: Optional[List[str]] = []
    next_page_token: Optional[str] = None
