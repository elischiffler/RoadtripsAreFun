"""Derived proof metadata. Input copies are always recomputed by timing owners."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OneDayProof(BaseModel):
    status: Literal["validated"] = "validated"
    elapsed_seconds: float = Field(ge=0, lt=43200, allow_inf_nan=False)
    threshold_seconds: Literal[43200] = 43200
    validated_at: datetime
