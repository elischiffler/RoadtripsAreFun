"""Synthetic research geometry checks; no real-world arrival is asserted."""

import hashlib
import json

import pytest
from scripts import catalog_arrival_geometry as geometry


def source_fixture(tmp_path, *, wrong_road=False, disconnected=False):
    junction, internal = [-79.03, 35.90], [-79.0301, 35.8999]
    roads = {
        "features": [
            {
                "attributes": {
                    "OBJECTID": 8202,
                    "FullName": "PARKING LOT",
                    "Cross1": "OLD MASON FARM RD",
                },
                "geometry": {"paths": [[junction, internal]]},
            },
            {
                "attributes": {
                    "OBJECTID": 9286,
                    "FullName": "OTHER RD" if wrong_road else "OLD MASON FARM RD",
                },
                "geometry": {
                    "paths": [[[-79.029, 35.90], [-79.031, 35.901] if disconnected else junction]]
                },
            },
        ]
    }
    lots = {
        "features": [
            {
                "attributes": {
                    "OBJECTID": 3864,
                    "LOT_NAME": "BOTANICAL GARDEN",
                    "LOT_NUMBER": "P256",
                },
                "geometry": {
                    "rings": [
                        [
                            [-79.031, 35.899],
                            [-79.03001, 35.899],
                            [-79.03001, 35.89999],
                            [-79.031, 35.89999],
                        ]
                    ]
                },
            }
        ]
    }
    receipts = []
    for ident, value, url in [
        (
            "deldot-public-approach-context",
            {
                "features": [
                    {"attributes": {"STREET_NAME": "BAYSIDE DRIVE"}},
                    {"attributes": {"STREET_NAME": "72 - Air Force"}},
                ]
            },
            "https://enterprise.firstmaptest.delaware.gov/arcgis/rest/services/Transportation/DE_Roadways_Main/MapServer/1/query?outSR=4326",
        ),
        (
            "chapelhill-front-parking-approaches",
            roads,
            "https://gis-portal.townofchapelhill.org/server/rest/services/OpenData/Streets/FeatureServer/0/query?outSR=4326",
        ),
        (
            "unc-parking-near-ncbg",
            lots,
            "https://gismaps.unc.edu/arcgis/rest/services/UNCOpenData/UNCOpenData/FeatureServer/7/query?outSR=4326",
        ),
    ]:
        body = json.dumps(value).encode()
        (tmp_path / (ident + ".bin")).write_bytes(body)
        receipts.append(
            {
                "id": ident,
                "status": 200,
                "path": ident + ".bin",
                "url": url,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
        )
    (tmp_path / "receipts.json").write_text(json.dumps(receipts))


def test_corroborated_geometry_remains_a_candidate_with_unknown_accuracy(tmp_path):
    source_fixture(tmp_path)
    result = geometry.review(tmp_path)
    assert result["ncbg"]["front_driveway_coordinate_lat_lon"] == [35.9, -79.03]
    assert result["ncbg"]["horizontal_accuracy_metres"] is None
    assert (
        result["qualified_arrivals"]
        == result["admission_changes"]
        == result["itinerary_ready"]
        == 0
    )
    assert result["amc"]["arrival_coordinate_lat_lon"] is None
    assert geometry.review(tmp_path) == result


@pytest.mark.parametrize(
    "options, reason",
    [
        ({"wrong_road": True}, "entities differ"),
        ({"disconnected": True}, "shared street/driveway"),
    ],
)
def test_other_road_or_disconnected_point_cannot_support_candidate(tmp_path, options, reason):
    source_fixture(tmp_path, **options)
    with pytest.raises(ValueError, match=reason):
        geometry.review(tmp_path)


def test_changed_geometry_body_is_rejected(tmp_path):
    source_fixture(tmp_path)
    (tmp_path / "unc-parking-near-ncbg.bin").write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest differs"):
        geometry.review(tmp_path)
