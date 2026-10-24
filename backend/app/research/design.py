"""Controlled scenarios and one-factor-at-a-time solver experiments."""

import random
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

from app.routing.cp_sat_selection import SelectionConfig
from app.routing.evaluation.scenarios import CORRIDORS, PERSONAS
from app.routing.lab_presets import preset_catalog
from app.routing.run_metrics import fingerprint

TRIPS = {
    "short-1d": ("Short single day", "short-day"),
    "medium-2d": ("Medium two-day", "medium-two-day"),
    "long-3d": ("Long three-day", "long-three-day"),
    "coast-5d": ("Coast to coast", "coast-to-coast"),
}


class Design(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trips: list[Literal["short-1d", "medium-2d", "long-3d", "coast-5d"]] = Field(
        default_factory=lambda: list(TRIPS), min_length=1, max_length=4
    )
    personas: list[Literal["nature", "entertainment"]] = Field(
        default_factory=lambda: list(PERSONAS), min_length=1, max_length=2
    )
    stops_per_day: list[StrictInt] = Field(
        default_factory=lambda: [1, 2, 3], min_length=1, max_length=3
    )
    repeats: int = Field(default=10, strict=True, ge=1, le=10)
    solver_repeats: int = Field(default=30, strict=True, ge=1, le=100)
    pipeline: bool = True
    solver: bool = True
    departure_date: date = Field(
        default_factory=lambda: (
            datetime.now(ZoneInfo("America/Los_Angeles")).date() + timedelta(days=7)
        )
    )
    seed: int = Field(default=1729, strict=True, ge=0, le=2147483647)
    quality_loss: list[StrictFloat] = Field(
        default_factory=lambda: [0.0, 0.05, 0.1, 0.2], min_length=1, max_length=7
    )
    detour_weight: list[StrictFloat] = Field(
        default_factory=lambda: [0.0, 0.25, 1.0, 4.0], min_length=1, max_length=7
    )

    @model_validator(mode="after")
    def validate_design(self):
        if not self.pipeline and not self.solver:
            raise ValueError("Choose at least one study")
        for name in ("trips", "personas", "stops_per_day", "quality_loss", "detour_weight"):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"Duplicate {name} values")
        if any(type(value) is not int or value not in (1, 2, 3) for value in self.stops_per_day):
            raise ValueError("Stops per day must be 1, 2 or 3")
        for value in self.quality_loss:
            SelectionConfig(quality_loss=value)
        for value in self.detour_weight:
            SelectionConfig(detour_weight=value)
        today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
        if not today < self.departure_date <= today + timedelta(days=180):
            raise ValueError("Choose a departure within the next 180 days")
        return self


def variants(design):
    base = SelectionConfig(candidate_limit=60, time_limit_seconds=15.0)
    rows = [{"id": "baseline", "parameter": "baseline", "value": None, "config": asdict(base)}]
    for parameter in ("quality_loss", "detour_weight"):
        for value in getattr(design, parameter):
            if value != getattr(base, parameter):
                rows.append(
                    {
                        "id": f"{parameter}-{value:g}",
                        "parameter": parameter,
                        "value": value,
                        "config": asdict(replace(base, **{parameter: value})),
                    }
                )
    return rows


def plan(design):
    presets = {row["id"]: row["inputs"] for row in preset_catalog()}
    conditions = variants(design)
    cells = []
    for trip in design.trips:
        start, end, days, _, _ = CORRIDORS[trip]
        for persona in design.personas:
            for density in design.stops_per_day:
                inputs = {
                    **{
                        key: value for key, value in presets["short-day"].items() if key != "budget"
                    },
                    "start_id": start,
                    "destination_id": end,
                    "departure_date": design.departure_date.isoformat(),
                    "departure_time": "08:00",
                    "num_stops": days * density,
                    "traveler_count": 2,
                    "hotel_rooms": [{"adults": 2, "child_ages": []}],
                    "car_status": "skipped",
                    "car": None,
                    "persona_weights": PERSONAS[persona],
                    "scheduling_policy": {
                        **presets["short-day"]["scheduling_policy"],
                        "latest_destination_arrival": "21:00",
                    },
                    "evening_interests": [],
                }
                cells.append(
                    {
                        "trip": trip,
                        "persona": persona,
                        "stops_per_day": density,
                        "target_days": days,
                        "inputs": inputs,
                        "preset_id": TRIPS[trip][1],
                    }
                )
    # Solver-only designs still collect one fresh real pool per scenario.
    captures_only = design.solver and not design.pipeline
    cases = []
    rng = random.Random(design.seed)
    for repeat in range(1, max(design.repeats, design.solver_repeats) + 1):
        block = []
        for cell in cells:
            if (design.pipeline and repeat <= design.repeats) or (captures_only and repeat == 1):
                block.append({**cell, "track": "pipeline", "variant": "live", "repeat": repeat})
            if design.solver and repeat <= design.solver_repeats:
                for variant in conditions:
                    block.append(
                        {**cell, "track": "solver", "variant": variant["id"], "repeat": repeat}
                    )
        rng.shuffle(block)
        cases.extend(block)
    dataset = {
        "kind": "real_capture_per_scenario",
        "candidate_limit": 60,
        "capture_repeat": 1,
        "description": "Last measured selection pool from the first live attempt of each scenario; frozen across settings and seeds.",
    }
    return {
        "schema_version": 2,
        "design": design.model_dump(mode="json"),
        "variants": conditions,
        "counts": {
            "combinations": len(cells),
            "pipeline": len(cells)
            * (design.repeats if design.pipeline else 1 if captures_only else 0),
            "solver": len(cells) * design.solver_repeats * len(conditions) if design.solver else 0,
            "total": len(cases),
        },
        "dataset": dataset,
        "dataset_hash": fingerprint(dataset),
        "cases": cases,
    }
