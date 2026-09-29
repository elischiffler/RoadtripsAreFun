"""Tests for the offline benchmark harness (deterministic, no network)."""

import pytest

from app.routing.benchmark import (
    DEFAULT_CASES,
    BenchmarkCase,
    format_table,
    run_benchmark,
)


@pytest.mark.asyncio
async def test_run_benchmark_covers_all_algorithms():
    payload = await run_benchmark()
    assert payload["algorithms"] == ["cp_sat"]
    assert len(payload["cases"]) == len(DEFAULT_CASES)
    for case in payload["cases"]:
        names = {r["algorithm"] for r in case["results"]}
        assert names == {"cp_sat"}
        for r in case["results"]:
            # Every result carries the comparable metric fields.
            for key in ("objective_score", "total_cost", "api_calls", "wall_clock_ms"):
                assert key in r


@pytest.mark.asyncio
async def test_run_benchmark_is_deterministic():
    """Cached candidate data => identical scores across runs."""
    a = await run_benchmark()
    b = await run_benchmark()
    scores_a = [r["objective_score"] for c in a["cases"] for r in c["results"]]
    scores_b = [r["objective_score"] for c in b["cases"] for r in c["results"]]
    assert scores_a == scores_b


@pytest.mark.asyncio
async def test_run_benchmark_subset_of_algorithms():
    payload = await run_benchmark(algorithms=["cp_sat"])
    assert payload["algorithms"] == ["cp_sat"]
    for case in payload["cases"]:
        assert {r["algorithm"] for r in case["results"]} == {"cp_sat"}


@pytest.mark.asyncio
async def test_zero_stops_case_has_no_attractions():
    case = BenchmarkCase("z", duration_hours=2, num_stops=0, budget=400)
    payload = await run_benchmark(cases=[case])
    for r in payload["cases"][0]["results"]:
        assert r["num_attractions"] == 0


@pytest.mark.asyncio
async def test_format_table_renders():
    payload = await run_benchmark(algorithms=["cp_sat"])
    table = format_table(payload)
    assert "CASE:" in table
    assert "algorithm" in table
    assert "cp_sat" in table
