"""Pydantic v2 models for the Tripadvisor **Terra** Partner API.

Terra replaced the deprecated Content API. The two endpoints the routing layer
uses are:

* ``GET /locations/nearby`` -> :class:`Terra_Page_Nearby_Location`
  (a page of :class:`Terra_Nearby_Location`, each wrapping a full
  :class:`Terra_Location`). Unlike the old ``nearby_search``, this returns the
  *complete* Location inline, so a single call yields name, coordinates,
  address, and urls — no per-result details fanout is needed.
* ``GET /locations/{id}`` -> :class:`Terra_Location` directly.

Only the fields the sourcing layer reads are modelled explicitly; every model
allows extra fields (``extra="allow"``) so unmodelled parts of the rich Terra
payload (photos, reviews, awards, opening hours, ...) are tolerated without a
validation error.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Terra_Coordinates(BaseModel):
    model_config = ConfigDict(extra="allow")

    latitude: float | None = None
    longitude: float | None = None


class Terra_Name(BaseModel):
    model_config = ConfigDict(extra="allow")

    language: str | None = None
    value: str | None = None
    primary: bool | None = None


class Terra_Address(BaseModel):
    model_config = ConfigDict(extra="allow")

    city: str | None = None
    state: str | None = None
    country_name: str | None = None
    country_code: str | None = None
    postal_code: str | None = None
    street_address: str | None = None
    street_address2: str | None = None
    language: str | None = None
    # Pre-formatted single-line address string; the closest analogue to the old
    # ``address_obj.address_string``.
    formatted: str | None = None


class Terra_Tripadvisor_Urls(BaseModel):
    model_config = ConfigDict(extra="allow")

    main: str | None = None
    photos: str | None = None
    write_review: str | None = None
    questions_answers: str | None = None


class Terra_Urls(BaseModel):
    model_config = ConfigDict(extra="allow")

    official: str | None = None
    menu: str | None = None
    # The public Tripadvisor listing links; ``tripadvisor.main`` is the analogue
    # of the old ``web_url``.
    tripadvisor: Terra_Tripadvisor_Urls | None = None


class Terra_Overall_Rating(BaseModel):
    model_config = ConfigDict(extra="allow")

    # 1.0-5.0 bubble rating. Terra has no per-location popularity *rank* integer
    # (the old ``ranking_data.ranking``), so rating is the quality signal.
    rating: float | None = None
    count: int | None = None


class Terra_Traveler_Ratings(BaseModel):
    model_config = ConfigDict(extra="allow")

    overall: Terra_Overall_Rating | None = None


class Terra_Ranking(BaseModel):
    """Populated only for locations that hold a ranked position in their Geo.

    Most locations omit ``rankings`` entirely (verified live), so this is best
    effort — the sourcing layer derives its ordering from result position, not
    from this field.
    """

    model_config = ConfigDict(extra="allow")

    rank: int | None = None
    total: int | None = None
    display_text: str | None = None
    geo: str | None = None


class Terra_Location(BaseModel):
    """The full Terra Location. Returned inline by nearby search and directly by
    the details endpoint."""

    model_config = ConfigDict(extra="allow")

    id: int | None = None
    geo: str | None = None
    geo_id: int | None = None
    names: list[Terra_Name] | None = None
    coordinates: Terra_Coordinates | None = None
    addresses: list[Terra_Address] | None = None
    urls: Terra_Urls | None = None
    traveler_ratings: Terra_Traveler_Ratings | None = None
    rankings: list[Terra_Ranking] | None = None

    def primary_name(self) -> str | None:
        """The Location's name, preferring the entry flagged ``primary``."""
        if not self.names:
            return None
        for name in self.names:
            if name.primary and name.value:
                return name.value
        return self.names[0].value

    def formatted_address(self) -> str | None:
        """The pre-formatted single-line address, if any."""
        if not self.addresses:
            return None
        for address in self.addresses:
            if address.formatted:
                return address.formatted
        return None

    def web_url(self) -> str | None:
        """The public Tripadvisor listing URL (analogue of the old ``web_url``)."""
        if self.urls and self.urls.tripadvisor:
            return self.urls.tripadvisor.main
        return None

    def overall_rating(self) -> float | None:
        """The overall bubble rating (1.0-5.0), if available."""
        if self.traveler_ratings and self.traveler_ratings.overall:
            return self.traveler_ratings.overall.rating
        return None


class Terra_Nearby_Location(BaseModel):
    """One entry in a nearby-search page: a full Location plus its distance and
    bearing from the search center."""

    model_config = ConfigDict(extra="allow")

    location: Terra_Location | None = None
    distance_miles: float | None = None
    distance_kilometers: float | None = None
    bearing: float | None = None


class Terra_Page_Metadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    page: int | None = None
    size: int | None = None
    total_elements: int | None = None
    total_pages: int | None = None


class Terra_Page_Nearby_Location(BaseModel):
    """Response body of ``GET /locations/nearby``."""

    model_config = ConfigDict(extra="allow")

    data: list[Terra_Nearby_Location] = []
    pagination: Terra_Page_Metadata | None = None
