"""Synthetic import orchestration tests; no hosted data or provider calls."""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.catalog.automated_bindings import bind_calendar, native_key

SPEC = importlib.util.spec_from_file_location(
    "catalog_automated_import",
    Path(__file__).resolve().parents[2] / "scripts/catalog_automated_import.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def place(key, lat=37.0, lon=-122.0, name=None, region="CA"):
    return {
        "source_id": key,
        "name": name or key,
        "latitude": lat,
        "longitude": lon,
        "region": region,
    }


def test_identity_name_and_arrival_collisions_are_held_without_moving_native_points():
    baseline = [place("parent", name="Original attraction")]
    additions = [
        place("parent", lat=38),
        place("same-name", lat=38, name="Original Attraction"),
        place("same-arrival", lat=37.0001),
        place("different", lat=37.01),
    ]
    selected, ledger = MODULE.select_arrivals(baseline, [("fixture", additions)])
    assert selected == {"fixture": ["different"]}
    assert {item["reason"] for item in ledger} == {
        None,
        "existing_identity",
        "same_name_and_region",
        "unresolved_arrival_within_250m",
    }
    assert additions[2]["latitude"] == 37.0001


def test_collisions_across_sources_and_grid_boundaries_are_held_deterministically():
    selected, ledger = MODULE.select_arrivals(
        [], [("first", [place("a")]), ("second", [place("b", lon=-122.00001), place("c", lat=38)])]
    )
    assert selected == {"first": ["a"], "second": ["c"]}
    assert ledger[1]["conflicting_source_id"] == "a"


def test_antimeridian_adjacent_points_share_the_arrival_guard():
    selected, _ = MODULE.select_arrivals(
        [place("a", lat=65, lon=179.9999, region="AK")],
        [("fixture", [place("b", lat=65, lon=-179.9999, region="AK")])],
    )
    assert selected == {"fixture": []}


def test_existing_output_and_oversized_evidence_are_not_overwritten(tmp_path):
    output = tmp_path / "already-there"
    output.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        MODULE.snapshot(None, output)
    with pytest.raises(ValueError, match="missing or oversized"):
        MODULE.load(tmp_path / "absent")


def native(sid, identity="123"):
    return {
        **place(sid),
        "provenance": [
            {
                "dataset": "USDA Forest Service public recreation facilities",
                "published_access_facts": {"construction_feed": {"record_id": identity}},
            }
        ],
    }


def test_exact_native_binding_retains_parent_identity_and_source_credits():
    parent, current = native("usfs:old-portal"), native("usfs:facility:123")
    entry = {
        "source_id": current["source_id"],
        "source_release": "new-source",
        "transformation": {},
    }
    result = bind_calendar(current, parent, entry)
    assert result["source_id"] == parent["source_id"]
    assert "source_release" not in result
    assert result["transformation"]["parent_identity_binding"]["coordinates_unchanged"]
    assert entry["source_release"] == "new-source"
    assert native_key(parent) == ("usfs-facility", "123")


@pytest.mark.parametrize("change", ["identity", "coordinates", "calendar"])
def test_native_binding_cannot_override_calendars_or_change_arrivals(change):
    parent, current = native("usfs:old-portal"), native("usfs:facility:123")
    if change == "identity":
        current = native("usfs:facility:124", "124")
    elif change == "coordinates":
        current["longitude"] += 0.000001
    else:
        parent["provenance"].append({"source_visit_calendar": {"unknown_reasons": ["Held"]}})
    with pytest.raises(ValueError, match="identical native facility"):
        bind_calendar(current, parent, {"source_id": current["source_id"], "transformation": {}})


def test_similar_names_are_never_native_identity_bindings():
    assert native_key(place("arbitrary", name="Same visitor center")) is None


def test_refresh_prepares_without_implicit_database_writes(tmp_path, monkeypatch):
    operations = []
    output = tmp_path / "run"

    def snapshot(path):
        operations.append(("read", path))

    def acquire(name, path, parent, routes_index, **kwargs):
        operations.append((name, kwargs["parking_publication_urls"]))
        return {"source_path": str(path / "source.json")}

    def build(parent, acquired, path, **kwargs):
        operations.append(("offline_build", len(acquired)))
        return {"rows": 4, "network_or_database_calls": False}

    monkeypatch.setattr(MODULE, "configured_snapshot", snapshot)
    monkeypatch.setattr(MODULE, "acquire_source", acquire)
    monkeypatch.setattr(MODULE, "bundle", build)
    result = MODULE.refresh(
        output,
        tmp_path / "routes.json",
        ["automated-nps", "usfs-current"],
        parking_publication_urls=["reviewed-publication"],
    )
    assert result["status"] == "prepared"
    assert result["database_write"] is False
    assert result["network_or_database_calls"] is True
    assert operations[1:3] == [("automated-nps", ()), ("usfs-current", ["reviewed-publication"])]
    assert operations[-1] == ("offline_build", 2)


def test_refresh_rejects_reused_output_before_any_source_call(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail("invalid refresh must not connect or fetch")

    monkeypatch.setattr(MODULE, "configured_snapshot", fail)
    with pytest.raises(ValueError, match="new output"):
        MODULE.refresh(tmp_path, tmp_path / "routes.json", ["usfs-current"])
    with pytest.raises(ValueError, match="reviewed source"):
        MODULE.refresh(tmp_path / "new", tmp_path / "routes.json", ["unreviewed"])


def test_refresh_captures_routes_when_no_retained_index_is_supplied(tmp_path, monkeypatch):
    captured = tmp_path / "new/routes/index.json"
    operations = []
    monkeypatch.setattr(
        MODULE, "acquire_routes", lambda path: operations.append("routes") or captured
    )
    monkeypatch.setattr(
        MODULE, "configured_snapshot", lambda path: operations.append("read_parent")
    )

    def acquire(name, output, parent, routes_index, **kwargs):
        assert routes_index == captured
        return {"source_path": "synthetic-source"}

    def build(*args, **kwargs):
        assert kwargs["routes_index"] == captured
        raise MODULE.NoUsableChanges()

    monkeypatch.setattr(MODULE, "acquire_source", acquire)
    monkeypatch.setattr(MODULE, "bundle", build)
    result = MODULE.refresh(tmp_path / "new", None, ["usfs-current"])
    assert operations == ["routes", "read_parent"]
    assert result["status"] == "no_change"
    assert result["database_write"] is False


def test_arrival_source_selectors_cannot_cross_agency_boundaries(tmp_path, monkeypatch):
    from app.catalog import automated_nps

    calls = []
    monkeypatch.setattr(automated_nps, "acquire", lambda output, **kwargs: calls.append(kwargs))
    MODULE.acquire_source(
        "automated-nps",
        tmp_path,
        None,
        None,
        codes=["test"],
        nps_arrival_page_urls=["https://www.nps.gov/test/planyourvisit/directions.htm"],
    )
    assert calls == [
        {
            "codes": ["test"],
            "arrival_page_urls": ["https://www.nps.gov/test/planyourvisit/directions.htm"],
        }
    ]
    with pytest.raises(ValueError, match="only to NPS"):
        MODULE.acquire_source("usfs-current", tmp_path, None, None, nps_arrival_page_urls=["page"])
    with pytest.raises(ValueError, match="only to USFS"):
        MODULE.acquire_source(
            "automated-nps", tmp_path, None, None, parking_publication_urls=["pdf"]
        )
