"""Reviewed display context never becomes admission, timing or client authority."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.catalog import place_context
from app.models.itinerary_models import Itinerary_Payload
from app.models.place_context import PlaceImage
from app.models.route_edit import RouteEditRequest
from app.models.routing_models.routing_models import Mapbox_geo, Route
from app.routers.itinerary_api import build_itinerary
from app.routing.alternatives import _public_place
from app.routing.base import PlanningError
from app.routing.route_edit import preview_route_edit

ROOT = Path(__file__).resolve().parents[2]
DOCUMENT = json.loads(place_context.REGISTRY_PATH.read_text())


def facts(index=2):
    # Synthetic admitted-access fixture, independent of the descriptive review.
    return {
        **deepcopy(DOCUMENT["entries"][index]["identity"]),
        "categories": ["daytime"],
        "source_provenance": [],
    }


def route(record=None):
    record = record or facts()
    return Route(
        coordinates=[[40, -105], record["coordinates"], [40.1, -105]],
        distance=2000,
        duration=1200,
        steps=[],
        cost=0,
        geometry={"coordinates": [[-105, 40], [-105, 40.1]], "type": "LineString"},
        departure_time="2030-06-01T09:00:00+00:00",
        start_timezone="UTC",
        scheduling_policy={},
        place_context={"invented": {"summary": "Client-supplied unreviewed claim"}},
        stops=[
            {**record, "type": "stop", "duration": 600, "timezone": "UTC"},
            {"name": "Destination", "type": "end", "duration": 600, "coordinates": [40.1, -105]},
        ],
    )


@pytest.mark.parametrize("index", range(7))
def test_reviewed_identity_gets_only_reviewed_facts_without_mutation(index):
    record = facts(index)
    original = deepcopy(record)
    result = place_context.context_for_admitted_place(record)
    assert result.summary == DOCUMENT["entries"][index]["context"]["summary"]
    assert record == original
    assert _public_place(record).place_context == result
    assert "place_context" not in record


@pytest.mark.parametrize(
    "change",
    [
        {"provider_id": "boulder:unknown"},
        {"source": "unreviewed-provider"},
        {"name": "Chautauqua Annex"},
        {"coordinates": [39.999, -105.28252474797]},
        {"source_provenance": [{"source_visit_calendar": {"unknown_reasons": ["closed"]}}]},
        {"source": "catalog-pilot"},  # No current admission contract.
    ],
)
def test_mismatched_or_unadmitted_identity_has_no_context(change):
    record = {**facts(), **change, "place_context": {"summary": "Forged"}}
    assert place_context.context_for_admitted_place(record) is None


def test_registry_review_and_asset_are_bounded_and_traceable():
    entries = DOCUMENT["entries"]
    assert len(entries) == 31
    assert len({e["identity"]["provider_id"] for e in entries}) == 31
    receipts = {r["url"]: r for r in DOCUMENT["source_receipts"]}
    for entry in entries:
        assert entry["review"]["source_url"] in receipts
        assert entry["review"]["reviewed_on"] == "2026-11-07"
        assert entry["review"]["claims"] == entry["context"]["summary"]
    photos = [e for e in entries if e["context"].get("image")]
    assert len(photos) == 1
    entry = photos[0]
    photo = PlaceImage.model_validate(entry["context"]["image"])
    asset = ROOT / "frontend/public" / photo.src.removeprefix("/")
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == entry["review"]["image"]["sha256"]
    assert photo.width == 960 and photo.height == 720
    assert "oldid=1295058964" in photo.source_url


@pytest.mark.parametrize(
    "src",
    [
        "https://example.test/photo.jpg",
        "//example.test/photo.jpg",
        "/place-images/../private.jpg",
        "/place-images/a.svg",
        "data:image/jpeg;base64,x",
    ],
)
def test_image_contract_rejects_remote_and_executable_assets(src):
    image = deepcopy(DOCUMENT["entries"][2]["context"]["image"])
    image["src"] = src
    with pytest.raises(ValidationError):
        PlaceImage.model_validate(image)


def test_registry_identities_match_checked_in_source_evidence():
    rows = []
    for pattern in [
        "catalog-expansion-500-20261015/reviewed-500.preview.jsonl",
        "catalog-expansion-20261015/reviewed-nature-12.preview.jsonl",
        "catalog-expansion-20261015/reviewed-nps-nature-29.preview.jsonl",
    ]:
        rows.extend(
            json.loads(line) for line in (ROOT / "docs/data" / pattern).read_text().splitlines()
        )
    for entry in DOCUMENT["entries"][:4]:
        identity = entry["identity"]
        source = next(r for r in rows if r["source_id"] == identity["provider_id"])
        assert source["name"] == identity["name"]
        assert [source["latitude"], source["longitude"]] == identity["coordinates"]
    # The three corridor additions retain their exact native names and points.
    coverage = json.loads(
        (ROOT / "docs/evidence/catalog-automation-coverage-20261019.json").read_text()
    )
    source_rows = {row["source_id"]: row for row in coverage["new_places"]}
    for entry in DOCUMENT["entries"][4:7]:
        identity = entry["identity"]
        source = source_rows[identity["provider_id"]]
        assert identity["name"] == source["name"]
        assert identity["coordinates"] == source["coordinates"]


@pytest.mark.asyncio
async def test_itinerary_recomputes_claims_after_refresh_and_keeps_stop_rows_clean():
    record = facts()
    data = Itinerary_Payload(route=route())
    original_stops = deepcopy(data.route.stops)
    days = await build_itinerary(data, catalog_lookup=lambda ids: {record["provider_id"]: record})
    assert set(data.route.place_context) == {record["provider_id"]}
    arrival = next(s for day in days for s in day.stops if s.provider_id)
    assert arrival.place_context.summary == DOCUMENT["entries"][2]["context"]["summary"]
    assert all("place_context" not in s for s in data.route.stops)
    assert data.route.stops[0]["name"] == original_stops[0]["name"]


@pytest.mark.asyncio
async def test_current_identity_change_removes_stale_context_and_legacy_still_builds():
    old = facts()
    current = {**old, "name": "Renamed since display review"}
    data = Itinerary_Payload(route=route(old))
    data.route.place_context = {old["provider_id"]: place_context.context_for_admitted_place(old)}
    days = await build_itinerary(data, catalog_lookup=lambda ids: {old["provider_id"]: current})
    assert data.route.place_context == {}
    assert all(s.place_context is None for day in days for s in day.stops)
    assert any(s.name == current["name"] for day in days for s in day.stops)


@pytest.mark.asyncio
async def test_failed_authoritative_refresh_cannot_render_supplied_claims():
    data = Itinerary_Payload(route=route())
    with pytest.raises(PlanningError):
        await build_itinerary(data, catalog_lookup=lambda ids: {})


@pytest.mark.asyncio
async def test_route_edit_replaces_stale_map_with_new_admitted_context():
    old, selected = facts(0), facts(2)
    saved = route(old)
    saved.place_context = {old["provider_id"]: place_context.context_for_admitted_place(old)}
    before = saved.model_dump()
    payload = RouteEditRequest(
        route=saved.model_dump(),
        action="replace",
        stop_index=0,
        provider_id=selected["provider_id"],
    )
    road = SimpleNamespace(
        legs=[SimpleNamespace(duration=600, distance=1000)] * 2,
        distance=2000,
        duration=1200,
        geometry=Mapbox_geo(coordinates=[[-105, 40], [-105, 40.1]], type="LineString"),
    )
    result = await preview_route_edit(
        payload,
        route_call=AsyncMock(return_value=road),
        timezone_at=AsyncMock(return_value="UTC"),
        catalog_lookup=lambda ids: {
            r["provider_id"]: r for r in [old, selected] if r["provider_id"] in ids
        },
    )
    assert set(result.route.place_context) == {selected["provider_id"]}
    assert (
        next(s for d in result.itinerary for s in d.stops if s.provider_id).place_context
        == result.route.place_context[selected["provider_id"]]
    )
    assert saved.model_dump() == before
    assert all("place_context" not in s for s in result.route.stops)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://commons.wikimedia.org.evil.test/wiki/File:X",
        "https://evil@commons.wikimedia.org/wiki/File:X",
        "https://commons.wikimedia.org/w/index.php-unreviewed",
    ],
)
def test_image_contract_rejects_unreviewed_credit_destinations(url):
    image = deepcopy(DOCUMENT["entries"][2]["context"]["image"])
    image["source_url"] = url
    with pytest.raises(ValidationError):
        PlaceImage.model_validate(image)
