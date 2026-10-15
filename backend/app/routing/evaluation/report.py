"""Static SVG plots from calculated rows only; synthetic checks are excluded."""

import csv
import io
import json
import textwrap
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from statistics import mean, quantiles

from app.routing.evaluation.comparisons import bound_comparisons, paired_results, successful
from app.routing.evaluation.runner import atomic, json_text

PLOTS = {
    "utility_mean": ("Attraction utility mean", "utility", "mean"),
    "utility_min": ("Attraction utility minimum", "utility", "min"),
    "utility_median": ("Attraction utility median", "utility", "median"),
    "actual_max_gap_seconds": (
        "Longest driving stretch (seconds)",
        "driving_gaps",
        "maximum_stretch_seconds",
    ),
    "added_driving_seconds": ("Added driving (seconds)", "driving", "extra_duration_seconds"),
    "added_distance_meters": ("Added driving (meters)", "driving", "extra_distance_meters"),
    "visit_seconds": ("Attraction visits (seconds)", "schedule", "visit_seconds"),
    "overnight_seconds": ("Overnight downtime (seconds)", "schedule", "overnight_downtime_seconds"),
    "quoted_hotel_usd": ("Quoted hotel cost (USD)", "hotel_costs", "quoted_total_usd"),
}
COLORS = ["#225ea8", "#41ab5d", "#e6550d", "#756bb1", "#636363", "#d94874", "#b8860b", "#111111"]


def fields(row):
    metrics = row.get("metrics") or {}
    trip = metrics.get("trip_evaluation") or {}
    utility = (trip.get("utility") or {}).get(
        "delivered" if row["track"] == "offline-pipeline" else "selected"
    ) or {}
    return {
        key: utility.get(field) if section == "utility" else trip.get(section, {}).get(field)
        for key, (_, section, field) in PLOTS.items()
    } | {
        "utility_max": utility.get("max"),
        "requested_normalized_delivered_utility": trip.get("utility", {}).get(
            "requested_normalized_delivered"
        ),
        "baseline_max_gap_seconds": metrics.get("selection_measurements", {}).get(
            "maximum_baseline_gap_seconds"
        ),
        "budget_utilization": trip.get("hotel_costs", {}).get("budget_utilization"),
        "over_target_fraction": trip.get("hotel_costs", {}).get("over_target_fraction"),
        "hotel_excess_usd": trip.get("hotel_costs", {}).get("above_target_total_usd"),
    }


def canvas(title, caption, low, high, width=980):
    if high == low:
        high = low + 1
    low, high = min(0, low), max(0, high)
    if high == low:
        high += 1

    def y(value):
        return 320 - (value - low) / (high - low) * 245

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="460" viewBox="0 0 {width} 460">',
        f'<rect width="{width}" height="460" fill="white"/>',
        '<g font-family="Arial,sans-serif" font-size="12" fill="#222">',
        f'<text x="35" y="25" font-size="17">{escape(title)}</text>',
        *(
            f'<text x="35" y="{45 + i * 15}">{escape(line)}</text>'
            for i, line in enumerate(textwrap.wrap(caption, width=max(80, int((width - 70) / 6.5))))
        ),
    ]
    for i in range(6):
        value = low + (high - low) * i / 5
        svg += [
            f'<line x1="80" x2="{width - 30}" y1="{y(value)}" y2="{y(value)}" stroke="#ddd"/>',
            f'<text x="70" y="{y(value) + 4}" text-anchor="end">{value:.3g}</text>',
        ]
    return svg, y


def box_plot(title, groups, caption):
    all_values = [v for values in groups.values() for v in values]
    if not all_values:
        return None
    canvas_width = max(980, len(groups) * 280)
    svg, y = canvas(title, caption, min(all_values), max(all_values), canvas_width)
    width = (canvas_width - 110) / max(1, len(groups))
    for i, (label, values) in enumerate(groups.items()):
        x = 80 + width * (i + 0.5)
        if len(values) >= 4:
            q1, q2, q3 = quantiles(values, n=4, method="inclusive")
            iqr = q3 - q1
            lo = min(v for v in values if v >= q1 - 1.5 * iqr)
            hi = max(v for v in values if v <= q3 + 1.5 * iqr)
            svg += [
                f'<line x1="{x}" x2="{x}" y1="{y(lo)}" y2="{y(hi)}" stroke="#225ea8"/>',
                f'<rect x="{x - 20}" y="{y(q3)}" width="40" height="{y(q1) - y(q3)}" fill="#d9e8f5" stroke="#225ea8"/>',
                f'<line x1="{x - 20}" x2="{x + 20}" y1="{y(q2)}" y2="{y(q2)}" stroke="#225ea8"/>',
            ]
        # All actual observations, with deterministic jitter; no simulated points.
        for j, v in enumerate(values):
            svg.append(f'<circle cx="{x + ((j % 5) - 2) * 3}" cy="{y(v)}" r="3" fill="#225ea8"/>')
        svg.append(
            f'<text x="{x}" y="345" text-anchor="middle">{escape(label)} (n={len(values)})</text>'
        )
    svg += [
        '<text x="35" y="420">Whiskers: observed values within 1.5 × IQR; n &lt; 4 uses points only. Repeats measure solver variation.</text>',
        "</g></svg>",
    ]
    return "\n".join(svg)


def columns(title, groups, caption):
    labels = list(dict.fromkeys(k for values in groups.values() for k in values))
    values = [v for group in groups.values() for v in group.values() if v is not None]
    if not values:
        return None
    canvas_width = max(980, len(groups) * 280)
    svg, y = canvas(title, caption, 0, max(values) or 1, canvas_width)
    group_width = (canvas_width - 110) / max(1, len(groups))
    bar_width = min(30, group_width / (len(labels) + 1))
    for i, (method, group) in enumerate(groups.items()):
        left = 80 + group_width * i
        for j, label in enumerate(labels):
            value = group.get(label)
            if value is None:
                continue
            x = left + bar_width * j + 10
            svg += [
                f'<rect x="{x}" y="{y(value)}" width="{bar_width - 2}" height="{y(0) - y(value)}" fill="{COLORS[j % len(COLORS)]}"/>',
                f'<text x="{x + bar_width / 2}" y="{y(value) - 5}" text-anchor="middle">{value:.3g}</text>',
            ]
        svg.append(
            f'<text x="{left + group_width / 2}" y="345" text-anchor="middle">{escape(method)}</text>'
        )
    for i, label in enumerate(labels):
        x = 35 + (i % 4) * 230
        yy = 375 + (i // 4) * 20
        svg += [
            f'<rect x="{x}" y="{yy - 10}" width="10" height="10" fill="{COLORS[i % len(COLORS)]}"/>',
            f'<text x="{x + 15}" y="{yy}">{escape(label)}</text>',
        ]
    return "\n".join([*svg, "</g></svg>"])


def with_provenance(svg, metadata):
    details = escape(json.dumps(metadata, sort_keys=True))
    visible = f"Revision {metadata['revision']} | metrics {metadata['metric_version']}"
    sources = (
        "Catalog "
        + ", ".join(metadata.get("catalog_generations", []))
        + " | "
        + metadata.get("evidence_layer", "")
    )
    return svg.replace(
        "</svg>",
        f'<metadata>{details}</metadata><g font-family="Arial,sans-serif" font-size="10"><text x="35" y="438">{escape(visible)}</text><text x="35" y="452">{escape(sources)}</text></g></svg>',
    )


def response_plot(title, groups, caption):
    values = [
        v for points in groups.values() for observations in points.values() for v in observations
    ]
    xs = sorted({x for points in groups.values() for x in points})
    if not values or not xs:
        return None
    svg, y = canvas(title, caption, min(values), max(values))

    def x(value):
        return 80 + (value - xs[0]) / (xs[-1] - xs[0]) * 870 if xs[-1] != xs[0] else 515

    for index, (label, points) in enumerate(sorted(groups.items())):
        path = " ".join(
            f"{'M' if i == 0 else 'L'} {x(value)} {y(mean(points[value]))}"
            for i, value in enumerate(sorted(points))
        )
        svg.append(f'<path d="{path}" fill="none" stroke="{COLORS[index % len(COLORS)]}"/>')
        for value, observations in sorted(points.items()):
            svg.append(
                f'<circle cx="{x(value)}" cy="{y(mean(observations))}" r="3" fill="{COLORS[index % len(COLORS)]}"/>'
            )
            svg.append(
                f'<text x="{x(value)}" y="{y(mean(observations)) - 8}">{mean(observations):.3g} (n={len(observations)})</text>'
            )
        svg.append(
            f'<text x="{35 + index * 200}" y="380" fill="{COLORS[index % len(COLORS)]}">{escape(label)}</text>'
        )
    for value in xs:
        svg.append(f'<text x="{x(value)}" y="345" text-anchor="middle">{value:g}</text>')
    return "\n".join([*svg, "</g></svg>"])


def render(directory):
    root = Path(directory)
    manifest = json.loads((root / "manifest.json").read_text())
    rows = [json.loads(line) for line in (root / "runs.jsonl").read_text().splitlines() if line]
    counts = Counter(row["status"] for row in rows)
    missing = manifest["expected_runs"] - len(rows)
    lines = [
        "# Route evaluation",
        "",
        f"Expected {manifest['expected_runs']} rows; recorded {len(rows)}; missing {missing}.",
        f"Terminal states: {dict(counts)}.",
        "",
        f"Revision: `{manifest['identity']['revision']}`; metrics: `{manifest['identity']['metric_version']}`.",
        "Selection objectives are comparable only for identical model keys. Compare methods using the physical metrics below.",
        "Hotel budget is a nightly per-room target; no total-trip budget is enforced.",
        "Synthetic checks stay in the labeled execution ledger and are excluded from primary figures. No live calls or database writes are performed.",
        "",
        "## Execution ledger",
        "",
        "",
        "| Scenario | Method | Evidence | State | Raw solver status | Fulfillment | Failure stage |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.insert(
        6,
        "Assessment totals: "
        + str(
            {
                name: dict(
                    Counter(row.get("assessments", {}).get(name, "unassessed") for row in rows)
                )
                for name in (
                    "input_support",
                    "request_fulfillment",
                    "scenario_target",
                    "pipeline_completion",
                    "nightly_room_target",
                )
            }
        ),
    )
    csv_rows = []
    for row in rows:
        assessment = row.get("assessments", {})
        lines.append(
            f"| {row['scenario_id']} | {row['method']} | {row.get('evidence_type') or 'capture missing'} | {row['status']} | {row['solver_status']} | {assessment.get('request_fulfillment', 'unassessed')} | {row['stage']} |"
        )
        csv_rows.append(
            {
                key: row.get(key)
                for key in (
                    "run_id",
                    "scenario_id",
                    "trip_type",
                    "persona",
                    "stops_per_day",
                    "method",
                    "track",
                    "status",
                    "solver_status",
                    "evidence_type",
                    "fixture_hash",
                    "model_key",
                    "parameter",
                    "parameter_value",
                    "paired_key",
                )
            }
            | {
                "eligible_for_primary_distribution": successful(row),
                "cpu_seconds": (row.get("resources") or {}).get("cpu_seconds"),
                "peak_rss_bytes": (row.get("resources") or {}).get("peak_rss_bytes"),
                "worker_elapsed_ms": row.get("worker_elapsed_ms"),
            }
            | fields(row)
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(csv_rows[0]) if csv_rows else ["run_id"])
    writer.writeheader()
    writer.writerows(csv_rows)
    atomic(root / "summary.csv", buf.getvalue())
    failures = Counter(
        (row["stage"], str(row.get("error", "")).replace("|", "/").replace("\n", " "))
        for row in rows
        if row["status"] != "completed"
    )
    lines += ["", "## Failure and data gates", ""]
    lines += [
        f"- {stage}: {count} row(s); {error}" for (stage, error), count in failures.items()
    ] or ["No recorded failures."]
    # Every facet keeps trip type, persona, density, evidence layer and track fixed.
    facets = defaultdict(list)
    for row in rows:
        if row.get("evidence_type") and row["evidence_type"] != "synthetic_unit_only":
            facets[
                (
                    row["trip_type"],
                    row["persona"],
                    row["stops_per_day"],
                    row["track"],
                    row["evidence_type"],
                )
            ].append(row)
    chart_count = 0
    for index, (facet, items) in enumerate(facets.items()):
        methods = sorted(
            set(
                row["method"]
                + (
                    f" {row.get('parameter')}={row.get('parameter_value')}"
                    if row.get("parameter")
                    else ""
                )
                for row in items
            )
        )

        def label(row):
            return row["method"] + (
                f" {row.get('parameter')}={row.get('parameter_value')}"
                if row.get("parameter")
                else ""
            )

        caption = f"{' / '.join(map(str, facet))}; recorded n={len(items)}; metrics {manifest['identity']['metric_version']}"
        lines += [
            "",
            f"## {' / '.join(map(str, facet))}",
            "",
            caption,
            "Sources: "
            + ", ".join(
                sorted(
                    {
                        f"{row.get('catalog_generation')} / {row.get('fixture_hash')}"
                        for row in items
                    }
                )
            ),
        ]
        provenance = {
            "revision": manifest["identity"]["revision"],
            "metric_version": manifest["identity"]["metric_version"],
            "evidence_layer": facet[-1],
            "track": facet[-2],
            "catalog_generations": sorted({str(row.get("catalog_generation")) for row in items}),
            "source_fixture_hashes": sorted({str(row.get("fixture_hash")) for row in items}),
            "attempted": len(items),
            "successful_fulfilled": sum(successful(row) for row in items),
        }
        caption += f"; successful fulfilled n={provenance['successful_fulfilled']} / {len(items)} attempted"
        for key, (title, _, _) in PLOTS.items():
            groups = {
                method: [
                    fields(row)[key]
                    for row in items
                    if label(row) == method and fields(row)[key] is not None and successful(row)
                ]
                for method in methods
            }
            svg = box_plot(title, groups, caption)
            if svg:
                path = f"figures/f{index}-{key}.svg"
                atomic(root / path, with_provenance(svg, provenance))
                chart_count += 1
                lines.append(f"![{title}]({path})")
        statuses = {
            method: dict(Counter(row["solver_status"] for row in items if label(row) == method))
            for method in methods
        }
        rate_groups = {}
        for method in methods:
            group = [row for row in items if label(row) == method]
            rate_groups[method] = {}
            for name in ("request_fulfillment", "scenario_target", "pipeline_completion"):
                assessed = [
                    row.get("assessments", {}).get(name)
                    for row in group
                    if row.get("assessments", {}).get(name) in {"pass", "fail"}
                ]
                rate_groups[method][f"{name} %"] = (
                    100 * assessed.count("pass") / len(assessed) if assessed else None
                )
                lines.append(
                    f"- {method} / {name}: {len(assessed)} assessed of {len(group)} expected; {len(group) - len(assessed)} unassessed/unsupported."
                )
        budget_groups = {
            method: {
                "mean excess USD": mean(values)
                if (
                    values := [
                        fields(row)["hotel_excess_usd"]
                        for row in items
                        if label(row) == method
                        and fields(row)["hotel_excess_usd"] is not None
                        and successful(row)
                    ]
                )
                else None
            }
            for method in methods
        }
        ratio_groups = {
            method: {
                field + " %": mean(values) * 100
                if (
                    values := [
                        fields(row)[field]
                        for row in items
                        if label(row) == method
                        and fields(row)[field] is not None
                        and successful(row)
                    ]
                )
                else None
                for field in ("budget_utilization", "over_target_fraction")
            }
            for method in methods
        }
        for name, title, groups in (
            ("status", "Raw solver status counts", statuses),
            ("rates", "Assessed pass rates (%)", rate_groups),
            ("budget", "Nightly quoted excess (USD)", budget_groups),
            (
                "utilization",
                "Nightly target utilization and over-target fraction (%)",
                ratio_groups,
            ),
        ):
            svg = columns(title, groups, caption)
            if svg:
                path = f"figures/f{index}-{name}.svg"
                atomic(root / path, with_provenance(svg, provenance))
                chart_count += 1
                lines.append(f"![{title}]({path})")
    if not chart_count:
        lines += [
            "",
            "No primary measured figures are available. Real-catalog captures and eligible coverage remain required; synthetic unit checks do not substitute for them.",
        ]
    paired = paired_results(rows, fields)
    bounds = bound_comparisons(rows)
    atomic(root / "paired-comparisons.json", json_text(paired))
    atomic(root / "bound-comparisons.json", json_text(bounds))
    lines += [
        "",
        "## Paired parameter and bound comparisons",
        "",
        f"{len(paired)} successful same-source parameter pairs; {len(bounds)} same-model incumbent/bound observations.",
        "See paired-comparisons.json for physical metric deltas and selected-ID changes. Raw objectives are never ranked across changed models.",
    ]
    for index, (facet, items) in enumerate(facets.items()):
        parameters = sorted({row.get("parameter") for row in items if row.get("parameter")})
        for parameter in parameters:
            eligible = [
                row for row in items if successful(row) and row.get("parameter") == parameter
            ]
            provenance = {
                "revision": manifest["identity"]["revision"],
                "metric_version": manifest["identity"]["metric_version"],
                "evidence_layer": facet[-1],
                "catalog_generations": sorted(
                    {str(row.get("catalog_generation")) for row in items}
                ),
                "source_fixture_hashes": sorted({str(row.get("fixture_hash")) for row in items}),
                "parameter": parameter,
            }
            for key, (title, _, _) in PLOTS.items():
                groups = {}
                for row in eligible:
                    value = fields(row)[key]
                    if value is not None:
                        groups.setdefault(row["method"], {}).setdefault(
                            row["parameter_value"], []
                        ).append(value)
                svg = response_plot(
                    title, groups, f"{parameter}; successful fulfilled outputs only"
                )
                if svg:
                    path = f"figures/f{index}-{parameter}-{key}-response.svg"
                    atomic(root / path, with_provenance(svg, provenance))
                    chart_count += 1
                    lines.append(f"![{parameter}: {title}]({path})")
    atomic(root / "plot-data.json", json_text(csv_rows))
    atomic(root / "report.md", "\n".join(lines) + "\n")
    return {
        "expected": manifest["expected_runs"],
        "recorded": len(rows),
        "states": dict(counts),
        "primary_figures": chart_count,
        "missing": missing,
    }
