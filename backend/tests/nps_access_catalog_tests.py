import hashlib
import io
import zipfile
from datetime import UTC, datetime, timedelta

import pytest

from app.catalog import nps
from app.catalog.ingest import prepare
from app.catalog.nps_access import dated_closure
from tests.nps_catalog_tests import evidence, source


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("September 1", "May 1", True),
        ("November 1", "April 30", False),
        ("October 14", "October 14", True),
        ("2025-01-01", "2025-12-31", False),
        ("not a date", "October 31", True),
    ],
)
def test_dated_closures_use_published_periods_and_hold_ambiguous_dates(start, end, expected):
    facility = {
        "operatingHours": {
            "1": {
                "exceptions": [
                    {"date_start": start, "date_end": end, "schedule": [{"is_closed": 1}]}
                ]
            }
        }
    }
    assert dated_closure(facility, "2026-10-15T02:00:00+00:00") is expected


def test_fresh_nps_intake_withholds_dated_closure_and_preserves_legacy_manifest(
    tmp_path, monkeypatch
):
    d = source()
    d["visitorCenters"][0]["operatingHours"]["1"]["exceptions"] = [
        {
            "name": "Building renovation",
            "date_start": (datetime.now(UTC).date() - timedelta(days=1)).isoformat(),
            "date_end": (datetime.now(UTC).date() + timedelta(days=1)).isoformat(),
            "schedule": [{"is_closed": 1}],
        }
    ]
    e = evidence(tmp_path, d)
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr(
            "parks.csv",
            "Park Code,Park Name,State,Acres,Latitude,Longitude\nARCH,Arches National Park,UT,1,38.68,-109.57\n",
        )
    p = tmp_path / "parks.zip"
    p.write_bytes(data.getvalue())
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    monkeypatch.setattr(nps, "ARCHIVE_SHA256", sha)
    rights = tmp_path / "rights.txt"
    rights.write_text("Synthetic rights evidence")
    lic = {"path": str(rights), "sha256": hashlib.sha256(rights.read_bytes()).hexdigest()}
    m = {
        "schema_version": nps.SCHEMA,
        "release": "kaggle-nps-v3+nps-" + datetime.now(UTC).date().isoformat(),
        "retrieved_at": e["retrieved_at"],
        "source_url": nps.SOURCE_URL,
        "sha256": sha,
        "filters": {"exclude_active_dated_closures": True},
        "attribution": nps.ATTRIBUTION,
        "licenses": {"CC0-1.0": lic, "LicenseRef-US-Government-Work": lic},
        "official_inputs": {"arch": e},
        "selections": {"arch": {"visitor_center_id": 71}},
    }
    rows, report = prepare(p, m)
    assert rows == [] and report["rejects"] == {"active_or_uncertain_dated_closure": 1}
    m["filters"]["exclude_active_dated_closures"] = False
    assert prepare(p, m)[1]["accepted"] == 1
