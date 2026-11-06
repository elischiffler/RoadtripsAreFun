"""Offline route-wide browsing tests; no database, model or provider calls."""

import pytest
from pydantic import ValidationError

from app.models.guided_planning import RouteAlternativesRequest
from app.routing import alternatives


def place(identity, coordinate):
    return {
        "provider_id": identity,
        "source": "boulder-osmp",
        "name": identity,
        "coordinates": coordinate,
        "categories": ["daytime"],
        "source_provenance": [],
        "source_attribution": "Fixture source credit",
    }


def test_distance_samples_ignore_uneven_vertex_density_and_include_endpoints():
    samples, total = alternatives.route_samples([[0, 0], [0.001, 0], [1, 0]])
    assert samples[0][0] == pytest.approx((0, 0))
    assert samples[-1][0] == pytest.approx((0, 1))
    distances = [alternatives._distance(a[0], b[0]) for a, b in zip(samples, samples[1:])]
    assert max(distances) - min(distances) < 0.001
    assert total > 60
    long_samples, _ = alternatives.route_samples([[0, 0], [120, 0]])
    assert len(long_samples) == alternatives.MAX_SAMPLES


def test_dateline_and_zero_length_geometry():
    samples, total = alternatives.route_samples([[179.9, 0], [-179.9, 0]])
    assert total < 14
    assert all(abs(point[1]) > 179 for point, _ in samples)
    assert alternatives.route_samples([[1, 2], [1, 2]]) == ([((2, 1), 0)], 0)


def test_balances_full_route_excludes_stops_and_retains_credit(monkeypatch):
    calls = []

    def nearby(point, categories, **kwargs):
        calls.append((point, kwargs))
        return [place(f"boulder:{len(calls)}:{index}", point) for index in range(12)]

    monkeypatch.setattr(alternatives, "catalog_nearby", nearby)
    payload = RouteAlternativesRequest(geometry=[[0, 0], [5, 0]], exclude_coordinates=[(0, 0)])
    result = alternatives.browse_alternatives(payload)
    assert len(calls) == alternatives.MAX_SAMPLES
    assert len(result.places) == 12
    assert max(p.route_fraction for p in result.places) > 0.9
    assert min(p.route_fraction for p in result.places) < 0.1
    assert all(p.coordinates != (0, 0) for p in result.places)
    assert all(p.source_attribution == "Fixture source credit" for p in result.places)
    assert all(p.detour_minutes is None for p in result.places)
    assert result.coverage["road_detours_checked"] is False
    assert result.coverage["trip_date_availability_checked"] is False
    assert result.coverage["continuous"] is False
    assert all(c[1]["require_visit_calendar"] for c in calls)


def test_admission_calendar_identity_and_outside_radius_fail_closed(monkeypatch):
    records = [
        None,
        {**place("boulder:bad-provenance", [0, 0]), "source_provenance": None},
        place("catalog-pilot:unreviewed", [0, 0]),
        {
            **place("boulder:unknown-calendar", [0, 0]),
            "source_provenance": [{"source_visit_calendar": {}}],
        },
        place("boulder:existing", [0, 0]),
        place("boulder:far", [50, 50]),
        place("boulder:usable", [0, 0]),
    ]
    monkeypatch.setattr(alternatives, "catalog_nearby", lambda *a, **k: records)
    result = alternatives.browse_alternatives(
        RouteAlternativesRequest(geometry=[[0, 0], [0, 0]], exclude_ids=["boulder:existing"])
    )
    assert [p.id for p in result.places] == ["boulder:usable"]


@pytest.mark.parametrize(
    "extra",
    [
        {"geometry": []},
        {"geometry": [[0, 0]]},
        {"geometry": [[181, 0], [0, 0]]},
        {"geometry": [[0, 0], [0, 91]]},
        {"geometry": [[0, 0]] * 10001},
        {"geometry": [[0, 0], [0, 0]], "exclude_coordinates": [[0, 0]] * 101},
    ],
)
def test_bounded_geometry_contract(extra):
    with pytest.raises(ValidationError):
        RouteAlternativesRequest(**extra)
