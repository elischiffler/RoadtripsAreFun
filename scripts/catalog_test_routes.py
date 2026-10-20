#!/usr/bin/env python3
"""Acquire immutable public OSRM route receipts for the current Studio corridors.

Only the fixed public routing service is contacted, at most once per second.
Responses are streamed under a two-MiB ceiling, redirects and ambient credentials
are disabled, and successful receipts are checked by the existing proof reader.
These city-to-city driving geometries are catalog diagnostics, not live trips.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.routing.lab_presets import BENCHMARKS, ENDPOINTS, PRESETS

from scripts.catalog_incremental_proof import routes as validate_routes

SERVER = "https://router.project-osrm.org"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
# Public city coordinates retained from the earlier source-backed corridor
# captures. Explicit current Studio coordinates take precedence when supplied.
CITY_COORDINATES = {
    "sf": (37.7749, -122.4194),
    "monterey": (36.6002, -121.8947),
    "la": (34.0522, -118.2437),
    "san-diego": (32.7157062, -117.1638284),
    "boise": (43.6166163, -116.200886),
    "chicago": (41.8755616, -87.6244212),
    "ely": (39.2480588, -114.891718),
    "reno": (39.5261788, -119.812658),
    "seattle": (47.6038321, -122.330062),
    "portland": (45.5202471, -122.674194),
    "phoenix": (33.4484367, -112.074141),
}
STUDIO_ROUTES = (
    ("short-day", "la", "san-diego"),
    ("medium-two-day", "sf", "boise"),
    ("long-multi-day", "sf", "chicago"),
    ("dense-corridor", "sf", "la"),
    ("sparse-corridor", "ely", "reno"),
    ("coastal-nature", "sf", "monterey"),
)
OPTIONAL_ROUTES = (
    ("pacific-northwest", "seattle", "portland"),
    ("southwest", "la", "phoenix"),
)
ATTRIBUTION = (
    "Routing: OSRM public routing service; © OpenStreetMap contributors, ODbL. "
    "City endpoint coordinates use explicit current Studio coordinates where available; "
    "other public city coordinates are retained from the earlier source-backed corridor captures. "
    "No live itinerary, provider pricing, opening hours or entrance access is established."
)


def specifications(include_optional=True):
    expected = {("sf", value[1]) for value in PRESETS.values()} | {
        (value[1], value[2]) for value in BENCHMARKS.values()
    }
    if expected != {(start, end) for _, start, end in STUDIO_ROUTES}:
        raise ValueError(
            "current Studio corridors changed; review the fixed route capture set"
        )
    selected = STUDIO_ROUTES + (OPTIONAL_ROUTES if include_optional else ())
    result = []
    for key, start, end in selected:
        points = [
            tuple(ENDPOINTS.get(name, {}).get("coordinates", CITY_COORDINATES[name]))
            for name in (start, end)
        ]
        coordinates = ";".join(f"{lon},{lat}" for lat, lon in points)
        url = (
            SERVER
            + "/route/v1/driving/"
            + coordinates
            + "?"
            + urlencode(
                {
                    "overview": "full",
                    "geometries": "geojson",
                    "steps": "false",
                    "alternatives": "false",
                }
            )
        )
        result.append(
            {
                "id": key,
                "role": "Studio benchmark corridor"
                if (key, start, end) in STUDIO_ROUTES
                else "Additional coverage corridor",
                "start_id": start,
                "destination_id": end,
                "endpoint_coordinates_lat_lon": [list(point) for point in points],
                "url": url,
            }
        )
    return result


def response_body(response, expected_url):
    if response.status_code != 200 or response.url != expected_url:
        raise ValueError(
            "OSRM did not return a successful response at the fixed requested URL"
        )
    if (
        response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        != "application/json"
    ):
        raise ValueError("OSRM response is not JSON")
    length = response.headers.get("Content-Length")
    if length is not None and (
        not length.isdigit() or int(length) > MAX_RESPONSE_BYTES
    ):
        raise ValueError("OSRM response exceeds the two-MiB ceiling")
    chunks, size = [], 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise ValueError("OSRM response exceeds the two-MiB ceiling")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body:
        raise ValueError("OSRM returned an empty response")
    return body


def acquire(
    output,
    *,
    include_optional=True,
    request_get=None,
    sleep=time.sleep,
    monotonic=time.monotonic,
    now=None,
):
    """Publish one new receipt directory; never overwrite or resume an old capture."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(
            "route output already exists; choose a new immutable directory"
        )
    specs = specifications(include_optional)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix="." + output.name + ".partial-", dir=output.parent)
    )
    session = None
    if request_get is None:
        session = requests.Session()
        session.trust_env = (
            False  # No .netrc credentials, proxies or ambient authentication.
        )
        session.auth = None
        request_get = session.get
    now = now or (lambda: datetime.now(UTC))
    index = {"routes": [], "receipts": [], "attribution": ATTRIBUTION}
    last_started = None
    try:
        for spec in specs:
            if last_started is not None:
                delay = max(0, 1 - (monotonic() - last_started))
                if delay:
                    sleep(delay)
            last_started = monotonic()
            response = request_get(
                spec["url"],
                stream=True,
                allow_redirects=False,
                timeout=(5, 30),
                headers={
                    "User-Agent": "RoadtripsAreFun-CatalogCoverage/1.0",
                    "Accept": "application/json",
                },
            )
            try:
                body = response_body(response, spec["url"])
            finally:
                response.close()
            checked = now()
            if checked.tzinfo is None:
                raise ValueError(
                    "route acquisition timestamps require an explicit timezone"
                )
            relative = "route-" + spec["id"] + ".json"
            (staging / relative).write_bytes(body)
            index["routes"].append(
                {key: value for key, value in spec.items() if key != "url"}
                | {"response_path": relative}
            )
            index["receipts"].append(
                {
                    "path": relative,
                    "url": spec["url"],
                    "status": 200,
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "retrieved_at": checked.astimezone(UTC).isoformat(),
                }
            )
        index_path = staging / "index.json"
        index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        validate_routes(index_path, staging.resolve())
        if output.exists() or output.is_symlink():
            raise ValueError(
                "route output appeared during capture; existing files were preserved"
            )
        staging.rename(output)
        return output / "index.json"
    finally:
        if session is not None:
            session.close()
        if staging.exists():
            shutil.rmtree(staging)
