"""Review reports cannot masquerade as import approval or driving points."""

import importlib.util
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def profiler():
    spec = importlib.util.spec_from_file_location(
        "profile_kaggle_probe", Path(__file__).parents[2] / "scripts/profile_kaggle_archive.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_profile_preserves_native_key_duplicates_and_unknown_status(tmp_path, profiler):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(
            "coaster_db.csv",
            "coaster_name,latitude,longitude,Location,Status\nRide,40,-105,Park,Operating\nRide,NaN,-105,Park,\nOther,91,0,Unknown,Removed\n",
        )
        z.writestr("photos.jpg", "never decoded as a place")
    report = profiler.profile(p, "coasters-v2")
    assert report["rows"] == 3
    assert report["duplicate_keys"] == 1
    assert report["finite_wgs84_source_points"] == 1
    assert report["groups"] == {"Operating": 1, "Removed": 1, "unknown": 1}
    assert report["review_only"] and report["accepted_for_import"] == 0
    assert not report["source_points_are_verified_arrivals"]


def test_roadside_metadata_does_not_invent_coordinates(tmp_path, profiler):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(
            "us_roadside_attractions.csv",
            "index,year,title,image,image_link\n1,1987,Old venue,a.jpg,https://example.test\n",
        )
    report = profiler.profile(p, "roadside-v4")
    assert report["finite_wgs84_source_points"] is None
    assert report["accepted_for_import"] == 0


@pytest.mark.parametrize(
    "data",
    [
        "unexpected,columns\n1,2\n",
        "coaster_name,latitude,longitude,Location,Status,Status\na,40,-105,Park,Open,Open\n",
    ],
)
def test_unexpected_or_duplicate_headers_fail(tmp_path, profiler, data):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("coaster_db.csv", data)
    with pytest.raises(ValueError, match="schema"):
        profiler.profile(p, "coasters-v2")


def test_bounded_profile_rejects_instead_of_claiming_complete_counts(
    tmp_path, profiler, monkeypatch
):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("us_roadside_attractions.csv", "index,year\n1,1987\n2,1988\n")
    monkeypatch.setattr(profiler, "MAX_ROWS", 1)
    with pytest.raises(ValueError, match="row profile ceiling"):
        profiler.profile(p, "roadside-v4")
    monkeypatch.setattr(profiler, "MAX_BYTES", 1)
    with pytest.raises(ValueError, match="20 MiB"):
        profiler.profile(p, "roadside-v4")


def test_unrequested_archive_member_is_not_selected(tmp_path, profiler):
    p = tmp_path / "test.zip"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr(
            "../parks.csv", "Park Code,Park Name,State,Latitude,Longitude\nX,Park,CO,40,-105\n"
        )
    with pytest.raises(ValueError, match="CSV member missing"):
        profiler.profile(p, "parks-v3")
    assert not (tmp_path / "parks.csv").exists()
