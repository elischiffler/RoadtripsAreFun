"""Physical shared-arrival admission, including global spatial-grid boundaries."""

import pytest

from tests.catalog_extraction_tests import load_script

release = load_script("catalog_expansion_release")


def row(ident, lat=35.0, lon=-120.0):
    return {"source_id": ident, "name": ident, "latitude": lat, "longitude": lon}


def test_new_different_names_cannot_inflate_identical_physical_arrival():
    with pytest.raises(ValueError, match="shared arrival"):
        release.proximity_review([row("Tuesday market"), row("Saturday market")], set())


def test_existing_baseline_coincidences_remain_preserved():
    assert release.proximity_review([row("old-a"), row("old-b")], {"old-a", "old-b"}) == []


@pytest.mark.parametrize(
    "a,b",
    [
        (row("a", 0, 179.9999), row("b", 0, -179.9999)),
        (row("a", 89.999, 0), row("b", 89.999, 90)),
        (row("a"), row("b", 35.001, -120)),
    ],
)
def test_nearby_distinct_destinations_are_reported_without_silent_merge(a, b):
    result = release.proximity_review([a, b], set())
    assert len(result) == 1
    assert result[0]["provider_ids"] == ["a", "b"]
    assert 1 < result[0]["distance_metres"] < 250


def test_new_arrival_is_checked_against_preserved_rows():
    with pytest.raises(ValueError, match="shared arrival"):
        release.proximity_review([row("old"), row("new")], {"old"})


def test_far_apart_points_do_not_create_a_review_pair():
    assert release.proximity_review([row("a"), row("b", 40, -73)], set()) == []
