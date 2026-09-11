"""Registry / plug-and-play selection tests."""

import pytest

from app.routing.base import PlanningError, RoutePlanner
from app.routing.registry import available_planners, get_planner


def test_known_planners_resolve():
    """Both shipped algorithms resolve to a RoutePlanner instance."""
    for name in ("greedy", "ortools"):
        planner = get_planner(name)
        assert isinstance(planner, RoutePlanner)
        assert planner.name == name


def test_available_planners_lists_both():
    names = available_planners()
    assert "greedy" in names
    assert "ortools" in names


def test_unknown_planner_raises_400():
    with pytest.raises(PlanningError) as exc:
        get_planner("does-not-exist")
    assert exc.value.status_code == 400
