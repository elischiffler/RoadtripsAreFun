"""Registry / plug-and-play selection tests."""

import pytest

from app.routing.base import PlanningError, RoutePlanner
from app.routing.registry import available_planners, get_planner


def test_known_planners_resolve():
    planner = get_planner("cp_sat")
    assert isinstance(planner, RoutePlanner)
    assert planner.name == "cp_sat"


def test_available_planners_only_offers_cp_sat():
    assert available_planners() == ["cp_sat"]


@pytest.mark.parametrize("name", ["greedy", "ortools"])
def test_retired_planners_are_rejected(name):
    with pytest.raises(PlanningError) as exc:
        get_planner(name)
    assert exc.value.status_code == 400


def test_unknown_planner_raises_400():
    with pytest.raises(PlanningError) as exc:
        get_planner("does-not-exist")
    assert exc.value.status_code == 400
