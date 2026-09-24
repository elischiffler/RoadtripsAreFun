from pydantic import BaseModel


class LatLngLiteral(BaseModel):
    lat: float
    lng: float


class GooglePlaces(BaseModel):
    class GooglePlace(BaseModel):
        class address_component(BaseModel):
            long_name: str
            short_name: str
            types: list[str]

        class PlaceOpeningHours(BaseModel):
            class PlaceOpeningHoursPeriod(BaseModel):
                class OpeningHoursPeriodDetail(BaseModel):
                    day: int
                    time: str
                    date: str | None = None
                    truncated: bool | None = None

                open: OpeningHoursPeriodDetail
                close: OpeningHoursPeriodDetail | None = None

            class PlaceSpecialDay(BaseModel):
                date: str | None = None
                exceptional_hours: bool | None = None

            open_now: bool | None = None
            periods: list[PlaceOpeningHoursPeriod] | None = []
            special_days: list[PlaceSpecialDay] | None = []
            type: str | None = None
            weekday_text: list[str] | None = []

        class PlaceEditorialSummary(BaseModel):
            language: str | None = None
            overview: str | None = None

        class Geometry(BaseModel):
            class Bounds(BaseModel):
                northeast: LatLngLiteral
                southwest: LatLngLiteral

            location: LatLngLiteral
            viewport: Bounds

        class Photo(BaseModel):
            height: int
            html_attributions: list[str]
            photo_reference: str
            width: int

        class PlusCode(BaseModel):
            global_code: str
            compound_code: str | None = None

        class PlaceReview(BaseModel):
            author_name: str
            rating: int | float
            relative_time_description: str
            time: int | float
            author_url: str | None = None
            language: str | None = None
            original_language: str | None = None
            profile_photo_url: str | None = None
            text: str | None = None
            translated: bool | None = None

        address_components: list[address_component] | None = []
        adr_address: str | None = None
        business_status: str | None = None
        curbside_pickup: bool | None = None
        current_opening_hours: list[PlaceOpeningHours] | None = []
        delivery: bool | None = None
        dine_in: bool | None = None
        editorial_summary: PlaceEditorialSummary | None = None
        formatted_address: str | None = None
        formatted_phone_number: str | None = None
        geometry: Geometry | None = None
        icon: str | None = None
        icon_background_color: str | None = None
        icon_mask_base_uri: str | None = None
        international_phone_number: str | None = None
        name: str | None = None
        opening_hours: PlaceOpeningHours | None = None
        photos: list[Photo] | None = []
        place_id: str | None = None
        plus_code: PlusCode | None = None
        price_level: int | None = None
        rating: float | None = None
        reservable: bool | None = None
        reviews: list[PlaceReview] | None = []
        secondary_opening_hours: list[PlaceOpeningHours] | None = []
        serves_beer: bool | None = None
        serves_breakfast: bool | None = None
        serves_brunch: bool | None = None
        serves_dinner: bool | None = None
        serves_lunch: bool | None = None
        serves_vegetarian_food: bool | None = None
        serves_wine: bool | None = None
        takeout: bool | None = None
        types: list[str] | None = []
        url: str | None = None
        user_ratings_total: int | None = None
        utc_offset: int | float | None = None
        vicinity: str | None = None
        website: str | None = None
        wheelchair_accessible_entrance: bool | None = None

    html_attributions: list[str]
    results: list[GooglePlace]
    status: str
    error_message: str | None = None
    info_messages: list[str] | None = []
    next_page_token: str | None = None
