"""Recognized catalog IDs replay frozen evidence without weakening live holds."""

import copy
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.catalog import repository
from app.crud import chat_crud
from app.routers.itinerary_api import generate_itinerary
from app.routing.evaluation import network
from app.routing.evaluation.runner import execute
from tests.routing.catalog_calendar_refresh_tests import IDS, authoritative, payload, record
from tests.routing.evaluation_tests import save_fixture, spec, write_fixture


def catalog_fixture(root, namespace="boulder:", source="boulder-osmp"):
    data, manifest = write_fixture(root)
    identities = {
        item["provider_id"]: namespace + item["provider_id"].split(":", 1)[1]
        for item in data["attractions"]
    }
    for item in data["attractions"]:
        item.update(
            provider_id=identities[item["provider_id"]],
            source=source,
            source_release="explicit-synthetic-frozen-release",
            # New estimated visits require a verified window. Preserve the
            # explicit synthetic hours supplied by write_fixture so this test
            # exercises a real visit/lookup rather than an empty itinerary.
            source_provenance=[
                {"dataset": "Explicit synthetic frozen catalog control"},
                *item.get("source_provenance", []),
            ],
        )
    for node in data["nodes"]:
        node["id"] = identities.get(node["id"], node["id"])
    for key, identifiers in data["production_shortlists"].items():
        data["production_shortlists"][key] = [identities[sid] for sid in identifiers]
    save_fixture(root, data, manifest)
    return copy.deepcopy(data)


@pytest.mark.parametrize("method", ["cp_sat", "utility_first", "spacing_first"])
@pytest.mark.parametrize(
    "namespace,source", [("boulder:", "boulder-osmp"), ("overture:", "overture")]
)
def test_catalog_id_pipeline_uses_only_frozen_facts(
    tmp_path, monkeypatch, method, namespace, source
):
    original = catalog_fixture(tmp_path / "short-1d", namespace, source)
    attempted = []

    def forbidden(*args, **kwargs):
        attempted.append(True)
        raise AssertionError("offline replay attempted database or network access")

    for name in ["current_records", "nearby", "nearby_page"]:
        monkeypatch.setattr(repository, name, forbidden)
    monkeypatch.setattr(chat_crud, "_get_conn", forbidden)
    monkeypatch.setattr(network, "denied", forbidden)
    row = execute(spec(tmp_path, "offline-pipeline", method))
    assert row["status"] == "completed", row["error"]
    assert row["itinerary"] and row["route"]
    assert row["external_calls"] == 0 and attempted == []
    assert row["offline_provider_reads"]["captured_catalog_fact_reads"] == 1
    arrivals = [
        stop for day in row["itinerary"] for stop in day["stops"] if stop.get("provider_id")
    ]
    assert all(stop["source_release"] == "explicit-synthetic-frozen-release" for stop in arrivals)
    import json

    assert json.loads((tmp_path / "short-1d/data.json").read_text()) == original


@pytest.mark.asyncio
async def test_http_payload_cannot_replace_current_hold_with_frozen_facts(monkeypatch):
    calls = []

    def current(identifiers):
        calls.append(identifiers)
        return {IDS[0]: authoritative(record())}

    monkeypatch.setattr(repository, "current_records", current)
    body = payload(record(held=False)).model_dump(mode="json")
    body["catalog_lookup"] = {IDS[0]: authoritative(record(held=False))}

    async def json_body():
        return body

    with pytest.raises(HTTPException) as error:
        await generate_itinerary(SimpleNamespace(json=json_body))
    assert error.value.status_code == 422 and calls == [[IDS[0]]]


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["held", "missing", "arrival_changed", "wrong_type"])
async def test_frozen_lookup_keeps_the_same_fail_closed_rules(monkeypatch, case):
    from app.routers.itinerary_api import build_itinerary
    from app.routing.visit_calendar import VisitCalendarConflict

    def forbidden(*args, **kwargs):
        raise AssertionError("explicit frozen lookup must never fall back to active DB")

    monkeypatch.setattr(repository, "current_records", forbidden)
    facts = {IDS[0]: authoritative(record(held=case == "held"))}
    if case == "missing":
        facts = {}
    if case == "arrival_changed":
        facts[IDS[0]]["coordinates"] = [0, 0]
    data = payload(record(held=False), kind="generic" if case == "wrong_type" else "stop")
    with pytest.raises(VisitCalendarConflict):
        await build_itinerary(data, catalog_lookup=lambda identifiers: facts)


def test_frozen_replay_does_not_change_live_hold_enforcement(tmp_path, monkeypatch):
    import asyncio

    from app.models.itinerary_models import Itinerary_Payload
    from app.routers.itinerary_api import build_itinerary
    from app.routing.visit_calendar import VisitCalendarConflict

    original = catalog_fixture(tmp_path / "short-1d")
    calls = []
    by_id = {item["provider_id"]: item for item in original["attractions"]}

    def active(identifiers):
        calls.append(identifiers)
        return {
            sid: {
                **authoritative(record()),
                "coordinates": by_id[sid]["coordinates"],
            }
            for sid in identifiers
        }

    monkeypatch.setattr(repository, "current_records", active)
    row = execute(spec(tmp_path, "offline-pipeline"))
    assert row["status"] == "completed" and calls == []
    assert len(row["selected_ids"]) == 1
    # The same serialized route must consult active facts on an ordinary call.
    data = Itinerary_Payload.model_validate({"route": row["route"]})
    with pytest.raises(VisitCalendarConflict, match="current catalog access is unresolved"):
        asyncio.run(build_itinerary(data))
    assert calls == [row["selected_ids"]]
