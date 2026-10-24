"""Describe a complete real-data research export without replacing missing outcomes."""

import collections
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

source = Path(sys.argv[1])
out = source.parent
study = json.loads(source.read_text())
rows = study["protocol"]["cases"]
assert study["state"] == "complete" and all(r["state"] == "finished" for r in rows)
assert len(rows) == study["counts"]["total"] == 5064
assert len({r["id"] for r in rows}) == len(rows)


def check_scope(value):
    if isinstance(value, dict):
        for key, item in value.items():
            assert key not in {
                "budget",
                "hotel_costs",
                "itinerary",
                "actual_days",
                "extra_meters",
                "extra_seconds",
            }, key
            check_scope(item)
    elif isinstance(value, list):
        for item in value:
            check_scope(item)


check_scope(rows)
assert {r["track"] for r in rows} == {"capture", "solver"}


def values(rs, k):
    return [
        r[k]
        for r in rs
        if isinstance(r.get(k), (int, float))
        and not isinstance(r[k], bool)
        and math.isfinite(r[k])
    ]


def mean(rs, k):
    v = values(rs, k)
    return statistics.mean(v) if v else None


def summary(rs):
    return {
        "attempts": len(rs),
        "completed": sum(bool(r.get("completed")) for r in rs),
        "selection_assessed": sum(bool(r.get("selection_assessed")) for r in rs),
        "statuses": dict(
            collections.Counter(r.get("solver_status", "NOT_RUN") for r in rs)
        ),
        "errors": dict(
            collections.Counter(
                (r.get("error") or {}).get("code") for r in rs if r.get("error")
            )
        ),
        "means": {
            k: mean(rs, k)
            for k in (
                "runtime_seconds",
                "solver_seconds",
                "candidate_utility_mean",
                "selected_utility_mean",
                "utility_gain",
                "utility_mean",
                "eligible_candidate_count",
                "spacing_deviation_seconds",
                "estimated_detour_seconds",
                "fulfillment",
            )
        },
        "assessed_counts": {
            k: len(values(rs, k))
            for k in ("utility_gain", "utility_mean", "fulfillment")
        },
    }


def cellkey(r):
    return (r["trip"], r["persona"], r["stops_per_day"])


keys = [
    (t, p, d)
    for t in study["design"]["trips"]
    for p in study["design"]["personas"]
    for d in study["design"]["stops_per_day"]
]
variants = [v["id"] for v in study["variants"]]
solver = [r for r in rows if r["track"] == "solver"]
live = [r for r in rows if r["track"] == "capture"]
assert len(solver) == 5040 and len(live) == 24
captures = [r for r in live if r.get("capture")]
assert len(captures) == 24
assert study["protocol"]["schema_version"] == 4
assert all(v["config"]["candidate_limit"] is None for v in study["variants"])
by_trip = {}
for row in captures:
    capture = row["capture"]
    config = capture["inputs"]["corridor"]
    canonical = []
    for place in capture["candidates"]:
        p = place["route_distance_fraction"]
        edge = math.exp(-0.5 * (0.5 / config["sigma"]) ** 2)
        bell = math.exp(-0.5 * ((p - 0.5) / config["sigma"]) ** 2)
        radius = config["endpoint_miles"] + (
            config["midpoint_miles"] - config["endpoint_miles"]
        ) * (bell - edge) / (1 - edge)
        assert math.isclose(place["corridor_radius_miles"], radius, abs_tol=1e-9)
        assert place["distance_meters"] <= radius * 1609.344
        canonical.append(
            {
                key: place[key]
                for key in (
                    "provider_id",
                    "coordinates",
                    "attribute_ratings",
                    "route_progress_seconds",
                    "detour_seconds",
                    "source_generation",
                )
            }
        )
    frozen = json.dumps(canonical, sort_keys=True)
    assert by_trip.setdefault(row["trip"], frozen) == frozen
assert len(by_trip) == 4
preparations = [
    r for r in captures if not r["capture_evidence"]["preparation"]["reused"]
]
assert len(preparations) == 4
assert len({r["capture_evidence"]["preparation"]["hash"] for r in captures}) == 4
for row in captures:
    capture = row["capture"]
    encoded = json.dumps(
        {k: v for k, v in capture.items() if k != "hash"},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert hashlib.sha256(encoded).hexdigest() == capture["hash"]
for r in solver:
    if r.get("evidence") == "real_frozen_selection":
        capture = next(
            c["capture"] for c in captures if c["id"] == r["capture_case_id"]
        )
        assert cellkey(r) == cellkey(
            next(c for c in captures if c["id"] == r["capture_case_id"])
        )
        assert r["dataset_hash"] == capture["hash"]
        if r.get("selection_assessed"):
            input_map = {p["provider_id"]: p["utility"] for p in capture["candidates"]}
            selected = r["selected_ids"]
            assert (
                len(selected)
                == len(set(selected))
                == min(r["requested"], capture["eligible_count"])
            )
            assert set(selected) <= input_map.keys()
            actual_mean = statistics.mean(input_map[pid] for pid in selected)
            assert math.isclose(actual_mean, r["selected_utility_mean"], abs_tol=1e-12)
            config = next(
                v["config"] for v in study["variants"] if v["id"] == r["variant"]
            )
            assert (
                actual_mean + 1e-9
                >= r["best_available_utility_mean"] - config["quality_loss"]
            )
for r in rows:
    if r.get("selection_assessed"):
        assert math.isclose(
            r["utility_gain"],
            r["selected_utility_mean"] - r["candidate_utility_mean"],
            abs_tol=1e-12,
        )

groups = {}
cells = []
for key in keys:
    by_variant = {
        v: [r for r in solver if cellkey(r) == key and r["variant"] == v]
        for v in variants
    }
    groups[key] = by_variant
    pipeline = [r for r in live if cellkey(r) == key]
    c = next((r["capture"] for r in captures if cellkey(r) == key), None)
    cells.append(
        {
            "scenario": ":".join(map(str, key)),
            "capture_hash": c["hash"] if c else None,
            "eligible_capture_count": c["eligible_count"] if c else None,
            "requested_stops": pipeline[0]["inputs"]["num_stops"],
            "baseline": summary(by_variant["baseline"]),
            "preparation": summary(pipeline),
            "variants": {
                v: summary(rs)
                | {
                    "distinct_selections": len(
                        {
                            tuple(r.get("selected_ids", []))
                            for r in rs
                            if r.get("selection_assessed")
                        }
                    )
                }
                for v, rs in by_variant.items()
            },
            "baseline_distinct_selections": len(
                {
                    tuple(r.get("selected_ids", []))
                    for r in by_variant["baseline"]
                    if r.get("selection_assessed")
                }
            ),
        }
    )
variant_summary = {}
for v in variants:
    subset = [r for r in solver if r["variant"] == v]
    assessed = [r for r in subset if r.get("selection_assessed")]
    paired_cells = [
        c for c in cells if c["variants"][v]["means"]["utility_gain"] is not None
    ]
    variant_summary[v] = summary(subset) | {
        "scenario_count_assessed": len(paired_cells),
        "scenario_equal_mean_gain": statistics.mean(
            c["variants"][v]["means"]["utility_gain"] for c in paired_cells
        )
        if paired_cells
        else None,
    }
paired_variants = {}
for v in variants[1:]:
    pairs = []
    for key in keys:
        baseline = {r["repeat"]: r for r in groups[key]["baseline"]}
        for r in groups[key][v]:
            b = baseline[r["repeat"]]
            if b.get("selection_assessed") and r.get("selection_assessed"):
                pairs.append(
                    {
                        "scenario": key,
                        "seed": r["repeat"] - 1,
                        **{
                            k: r[k] - b[k]
                            for k in (
                                "selected_utility_mean",
                                "spacing_deviation_seconds",
                                "estimated_detour_seconds",
                            )
                            if r.get(k) is not None and b.get(k) is not None
                        },
                    }
                )
    paired_variants[v] = {
        "matched_seed_pairs": len(pairs),
        "matched_scenarios": len({p["scenario"] for p in pairs}),
        "mean_differences_from_baseline": {
            k: mean(pairs, k)
            for k in (
                "selected_utility_mean",
                "spacing_deviation_seconds",
                "estimated_detour_seconds",
            )
        },
    }
result = {
    "study_id": study["id"],
    "state": study["state"],
    "identity": study["identity"],
    "design": study["design"],
    "planned_counts": study["counts"],
    "solver": summary(solver),
    "preparation": summary(live),
    "unique_route_preparations": summary(preparations),
    "reused_scenario_preparations": len(captures) - len(preparations),
    "corridor": study["protocol"]["dataset"]["corridor"],
    "capture_scenarios": len(captures),
    "variants": variant_summary,
    "matched_variant_comparisons": paired_variants,
    "scenarios": cells,
    "interpretation": "Model-estimated preference match; seeds repeat each fixed pool, not independent traveler observations. Failed and missing outcomes retained. No budget measurements.",
}
baseline_cells = [c["baseline"]["means"]["utility_gain"] for c in cells]
result.update(
    baseline_positive_scenarios=sum(
        v is not None and v > 1e-10 for v in baseline_cells
    ),
    baseline_negative_scenarios=sum(
        v is not None and v < -1e-10 for v in baseline_cells
    ),
    baseline_zero_scenarios=sum(
        v is not None and abs(v) <= 1e-10 for v in baseline_cells
    ),
    shortage_scenarios=sum(
        c["requested_stops"] > c["eligible_capture_count"] for c in cells
    ),
    requested_per_seed=sum(c["requested_stops"] for c in cells),
    selected_per_seed=sum(
        min(c["requested_stops"], c["eligible_capture_count"]) for c in cells
    ),
)
input_places = {p["provider_id"] for c in captures for p in c["capture"]["candidates"]}
result.update(
    input_export_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    distinct_input_places=len(input_places),
    input_place_ids=sorted(input_places),
    catalog_generations=sorted(
        {p["source_generation"] for c in captures for p in c["capture"]["candidates"]}
    ),
    rating_providers=sorted(
        {
            p["provenance"]["ratings_provider"]
            for c in captures
            for p in c["capture"]["candidates"]
        }
    ),
    capture_pool_sizes=[len(c["capture"]["candidates"]) for c in captures],
    recorded_start=min(r["attempt_started_at"] for r in rows),
    recorded_end=max(r["recorded_at"] for r in rows),
)
(out / "summary.json").write_text(json.dumps(result, indent=2, allow_nan=False))

names = {
    "short-1d": "LA–San Diego",
    "medium-2d": "SF–Boise",
    "long-3d": "SF–Denver",
    "coast-5d": "SF–New York",
}
labels = [f"{names[t]} · {p[0].upper()} · {d}/day" for t, p, d in keys]
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.facecolor": "white",
    }
)
fig, ax = plt.subplots(figsize=(7.2, 8.3))
for i, c in enumerate(cells):
    paired = [r for r in groups[keys[i]]["baseline"] if r.get("selection_assessed")]
    pool = mean(paired, "candidate_utility_mean")
    selected = mean(paired, "selected_utility_mean")
    if paired:
        ax.plot([pool, selected], [i, i], color="#aab5ba", lw=2, zorder=1)
        ax.scatter(
            pool,
            i,
            facecolors="none",
            edgecolors="#65737d",
            linewidths=1.5,
            s=65,
            label="Eligible pool" if i == 0 else None,
            zorder=3,
        )
        ax.scatter(
            selected,
            i,
            color="#087e8b",
            s=40,
            label="Selected" if i == 0 else None,
            zorder=3,
        )
        ax.annotate(
            f" n={len(paired)}/30",
            (max(pool, selected), i),
            xytext=(5, -3),
            textcoords="offset points",
            fontsize=7.5,
        )
    else:
        ax.text(
            0.01, i, "No assessed selection", va="center", color="#777777", fontsize=8
        )
ax.set_yticks(range(24), labels)
ax.invert_yaxis()
ax.set_xlim(0, 1.12)
ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
ax.grid(axis="x", alpha=0.2)
ax.set_xlabel("Mean preference-match utility (0–1)")
ax.legend(loc="upper right", fontsize=8)
ax.set_title(
    "Baseline: candidate pool versus selected attractions", fontsize=12, pad=14
)
fig.text(
    0.5,
    0.025,
    "Assessed seeds on each fixed pool; N = nature, E = entertainment.\nMissing outcomes are not zero. Repeated seeds are not independent place samples.",
    ha="center",
    fontsize=8,
)
fig.tight_layout(rect=(0, 0.06, 1, 1))
for ext in ("png", "svg"):
    fig.savefig(out / f"candidate-selected-utility.{ext}", dpi=240)
plt.close(fig)

matrix = (
    np.array(
        [
            [
                c["variants"][v]["means"]["utility_gain"]
                if c["variants"][v]["means"]["utility_gain"] is not None
                else np.nan
                for v in variants
            ]
            for c in cells
        ]
    )
    * 100
)
finite = matrix[np.isfinite(matrix)]
limit = max(1, float(np.max(np.abs(finite)))) if len(finite) else 1
fig, ax = plt.subplots(figsize=(7.4, 9))
cmap = plt.get_cmap("BrBG").copy()
cmap.set_bad("#eeeeee")
im = ax.imshow(
    np.ma.masked_invalid(matrix), cmap=cmap, vmin=-limit, vmax=limit, aspect="auto"
)
ax.set_yticks(range(len(keys)), labels)
ax.set_xticks(
    range(len(variants)),
    [
        "Baseline",
        "Loss 0",
        "Loss 0.05",
        "Loss 0.20",
        "Detour 0",
        "Detour 0.25",
        "Detour 4",
    ],
    rotation=35,
    ha="right",
)
for i in range(len(keys)):
    for j in range(len(variants)):
        val = matrix[i, j]
        ax.text(
            j,
            i,
            f"{val:+.1f}" if math.isfinite(val) else "—",
            ha="center",
            va="center",
            fontsize=7,
            color="white"
            if math.isfinite(val) and abs(val) > 0.65 * limit
            else "#202020",
        )
ax.set_title("Selected mean minus eligible-pool mean", pad=15, fontsize=14)
fig.colorbar(im, ax=ax, label="Percentage points of the 0–1 utility scale", shrink=0.75)
fig.text(
    0.5,
    0.015,
    "Each cell averages assessed seeds on one fixed real pool.\nA dash means no valid selections (see outcome counts); 0.0 means measured zero change.",
    ha="center",
    fontsize=8,
)
fig.tight_layout(rect=(0, 0.04, 1, 1))
for ext in ("png", "svg"):
    fig.savefig(out / f"utility-gain-heatmap.{ext}", dpi=240)
plt.close(fig)

print(
    json.dumps(
        {
            "study": study["id"],
            "solver": result["solver"],
            "preparation": result["preparation"],
            "capture_scenarios": len(captures),
        },
        indent=2,
    )
)
