"""Display-only reviewed facts. They never authorize a visit or change timing."""

from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PlaceImage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    src: Annotated[str, Field(pattern=r"^/place-images/[a-z0-9-]+\.(?:jpg|jpeg|png|webp)$")]
    alt: str = Field(min_length=1, max_length=500)
    credit: str = Field(min_length=1, max_length=300)
    license: Literal["CC BY-SA 4.0"]
    license_url: Literal["https://creativecommons.org/licenses/by-sa/4.0/"]
    source_url: str = Field(max_length=2000)
    caption: str = Field(min_length=1, max_length=500)
    width: int = Field(strict=True, ge=1, le=4000)
    height: int = Field(strict=True, ge=1, le=4000)

    @field_validator("source_url")
    @classmethod
    def source_is_review_record(cls, value):
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc != "commons.wikimedia.org"
            or not (url.path.startswith("/wiki/File:") or url.path == "/w/index.php")
        ):
            raise ValueError("A reviewed Commons image record is required")
        return value


class PlaceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(min_length=1, max_length=1000)
    image: PlaceImage | None = None
