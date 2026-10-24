"""One catalog snapshot and one measured candidate pool per route in a study."""

import asyncio
import json
import os
from copy import deepcopy

from app.agent.persona import normalize_weights
from app.catalog.repository import routing_snapshot
from app.research import store
from app.research.collect import collect_inputs
from app.routing.evaluation.runner import atomic, json_text
from app.routing.profiles import crossmatch
from app.routing.run_metrics import fingerprint

_locks = {}


def intent(path):
    try:
        with path.open("x") as handle:
            os.chmod(path, 0o600)
            handle.write(store.now())
    except FileExistsError:
        raise ValueError(
            "Interrupted preparation requires inspection; live calls were not repeated"
        ) from None


def reweight(prepared, case, *, reused):
    """Only persona arithmetic changes; identity, route, traits and roads stay fixed."""
    envelope = deepcopy(prepared["envelope"])
    envelope["input_snapshot"] = case["inputs"]
    weights = normalize_weights(case["inputs"]["persona_weights"])
    explanation = envelope.get("explanation", {})
    explanation["weights"] = weights
    for field in ("candidates", "road_checks"):
        for candidate in explanation.get(field, []):
            candidate.update(crossmatch(weights, candidate["attribute_ratings"]).model_dump())
    envelope["preparation"] = {
        "source_case_id": prepared["case_id"],
        "reused": reused,
        "hash": prepared["hash"],
    }
    if reused:
        envelope["runtime_seconds"] = 0.0
        envelope["provider_measurements"] = {}
        envelope["attempts"] = []
    return envelope


async def inputs(case, study):
    root = store.directory() / study["id"]
    catalog_path = root / "catalog-snapshot.json"
    async with _locks.setdefault(str(catalog_path), asyncio.Lock()):
        if not catalog_path.exists():
            intent(root / "catalog-snapshot.started")
            catalog = await asyncio.to_thread(routing_snapshot)
            atomic(catalog_path, json_text(catalog))
        catalog = json.loads(catalog_path.read_text())
    route_key = fingerprint(
        {
            key: case["inputs"][key]
            for key in (
                "start_id",
                "destination_id",
                "corridor",
            )
        }
    )
    route_path = root / f"route-{route_key}.json"
    async with _locks.setdefault(str(route_path), asyncio.Lock()):
        reused = route_path.exists()
        if not reused:
            intent(root / f"route-{route_key}.started")
            envelope = await collect_inputs(case, catalog)
            prepared = {"case_id": case["id"], "envelope": envelope}
            prepared["hash"] = fingerprint(prepared)
            atomic(route_path, json_text(prepared))
        prepared = json.loads(route_path.read_text())
        if prepared["hash"] != fingerprint({k: v for k, v in prepared.items() if k != "hash"}):
            raise ValueError("Prepared route hash mismatch")
        return reweight(prepared, case, reused=reused)
