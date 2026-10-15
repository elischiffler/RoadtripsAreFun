"""Evaluation-side capture and access-review exchange; no catalog DB changes."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.routing.cp_sat_selection import valid_coordinates


class StrictEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("schema_version", mode="before", check_fields=False)
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value


class EvidenceReference(StrictEvidence):
    uri: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RatingCapture(StrictEvidence):
    capture_id: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    configuration: dict
    captured_at: datetime

    @field_validator("captured_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("capture time must include a UTC offset")
        return value


class RoutingCapture(StrictEvidence):
    capture_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    profile: str = Field(min_length=1)
    departure_context: datetime
    captured_at: datetime

    @field_validator("captured_at", "departure_context")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("routing times must include UTC offsets")
        return value


class AccessReview(StrictEvidence):
    provider_id: str = Field(min_length=1)
    coordinates: list[float]
    status: Literal["eligible", "ineligible", "pending"]
    arrival_eligible: StrictBool
    reviewed_at: datetime | None
    valid_through: date | None
    reviewer: str | None
    evidence: list[EvidenceReference]

    @field_validator("coordinates", mode="before")
    @classmethod
    def coords(cls, value):
        if not valid_coordinates(value):
            raise ValueError("review requires finite [lat, lon] arrival coordinates")
        return value

    def rejection(self, coordinates, clock, departure):
        if self.status != "eligible" or not self.arrival_eligible:
            return "access_not_approved"
        if self.coordinates != coordinates:
            return "review_arrival_coordinates_changed"
        if not self.reviewed_at or not self.reviewed_at.tzinfo or self.reviewed_at > clock:
            return "review_time_missing_or_after_evaluation_clock"
        if not self.valid_through or self.valid_through < departure.date():
            return "access_review_expired"
        if not self.reviewer or not self.reviewer.strip() or not self.evidence:
            return "access_review_evidence_missing"
        return None


class ReviewLedger(StrictEvidence):
    schema_version: Literal[1]
    catalog_generation: str = Field(min_length=1)
    catalog_release: str = Field(min_length=1)
    records: list[AccessReview]

    def approved(self, generation, release, clock, departure):
        if (self.catalog_generation, self.catalog_release) != (generation, release):
            raise ValueError("access reviews belong to a different catalog generation/release")
        by_id = {}
        for review in self.records:
            if review.provider_id in by_id:
                raise ValueError("duplicate access-review identity")
            by_id[review.provider_id] = review
        return by_id


class RightsEvidence(StrictEvidence):
    schema_version: Literal[1]
    catalog_generation: str = Field(min_length=1)
    catalog_release: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    approved_for_evaluation: Literal[True]
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    licenses: list[EvidenceReference] = Field(min_length=1)

    @field_validator("approved_for_evaluation", mode="before")
    @classmethod
    def explicit_approval(cls, value):
        if value is not True:
            raise ValueError("rights approval must be explicit true")
        return value


class SourceCatalog(StrictEvidence):
    release: str = Field(min_length=1)
    attribution: str = Field(min_length=1)


def source_metadata(source, release, attribution, source_catalogs, provenance=()):
    """Honor catalog leaf metadata and retained duplicate-source credits."""
    if source_catalogs:
        if source not in source_catalogs:
            raise ValueError("source is absent from declared source_catalogs")
        leaf = SourceCatalog.model_validate(source_catalogs[source])
        release, attribution = leaf.release, leaf.attribution
    additional = {
        part["source_attribution"]
        for part in provenance
        if isinstance(part.get("source_attribution"), str)
    }
    return release, "; ".join(dict.fromkeys([attribution, *sorted(additional)]))


class CatalogExport(StrictEvidence):
    schema_version: Literal[1]
    evidence_type: Literal["catalog_owner_export", "synthetic_unit_only"]
    catalog_generation: str = Field(min_length=1)
    catalog_release: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    records: list[dict]
    source_catalogs: dict[str, SourceCatalog] = {}
